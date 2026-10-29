#define _POSIX_C_SOURCE 200809L
/* Diagnostic only. Same frozen game/renderer; the adviser supplies legal
 * inputs. Fixed fixtures and accelerated simulation are explicitly labelled. */
#include "luma3d_render.h"
#include "luma3d_progress.h"
#include "luma3d_activities.h"
#include <assert.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static const uint32_t ids[]={0x4c455431,0x4c455432,0x4c455433,0x4c455434};
static const L3ProgressSchema schema={0x56414c31,4,4,ids};
static int host,mode,opened; /* 1=fixtures, 2=physical input replay, 3=fixture */
static const char *directory,*save_path;
static L3Render renderer;
static unsigned simulated_steps,replay_frames,reloads;
static volatile sig_atomic_t interrupted;
static void on_signal(int n){interrupted=n;}
static unsigned checksum(const void *data,size_t bytes){const unsigned char *p=data;unsigned c=~0u;while(bytes--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^(0xedb88320u&-(c&1));}return ~c;}
static double seconds(void){struct timespec t;assert(!clock_gettime(CLOCK_MONOTONIC,&t));return t.tv_sec+t.tv_nsec*1e-9;}
static void cancel(void){if(interrupted){if(opened)l3_render_close(&renderer);exit(128+interrupted);}}
static void draw(const L3Game *g){
 cancel();if(!opened){assert(l3_render_open(&renderer,host,0));opened=1;}
 assert(l3_render_frame(&renderer,g));replay_frames++;
}
static void op1_step(L3Game *g,const L3Input *in,float dt){
 cancel();l3_game_step(g,in,dt);simulated_steps++;
 /* The initial historical auto route is simulated without rendering. The
  * new manually driven route is sampled at 5 rendered frames/simulation s.
  * This is a correctness replay, never a real-time FPS benchmark. */
 if(mode==2&&g->story.region&&!g->autopilot&&!(simulated_steps%12))draw(g);
}
static void op1_capture(const L3Game *g,const char *name){
 if(mode==1){
  char prefix[1024],path[1100];snprintf(prefix,sizeof(prefix),"%s/%s",directory,name);
  snprintf(path,sizeof(path),"%s.save",prefix);assert(l3_progress_write(path,g,&schema)==L3_PROGRESS_OK);
  L3World fresh;L3Game restored;l3_world_init(&fresh);assert(l3_game_init(&restored,&fresh,0));assert(l3_progress_read(path,&restored,&schema)==L3_PROGRESS_OK);
  L3Render r;assert(l3_render_open(&r,1,0));snprintf(path,sizeof(path),"%s.commands",prefix);
  r.capture=fopen(path,"wb");assert(r.capture);
  for(unsigned i=0;i<3;i++)assert(l3_render_frame(&r,&restored));
  assert(!fclose(r.capture));r.capture=NULL;assert(l3_render_dump(&r,prefix));assert(l3_render_close(&r));
 }else if(mode==2){draw(g);printf("OP1_CHECKPOINT name=%s active=%u won=%u region=%u x=%.3f y=%.3f z=%.3f\n",name,g->activities.active,g->activities.won,g->story.region,g->player.position.x,g->player.position.y,g->player.position.z);fflush(stdout);}
}
static void op1_reload(L3Game *g){
 if(mode!=2)return;
 assert(l3_progress_write(save_path,g,&schema)==L3_PROGRESS_OK);
 L3Game loaded;assert(l3_game_init(&loaded,&g->world,0));assert(l3_progress_read(save_path,&loaded,&schema)==L3_PROGRESS_OK);
 assert(!memcmp(&loaded.player,&g->player,sizeof(g->player)));
 assert(!memcmp(&loaded.camera,&g->camera,sizeof(g->camera)));
 assert(loaded.activities.active==g->activities.active&&loaded.activities.won==g->activities.won);
 assert(loaded.activities.initialized==g->activities.initialized);
 for(unsigned i=0;i<5;i++)assert(!memcmp(&loaded.activities.games[i],&g->activities.games[i],sizeof(L3MiniState)));
 *g=loaded;reloads++;printf("OP1_RELOAD active=%u won=%u exact_pose=1\n",g->activities.active,g->activities.won);fflush(stdout);
}
static void op1_finish(const L3Game *g){
 assert(g->activities.won==31&&!g->activities.active);
 if(mode==1){char path[1100];snprintf(path,sizeof(path),"%s/completed.save",directory);assert(l3_progress_write(path,g,&schema)==L3_PROGRESS_OK);}
 else {assert(reloads==5);assert(l3_progress_write(save_path,g,&schema)==L3_PROGRESS_OK);draw(g);}
 printf("OP1_COMPLETE won=%u active=%u region=%u phase=%u met_nils=%u reloads=%u input_steps=%u rendered_frames=%u accelerated_replay=1\n",g->activities.won,g->activities.active,g->story.region,g->story.amber_phase,g->story.amber_met_nils,reloads,simulated_steps,replay_frames);fflush(stdout);
}

