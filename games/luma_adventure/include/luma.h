/* SPDX-License-Identifier: MIT */
#ifndef LUMA_H
#define LUMA_H
#include <stdint.h>
#define LUMA_HZ 60
#define LUMA_MAX_WORLDS 96
#define LUMA_MAX_ENTITIES 64
#define LUMA_SHOTS 32
#define LUMA_PARTICLES 48
#define LUMA_BEAMS 256
enum { E_NPC, E_SHRINE, E_CHEST, E_CRYSTAL, E_ENEMY, E_SIGN, E_PORTAL, E_STABLE, E_BOSS, E_DOOR, E_SWITCH, E_TARGET, E_PLATE, E_CRATE, E_SEQUENCE, E_LAMP, E_EMITTER, E_MIRROR, E_RECEIVER };
enum { WALK, HORSE, PARACHUTE, PLANE, GLIDER, SCOOTER, BIKE, CAR, VEHICLES };
enum { B_INTERACT=1, B_ATTACK=2, B_SHOOT=4, B_VEHICLE=8, B_MAP=16, B_JOURNAL=32, B_PAUSE=64, B_CHOICE1=128, B_CHOICE2=256, B_CHOICE3=512, B_RESET=1024, B_HELP=2048 };
typedef struct { const char *id,*name,*text,*after; float x,y; unsigned kind,requires,grants,cost,vehicle,art; int target_world; float target_x,target_y; unsigned forbids,hp,behavior;float shot_period; } LumaEntity;
enum { M_TALK, M_VISIT, M_COLLECT, M_DEFEAT, M_CHOICE, M_ROUTE, M_DUNGEON };
typedef struct { float x,y,radius; } LumaCheckpoint;
typedef struct { const char *id,*title,*text,*options[3],*feedback; unsigned type,requires,target,count,vehicle,answer,reward_vehicle,reward_crystals,reward_flags,required; uint64_t targets; const LumaCheckpoint *points; unsigned point_count; } LumaMission;
typedef struct { const char *title,*objective; unsigned requires,complete,optional; } LumaQuest;
typedef struct { const char *title,*name,*id; int width,height,tile; const char *terrain; float spawn_x,spawn_y; unsigned entity_count; const LumaEntity *entities; const LumaQuest *quests; unsigned quest_count; const LumaMission *missions; unsigned mission_count,indoors; } LumaWorld;
typedef struct { float dx,dy; unsigned pressed,held; } LumaInput;
typedef struct { float x,y,vx,vy,age; int live,hostile; } LumaShot;
typedef struct { float x,y,vx,vy,age; unsigned color; int live; } LumaParticle;
typedef struct { float x,y,hp,cooldown,stun; int alive; } LumaActor;
typedef struct { uint16_t x1,y1,x2,y2; } LumaBeam;
typedef struct { unsigned flags; uint64_t collected,activated,defeated,talked; unsigned missions; uint8_t steps[16]; uint32_t objects[64]; } LumaProgress;
typedef struct {
 const LumaWorld *world;
 unsigned world_index; LumaProgress progress[LUMA_MAX_WORLDS];
 float x,y,vx,vy,face_x,face_y,camera_x,camera_y,time,stamina,invincible,attack,fire;
 unsigned tick,flags,unlocked,vehicle,crystals,health,hearts,kills,deaths,visited;
 uint64_t collected,activated,defeated,talked;
 unsigned missions; uint8_t mission_steps[16]; int puzzle;
 unsigned rng,shots_fired,secrets,damage;
 int paused,map,journal,help,dialogue,dialogue_page,nearby,won,ending_open,dirty;
 char notice[128]; float notice_time;
 LumaActor actors[LUMA_MAX_ENTITIES]; LumaShot shots[LUMA_SHOTS]; LumaParticle particles[LUMA_PARTICLES];
 uint8_t mirror_orientation[LUMA_MAX_ENTITIES];LumaBeam beams[LUMA_BEAMS];
 unsigned beam_count,light_network,light_flags,light_dirty,light_fault;uint64_t receivers_lit;
} LumaGame;
static inline int luma_entity_enabled(const LumaGame *g,const LumaEntity *e){return (g->flags&e->requires)==e->requires&&!(g->flags&e->forbids);}
extern const LumaWorld luma_worlds[];
extern const unsigned luma_world_count;
#define luma_world luma_worlds[0]
extern const char *const luma_vehicle_names[VEHICLES];
void luma_init(LumaGame *g,const LumaWorld *w);
int luma_enter(LumaGame *g,unsigned index,float x,float y);
void luma_step(LumaGame *g,LumaInput input);
int luma_walkable(const LumaGame *g,float x,float y,unsigned vehicle);
const char *luma_objective(const LumaGame *g);
void luma_missions_update(LumaGame *g);
int luma_missions_complete(const LumaGame *g);
void luma_restore_objects(LumaGame *g);
void luma_light_init(LumaGame *g);
void luma_light_update(LumaGame *g);
void luma_plates_update(LumaGame *g);
LumaProgress luma_progress(const LumaGame *g);
void luma_notice(LumaGame *g,const char *text);
int luma_save(const LumaGame *g,const char *path);
int luma_load(LumaGame *g,const char *path);
uint32_t luma_crc(const void *data,unsigned n);
#endif
