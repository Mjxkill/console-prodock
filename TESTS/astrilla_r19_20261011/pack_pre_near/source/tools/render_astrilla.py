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
FULL=1045;ATLAS_W=576;ATLAS_H=320;ATLAS_BYTES=ATLAS_W*ATLAS_H*2;CACHE_COUNT=FULL+26*16
KEYS=(0,1925,3850,5500,7150,8800,10450,12375,14300,15675,16500)
POSES=sorted(set([100,219,220,221,300,450,550,770,990,1200,1420,1640,1850,
 2100,2350,2600,2900,3200,3500,3900,4100,4200,4300,4400,4509,4510,4518,4560,4700,4770,4990,5250,5350,
 5700,6150,6800,7180,7400,7560,7700,7980,8250,8650,9000,9500,9600,10200,10800,11400,12000,
 12700,13200,13464,13474,13475,13480,13520,13600,13639,13640,13749,13750,13780,14200,14400,14700,15100,
 15289,15290,15300,15674,15675,15800,15949,15950,16000,16300]+[v+d for v in KEYS[:-1] for d in (-1,0,19,20) if 0<=v+d<TOTAL]+[TOTAL-1]))
POSES=sorted(set(POSES+[v+d for v in range(0,1925,385) for d in (-1,0,40) if v+d>=0]+[6874,6875,6876,6970,7060,7140,9294,9295,9340]+[t+d for t in range(8800,13750,550) for d in (-1,0,40)]))
class Info(ctypes.Structure):_fields_=[(n,ctypes.c_uint) for n in ('frame','chapter','sprites','shots')]
class Camera(ctypes.Structure):
 _fields_=[('base',ctypes.c_uint32)]+[(n,ctypes.c_int32) for n in ('width','height','u','v','ux','vx','uy','vy','lens','portal')]+[(n,ctypes.c_float) for n in ('seconds','roll','travel','shot')]
class AstrillaModel(Model):
 def __init__(self,assets,base,poison=0xa5):
  self.memory=bytearray([poison])*(8*(1<<20))+bytearray(assets);self.asset_base=base;self.asset_bytes=len(assets);self.commands=[];self.rejected=0;self.passed=0;self.planes={}
 def at(self,a):
  if 0x800000<=a<0x1000000:return a-0x800000
  if 0x0a000000<=a<0x0a000000+FULL*192000+26*16*ATLAS_BYTES:
   offset=a-0x0a000000
   return 6*(1<<20)+(offset%192000 if offset<FULL*192000 else (offset-FULL*192000)%ATLAS_BYTES)
  assert self.asset_base<=a<self.asset_base+self.asset_bytes,hex(a)
  return 8*(1<<20)+a-self.asset_base
