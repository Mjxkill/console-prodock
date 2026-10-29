/* Fixed-step input latch shared by frontend and regression test. */
#ifndef LUMA_STEPPER_H
#define LUMA_STEPPER_H
#include "luma.h"
typedef struct { double accumulator; unsigned pending; } LumaStepper;
static inline unsigned luma_frame_steps(LumaStepper *clock,LumaGame *game,LumaInput input,double elapsed){
 clock->accumulator+=elapsed;clock->pending|=input.pressed;unsigned steps=0;
 while(clock->accumulator>=1.0/LUMA_HZ&&steps<15){input.pressed=clock->pending;luma_step(game,input);clock->pending=0;clock->accumulator-=1.0/LUMA_HZ;steps++;}
 return steps;
}
#endif
