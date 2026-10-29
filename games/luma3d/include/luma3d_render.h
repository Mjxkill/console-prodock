#ifndef LUMA3D_RENDER_H
#define LUMA3D_RENDER_H
#include "luma3d_game.h"
#include "gpu_geometry.h"
#include "prodock-uapi.h"
#include <stdio.h>

/* Same command producer for native GPU and independent model capture. */
#define L3_MAP_BYTES (32U*1024*1024)
#define L3_ASSET_OFFSET (8U*1024*1024)
typedef struct {
    int fd, display, host, failed;
    unsigned width, height, pitch, page_bytes, frame;
    unsigned commands, draws, triangles, instances, culled, uploaded;
    unsigned total_commands, total_flushes;
    double feed_seconds, present_seconds;
    uint8_t *memory;
    struct prodock_batch batch;
    gpu_command state_cache[6]; /* matrix rows, light, material, texture */
    unsigned state_valid;
    struct prodock_display_info initial;
    struct prodock_geometry_info initial_geometry;
    gpu_v1_context gpu;
    gpu_geom_mesh *meshes;
    uint32_t *textures;
    FILE *capture;
    L3Vec3 right, down, forward;
    float focal, near_z, far_z;
} L3Render;
int l3_render_open(L3Render *, int host, int wide);
int l3_render_frame(L3Render *, const L3Game *);
int l3_render_dump(L3Render *, const char *prefix);
int l3_render_close(L3Render *);
void l3_world_init(L3World *world);
#endif
