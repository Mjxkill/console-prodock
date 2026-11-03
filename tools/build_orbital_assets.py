#!/usr/bin/env python3
"""Pack original ORBITAL art for R31: RGB565/ARGB4444 plus native indexed HUD."""
from pathlib import Path
import colorsys,hashlib,json,math,struct,zlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'games/orbital/assets/packed';BASE=0x05000000

def font(n):return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',n)
def label(im,xy,text,n=14,color=(155,236,247,255)):
 ImageDraw.Draw(im).text(xy,text,font=font(n),fill=color)
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 # The rifle aims: 17 frames turned about a pivot on the lower edge, from -20 to +20 degrees.
 # The canvas is larger than the 416x248 rifle so that the turned barrel is never cropped;
 # the cut wrists stay below the bottom HUD band.
 source=Image.open(ROOT/'games/orbital/assets/source/weapon.png').convert('RGBA');scale=416/source.width
 FW,FH,OX,OY=512,320,96,72;pivot=(OX+258,OY+248);muzzle0=(OX+127,OY+29);weapons=[];muzzles=[]
 for i in range(17):
  angle=(i-8)*2.5;big=Image.new('RGBA',(int(FW/scale),int(FH/scale)));big.paste(source,(int(OX/scale),int(OY/scale)))
  turned=big.rotate(angle,resample=Image.Resampling.BICUBIC,center=(pivot[0]/scale,pivot[1]/scale)).resize((FW,FH),Image.Resampling.LANCZOS)
  weapons.append(turned);a=math.radians(-angle);dx,dy=muzzle0[0]-pivot[0],muzzle0[1]-pivot[1]
  muzzles.append((round(pivot[0]+dx*math.cos(a)-dy*math.sin(a)),round(pivot[1]+dx*math.sin(a)+dy*math.cos(a))))
 weapon=weapons[8]
 top=Image.new('RGBA',(800,48));d=ImageDraw.Draw(top);d.rectangle((0,0,799,47),fill=(7,16,27,255));d.line((0,47,799,47),fill=(48,116,148,255))
 label(top,(18,8),'ORBITAL',22);label(top,(652,9),'AUTO // R31',14);label(top,(318,8),'BOUCLIER',10)
 bottom=Image.new('RGBA',(800,38));d=ImageDraw.Draw(bottom);d.rectangle((0,0,799,37),fill=(7,16,27,255));d.line((0,0,799,0),fill=(48,116,148,255));label(bottom,(18,10),'STATION AURORA  /  SECTEUR 07',12);label(bottom,(300,10),'DÉMONSTRATION AUTOMATIQUE',12);label(bottom,(584,12),'DRONES',11);label(bottom,(700,12),'AR-7',11)
 captions=[]
 for a,b in [('SAS D’AMARRAGE','Station Aurora · Drones hostiles à bord'),('BAIE D’OBSERVATION','Traverser la plate-forme panoramique'),('MONTE-CHARGE','Descente vers le cœur de la station'),('SALLE DU RÉACTEUR','Le cœur est instable · Rester à couvert'),('LE GARDIEN','Détruire la machine de guerre'),('ALERTE','Réacteur critique · Évacuation immédiate'),('PONT EXTÉRIEUR','Les renforts arrivent')]:
  im=Image.new('RGBA',(448,64),(7,20,31,255));d=ImageDraw.Draw(im);d.line((0,0,447,0),fill=(64,203,228,255));label(im,(16,7),a,17);label(im,(16,34),b,12);captions.append(im)
 title=Image.new('RGBA',(512,150),(7,20,31,230));label(title,(63,16),'ORBITAL',69);label(title,(99,106),'DÉMONSTRATION GPU  /  PRO DOCK',14)
 finish=Image.new('RGBA',(512,110),(7,20,31,230));label(finish,(56,10),'STATION SÉCURISÉE',35);label(finish,(95,65),'ORBITAL  ·  LE VOYAGE RECOMMENCE',14)
 # Motion tracker, guardian gauge and counters of the native HUD.
 gauge=Image.new('RGBA',(320,32),(7,20,31,255));d=ImageDraw.Draw(gauge);d.rectangle((0,0,319,31),outline=(244,85,201,255));label(gauge,(10,7),'GARDIEN',14,(255,211,90,255))
 images=weapons+[top,bottom,title,finish,gauge]+captions
 colors=np.concatenate([np.asarray(im)[:,:,:3][np.asarray(im)[:,:,3]>=128] for im in images]);colors=colors[:len(colors)//256*256]
 trained=Image.fromarray(colors.reshape(-1,256,3)).quantize(colors=223,method=Image.Quantize.MEDIANCUT)
 # 224..239: ramp from bright cyan to deep blue, the range the 2D gradient opcodes interpolate.
 ramp=[(80-70*k//15,220-180*k//15,255-165*k//15) for k in range(16)]
 pal=[(0,0,0)]+list(zip(*[iter(trained.getpalette()[:223*3])]*3))+ramp+[(240,250,255),(80,220,255),(255,211,90),(244,85,201),(10,27,43),(80,170,200),(255,255,220),(40,110,150),(255,150,50),(110,200,244),(122,244,255),(255,80,40),(255,235,140),(25,60,95),(77,130,170),(0,0,0)]
 palette=Image.new('P',(1,1));palette.putpalette(sum((list(c) for c in pal),[]))
 def quant(im):
  a=np.asarray(im.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE)).copy();opaque=np.asarray(im)[:,:,3]>=128;a[~opaque]=0;a[opaque&(a==0)]=244;return a
 data=bytearray(1024);regions={}
 def add(name,raw,**meta):
  data.extend(bytes((-len(data))%32));off=len(data);data.extend(raw);regions[name]=dict(address=BASE+off,offset=off,bytes=len(raw),**meta)
 def rgb565(im):
  a=np.asarray(im.convert('RGB')).astype(np.uint32);return (((a[:,:,0]*31+127)//255<<11)|((a[:,:,1]*63+127)//255<<5)|((a[:,:,2]*31+127)//255)).astype('<u2').tobytes()
 add('palette',struct.pack('<256I',*[((r*63+127)//255<<12)|((g*63+127)//255<<6)|((b*63+127)//255) for r,g,b in pal]))
 sky=Image.open(ROOT/'games/orbital/assets/source/sky.png').convert('RGB').resize((512,256),Image.Resampling.LANCZOS);add('sky',rgb565(sky),width=512,height=256,stride=1024)
 add('weapon',b''.join(quant(im).tobytes() for im in weapons),width=FW,height=FH,frames=17)
 for name,im in [('top',top),('bottom',bottom),('title',title),('finish',finish),('gauge',gauge)]+[(f'caption{i}',im) for i,im in enumerate(captions)]:add(name,quant(im).tobytes(),width=im.width,height=im.height)
 enemy=Image.open(ROOT/'games/orbital/assets/source/drones.png').convert('RGBA')
 # Four kinds of enemies: the drone sheet of the first session, then the elite, the Guardian and
 # the scout generated on a green screen by tools/orbital_art.py (four poses each, the last three
 # edited from the first so that the machine keeps its identity).
 GEN=ROOT/'games/orbital/assets/source/gen'
 def keyed(name):
  a=np.asarray(Image.open(GEN/f'{name}.png').convert('RGB')).astype(np.int32);r,g,b=a[:,:,0],a[:,:,1],a[:,:,2]
  screen=(g>70)&(g*4>np.maximum(r,b)*5)
  # one pixel of the outline is given up to the screen, and what green remains on the edge is removed
  grown=screen.copy()
  for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):grown|=np.roll(screen,(dy,dx),axis=(0,1))
  out=np.dstack([r,np.minimum(g,np.maximum(r,b)+12),b,np.where(grown,0,255)]).astype(np.uint8);return Image.fromarray(out,'RGBA')
 def poses_of(kind,size):
  # one square frame for the four poses, from the union of their outlines: they stay registered
  ims=[keyed(f'{kind}{i}') for i in range(4)];boxes=[im.getbbox() for im in ims]
  x0=min(b[0] for b in boxes);y0=min(b[1] for b in boxes);x1=max(b[2] for b in boxes);y1=max(b[3] for b in boxes)
  side=max(x1-x0,y1-y0)+16;cx=(x0+x1)//2;cy=(y0+y1)//2;frame=(cx-side//2,cy-side//2,cx-side//2+side,cy-side//2+side)
  return [im.crop(frame).resize((size,size),Image.Resampling.LANCZOS) for im in ims]
 def argb(im):
  a=np.asarray(im).astype(np.uint16);return ((a[:,:,3]*15+127)//255<<12)|((a[:,:,0]//17)<<8)|((a[:,:,1]//17)<<4)|(a[:,:,2]//17)
 def occupancy(v,cell):
  occupied=(v>>12).reshape(8,cell,8,cell).max(axis=(1,3))>0;return [int(sum(1<<c for c in range(8) if row[c])) for row in occupied]
 cells=[]
 drone=[enemy.crop(((i%2)*enemy.width//2,(i//2)*enemy.height//2,(i%2+1)*enemy.width//2,(i//2+1)*enemy.height//2)).resize((128,128),Image.Resampling.LANCZOS) for i in range(4)]
 for kind,ims,size in (('drone',drone,128),('elite',poses_of('elite',128),128),('guardian',poses_of('guardian',256),256),('scout',poses_of('scout',128),128)):
  for i,im in enumerate(ims):
   v=argb(im);add(f'{kind}{i}',v.astype('<u2').tobytes(),width=size,height=size,stride=size*2);cells.append(occupancy(v,size//8))
 # Dawn sky of the lower level and of the finale, and the opening illustration (400x197, the 3D window).
 sky2=Image.open(GEN/'sky2.png').convert('RGB').resize((512,256),Image.Resampling.LANCZOS);add('sky2',rgb565(sky2),width=512,height=256,stride=1024)
 art=Image.open(GEN/'title.png').convert('RGB');art=art.resize((400,200),Image.Resampling.LANCZOS).crop((0,2,400,199));add('art',rgb565(art),width=400,height=197,stride=800)
 # Decor textures, 128x128, generated flat and seen in perspective by the GPU.
 for name in ('panel','floor','pillar','crate','door'):
  add(f'tex_{name}',rgb565(Image.open(GEN/f'tex_{name}.png').convert('RGB').resize((128,128),Image.Resampling.LANCZOS)),width=128,height=128,stride=256)
 # Native crosshair, shield and an indexed particles/flash atlas.
 cross=Image.new('L',(32,32));d=ImageDraw.Draw(cross);d.line((4,16,11,16),fill=241);d.line((21,16,28,16),fill=241);d.line((16,4,16,11),fill=241);d.line((16,21,16,28),fill=241);d.point((16,16),fill=240);add('crosshair',cross.tobytes())
 add('shield',bytes([241])*256*8)
 fx=[]
 for k in range(16):
  im=Image.new('L',(32,32));d=ImageDraw.Draw(im);r=3+(k%4)*3;c=242 if k<8 else 243
  if k<4:d.ellipse((16-r,16-r,16+r,16+r),fill=c);d.ellipse((14-r//2,14-r//2,18+r//2,18+r//2),fill=246)
  elif k<8:d.polygon([(16,1),(19,12),(30,8),(22,17),(31,25),(20,21),(16,31),(12,21),(1,25),(9,17),(2,7),(13,12)],fill=c);d.ellipse((12,12,20,20),fill=246)
  else:d.line((16-r,16,16+r,16),fill=c,width=2);d.line((16,16-r,16,16+r),fill=c,width=2)
  fx.append(im.tobytes())
 add('effects',b''.join(fx))
 # Station emblem: 512x512 with three precomputed mipmap levels, selected by distance.
 emblem=Image.open(GEN/'tex_emblem.png').convert('RGB')
 for level in range(4):
  side=512>>level;add(f'emblem{level}',rgb565(emblem.resize((side,side),Image.Resampling.LANCZOS)),width=side,height=side,stride=side*2)
 # Perforated girder: colour 0 is the key of the texture, the holes show what is behind. Tiles vertically.
 girder=Image.new('RGB',(128,128),(0,0,0));d=ImageDraw.Draw(girder)
 for x0,x1 in ((0,22),(105,127)):d.rectangle((x0,0,x1,127),fill=(92,104,118));d.line((x0+3,0,x0+3,127),fill=(140,152,160));d.line((x1-3,0,x1-3,127),fill=(48,56,66))
 for y0 in (0,64):
  d.line((22,y0,105,y0+63),fill=(104,116,128),width=9);d.line((105,y0,22,y0+63),fill=(84,96,110),width=9);d.rectangle((0,y0,127,y0+7),fill=(70,80,92));d.rectangle((0,y0+2,127,y0+3),fill=(255,150,50))
 pixels=np.frombuffer(rgb565(girder),dtype='<u2').reshape(128,128).copy();solid=np.asarray(girder).sum(axis=2)>0;pixels[solid&(pixels==0)]=0x0841;pixels[~solid]=0
 add('girder',pixels.tobytes(),width=128,height=128,stride=256)
 # Font atlas of gpu_v1_text: the console 8x16 font, 16 glyphs per row, ARGB4444 opaque white on clear.
 glyphs=[int(line,16) for line in (ROOT/'tang/rtl/video/font8x16.hex').read_text().split()];assert len(glyphs)==4096
 atlas=np.zeros((256,128),dtype='<u2')
 for ch in range(256):
  for y in range(16):
   for x in range(8):
    if glyphs[ch*16+y]&(128>>x):atlas[(ch//16)*16+y,(ch%16)*8+x]=0xffff
 add('font',atlas.tobytes(),width=128,height=256,stride=256)
 # Alert ticker: a 64x1 map of 16x16 tiles scrolled by the compositor, no drawing command.
 # '<' is the '>' tile with the horizontal flip bit.
 message='  ALERTE  >>>  REACTEUR CRITIQUE  >>>  EVACUATION  <<<  PONT 7  '.ljust(64)[:64];letters=sorted(set(message.replace('<','>'))-{' '})
 tiles=[bytes(256)]
 for ch in letters:
  im=Image.new('L',(16,16));ImageDraw.Draw(im).text((2,-1),ch,font=font(15),fill=255);tiles.append(bytes(251 if v>110 else 0 for v in im.tobytes()))
 add('tiles',b''.join(tiles),tile=16,count=len(tiles))
 cells_of=[0 if ch==' ' else (letters.index('>')+1)|0x4000 if ch=='<' else letters.index(ch)+1 for ch in message]
 add('ticker',struct.pack('<64H',*cells_of),width=64,height=1)
 data.extend(bytes((-len(data))%32));crc=zlib.crc32(data[1024:]);struct.pack_into('<4I',data,0,0x4f524249,1,len(data),crc);(OUT/'orbital.bin').write_bytes(data)
 m=dict(version=1,base=BASE,bytes=len(data),crc32=f'{crc:08x}',sha256=hashlib.sha256(data).hexdigest(),regions=regions,sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'games/orbital/assets/source').glob('*.png'))});(OUT/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 h=['// Generated by tools/build_orbital_assets.py','#ifndef ORBITAL_ASSETS_H','#define ORBITAL_ASSETS_H',f'#define ORBITAL_BASE 0x{BASE:08x}UL',f'#define ORBITAL_BYTES {len(data)}UL',f'#define ORBITAL_CRC 0x{crc:08x}U']+[f'#define ORBITAL_{name.upper()} 0x{r["address"]:08x}UL' for name,r in regions.items()]+['#define ORBITAL_CELLS {'+','.join('{'+','.join(f'0x{v:02x}' for v in pose)+'}' for pose in cells)+'}',f'#define ORBITAL_WEAPON_W {FW}',f'#define ORBITAL_WEAPON_H {FH}',f'#define ORBITAL_PIVOT_X {pivot[0]}',f'#define ORBITAL_PIVOT_Y {pivot[1]}','#define ORBITAL_MUZZLES {'+','.join(f'{{{x},{y}}}' for x,y in muzzles)+'}']+['#endif',''];(ROOT/'games/orbital/src/orbital_assets.h').write_text('\n'.join(h));print(json.dumps({k:m[k] for k in ('bytes','crc32','sha256')},indent=2))
if __name__=='__main__':main()
