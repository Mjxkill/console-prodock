#ifndef WORLD3D_SCENE_H
#define WORLD3D_SCENE_H
#ifndef ASTRILLA_HW_GEOMETRY
#define ASTRILLA_HW_GEOMETRY 1
#endif
#include "astrilla_scene.h"
#define WORLD_EXTRA_BASE (AS3_HW_BASE+AS3_HW_BYTES)
#define WORLD_EXTRA_BYTES 1024U
// Mutable game state. World coordinates: X right, Y down, Z forward.
// Angles are turns/256. No frame/camera image cache is used by this scene.
typedef struct {float x,y,z,yaw,pitch,actor_x,actor_y,actor_z,actor_heading;} world3d_state;
typedef struct {as3_vec position,right,down,forward;} world3d_camera;
typedef struct {unsigned objects,billboards;} world3d_info;
static gpu_geom_mesh world_floor,world_quad;
static as3_vec world_vec(world3d_camera c,as3_vec v){return (as3_vec){v.x*c.right.x+v.y*c.right.y+v.z*c.right.z,v.x*c.down.x+v.y*c.down.y+v.z*c.down.z,v.x*c.forward.x+v.y*c.forward.y+v.z*c.forward.z};}
static as3_vec world_point(world3d_camera c,as3_vec v){return world_vec(c,(as3_vec){v.x-c.position.x,v.y-c.position.y,v.z-c.position.z});}
static world3d_camera world_camera(world3d_state s){
 float cy=af_cos(s.yaw),sy=af_sin(s.yaw),cp=af_cos(s.pitch),sp=af_sin(s.pitch);
 return (world3d_camera){{s.x,s.y,s.z},{cy,0,-sy},{-sy*sp,cp,-cy*sp},{sy*cp,sp,cy*cp}};
}
static world3d_state world_auto(unsigned frame){
 float t=(float)(frame%6600)/55.f,a=t*2.1f,r=14.f+2.f*af_sin(t*3.f);
 return (world3d_state){af_sin(a)*r,-4.f+1.5f*af_sin(t*4.f),14.f-af_cos(a)*r,-a,11.f+3.f*af_sin(t*2.f),0,-.7f,14,64.f};
}
static int world_state_valid(const world3d_state *s){
 const float v[9]={s->x,s->y,s->z,s->yaw,s->pitch,s->actor_x,s->actor_y,s->actor_z,s->actor_heading};
 for(unsigned i=0;i<9;++i)if(!(v[i]>=-512.f&&v[i]<=512.f))return 0;
 return s->pitch>=-56.f&&s->pitch<=56.f;
}
static int world_prepare(uint8_t *models,uint8_t *extra){
 if(!as3_hw_prepare(models))return 0;
 memset(extra,0,WORLD_EXTRA_BYTES);
 const int32_t points[8][3]={{-65536,0,-65536},{65536,0,-65536},{65536,0,65536},{-65536,0,65536},
  {-65536,-65536,0},{-65536,65536,0},{65536,65536,0},{65536,-65536,0}};
 for(unsigned i=0;i<8;++i){gpu_geom_vertex *v=(gpu_geom_vertex *)(extra+i*32);v->x=points[i][0];v->y=points[i][1];v->z=points[i][2];}
 for(unsigned i=0;i<4;++i){gpu_geom_face *f=(gpu_geom_face *)(extra+256+i*32);unsigned quad=i/2,j=i&1,span=quad?63:1023;
  f->words[0]=(j?0|(2<<8)|(3<<16):0|(1<<8)|(2<<16))|(quad?1UL<<24:0);
  f->words[1]=0;f->words[2]=j?(span<<16)|span:quad?span:span<<16;f->words[3]=j?(quad?span<<16:span):(span<<16)|span;
  f->words[4]=quad?0:(uint16_t)-32767;f->words[5]=quad?(uint16_t)-32767:0;
  f->words[6]=256|(256<<9)|(256<<18);
 }
 world_floor=(gpu_geom_mesh){WORLD_EXTRA_BASE,WORLD_EXTRA_BASE+256,4,2};
 world_quad=(gpu_geom_mesh){WORLD_EXTRA_BASE+128,WORLD_EXTRA_BASE+320,4,2};return 1;
}
static int world_transform(gpu_geom_transform *out,as3_vec center,as3_vec x,as3_vec y,as3_vec z){
 float v[12]={x.x,y.x,z.x,center.x,x.y,y.y,z.y,center.y,x.z,y.z,z.z,center.z};
 for(unsigned i=0;i<12;++i)if(!gpu_geom_fixed(v[i],&out->values[i]))return 0;
 return 1;
}
static void world_ship_basis(as3_vec direction,float bank,as3_vec *f,as3_vec *w,as3_vec *up){
 float norm=as3_sqrt(direction.x*direction.x+direction.y*direction.y+direction.z*direction.z);
 *f=(as3_vec){direction.x/norm,direction.y/norm,direction.z/norm};
 float flat=as3_sqrt(f->x*f->x+f->z*f->z);
 as3_vec side=flat>.0001f?(as3_vec){f->z/flat,0,-f->x/flat}:(as3_vec){1,0,0};
 as3_vec top={-side.z*f->y,side.z*f->x-side.x*f->z,side.x*f->y};
 float cb=af_cos(bank),sb=af_sin(bank);
 *w=(as3_vec){side.x*cb+top.x*sb,side.y*cb+top.y*sb,side.z*cb+top.z*sb};
 *up=(as3_vec){top.x*cb-side.x*sb,top.y*cb-side.y*sb,top.z*cb-side.z*sb};
}
static int world_render(gpu_v1_context *c,unsigned frame,unsigned page,const world3d_state *input,world3d_info *info){
 if(!world_state_valid(input)||page>1)return 0;
 world3d_camera camera=world_camera(*input);world3d_info stats={0};
 gpu_target target={GPU_PAGE_ADDR(page),GPU_PAGE_ADDR(2),400,240,800,800};
 if(!gpu_v1_target(c,&target)||!gpu_v1_scissor(c,0,0,400,240)||!gpu_v1_clear(c,3,0x0846,65535,0,0,400,240))return 0;
 const gpu_geom_camera projection={16384,96*65536,200*65536,200*65536,200,120};
 const gpu_geom_light light={0,-32767,0,100,156};
 if(!gpu_geom_set_camera(c,&projection))return 0;
 gpu_geom_transform floor;
 if(!world_transform(&floor,world_point(camera,(as3_vec){0,3,14}),world_vec(camera,(as3_vec){24,0,0}),world_vec(camera,(as3_vec){0,24,0}),world_vec(camera,(as3_vec){0,0,24})))return 0;
 gpu_texture_level texture={ASTRILLA_LEAF3D,128,128,256,GPU_RGB565,GPU_TEX_REPEAT,GPU_TEX_REPEAT,0};
 gpu_material material={GPU_RASTER_TEXTURE|GPU_PERSPECTIVE|GPU_Z_TEST|GPU_Z_WRITE,256,65535,105,160,125,0,0,0};
 if(!gpu_v1_texture(c,&texture)||!gpu_v1_material(c,&material)||!gpu_geom_instance(c,&world_floor,&floor,&light,1))return 0;
  ++stats.objects;
 for(unsigned i=0;i<12;++i){float a=(float)i*256.f/12.f,r=i&1?10.f:18.f,scale=i&1?1.4f:2.2f;
  as3_vec pos={af_sin(a)*r,3.f,14.f+af_cos(a)*r};
  as3_vec x=world_vec(camera,(as3_vec){1,0,0}),y=world_vec(camera,(as3_vec){0,-1,0}),z=world_vec(camera,(as3_vec){0,0,-1});
  if(!as3_hw_draw(c,i%3?&as3_tree:&as3_rock,world_point(camera,pos),scale,x,y,z))return 0;
  ++stats.objects;
 }
 float sec=(float)(frame%6600)/55.f;
 for(unsigned i=0;i<4;++i){float a=input->actor_heading+sec*(i?6.f:3.f)+i*64.f,bank=14.f*af_sin(sec*9.f+i*57.f);
  as3_vec direction=i?(as3_vec){3.f*(4.f+i)*af_cos(sec*3.f+i*83.f),8.f*af_cos(sec*8.f+i*47.f),-4.f*(5.f+i)*af_sin(sec*4.f+i*83.f)}:(as3_vec){af_sin(a),0,af_cos(a)};
  as3_vec f,w,up;world_ship_basis(direction,bank,&f,&w,&up);
  as3_vec pos=i?(as3_vec){af_sin(sec*3.f+i*83.f)*(4.f+i),-1.f+af_sin(sec*8.f+i*47.f),14.f+af_cos(sec*4.f+i*83.f)*(5.f+i)}:(as3_vec){input->actor_x,input->actor_y,input->actor_z};
  if(!as3_hw_draw(c,i==1?&as3_enemy:&as3_hero,world_point(camera,pos),i?1.f:1.6f,world_vec(camera,f),world_vec(camera,w),world_vec(camera,up)))return 0;
  ++stats.objects;
 }
 // Camera-facing, rotating translucent sprites, correctly tested against opaque Z.
 // Alpha sprites are stable-sorted back to front; each uses the shared unit mesh.
 as3_vec particles[24];unsigned order[24];
 for(unsigned i=0;i<24;++i){float a=i*37.f+sec*3.f;
  particles[i]=world_point(camera,(as3_vec){af_sin(a)*(5.f+(i%5)),1.f-3.f*af_sin(sec*5.f+i*53.f),14.f+af_cos(a)*(5.f+(i%5))});order[i]=i;
  for(unsigned j=i;j&&particles[order[j]].z>particles[order[j-1]].z;--j){unsigned temp=order[j];order[j]=order[j-1];order[j-1]=temp;}
 }
 texture=(gpu_texture_level){ASTRILLA_GLOW,64,64,128,GPU_ARGB4444,GPU_TEX_CLAMP,GPU_TEX_CLAMP,0};
 if(!gpu_v1_texture(c,&texture)||!gpu_geom_set_camera(c,&projection))return 0;
 const gpu_geom_light unlit={0,0,0,256,0};
 for(unsigned j=0;j<24;++j){unsigned i=order[j];as3_vec p=particles[i];gpu_geom_transform transform;int32_t x,y,z,size;
  if(!gpu_geom_fixed(p.x,&x)||!gpu_geom_fixed(p.y,&y)||!gpu_geom_fixed(p.z,&z)||!gpu_geom_fixed(.35f+.18f*af_sin(sec*8.f+i*31.f),&size))return 0;
  if(!gpu_geom_billboard_transform(&transform,x,y,z,size,size,(int16_t)af_round(af_sin(sec*11.f+i*23.f)*32767.f),(int16_t)af_round(af_cos(sec*11.f+i*23.f)*32767.f)))return 0;
  material=(gpu_material){GPU_RASTER_TEXTURE|GPU_PERSPECTIVE|GPU_Z_TEST,210,65535,i&1?256:100,i&1?160:240,i&1?70:256,0,0,0};
  if(!gpu_v1_material(c,&material)||!gpu_geom_instance(c,&world_quad,&transform,&unlit,0))return 0;
  ++stats.billboards;
 }
 *info=stats;return 1;
}
#endif
