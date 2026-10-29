#!/usr/bin/env python3
"""Pack reviewed candidate cells; this script never writes the live art atlas."""
import hashlib
import json
import math
import sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

HERE=Path(__file__).resolve().parent
ART=HERE.parents[2]
sys.path.insert(0,str(ART))
from import_assets import cutout

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def result(name):
    p=HERE/'renders'/name;m=json.loads((p/'submission.json').read_text());assert m['status']=='generated'
    for f in m['files']:assert sha(p/f['file'])==f['sha256']
    return p,m

def main():
    folder,meta=result('sanctuary_cutouts');mapping=json.loads((HERE/'cutout_mapping.json').read_text());sprites={};records={}
    for i,entry in enumerate(mapping):
        if entry['id']=='lamp':continue  # First off-state was clipped; retained but rejected.
        path=folder/meta['files'][i]['file'];im,coverage,bbox=cutout(Image.open(path))
        sprites[entry['id']]=im;records[entry['id']]=dict(source=str(path.relative_to(HERE)),sha256=sha(path),source_cell=entry['cell'],coverage=coverage,bbox=bbox)
    folder,meta=result('lamp_off_r2_cutout');path=folder/meta['files'][0]['file'];sprites['lamp'],coverage,bbox=cutout(Image.open(path));records['lamp']=dict(source=str(path.relative_to(HERE)),sha256=sha(path),coverage=coverage,bbox=bbox)
    atlas=Image.new('RGBA',(5*64,math.ceil(len(sprites)/5)*64));manifest=[];review=Image.new('RGB',(5*132,math.ceil(len(sprites)/5)*152),(43,62,59));draw=ImageDraw.Draw(review)
    for n,(eid,im) in enumerate(sprites.items()):
        x=n%5*64;y=n//5*64;atlas.alpha_composite(im,(x,y));manifest.append(dict(id=eid,x=x,y=y,w=64,h=64,anchor_x=32,anchor_y=62,**records[eid]))
        shown=im.resize((128,128),Image.Resampling.NEAREST);review.paste(shown,(n%5*132,n//5*152),shown);draw.text((n%5*132+3,n//5*152+131),eid,fill='white')
    atlas.save(HERE/'imported/atlas.png');review.save(HERE/'imported/actors_review.png');write(HERE/'imported/atlas.json',dict(schema=1,image='atlas.png',sprites=manifest,generated_by='local ComfyUI Qwen Image and BiRefNet',status='candidate_pending_game_render',importer_sha256=sha(Path(__file__))))
    terrain=Image.new('RGB',(128,64));tiles=[];repeat=Image.new('RGB',(768,384));rng=np.random.default_rng(20261024)
    for row,(name,crop) in enumerate([('indoor_floor',(400,400,624,624)),('indoor_wall',(384,352,640,608))]):
        folder,meta=result(name);path=folder/meta['files'][0]['file'];material=Image.open(path).convert('RGB').crop(crop);cw,ch=material.width//2,material.height//2;variants=[]
        for n in range(4):
            box=(n%2*cw,n//2*ch,(n%2+1)*cw,(n//2+1)*ch);im=material.crop(box).resize((32,32),Image.Resampling.LANCZOS);variants.append(im);terrain.paste(im,(n*32,row*32));tiles.append(dict(id=name if not n else name+f'_{n:02}',char=name,variant=n,x=n*32,y=row*32,w=32,h=32,source=str(path.relative_to(HERE)),sha256=sha(path),source_material_crop=list(crop),source_variant_crop=list(box)))
        for yy in range(12):
            for xx in range(12):repeat.paste(variants[int(rng.integers(4))],(row*384+xx*32,yy*32))
    terrain.save(HERE/'imported/terrain.png');repeat.save(HERE/'imported/terrain_repeat_review.png');write(HERE/'imported/terrain.json',dict(schema=1,image='terrain.png',sprites=tiles,status='candidate_pending_game_render'))
    print(f'Packed {len(sprites)} mechanism states and {len(tiles)} indoor texture variants in candidate folder only.')

if __name__=='__main__':main()
