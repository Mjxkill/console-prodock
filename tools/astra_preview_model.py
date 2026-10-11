"""Vectorized integer preview rasterizer. Checked against Model's scalar oracle.

Only accelerates pixel iteration; emitted packets and integer rounding retain
the independently specified V1 rules. No RTL or scene geometry is duplicated.
"""
import numpy as np

class FastPixels:
 def clear(self,flags=3,color=0x2104,z=65535,x=0,y=0,w=None,h=None):
  if w is None:w=self.width
  if h is None:h=self.height
  xy=lambda a,b:((a&65535)<<16)|(b&65535)
  self.emit(28,flags,color,z,xy(x,y),xy(w,h));l,t,r,b=self.clip
  xx0,xx1=max(l,x),min(r,x+w);yy0,yy1=max(t,y),min(b,y+h)
  if xx1<=xx0 or yy1<=yy0:return
  for flag,base,pitch,value in [(1,self.base,self.stride,color),(2,self.zbase,self.zstride,z)]:
   if flags&flag:
    a=np.ndarray((self.height,pitch//2),dtype='<u2',buffer=self.memory,offset=self.at(base));a[yy0:yy1,xx0:xx1]=value
 def copy(self,src,sw,sh,ss,sx,sy,dx,dy,w,h):
  xy=lambda a,b:((a&65535)<<16)|(b&65535)
  self.emit(29,src,xy(sw,sh),ss,xy(sx,sy),xy(dx,dy),xy(w,h));l,t,r,b=self.clip
  x0,x1=max(l,dx,dx-sx),min(r,dx+w,dx+sw-sx);y0,y1=max(t,dy,dy-sy),min(b,dy+h,dy+sh-sy)
  if x0>=x1 or y0>=y1:return
  source=np.ndarray((sh,ss//2),dtype='<u2',buffer=self.memory,offset=self.at(src));dest=np.ndarray((self.height,self.stride//2),dtype='<u2',buffer=self.memory,offset=self.at(self.base))
  dest[y0:y1,x0:x1]=source[y0-dy+sy:y1-dy+sy,x0-dx+sx:x1-dx+sx].copy()
 def triangle(self,points):
  xy=lambda a,b:((a&65535)<<16)|(b&65535)
  self.emit(27,*[xy(x,y) for x,y in points]);l,t,r,b=self.clip
  flags,alpha,solid,tint,fog=self.mat
  area=(points[1][0]-points[0][0])*(points[2][1]-points[0][1])-(points[1][1]-points[0][1])*(points[2][0]-points[0][0])
  if not area or not alpha:return
  if area<0:points=[points[0],points[2],points[1]]
  x0,x1=max(l,min(p[0] for p in points)),min(r,max(p[0] for p in points)+1)
  y0,y1=max(t,min(p[1] for p in points)),min(b,max(p[1] for p in points)+1)
  if x0>=x1 or y0>=y1:return
  y,x=np.mgrid[y0:y1,x0:x1];mask=np.ones(x.shape,dtype=bool)
  for (ax,ay),(bx,by) in zip(points,points[1:]+points[:1]):
   dx,dy=bx-ax,by-ay;e=dx*(2*y+1-2*ay)-dy*(2*x+1-2*ax);mask&=(e>0)|((e==0)&(dy<0 or (dy==0 and dx>0)))
  x=x[mask].astype(np.int64);y=y[mask].astype(np.int64)
  if not len(x):return
  def pv(k):
   o,dx,dy=self.planes.get(k,(0,0,0));return o+x*dx+y*dy
  depth=pv(3)//65536
  mem=np.frombuffer(self.memory,dtype='<u2');dst=self.at(self.base)//2+y*(self.stride//2)+x;zdst=self.at(self.zbase)//2+y*(self.zstride//2)+x
  valid=np.ones(len(x),dtype=bool)
  if flags&134:valid&=(depth>=0)&(depth<=65535)
  if flags&2:valid&=depth<mem[zdst]
  ta=256
  if flags&1:
   base,w,h,stride,argb,mu,mv,lod=self.tex;den=pv(2) if flags&16 else np.full(len(x),65536,dtype=np.int64)
   valid&=den>0;den=np.maximum(den,1);uv=[]
   for k,size,mode in [(0,w,mu),(1,h,mv)]:
    v=(pv(k)//den)//(1<<lod)
    if mode==1:v%=size
    elif mode==2:v=np.clip(v,0,size-1)
    valid&=(v>=0)&(v<size);uv.append(np.clip(v,0,size-1))
   u,v=uv;colour=mem[self.at(base)//2+v*(stride//2)+u].astype(np.int64)
   if argb:ta=np.where(colour>>12==15,256,(colour>>12)*17)
  else:colour=np.full(len(x),solid,dtype=np.int64)
  if flags&8:valid&=colour!=0
  aa=(alpha*ta+128)//256;valid&=aa!=0
  if flags&1 and self.tex[4]:
   rr,gg,bb=(colour>>8)&15,(colour>>4)&15,colour&15;channels=[(rr<<1)|(rr>>3),(gg<<2)|(gg>>2),(bb<<1)|(bb>>3)]
  else:channels=[colour>>11,(colour>>5)&63,colour&31]
  near,fc,scale=fog;f=np.clip((depth-near)*scale//65536,0,256) if flags&128 else 0
  result=np.zeros(len(x),dtype=np.int64);old=mem[dst].astype(np.int64)
  for k,(v,shift,limit) in enumerate(zip(channels,(11,5,0),(31,63,31))):
   gain=np.clip(pv(4+k)//65536,0,256) if flags&64 else tint[k];v=(v*gain+128)//256
   v=(v*(256-f)+((fc>>shift)&limit)*f+128)//256;bg=(old>>shift)&limit
   result|=np.minimum(limit,(v*aa+bg*(256 if flags&32 else 256-aa)+128)//256)<<shift
  mem[dst[valid]]=result[valid].astype(np.uint16)
  if flags&4:mem[zdst[valid]]=depth[valid].astype(np.uint16)
  self.passed+=int(valid.sum())
