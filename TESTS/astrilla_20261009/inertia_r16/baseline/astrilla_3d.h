#ifndef ASTRILLA_3D_H
#define ASTRILLA_3D_H
#include "astrilla_meshes.h"
#ifdef ASTRILLA_HOST
static unsigned as3_enemy_triangles;
#endif
static as3_vec as3_transform(as3_vec p,as3_vec f,as3_vec w,as3_vec up){
 return (as3_vec){p.x*f.x+p.y*w.x+p.z*up.x,p.x*f.y+p.y*w.y+p.z*up.y,p.x*f.z+p.y*w.z+p.z*up.z};
}
// One perspective camera for all objects. Requested screen center and size
// determine a 3D translation; rotated vertices then project independently.
// Reciprocal Z is linear in screen space and also drives perspective UVs.
static int as3_draw(gpu_v1_context *c,const as3_mesh *mesh,float x,float y,float size,
 as3_vec f,as3_vec w,as3_vec up,unsigned enemy){
 if(size<2.f||x+size*1.4f<0||x-size*1.4f>400||y+size*1.4f<0||y-size*1.4f>240)return 1;
 if(size>175.f||mesh->nv>64)return 0;
 float zc=520.f/size,xc=(x-200.f)*zc/200.f,yc=(y-120.f)*zc/200.f;
 as3_vec view[64];gpu_vertex vertex[64];
 for(unsigned i=0;i<mesh->nv;++i){view[i]=as3_transform(mesh->vertices[i],f,w,up);
  view[i].x+=xc;view[i].y+=yc;view[i].z+=zc;
  if(view[i].z<.25f)return 0;
  float q=65536.f/view[i].z;
  vertex[i]=(gpu_vertex){af_round(200.f+200.f*view[i].x/view[i].z),af_round(120.f+200.f*view[i].y/view[i].z),0,0,
   af_round(65535.f-q*.5f),af_round(q),256,256,256};
 }
 unsigned bound=0;
 for(unsigned i=0;i<mesh->nf;++i){const as3_face *face=&mesh->faces[i];
  as3_vec n=as3_transform((as3_vec){face->nx,face->ny,face->nz},f,w,up),a=view[face->a];
  if(n.x*a.x+n.y*a.y+n.z*a.z>=0)continue;
  unsigned mat=face->material;if(enemy&&mat==0)mat=1;
  unsigned texture=mat==6?ASTRILLA_ROCK3D:mat==7?ASTRILLA_BARK3D:mat==8?ASTRILLA_LEAF3D:ASTRILLA_HULL3D;
  if(texture!=bound){gpu_texture_level tex={texture,128,128,256,GPU_RGB565,GPU_TEX_REPEAT,GPU_TEX_REPEAT,0};TRY(gpu_v1_texture(c,&tex));bound=texture;}
  static const unsigned tint[9]={0xe9edf7,0x626f8b,0xe34c37,0x57dbff,0xff6741,0x449fff,0xffffff,0xffffff,0xe6ffba};
  float light=af_clamp(.28f-.30f*n.x-.48f*n.y-.73f*n.z,.20f,1.f);
  float shine=af_clamp(-.24f*n.x-.33f*n.y-.91f*n.z,0,1);shine*=shine;shine*=shine;
  if(mat<6)light=af_clamp(light+shine*.28f,0,1);
  if(mat==3||mat==4)light=1.f;
  unsigned rgb=tint[mat],r=af_round(((rgb>>16)&255)*light),g=af_round(((rgb>>8)&255)*light),b=af_round((rgb&255)*light);
  TRY(as_mat(c,0xffff,256,GPU_RASTER_TEXTURE|GPU_PERSPECTIVE|GPU_Z_TEST|GPU_Z_WRITE,r+(r==255),g+(g==255),b+(b==255)));
  gpu_vertex v[3]={vertex[face->a],vertex[face->b],vertex[face->c]};unsigned ids[3]={face->a,face->b,face->c};
  if((v[0].x<0&&v[1].x<0&&v[2].x<0)||(v[0].x>=400&&v[1].x>=400&&v[2].x>=400)||
     (v[0].y<0&&v[1].y<0&&v[2].y<0)||(v[0].y>=240&&v[1].y>=240&&v[2].y>=240))continue;
  float nx=face->nx<0?-face->nx:face->nx,ny=face->ny<0?-face->ny:face->ny,nz=face->nz<0?-face->nz:face->nz;
  for(unsigned j=0;j<3;++j){as3_vec p=mesh->vertices[ids[j]];
   float u=nx>nz&&nx>ny?p.y:p.x,vv=nz>=nx&&nz>=ny?p.y:p.z;
   v[j].u=af_round(u*58.f+64.f);v[j].v=af_round(vv*58.f+64.f);}
  // Integer projection can leave an edge-on face with <=1 pixel of area.
  // Preserve its raster coverage using centroid attributes: extrapolating
  // depth/UV across such a sliver would overflow the hardware plane format.
  int area=(v[1].x-v[0].x)*(v[2].y-v[0].y)-(v[2].x-v[0].x)*(v[1].y-v[0].y);
  if(area>=-2&&area<=2){int u=(v[0].u+v[1].u+v[2].u)/3,vv=(v[0].v+v[1].v+v[2].v)/3;
   int z=(v[0].z+v[1].z+v[2].z)/3,q=(v[0].q+v[1].q+v[2].q)/3;
   for(unsigned j=0;j<3;++j){v[j].u=u;v[j].v=vv;v[j].z=z;v[j].q=q;}}
  if(!gpu_v1_triangle(c,v)){
#ifdef ASTRILLA_HOST
   for(unsigned j=0;j<3;++j)fprintf(stderr,"mesh triangle %u vertex %u: xy=%d,%d uv=%d,%d z=%d q=%d\n",i,j,v[j].x,v[j].y,v[j].u,v[j].v,v[j].z,v[j].q);
#endif
   return 0;
  }
#ifdef ASTRILLA_HOST
  if(enemy)++as3_enemy_triangles;
#endif
 }
 return 1;
}
static int as3_ship(gpu_v1_context *c,float x,float y,float size,float heading,float pitch,float bank,unsigned enemy,float throttle,unsigned t){
 float ch=af_cos(heading),sh=af_sin(heading),cp=af_cos(pitch),sp=af_sin(pitch),cb=af_cos(bank),sb=af_sin(bank);
 as3_vec f={ch*cp,sh*cp,sp},side={-sh,ch,0},top={ch*sp,sh*sp,-cp};
 as3_vec w={side.x*cb+top.x*sb,side.y*cb+top.y*sb,side.z*cb+top.z*sb};
 as3_vec up={top.x*cb-side.x*sb,top.y*cb-side.y*sb,top.z*cb-side.z*sb};
 const as3_mesh *mesh=size<52.f?&as3_fighter:enemy?&as3_enemy:&as3_hero;
 TRY(as3_draw(c,mesh,x,y,size,f,w,up,enemy));
 if(throttle>.01f&&size>42.f){float sx=x-ch*size*.36f,sy=y-sh*size*.36f;
  TRY(as_beam(c,sx,sy,sx-ch*size*(.18f+throttle*.18f),sy-sh*size*(.18f+throttle*.18f),size*.026f,enemy?0xfb87:0x5fff,200));
  TRY(as_glow(c,sx,sy,size*.13f,enemy?0xff7744:0x55ccff,(unsigned)(160.f+18.f*af_sin(t*3.f))));}
 return 1;
}
static int as3_obstacle(gpu_v1_context *c,unsigned tree,float x,float y,float size,float yaw){
 float sn=af_sin(yaw),cs=af_cos(yaw);
 // Local Y points up in the terrain models; screen Y points down.
 return as3_draw(c,tree?&as3_tree:&as3_rock,x,y,size,(as3_vec){cs,0,sn},(as3_vec){0,-1,0},(as3_vec){sn,0,-cs},0);
}
#endif
