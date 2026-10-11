"""Independent integer specification of G3D1 geometry (no RTL/C implementation import)."""
from dataclasses import dataclass
import struct
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'TESTS'))
from test_gpu_v1 import Model,xy

def signed(n,bits=32):
 n &= (1<<bits)-1
 return n-(1<<bits) if n>>(bits-1) else n

def trunc(a,b):return (abs(a)//abs(b))*(-1 if (a<0) != (b<0) else 1)
def pack(*words):return [v&0xffffffff for v in words]+[0]*(8-len(words))
def q16(v):return round(v*65536)

def clip_intersection(a,da,b,db):
 # Canonical inside-to-outside interpolation makes a shared edge independent
 # of triangle winding, including fixed-point rounding of positions and UVs.
 if not (da and db and (da<0)!=(db<0)):raise ValueError('Edge must cross the plane')
 if da<0:a,b,da,db=b,a,db,da
 t=(da<<16)//(da-db)
 return tuple(aa+(((bb-aa)*t)>>16) for aa,bb in zip(a,b))

@dataclass
class Camera:
 near:int=q16(.25)
 far:int=q16(80)
 fx:int=q16(80)
 fy:int=q16(80)
 cx:int=80
 cy:int=50
 width:int=160
 height:int=100
 def words(self):return pack(32<<24,self.near,self.far,self.fx,self.fy,xy(self.cx,self.cy),xy(self.width,self.height))

class Geometry:
 def __init__(self,pixels):
  self.p=pixels;self.input=[];self.matrix=[65536,0,0,0,0,65536,0,0,0,0,65536,0]
  self.camera=Camera();self.light=(0,0,0,256,0);self.material=pack(25<<24,6,256,65535,256|(256<<9)|(256<<18))
  self.vertices=self.triangles=self.culled=self.clipped=self.slivers=0
  self.approximations=[]
 def command(self,c):
  c=pack(*c) if len(c)<8 else c;self.input+=c;op=c[0]>>24
  if op==31:self.matrix[c[1]*4:c[1]*4+4]=[signed(v) for v in c[2:6]]
  elif op==32:self.camera=Camera(*c[1:5],c[5]>>16,c[5]&65535,c[6]>>16,c[6]&65535)
  elif op==33:self.light=(signed(c[1]>>16,16),signed(c[1],16),signed(c[2],16),c[3]&65535,c[3]>>16)
  elif op==34:self.draw(c[1],c[2],c[3]>>16,c[3]&65535,c[4])
  else:
   self.p.apply(c)
   if op==25:self.material=c
 def upload(self,address,raw):
  i=self.p.at(address);self.p.memory[i:i+len(raw)]=raw
 def draw(self,vb,fb,nv,nf,cull):
  mat=self.matrix;points=[];cam=self.camera
  for i in range(nv):
   p=struct.unpack_from('<3i',self.p.memory,self.p.at(vb+i*32))
   points.append(tuple(sum((mat[r*4+k]*p[k])>>16 for k in range(3))+mat[r*4+3] for r in range(3)))
  self.vertices+=nv
  ratios=(cam.cx*65536*65536//cam.fx,(cam.width-cam.cx)*65536*65536//cam.fx,cam.cy*65536*65536//cam.fy,(cam.height-cam.cy)*65536*65536//cam.fy)
  def distance(p,plane):
   x,y,z=p[:3]
   return z-cam.near if plane==0 else cam.far-z if plane==1 else ((z*ratios[plane-2])>>16)+(x if plane==2 else -x if plane==3 else y if plane==4 else -y)
  for i in range(nf):
   f=struct.unpack_from('<8I',self.p.memory,self.p.at(fb+i*32));flags=f[0]>>24
   p=[(*points[(f[0]>>(k*8))&255],signed(f[k+1]>>16,16)<<16,signed(f[k+1],16)<<16) for k in range(3)]
   normal=signed(f[4]>>16,16),signed(f[4],16),signed(f[5],16)
   lx,ly,lz,ambient,diffuse=self.light
   intensity=256 if flags&1 else min(256,ambient+max(0,((sum(a*b for a,b in zip(normal,(lx,ly,lz)))>>15)*diffuse)>>15))
   gains=[((f[6]>>(9*k)&511)*intensity+128)>>8 for k in range(3)]
   for plane in range(6):
    out=[];a=p[-1];da=distance(a,plane)
    for b in p:
     db=distance(b,plane)
     if da and db and (da<0)!=(db<0):
      out.append(clip_intersection(a,da,b,db));self.clipped+=1
     if db>=0:out.append(b)
     a,da=b,db
    p=out
    if len(p)<3:break
   if len(p)<3:self.culled+=1;continue
   projected=[]
   for x,y,z,u,v in p:
    q=(1<<32)//max(z,cam.near)
    sx=min(cam.width,max(0,(((x*q)>>16)*cam.fx>>32)+cam.cx));sy=min(cam.height,max(0,(((y*q)>>16)*cam.fy>>32)+cam.cy))
    depth=max(0,((65536-((cam.near*q)>>16))*65534)>>16)
    projected.append((sx,sy,u>>16,v>>16,depth,q))
   for fan in range(1,len(p)-1):
    v=[projected[0],projected[fan],projected[fan+1]]
    area=(v[1][0]-v[0][0])*(v[2][1]-v[0][1])-(v[2][0]-v[0][0])*(v[1][1]-v[0][1])
    if not area or (cull and not flags&2 and area>=0):self.culled+=1;continue
    material=list(self.material);material[4]=sum(((((material[4]>>(9*k))&511)*gains[k]+128)>>8)<<(9*k) for k in range(3));self.p.apply(material)
    mf=material[1];mask=(3 if mf&1 else 0)|(4 if mf&16 else 0)|(8 if mf&134 else 0)
    for k in range(4):
     if not mask>>k&1:continue
     values=[(a[2+k]*(a[5] if mf&16 else 65536)) if k<2 else a[5] if k==2 else a[4]*65536 for a in v]
     dx=trunc((values[1]-values[0])*(v[2][1]-v[0][1])-(values[2]-values[0])*(v[1][1]-v[0][1]),area)
     dy=trunc((v[1][0]-v[0][0])*(values[2]-values[0])-(v[2][0]-v[0][0])*(values[1]-values[0]),area)
     if not(-(1<<31)<=dx<(1<<31) and -(1<<31)<=dy<(1<<31)):
      self.approximations.append(dict(attribute=k,points=[(a[0],a[1]) for a in v],dx=dx,dy=dy))
      dx=dy=0;values[0]=trunc(sum(values),3);self.slivers+=1
     origin=values[0]-dx*v[0][0]-dy*v[0][1]+trunc(dx+dy,2)
     self.p.plane(k,origin,dx,dy)
    self.p.triangle([(a[0],a[1]) for a in v]);self.triangles+=1
  self.p.apply(self.material)

def mesh_bytes(points,faces):
 vertices=b''.join(struct.pack('<3i5I',*[q16(v) for v in p],0,0,0,0,0) for p in points)
 triangles=bytearray()
 for ids,uv,normal,color,flags in faces:
  n=[max(-32768,min(32767,round(v*32767))) for v in normal]
  triangles+=struct.pack('<8I',ids[0]|ids[1]<<8|ids[2]<<16|flags<<24,*[xy(u,v) for u,v in uv],xy(n[0],n[1]),n[2]&65535,color[0]|color[1]<<9|color[2]<<18,0)
 return vertices,bytes(triangles)
