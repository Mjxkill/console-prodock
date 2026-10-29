#!/usr/bin/env python3
"""Read-only comparison of frozen Neo/Pro Dock USB inputs; no hardware."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
NEO = ROOT / 'tang/impl/console_neo_n56r3/source'
PRO = ROOT / 'tang/impl/gpu_geometry_g22r0/source'
REF = Path('/home/michael/gowin/ref/TangMega-138KPro-example/usb2_soft/usb_uart_loopback/src')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(text):
    return re.sub(r'\s+', '', re.sub(r'//[^\n]*', '', text))


def section(text, start, end):
    value = text[text.index(start):]
    return value[:value.index(end)]


def audit():
    n = (NEO / 'tang/boards/neo/soft_usb.vh').read_text()
    p = (PRO / 'tang/rtl/console_top.v').read_text()
    sections = {}
    for start, end in [
        ('Gowin_PLL_F u_pll_f', 'wire        usb_highspeed'),
        ('USB_Device_Controller_Top u_usb_device_controller_top', '`ifdef CONSOLE_USB_FS_PHY'),
        ('USB2_0_SoftPHY_Top u_usb_softphy_top', '`endif'),
    ]:
        sections[start] = norm(section(n, start, end)) == norm(section(p, start, end))
    ips = {}
    for name in ('usb2_0_softphy', 'usb_device_controller'):
        np, pp, rp = (NEO / 'tang/rtl/usb' / (name + '.v'),
                      PRO / 'tang/rtl/usb' / (name + '.v'), REF / name / (name + '.v'))
        ips[name] = {
            'neo_sha256': sha(np), 'prodock_sha256': sha(pp), 'sipeed_sha256': sha(rp),
            'neo_matches_sipeed': sha(np) == sha(rp),
            'neo_matches_prodock': sha(np) == sha(pp),
            'neo_header': np.read_text().split('`pragma protect', 1)[0],
            'prodock_header': pp.read_text().split('`pragma protect', 1)[0],
            'sipeed_ipc': (rp.parent / (name + '.ipc')).read_text(),
        }
    same, changed = [], []
    for np in sorted((NEO / 'tang/rtl/usb').rglob('*')):
        if not np.is_file():
            continue
        rel = np.relative_to(NEO)
        pp = PRO / rel
        row = {'path': str(rel), 'neo_sha256': sha(np),
               'prodock_sha256': sha(pp) if pp.is_file() else None}
        (same if row['neo_sha256'] == row['prodock_sha256'] else changed).append(row)
    tcl = ROOT / 'tang/impl/console_neo_n56_observe/build.tcl'
    synthesis_log = tcl.parent / 'impl/gwsynthesis/console_neo.log'
    cst = NEO / 'tang/boards/neo/neo.cst'
    evidence = [tcl, synthesis_log, cst, NEO / 'tang/boards/neo/neo.sdc',
                NEO / 'tang/boards/neo/soft_usb.vh', PRO / 'tang/rtl/console_top.v',
                PRO / 'usb_phy_ip/usbtwosoftphy.ipspec', PRO / 'usb_ip/usb_device_controller.ipspec']
    return {
        'hardware_access': False, 'functional_usb_validation': False,
        'compiled_input_lines': [l for l in tcl.read_text().splitlines()
                                 if 'usb2_0_softphy.v}' in l or 'usb_device_controller.v}' in l],
        'synthesis_input_lines': [l for l in synthesis_log.read_text().splitlines()
                                 if l.startswith('Analyzing Verilog file') and
                                 ('usb2_0_softphy.v' in l or 'usb_device_controller.v' in l)],
        'ips': ips, 'normalized_integration_identical': sections,
        'usb_files_identical': same, 'usb_files_changed': changed,
        'neo_usb_constraints': [l for l in cst.read_text().splitlines()
                                if 'usb_' in l or 'u_pll_f' in l or 'u_pll_b' in l or
                                '"phy_clk"' in l or '"fclk_960m"' in l or '"clk48"' in l],
        'evidence_sha256': {str(p): sha(p) for p in evidence},
        'limitations': [
            'Encrypted IP headers and hashes identify different generated artifacts; they do not establish the root cause.',
            'Sipeed IPC target is provenance for matching IP bytes, not proof of incompatibility with GW5AST-138C.',
            'Pin mapping agrees with recorded schematic review; schematics not independently reopened in this audit.',
            'No physical PLL-lock, reset-release, cable, host-enumeration or UTMI activity measurements made.',
            'N56r3 reuses the exact N56 synthesis netlist; the cited N56 Tcl/log establish its USB input provenance.',
        ],
    }


if __name__ == '__main__':
    data = audit()
    out = HERE / 'usb_source_audit.json'
    out.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'output': str(out), 'normalized_integration_identical': data['normalized_integration_identical'],
                      'changed': [x['path'] for x in data['usb_files_changed']],
                      'identical_count': len(data['usb_files_identical'])}, indent=2))
