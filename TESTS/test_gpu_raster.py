#!/usr/bin/env python3
"""Independent pixel/depth reference through AHB + both DDR clients + stalls."""
import argparse
from pathlib import Path
import random
import shutil
import subprocess
from test_gpu_accel import triangle_pixels

ROOT=Path(__file__).resolve().parents[1]
W,H,SLOT=800,480,1<<20

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();out=args.out;out.mkdir(parents=True,exist_ok=True)
    memory=bytearray((i*29+(i>>11))&255 for i in range(3*SLOT))
    def base(page):return {0:0,1:SLOT,15:2*SLOT}[page]
    def get(page,x,y):
        at=base(page)+2*(y*W+x);return int.from_bytes(memory[at:at+2],'little')
    def put(page,x,y,c):
        at=base(page)+2*(y*W+x);memory[at:at+2]=c.to_bytes(2,'little')
    for y in range(H):
        for x in range(W):
            c=0 if (x//4+y//4)%5==0 else (((x*3+y)&31)<<11)|(((x+2*y)&63)<<5)|((x^y)&31)
            put(15,x,y,c)
    commands=[];state=None;texture=None;planes={};rejected=0
    def signed(n):return n-(1<<32) if n&(1<<31) else n
    def emit(op,*args,header=0):
        nonlocal state,texture,rejected
        w=[(op<<24)|header]+[x&0xffffffff for x in args]
        w += [0]*(8-len(w));assert len(w)==8;commands.extend(w)
        valid=header==0
        if op==14:
            valid &= w[1]<256 and (w[1]&15)!=(w[1]>>4) and (w[2]<32 and (not(w[2]&16) or bool(w[2]&1))) and w[3]<=256 and w[4]<65536 and not any(w[5:])
            state=(w[1]&15,w[1]>>4,w[2],w[3],w[4]) if valid else None
        elif op==15:
            sx,sy=w[2]>>16,w[2]&65535;sw,sh=w[3]>>16,w[3]&65535
            mu,mv=w[4]&3,(w[4]>>2)&3
            valid &= w[1]<16 and w[4]<16 and not any(w[5:]) and 1<=sw<=128 and 1<=sh<=128 and sx+sw<=W and sy+sh<=H
            valid &= mu!=3 and mv!=3 and (mu!=1 or sw&(sw-1)==0) and (mv!=1 or sh&(sh-1)==0)
            texture=([[get(w[1],sx+x,sy+y) for x in range(sw)] for y in range(sh)],mu,mv) if valid else None
        elif op in (16,17,18,21):
            valid &= w[4]<0x20000 and (w[4]==0 or bool(w[4]&0x10000)) and not any(w[5:])
            origin=((w[4]&65535)<<32)|w[1]
            if origin&(1<<47):origin-=1<<48
            if not w[4]&0x10000:origin=w[1] if op==18 else signed(w[1])
            planes[op]=(origin,signed(w[2]),signed(w[3])) if valid else None
        elif op==20:
            valid &= state is not None and w[1]<4 and w[2]<65536 and w[3]<65536 and not any(w[4:])
            if valid:
                for bit,page,c in ((1,state[0],w[2]),(2,state[1],w[3])):
                    if w[1]&bit:memory[base(page):base(page)+W*H*2]=c.to_bytes(2,'little')*(W*H)
        elif op==19:
            valid &= state is not None and not any(w[4:])
            if state:
                cp,zp,flags,a,color=state
                valid &= not(flags&1) or (texture is not None and planes.get(16) is not None and planes.get(17) is not None)
                valid &= not(flags&6) or planes.get(18) is not None
                valid &= not(flags&16) or planes.get(21) is not None
            if valid and a:
                xy=[]
                for v in w[1:4]:
                    xy.extend(vv-65536 if vv&32768 else vv for vv in (v>>16,v&65535))
                for x,y in triangle_pixels(*xy):
                    c=color
                    if flags&16:
                        qo,qx,qy=planes[21]
                        if qo+x*qx+y*qy<=0:continue
                    if flags&1:
                        pixels,mu,mv=texture;sh=len(pixels);sw=len(pixels[0]);uv=[]
                        for op,size,mode in ((16,sw,mu),(17,sh,mv)):
                            origin,dx,dy=planes[op]
                            denominator=65536
                            if flags&16:
                                qo,qx,qy=planes[21];denominator=qo+x*qx+y*qy
                            q=(origin+x*dx+y*dy)//denominator if denominator>0 else -1000000000
                            uv.append(q%size if mode==1 else min(size-1,max(0,q)) if mode==2 else q)
                        u,v=uv
                        if not(0<=u<sw and 0<=v<sh):continue
                        c=pixels[v][u]
                    if flags&8 and c==0:continue
                    depth=0
                    if flags&6:
                        origin,dx,dy=planes[18];depth=(origin+x*dx+y*dy)//65536
                        if not 0<=depth<=65535:continue
                        if flags&2 and depth>=get(zp,x,y):continue
                    old=get(cp,x,y);result=0
                    for shift,mask in ((11,31),(5,63),(0,31)):
                        result|=((((c>>shift)&mask)*a+((old>>shift)&mask)*(256-a)+128)//256)<<shift
                    put(cp,x,y,result)
                    if flags&4:put(zp,x,y,depth)
        else:raise AssertionError(op)
        if not valid:rejected+=1
    def config(flags=0,alpha=256,color=0xf800,page=0,zpage=1):emit(14,page|(zpage<<4),flags,alpha,color)
    def triangle(points):emit(19,*[((x&65535)<<16)|(y&65535) for x,y in points])
    def plane(op,o=0,dx=0,dy=0):emit(op,o,dx,dy)
    config();emit(20,3,0x2104,65535)
    # Every native halfword lane, both full and partial masks; all alpha extrema.
    for i,a in enumerate((0,1,16,64,127,128,192,255,256)):
        config(alpha=a,color=(0xffff if i%2 else 0xf81f))
        x=3+i*65;triangle([(x,5),(x+60,5),(x+60,72)]);triangle([(x,5),(x+60,72),(x,72)])
    for x in range(16):
        config(alpha=128,color=0x07e0);triangle([(x+640,10),(x+671,11),(x+650,90)])
    # Intersections, equal-depth rejection and transparent Z policy.
    shape=[(30,120),(240,125),(100,280)]
    for color,o,dx in ((0xf800,10000<<16,100<<16),(0x001f,40000<<16,-100<<16),(0xffff,10000<<16,100<<16)):
        config(flags=6,color=color);plane(18,o,dx);triangle(shape)
    config(flags=2,alpha=80,color=0x07e0);plane(18,5000<<16);triangle([(20,100),(220,200),(10,290)])
    config(flags=6,alpha=0);plane(18,0);triangle([(0,100),(250,100),(250,300)])
    # Textures: odd origins, dimensions, complete 128 cache, all address modes.
    for i,(sw,sh,mu,mv) in enumerate(((13,7,0,0),(13,7,2,2),(16,8,1,1),(128,128,0,0),(127,3,2,0),(1,1,0,2))):
        emit(15,15,(17<<16)|19,(sw<<16)|sh,mu|(mv<<2))
        x=280+(i%3)*150;y=115+(i//3)*140
        plane(16,-x*65536-3*65536,65536,1000)
        plane(17,-y*32768+20*65536,0,32768 if i%2==0 else -32768)
        plane(18,30000<<16,-300<<16,25<<16)
        config(flags=15,alpha=128 if i%2 else 256)
        triangle([(x,y),(x+140,y+3),(x+100,y+130)])
    rng=random.Random(131415)
    emit(15,15,0,(128<<16)|128,5)
    for i in range(35):
        config(flags=rng.choice([0,1,3,5,6,7,9,15]),alpha=rng.choice([1,128,255,256]),color=rng.randrange(65536))
        for op in (16,17):plane(op,rng.randrange(-100,100)<<16,rng.randrange(-2<<16,2<<16),rng.randrange(-2<<16,2<<16))
        plane(18,rng.randrange(65536)<<16,rng.randrange(-100,100)<<16,rng.randrange(-100,100)<<16)
        x=rng.randrange(-30,810);y=rng.randrange(325,490)
        triangle([(x,y),(x+55,y-12),(x-6,y+30)])
    # Extreme plane arithmetic and winding/degenerate/off-screen geometry.
    for points in ([(-32768,450),(32767,450),(0,480)],[(799,479),(800,480),(800,479)],[(1,1)]*3):
        config(flags=7);plane(16,0x7fffffff,0x7fffffff,0x80000000);plane(17,0x80000000,0x80000000,0x7fffffff)
        plane(18,0xffffffff,0x7fffffff,0x80000000);triangle(points)
    # Invalid descriptors must complete, count refusal, and invalidate state.
    emit(15,15,0,(129<<16)|8);config(flags=1);triangle(shape)
    emit(15,15,0,(13<<16)|8,1);triangle(shape)
    emit(16,0,0,0,1);triangle(shape)
    emit(14,0,0,256,0xffff);triangle(shape);emit(20,3,0,0)
    config();emit(20,4,0,0);emit(19,0,1,2,1)
    # Same crossing geometry submitted in opposite orders in two windows.
    for offset in (0,400):
        left=15+offset
        config(flags=4,color=0x2104);plane(18,65535<<16)
        triangle([(left,350),(left+130,350),(left+130,470)])
        triangle([(left,350),(left+130,470),(left,470)])
        faces=[(0xf800,20000-80*left+40*350,80,-40),
               (0x001f,25000+80*left-40*350,-80,40)]
        if offset:faces.reverse()
        for color,origin,dx,dy in faces:
            config(flags=6,color=color);plane(18,origin<<16,dx<<16,dy<<16)
            triangle([(left+3,353),(left+125,357),(left+46,462)])
    for y in range(350,470):
        for x in range(15,145):
            assert get(0,x,y)==get(0,x+400,y) and get(1,x,y)==get(1,x+400,y)
    # Same-page texture snapshot, destination page 15 (checks address high bits).
    emit(15,15,(31<<16)|25,(32<<16)|32,5)
    config(flags=1,alpha=192,page=15);plane(16,0,65536,0);plane(17,0,0,65536)
    triangle([(11,14),(72,14),(30,91)])
    # Origins outside 32-bit range still interpolate to visible U/V/Z values.
    def extended(op,o,dx=0,dy=0):emit(op,o,dx,dy,0x10000|((o>>32)&65535))
    config(flags=7)
    extended(16,-66000<<16,100<<16);extended(17,-100000<<16,0,400<<16)
    extended(18,-50000<<16,100<<16)
    triangle([(620,180),(760,180),(690,310)])
    extended(18,100000<<16,-100<<16)
    triangle([(600,180),(750,190),(610,320)])
    # Extreme signed 48-bit origins must not overflow into visible depth.
    for origin in (-(1<<47),(1<<47)-1):
        extended(18,origin,0x7fffffff,-0x80000000)
        triangle([(600,180),(780,180),(690,330)])
    emit(15,15,(31<<16)|25,(32<<16)|32,10)
    config(flags=1,alpha=128)
    extended(16,(1<<47)-1,0x7fffffff);extended(17,-(1<<47),-0x80000000)
    triangle([(650,240),(780,240),(690,330)])
    emit(16,0,0,0,0x20000)  # reserved format bit
    emit(19,0,1,2,0x10000)  # triangle tail stays reserved
    # Independent exact rational reference: signed UQ/VQ over positive Q.
    # Near-zero Q, sign changes, repeat with huge ratios, all edge modes,
    # scalar alpha/Z/key and 1/2/odd/even/full native chunks.
    config(flags=17);triangle([(10,10),(15,10),(10,15)]) # missing Q rejects
    for i in range(60):
        mode=i%3
        emit(15,15,(17<<16)|19,(128<<16)|128,mode|(mode<<2))
        config(flags=17|(i%8)*2,alpha=(1,128,256)[i%3])
        x=5+(i%10)*76;y=10+(i//10)*73
        if i<40:
            denominator=rng.choice([1,10000,1<<24])
            extended(21,denominator-300*x,300,(-1 if i%2 else 1)*80)
            extended(16,(-x+25)*denominator,denominator,denominator//7)
            extended(17,(-y+13)*denominator,denominator//11,denominator)
        else:
            extended(21,rng.choice([-1,0,1,2,513,(1<<47)-1]))
            extended(16,rng.randrange(-(1<<47),(1<<47)),rng.randrange(-2147483648,2147483648))
            extended(17,rng.randrange(-(1<<47),(1<<47)),0,rng.randrange(-2147483648,2147483648))
        extended(18,12000<<16,3<<16,-2<<16)
        width=(1,2,3,15,16,17,67)[i%7]
        triangle([(x,y),(x+width,y),(x,y+59)])
    emit(21,0,0,0,0x20000);triangle([(10,10),(15,10),(10,15)])
    config(flags=16);triangle([(10,10),(15,10),(10,15)]) # texture flag required
    (out/'commands.hex').write_text(''.join(f'{w:08x}\n' for w in commands))
    (out/'expected.hex').write_text(''.join(f'{v:02x}\n' for v in memory))
    shutil.copy2(ROOT/'tang/rtl/video/font8x16.hex',out/'font8x16.hex')
    sources=['TESTS/rtl/gpu_accel_tb.sv','tang/rtl/video/gpu_accel.v','tang/rtl/video/blitter.v',
        'tang/rtl/video/gpu_raster.v','tang/rtl/video/gpu_v1.v','tang/rtl/video/gpu_texture_cache.v','tang/rtl/video/gpu_copy565.v','tang/rtl/video/gpu_perspective.v','tang/rtl/video/gpu_triangle.v','tang/rtl/video/gpu_blit_dma.v',
        'tang/rtl/video/font_ram.v','tang/rtl/board/ddr_dcfifo.v','tang/rtl/board/cdc_word.v',
        'tang/rtl/board/ddr_gpu_arb.v']
    with (out/'build.log').open('w') as log:
        subprocess.run(['verilator','--binary','--timing','-Wno-fatal','--top-module','gpu_accel_tb',
            '--Mdir',str(out/'obj')]+[str(ROOT/s) for s in sources],stdout=log,stderr=log,check=True)
    command=[str(out/'obj/Vgpu_accel_tb'),f'+ncmd={len(commands)//8}',f'+raster_bad={rejected}','+rgbinit=1']
    with (out/'simulation.log').open('w') as log:
        p=subprocess.run(command,cwd=out,stdout=log,stderr=subprocess.STDOUT)
    print((out/'simulation.log').read_text());print('Reference:',len(commands)//8,'commands;',rejected,'expected rejections')
    p.check_returncode()

if __name__=='__main__':main()
