#!/usr/bin/env python3
"""Offline visual/budget study only; does not change the game's renderer or assets."""
from pathlib import Path
import json,math,struct
import numpy as np
from PIL import Image
root=Path(__file__).resolve().parents[1];out=root/'build/indexed_study';out.mkdir(exist_ok=True)
world=Image.open(root/'build/world_0.png').convert('RGB');atlas=Image.open(root/'art/atlas.png').convert('RGBA')
background=np.asarray(world.resize((768,614)),dtype=np.uint8).reshape(-1,3)
rgba=np.asarray(atlas);actors=rgba[:,:,:3][rgba[:,:,3]>96];training=np.concatenate([background,actors,actors])
w=1024;training=np.pad(training,((0,(-len(training))%w),(0,0)),mode='wrap').reshape(-1,w,3)
quant=Image.fromarray(training).quantize(colors=238);colors=quant.getpalette()[:714];palette=[0,0,0]+colors+[255,244,214]+[0]*48;pal=Image.new('P',(1,1));pal.putpalette(palette)
indexed=world.quantize(palette=pal,dither=Image.Dither.NONE);indices=np.asarray(indexed).copy();indices[(indices==0)|(indices>=240)]=1;indexed=Image.fromarray(indices,'P');indexed.putpalette(palette)
indexed.save(out/'world_indexed.png')
source=np.asarray(world,dtype=np.float32);target=np.asarray(indexed.convert('RGB'),dtype=np.float32);rmse=float(np.sqrt(np.mean((source-target)**2)))
# Budget a real 32px native tile map with exact byte deduplication.
native=np.asarray(indexed.resize((world.width*2,world.height*2),Image.Resampling.NEAREST));tiles={bytes(1024):0};map_w=1<<math.ceil(math.log2(native.shape[1]/32));map_h=1<<math.ceil(math.log2(native.shape[0]/32));tilemap=np.zeros((map_h,map_w),dtype='<u2')
for y in range(native.shape[0]//32):
 for x in range(native.shape[1]//32):
  b=native[y*32:(y+1)*32,x*32:(x+1)*32].tobytes();tilemap[y,x]=tiles.setdefault(b,len(tiles))
(out/'tilemap.bin').write_bytes(tilemap.tobytes());(out/'atlas.bin').write_bytes(b''.join(tiles))
# Study of the current screenshot: quantization only, explicitly not GPU output.
preview=Image.open(root/'build/village_r6.png').convert('RGB');preview.quantize(palette=pal,dither=Image.Dither.NONE).save(out/'village_palette_study.png')
report={'status':'offline budget/colour study, not implemented or hardware tested','colors_usable':238,'rgb_rmse_0_255':rmse,'tiles_unique':len(tiles),'hardware_tile_limit':8192,'tilemap_bytes':tilemap.nbytes,'atlas_bytes':len(tiles)*1024,'fits_tile_index':len(tiles)<=8192}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
