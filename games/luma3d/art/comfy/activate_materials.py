#!/usr/bin/env python3
"""Apply a reviewed local material bank; preserve the old bank and world geometry.

Run only after renderer comparison is accepted. Preparation alone never invokes it.
"""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent;ART=HERE.parent;ROOT=ART.parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('candidate',type=Path);p.add_argument('--review-evidence',required=True);args=p.parse_args()
 candidate=args.candidate.resolve();report=json.loads((candidate/'report.json').read_text())
 assert len(report['textures'])==8
 geometry={name:sha(ROOT/'world'/name) for name in ['scene.json','meshes.json','heightfield.json']}
 previous=candidate/'pre_activation';previous.mkdir(exist_ok=True)
 original={}
 for name in ['textures.json',*[t['id']+suffix for t in report['textures'] for suffix in ['.rgb565','.png']]]:
  src=ART/name;dst=previous/name
  if dst.exists():assert dst.read_bytes()==src.read_bytes(),'Existing activation archive belongs to an earlier bank; use a new candidate revision'
  else:shutil.copy2(src,dst)
  original[name]=sha(src)
 textures=[]
 for t in report['textures']:
  source=candidate/(t['id']+'.rgb565');assert sha(source)==t['rgb565_sha256']
  textures.append(dict(id=t['id'],source_rgb565=str(source.relative_to(ART)),source_preview=str((candidate/(t['id']+'_modulation128.png')).relative_to(ART)),sha256=sha(source),
    provenance=dict(prompt_id=t['prompt_id'],workflow=t['workflow'],source_sha256=t['source_sha256'],import_report=str((candidate/'report.json').relative_to(ART)))))
 selection=dict(schema=1,status='active_reviewed_import',project_object_uv=True,review_evidence=args.review_evidence,textures=textures)
 (ART/'material_selection.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n')
 subprocess.run([sys.executable,str(ROOT/'tools/build_world.py')],check=True,capture_output=True,text=True)
 assert all(sha(ROOT/'world'/name)==digest for name,digest in geometry.items()),'Texture import changed geometry or physics'
 subprocess.run([sys.executable,str(ROOT/'world/export_c.py')],check=True,capture_output=True,text=True)
 result=dict(status='PASS',scope='Reviewed texture bank activated; active geometry, heightfield, scene and physics unchanged. Native renderer tests remain separate.',
  review_evidence=args.review_evidence,preserved_world_sha256=geometry,previous_art_sha256=original,
  active_art_sha256={t['id']:sha(ART/(t['id']+'.rgb565')) for t in textures},active_data_sha256=sha(ROOT/'world/data.c'))
 (candidate/'activation_report.json').write_text(json.dumps(result,indent=2)+'\n');print('Imported eight reviewed materials; geometry and physics hashes unchanged.')
if __name__=='__main__':main()
