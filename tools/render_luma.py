#!/usr/bin/env python3
"""Run the exact autonomous scene under UBSan; compose pixels independently."""
import argparse,ctypes,json,struct,subprocess,tempfile,sys,zlib
from pathlib import Path
import numpy as np
from PIL import Image
from render_gpu_demo import brace_block
from gpu_compose import compose,frame_hash,palette_rgb,signed16
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'TESTS'))
from test_gpu_v1 import Model
FX_START,FX_FRAMES=5120,3200
TOTAL=FX_START+FX_FRAMES
class Info(ctypes.Structure):
    _fields_=[(n,ctypes.c_uint if i<4 else ctypes.c_int) for i,n in enumerate(('frame','chapter','sprites','light','camera_x','camera_y','hero_x','hero_y'))]
class Scene:
    def __init__(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='luma_scene_');work=Path(self.tmp.name)
        driver=(ROOT/'fw_console/gpu.c').read_text()
        source='#include "luma_fx_scene.h"\n'+'\n'.join(brace_block(driver,s) for s in ('gpu_layer gpu_make_layer(','gpu_layer gpu_make_tile_layer(','gpu_sprite gpu_make_sprite('))
        source+='''
void scene(unsigned f,gpu_layer *l,gpu_sprite *s,luma_info *i){f%=LUMA_FRAMES;if(f>=LUMA_FX_START)luma_fx_layers(f-LUMA_FX_START,l,s,i);else luma_scene(f,l,s,i);}
uint32_t color(uint32_t c,unsigned i,unsigned f,unsigned light){return luma_color(c,i,f,light);}
static unsigned count;
static gpu_command commands[4096];
static void emit(const gpu_command *c){if(count<4096)commands[count]=*c;++count;}
unsigned command_count(void){return count;}
uint32_t *command_words(void){return &commands[0].words[0];}
int fx(unsigned f,int prepare){count=0;gpu_v1_context c;gpu_v1_init(&c,emit);return (prepare?luma_fx_prepare(&c):luma_fx_render(&c,f,0)) && count<=4096;}
'''
        (work/'scene.c').write_text(source)
        subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Wno-unused-function','-fsanitize=undefined','-fno-sanitize-recover=all','-shared','-fPIC','-I',str(ROOT/'fw_console'),str(work/'scene.c'),str(ROOT/'fw_console/gpu_v1.c'),'-o',str(work/'scene.so')],check=True)
        self.lib=ctypes.CDLL(str(work/'scene.so'));self.lib.color.restype=ctypes.c_uint32
        self.raw=(ROOT/'assets/luma/packed/luma.bin').read_bytes()
        self.manifest=json.loads((ROOT/'assets/luma/packed/manifest.json').read_text());self.base=self.manifest['base']
        self.palette=struct.unpack('<256I',self.read(self.manifest['regions']['palette']['address'],1024))
        self.lib.command_words.restype=ctypes.POINTER(ctypes.c_uint32)
        self.fx_initial=None
    def read(self,addr,n):
        assert self.base<=addr<=self.base+len(self.raw)-n,(hex(addr),n)
        return self.raw[addr-self.base:addr-self.base+n]
    def get(self,f):
        l=((ctypes.c_uint32*8)*16)();s=((ctypes.c_uint32*4)*64)();i=Info();self.lib.scene(f,l,s,ctypes.byref(i))
        return [tuple(a) for a in l],[tuple(a) for a in s],i
    def fast(self,layers,sprites):
        # Fast preview only; exact poses are cross-checked with gpu_compose.
        out=Image.new('L',(800,480))
        for num,w in enumerate(layers):
            if w[6]&1:
                base,wh,xy,v,scroll,stride,flags,_=w;sw,sh=wh&65535,wh>>16
                assert not flags&4
                im=Image.frombytes('L',(stride,sh),self.read(base,stride*sh))
                sx,sy=scroll&65535,scroll>>16
                im=im.crop((sx,sy,min(sw,sx+(v&65535)),min(sh,sy+(v>>16))))
                out.paste(im,(signed16(xy&65535),signed16(xy>>16)),im.point(lambda x:255 if x else 0) if flags&2 else None)
            for base,xy,p,_ in sprites:
                if p&65536 and (p>>20)&15==num:
                    w,h=p&255,(p>>8)&255
                    im=Image.frombytes('L',(32,h),self.read(base,32*h)).crop((0,0,w,h))
                    if p&131072:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                    if p&262144:im=im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                    out.paste(im,(signed16(xy&65535),signed16(xy>>16)),im.point(lambda x:255 if x else 0))
        return out.tobytes()
    def render(self,f,exact=False):
        l,s,info=self.get(f);indices=self.fast(l,s)
        if exact:assert indices==bytes(compose(l,s,self.read)),f
        im=Image.frombytes('P',(800,480),indices)
        pal=struct.pack('<256I',*(self.lib.color(c,i,f%TOTAL,info.light) for i,c in enumerate(self.palette)))
        im.putpalette(palette_rgb(pal))
        return im.convert('RGB'),indices,info
    def commands(self,f=0,prepare=False):
        assert self.lib.fx(f,int(prepare)),f
        n=self.lib.command_count();raw=self.lib.command_words()
        return [list(raw[i*8:i*8+8]) for i in range(n)]
    def render_fx(self,f):
        if self.fx_initial is None:
            m=FxModel(self.raw,self.base)
            for cmd in self.commands(prepare=True):m.apply(cmd)
            self.fx_initial=bytes(m.memory)
        m=FxModel(self.raw,self.base,self.fx_initial)
        commands=self.commands(f-FX_START)
        for cmd in commands:m.apply(cmd)
        l,s,info=self.get(f);indices=bytes(compose(l,s,self.read))
        pixels=np.frombuffer(m.memory[:800*240],dtype='<u2').reshape(240,400).repeat(2,axis=0).repeat(2,axis=1).astype(np.uint32)
        r=pixels>>11;g=(pixels>>5)&63;b=pixels&31
        rgb=np.stack((r*2+(r>>4),g,b*2+(b>>4)),axis=-1)
        indexed=np.frombuffer(indices,dtype=np.uint8).reshape(480,800)
        palette=np.array([self.lib.color(c,i,f,256) for i,c in enumerate(self.palette)],dtype=np.uint32)
        overlay=palette[indexed];mask=indexed!=0
        values=np.stack(((overlay>>12)&63,(overlay>>6)&63,overlay&63),axis=-1)
        rgb[mask]=values[mask]
        lcd=int(np.sum((rgb[:,:,0]<<12)+(rgb[:,:,1]<<6)+rgb[:,:,2],dtype=np.uint64))&0xffffffff
        im=Image.fromarray(((rgb*255+31)//63).astype(np.uint8))
        return im,dict(frame=f,lcd=f'{lcd:08x}',crc565=f'{zlib.crc32(m.memory[:800*240]):08x}',mode='rgb565',commands=len(commands),fragments=m.passed,sprites=info.sprites)
    def sweep(self):
        maximum=0
        max_commands=0
        for f in range(TOTAL):
            l,s,i=self.get(f);assert 0<=i.camera_x<=736 and 0<=i.camera_y<=544 and i.sprites<=64
            maximum=max(maximum,i.sprites)
            for b,xy,p,_ in s:
                if p&65536:
                    assert b%32==0 and 1<=(p&255)<=32 and 1<=((p>>8)&255)<=32
                    self.read(b,1024)
            if f>=FX_START:max_commands=max(max_commands,len(self.commands(f-FX_START)))
        print(f'PASS: {TOTAL} frames under UBSan, bounded descriptors, max {maximum} sprites, {max_commands} GPU commands')
class FxModel(Model):
    def __init__(self,assets,base,initial=None):
        self.base_assets=base;self.asset_bytes=len(assets)
        self.memory=bytearray(initial) if initial else bytearray([0xa5])*(4*(1<<20))+bytearray(assets)
        self.commands=[];self.rejected=0;self.passed=0;self.planes={}
    def at(self,a):
        if 0x800000<=a<0xc00000:return a-0x800000
        assert self.base_assets<=a<self.base_assets+self.asset_bytes,hex(a)
        return 4*(1<<20)+a-self.base_assets
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'TESTS/luma_fx_20261004/preview');p.add_argument('--animation',action='store_true');p.add_argument('--fx-animation',action='store_true');p.add_argument('--sweep',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    sc=Scene()
    if a.sweep:sc.sweep()
    records=[]
    for f in (100,800,1600,2305,2640,2958,3480,3880,4115,4490,4900):
        im,raw,info=sc.render(f,True);im.save(a.out/f'frame_{f:04}.png');record=dict(frame=f,hash=f'{frame_hash(raw):08x}',sprites=info.sprites,chapter=info.chapter);records.append(record);print(record)
    for f in (5200,5580,6010,6270,6650,6940,7100,7240,7310,7350,7440,7660,7940,8240):
        im,record=sc.render_fx(f);im.save(a.out/f'frame_{f:04}.png');records.append(record);print(record,flush=True)
    (a.out/'expected.json').write_text(json.dumps(records,indent=2)+'\n')
    if a.animation:
        # A full-loop video stays much smaller than an animated WebP of a
        # detailed scrolling background. Playback has the measured panel rate.
        command=['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgb24',
                 '-video_size','800x480','-framerate','5.0036','-i','-',
                 '-an','-c:v','libx264','-preset','medium','-crf','20',
                 '-pix_fmt','yuv420p','-movflags','+faststart',str(a.out/'luma_adventure.mp4')]
        with subprocess.Popen(command,stdin=subprocess.PIPE) as encoder:
            for f in range(0,FX_START,11):encoder.stdin.write(sc.render(f)[0].tobytes())
            encoder.stdin.close()
            if encoder.wait():raise RuntimeError('Preview video encoding failed')
        print(a.out/'luma_adventure.mp4')
    if a.fx_animation:
        # Expected images at one sample per eleven phases, played at the LCD
        # cadence divided by eleven. This is not a recording from the board.
        command=['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgb24',
                 '-video_size','800x480','-framerate','5.0036','-i','-',
                 '-an','-c:v','libx264','-preset','medium','-crf','20',
                 '-pix_fmt','yuv420p','-movflags','+faststart',str(a.out/'luma_fx.mp4')]
        with subprocess.Popen(command,stdin=subprocess.PIPE) as encoder:
            for f in range(FX_START,TOTAL,11):encoder.stdin.write(sc.render_fx(f)[0].tobytes())
            encoder.stdin.close()
            if encoder.wait():raise RuntimeError('Effects preview encoding failed')
        print(a.out/'luma_fx.mp4')
