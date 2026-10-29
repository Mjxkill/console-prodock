#include "luma3d_game.h"

#include <math.h>
#include <string.h>

#define PI 3.14159265358979323846f
#define RADIUS .30f
#define BODY_HEIGHT 1.65f
#define WALK_SPEED 4.5f
#define RUN_SPEED 7.0f
#define GRAVITY 16.0f

static float clampf(float v, float lo, float hi) { return fminf(hi, fmaxf(lo, v)); }
static float axis(float v) { return isfinite(v) ? clampf(v, -1, 1) : 0; }
static float length2(float x, float z) { return sqrtf(x*x + z*z); }
static float angle(float v) { return remainderf(v, 2*PI); }
static float approach(float v, float target, float amount) {
    return v + clampf(target-v, -amount, amount);
}
static float height(const L3Game *g, float x, float z) {
    float h = g->world.height(g->world.context, x, z);
    return isfinite(h) ? h : 100000.0f; /* malformed query is impassable */
}
static int blocked(const L3Game *g, float x, float y, float z, float r, float h) {
    return x-r < g->world.min_x || x+r > g->world.max_x ||
           z-r < g->world.min_z || z+r > g->world.max_z ||
           (g->world.blocked && g->world.blocked(g->world.context,x,y,z,r,h));
}

static L3Vec3 camera_clip(const L3Game *g, L3Vec3 from, L3Vec3 to) {
    L3Vec3 delta = {to.x-from.x, to.y-from.y, to.z-from.z}, last = from;
    float dist = sqrtf(delta.x*delta.x + delta.y*delta.y + delta.z*delta.z);
    int steps = (int)ceilf(dist/.18f);
    if (steps > 160) steps = 160;
    for (int i=1; i<=steps; ++i) {
        float f = (float)i/(float)steps;
        L3Vec3 p = {from.x+delta.x*f,from.y+delta.y*f,from.z+delta.z*f};
        if (p.y < height(g,p.x,p.z)+.24f || blocked(g,p.x,p.y-.2f,p.z,.2f,.4f))
            break;
        last = p;
    }
    return last;
}

static void camera_update(L3Game *g, float dt, int immediate) {
    L3Camera *c=&g->camera;
    L3Vec3 target={g->player.position.x,g->player.position.y+1.35f,g->player.position.z};
    float blend = immediate ? 1 : 1-expf(-9*dt);
    c->target.x += (target.x-c->target.x)*blend;
    c->target.y += (target.y-c->target.y)*blend;
    c->target.z += (target.z-c->target.z)*blend;
    /* Never let lag place the target inside a hill or behind a wall. */
    c->target=camera_clip(g,target,c->target);
    L3Vec3 desired={c->target.x-sinf(c->yaw)*cosf(c->pitch)*c->distance,
                   c->target.y+sinf(c->pitch)*c->distance,
                   c->target.z-cosf(c->yaw)*cosf(c->pitch)*c->distance};
    desired=camera_clip(g,c->target,desired);
    L3Vec3 smooth={c->eye.x+(desired.x-c->eye.x)*blend,
                   c->eye.y+(desired.y-c->eye.y)*blend,
                   c->eye.z+(desired.z-c->eye.z)*blend};
    c->eye=camera_clip(g,c->target,smooth);
}

int l3_game_init(L3Game *g, const L3World *w, int autopilot) {
    if (!g) return 0;
    memset(g,0,sizeof(*g));
    if (!w || !w->height || !isfinite(w->min_x) || !isfinite(w->max_x) ||
        !isfinite(w->min_z) || !isfinite(w->max_z) ||
        w->max_x-w->min_x <= 2*RADIUS || w->max_z-w->min_z <= 2*RADIUS ||
        !isfinite(w->spawn.x) || !isfinite(w->spawn.z) || !isfinite(w->spawn_yaw) ||
        !isfinite(w->goal.x) || !isfinite(w->goal.y) || !isfinite(w->goal.z) ||
        w->collectible_count > 32 || (w->collectible_count && !w->collectibles) ||
        w->route_count > 1024 || (w->route_count && !w->route)) return 0;
    for (uint32_t i=0;i<w->route_count;++i)
        if (!isfinite(w->route[i].x) || !isfinite(w->route[i].z)) return 0;
    for (uint32_t i=0;i<w->collectible_count;++i)
        if (!isfinite(w->collectibles[i].x) || !isfinite(w->collectibles[i].y) ||
            !isfinite(w->collectibles[i].z)) return 0;
    g->world=*w;
    g->player.position=w->spawn;
    g->player.position.x=clampf(w->spawn.x,w->min_x+RADIUS,w->max_x-RADIUS);
    g->player.position.z=clampf(w->spawn.z,w->min_z+RADIUS,w->max_z-RADIUS);
    g->player.position.y=height(g,g->player.position.x,g->player.position.z);
    if (g->player.position.y==100000.0f || blocked(g,g->player.position.x,
        g->player.position.y,g->player.position.z,RADIUS,BODY_HEIGHT)) return 0;
    g->player.yaw=angle(w->spawn_yaw);
    g->player.grounded=1;
    g->camera.yaw=g->player.yaw;
    g->camera.pitch=.30f;
    g->camera.distance=7.8f;
    g->autopilot=autopilot && w->route_count>1;
    g->route_direction=1;
    g->valid=1;
    camera_update(g,0,1);
    return 1;
}

