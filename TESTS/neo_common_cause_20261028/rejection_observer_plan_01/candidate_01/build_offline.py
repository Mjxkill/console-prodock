#!/usr/bin/env python3
"""Map only the observation helpers and run local simulation; no P&R or hardware."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BIN = ROOT / 'optimizer/.tools/oss-cad-suite/bin'
PRIM = Path('/home/michael/gowin/Gowin_V1.9.12_linux/IDE/simlib/gw5a/prim_sim.v')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log, timeout=120):
    with log.open('x') as stream:
        p = subprocess.run(list(map(str, args)), stdout=stream, stderr=subprocess.STDOUT,
                           timeout=timeout, cwd=ROOT)
    assert p.returncode == 0, (args, log, p.returncode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    assert out.parent == HERE
    out.mkdir(exist_ok=False)
    records = {}
    for top in ('neo_reject_witness', 'neo_rjc_readback'):
        source = HERE / (top + '.v')
        script = (f'read_verilog {source}; synth_gowin -family gw5a -strict-gw5a-dffs '
                  f'-top {top} -nobram -nolutram -noiopads; '
                  f'write_verilog -simple-lhs -decimal -attr2comment -defparam {out}/{top}_mapped.v; '
                  f'write_json {out}/{top}.json')
        ys = out / (top + '.ys')
        ys.write_text(script + '\n')
        run([BIN/'yosys', '-Q', '-T', '-s', ys], out/(top+'.log'))
        data = json.loads((out/(top+'.json')).read_text())['modules'][top]
        counts = Counter(c['type'] for c in data['cells'].values())
        allowed = {'DFFRE','ALU','LUT1','LUT2','LUT3','LUT4','MUX2_LUT5','MUX2_LUT6',
                   'MUX2_LUT7','MUX2_LUT8','VCC','GND','$scopeinfo'}
        assert set(counts) <= allowed, counts
        if top == 'neo_reject_witness':
            for cell in data['cells'].values():
                if cell['type'] == 'DFFRE':
                    assert cell['connections']['CLK'] == data['ports']['clk']['bits']
        else:
            assert counts['DFFRE'] == 0
        records[top] = {'source_sha256': sha(source), 'cell_counts': dict(counts),
                        'mapped_sha256': sha(out/(top+'_mapped.v'))}
    tb = HERE / 'tb_reject_witness.sv'
    for mapped in (False, True):
        mode = 'mapped' if mapped else 'rtl'
        sources = [out/'neo_reject_witness_mapped.v', PRIM] if mapped else [HERE/'neo_reject_witness.v']
        command = [BIN/'iverilog','-g2012','-s','tb','-o',out/(mode+'.vvp')]
        if mapped:
            command += ['-DMAPPED']
        run(command + sources + [tb], out/(mode+'_compile.log'))
        run([BIN/'vvp', out/(mode+'.vvp')], out/(mode+'_test.log'))
        expected = 'RESULT PASS cases=15' if mapped else 'RESULT PASS cases=17'
        assert expected in (out/(mode+'_test.log')).read_text()
    result = {'passed': True, 'hardware': False, 'full_design_mapped': False,
              'routing': False, 'rtl_cases': 17, 'mapped_cases': 15,
              'overflow_cases': 'RTL only; direct internal force omitted in mapped simulation',
              'helpers': records, 'tools': {str(p):sha(p) for p in
                                          (BIN/'yosys',BIN/'iverilog',BIN/'vvp',PRIM)},
              'inputs': {str(p.relative_to(HERE)):sha(p) for p in
                         (Path(__file__),tb,HERE/'neo_reject_witness.v',HERE/'neo_rjc_readback.v')}}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
