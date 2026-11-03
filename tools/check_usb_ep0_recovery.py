#!/usr/bin/env python3
"""HS EP0 recovery against the intact original official controller model.

Reuse the existing integrated controller/FIFO harness, replace only its test
sequence, and match the current production EP0-ready override. No vendor
internal state is forced. Neither production RTL nor a build stage is edited.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from vendor_reference import USB as SIPEED_USB
import subprocess
import tempfile
import time
from gowin_toolchain import PRIMITIVES

ROOT = Path(__file__).resolve().parents[1]
REF = SIPEED_USB / 'usb_device_controller'
IVBASE = Path('/tmp/console-usb-sim-tools/extracted/usr')
CASES = {'normal': 0, 'retry7': 1, 'retry32': 2, 'preempt_wait': 3, 'preempt_sent': 4}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=CASES, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--timeout', type=int, default=180)
    p.add_argument('--config-rtl', type=Path,
                   help='immutable baseline CDC handler for before/after comparison')
    p.add_argument('--controller-model-dir', type=Path,
                   help='official HS3.3 export stage containing provenance.json and intact .vo')
    a = p.parse_args()
    base = ROOT/'TESTS/rtl/usb_controller_packet_tb.sv'
    tasks = ROOT/'TESTS/rtl/usb_ep0_recovery_tasks.svh'
    includes = ROOT/'TESTS/rtl/usb_controller_cdc_tasks.svh'
    rtl = ROOT/'tang/rtl/usb'
    original = rtl/'usb_device_controller.v'
    if a.controller_model_dir is None and sha(original) != sha(REF/'usb_device_controller.v'):
        p.error('Controller reference does not match project synthesis netlist')
    config = a.config_rtl or rtl/'uart/usb_uart_config.v'
    sources = [rtl/'usb_descriptor.v', config,
               rtl/'sync_fifo/usb_fifo.v', rtl/'sync_fifo/sync_tx_pkt_fifo.v',
               rtl/'sync_fifo/sync_rx_pkt_fifo.v', REF/'usb_device_controller.vo',
               PRIMITIVES]
    hashes = {str(x):sha(x) for x in [base,tasks,includes,original,REF/'usb_device_controller.v',Path(__file__),*sources]}
    text = base.read_text()
    auxiliary_text = includes.read_text()
    start = text.index('    initial begin\n        gap(10);reset=0;')
    end = text.index('    initial begin #30000000;', start)
    text = text[:start]+'    `include "usb_ep0_recovery_tasks.svh"\n'+text[end:]
    old = '    assign usb_rxrdy     = ep_usb_rxrdy;'
    new = "    assign usb_rxrdy     = (endpt_sel == ENDPT_UART_CONFIG) ? 1'b1 : ep_usb_rxrdy;"
    if text.count(old) + text.count(new) != 1:
        p.error('Unexpected base harness EP0 ready connection')
    text = text.replace(old, new)
    # Older snapshots lack the acknowledgment input. A baseline comparison
    # must compile that original interface, without altering its source.
    fin = '        .usb_txpktfin(usb_txpktfin),\n'
    if 'input              usb_txpktfin' not in config.read_text():
        text = text.replace(fin, '')
    elif fin not in text:
        old = '.usb_txact(usb_txact), .usb_txpop(usb_txpop),'
        if text.count(old) != 1:
            p.error('Unexpected CDC handler instantiation')
        text = text.replace(old, old+' .usb_txpktfin(usb_txpktfin),')
    report = dict(scope='HS EP0 class requests, UTMI + intact official controller model + real application RTL',
                  case=a.case, sha256=hashes,
                  limits=['Original Sipeed HS controller model, not the newly generated HS 3.3 controller',
                          'Ideal UTMI, no PHY, cable, analog effects or physical timing',
                          'Normal SET_ADDRESS/SET_CONFIGURATION bootstrap, not complete descriptor enumeration',
                          'This does not establish the cause of the physical bulk insertion/loss'],
                  harness_changes=['Replace test sequence by usb_ep0_recovery_tasks.svh',
                                   'EP0 RXRDY forced high exactly as current production top'])
    if a.controller_model_dir is not None:
        stage = a.controller_model_dir.resolve()
        provenance_path = stage/'provenance.json'
        provenance = json.loads(provenance_path.read_text())
        vendor = stage/'usb_device_controller.vg'
        if sha(vendor) != provenance['origin_sha256']:
            p.error('HS3.3 export VG differs from its recorded origin')
        model_paths = list(stage.glob('export/*/impl/pnr/*.vo'))
        if len(model_paths) != 1:
            p.error('Expected one officially exported controller model')
        model = model_paths[0]
        for name,h in provenance['source_sha256'].items():
            if sha(stage/name) != h:
                p.error('Modified export input: '+name)
        model_sources = [stage/name for name in provenance['source_sha256']]
        hashes.update({str(x):sha(x) for x in [provenance_path,model,*model_sources]})
        sources = [config, rtl/'sync_fifo/usb_fifo.v', rtl/'sync_fifo/sync_tx_pkt_fifo.v',
                   rtl/'sync_fifo/sync_rx_pkt_fifo.v', model, sources[-1]]
        start = text.index('    usb_desc #(')
        end = text.index('    usb_uart_config u_usb_uart_config',start)
        ports = ('phy_clk RESET usb_txdat endpt0_send usb_txdat_len usb_txcork usb_rxrdy inf_alter_i '
                 'usb_busreset usb_highspeed usb_suspend usb_online usb_sof usb_txpop usb_txact usb_txpktfin '
                 'usb_rxdat usb_rxval usb_rxact usb_rxpktval setup_active endpt_sel inf_alter_o inf_sel_o inf_set_o '
                 'PHY_DATAOUT PHY_TXVALID PHY_TXREADY PHY_DATAIN PHY_RXACTIVE PHY_RXVALID PHY_RXERROR '
                 'PHY_LINESTATE PHY_OPMODE PHY_XCVRSELECT PHY_TERMSELECT PHY_RESET').split()
        text = text[:start]+'    USB_HS_Controller_Model u_hs_model(\n'+',\n'.join(
            '        .'+x+'('+x+')' for x in ports)+'\n    );\n\n'+text[end:]
        # Observer fields belong to the original flattened model. The new
        # EP0 sequence judges public bytes/PID/CRC/status, never these fields.
        observer = r'u_usb_device_controller_top\.\\u_usb_device_controller/u_usb_device_controller_utmi/(?:usbc_clr_in|isync) \[2\]'
        text = re.sub(observer,"1'b0",text)
        auxiliary_text = re.sub(observer,"1'b0",auxiliary_text)
        report['limits'][0] = 'Exact HS3.3 VG exported officially with the actual descriptor ROM; BOS inputs tied to zero in the export wrapper'
        report['limits'].append('Private legacy observer fields are replaced by constant display values; verdicts use public EP0 transactions only')
        report['controller_model'] = dict(stage=str(stage), model=str(model), model_sha256=sha(model),
                                         vendor_sha256=sha(vendor))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='console-usb-ep0-recovery-') as td:
        td = Path(td)
        harness = td/'usb_controller_packet_tb.sv'
        harness.write_text(text)
        (td/'usb_controller_cdc_tasks.svh').write_text(auxiliary_text)
        report['generated_harness_sha256'] = sha(harness)
        exe = td/'test.vvp'
        cmd = [str(IVBASE/'bin/iverilog'), '-B', str(IVBASE/'lib/x86_64-linux-gnu/ivl'),
               '-g2012', '-I', str(td), '-I', str(ROOT/'TESTS/rtl'), '-s', 'usb_controller_packet_tb', '-o', str(exe),
               str(harness), *map(str,sources)]
        c = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        report['compile'] = dict(command=cmd, returncode=c.returncode, stdout=c.stdout, stderr=c.stderr)
        report['pass'] = False
        if c.returncode == 0:
            begin = time.monotonic()
            cmd = [str(IVBASE/'bin/vvp'), str(exe), f'+RECOVERY_CASE={CASES[a.case]}']
            log = a.output.with_suffix('.log')
            try:
                with log.open('w') as stream:
                    run = subprocess.run(cmd, stdout=stream, stderr=subprocess.STDOUT, timeout=a.timeout)
                report['run'] = dict(command=cmd, returncode=run.returncode, elapsed_s=time.monotonic()-begin,
                                     stdout=log.read_text())
                report['pass'] = run.returncode==0 and 'PASS HS EP0 recovery' in report['run']['stdout']
            except subprocess.TimeoutExpired:
                report['run'] = dict(command=cmd, timeout=True, elapsed_s=time.monotonic()-begin,
                                     stdout=log.read_text())
            print(report['run']['stdout'][-5000:])
        else:
            print(c.stderr)
    report['sources_unchanged'] = all(sha(Path(path))==h for path,h in hashes.items())
    a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(('PASS' if report['pass'] else 'FAIL')+f'; {a.output}')
    return 0 if report['pass'] and report['sources_unchanged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
