#!/usr/bin/env python3
"""Prepare repeatable 128px RGB565 candidates, leaving the active bank untouched."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

HERE=Path(__file__).resolve().parent
CHOICES=dict(grass='material_grass_qwen_r2',stone='material_stone_flux_r3',earth='material_earth_flux_r3',
 plaster='material_plaster_flux_r3',roof='material_roof_flux_r3',bark='material_bark_flux_r3',water='material_water_flux_r3',leaf='material_leaf_flux_r3')

def pack(a):
 a=a.astype(np.uint32)
 return (((a[:,:,0]*31+127)//255<<11)|((a[:,:,1]*63+127)//255<<5)|((a[:,:,2]*31+127)//255)).astype('<u2')
def unpack(a):
 return np.stack(((a>>11)*255/31,((a>>5)&63)*255/63,(a&31)*255/31),axis=-1).astype(np.uint8)
def seam(a):return float((np.abs(a[0].astype(float)-a[-1]).mean()+np.abs(a[:,0].astype(float)-a[:,-1]).mean())/2)

def main():
 out=HERE/'candidates_r3';out.mkdir(exist_ok=True)
 scene=json.loads((HERE.parents[1]/'world/scene.json').read_text())
 report=[];review=Image.new('RGB',(1024,560),(232,232,225));draw=ImageDraw.Draw(review)
 repeat=Image.new('RGB',(2048,1024))
 for i,(name,job) in enumerate(CHOICES.items()):
  folder=HERE/'renders'/job;meta=json.loads((folder/'submission.json').read_text());assert meta['status']=='generated'
  source=folder/meta['files'][0]['file'];a=np.array(Image.open(source).convert('RGB').resize((128,128),Image.Resampling.LANCZOS)).astype(float)
  # Remove only opposing-edge discrepancies. This is a deterministic import
  # correction, retained beside the uncorrected albedo for direct review.
  periodic=a-np.linspace(-.5,.5,128)[None,:,None]*(a[:,-1]-a[:,0])[:,None,:]
  periodic-=np.linspace(-.5,.5,128)[:,None,None]*(periodic[-1]-periodic[0])[None,:,:]
  periodic=np.clip(periodic,1,255)
  mean=periodic.mean(axis=(0,1));modulation=np.clip(242*(periodic/mean)**.65,0,255).astype(np.uint8)
  packed=pack(modulation);decoded=unpack(packed)
  material=next(m for m in scene['materials'] if Path(m['texture']).stem==name)
  effective=np.clip(decoded.astype(float)*np.array(material['color'])/255,0,255).astype(np.uint8)
  Image.fromarray(a.astype(np.uint8)).save(out/(name+'_raw128.png'))
  Image.fromarray(periodic.astype(np.uint8)).save(out/(name+'_albedo128.png'))
  Image.fromarray(decoded).save(out/(name+'_modulation128.png'))
  Image.fromarray(effective).save(out/(name+'_effective128.png'))
  (out/(name+'.rgb565')).write_bytes(packed.tobytes())
  x=(i%4)*256;y=(i//4)*280
  review.paste(Image.fromarray(effective).resize((256,256),Image.Resampling.NEAREST),(x,y));draw.text((x+5,y+260),name+' / RGB565 x material',fill=(20,20,20))
  block=np.tile(effective,(4,4,1));repeat.paste(Image.fromarray(block),((i%4)*512,(i//4)*512))
  report.append(dict(id=name,status='candidate_not_imported',source=str(source.relative_to(HERE)),prompt_id=meta['prompt_id'],workflow=meta['workflow'],
   source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),rgb565_sha256=hashlib.sha256(packed.tobytes()).hexdigest(),
   source_mean=[round(float(v),2) for v in a.mean(axis=(0,1))],modulation_mean=[round(float(v),2) for v in decoded.mean(axis=(0,1))],
   effective_mean=[round(float(v),2) for v in effective.mean(axis=(0,1))],effective_std=[round(float(v),2) for v in effective.std(axis=(0,1))],
   raw_seam_mean_absolute=round(seam(a),3),rgb565_seam_mean_absolute=round(seam(decoded),3),
   active_material_color=material['color'],clipped_modulation_fraction=round(float((modulation==255).mean()),4)))
 review.save(out/'materials_effective.png');repeat.save(out/'repeat128_x4.png')
 result=dict(status='candidate_review_pending',method='128px Lanczos; remove opposing-edge discrepancies; per-channel mean normalisation with power0.65; RGB565 roundtrip; previews multiply the actual active material colour exactly once. No lighting applied in these swatches.',textures=report,
  active_scene_or_physics_changed=False,active_texture_bank_changed=False)
 (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('Prepared eight candidate RGB565 materials; active bank unchanged.')

if __name__=='__main__':main()
