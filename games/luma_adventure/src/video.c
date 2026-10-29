/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include "video.h"
#include "assets.h"
#include "prodock-validate.h"
#include <fcntl.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <time.h>
#define BASE PRODOCK_GPU_BASE
static uint32_t xy(int x,int y){return (uint32_t)(uint16_t)x<<16|(uint16_t)y;}
static uint32_t yx(int x,int y){return (uint32_t)(uint16_t)y<<16|(uint16_t)x;}
static int checked(LumaVideo *v,unsigned long op,void *p){if(v->host)return 0;if(ioctl(op==PRODOCK_LAYOUT||op==PRODOCK_DISPLAY_INFO?v->display:v->fd,op,p)){perror("LUMA GPU");v->failed=1;return -1;}return 0;}
static double video_clock(void);
static void flush(LumaVideo *v){if(v->batch.count&&!v->failed){double phase=video_clock();checked(v,PRODOCK_SUBMIT,&v->batch);v->flush_seconds+=video_clock()-phase;v->flush_count++;v->commands+=v->batch.count;v->batch.count=0;}}
static void emit(LumaVideo *v,uint32_t a,uint32_t b,uint32_t c,uint32_t d,uint32_t e,uint32_t f,uint32_t g){
 if(v->batch.count==PRODOCK_BATCH_MAX)flush(v);uint32_t words[8]={a,b,c,d,e,f,g,0};
 if(prodock_command(words)){fprintf(stderr,"LUMA invalid command %u\n",a>>24);v->failed=1;return;}
 memcpy(v->batch.commands[v->batch.count++],words,sizeof(words));if(v->host){if(v->capture_count>=512){v->failed=1;return;}memcpy(v->capture[v->capture_count++],words,sizeof(words));}
}
static unsigned ink(LumaVideo *v,unsigned rgb){int best=1,distance=100000;int r=(rgb>>16)&255,g=(rgb>>8)&255,b=rgb&255;for(unsigned i=1;i<240;i++){unsigned c=v->palette[i];int dr=r-(int)((c>>11)*255/31),dg=g-(int)(((c>>5)&63)*255/63),db=b-(int)((c&31)*255/31);int d=dr*dr+dg*dg+db*db;if(d<distance){distance=d;best=i;}}return best;}
/* Bounded raw LZ4 decoder: packaged assets are validated by exact length + CRC. */
static int unpack(const unsigned char *src,size_t size,unsigned char *out,size_t capacity){
 size_t p=0,n=0;while(p<size){unsigned token=src[p++];size_t literal=token>>4,match=(token&15)+4;
  if(literal==15){unsigned b;do{if(p>=size)return -1;b=src[p++];literal+=b;}while(b==255);}
  if(literal>size-p||literal>capacity-n)return -1;memcpy(out+n,src+p,literal);p+=literal;n+=literal;if(p==size)return n==capacity?0:-1;
  if(size-p<2)return -1;unsigned offset=src[p]|(unsigned)src[p+1]<<8;p+=2;if(!offset||offset>n)return -1;
  if((token&15)==15){unsigned b;do{if(p>=size)return -1;b=src[p++];match+=b;}while(b==255);}
  if(match>capacity-n)return -1;size_t distance=offset;while(match){size_t chunk=match<distance?match:distance;memcpy(out+n,out+n-distance,chunk);n+=chunk;match-=chunk;if(distance<65536)distance*=2;}
 }return n==capacity?0:-1;
}
static double video_clock(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static unsigned char *load_blob(const char *path,unsigned expected,unsigned crc){
 double start=video_clock();FILE *f=fopen(path,"rb");if(!f){perror(path);return NULL;}unsigned header[4];if(fread(header,1,16,f)!=16){fprintf(stderr,"LUMA short resource header: %s\n",path);fclose(f);return NULL;}
 unsigned char *data=malloc(expected);if(!data){perror("LUMA CPU resource allocation");fclose(f);return NULL;}int bad=0;double read_seconds=0,decode_seconds=0,crc_seconds=0;
 if(header[0]==0x4c345a4c){if(header[1]!=expected||header[2]>expected||!header[2]||(crc&&crc!=header[3])){fprintf(stderr,"LUMA compressed header mismatch: %s size=%u expected=%u\n",path,header[1],expected);bad=1;}else{unsigned char *packed=malloc(header[2]);if(!packed){perror("LUMA compressed allocation");bad=1;}else{double phase=video_clock();size_t n=fread(packed,1,header[2],f);read_seconds=video_clock()-phase;bad=n!=header[2]||fgetc(f)!=EOF;if(!bad){phase=video_clock();bad=unpack(packed,n,data,expected);decode_seconds=video_clock()-phase;}free(packed);if(!bad){phase=video_clock();unsigned actual=luma_crc(data,expected);crc_seconds=video_clock()-phase;if(actual!=header[3]){fprintf(stderr,"LUMA decompressed CRC mismatch: %s actual=%08x expected=%08x\n",path,actual,header[3]);bad=1;}}}}}
 else{memcpy(data,header,16);bad=fread(data+16,1,expected-16,f)!=expected-16||fgetc(f)!=EOF;if(!bad&&crc&&luma_crc(data,expected)!=crc)bad=1;}
 fclose(f);if(bad){fprintf(stderr,"LUMA CPU resource decode failed: %s\n",path);free(data);return NULL;}printf("LUMA_LOAD file=%s bytes=%u cpu_seconds=%.3f read=%.3f decode=%.3f crc=%.3f\n",path,expected,video_clock()-start,read_seconds,decode_seconds,crc_seconds);fflush(stdout);return data;
}
static int upload(LumaVideo *v,unsigned offset,const unsigned char *data,unsigned n){double start=video_clock();memcpy(v->mem+offset,data,n);const volatile uint32_t *gpu=(const volatile uint32_t *)(v->mem+offset);const uint32_t *cpu=(const uint32_t *)data;for(unsigned i=0;i<n/4;i++)if(gpu[i]!=cpu[i]){fprintf(stderr,"LUMA GPU upload mismatch offset=%u actual=%08x expected=%08x\n",offset+i*4,gpu[i],cpu[i]);return -1;}printf("LUMA_UPLOAD bytes=%u copy_verify_seconds=%.3f\n",n,video_clock()-start);fflush(stdout);return 0;}
/* PRESENT completes before any active streamed source is overwritten. */
static int loading_scene(LumaVideo *v){
 v->scene=(struct prodock_scene){.base=BASE,.stride=v->pitch,.format=7};
 emit(v,22U<<24,BASE,BASE+2*v->page_bytes,xy(v->width,v->height),xy(v->pitch,v->pitch),0,0);
 emit(v,28U<<24,1,0x1166,0,0,xy(v->width,v->height),0);
 emit(v,28U<<24,1,0xeed1,0,xy((int)v->width/2-70,(int)v->height/2),xy(140,3),0);
 flush(v);if(checked(v,PRODOCK_PRESENT,&v->scene))return -1;v->loading_scenes++;return v->failed?-1:0;
}
int luma_video_open(LumaVideo *v,int host,int wide,const char *path){
 memset(v,0,sizeof(*v));v->fd=v->display=-1;v->host=host;v->world_loaded=-1;snprintf(v->asset_dir,sizeof(v->asset_dir),"%s",path);char *slash=strrchr(v->asset_dir,'/');if(slash)*slash=0;else strcpy(v->asset_dir,".");unsigned width=wide?1280:800,height=wide?720:480;
 if(!host){v->fd=open("/dev/prodock-gpu",O_RDWR|O_CLOEXEC);v->display=open("/dev/prodock-display",O_RDWR|O_CLOEXEC);if(v->fd<0||v->display<0){perror("LUMA open");return -1;}
  struct prodock_info info;if(checked(v,PRODOCK_INFO,&info))return -1;printf("LUMA_GPU abi=%u width=%u height=%u caps=%08x errors=%u fault=%u\n",info.abi,info.width,info.height,info.caps,info.errors,info.faulted);fflush(stdout);if(info.abi!=PRODOCK_ABI||(info.caps&0x1ff)!=0x1ff||info.faulted||info.errors)return -1;width=info.width;height=info.height;if(checked(v,PRODOCK_DISPLAY_INFO,&v->initial))return -1;
 }
 if(!((width==800&&height==480)||(width==1280&&height==720)))return -1;v->width=width/2;v->height=height/2;v->pitch=width*2;v->page_bytes=width==800?0x100000:0x200000;
 if(LUMA_ASSET_BASE+LUMA_PACK_BYTES>LUMA_MAP_BYTES){fprintf(stderr,"LUMA GPU asset budget exceeded\n");return -1;}
 v->mem=host?calloc(1,LUMA_MAP_BYTES):mmap(NULL,LUMA_MAP_BYTES,PROT_READ|PROT_WRITE,MAP_SHARED,v->fd,0);if(v->mem==MAP_FAILED){v->mem=NULL;perror("LUMA mmap");return -1;}if(!v->mem){perror("LUMA allocation");return -1;}
 if(!host){struct prodock_layout mode={.mode=PRODOCK_GAME};if(checked(v,PRODOCK_LAYOUT,&mode))return -1;if(loading_scene(v))return -1;}
 uint8_t *data=load_blob(path,LUMA_PACK_BYTES,0);if(!data)return -1;uint32_t h[8];memcpy(h,data,sizeof(h));
 if(h[0]!=0x414d554c||h[1]!=1||h[2]!=LUMA_PACK_BYTES||h[3]!=LUMA_PACK_CRC||luma_crc(data+32,LUMA_PACK_BYTES-32)!=LUMA_PACK_CRC){fprintf(stderr,"LUMA common asset identity/CRC failed\n");free(data);return -1;}
 if(upload(v,LUMA_ASSET_BASE,data,LUMA_PACK_BYTES)){free(data);return -1;}
 memcpy(v->font,data+LUMA_FONT_OFFSET,sizeof(v->font));
 struct prodock_palette palette;memcpy(palette.rgb,data+LUMA_PALETTE_OFFSET,sizeof(palette.rgb));free(data);for(unsigned i=0;i<256;i++){unsigned c=palette.rgb[i];v->palette[i]=(((c>>12)&63)*31/63<<11)|(((c>>6)&63)<<5)|((c&63)*31/63);}
 for(unsigned i=240;i<256;i++)if(palette.rgb[i]){fprintf(stderr,"LUMA reserved Linux palette index %u is nonzero\n",i);return -1;}if(checked(v,PRODOCK_PALETTE,&palette))return -1;
 v->ui_pixels=malloc(width*height);if(!v->ui_pixels)return -1;
#ifdef LUMA_INDEXED_BACKGROUND
 if(LUMA_ASSET_BASE+LUMA_PACK_BYTES>10U*1024*1024)return -1;
 for(unsigned page=0;page<2;page++){v->effects[page]=calloc(1,width*height);if(!v->effects[page])return -1;memset(v->mem+10U*1024*1024+page*1024*1024,0,width*height);for(unsigned y=0;y<height;y++)v->effects_left[page][y]=width;}
#endif
 if(host){v->pixels=malloc(width*height*2);if(!v->pixels)return -1;}else{struct prodock_layout mode={.mode=PRODOCK_GAME};if(checked(v,PRODOCK_LAYOUT,&mode))return -1;}
 return 0;
}
#ifdef LUMA_INDEXED_BACKGROUND
#define EFFECT_BASE (10U*1024*1024)
static void effects_begin(LumaVideo *v){
 unsigned page=v->frames&1,width=v->width*2,height=v->height*2;
 for(unsigned y=0;y<height;y++){unsigned left=v->effects_left[page][y],right=v->effects_right[page][y];v->dirty_left[y]=left;v->dirty_right[y]=right;if(right>left)memset(v->effects[page]+y*width+left,0,right-left);v->effects_left[page][y]=width;v->effects_right[page][y]=0;}
}
static void effects_present(LumaVideo *v){
 unsigned page=v->frames&1,width=v->width*2,height=v->height*2,base=EFFECT_BASE+page*1024*1024;unsigned left=width,right=0,top=height,bottom=0;
 for(unsigned y=0;y<height;y++){
  unsigned a=v->dirty_left[y],b=v->dirty_right[y];if(b>a){a&=~31U;b=(b+31)&~31U;memcpy(v->mem+base+y*width+a,v->effects[page]+y*width+a,b-a);v->effect_bytes+=b-a;}
  a=v->effects_left[page][y];b=v->effects_right[page][y];if(b>a){if(a<left)left=a;if(b>right)right=b;if(y<top)top=y;bottom=y+1;}
 }
 if(right>left){left&=~31U;uint32_t *p=v->scene.layers[1];p[0]=BASE+base+top*width+left;p[1]=yx(right-left,bottom-top);p[2]=yx(left,top);p[3]=p[1];p[5]=width;p[6]=3;}
}
#endif
static void rect(LumaVideo *v,unsigned color,int x,int y,int w,int h){
#ifdef LUMA_INDEXED_BACKGROUND
 if(w<1||h<1)return;int left=x*2,top=y*2,right=(x+w)*2,bottom=(y+h)*2,width=v->width*2,height=v->height*2;if(left<0)left=0;if(top<0)top=0;if(right>width)right=width;if(bottom>height)bottom=height;if(right<=left||bottom<=top)return;
 unsigned index=0,page=v->frames&1;for(unsigned i=0;i<sizeof(luma_effect_rgb565)/sizeof(*luma_effect_rgb565);i++)if(luma_effect_rgb565[i]==color){index=LUMA_EFFECT_FIRST+i;break;}
 if(!index){unsigned c=((color>>11)*255/31<<16)|(((color>>5)&63)*255/63<<8)|((color&31)*255/31);index=ink(v,c);}
 for(int yy=top;yy<bottom;yy++){memset(v->effects[page]+yy*width+left,index,right-left);if((unsigned)left<v->effects_left[page][yy])v->effects_left[page][yy]=left;if((unsigned)right>v->effects_right[page][yy])v->effects_right[page][yy]=right;if((unsigned)left<v->dirty_left[yy])v->dirty_left[yy]=left;if((unsigned)right>v->dirty_right[yy])v->dirty_right[yy]=right;}
#else
 if(w<1||h<1||x+w<=0||y+h<=0||x>=(int)v->width||y>=(int)v->height)return;emit(v,28U<<24,1,color,0,xy(x,y),xy(w,h),0);
 if(v->host){int width=(int)v->width*2,height=(int)v->height*2;for(int yy=y*2;yy<(y+h)*2;yy++)if(yy>=0&&yy<height)for(int xx=x*2;xx<(x+w)*2;xx++)if(xx>=0&&xx<width)v->pixels[yy*width+xx]=(uint16_t)color;}
#endif
}
int luma_video_prepare(LumaVideo *v,unsigned index){
 if(v->world_loaded==(int)index)return 0;if(index>=luma_world_count||luma_region_bytes[index]>LUMA_MAP_BYTES-LUMA_WORLD_BASE)return -1;
#ifdef LUMA_INDEXED_BACKGROUND
 if(v->world_loaded>=0&&loading_scene(v))return -1;
#endif
 char path[1200];snprintf(path,sizeof(path),"%s/world_%02u.lz4",v->asset_dir,index);unsigned char *data=load_blob(path,luma_region_bytes[index],luma_region_crcs[index]);if(!data)return -1;int bad=upload(v,LUMA_WORLD_BASE,data,luma_region_bytes[index]);free(data);if(bad)return -1;v->world_loaded=(int)index;return 0;
}
static void background(LumaVideo *v,const LumaGame *g,int cx,int cy){
#ifdef LUMA_INDEXED_BACKGROUND
 const unsigned *layout=luma_tile_layout[g->world_index];uint32_t *p=v->scene.layers[0];p[0]=BASE+LUMA_WORLD_BASE;p[1]=p[0]+layout[0];p[3]=yx(v->width*2,v->height*2);p[4]=yx(cx*2,cy*2);p[5]=layout[1];p[6]=5;
 if(v->host)memset(v->pixels,0,v->width*v->height*8);
#else
 unsigned columns=(g->world->width*g->world->tile+511)/512;int x0=cx/512,y0=cy/512,x1=(cx+(int)v->width-1)/512,y1=(cy+(int)v->height-1)/512;
 for(int y=y0;y<=y1;y++)for(int x=x0;x<=x1;x++){
  unsigned off=luma_chunk_offsets[g->world_index][y*columns+x];int dx=x*512-cx,dy=y*512-cy,sx=dx<0?-dx:0,sy=dy<0?-dy:0,ex=dx+512>(int)v->width?(int)v->width-dx:512,ey=dy+512>(int)v->height?(int)v->height-dy:512;emit(v,29U<<24,BASE+LUMA_WORLD_BASE+off,xy(512,512),1024,xy(sx,sy),xy(dx+sx,dy+sy),xy(ex-sx,ey-sy));
  if(v->host){const uint16_t *p=(const uint16_t *)(v->mem+LUMA_WORLD_BASE+off);for(int yy=0;yy<512;yy++){int sy=dy+yy;if(sy<0||sy>=(int)v->height)continue;for(int xx=0;xx<512;xx++){int sx=dx+xx;if(sx<0||sx>=(int)v->width)continue;unsigned pos=(sy*2)*(v->width*2)+sx*2;uint16_t c=p[yy*512+xx];v->pixels[pos]=v->pixels[pos+1]=v->pixels[pos+v->width*2]=v->pixels[pos+v->width*2+1]=c;}}}
 }
#endif
}

static void actor(LumaVideo *v,unsigned art,int x,int y){
 if(art>=LUMA_ART_COUNT)art=0;x=x*2-32;y=y*2-52;if(x+64<0||y+64<0||x>=(int)v->width*2||y>=(int)v->height*2)return;
 if(v->sprites+4>64)return;
 for(unsigned ty=0;ty<2;ty++)for(unsigned tx=0;tx<2;tx++){
  unsigned off=luma_art_offsets[art]+(ty*2+tx)*1024;uint32_t *p=v->scene.sprites[v->sprites++];p[0]=BASE+LUMA_ASSET_BASE+off;p[1]=yx(x+tx*32,y+ty*32);p[2]=32|(32<<8)|(1U<<16)|(v->actor_priority<<20);

 }
}
static void ui_rect(LumaVideo *v,int x,int y,int w,int h,unsigned c){for(int yy=y;yy<y+h;yy++)if(yy>=0&&yy<(int)v->ui_height)for(int xx=x;xx<x+w;xx++)if(xx>=0&&xx<(int)v->ui_width)v->ui[yy*v->ui_width+xx]=(uint8_t)c;}
static void text(LumaVideo *v,int x,int y,const char *s,unsigned c,int scale,int wrap){
 const uint8_t *font=v->font;int start=x;
 for(;*s;s++){unsigned ch=(unsigned char)*s;if(ch>=0xc2&&ch<0xe0&&s[1]&&((unsigned char)s[1]&0xc0)==0x80){ch=((ch&31)<<6)|((unsigned char)*++s&63);}else if(ch>=0xe0&&ch<0xf0&&s[1]&&s[2]){ch=((ch&15)<<12)|(((unsigned char)s[1]&63)<<6)|((unsigned char)s[2]&63);s+=2;}if(ch==0x153)ch=128;else if(ch==0x152)ch=129;else if(ch==0x2026)ch=130;if(ch==0x2019||ch==0x2018)ch='\'';if(ch==0x2013||ch==0x2014)ch='-';if(ch>=256)ch='?';if(ch=='\n'||(wrap&&x+8*scale>wrap)){x=start;y+=16*scale;if(ch=='\n')continue;}
  for(int yy=0;yy<14;yy++)for(int xx=0;xx<8;xx++)if(font[ch*112+yy*8+xx])ui_rect(v,x+xx*scale,y+yy*scale,scale,scale,c);x+=8*scale;
 }
}
static void layer(LumaVideo *v,unsigned slot,unsigned offset,int x,int y,unsigned w,unsigned h){
 uint32_t *p=v->scene.layers[slot];p[0]=BASE+offset;p[1]=yx(w,h);p[2]=yx(x,y);p[3]=yx(w,h);p[5]=w;p[6]=3;

}
static void host_compose(LumaVideo *v){
 unsigned width=v->width*2,height=v->height*2;
 for(unsigned slot=0;slot<16;slot++){
  const uint32_t *l=v->scene.layers[slot];if(l[6]&1){
   int x=(int16_t)l[2],y=(int16_t)(l[2]>>16);unsigned vw=l[3]&65535,vh=l[3]>>16,sx0=l[4]&65535,sy0=l[4]>>16;
   for(unsigned yy=0;yy<vh;yy++){int dy=y+(int)yy;if(dy<0||dy>=(int)height)continue;unsigned sy=sy0+yy;
    for(unsigned xx=0;xx<vw;xx++){int dx=x+(int)xx;if(dx<0||dx>=(int)width)continue;unsigned sx=sx0+xx,c;
     if(l[6]&4){unsigned shift=((l[5]>>8)&3)+3,wlog=l[5]&15,hlog=(l[5]>>4)&15,tw=1U<<(shift+wlog),th=1U<<(shift+hlog);if(sx>=tw||sy>=th)continue;const uint16_t *map=(const uint16_t *)(v->mem+l[0]-BASE);unsigned tile=map[((sy>>shift)<<wlog)+(sx>>shift)],mask=(1U<<shift)-1,tx=sx&mask,ty=sy&mask;if(tile&0x4000)tx=mask-tx;if(tile&0x8000)ty=mask-ty;c=v->mem[l[1]-BASE+((tile&8191)<<(2*shift))+(ty<<shift)+tx];}
     else{unsigned sw=l[1]&65535,sh=l[1]>>16;if(sx>=sw||sy>=sh)continue;c=v->mem[l[0]-BASE+sy*l[5]+sx];}
     if(c||!(l[6]&2))v->pixels[dy*width+dx]=v->palette[c];
    }
   }
  }
  for(unsigned i=0;i<v->sprites;i++){const uint32_t *p=v->scene.sprites[i];if(((p[2]>>20)&15)!=slot)continue;int x=(int16_t)p[1],y=(int16_t)(p[1]>>16);unsigned w=p[2]&255,h=(p[2]>>8)&255;const unsigned char *src=v->mem+p[0]-BASE;for(unsigned yy=0;yy<h;yy++)for(unsigned xx=0;xx<w;xx++){int sx=x+(int)xx,sy=y+(int)yy;unsigned c=src[yy*32+xx];if(c&&sx>=0&&sy>=0&&sx<(int)width&&sy<(int)height)v->pixels[sy*width+sx]=v->palette[c];}}
 }
}
static void hud(LumaVideo *v,const LumaGame *g){
 unsigned page=v->frames&1,base=6*1024*1024+page*1024*1024,width=v->width*2,used=width*88;
 int modal=g->dialogue>=0||g->map||g->journal||g->help||g->paused||g->ending_open;
 const char *message=g->notice_time>0?g->notice:luma_objective(g);
 struct {const char *message;unsigned values[18];char notice[128];} key={0};
 _Static_assert(sizeof(key)<=256,"UI cache key fits");key.message=message;
 unsigned values[]={g->world_index,g->health,g->hearts,(unsigned)g->stamina,g->crystals,g->vehicle,(unsigned)g->dialogue,(unsigned)g->dialogue_page,(unsigned)g->puzzle,(unsigned)g->map,(unsigned)g->journal,(unsigned)g->help,(unsigned)g->paused,(unsigned)g->ending_open,g->flags,g->missions,g->map?(unsigned)(g->x/g->world->tile):0,g->map?(unsigned)(g->y/g->world->tile):0};
 memcpy(key.values,values,sizeof(values));if(message==g->notice)memcpy(key.notice,g->notice,sizeof(key.notice));
 if(v->ui_valid[page]&&!memcmp(v->ui_key[page],&key,sizeof(key))){layer(v,9,base,0,0,width,48);layer(v,10,base+width*48,0,(int)v->height*2-40,width,40);if(modal)layer(v,11,base+width*88,0,56,width,v->height*2-108);return;}
 unsigned dark=ink(v,0x142b2c),gold=ink(v,0xe9ce94),white=239,muted=ink(v,0x9fb5a1),red=ink(v,0xe67b67),green=ink(v,0x97dbb9);
 v->ui_width=width;v->ui_height=48;v->ui=v->ui_pixels;memset(v->ui,dark,width*48);ui_rect(v,0,47,width,1,gold);
 text(v,18,9,"L U M A",gold,2,0);char line[180];snprintf(line,sizeof(line),"%s  /  %s",g->world->name,luma_vehicle_names[g->vehicle]);text(v,178,8,line,white,1,width-14);ui_rect(v,430,36,104,7,muted);ui_rect(v,432,38,(int)g->stamina,3,green);
 static const unsigned hearts[6]={54,127,127,62,28,8};for(unsigned i=0;i<g->hearts;i++)for(unsigned y=0;y<6;y++)for(unsigned x=0;x<7;x++)if(hearts[y]&(1U<<x))ui_rect(v,180+i*17+x*2,32+y*2,2,2,i<g->health?red:muted);
 snprintf(line,sizeof(line),"%u eclats",g->crystals);text(v,302,34,line,gold,1,0);text(v,(int)width-148,34,"E interagir",muted,1,0);layer(v,9,base,0,0,width,48);
 unsigned bottom=base+width*48;v->ui=v->ui_pixels+width*48;v->ui_height=40;memset(v->ui,0,width*40);
 ui_rect(v,12,1,width-24,38,dark);ui_rect(v,12,1,3,38,gold);text(v,26,5,message,white,1,width-108);text(v,(int)width-88,22,"H aide",muted,1,0);
 
 layer(v,10,bottom,0,(int)v->height*2-40,width,40);
 if(g->dialogue>=0||g->map||g->journal||g->help||g->paused||g->ending_open){
  unsigned off=bottom+width*40,h=v->height*2-108;v->ui=v->ui_pixels+width*88;v->ui_height=h;memset(v->ui,dark,width*h);ui_rect(v,16,12,width-32,2,gold);
  if(g->dialogue>=0){const LumaEntity *e=g->world->entities+g->dialogue;text(v,28,28,e->name,gold,2,0);const LumaMission *puzzle=g->puzzle>=0?g->world->missions+g->puzzle:NULL;text(v,28,76,puzzle?puzzle->text:g->dialogue_page&&e->after[0]?e->after:e->text,white,1,width-28);if(puzzle){for(unsigned i=0;i<3;i++){snprintf(line,sizeof(line),"%u. %s",i+1,puzzle->options[i]);text(v,28,172+(int)i*30,line,gold,1,width-28);}text(v,28,(int)h-32,"1 / 2 / 3 pour répondre. E pour revenir aux indices.",green,1,width-28);}else text(v,28,(int)h-32,"E pour reprendre votre voyage",green,1,0);}
  else if(g->map){
   text(v,28,24,"ATLAS DES MONDES RELIES",gold,2,0);int scale=(int)(h-100)/g->world->height;if(scale<1)scale=1;int ox=30,oy=70;
   for(int y=0;y<g->world->height;y++)for(int x=0;x<g->world->width;x++){char c=g->world->terrain[y*g->world->width+x];unsigned col=c=='~'?ink(v,0x48899e):c=='#'?muted:c=='='?gold:green;ui_rect(v,ox+x*scale,oy+y*scale,scale,scale,col);}
   ui_rect(v,ox+(int)(g->x/g->world->tile)*scale-2,oy+(int)(g->y/g->world->tile)*scale-2,5,5,red);
   int tx=ox+g->world->width*scale+24;for(unsigned i=0;i<luma_world_count&&i<6;i++){snprintf(line,sizeof(line),"%c %u. %s",i==g->world_index?'>':' ',i+1,luma_worlds[i].name);text(v,tx,74+(int)i*28,line,i==g->world_index?gold:muted,1,width-10);}
   text(v,tx,260,"M pour fermer",white,1,width-14);
  }else if(g->help){text(v,28,28,"LES GESTES DU VOYAGE",gold,2,0);text(v,28,78,"WASD / flèches : se déplacer\nE : parler, ouvrir, pousser ou activer\nESPACE : épée    F / X : arc\nV / TAB : changer de monture\nM : carte    J : carnet de missions\n1 / 2 / 3 : répondre à une énigme\nR : recommencer les mécanismes de la salle\nP : pause    Q : sauvegarder et quitter\nH : fermer cette aide\nManette : A parler, X épée, B/RB arc, Y monture\nRetour carte, LB carnet, Start pause, clic droit aide\nÉnigmes : A/B/X ; clic gauche : salle à zéro",white,1,width-28);}else if(g->journal){
   text(v,28,28,"LE CARNET DE LUMA",gold,2,0);text(v,28,76,luma_objective(g),white,1,width-28);
   for(unsigned i=0;i<g->world->quest_count&&!g->world->mission_count;i++){const LumaQuest *q=g->world->quests+i;snprintf(line,sizeof(line),"%c %s%s",(g->flags&q->complete)==q->complete?'+':'-',q->title,q->optional?" (decouverte)":"");text(v,28,112+(int)i*22,line,(g->flags&q->complete)==q->complete?green:muted,1,width-28);}for(unsigned i=0;i<g->world->mission_count;i++){const LumaMission *m=g->world->missions+i;snprintf(line,sizeof(line),"%c %s",(g->missions&(1U<<i))?'+':'-',m->title);text(v,28+(int)(i/8)*(width/2),110+(int)(i%8)*21,line,(g->missions&(1U<<i))?green:muted,1,(int)((i/8+1)*(width/2))-12);}text(v,28,(int)h-32,"J pour fermer. Les habitants connaissent les chemins.",green,1,0);
  }else{text(v,28,44,g->paused?"VOYAGE EN PAUSE":"LES MONDES SONT RELIES",gold,2,0);text(v,28,100,g->paused?"P pour reprendre. Q pour sauvegarder et quitter.":"Vous avez rendu leur lumiere aux six mondes.\nIl reste des coffres, des sentiers et des montures a decouvrir.\nE / A ou Start : poursuivre librement votre voyage.",white,1,width-28);}
  layer(v,11,off,0,56,width,h);used+=width*h;
 }
 if(used>v->ui_capacity[page]){unsigned char *cache=realloc(v->ui_cache[page],used);if(!cache){perror("LUMA UI cache");v->failed=1;return;}v->ui_cache[page]=cache;v->ui_capacity[page]=used;}
 /* Compare cached CPU bytes, then upload contiguous changed 32-byte words.
  * One stamina point changes three short rows, not the whole HUD surface. */
 for(unsigned off=0;off<used;){
  if(off<v->ui_bytes[page]&&!memcmp(v->ui_cache[page]+off,v->ui_pixels+off,32)){off+=32;continue;}
  unsigned first=off;do{off+=32;}while(off<used&&(off>=v->ui_bytes[page]||memcmp(v->ui_cache[page]+off,v->ui_pixels+off,32)));
  memcpy(v->mem+base+first,v->ui_pixels+first,off-first);memcpy(v->ui_cache[page]+first,v->ui_pixels+first,off-first);v->ui_upload_bytes+=off-first;
 }
 memcpy(v->ui_key[page],&key,sizeof(key));v->ui_valid[page]=1;v->ui_bytes[page]=used;
}
void luma_render(LumaVideo *v,const LumaGame *g){
 if(v->failed)return;if(luma_video_prepare(v,g->world_index)){fprintf(stderr,"LUMA region load failed: %u\n",g->world_index);v->failed=1;return;}unsigned page=v->frames&1;v->scene=(struct prodock_scene){.base=BASE+page*v->page_bytes,.stride=v->pitch,.format=7,.layers_enabled=1,.sprites_enabled=1};v->sprites=0;v->capture_count=0;
#ifdef LUMA_INDEXED_BACKGROUND
 effects_begin(v);
#else
 emit(v,22U<<24,v->scene.base,BASE+2*v->page_bytes,xy(v->width,v->height),xy(v->pitch,v->pitch),0,0);
#endif
 int maxx=g->world->width*g->world->tile-(int)v->width,maxy=g->world->height*g->world->tile-(int)v->height;
 int cx=(int)lroundf(g->camera_x-v->width*.5f),cy=(int)lroundf(g->camera_y-v->height*.5f);if(cx<0)cx=0;if(cy<0)cy=0;if(cx>maxx)cx=maxx;if(cy>maxy)cy=maxy;
 double phase=video_clock();background(v,g,cx,cy);v->background_seconds+=video_clock()-phase;phase=video_clock();unsigned fore[8],fore_count=0;for(unsigned i=0;i<luma_occluder_counts[g->world_index];i++){const LumaOccluder *o=luma_occluders[g->world_index]+i;int x=(o->x-cx)*2-o->w/2,y=(o->y-cy)*2-o->h;if(x+o->w<0||y+o->h<0||x>=(int)v->width*2||y>=(int)v->height*2)continue;fore[fore_count++]=i;}for(unsigned i=1;i<fore_count;i++){unsigned k=fore[i],j=i;while(j&&luma_occluders[g->world_index][fore[j-1]].y>luma_occluders[g->world_index][k].y){fore[j]=fore[j-1];j--;}fore[j]=k;}if(fore_count>4)fore_count=4;
 for(unsigned i=0;i<fore_count;i++){const LumaOccluder *o=luma_occluders[g->world_index]+fore[i];uint32_t *p=v->scene.layers[4+i];p[0]=BASE+LUMA_ASSET_BASE+o->offset;p[1]=yx(o->w,o->h);p[2]=yx((o->x-cx)*2-o->w/2,(o->y-cy)*2-o->h);p[3]=yx(o->w,o->h);p[5]=o->pitch;p[6]=3;}
 if(!g->world->indoors)for(unsigned i=0;i<12;i++){float xx=g->world->spawn_x+(int)(i*73%340)-170,yy=g->world->spawn_y+(int)(i*59%220)-110;float pulse=sinf(g->time*2+i*1.7f);if(pulse>.55f)rect(v,0xfff2,(int)(xx+sinf(g->time+i)*6)-cx,(int)(yy+cosf(g->time*.7f+i)*4)-cy,1,1);}
 for(unsigned i=0;i<g->beam_count;i++){const LumaBeam *b=g->beams+i;int x=b->x1<b->x2?b->x1:b->x2,y=b->y1<b->y2?b->y1:b->y2;int w=abs((int)b->x2-b->x1)+1,h=abs((int)b->y2-b->y1)+1;rect(v,0xfff1,x-cx,y-cy-12,w,h);}
 for(unsigned i=0;i<g->world->mission_count;i++){const LumaMission *m=g->world->missions+i;if((g->missions&(1U<<i))||(g->missions&m->requires)!=m->requires||(m->type!=M_ROUTE&&m->type!=M_VISIT)||g->mission_steps[i]>=m->point_count)continue;const LumaCheckpoint *p=m->points+g->mission_steps[i];int px=(int)p->x-cx,py=(int)p->y-cy;rect(v,0xffd2,px-8,py-1,17,2);rect(v,0xffd2,px-1,py-8,2,17);break;}
 for(unsigned i=0;i<LUMA_PARTICLES;i++){const LumaParticle *p=g->particles+i;if(p->live)rect(v,p->color,(int)p->x-cx,(int)p->y-cy,2,2);}
 for(unsigned i=0;i<LUMA_SHOTS;i++){const LumaShot *p=g->shots+i;if(p->live)rect(v,p->hostile?0xfaed:0xfff1,(int)p->x-cx,(int)p->y-cy-4,4,3);}
 if(g->attack>0)for(int i=-2;i<3;i++){int x=(int)(g->x+g->face_x*24-g->face_y*i*5)-cx,y=(int)(g->y+g->face_y*24+g->face_x*i*5)-cy;rect(v,0xfff4,x,y,3,3);}
 for(unsigned i=0;i<g->world->entity_count;i++){const LumaEntity *e=g->world->entities+i;if(e->kind==E_LAMP&&luma_active_art[e->art]==e->art)rect(v,(g->flags&e->grants)==e->grants?0xffd2:0x39c7,(int)e->x-cx-4,(int)e->y-cy-20,8,8);}
 // R17 reserves layers 12..15 and sprite priorities >=12 for Linux text.
 // Trees 4..7, actors 3..8, HUD 9..11 preserve that ownership.
 // Stable feet-order keeps crossing characters visually coherent.
 unsigned order[65],n=0;for(unsigned i=0;i<g->world->entity_count;i++){const LumaEntity *e=g->world->entities+i;if(((e->kind==E_ENEMY||e->kind==E_BOSS)&&!g->actors[i].alive)||(e->kind==E_CRYSTAL&&(g->collected&(UINT64_C(1)<<i))))continue;if(!luma_entity_enabled(g,e)&&(e->kind==E_ENEMY||e->kind==E_BOSS))continue;int ax=(int)g->actors[i].x-cx,ay=(int)g->actors[i].y-cy;if(ax< -32||ay< -32||ax>(int)v->width+32||ay>(int)v->height+32)continue;order[n++]=i;}
 for(unsigned i=1;i<n;i++){unsigned k=order[i],j=i;float dx=g->actors[k].x-g->x,dy=g->actors[k].y-g->y,d=dx*dx+dy*dy;while(j){unsigned other=order[j-1];float ox=g->actors[other].x-g->x,oy=g->actors[other].y-g->y;if(ox*ox+oy*oy<=d)break;order[j]=other;j--;}order[j]=k;}
 if(n>15){v->sprites_culled+=n-15;n=15;}order[n++]=64;
 for(unsigned i=1;i<n;i++){unsigned k=order[i],j=i;float ky=k==64?g->y:g->actors[k].y;while(j&&(order[j-1]==64?g->y:g->actors[order[j-1]].y)>ky){order[j]=order[j-1];j--;}order[j]=k;}
 for(unsigned k=0;k<n;k++){unsigned i=order[k];float feet=i==64?g->y:g->actors[i].y;v->actor_priority=3;for(unsigned j=0;j<fore_count;j++)if(feet>=luma_occluders[g->world_index][fore[j]].y)v->actor_priority=4+j;if(i==64&&(g->vehicle==PLANE||g->vehicle==GLIDER||g->vehicle==PARACHUTE))v->actor_priority=8;if(i==64){if(g->invincible>0&&g->tick%8<4)continue;unsigned art=g->vehicle?9+g->vehicle:0;if(!g->vehicle){if(fabsf(g->face_x)>fabsf(g->face_y))art=g->face_x>0?LUMA_HERO_E:LUMA_HERO_W;else if(g->face_y<0)art=LUMA_HERO_N;else if(fabsf(g->vx)+fabsf(g->vy)>5)art=19+((g->tick/8)%4);}actor(v,art,(int)g->x-cx,(int)g->y-cy-(g->vehicle==PLANE||g->vehicle==GLIDER||g->vehicle==PARACHUTE?16:0));}
  else {const LumaEntity *e=g->world->entities+i;unsigned art=e->art;if((e->kind==E_DOOR&&luma_entity_enabled(g,e))||((e->kind==E_SWITCH||e->kind==E_TARGET||e->kind==E_PLATE||e->kind==E_LAMP||e->kind==E_SEQUENCE||e->kind==E_RECEIVER)&&e->grants&&(g->flags&e->grants)==e->grants))art=luma_active_art[art];if(e->kind==E_MIRROR&&g->mirror_orientation[i])art=luma_rotated_art[art];if(e->kind==E_SHRINE&&(g->activated&(UINT64_C(1)<<i)))art=17;if(e->kind==E_CHEST&&(g->collected&(UINT64_C(1)<<i)))art=18;actor(v,art,(int)g->actors[i].x-cx,(int)g->actors[i].y-cy);}}
#ifdef LUMA_INDEXED_BACKGROUND
 effects_present(v);
#endif
 v->scene_seconds+=video_clock()-phase;phase=video_clock();hud(v,g);v->hud_seconds+=video_clock()-phase;if(v->failed)return;if(v->host)host_compose(v);if(v->sprites>v->max_sprites)v->max_sprites=v->sprites;
 if(prodock_scene_valid_for(&v->scene,v->width*2,v->height*2)){fprintf(stderr,"LUMA scene ABI rejected\n");v->failed=1;return;}phase=video_clock();flush(v);v->submit_seconds+=video_clock()-phase;phase=video_clock();checked(v,PRODOCK_PRESENT,&v->scene);v->present_seconds+=video_clock()-phase;v->frames++;
 if(!v->host&&v->frames%60==0){checked(v,PRODOCK_DISPLAY_INFO,&v->last);if(v->last.errors||v->last.faulted||v->last.underflows!=v->initial.underflows||v->last.invalid_layers!=v->initial.invalid_layers||v->last.invalid_sprites!=v->initial.invalid_sprites){fprintf(stderr,"LUMA display counters changed errors=%u underflows=%u layers=%u sprites=%u fault=%u\n",v->last.errors,v->last.underflows,v->last.invalid_layers,v->last.invalid_sprites,v->last.faulted);v->failed=1;}}
}
int luma_snapshot(const LumaVideo *v,const char *path){if(!v->host)return -1;FILE *f=fopen(path,"wb");if(!f)return -1;fprintf(f,"P6\n%u %u\n255\n",v->width*2,v->height*2);for(unsigned i=0;i<v->width*v->height*4;i++){unsigned c=v->pixels[i];unsigned char p[3]={(c>>11)*255/31,((c>>5)&63)*255/63,(c&31)*255/31};if(fwrite(p,1,3,f)!=3){fclose(f);return -1;}}return fclose(f);}
void luma_video_close(LumaVideo *v){free(v->pixels);free(v->ui_pixels);free(v->ui_cache[0]);free(v->ui_cache[1]);free(v->effects[0]);free(v->effects[1]);if(v->mem){if(v->host)free(v->mem);else munmap(v->mem,LUMA_MAP_BYTES);}if(v->fd>=0)close(v->fd);if(v->display>=0)close(v->display);}

int luma_capture(const LumaVideo *v,const char *prefix){if(!v->host||v->world_loaded<0)return -1;char path[1200];const char *suffix[]={"memory","scene","commands"};const void *ptr[]={v->mem,&v->scene,v->capture};unsigned sizes[]={LUMA_WORLD_BASE+luma_region_bytes[v->world_loaded],sizeof(v->scene),v->capture_count*32};for(unsigned i=0;i<3;i++){snprintf(path,sizeof(path),"%s.%s",prefix,suffix[i]);FILE *f=fopen(path,"wb");if(!f)return -1;size_t n=fwrite(ptr[i],1,sizes[i],f);int rc=fclose(f);if(n!=sizes[i]||rc)return -1;}snprintf(path,sizeof(path),"%s.json",prefix);FILE *f=fopen(path,"w");if(!f)return -1;fprintf(f,"{\"width\":%u,\"height\":%u,\"palette_offset\":%u,\"sprites\":%u}\n",v->width*2,v->height*2,LUMA_ASSET_BASE+LUMA_PALETTE_OFFSET,v->sprites);if(fclose(f))return -1;snprintf(path,sizeof(path),"%s.ppm",prefix);return luma_snapshot(v,path);}

void luma_video_measure_begin(LumaVideo *v){v->flush_seconds=0;v->flush_count=0;v->effect_bytes=0;v->ui_upload_bytes=0;v->background_seconds=v->scene_seconds=v->hud_seconds=v->submit_seconds=v->present_seconds=0;v->commands=0;v->max_sprites=0;v->sprites_culled=0;if(!v->host)checked(v,PRODOCK_DISPLAY_INFO,&v->measured);}