static void nearest_route(L3Game *g) {
    float best=1e30f;
    for (uint32_t i=0;i<g->world.route_count;++i) {
        float d=length2(g->world.route[i].x-g->player.position.x,
                        g->world.route[i].z-g->player.position.z);
        if (d<best) { best=d; g->route_index=i; }
    }
}

static void route_advance(L3Game *g) {
    if (g->route_direction>0) {
        if (g->route_index+1<g->world.route_count) ++g->route_index;
        else { g->route_direction=-1; --g->route_index; ++g->completed_routes; }
    } else {
        if (g->route_index>0) --g->route_index;
        else { g->route_direction=1; ++g->route_index; ++g->completed_routes; }
    }
}

static int horizontal_try(L3Game *g, float x, float z) {
    L3Player *p=&g->player;
    float floor=height(g,x,z), old_floor=height(g,p->position.x,p->position.z);
    float distance=length2(x-p->position.x,z-p->position.z);
    float feet=p->position.y;
    if (p->grounded) {
        /* Tolerance must stay below float noise: a centimetre allowance per
         * substep lets a blocked character slowly climb vertical slopes. */
        if (floor-old_floor > .00005f+distance*.95f) return 0;
        if (floor > feet-.32f) feet=floor;
    } else if (floor > feet+.08f) return 0;
    if (blocked(g,x,feet,z,RADIUS,BODY_HEIGHT)) return 0;
    p->position.x=x; p->position.z=z;
    if (p->grounded && feet>=floor && feet-floor<.32f) p->position.y=floor;
    else if (feet-floor>=.32f) p->grounded=0;
    return 1;
}

static void collect_and_interact(L3Game *g, int interact) {
    for (uint32_t i=0;i<g->world.collectible_count;++i) {
        uint32_t bit=UINT32_C(1)<<i;
        L3Vec3 a=g->world.collectibles[i], p=g->player.position;
        if (!(g->collected_mask&bit) && length2(a.x-p.x,a.z-p.z)<1.35f &&
            fabsf(a.y-p.y)<2.2f) {
            g->collected_mask|=bit;
            ++g->collected_count;
        }
    }
    float radius=g->world.goal_radius>0 ? g->world.goal_radius : 2.5f;
    if (interact && g->collected_count==g->world.collectible_count &&
        length2(g->player.position.x-g->world.goal.x,g->player.position.z-g->world.goal.z)<radius &&
        fabsf(g->player.position.y-g->world.goal.y)<2.2f) g->objective_complete=1;
}

