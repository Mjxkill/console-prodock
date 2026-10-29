#!/usr/bin/env python3
"""Independent coverage, bounds and packed-asset invariants for LUMA's valley."""
import hashlib,json,math
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
def main():
 scene=json.loads((HERE/'scene.json').read_text());meshes=json.loads((HERE/'meshes.json').read_text())['meshes'];hf=json.loads((HERE/'heightfield.json').read_text())
 def h(x,z):
  x=max(0,min(79.999999,x/2));z=max(0,min(79.999999,z/2));ix=int(x);iz=int(z);u=x-ix;v=z-iz
  a=hf['heights'][iz][ix];b=hf['heights'][iz][ix+1];c=hf['heights'][iz+1][ix+1];d=hf['heights'][iz+1][ix]
  return a+(b-a)*u+(c-b)*v if u>=v else a+(c-d)*u+(d-a)*v
 reports=[];total_degenerate=0;worst_area=0;worst_height=0
 for name,m in meshes.items():
  vv=np.array(m['vertices']);assert np.isfinite(vv).all();assert all(len(f['indices'])==3 for f in m['faces'])
  mat_vertices={};area=0;degenerate=0
  for face in m['faces']:
   ids=face['indices'];assert len(set(ids))==3 and all(0<=i<len(vv) for i in ids)
   assert 0<=face['material']<len(scene['materials']);mat_vertices.setdefault(face['material'],set()).update(ids)
   p=vv[ids];cross=np.cross(p[1]-p[0],p[2]-p[0]);length=np.linalg.norm(cross)
   assert abs(np.linalg.norm(face['normal'])-1)<2e-6
   if length<1e-6:degenerate+=1
   elif length>1e-4:assert np.dot(cross/length,face['normal'])>.999,(name,'normal disagrees with winding')
   if name.startswith('terrain_'):
    assert cross[1]>=-1e-5,(name,'downward ground face')
    area+=abs(cross[1])*.5
  assert max(map(len,mat_vertices.values()))<=256,(name,'index budget')
  if name.startswith('terrain_'):
   error=abs(area-256);worst_area=max(worst_area,error);assert error<.005,(name,'terrain coverage mismatch',area)
   if name.endswith('lod0'):
    _,xx,zz,_=name.split('_');tx=int(xx)*16;tz=int(zz)*16
    for face in m['faces']:
     if face['normal'][1]<=1e-5:continue
     for vertex in vv[face['indices']]:
      err=abs(vertex[1]-h(tx+vertex[0],tz+vertex[2]));worst_height=max(worst_height,err);assert err<.0001,(name,'render surface differs from collision',err)
   reports.append(dict(mesh=name,footprint_area=round(area,6),near_degenerate_faces=degenerate))
  total_degenerate+=degenerate
 for obj in scene['instances']:
  assert obj['mesh'] in meshes and len(obj.get('lods',[]))<=2
  assert max(obj['scale'])-min(obj['scale'])<1e-9,'Unbaked nonuniform instance scale changes lighting normals'
  for lod in obj.get('lods',[]):assert lod['mesh'] in meshes
 assert len(scene['gameplay']['route'])<=32 and len(scene['gameplay']['collectibles'])<=8
 for p in scene['gameplay']['route']:assert abs(p['y']-h(p['x'],p['z']))<.0001
 result=dict(status='PASS',scope='Independent projected terrain area, normal orientation, full-detail terrain/collision agreement, group index bounds and uniform-scale lighting. Does not prove hardware FPS or artistic acceptance.',
  terrain_patches_and_lods=len(reports),worst_footprint_area_error_square_metres=worst_area,worst_render_collision_height_error_metres=worst_height,
  near_degenerate_faces=total_degenerate,near_degenerate_note='Measured after five-decimal vertex quantisation; zero-area projected slivers are culled by the renderer.',
  terrain=reports,inputs={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ['scene.json','meshes.json','heightfield.json']})
 (HERE/'asset_validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['terrain','inputs']}))
if __name__=='__main__':main()
