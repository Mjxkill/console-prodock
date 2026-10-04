#!/usr/bin/env python3
"""Run actual firmware RGB/depth scene commands against its pixel reference."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--perspective',action='store_true')
    args=p.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    sources=['TESTS/rtl/gpu_accel_tb.sv','tang/rtl/video/gpu_accel.v','tang/rtl/video/blitter.v',
        'tang/rtl/video/gpu_raster.v','tang/rtl/video/gpu_v1.v','tang/rtl/video/gpu_texture_cache.v','tang/rtl/video/gpu_copy565.v','tang/rtl/video/gpu_perspective.v','tang/rtl/video/gpu_triangle.v','tang/rtl/video/gpu_blit_dma.v',
        'tang/rtl/video/font_ram.v','tang/rtl/board/ddr_dcfifo.v','tang/rtl/board/cdc_word.v',
        'tang/rtl/board/ddr_gpu_arb.v']
    with (out/'build.log').open('w') as log:
        subprocess.run(['verilator','--binary','--timing','-Wno-fatal','--top-module','gpu_accel_tb',
            '-GDEPTH_SLOT=8','--Mdir',str(out/'obj')]+[str(ROOT/s) for s in sources],stdout=log,stderr=log,check=True)
    for pose in range(4):
        run=out/f'pose{pose}';run.mkdir(exist_ok=True)
        subprocess.run([sys.executable,str(ROOT/'tools/render_gpu_raster.py'),'--out',str(run),'--angle',str(pose*37),'--reverse',str(pose&1)]+(['--perspective'] if args.perspective else []),check=True)
        commands=[15<<24,15,(17<<16)|19,(64<<16)|64,10,0,0,0]
        data=(run/'commands.bin').read_bytes();commands += [int.from_bytes(data[i:i+4],'little') for i in range(0,len(data),4)]
        memory=bytearray((i*29+(i>>11))&255 for i in range(3*1048576))
        memory[:768000]=(run/'color.bin').read_bytes()
        memory[1048576:1048576+768000]=(run/'depth.bin').read_bytes()
        for y in range(64):
            for x in range(64):
                c=65535 if x<2 or x>=62 or y<2 or y>=62 else 0 if (x//8+y//8)%5==0 else (((x*31)//63)<<11)|(y<<5)|(((x^y)&63)//2)
                at=2*1048576+2*((y+19)*800+x+17);memory[at:at+2]=c.to_bytes(2,'little')
        (run/'commands.hex').write_text(''.join(f'{w:08x}\n' for w in commands))
        (run/'expected.hex').write_text(''.join(f'{v:02x}\n' for v in memory))
        shutil.copy2(ROOT/'tang/rtl/video/font8x16.hex',run/'font8x16.hex')
        with (run/'simulation.log').open('w') as log:
            r=subprocess.run([str(out/'obj/Vgpu_accel_tb'),f'+ncmd={len(commands)//8}','+rgbinit=2','+raster_bad=0'],cwd=run,stdout=log,stderr=log)
        print((run/'simulation.log').read_text(),flush=True);r.check_returncode()
if __name__=='__main__':main()
