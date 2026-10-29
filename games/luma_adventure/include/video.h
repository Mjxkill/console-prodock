/* SPDX-License-Identifier: MIT */
#ifndef LUMA_VIDEO_H
#define LUMA_VIDEO_H
#include "luma.h"
#include "prodock-uapi.h"
#define LUMA_MAP_BYTES (80U*1024*1024)
#define LUMA_WORLD_BASE (16U*1024*1024)
#define LUMA_ASSET_BASE (8U*1024*1024)
typedef struct {
 int fd,display,host,failed,world_loaded; char asset_dir[1024];unsigned width,height,pitch,page_bytes,frames,commands,sprites,max_sprites,sprites_culled,actor_priority;
 uint8_t *mem;uint16_t *pixels;uint16_t palette[256];uint8_t font[256*112];
 uint8_t *effects[2];unsigned effects_left[2][720],effects_right[2][720],dirty_left[720],dirty_right[720];unsigned effect_bytes,loading_scenes;
 uint32_t capture[512][8]; unsigned capture_count;
 struct prodock_batch batch;struct prodock_scene scene;struct prodock_display_info initial,last;
 double flush_seconds;unsigned flush_count;double background_seconds,scene_seconds,hud_seconds,submit_seconds,present_seconds;struct prodock_display_info measured;
 unsigned ui_width,ui_height;uint8_t *ui,*ui_pixels,*ui_cache[2];unsigned ui_capacity[2],ui_upload_bytes,ui_bytes[2];uint8_t ui_key[2][256];int ui_valid[2];
} LumaVideo;
int luma_video_open(LumaVideo *v,int host,int wide,const char *path);
void luma_video_measure_begin(LumaVideo *v);
int luma_video_prepare(LumaVideo *v,unsigned world);
void luma_render(LumaVideo *v,const LumaGame *g);
int luma_capture(const LumaVideo *v,const char *prefix);
int luma_snapshot(const LumaVideo *v,const char *path);
void luma_video_close(LumaVideo *v);
#endif
