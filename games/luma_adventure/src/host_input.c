/* SPDX-License-Identifier: MIT */
#include "host_input.h"
#ifdef LUMA_HOST
_Static_assert(SDL_CONTROLLER_BUTTON_MAX<=32,"controller button mask fits");
static SDL_GameController *pads[4];
static unsigned previous[4];
static unsigned buttons(SDL_GameController *pad){
 unsigned bits=0;for(unsigned i=0;i<SDL_CONTROLLER_BUTTON_MAX;i++)if(SDL_GameControllerGetButton(pad,(SDL_GameControllerButton)i))bits|=1U<<i;return bits;
}
static void attach(int device){
 if(!SDL_IsGameController(device))return;SDL_JoystickID id=SDL_JoystickGetDeviceInstanceID(device);
 for(unsigned i=0;i<4;i++)if(pads[i]&&SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pads[i]))==id)return;
 for(unsigned i=0;i<4;i++)if(!pads[i]){pads[i]=SDL_GameControllerOpen(device);if(pads[i])previous[i]=buttons(pads[i]);return;}
}
void luma_host_input_open(void){for(int i=0;i<SDL_NumJoysticks();i++)attach(i);}
void luma_host_input_event(const SDL_Event *event){
 if(event->type==SDL_CONTROLLERDEVICEADDED)attach(event->cdevice.which);
 if(event->type==SDL_CONTROLLERDEVICEREMOVED)for(unsigned i=0;i<4;i++)if(pads[i]&&SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(pads[i]))==event->cdevice.which){SDL_GameControllerClose(pads[i]);pads[i]=NULL;previous[i]=0;}
}
static float axis(Sint16 value){const int dead=8000;return value>dead?(value-dead)/24767.f:value< -dead?(value+dead)/24768.f:0;}
void luma_host_input_sample(LumaInput *input,const LumaGame *game){
 SDL_GameControllerUpdate();
 for(unsigned i=0;i<4;i++)if(pads[i]&&SDL_GameControllerGetAttached(pads[i])){
  SDL_GameController *pad=pads[i];unsigned down=buttons(pad),edge=down&~previous[i];previous[i]=down;
  float x=axis(SDL_GameControllerGetAxis(pad,SDL_CONTROLLER_AXIS_LEFTX)),y=axis(SDL_GameControllerGetAxis(pad,SDL_CONTROLLER_AXIS_LEFTY));
  if(down&(1U<<SDL_CONTROLLER_BUTTON_DPAD_LEFT))x=-1;if(down&(1U<<SDL_CONTROLLER_BUTTON_DPAD_RIGHT))x=1;if(down&(1U<<SDL_CONTROLLER_BUTTON_DPAD_UP))y=-1;if(down&(1U<<SDL_CONTROLLER_BUTTON_DPAD_DOWN))y=1;input->dx+=x;input->dy+=y;
  if(game->puzzle>=0){if(edge&(1U<<SDL_CONTROLLER_BUTTON_A))input->pressed|=B_CHOICE1;if(edge&(1U<<SDL_CONTROLLER_BUTTON_B))input->pressed|=B_CHOICE2;if(edge&(1U<<SDL_CONTROLLER_BUTTON_X))input->pressed|=B_CHOICE3;}
  else{if(edge&(1U<<SDL_CONTROLLER_BUTTON_A))input->pressed|=B_INTERACT;if(edge&(1U<<SDL_CONTROLLER_BUTTON_X))input->pressed|=B_ATTACK;if(down&(1U<<SDL_CONTROLLER_BUTTON_B))input->held|=B_SHOOT;}
  if(down&(1U<<SDL_CONTROLLER_BUTTON_RIGHTSHOULDER)||SDL_GameControllerGetAxis(pad,SDL_CONTROLLER_AXIS_TRIGGERRIGHT)>6000)input->held|=B_SHOOT;
  if(edge&(1U<<SDL_CONTROLLER_BUTTON_Y))input->pressed|=B_VEHICLE;
  if(edge&(1U<<SDL_CONTROLLER_BUTTON_BACK))input->pressed|=B_MAP;
  if(edge&(1U<<SDL_CONTROLLER_BUTTON_START))input->pressed|=B_PAUSE;
  if(edge&(1U<<SDL_CONTROLLER_BUTTON_LEFTSHOULDER))input->pressed|=B_JOURNAL;
  if(edge&(1U<<SDL_CONTROLLER_BUTTON_RIGHTSTICK))input->pressed|=B_HELP;
  if(game->world->indoors&&(edge&(1U<<SDL_CONTROLLER_BUTTON_LEFTSTICK)))input->pressed|=B_RESET;
 }
 if(input->dx>1)input->dx=1;if(input->dx< -1)input->dx=-1;if(input->dy>1)input->dy=1;if(input->dy< -1)input->dy=-1;
}
void luma_host_input_close(void){for(unsigned i=0;i<4;i++){if(pads[i])SDL_GameControllerClose(pads[i]);pads[i]=NULL;previous[i]=0;}}
#endif
