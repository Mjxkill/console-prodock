#!/usr/bin/env python3
"""Compile authored worlds and replaceable atlas artwork into the GPU ABI.

Only this game's build/ directory is written. Existing LUMA art is explicitly
the provisional fallback until the ComfyUI atlas manifest is installed.
"""
from pathlib import Path
import argparse,ctypes,ctypes.util,hashlib,json,math,struct,unicodedata,zlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
OUT=ROOT/'build'
KINDS=['npc','shrine','chest','crystal','enemy','sign','portal','stable','boss','door','switch','target','plate','crate','sequence','lamp','emitter','mirror','receiver']
ART=['player','npc','shrine','chest','crystal','enemy','sign','portal','stable','boss','horse','parachute','plane','glider','scooter','bike','car','shrine_lit','chest_open']
def ascii_text(s):return unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode()
def cstr(s):return json.dumps(s,ensure_ascii=False)
def rgb565(im):
 a=np.asarray(im.convert('RGB'),dtype=np.uint32)
 return (((a[:,:,0]>>3)<<11)|((a[:,:,1]>>2)<<5)|(a[:,:,2]>>3)).astype('<u2')
def unique_ids(ids,context):
 hashes=[zlib.crc32(s.encode()) for s in ids]
 assert len(ids)==len(set(ids)) and len(hashes)==len(set(hashes)),f'{context}: duplicate IDs or CRC32 collision'
def read_worlds():
 campaign=ROOT/'content/campaign.json'
 paths=json.loads(campaign.read_text())['worlds'] if campaign.exists() else ['world.json']
 worlds=[]
 for p in paths:
  if isinstance(p,dict):p=p.get('file',p.get('path'))
  w=json.loads((ROOT/'content'/p).read_text());w.setdefault('tile',32)
  rows=w.get('rows',w.get('terrain'));rows=rows.get('rows') if isinstance(rows,dict) else rows
  assert len(rows)==w['height'] and all(len(r)==w['width'] for r in rows),(p,'terrain size')
  w['rows']=rows;assert len(w['entities'])<=64
  ids=[e['id'] for e in w['entities']];unique_ids(ids,p)
  worlds.append(w)
 assert 1<=len(worlds)<=96
 unique_ids([w.get('id',str(i)) for i,w in enumerate(worlds)],'worlds')
 return worlds