static void step(L3Game *g, L3Input in, float dt) {
    L3Player *p=&g->player;
    if ((in.pressed&L3_TOGGLE_AUTO) && g->world.route_count>1) {
        g->autopilot=!g->autopilot;
        nearest_route(g);
    }
    if (fabsf(in.move_x)+fabsf(in.move_z)+fabsf(in.look_x)+fabsf(in.look_y)>.02f ||
        (in.pressed&(L3_JUMP|L3_INTERACT))) g->autopilot=0;
    g->camera_manual_seconds=fmaxf(0,g->camera_manual_seconds-dt);
    if (fabsf(in.look_x)+fabsf(in.look_y)>.01f) {
        g->camera.yaw=angle(g->camera.yaw-in.look_x*2.1f*dt);
        g->camera.pitch=clampf(g->camera.pitch+in.look_y*1.2f*dt,.10f,.85f);
        g->camera_manual_seconds=2.5f;
    }
    float dx=0,dz=0, speed=(in.held&L3_SPRINT)?RUN_SPEED:WALK_SPEED;
    if (g->autopilot) {
        L3Vec3 point=g->world.route[g->route_index];
        dx=point.x-p->position.x; dz=point.z-p->position.z;
        float dist=length2(dx,dz);
        if (dist<.60f) {
            route_advance(g);
            point=g->world.route[g->route_index];
            dx=point.x-p->position.x; dz=point.z-p->position.z;
            dist=length2(dx,dz);
        }
        speed=fminf(WALK_SPEED,1.8f+dist*1.5f);
        if (dist>.001f) { dx/=dist; dz/=dist; }
    } else {
        dx=-cosf(g->camera.yaw)*in.move_x+sinf(g->camera.yaw)*in.move_z;
        dz=sinf(g->camera.yaw)*in.move_x+cosf(g->camera.yaw)*in.move_z;
        float n=length2(dx,dz);
        if (n>1) { dx/=n; dz/=n; }
    }
    float accel=p->grounded ? 20.0f : 6.0f;
    p->velocity.x=approach(p->velocity.x,dx*speed,accel*dt);
    p->velocity.z=approach(p->velocity.z,dz*speed,accel*dt);
    if (length2(dx,dz)>.02f) p->yaw=angle(p->yaw+angle(atan2f(dx,dz)-p->yaw)*(1-expf(-12*dt)));
    if (p->grounded) g->coyote_seconds=.10f;
    else g->coyote_seconds=fmaxf(0,g->coyote_seconds-dt);
    if (in.pressed&L3_JUMP) g->jump_buffer_seconds=.12f;
    else g->jump_buffer_seconds=fmaxf(0,g->jump_buffer_seconds-dt);
    if (g->jump_buffer_seconds>0 && g->coyote_seconds>0) {
        p->velocity.y=6.2f; p->grounded=0;
        g->jump_buffer_seconds=0; g->coyote_seconds=0;
    }
    L3Vec3 before=p->position;
    float mx=p->velocity.x*dt, mz=p->velocity.z*dt;
    int sub=(int)ceilf(length2(mx,mz)/.12f);
    if (sub<1) sub=1;
    for (int i=0;i<sub;++i) {
        if (!horizontal_try(g,p->position.x+mx/sub,p->position.z+mz/sub)) {
            if (!horizontal_try(g,p->position.x+mx/sub,p->position.z)) p->velocity.x=0;
            if (!horizontal_try(g,p->position.x,p->position.z+mz/sub)) p->velocity.z=0;
        }
    }
    if (!p->grounded) {
        p->velocity.y-=GRAVITY*dt;
        float next_y=p->position.y+p->velocity.y*dt;
        if (blocked(g,p->position.x,next_y,p->position.z,RADIUS,BODY_HEIGHT)) p->velocity.y=0;
        else p->position.y=next_y;
    }
    float floor=height(g,p->position.x,p->position.z);
    if (p->position.y<=floor && p->velocity.y<=0) {
        p->position.y=floor; p->velocity.y=0; p->grounded=1;
    }
    float moved=length2(p->position.x-before.x,p->position.z-before.z);
    p->speed=moved/dt;
    if (p->grounded) {
        g->distance_walked+=moved;
        p->walk_phase=fmodf(p->walk_phase+moved*3.5f,2*PI);
    }
    if (g->autopilot && moved<.005f) g->autopilot_stuck_seconds+=dt;
    else g->autopilot_stuck_seconds=0;
    collect_and_interact(g,(in.pressed&L3_INTERACT)!=0 || g->autopilot);
    if (g->camera_manual_seconds<=0 && p->speed>.2f)
        g->camera.yaw=angle(g->camera.yaw+angle(p->yaw-g->camera.yaw)*(1-expf(-2.8f*dt)));
    camera_update(g,dt,0);
    g->time+=dt;
}

void l3_game_step(L3Game *g, const L3Input *input, float dt) {
    if (!g || !g->valid || !isfinite(dt) || dt<=0) return;
    dt=fminf(dt,.1f);
    L3Input in=input ? *input : (L3Input){0};
    in.move_x=axis(in.move_x); in.move_z=axis(in.move_z);
    in.look_x=axis(in.look_x); in.look_y=axis(in.look_y);
    int n=(int)ceilf(dt/(1.0f/60));
    for (int i=0;i<n;++i) {
        step(g,in,dt/n);
        in.pressed=0;
    }
}
