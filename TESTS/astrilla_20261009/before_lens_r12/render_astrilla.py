#!/usr/bin/env python3
"""ASTRILLA shared scene under UBSan + independent GPU pixel/composition reference."""
import argparse,ctypes,json,math,struct,subprocess,tempfile,sys,zlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from render_gpu_demo import brace_block
from gpu_compose import compose
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'TESTS'))
from test_gpu_v1 import Model
from astra_preview_model import FastPixels
TOTAL=16500
KEYS=(0,1925,3850,5500,7150,8800,10450,12375,14300,15675,16500)
POSES=sorted(set([100,329,330,331,450,659,660,700,780,1160,1700,2200,3500,4300,5250,5700,6150,6800,7180,7560,7980,8650,9500,10480,11200,12000,12700,13500,14200,14400,15100,15289,15290,15674,15675,15800,16000,16224,16225,16300]+[v+d for v in KEYS[:-1] for d in (-1,0,19,20) if 0<=v+d<TOTAL]+[TOTAL-1]))
class Info(ctypes.Structure):_fields_=[(n,ctypes.c_uint) for n in ('frame','chapter','sprites','shots')]
class Camera(ctypes.Structure):
 _fields_=[('base',ctypes.c_uint32)]+[(n,ctypes.c_int32) for n in ('width','height','u','v','ux','vx','uy','vy')]+[(n,ctypes.c_float) for n in ('seconds','roll','travel','shot')]
class AstrillaModel(Model):
 def __init__(self,assets,base,poison=0xa5):
  self.memory=bytearray([poison])*(8*(1<<20))+bytearray(assets);self.asset_base=base;self.asset_bytes=len(assets);self.commands=[];self.rejected=0;self.passed=0;self.planes={}
 def at(self,a):
  if 0x800000<=a<0x1000000:return a-0x800000
  if 0x0a000000<=a<0x0a000000+1815*192000:return 6*(1<<20)+(a-0x0a000000)%192000
  assert self.asset_base<=a<self.asset_base+self.asset_bytes,hex(a)
  return 8*(1<<20)+a-self.asset_base
