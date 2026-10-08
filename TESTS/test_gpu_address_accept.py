#!/usr/bin/env python3
"""Compare exhaustivement les autorisations AHB extraites des vrais tops."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def select(text):
    block = text.split('gpu_accel u_accel (', 1)[1].split(');', 1)[0]
    return re.search(r'\.hsel\(([^)]+)\)', block)[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    current = ROOT / 'tang/rtl/console_top.v'
    reference = args.reference_root / 'tang/rtl/console_top.v'
    text = current.read_text()
    statements = []
    for name in ('usb_leg_hready', 'blit_address_ready', 'vid_hready'):
        statements.append(re.search(r'(?:wire\s+|assign\s+)' + name + r'\s*=[^;]+;', text)[0])
    bench = '''module address_accept_tb;
reg vid_hsel,usb_trace_selected,blit_selected,scan_hready,blit_hready,usb_trace_hready,usb_msc_hready;
reg [31:0] vid_haddr=0;
wire vid_hready;
''' + '\n'.join(statements) + f'''
wire old_sel = {select(reference.read_text())};
wire new_sel = {select(text)};
initial begin
    for(integer b=0;b<512;b++)begin
        {{vid_hsel,vid_haddr[13:12],usb_trace_selected,blit_selected,scan_hready,
          blit_hready,usb_trace_hready,usb_msc_hready}}=9'(b);
        #1;
        if ((old_sel && blit_hready) !== (new_sel && blit_hready))
            $fatal(1,"AHB address acceptance differs: %b",9'(b));
    end
    $display("PASS 512 AHB address acceptance combinations");
    $finish;
end
endmodule
'''
    path = args.out / 'bench.sv'
    path.write_text(bench)
    with (args.out / 'build.log').open('w') as log:
        subprocess.run(['verilator', '--binary', '--timing', '-Wno-fatal',
                        '--top-module', 'address_accept_tb', '--Mdir', str(args.out / 'obj'),
                        str(path)], stdout=log, stderr=log, check=True)
    result = subprocess.run([str(args.out / 'obj/Vaddress_accept_tb')],
                            capture_output=True, text=True, check=True)
    (args.out / 'simulation.log').write_text(result.stdout + result.stderr)
    (args.out / 'result.json').write_text(json.dumps(dict(passed=True, combinations=512,
        sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (current, reference, path, Path(__file__))}), indent=2) + '\n')
    print(result.stdout, end='')


if __name__ == '__main__':
    main()
