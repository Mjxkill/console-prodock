#ifndef L3_MINI_ACTORS_H
#define L3_MINI_ACTORS_H
#include "l3_minigames.h"

/* Additive read-only MAZE adapter. Does not alter the v1 state/save format. */
enum { L3_MINI_ACTOR_POWERED=1u, L3_MINI_ACTOR_PROTECTED=2u,
       L3_MINI_ACTOR_FRIGHTENED=4u };
typedef struct L3MiniActor {
    uint16_t x256,y256; /* Cell centers in units1/256; x=cell_x*256+128. */
    uint8_t direction; /* N/E/S/W=0/1/2/3;4=none. Enemies: next planned turn. */
    uint8_t kind,color,flags;
} L3MiniActor;
typedef struct L3MiniActors {
    L3MiniActor actors[3]; /* player, ghost0, ghost1 */
    uint16_t power_ticks,respawn_ticks,progress,target;
    uint8_t count,player_tick,enemy_tick,next_direction;
    /* Player advances every6 ticks, enemies every14; phases above count up.
     * Render interpolation is cosmetic and must never feed the engine state. */
} L3MiniActors;
int l3_mini_actors(const L3MiniState *state,L3MiniActors *actors);
#endif
