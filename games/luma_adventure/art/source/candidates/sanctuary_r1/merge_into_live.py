#!/usr/bin/env python3
"""Merge reviewed sanctuary cells while preserving every existing sprite pixel."""
import hashlib
import json
import math
from pathlib import Path
from PIL import Image,ImageDraw

HERE=Path(__file__).resolve().parent
ART=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

def merge(name,size,cols,mode):
    target=ART/(name+'.json');old=json.loads(target.read_text());incoming=json.loads((HERE/'imported'/(name+'.json')).read_text())
    pixels=Image.open(ART/old['image']).convert(mode);newpixels=Image.open(HERE/'imported'/incoming['image']).convert(mode)
    records={};images={};before={}
    for s in old['sprites']:
        records[s['id']]=dict(s);images[s['id']]=pixels.crop((s['x'],s['y'],s['x']+s['w'],s['y']+s['h']));before[s['id']]=images[s['id']].tobytes()
    for s in incoming['sprites']:
        record=dict(s)
        if 'source' in record:record['source']='source/candidates/sanctuary_r1/'+record['source']
        record['candidate_origin']='sanctuary_r1';records[s['id']]=record;images[s['id']]=newpixels.crop((s['x'],s['y'],s['x']+s['w'],s['y']+s['h']))
    out=Image.new(mode,(cols*size,math.ceil(len(images)/cols)*size));manifest=[]
    for n,(eid,im) in enumerate(images.items()):
        assert im.size==(size,size);x=n%cols*size;y=n//cols*size
        out.paste(im,(x,y));record=records[eid];record.update(x=x,y=y);manifest.append(record)
    for s in manifest:
        if s['id'] in before and s.get('candidate_origin')!='sanctuary_r1':
            assert out.crop((s['x'],s['y'],s['x']+size,s['y']+size)).tobytes()==before[s['id']],s['id']
    out.save(ART/old['image']);old['sprites']=manifest;old.setdefault('candidate_imports',{})['sanctuary_r1']=dict(manifest_sha256=sha(HERE/'imported'/(name+'.json')),image_sha256=sha(HERE/'imported'/incoming['image']),merger_sha256=sha(Path(__file__)))
    write(target,old)
    if name=='atlas':
        preview=Image.new('RGB',(cols*132,math.ceil(len(images)/cols)*148),(34,54,51));draw=ImageDraw.Draw(preview)
        for n,(eid,im) in enumerate(images.items()):
            shown=im.resize((128,128),Image.Resampling.NEAREST);x=n%cols*132;y=n//cols*148;preview.paste(shown,(x,y),shown);draw.text((x+2,y+130),eid,fill=(240,230,200))
        preview.save(ART/'atlas_review.png')
    print(f'{name}: {len(before)} -> {len(manifest)} IDs; prior pixels preserved.')

def main():
    review=json.loads((HERE/'review.json').read_text());assert review['status']=='accepted_for_integration'
    merge('atlas',64,8,'RGBA');merge('terrain',32,4,'RGB')
    path=ART/'acceptance.json';a=json.loads(path.read_text());a['status']='sanctuary_assets_integrated_pending_game_capture';a['outputs']={f:sha(ART/f) for f in ['atlas.png','atlas.json','terrain.png','terrain.json']};a['sprite_ids']=len(json.loads((ART/'atlas.json').read_text())['sprites']);a['terrain_ids']=len(json.loads((ART/'terrain.json').read_text())['sprites']);a['additional_import_commands']=['python3 games/luma_adventure/art/source/candidates/sanctuary_r1/import_candidate.py','python3 games/luma_adventure/art/source/candidates/sanctuary_r1/merge_into_live.py'];a['sanctuary_review']='source/candidates/sanctuary_r1/review.json';write(path,a)

if __name__=='__main__':main()
