#!/usr/bin/env python3
"""Freeze expected probe drivers from completed R9, not from active PNR output."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021'))
from audit_geometry_controls import indexed_netlist
from audit_generated import EXPECTED


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent = ROOT / 'tang/impl/console_neo_n56r9_route9_dma_c150'
    vo = parent / 'impl/pnr/console_neo.vo'
    assert sha(vo) == 'd3888d979ae0195b6e0f806e4baa0c255fa5ce288953541090f85d0dc4736b77'
    cc, params, drivers, loads = indexed_netlist(vo)
    rows = []
    for i, net in enumerate(EXPECTED + ['clk_d']):
        assert len(drivers[net]) == 1, (net, drivers[net])
        name, kind, port = drivers[net][0]
        sinks = sorted(loads[net])
        rows.append(dict(net=net, data_i_bit=19-i if i < 20 else None,
            role='captured probe' if i < 20 else 'sample clock',
            application_driver=dict(instance=name, primitive=kind, port=port,
                                    cell=cc[name], parameters=params.get(name, {})),
            parent_load_count=len(sinks), parent_load_pin_counts=dict(Counter(s[2] for s in sinks)),
            parent_load_set_sha256=hashlib.sha256(json.dumps(sinks, separators=(',', ':')).encode()).hexdigest()))
    result = dict(scope='Expected bindings for later final-VO inspection',
        route_output_read=False, postroute_passed=None, hardware_access=False,
        parent=str(parent), parent_vo_sha256=sha(vo), probes=rows,
        generated_data_input_bits=20, generated_memory_width_bits=21,
        captured_trigger=dict(net='ddr_init', generated_port='trig0_i', value=1),
        final_checks=[
            'Require route_result returncode0/statusROUTED_NOT_QUALIFIED and both FS/TR log completion markers before opening outputs.',
            'Hash all final outputs before/after; verify frozen application sources, VG, CST/SDC, Tcl and generated GAO unchanged.',
            'Resolve each original application driver and its signal through any explicit aliases to the added GAO input/load.',
            'Verify capture bit order against routed data registers/RAM and generated readout metadata; do not infer raw21-bit ordering.',
            'Verify the capture path clock traces to clk_d/clk_ibuf, not a CPU/DDR-derived clock; distinguish JTAG control clocks.',
            'Compare selected startup primitive pins/parameters/INIT and application load sets with frozen R9.',
            'Compare global clock/control routes, PLL sites, reset routes, and GAO-only/new whole-design resources.',
            'Run unchanged global qualifier using reviewed route metadata; require all ten parent audit names remain present.',
            'Keep timing/structural FAIL distinct from insertion audit, and do not infer hardware capture success.'],
        input_sha256={str(p): sha(p) for p in [vo, HERE/'result.json',
            HERE.parent/'route9_startup_analysis/r9.json', Path(__file__).resolve()]})
    out = HERE / 'expected_probe_bindings.json'
    with out.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(expected_probes=20, sample_clock='clk_d',
                         final_output_read=False, output_sha256=sha(out))))


if __name__ == '__main__':
    main()
