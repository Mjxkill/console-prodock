#ifndef CONSOLE_GPU_PALETTE_H
#define CONSOLE_GPU_PALETTE_H
#include <stdint.h>

enum gpu_demo_color {
    DEMO_TRANSPARENT=0, DEMO_BACKGROUND=1, DEMO_WHITE=2, DEMO_YELLOW=3,
    DEMO_CYAN=4, DEMO_RED=5, DEMO_TEXT_BACKGROUND=6,
    DEMO_GRAY_FIRST=64, DEMO_GRAY_LAST=127,
    DEMO_COOL_FIRST=128, DEMO_COOL_LAST=191,
    DEMO_WARM_FIRST=192, DEMO_WARM_LAST=255
};

// The LCD accepts six bits per component. Reserve three contiguous ramps,
// each with 64 distinct colors, so interpolation of indices follows a color.
static inline uint32_t gpu_demo_palette_color(unsigned i)
{
    unsigned r=0,g=0,b=0,t=i&63;
    if(i>=192) {r=63;g=t;}
    else if(i>=128) {g=t;b=63;}
    else if(i>=64) {r=t;g=t;b=t;}
    else switch(i) {
    case DEMO_BACKGROUND: b=8; break;
    case DEMO_WHITE: r=g=b=63; break;
    case DEMO_YELLOW: r=g=63; break;
    case DEMO_CYAN: g=b=63; break;
    case DEMO_RED: r=63; break;
    case DEMO_TEXT_BACKGROUND: g=9;b=12; break;
    default: r=(i>>5)*9;g=((i>>2)&7)*9;b=(i&3)*21;break;
    }
    return (r<<12)|(g<<6)|b;
}
#endif
