#ifndef L3_MESH_CACHE_H
#define L3_MESH_CACHE_H
#include <stddef.h>
#include <stdint.h>
/* CPU-only shadow of dynamic mesh banks26/27MiB. Never a scanout source.
 * GM1 retains every vertex/face and the exact command stream. */
typedef struct L3MeshCache L3MeshCache;
typedef struct {uint64_t requested,published,compared;size_t allocated;} L3MeshCacheStats;
L3MeshCache *l3_mesh_cache_create(void);
void l3_mesh_cache_reset(L3MeshCache *);
void l3_mesh_cache_destroy(L3MeshCache *);
int l3_mesh_cache_publish(L3MeshCache *,void *gpu_memory,size_t map_bytes,
                          unsigned offset,const void *source,unsigned bytes);
L3MeshCacheStats l3_mesh_cache_stats(const L3MeshCache *);
#endif