class FastAstrillaModel(FastPixels,AstrillaModel):pass
class Scene:
 def __init__(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='astrilla_');work=Path(self.tmp.name);driver=(ROOT/'fw_console/gpu.c').read_text()
  code='#include "astrilla_scene.h"\n'+'\n'.join(brace_block(driver,s) for s in ('gpu_layer gpu_make_layer(','gpu_sprite gpu_make_sprite('))
  code+='''
static gpu_command commands[16384];static unsigned count;
static void emit(const gpu_command *c){if(count<16384)commands[count]=*c;++count;}
unsigned command_count(void){return count;}
uint32_t *command_words(void){return commands[0].words;}
int render(unsigned t){count=0;gpu_v1_context c;gpu_v1_init(&c,emit);return astrilla_render(&c,t,0)&&count<=16384;}
unsigned plate(unsigned t){return as_plate(t);}
unsigned plate_time(unsigned i){return as_plate_time(i);}
float sine(float p){return af_sin(p);}
float heading(float x,float y){return as_heading(x,y);}
void landing(unsigned t,as_landing_pose *p){*p=as_landing(t);}
void flagship(float seconds,as_motion *m){*m=as_flagship(seconds);}
void camera(unsigned t,as_camera *c){*c=as_view(t);}
void background(unsigned t,uint16_t *p,const uint8_t *a){astrilla_background(t,p,a);}
void layers(unsigned t,gpu_layer *l,gpu_sprite *s,astrilla_info *i){astrilla_layers(t,l,s,i);}
'''
  (work/'scene.c').write_text(code)
  subprocess.run(['cc','-std=c11','-O2','-ffp-contract=off','-Wall','-Wextra','-Wno-unused-function','-fsanitize=undefined','-fno-sanitize-recover=all','-shared','-fPIC','-I',str(ROOT/'fw_console'),str(work/'scene.c'),str(ROOT/'fw_console/gpu_v1.c'),'-o',str(work/'scene.so')],check=True)
  self.lib=ctypes.CDLL(str(work/'scene.so'));self.lib.command_words.restype=ctypes.POINTER(ctypes.c_uint32)
  self.lib.sine.argtypes=[ctypes.c_float];self.lib.sine.restype=ctypes.c_float
  self.raw=(ROOT/'assets/astrilla/packed/astrilla.bin').read_bytes();self.manifest=json.loads((ROOT/'assets/astrilla/packed/manifest.json').read_text());self.base=self.manifest['base']
  self.palette=struct.unpack('<256I',self.read(self.manifest['regions']['palette']['address'],1024))
 def read(self,a,n):
  assert self.base<=a<=self.base+len(self.raw)-n,(hex(a),n)
  return self.raw[a-self.base:a-self.base+n]
 def layers(self,t):
  l=((ctypes.c_uint32*8)*16)();s=((ctypes.c_uint32*4)*64)();i=Info();self.lib.layers(t,l,s,ctypes.byref(i));return [tuple(v) for v in l],[tuple(v) for v in s],i
 def commands(self,t):
  assert self.lib.render(t),t
  n=self.lib.command_count();w=self.lib.command_words();return [list(w[i*8:i*8+8]) for i in range(n)]
 def background(self,t,check=False):
  camera=Camera();self.lib.camera(t,ctypes.byref(camera));c=camera
  yy,xx=np.mgrid[:240,:400];u=c.u+c.ux*xx+c.uy*yy;v=c.v+c.vx*xx+c.vy*yy
  ix=u>>16;iy=v>>16;fx=(u>>12)&15;fy=(v>>12)&15
  fx=np.where(ix<0,0,np.where(ix>=c.width-1,15,fx));fy=np.where(iy<0,0,np.where(iy>=c.height-1,15,fy))
  ix=np.clip(ix,0,c.width-2);iy=np.clip(iy,0,c.height-2)
  source=np.frombuffer(self.read(c.base,c.width*c.height*2),dtype='<u2').reshape(c.height,c.width).astype(np.int64)
  def mix(a,b,w):
   return ((((a&0xf81f)*(16-w)+(b&0xf81f)*w)>>4)&0xf81f)|((((a&0x7e0)*(16-w)+(b&0x7e0)*w)>>4)&0x7e0)
  image=mix(mix(source[iy,ix],source[iy,ix+1],fx),mix(source[iy+1,ix],source[iy+1,ix+1],fx),fy).astype('<u2').tobytes()
  if check:
   array=(ctypes.c_uint16*96000)();data=(ctypes.c_uint8*len(self.raw)).from_buffer_copy(self.raw);self.lib.background(t,array,data)
   assert bytes(array)==image,('C vs independent bilinear sampler',t)
  return image
 def sweep(self):
  maximum=0;sprites=0;chapters=[0]*10
  for a in range(0,65536,13):assert abs(self.lib.sine(a/256)-math.sin(a*math.pi/32768))<.0002
  for i in range(1815):assert self.lib.plate(self.lib.plate_time(i))==i
  for t in range(TOTAL):
   c=Camera();d=Camera();self.lib.camera(t,ctypes.byref(c));self.lib.camera(self.lib.plate_time(self.lib.plate(t)),ctypes.byref(d))
   assert bytes(c)[:36]==bytes(d)[:36],('cached camera mismatch',t)
   assert self.lib.render(t),t;maximum=max(maximum,self.lib.command_count())
   l,s,i=self.layers(t);assert i.frame==t and i.sprites<=64;chapters[i.chapter]+=1;sprites=max(sprites,i.sprites)
   assert bool(i.shots)==(7150<=t<8800)
   if t%113==0:
    self.background(t,check=True)
    assert self.background(t)==self.background(self.lib.plate_time(self.lib.plate(t))),('cache mapping',t)
   for b,xy,p,_ in s:
    if p&65536:self.read(b,1024)
  assert chapters==[KEYS[i+1]-KEYS[i] for i in range(10)] and chapters[4]==30*55
  assert not self.lib.render(TOTAL) and not self.lib.render(0xffffffff)
  result=dict(phases=TOTAL,seconds=300,battle_seconds=chapters[4]/55,max_commands=maximum,max_sprites=sprites,chapter_phases=chapters,ubsan='PASS')
  print(json.dumps(result),flush=True);return result
 def render(self,t,poison=0xa5,fast=False):
  m=(FastAstrillaModel if fast else AstrillaModel)(self.raw,self.base,poison);cmds=self.commands(t)
  background=self.background(t);m.memory[6*(1<<20):6*(1<<20)+192000]=background
  for c in cmds:m.apply(c)
  for p in (0,2):assert m.memory[p*(1<<20)+192000:(p+1)*(1<<20)]==bytes([poison])*((1<<20)-192000)
  assert m.memory[(1<<20):2*(1<<20)]==bytes([poison])*(1<<20)
  assert m.memory[8*(1<<20):]==self.raw
  l,s,info=self.layers(t);indices=np.frombuffer(bytes(compose(l,s,self.read)),dtype=np.uint8).reshape(480,800)
  pixels=np.frombuffer(m.memory[:192000],dtype='<u2').reshape(240,400).repeat(2,0).repeat(2,1).astype(np.uint32)
  r=pixels>>11;g=(pixels>>5)&63;b=pixels&31;rgb=np.stack((r*2+(r>>4),g,b*2+(b>>4)),axis=-1)
  overlay=np.array(self.palette,dtype=np.uint32)[indices];mask=indices!=0;values=np.stack(((overlay>>12)&63,(overlay>>6)&63,overlay&63),axis=-1);rgb[mask]=values[mask]
  lcd=int(np.sum((rgb[:,:,0]<<12)+(rgb[:,:,1]<<6)+rgb[:,:,2],dtype=np.uint64))&0xffffffff
  record=dict(frame=t,chapter=info.chapter,mode='rgb565',lcd=f'{lcd:08x}',crc565=f'{zlib.crc32(m.memory[:192000]):08x}',commands=len(cmds),fragments=m.passed,sprites=info.sprites)
  return Image.fromarray(((rgb*255+31)//63).astype(np.uint8)),record
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'TESTS/astrilla_20261009/reference');p.add_argument('--sweep',action='store_true');p.add_argument('--poses',type=int,nargs='+',default=POSES);p.add_argument('--fast',action='store_true');p.add_argument('--animation',action='store_true');p.add_argument('--fps',type=int,default=10);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);scene=Scene()
 if not 1<=a.fps<=55:p.error('--fps must be 1..55')
 if a.sweep:(a.out/'sweep.json').write_text(json.dumps(scene.sweep(),indent=2)+'\n')
 records=[];thumbs=[]
 for t in a.poses:
  im,r=scene.render(t,fast=a.fast);im.save(a.out/f'frame_{t:05}.png');records.append(r);print(r,flush=True)
  small=im.resize((400,240));ImageDraw.Draw(small).text((8,22),f'{t/55:.1f}s',fill='white');thumbs.append(small)
 (a.out/'expected.json').write_text(json.dumps(records,indent=2)+'\n')
 sheet=Image.new('RGB',(1200,240*((len(thumbs)+2)//3)))
 for n,im in enumerate(thumbs):sheet.paste(im,(n%3*400,n//3*240))
 sheet.save(a.out/'contact.png')
 if a.animation:
  cmd=['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size','800x480','-framerate',str(a.fps),'-i','-','-an','-c:v','libx264','-threads','2','-preset','fast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(a.out/'astrilla.mp4')]
  with subprocess.Popen(cmd,stdin=subprocess.PIPE) as enc:
   for index in range(300*a.fps):
    phase=index*55//a.fps;enc.stdin.write(scene.render(phase,fast=True)[0].tobytes())
    if index%(30*a.fps)==0:print('PREVIEW',index/a.fps,'/300 s',flush=True)
   enc.stdin.close();assert enc.wait()==0
  (a.out/'preview.json').write_text(json.dumps(dict(duration_seconds=300,fps=a.fps,frames=300*a.fps,source='software reference, not LCD capture',audio=False),indent=2)+'\n')
if __name__=='__main__':main()
