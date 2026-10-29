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
static void flush(LumaVideo *v){if(v->batch.count&&!v->failed){checked(v,PRODOCK_SUBMIT,&v->batch);v->commands+=v->batch.count;v->batch.count=0;}}
static void emit(LumaVideo *v,uint32_t a,uint32_t b,uint32_t c,uint32_t d,uint32_t e,uint32_t f,uint32_t g){
 if(v->batch.count==PRODOCK_BATCH_MAX)flush(v);uint32_t words[8]={a,b,c,d,e,f,g,0};
 if(prodock_command(words)){fprintf(stderr,"LUMA invalid command %u\n",a>>24);v->failed=1;return;}
 memcpy(v->batch.commands[v->batch.count++],words,sizeof(words));
}
static unsigned ink(LumaVideo *v,unsigned rgb){int best=1,distance=100000;int r=(rgb>>16)&255,g=(rgb>>8)&255,b=rgb&255;for(unsigned i=1;i<240;i++){unsigned c=v->palette[i];int dr=r-(int)((c>>11)*255/31),dg=g-(int)(((c>>5)&63)*255/63),db=b-(int)((c&31)*255/31);int d=dr*dr+dg*dg+db*db;if(d<distance){distance=d;best=i;}}return best;}
/* Bounded raw LZ4 decoder: packaged assets are validated by exact length + CRC. */
static int unpack(const unsigned char *src,size_t size,unsigned char *out,size_t capacity){
 size_t p=0,n=0;while(p<size){unsigned token=src[p++];size_t literal=token>>4,match=(token&15)+4;
  if(literal==15){unsigned b;do{if(p>=size)return -1;b=src[p++];literal+=b;}while(b==255);}
  if(literal>size-p||literal>capacity-n)return -1;memcpy(out+n,src+p,literal);p+=literal;n+=literal;if(p==size)return n==capacity?0:-1;
  if(size-p<2)return -1;unsigned offset=src[p]|(unsigned)src[p+1]<<8;p+=2;if(!offset||offset>n)return -1;
  if((token&15)==15){unsigned b;do{if(p>=size)return -1;b=src[p++];match+=b;}while(b==255);}
  if(match>capacity-n)return -1;for(size_t i=0;i<match;i++){out[n]=out[n-offset];n++;}
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
int luma_video_open(LumaVideo *v,int host,int wide,const char *path){
 memset(v,0,sizeof(*v));v->fd=v->display=-1;v->host=host;v->world_loaded=-1;snprintf(v->asset_dir,sizeof(v->asset_dir),"%s",path);char *slash=strrchr(v->asset_dir,'/');if(slash)*slash=0;else strcpy(v->asset_dir,".");unsigned width=wide?1280:800,height=wide?720:480;
 if(!host){v->fd=open("/dev/prodock-gpu",O_RDWR|O_CLOEXEC);v->display=open("/dev/prodock-display",O_RDWR|O_CLOEXEC);if(v->fd<0||v->display<0){perror("LUMA open");return -1;}
  struct prodock_info info;if(checked(v,PRODOCK_INFO,&info))return -1;printf("LUMA_GPU abi=%u width=%u height=%u caps=%08x errors=%u fault=%u\n",info.abi,info.width,info.height,info.caps,info.errors,info.faulted);fflush(stdout);if(info.abi!=PRODOCK_ABI||(info.caps&0x1ff)!=0x1ff||info.faulted||info.errors)return -1;width=info.width;height=info.height;if(checked(v,PRODOCK_DISPLAY_INFO,&v->initial))return -1;
 }
 if(!((width==800&&height==480)||(width==1280&&height==720)))return -1;v->width=width/2;v->height=height/2;v->pitch=width*2;v->page_bytes=width==800?0x100000:0x200000;
 if(LUMA_ASSET_BASE+LUMA_PACK_BYTES>LUMA_MAP_BYTES){fprintf(stderr,"LUMA GPU asset budget exceeded\n");return -1;}
 v->mem=host?calloc(1,LUMA_MAP_BYTES):mmap(NULL,LUMA_MAP_BYTES,PROT_READ|PROT_WRITE,MAP_SHARED,v->fd,0);if(v->mem==MAP_FAILED){v->mem=NULL;perror("LUMA mmap");return -1;}if(!v->mem){perror("LUMA allocation");return -1;}
 if(!host){struct prodock_layout mode={.mode=PRODOCK_GAME};if(checked(v,PRODOCK_LAYOUT,&mode))return -1;struct prodock_scene loading={.base=BASE,.stride=v->pitch,.format=7};emit(v,22U<<24,BASE,BASE+2*v->page_bytes,xy(v->width,v->height),xy(v->pitch,v->pitch),0,0);emit(v,28U<<24,1,0x1166,0,0,xy(v->width,v->height),0);emit(v,28U<<24,1,0xeed1,0,xy((int)v->width/2-70,(int)v->height/2),xy(140,3),0);flush(v);if(checked(v,PRODOCK_PRESENT,&loading))return -1;}
 uint8_t *data=load_blob(path,LUMA_PACK_BYTES,0);if(!data)return -1;uint32_t h[8];memcpy(h,data,sizeof(h));
 if(h[0]!=0x414d554c||h[1]!=1||h[2]!=LUMA_PACK_BYTES||h[3]!=LUMA_PACK_CRC||luma_crc(data+32,LUMA_PACK_BYTES-32)!=LUMA_PACK_CRC){fprintf(stderr,"LUMA common asset identity/CRC failed\n");free(data);return -1;}
 if(upload(v,LUMA_ASSET_BASE,data,LUMA_PACK_BYTES)){free(data);return -1;}
 memcpy(v->font,data+LUMA_FONT_OFFSET,sizeof(v->font));
 struct prodock_palette palette;memcpy(palette.rgb,data+LUMA_PALETTE_OFFSET,sizeof(palette.rgb));free(data);for(unsigned i=0;i<256;i++){unsigned c=palette.rgb[i];v->palette[i]=(((c>>12)&63)*31/63<<11)|(((c>>6)&63)<<5)|((c&63)*31/63);}
 for(unsigned i=240;i<256;i++)if(palette.rgb[i]){fprintf(stderr,"LUMA reserved Linux palette index %u is nonzero\n",i);return -1;}if(checked(v,PRODOCK_PALETTE,&palette))return -1;
 v->ui_pixels=malloc(width*height);if(!v->ui_pixels)return -1;
 if(host){v->pixels=malloc(width*height*2);if(!v->pixels)return -1;}else{struct prodock_layout mode={.mode=PRODOCK_GAME};if(checked(v,PRODOCK_LAYOUT,&mode))return -1;}
 return 0;
}
static void rect(LumaVideo *v,unsigned color,int x,int y,int w,int h){
 if(w<1||h<1)return;emit(v,28U<<24,1,color,0,xy(x,y),xy(w,h),0);
 if(v->host){int width=(int)v->width*2,height=(int)v->height*2;for(int yy=y*2;yy<(y+h)*2;yy++)if(yy>=0&&yy<height)for(int xx=x*2;xx<(x+w)*2;xx++)if(xx>=0&&xx<width)v->pixels[yy*width+xx]=(uint16_t)color;}
}
int luma_video_prepare(LumaVideo *v,unsigned index){
 if(v->world_loaded==(int)index)return 0;if(index>=luma_world_count||luma_region_bytes[index]>LUMA_MAP_BYTES-LUMA_WORLD_BASE)return -1;
 char path[1200];snprintf(path,sizeof(path),"%s/world_%02u.lz4",v->asset_dir,index);unsigned char *data=load_blob(path,luma_region_bytes[index],luma_region_crcs[index]);if(!data)return -1;int bad=upload(v,LUMA_WORLD_BASE,data,luma_region_bytes[index]);free(data);if(bad)return -1;v->world_loaded=(int)index;return 0;
}
static void background(LumaVideo *v,const LumaGame *g,int cx,int cy){
 unsigned columns=(g->world->width*g->world->tile+511)/512;int x0=cx/512,y0=cy/512,x1=(cx+(int)v->width-1)/512,y1=(cy+(int)v->height-1)/512;
 for(int y=y0;y<=y1;y++)for(int x=x0;x<=x1;x++){
  unsigned off=luma_chunk_offsets[g->world_index][y*columns+x];int dx=x*512-cx,dy=y*512-cy;emit(v,29U<<24,BASE+LUMA_WORLD_BASE+off,xy(512,512),1024,0,xy(dx,dy),xy(512,512));
  if(v->host){const uint16_t *p=(const uint16_t *)(v->mem+LUMA_WORLD_BASE+off);for(int yy=0;yy<512;yy++){int sy=dy+yy;if(sy<0||sy>=(int)v->height)continue;for(int xx=0;xx<512;xx++){int sx=dx+xx;if(sx<0||sx>=(int)v->width)continue;unsigned pos=(sy*2)*(v->width*2)+sx*2;uint16_t c=p[yy*512+xx];v->pixels[pos]=v->pixels[pos+1]=v->pixels[pos+v->width*2]=v->pixels[pos+v->width*2+1]=c;}}}
 }
}
static void actor(LumaVideo *v,unsigned art,int x,int y){
 if(art>=LUMA_ART_COUNT)art=0;x=x*2-32;y=y*2-52;if(x+64<0||y+64<0||x>=(int)v->width*2||y>=(int)v->height*2)return;
 if(v->sprites+4>64)return;
 for(unsigned ty=0;ty<2;ty++)for(unsigned tx=0;tx<2;tx++){
  unsigned off=luma_art_offsets[art]+(ty*2+tx)*1024;uint32_t *p=v->scene.sprites[v->sprites++];p[0]=BASE+LUMA_ASSET_BASE+off;p[1]=yx(x+tx*32,y+ty*32);p[2]=32|(32<<8)|(1U<<16)|(8U<<20);
  if(v->host){const uint8_t *pixels=v->mem+LUMA_ASSET_BASE+off;for(int yy=0;yy<32;yy++)for(int xx=0;xx<32;xx++){int sx=x+tx*32+xx,sy=y+ty*32+yy;unsigned c=pixels[yy*32+xx];if(c&&sx>=0&&sy>=0&&sx<(int)v->width*2&&sy<(int)v->height*2)v->pixels[sy*v->width*2+sx]=v->palette[c];}}
 }
}
static void ui_rect(LumaVideo *v,int x,int y,int w,int h,unsigned c){for(int yy=y;yy<y+h;yy++)if(yy>=0&&yy<(int)v->ui_height)for(int xx=x;xx<x+w;xx++)if(xx>=0&&xx<(int)v->ui_width)v->ui[yy*v->ui_width+xx]=(uint8_t)c;}
static void text(LumaVideo *v,int x,int y,const char *s,unsigned c,int scale,int wrap){
 const uint8_t *font=v->font;int start=x;
 for(;*s;s++){unsigned ch=(unsigned char)*s;if(ch>=0xc2&&ch<0xe0&&s[1]&&((unsigned char)s[1]&0xc0)==0x80){ch=((ch&31)<<6)|((unsigned char)*++s&63);}else if(ch>=0xe0&&ch<0xf0&&s[1]&&s[2]){ch=((ch&15)<<12)|(((unsigned char)s[1]&63)<<6)|((unsigned char)s[2]&63);s+=2;}if(ch==0x2019||ch==0x2018)ch='\'';if(ch==0x2013||ch==0x2014)ch='-';if(ch>=256)ch='?';if(ch=='\n'||(wrap&&x+8*scale>wrap)){x=start;y+=16*scale;if(ch=='\n')continue;}
  for(int yy=0;yy<14;yy++)for(int xx=0;xx<8;xx++)if(font[ch*112+yy*8+xx])ui_rect(v,x+xx*scale,y+yy*scale,scale,scale,c);x+=8*scale;
 }
}
static void layer(LumaVideo *v,unsigned slot,unsigned offset,int x,int y,unsigned w,unsigned h){
 uint32_t *p=v->scene.layers[slot];p[0]=BASE+offset;p[1]=yx(w,h);p[2]=yx(x,y);p[3]=yx(w,h);p[5]=w;p[6]=3;
 if(v->host){const uint8_t *src=v->ui_pixels+offset-(6*1024*1024+(v->frames&1)*1024*1024);for(unsigned yy=0;yy<h;yy++)for(unsigned xx=0;xx<w;xx++){int sx=x+(int)xx,sy=y+(int)yy;unsigned c=src[yy*w+xx];if(c&&sx>=0&&sy>=0&&sx<(int)v->width*2&&sy<(int)v->height*2)v->pixels[sy*v->width*2+sx]=v->palette[c];}}
}
static void hud(LumaVideo *v,const LumaGame *g){
 unsigned base=6*1024*1024+(v->frames&1)*1024*1024;unsigned width=v->width*2,used=width*88;unsigned dark=ink(v,0x142b2c),gold=ink(v,0xe9ce94),white=239,muted=ink(v,0x9fb5a1),red=ink(v,0xe67b67),green=ink(v,0x97dbb9);
 v->ui_width=width;v->ui_height=48;v->ui=v->ui_pixels;memset(v->ui,dark,width*48);ui_rect(v,0,47,width,1,gold);
 text(v,18,9,"L U M A",gold,2,0);char line[180];snprintf(line,sizeof(line),"%s  /  %s",g->world->name,luma_vehicle_names[g->vehicle]);text(v,178,8,line,white,1,width-14);ui_rect(v,430,36,104,7,muted);ui_rect(v,432,38,(int)g->stamina,3,green);
 for(unsigned i=0;i<g->hearts;i++)ui_rect(v,180+i*17,34,12,12,i<g->health?red:muted);
 snprintf(line,sizeof(line),"%u eclats",g->crystals);text(v,302,34,line,gold,1,0);text(v,(int)width-148,34,"E interagir",muted,1,0);layer(v,0,base,0,0,width,48);
 unsigned bottom=base+width*48;v->ui=v->ui_pixels+width*48;v->ui_height=40;memset(v->ui,0,width*40);
 const char *message=g->notice_time>0?g->notice:luma_objective(g);
 ui_rect(v,12,1,width-24,38,dark);ui_rect(v,12,1,3,38,gold);text(v,26,5,message,white,1,width-108);text(v,(int)width-88,22,"H aide",muted,1,0);
 
 layer(v,1,bottom,0,(int)v->height*2-40,width,40);
 if(g->dialogue>=0||g->map||g->journal||g->help||g->paused||g->won){
  unsigned off=bottom+width*40,h=v->height*2-108;v->ui=v->ui_pixels+width*88;v->ui_height=h;memset(v->ui,dark,width*h);ui_rect(v,16,12,width-32,2,gold);
  if(g->dialogue>=0){const LumaEntity *e=g->world->entities+g->dialogue;text(v,28,28,e->name,gold,2,0);const LumaMission *puzzle=g->puzzle>=0?g->world->missions+g->puzzle:NULL;text(v,28,76,puzzle?puzzle->text:g->dialogue_page&&e->after[0]?e->after:e->text,white,1,width-28);if(puzzle){for(unsigned i=0;i<3;i++){snprintf(line,sizeof(line),"%u. %s",i+1,puzzle->options[i]);text(v,28,172+(int)i*30,line,gold,1,width-28);}text(v,28,(int)h-32,"1 / 2 / 3 pour répondre. E pour revenir aux indices.",green,1,width-28);}else text(v,28,(int)h-32,"E pour reprendre votre voyage",green,1,0);}
  else if(g->map){
   text(v,28,24,"ATLAS DES MONDES RELIES",gold,2,0);int scale=(int)(h-100)/g->world->height;if(scale<1)scale=1;int ox=30,oy=70;
   for(int y=0;y<g->world->height;y++)for(int x=0;x<g->world->width;x++){char c=g->world->terrain[y*g->world->width+x];unsigned col=c=='~'?ink(v,0x48899e):c=='#'?muted:c=='='?gold:green;ui_rect(v,ox+x*scale,oy+y*scale,scale,scale,col);}
   ui_rect(v,ox+(int)(g->x/g->world->tile)*scale-2,oy+(int)(g->y/g->world->tile)*scale-2,5,5,red);
   int tx=ox+g->world->width*scale+24;for(unsigned i=0;i<luma_world_count&&i<6;i++){snprintf(line,sizeof(line),"%c %u. %s",i==g->world_index?'>':' ',i+1,luma_worlds[i].name);text(v,tx,74+(int)i*28,line,i==g->world_index?gold:muted,1,width-10);}
   text(v,tx,260,"M pour fermer",white,1,width-14);
  }else if(g->help){text(v,28,28,"LES GESTES DU VOYAGE",gold,2,0);text(v,28,78,"WASD / flèches : se déplacer\nE : parler, ouvrir, pousser ou activer\nESPACE : épée    F / X : arc\nV / TAB : changer de monture\nM : carte    J : carnet de missions\n1 / 2 / 3 : répondre à une énigme\nR : recommencer les mécanismes de la salle\nP : pause    Q : sauvegarder et quitter\nH : fermer cette aide",white,1,width-28);}else if(g->journal){
   text(v,28,28,"LE CARNET DE LUMA",gold,2,0);text(v,28,76,luma_objective(g),white,1,width-28);
   for(unsigned i=0;i<g->world->quest_count&&!g->world->mission_count;i++){const LumaQuest *q=g->world->quests+i;snprintf(line,sizeof(line),"%c %s%s",(g->flags&q->complete)==q->complete?'+':'-',q->title,q->optional?" (decouverte)":"");text(v,28,112+(int)i*22,line,(g->flags&q->complete)==q->complete?green:muted,1,width-28);}for(unsigned i=0;i<g->world->mission_count;i++){const LumaMission *m=g->world->missions+i;snprintf(line,sizeof(line),"%c %s",(g->missions&(1U<<i))?'+':'-',m->title);text(v,28+(int)(i/8)*(width/2),110+(int)(i%8)*21,line,(g->missions&(1U<<i))?green:muted,1,(int)((i/8+1)*(width/2))-12);}text(v,28,(int)h-32,"J pour fermer. Les habitants connaissent les chemins.",green,1,0);
  }else{text(v,28,44,g->paused?"VOYAGE EN PAUSE":"LES MONDES SONT RELIES",gold,2,0);text(v,28,100,g->paused?"P pour reprendre. Q pour sauvegarder et quitter.":"Vous avez rendu leur lumiere aux six mondes.\nIl reste des coffres, des sentiers et des montures a decouvrir.",white,1,width-28);}
  layer(v,2,off,0,56,width,h);used+=width*h;
 }
 unsigned page=v->frames&1;uint32_t hash=luma_crc(v->ui_pixels,used);if(hash!=v->ui_hash[page]||used!=v->ui_bytes[page]){memcpy(v->mem+base,v->ui_pixels,used);v->ui_hash[page]=hash;v->ui_bytes[page]=used;}
}
void luma_render(LumaVideo *v,const LumaGame *g){
 if(v->failed)return;if(luma_video_prepare(v,g->world_index)){fprintf(stderr,"LUMA region load failed: %u\n",g->world_index);v->failed=1;return;}unsigned page=v->frames&1;v->scene=(struct prodock_scene){.base=BASE+page*v->page_bytes,.stride=v->pitch,.format=7,.layers_enabled=1,.sprites_enabled=1};v->sprites=0;
 emit(v,22U<<24,v->scene.base,BASE+2*v->page_bytes,xy(v->width,v->height),xy(v->pitch,v->pitch),0,0);
 int maxx=g->world->width*g->world->tile-(int)v->width,maxy=g->world->height*g->world->tile-(int)v->height;
 int cx=(int)lroundf(g->camera_x-v->width*.5f),cy=(int)lroundf(g->camera_y-v->height*.5f);if(cx<0)cx=0;if(cy<0)cy=0;if(cx>maxx)cx=maxx;if(cy>maxy)cy=maxy;
 double phase=video_clock();background(v,g,cx,cy);v->background_seconds+=video_clock()-phase;phase=video_clock();
 for(unsigned i=0;i<g->world->mission_count;i++){const LumaMission *m=g->world->missions+i;if((g->missions&(1U<<i))||(g->missions&m->requires)!=m->requires||(m->type!=M_ROUTE&&m->type!=M_VISIT)||g->mission_steps[i]>=m->point_count)continue;const LumaCheckpoint *p=m->points+g->mission_steps[i];int px=(int)p->x-cx,py=(int)p->y-cy;rect(v,0xffd2,px-8,py-1,17,2);rect(v,0xffd2,px-1,py-8,2,17);break;}
 for(unsigned i=0;i<LUMA_PARTICLES;i++){const LumaParticle *p=g->particles+i;if(p->live)rect(v,p->color,(int)p->x-cx,(int)p->y-cy,2,2);}
 for(unsigned i=0;i<LUMA_SHOTS;i++){const LumaShot *p=g->shots+i;if(p->live)rect(v,p->hostile?0xfaed:0xfff1,(int)p->x-cx,(int)p->y-cy-4,4,3);}
 if(g->attack>0)for(int i=-2;i<3;i++){int x=(int)(g->x+g->face_x*24-g->face_y*i*5)-cx,y=(int)(g->y+g->face_y*24+g->face_x*i*5)-cy;rect(v,0xfff4,x,y,3,3);}
 // Stable feet-order keeps crossing characters visually coherent.
 unsigned order[65],n=0;for(unsigned i=0;i<g->world->entity_count;i++){const LumaEntity *e=g->world->entities+i;if(((e->kind==E_ENEMY||e->kind==E_BOSS)&&!g->actors[i].alive)||(e->kind==E_CRYSTAL&&(g->collected&(UINT64_C(1)<<i))))continue;if((g->flags&e->requires)!=e->requires&&(e->kind==E_ENEMY||e->kind==E_BOSS))continue;int ax=(int)g->actors[i].x-cx,ay=(int)g->actors[i].y-cy;if(ax< -32||ay< -32||ax>(int)v->width+32||ay>(int)v->height+32)continue;order[n++]=i;}
 for(unsigned i=1;i<n;i++){unsigned k=order[i],j=i;float dx=g->actors[k].x-g->x,dy=g->actors[k].y-g->y,d=dx*dx+dy*dy;while(j){unsigned other=order[j-1];float ox=g->actors[other].x-g->x,oy=g->actors[other].y-g->y;if(ox*ox+oy*oy<=d)break;order[j]=other;j--;}order[j]=k;}
 if(n>15){v->sprites_culled+=n-15;n=15;}order[n++]=64;
 for(unsigned i=1;i<n;i++){unsigned k=order[i],j=i;float ky=k==64?g->y:g->actors[k].y;while(j&&(order[j-1]==64?g->y:g->actors[order[j-1]].y)>ky){order[j]=order[j-1];j--;}order[j]=k;}
 for(unsigned k=0;k<n;k++){unsigned i=order[k];if(i==64){if(g->invincible>0&&g->tick%8<4)continue;unsigned art=g->vehicle?9+g->vehicle:0;if(!g->vehicle&&fabsf(g->vx)+fabsf(g->vy)>5)art=19+((g->tick/8)%3);actor(v,art,(int)g->x-cx,(int)g->y-cy-(g->vehicle==PLANE||g->vehicle==GLIDER||g->vehicle==PARACHUTE?16:0));}
  else {const LumaEntity *e=g->world->entities+i;unsigned art=e->art;if(e->kind==E_SHRINE&&(g->activated&(UINT64_C(1)<<i)))art=17;if(e->kind==E_CHEST&&(g->collected&(UINT64_C(1)<<i)))art=18;actor(v,art,(int)g->actors[i].x-cx,(int)g->actors[i].y-cy);}}
 v->scene_seconds+=video_clock()-phase;phase=video_clock();hud(v,g);v->hud_seconds+=video_clock()-phase;if(v->sprites>v->max_sprites)v->max_sprites=v->sprites;
 if(prodock_scene_valid_for(&v->scene,v->width*2,v->height*2)){fprintf(stderr,"LUMA scene ABI rejected\n");v->failed=1;return;}phase=video_clock();flush(v);v->submit_seconds+=video_clock()-phase;phase=video_clock();checked(v,PRODOCK_PRESENT,&v->scene);v->present_seconds+=video_clock()-phase;v->frames++;
 if(!v->host&&v->frames%60==0){checked(v,PRODOCK_DISPLAY_INFO,&v->last);if(v->last.errors||v->last.faulted||v->last.underflows!=v->initial.underflows||v->last.invalid_layers!=v->initial.invalid_layers||v->last.invalid_sprites!=v->initial.invalid_sprites){fprintf(stderr,"LUMA display counters changed errors=%u underflows=%u layers=%u sprites=%u fault=%u\n",v->last.errors,v->last.underflows,v->last.invalid_layers,v->last.invalid_sprites,v->last.faulted);v->failed=1;}}
}
int luma_snapshot(const LumaVideo *v,const char *path){if(!v->host)return -1;FILE *f=fopen(path,"wb");if(!f)return -1;fprintf(f,"P6\n%u %u\n255\n",v->width*2,v->height*2);for(unsigned i=0;i<v->width*v->height*4;i++){unsigned c=v->pixels[i];unsigned char p[3]={(c>>11)*255/31,((c>>5)&63)*255/63,(c&31)*255/31};if(fwrite(p,1,3,f)!=3){fclose(f);return -1;}}return fclose(f);}
void luma_video_close(LumaVideo *v){free(v->pixels);free(v->ui_pixels);if(v->mem){if(v->host)free(v->mem);else munmap(v->mem,LUMA_MAP_BYTES);}if(v->fd>=0)close(v->fd);if(v->display>=0)close(v->display);}

void luma_video_measure_begin(LumaVideo *v){v->background_seconds=v->scene_seconds=v->hud_seconds=v->submit_seconds=v->present_seconds=0;v->commands=0;v->max_sprites=0;if(!v->host)checked(v,PRODOCK_DISPLAY_INFO,&v->measured);}
