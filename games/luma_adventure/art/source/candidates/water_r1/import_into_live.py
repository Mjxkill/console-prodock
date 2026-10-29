#!/usr/bin/env python3
"""Import reviewed quiet water, preserving every other tile and all content."""
import hashlib
import json
import math
import shutil
from pathlib import Path
from PIL import Image

HERE=Path(__file__).resolve().parent
ART=HERE.parents[2]
CONTENT=ART.parent/'content'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def main():
    preserved={p:sha(p) for p in [ART/'atlas.png',ART/'atlas.json',*sorted(CONTENT.rglob('*'))] if p.is_file()}
    original=json.loads((ART/'terrain.json').read_text());candidate=json.loads((HERE/'terrain.json').read_text())
    assert len(candidate['sprites'])==16 and all(s.get('char')=='~' for s in candidate['sprites'])
    source=HERE/candidate['sprites'][0]['source'];assert sha(source)==candidate['source_sha256']
    old=Image.open(ART/original['image']).convert('RGB');water=Image.open(HERE/candidate['image']).convert('RGB')
    before={s['id']:dict(s) for s in original['sprites']};incoming={s['id'] for s in candidate['sprites']}
    assert all(s['id'] in incoming for s in original['sprites'] if s.get('char')=='~'),'Unexpected active water mapping; inspect before replacing'
    archive=HERE/'pre_import';archive.mkdir(exist_ok=True)
    for name in ('terrain.png','terrain.json'):
        if not (archive/name).exists():shutil.copy2(ART/name,archive/name)
    if not (archive/'hashes.json').exists():write(archive/'hashes.json',{name:sha(archive/name) for name in ('terrain.png','terrain.json')})
    records={s['id']:dict(s) for s in original['sprites']};columns=old.width//32
    next_slot=max(s['y']//32*columns+s['x']//32 for s in records.values())+1
    placements=[]
    for s in candidate['sprites']:
        r=dict(s)
        if s['id'] in records:x,y=records[s['id']]['x'],records[s['id']]['y']
        else:x,y=next_slot%columns*32,next_slot//columns*32;next_slot+=1
        r.update(x=x,y=y,candidate_origin='water_r1',source='source/candidates/water_r1/'+r['source'])
        records[s['id']]=r;placements.append((s,x,y))
    out=Image.new('RGB',(old.width,max(old.height,math.ceil(next_slot/columns)*32)));out.paste(old,(0,0))
    for s,x,y in placements:out.paste(water.crop((s['x'],s['y'],s['x']+32,s['y']+32)),(x,y))
    for eid,s in before.items():
        if eid in incoming:continue
        assert records[eid]==s,(eid,'metadata changed')
        box=(s['x'],s['y'],s['x']+s['w'],s['y']+s['h'])
        assert old.crop(box).tobytes()==out.crop(box).tobytes(),(eid,'pixels changed')
    active=[s['id'] for s in records.values() if s.get('char')=='~'];assert set(active)==incoming and len(active)==16
    out.save(ART/original['image']);original['sprites']=list(records.values())
    original.setdefault('candidate_imports',{})['water_r1']=dict(manifest_sha256=sha(HERE/'terrain.json'),image_sha256=sha(HERE/'terrain.png'),source_sha256=candidate['source_sha256'],importer_sha256=sha(Path(__file__)),superseded_water_archive='source/candidates/water_r1/pre_import/')
    write(ART/'terrain.json',original)
    for p,digest in preserved.items():assert sha(p)==digest,('protected input changed',str(p))
    a=json.loads((ART/'acceptance.json').read_text());a['status']='quiet_water_imported_pending_R5_capture'
    for f in ('terrain.png','terrain.json'):a['outputs'][f]=sha(ART/f)
    a['terrain_ids']=len(records);cmd='python3 games/luma_adventure/art/source/candidates/water_r1/import_into_live.py'
    if cmd not in a['additional_import_commands']:a['additional_import_commands'].append(cmd)
    evidence='source/candidates/water_r1/repeat32.png'
    if evidence not in a['review_evidence']:a['review_evidence'].append(evidence)
    a['water_review']='source/candidates/water_r1/import_report.json';write(ART/'acceptance.json',a)
    write(HERE/'import_report.json',dict(status='PASS',scope='Import and exact preservation of all non-water tile metadata/pixels, actor atlas and content files; engine/resource/hardware checks remain separate.',active_mapping='~',active_ids=active,terrain_ids=len(records),preserved_non_water_tiles=len(set(before)-incoming),preserved_actor_hashes={p.name:d for p,d in preserved.items() if p.parent==ART},preserved_content_files=sum(p.is_relative_to(CONTENT) for p in preserved),source_sha256=candidate['source_sha256'],outputs={f:sha(ART/f) for f in ('terrain.png','terrain.json')}))
    print(f'PASS: {len(active)} quiet water variants active; {len(set(before)-incoming)} other tiles and all actor/content inputs preserved. Terrain IDs: {len(records)}.')

if __name__=='__main__':main()
