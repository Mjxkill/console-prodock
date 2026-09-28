#!/usr/bin/env python3
"""Compare the G2/G5 AHB->blitter->256-bit DDR path against byte-level rasterization."""
from pathlib import Path
import random
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('/tmp/console_gpu_accel_test')
W, H, SLOT = 800, 480, 1 << 20


def triangle_pixels(x,y,a,b,sx,sy):
    """Independent half-plane reference, sampled at pixel centres."""
    points=[(x,y),(a,b),(sx,sy)]
    area=(a-x)*(sy-y)-(b-y)*(sx-x)
    if not area:return
    if area<0:points[1],points[2]=points[2],points[1]
    edges=list(zip(points,points[1:]+points[:1]))
    for yy in range(max(0,min(y,b,sy)),min(H-1,max(y,b,sy))+1):
        for xx in range(max(0,min(x,a,sx)),min(W-1,max(x,a,sx))+1):
            covered=True
            for (ax,ay),(bx,by) in edges:
                dx,dy=bx-ax,by-ay
                e=dx*(2*yy+1-2*ay)-dy*(2*xx+1-2*ax)
                if e<0 or (e==0 and not (dy<0 or (dy==0 and dx>0))):
                    covered=False;break
            if covered:yield xx,yy


def main():
    OUT.mkdir(exist_ok=True)
    font = [int(v,16) for v in (ROOT/'tang/rtl/video/font8x16.hex').read_text().split()]
    shutil.copy2(ROOT/'tang/rtl/video/font8x16.hex',OUT/'font8x16.hex')
    for row in range(16):
        font[0x800+row] = 0xa5 if row%2 else 0x5a
    memory = bytearray((i*29+(i>>11)) & 255 for i in range(3*SLOT))
    commands = []
    def base(page):
        return {0:0,1:SLOT,15:2*SLOT}[page]
    def plot(page,x,y,c):
        if 0<=x<W and 0<=y<H:
            memory[base(page)+y*W+x]=c
    def emit(op,x=0,y=0,a=0,b=0,c=0,d=0,sx=0,sy=0,page=0,src=1,text=b''):
        words=[(op<<24)|(page<<20)|(src<<16)|(c<<8)|d,
               ((x&65535)<<16)|(y&65535),((a&65535)<<16)|(b&65535),
               ((sx&65535)<<16)|(sy&65535)]
        words += [int.from_bytes(text[i:i+4].ljust(4,b'\0'),'little') for i in range(0,16,4)]
        commands.extend(words)
        if op in (1,2,3,4):
            if a<=0 or b<=0: return
            n = a-1 if op==2 else b-1 if op==3 else a+b-2
            step=65536 if n==0 else 65536//n
            for yy in range(max(0,y),min(H,y+b)):
                for xx in range(max(0,x),min(W,x+a)):
                    i=xx-x if op==2 else yy-y if op==3 else xx-x+yy-y
                    amount=min(255,(abs(d-c)*i*step)>>16)
                    color=c if op==1 else c-amount if d<c else c+amount
                    plot(page,xx,yy,color)
        elif op==5:
            xx,yy=x,y; dx,dy=abs(a-x),abs(b-y); ex=1 if a>=x else -1; ey=1 if b>=y else -1
            error=dx-dy
            while True:
                plot(page,xx,yy,c)
                if (xx,yy)==(a,b): break
                twice=2*error
                if twice>-dy: error-=dy;xx+=ex
                if twice<dx: error+=dx;yy+=ey
        elif op in (6,7):
            if a<0:return
            xx,yy,error=a,0,1-a
            while xx>=yy:
                if op==6:
                    for px,py in ((x+xx,y+yy),(x-xx,y+yy),(x+xx,y-yy),(x-xx,y-yy),
                                  (x+yy,y+xx),(x-yy,y+xx),(x+yy,y-xx),(x-yy,y-xx)):
                        plot(page,px,py,c)
                else:
                    for py,left,right in ((y+yy,x-xx,x+xx),(y-yy,x-xx,x+xx),
                                          (y+xx,x-yy,x+yy),(y-xx,x-yy,x+yy)):
                        for px in range(max(0,left),min(W-1,right)+1):plot(page,px,py,c)
                yy+=1
                if error<0:error+=2*yy+1
                else:xx-=1;error+=2*(yy-xx)+1
        elif op==8:
            before=bytes(memory[base(src):base(src)+W*H])  # memmove semantics
            for yy in range(max(0,y),min(H,y+b)):
                for xx in range(max(0,x),min(W,x+a)):
                    qx,qy=sx+xx-x,sy+yy-y
                    if 0<=qx<W and 0<=qy<H:plot(page,xx,yy,before[qy*W+qx])
        elif op==10:
            for xx,yy in triangle_pixels(x,y,a,b,sx,sy):plot(page,xx,yy,c)
        elif op==9:
            scale=2 if b==2 else 1
            for i,ch in enumerate(text[:16]):
                for row in range(16):
                    for col in range(8):
                        on=font[ch*16+row] & (128>>col)
                        if not on and d==0:continue
                        for dy in range(scale):
                            for dx in range(scale):plot(page,x+(i*8+col)*scale+dx,y+row*scale+dy,c if on else d)

    emit(1,a=W,b=H,c=0x12)
    rng=random.Random(918)
    # Every destination burst offset, including odd start/end masks.
    for i in range(32):emit(1,x=32+i,y=i*3,a=65-i,b=2,c=33+i)
    for i in range(32):emit(8,x=240+i,y=i*3,a=65-i,b=2,sx=10+31-i,sy=200+i)
    emit(2,x=5,y=110,a=256,b=30,c=0,d=255)
    emit(2,x=-32700,y=145,a=32767,b=4,c=3,d=240)
    emit(3,x=300,y=110,a=80,b=256,c=200,d=10)
    emit(4,x=410,y=110,a=250,b=150,c=7,d=240)
    emit(4,x=-30,y=460,a=100,b=70,c=255,d=3)
    emit(2,x=700,y=100,a=1,b=10,c=17,d=200)
    emit(1,x=25,y=25,a=0,b=20,c=244)
    emit(1,x=-32768,y=10,a=-1,b=1,c=244)
    for points in ((-25,200,600,370),(600,375,20,205),(50,450,55,50),
                   (-32768,400,32767,401),(799,0,799,479)):
        emit(5,x=points[0],y=points[1],a=points[2],b=points[3],c=rng.randrange(256))
    emit(6,x=400,y=350,a=85,c=0xee)
    emit(7,x=130,y=340,a=60,c=0x87)
    emit(7,x=790,y=465,a=50,c=0x61)
    emit(6,x=32760,y=50,a=100,c=0xf7)  # no wrapped coordinates on-screen
    emit(7,x=-32760,y=50,a=100,c=0xf7)
    emit(6,x=10,y=10,a=0,c=0xcc)
    emit(8,x=-8,y=180,a=100,b=30,sx=-3,sy=460)
    emit(8,x=740,y=210,a=100,b=40,sx=790,sy=8)
    emit(8,x=600,y=30,a=32,b=32,sx=-32768,sy=0)
    emit(8,x=600,y=30,a=32,b=32,sx=32767,sy=0)
    # Horizontal, vertical and diagonal overlap, including reverse row traversal.
    emit(8,x=305,y=130,a=70,b=180,sx=301,sy=110,src=0)
    emit(8,x=306,y=109,a=60,b=40,sx=309,sy=120,src=0)
    emit(8,x=40,y=112,a=100,b=12,sx=6,sy=112,src=0)
    emit(1,x=770,y=475,a=100,b=100,c=0xaa,page=15)
    for x,y,t,scale,bg in ((10,5,b'Mega Pro DDR3',1,0),(-13,275,b'clipping',2,3),
                           (650,450,b'right-bottom',2,0),(120,-5,b'top',1,7),
                           (400,300,b'0123456789ABCDEF',2,0),(400,400,b'\x80\x81\x82',1,0)):
        emit(9,x=x,y=y,a=len(t),b=scale,c=255,d=bg,text=t)
    emit(9,x=10,y=20,a=0,b=1,c=255,text=b'')
    # G5: winding, flat edges, clipping, subpixel edge ownership, degeneracy,
    # extreme signed vertices and native DDR byte masks on page 15 as well.
    triangles=[(-32768,-32768,32767,-32768,0,32767),
        (0,0,800,0,800,480),(0,0,800,480,0,480),
        (-5,100,105,101,51,250),(20,20,20,20,20,20),
        (-32768,4,32767,4,0,4),(0,0,1,0,0,1),
        (799,479,800,479,800,480),(800,480,800,479,799,479),
        (32760,32760,32767,32760,32760,32767)]
    for i in range(32):
        triangles.append((32+i,150,110+i,152+i%3,58+i,210))
    for i in range(28):
        triangles.append(tuple(rng.randrange(-80,880) if j%2==0 else rng.randrange(-60,540) for j in range(6)))
    for i,t in enumerate(triangles):
        x,y,a,b,sx,sy=t
        if i%2:a,b,sx,sy=sx,sy,a,b
        emit(10,x=x,y=y,a=a,b=b,sx=sx,sy=sy,c=80+i,page=(0,1,15)[i%3])
    emit(255)  # unknown opcode must complete and increment BAD, without writes
    (OUT/'commands.hex').write_text(''.join(f'{w:08x}\n' for w in commands))
    (OUT/'expected.hex').write_text(''.join(f'{v:02x}\n' for v in memory))
    sources=['TESTS/rtl/gpu_accel_tb.sv','tang/rtl/video/gpu_accel.v','tang/rtl/video/blitter.v',
             'tang/rtl/video/gpu_blit_dma.v','tang/rtl/video/font_ram.v','tang/rtl/video/gpu_triangle.v',
             'tang/rtl/board/ddr_dcfifo.v','tang/rtl/board/cdc_word.v','tang/rtl/board/ddr_gpu_arb.v']
    with (OUT/'build.log').open('w') as log:
        subprocess.run(['verilator','--binary','--timing','-Wno-fatal','--top-module','gpu_accel_tb',
                        '--Mdir',str(OUT/'obj')]+[str(ROOT/s) for s in sources],stdout=log,stderr=log,check=True)
    subprocess.run([str(OUT/'obj/Vgpu_accel_tb'),f'+ncmd={len(commands)//8}','+bad=1'],cwd=OUT,check=True)


if __name__=='__main__':main()
