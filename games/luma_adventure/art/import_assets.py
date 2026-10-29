#!/usr/bin/env python3
"""Deterministically import reviewed ComfyUI sheets into the C renderer's atlases.

This performs only cropping, chroma-key removal, sizing and packing; it does not
invent source art. Originals and generation provenance are always preserved.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent
ALIASES={'player':'player_s','player0':'player_s','player1':'player_s_step1','player2':'player_s_step2','player3':'player_s_step1','stable':'horse','shrine_lit':'shrine','chest_open':'chest'}
CHARS={'grass':'.','path':'=','water':'~','sand':':','forest':'t','cliff':'#','flower':','}
# Reviewed material-only regions in the first source sheet. Water and sand
# deliberately exclude the illustrative shoreline; paths exclude the grassy edge.
TERRAIN_CROPS={'grass':(30,30,230,230),'path':(85,50,175,240),'water':(10,110,230,250),'sand':(80,195,240,250)}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def cutout(cell):
    pixels=np.asarray(cell.convert('RGB')).astype(np.float32)
    r,g,b=pixels[:,:,0],pixels[:,:,1],pixels[:,:,2]
    # Saturated pink background and pink antialiasing are removed. Green foliage
    # and the hero's orange coat are retained because both fail this chroma rule.
    chroma=(r>75)&(b>60)&(g<r*.68)&(g<b*.78)&(r+b>g*3.1)
    if cell.mode=='RGBA' and cell.getchannel('A').getextrema()[0]<250:
        alpha=np.asarray(cell.getchannel('A')).copy();alpha[alpha<8]=0
    else:alpha=np.where(chroma,0,255).astype(np.uint8)
    out=Image.fromarray(np.dstack((pixels.astype(np.uint8),alpha)),'RGBA')
    bbox=out.getbbox()
    if not bbox:raise ValueError('Empty sprite after chroma key')
    coverage=float((alpha>0).mean())
    if coverage>.87:raise ValueError(f'Background key failed or adjacent cells overlap ({coverage:.3f})')
    if coverage<.015:raise ValueError(f'Sprite too small ({coverage:.3f})')
    out=out.crop(bbox);out.thumbnail((60,60),Image.Resampling.LANCZOS)
    result=Image.new('RGBA',(64,64));result.alpha_composite(out,((64-out.width)//2,62-out.height))
    return result,coverage,bbox

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reviewed',nargs='+',required=True,help='Names of source sheets visually reviewed before import')
    args=p.parse_args();brief=json.loads((ROOT/'brief.json').read_text())
    sprites={};records={};terrain={};terrain_chars={};sources=[]
    for spec in brief['images']:
        source=ROOT/'source'/f"{spec['name']}.png"
        if spec['name'] not in args.reviewed:continue
        if not source.exists():raise SystemExit(f'No generated source to import: {source}')
        provenance=ROOT/'provenance'/f"{spec['name']}.json"
        if not provenance.exists() or json.loads(provenance.read_text()).get('sha256')!=digest(source):raise SystemExit(f'Missing/mismatched generation provenance: {source}')
        masked=ROOT/'source'/f"{spec['name']}_rgba.png"
        if spec['type']=='sprites' and masked.exists():
            mp=ROOT/'provenance'/f"{spec['name']}_rgba.json"
            if not mp.exists() or json.loads(mp.read_text())['sha256']!=digest(masked):raise SystemExit('Missing segmentation provenance: '+str(masked))
            im=Image.open(masked).convert('RGBA')
        else:im=Image.open(source).convert('RGBA' if spec['type']=='sprites' else 'RGB')
        material_crop=(256,256,768,768) if spec['name'] in ('ground_grass','ground_path') else None
        if material_crop:im=im.crop(material_crop)
        cols,rows=spec['grid'];cw,ch=im.width//cols,im.height//rows
        sources.append(dict(file=source.relative_to(ROOT).as_posix(),sha256=digest(source),reviewed=True,material_crop=material_crop))
        for n,asset_id in enumerate(spec['ids']):
            if spec['name']=='travel_sheet' and asset_id in ('horse_n','horse_w','horse_e','glider','parachute','scooter'):continue
            if spec['name']=='cast_sheet':
                if asset_id=='npc_maelle':n=14
                elif asset_id=='npc':n=0
            # The first generated hero sheet has front/back poses but did not
            # obey the requested side directions. Do not label those as valid.
            if spec['name']=='hero_sheet':
                if asset_id!='player_s':continue
                if asset_id=='player_s':n=1
                elif asset_id=='player_s_step1':n=4
                elif asset_id=='player_s_step2':n=5
            x=(n%cols)*cw;y=(n//cols)*ch;box=(x,y,x+cw,y+ch);part=im.crop(box)
            if spec['type']=='sprites':
                result,coverage,bbox=cutout(part);sprites[asset_id]=result
                records[asset_id]=dict(source=source.relative_to(ROOT).as_posix(),source_rect=list(box),keyed_coverage=round(coverage,4),content_bbox=list(bbox))
            else:
                inset=max(2,cw//32)
                crop=TERRAIN_CROPS.get(asset_id,(inset,inset,cw-inset,ch-inset)) if spec['name']=='terrain_sheet' else (inset,inset,cw-inset,ch-inset)
                terrain[asset_id]=part.crop(crop).resize((32,32),Image.Resampling.LANCZOS)
                if spec['name'].startswith('ground_'):terrain_chars[asset_id]=CHARS[spec['name'].split('_',1)[1]]
    if sprites:
        aliases=dict(ALIASES)
        if 'stride_a' in sprites and 'stride_opposite' in sprites:
            aliases.update(player1='stride_a',player2='player_s',player3='stride_opposite',player4='player_s')
        for alias,original in aliases.items():
            if original in sprites:sprites[alias]=sprites[original].copy();records[alias]=dict(alias_of=original)
        cols=8;atlas=Image.new('RGBA',(cols*64,math.ceil(len(sprites)/cols)*64));manifest=[]
        for n,(asset_id,im) in enumerate(sprites.items()):
            x=n%cols*64;y=n//cols*64;atlas.alpha_composite(im,(x,y))
            manifest.append(dict(id=asset_id,x=x,y=y,w=64,h=64,anchor_x=32,anchor_y=62,**records[asset_id]))
        atlas.save(ROOT/'atlas.png')
        write(ROOT/'atlas.json',dict(schema=1,image='atlas.png',generated_by='ComfyUI on gx10-2',sprites=manifest,sources=sources,importer_sha256=digest(Path(__file__))))
        preview=Image.new('RGB',(cols*132,math.ceil(len(sprites)/cols)*148),(34,54,51));d=ImageDraw.Draw(preview)
        for n,(asset_id,im) in enumerate(sprites.items()):
            x=n%cols*132;y=n//cols*148;preview.paste(im.resize((128,128),Image.Resampling.NEAREST),(x,y),im.resize((128,128),Image.Resampling.NEAREST));d.text((x+2,y+130),asset_id,fill=(240,230,200))
        preview.save(ROOT/'atlas_review.png')
        print(f'Imported {len(sprites)} sprite IDs from {len(sources)} reviewed source sheets')
    if terrain:
        atlas=Image.new('RGB',(128,math.ceil((len(terrain)+1)/4)*32));manifest=[]
        for n,(asset_id,im) in enumerate(terrain.items()):
            x=n%4*32;y=n//4*32;atlas.paste(im,(x,y));r=dict(id=asset_id,x=x,y=y,w=32,h=32)
            if asset_id in CHARS:r['char']=CHARS[asset_id]
            if asset_id in terrain_chars:r['char']=terrain_chars[asset_id];r['variant']=int(asset_id.rsplit('_',1)[-1]) if '_' in asset_id else 0
            if asset_id in TERRAIN_CROPS:r['reviewed_source_crop']=list(TERRAIN_CROPS[asset_id])
            manifest.append(r)
        grass=next(r for r in manifest if r['id']=='grass');manifest.append(dict(grass,id='building_floor',char='H'))
        atlas.save(ROOT/'terrain.png');write(ROOT/'terrain.json',dict(schema=1,image='terrain.png',sprites=manifest,sources=sources,importer_sha256=digest(Path(__file__))))
        print(f'Imported {len(manifest)} terrain IDs')

if __name__=='__main__':main()
