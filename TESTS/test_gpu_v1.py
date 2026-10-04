#!/usr/bin/env python3
"""GPU V1: independent integer pixel oracle, complete memory/guards, shared DDR stalls."""
import argparse,json,random,shutil,subprocess
from pathlib import Path
from test_gpu_accel import triangle_pixels
ROOT=Path(__file__).resolve().parents[1]
SLOT=1<<20
COLOR,Z,TEX=0x800000,0x900000,0x1700000

def xy(x,y):return ((x&65535)<<16)|(y&65535)
def signed16(v):return (v&65535)-65536 if v&32768 else v&65535
class Model:
    def __init__(self,depth_slot=1):
        self.memory=bytearray((i*29+(i>>11))&255 for i in range(3*SLOT))
        self.slots={0:0,depth_slot:SLOT,15:2*SLOT}
        self.commands=[];self.rejected=0;self.passed=0;self.planes={}
    def at(self,a):
        slot=(a-0x800000)//SLOT
        assert slot in self.slots,hex(a)
        return self.slots[slot]+(a&(SLOT-1))
    def get(self,a):return int.from_bytes(self.memory[self.at(a):self.at(a)+2],'little')
    def put(self,a,c):self.memory[self.at(a):self.at(a)+2]=c.to_bytes(2,'little')
    def emit(self,op,*args,header=0):
        w=[(op<<24)|header]+[a&0xffffffff for a in args];w += [0]*(8-len(w));assert len(w)==8
        self.commands.extend(w)
    def invalid(self,op,*args,header=0):self.emit(op,*args,header=header);self.rejected+=1
    def target(self,width=160,height=100,stride=352,zstride=384,base=COLOR,zbase=Z):
        self.emit(22,base,zbase,xy(width,height),xy(stride,zstride))
        self.base,self.zbase,self.width,self.height,self.stride,self.zstride=base,zbase,width,height,stride,zstride
        self.clip=0,0,width,height
    def scissor(self,l,t,r,b):self.emit(23,xy(l,t),xy(r,b));self.clip=l,t,r,b
    def texture(self,w=512,h=512,stride=1024,argb=False,mu=0,mv=0,lod=0,base=TEX):
        self.emit(24,base,xy(w,h),stride|(int(argb)<<16),mu|(mv<<2)|(lod<<4))
        self.tex=base,w,h,stride,argb,mu,mv,lod
    def material(self,flags=0,alpha=256,color=0xffff,tint=(256,256,256),fog=(0,0,0)):
        near,fc,scale=fog
        self.emit(25,flags,alpha,color,tint[0]|(tint[1]<<9)|(tint[2]<<18),(near<<16)|fc,scale)
        self.mat=flags,alpha,color,tint,fog
    def plane(self,index,origin=0,dx=0,dy=0):
        self.emit(26,origin,dx,dy,(origin>>32)&65535,header=index);self.planes[index]=origin,dx,dy
    def clear(self,flags=3,color=0x2104,z=65535,x=0,y=0,w=None,h=None):
        if w is None:w=self.width
        if h is None:h=self.height
        self.emit(28,flags,color,z,xy(x,y),xy(w,h));l,t,r,b=self.clip
        for yy in range(max(t,y),min(b,y+h)):
            for xx in range(max(l,x),min(r,x+w)):
                if flags&1:self.put(self.base+yy*self.stride+xx*2,color)
                if flags&2:self.put(self.zbase+yy*self.zstride+xx*2,z)
    def triangle(self,points):
        self.emit(27,*[xy(x,y) for x,y in points]);l,t,r,b=self.clip
        flags,a,solid,tint,fog=self.mat
        def pv(p,x,y):o,dx,dy=self.planes.get(p,(0,0,0));return o+x*dx+y*dy
        for x,y in triangle_pixels(*sum(([x,y] for x,y in points),[]),width=self.width,height=self.height):
            if not(l<=x<r and t<=y<b) or a==0:continue
            depth=pv(3,x,y)//65536
            if flags&134 and not 0<=depth<=65535:continue
            if flags&2 and depth>=self.get(self.zbase+y*self.zstride+x*2):continue
            c=solid;ta=256
            if flags&1:
                base,w,h,stride,argb,mu,mv,lod=self.tex
                den=pv(2,x,y) if flags&16 else 65536
                if den<=0:continue
                uv=[(pv(k,x,y)//den)//(1<<lod) for k in (0,1)]
                u,v=[v%size if mode==1 else max(0,min(size-1,v)) if mode==2 else v for v,size,mode in zip(uv,(w,h),(mu,mv))]
                if not (0<=u<w and 0<=v<h):continue
                c=self.get(base+v*stride+u*2)
                if argb:ta=256 if c>>12==15 else (c>>12)*17
            if flags&8 and c==0:continue
            aa=(a*ta+128)//256
            if aa==0:continue
            if flags&1 and self.tex[4]:
                rr,gg,bb=(c>>8)&15,(c>>4)&15,c&15
                channels=[(rr<<1)|(rr>>3),(gg<<2)|(gg>>2),(bb<<1)|(bb>>3)]
            else:channels=[(c>>11)&31,(c>>5)&63,c&31]
            gains=[max(0,min(256,pv(4+k,x,y)//65536)) for k in range(3)] if flags&64 else tint
            channels=[(v*g+128)//256 for v,g in zip(channels,gains)]
            near,fc,scale=fog
            f=max(0,min(256,((depth-near)*scale)//65536)) if flags&128 else 0
            fogchannels=[(fc>>11)&31,(fc>>5)&63,fc&31]
            channels=[(v*(256-f)+fv*f+128)//256 for v,fv in zip(channels,fogchannels)]
            old=self.get(self.base+y*self.stride+x*2);result=0
            for v,shift,mask in zip(channels,(11,5,0),(31,63,31)):
                bg=(old>>shift)&mask
                result |= min(mask,(v*aa+bg*(256 if flags&32 else 256-aa)+128)//256)<<shift
            self.put(self.base+y*self.stride+x*2,result)
            if flags&4:self.put(self.zbase+y*self.zstride+x*2,depth)
            self.passed+=1
    def copy(self,src,sw,sh,ss,sx,sy,dx,dy,w,h):
        self.emit(29,src,xy(sw,sh),ss,xy(sx,sy),xy(dx,dy),xy(w,h));l,t,r,b=self.clip
        snapshot=bytes(self.memory)
        for y in range(max(t,dy,dy-sy),min(b,dy+h,dy+sh-sy)):
            for x in range(max(l,dx,dx-sx),min(r,dx+w,dx+sw-sx)):
                a=self.at(src+(y-dy+sy)*ss+(x-dx+sx)*2)
                self.put(self.base+y*self.stride+x*2,int.from_bytes(snapshot[a:a+2],'little'))

    def apply(self,w):
        op=w[0]>>24
        xy1=lambda value:(signed16(value>>16),signed16(value))
        unsigned=lambda value:(value>>16,value&65535)
        s32=lambda value:value-(1<<32) if value&(1<<31) else value
        if op==22:self.target(*unsigned(w[3]),*unsigned(w[4]),w[1],w[2])
        elif op==23:self.scissor(*unsigned(w[1]),*unsigned(w[2]))
        elif op==24:self.texture(*unsigned(w[2]),w[3]&65535,bool(w[3]&65536),w[4]&3,(w[4]>>2)&3,w[4]>>4,w[1])
        elif op==25:self.material(w[1],w[2],w[3],(w[4]&511,(w[4]>>9)&511,(w[4]>>18)&511),(w[5]>>16,w[5]&65535,w[6]))
        elif op==26:
            origin=(w[4]<<32)|w[1]
            if origin&(1<<47):origin-=1<<48
            self.plane(w[0]&7,origin,s32(w[2]),s32(w[3]))
        elif op==27:self.triangle([xy1(a) for a in w[1:4]])
        elif op==28:self.clear(w[1],w[2],w[3],*xy1(w[4]),*unsigned(w[5]))
        elif op==29:self.copy(w[1],*unsigned(w[2]),w[3],*xy1(w[4]),*xy1(w[5]),*unsigned(w[6]))
        elif op==30:self.emit(30)
        else:raise ValueError(op)
        assert self.commands[-8:]==w,(self.commands[-8:],w)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--reuse',action='store_true');ap.add_argument('--read-min',type=int,choices=(1,3),default=3);args=ap.parse_args()
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=True);m=Model();rng=random.Random(20261003)
    m.target(width=1024,height=512,stride=2048,zstride=2048);m.clear();m.material()
    m.triangle([(990,495),(1024,495),(1024,512)]);m.triangle([(990,495),(1024,512),(990,512)])
    m.target();m.clear();m.material();m.triangle([(0,0),(159,0),(0,99)])
    # Scissor, odd pitches, halfword masks, partial depth and negative rectangles.
    m.scissor(3,7,157,93)
    for x in range(16):m.clear(1,(x*3917)&65535,x=-10+x,y=5+x,w=149-x,h=3)
    m.clear(2,z=1234,x=13,y=33,w=91,h=8)
    for i in range(48):
        # Interleave all three owners in one FIFO; their state persists independently.
        m.emit(14,16,0,256,0xffff);m.emit(20,0);m.emit(1)
        flags=rng.choice([0,1,3,5,6,7,9,15,17,23,32,33,65,71,129,135,193,199,231])
        m.texture(w=(512,256,13,16)[i%4],h=(512,256,7,8)[i%4],stride=(1024,512,32,32)[i%4],argb=bool(i%2),mu=2 if i%4==2 else i%3,mv=2 if i%4==2 else (i+1)%3,lod=i%3)
        m.material(flags=flags,alpha=(0,1,128,255,256)[i%5],color=rng.randrange(65536),tint=(173,256,91),fog=(23000,0xaddb,1300))
        m.plane(0,rng.randrange(-200,500)<<16,98304,32768)
        m.plane(1,rng.randrange(-200,500)<<16,-32768,98304)
        m.plane(2,20000,100,-50);m.plane(3,30000<<16,-40<<16,80<<16)
        for k in range(4,7):m.plane(k,rng.randrange(-100,400)<<16,rng.randrange(-3,3)<<16,rng.randrange(-3,3)<<16)
        x=rng.randrange(-20,140);y=rng.randrange(-10,90)
        m.triangle([(x,y),(x+40,y-10),(x+7,y+35)])
    # Every source/destination lane, overlapping forwards/backwards and rows.
    m.scissor(0,0,160,100)
    for i in range(16):m.copy(TEX,512,512,1024,i,7,15-i,8,101,3)
    for sx,sy,dx,dy in [(0,0,1,0),(1,0,0,0),(7,3,9,8),(9,8,7,3),(2,2,2,2),(-8,-2,3,6),(0,0,-10,-3)]:
        m.copy(COLOR,160,100,352,sx,sy,dx,dy,130,40)
    m.scissor(5,9,143,81);m.copy(TEX,512,512,1024,-10,-5,-3,4,177,100)
    m.emit(30)
    # Rebind target at nonzero offsets, stress bounds and untouched row padding.
    m.target(width=65,height=41,stride=160,zstride=192,base=COLOR+0x40000,zbase=Z+0x40000);m.clear()
    m.material(32,color=0xffff);m.triangle([(-20,-20),(100,1),(23,61)])
    m.scissor(6,7,6,19);m.clear();m.triangle([(0,0),(60,0),(0,40)])
    # Render-to-texture, explicit invalidation, then automatic invalidation by COPY.
    for iteration in range(3):
        m.target(width=64,height=32,stride=160,zstride=160,base=COLOR+0x40000,zbase=Z+0x40000)
        if iteration<2:m.clear(1,color=(0xf800,0x001f)[iteration])
        else:m.copy(TEX,512,512,1024,0,0,0,0,64,32)
        m.target();m.texture(w=64,h=32,stride=160,mu=2,mv=2,base=COLOR+0x40000);m.material(1)
        if iteration<2:m.emit(30)
        m.plane(0,-70*65536,65536);m.plane(1,-3*65536,0,65536)
        m.triangle([(70,3),(134,3),(134,35)]);m.triangle([(70,3),(134,35),(70,35)])
    # Change Z from above the color range to below it, without an intervening
    # command: synthesized DSP input registers must not retain the old base.
    m.target(width=32,height=8,stride=96,zstride=96,base=Z,zbase=TEX)
    m.target(width=32,height=8,stride=96,zstride=96,base=Z,zbase=COLOR)
    m.clear(1,color=0xf800);m.copy(COLOR,32,8,96,2,1,3,2,20,3)
    m.clear(2,z=0x1234,x=1,y=6,w=7,h=1)
    # Explicit invalid packets: no memory effects, correct refusal accounting.
    m.invalid(22,COLOR,Z,xy(1025,10),xy(2080,2080));m.invalid(27,0,xy(4,0),xy(0,4));m.invalid(28,3,0,0,0,xy(1,1))
    m.invalid(22,COLOR,COLOR,xy(32,10),xy(64,64));m.target()
    m.invalid(23,xy(10,10),xy(9,9));m.invalid(24,TEX,xy(513,512),1024);m.material(1);m.invalid(27,0,xy(4,0),xy(0,4))
    m.invalid(24,TEX,xy(13,8),32,1);m.invalid(25,256,256);m.invalid(27,0,xy(4,0),xy(0,4))
    m.invalid(26,0,0,0,0,header=7);m.invalid(29,COLOR+32,xy(160,100),352,0,0,xy(10,10))
    m.invalid(30,1);m.material(1);m.texture(base=COLOR,w=16,h=16,stride=32);m.invalid(27,0,xy(4,0),xy(0,4))
    # Invalid reserved header bits also invalidate a previously valid descriptor.
    m.target();m.material(1);m.texture(w=16,h=16,stride=32)
    m.invalid(22,COLOR,Z,xy(160,100),xy(352,352),header=1)
    m.invalid(28,3,0,0,0,xy(4,4));m.target()
    m.invalid(24,TEX,xy(16,16),32,header=1)
    m.invalid(27,0,xy(4,0),xy(0,4));m.texture(w=16,h=16,stride=32)
    m.invalid(25,1,256,header=1)
    m.invalid(27,0,xy(4,0),xy(0,4));m.material(1)
    m.invalid(26,0,65536,0,0,header=8)
    m.invalid(27,0,xy(4,0),xy(0,4))
    (out/'commands.hex').write_text(''.join(f'{w:08x}\n' for w in m.commands))
    (out/'expected.hex').write_text(''.join(f'{v:02x}\n' for v in m.memory));shutil.copy2(ROOT/'tang/rtl/video/font8x16.hex',out/'font8x16.hex')
    sources=['TESTS/rtl/gpu_accel_tb.sv']+['tang/rtl/video/'+s+'.v' for s in ['gpu_accel','blitter','gpu_raster','gpu_v1','gpu_texture_cache','gpu_copy565','gpu_perspective','gpu_triangle','gpu_blit_dma','font_ram']]+['tang/rtl/board/'+s+'.v' for s in ['ddr_dcfifo','cdc_word','ddr_gpu_arb']]
    if not args.reuse:
        with (out/'build.log').open('w') as log:subprocess.run(['verilator','--binary','-j','4','--timing','-Wno-fatal','--top-module','gpu_accel_tb',f'-GREAD_MIN={args.read_min}','--Mdir',str(out/'obj')]+[str(ROOT/s) for s in sources],stdout=log,stderr=log,check=True)
    with (out/'simulation.log').open('w') as log:p=subprocess.run([str(out/'obj/Vgpu_accel_tb'),f'+ncmd={len(m.commands)//8}',f'+v1_bad={m.rejected}',f'+v1_pass={m.passed}'],cwd=out,stdout=log,stderr=subprocess.STDOUT)
    print((out/'simulation.log').read_text());print(f'Reference: {len(m.commands)//8} commands, {m.rejected} rejections, {m.passed} shaded pixels');p.check_returncode()
    (out/'result.json').write_text(json.dumps(dict(commands=len(m.commands)//8,rejected=m.rejected,passed=m.passed,bytes_compared=len(m.memory),read_min=args.read_min),indent=2)+'\n')
if __name__=='__main__':main()
