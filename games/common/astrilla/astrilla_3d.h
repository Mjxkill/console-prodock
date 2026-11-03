#ifndef ASTRILLA_3D_H
#define ASTRILLA_3D_H
#include "astrilla_meshes.h"
#ifdef ASTRILLA_HW_GEOMETRY
#include "astrilla_geometry.h"
#endif
#ifdef ASTRILLA_HOST
static unsigned as3_enemy_triangles;
#endif
static as3_vec as3_transform(as3_vec p,as3_vec f,as3_vec w,as3_vec up){
 return (as3_vec){p.x*f.x+p.y*w.x+p.z*up.x,p.x*f.y+p.y*w.y+p.z*up.y,p.x*f.z+p.y*w.z+p.z*up.z};
}
// All objects share camera-space positions and physical scales. Their depth
// remains comparable even when ships and obstacles have different dimensions.
// Reciprocal Z is linear in screen space and also drives perspective UVs.
static int as3_draw_at(gpu_v1_context *c,const as3_mesh *mesh,as3_vec center,float scale,
 as3_vec f,as3_vec w,as3_vec up,unsigned enemy){
#ifdef ASTRILLA_HW_GEOMETRY
 (void)enemy;
 // ASTRILLA shares a 1/8-unit near plane across all its mesh instances,
 // limiting steep depth gradients on close portals without mixed Z scales.
 return as3_hw_draw_near(c,mesh,center,scale,f,w,up,8192);
#else
 if(center.z<=0)return 1;
 float size=520.f*scale/center.z,x=200.f+200.f*center.x/center.z,y=120.f+200.f*center.y/center.z;
 if(size<2.f||x+size*1.4f<0||x-size*1.4f>400||y+size*1.4f<0||y-size*1.4f>240)return 1;
 if(size>175.f||mesh->nv>64)return 0;
 as3_vec view[64];gpu_vertex vertex[64];
 for(unsigned i=0;i<mesh->nv;++i){view[i]=as3_transform(mesh->vertices[i],f,w,up);
  view[i].x=view[i].x*scale+center.x;view[i].y=view[i].y*scale+center.y;view[i].z=view[i].z*scale+center.z;
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
#endif
}
static float as3_sqrt(float x){
#ifdef ASTRILLA_HOST
 return __builtin_sqrtf(x);
#else
 float r;__asm__("fsqrt.s %0, %1":"=f"(r):"f"(x));return r;
#endif
}
// Camera X right, Y down, Z away. Local X is the nose, Y the wings,
// Z the upper hull. A level wing follows the horizon, not screen heading.
static void as3_basis(float heading,float pitch,float bank,as3_vec *f,as3_vec *w,as3_vec *up){
 float ch=af_cos(heading),sh=af_sin(heading),cp=af_cos(pitch),sp=af_sin(pitch),cb=af_cos(bank),sb=af_sin(bank);
 *f=(as3_vec){ch*cp,sh*cp,sp};float norm=as3_sqrt(f->x*f->x+f->y*f->y+f->z*f->z);
 f->x/=norm;f->y/=norm;f->z/=norm;
 float horizontal=as3_sqrt(f->x*f->x+f->z*f->z);
 as3_vec side=horizontal>.0001f?(as3_vec){-f->z/horizontal,0,f->x/horizontal}:(as3_vec){1,0,0};
 as3_vec top={f->y*side.z,f->z*side.x-f->x*side.z,-f->y*side.x};
 norm=as3_sqrt(cb*cb+sb*sb);cb/=norm;sb/=norm;
 *w=(as3_vec){side.x*cb+top.x*sb,side.y*cb+top.y*sb,side.z*cb+top.z*sb};
 *up=(as3_vec){top.x*cb-side.x*sb,top.y*cb-side.y*sb,top.z*cb-side.z*sb};
}
static int as3_ship_at(gpu_v1_context *c,as3_vec center,float scale,float heading,float pitch,float bank,unsigned enemy,float throttle,unsigned t){
 if(center.z<=0)return 1;
 float size=520.f*scale/center.z;
 as3_vec f,w,up;as3_basis(heading,pitch,bank,&f,&w,&up);
 const as3_mesh *mesh=size<38.f?&as3_fighter:enemy?&as3_enemy:&as3_hero;
 TRY(as3_draw_at(c,mesh,center,scale,f,w,up,enemy));
 if(throttle>.01f&&size>26.f){
  float tail=(1.2f+throttle*.6f)*scale,engine=.96f*scale;
  float sx=200.f+200.f*(center.x-f.x*engine)/(center.z-f.z*engine),sy=120.f+200.f*(center.y-f.y*engine)/(center.z-f.z*engine);
  float ex=200.f+200.f*(center.x-f.x*tail)/(center.z-f.z*tail),ey=120.f+200.f*(center.y-f.y*tail)/(center.z-f.z*tail);
  TRY(as_beam(c,sx,sy,ex,ey,size*.026f,enemy?0xfb87:0x5fff,200));
  TRY(as_glow(c,sx,sy,size*.13f,enemy?0xff7744:0x55ccff,(unsigned)(160.f+18.f*af_sin(t*3.f))));}
 return 1;
}
static int as3_ship(gpu_v1_context *c,float x,float y,float size,float heading,float pitch,float bank,unsigned enemy,float throttle,unsigned t){
 float z=520.f/size;return as3_ship_at(c,(as3_vec){(x-200.f)*z/200.f,(y-120.f)*z/200.f,z},1,heading,pitch,bank,enemy,throttle,t);
}
static int as3_obstacle_at(gpu_v1_context *c,unsigned tree,as3_vec center,float scale,float yaw){
 float sn=af_sin(yaw),cs=af_cos(yaw);
 return as3_draw_at(c,tree?&as3_tree:&as3_rock,center,scale,(as3_vec){cs,0,sn},(as3_vec){0,-1,0},(as3_vec){sn,0,-cs},0);
}
static int as3_obstacle(gpu_v1_context *c,unsigned tree,float x,float y,float size,float yaw){
 float sn=af_sin(yaw),cs=af_cos(yaw);
 // Local Y points up in the terrain models; screen Y points down.
 float z=520.f/size;return as3_draw_at(c,tree?&as3_tree:&as3_rock,(as3_vec){(x-200.f)*z/200.f,(y-120.f)*z/200.f,z},1,(as3_vec){cs,0,sn},(as3_vec){0,-1,0},(as3_vec){sn,0,-cs},0);
}
#endif
