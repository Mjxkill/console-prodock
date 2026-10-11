#include "gpu_geometry.h"
#include <limits.h>
#define BLT ((volatile uint32_t *)0xe9001000UL)
_Static_assert(sizeof(gpu_geom_vertex)==32,"G3D1 vertex ABI");
_Static_assert(sizeof(gpu_geom_face)==32,"G3D1 face ABI");
int gpu_geom_supported(void){return BLT[0x48/4]==0x47334431U;}
gpu_geom_stats gpu_geom_read_stats(void){
 return (gpu_geom_stats){BLT[0x4c/4],BLT[0x50/4],BLT[0x54/4],BLT[0x58/4],BLT[0x5c/4],BLT[0x60/4],BLT[0x64/4]};
}
int gpu_geom_fixed(float value,int32_t *out){
 // Comparisons also reject NaN. Keep the truncated result within signed Q16.16.
 if(!out||!(value>=-32768.f&&value<=32767.998f))return 0;
 float scaled=value*65536.f;*out=(int32_t)scaled;return 1;
}
int gpu_geom_set_camera(gpu_v1_context *c,const gpu_geom_camera *v){
 if(!c||!c->emit||!v||!c->target.width||!c->target.height||c->target.width>1024||c->target.height>512||v->near_z<4096||v->far_z<=v->near_z||
  v->focal_x<65536||v->focal_y<65536||v->focal_x>0x10000000||v->focal_y>0x10000000||
  v->center_x>c->target.width||v->center_y>c->target.height||
  ((uint64_t)v->center_x<<32)/(unsigned)v->focal_x>524288||
  ((uint64_t)(c->target.width-v->center_x)<<32)/(unsigned)v->focal_x>524288||
  ((uint64_t)v->center_y<<32)/(unsigned)v->focal_y>524288||
  ((uint64_t)(c->target.height-v->center_y)<<32)/(unsigned)v->focal_y>524288)return 0;
 gpu_command q={{GPU_GEOM_CAMERA<<24,v->near_z,v->far_z,v->focal_x,v->focal_y,
  ((uint32_t)v->center_x<<16)|v->center_y,((uint32_t)c->target.width<<16)|c->target.height,0}};c->emit(&q);return 1;
}
int gpu_geom_set_transform(gpu_v1_context *c,const gpu_geom_transform *t){
 if(!c||!c->emit||!t)return 0;
 for(unsigned r=0;r<3;++r){gpu_command q={{GPU_GEOM_MATRIX<<24,r,t->values[r*4],t->values[r*4+1],t->values[r*4+2],t->values[r*4+3],0,0}};c->emit(&q);}return 1;
}
int gpu_geom_set_light(gpu_v1_context *c,const gpu_geom_light *l){
 if(!c||!c->emit||!l||l->ambient>256||l->diffuse>256)return 0;
 gpu_command q={{GPU_GEOM_LIGHT<<24,((uint32_t)(uint16_t)l->x<<16)|(uint16_t)l->y,(uint16_t)l->z,
  (uint32_t)l->ambient|((uint32_t)l->diffuse<<16),0,0,0,0}};c->emit(&q);return 1;
}
static int mesh_valid(const gpu_geom_mesh *m){
 return m&&!(m->vertices&31)&&!(m->faces&31)&&m->vertex_count&&m->vertex_count<=256&&m->face_count&&
  (uint64_t)m->vertices+(uint64_t)m->vertex_count*32<=0x20000000ULL&&
  (uint64_t)m->faces+(uint64_t)m->face_count*32<=0x20000000ULL;
}
int gpu_geom_draw(gpu_v1_context *c,const gpu_geom_mesh *m,unsigned cull){
 if(!c||!c->emit||!mesh_valid(m)||cull>1||(c->flags&GPU_V1_GOURAUD))return 0;
 gpu_command q={{GPU_GEOM_DRAW<<24,m->vertices,m->faces,((uint32_t)m->vertex_count<<16)|m->face_count,cull,0,0,0}};c->emit(&q);return 1;
}
int gpu_geom_instance(gpu_v1_context *c,const gpu_geom_mesh *m,const gpu_geom_transform *t,const gpu_geom_light *l,unsigned cull){
 // Validate the whole request before emitting its first configuration command.
 if(!c||!c->emit||!mesh_valid(m)||!t||!l||l->ambient>256||l->diffuse>256||cull>1||(c->flags&GPU_V1_GOURAUD))return 0;
 return gpu_geom_set_transform(c,t)&&gpu_geom_set_light(c,l)&&gpu_geom_draw(c,m,cull);
}
int gpu_geom_billboard_transform(gpu_geom_transform *out,int32_t x,int32_t y,int32_t z,int32_t w,int32_t h,int16_t sn,int16_t cs){
 if(!out||w<=0||h<=0)return 0;
 int64_t a=(int64_t)cs*w/32768,b=-(int64_t)sn*h/32768,c=(int64_t)sn*w/32768,d=(int64_t)cs*h/32768;
 *out=(gpu_geom_transform){{(int32_t)a,(int32_t)b,0,x,(int32_t)c,(int32_t)d,0,y,0,0,65536,z}};return 1;
}
