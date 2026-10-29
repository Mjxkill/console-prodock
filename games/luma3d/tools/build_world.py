#!/usr/bin/env python3
"""LUMA3D: original authored valley and reusable, genuinely three-dimensional models.

Writes only ../world and ../art. No camera sequence, external service or video.
Axes are X east, Y up, Z south, units metres; rotations are radians about +Y.
"""
from pathlib import Path
import hashlib,json,math,random,shutil
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'world';ART=ROOT/'art'
SEED=240326
MATERIALS=[
 ('meadow',(109,157,75),'grass'),('chalk',(155,164,139),'stone'),
 ('trail',(185,161,111),'earth'),('plaster',(225,210,168),'plaster'),
 ('terracotta',(164,84,61),'roof'),('timber',(101,74,46),'bark'),
 ('water',(61,156,166),'water'),('leaf',(85,139,67),'leaf'),
 ('glass',(106,182,181),'water'),('gold',(229,187,85),'plaster'),
 ('shadow',(56,68,69),'stone'),('foam',(194,232,218),'water'),
 ('flowers',(230,153,158),'leaf'),('cloth',(54,113,132),'plaster')]

def write(path,value):
 data=json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n'
 if not path.exists() or path.read_text()!=data:path.write_text(data)
def norm(v):
 v=np.array(v,dtype=float);return v/max(np.linalg.norm(v),1e-12)
def smooth(a,b,t):
 t=max(0,min(1,t));return a+(b-a)*t*t*(3-2*t)
def gauss(x,z,cx,cz,sx,sz):return math.exp(-((x-cx)/sx)**2-((z-cz)/sz)**2)

