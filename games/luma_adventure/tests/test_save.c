/* Save compatibility and rejection tests; file records are deliberately reordered. */
#define _POSIX_C_SOURCE 200809L
#include "luma.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#define N 131072
#define R 960
static unsigned char original[N],changed[N];
static void put(unsigned char *p,unsigned x){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(x>>(8*i));}
static void swap(unsigned char *a,unsigned char *b,unsigned n){while(n--){unsigned char c=*a;*a++=*b;*b++=c;}}
static void write_file(const char *path){put(changed+N-4,luma_crc(changed,N-4));FILE *f=fopen(path,"wb");assert(f);assert(fwrite(changed,1,N,f)==N);assert(!fclose(f));}
static void rejected(LumaGame *g,const char *path){LumaGame before=*g;write_file(path);assert(luma_load(g,path)<0&&errno==EINVAL);assert(!memcmp(&before,g,sizeof(before)));}
int main(void){
 char directory[]="/tmp/luma-save-regression-XXXXXX";assert(mkdtemp(directory));char path[200];snprintf(path,sizeof(path),"%s/carnet.sav",directory);LumaGame g,loaded;luma_init(&g,&luma_world);g.flags=7;g.collected=5;g.talked=2;g.missions=1;g.crystals=42;
 char stale[240];snprintf(stale,sizeof(stale),"%s.tmp.%ld",path,(long)getpid());FILE *interrupted=fopen(stale,"wx");assert(interrupted);assert(fputs("interrupted previous writer",interrupted)>=0);assert(!fclose(interrupted));
 assert(!luma_enter(&g,5,0,0));g.flags=319;g.collected=UINT64_C(1)<<10;g.defeated=UINT64_C(1)<<20;g.won=1;g.ending_open=1;assert(!luma_save(&g,path));FILE *f=fopen(path,"rb");assert(f&&fread(original,1,N,f)==N);fclose(f);interrupted=fopen(stale,"rb");char sentinel[40]={0};assert(interrupted&&fread(sentinel,1,27,interrupted)==27);fclose(interrupted);assert(!strcmp(sentinel,"interrupted previous writer"));unlink(stale);puts("PASS interrupted temporary save does not block a new atomic save and is not overwritten");
 memcpy(changed,original,N);swap(changed+128,changed+128+5*R,R);unsigned char *r=changed+128;swap(r+32,r+32+10*8,8);swap(r+704,r+704+10*4,4);swap(r+544,r+552,8);write_file(path);luma_init(&loaded,&luma_world);assert(!luma_load(&loaded,path));assert(loaded.world_index==5&&loaded.flags==319&&loaded.collected==g.collected&&loaded.defeated==g.defeated&&loaded.progress[0].collected==5&&loaded.progress[0].missions==1);puts("PASS stable world/entity/mission IDs survive reordered save records and loading from a fresh game");
 assert(loaded.won&&!loaded.ending_open);puts("PASS completed story persists while loading resumes free exploration");
 memcpy(changed,original,N);memcpy(changed+128+R,changed+128,R);rejected(&loaded,path);
 memcpy(changed,original,N);memcpy(changed+128+40,changed+128+32,4);rejected(&loaded,path);
 memcpy(changed,original,N);put(changed+128+36,16);rejected(&loaded,path);
 memcpy(changed,original,N);memcpy(changed+128+552,changed+128+544,4);rejected(&loaded,path);
 memcpy(changed,original,N);put(changed+128+548,1024);rejected(&loaded,path);
 memcpy(changed,original,N);put(changed+128+8,65);rejected(&loaded,path);
 memcpy(changed,original,N);put(changed+12,97);rejected(&loaded,path);puts("PASS duplicate records, invalid counts and invalid state bits rejected atomically");
 if(luma_world_count>9){
  luma_init(&g,&luma_world);assert(!luma_enter(&g,9,0,0));unsigned crate=0;while(crate<g.world->entity_count&&g.world->entities[crate].kind!=E_CRATE)crate++;assert(crate<g.world->entity_count);
  /* A completed legal push, player standing on the crate's original square. */
  float old_x=g.actors[crate].x;g.actors[crate].x-=32;g.x=old_x;g.y=g.actors[crate].y;assert(!luma_save(&g,path));luma_init(&loaded,&luma_world);assert(!luma_load(&loaded,path));assert(loaded.world_index==9&&loaded.actors[crate].x==g.actors[crate].x&&loaded.x==g.x&&loaded.y==g.y);
  unsigned crystals=loaded.crystals;luma_step(&loaded,(LumaInput){0,0,B_RESET,0});assert(loaded.actors[crate].x==old_x&&loaded.crystals==crystals);puts("PASS active room crate and player resume coherently before collision validation");
 }
 unlink(path);assert(!rmdir(directory));puts("LUMA_SAVE_PASS");return 0;
}
