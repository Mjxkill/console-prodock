#define _POSIX_C_SOURCE 200809L
#include "luma3d_render.h"
#include "generated.h"
#include "prodock-validate.h"
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

/* gpu_v1's emitter has no user pointer. The native application has exactly one
 * producer, and capture uses this identical producer, never CPU projection. */
static L3Render *active;
static double clock_seconds(void) {struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static float dot(L3Vec3 a,L3Vec3 b) {return a.x*b.x+a.y*b.y+a.z*b.z;}
static L3Vec3 sub(L3Vec3 a,L3Vec3 b) {return (L3Vec3){a.x-b.x,a.y-b.y,a.z-b.z};}
static L3Vec3 cross(L3Vec3 a,L3Vec3 b) {return (L3Vec3){a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
static L3Vec3 unit(L3Vec3 a) {float n=sqrtf(dot(a,a));return n>1e-6f?(L3Vec3){a.x/n,a.y/n,a.z/n}:(L3Vec3){0,0,1};}
static unsigned rgb(unsigned r,unsigned g,unsigned b) {return (r*31/255<<11)|(g*63/255<<5)|(b*31/255);}
static int call(L3Render *r,unsigned long op,void *v) {
    if(r->failed)return 0;
    if(!r->host&&ioctl(op==PRODOCK_LAYOUT||op==PRODOCK_DISPLAY_INFO?r->display:r->fd,op,v)) {
        perror("LUMA3D GPU");r->failed=1;return 0;
    }return 1;
}
static void flush(L3Render *r) {
    if(!r->batch.count||r->failed)return;
    double t=clock_seconds();call(r,PRODOCK_SUBMIT,&r->batch);
    r->feed_seconds+=clock_seconds()-t;r->total_flushes++;r->batch.count=0;
}
static void emit(const gpu_command *c) {
    L3Render *r=active;
    if(!r||r->failed)return;
    if(prodock_command(c->words)) {fprintf(stderr,"Invalid G3D command %u\n",c->words[0]>>24);r->failed=1;return;}
    unsigned op=c->words[0]>>24;
    int slot=op==31?(int)c->words[1]:op==33?3:op==25?4:op==24?5:-1;
    /* G3D DRAW restores MATERIAL and retains MATRIX/LIGHT/TEXTURE. COPY
     * invalidates texture contents, not its descriptor. Keep all descriptors
     * explicit again after TARGET; do not cache raster interpolation planes. */
    if(op==22)r->state_valid=0;
    if(slot>=0&&(r->state_valid&(1U<<slot))&&!memcmp(c,&r->state_cache[slot],sizeof(*c)))return;
    if(r->batch.count==PRODOCK_BATCH_MAX)flush(r);
    if(r->failed)return;
    memcpy(r->batch.commands[r->batch.count++],c->words,32);r->commands++;r->total_commands++;
    if(slot>=0) {r->state_cache[slot]=*c;r->state_valid|=1U<<slot;}
    if(r->capture&&fwrite(c->words,32,1,r->capture)!=1)r->failed=1;
}
static uint32_t upload(L3Render *r,const void *source,unsigned bytes) {
    unsigned offset=(r->uploaded+31)&~31U;
    if(offset>L3_MAP_BYTES||bytes>L3_MAP_BYTES-offset) {r->failed=1;return 0;}
    memcpy(r->memory+offset,source,bytes);
    if(memcmp(r->memory+offset,source,bytes)) {fputs("LUMA3D upload verification failed\n",stderr);r->failed=1;return 0;}
    r->uploaded=offset+bytes;return PRODOCK_GPU_BASE+offset;
}
int l3_render_open(L3Render *r,int host,int wide) {
    memset(r,0,sizeof(*r));r->fd=r->display=-1;r->host=host;
    if(active) {fputs("Only one GPU producer allowed\n",stderr);return 0;}
    unsigned w=wide?1280:800,h=wide?720:480;
    if(!host) {
        r->fd=open("/dev/prodock-gpu",O_RDWR|O_CLOEXEC);
        r->display=open("/dev/prodock-display",O_RDWR|O_CLOEXEC);
        if(r->fd<0||r->display<0) {perror("LUMA3D open");return 0;}
        struct prodock_info i;
        if(!call(r,PRODOCK_INFO,&i)||i.abi!=PRODOCK_ABI||i.faulted||i.errors||(i.caps&511)!=511)return 0;
        if(!call(r,PRODOCK_GEOMETRY_INFO,&r->initial_geometry)||r->initial_geometry.signature!=PRODOCK_GEOMETRY_SIGNATURE||r->initial_geometry.errors)return 0;
        if(!call(r,PRODOCK_DISPLAY_INFO,&r->initial))return 0;
        w=i.width;h=i.height;
    }
    if(!((w==800&&h==480)||(w==1280&&h==720)))return 0;
    r->width=w/2;r->height=h/2;r->pitch=w*2;r->page_bytes=w==800?1U<<20:2U<<20;
    r->memory=host?calloc(1,L3_MAP_BYTES):mmap(NULL,L3_MAP_BYTES,PROT_READ|PROT_WRITE,MAP_SHARED,r->fd,0);
    if(r->memory==MAP_FAILED)r->memory=NULL;
    if(!r->memory)return 0;
    r->meshes=calloc(l3_asset_group_count,sizeof(*r->meshes));
    r->textures=calloc(l3_asset_texture_count,sizeof(*r->textures));
    if(!r->meshes||!r->textures)return 0;
    r->uploaded=L3_ASSET_OFFSET;
    for(unsigned i=0;i<l3_asset_group_count;i++) {
        const L3AssetGroup *g=l3_asset_groups+i;
        if(!g->nv||g->nv>256||!g->nf||g->material>=l3_asset_material_count)return 0;
        r->meshes[i]=(gpu_geom_mesh){upload(r,g->vertices,g->nv*32),upload(r,g->faces,g->nf*32),g->nv,g->nf};
    }
    for(unsigned i=0;i<l3_asset_texture_count;i++) {
        const L3AssetTexture *t=&l3_asset_textures[i];
        if(t->width!=128||t->height!=128)return 0;
        r->textures[i]=upload(r,t->pixels,t->width*t->height*2);
    }
    if(r->failed)return 0;
    active=r;gpu_v1_init(&r->gpu,emit);
    r->near_z=.5f;r->far_z=210;r->focal=r->width*.82f;
    printf("LUMA3D ready: %ux%u G3D1 assets=%u bytes groups=%u textures=%u\n",r->width,r->height,r->uploaded-L3_ASSET_OFFSET,l3_asset_group_count,l3_asset_texture_count);fflush(stdout);
    if(!host) {struct prodock_layout layout={.mode=PRODOCK_GAME};if(!call(r,PRODOCK_LAYOUT,&layout))return 0;}
    return 1;
}
static L3Vec3 object_point(L3Vec3 p,L3Vec3 scale,float yaw,L3Vec3 position) {
    float s=sinf(yaw),c=cosf(yaw),x=p.x*scale.x,z=p.z*scale.z;
    return (L3Vec3){position.x+c*x+s*z,position.y+p.y*scale.y,position.z-s*x+c*z};
}
static int visible(L3Render *r,const L3Game *g,const L3AssetMesh *m,L3Vec3 p,L3Vec3 scale,float yaw,float *distance) {
    L3Vec3 rel=sub(object_point(m->center,scale,yaw,p),g->camera.eye);
    float x=dot(rel,r->right),y=dot(rel,r->down),z=dot(rel,r->forward);
    float radius=m->radius*fmaxf(fabsf(scale.x),fmaxf(fabsf(scale.y),fabsf(scale.z)));
    *distance=sqrtf(dot(rel,rel));
    float sx=r->width*.5f/r->focal,sy=r->height*.5f/r->focal;
    return z+radius>=r->near_z&&z-radius<=r->far_z&&fabsf(x)-z*sx<=radius*sqrtf(1+sx*sx)&&fabsf(y)-z*sy<=radius*sqrtf(1+sy*sy);
}
static int draw_ex(L3Render *r,const L3Game *g,unsigned mesh,L3Vec3 p,L3Vec3 scale,float yaw,float pitch,float roll,int cull) {
    if(mesh>=l3_asset_mesh_count)return 0;
    const L3AssetMesh *m=&l3_asset_meshes[mesh];float distance;
    float sp=sinf(pitch),cp=cosf(pitch),sr=sinf(roll),cr=cosf(roll);
    L3Vec3 local_columns[3]={{cr,cp*sr,sp*sr},{-sr,cp*cr,sp*cr},{0,-sp,cp}};
    L3AssetMesh bounds=*m;L3Vec3 center=m->center;
    bounds.center=(L3Vec3){cr*center.x-sr*center.y,
        cp*sr*center.x+cp*cr*center.y-sp*center.z,
        sp*sr*center.x+sp*cr*center.y+cp*center.z};
    if(!visible(r,g,&bounds,p,scale,yaw,&distance)) {r->culled++;return 1;}
    float s=sinf(yaw),c=cosf(yaw);
    L3Vec3 cols[3];float scales[3]={scale.x,scale.y,scale.z};
    /* All meshes bake nonuniform scale into positions/normals at export. */
    if(scale.x<=0||fabsf(scale.x-scale.y)>1e-5f||fabsf(scale.x-scale.z)>1e-5f)return 0;
    for(unsigned k=0;k<3;k++) {
        L3Vec3 v=local_columns[k];
        cols[k]=(L3Vec3){(c*v.x+s*v.z)*scales[k],v.y*scales[k],(-s*v.x+c*v.z)*scales[k]};
    }
    L3Vec3 rows[3]={r->right,r->down,r->forward},rel=sub(p,g->camera.eye);
    gpu_geom_transform transform;
    for(unsigned a=0;a<3;a++) {
        for(unsigned b=0;b<3;b++)if(!gpu_geom_fixed(dot(rows[a],cols[b]),&transform.values[a*4+b]))return 0;
        if(!gpu_geom_fixed(dot(rows[a],rel),&transform.values[a*4+3]))return 0;
    }
    L3Vec3 l=l3_asset_light_direction;
    L3Vec3 local=unit((L3Vec3){dot(cols[0],l),dot(cols[1],l),dot(cols[2],l)});
    unsigned ambient=(unsigned)(l3_asset_ambient*256);
    gpu_geom_light light={(int16_t)(local.x*32767),(int16_t)(local.y*32767),(int16_t)(local.z*32767),ambient,256-ambient};
    if(!gpu_geom_set_transform(&r->gpu,&transform)||!gpu_geom_set_light(&r->gpu,&light))return 0;
    unsigned fog=rgb(l3_asset_fog_color[0],l3_asset_fog_color[1],l3_asset_fog_color[2]);
    unsigned zn=(unsigned)((1-r->near_z/l3_asset_fog_start)*65534);
    unsigned zf=(unsigned)((1-r->near_z/l3_asset_fog_end)*65534);
    L3Vec3 bound_rel=sub(object_point(bounds.center,scale,yaw,p),g->camera.eye);
    /* A conservative 5 m margin covers fixed-point depth/plane rounding.
     * Removing an ineffective fog flag enables G22r0's opaque pixel path. */
    unsigned fog_flag=dot(bound_rel,r->forward)+m->radius*scale.x>=l3_asset_fog_start-5?128:0;
    gpu_material mat={1|2|4|16|fog_flag,256,65535,256,256,256,zn,fog,(256U*65536)/(zf-zn)};
    if(!gpu_v1_material(&r->gpu,&mat))return 0;
    for(unsigned j=0;j<m->group_count;j++) {
        const L3AssetGroup *a=&m->groups[j];unsigned idx=(unsigned)(a-l3_asset_groups);
        if(idx>=l3_asset_group_count||a->material>=l3_asset_material_count)return 0;
        unsigned ti=l3_asset_materials[a->material].texture_index;
        if(ti>=l3_asset_texture_count)return 0;
        gpu_texture_level tex={r->textures[ti],128,128,256,GPU_RGB565,1,1,0};
        if(!gpu_v1_texture(&r->gpu,&tex)||!gpu_geom_draw(&r->gpu,r->meshes+idx,cull))return 0;
        r->draws++;r->triangles+=a->nf;
    }
    r->instances++;return !r->failed;
}
static int draw(L3Render *r,const L3Game *g,unsigned mesh,L3Vec3 p,L3Vec3 scale,float yaw,int cull) {
    return draw_ex(r,g,mesh,p,scale,yaw,0,0,cull);
}
int l3_render_frame(L3Render *r,const L3Game *g) {
    if(r->failed||!g->valid)return 0;
    active=r;r->commands=r->draws=r->triangles=r->instances=r->culled=0;
    r->forward=unit(sub(g->camera.target,g->camera.eye));
    /* World is right-handed Y-up; G3D1 is right/down/forward. Preserve
     * determinant +1, otherwise visible faces are culled and east is mirrored. */
    r->right=unit(cross(r->forward,(L3Vec3){0,1,0}));r->down=cross(r->forward,r->right);
    gpu_target target={PRODOCK_GPU_BASE+(r->frame&1)*r->page_bytes,PRODOCK_GPU_BASE+2*r->page_bytes,r->width,r->height,r->pitch,r->pitch};
    gpu_target background=target;background.color=PRODOCK_GPU_BASE+6U*1024*1024;
    /* The sky is generated once by the same GPU Gouraud operation as R1.
     * It is an angle-independent gradient, not a cached 3D camera image. */
    if(r->frame==0) {
    if(!gpu_v1_target(&r->gpu,&background)||!gpu_v1_scissor(&r->gpu,0,0,r->width,r->height))return 0;
    gpu_material sky={GPU_V1_GOURAUD,256,65535,256,256,256,0,0,0};
    gpu_vertex quad[4]={{0,0,0,0,0,0,0,0,0},{r->width,0,0,0,0,0,0,0,0},{r->width,r->height,0,0,0,0,0,0,0},{0,r->height,0,0,0,0,0,0,0}};
    for(unsigned i=0;i<4;i++) {const uint8_t *a=i<2?l3_asset_sky_zenith:l3_asset_sky_horizon;quad[i].r=a[0]*256/255;quad[i].g=a[1]*256/255;quad[i].b=a[2]*256/255;}
    if(!gpu_v1_material(&r->gpu,&sky)||!gpu_v1_quad(&r->gpu,quad))return 0;
    }
    if(!gpu_v1_target(&r->gpu,&target)||!gpu_v1_scissor(&r->gpu,0,0,r->width,r->height)||
       !gpu_v1_clear(&r->gpu,2,0,65535,0,0,r->width,r->height)||
       !gpu_v1_copy(&r->gpu,&background,0,0,0,0,r->width,r->height))return 0;
    gpu_geom_camera camera={(int32_t)(r->near_z*65536),(int32_t)(r->far_z*65536),(int32_t)(r->focal*65536),(int32_t)(r->focal*65536),r->width/2,r->height/2};
    if(!gpu_geom_set_camera(&r->gpu,&camera))return 0;
    if(r->frame==0)gpu_v1_invalidate(&r->gpu);
    for(unsigned i=0;i<l3_asset_instance_count;i++) {
        const L3AssetInstance *a=&l3_asset_instances[i];
        if(a->kind==L3_ASSET_ACTOR)continue;
        unsigned mesh=a->mesh_id;float distance;
        if(!visible(r,g,&l3_asset_meshes[mesh],a->position,a->scale,a->yaw,&distance)) {r->culled++;continue;}
        for(unsigned j=0;j<a->lod_count;j++)if(distance>a->lods[j].distance)mesh=a->lods[j].mesh_id;
        if(!strcmp(a->id,"windmill")) {
            if(!draw(r,g,l3_asset_windmill_static_mesh,a->position,a->scale,a->yaw,1))return 0;
            L3Vec3 pivot=object_point(l3_asset_windmill_rotor_pivot,a->scale,a->yaw,a->position);
            if(!draw_ex(r,g,l3_asset_windmill_rotor_mesh,pivot,a->scale,a->yaw,0,g->time*.45f,1))return 0;
            continue;
        }
        if(!draw(r,g,mesh,a->position,a->scale,a->yaw,1))return 0;
    }
    L3Vec3 hero=g->player.position;
    hero.y+=fabsf(sinf(g->player.walk_phase))*.035f*fminf(1,g->player.speed);
    float gait=sinf(g->player.walk_phase)*.65f*fminf(1,g->player.speed/4.5f);
    for(unsigned i=0;i<l3_asset_hero_part_count;i++) {
        const L3AssetPart *part=l3_asset_hero_parts+i;
        float angle=part->kind==1||part->kind==4?gait:part->kind==2||part->kind==3?-gait:part->kind==5?-.1f-sinf(g->time*2)*.07f:0;
        L3Vec3 pivot=object_point(part->pivot,(L3Vec3){1,1,1},g->player.yaw,hero);
        if(!draw_ex(r,g,part->mesh_id,pivot,(L3Vec3){1,1,1},g->player.yaw,angle,0,1))return 0;
    }
    for(unsigned i=0;i<l3_asset_collectible_count;i++)if(!(g->collected_mask&(1U<<i))) {
        L3Vec3 pos=l3_asset_collectibles[i];pos.y+=.16f*sinf(g->time*2+i);
        if(!draw(r,g,l3_asset_letter_mesh,pos,(L3Vec3){1,1,1},g->time*.9f+i,1))return 0;
    }
    flush(r);if(r->failed)return 0;
    struct prodock_scene scene={.base=target.color,.stride=target.stride,.format=7};
    double t=clock_seconds();if(!call(r,PRODOCK_PRESENT,&scene))return 0;r->present_seconds+=clock_seconds()-t;
    r->frame++;return 1;
}
int l3_render_dump(L3Render *r,const char *prefix) {
    char path[1024];if(snprintf(path,sizeof(path),"%s.memory",prefix)>=(int)sizeof(path))return 0;
    FILE *f=fopen(path,"wb");if(!f)return 0;int ok=fwrite(r->memory,1,r->uploaded,f)==r->uploaded;if(fclose(f))ok=0;
    if(snprintf(path,sizeof(path),"%s.json",prefix)>=(int)sizeof(path))return 0;
    f=fopen(path,"w");if(!f)return 0;
    fprintf(f,"{\"width\":%u,\"height\":%u,\"pitch\":%u,\"page_bytes\":%u,\"page\":%u,\"bytes\":%u,\"commands\":%u,\"draws\":%u,\"submitted_triangles\":%u,\"instances\":%u,\"culled_instances\":%u,\"hardware\":false}\n",r->width,r->height,r->pitch,r->page_bytes,(r->frame-1)&1,r->uploaded,r->commands,r->draws,r->triangles,r->instances,r->culled);
    if(fclose(f))ok=0;return ok;
}
int l3_render_close(L3Render *r) {
    int ok=!r->failed;
    if(!r->host&&r->fd>=0&&!r->failed) {
        struct prodock_geometry_info g;struct prodock_display_info d;
        if(!call(r,PRODOCK_GEOMETRY_INFO,&g)||!call(r,PRODOCK_DISPLAY_INFO,&d))ok=0;
        else {
            printf("LUMA3D_COUNTERS errors=%u underflows=%u fault=%u geometry_errors=%u vertices=%u triangles=%u slivers=%u frames=%u\n",d.errors-r->initial.errors,d.underflows-r->initial.underflows,d.faulted,g.errors-r->initial_geometry.errors,g.vertices-r->initial_geometry.vertices,g.triangles-r->initial_geometry.triangles,g.slivers-r->initial_geometry.slivers,r->frame);
            if(d.errors!=r->initial.errors||d.underflows!=r->initial.underflows||d.faulted||g.errors!=r->initial_geometry.errors)ok=0;
        }
    }
    if(r->memory) {if(r->host)free(r->memory);else munmap(r->memory,L3_MAP_BYTES);}
    free(r->meshes);free(r->textures);if(r->fd>=0)close(r->fd);if(r->display>=0)close(r->display);
    if(active==r)active=NULL;return ok;
}
