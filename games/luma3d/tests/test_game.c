#include "luma3d_game.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

typedef struct { int wall; float slope; } Fixture;
static float ground(void *ctx,float x,float z) {
    (void)z;
    Fixture *f=ctx;
    return f->slope*fmaxf(0,x-12);
}
static int solid(void *ctx,float x,float y,float z,float r,float h) {
    Fixture *f=ctx;
    return f->wall && x+r>15 && x-r<15.3f && z+r>5 && z-r<25 && y<8 && y+h>0;
}
static L3World world(Fixture *f) {
    L3World w={0};
    w.context=f; w.height=ground; w.blocked=solid;
    w.min_x=w.min_z=0; w.max_x=w.max_z=40;
    w.spawn=(L3Vec3){10,0,10}; w.goal=(L3Vec3){20,0,20};
    return w;
}
static void simulate(L3Game *g,L3Input in,int frames) {
    for (int i=0;i<frames;++i) {
        l3_game_step(g,&in,1.0f/60);
        in.pressed=0;
        assert(isfinite(g->camera.eye.x) && isfinite(g->player.position.y));
        assert(g->player.position.y>=ground(g->world.context,g->player.position.x,g->player.position.z)-.001f);
    }
}

static void movement(void) {
    Fixture f={0}; L3World w=world(&f); L3Game a,b;
    assert(l3_game_init(&a,&w,0)); b=a;
    L3Input in={.move_z=1};
    simulate(&a,in,120); simulate(&b,in,120);
    assert(memcmp(&a,&b,sizeof(a))==0);
    assert(a.player.position.z>18 && a.player.position.z<19.1f);
    assert(a.distance_walked>8 && a.player.walk_phase!=0);
    float z=a.player.position.z;
    simulate(&a,(L3Input){0},60);
    assert(a.player.position.z>z && a.player.position.z<z+1);
    assert(a.player.speed<.001f);
    b=a;
    l3_game_step(&a,&in,0); l3_game_step(&a,&in,-1); l3_game_step(&a,&in,NAN);
    assert(memcmp(&a,&b,sizeof(a))==0);
    l3_game_step(&a,&in,100);
    assert(a.time-b.time<.101f);
    assert(!l3_game_init(&a,NULL,0));
    w.spawn.x=NAN;
    assert(!l3_game_init(&a,&w,0));
}

static void collision(void) {
    Fixture f={.wall=1}; L3World w=world(&f); L3Game g;
    w.spawn_yaw=1.57079632679f;
    assert(l3_game_init(&g,&w,0));
    simulate(&g,(L3Input){.move_z=1,.held=L3_SPRINT},240);
    assert(g.player.position.x<=14.701f && g.player.position.x>14.5f);
    assert(!solid(&f,g.player.position.x,g.player.position.y,g.player.position.z,.30f,1.65f));
    /* Camera must shorten its boom before crossing the same wall. */
    w.spawn.x=17; w.spawn_yaw=1.57079632679f;
    assert(l3_game_init(&g,&w,0));
    assert(g.camera.eye.x>15.4f && g.camera.eye.x<17);
    f.wall=0; f.slope=2;
    w.spawn.x=10;
    assert(l3_game_init(&g,&w,0));
    simulate(&g,(L3Input){.move_z=1},240);
    assert(g.player.position.x<12.15f);
    f.slope=.5f;
    assert(l3_game_init(&g,&w,0));
    simulate(&g,(L3Input){.move_z=1},120);
    assert(g.player.position.x>18);
    assert(fabsf(g.player.position.y-ground(&f,g.player.position.x,g.player.position.z))<.001f);
    assert(g.camera.eye.y>ground(&f,g.camera.eye.x,g.camera.eye.z)+.23f);
}

