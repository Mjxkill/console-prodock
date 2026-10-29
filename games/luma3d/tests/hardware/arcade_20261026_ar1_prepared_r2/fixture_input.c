/* Offline fixture via ordinary inputs, not an injected engine state. */
#include "luma3d_render.h"
#include "luma3d_progress.h"
#include "luma3d_activities.h"
#include <assert.h>
#include <stdio.h>
static const uint32_t ids[]={0x4c455431,0x4c455432,0x4c455433,0x4c455434};
static const L3ProgressSchema schema={0x56414c31,5,4,ids};
int main(int argc,char **argv){
 assert(argc==3);L3World w;L3Game g;l3_world_init(&w);assert(l3_game_init(&g,&w,0));assert(l3_progress_read(argv[1],&g,&schema)==1&&g.activities.arcade.active==6);
 L3ArcadeView view;unsigned i;
 for(i=0;i<1000;i++){
  assert(l3_arcade_view(&g.activities.arcade,&view));
  if(view.content.simon.phase==L3_SIMON_INPUT&&view.content.simon.sequence_length==2&&view.content.simon.input_index==1)break;
  L3Input in={0};uint32_t ms;assert(l3_arcade_demo_input(&g.activities.arcade,&in.mini_pressed,&in.mini_held,&ms));
  if(!ms)l3_activity_step(&g,&in,0);
  while(ms){unsigned dt=ms>100?100:ms;l3_game_step(&g,&in,dt/1000.f);in.mini_pressed=0;ms-=dt;}
 }
 assert(i<1000);assert(l3_progress_write(argv[2],&g,&schema)==1);
 printf("SIMON_INPUT_FIXTURE phase=%u length=%u input_index=%u legal_commands=%u\n",view.content.simon.phase,view.content.simon.sequence_length,view.content.simon.input_index,i);return 0;
}
