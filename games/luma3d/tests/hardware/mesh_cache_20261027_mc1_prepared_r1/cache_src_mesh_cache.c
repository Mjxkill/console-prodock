#include "l3_mesh_cache.h"
#include <stdlib.h>
#include <string.h>

enum {BANK_BYTES=1U<<20,BASE=26U<<20,BLOCK=32,VALID_BYTES=BANK_BYTES/BLOCK/8};
struct L3MeshCache {
 unsigned char *shadow[2];
 size_t capacity[2];
 void *bound_memory;
 size_t bound_bytes;
 unsigned char valid[2][VALID_BYTES];
 L3MeshCacheStats stats;
};
L3MeshCache *l3_mesh_cache_create(void){return calloc(1,sizeof(L3MeshCache));}
void l3_mesh_cache_reset(L3MeshCache *c){if(c)memset(c->valid,0,sizeof c->valid);}
void l3_mesh_cache_destroy(L3MeshCache *c){if(c){free(c->shadow[0]);free(c->shadow[1]);free(c);}}
L3MeshCacheStats l3_mesh_cache_stats(const L3MeshCache *c){return c?c->stats:(L3MeshCacheStats){0};}
int l3_mesh_cache_publish(L3MeshCache *c,void *gpu_memory,size_t map_bytes,
                          unsigned offset,const void *source,unsigned bytes){
 /* Reject every invalid request before allocation or any write. Source must
  * be ordinary CPU RAM, never a readable mirror of the GPU aperture. */
 uintptr_t dst=(uintptr_t)gpu_memory,src=(uintptr_t)source;
 if(!c||!gpu_memory||!source||(dst&3)||(offset&31)||(bytes&31)||
    offset<BASE||offset>=BASE+2U*BANK_BYTES||
    offset>map_bytes||bytes>map_bytes-offset||
    bytes>BANK_BYTES-(offset-BASE)%BANK_BYTES||
    map_bytes>UINTPTR_MAX-dst||bytes>UINTPTR_MAX-src||
    (src<dst+map_bytes&&src+bytes>dst))return 0;
 if(!bytes)return 1;
 unsigned page=(offset-BASE)/BANK_BYTES,pos=(offset-BASE)%BANK_BYTES;
 size_t need=(size_t)pos+bytes;
 if(need>c->capacity[page]){
  size_t cap=c->capacity[page]?c->capacity[page]:128U<<10;
  while(cap<need)cap*=2;
  unsigned char *next=realloc(c->shadow[page],cap);if(!next)return 0;
  c->stats.allocated+=cap-c->capacity[page];c->capacity[page]=cap;c->shadow[page]=next;
 }
 /* A cache reused with a different mapping must republish, even if its
  * source blocks are unchanged. Commit the binding only after allocation. */
 if(c->bound_memory!=gpu_memory||c->bound_bytes!=map_bytes){
  l3_mesh_cache_reset(c);c->bound_memory=gpu_memory;c->bound_bytes=map_bytes;
 }
 c->stats.requested+=bytes;
 const unsigned char *s=source;
 for(unsigned i=0;i<bytes;i+=BLOCK){
  unsigned block=(pos+i)/BLOCK,byte=block/8,bit=1U<<(block%8);
  unsigned char *old=c->shadow[page]+pos+i;
  if(c->valid[page][byte]&bit){
   c->stats.compared+=BLOCK;
   if(!memcmp(old,s+i,BLOCK))continue;
  }
  volatile uint32_t *d=(volatile uint32_t *)((unsigned char *)gpu_memory+offset+i);
  for(unsigned w=0;w<BLOCK/4;w++){uint32_t word;memcpy(&word,s+i+w*4,4);d[w]=word;}
  memcpy(old,s+i,BLOCK);c->valid[page][byte]|=bit;c->stats.published+=BLOCK;
 }
 return 1;
}
