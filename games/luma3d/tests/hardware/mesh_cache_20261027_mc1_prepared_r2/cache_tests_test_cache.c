#include "l3_mesh_cache.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int fail_realloc;
static void *cache_realloc(void *p,size_t n){if(fail_realloc){fail_realloc=0;return NULL;}return realloc(p,n);}
#define realloc cache_realloc
#include "../src/mesh_cache.c"
#undef realloc
enum {MAP=29U<<20};
static unsigned seed=0x718992a1;
static unsigned random_word(void){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}
int main(void){
 unsigned char *memory=malloc(MAP),*reference=malloc(MAP),*source=malloc(65536+1);
 assert(memory&&reference&&source);memset(memory,0xa5,MAP);memcpy(reference,memory,MAP);
 L3MeshCache *c=l3_mesh_cache_create();assert(c);
 for(unsigned trial=0;trial<1600;trial++){
  unsigned n=(1+random_word()%512)*32,off=(26U+trial%2)<<20;
  off+=(random_word()%((BANK_BYTES-n)/32+1))*32;
  unsigned char *src=source+(trial%2); /* unaligned source is legal */
  for(unsigned i=0;i<n;i++)src[i]=(unsigned char)random_word();
  if(trial%13==0)l3_mesh_cache_reset(c);
  assert(l3_mesh_cache_publish(c,memory,MAP,off,src,n));memcpy(reference+off,src,n);
  assert(!memcmp(memory,reference,MAP));
  L3MeshCacheStats before=l3_mesh_cache_stats(c);
  assert(l3_mesh_cache_publish(c,memory,MAP,off,src,n));
  L3MeshCacheStats after=l3_mesh_cache_stats(c);
  assert(after.published==before.published&&after.requested==before.requested+n);
  /* A single changed byte must publish one32-byte block and nothing else. */
  src[n/2]^=1;assert(l3_mesh_cache_publish(c,memory,MAP,off,src,n));
  assert(l3_mesh_cache_stats(c).published==after.published+32);memcpy(reference+off,src,n);
  assert(!memcmp(memory,reference,MAP));
 }
 uint64_t published=l3_mesh_cache_stats(c).published;
 for(unsigned test=0;test<6;test++){
  int ok=test==0?l3_mesh_cache_publish(c,memory,MAP,(26U<<20)+1,source,32):
   test==1?l3_mesh_cache_publish(c,memory,MAP,26U<<20,source,33):
   test==2?l3_mesh_cache_publish(c,memory,MAP,(27U<<20)-32,source,64):
   test==3?l3_mesh_cache_publish(c,memory,MAP,28U<<20,source,32):
   test==4?l3_mesh_cache_publish(c,memory,MAP,26U<<20,memory+(26U<<20),32):
   l3_mesh_cache_publish(c,memory,26U<<20,26U<<20,source,32);
  assert(!ok&&published==l3_mesh_cache_stats(c).published&&!memcmp(memory,reference,MAP));
 }
 l3_mesh_cache_destroy(c);c=l3_mesh_cache_create();assert(c);
 fail_realloc=1;assert(!l3_mesh_cache_publish(c,memory,MAP,26U<<20,source,32));
 assert(!memcmp(memory,reference,MAP)&&!l3_mesh_cache_stats(c).published);
 assert(l3_mesh_cache_publish(c,memory,MAP,26U<<20,source,32));memcpy(reference+(26U<<20),source,32);
 assert(!memcmp(memory,reference,MAP));
 l3_mesh_cache_reset(c);published=l3_mesh_cache_stats(c).published;
 assert(l3_mesh_cache_publish(c,memory,MAP,26U<<20,source,32));
 assert(l3_mesh_cache_stats(c).published==published+32);
 /* Growth failure and the other bank fail before the current publication. */
 for(unsigned bank=0;bank<2;bank++){
  unsigned off=((26U+bank)<<20)+(256U<<10);
  published=l3_mesh_cache_stats(c).published;fail_realloc=1;
  assert(!l3_mesh_cache_publish(c,memory,MAP,off,source,32));
  assert(published==l3_mesh_cache_stats(c).published&&!memcmp(memory,reference,MAP));
 }
 /* Independently reproduced review counterexample: same cache, new map. */
 unsigned off=26U<<20;published=l3_mesh_cache_stats(c).published;
 memset(reference+off,0xa5,32);
 assert(l3_mesh_cache_publish(c,reference,MAP,off,source,32));
 assert(!memcmp(reference+off,source,32)&&l3_mesh_cache_stats(c).published==published+32);
 published=l3_mesh_cache_stats(c).published;
 assert(l3_mesh_cache_publish(c,reference,MAP-32,off,source,32));
 assert(l3_mesh_cache_stats(c).published==published+32);
 assert(l3_mesh_cache_publish(c,memory,MAP,off,source,32));
 assert(!memcmp(memory,reference,MAP));
 l3_mesh_cache_destroy(c);free(memory);free(reference);free(source);
 puts("MESH_CACHE_TEST_PASS cases=1600 invalid=6 allocation_failure=3 mapping_rebind=3 full_memory_equality=1");return 0;
}
