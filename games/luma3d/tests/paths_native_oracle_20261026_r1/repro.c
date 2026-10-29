#include "luma3d_render.h"
#include "luma3d_progress.h"
#include "luma3d_amber.h"
#include <assert.h>
#include <string.h>
static const uint32_t ids[]={0x4c455431,0x4c455432,0x4c455433,0x4c455434};
static const L3ProgressSchema schema={0x56414c31,4,4,ids};
static void capture(L3Game *g,const char *prefix){L3Render r;assert(l3_render_open(&r,1,0));char p[1024];snprintf(p,sizeof(p),"%s.commands",prefix);r.capture=fopen(p,"wb");assert(r.capture);for(unsigned i=0;i<3;i++)assert(l3_render_frame(&r,g));assert(!fclose(r.capture));r.capture=NULL;assert(l3_render_dump(&r,prefix));assert(l3_render_close(&r));}
int main(int argc,char **argv){assert(argc==3);L3World w;L3Game a,b; l3_world_init(&w);assert(l3_game_init(&a,&w,0));l3_amber_bind(&a,1);assert(l3_game_init(&b,&a.world,0));assert(l3_game_init(&a,&w,0));assert(l3_progress_read(argv[1],&a,&schema)==L3_PROGRESS_OK);assert(l3_progress_read(argv[1],&b,&schema)==L3_PROGRESS_OK);printf("CAMERAS_EQUAL %d\n",!memcmp(&a.camera,&b.camera,sizeof(a.camera)));const float *fa=(const float *)&a.camera,*fb=(const float *)&b.camera;for(unsigned i=0;i<sizeof(a.camera)/sizeof(float);i++)printf("CAMERA %u %a %a\n",i,(double)fa[i],(double)fb[i]);char prefix[1024];snprintf(prefix,sizeof(prefix),"%s_valley",argv[2]);capture(&a,prefix);snprintf(prefix,sizeof(prefix),"%s_amber",argv[2]);capture(&b,prefix);return 0;}
