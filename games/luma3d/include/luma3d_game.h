#ifndef LUMA3D_GAME_H
#define LUMA3D_GAME_H

#include <stdint.h>

/* Metres, X east / Y up / Z south. Yaw 0 faces +Z; angles in radians.
 * The renderer and collision query must use the SAME terrain triangles.
 * All pointed-to world data must outlive L3Game. No graphics dependencies. */
typedef struct { float x, y, z; } L3Vec3;

enum {
    L3_JUMP = 1u << 0,
    L3_SPRINT = 1u << 1,
    L3_INTERACT = 1u << 2,
    L3_TOGGLE_AUTO = 1u << 3
};

typedef struct {
    /* Camera relative: W = move_z +1, D = move_x +1. Clamp to [-1,1].
     * look_x/y are angular input rates, not per-frame mouse deltas.
     * Positive look_x turns right: right=cross(forward,world_up).
     * pressed contains edges; held contains continuously held buttons. */
    float move_x, move_z, look_x, look_y;
    uint32_t pressed, held;
} L3Input;

typedef float (*L3HeightQuery)(void *context, float x, float z);
/* Closed solid capsule test. y is feet; radius and height are metres.
 * Include buildings and impassable deep water; include bridge surfaces in
 * height(), not as full-height solid boxes. Camera calls use height .4. */
typedef int (*L3BlockedQuery)(void *context, float x, float y, float z,
                            float radius, float height);

typedef struct {
    void *context;
    L3HeightQuery height;
    L3BlockedQuery blocked;
    float min_x, max_x, min_z, max_z;
    L3Vec3 spawn;
    float spawn_yaw;
    const L3Vec3 *route;
    uint32_t route_count;
    const L3Vec3 *collectibles;
    uint32_t collectible_count; /* 0..32. Index is stable for this slice. */
    L3Vec3 goal;
    float goal_radius; /* <=0 defaults to 2.5 m. All collectibles required. */
} L3World;

typedef struct {
    L3Vec3 position, velocity; /* position at feet */
    float yaw, speed, walk_phase;
    int grounded;
} L3Player;

typedef struct {
    L3Vec3 eye, target;
    float yaw, pitch, distance;
} L3Camera;

typedef struct {
    L3World world;
    L3Player player;
    L3Camera camera;
    float time, distance_walked;
    uint32_t collected_mask, collected_count;
    int objective_complete, autopilot;
    uint32_t route_index, completed_routes;
    int route_direction;
    float camera_manual_seconds, coyote_seconds, jump_buffer_seconds;
    /* Diagnostic only: stationary against an obstacle, never teleporting. */
    float autopilot_stuck_seconds;
    int valid;
} L3Game;

/* Returns 0 for invalid configuration. Does not mutate pointed-to world data.
 * Auto mode physically walks route forward/back; manual action takes control. */
int l3_game_init(L3Game *game, const L3World *world, int autopilot);
/* Main normally calls at 1/60 s. Finite positive dt is capped to .1 s and
 * subdivided to <=1/60; zero, negative and nonfinite deltas are no-ops.
 * Frontend must keep pressed edges pending until a positive simulation step. */
void l3_game_step(L3Game *game, const L3Input *input, float dt);

#endif
