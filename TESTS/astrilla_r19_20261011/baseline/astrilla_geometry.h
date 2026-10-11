// ASTRILLA adapter for the reusable G3D1 hardware pipeline.
#ifndef ASTRILLA_GEOMETRY_H
#define ASTRILLA_GEOMETRY_H
#include "gpu_geometry.h"
#define AS3_HW_BASE 0x06000000UL
#define AS3_HW_BYTES 32768U
static gpu_geom_mesh as3_hw_mesh[5][3];
static unsigned as3_hw_groups[5];
static const as3_mesh *const as3_hw_sources[5]={&as3_hero,&as3_enemy,&as3_fighter,&as3_rock,&as3_tree};
static const uint32_t as3_hw_tints[9]={0xe9edf7,0x626f8b,0xe34c37,0x57dbff,0xff6741,0x449fff,0xffffff,0xffffff,0xe6ffba};
static unsigned as3_hw_group(unsigned material){return material<6?0:material==6?0:material-7;}
static int as3_hw_prepare(uint8_t *storage){
 unsigned offset=0;memset(storage,0,AS3_HW_BYTES);
 for(unsigned n=0;n<5;++n){const as3_mesh *m=as3_hw_sources[n];unsigned vb=offset;
  if(offset+m->nv*32>AS3_HW_BYTES)return 0;
  for(unsigned i=0;i<m->nv;++i){gpu_geom_vertex *v=(gpu_geom_vertex *)(storage+offset);
   if(!gpu_geom_fixed(m->vertices[i].x,&v->x)||!gpu_geom_fixed(m->vertices[i].y,&v->y)||!gpu_geom_fixed(m->vertices[i].z,&v->z))return 0;
   offset+=32;}
  unsigned groups=n==4?2:1;as3_hw_groups[n]=groups;
  for(unsigned g=0;g<groups;++g){unsigned fb=offset,count=0;
   for(unsigned i=0;i<m->nf;++i){const as3_face *f=&m->faces[i];if(as3_hw_group(f->material)!=g)continue;
    if(offset+32>AS3_HW_BYTES)return 0;
    gpu_geom_face *out=(gpu_geom_face *)(storage+offset);unsigned ids[3]={f->a,f->b,f->c};
    out->words[0]=f->a|((uint32_t)f->b<<8)|((uint32_t)f->c<<16)|((f->material==3||f->material==4)?1UL<<24:0);
    float nx=f->nx<0?-f->nx:f->nx,ny=f->ny<0?-f->ny:f->ny,nz=f->nz<0?-f->nz:f->nz;
    for(unsigned j=0;j<3;++j){as3_vec p=m->vertices[ids[j]];float u=nx>nz&&nx>ny?p.y:p.x,v=nz>=nx&&nz>=ny?p.y:p.z;
     out->words[1+j]=((uint32_t)(uint16_t)af_round(u*58.f+64.f)<<16)|(uint16_t)af_round(v*58.f+64.f);}
    out->words[4]=((uint32_t)(uint16_t)af_round(f->nx*32767.f)<<16)|(uint16_t)af_round(f->ny*32767.f);
    out->words[5]=(uint16_t)af_round(f->nz*32767.f);
    unsigned rgb=as3_hw_tints[f->material],r=(rgb>>16)&255,green=(rgb>>8)&255,b=rgb&255;
    out->words[6]=(r+(r==255))|((green+(green==255))<<9)|((b+(b==255))<<18);
    ++count;offset+=32;
   }
   as3_hw_mesh[n][g]=(gpu_geom_mesh){AS3_HW_BASE+vb,AS3_HW_BASE+fb,m->nv,count};
  }
 }
 return 1;
}
static int as3_hw_draw(gpu_v1_context *c,const as3_mesh *mesh,as3_vec center,float scale,as3_vec f,as3_vec w,as3_vec up){
 unsigned n;for(n=0;n<5&&as3_hw_sources[n]!=mesh;++n){}if(n==5)return 0;
 gpu_geom_transform t;float a[12]={f.x*scale,w.x*scale,up.x*scale,center.x,f.y*scale,w.y*scale,up.y*scale,center.y,f.z*scale,w.z*scale,up.z*scale,center.z};
 for(unsigned i=0;i<12;++i)if(!gpu_geom_fixed(a[i],&t.values[i]))return 0;
 const gpu_geom_camera camera={16384,0x7fff0000,200*65536,200*65536,200,120};
 gpu_geom_light light={(int16_t)af_round((-f.x*.30f-f.y*.48f-f.z*.73f)*32767.f),
  (int16_t)af_round((-w.x*.30f-w.y*.48f-w.z*.73f)*32767.f),
  (int16_t)af_round((-up.x*.30f-up.y*.48f-up.z*.73f)*32767.f),72,256};
 if(!gpu_geom_set_camera(c,&camera)||!gpu_geom_set_transform(c,&t)||!gpu_geom_set_light(c,&light))return 0;
 for(unsigned g=0;g<as3_hw_groups[n];++g){unsigned texture=n<3?ASTRILLA_HULL3D:n==3?ASTRILLA_ROCK3D:g?ASTRILLA_LEAF3D:ASTRILLA_BARK3D;
  gpu_texture_level tex={texture,128,128,256,GPU_RGB565,GPU_TEX_REPEAT,GPU_TEX_REPEAT,0};
  if(!gpu_v1_texture(c,&tex)||!as_mat(c,65535,256,GPU_RASTER_TEXTURE|GPU_PERSPECTIVE|GPU_Z_TEST|GPU_Z_WRITE,256,256,256)||!gpu_geom_draw(c,&as3_hw_mesh[n][g],1))return 0;
 }
 return 1;
}
#endif
