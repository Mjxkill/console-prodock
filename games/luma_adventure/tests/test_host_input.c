#include "host_input.h"
#include <assert.h>
#include <stdio.h>
static void pump(void){SDL_Event event;SDL_PumpEvents();while(SDL_PollEvent(&event))luma_host_input_event(&event);}
static LumaInput sample(LumaGame *g){LumaInput i={0};pump();luma_host_input_sample(&i,g);return i;}
int main(void){
 assert(!SDL_Init(SDL_INIT_EVENTS|SDL_INIT_GAMECONTROLLER));int device=SDL_JoystickAttachVirtual(SDL_JOYSTICK_TYPE_GAMECONTROLLER,SDL_CONTROLLER_AXIS_MAX,SDL_CONTROLLER_BUTTON_MAX,0);assert(device>=0);assert(SDL_IsGameController(device));SDL_Joystick *joy=SDL_JoystickOpen(device);assert(joy);luma_host_input_open();
 LumaWorld world={0};LumaGame g={.world=&world,.puzzle=-1};LumaInput i=sample(&g);assert(!i.pressed);
 SDL_JoystickSetVirtualAxis(joy,SDL_CONTROLLER_AXIS_LEFTX,6000);i=sample(&g);assert(i.dx==0);
 SDL_JoystickSetVirtualAxis(joy,SDL_CONTROLLER_AXIS_LEFTX,32767);i=sample(&g);assert(i.dx==1);
 SDL_JoystickSetVirtualButton(joy,SDL_CONTROLLER_BUTTON_A,1);i=sample(&g);assert(i.pressed&B_INTERACT);i=sample(&g);assert(!(i.pressed&B_INTERACT));
 SDL_JoystickSetVirtualButton(joy,SDL_CONTROLLER_BUTTON_A,0);sample(&g);g.puzzle=0;SDL_JoystickSetVirtualButton(joy,SDL_CONTROLLER_BUTTON_B,1);i=sample(&g);assert(i.pressed&B_CHOICE2);assert(!(i.held&B_SHOOT));
 SDL_JoystickSetVirtualButton(joy,SDL_CONTROLLER_BUTTON_B,0);sample(&g);g.puzzle=-1;SDL_JoystickSetVirtualButton(joy,SDL_CONTROLLER_BUTTON_B,1);i=sample(&g);assert(i.held&B_SHOOT);
 SDL_JoystickSetVirtualButton(joy,SDL_CONTROLLER_BUTTON_Y,1);i=sample(&g);assert(i.pressed&B_VEHICLE);
 SDL_JoystickClose(joy);assert(!SDL_JoystickDetachVirtual(device));i=sample(&g);assert(i.dx==0&&!i.held&&!i.pressed);luma_host_input_close();SDL_Quit();puts("LUMA_HOST_INPUT_PASS virtual SDL pad, deadzone, edges, puzzle, held bow, vehicle, unplug");return 0;
}
