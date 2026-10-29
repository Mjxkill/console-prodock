#ifndef L3_SHOOTER_H
#define L3_SHOOTER_H
#include "l3_minigames.h"

#define L3_SHOOTER_VERSION 1u
#define L3_SHOOTER_SAVE_BYTES 1552u
#define L3_SHOOTER_WIDTH 160u
#define L3_SHOOTER_HEIGHT 192u
#define L3_SHOOTER_ENEMIES 8u
#define L3_SHOOTER_SHOTS 32u
#define L3_SHOOTER_BONUSES 4u
#define L3_SHOOTER_ACTORS 45u
typedef enum L3ShooterKind {
    L3_SHOOTER_NONE,L3_SHOOTER_DRIFTER,L3_SHOOTER_ZIGZAG,L3_SHOOTER_SWEEPER,
    L3_SHOOTER_BOSS,L3_SHOOTER_PLAYER_SHOT,L3_SHOOTER_ENEMY_SHOT,
    L3_SHOOTER_SHIELD,L3_SHOOTER_HEART,L3_SHOOTER_DOUBLE,L3_SHOOTER_PLAYER
} L3ShooterKind;
typedef struct L3ShooterEntity { uint32_t words[8]; } L3ShooterEntity;
typedef struct L3ShooterState {
    uint32_t words[32];
    L3ShooterEntity enemies[L3_SHOOTER_ENEMIES],shots[L3_SHOOTER_SHOTS],bonuses[L3_SHOOTER_BONUSES];
} L3ShooterState;
typedef struct L3ShooterActor {
    int32_t x256,y256; /* center, units1/256 of a logical160x192 arena pixel */
    int16_t vx256,vy256;
    uint16_t id,hp;
    uint8_t kind,color,half_width,half_height,flags;
} L3ShooterActor;
typedef struct L3ShooterView {
    L3ShooterActor actors[L3_SHOOTER_ACTORS];
    uint32_t status,score,elapsed_ms;
    uint16_t actor_count,shield_ticks,double_ticks,boss_hp;
    uint8_t lives,wave,kills,escaped;
    const char *title,*help,*objective;
} L3ShooterView;
int l3_shooter_init(L3ShooterState *state,uint32_t seed);
uint32_t l3_shooter_step(L3ShooterState *state,uint32_t pressed,uint32_t held,uint32_t dt_ms);
int l3_shooter_view(const L3ShooterState *state,L3ShooterView *view);
int l3_shooter_validate(const L3ShooterState *state);
size_t l3_shooter_encode(const L3ShooterState *state,void *output,size_t capacity);
int l3_shooter_decode(L3ShooterState *state,const void *input,size_t size);
int l3_shooter_demo_input(const L3ShooterState *state,uint32_t *pressed,uint32_t *held,uint32_t *dt_ms);
/* Fixed60Hz+saved fractional phase; same BACK/freeze/dt<=250 contract asv1.
 * Directions are continuous held controls, ACT is an edge or held rapid fire.
 * Pools never allocate; a full pool drops a spawn deterministically. */
#endif
