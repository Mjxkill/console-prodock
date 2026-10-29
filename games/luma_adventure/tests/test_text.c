/* UTF-8 dialogue text must keep accented letters and French ligatures. */
#include "../src/video.c"
#include <assert.h>
int main(void){
 LumaVideo v;assert(!luma_video_open(&v,1,0,"build/luma.pak"));v.ui=v.ui_pixels;v.ui_width=128;v.ui_height=16;memset(v.ui,0,128*16);
 text(&v,0,0,"éàçœŒ…",239,1,0);const unsigned codes[]={233,224,231,128,129,130};
 for(unsigned c=0;c<sizeof(codes)/sizeof(*codes);c++){
  unsigned painted=0;for(unsigned y=0;y<14;y++)for(unsigned x=0;x<8;x++){unsigned expected=v.font[codes[c]*112+y*8+x]?239:0;assert(v.ui[y*128+c*8+x]==expected);painted+=expected!=0;}assert(painted);
 }
 luma_video_close(&v);puts("LUMA_TEXT_PASS accented UTF-8, oe/OE ligatures, ellipsis glyphs");return 0;
}
