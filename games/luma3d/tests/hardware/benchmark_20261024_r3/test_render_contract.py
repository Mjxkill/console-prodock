#!/usr/bin/env python3
"""Actual renderer/simulation contract, ASAN/UBSAN, no hardware or CPU raster.

Compare capture bytes to the native ioctl path with fake devices for identical
physical game states. Check GPU descriptors and failure fencing; independently
compare the production collision adapter with the authored JSON world.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]

HARNESS = r'''
#define _POSIX_C_SOURCE 200809L
#include "luma3d_render.h"
#include "generated.h"
#include "prodock-validate.h"
#include <assert.h>
#include <errno.h>
#include <math.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <unistd.h>
/* Include the production implementation to exercise its private culler too. */
#include "render.c"

static unsigned display_width=800,display_height=480,submits,presents,fail_submit;
static unsigned camera_ready,matrix_rows,material_flags,target_base,draw_count;
static unsigned current_width,current_height,absent,failed_ioctls;
static unsigned sky_targets,sky_triangles,sky_planes,sky_material,sky_scissor;
static unsigned visible_targets,sky_copies,depth_clears;
static unsigned generic_commands,cli_mode,device_opens;
#define SKY_BASE (PRODOCK_GPU_BASE+6U*1024*1024)
static void *mapped;
static FILE *submitted;
int __real_open(const char *,int,...);
int __real_close(int);
void *__real_mmap(void *,size_t,int,int,int,off_t);
int __real_munmap(void *,size_t);
int __real_ioctl(int,unsigned long,...);
int __wrap_open(const char *name,int flags,...) {
    if(!strcmp(name,"/dev/prodock-gpu")){device_opens++;return 900;}
    if(!strcmp(name,"/dev/prodock-display")){device_opens++;return 901;}
    assert(strncmp(name,"/dev/",5)); /* Never fall through to a real device. */
    return __real_open(name,flags,0600);
}
int __wrap_close(int fd) {return fd==900||fd==901?0:__real_close(fd);}
void *__wrap_mmap(void *p,size_t bytes,int prot,int flags,int fd,off_t off) {
    if(fd!=900)return __real_mmap(p,bytes,prot,flags,fd,off);
    assert(!p&&bytes==L3_MAP_BYTES&&bytes<=PRODOCK_GPU_BYTES&&off==0);
    assert(prot==(PROT_READ|PROT_WRITE)&&flags==MAP_SHARED&&!mapped);
    return mapped=calloc(1,bytes);
}
int __wrap_munmap(void *p,size_t bytes) {
    if(p!=mapped)return __real_munmap(p,bytes);
    assert(bytes==L3_MAP_BYTES);free(mapped);mapped=NULL;return 0;
}
static void descriptor(const uint32_t *c) {
    assert(prodock_command(c)==0);
    unsigned op=c[0]>>24;
    /* Only this one-time, GPU-generated Gouraud background may use scratch.
     * Meshes, camera, clear, texture and COPY destination stay on display pages. */
    if(target_base==SKY_BASE&&op!=22)
        assert(op==23||op==25||op==26||op==27);
    if(op==22) {
        current_width=c[3]>>16;current_height=c[3]&65535;camera_ready=0;
        assert(current_width==display_width/2&&current_height==display_height/2);
        unsigned page=display_width==800?1U<<20:2U<<20;
        assert(c[2]==PRODOCK_GPU_BASE+2*page);
        assert((c[4]>>16)==display_width*2&&(c[4]&65535)==display_width*2);
        assert(display_width*2*display_height<=page);
        assert(c[2]-PRODOCK_GPU_BASE+current_height*display_width*2<=L3_ASSET_OFFSET);
        /* Whole Z page and the full scratch pitch range must be disjoint,
         * including at 720p, where Z occupies [4 MiB, 6 MiB). */
        assert(PRODOCK_GPU_BASE+3*page<=SKY_BASE);
        assert((uint64_t)SKY_BASE+(uint64_t)current_height*display_width*2<=PRODOCK_GPU_BASE+L3_ASSET_OFFSET);
        if(c[1]==SKY_BASE) {
            assert(!presents&&!target_base&&!sky_targets&&!visible_targets);
            sky_targets++;
        } else {
            assert(c[1]==PRODOCK_GPU_BASE+(presents&1)*page);
            assert(sky_targets==1&&sky_triangles==2&&!sky_planes);
            assert(visible_targets==presents);visible_targets++;
        }
        target_base=c[1];
    } else if(op==23&&target_base==SKY_BASE) {
        assert(!sky_scissor&&!sky_material&&!sky_triangles);
        assert(!c[1]&&c[2]==((current_width<<16)|current_height));sky_scissor=1;
    } else if(op==25) {
        material_flags=c[1];
        if(target_base==SKY_BASE) {
            assert(sky_scissor&&!sky_material&&!sky_triangles);
            assert(c[1]==GPU_V1_GOURAUD&&c[2]==256&&c[3]==65535);
            assert(c[4]==(256U|(256U<<9)|(256U<<18))&&!c[5]&&!c[6]);sky_material=1;
        }
    } else if(op==26&&target_base==SKY_BASE) {
        unsigned plane=c[0]&0xffffff;
        assert(sky_material&&sky_triangles<2&&plane>=4&&plane<=6);
        assert(!(sky_planes&(1U<<plane)));sky_planes|=1U<<plane;
    } else if(op==27) {
        assert(target_base==SKY_BASE&&sky_material&&sky_triangles<2&&sky_planes==112);
        assert(!c[1]);
        assert(c[2]==((current_width<<16)|(sky_triangles?current_height:0)));
        assert(c[3]==((sky_triangles?0:current_width)<<16|current_height));
        sky_triangles++;sky_planes=0;
    } else if(op==28) {
        assert(target_base!=SKY_BASE&&visible_targets==presents+1&&depth_clears==presents);
        assert(c[1]==2&&!c[2]&&c[3]==65535&&!c[4]&&c[5]==((current_width<<16)|current_height));
        depth_clears++;
    } else if(op==29) {
        assert(target_base!=SKY_BASE&&sky_triangles==2&&depth_clears==presents+1);
        assert(sky_copies==presents&&!camera_ready);
        assert(c[1]==SKY_BASE&&c[2]==((current_width<<16)|current_height)&&c[3]==display_width*2);
        assert(!c[4]&&!c[5]&&c[6]==c[2]);
        assert((uint64_t)c[1]+(uint64_t)(c[2]&65535)*c[3]<=PRODOCK_GPU_BASE+L3_ASSET_OFFSET);
        sky_copies++;
    }
    else if(op==31)matrix_rows|=1U<<c[1];
    else if(op==32) {
        assert(target_base!=SKY_BASE&&sky_copies==presents+1);
        assert((c[6]>>16)==current_width&&(c[6]&65535)==current_height);
        assert((c[5]>>16)==current_width/2&&(c[5]&65535)==current_height/2);
        camera_ready=1;
    } else if(op==34) {
        assert(target_base!=SKY_BASE&&sky_copies==presents+1);
        assert(camera_ready&&matrix_rows==7&&!(material_flags&GPU_V1_GOURAUD));
        assert(c[1]>=PRODOCK_GPU_BASE+L3_ASSET_OFFSET&&c[2]>=PRODOCK_GPU_BASE+L3_ASSET_OFFSET);
        assert(c[1]+(c[3]>>16)*32<=PRODOCK_GPU_BASE+L3_MAP_BYTES);
        assert(c[2]+(c[3]&65535)*32<=PRODOCK_GPU_BASE+L3_MAP_BYTES);
        assert(c[4]==1);draw_count++;
    }
}
int __wrap_ioctl(int fd,unsigned long op,...) {
    va_list args;va_start(args,op);void *value=va_arg(args,void *);va_end(args);
    if(fd!=900&&fd!=901)return __real_ioctl(fd,op,value);
    if(op==PRODOCK_INFO) {
        *(struct prodock_info *)value=(struct prodock_info){.abi=1,.width=display_width,
            .height=display_height,.caps=511,.memory_base=PRODOCK_GPU_BASE,.memory_bytes=PRODOCK_GPU_BYTES};
    } else if(op==PRODOCK_GEOMETRY_INFO) {
        if(absent){errno=EOPNOTSUPP;return -1;}
        *(struct prodock_geometry_info *)value=(struct prodock_geometry_info){.signature=PRODOCK_GEOMETRY_SIGNATURE,
            .vertices=draw_count*3,.triangles=draw_count,.cycles=0xffff0000U+draw_count*1000003U};
    } else if(op==PRODOCK_DISPLAY_INFO)
        *(struct prodock_display_info *)value=(struct prodock_display_info){
            .feed_us=submits*3,.wait_us=submits*7,.cache_us=submits*2,.present_us=presents*11};
    else if(op==PRODOCK_LAYOUT)assert(((struct prodock_layout *)value)->mode==PRODOCK_GAME);
    else if(op==PRODOCK_SUBMIT) {
        struct prodock_batch *b=value;assert(b->count&&b->count<=64&&!b->reserved);
        submits++;
        if(submits==fail_submit){failed_ioctls++;errno=EIO;return -1;}
        assert(!failed_ioctls);
        for(unsigned i=0;i<b->count;i++) {
            if(generic_commands)assert(!prodock_command(b->commands[i]));
            else descriptor(b->commands[i]);
        }
        if(submitted)assert(fwrite(b->commands,32,b->count,submitted)==b->count);
    } else if(op==PRODOCK_PRESENT) {
        const struct prodock_scene *s=value;assert(!failed_ioctls);
        assert(prodock_scene_valid_for(s,display_width,display_height)==0);
        assert(s->base==target_base&&s->format==7&&s->stride==display_width*2);
        unsigned page=display_width==800?1U<<20:2U<<20;
        assert(s->base==PRODOCK_GPU_BASE+(presents&1)*page&&s->base!=SKY_BASE);
        assert(camera_ready&&visible_targets==presents+1&&sky_copies==presents+1&&depth_clears==presents+1);
        assert(!s->layers_enabled&&!s->sprites_enabled);presents++;
        if(cli_mode)printf("CLI_FRAME index=%u bytes=%ld batches=%u\n",presents,ftell(submitted),submits);
    } else assert(0);
    return 0;
}
static void reset_io(void) {
    submits=presents=fail_submit=camera_ready=matrix_rows=material_flags=target_base=draw_count=absent=failed_ioctls=0;
    sky_targets=sky_triangles=sky_planes=sky_material=sky_scissor=visible_targets=sky_copies=depth_clears=0;
    generic_commands=cli_mode=device_opens=0;
    assert(!mapped);submitted=NULL;
}
static void check_assets(const L3Render *r) {
    assert(r->uploaded<=L3_MAP_BYTES);
    for(unsigned j=0;j<l3_asset_group_count;j++) {
        const L3AssetGroup *a=&l3_asset_groups[j];
        assert(a->nv&&a->nv<=256&&a->nf&&a->material<l3_asset_material_count&&!a->reserved);
        const gpu_geom_mesh *m=&r->meshes[j];assert(!(m->vertices&31)&&!(m->faces&31));
        assert(!memcmp(r->memory+m->vertices-PRODOCK_GPU_BASE,a->vertices,a->nv*32));
        assert(!memcmp(r->memory+m->faces-PRODOCK_GPU_BASE,a->faces,a->nf*32));
        for(unsigned i=0;i<a->nv;i++)for(unsigned k=3;k<8;k++)assert(!a->vertices[i*8+k]);
        for(unsigned i=0;i<a->nf;i++) {
            const uint32_t *f=a->faces+i*8;
            for(unsigned k=0;k<3;k++)assert(((f[0]>>(8*k))&255)<a->nv);
            assert(!(f[0]>>26)&&!(f[5]>>16)&&!(f[6]>>27)&&!f[7]);
            for(unsigned k=0;k<3;k++)assert(((f[6]>>(9*k))&511)<=256);
            double nx=(int16_t)(f[4]>>16)/32767.,ny=(int16_t)f[4]/32767.,nz=(int16_t)f[5]/32767.;
            assert(fabs(nx*nx+ny*ny+nz*nz-1)<.0002);
        }
    }
    for(unsigned j=0;j<l3_asset_mesh_count;j++) {
        const L3AssetMesh *m=&l3_asset_meshes[j];assert(m->radius>=0&&isfinite(m->radius));
        for(unsigned k=0;k<m->group_count;k++) {
            const L3AssetGroup *g=m->groups+k;
            assert(g>=l3_asset_groups&&g<l3_asset_groups+l3_asset_group_count);
            for(unsigned v=0;v<g->nv;v++) {
                double x=(int32_t)g->vertices[v*8]/65536.-m->center.x;
                double y=(int32_t)g->vertices[v*8+1]/65536.-m->center.y;
                double z=(int32_t)g->vertices[v*8+2]/65536.-m->center.z;
                assert(sqrt(x*x+y*y+z*z)<=m->radius+.0001);
            }
        }
    }
    for(unsigned j=0;j<l3_asset_instance_count;j++) {
        const L3AssetInstance *i=&l3_asset_instances[j];assert(i->mesh_id<l3_asset_mesh_count&&i->lod_count<=2);
        /* Current G3D1 light path rotates normals only; bake anisotropic scale. */
        assert(i->scale.x>0&&fabsf(i->scale.x-i->scale.y)<.00001f&&fabsf(i->scale.x-i->scale.z)<.00001f);
        for(unsigned k=0;k<i->lod_count;k++)assert(i->lods[k].mesh_id<l3_asset_mesh_count&&i->lods[k].distance>0);
    }
}
static void culling(L3Render *r) {
    L3Game g={0};L3AssetMesh m={.radius=1};L3Vec3 one={1,1,1};float d;
    r->forward=(L3Vec3){0,0,1};r->right=(L3Vec3){1,0,0};r->down=(L3Vec3){0,-1,0};
    assert(visible(r,&g,&m,(L3Vec3){0,0,2},one,0,&d));
    assert(!visible(r,&g,&m,(L3Vec3){0,0,-2},one,0,&d));
    assert(!visible(r,&g,&m,(L3Vec3){0,0,r->far_z+2},one,0,&d));
    assert(!visible(r,&g,&m,(L3Vec3){100,0,10},one,0,&d));
    assert(!visible(r,&g,&m,(L3Vec3){0,100,10},one,0,&d));
    /* Boundary sphere intersects the side plane and must survive culling. */
    float sx=r->width*.5f/r->focal;
    assert(visible(r,&g,&m,(L3Vec3){10*sx+.5f,0,10},one,0,&d));
}
static FILE *sequence(int native,unsigned wide,unsigned count,unsigned *first_batches) {
    reset_io();display_width=wide?1280:800;display_height=wide?720:480;
    FILE *file=tmpfile();assert(file);if(native)submitted=file;
    L3World world;L3Game game;L3Render r;l3_world_init(&world);assert(l3_game_init(&game,&world,1));
    assert(l3_render_open(&r,!native,wide));check_assets(&r);culling(&r);
    uint8_t *snapshot=malloc(r.uploaded);assert(snapshot);memcpy(snapshot,r.memory,r.uploaded);
    if(!native)r.capture=file;
    unsigned maximum_draws=0,maximum_triangles=0;
    for(unsigned i=0;i<count;i++) {
        if(i)l3_game_step(&game,NULL,1.0f/60);
        assert(l3_render_frame(&r,&game));assert(r.frame==i+1);
        assert(r.commands&&r.draws&&r.triangles&&isfinite(game.camera.eye.x));
        if(r.draws>maximum_draws)maximum_draws=r.draws;
        if(r.triangles>maximum_triangles)maximum_triangles=r.triangles;
        assert(fabsf(dot(r.right,r.forward))<.0001f&&fabsf(dot(r.down,r.forward))<.0001f);
        if(i==0&&native)*first_batches=submits;
    }
    assert(!memcmp(snapshot,r.memory,r.uploaded)); /* No CPU framebuffer writes. */
    free(snapshot);r.capture=NULL;assert(l3_render_close(&r));assert(!mapped);
    if(native) {
        assert(presents==count&&draw_count>count);
        assert(sky_targets==1&&sky_triangles==2&&sky_copies==count&&depth_clears==count);
        printf("COMMAND_BUDGET display=%ux%u max_draws=%u max_input_triangles=%u no_timing_claim=1\n",display_width,display_height,maximum_draws,maximum_triangles);
    }
    assert(!fflush(file));rewind(file);return file;
}
static void failures(unsigned batches) {
    const unsigned positions[]={1,(batches+1)/2,batches};
    for(unsigned i=0;i<3;i++) {
        reset_io();display_width=800;display_height=480;fail_submit=positions[i];
        L3Render r;L3World w;L3Game g;l3_world_init(&w);assert(l3_game_init(&g,&w,1));
        assert(l3_render_open(&r,0,0));assert(!l3_render_frame(&r,&g));
        assert(r.failed&&!r.frame&&!presents&&failed_ioctls==1&&submits==fail_submit);
        assert(!l3_render_frame(&r,&g)&&submits==fail_submit&&!presents);
        assert(!l3_render_close(&r)&&!mapped);
    }
    reset_io();absent=1;L3Render r;assert(!l3_render_open(&r,0,0));
    assert(!submits&&!presents&&!mapped);l3_render_close(&r);
}
static void physical_route(void) {
    L3World w;L3Game g;l3_world_init(&w);assert(l3_game_init(&g,&w,1));
    unsigned frames=0;float worst=0;
    while(g.completed_routes<2&&frames<36000) {
        L3Vec3 p=g.player.position;l3_game_step(&g,NULL,1.0f/60);frames++;
        assert(hypotf(g.player.position.x-p.x,g.player.position.z-p.z)<.12f);
        assert(!w.blocked(w.context,g.player.position.x,g.player.position.y,g.player.position.z,.3f,1.65f));
        worst=fmaxf(worst,g.autopilot_stuck_seconds);assert(worst<=3);
    }
    assert(g.completed_routes>=2&&g.objective_complete&&g.collected_count==w.collectible_count);
    printf("PRODUCTION_ROUTE_PASS frames=%u letters=%u legs=%u worst_stuck=%.4f\n",frames,g.collected_count,g.completed_routes,worst);
}
static float flat(void *ctx,float x,float z) {(void)ctx;(void)x;(void)z;return 0;}
static void controls(void) {
    reset_io();L3Render r;assert(l3_render_open(&r,1,0));
    for(unsigned i=0;i<4;i++) {
        L3World w={.height=flat,.max_x=160,.max_z=160,.spawn={80,0,80},.spawn_yaw=i*1.57079632679f};
        L3Game g;assert(l3_game_init(&g,&w,0));assert(l3_render_frame(&r,&g));
        /* G3D1 cull=1 and the outward mesh winding require a positive basis. */
        assert(dot(cross(r.right,r.down),r.forward)>.9999f);
        L3Vec3 p=g.player.position,right=r.right;L3Input in={.move_x=1};l3_game_step(&g,&in,1.0f/60);
        assert(dot(sub(g.player.position,p),right)>0);
    }assert(l3_render_close(&r));puts("CAMERA_RIGHT_CONTROL_PASS four headings");
}
/* Exercise the public command stream, including identical state on opposite
 * sides of a successful SUBMIT. The expected stream is explicitly authored;
 * it is not generated with the renderer's cache predicate. */
static gpu_command expected_commands[512];
static unsigned expected_count;
static void offer(gpu_command c,int emitted) {
    assert(!prodock_command(c.words));
    if(emitted){assert(expected_count<512);expected_commands[expected_count++]=c;}
    emit(&c);
}
static void state_cache_contract(void) {
    const gpu_command target={{22U<<24,PRODOCK_GPU_BASE,PRODOCK_GPU_BASE+2*1048576,400U<<16|240,1600U<<16|1600,0,0,0}};
    const gpu_command camera={{32U<<24,32768,210U*65536,328U*65536,328U*65536,200U<<16|120,400U<<16|240,0}};
    gpu_command states[6]={
        {{31U<<24,0,65536,0,0,0,0,0}},{{31U<<24,1,0,65536,0,0,0,0}},
        {{31U<<24,2,0,0,65536,0,0,0}},{{33U<<24,0,32767,128U<<16|128,0,0,0,0}},
        {{25U<<24,0,256,65535,256U|256U<<9|256U<<18,0,0,0}},
        {{24U<<24,PRODOCK_GPU_BASE+L3_ASSET_OFFSET,128U<<16|128,256,0,0,0,0}}};
    const gpu_command draw={{34U<<24,PRODOCK_GPU_BASE+L3_ASSET_OFFSET+32768,PRODOCK_GPU_BASE+L3_ASSET_OFFSET+32864,3U<<16|1,1,0,0,0}};
    const gpu_command copy={{29U<<24,SKY_BASE,400U<<16|240,1600,0,0,400U<<16|240,0}};
    const gpu_command invalidate={{30U<<24,0,0,0,0,0,0,0}};
    const gpu_command plane={{26U<<24|4,0,0,0,0,0,0,0}};
    reset_io();generic_commands=1;expected_count=0;
    L3Render r={.fd=900,.display=901};active=&r;
    FILE *capture=tmpfile();submitted=tmpfile();assert(capture&&submitted);r.capture=capture;
    offer(target,1);offer(camera,1);
    for(unsigned i=0;i<6;i++)offer(states[i],1);
    for(unsigned i=0;i<6;i++)offer(states[i],0);
    flush(&r);assert(submits==1);
    for(unsigned i=0;i<6;i++)offer(states[i],0);
    offer(draw,1);offer(draw,1);
    for(unsigned i=0;i<6;i++)offer(states[i],0);
    offer(copy,1);offer(invalidate,1);
    for(unsigned i=0;i<6;i++)offer(states[i],0);
    /* Planes, CAMERA and DRAW are deliberately never cached. */
    offer(plane,1);offer(plane,1);offer(camera,1);
    for(unsigned i=0;i<6;i++) {
        gpu_command changed=states[i];
        if(i<3)changed.words[5]=65536;
        else if(i==3)changed.words[3]++;
        else if(i==4)changed.words[3]--;
        else changed.words[1]+=32;
        offer(changed,1);offer(changed,0);offer(states[i],1);
    }
    while(r.batch.count<64)offer(invalidate,1);
    unsigned before=submits;
    offer(states[3],0);assert(submits==before&&r.batch.count==64);
    gpu_command changed=states[3];changed.words[3]++;
    offer(changed,1);assert(submits==before+1&&r.batch.count==1);
    offer(states[3],1);
    /* TARGET forces an explicit new state set, even if its bytes are equal. */
    offer(target,1);offer(camera,1);
    for(unsigned i=0;i<6;i++)offer(states[i],1);
    offer(draw,1);flush(&r);assert(!r.failed&&r.total_commands==expected_count);
    FILE *streams[]={capture,submitted};
    for(unsigned k=0;k<2;k++) {
        assert(!fflush(streams[k]));rewind(streams[k]);gpu_command c;
        for(unsigned i=0;i<expected_count;i++){assert(fread(&c,32,1,streams[k])==1);assert(!memcmp(&c,&expected_commands[i],32));}
        assert(fgetc(streams[k])==EOF);fclose(streams[k]);
    }
    active=NULL;submitted=NULL;
    /* A failed boundary flush must not append or publish the new descriptor,
     * even when later callers request previously cached state. */
    reset_io();generic_commands=1;fail_submit=1;r=(L3Render){.fd=900,.display=901};active=&r;
    emit(&states[3]);while(r.batch.count<64)emit(&invalidate);
    emit(&changed);assert(r.failed&&submits==1&&r.total_commands==64&&!presents);
    emit(&states[3]);emit(&draw);flush(&r);assert(submits==1&&r.total_commands==64);
    struct prodock_scene scene={0};assert(!call(&r,PRODOCK_PRESENT,&scene)&&!presents);active=NULL;
    /* Geometry reserved fields, out-of-range matrix rows and invalid texture
     * addresses are rejected before cache indexing. Legacy raster reserved
     * words are not validated by prodock_command; the producer's public API
     * supplies zeroes there. ASAN/UBSAN exercise the dangerous matrix row. */
    for(unsigned i=0;i<3;i++) {
        reset_io();generic_commands=1;r=(L3Render){.fd=900,.display=901};active=&r;
        gpu_command bad=states[i==0?0:i==1?3:5];
        if(!i)bad.words[1]=3;else if(i==1)bad.words[7]=1;else bad.words[1]=1;
        emit(&bad);emit(&draw);flush(&r);
        assert(r.failed&&!r.total_commands&&!submits&&!presents);active=NULL;
    }
    puts("STATE_CACHE_PASS equal/change/restore TARGET DRAW COPY planes batch-boundary errors");
}
#define main luma_cli_main
#include "main.c"
#undef main
int main(int argc,char **argv) {
    if(argc>1&&!strcmp(argv[1],"--cli")) {
        reset_io();cli_mode=1;
        for(int i=2;i<argc;i++)if(!strcmp(argv[i],"--720p")){display_width=1280;display_height=720;}
        const char *path=getenv("L3_TEST_STREAM");assert(path);submitted=fopen(path,"wb");assert(submitted);
        const char *failure=getenv("L3_TEST_FAIL_SUBMIT");if(failure)fail_submit=(unsigned)strtoul(failure,NULL,10);
        int code=luma_cli_main(argc-1,argv+1);
        printf("CLI_IO presents=%u submits=%u device_opens=%u failed_ioctls=%u\n",presents,submits,device_opens,failed_ioctls);
        assert(!mapped);fclose(submitted);return code;
    }
    unsigned first=0;
    for(unsigned wide=0;wide<2;wide++) {
        unsigned count=wide?400:600,batches=0;
        FILE *host=sequence(0,wide,count,&batches),*native=sequence(1,wide,count,&batches);
        uint64_t bytes=0,hash=1469598103934665603ULL;int a,b;
        do {a=fgetc(host);b=fgetc(native);assert(a==b);if(a!=EOF){bytes++;hash=(hash^(unsigned)a)*1099511628211ULL;}}while(a!=EOF);
        fclose(host);fclose(native);if(!wide)first=batches;
        printf("RENDER_CONTRACT_PASS display=%ux%u states=%u bytes=%llu fnv64=%016llx\n",display_width,display_height,count,(unsigned long long)bytes,(unsigned long long)hash);
    }
    failures(first);puts("NATIVE_FAILURE_NO_PRESENT_PASS first/middle/final batch and absent G3D1");
    physical_route();controls();state_cache_contract();return 0;
}
'''

QUERY = r'''
#include "luma3d_render.h"
static L3World w;
void init_queries(void){l3_world_init(&w);}
float query_height(float x,float z){return w.height(w.context,x,z);}
int query_blocked(float x,float y,float z,float r,float h){return w.blocked(w.context,x,y,z,r,h);}
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cli_contract(out):
    """Run the production CLI against fake ioctl devices, never real hardware."""
    records = []

    def invoke(name, arguments, expected=0, failure=None):
        stream = out / (name+'.commands')
        env = dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1',
                   L3_TEST_STREAM=str(stream))
        if failure is not None:
            env['L3_TEST_FAIL_SUBMIT'] = str(failure)
        result = subprocess.run([str(out/'harness'), '--cli', *arguments], env=env,
                                text=True, capture_output=True, timeout=60)
        (out/(name+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode == expected, (name, result.returncode, result.stdout, result.stderr)
        return result.stdout, stream.read_bytes()

    def fields(line):
        return dict(re.findall(r'(\w+)=([^\s]+)', line))

    for wide in (False, True):
        for pose, warmup, count in ((0, 3, 5), (1600, 2, 4)):
            args = ['--benchmark', '--frames', str(count), '--advance', str(pose)]
            if warmup != 3:
                args += ['--warmup', str(warmup)]
            if wide:
                args += ['--720p']
            name = f'cli_{1280 if wide else 800}_{pose}'
            output, raw = invoke(name, args)
            result = fields(next(s for s in output.splitlines() if s.startswith('LUMA3D_RESULT ')))
            io = fields(next(s for s in output.splitlines() if s.startswith('CLI_IO ')))
            frames = [fields(s) for s in output.splitlines() if s.startswith('CLI_FRAME ')]
            assert int(result['frames']) == count and int(result['warmup']) == warmup
            assert result['benchmark'] == result['hardware'] == '1'
            assert int(io['presents']) == len(frames) == count+warmup
            assert io['failed_ioctls'] == '0'
            offsets = [0]+[int(f['bytes']) for f in frames]
            batches = [0]+[int(f['batches']) for f in frames]
            assert offsets[-1] == len(raw)
            assert int(result['commands']) == (len(raw)-offsets[warmup])//32
            assert int(result['batches']) == batches[-1]-batches[warmup]
            counters = fields(next(s for s in output.splitlines() if s.startswith('LUMA3D_BENCHMARK_COUNTERS ')))
            measured = list(struct.iter_unpack('<8I', raw[offsets[warmup]:]))
            draws = sum(c[0] >> 24 == 34 for c in measured)
            assert int(counters['cycles']) == (draws*1000003) & 0xffffffff
            assert int(counters['vertices']) == draws*3
            assert int(counters['raster_triangles']) == draws
            for key, multiplier in [('feed_us', 3), ('wait_us', 7), ('cache_us', 2)]:
                assert int(counters[key]) == (batches[-1]-batches[warmup])*multiplier
            assert int(counters['present_us']) == count*11
            by_page = {}
            for i in range(warmup, count+warmup):
                commands = raw[offsets[i]:offsets[i+1]]
                target = struct.unpack_from('<8I', commands)
                assert target[0] >> 24 == 22
                page = target[1]
                if page in by_page:
                    assert commands == by_page[page], (name, i, 'pose/animation or state drift')
                by_page[page] = commands
            assert len(by_page) == 2
            # A failure in the first measured batch must not publish a partial
            # frame, nor report successful completion after a valid warmup.
            failed, _ = invoke(name+'_failure', args, expected=1, failure=batches[warmup]+1)
            failed_result = fields(next(s for s in failed.splitlines() if s.startswith('LUMA3D_RESULT ')))
            failed_io = fields(next(s for s in failed.splitlines() if s.startswith('CLI_IO ')))
            assert failed_result['frames'] == '0' and int(failed_io['presents']) == warmup
            assert failed_io['failed_ioctls'] == '1'
            records.append(dict(display_width=1280 if wide else 800, pose=pose,
                                warmup=warmup, measured_frames=count,
                                presents=len(frames), measured_commands=int(result['commands']),
                                stable_commands_per_page=True, measured_failure_fenced=True))
    invalid = [
        ['--benchmark'], ['--benchmark', '--frames', '0'],
        ['--warmup', '3'], ['--benchmark', '--frames', '1', '--warmup', '1'],
        ['--benchmark', '--frames', '1', '--warmup', '0'],
        ['--benchmark', '--frames', '1', '--warmup'], ['--frames'],
        ['--frames', '-1'], ['--frames', '1000001'], ['--frames', '1x'],
        ['--advance', '-1'], ['--advance', '1000001'],
        ['--benchmark', '--host', '--frames', '1', '--capture', 'unused'],
        ['--not-an-option'],
    ]
    for i, args in enumerate(invalid):
        output, raw = invoke(f'cli_invalid_{i:02}', args, expected=2)
        io = fields(next(s for s in output.splitlines() if s.startswith('CLI_IO ')))
        assert not raw and io['device_opens'] == io['submits'] == io['presents'] == '0'
    return dict(passed=True, fake_devices=True, hardware_validation=False,
                cases=records, invalid_argument_cases=len(invalid))


def oracle_queries(lib):
    scene = json.loads((ROOT / 'world/scene.json').read_text())
    heights = json.loads((ROOT / 'world/heightfield.json').read_text())['heights']

    def ground(x, z):
        x, z = min(159.9999, max(0, x)), min(159.9999, max(0, z))
        ix, iz = int(x/2), int(z/2)
        u, v = x/2-ix, z/2-iz
        a, b, c, d = heights[iz][ix], heights[iz][ix+1], heights[iz+1][ix+1], heights[iz+1][ix]
        return a+(b-a)*u+(c-b)*v if u >= v else a+(c-d)*u+(d-a)*v

    def bridge(x, z, radius):
        for c in scene['colliders']:
            if c['kind'] != 'walkable_bridge':
                continue
            dx, dz, yaw = x-c['x'], z-c['z'], c['yaw']
            u, v = math.cos(yaw)*dx-math.sin(yaw)*dz, math.sin(yaw)*dx+math.cos(yaw)*dz
            if abs(u) <= c['length']/2 and abs(v) <= c['width']/2-radius:
                return c['y']+c['arch_height']*math.sin(math.pi*(u/c['length']+.5))
        return None

    def height(x, z):
        deck = bridge(x, z, 0)
        return max(ground(x, z), deck) if deck is not None else ground(x, z)

    def blocked(x, y, z, radius, tall):
        for c in scene['colliders']:
            if c['kind'] == 'walkable_bridge' or y >= c['max_y'] or y+tall <= c['min_y']:
                continue
            if c['kind'] == 'circle' and math.hypot(x-c['x'], z-c['z']) < radius+c['radius']:
                return True
            if c['kind'] == 'box':
                dx, dz, yaw = x-c['x'], z-c['z'], c['yaw']
                if abs(math.cos(yaw)*dx-math.sin(yaw)*dz) < c['length']/2+radius and abs(math.sin(yaw)*dx+math.cos(yaw)*dz) < c['width']/2+radius:
                    return True
        deck = bridge(x, z, radius)
        if deck is not None and y >= deck-.1:
            return False
        for w in scene['water_zones']:
            if w['level']-ground(x, z) <= .65 or y >= w['level']+.2:
                continue
            if w['kind'] == 'ellipse':
                if ((x-w['x'])/(w['rx']+.3))**2+((z-w['z'])/(w['rz']+.3))**2 < 1:
                    return True
            elif w['kind'] == 'ribbon':
                for a, b in zip(w['points'], w['points'][1:]):
                    dx, dz = b[0]-a[0], b[1]-a[1]
                    d2 = dx*dx+dz*dz
                    t = min(1, max(0, ((x-a[0])*dx+(z-a[1])*dz)/d2)) if d2 else 0
                    if math.hypot(x-a[0]-t*dx, z-a[1]-t*dz) < w['width']/2+radius:
                        return True
        return False

    lib.init_queries()
    lib.query_height.argtypes = [ctypes.c_float]*2
    lib.query_height.restype = ctypes.c_float
    lib.query_blocked.argtypes = [ctypes.c_float]*5
    lib.query_blocked.restype = ctypes.c_int
    rng = random.Random(0x47334431)
    maximum_error = 0
    for _ in range(20000):
        x, z = [ctypes.c_float(rng.uniform(-1, 161)).value for _ in range(2)]
        expected = height(x, z)
        actual = lib.query_height(x, z)
        maximum_error = max(maximum_error, abs(actual-expected))
        assert abs(actual-expected) < .00015, (x, z, actual, expected)
        y = ctypes.c_float(actual+rng.uniform(-.3, 3)).value
        radius, tall = (.3, 1.65) if rng.random() < .5 else (.2, .4)
        assert bool(lib.query_blocked(x, y, z, radius, tall)) == blocked(x, y, z, radius, tall), (x, y, z)
    meshes = json.loads((ROOT / 'world/meshes.json').read_text())['meshes']
    terrain_faces, maximum_mesh_error = 0, 0
    for instance in scene['instances']:
        if instance['kind'] != 'terrain':
            continue
        assert instance['scale'] == [1, 1, 1] and instance['yaw'] == 0
        mesh = meshes[instance['mesh']]
        for face in mesh['faces']:
            if abs(face['normal'][1]) < .000001:
                continue  # Vertical LOD seam skirts are below the walking surface.
            assert face['normal'][1] > 0, (instance['id'], face['normal'])
            points = [mesh['vertices'][i] for i in face['indices']]
            center = [sum(p[k] for p in points)/3+instance['position'][k] for k in range(3)]
            error = abs(center[1]-ground(center[0], center[2]))
            maximum_mesh_error = max(maximum_mesh_error, error)
            assert error < .00015, (instance['id'], face['indices'], error)
            terrain_faces += 1
    return {'queries': 20000, 'maximum_height_error': maximum_error,
            'terrain_lod0_faces': terrain_faces, 'maximum_mesh_collision_error': maximum_mesh_error}


def main():
    global ROOT, REPO
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-repo', type=Path,
                        help='Complete frozen source tree, with games/luma3d and fw_console')
    parser.add_argument('--renderer-only', action='store_true',
                        help='Frozen candidate C/CLI contract only; no independent JSON terrain oracle')
    args = parser.parse_args()
    if args.renderer_only and not args.source_repo:
        parser.error('--renderer-only requires an explicit frozen --source-repo')
    if args.source_repo:
        REPO = args.source_repo.resolve()
        ROOT = REPO/'games/luma3d'
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    paths = [ROOT / p for p in ['src/render.c', 'src/main.c', 'src/world.c', 'src/game.c',
        'include/luma3d_render.h', 'include/luma3d_game.h', 'world/generated.h', 'world/data.c',
        'world/scene.json', 'world/heightfield.json', 'world/meshes.json']]
    if (ROOT/'world/export_c.py').exists():
        paths += [ROOT/'world/export_c.py']
    paths += [REPO / p for p in ['fw_console/gpu_v1.c', 'fw_console/gpu_geometry.c',
                                'fw_console/gpu.h', 'fw_console/gpu_v1.h', 'fw_console/gpu_geometry.h',
                                'linux/drivers/prodock-uapi.h', 'linux/drivers/prodock-validate.h']]
    inputs = {str(p.relative_to(REPO)): sha(p) for p in paths}
    report = {'passed': False, 'hardware_validation': False, 'cpu_rasterization': False,
              'pixel_oracle': False, 'inputs': inputs, 'test_sha256': sha(Path(__file__))}
    report['source_repo'] = str(REPO)
    report['scope'] = 'C renderer and CLI only' if args.renderer_only else 'C renderer, CLI and JSON terrain/collision'
    (out / 'harness.c').write_text(HARNESS)
    (out / 'queries.c').write_text(QUERY)
    include = ['-I'+str(ROOT / p) for p in ['include', 'world', 'src']]
    include += ['-I'+str(REPO / p) for p in ['fw_console', 'linux/drivers']]
    flags = ['-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
             '-ffp-contract=off', '-ffunction-sections', '-fdata-sections', *include]

    def run(name, command):
        result = subprocess.run(list(map(str, command)), text=True, capture_output=True,
                                env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0', UBSAN_OPTIONS='halt_on_error=1'))
        (out / (name+'.log')).write_text(result.stdout+result.stderr)
        print(result.stdout+result.stderr, end='')
        result.check_returncode()

    try:
        common = [ROOT/'src/game.c', ROOT/'src/world.c', ROOT/'world/data.c']
        run('build', ['cc', *flags, '-fsanitize=address,undefined', out/'harness.c', *common,
            REPO/'fw_console/gpu_v1.c', REPO/'fw_console/gpu_geometry.c', '-Wl,--gc-sections',
            *['-Wl,--wrap='+x for x in ['open', 'close', 'mmap', 'munmap', 'ioctl']], '-lm', '-o', out/'harness'])
        run('contract', [out/'harness'])
        report['cli'] = cli_contract(out)
        if args.renderer_only:
            report['production_json_oracle'] = {'executed': False,
                'reason': 'Explicit frozen-candidate renderer-only scope; terrain agreement is not qualified'}
        else:
            run('queries_build', ['cc', *flags, '-shared', '-fPIC', out/'queries.c', ROOT/'src/world.c',
                                  ROOT/'world/data.c', '-lm', '-o', out/'queries.so'])
            report['production_json_oracle'] = oracle_queries(ctypes.CDLL(str(out/'queries.so')))
        report['inputs_stable'] = inputs == {str(p.relative_to(REPO)): sha(p) for p in paths}
        assert report['inputs_stable'], 'Sources changed during verification; rerun in a new output directory'
        report['passed'] = True
    finally:
        (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
