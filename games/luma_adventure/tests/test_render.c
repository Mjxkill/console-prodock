/* Rendering cache must equal a fresh renderer for every UI transition. */
#include "video.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#ifndef LUMA_TEST_ASSETS
#define LUMA_TEST_ASSETS "build/luma.pak"
#endif
static void compare(LumaVideo *cached,const LumaGame *g,unsigned state){
 for(unsigned page=0;page<2;page++){
  LumaVideo fresh;assert(!luma_video_open(&fresh,1,0,LUMA_TEST_ASSETS));luma_render(cached,g);luma_render(&fresh,g);
  assert(!cached->failed&&!fresh.failed);assert(!memcmp(cached->pixels,fresh.pixels,cached->width*cached->height*8));
  luma_video_close(&fresh);
 }
 printf("PASS cached UI state %u matches fresh rendering on both pages\n",state);
}
int main(void){LumaGame g;luma_init(&g,&luma_world);LumaVideo video;assert(!luma_video_open(&video,1,0,LUMA_TEST_ASSETS));unsigned n=0;
 compare(&video,&g,n++);unsigned uploads=video.ui_upload_bytes;g.stamina=99;compare(&video,&g,n++);assert(video.ui_upload_bytes-uploads<=256);puts("PASS one stamina point uploads at most 256 bytes across both pages");g.stamina=100;compare(&video,&g,n++);g.notice_time=0;compare(&video,&g,n++);g.health=3;g.crystals=23;g.stamina=47;compare(&video,&g,n++);
 g.vehicle=HORSE;compare(&video,&g,n++);g.dialogue=0;compare(&video,&g,n++);g.dialogue_page=1;compare(&video,&g,n++);
 g.dialogue=-1;g.map=1;compare(&video,&g,n++);g.x+=64;compare(&video,&g,n++);g.map=0;g.journal=1;compare(&video,&g,n++);
 g.missions=3;compare(&video,&g,n++);g.journal=0;g.help=1;compare(&video,&g,n++);g.help=0;g.paused=1;compare(&video,&g,n++);
 g.paused=0;g.won=1;g.ending_open=1;compare(&video,&g,n++);g.ending_open=0;compare(&video,&g,n++);g.won=0;luma_notice(&g,"Une mémoire retrouvée : cœur, forêt et lumière.");compare(&video,&g,n++);
 assert(!luma_enter(&g,9,0,0));compare(&video,&g,n++);luma_video_close(&video);puts("LUMA_RENDER_CACHE_PASS");return 0;}
