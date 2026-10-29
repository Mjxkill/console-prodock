#ifndef LUMA_TEST_INPUT_H
#define LUMA_TEST_INPUT_H
/* SPDX-License-Identifier: MIT
 * Deterministic input-only campaign run. No teleport, inventory injection,
 * damage immunity, flags injection, or scripted enemy removal. */
#include "luma.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
static int predecessor[5120],queue[5120];
static int direction(const LumaGame *g,float tx,float ty,float *dx,float *dy){
 const LumaWorld *w=g->world;int width=w->width,n=width*w->height,start=(int)(g->y/w->tile)*width+(int)(g->x/w->tile),goal=(int)(ty/w->tile)*width+(int)(tx/w->tile);assert(n<=5120);
 if(start!=goal){for(int i=0;i<n;i++)predecessor[i]=-1;int head=0,tail=0;queue[tail++]=start;predecessor[start]=start;
  while(head<tail&&predecessor[goal]<0){int u=queue[head++],x=u%width,y=u/width;int next[4]={u-1,u+1,u-width,u+width};for(int i=0;i<4;i++){int v=next[i];if((i==0&&x==0)||(i==1&&x==width-1)||(i==2&&y==0)||(i==3&&y==w->height-1)||predecessor[v]>=0)continue;float px=(v%width+.5f)*w->tile,py=(v/width+.5f)*w->tile;if(!luma_walkable(g,px,py,g->vehicle))continue;predecessor[v]=u;queue[tail++]=v;}}
  if(predecessor[goal]<0)return -1;int v=goal;while(predecessor[v]!=start)v=predecessor[v];tx=(v%width+.5f)*w->tile;ty=(v/width+.5f)*w->tile;
 }
 float distance=hypotf(tx-g->x,ty-g->y);*dx=distance>2?(tx-g->x)/distance:0;*dy=distance>2?(ty-g->y)/distance:0;return 0;
}
static int reach_point(LumaGame *g,float gx,float gy,float radius){
 for(unsigned tick=0;tick<40000;tick++){
  int fighting=-1;float nearest=170*170;
  for(unsigned i=0;i<g->world->entity_count;i++){const LumaEntity *e=g->world->entities+i;if((e->kind!=E_ENEMY&&e->kind!=E_BOSS)||!g->actors[i].alive||!luma_entity_enabled(g,e))continue;float dx=g->actors[i].x-g->x,dy=g->actors[i].y-g->y,d=dx*dx+dy*dy;if(d<nearest){nearest=d;fighting=(int)i;}}
  if(g->vehicle==PLANE||g->vehicle==GLIDER||g->vehicle==PARACHUTE)fighting=-1;float tx=gx,ty=gy;if(fighting>=0){tx=g->actors[fighting].x;ty=g->actors[fighting].y;}
  if(fighting<0&&hypotf(g->x-tx,g->y-ty)<radius)return 0;
  float dx=0,dy=0;if(direction(g,tx,ty,&dx,&dy))return -1;
  // Face the threat, stop close enough to use the sword, then shoot/swing.
  if(fighting>=0&&nearest<16*16)dx=dy=0;
  luma_step(g,(LumaInput){dx,dy,fighting>=0?B_ATTACK:0,fighting>=0?B_SHOOT:0});
 }
 return -1;
}
static int reach(LumaGame *g,unsigned target){const LumaEntity *e=g->world->entities+target;return reach_point(g,e->x,e->y,10);}
static void interact(LumaGame *g){luma_step(g,(LumaInput){0,0,B_INTERACT,0});if(g->dialogue>=0&&g->puzzle<0)luma_step(g,(LumaInput){0,0,B_INTERACT,0});}
static int vehicle(LumaGame *g,unsigned mode){for(unsigned i=0;i<VEHICLES;i++){if(g->vehicle==mode)return 0;luma_step(g,(LumaInput){0,0,B_VEHICLE,0});}return -1;}

#endif
