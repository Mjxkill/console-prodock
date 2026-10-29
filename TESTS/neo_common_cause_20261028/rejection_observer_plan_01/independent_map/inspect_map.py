#!/usr/bin/env python3
"""Read-only structural inventory of the exact R19 diagnostic CSR integration.

This is an inventory, not a netlist equivalence or hardware test. Module/port
assertions prevent silently applying the source-level map to another snapshot.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
BUILD = ROOT / 'tang/impl/console_neo_n56r19_capture_ce_local'
OUT = Path(__file__).resolve().parent


def module(text, name):
    start = re.search(r'^module ' + re.escape(name) + r'\s*\(', text, re.M)
    assert start, name
    end = text.index('endmodule', start.start()) + len('endmodule')
    return text[start.start():end]


def main():
    vg_path = BUILD / 'console_neo.vg'
    vg = vg_path.read_text()
    assert hashlib.sha256(vg_path.read_bytes()).hexdigest() == 'dfac41d80eecaa0b6a3c152d36d8fcdb902060cecbd450647ede445d1c8004b6'
    gpu = module(vg, 'neo_gpu_debug_0')
    scan = module(vg, 'neo_gpu_debug')
    top = module(vg, 'console_neo')
    capture = module(vg, 'neo_capture_bus')
    assert 'neo_capture_bus u_capture_bus (' in gpu
    assert 'neo_capture_bus' not in scan
    assert '.legacy_data(trace_legacy_data[31:0]),.hrdata(debug_hrdata[31:0])' in gpu
    inst = re.search(r'neo_gpu_debug_0 u_gpu_debug \((.*?)\n\);', top, re.S).group(1)
    address_bits = sorted(map(int, re.findall(r'\.bus_haddr_(\d+)\(', inst)))
    assert address_bits == [0, 1, 2, 3, 4, 5, 6, 7, 12, 13, 14]
    experiment = json.loads((BUILD/'experiment.json').read_text())
    assert experiment['gao'] is False
    files = [vg_path, BUILD/'build.tcl', BUILD/'experiment.json',
             BUILD/'source/tang/boards/neo/console_neo.v',
             BUILD/'source/tang/boards/neo/neo_capture_bus.v',
             BUILD/'source/tang/boards/neo/neo_gpu_debug.v',
             BUILD/'source/tang/rtl/board/ahb_exts_bridge.v']
    facts = {
        'hardware': False, 'scope': 'structural inventory plus frozen RTL map; not full equivalence',
        'gpu_address_bits_in_exact_instance': address_bits,
        'capture_in_gpu_debug': True, 'capture_in_scan_debug': False,
        'gao_enabled_in_build_manifest': False,
        'helper_module_sha256': hashlib.sha256(capture.encode()).hexdigest(),
        'gpu_debug_module_sha256': hashlib.sha256(gpu.encode()).hexdigest(),
        'legacy_word_offsets': [hex(4*i) for i in range(17)],
        'ncp_word_offsets': ['0x80','0x84','0x88','0x8c','0x90','0x94','0x98'],
        'unused_aligned_offsets_source_map': [hex(x) for x in list(range(0x44,0x80,4))+list(range(0x9c,0x100,4))],
        'not_free_new_pages': ['0xe9005100 repeats 0xe9005000', '0xe9007000 returns scan mux without page7 select'],
        'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
    }
    (OUT/'evidence.json').write_text(json.dumps(facts, indent=2)+'\n')
    print(json.dumps({'checks': 'PASS', 'hardware': False, 'address_bits': address_bits}))


if __name__ == '__main__':
    main()
