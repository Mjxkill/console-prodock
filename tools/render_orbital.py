#!/usr/bin/env python3
"""Execute the shared ORBITAL 3D scene under UBSan and independent pixel oracle."""
import argparse,ctypes,json,math,struct,subprocess,tempfile,sys,zlib
from pathlib import Path
import numpy as np
from PIL import Image
from render_gpu_demo import brace_block
from gpu_compose import compose
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'TESTS'))
from test_gpu_v1 import Model
TOTAL=13200
# One or more poses per chapter and per effect: title, corridor fight, bulkhead, bay, tower door,
# lift ride, reactor and core, guardian fight and fall, red alert run, outer deck, reinforcements, dawn.
POSES=(40,250,560,690,720,1090,1560,2030,2200,2500,2790,3110,3500,3900,4100,4350,4700,4890,5200,5450,5700,6090,6400,6590,6800,7090,7400,7700,8000,8300,8790,9100,9500,9800,9990,10030,10100,10250,10450,10700,10890,11150,11500,11700,11950,12290,12590,12650,12800,12900,13100)
class Info(ctypes.Structure):
 _fields_=[(n,ctypes.c_uint if i<4 else ctypes.c_int) for i,n in enumerate(('frame','chapter','sprites','shots','aim_x','aim_y'))]
class OrbModel(Model):
 def __init__(self,assets,base):
  self.memory=bytearray([0xa5])*(8*(1<<20))+bytearray(assets);self.asset_base=base;self.asset_bytes=len(assets);self.commands=[];self.rejected=0;self.passed=0;self.planes={}
 def at(self,a):
  if 0x800000<=a<0x1000000:return a-0x800000   # pages 0..7: colour, depth, HUD, wall screens
  assert self.asset_base<=a<self.asset_base+self.asset_bytes,hex(a)
  return 8*(1<<20)+a-self.asset_base
