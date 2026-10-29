#!/usr/bin/env python3
"""Exercise the Neo DDR adapter with an independent byte-lane scoreboard."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--split-control', action='store_true', help='Test the Neo split-control adapter')
    p.add_argument('--tag-log2', type=int, choices=range(1,6), default=4)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    adapter='ddr_ui_adapt_split.v' if a.split_control else 'ddr_ui_adapt.v'
    sources=[ROOT/'TESTS/rtl/neo_ddr_adapter_tb.sv',ROOT/'tang/boards/neo'/adapter]
    result={'passed':False,'tag_log2':a.tag_log2,'sources':{str(s.relative_to(ROOT)):hashlib.sha256(s.read_bytes()).hexdigest() for s in sources},'cases':[]}
    try:
        with (out/'build.log').open('w') as f:
            subprocess.run(['verilator','--binary','--timing','-Wno-fatal','-j','2','--top-module','neo_ddr_adapter_tb',f'-GTAG_LOG2={a.tag_log2}','--Mdir',str(out/'obj'),*map(str,sources)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180)
        for seed in (138,20261014,7351):
            r=subprocess.run([str(out/'obj/Vneo_ddr_adapter_tb'),f'+seed={seed}'],capture_output=True,text=True,timeout=30)
            (out/f'seed_{seed}.log').write_text(r.stdout+r.stderr)
            passed=r.returncode==0 and 'PASS reads=' in r.stdout
            result['cases'].append({'seed':seed,'passed':passed})
            if not passed:raise RuntimeError(r.stdout+r.stderr)
            print(r.stdout.splitlines()[0],flush=True)
        result['passed']=True
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
