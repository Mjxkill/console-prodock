#ifndef L3_PLATFORM_H
#define L3_PLATFORM_H
#include "l3_minigames.h"

#define L3_PLATFORM_VERSION 1u
#define L3_PLATFORM_SAVE_BYTES 400u
#define L3_PLATFORM_BARRELS 8u
typedef struct L3PlatformBarrel { uint32_t words[8]; } L3PlatformBarrel;
typedef struct L3PlatformState { uint32_t words[32]; L3PlatformBarrel barrels[8]; } L3PlatformState;
typedef struct L3PlatformActor {
    int32_t x256,y256,z256; /* y=height, x/z=ground plane, units1/256 */
    int16_t vx256,vy256,vz256;
    uint16_t id;
    uint8_t kind,color,flags; /*1=player,2=barrel,3=goal,4=checkpoint */
} L3PlatformActor;
typedef struct L3PlatformSurface { int32_t x0,z0,x1,z1,y256; } L3PlatformSurface;
typedef struct L3PlatformLadder { int32_t x256,z256,y0,y1; } L3PlatformLadder;
typedef struct L3PlatformView {
    L3PlatformActor actors[11];
    L3PlatformSurface surfaces[7];
    L3PlatformLadder ladders[4];
    uint32_t status,score,elapsed_ms,jumps;
    uint16_t protection_ticks;
    uint8_t actor_count,surface_count,ladder_count,lives,floor,checkpoint_floor,highest_floor;
    const char *title,*help,*objective;
} L3PlatformView;
int l3_platform_init(L3PlatformState *state,uint32_t seed);
uint32_t l3_platform_step(L3PlatformState *state,uint32_t pressed,uint32_t held,uint32_t dt_ms);
int l3_platform_view(const L3PlatformState *state,L3PlatformView *view);
int l3_platform_validate(const L3PlatformState *state);
size_t l3_platform_encode(const L3PlatformState *state,void *output,size_t capacity);
int l3_platform_decode(L3PlatformState *state,const void *input,size_t size);
int l3_platform_demo_input(const L3PlatformState *state,uint32_t *pressed,uint32_t *held,uint32_t *dt_ms);
/* Five real-height floors (y=0,32,64,96,128), depth z=8..56, alternating
 * ladders and gaps on floors1/3. Held left/right move x; up/down move z or
 * climb when aligned with a ladder. ACT edge jumps; holding ACT never jumps
 * twice. Fixed60Hz, clamped250ms, saved phase. BACK/freeze as v1. */
#endif
