#!/usr/bin/env python3
"""Exercise registered video bus transactions, backpressure and reset cancellation."""
import argparse
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--out',type=Path,required=True)
a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
with (out/'build.log').open('w') as log:
    subprocess.run(['verilator','--binary','--timing','-Wno-fatal','--top-module','video_bus_stage_tb',
                    '--Mdir',str(out/'obj'),str(ROOT/'TESTS/rtl/video_bus_stage_tb.sv'),
                    str(ROOT/'tang/rtl/video/video_bus_stage.v')],stdout=log,stderr=log,check=True)
with (out/'simulation.log').open('w') as log:
    result=subprocess.run([str(out/'obj/Vvideo_bus_stage_tb')],stdout=log,stderr=log)
print((out/'simulation.log').read_text());result.check_returncode()
