#!/usr/bin/env python3
"""Disque USB contre le modèle officiel du contrôleur Gowin HS 3.3.

Réutilise le banc intégré usb_controller_packet_tb.sv (hôte au niveau UTMI,
descripteur, automate EP0 et FIFO réels du projet) : seules la séquence de
test et les liaisons EP1 sont remplacées. Vérifie les descripteurs du
périphérique composite, Get Max LUN, Bulk-Only Reset, le lecteur sans carte
servi par le matériel, la prise de main du firmware et les transferts bulk EP1
avec ACK perdus, port série EP2 actif. Aucun signal interne du
fournisseur n'est forcé. Simulation numérique : pas de PHY ni de câble.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path('/tmp/console-usb-sim-tools/extracted/usr')
PRIMITIVES = Path('/home/michael/gowin/Gowin_V1.9.12_linux/IDE/simlib/gw5a/prim_sim.v')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit(f'Motif attendu une fois dans le banc : {old!r}')
    return text.replace(old, new)


def parse_configuration(data):
    """Découpe le descripteur de configuration ; retourne ses éléments."""
    items, i = [], 0
    while i < len(data):
        n = data[i]
        if n < 2 or i + n > len(data):
            raise SystemExit(f'Descripteur mal formé à l\'octet {i}')
        items.append(data[i:i + n])
        i += n
    return items


def check_descriptors(log):
    found = {}
    for name in ('DEVICE_DESCRIPTOR', 'QUALIFIER_DESCRIPTOR', 'CONFIG_HEADER', 'CONFIG_DESCRIPTOR'):
        m = re.search(rf'^{name}((?: [0-9a-f]{{2}})+)$', log, re.M)
        if not m:
            raise SystemExit(f'{name} absent du journal')
        found[name] = bytes.fromhex(m[1].replace(' ', ''))
    dev, cfg = found['DEVICE_DESCRIPTOR'], found['CONFIG_DESCRIPTOR']
    errors = []
    if len(dev) != 18 or dev[4:7] != bytes([0xef, 2, 1]):
        errors.append('classe du périphérique : EF/02/01 attendu')
    if dev[8:12] != bytes([0x9f, 0x35, 0x11, 0x20]):
        errors.append('VID:PID 359f:2011 attendu')
    if found['QUALIFIER_DESCRIPTOR'][4:7] != bytes([0xef, 2, 1]):
        errors.append('classe du qualificateur')
    if found['CONFIG_HEADER'] != cfg[:9]:
        errors.append('en-tête de configuration différent du descripteur complet')
    if len(cfg) != 98 or int.from_bytes(cfg[2:4], 'little') != 98 or cfg[4] != 3:
        errors.append('configuration : 98 octets et 3 interfaces attendus')
    items = parse_configuration(cfg)
    kinds = [x[1] for x in items]
    if kinds != [2, 0x0b, 4, 0x24, 0x24, 0x24, 0x24, 5, 4, 5, 5, 4, 5, 5]:
        errors.append(f'suite de descripteurs inattendue : {kinds}')
    else:
        iad, storage, out_ep, in_ep = items[1], items[11], items[12], items[13]
        if iad != bytes([8, 0x0b, 0, 2, 2, 2, 1, 0]):
            errors.append('association d\'interfaces CDC')
        if [items[2][2], items[8][2], storage[2]] != [0, 1, 2]:
            errors.append('numéros d\'interface')
        if storage[4:8] != bytes([2, 8, 6, 0x50]):
            errors.append('interface stockage de masse SCSI Bulk-Only')
        if out_ep[2:6] != bytes([0x01, 2, 0x00, 0x02]) or in_ep[2:6] != bytes([0x81, 2, 0x00, 0x02]):
            errors.append('endpoints bulk EP1 de 512 octets')
        if [items[7][2], items[9][2], items[10][2]] != [0x83, 0x02, 0x82]:
            errors.append('endpoints CDC modifiés')
    return {k: v.hex() for k, v in found.items()}, errors


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog', default=str(TOOLS / 'bin/iverilog'))
    p.add_argument('--vvp', default=str(TOOLS / 'bin/vvp'))
    p.add_argument('--ivl-root', type=Path, default=TOOLS / 'lib/x86_64-linux-gnu/ivl')
    p.add_argument('--controller-model-dir', type=Path,
                   default=ROOT / 'tang/impl/gpu_usb_controller33_hs_msc_model_r1',
                   help='export officiel du contrôleur avec la ROM du descripteur composite')
    p.add_argument('--timeout', type=int, default=600)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    rtl = ROOT / 'tang/rtl'
    stage = a.controller_model_dir.resolve()
    provenance = json.loads((stage / 'provenance.json').read_text())
    if sha(stage / 'usb_device_controller.vg') != provenance['origin_sha256']:
        raise SystemExit('Le modèle HS 3.3 exporté ne correspond plus à son origine')
    for name, h in provenance['source_sha256'].items():
        if sha(stage / name) != h:
            raise SystemExit('Entrée d\'export modifiée : ' + name)
    models = list(stage.glob('export/*/impl/pnr/*.vo'))
    if len(models) != 1:
        raise SystemExit('Un seul modèle officiel exporté attendu')
    base = ROOT / 'TESTS/rtl/usb_controller_packet_tb.sv'
    decl = ROOT / 'TESTS/rtl/usb_msc_controller_decl.svh'
    tasks = ROOT / 'TESTS/rtl/usb_msc_controller_tasks.svh'
    bench = base.read_text()
    start = bench.index('    usb_desc #(')
    end = bench.index('    usb_uart_config u_usb_uart_config', start)
    ports = ('phy_clk RESET usb_txdat endpt0_send usb_txdat_len usb_txcork usb_rxrdy inf_alter_i '
             'usb_busreset usb_highspeed usb_suspend usb_online usb_sof usb_txpop usb_txact usb_txpktfin '
             'usb_rxdat usb_rxval usb_rxact usb_rxpktval setup_active endpt_sel inf_alter_o inf_sel_o inf_set_o '
             'PHY_DATAOUT PHY_TXVALID PHY_TXREADY PHY_DATAIN PHY_RXACTIVE PHY_RXVALID PHY_RXERROR '
             'PHY_LINESTATE PHY_OPMODE PHY_XCVRSELECT PHY_TERMSELECT PHY_RESET').split()
    bench = (bench[:start] + '    USB_HS_Controller_Model u_hs_model(\n'
             + ',\n'.join(f'        .{x}({"controller_dataout" if x=="PHY_DATAOUT" else x})' for x in ports) + '\n    );\n\n' + bench[end:])
    observer = r'u_usb_device_controller_top\.\\u_usb_device_controller/u_usb_device_controller_utmi/(?:usbc_clr_in|isync) \[2\]'
    bench = re.sub(observer, "1'b0", bench)
    bench = replace_once(bench, '    usb_fifo u_usb_fifo (\n',
                         '    `include "usb_msc_controller_decl.svh"\n    usb_fifo u_usb_fifo (\n'
                         '        .i_ep1_tx_clk  (phy_clk),\n'
                         "        .i_ep1_tx_max  (usb_highspeed ? 12'd512 : 12'd64),\n"
                         '        .i_ep1_tx_dval (msc_tx_dval),\n'
                         '        .i_ep1_tx_data (msc_tx_data),\n'
                         '        .i_ep1_flush   (msc_flush),\n'
                         '        .i_ep1_tx_committed(msc_tx_committed),\n'
                         '        .o_ep1_tx_sent (msc_tx_sent),\n'
                         '        .i_ep1_rx_clk  (phy_clk),\n'
                         '        .i_ep1_rx_rdy  (msc_rx_rdy && !msc_halted),\n'
                         '        .o_ep1_rx_dval (msc_rx_dval),\n'
                         '        .o_ep1_rx_data (msc_rx_data),\n')
    bench=replace_once(bench,"? 1'b1 : ep_usb_rxrdy;","? 1'b1 : (endpt_sel==1 && msc_halted) ? 1'b0 : ep_usb_rxrdy;")
    bench=replace_once(bench,"? 1'b0 : ep_usb_txcork;","? 1'b0 : (endpt_sel==1 && msc_halted) ? 1'b1 : ep_usb_txcork;")
    bench = replace_once(bench, '.endpt0_dat_o(endpt0_dat), .endpt0_send_o(endpt0_send),',
                         '.endpt0_dat_o(endpt0_dat), .endpt0_send_o(endpt0_send), .msc_reset_o(msc_bot_reset),')
    bench = replace_once(bench, '    defparam u_usb_uart_config.ENDPT_UART_CONFIG = ENDPT_UART_CONFIG;',
                         '    defparam u_usb_uart_config.ENDPT_UART_CONFIG = ENDPT_UART_CONFIG;\n'
                         '    defparam u_usb_uart_config.MSC = 1;')
    first = bench.index('    initial begin\n        gap(10);reset=0;')
    last = bench.index('    initial begin #30000000;')
    bench = (bench[:first] + '    `include "usb_msc_controller_tasks.svh"\n'
             + '    initial begin #120000000;$fatal(1,"USB disk timeout");end\nendmodule\n')
    del last
    report_stage = str(stage)
    if sha(stage / 'usb_descriptor.v') != sha(rtl / 'usb/usb_descriptor.v'):
        raise SystemExit('Le descripteur du modèle exporté diffère de tang/rtl/usb/usb_descriptor.v : refaire l\'export')
    sources = [rtl / 'usb/uart/usb_uart_config.v',
               rtl / 'usb/sync_fifo/usb_fifo.v', rtl / 'usb/sync_fifo/sync_tx_pkt_fifo.v',
               rtl / 'usb/sync_fifo/sync_rx_pkt_fifo.v', rtl / 'usb/usb_msc_port.v', rtl / 'usb/usb_msc_empty.v', rtl / 'usb/usb_msc_guard.v',
               rtl / 'board/ddr_dcfifo.v', rtl / 'board/cdc_word.v']
    report = {
        'scope': 'Disque USB composite : descripteurs, requêtes de classe et bulk EP1 contre le contrôleur officiel HS 3.3',
        'limits': ['Hôte idéal au niveau UTMI ; ni PHY, ni câble, ni pilote hôte réel',
                   'Simulation numérique ; aucune preuve de timing physique',
                   'Le protocole Bulk-Only/SCSI du firmware n\'est pas simulé ici'],
        'sha256': {str(x): sha(x) for x in [base, decl, tasks, models[0], Path(__file__), *sources]},
        'controller_model': str(models[0]), 'controller_stage': report_stage,
        'provenance': provenance,
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='console-usb-msc-') as tmp:
        tmp = Path(tmp)
        harness = tmp / 'usb_controller_packet_tb.sv'
        harness.write_text(bench)
        (tmp / 'usb_controller_cdc_tasks.svh').write_text(
            re.sub(observer, "1'b0", (ROOT / 'TESTS/rtl/usb_controller_cdc_tasks.svh').read_text()))
        exe = tmp / 'msc.vvp'
        cmd = [a.iverilog, '-B', str(a.ivl_root), '-g2012', '-I', str(tmp), '-I', str(ROOT / 'TESTS/rtl'),
               '-s', 'usb_controller_packet_tb', '-o', str(exe), str(harness),
               *map(str, sources), str(models[0]), str(PRIMITIVES)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        report['compile'] = dict(command=cmd, returncode=result.returncode, stderr=result.stderr[-4000:])
        if result.returncode:
            a.output.write_text(json.dumps(report, indent=2) + '\n')
            raise SystemExit(result.stderr[-4000:])
        log_path = a.output.with_suffix('.log')
        with log_path.open('w') as stream:
            result = subprocess.run([a.vvp, str(exe)], stdout=stream, stderr=subprocess.STDOUT, timeout=a.timeout)
        log = log_path.read_text()
        summary = re.search(r'^PASS USB disk with official controller HS=1.*$', log, re.M)
        report['run'] = dict(returncode=result.returncode, summary=summary[0] if summary else None)
        errors = []
        if summary:
            report['descriptors'], errors = check_descriptors(log)
        report['descriptor_errors'] = errors
        report['pass'] = result.returncode == 0 and summary is not None and not errors
    a.output.write_text(json.dumps(report, indent=2) + '\n')
    if not report['pass']:
        raise SystemExit('ÉCHEC : ' + ('; '.join(errors) or log[-1500:]))
    print(report['run']['summary'])
    print('PASS;', a.output)


if __name__ == '__main__':
    main()
