#ifndef L3_SIMON_H
#define L3_SIMON_H
#include "l3_minigames.h"

#define L3_SIMON_VERSION 1u
#define L3_SIMON_SAVE_BYTES 128u
#define L3_SIMON_GOAL 8u
typedef enum L3SimonPhase {
    L3_SIMON_INTRO, L3_SIMON_SHOW, L3_SIMON_GAP, L3_SIMON_INPUT,
    L3_SIMON_ROUND_OK, L3_SIMON_ERROR, L3_SIMON_COMPLETE
} L3SimonPhase;
typedef struct L3SimonState { uint32_t words[24]; uint8_t sequence[16]; } L3SimonState;
typedef struct L3SimonView {
    L3MiniView grid; /*2x2, stride20, cells corresponding to colors0,1,2,3 */
    uint16_t phase_ms,feedback_ms;
    uint8_t phase,active_color,sequence_length,input_index;
    /* Colors0/1/2/3: up/right/down/left = red/green/blue/yellow.
     * active_color=4 means no lit button. */
} L3SimonView;
int l3_simon_init(L3SimonState *state,uint32_t seed);
uint32_t l3_simon_step(L3SimonState *state,uint32_t pressed,uint32_t held,uint32_t dt_ms);
int l3_simon_view(const L3SimonState *state,L3SimonView *view);
int l3_simon_validate(const L3SimonState *state);
size_t l3_simon_encode(const L3SimonState *state,void *output,size_t capacity);
int l3_simon_decode(L3SimonState *state,const void *input,size_t size);
int l3_simon_demo_input(const L3SimonState *state,uint32_t *pressed,uint32_t *held,uint32_t *dt_ms);
/* Same front/BACK/freeze/dt<=250 contract as v1. Edges during demonstration
 * are ignored. A held button never becomes a new color at INPUT transition.
 * Eight seeded rounds, 600ms flashes,250ms gaps,240ms input feedback. */
#endif