class FastAstrillaModel(FastPixels,AstrillaModel):pass
class Scene:
 def __init__(self,geometry=False):
  self.geometry=geometry
  self.tmp=tempfile.TemporaryDirectory(prefix='astrilla_');work=Path(self.tmp.name);driver=(ROOT/'fw_console/gpu.c').read_text()
  code=('#define ASTRILLA_HW_GEOMETRY 1\n' if geometry else '')+'#define ASTRILLA_HOST 1\n#include "astrilla_scene.h"\n#include "astrilla_hud.h"\n'+'\n'.join(brace_block(driver,s) for s in ('gpu_command gpu_make_command(','gpu_layer gpu_make_layer(','gpu_sprite gpu_make_sprite('))
  code+='''
static gpu_command commands[16384];static unsigned count;
static void emit(const gpu_command *c){if(count<16384)commands[count]=*c;++count;}
unsigned command_count(void){return count;}
uint32_t *command_words(void){return commands[0].words;}
int render(unsigned t){count=0;as3_enemy_triangles=0;gpu_v1_context c;gpu_v1_init(&c,emit);return astrilla_render(&c,t,0)&&count<=16384;}
unsigned enemy_triangles(void){return as3_enemy_triangles;}
void dogfight(float seconds,unsigned ship,as_motion *m){float p;*m=as_dogfight(seconds,ship,&p);}
void pursuit(unsigned t,int enemy,as_motion *m){*m=as_pursuit(t,enemy);}
void flight_probe(float seconds,unsigned ship,as_flight *f){float p;*f=as_dogfight_flight(seconds,ship,&p);}
void pursuit_probe(unsigned t,int enemy,as_flight *f){*f=as_pursuit_flight(t,enemy);}
void basis_probe(float heading,float pitch,float bank,as3_vec *v){as3_basis(heading,pitch,bank,&v[0],&v[1],&v[2]);}
void flyby_probe(unsigned t,unsigned variant,as_flight *f){*f=as_flyby_flight(t,variant);}
void orbit_probe(float seconds,unsigned ship,as_orbit *o){*o=as_space_orbit(seconds,ship);}
void race_probe(float seconds,unsigned enemy,as_orbit *o){*o=as_race_orbit(seconds,enemy);}
float straight_bank(float p){(void)p;return as_orbit_bank((as_orbit){{0,0,10},{4,0,10},{0,0,0}});}
int mesh_probe(float heading,float pitch,float bank){count=0;gpu_v1_context c;gpu_v1_init(&c,emit);return as3_ship(&c,200,120,120,heading,pitch,bank,0,0,0);}
unsigned plate(unsigned t){int x,y;return as_plate(t,&x,&y);}
void crop(unsigned t,int *p){as_plate(t,&p[0],&p[1]);}
unsigned cache_clock(unsigned i){return as_cache_clock(i);}
void cache_camera(unsigned i,as_camera *c){*c=as_cache_view(i);}
void cache(unsigned i,uint16_t *p,const uint8_t *a){astrilla_cache(i,p,a);}
float sine(float p){return af_sin(p);}
float heading(float x,float y){return as_heading(x,y);}
void landing(unsigned t,as_landing_pose *p){*p=as_landing(t);}
void flagship(float seconds,as_motion *m){*m=as_flagship(seconds);}
void camera(unsigned t,as_camera *c){*c=as_view(t);}
void background(unsigned t,uint16_t *p,const uint8_t *a){astrilla_background(t,p,a);}
void layers(unsigned t,gpu_layer *l,gpu_sprite *s,astrilla_info *i){astrilla_layers(t,l,s,i);as_hud_layers(i->chapter,8,l);}
void hud(unsigned fps,unsigned cps,unsigned sprites,unsigned layers){count=0;as_hud_draw(emit,8,fps,cps,sprites,layers);}
static as_meter meter;
void meter_reset(uint64_t now){as_meter_reset(&meter,now);}
void meter_frame(uint64_t now,unsigned commands){as_meter_frame(&meter,now,commands);}
unsigned meter_fps(void){return meter.fps_x10;}
unsigned meter_cps(void){return meter.commands_s;}
'''
  if geometry:code+='\nint prepare_geometry(uint8_t *p){return as3_hw_prepare(p); }\n'
  (work/'scene.c').write_text(code)
  subprocess.run(['cc','-std=c11','-O2','-ffp-contract=off','-Wall','-Wextra','-Wno-unused-function','-fsanitize=undefined','-fno-sanitize-recover=all','-shared','-fPIC','-I',str(ROOT/'fw_console'),str(work/'scene.c'),str(ROOT/'fw_console/gpu_v1.c'),*([str(ROOT/'fw_console/gpu_geometry.c')] if geometry else []),'-o',str(work/'scene.so')],check=True)
  self.lib=ctypes.CDLL(str(work/'scene.so'));self.lib.command_words.restype=ctypes.POINTER(ctypes.c_uint32)
  self.lib.sine.argtypes=[ctypes.c_float];self.lib.sine.restype=ctypes.c_float
  self.geometry_bytes=b''
  if geometry:
   data=(ctypes.c_uint8*32768)();assert self.lib.prepare_geometry(data);self.geometry_bytes=bytes(data)
  self.hud_pixels=bytes(800*32)
  self.raw=(ROOT/'assets/astrilla/packed/astrilla.bin').read_bytes();self.manifest=json.loads((ROOT/'assets/astrilla/packed/manifest.json').read_text());self.base=self.manifest['base']
  self.palette=struct.unpack('<256I',self.read(self.manifest['regions']['palette']['address'],1024))
 def read(self,a,n):
  if 0x1000000<=a and a+n<=0x1000000+800*32:return self.hud_pixels[a-0x1000000:a-0x1000000+n]
  assert self.base<=a<=self.base+len(self.raw)-n,(hex(a),n)
  return self.raw[a-self.base:a-self.base+n]
 def layers(self,t):
  l=((ctypes.c_uint32*8)*16)();s=((ctypes.c_uint32*4)*64)();i=Info();self.lib.layers(t,l,s,ctypes.byref(i));return [tuple(v) for v in l],[tuple(v) for v in s],i
 def commands(self,t):
  assert self.lib.render(t),t
  n=self.lib.command_count();w=self.lib.command_words();return [list(w[i*8:i*8+8]) for i in range(n)]
 def pixels(self,c,t,width=400,height=240):
  yy,xx=np.mgrid[:height,:width];u=c.u+c.ux*xx+c.uy*yy;v=c.v+c.vx*xx+c.vy*yy
  wave=np.array([round(math.sin(i*math.pi/128)*16384) for i in range(256)])
  def sample(base,sw,sh,u,v):
   ix=u>>16;iy=v>>16;fx=(u>>12)&15;fy=(v>>12)&15
   fx=np.where(ix<0,0,np.where(ix>=sw-1,15,fx));fy=np.where(iy<0,0,np.where(iy>=sh-1,15,fy))
   ix=np.clip(ix,0,sw-2);iy=np.clip(iy,0,sh-2)
   source=np.frombuffer(self.read(base,sw*sh*2),dtype='<u2').reshape(sh,sw).astype(np.int64)
   def mix(a,b,w):
    return ((((a&0xf81f)*(16-w)+(b&0xf81f)*w)>>4)&0xf81f)|((((a&0x7e0)*(16-w)+(b&0x7e0)*w)>>4)&0x7e0)
   return mix(mix(source[iy,ix],source[iy,ix+1],fx),mix(source[iy+1,ix],source[iy+1,ix+1],fx),fy)
  if c.lens>0:
   dx,dy=xx-200,yy-120;radius2=c.lens*c.lens>>8;distance2=dx*dx+dy*dy+1
   bend=radius2*4096//(distance2+radius2//4+1);gain=55706*(4096+2*bend)>>12
   u=512*65536+dx*gain;v=176*65536+dy*gain
  if c.lens<0:
   phase=(-c.lens-1)*256//110
   u=u+wave[(yy*2+phase)&255]*100;v=v+wave[(xx*2-phase)&255]*68
  pixels=sample(c.base,c.width,c.height,u,v)
  if c.lens>0:
   relative=np.minimum(1024,abs(distance2-radius2)*256//(radius2+1))
   ring=255*256//(256+relative*relative);halo=100*radius2//(distance2+radius2)
   hx=dx+(dy>>2);hy=dy-(dx>>2)
   delta=np.minimum(1024,abs(hx*hx+25*hy*hy-radius2*4)*128//(radius2*4+1))
   disk=255*400//(400+delta*delta)
   ripple=208+((wave[(hx*2+hy*5+t//2)&255]+16384)*47>>15);disk=disk*ripple//255
   r=np.minimum(31,(pixels>>11)+(ring*24+disk*31+halo*3)//255)
   g=np.minimum(63,((pixels>>5)&63)+(ring*60+disk*40+halo*8)//255)
   b=np.minimum(31,(pixels&31)+(ring*27+disk*8+halo*10)//255)
   pixels=(r<<11)|(g<<5)|b
   portal=np.zeros_like(pixels)
   if c.portal:
    gain=51118 if c.portal>=3840 else 196293120//c.portal
    phase_index=(t-4510+5500)%110;phase=phase_index*256//110;world=Camera()
    self.lib.cache_camera(660+phase_index,ctypes.byref(world))
    u=world.u+200*world.ux+dx*gain+wave[(yy*2+phase)&255]*100
    v=world.v+120*world.vy+dy*gain+wave[(xx*2-phase)&255]*68
    other=sample(world.base,world.width,world.height,u,v)
    portal=np.where(distance2<=c.portal*c.portal//256,other,0)
   pixels=np.where(distance2<radius2*3//4,portal,pixels)
  if c.portal==-1:
   tu=(u-376*65536)*2;tv=(v-81*65536)*2
   ix=tu>>16;iy=tv>>16;mask=(ix>=0)&(ix<255)&(iy>=0)&(iy<255)
   ix=np.clip(ix,0,254);iy=np.clip(iy,0,254);fx=(tu>>12)&15;fy=(tv>>12)&15
   station=np.frombuffer(self.read(self.manifest['regions']['station']['address'],256*256*2),dtype='<u2').reshape(256,256).astype(np.int64)
   accum=[np.zeros_like(pixels) for _ in range(4)]
   for j in range(2):
    for i in range(2):
     weight=(fx if i else 16-fx)*(fy if j else 16-fy);p=station[iy+j,ix+i];alpha=(p>>12)*weight
     accum[0]+=alpha
     for a,shift in zip(accum[1:],(8,4,0)):a+=((p>>shift)&15)*alpha
   channels=[]
   for a,shift,maximum in zip(accum[1:],(11,5,0),(31,63,31)):
    channels.append((a*maximum+((pixels>>shift)&maximum)*15*(3840-accum[0]))//57600)
   pixels=np.where(mask,(channels[0]<<11)|(channels[1]<<5)|channels[2],pixels)
  return pixels.astype('<u2').tobytes()
 def background(self,t,check=False):
  c=Camera();self.lib.camera(t,ctypes.byref(c));image=self.pixels(c,t)
  if check:
   array=(ctypes.c_uint16*96000)();data=(ctypes.c_uint8*len(self.raw)).from_buffer_copy(self.raw);self.lib.background(t,array,data)
   assert bytes(array)==image,('C vs independent background',t)
  return image
 def cached(self,index,check=False):
  c=Camera();self.lib.cache_camera(index,ctypes.byref(c));w,h=(400,240) if index<FULL else (ATLAS_W,ATLAS_H)
  image=self.pixels(c,self.lib.cache_clock(index),w,h)
  if check:
   array=(ctypes.c_uint16*(w*h))();data=(ctypes.c_uint8*len(self.raw)).from_buffer_copy(self.raw);self.lib.cache(index,array,data)
   assert bytes(array)==image,('C vs independent cache',index)
  return image
 def sweep(self):
  maximum=0;sprites=0;chapters=[0]*10
  for a in range(0,65536,13):assert abs(self.lib.sine(a/256)-math.sin(a*math.pi/32768))<.0002
  for i in range(CACHE_COUNT):
   c=Camera();self.lib.cache_camera(i,ctypes.byref(c))
   self.read(c.base,c.width*c.height*2)
   if i%17==0:self.cached(i,check=True)
  for t in range(TOTAL):
   c=Camera();d=Camera();self.lib.camera(t,ctypes.byref(c));index=self.lib.plate(t);self.lib.cache_camera(index,ctypes.byref(d))
   crop=(ctypes.c_int*2)();self.lib.crop(t,crop);x,y=crop
   d.u+=d.ux*x+d.uy*y;d.v+=d.vx*x+d.vy*y
   assert bytes(c)[:44]==bytes(d)[:44],('cached camera mismatch',t)
   assert 0<=index<CACHE_COUNT and 0<=x<=(ATLAS_W-400) and 0<=y<=(ATLAS_H-240)
   assert self.lib.render(t),t;maximum=max(maximum,self.lib.command_count())
   l,s,i=self.layers(t);assert i.frame==t and i.sprites<=64;chapters[i.chapter]+=1;sprites=max(sprites,i.sprites)
   assert bool(i.shots)==(7150<=t<8800 or 9295<=t<13475)
   if t%113==0:
    self.background(t,check=True)
    cached=np.frombuffer(self.cached(index),dtype='<u2').reshape((240,400) if index<FULL else (ATLAS_H,ATLAS_W))
    assert cached[y:y+240,x:x+400].tobytes()==self.background(t),('cache crop',t)
   for b,xy,p,_ in s:
    if p&65536:self.read(b,1024)
  assert chapters==[KEYS[i+1]-KEYS[i] for i in range(10)] and chapters[4]==30*55
  assert not self.lib.render(TOTAL) and not self.lib.render(0xffffffff)
  result=dict(phases=TOTAL,seconds=300,battle_seconds=chapters[4]/55,max_commands=maximum,max_sprites=sprites,chapter_phases=chapters,ubsan='PASS')
  print(json.dumps(result),flush=True);return result
 def hud(self,fps,cps,sprites,layers):
  self.lib.hud(fps,cps,sprites,layers)
  words=self.lib.command_words();count=self.lib.command_count()
  pixels=np.zeros((32,800),dtype=np.uint8)
  font=np.array([int(v,16) for v in (ROOT/'tang/rtl/video/font8x16.hex').read_text().split()],dtype=np.uint8).reshape(256,16)
  for i in range(count):
   c=[words[i*8+j] for j in range(8)];op=c[0]>>24;x,y=c[1]>>16,c[1]&65535;fg=(c[0]>>8)&255;bg=c[0]&255
   assert (c[0]>>20)&15==8
   if op==1:
    w,h=c[2]>>16,c[2]&65535;assert x+w<=800 and y+h<=32
    pixels[y:y+h,x:x+w]=fg
   else:
    assert op==9 and c[2]&65535==1
    chars=struct.pack('<4I',*c[4:8])[:c[2]>>16]
    for k,ch in enumerate(chars):
     assert 32<=ch<=90 and x+(k+1)*8<=800 and y+16<=32
     bits=(font[ch,:,None]>>np.arange(7,-1,-1))&1
     pixels[y:y+16,x+k*8:x+k*8+8]=np.where(bits,fg,bg)
  self.hud_pixels=pixels.tobytes();return count
 def render(self,t,poison=0xa5,fast=False,hud_fps=0,hud_cps=0):
  m=(FastAstrillaModel if fast else AstrillaModel)(self.raw,self.base,poison);cmds=self.commands(t)
  background=self.cached(self.lib.plate(t));m.memory[6*(1<<20):6*(1<<20)+len(background)]=background
  geometry=None
  if self.geometry:
   from gpu_geometry_model import Geometry
   old_at=m.at
   m.at=lambda a: 5*(1<<20)+a-0x06000000 if 0x06000000<=a<0x06008000 else old_at(a)
   m.memory[5*(1<<20):5*(1<<20)+len(self.geometry_bytes)]=self.geometry_bytes
   geometry=Geometry(m)
  for c in cmds:
   if geometry:geometry.command(c)
   else:m.apply(c)
  for p in (0,2):assert m.memory[p*(1<<20)+192000:(p+1)*(1<<20)]==bytes([poison])*((1<<20)-192000)
  assert m.memory[(1<<20):2*(1<<20)]==bytes([poison])*(1<<20)
  assert m.memory[8*(1<<20):]==self.raw
  l,s,info=self.layers(t);native_layers=sum(bool(v[6]&1) for v in l);hud_commands=self.hud(hud_fps,hud_cps,info.sprites,native_layers);indices=np.frombuffer(bytes(compose(l,s,self.read)),dtype=np.uint8).reshape(480,800)
  pixels=np.frombuffer(m.memory[:192000],dtype='<u2').reshape(240,400).repeat(2,0).repeat(2,1).astype(np.uint32)
  r=pixels>>11;g=(pixels>>5)&63;b=pixels&31;rgb=np.stack((r*2+(r>>4),g,b*2+(b>>4)),axis=-1)
  overlay=np.array(self.palette,dtype=np.uint32)[indices];mask=indices!=0;values=np.stack(((overlay>>12)&63,(overlay>>6)&63,overlay&63),axis=-1);rgb[mask]=values[mask]
  lcd=int(np.sum((rgb[:,:,0]<<12)+(rgb[:,:,1]<<6)+rgb[:,:,2],dtype=np.uint64))&0xffffffff
  record=dict(frame=t,chapter=info.chapter,mode='rgb565',lcd=f'{lcd:08x}',crc565=f'{zlib.crc32(m.memory[:192000]):08x}',commands=len(cmds)+hud_commands,scene_commands=len(cmds),fragments=m.passed,sprites=info.sprites,layers=native_layers,hud_fps_x10=hud_fps,hud_cmds_s=hud_cps,hud_crc=f'{zlib.crc32(self.hud_pixels):08x}')
  if geometry:record.update(hardware_geometry=True,vertices=geometry.vertices,triangles=geometry.triangles,culled=geometry.culled,intersections=geometry.clipped,slivers=geometry.slivers)
  return Image.fromarray(((rgb*255+31)//63).astype(np.uint8)),record
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'TESTS/astrilla_20261009/reference');p.add_argument('--sweep',action='store_true');p.add_argument('--hardware-geometry',action='store_true');p.add_argument('--poses',type=int,nargs='+',default=POSES);p.add_argument('--fast',action='store_true');p.add_argument('--animation',action='store_true');p.add_argument('--fps',type=int,default=10);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);scene=Scene(geometry=a.hardware_geometry)
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