/* Generated from the already validated physical-route test. Only hooks,
 * the entry name and l3_game_step wrapper are changed; coordinates/inputs
 * and all assertions are byte-identical. The bundle records its source. */
#include "route_core.inc"

int main(int argc,char **argv){
 signal(SIGTERM,on_signal);signal(SIGINT,on_signal);signal(SIGHUP,on_signal);
 int at=1;if(at<argc&&!strcmp(argv[at],"--host")){host=1;at++;}
 if(argc-at!=2)return 2;
 double start=seconds();
 if(!strcmp(argv[at],"--fixtures")&&host){mode=1;directory=argv[at+1];assert(!op1_route_main());}
 else if(!strcmp(argv[at],"--replay")){mode=2;save_path=argv[at+1];if(strncmp(save_path,"/tmp/",5)||strchr(save_path+5,'/'))return 2;assert(!op1_route_main());}
 else if(!strcmp(argv[at],"--scene")){
  mode=3;L3World w;L3Game g;l3_world_init(&w);assert(l3_game_init(&g,&w,0));assert(l3_progress_read(argv[at+1],&g,&schema)==L3_PROGRESS_OK);
  for(unsigned i=0;i<3;i++)draw(&g);
  printf("OP1_SCENE active=%u won=%u region=%u fixed_fixture=1 frames=%u commands=%u batches=%u draws_last=%u triangles_last=%u mini_uploads=%u mini_bytes=%u\n",g.activities.active,g.activities.won,g.story.region,renderer.frame,renderer.total_commands,renderer.total_flushes,renderer.draws,renderer.triangles,renderer.mini_uploads,renderer.mini_bytes);
  printf("OP1_PRESENT layers=%u palette_crc=%u descriptor_crc=%u cpu_descriptor=1\n",renderer.last_scene.layers_enabled,checksum(&renderer.hud_palette,sizeof(renderer.hud_palette)),checksum(&renderer.last_scene,sizeof(renderer.last_scene)));
 }else if(!strcmp(argv[at],"--inspect-save")){
  L3World w;L3Game g;l3_world_init(&w);assert(l3_game_init(&g,&w,1));assert(l3_progress_read(argv[at+1],&g,&schema)==L3_PROGRESS_OK);
  unsigned char data[L3_PROGRESS_MAX_BYTES];size_t bytes=0;assert(l3_progress_encode(&g,&schema,data,sizeof(data),&bytes)==L3_PROGRESS_OK);
  printf("OP1_SAVE bytes=%zu active=%u won=%u initialized=%u region=%u phase=%u met_nils=%u auto=%d canonical_crc=%u\n",bytes,g.activities.active,g.activities.won,g.activities.initialized,g.story.region,g.story.amber_phase,g.story.amber_met_nils,g.autopilot,checksum(data,bytes));
 }else return 2;
 if(opened){printf("OP1_RENDER frames=%u elapsed=%.6f commands=%u batches=%u feed_seconds=%.6f present_seconds=%.6f scope=accelerated_or_fixed_fixture\n",renderer.frame,seconds()-start,renderer.total_commands,renderer.total_flushes,renderer.feed_seconds,renderer.present_seconds);assert(l3_render_close(&renderer));}
 puts("OP1_PASS");return 0;
}
