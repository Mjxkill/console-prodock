/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include "luma.h"
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#define SAVE_BYTES 131072
#define RECORD_BYTES 960
uint32_t luma_crc(const void *data,unsigned n){static uint32_t table[256];static int ready;if(!ready){for(unsigned i=0;i<256;i++){uint32_t c=i;for(unsigned k=0;k<8;k++)c=(c>>1)^(0xedb88320U&-(c&1));table[i]=c;}ready=1;}const unsigned char *p=data;uint32_t c=~0U;while(n--){c=table[(c^*p++)&255]^(c>>8);}return ~c;}
static uint32_t id(const char *s){return luma_crc(s,(unsigned)strlen(s));}
static void put(unsigned char *p,uint32_t x){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(x>>(8*i));}
static uint32_t get(const unsigned char *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
int luma_save(const LumaGame *g,const char *path){
 unsigned char b[SAVE_BYTES]={0};memcpy(b,"LUMASAVE",8);put(b+8,4);put(b+12,luma_world_count);
 const uint32_t words[]={(uint32_t)lroundf(g->x*256),(uint32_t)lroundf(g->y*256),g->unlocked,g->vehicle,g->crystals,g->health,g->hearts,g->kills,g->deaths,g->visited,g->secrets,g->tick,g->rng,id(g->world->id),g->won};
 for(unsigned i=0;i<sizeof(words)/sizeof(words[0]);i++)put(b+16+i*4,words[i]);
 for(unsigned wi=0;wi<luma_world_count;wi++){
  const LumaWorld *w=luma_worlds+wi;LumaProgress p=wi==g->world_index?luma_progress(g):g->progress[wi];unsigned char *r=b+128+wi*RECORD_BYTES;
  put(r,id(w->id));put(r+4,p.flags);put(r+8,w->entity_count);put(r+12,w->mission_count);
  for(unsigned i=0;i<w->entity_count;i++){uint64_t bit=UINT64_C(1)<<i;unsigned state=(!!(p.collected&bit))|((!!(p.activated&bit))<<1)|((!!(p.defeated&bit))<<2)|((!!(p.talked&bit))<<3);put(r+32+i*8,id(w->entities[i].id));put(r+36+i*8,state);put(r+704+i*4,p.objects[i]);}
  for(unsigned i=0;i<w->mission_count;i++){put(r+544+i*8,id(w->missions[i].id));put(r+548+i*8,p.steps[i]|((!!(p.missions&(1U<<i)))<<8));}
 }
 put(b+SAVE_BYTES-4,luma_crc(b,SAVE_BYTES-4));
 char tmp[1024];if(snprintf(tmp,sizeof(tmp),"%s.tmp.%ld",path,(long)getpid())>=(int)sizeof(tmp)){errno=ENAMETOOLONG;return -1;}
 int fd=open(tmp,O_WRONLY|O_CREAT|O_EXCL,0600);if(fd<0)return -1;unsigned n=0;int ok=1;
 while(n<sizeof(b)){ssize_t k=write(fd,b+n,sizeof(b)-n);if(k<0&&errno==EINTR)continue;if(k<=0){ok=0;break;}n+=(unsigned)k;}
 if(ok&&fsync(fd))ok=0;if(close(fd))ok=0;if(ok&&rename(tmp,path))ok=0;if(!ok){int e=errno;unlink(tmp);errno=e;return -1;}
 char dir[1024];snprintf(dir,sizeof(dir),"%s",path);char *slash=strrchr(dir,'/');if(slash){if(slash==dir)slash[1]=0;else *slash=0;}else strcpy(dir,".");
 fd=open(dir,O_RDONLY|O_DIRECTORY);if(fd<0)return -1;int result=fsync(fd);int e=errno;close(fd);errno=e;return result;
}
int luma_load(LumaGame *g,const char *path){
 unsigned char b[SAVE_BYTES+1];FILE *f=fopen(path,"rb");if(!f)return -1;size_t n=fread(b,1,sizeof(b),f);int error=ferror(f);fclose(f);
 if(error||n!=SAVE_BYTES||memcmp(b,"LUMASAVE",8)||get(b+8)!=4||get(b+12)>LUMA_MAX_WORLDS||get(b+SAVE_BYTES-4)!=luma_crc(b,SAVE_BYTES-4)){errno=EINVAL;return -1;}
 uint32_t w[15];for(unsigned i=0;i<15;i++)w[i]=get(b+16+4*i);int active=-1;
 for(unsigned i=0;i<luma_world_count;i++)if(id(luma_worlds[i].id)==w[13])active=(int)i;
 if(active<0||w[3]>=VEHICLES||!(w[2]&1)||w[2]&~255U||!(w[2]&(1U<<w[3]))||w[5]<1||w[5]>w[6]||w[6]!=6||w[4]>1000000||w[14]>1){errno=EINVAL;return -1;}
 LumaGame next;luma_init(&next,luma_worlds+active);next.world_index=(unsigned)active;next.x=w[0]/256.f;next.y=w[1]/256.f;next.unlocked=w[2];next.vehicle=w[3];next.crystals=w[4];next.health=w[5];next.hearts=w[6];next.kills=w[7];next.deaths=w[8];next.visited=w[9];next.secrets=w[10];next.tick=w[11];next.time=next.tick/(float)LUMA_HZ;next.rng=w[12];next.won=w[14];int migrated=0;
 if(next.x<0||next.y<0||next.x>=65536||next.y>=65536){errno=EINVAL;return -1;}
 unsigned char seen[LUMA_MAX_WORLDS]={0};
 for(unsigned record=0;record<get(b+12);record++){
  const unsigned char *r=b+128+record*RECORD_BYTES;unsigned entities=get(r+8),missions=get(r+12);if(entities>64||missions>16){errno=EINVAL;return -1;}
  int wi=-1;for(unsigned i=0;i<luma_world_count;i++)if(id(luma_worlds[i].id)==get(r))wi=(int)i;
  if(wi<0){migrated=1;continue;}if(seen[wi]){errno=EINVAL;return -1;}seen[wi]=1;
  const LumaWorld *world=luma_worlds+wi;LumaProgress *p=next.progress+wi;p->flags=get(r+4);
  uint64_t mapped=0;unsigned mapped_missions=0;
  for(unsigned old=0;old<entities;old++){
   unsigned key=get(r+32+old*8),state=get(r+36+old*8);if(state&~15U){errno=EINVAL;return -1;}int found=-1;
   for(unsigned i=0;i<world->entity_count;i++)if(id(world->entities[i].id)==key)found=(int)i;
   if(found<0){migrated=1;continue;}uint64_t bit=UINT64_C(1)<<found;if(mapped&bit){errno=EINVAL;return -1;}mapped|=bit;
   p->objects[found]=get(r+704+old*4);if(state&1)p->collected|=bit;if(state&2)p->activated|=bit;if(state&4)p->defeated|=bit;if(state&8)p->talked|=bit;
  }
  for(unsigned old=0;old<missions;old++){
   unsigned key=get(r+544+old*8),state=get(r+548+old*8);if(state&~511U){errno=EINVAL;return -1;}int found=-1;
   for(unsigned i=0;i<world->mission_count;i++)if(id(world->missions[i].id)==key)found=(int)i;
   if(found<0){migrated=1;continue;}if(mapped_missions&(1U<<found)){errno=EINVAL;return -1;}mapped_missions|=1U<<found;
   const LumaMission *m=world->missions+found;unsigned step=state&255,limit=m->type==M_CHOICE?1:m->point_count;
   if(step>limit){step=limit;migrated=1;}p->steps[found]=(uint8_t)step;if(state&256)p->missions|=1U<<found;
  }
 }
 if(!seen[active]){errno=EINVAL;return -1;}
 LumaProgress p=next.progress[active];next.flags=p.flags;next.collected=p.collected;next.activated=p.activated;next.defeated=p.defeated;next.talked=p.talked;next.missions=p.missions;memcpy(next.mission_steps,p.steps,16);
 if(!luma_walkable(&next,next.x,next.y,next.vehicle)){next.x=next.world->spawn_x;next.y=next.world->spawn_y;next.vehicle=WALK;migrated=1;}
 for(unsigned i=0;i<next.world->entity_count;i++)if(next.defeated&(UINT64_C(1)<<i))next.actors[i].alive=0;
 luma_restore_objects(&next);next.camera_x=next.x;next.camera_y=next.y;luma_notice(&next,migrated?"Votre carnet a été adapté au monde. Vos découvertes sont conservées.":"Votre carnet de voyage a été retrouvé.");*g=next;return 0;
}
