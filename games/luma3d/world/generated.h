/* LUMA3D authored assets. Generated data definitions are in data.c.
 * Geometry groups contain native G3D1 little-endian 32-byte vertex/face records.
 * Vertex XYZ are signed Q16.16. Face UV are signed integer texture pixels.
 * Face normals are Q1.15; face tint already combines material and face colours
 * in three unsigned nine-bit multipliers (256 = white). Do not tint twice.
 * Y is up; XZ is ground. Yaw 0 faces +Z. Units metres, angles radians.
 */
#ifndef LUMA3D_GENERATED_H
#define LUMA3D_GENERATED_H
#include <stdint.h>
#include "luma3d_game.h"

typedef struct {
 const uint32_t *vertices, *faces;
 uint16_t nv, nf, material, reserved;
} L3AssetGroup;
typedef struct {
 const char *name;
 const L3AssetGroup *groups;
 uint16_t group_count, reserved;
 L3Vec3 center;
 float radius;
} L3AssetMesh;
typedef struct { float distance; uint16_t mesh_id, reserved; } L3AssetLod;
enum { L3_PART_BODY=0, L3_PART_LEG_LEFT=1, L3_PART_LEG_RIGHT=2,
       L3_PART_ARM_LEFT=3, L3_PART_ARM_RIGHT=4, L3_PART_CAPE=5 };
typedef struct { uint16_t mesh_id, kind; L3Vec3 pivot; } L3AssetPart;
enum { L3_ASSET_PROP=0, L3_ASSET_TERRAIN=1, L3_ASSET_WATER=2,
       L3_ASSET_WATERFALL=3, L3_ASSET_BRIDGE=4, L3_ASSET_ACTOR=5 };
typedef struct {
 const char *id;
 uint16_t mesh_id;
 uint8_t lod_count, kind;
 L3Vec3 position, scale;
 float yaw;
 L3AssetLod lods[2];
} L3AssetInstance;
typedef struct {
 const char *name;
 const uint16_t *pixels;
 uint16_t width, height;
} L3AssetTexture;
typedef struct {
 const char *name;
 uint16_t texture_index;
 uint8_t red, green, blue, reserved;
} L3AssetMaterial;
enum { L3_COLLIDER_CIRCLE=1, L3_COLLIDER_BOX=2, L3_COLLIDER_BRIDGE=3 };
typedef struct {
 const char *id;
 uint16_t kind, reserved;
 float x, z, radius, min_y, max_y;
 float length, width, y, arch_height, yaw;
} L3AssetCollider;
enum { L3_WATER_ELLIPSE=1, L3_WATER_RIBBON=2 };
typedef struct { float x, z; } L3AssetPoint2;
typedef struct {
 const char *id;
 uint16_t kind, first_point, point_count, reserved;
 float x, z, rx, rz, width, level;
} L3AssetWater;

extern const L3AssetGroup l3_asset_groups[];
extern const unsigned l3_asset_group_count;
extern const L3AssetMesh l3_asset_meshes[];
extern const unsigned l3_asset_mesh_count;
extern const L3AssetInstance l3_asset_instances[];
extern const unsigned l3_asset_instance_count;
extern const L3AssetTexture l3_asset_textures[];
extern const unsigned l3_asset_texture_count;
extern const L3AssetMaterial l3_asset_materials[];
extern const unsigned l3_asset_material_count;
extern const L3AssetCollider l3_asset_colliders[];
extern const unsigned l3_asset_collider_count;
extern const L3AssetWater l3_asset_waters[];
extern const unsigned l3_asset_water_count;
extern const L3AssetPoint2 l3_asset_water_points[];
extern const unsigned l3_asset_water_point_count;
extern const float l3_asset_heights[81][81];
extern const L3Vec3 l3_asset_spawn;
extern const float l3_asset_spawn_yaw;
extern const L3Vec3 l3_asset_route[];
extern const unsigned l3_asset_route_count;
extern const L3Vec3 l3_asset_collectibles[];
extern const char *const l3_asset_collectible_names[];
extern const unsigned l3_asset_collectible_count;
extern const L3Vec3 l3_asset_goal;
extern const float l3_asset_goal_radius;
extern const L3Vec3 l3_asset_light_direction;
extern const float l3_asset_ambient, l3_asset_fog_start, l3_asset_fog_end;
extern const uint8_t l3_asset_fog_color[3], l3_asset_sky_horizon[3], l3_asset_sky_zenith[3];
extern const unsigned l3_asset_hero_mesh;
extern const L3AssetPart l3_asset_hero_parts[];
extern const unsigned l3_asset_hero_part_count;
extern const unsigned l3_asset_letter_mesh;
extern const unsigned l3_asset_windmill_static_mesh, l3_asset_windmill_rotor_mesh;
extern const L3Vec3 l3_asset_windmill_rotor_pivot;
#endif