def world_image(w,index,terrain):
 width,height,t=w['width'],w['height'],w['tile'];im=Image.new('RGB',(width*t,height*t));d=ImageDraw.Draw(im)
 colors={'.':(78,111,76),',':(87,124,78),'=':(174,155,112),':':(187,173,132),'~':(36,109,124),'#':(79,86,89),'t':(55,93,64),'H':(106,95,74)}
 palette=w.get('terrain',{}).get('palette',{}) if isinstance(w.get('terrain'),dict) else {}
 for ch,value in palette.items():colors[ch]=tuple(bytes.fromhex(value.lstrip('#')))
 rng=np.random.default_rng(0x4c554d41+index);road_rect=w.get('road_override_rect')
 for y,row in enumerate(w['rows']):
  for x,ch in enumerate(row):
   xx,yy=x*t,y*t
   if ch=='=' and road_rect and road_rect['x']<=xx<road_rect['x']+road_rect['w'] and road_rect['y']<=yy<road_rect['y']+road_rect['h']:ch='.'
   c=colors.get(ch,colors['.']);v=int(rng.integers(-5,6));c=tuple(max(0,min(255,a+v)) for a in c);d.rectangle((xx,yy,xx+t-1,yy+t-1),fill=c)
   material=('indoor_wall' if ch=='#' else 'indoor_floor' if ch in '.,=:H' else ch) if w.get('indoors') else ch
   if material not in terrain:material=ch
   if material in terrain:
    key=(x*73856093)^(y*19349663)^(index*83492791);variants=terrain[material];tile=variants[key%len(variants)].resize((t,t))
    if ch=='=' and '.' in terrain and not w.get('indoors'):
     grass=terrain['.'][(key>>5)%len(terrain['.'])].resize((t,t));im.paste(grass,(xx,yy));mask=Image.new('L',(t,t));md=ImageDraw.Draw(mask);md.rounded_rectangle((t//8,t//8,t*7//8-1,t*7//8-1),radius=3,fill=255)
     if x>0 and row[x-1]=='=':md.rectangle((0,t//8,t//2,t*7//8-1),fill=255)
     if x+1<width and row[x+1]=='=':md.rectangle((t//2,t//8,t-1,t*7//8-1),fill=255)
     if y>0 and w['rows'][y-1][x]=='=':md.rectangle((t//8,0,t*7//8-1,t//2),fill=255)
     if y+1<height and w['rows'][y+1][x]=='=':md.rectangle((t//8,t//2,t*7//8-1,t-1),fill=255)
     im.paste(tile,(xx,yy),mask)
    else:im.paste(tile,(xx,yy))
    if ch=='#' and w.get('indoors'):
     mean=np.asarray(tile).mean(axis=(0,1));shade=tuple(int(a*.58) for a in mean);edge=tuple(min(255,int(a*1.4+10)) for a in mean)
     if y+1<height and w['rows'][y+1][x]!='#':d.rectangle((xx,yy+t-6,xx+t-1,yy+t-1),fill=shade);d.line((xx,yy+t-7,xx+t-1,yy+t-7),fill=edge)
     if y and w['rows'][y-1][x]!='#':d.line((xx,yy,xx+t-1,yy),fill=edge)
     if x and row[x-1]!='#':d.line((xx,yy,xx,yy+t-1),fill=edge)
     if x+1<width and row[x+1]!='#':d.line((xx+t-1,yy,xx+t-1,yy+t-1),fill=shade)
    if ch not in 'tH':continue
   if ch in '.,':
    for _ in range(5):
     px=xx+int(rng.integers(t));py=yy+int(rng.integers(t));d.line((px,py,px+1,py-2),fill=(c[0]+9,c[1]+11,c[2]+4))
    if ch==',':
     for _ in range(4):
      px=xx+int(rng.integers(t));py=yy+int(rng.integers(t));d.ellipse((px,py,px+2,py+2),fill=(239,204,145))
   elif ch=='~':
    d.arc((xx+4,yy+7,xx+26,yy+13),0,160,fill=(74,151,155));d.line((xx+5,yy+22,xx+17,yy+22),fill=(50,131,143))
   elif ch=='#':
    d.polygon([(xx,yy+t),(xx+3,yy+8),(xx+15,yy+2),(xx+29,yy+10),(xx+t,yy+t)],fill=(103,111,109));d.line((xx+3,yy+8,xx+15,yy+2,xx+29,yy+10),fill=(144,153,140),width=2)
   elif ch=='t':
    d.ellipse((xx-4,yy+1,xx+t+4,yy+t+10),fill=(36,67,50));d.rectangle((xx+14,yy+10,xx+18,yy+30),fill=(100,75,50));d.ellipse((xx-3,yy-6,xx+t+3,yy+24),fill=(42,84,58));d.ellipse((xx+1,yy-8,xx+27,yy+12),fill=(68,113,69));d.arc((xx+3,yy-6,xx+27,yy+12),180,300,fill=(113,143,80),width=2)
   elif ch=='H' and not w.get('decorations'):
    d.rectangle((xx+1,yy+6,xx+30,yy+29),fill=(185,164,119));d.polygon([(xx-2,yy+9),(xx+16,yy-5),(xx+34,yy+9)],fill=(120,73,66));d.rectangle((xx+12,yy+17,xx+20,yy+31),fill=(75,68,58))
 # Feather only grass-to-grass seams before placing solid scenery.
 seam=Image.new('L',im.size);sd=ImageDraw.Draw(seam)
 for y in range(height):
  for x in range(width):
   if w.get('indoors') or w['rows'][y][x] not in '.,':continue
   if x and w['rows'][y][x-1] in '.,':sd.rectangle((x*t-2,y*t,x*t+2,(y+1)*t-1),fill=210)
   if y and w['rows'][y-1][x] in '.,':sd.rectangle((x*t,y*t-2,(x+1)*t-1,y*t+2),fill=210)
 im.paste(im.filter(ImageFilter.GaussianBlur(2)),(0,0),seam)
 # Continuous textured paths authored in world pixels. This changes art only.
 if road_rect and w.get('road_paths') and '=' in terrain:
  mask=Image.new('L',im.size);md=ImageDraw.Draw(mask)
  for road in w['road_paths']:
   points=road['points'];extended=[points[0]]+points+[points[-1]];curve=[]
   for i in range(1,len(extended)-2):
    a,b,c,d=extended[i-1:i+3]
    for step in range(24):
     u=step/24
     curve.append(tuple(.5*((2*b[k])+(-a[k]+c[k])*u+(2*a[k]-5*b[k]+4*c[k]-d[k])*u*u+(-a[k]+3*b[k]-3*c[k]+d[k])*u*u*u) for k in range(2)))
   curve.append(tuple(points[-1]));size=road.get('width',22);md.line(curve,fill=255,width=size,joint='curve')
   for x,y in (curve[0],curve[-1]):md.ellipse((x-size/2,y-size/2,x+size/2,y+size/2),fill=255)
  clip=Image.new('L',im.size);ImageDraw.Draw(clip).rectangle((road_rect['x'],road_rect['y'],road_rect['x']+road_rect['w']-1,road_rect['y']+road_rect['h']-1),fill=255)
  mask=Image.fromarray(np.minimum(np.array(mask),np.array(clip))).filter(ImageFilter.GaussianBlur(.6));road_surface=Image.new('RGB',im.size)
  for yy in range(road_rect['y']//t*t,road_rect['y']+road_rect['h'],t):
   for xx in range(road_rect['x']//t*t,road_rect['x']+road_rect['w'],t):
    variants=terrain['='];road_surface.paste(variants[(((xx//t)*73856093)^((yy//t)*19349663))%len(variants)].resize((t,t)),(xx,yy))
  im.paste(road_surface,(0,0),mask)
 # Authored decorations are composited before GPU chunking, with feet anchors.
 manifest=ROOT/'art/atlas.json'
 if manifest.exists():
  atlas=json.loads(manifest.read_text());sheet=Image.open(ROOT/'art'/atlas.get('image','atlas.png')).convert('RGBA');lookup={r['id']:r for r in atlas['sprites']}
  for obj in sorted(w.get('decorations',[]),key=lambda d:d['y']):
   r=lookup.get(obj['art'])
   if not r:continue
   part=sheet.crop((r['x'],r['y'],r['x']+r['w'],r['y']+r['h'])).resize((obj.get('w',64),obj.get('h',64)),Image.Resampling.LANCZOS)
   shadow=Image.new('RGBA',(part.width,16));ImageDraw.Draw(shadow).ellipse((4,2,part.width-4,14),fill=(10,27,25,70));im.paste(shadow,(int(obj['x']-part.width/2),int(obj['y']-8)),shadow)
   im.paste(part,(int(obj['x']-part.width/2),int(obj['y']-part.height)),part)
 return im

def fallback_actors(optics=False):
 result={};sheet=Image.open(REPO/'games/luma/assets/source/hero.png').convert('RGBA')
 for i in range(4):result['player'+str(i)]=sheet.crop((i*sheet.width//4,0,(i+1)*sheet.width//4,sheet.height//4)).resize((64,64),Image.Resampling.LANCZOS)
 result['player']=result['player0'];result['npc']=result['player1']
 enemies=Image.open(REPO/'games/luma/assets/source/enemies.png').convert('RGBA')
 for name,row in [('enemy',0),('boss',2)]:result[name]=enemies.crop((0,row*enemies.height//4,enemies.width//4,(row+1)*enemies.height//4)).resize((64,64),Image.Resampling.LANCZOS)
 for name in ART:
  if name in result:continue
  im=Image.new('RGBA',(64,64));d=ImageDraw.Draw(im);d.ellipse((8,47,56,58),fill=(12,28,31,100))
  if name in ['crystal','shrine','shrine_lit','portal']:
   d.ellipse((12,43,52,58),fill=(96,113,106),outline=(201,204,156),width=2)
   col=(117,242,223) if name in ['crystal','shrine_lit'] else (110,152,160)
   d.polygon([(32,5),(46,28),(32,48),(18,28)],fill=col,outline=(210,251,215));d.line((32,8,32,43),fill=(236,255,228),width=2)
  elif name in ['chest','chest_open']:
   d.rounded_rectangle((12,27,52,52),4,fill=(130,83,52),outline=(229,191,96),width=3);d.line((13,36,51,36),fill=(225,180,84),width=3);d.rectangle((29,33,35,42),fill=(255,221,130))
  elif name=='sign':d.rectangle((29,29,35,55),fill=(115,89,59));d.rectangle((9,12,55,35),fill=(180,143,88),outline=(236,206,148),width=2)
  else:
   # Deliberately simple placeholder silhouettes, not final character art.
   if name in ['glider','parachute','plane']:d.polygon([(4,22),(32,5),(60,22),(39,28),(32,47),(25,28)],fill=(236,193,110),outline=(75,110,107))
   elif name in ['car','scooter','bike']:d.rounded_rectangle((14,23,50,46),7,fill=(177,95,74));d.ellipse((8,42,23,57),fill=(38,49,51));d.ellipse((42,42,57,57),fill=(38,49,51))
   else:d.ellipse((11,26,52,49),fill=(143,103,74));d.rectangle((18,43,23,57),fill=(102,77,62));d.rectangle((43,42,48,57),fill=(102,77,62));d.ellipse((39,9,56,33),fill=(162,124,88))
  result[name]=im
 if optics:
  # Explicit provisional mechanism art, replaced by authored atlas entries.
  for name in ['emitter','mirror','mirror_turned','receiver','receiver_lit']:
   im=Image.new('RGBA',(64,64));d=ImageDraw.Draw(im);d.ellipse((12,45,52,59),fill=(12,28,31,100));d.rounded_rectangle((20,39,44,55),4,fill=(115,102,77),outline=(225,192,126),width=2)
   d.ellipse((10,4,54,48),fill=(42,79,85),outline=(225,192,126),width=4)
   if name.startswith('mirror'):d.line((18,12,46,40) if name.endswith('turned') else (18,40,46,12),fill=(206,248,245),width=7)
   else:d.ellipse((22,16,42,36),fill=(248,234,146) if name in ['emitter','receiver_lit'] else (37,74,78),outline=(141,193,179),width=2)
   result[name]=im
 return result
def atlas_overrides(actors):
 manifest=ROOT/'art/atlas.json';used=[]
 if manifest.exists():
  m=json.loads(manifest.read_text());im=Image.open(ROOT/'art'/m.get('image','atlas.png')).convert('RGBA')
  for r in m['sprites']:
   actors[r['id']]=im.crop((r['x'],r['y'],r['x']+r['w'],r['y']+r['h'])).resize((64,64),Image.Resampling.LANCZOS);used.append(r['id'])
 return used
def compile_worlds(worlds,art_names):
 arcs=ROOT/'content/campaign_arcs.json';mission_worlds=json.loads(arcs.read_text()).get('worlds',[]) if arcs.exists() else []
 mission_data={row['world']:row['missions'] for row in mission_worlds}
 lines=['/* Generated from authored JSON. Do not edit. */','#include "luma.h"']
 for wi,w in enumerate(worlds):
  missions=mission_data.get(wi,[]);assert len(missions)<=16
  receivers=[e for e in w['entities'] if e['kind']=='receiver'];receiver_mask=0;optic_cells=set()
  assert sum(e['kind']=='emitter' for e in w['entities'])<=4
  assert sum(e['kind']=='mirror' for e in w['entities'])<=12
  for e in receivers:
   bit=e.get('grants',0);assert bit and not bit&(bit-1) and bit<(1<<24) and not bit&receiver_mask,(w['id'],e['id'],'receiver needs a unique low flag bit');receiver_mask|=bit
  for e in w['entities']:
   if e['kind'] in ['emitter','mirror','receiver']:
    assert w['width']<=128 and w['height']<=128 and w['tile']==32
    assert 0<=e['x']<w['width']*w['tile'] and 0<=e['y']<w['height']*w['tile'],(w['id'],e['id'],'optic outside map')
    assert w['rows'][int(e['y']/w['tile'])][int(e['x']/w['tile'])] not in '#tH',(w['id'],e['id'],'optic inside wall')
    assert e['x']%w['tile']==w['tile']//2 and e['y']%w['tile']==w['tile']//2,(w['id'],e['id'],'optic must be tile-centred')
    cell=(e['x'],e['y']);assert cell not in optic_cells,(w['id'],'overlapping optics');optic_cells.add(cell)
   if e['kind']=='emitter':assert e.get('direction',0) in range(4) and not (e.get('requires',0)|e.get('forbids',0))&receiver_mask,(w['id'],'optical feedback is forbidden')
   if e['kind'] in ['mirror','receiver']:assert not(e.get('requires',0)|e.get('forbids',0)),(w['id'],'mirrors/receivers are always active')
   if e['kind']=='mirror':assert e.get('orientation',0) in [0,1]
   if e['kind'] not in ['receiver','lamp']:assert not e.get('grants',0)&receiver_mask,(w['id'],e['id'],'receiver flag reused by a producer')
  for m in missions:assert not m.get('reward',{}).get('flags',0)&receiver_mask,(w['id'],'mission reward reuses receiver flag')
  entity_ids={e['id']:i for i,e in enumerate(w['entities'])};mission_ids={m['id']:i for i,m in enumerate(missions)};unique_ids([m['id'] for m in missions],'missions '+str(wi))
  for mi,m in enumerate(missions):
   points=m.get('checkpoints',[m['point']] if 'point' in m else []);assert len(points)<=255
   lines.append(f'static const LumaCheckpoint points_{wi}_{mi}[]={{'+','.join('{'+','.join(map(str,[p['x'],p['y'],p.get('radius',28)]))+'}' for p in points)+'};')
  lines.append(f'static const LumaMission missions_{wi}[]={{')
  for mi,m in enumerate(missions):
   opts=(m.get('options',[])+['','',''])[:3];reward=m.get('reward',{});prereq=sum(1<<mission_ids[k] for k in m.get('requires',[]));targets=sum(1<<entity_ids[k] for k in m.get('targets',[]));points=m.get('checkpoints',[m['point']] if 'point' in m else [])
   vals=[cstr(m['id']),cstr(m['title']),cstr(m.get('text',m['title'])),'{'+','.join(map(cstr,opts))+'}',cstr(m.get('feedback','Observez les indices et essayez encore.')),str(['talk','visit','collect','defeat','choice','vehicle_route','dungeon'].index(m['type'])),str(prereq),str(m.get('target_world',entity_ids.get(m.get('target'),0))),str(m.get('complete_flags',m.get('count',1))),str(m.get('vehicle',0)),str(m.get('answer',0)),str(reward.get('vehicle',255)),str(reward.get('crystals',0)),str(reward.get('flags',0)),str(int(m.get('required',True))),f'UINT64_C({targets})',f'points_{wi}_{mi}',str(len(points))]
   lines.append('{'+','.join(vals)+'},')
  lines.append('};')
  lines.append(f'static const char terrain_{wi}[]='+''.join(cstr(r) for r in w['rows'])+';')
  lines.append(f'static const LumaEntity entities_{wi}[]={{')
  for e in w['entities']:
   text=e.get('text',e.get('dialogue',''));text=' | '.join(text) if isinstance(text,list) else text
   art=e.get('art',e['kind']);art=art_names.index(art) if art in art_names else ART.index(e['kind'])
   cost=e.get('orientation',0) if e['kind']=='mirror' else e.get('cost',0)
   behavior=e.get('direction',0) if e['kind']=='emitter' else ['melee','turret'].index(e.get('behavior','melee'))
   lines.append('{'+','.join([cstr(e['id']),cstr(e.get('name',e['id'])),cstr(text),cstr(e.get('after','')),str(e['x']),str(e['y']),str(KINDS.index(e['kind'])),str(e.get('requires',0)),str(e.get('grants',0)),str(cost),str(e.get('vehicle',0)),str(art),str(e.get('target_world',-1)),str(e.get('target_x',0)),str(e.get('target_y',0)),str(e.get('forbids',0)),str(e.get('hp',0)),str(behavior),str(e.get('shot_period',0))])+'},')
  lines.append('};')
  lines.append(f'static const LumaQuest quests_{wi}[]={{')
  for q in w.get('quests',[]):lines.append('{'+','.join([cstr(q['title']),cstr(q['objective']),str(q.get('requires',0)),str(q['complete_mask']),str(int(q.get('optional',False)))])+'},')
  lines.append('};')
 lines.append('const LumaWorld luma_worlds[]={')
 for i,w in enumerate(worlds):
  spawn=w['spawn'];x,y=(spawn['x'],spawn['y']) if isinstance(spawn,dict) else spawn
  lines.append('{'+','.join([cstr(w.get('title',w.get('name','LUMA'))),cstr(w.get('name','LUMA')),cstr(w.get('id',str(i))),str(w['width']),str(w['height']),str(w['tile']),f'terrain_{i}',str(x),str(y),str(len(w['entities'])),f'entities_{i}',f'quests_{i}',str(len(w.get('quests',[]))),f'missions_{i}',str(len(mission_data.get(i,[]))),str(int(w.get('indoors',False)))])+'},')
 lines+=['};',f'const unsigned luma_world_count={len(worlds)};'];(OUT/'world.c').write_text('\n'.join(lines)+'\n')

def compress(data):
 lib=ctypes.CDLL(ctypes.util.find_library('lz4'));lib.LZ4_compressBound.argtypes=[ctypes.c_int];lib.LZ4_compress_HC.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int]
 packed=ctypes.create_string_buffer(lib.LZ4_compressBound(len(data)));size=lib.LZ4_compress_HC(bytes(data),packed,len(data),len(packed),12);assert size>0
 return struct.pack('<4sIII',b'LZ4L',len(data),size,zlib.crc32(data))+packed.raw[:size]
def main():
 global OUT
 parser=argparse.ArgumentParser();parser.add_argument('--indexed',action='store_true');parser.add_argument('--out',type=Path);args=parser.parse_args()
 if args.out:OUT=args.out.resolve()
 elif args.indexed:OUT=OUT/'indexed'
 OUT.mkdir(parents=True,exist_ok=True);worlds=read_worlds();actors=fallback_actors(any(e['kind'] in ['emitter','mirror','receiver'] for w in worlds for e in w['entities']));overrides=atlas_overrides(actors)
 for w in worlds:
  for e in w['entities']:
   art=e.get('art',e['kind'])
   if art not in actors:actors[art]=actors.get(e['kind'],actors['chest'] if e['kind']=='crate' else actors['shrine']).copy()
 terrains={};tm=ROOT/'art/terrain.json'
 if tm.exists():
  m=json.loads(tm.read_text());im=Image.open(ROOT/'art'/m.get('image','terrain.png')).convert('RGB')
  for r in m['sprites']:terrains.setdefault(r.get('char',r['id']),[]).append(im.crop((r['x'],r['y'],r['x']+r['w'],r['y']+r['h'])))
 if '.' in terrains:
  arrays=[np.asarray(tile.resize((32,32)),dtype=np.float32) for tile in terrains['.']];mean=np.mean([a.mean(axis=(0,1)) for a in arrays],axis=0)
  terrains['.']=[Image.fromarray(np.clip(a-a.mean(axis=(0,1))+mean,0,255).astype('uint8')) for a in arrays]
 images=[world_image(w,i,terrains) for i,w in enumerate(worlds)]
 # Shared indexed actor palette: transparent index 0; all opaque colors 1..255.
 samples=[]
 for name,im in actors.items():
  sample=im.resize((128,128),Image.Resampling.LANCZOS) if name.startswith('tree') else im;a=np.asarray(sample);pixels=a[:,:,:3][a[:,:,3]>=96]
  if len(pixels):samples.append(np.repeat(pixels,(12 if name.startswith('tree') else 3) if args.indexed else (3 if name.startswith('tree') else 1),axis=0))
 if args.indexed:
  for im in images:samples.append(np.asarray(im)[::8,::8].reshape(-1,3))
 colors=np.concatenate(samples);colors=np.pad(colors,((0,(-len(colors))%1024),(0,0)),mode='edge');train=Image.fromarray(colors.reshape(-1,1024,3))
 effects=[0xfff2,0xffd2,0xfaed,0xfff1,0xfff4,0x39c7,0xf9a7,0xaffe,0x9fff]
 ui_colors=[[20,43,44],[233,206,148],[159,181,161],[230,123,103],[151,219,185]]
 count=238-len(effects)-len(ui_colors) if args.indexed else 238
 quant=train.quantize(colors=count);colors=quant.getpalette()[:count*3]
 if args.indexed:
  for c in effects:colors.extend([((c>>11)*63+30)//31*255//63,((c>>5)&63)*255//63,((c&31)*63+30)//31*255//63])
 if args.indexed:
  for rgb in ui_colors:colors.extend(rgb)
 palette=[0,0,0]+colors+[255,244,214]+[0]*48;pal=Image.new('P',(1,1));pal.putpalette(palette)
 if args.indexed:pal.putpalette(colors[:3]+palette[3:720]+colors[:3]*16) # reserved indices never steal opaque black
 data=bytearray(4096);resources={};chunks=[];region_bytes=[];region_crcs=[]
 def add(raw):data.extend(bytes((-len(data))%32));off=len(data);data.extend(raw);return off
 words=[((r*63//255)<<12)|((g*63//255)<<6)|(b*63//255) for r,g,b in zip(palette[::3],palette[1::3],palette[2::3])]
 if args.indexed:
  for i,c in enumerate(effects):words[count+1+i]=(((c>>11)*63+30)//31<<12)|(((c>>5)&63)<<6)|(((c&31)*63+30)//31)
 assert all(c==0 for c in words[240:]);palette_off=add(struct.pack('<256I',*words))
 actors.setdefault('lamp',actors['shrine_lit'])
 actors.setdefault('player4',actors['player2'])
 art_names=ART+['player1','player2','player3','player4']+sorted(set(actors)-set(ART)-{'player0','player1','player2','player3','player4'})
 for name in art_names:
  im=actors[name];a=np.asarray(im.convert('RGB').quantize(palette=pal,dither=Image.Dither.NONE)).copy();alpha=np.asarray(im)[:,:,3];a[alpha<96]=0;a[(alpha>=96)&((a==0)|(a>=240))]=1
  raw=b''.join(a[y:y+32,x:x+32].tobytes() for y in (0,32) for x in (0,32));resources[name]=add(raw)
 font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',12);glyphs=[]
 for ch in range(256):
  letter={128:'œ',129:'Œ',130:'…'}.get(ch,chr(ch));im=Image.new('L',(20,14));ImageDraw.Draw(im).text((0,-1),letter,font=font,fill=255);bbox=im.getbbox();extent=max(8,bbox[2] if bbox else 8);im=im.crop((0,0,extent,14)).resize((8,14),Image.Resampling.LANCZOS);glyphs.append((np.asarray(im)>100).astype('uint8').tobytes())
 font_off=add(b''.join(glyphs));occluders=[];occluder_cache={}
 for wi,w in enumerate(worlds):
  entries=[]
  for obj in w.get('decorations',[]):
   if not obj['art'].startswith('tree') and not obj.get('foreground'):continue
   if obj['art'] not in actors:continue
   ww=obj.get('w',64)*2;hh=obj.get('h',64)*2;key=(obj['art'],ww,hh);pitch=(ww+31)&~31
   if key not in occluder_cache:
    im=actors[obj['art']].resize((ww//2,hh//2),Image.Resampling.LANCZOS).resize((ww,hh),Image.Resampling.NEAREST);q=np.asarray(im.convert('RGB').quantize(palette=pal,dither=Image.Dither.NONE)).copy();alpha=np.asarray(im)[:,:,3];q[alpha<96]=0;q[(alpha>=96)&((q==0)|(q>=240))]=1;buf=np.zeros((hh,pitch),dtype='uint8');buf[:,:ww]=q;occluder_cache[key]=add(buf.tobytes())
   entries.append([int(obj['x']),int(obj['y']),ww,hh,pitch,occluder_cache[key]])
  assert len(entries)<=8
  # At most four foreground layers can coexist: R17 reserves layers12..15,
  # and the HUD uses9..11. Check the widest supported camera (640x360 world px).
  boxes=[(x-ww/4-320,x+ww/4+320,y-hh/2-180,y+180) for x,y,ww,hh,_,_ in entries]
  for px in [b[k] for b in boxes for k in (0,1)]:
   for py in [b[k] for b in boxes for k in (2,3)]:
    assert sum(left<px+.01<right and top<py+.01<bottom for left,right,top,bottom in boxes)<=4,(w['id'],'more than four visible foreground objects')
  occluders.append(entries)
 tile_layouts=[]
 for wi,w in enumerate(worlds):
  im=images[wi];im.save(OUT/f'world_{wi}.png');a=rgb565(im);items=[];region=bytearray()
  for y in range(0,im.height,512):
   for x in range(0,im.width,512):
    tile=np.zeros((512,512),dtype='<u2');part=a[y:y+512,x:x+512];tile[:part.shape[0],:part.shape[1]]=part;items.append(len(region));region.extend(tile.tobytes())
  if args.indexed:
   q=np.asarray(im.quantize(palette=pal,dither=Image.Dither.NONE)).copy();q[(q==0)|(q>=240)]=1
   native=np.repeat(np.repeat(q,2,axis=0),2,axis=1);mw=1<<math.ceil(math.log2(native.shape[1]/32));mh=1<<math.ceil(math.log2(native.shape[0]/32));tilemap=np.zeros((mh,mw),dtype='<u2');tiles={bytes(1024):0}
   for ty in range(native.shape[0]//32):
    for tx in range(native.shape[1]//32):
     raw=native[ty*32:(ty+1)*32,tx*32:(tx+1)*32].tobytes();tilemap[ty,tx]=tiles.setdefault(raw,len(tiles))
   assert len(tiles)<=8192,(w['id'],len(tiles),'GPU tile atlas overflow')
   region=bytearray(tilemap.tobytes()+b''.join(tiles));tile_layouts.append([tilemap.nbytes,int(math.log2(mw))|(int(math.log2(mh))<<4)|(2<<8),len(tiles)])
  chunks.append(items);region_bytes.append(len(region));region_crcs.append(zlib.crc32(region));(OUT/f'world_{wi:02d}.lz4').write_bytes(compress(region))
 struct.pack_into('<8I',data,0,0x414d554c,1,len(data),0,len(worlds),palette_off,font_off,len(art_names));struct.pack_into('<I',data,12,zlib.crc32(data[32:]))
 (OUT/'luma.pak').write_bytes(data)
 (OUT/'luma.lz4').write_bytes(compress(data))
 compile_worlds(worlds,art_names)
 lines=['/* Generated resource layout. */','#ifndef LUMA_ASSETS_H','#define LUMA_ASSETS_H',f'#define LUMA_PACK_BYTES {len(data)}U',f'#define LUMA_PACK_CRC {zlib.crc32(data[32:])}U',f'#define LUMA_PALETTE_OFFSET {palette_off}U',f'#define LUMA_FONT_OFFSET {font_off}U',f'#define LUMA_ART_COUNT {len(art_names)}', 'static const unsigned luma_art_offsets[]={'+','.join(map(str,[resources[n] for n in art_names]))+'};']
 lines.append('static const unsigned luma_active_art[]={'+','.join(str(art_names.index(name+'_open') if name+'_open' in art_names else art_names.index(name+'_lit') if name+'_lit' in art_names else i) for i,name in enumerate(art_names))+'};')
 lines.append('static const unsigned luma_rotated_art[]={'+','.join(str(art_names.index(name+'_turned') if name+'_turned' in art_names else i) for i,name in enumerate(art_names))+'};')
 for direction in ['n','e','w']:lines.append(f'#define LUMA_HERO_{direction.upper()} '+str(art_names.index('player_'+direction) if 'player_'+direction in art_names else 0))
 lines+=['static const unsigned luma_chunk_offsets[LUMA_MAX_WORLDS][64]={']+['{'+','.join(map(str,c))+'},' for c in chunks]+['};','typedef struct { int x,y,w,h; unsigned pitch,offset; } LumaOccluder;','static const LumaOccluder luma_occluders[LUMA_MAX_WORLDS][8]={']+['{'+','.join('{'+','.join(map(str,o))+'}' for o in world)+'},' for world in occluders]+['};','static const unsigned luma_occluder_counts[]={'+','.join(str(len(w)) for w in occluders)+'};','static const unsigned luma_region_bytes[]={'+','.join(map(str,region_bytes))+'};','static const unsigned luma_region_crcs[]={'+','.join(str(c)+'U' for c in region_crcs)+'};','#endif']
 if args.indexed:
  lines[-1:-1]=['#define LUMA_INDEXED_BACKGROUND 1','static const unsigned luma_tile_layout[][3]={'+','.join('{'+','.join(map(str,row))+'}' for row in tile_layouts)+'};','static const unsigned luma_effect_rgb565[]={'+','.join(hex(c) for c in effects)+'};',f'#define LUMA_EFFECT_FIRST {count+1}']
 (OUT/'assets.h').write_text('\n'.join(lines)+'\n')
 (OUT/'manifest.json').write_text(json.dumps({'format':1,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'world_count':len(worlds),'backend':'indexed_scrolling_candidate' if args.indexed else 'rgb565_blitter','tile_layouts':tile_layouts,'entities':[len(w['entities']) for w in worlds],'intended_boards':['prodock','neo'],'art_status':'provisional_existing_luma_and_procedural' if len(overrides)<len(ART) else 'comfyui_atlas','atlas_overrides':overrides,'hardware_qualification':{'prodock':'pending','neo':'pending'}},indent=2)+'\n')
 audio_manifest=ROOT/'audio/manifest.json';cues=json.loads(audio_manifest.read_text()).get('cues',[]) if audio_manifest.exists() else []
 audio_lines=['/* Only listened-to, approved cues enter normal gameplay. */','typedef struct { const char *file,*state; int world; } LumaMusic;','static const LumaMusic luma_music[]={']
 for cue in cues:
  if cue.get('status')=='ready' and isinstance(cue.get('file'),str):
   assert (ROOT/cue['file']).is_file(),cue['file'];audio_lines.append('{'+','.join([cstr(cue['file']),cstr(cue['state']),str(cue.get('world',-1))])+'},')
 audio_lines+=['{NULL,NULL,-1}};'];(OUT/'music.h').write_text('\n'.join(audio_lines)+'\n')
 print(f'LUMA assets {len(worlds)} worlds, {len(data):,} bytes; {len(overrides)} ComfyUI atlas overrides')
if __name__=='__main__':main()
