/* SPDX-License-Identifier: MIT */
#ifndef LUMA_HOST_INPUT_H
#define LUMA_HOST_INPUT_H
#ifdef LUMA_HOST
#include <SDL.h>
#include "luma.h"
void luma_host_input_open(void);
void luma_host_input_event(const SDL_Event *event);
void luma_host_input_sample(LumaInput *input,const LumaGame *game);
void luma_host_input_close(void);
#endif
#endif