class Mesh:
 def __init__(self):self.vertices=[];self.faces=[]
 def face(self,points,material,color=None,uv=None):
  if uv is None:
   points=[p for i,p in enumerate(points) if np.linalg.norm(np.array(p)-np.array(points[i-1]))>1e-6]
   changed=True
   while changed and len(points)>3:
    changed=False
    for i,p in enumerate(points):
     a=np.array(points[i-1]);b=np.array(p);c=np.array(points[(i+1)%len(points)])
     if np.linalg.norm(np.cross(b-a,c-b))<1e-7:
      points.pop(i);changed=True;break
  if len(points)<3:return
  off=len(self.vertices);self.vertices.extend([list(map(float,p)) for p in points])
  for k in range(1,len(points)-1):
   ids=[off,off+k,off+k+1];a,b,c=[np.array(self.vertices[i]) for i in ids]
   n=np.cross(b-a,c-a);length=np.linalg.norm(n)
   if length<1e-8:continue
   self.faces.append(dict(indices=ids,normal=[round(float(v),6) for v in n/length],
      uv=[uv[i] for i in (0,k,k+1)] if uv else [[0,0],[128,0],[128,128]],
      material=material,color=list(color or (255,255,255))))
 def solid(self,points,polygons,material):
  center=np.mean(points,axis=0)
  for poly in polygons:
   pp=[points[i] for i in poly];a,b,c=map(np.array,pp[:3])
   if np.dot(np.cross(b-a,c-a),a-center)<0:pp=list(reversed(pp))
   self.face(pp,material)
 def box(self,center,size,material):
  x,y,z=center;sx,sy,sz=[v/2 for v in size]
  p=[(x+a*sx,y+b*sy,z+c*sz) for a,b,c in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
  self.solid(p,[(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],material)
 def tube(self,a,b,ra,rb,material,sides=6):
  a=np.array(a);b=np.array(b);axis=norm(b-a);ref=np.array([0.,1.,0.])
  if abs(np.dot(axis,ref))>.9:ref=np.array([1.,0.,0.])
  u=norm(np.cross(axis,ref));v=np.cross(axis,u)
  points=[list(c+r*(u*math.cos(i*math.tau/sides)+v*math.sin(i*math.tau/sides))) for c,r in [(a,ra),(b,rb)] for i in range(sides)]
  polys=[(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)]+[tuple(range(sides-1,-1,-1)),tuple(range(sides,2*sides))]
  self.solid(points,polys,material)
 def crown(self,center,scale,material,seed=0,sides=7):
  rng=random.Random(seed);cx,cy,cz=center;sx,sy,sz=scale;points=[]
  for ring,(yy,rad) in enumerate([(-.55,.55),(-.05,1),(.55,.72)]):
   for i in range(sides):
    angle=math.tau*(i+.17*ring)/sides;rr=rad*rng.uniform(.87,1.13)
    points.append((cx+math.cos(angle)*sx*rr,cy+(yy+rng.uniform(-.09,.09))*sy,cz+math.sin(angle)*sz*rr))
  points.extend([(cx+.13*sx,cy+sy,cz-.08*sz),(cx,cy-.78*sy,cz)])
  polys=[]
  for r in range(2):
   for i in range(sides):polys.append((r*sides+i,r*sides+(i+1)%sides,(r+1)*sides+(i+1)%sides,(r+1)*sides+i))
  polys.extend((2*sides+i,2*sides+(i+1)%sides,3*sides) for i in range(sides))
  polys.extend(((i+1)%sides,i,3*sides+1) for i in range(sides))
  self.solid(points,polys,material)
 def export(self):
  # Deduplicate the authored positions. G3D1 indices have eight bits, so large
  # meshes are partitioned into independent <=240-vertex draw groups below.
  unique=[];lookup={};remap=[]
  used={i for f in self.faces for i in f['indices']}
  for original,p in enumerate(self.vertices):
   if original not in used:remap.append(-1);continue
   key=tuple(round(x,5) for x in p)
   if key not in lookup:lookup[key]=len(unique);unique.append(list(key))
   remap.append(lookup[key])
  faces=[]
  for f in self.faces:
   f=dict(f);f['indices']=[remap[i] for i in f['indices']];faces.append(f)
  minimum=np.min(unique,axis=0).tolist();maximum=np.max(unique,axis=0).tolist()
  return dict(vertices=unique,faces=faces,bounds=dict(min=minimum,max=maximum))

def tree(kind='oak',low=False):
 m=Mesh();m.tube((0,0,0),(.18,3.8,0),.38,.20,5,5 if low else 7)
 if kind=='pine':
  for y,r in [(2.8,2.2),(4.2,1.75),(5.7,1.25)]:
   p=[(math.cos(i*math.tau/7)*r,y,math.sin(i*math.tau/7)*r) for i in range(7)]+[(.12,y+2.7,-.08)]
   m.solid(p,[(i,(i+1)%7,7) for i in range(7)]+[tuple(range(6,-1,-1))],7)
 elif low:m.crown((0,4.4,0),(2.7,2.2,2.6),12 if kind=='blossom' else 7,12,5)
 else:
  for n,(x,y,z,s) in enumerate([(-1.4,4.2,-.2,1.8),(1.15,4.5,.55,1.9),(0,5.6,-.4,2.0)]):
   m.tube((.1,2.7,0),(x,y,z),.16,.08,5,5)
   m.crown((x,y,z),(s,s*.85,s*.95),12 if kind=='blossom' else 7,42+n,6)
 return m

def house(low=False):
 m=Mesh();w,d=5.8,4.6
 # A gabled pentagonal volume, with the roof extending beyond the walls.
 p=[(x,y,z) for z in (-d/2,d/2) for x,y in [(-w/2,0),(w/2,0),(w/2,3.3),(0,5.3),(-w/2,3.3)]]
 m.solid(p,[(0,4,3,2,1),(5,6,7,8,9),(0,1,6,5),(1,2,7,6),(4,0,5,9)],3)
 # Broad bent roof slopes catch light in three strips, avoiding a box silhouette.
 for side in (-1,1):
  profile=[(0,5.5),(side*1.65,4.7),(side*3.3,3.1)]
  for (x0,y0),(x1,y1) in zip(profile,profile[1:]):
   q=[(x0,y0,-2.65),(x1,y1,-2.65),(x1,y1,2.65),(x0,y0,2.65)]
   if side>0:q.reverse()
   m.face(q,4,uv=[[0,0],[128,0],[128,128],[0,128]])
 if not low:
  m.box((1.8,4.8,-.8),(.65,2.0,.7),1)
  m.box((1.8,5.82,-.8),(.9,.18,.92),3)
  m.box((0,.98,2.34),(1.15,1.96,.12),5)
  m.tube((-.65,0,2.40),(-.65,2.25,2.40),.08,.08,5,4);m.tube((.65,0,2.40),(.65,2.25,2.40),.08,.08,5,4)
  m.box((0,2.26,2.40),(1.45,.18,.17),5)
  for x in (-1.85,1.85):
   m.box((x,1.85,2.37),(1.0,1.0,.10),5);m.box((x,1.85,2.44),(.76,.76,.06),8)
   m.box((x,1.85,2.49),(.07,.84,.05),3);m.box((x,1.85,2.49),(.84,.07,.05),3)
   m.box((x,1.25,2.65),(1.25,.22,.55),5)
  for x in (-2.95,2.95):m.box((x,1.65,2.35),(.18,3.3,.18),5)
 return m

def mill(low=False,rotor=True):
 m=Mesh();m.tube((0,0,0),(0,8.1,0),2.3,1.4,3,8)
 roof=[(math.cos(i*math.tau/8)*1.9,8,math.sin(i*math.tau/8)*1.9) for i in range(8)]+[(0,10.5,0)]
 m.solid(roof,[(i,(i+1)%8,8) for i in range(8)],4)
 m.tube((0,6.4,1.1),(0,6.4,2.3),.25,.25,5,8)
 for i in range(4 if rotor else 0):
  a=i*math.pi/2+.24;rad=np.array([math.cos(a),math.sin(a),0]);side=np.array([-math.sin(a),math.cos(a),0]);c=np.array([0,6.4,2.4])
  points=[c+rad*r+side*s for r,s in [(.6,-.12),(5.4,-.4),(5.1,.8),(1.1,.2)]]
  m.face(points,3)
  if not low:m.tube(c+rad*.5,c+rad*5.5,.06,.05,5,4)
 if not low:m.box((0,1.1,2.1),(1.1,2.2,.16),5);m.box((0,4.1,1.76),(.75,1.2,.12),8)
 return m

def ruin(low=False):
 m=Mesh();r1,r2=2.2,3.0;n=8
 for side in (-1,1):
  m.tube((side*2.6,0,0),(side*2.6,3.4,0),.6,.53,1,6)
  if not low:m.box((side*2.6,.2,0),(1.5,.4,1.5),1)
 for i in range(n):
  # Separate stone voussoirs keep an actual hollow arch and broken outer edges.
  a=i*math.pi/n;b=(i+1)*math.pi/n-.012
  points=[(math.cos(t)*r,3.1+math.sin(t)*r,z) for z in (-.6,.6) for t,r in [(a,r1),(a,r2),(b,r2),(b,r1)]]
  m.solid(points,[(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],1)
 return m

def bridge(low=False):
 m=Mesh();segments=6 if low else 10
 for i in range(segments):
  x0=-7+14*i/segments;x1=-7+14*(i+1)/segments
  y0=.7*math.sin((x0+7)/14*math.pi);y1=.7*math.sin((x1+7)/14*math.pi)
  m.face([(x0,y0,-1.5),(x0,y0,1.5),(x1,y1,1.5),(x1,y1,-1.5)],5)
  if not low:
   for side in (-1,1):
    if i%2==0:m.tube((x0,y0,side*1.55),(x0,y0+1.05,side*1.55),.07,.07,5,4)
    m.face([(x0,y0+.88,side*1.55),(x1,y1+.88,side*1.55),(x1,y1+1.02,side*1.55),(x0,y0+1.02,side*1.55)],5)
 return m

def hero():
 m=Mesh()
 for side in (-1,1):
  m.tube((side*.18,.1,0),(side*.16,.8,0),.13,.14,5,5)
  m.crown((side*.18,.12,.1),(.17,.12,.28),5,2,5)
 m.tube((0,.64,0),(0,1.28,0),.32,.25,13,7)
 m.tube((0,.75,0),(0,.83,0),.33,.33,5,7)
 m.crown((0,1.55,0),(.23,.27,.22),3,2,7)
 m.crown((0,1.73,-.02),(.25,.15,.24),5,11,6)
 for side in (-1,1):
  m.tube((side*.24,1.18,0),(side*.39,.78,.06),.12,.09,13,5)
  m.crown((side*.40,.72,.06),(.09,.12,.10),3,3,5)
 # A small ochre shoulder cape and a real backpack are readable from behind.
 m.face([(-.30,1.27,-.1),(.30,1.27,-.1),(.42,.68,-.30),(-.38,.68,-.30)],9)
 m.crown((0,1.0,-.3),(.23,.27,.12),5,8,5)
 return m

def hero_parts():
 parts=[]
 for side,name,kind in [(-1,'leg_left',1),(1,'leg_right',2)]:
  m=Mesh();m.tube((side*.18,.1,0),(side*.16,.8,0),.13,.14,5,5);m.crown((side*.18,.12,.1),(.17,.12,.28),5,2,5)
  parts.append((name,kind,[side*.17,.76,0],m))
 body=Mesh();body.tube((0,.64,0),(0,1.28,0),.32,.25,13,7);body.tube((0,.75,0),(0,.83,0),.33,.33,5,7)
 body.crown((0,1.55,0),(.23,.27,.22),3,2,7);body.crown((0,1.73,-.02),(.25,.15,.24),5,11,6)
 body.crown((0,1.0,-.3),(.23,.27,.12),5,8,5);parts.append(('body',0,[0,0,0],body))
 for side,name,kind in [(-1,'arm_left',3),(1,'arm_right',4)]:
  m=Mesh();m.tube((side*.24,1.18,0),(side*.39,.78,.06),.12,.09,13,5);m.crown((side*.40,.72,.06),(.09,.12,.10),3,3,5)
  parts.append((name,kind,[side*.24,1.18,0],m))
 cape=Mesh();cape.face([(-.30,1.27,-.1),(.30,1.27,-.1),(.42,.68,-.30),(-.38,.68,-.30)],9)
 # Two-sided thin cloth is explicitly modelled, not a global culling override.
 cape.face([(-.38,.68,-.30),(.42,.68,-.30),(.30,1.27,-.1),(-.30,1.27,-.1)],9)
 parts.append(('cape',5,[0,1.25,-.12],cape))
 for _,_,pivot,m in parts:m.vertices=[[p[i]-pivot[i] for i in range(3)] for p in m.vertices]
 return parts

def windmill_rotor():
 m=Mesh()
 for i in range(4):
  a=i*math.pi/2+.24;rad=np.array([math.cos(a),math.sin(a),0]);side=np.array([-math.sin(a),math.cos(a),0])
  pts=[rad*r+side*s for r,s in [(.6,-.12),(5.4,-.4),(5.1,.8),(1.1,.2)]]
  m.face(pts,3);m.face(list(reversed(pts)),3);m.tube(rad*.5,rad*5.5,.06,.05,5,4)
 return m

def letter():
 m=Mesh();m.box((0,0,0),(.72,.48,.10),3)
 m.face([(-.35,.23,.056),(.35,.23,.056),(0,-.04,.075)],9)
 m.face([(-.35,-.23,.056),(0,.02,.075),(.35,-.23,.056)],3)
 m.crown((0,-.045,.09),(.065,.065,.025),4,8,6)
 return m

def catmull(points,sub=8):
 out=[]
 for i in range(len(points)-1):
  p0=np.array(points[max(0,i-1)]);p1=np.array(points[i]);p2=np.array(points[i+1]);p3=np.array(points[min(len(points)-1,i+2)])
  for t in np.linspace(0,1,sub,endpoint=False):out.append((.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)).tolist())
 return out+[list(points[-1])]

TRAILS=[dict(id='village_trail',width=3.4,points=catmull([(28,20,126),(36,17,115),(50,11,109),(62,7,101),(67,6,91),(66,7,79),(59,13,66),(52,17,57)],4)),
 dict(id='ruins_trail',width=3.0,points=catmull([(67,6,91),(77,7,78),(88,9,65),(93,13,53),(96,17,48),(98,20,45),(101,22,43),(123,26,36)],4))]

def nearest_trail(x,z):
 best=(1e6,0,0)
 for trail in TRAILS:
  for a,b in zip(trail['points'],trail['points'][1:]):
   dx,dz=b[0]-a[0],b[2]-a[2];den=dx*dx+dz*dz;t=max(0,min(1,((x-a[0])*dx+(z-a[2])*dz)/den)) if den else 0
   distance=math.hypot(x-a[0]-t*dx,z-a[2]-t*dz)
   if distance<best[0]:best=(distance,a[1]+t*(b[1]-a[1]),trail['width'])
 return best

def road_polygons():
 out=[]
 for trail in TRAILS:
  pts=trail['points'];cross=[]
  for i,p in enumerate(pts):
   a=pts[max(0,i-1)];b=pts[min(len(pts)-1,i+1)];d=norm([b[0]-a[0],0,b[2]-a[2]])
   right=np.array([d[2],0,-d[0]])*trail['width']/2
   cross.append([(p[0]+side*right[0],p[2]+side*right[2]) for side in (-1,1)])
  for i in range(len(cross)-1):out.append([cross[i][0],cross[i+1][0],cross[i+1][1],cross[i][1]])
 return out

def half_plane(poly,a,b,side):
 """Clip a 3D polygon in XZ; inserted points stay on its original plane."""
 result=[]
 def value(p):return side*((b[0]-a[0])*(p[2]-a[1])-(b[1]-a[1])*(p[0]-a[0]))
 for i,p in enumerate(poly):
  q=poly[(i+1)%len(poly)];vp=value(p);vq=value(q);pin=vp>=-1e-8;qin=vq>=-1e-8
  if pin:result.append(p)
  if pin!=qin:
   t=vp/(vp-vq);result.append(tuple(p[j]+t*(q[j]-p[j]) for j in range(3)))
 return result

def cut_road(triangle,roads):
 """Partition terrain itself: the road cannot float above an unlike LOD."""
 rest=[triangle];painted=[]
 for quad in roads:
  xmin=min(p[0] for p in quad);xmax=max(p[0] for p in quad);zmin=min(p[1] for p in quad);zmax=max(p[1] for p in quad)
  sign=1 if sum(quad[i][0]*quad[(i+1)%4][1]-quad[(i+1)%4][0]*quad[i][1] for i in range(4))>0 else -1
  remaining=[]
  for poly in rest:
   if max(p[0] for p in poly)<xmin or min(p[0] for p in poly)>xmax or max(p[2] for p in poly)<zmin or min(p[2] for p in poly)>zmax:
    remaining.append(poly);continue
   inside=poly
   for i,a in enumerate(quad):
    if len(inside)<3:break
    b=quad[(i+1)%4];outside=half_plane(inside,a,b,-sign)
    if len(outside)>=3:remaining.append(outside)
    inside=half_plane(inside,a,b,sign)
   if len(inside)>=3:painted.append(inside)
  rest=remaining
 return [(p,False) for p in rest]+[(p,True) for p in painted]

def landscape(x,z):
 h=5.5+1.4*math.sin(x*.065+z*.021)+1.0*math.cos(z*.085-x*.024)
 for cx,cz,sx,sz,amp in [(17,128,24,28,13),(50,57,18,21,13),(111,26,38,20,28),(34,5,25,18,33),(149,66,16,39,25),(6,62,15,48,24),(150,143,25,19,16)]:h+=amp*gauss(x,z,cx,cz,sx,sz)
 lake=math.sqrt(((x-106)/25)**2+((z-89)/20)**2)
 if lake<1.22:h=smooth(-3+4.6*min(lake,1)**4,h,(lake-.91)/.31)
 if 53<z<77:
  river=114+2*math.sin((z-53)*.13);weight=1-smooth(0,1,(abs(x-river)-3)/5)
  h=h*(1-weight)+1.0*weight
 # Above the cascade a ledge holds a narrow stream, below it the river is cut.
 if 25<z<47 and abs(x-114)<7:
  weight=1-smooth(0,1,(abs(x-114)-2.4)/4.6);h=h*(1-weight)+22.0*weight
 distance,path_y,width=nearest_trail(x,z)
 if distance<width/2+4.0:
  weight=1-smooth(0,1,(distance-width/2)/4);h=h*(1-weight)+path_y*weight
 # An intentionally calm, walkable clearing supports the clustered village.
 clear=math.hypot((x-66)/1.1,z-92)
 if clear<12:h=smooth(6,h,(clear-7)/5)
 return h

def textures():
 selection=ART/'material_selection.json'
 if selection.exists():
  chosen=json.loads(selection.read_text());assert chosen['status']=='active_reviewed_import'
  names=[]
  for t in chosen['textures']:
   source=ART/t['source_rgb565'];image=ART/t['source_preview']
   assert hashlib.sha256(source.read_bytes()).hexdigest()==t['sha256']
   shutil.copyfile(source,ART/(t['id']+'.rgb565'));shutil.copyfile(image,ART/(t['id']+'.png'))
   names.append(dict(id=t['id'],width=128,height=128,format='RGB565_LE',file=t['id']+'.rgb565',preview=t['id']+'.png',bytes=32768,
       provenance=t['provenance']))
  write(ART/'textures.json',dict(schema=1,provenance='Locally generated ComfyUI material sources, reviewed and converted through the retained import workflow.',textures=names))
  return
 rng=np.random.default_rng(SEED);names=[]
 for ti,(name,color) in enumerate([(t,next(c for _,c,t2 in MATERIALS if t==t2)) for t in dict.fromkeys(t for _,_,t in MATERIALS)]):
  y,x=np.mgrid[:128,:128];noise=rng.normal(0,1,(128,128))
  detail=2.4*np.sin(x*math.tau/32)*np.cos(y*math.tau/64)+1.6*np.cos((x+y)*math.tau/16)+noise*.65
  if name=='bark':detail+=4*np.sin(x*math.tau/16+np.sin(y*math.tau/128))
  if name=='roof':detail+=np.where(y%32<2,-9,0)+np.where((x+(y//32%2)*16)%32<2,-5,0)
  if name=='water':detail=2.2*np.sin(y*math.tau/16+np.sin(x*math.tau/64))+np.sin((x+y)*math.tau/32)
  # Material tint lives in scene.json. These neutral texture values prevent
  # double tinting, and weak periodic detail has no vignette/tile border.
  rgb=np.clip(239+detail[:,:,None]*np.array([1.0,.95,.85]),0,255)
  rgb=rgb.astype(np.uint8);im=Image.fromarray(rgb);im.save(ART/(name+'.png'))
  a=rgb.astype(np.uint32);packed=(((a[:,:,0]*31+127)//255<<11)|((a[:,:,1]*63+127)//255<<5)|((a[:,:,2]*31+127)//255)).astype('<u2')
  (ART/(name+'.rgb565')).write_bytes(packed.tobytes())
  names.append(dict(id=name,width=128,height=128,format='RGB565_LE',file=name+'.rgb565',preview=name+'.png',bytes=32768))
 write(ART/'textures.json',dict(schema=1,provenance='Original deterministic procedural surfaces; no generated image service used.',seed=SEED,textures=names))

def main():
 OUT.mkdir(parents=True,exist_ok=True);ART.mkdir(parents=True,exist_ok=True)
 textures();heights=[[round(landscape(x*2,z*2),5) for x in range(81)] for z in range(81)]
 def height(x,z):
  fx=max(0,min(79.999,x/2));fz=max(0,min(79.999,z/2));ix=int(fx);iz=int(fz);u=fx-ix;v=fz-iz
  a=heights[iz][ix];b=heights[iz][ix+1];c=heights[iz+1][ix+1];d=heights[iz+1][ix]
  return a+(b-a)*u+(c-b)*v if u>=v else a+(c-d)*u+(d-a)*v
 meshes={};instances=[];colliders=[];roads=road_polygons()
 def register(name,m):meshes[name]=m.export()
 def instance(eid,mesh,x,z,scale=(1,1,1),yaw=0,y=None,kind='prop',radius=0,lods=None):
  obj=dict(id=eid,mesh=mesh,position=[round(x,4),round(height(x,z) if y is None else y,4),round(z,4)],scale=list(scale),yaw=round(yaw,5),kind=kind)
  if lods:obj['lods']=lods
  instances.append(obj)
  if radius:colliders.append(dict(id=eid,kind='circle',x=x,z=z,radius=radius,min_y=obj['position'][1],max_y=obj['position'][1]+8*scale[1]))
  return obj
 for tz in range(10):
  for tx in range(10):
   for lod,step in enumerate((1,2,4)):
    m=Mesh()
    for iz in range(0,8,step):
     for ix in range(0,8,step):
      x=tx*16+ix*2;z=tz*16+iz*2;size=step*2
      p=[(x-tx*16,heights[tz*8+iz][tx*8+ix],z-tz*16),(x-tx*16+size,heights[tz*8+iz][tx*8+ix+step],z-tz*16),(x-tx*16+size,heights[tz*8+iz+step][tx*8+ix+step],z-tz*16+size),(x-tx*16,heights[tz*8+iz+step][tx*8+ix],z-tz*16+size)]
      slope=(max(q[1] for q in p)-min(q[1] for q in p))/size
      lake=math.sqrt(((x+size/2-106)/25)**2+((z+size/2-89)/20)**2)
      mat=1 if slope>.85 else 2 if lake<1.12 else 0
      shade=1+.04*math.sin(x*.065)*math.cos(z*.071);color=tuple(int(min(255,v*shade)) for v in (248,250,239))
      for ids in ((0,2,1),(0,3,2)):
       triangle=[(p[i][0]+tx*16,p[i][1],p[i][2]+tz*16) for i in ids]
       for polygon,on_road in cut_road(triangle,roads):
        local=[(v[0]-tx*16,v[1],v[2]-tz*16) for v in polygon]
        m.face(local,2 if on_road else mat,color,[[v[0]*16,v[2]*16] for v in polygon])
    # Short downward skirts close T-junction cracks between neighbouring LODs.
    # They do not affect the collision surface or add any hidden flat backdrop.
    bottom=min(heights[tz*8+zz][tx*8+xx] for zz in range(9) for xx in range(9))-6
    for edge in range(4):
     top=[]
     for q in range(0,9,step):
      ix,iz=[(q,0),(8,q),(8-q,8),(0,8-q)][edge]
      top.append((ix*2,heights[tz*8+iz][tx*8+ix],iz*2))
     m.face([(top[0][0],bottom,top[0][2]),*top,(top[-1][0],bottom,top[-1][2])],0)
    register(f'terrain_{tx:02}_{tz:02}_lod{lod}',m)
   instance(f'terrain_{tx:02}_{tz:02}',f'terrain_{tx:02}_{tz:02}_lod0',tx*16,tz*16,y=0,kind='terrain',lods=[dict(distance=28,mesh=f'terrain_{tx:02}_{tz:02}_lod1'),dict(distance=58,mesh=f'terrain_{tx:02}_{tz:02}_lod2')])
 for name,fn in [('oak',lambda low:tree('oak',low)),('blossom',lambda low:tree('blossom',low)),('pine',lambda low:tree('pine',low)),('cottage',house),('windmill',mill),('ruin_arch',ruin),('bridge',bridge)]:
  register(name,fn(False));register(name+'_low',fn(True))
 rock=Mesh();rock.crown((0,.64,0),(1.5,.96,1.1),1,9,6);register('rock',rock)
 register('hero',hero())
 parts=hero_parts()
 for name,_,_,mesh in parts:register('hero_'+name,mesh)
 register('windmill_static',mill(rotor=False));register('windmill_rotor',windmill_rotor());register('letter',letter())
 houses=[('maelle_home',60,94,1.0,.15),('inn',70,96,1.15,-.25),('workshop',64,84,.9,2.8),('lakeside_home',75,87,.85,-1.0)]
 for name,x,z,s,yaw in houses:
  instance(name,'cottage',x,z,(s,s,s),yaw,radius=3.5*s,lods=[dict(distance=42,mesh='cottage_low')])
 instance('windmill','windmill',52,57,(1.1,1.1,1.1),.18,radius=2.6,lods=[dict(distance=65,mesh='windmill_low')])
 instance('old_observatory','ruin_arch',123,36,(1.7,1.7,1.7),-.38,lods=[dict(distance=70,mesh='ruin_arch_low')])
 for s in (-1,1):colliders.append(dict(id='old_observatory_pier_'+str(s),kind='circle',x=123+s*4.1,z=36+s*1.6,radius=1.0,min_y=height(123,36),max_y=height(123,36)+7))
 # The river footbridge supplies an explicit walkable height profile.
 instance('river_bridge','bridge',114,65,y=3.3,kind='bridge')
 colliders.append(dict(id='river_bridge_deck',kind='walkable_bridge',x=114,z=65,length=14,width=3,y=3.3,arch_height=.7,yaw=0))
 rng=random.Random(SEED)
 explicit=[('oak',18,129,1.3),('oak',39,134,1.1),('blossom',58,88,1.05),('blossom',74,101,.8),('oak',85,108,1.0),('pine',132,45,1.0)]
 for i,(kind,x,z,s) in enumerate(explicit):instance('tree_landmark_'+str(i),kind,x,z,(s,s,s),rng.random()*math.tau,radius=.4*s,lods=[dict(distance=35,mesh=kind+'_low')])
 placed=[(x,z) for _,x,z,_ in explicit]
 for i in range(80):
  x=rng.uniform(8,152);z=rng.uniform(12,150);h=height(x,z);near,width=nearest_trail(x,z)[0],nearest_trail(x,z)[2]
  if h<3 or near<width/2+3 or math.hypot(x-66,z-92)<15 or min(math.hypot(x-a,z-b) for a,b in placed)<7:continue
  if (x-31)**2+(z-121)**2<70:continue
  kind='pine' if h>20 else 'oak';s=rng.uniform(.75,1.5)
  instance('tree_'+str(i),kind,x,z,(s,s,s),rng.random()*math.tau,radius=.4*s,lods=[dict(distance=32,mesh=kind+'_low')]);placed.append((x,z))
 for i,(x,z) in enumerate([(22,121),(35,131),(91,106),(131,88),(125,58),(107,52),(118,42),(120,32),(128,35),(129,39)]):
  s=rng.uniform(.7,1.6);obj=instance('stone_'+str(i),'rock',x,z,(s,s,s),rng.random()*math.tau,radius=1.1*s)
  colliders[-1]['max_y']=obj['position'][1]+6.4*s
 # Lake polygon and its feeder are real horizontal meshes with a coherent level.
 lake=Mesh();outline=[(106+math.cos(i*math.tau/36)*24.5,2.4,89+math.sin(i*math.tau/36)*19.5) for i in range(36)]
 for i in range(36):lake.face([(106,2.4,89),outline[(i+1)%36],outline[i]],6,uv=[[64,64],[(outline[(i+1)%36][0]-80)*8,(outline[(i+1)%36][2]-65)*8],[(outline[i][0]-80)*8,(outline[i][2]-65)*8]])
 register('lake',lake);instance('lake','lake',0,0,y=0,kind='water')
 river=Mesh()
 for z in range(54,80,2):
  x0=114+2*math.sin((z-53)*.13);x1=114+2*math.sin((z+2-53)*.13)
  river.face([(x0-2.7,2.4,z),(x1-2.7,2.4,z+2),(x1+2.7,2.4,z+2),(x0+2.7,2.4,z)],6,uv=[[0,z*16],[0,(z+2)*16],[128,(z+2)*16],[128,z*16]])
 register('river',river);instance('river','river',0,0,y=0,kind='water')
 fall=Mesh()
 for i in range(4):
  x=111.4+i*1.3;fall.face([(x-.2,2.5,55),(x+1.5,2.5,55),(x+1.3,22.4,46),(x,22.4,46)],11 if i%3==0 else 6,uv=[[0,512],[32,512],[32,0],[0,0]])
 fall.face([(110.8,2.46,54),(110.8,2.46,58),(117.5,2.46,58),(117.5,2.46,54)],11)
 register('waterfall',fall);instance('waterfall','waterfall',0,0,y=0,kind='waterfall')
 water_zones=[dict(id='lake',kind='ellipse',x=106,z=89,rx=24.5,rz=19.5,level=2.4),dict(id='river',kind='ribbon',points=[[114+2*math.sin((z-53)*.13),z] for z in range(54,80,2)],width=5.4,level=2.4)]
 world=dict(schema=1,title='LUMA — Le Val des Courriers',units='metres',axes=dict(x='east',y='up',z='south'),
  terrain=dict(heightfield='heightfield.json',patch_size=16,diagonal='00_to_11',triangles=[[0,2,1],[0,3,2]],render_lod_does_not_change_collision=True),
  materials=[dict(id=i,name=n,color=list(c),texture='../art/'+t+'.rgb565',texture_size=[128,128]) for i,(n,c,t) in enumerate(MATERIALS)],
  meshes='meshes.json',instances=instances,colliders=colliders,water_zones=water_zones,paths=TRAILS,
  spawn=dict(position=[28,round(height(28,126),5),126],heading=math.atan2(67-28,91-126)),
  light=dict(direction=[-.48,.78,.40],ambient=.38,color=[255,242,214],fog_color=[160,196,189],fog_start=65,fog_end=165),
  sky=dict(horizon=[196,218,200],zenith=[100,164,190]),
  landmarks=[dict(id=e['id'],position=e['position'],name=label) for e,label in [(next(e for e in instances if e['id']=='maelle_home'),'Le hameau des lettres'),(next(e for e in instances if e['id']=='windmill'),'Le moulin des chemins'),(next(e for e in instances if e['id']=='old_observatory'),'La porte des nuages')]],
  budgets=dict(target_visible_triangles=2500,target_draw_calls=90,measured_hardware_fps=None,terrain_lod_distances=[28,58],note='Targets only. Renderer must frustum-cull and select LOD, then report actual counts; not all stored triangles are submitted each frame.'),
  provenance=dict(seed=SEED,method='Original authored terrain and procedural polygon models. No video, no precalculated camera, no external assets. ASTRILLA mesh/G3D1 conventions inspected for compatibility; none of its illustrated panoramas used as scenery.'))
 world['gameplay']=dict(route=[dict(x=x,y=round(height(x,z),5),z=z) for x,z in [(28,126),(36,115),(45,111),(50,109),(62,101),(67,91),(77,78),(86,68),(88,65),(93,53),(96,48),(98,45),(101,43),(102,43),(123,36)]],
  collectibles=[dict(id=eid,name=name,position=[x,round(height(x,z),5)+.8,z],radius=1.4) for eid,name,x,z in [('letter_01','Une lettre au vent',45,111),('letter_02','Le courrier du hameau',67,91),('letter_03','Le reflet du lac',86,68),('letter_04','La réponse du phare',102,43)]],
  goal=dict(id='observatory',name='La porte des nuages',position=[123,round(height(123,36),5),36],radius=3.0,requires_collectibles=4))
 world['animated_models']=dict(hero=[dict(mesh='hero_'+name,kind=kind,pivot=pivot) for name,kind,pivot,_ in parts],
  windmill=dict(static_mesh='windmill_static',rotor_mesh='windmill_rotor',rotor_pivot=[0,6.4,2.4],axis='local_Z'),
  collectible_mesh='letter',note='Only rest geometry and local rotation pivots. Runtime motion derives from gameplay distance/time, not a stored animation or camera sequence.')
 write(OUT/'heightfield.json',dict(schema=1,width=81,height=81,spacing=2,origin=[0,0],heights=heights,interpolation='triangular_00_to_11'))
 write(OUT/'meshes.json',dict(schema=1,meshes=meshes));write(OUT/'scene.json',world)
 stats=dict(meshes=len(meshes),instances=len(instances),unique_vertices=sum(len(m['vertices']) for m in meshes.values()),stored_triangles=sum(len(m['faces']) for m in meshes.values()),models={n:dict(vertices=len(m['vertices']),triangles=len(m['faces'])) for n,m in meshes.items() if not n.startswith('terrain_')},max_mesh_vertices=max(len(m['vertices']) for m in meshes.values()),runtime_budget_not_measured=True)
 write(OUT/'stats.json',stats)
 print(json.dumps(stats,ensure_ascii=False))

if __name__=='__main__':main()
