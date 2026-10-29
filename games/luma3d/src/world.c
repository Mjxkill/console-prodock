#include "luma3d_render.h"
#include "generated.h"
#include <math.h>

static float ground(float x,float z) {
    x=fminf(159.9999f,fmaxf(0,x)); z=fminf(159.9999f,fmaxf(0,z));
    int ix=(int)(x*.5f),iz=(int)(z*.5f); float u=x*.5f-ix,v=z*.5f-iz;
    float a=l3_asset_heights[iz][ix],b=l3_asset_heights[iz][ix+1];
    float c=l3_asset_heights[iz+1][ix+1],d=l3_asset_heights[iz+1][ix];
    return u>=v?a+(b-a)*u+(c-b)*v:a+(c-d)*u+(d-a)*v;
}
static int bridge(float x,float z,float radius,float *deck) {
    for(unsigned i=0;i<l3_asset_collider_count;i++) {
        const L3AssetCollider *c=&l3_asset_colliders[i];
        if(c->kind!=L3_COLLIDER_BRIDGE)continue;
        float dx=x-c->x,dz=z-c->z,s=sinf(c->yaw),co=cosf(c->yaw);
        float u=co*dx-s*dz,v=s*dx+co*dz;
        if(fabsf(u)<=c->length*.5f&&fabsf(v)<=c->width*.5f-radius) {
            *deck=c->y+c->arch_height*sinf(3.14159265f*(u/c->length+.5f));return 1;
        }
    }return 0;
}
static float height(void *ctx,float x,float z) {
    (void)ctx;float y=ground(x,z),deck;
    return bridge(x,z,0,&deck)?fmaxf(y,deck):y;
}
static int blocked(void *ctx,float x,float y,float z,float r,float h) {
    (void)ctx;
    for(unsigned i=0;i<l3_asset_collider_count;i++) {
        const L3AssetCollider *c=&l3_asset_colliders[i];
        if(c->kind==L3_COLLIDER_BRIDGE||y>=c->max_y||y+h<=c->min_y)continue;
        if(c->kind==L3_COLLIDER_CIRCLE&&hypotf(x-c->x,z-c->z)<r+c->radius)return 1;
        if(c->kind==L3_COLLIDER_BOX) {
            float dx=x-c->x,dz=z-c->z,co=cosf(c->yaw),s=sinf(c->yaw);
            if(fabsf(co*dx-s*dz)<c->length*.5f+r&&fabsf(s*dx+co*dz)<c->width*.5f+r)return 1;
        }
    }
    float deck;if(bridge(x,z,r,&deck)&&y>=deck-.1f)return 0;
    float floor=ground(x,z);
    for(unsigned i=0;i<l3_asset_water_count;i++) {
        const L3AssetWater *w=&l3_asset_waters[i];
        if(w->level-floor<=.65f||y>=w->level+.2f)continue;
        if(w->kind==L3_WATER_ELLIPSE) {
            float a=(x-w->x)/(w->rx+.3f),b=(z-w->z)/(w->rz+.3f);
            if(a*a+b*b<1)return 1;
        }else if(w->kind==L3_WATER_RIBBON) {
            for(unsigned j=1;j<w->point_count;j++) {
                const L3AssetPoint2 *a=&l3_asset_water_points[w->first_point+j-1],*b=a+1;
                float dx=b->x-a->x,dz=b->z-a->z,d2=dx*dx+dz*dz;
                float t=d2>0?fminf(1,fmaxf(0,((x-a->x)*dx+(z-a->z)*dz)/d2)):0;
                if(hypotf(x-a->x-t*dx,z-a->z-t*dz)<w->width*.5f+r)return 1;
            }
        }
    }return 0;
}
void l3_world_init(L3World *w) {
    *w=(L3World){.height=height,.blocked=blocked,.max_x=160,.max_z=160,
      .spawn=l3_asset_spawn,.spawn_yaw=l3_asset_spawn_yaw,
      .route=l3_asset_route,.route_count=l3_asset_route_count,
      .collectibles=l3_asset_collectibles,.collectible_count=l3_asset_collectible_count,
      .goal=l3_asset_goal,.goal_radius=l3_asset_goal_radius};
}
