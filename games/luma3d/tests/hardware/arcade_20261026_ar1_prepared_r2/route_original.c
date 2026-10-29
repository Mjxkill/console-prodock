#include "luma3d_render.h"
#include "luma3d_amber.h"
#include "luma3d_activities.h"
#include "luma3d_progress.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static const uint32_t ids[]={0x4c455431,0x4c455432,0x4c455433,0x4c455434};
static const L3ProgressSchema schema={0x56414c31,5,4,ids};

static void capture(const L3Game *g,const char *name){
#ifdef L3_CAPTURE
 const char *directory=getenv("LUMA_CAPTURE_DIR");if(!directory)return;
 for(int wide=0;wide<2;wide++){
  L3Render r;assert(l3_render_open(&r,1,wide));char prefix[1024],path[1100];snprintf(prefix,sizeof(prefix),"%s/%s%s",directory,name,wide?"_720":"");snprintf(path,sizeof(path),"%s.commands",prefix);
  char save[1100];snprintf(save,sizeof(save),"%s.save",prefix);assert(l3_progress_write(save,g,&schema)==1);
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
static void save_resume(L3Game *g){
 unsigned char b[L3_PROGRESS_MAX_BYTES];size_t n=0;assert(l3_progress_encode(g,&schema,b,sizeof(b),&n)==L3_PROGRESS_OK);assert(n<=7480);
 L3World w;L3Game next;l3_world_init(&w);assert(l3_game_init(&next,&w,0));assert(l3_progress_decode(&next,&schema,b,n)==L3_PROGRESS_OK);
 assert(!memcmp(&g->player,&next.player,sizeof(g->player))&&!memcmp(&g->camera,&next.camera,sizeof(g->camera)));
 assert(g->time==next.time&&g->story.region==next.story.region&&g->story.amber_phase==next.story.amber_phase);
 L3ArcadeState expected=g->activities.arcade;expected.release_inputs=1;assert(!memcmp(&expected,&next.activities.arcade,sizeof(expected)));
 L3Game preserved=next;b[n-1]^=1;assert(!l3_progress_decode(&next,&schema,b,n));assert(!memcmp(&next,&preserved,sizeof(next)));b[n-1]^=1;
 assert(!l3_progress_decode(&next,&schema,b,n-1));assert(!memcmp(&next,&preserved,sizeof(next)));
 /* Continue original run; independently resumed engine is checked after the
  * release gate, without imposing a new world tick or a second reward. */
 assert(l3_arcade_step(&next.activities.arcade,0,0,0)==0);expected.release_inputs=0;
 L3ArcadeState original=g->activities.arcade;original.release_inputs=0;assert(!memcmp(&original,&next.activities.arcade,sizeof(original)));
}
static void solve(L3Game *g,unsigned kind){
 press(g);assert(g->activities.arcade.active==kind+1);L3Game paused=*g;
 char name[24];snprintf(name,sizeof(name),"activity_%u",kind);capture(g,name);
 l3_game_step(g,NULL,1.f/60);unsigned i=0;L3ArcadeView v;
 for(;i<12000;i++){
  assert(l3_arcade_view(&g->activities.arcade,&v));if(v.status!=L3_MINI_RUNNING)break;
  L3Input in={0};uint32_t ms;assert(l3_arcade_demo_input(&g->activities.arcade,&in.mini_pressed,&in.mini_held,&ms));
  /* Engine adviser dt may be >game's .1s guard. Split exactly and never
   * replace game state or inject a win. Edges belong only to first piece. */
  if(!ms)l3_activity_step(g,&in,0);
  while(ms){unsigned part=ms>100?100:ms;l3_game_step(g,&in,part/1000.f);in.mini_pressed=0;ms-=part;}
  unchanged(g,&paused);
  if(i==4)save_resume(g);
  if((kind==5&&i==20)||(kind==6&&i==60)||(kind==7&&i==40)){snprintf(name,sizeof(name),"activity_%u_mid",kind);capture(g,name);}

 }
 assert(i<12000&&v.status==L3_MINI_WON&&l3_activity_won(g,kind));
 if(kind>=5){snprintf(name,sizeof(name),"activity_%u_won",kind);capture(g,name);}
 save_resume(g);unsigned won=g->activities.arcade.won;L3Input restart={0};restart.mini_pressed=L3_MINI_RESTART;l3_game_step(g,&restart,1.f/60);assert(g->activities.arcade.won==won);
 l3_game_step(g,NULL,1.f/60);L3Input back={0};back.mini_pressed=L3_MINI_BACK;l3_game_step(g,&back,1.f/60);assert(!g->activities.arcade.active);unchanged(g,&paused);
 unsigned elapsed=kind<5?v.content.grid.elapsed_ms:kind==5?v.content.simon.grid.elapsed_ms:kind==6?v.content.shooter.elapsed_ms:v.content.platform.elapsed_ms;
 printf("ACTIVITY %u physical enter / legal win / unique reward / exact return PASS adviser_calls=%u engine_ms=%u\n",kind,i,elapsed);
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
 assert(g.activities.arcade.won==31&&l3_activities_valid(&g));
 static const float tower[][2]={{219,65},{220,58},{224,50},{224,42},{228,42},{231,42}};path(&g,tower,6);capture(&g,"tower_site");
 assert(l3_amber_blocked(&g,231,l3_amber_ground(231,46),46,.3f,1.65f));solve(&g,L3_ARCADE_PLATFORM);
 static const float tower_exit[][2]={{231,46},{231,48},{230,50},{224,50},{224,42},{224,30},{222.5f,30},{220,32}};
 path(&g,tower_exit,8);assert(!l3_amber_blocked(&g,231,l3_amber_ground(231,46),46,.3f,1.65f));capture(&g,"crystals_site");solve(&g,L3_ARCADE_SIMON);
 static const float stars[][2]={{222.5f,30},{224,30},{232,24},{244,24},{250,24},{254,24},{256,22}};
 path(&g,stars,7);capture(&g,"simulator_site");solve(&g,L3_ARCADE_SHOOTER);
 assert(g.activities.arcade.won==255&&l3_activities_valid(&g));
 printf("EIGHT_ACTIVITIES physical access / V5 pause / legal victories / exact exit PASS steps=%u simulated_seconds=%.3f\n",steps,steps/60.f);
 return 0;
}