class Scene:
 def __init__(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='orbital_');work=Path(self.tmp.name);driver=(ROOT/'fw_console/gpu.c').read_text()
  prototypes='#include "gpu.h"\n'
  code=prototypes+'#include "orbital_scene.h"\n'+'\n'.join(brace_block(driver,s) for s in ('gpu_command gpu_make_command(','gpu_layer gpu_make_layer(','gpu_layer gpu_make_tile_layer(','gpu_sprite gpu_make_sprite('))
  code+='''
static gpu_command commands[8192];static unsigned count;
static void emit(const gpu_command *c){if(count<8192)commands[count]=*c;++count;}
unsigned command_count(void){return count;}
uint32_t *command_words(void){return commands[0].words;}
int render(unsigned f,unsigned mask){orb_skip=mask;count=0;gpu_v1_context c;gpu_v1_init(&c,emit);return orbital_render(&c,f,0)&&count<=8192;}
int sine(unsigned p){return orb_sin(p);}
void layers(unsigned f,unsigned hud,gpu_layer *l,gpu_sprite *s,orb_info *i){orbital_layers(f,hud,l,s,i);}
static gpu_command hud_commands[256];static unsigned hud_count;
static void hud_emit(const gpu_command *c){if(hud_count<256)hud_commands[hud_count]=*c;++hud_count;}
unsigned hud(unsigned f,int previous,unsigned page){hud_count=0;orbital_hud(f,previous,page,hud_emit);return hud_count;}
uint32_t *hud_words(void){return hud_commands[0].words;}
uint32_t palette(unsigned f,unsigned i,uint32_t c){return orbital_palette(f,i,c);}
'''
  (work/'scene.c').write_text(code);subprocess.run(['cc','-std=c11','-O2','-Wall','-Wextra','-Wno-unused-function','-fsanitize=undefined','-fno-sanitize-recover=all','-shared','-fPIC','-I',str(ROOT/'fw_console'),'-I',str(ROOT/'games/orbital/src'),str(work/'scene.c'),str(ROOT/'fw_console/gpu_v1.c'),'-o',str(work/'scene.so')],check=True)
  self.lib=ctypes.CDLL(str(work/'scene.so'));self.lib.command_words.restype=ctypes.POINTER(ctypes.c_uint32);self.lib.hud_words.restype=ctypes.POINTER(ctypes.c_uint32);self.lib.palette.restype=ctypes.c_uint32
  # The indexed 2D commands of the HUD page are drawn by reference_draw, the software reference
  # of the G2..L12 milestones in fw_console/gpu_demo.h: independent of this scene and of the RTL.
  (work/'build').mkdir();subprocess.run([sys.executable,str(ROOT/'tools/gen_gpu_font.py'),str(ROOT/'tang/rtl/video/font8x16.hex'),str(work/'build/gpu_font.h')],check=True)
  reference=(ROOT/'fw_console/gpu_demo.h').read_text().split('static int gpu_accel_demo(void)',1)[0]
  (work/'hud.c').write_text('#include <stdint.h>\n#include <string.h>\n#include "gpu.h"\nstatic uint8_t pages[16][4];\n#undef GPU_PAGE_ADDR\n#define GPU_PAGE_ADDR(p) ((uintptr_t)pages[p])\n'+brace_block(driver,'gpu_command gpu_make_command(')+'\n'+reference+'\nvoid hud_apply(const uint32_t *w,uint8_t *page){gpu_command c;memcpy(c.words,w,32);reference_draw(&c,page);}\n')
  subprocess.run(['cc','-std=c11','-O2','-Wno-unused-function','-fsanitize=undefined','-fno-sanitize-recover=all','-shared','-fPIC','-I',str(ROOT/'fw_console'),'-I',str(ROOT/'games/orbital/src'),'-I',str(work),str(work/'hud.c'),'-o',str(work/'hud.so')],check=True)
  self.hudlib=ctypes.CDLL(str(work/'hud.so'));self.page=bytes(384000)
  self.raw=(ROOT/'games/orbital/assets/packed/orbital.bin').read_bytes();self.manifest=json.loads((ROOT/'games/orbital/assets/packed/manifest.json').read_text());self.base=self.manifest['base'];self.palette=struct.unpack('<256I',self.read(self.manifest['regions']['palette']['address'],1024))
 HUD=0x800000+4*(1<<20)
 def read(self,a,n):
  if self.HUD<=a<=self.HUD+384000-n:return self.page[a-self.HUD:a-self.HUD+n]
  assert self.base<=a<=self.base+len(self.raw)-n,(hex(a),n)
  return self.raw[a-self.base:a-self.base+n]
 def hud(self,t,previous=-1,page=None):
  # HUD page of the frame: opcodes 1..9 only. From an empty page, or over the page of an earlier phase.
  n=self.lib.hud(t,previous,4);assert 0<n<=128,n
  w=self.lib.hud_words();page=(ctypes.c_uint8*384000)(*page) if page else (ctypes.c_uint8*384000)()
  for i in range(n):
   words=(ctypes.c_uint32*8)(*w[i*8:i*8+8]);assert 1<=words[0]>>24<=9 and (words[0]>>20)&15==4,hex(words[0]);self.hudlib.hud_apply(words,page)
  self.page=bytes(page);return n
 def colours(self,t):return [self.lib.palette(t,i,c) for i,c in enumerate(self.palette)]
 def layers(self,t):
  l=((ctypes.c_uint32*8)*16)();s=((ctypes.c_uint32*4)*64)();i=Info();self.lib.layers(t,4,l,s,ctypes.byref(i));return [tuple(v) for v in l],[tuple(v) for v in s],i
 def commands(self,t,mask=0):
  assert self.lib.render(t,mask),t
  n=self.lib.command_count();w=self.lib.command_words();return [list(w[i*8:i*8+8]) for i in range(n)]
 def sweep(self):
  maximum=0;sprites=0
  # A truncated table once made cos(0)=0 and the whole station vanish at zero yaw.
  for p in range(256):assert abs(self.lib.sine(p)-16384*math.sin(p*math.pi/128))<=0.5,p
  for t in range(TOTAL):
   cmds=self.commands(t);maximum=max(maximum,len(cmds));assert t<150 or sum(c[0]>>24==28 for c in cmds)>=40,f'station missing at phase {t}'
   l,s,i=self.layers(t);sprites=max(sprites,i.sprites);assert i.sprites<=64
   # The incremental HUD (over the page drawn two frames earlier, or after a jump) must leave
   # exactly the page of a full redraw.
   if t%3==0:
    self.hud(t);full=self.page
    for previous in (t-2,(t*7919)%TOTAL):
     if previous>=0:
      self.hud(previous);old=self.page;self.hud(t,previous,old);assert self.page==full,(t,previous)
   for b,xy,p,_ in s:
    if p&65536:self.read(b,1024)
  print(f'PASS {TOTAL} phases under UBSan, max {maximum} GPU commands / {sprites} sprites',flush=True)
 def render(self,t,mask=0):
  m=OrbModel(self.raw,self.base);cmds=self.commands(t,mask)
  for c in cmds:m.apply(c)
  for page in range(3):assert m.memory[page*(1<<20)+192000:(page+1)*(1<<20)]==bytes([0xa5])*((1<<20)-192000)
  self.hud(t);l,s,info=self.layers(t);indices=np.frombuffer(bytes(compose(l,s,self.read)),dtype=np.uint8).reshape(480,800)
  pixels=np.frombuffer(m.memory[:192000],dtype='<u2').reshape(240,400).repeat(2,axis=0).repeat(2,axis=1).astype(np.uint32)
  r=pixels>>11;g=(pixels>>5)&63;b=pixels&31;rgb=np.stack((r*2+(r>>4),g,b*2+(b>>4)),axis=-1)
  overlay=np.array(self.colours(t),dtype=np.uint32)[indices];mask=indices!=0;values=np.stack(((overlay>>12)&63,(overlay>>6)&63,overlay&63),axis=-1);rgb[mask]=values[mask]
  lcd=int(np.sum((rgb[:,:,0]<<12)+(rgb[:,:,1]<<6)+rgb[:,:,2],dtype=np.uint64))&0xffffffff
  record=dict(frame=t,mode='rgb565',lcd=f'{lcd:08x}',crc565=f'{zlib.crc32(m.memory[:192000]):08x}',commands=len(cmds),fragments=m.passed,sprites=info.sprites)
  return Image.fromarray(((rgb*255+31)//63).astype(np.uint8)),record
def prove(phases):
 # Coverage proof: with the sky copied only where it is expected to show, every byte of the
 # page must equal the page obtained with a full-screen sky copy, from a poisoned memory.
 scene=Scene();bad=[]
 for t in phases:
  pages=[]
  for mask in (0,256):
   m=OrbModel(scene.raw,scene.base)
   for c in scene.commands(t,mask):m.apply(c)
   pages.append(bytes(m.memory[:192000]))
  if pages[0]!=pages[1]:bad.append((t,sum(a!=b for a,b in zip(pages[0][::2],pages[1][::2]))))
 return bad
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,default=ROOT/'TESTS/orbital_20261005/reference_r6');p.add_argument('--sweep',action='store_true');p.add_argument('--poses',type=int,nargs='+',default=POSES);p.add_argument('--animation',action='store_true');p.add_argument('--prove',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);scene=Scene()
 if a.sweep:scene.sweep()
 if a.prove:
  import multiprocessing
  with multiprocessing.Pool() as pool:bad=sorted(sum(pool.map(prove,[range(i,TOTAL,64) for i in range(64)]),[]))
  assert not bad,f'{len(bad)} phases differ from the full-sky page: {bad[:12]}'
  print(f'PASS {TOTAL} phases identical to the full-screen sky copy',flush=True)
 records=[]
 for t in a.poses:
  im,r=scene.render(t);im.save(a.out/f'frame_{t:04}.png');records.append(r);print(r,flush=True)
 (a.out/'expected.json').write_text(json.dumps(records,indent=2)+'\n')
 if a.animation:
  cmd=['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size','800x480','-framerate','5.0036','-i','-','-an','-c:v','libx264','-preset','medium','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(a.out/'orbital.mp4')]
  with subprocess.Popen(cmd,stdin=subprocess.PIPE) as enc:
   for t in range(0,TOTAL,11):enc.stdin.write(scene.render(t)[0].tobytes())
   enc.stdin.close();assert enc.wait()==0
