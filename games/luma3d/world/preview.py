#!/usr/bin/env python3
"""Diagnostic CPU z-buffer preview of the actual authored mesh data.

No runtime images, scenery billboards or camera scripts are produced.
This preview omits texture detail; GPU rendering remains the final reference.
"""
from pathlib import Path
import argparse,json,math
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
def normal(v):return v/max(np.linalg.norm(v),1e-12)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--view',choices=['arrival','village','lake'],default='arrival');a=ap.parse_args()
 scene=json.loads((HERE/'scene.json').read_text());meshes=json.loads((HERE/'meshes.json').read_text())['meshes']
 views={'arrival':([24,26,134],[69,9,80]),'village':([59,10,105],[72,9,77]),'lake':([83,12,104],[113,12,51])}
 eye,target=map(np.array,views[a.view]);forward=normal(target-eye);right=normal(np.cross(forward,[0,1,0]));up=np.cross(right,forward)
 W,H=800,480;f=W/(2*math.tan(math.radians(64)/2));depth=np.full((H,W),np.inf)
 horizon=np.array(scene['sky']['horizon']);zenith=np.array(scene['sky']['zenith'])
 rgb=np.broadcast_to(np.linspace(zenith,horizon,H)[:,None,:],(H,W,3)).copy();light=normal(np.array(scene['light']['direction']))
 fog=np.array(scene['light']['fog_color']);stats={'submitted_triangles':0,'rasterized_triangles':0,'instances':0,'visible_pixels':0}
 instances=list(scene['instances'])
 if a.view=='arrival':instances.append(dict(id='hero_preview',mesh='hero',position=scene['spawn']['position'],scale=[1,1,1],yaw=scene['spawn']['heading'],kind='actor'))
 for obj in instances:
  pos=np.array(obj['position']);scale=np.array(obj['scale']);yaw=obj['yaw'];c,s=math.cos(yaw),math.sin(yaw)
  rot=np.array([[c,0,s],[0,1,0],[-s,0,c]]);name=obj['mesh'];distance=np.linalg.norm(pos-eye)
  for lod in obj.get('lods',[]):
   if distance>lod['distance']:name=lod['mesh']
  mesh=meshes[name];vertices=np.array(mesh['vertices'])*scale@rot.T+pos
  projected=np.stack(((vertices-eye)@right,(vertices-eye)@up,(vertices-eye)@forward),axis=1)
  if projected[:,2].max()<.2:continue
  safe=np.maximum(.2,projected[:,2]);xy=np.stack((W/2+f*projected[:,0]/safe,H/2-f*projected[:,1]/safe),axis=1)
  if xy[:,0].max()<0 or xy[:,0].min()>W or xy[:,1].max()<0 or xy[:,1].min()>H:continue
  stats['instances']+=1
  for face in mesh['faces']:
   ids=face['indices'];v=projected[ids];stats['submitted_triangles']+=1
   # Clip exactly at the camera near plane before perspective division.
   poly=[x for x in v];clipped=[]
   for i,p in enumerate(poly):
    q=poly[(i+1)%len(poly)];pin=p[2]>=.2;qin=q[2]>=.2
    if pin:clipped.append(p)
    if pin!=qin:clipped.append(p+(q-p)*(.2-p[2])/(q[2]-p[2]))
   if len(clipped)<3:continue
   n=normal(np.array(face['normal'])/scale@rot.T)
   if np.dot(n,np.mean(vertices[ids],axis=0)-eye)>0:continue
   material=scene['materials'][face['material']];base=np.array(material['color'])*np.array(face['color'])/255
   illumination=.40+.60*max(0,np.dot(n,light));base=base*illumination
   for k in range(1,len(clipped)-1):
    vv=np.array([clipped[0],clipped[k],clipped[k+1]]);q=1/vv[:,2];p=np.stack((W/2+f*vv[:,0]*q,H/2-f*vv[:,1]*q),axis=1)
    lo=np.maximum([0,0],np.floor(p.min(axis=0))).astype(int);hi=np.minimum([W-1,H-1],np.ceil(p.max(axis=0))).astype(int)
    if np.any(lo>hi):continue
    den=(p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
    if abs(den)<1e-5:continue
    yy,xx=np.mgrid[lo[1]:hi[1]+1,lo[0]:hi[0]+1];xx=xx+.5;yy=yy+.5
    aa=((p[1,1]-p[2,1])*(xx-p[2,0])+(p[2,0]-p[1,0])*(yy-p[2,1]))/den
    bb=((p[2,1]-p[0,1])*(xx-p[2,0])+(p[0,0]-p[2,0])*(yy-p[2,1]))/den;cc=1-aa-bb
    inv=aa*q[0]+bb*q[1]+cc*q[2];zz=1/np.maximum(1e-12,inv)
    old=depth[lo[1]:hi[1]+1,lo[0]:hi[0]+1];mask=(aa>=0)&(bb>=0)&(cc>=0)&(zz<old)
    if not mask.any():continue
    fade=np.clip((zz-scene['light']['fog_start'])/(scene['light']['fog_end']-scene['light']['fog_start']),0,1)
    color=base[None,None,:]*(1-fade[:,:,None])+fog[None,None,:]*fade[:,:,None]
    old[mask]=zz[mask];rgb[lo[1]:hi[1]+1,lo[0]:hi[0]+1][mask]=color[mask];stats['rasterized_triangles']+=1
 stats['visible_pixels']=int(np.isfinite(depth).sum());stats['view']=a.view;stats['camera_position']=eye.tolist();stats['note']='Diagnostic CPU z-buffer, fixed inspection pose, texture detail omitted. Not a gameplay frame or hardware performance result.'
 Image.fromarray(np.clip(rgb,0,255).astype(np.uint8)).save(HERE/('preview_'+a.view+'.png'))
 (HERE/('preview_'+a.view+'.json')).write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps(stats))
if __name__=='__main__':main()
