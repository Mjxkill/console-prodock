#include "luma3d_render.h"
#include "luma3d_amber.h"
#include "luma3d_activities.h"
#include "luma3d_progress.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static void capture(const L3Game *g,const char *name){
#ifdef L3_CAPTURE
 const char *directory=getenv("LUMA_CAPTURE_DIR");if(!directory)return;
 for(int wide=0;wide<2;wide++){
  L3Render r;assert(l3_render_open(&r,1,wide));char prefix[1024],path[1100];snprintf(prefix,sizeof(prefix),"%s/%s%s",directory,name,wide?"_720":"");snprintf(path,sizeof(path),"%s.commands",prefix);
  r.capture=fopen(path,"wb");assert(r.capture);assert(l3_render_frame(&r,g));assert(!fclose(r.capture));r.capture=NULL;assert(l3_render_dump(&r,prefix));assert(l3_render_close(&r));
 }
#else
 (void)g;(void)name;
#endif
}

/* Every route uses the normal inertial player inputs and collision function.
 * No relocation, assignment of player/camera coordinates, or relaxed slope. */
static unsigned steps;
static void walk(L3Game *g,float x,float z) {
    unsigned n=0;float previous=1e9f;unsigned still=0;
    for(;n<2400;n++) {
        float dx=x-g->player.position.x,dz=z-g->player.position.z,d=hypotf(dx,dz);
        if(d<.18f)break;
        float scale=fminf(1,d*1.8f)/d,c=cosf(g->camera.yaw),s=sinf(g->camera.yaw);
        L3Input in={0};in.move_x=(-c*dx+s*dz)*scale;in.move_z=(s*dx+c*dz)*scale;
        l3_game_step(g,&in,1.f/60);steps++;
        if(fabsf(previous-d)<.00001f)still++;else still=0;previous=d;
        if(still>180)break;
    }
    if(n>=2400||hypotf(x-g->player.position.x,z-g->player.position.z)>=.18f) {
        fprintf(stderr,"BLOCKED target %.2f %.2f actual %.3f %.3f %.3f phase%u near%d\n",x,z,g->player.position.x,g->player.position.y,g->player.position.z,g->story.amber_phase,g->story.nearest);assert(0);
    }
    if(x==219&&z==65)capture(g,"house_entry");
}
static void path(L3Game *g,const float (*p)[2],unsigned n){for(unsigned i=0;i<n;i++)walk(g,p[i][0],p[i][1]);}
static void press(L3Game *g){L3Input in={0};in.pressed=L3_INTERACT;l3_game_step(g,&in,1.f/60);steps++;}
static void unchanged(const L3Game *g,const L3Game *before){L3Game copy=*g;copy.activities=before->activities;copy.story.revision=before->story.revision;assert(!memcmp(&copy,before,sizeof(copy)));}
static void solve(L3Game *g,unsigned kind){
 press(g);assert(g->activities.active==kind+1);L3Game paused=*g;
 char name[24];snprintf(name,sizeof(name),"activity_%u",kind);capture(g,name);
 l3_game_step(g,NULL,1.f/60);unsigned i=0;L3MiniView v;
 for(;i<12000;i++){
  assert(l3_mini_view(&g->activities.games[kind],&v));if(v.status!=L3_MINI_RUNNING)break;
  L3Input in={0};uint32_t ms;assert(l3_mini_demo_input(&g->activities.games[kind],&in.mini_pressed,&in.mini_held,&ms));
  /* Engine adviser dt may be >game's .1s guard. Split exactly and never
   * replace game state or inject a win. Edges belong only to first piece. */
  if(!ms)l3_activity_step(g,&in,0);
  while(ms){unsigned part=ms>100?100:ms;l3_game_step(g,&in,part/1000.f);in.mini_pressed=0;ms-=part;}
  unchanged(g,&paused);
 }
 assert(i<12000&&v.status==L3_MINI_WON&&l3_activity_won(g,kind));
 unsigned won=g->activities.won;L3Input restart={0};restart.mini_pressed=L3_MINI_RESTART;l3_game_step(g,&restart,1.f/60);assert(g->activities.won==won);
 l3_game_step(g,NULL,1.f/60);L3Input back={0};back.mini_pressed=L3_MINI_BACK;l3_game_step(g,&back,1.f/60);assert(!g->activities.active);unchanged(g,&paused);
 printf("ACTIVITY %u physical enter / legal win / unique reward / exact return PASS\n",kind);
}
int main(void){
 L3World w;L3Game g;l3_world_init(&w);assert(l3_game_init(&g,&w,1));
 for(unsigned i=0;i<15000&&!(g.story.region&&g.story.amber_phase==2&&g.story.dialogue<0);i++)l3_game_step(&g,NULL,1.f/60);
 assert(g.story.region&&g.story.amber_phase==2);L3Input manual={0};manual.pressed=L3_TOGGLE_AUTO;l3_game_step(&g,&manual,1.f/60);assert(!g.autopilot);
 static const float west[][2]={{220,58},{224,50},{224,42},{224,30},{232,24},{244,24},{250,24},{252,21.2f}};
 path(&g,west,sizeof(west)/sizeof(*west));assert(!g.story.amber_intake&&!g.story.amber_lift);puts("WEST_ROUTE physical PASS bridge closed");
 press(&g);while(g.story.dialogue>=0)press(&g);assert(g.story.amber_met_nils&&g.story.amber_phase==2);
 static const float garden[][2]={{250,24},{244,24},{232,24},{224,30},{218,28},{212,24}};
 path(&g,garden,sizeof(garden)/sizeof(*garden));puts("GARDEN_BRANCH physical PASS");capture(&g,"garden");
 L3Game rejoin=g;walk(&rejoin,216,34);L3Input auto_in={.pressed=L3_TOGGLE_AUTO};l3_game_step(&rejoin,&auto_in,1.f/60);assert(!rejoin.autopilot&&rejoin.story.toast==15);
 assert(l3_amber_blocked(&g,216,l3_amber_ground(216,40),40,.3f,1.65f));solve(&g,L3_MINI_SHAPES);
 static const float shortcut[][2]={{216,34},{216,40},{216,44},{220,48},{220,58}};path(&g,shortcut,5);
 assert(!l3_amber_blocked(&g,216,l3_amber_ground(216,40),40,.3f,1.65f));puts("GARDEN_SHORTCUT physical PASS");
 static const float back[][2]={{224,54},{230,50}};
 path(&g,back,sizeof(back)/sizeof(*back));press(&g);assert(g.story.amber_intake);
 static const float valve[][2]={{236,46},{242,43}};path(&g,valve,2);press(&g);press(&g);assert(g.story.amber_phase>=3);
 for(unsigned i=0;i<130;i++)l3_game_step(&g,NULL,1.f/60);
 static const float water[][2]={{244,40},{244,28},{250,24},{252,21.2f}};path(&g,water,4);
 printf("WATER_ROUTE physical PASS loop steps=%u seconds=%.2f\n",steps,steps/60.f);
 assert(g.story.amber_phase==4&&g.story.amber_met_nils);assert(l3_amber_state_ok(&g));
 static const float tour[][2]={{250,24},{256,28},{258,27}};path(&g,tour,3);solve(&g,L3_MINI_MERGE1024);
 static const float blocks[][2]={{256,28},{250,24},{244,24},{232,24},{224,30},{224,40},{227,41}};path(&g,blocks,7);solve(&g,L3_MINI_BLOCKS);
 static const float circuit[][2]={{224,42},{224,50},{224,54},{229,57}};path(&g,circuit,4);solve(&g,L3_MINI_CIRCUIT);
 static const float house[][2]={{224,54},{220,58},{218,62},{219,65},{219,68},{219,70.5f},{221,70.5f},{224,70.5f},{224,72}};path(&g,house,9);solve(&g,L3_MINI_MAZE);
 static const float secret[][2]={{224,70.5f},{221,70.5f},{219,72},{217,72},{215,72}};path(&g,secret,5);puts("HOUSE rooms / secret exit physical PASS");
 assert(g.activities.won==31&&l3_activities_valid(&g));
 return 0;
}
