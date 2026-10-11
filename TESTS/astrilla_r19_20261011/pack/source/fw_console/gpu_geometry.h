#ifndef CONSOLE_GPU_GEOMETRY_H
#define CONSOLE_GPU_GEOMETRY_H
#include "gpu_v1.h"
// G3D1 fixed-function geometry frontend. Same ordered queue/fence as GPU V1.
// Vertices: 32 bytes, XYZ signed Q16.16 then five zero words, aligned to 32.
// Faces: 32 bytes; words documented in ARCHI/GPU_GEOMETRY.md. Indices are 8-bit.
// One mesh <=256 vertices, <=65535 faces; all storage in physical DDR [0,512MiB).
// Inputs are camera-space after the supplied affine model/view matrix. X right,
// Y down, Z forward. Front winding has negative signed area after projection.
// Material/texture use gpu_v1_*; DRAW restores material but clobbers raster planes.
// Gouraud material is not supported by this flat-lit geometry ABI.
// Caller publishes CPU-written mesh bytes before submission, then waits before reuse.
enum {GPU_GEOM_MATRIX=31,GPU_GEOM_CAMERA,GPU_GEOM_LIGHT,GPU_GEOM_DRAW};
enum {GPU_GEOM_EMISSIVE=1,GPU_GEOM_TWO_SIDED=2};
typedef struct {int32_t x,y,z;uint32_t reserved[5];} gpu_geom_vertex;
typedef struct {uint32_t words[8];} gpu_geom_face;
typedef struct {uint32_t vertices,faces;uint16_t vertex_count,face_count;} gpu_geom_mesh;
typedef struct {int32_t values[12];} gpu_geom_transform;
typedef struct {int32_t near_z,far_z,focal_x,focal_y;uint16_t center_x,center_y;} gpu_geom_camera;
typedef struct {int16_t x,y,z;uint16_t ambient,diffuse;} gpu_geom_light;
typedef struct {uint32_t errors,vertices,triangles,culled,intersections,slivers,cycles;} gpu_geom_stats;
int gpu_geom_supported(void);
gpu_geom_stats gpu_geom_read_stats(void);
int gpu_geom_set_camera(gpu_v1_context *c,const gpu_geom_camera *camera);
int gpu_geom_set_transform(gpu_v1_context *c,const gpu_geom_transform *transform);
// Unit directional light expressed in object coordinates (Q1.15), gains 0..256.
// Exact Lambert lighting for rotations and uniform scales. With nonuniform
// scaling, supply a mesh with corrected normals or use emissive/unlit material.
int gpu_geom_set_light(gpu_v1_context *c,const gpu_geom_light *light);
int gpu_geom_draw(gpu_v1_context *c,const gpu_geom_mesh *mesh,unsigned cull_backfaces);
int gpu_geom_instance(gpu_v1_context *c,const gpu_geom_mesh *mesh,const gpu_geom_transform *transform,const gpu_geom_light *light,unsigned cull_backfaces);
// Build a camera-facing quad transform. Center and half sizes Q16.16;
// sine/cosine Q1.15. Submit a shared unit quad mesh using gpu_geom_instance.
int gpu_geom_billboard_transform(gpu_geom_transform *out,int32_t x,int32_t y,int32_t z,int32_t half_width,int32_t half_height,int16_t sine,int16_t cosine);
// Explicit safe float conversion for game state -> fixed geometry parameters.
int gpu_geom_fixed(float value,int32_t *out);
#endif
