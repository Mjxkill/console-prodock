#!/usr/bin/env python3
"""Exercise AE350 AHB/DDR CDC with drift, phases, bursts and clock stops."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['TESTS/rtl/ahb_ddr_cdc_tb.sv', 'tang/rtl/board/ahb_ddr_cdc.v',
           'tang/rtl/board/ddr_dcfifo.v']
CASES = [(10, 6.667, 0), (10, 6.667, 3.127), (10.02, 6.658, 0.237),
         (9.98, 6.676, 5.137), (6.667, 10, 1.337),
         (4, 4.016064, 0.213), (4.003203, 3.99361, 3.017),
         # DDR-400: CPU DDR bridge is 50 MHz, UI is 100 MHz. Also stress
         # the 80/100 MHz ratio without claiming the CPU bridge runs at 80.
         (10, 5, 0), (10, 5, 3.127), (10.02, 4.995, .237),
         (9.98, 5.005, 4.137), (6.25, 5, 0), (6.25, 5, 2.713)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    path = parser.add_mutually_exclusive_group()
    path.add_argument('--neo-ddr', action='store_true',
                        help='Include both console arbiters and the Neo registered 128/256-bit adapter')
    path.add_argument('--prodock-ddr', action='store_true',
                        help='Include both console arbiters and the unchanged Pro Dock 128/256-bit adapter')
    parser.add_argument('--split-control', action='store_true',
                        help='Use the Neo split-control adapter (requires --neo-ddr)')
    parser.add_argument('--fifo-registers', action='store_true',
                        help='Neo experiment: four-slot AHB FIFOs in explicit registers')
    args = parser.parse_args()
    if args.split_control and not args.neo_ddr:
        parser.error('--split-control requires --neo-ddr')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sources = list(SOURCES)
    if args.fifo_registers:
        sources[2] = 'tang/boards/neo/ddr_dcfifo_registers.v'
    full_path = args.neo_ddr or args.prodock_ddr
    if full_path:
        adapter=('tang/rtl/board/ddr_ui_adapt.v' if args.prodock_ddr else
                 'tang/boards/neo/'+('ddr_ui_adapt_split.v' if args.split_control else 'ddr_ui_adapt.v'))
        sources += ['TESTS/rtl/neo_ddr_cpu_path.sv','tang/rtl/board/ddr_arb.v',
                    'tang/rtl/board/ddr_gpu_arb.v',adapter]
    result = dict(status='running', neo_ddr=args.neo_ddr, prodock_ddr=args.prodock_ddr,
                  split_control=args.split_control, fifo_registers=args.fifo_registers,
                  sources={s: hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources}, cases=[])
    compile_sources = [str(ROOT/s) for s in sources]
    if full_path:
        bench = (ROOT/SOURCES[0]).read_text()
        model_path=ROOT/'TESTS/rtl/neo_ddr_native_model.svh'
        model=model_path.read_text()
        result['sources'][str(model_path.relative_to(ROOT))]=hashlib.sha256(model.encode()).hexdigest()
        begin=bench.index('    byte unsigned mem[')
        end=bench.index('    task automatic wait_ready;')
        bench=bench[:begin]+model+'\n'+bench[end:]
        for old,new in [('reg cr=0,wr=0,rv=0;', 'wire cr,wr,rv;'),
                        ('reg [127:0] rd=0;', 'wire [127:0] rd;'),
                        ('countdown=0; rv=0;', 'countdown=0; native_rv=0;')]:
            if old not in bench:raise ValueError('CDC bench interface changed: '+old)
            bench=bench.replace(old,new)
        expanded=out/'ahb_ddr_cdc_tb.sv';expanded.write_text(bench)
        result['generated_bench_sha256']=hashlib.sha256(bench.encode()).hexdigest()
        compile_sources[0]=str(expanded)
    try:
        with (out/'compile.log').open('w') as log:
            subprocess.run(['verilator', '--binary', '--timing', '-Wno-fatal', '-j', '2',
                            '--top-module', 'ahb_ddr_cdc_tb', '--Mdir', str(out/'obj')]
                           + compile_sources, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=180)
        for i, (hp, up, phase) in enumerate(CASES):
            proc = subprocess.run([str(out/'obj/Vahb_ddr_cdc_tb'), f'+hp={hp}',
                                   f'+up={up}', f'+phase={phase}'], cwd=ROOT,
                                  capture_output=True, text=True, timeout=30)
            (out/f'case{i}.log').write_text(proc.stdout+proc.stderr)
            passed = proc.returncode == 0 and 'PASS hp=' in proc.stdout
            result['cases'].append(dict(hclk_mhz=500/hp, ui_clk_mhz=500/up,
                phase_ns=phase, passed=passed, log=f'case{i}.log'))
            if not passed:
                raise RuntimeError(f'Case {i} failed: {proc.stdout}{proc.stderr}')
            print(proc.stdout.splitlines()[0], flush=True)
        result['status'] = 'pass'
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
