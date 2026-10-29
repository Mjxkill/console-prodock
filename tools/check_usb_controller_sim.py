#!/usr/bin/env python3
"""Check USB DATA toggle/retry behavior with the original controller and FIFO.

The default host is modeled at UTMI. With --serial-phy, data transfers use
the original PHY after a UTMI bootstrap. No vendor internal signal is forced
or modified. This remains a digital test, without an analog cable model.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess
import tempfile
import time
from gowin_toolchain import PRIMITIVES

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = Path('/home/michael/gowin/ref/TangMega-138KPro-example/usb2_soft/usb_uart_loopback/src/usb_device_controller')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog', default='iverilog')
    p.add_argument('--vvp', default='vvp')
    p.add_argument('--ivl-root', type=Path)
    p.add_argument('--rtl-root', type=Path, default=ROOT)
    p.add_argument('--reference', type=Path, default=REFERENCE)
    p.add_argument('--controller-model-dir', type=Path,
                   help='official HS3.3 export with provenance.json and intact .vo')
    p.add_argument('--phy-reference', type=Path,
                   help='directory containing an official usb2_0_softphy.vo model and its companion usb2_0_softphy.v synthesis netlist')
    p.add_argument('--phy-internal-observers', choices=('auto','on','off'),default='auto',
                   help='enable model-specific internal observation only when available; never changes stimulus')
    p.add_argument('--primitives', type=Path, default=PRIMITIVES)
    p.add_argument('--timeout', type=int, default=240)
    p.add_argument('--bare-config', action='store_true', help='test bulk immediately after SET_CONFIGURATION')
    p.add_argument('--ack-delay', type=int, default=20, help='UTMI cycles before host ACK')
    p.add_argument('--serial-phy', action='store_true', help='after UTMI bootstrap, transfer through original PHY D+/D-')
    p.add_argument('--host-ppm', type=float, default=0)
    p.add_argument('--card-ppm', type=float, default=0)
    p.add_argument('--phase-ns', type=float, default=.317)
    p.add_argument('--local-phase-ns', type=float, default=0,
                   help='delay the local 960 MHz clock relative to the 60 MHz clock (ns)')
    p.add_argument('--debug', action='store_true')
    p.add_argument('--bulk-blocks', type=int, default=0,
                   help='0..24 queued 256-byte blocks, lost ACK and FIFO wrap coverage')
    p.add_argument('--interleave-out', action='store_true', help='interleave bulk OUT commands with IN, including an unacknowledged IN')
    p.add_argument('--sof-context', action='store_true', help='inject sparse SOFs across idle and unacknowledged IN contexts')
    p.add_argument('--interrupt-polls', action='store_true', help='poll empty notification EP3 between EP2 IN retries')
    p.add_argument('--cdc-context', action='store_true',
                   help='execute CDC open and exact private diagnostic controls before OUT and during IN retries')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if not 0 <= a.bulk_blocks <= 24:
        p.error('--bulk-blocks must be 0..24')
    if a.phy_reference is not None and not a.serial_phy:
        p.error('--phy-reference requires --serial-phy')
    if not 0 <= a.local_phase_ns < 1000.0 / 60.0:
        p.error('--local-phase-ns must be in [0, 16.666667) ns')
    rtl = a.rtl_root / 'tang/rtl/usb'
    encrypted = rtl / 'usb_device_controller.v'
    reference_encrypted = a.reference / 'usb_device_controller.v'
    if a.controller_model_dir is None and sha(encrypted) != sha(reference_encrypted):
        p.error('Reference synthesis netlist differs from the controller under test')
    sources = [ROOT / 'TESTS/rtl/usb_controller_packet_tb.sv',
               rtl / 'usb_descriptor.v', rtl / 'uart/usb_uart_config.v',
               rtl / 'sync_fifo/usb_fifo.v', rtl / 'sync_fifo/sync_tx_pkt_fifo.v',
               rtl / 'sync_fifo/sync_rx_pkt_fifo.v',
               a.reference / 'usb_device_controller.vo', a.primitives]
    includes=[ROOT/'TESTS/rtl/usb_controller_cdc_tasks.svh']
    observers_enabled=False
    if a.serial_phy:
        phy_reference=a.phy_reference or a.reference.parent/'usb2_0_softphy'
        phy=phy_reference/'usb2_0_softphy.vo'
        phy_encrypted=phy_reference/'usb2_0_softphy.v'
        if sha(phy_encrypted)!=sha(rtl/'usb2_0_softphy.v'):
            p.error('Reference PHY differs from the project')
        sources.append(phy)
        includes += [ROOT/'TESTS/rtl/usb_controller_phy_link.svh',phy_encrypted,rtl/'usb2_0_softphy.v']
        observer_names=['/rx_en_s0 ', '/s_state ', '/q_tx_cnt ']
        phy_text=phy.read_text()
        observers_missing=[name for name in observer_names if name not in phy_text]
        if a.phy_internal_observers=='on' and observers_missing:
            p.error('Selected PHY lacks internal observer signals: '+', '.join(observers_missing))
        observers_enabled=a.phy_internal_observers!='off' and not observers_missing
    hashes = {str(x): sha(x) for x in sources + includes + [encrypted, reference_encrypted]}
    report = {
        'scope': 'HS controller/FIFO DATA toggle, late UART arrival and lost ACK',
        'limits': ['Ideal UTMI receiver/transmitter; no physical PHY or independent serial clock',
                   'Digital simulation only; no metastability, SDF or physical timing proof',
                   'SET_ADDRESS, SET_CONFIGURATION and optional GET_CONFIGURATION; not complete enumeration'],
        'bare_config': a.bare_config, 'ack_delay_cycles': a.ack_delay,
        'interleave_out': a.interleave_out,
        'sof_context': a.sof_context,
        'interrupt_polls': a.interrupt_polls,
        'cdc_context': a.cdc_context,
        'notification_endpoint': 3, 'out_payload_checked': True,
        'bulk_blocks': a.bulk_blocks,
        'sha256': hashes,
    }
    if a.serial_phy:
        report.update(scope='Controller/FIFO with original PHY and independent serial host after UTMI bootstrap',
                      host_ppm=a.host_ppm,card_ppm=a.card_ppm,phase_ns=a.phase_ns,
                      local_phase_ns=a.local_phase_ns,phy_reference=str(phy_reference.resolve()))
        report['internal_observers']=dict(requested=a.phy_internal_observers,enabled=observers_enabled,
                                           available=not observers_missing,missing=observers_missing)
        if a.phy_reference is not None:
            report['scope']='Controller/FIFO with selected official PHY model and independent serial host after UTMI bootstrap'
            report['limits'].append('Alternative PHY model is tied to the RTL by its companion synthesis-netlist hash; no SDF or loaded-bitstream timing equivalence is inferred')
        report['limits'][0]='HS negotiation/enumeration bootstrap uses ideal UTMI; only subsequent packets traverse D+/D-'
        report['limits'].append('Digital ideal CDR; framing differences are recorded separately and prevent a full-link pass')
        report['limits'].append('Response timing uses actual host EOP and device first K from the same simulated transaction; no SDF or physical timing accuracy is inferred from printed decimals')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='console-usb-controller-') as tmp:
        tmp = Path(tmp)
        include_dir = ROOT/'TESTS/rtl'
        if a.controller_model_dir is not None:
            if a.serial_phy:
                p.error('HS3.3 model adapter currently supports UTMI tests only')
            stage = a.controller_model_dir.resolve()
            provenance_path = stage/'provenance.json'
            provenance = json.loads(provenance_path.read_text())
            vendor = stage/'usb_device_controller.vg'
            if sha(vendor) != provenance['origin_sha256']:
                p.error('HS3.3 export VG differs from its recorded origin')
            models = list(stage.glob('export/*/impl/pnr/*.vo'))
            if len(models) != 1:
                p.error('Expected one officially exported controller model')
            for name,h in provenance['source_sha256'].items():
                if sha(stage/name) != h:
                    p.error('Modified export input: '+name)
            model = models[0]
            inputs = [provenance_path,model,*[stage/n for n in provenance['source_sha256']]]
            hashes.update({str(x):sha(x) for x in inputs})
            bench = sources[0].read_text()
            start = bench.index('    usb_desc #(')
            end = bench.index('    usb_uart_config u_usb_uart_config',start)
            ports = ('phy_clk RESET usb_txdat endpt0_send usb_txdat_len usb_txcork usb_rxrdy inf_alter_i '
                     'usb_busreset usb_highspeed usb_suspend usb_online usb_sof usb_txpop usb_txact usb_txpktfin '
                     'usb_rxdat usb_rxval usb_rxact usb_rxpktval setup_active endpt_sel inf_alter_o inf_sel_o inf_set_o '
                     'PHY_DATAOUT PHY_TXVALID PHY_TXREADY PHY_DATAIN PHY_RXACTIVE PHY_RXVALID PHY_RXERROR '
                     'PHY_LINESTATE PHY_OPMODE PHY_XCVRSELECT PHY_TERMSELECT PHY_RESET').split()
            bench = bench[:start]+'    USB_HS_Controller_Model u_hs_model(\n'+',\n'.join(
                '        .'+x+'('+x+')' for x in ports)+'\n    );\n\n'+bench[end:]
            observer = r'u_usb_device_controller_top\.\\u_usb_device_controller/u_usb_device_controller_utmi/(?:usbc_clr_in|isync) \[2\]'
            bench = re.sub(observer,"1'b0",bench)
            harness = tmp/'usb_controller_packet_tb.sv'
            harness.write_text(bench)
            (tmp/'usb_controller_cdc_tasks.svh').write_text(re.sub(
                observer,"1'b0",includes[0].read_text()))
            sources = [harness,*sources[2:-2],model,sources[-1]]
            include_dir = tmp
            report['controller_model'] = dict(stage=str(stage),model=str(model),model_sha256=sha(model),
                                             vendor_sha256=sha(vendor))
            report['limits'].append('HS3.3 model replaces private legacy observers by constants; payload/PID/CRC and FIFO endpoint observation remain real. No internal controller toggle assertion is inferred.')
            report['generated_harness_sha256'] = sha(harness)
        executable = Path(tmp) / 'controller.vvp'
        cmd = [a.iverilog]
        if a.ivl_root:
            cmd += ['-B', str(a.ivl_root)]
        cmd += ['-g2012', '-I',str(include_dir), '-I',str(ROOT/'TESTS/rtl'), '-s', 'usb_controller_packet_tb', '-o', str(executable)]
        if a.serial_phy:
            cmd+=['-DWITH_SERIAL_PHY']
            if observers_enabled:
                cmd+=['-DPHY_INTERNAL_OBSERVERS']
        cmd += list(map(str, sources))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        report['compile'] = dict(command=cmd, returncode=result.returncode,
                                 stdout=result.stdout, stderr=result.stderr)
        a.output.write_text(json.dumps(report, indent=2) + '\n')
        if result.returncode:
            raise SystemExit(result.stderr)
        start = time.monotonic()
        try:
            cmd = [a.vvp, str(executable), f'+ACK_DELAY={a.ack_delay}']
            cmd += [f'+HOST_PPM={a.host_ppm}',f'+CARD_PPM={a.card_ppm}',f'+PHASE_NS={a.phase_ns}',
                    f'+LOCAL_PHASE_NS={a.local_phase_ns}']
            if a.bare_config:
                cmd += ['+BARE_CONFIG']
            if a.debug:
                cmd += ['+DEBUG']
            if a.bulk_blocks:
                cmd += [f'+BULK_BLOCKS={a.bulk_blocks}']
            if a.interleave_out:
                cmd += ['+INTERLEAVE_OUT']
            if a.sof_context:
                cmd += ['+SOF_CONTEXT']
            if a.interrupt_polls:
                cmd += ['+INTERRUPT_POLLS']
            if a.cdc_context:
                cmd += ['+CDC_CONTEXT']
            log_path=a.output.with_suffix('.log')
            with log_path.open('w') as stream:
                result = subprocess.run(cmd, stdout=stream, stderr=subprocess.STDOUT, timeout=a.timeout)
            stdout=log_path.read_text()
            report['run'] = dict(returncode=result.returncode, stdout=stdout,
                                 stderr='', elapsed_s=time.monotonic() - start)
            report['pass'] = result.returncode == 0 and 'PASS controller/FIFO retries HS=1' in stdout
            fin = re.search(r'FIN_ENDPOINT_SUMMARY events=(\d+) mismatches=(\d+)', stdout)
            report['fin_endpoint_observation'] = dict(events=int(fin[1]),mismatches=int(fin[2])) if fin else None
            if a.bulk_blocks:
                bulk = re.search(r'BULK_BLOCKS_PASS blocks=(\d+) full64_packets=(\d+) produced=(\d+) delivered=(\d+)', stdout)
                report['bulk_block_check'] = dict(zip(('blocks','full64_packets','produced','delivered'),map(int,bulk.groups()))) if bulk else None
                report['pass'] = report['pass'] and bulk is not None and int(bulk[1])==a.bulk_blocks
            if a.cdc_context:
                controls=re.search(r'CDC CONTEXT PASS: controls=(\d+) controls_during_pending=(\d+)',stdout)
                report['cdc_controls_checked']=int(controls[1]) if controls else None
                report['cdc_controls_during_pending']=int(controls[2]) if controls else None
                report['pass']=report['pass'] and controls is not None
                report['limits'].append('CDC diagnostic payload is a fixed byte ramp; live console counters are not simulated')
            if a.serial_phy:
                report['payload_pass']=report['pass']
                framing=re.search(r'framing_differences=(\d+)',stdout)
                report['framing_differences']=int(framing[1]) if framing else None
                report['pass']=report['pass'] and report['framing_differences']==0
                timings=[]
                for line in stdout.splitlines():
                    if not line.startswith('RESPONSE_TIMING '):
                        continue
                    row=dict(re.findall(r'(\w+)=([^ ]+)',line))
                    for key in ('host_seq','endpoint'):
                        row[key]=int(row[key])
                    for key in ('host_eop_ns','first_k_ns','response_delay_ns','first_k_width_ns','eop_tail_ns'):
                        row[key]=float(row[key])
                    row['exceeds_nominal_192_bits']=row['response_delay_ns']>400.0
                    timings.append(row)
                groups=[]
                for host,token,ep,response in sorted({(t['host_pid'],t['token_pid'],t['endpoint'],t['response_pid']) for t in timings}):
                    rows=[t for t in timings if (t['host_pid'],t['token_pid'],t['endpoint'],t['response_pid'])==(host,token,ep,response)]
                    delays=[t['response_delay_ns'] for t in rows]
                    groups.append(dict(host_pid=host,token_pid=token,endpoint=ep,response_pid=response,count=len(rows),
                                       min_ns=min(delays),max_ns=max(delays),mean_ns=sum(delays)/len(delays),
                                       exceeds_nominal_192_bits=sum(t['exceeds_nominal_192_bits'] for t in rows)))
                report['response_timing']=dict(measurement='host electrical EOP to first device K, same transaction',
                                               nominal_budget_bits=192,nominal_budget_ns=400.0,
                                               timing_changes_stimulus=False,groups=groups,transactions=timings)
        except subprocess.TimeoutExpired as exc:
            report['run'] = dict(timeout=True, elapsed_s=time.monotonic() - start,
                                 stdout=log_path.read_text(), stderr='')
            report['pass'] = False
    report['sources_unchanged'] = all(sha(Path(x)) == h for x, h in hashes.items())
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    print(report['run']['stdout'][-6000:])
    print(('PASS' if report['pass'] else 'FAIL') + f'; {a.output}')
    return 0 if report['pass'] and report['sources_unchanged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