static void camera_relative_controls(void) {
    /* Independent cardinal directions for right = forward x world-up.
     * Hold the camera heading so follow-steering cannot hide a sign error. */
    const float yaw[4]={0,1.57079632679f,3.14159265359f,-1.57079632679f};
    const float right[4][2]={{-1,0},{0,1},{1,0},{0,-1}};
    const float forward[4][2]={{0,1},{1,0},{0,-1},{-1,0}};
    Fixture f={0};L3World w=world(&f);w.spawn=(L3Vec3){20,0,20};
    for(unsigned cap=0;cap<4;cap++) {
        w.spawn_yaw=yaw[cap];
        for(int direction=-1;direction<=1;direction+=2) {
            L3Game g;assert(l3_game_init(&g,&w,0));g.camera_manual_seconds=10;
            simulate(&g,(L3Input){.move_x=direction},60);
            float dx=g.player.position.x-w.spawn.x,dz=g.player.position.z-w.spawn.z;
            assert(direction*(dx*right[cap][0]+dz*right[cap][1])>3.8f);
            assert(fabsf(dx*forward[cap][0]+dz*forward[cap][1])<.001f);
        }
        L3Game g;assert(l3_game_init(&g,&w,0));
        simulate(&g,(L3Input){.look_x=1},15);
        float fx=sinf(g.camera.yaw),fz=cosf(g.camera.yaw);
        assert(fx*right[cap][0]+fz*right[cap][1]>.45f);
        assert(fx*forward[cap][0]+fz*forward[cap][1]>.8f);
        assert(g.player.position.x==w.spawn.x&&g.player.position.z==w.spawn.z);
    }
    puts("Camera controls PASS: A/D translation and positive look-right at four cardinal headings.");
}

static void jump(void) {
    Fixture f={0}; L3World w=world(&f); L3Game g;
    assert(l3_game_init(&g,&w,0));
    L3Input in={.pressed=L3_JUMP};
    l3_game_step(&g,&in,1.0f/60);
    assert(!g.player.grounded && g.player.velocity.y>5);
    simulate(&g,(L3Input){0},15);
    assert(g.player.position.y>.9f);
    simulate(&g,(L3Input){0},60);
    assert(g.player.grounded && fabsf(g.player.position.y)<.001f);
}

static void journey(void) {
    Fixture f={.wall=1}; L3World w=world(&f); L3Game g;
    /* A real detour around the north end of a wall, then back. */
    L3Vec3 route[]={{10,0,10},{10,0,3},{20,0,3},{20,0,10},{25,0,20}};
    L3Vec3 items[]={{10,0,4},{19,0,3},{20,0,10}};
    w.route=route; w.route_count=5; w.collectibles=items; w.collectible_count=3;
    w.goal=route[4];
    assert(l3_game_init(&g,&w,1));
    float worst_stuck=0;
    for (int i=0;i<2400;++i) {
        L3Vec3 before=g.player.position;
        l3_game_step(&g,NULL,1.0f/60);
        assert(hypotf(g.player.position.x-before.x,g.player.position.z-before.z)<.12f);
        assert(!solid(&f,g.player.position.x,g.player.position.y,g.player.position.z,.30f,1.65f));
        worst_stuck=fmaxf(worst_stuck,g.autopilot_stuck_seconds);
    }
    assert(g.objective_complete && g.collected_count==3 && g.collected_mask==7);
    assert(g.completed_routes>=2 && worst_stuck<1);
    uint32_t mask=g.collected_mask;
    simulate(&g,(L3Input){.move_x=1},1);
    assert(!g.autopilot);
    simulate(&g,(L3Input){.pressed=L3_TOGGLE_AUTO},1);
    assert(g.autopilot && g.collected_mask==mask && g.objective_complete);
    simulate(&g,(L3Input){.look_x=1},1);
    assert(!g.autopilot);
    printf("Journey PASS: 3 contact pickups, objective, %u physical route legs, %.1f m walked.\n",g.completed_routes,g.distance_walked);
}

int main(void) {
    movement(); collision(); camera_relative_controls(); jump(); journey();
    puts("LUMA3D gameplay PASS: deterministic movement, inertia, dt, collision, slope, jump, camera, objective and manual takeover.");
    return 0;
}
