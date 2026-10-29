#!/usr/bin/env python3
"""Extend the immutable R3 routed test with the exact register-only CAMERA cases.

No hardware, DMA, SDF, retiming, primitive substitution or source change.
The root-owned hardware script is parsed for its pure camera_cases function;
its imports and probe.main() are never executed.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
BASE = HERE / 'n56r3_full_routed'
CASES_SOURCE = HERE.parent / 'n56r3_validation_20261021/probe_camera_configs.py'
OUT = HERE / 'n56r3_camera_routed'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    evidence = json.loads((BASE / 'result.json').read_text())
    if not evidence['passed']:
        raise ValueError('Base routed test must pass')
    for name, expected in evidence['sha256'].items():
        if sha(Path(name)) != expected:
            raise ValueError('Changed base evidence: ' + name)
    tree = ast.parse(CASES_SOURCE.read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'camera_cases']
    if len(functions) != 1:
        raise ValueError('Expected one pure camera_cases function')
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(CASES_SOURCE), 'exec'), namespace)
    cases = namespace['camera_cases']()
    if len(cases) != 21:
        raise ValueError('Changed camera suite requires review')
    # Keep the original timing, AHB transactions and memory-request assertion.
    prefix = (BASE / 'tb.sv').read_text().split(' // preflight\n')[0]
    if not prefix.endswith('read_reg(\'h5000,value);if(value!==32\'h4e474442)$fatal(1,"Wrong debug ID %h",value);\n'):
        raise ValueError('Unexpected original bench boundary')
    prefix = prefix.replace('integer checks=0;', 'integer waits;integer checks=0;')
    bench = prefix
    rejected = 0
    invalid = 0
    for index, case in enumerate(cases, 1):
        name = case['name']
        words = case['words']
        if len(words) != 8 or words[0] >> 24 not in (22, 32):
            raise ValueError('Only TARGET and CAMERA configurations allowed')
        rejected += not case['accepted']
        invalid += not case['accepted'] and words[0] >> 24 == 32
        bench += f' // {name}\n'
        for word in words:
            bench += f" write_reg('h1010,32'h{word:08x});\n"
        bench += f""" waits=0;value=0;
 while(value!==32'd{index} && waits<1000)begin
  read_reg('h1008,value);waits=waits+1;
 end
 if(value!==32'd{index})$fatal(1,"{name} fence %h",value);
 read_reg('h1034,value);if(value!==32'd{int(rejected)})$fatal(1,"{name} rejected %h expected {int(rejected)}",value);
 read_reg('h104c,value);if(value!==32'd{int(invalid)})$fatal(1,"{name} geometry invalid %h expected {int(invalid)}",value);
 checks++;
 $display("Camera routed checks=%0d ({name})",checks);$fflush();
"""
    bench += """ $display("PASS routed CAMERA: 21 configurations, zero DMA, exact rejection counters");$finish;
end
initial begin #1000000;$fatal(1,"Watchdog");end
endmodule
"""
    OUT.mkdir(exist_ok=False)
    testbench = OUT / 'tb.sv'
    testbench.write_text(bench)
    compile_cmd = evidence['compile_command'].copy()
    compile_cmd[compile_cmd.index('-o') + 1] = str(OUT / 'sim.vvp')
    compile_cmd[compile_cmd.index(str(BASE / 'tb.sv'))] = str(testbench)
    sim_cmd = [evidence['simulation_command'][0], str(OUT / 'sim.vvp')]
    result = dict(passed=False, cases=cases, source_netlist_sha256=evidence['source_netlist_sha256'],
        scope=__doc__, base_result_sha256=sha(BASE / 'result.json'), hardware_access=False,
        sha256={str(p): sha(p) for p in [Path(__file__), CASES_SOURCE, testbench, BASE / 'routed.v']},
        compile_command=compile_cmd, simulation_command=sim_cmd)
    try:
        for cmd, name, timeout in [(compile_cmd, 'compile.log', 180), (sim_cmd, 'simulation.log', 600)]:
            with (OUT / name).open('w') as log:
                subprocess.run(cmd, stdout=log, stderr=log, check=True, timeout=timeout)
        result['passed'] = 'PASS routed CAMERA: 21 configurations' in (OUT / 'simulation.log').read_text()
    finally:
        (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print((OUT / 'simulation.log').read_text())
    if not result['passed']:
        raise SystemExit('Routed CAMERA test failed')


if __name__ == '__main__':
    main()
