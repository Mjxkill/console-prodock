// Native 800x480 diagnostic bars, independent of the 400x240 scene target.
#ifndef ASTRILLA_HUD_H
#define ASTRILLA_HUD_H
#include <stdio.h>
#include "gpu_v1.h"
#include "astrilla_assets.h"
typedef struct {
 uint64_t since;
 uint32_t frames,commands,fps_x10,commands_s;
} as_meter;
static void as_meter_reset(as_meter *m,uint64_t now){*m=(as_meter){.since=now};}
static void as_meter_frame(as_meter *m,uint64_t now,unsigned commands){
 ++m->frames;m->commands+=commands;
 uint64_t elapsed=now-m->since;
 if(elapsed>=400000000ULL){
  m->fps_x10=(unsigned)(((uint64_t)m->frames*8000000000ULL+elapsed/2)/elapsed);
  m->commands_s=(unsigned)(((uint64_t)m->commands*800000000ULL+elapsed/2)/elapsed);
  m->since=now;m->frames=m->commands=0;
 }
}
static void as_hud_layers(unsigned chapter,unsigned page,gpu_layer l[16]){
 // Keep the chapter title and counters above the iris, including cuts.
 l[14]=gpu_make_layer(ASTRILLA_HUD0+chapter*64000U,800,800,80,0,0,800,36,0,0,1);
 l[15]=gpu_make_layer(GPU_PAGE_ADDR(page),800,800,32,0,448,800,32,0,0,1);
}
static unsigned as_hud_layer_count(const gpu_layer l[16]){
 unsigned n=0;for(unsigned i=0;i<16;++i)n+=(l[i].words[6]&GPU_LAYER_ENABLE)!=0;return n;
}
static unsigned as_hud_sprite_count(const gpu_sprite s[64]){
 unsigned n=0;for(unsigned i=0;i<64;++i)n+=(s[i].words[2]&(GPU_SPRITE_ENABLE<<16))!=0;return n;
}
static void as_hud_text(void (*emit)(const gpu_command *),unsigned page,int x,const char *s){
 while(*s){gpu_command c=gpu_make_command(GPU_TEXT,page,0,x,9,0,1,0,0,33,1);unsigned n=0;
  while(n<16&&*s){c.words[4+n/4]|=(uint32_t)(uint8_t)*s++<<(8*(n%4));++n;}
  c.words[2]|=n<<16;emit(&c);x+=(int)n*8;
 }
}
static void as_hud_draw(void (*emit)(const gpu_command *),unsigned page,unsigned fps_x10,unsigned cmds,unsigned sprites,unsigned layers){
 gpu_command c=gpu_make_command(GPU_FILL,page,0,0,0,800,32,0,0,1,0);emit(&c);
 c=gpu_make_command(GPU_FILL,page,0,18,0,764,1,0,0,50,0);emit(&c);
 char text[40];
 snprintf(text,sizeof(text),"FPS %u.%u",fps_x10/10,fps_x10%10);as_hud_text(emit,page,18,text);
 snprintf(text,sizeof(text),"SPRITES %u/64",sprites);as_hud_text(emit,page,174,text);
 snprintf(text,sizeof(text),"GPU CMD/S %u",cmds);as_hud_text(emit,page,374,text);
 // RGB565 base framebuffer is separate from the 16 native overlay slots.
 snprintf(text,sizeof(text),"LAYERS %u/16+FB",layers);as_hud_text(emit,page,634,text);
}
#endif
