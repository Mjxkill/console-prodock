/* SPDX-License-Identifier: MIT */
#include "luma.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
const char *const luma_vehicle_names[VEHICLES]={"A pied","Cheval","Parachute","Avion","Parapente","Trottinette","Velo","Voiture"};
static const float speeds[VEHICLES]={82,155,105,250,145,115,140,190};
static float clamp(float x,float a,float b){return x<a?a:x>b?b:x;}
static float dist2(float x,float y){return x*x+y*y;}
static unsigned random_u(LumaGame *g){unsigned x=g->rng;x^=x<<13;x^=x>>17;x^=x<<5;return g->rng=x;}
void luma_notice(LumaGame *g,const char *s){snprintf(g->notice,sizeof(g->notice),"%s",s);g->notice_time=5;}
int luma_walkable(const LumaGame *g,float x,float y,unsigned vehicle){
 const LumaWorld *w=g->world;int tx=(int)floorf(x/w->tile),ty=(int)floorf(y/w->tile);
 if(tx<1||ty<1||tx>=w->width-1||ty>=w->height-1)return 0;
 char c=w->terrain[ty*w->width+tx];
 for(unsigned i=0;i<w->entity_count;i++){const LumaEntity *e=w->entities+i;float ex=g->actors[i].x,ey=g->actors[i].y;if(e->kind==E_DOOR&&!luma_entity_enabled(g,e)&&(int)(ex/w->tile)==tx&&(int)(ey/w->tile)==ty)return 0;if((e->kind==E_CRATE||e->kind==E_MIRROR)&&fabsf(x-ex)<11&&fabsf(y-ey)<11)return 0;}
 if(vehicle==PLANE||vehicle==GLIDER||vehicle==PARACHUTE)return 1;
 return c!='~'&&c!='#'&&c!='t'&&c!='H';
}
static int pass(const LumaGame *g,float x,float y,unsigned vehicle){
 return luma_walkable(g,x-5,y-4,vehicle)&&luma_walkable(g,x+5,y-4,vehicle)&&luma_walkable(g,x-5,y+4,vehicle)&&luma_walkable(g,x+5,y+4,vehicle);
}
void luma_plates_update(LumaGame *g){
 unsigned mask=0,on=0;int air=g->vehicle==PLANE||g->vehicle==GLIDER||g->vehicle==PARACHUTE;
 for(unsigned i=0;i<g->world->entity_count;i++){
  const LumaEntity *p=g->world->entities+i;if(p->kind!=E_PLATE)continue;mask|=p->grants;
  int occupied=!air&&dist2(g->x-p->x,g->y-p->y)<14*14;
  for(unsigned n=0;n<g->world->entity_count;n++)if(g->world->entities[n].kind==E_CRATE&&dist2(g->actors[n].x-p->x,g->actors[n].y-p->y)<14*14)occupied=1;
  if(occupied)on|=p->grants;
 }
 unsigned flags=(g->flags&~mask)|on;if(flags!=g->flags)g->dirty=1;g->flags=flags;
}
static void burst(LumaGame *g,float x,float y,unsigned color){
 for(unsigned n=0;n<10;n++)for(unsigned i=0;i<LUMA_PARTICLES;i++)if(!g->particles[i].live){
  float a=(random_u(g)%6283)/1000.f,s=15+random_u(g)%40;g->particles[i]=(LumaParticle){x,y,cosf(a)*s,sinf(a)*s,0,color,1};break;}
}
void luma_init(LumaGame *g,const LumaWorld *w){
 memset(g,0,sizeof(*g));g->world=w;g->x=w->spawn_x;g->y=w->spawn_y;g->camera_x=g->x;g->camera_y=g->y;
 g->health=g->hearts=6;g->stamina=100;g->face_y=1;g->rng=0x4c554d41;g->unlocked=1;g->dialogue=-1;g->nearby=-1;g->puzzle=-1;
 for(unsigned i=0;i<w->entity_count;i++){const LumaEntity *e=w->entities+i;g->actors[i]=(LumaActor){e->x,e->y,e->hp?e->hp:e->kind==E_BOSS?18:3,0,0,1};}
 luma_plates_update(g);luma_light_init(g);luma_light_update(g);
 luma_notice(g,"Bienvenue. Approchez-vous d'un habitant et appuyez sur E.");
}
int luma_enter(LumaGame *g,unsigned index,float x,float y){
 if(index>=luma_world_count||index>=LUMA_MAX_WORLDS)return -1;
 g->progress[g->world_index]=luma_progress(g);
 LumaProgress p=g->progress[index];g->world_index=index;g->world=luma_worlds+index;g->flags=p.flags;g->collected=p.collected;g->activated=p.activated;g->defeated=p.defeated;g->talked=p.talked;g->missions=p.missions;memcpy(g->mission_steps,p.steps,16);g->puzzle=-1;
 g->x=x>0?x:g->world->spawn_x;g->y=y>0?y:g->world->spawn_y;g->camera_x=g->x;g->camera_y=g->y;g->vx=g->vy=0;g->dialogue=g->nearby=-1;g->vehicle=WALK;
 memset(g->shots,0,sizeof(g->shots));memset(g->particles,0,sizeof(g->particles));
 for(unsigned i=0;i<g->world->entity_count;i++){const LumaEntity *e=g->world->entities+i;g->actors[i]=(LumaActor){e->x,e->y,e->hp?e->hp:e->kind==E_BOSS?18:3,0,0,!(g->defeated&(UINT64_C(1)<<i))};}
 luma_light_init(g);luma_restore_objects(g);luma_plates_update(g);luma_light_update(g);luma_notice(g,g->world->indoors?g->world->name:g->world->title);g->dirty=1;return 0;
}
const char *luma_objective(const LumaGame *g){
 for(unsigned i=0;i<g->world->mission_count;i++){const LumaMission *m=g->world->missions+i;if(m->required&&!(g->missions&(1U<<i))&&(g->missions&m->requires)==m->requires)return m->text;}
 for(unsigned i=0;i<g->world->quest_count;i++){const LumaQuest *q=g->world->quests+i;if(!q->optional&&(g->flags&q->requires)==q->requires&&(g->flags&q->complete)!=q->complete)return q->objective;}
 if(g->world->indoors)return "Lire les inscriptions, résoudre la salle et rejoindre la porte.";
 if(!(g->flags&1))return "Rencontrer la gardienne du village";
 if((g->flags&14)!=14)return "Retrouver et rallumer les trois balises";
 if(!(g->flags&16))return "Apaiser le gardien de l'observatoire";
 if(!(g->flags&32))return "Ouvrir l'observatoire des mondes";
 return "Explorer les sentiers, secrets et nouvelles montures";
}
static void unlock(LumaGame *g,unsigned vehicle){if(vehicle<VEHICLES){g->unlocked|=1U<<vehicle;g->dirty=1;}}
static void hurt(LumaGame *g,float x,float y){
 if(g->invincible>0)return;g->damage++;g->health--;g->invincible=1.2f;burst(g,g->x,g->y,0xf9a7);
 float d=sqrtf(dist2(g->x-x,g->y-y));if(d>0){g->vx+=(g->x-x)*150/d;g->vy+=(g->y-y)*150/d;}
 if(!g->health){g->deaths++;g->health=g->hearts;g->x=g->world->spawn_x;g->y=g->world->spawn_y;g->vehicle=WALK;g->stamina=100;luma_notice(g,"Les lucioles vous ramènent au village. Votre carnet et vos éclats sont en sécurité.");g->dirty=1;}
}
static void hit_actor(LumaGame *g,unsigned i,float damage){
 LumaActor *a=g->actors+i;const LumaEntity *e=g->world->entities+i;if(!a->alive||a->stun>0||!luma_entity_enabled(g,e))return;
 a->hp-=damage;a->stun=.2f;burst(g,a->x,a->y,0xffd2);
 if(a->hp<=0){a->alive=0;g->defeated|=UINT64_C(1)<<i;g->kills++;g->crystals+=e->kind==E_BOSS?8:2;g->flags|=e->grants;g->dirty=1;
  if(e->kind==E_BOSS){luma_notice(g,"Le gardien retrouve sa mémoire. L'observatoire vous attend.");}}
}
static void interact(LumaGame *g){
 if(g->dialogue>=0){g->dialogue=-1;g->puzzle=-1;return;}
 if(g->nearby<0){luma_notice(g,"Explorez : les lucioles signalent les lieux à découvrir.");return;}
 unsigned i=(unsigned)g->nearby;const LumaEntity *e=g->world->entities+i;uint64_t bit=UINT64_C(1)<<i;
 if(!luma_entity_enabled(g,e)){luma_notice(g,"Ce lieu attend que votre voyage avance. Consultez le journal (J).");return;}
 if(e->kind==E_DOOR){g->talked|=bit;g->flags|=e->grants;g->dirty=1;if(e->target_world==(int)g->world_index){g->x=e->target_x;g->y=e->target_y;g->camera_x=g->x;g->camera_y=g->y;g->vx=g->vy=0;}else if(e->target_world>=0)luma_enter(g,(unsigned)e->target_world,e->target_x,e->target_y);return;}
 if(e->kind==E_CRATE){LumaActor *a=g->actors+i;int dx=0,dy=0;if(fabsf(g->face_x)>fabsf(g->face_y))dx=g->face_x>0?1:-1;else dy=g->face_y>0?1:-1;float nx=a->x+dx*g->world->tile,ny=a->y+dy*g->world->tile;if(pass(g,nx,ny,WALK)){a->x=nx;a->y=ny;g->dirty=1;g->light_dirty=1;g->talked|=bit;}else luma_notice(g,"La caisse ne peut pas passer ici.");return;}
 if(e->kind==E_MIRROR){g->mirror_orientation[i]^=1;g->light_dirty=1;g->dirty=1;g->talked|=bit;luma_notice(g,g->mirror_orientation[i]?"Le miroir incline la lumière : \\":"Le miroir incline la lumière : /");return;}
 if(e->kind==E_SWITCH){g->flags^=e->grants;g->talked|=bit;g->dirty=1;luma_notice(g,e->after);return;}
 if(e->kind==E_SEQUENCE){unsigned expected=(g->flags>>24)+1;if(e->cost==expected){g->flags=(g->flags&0xffffff)|(e->cost<<24);g->flags|=e->grants;g->talked|=bit;luma_notice(g,e->after);}else{unsigned mask=0;for(unsigned n=0;n<g->world->entity_count;n++)if(g->world->entities[n].kind==E_SEQUENCE)mask|=g->world->entities[n].grants;g->flags&=~(mask|0xff000000U);luma_notice(g,"La mélodie retombe. Retrouvez l'ordre indiqué dans la salle.");}g->dirty=1;return;}
 for(unsigned m=0;m<g->world->mission_count;m++){const LumaMission *q=g->world->missions+m;if(q->type==M_CHOICE&&q->target==i&&!(g->missions&(1U<<m))&&(g->missions&q->requires)==q->requires){g->puzzle=(int)m;g->dialogue=(int)i;return;}}
 if(e->kind==E_NPC||e->kind==E_SIGN){g->talked|=bit;g->dialogue=(int)i;g->dialogue_page=e->grants&&(g->flags&e->grants)==e->grants;g->flags|=e->grants;g->dirty=1;unlock(g,e->vehicle);return;}
 if(e->kind==E_STABLE){g->talked|=bit;unlock(g,e->vehicle);g->vehicle=e->vehicle;luma_notice(g,luma_vehicle_names[g->vehicle]);return;}
 if(e->kind!=E_PORTAL&&((g->activated|g->collected)&bit)){luma_notice(g,e->after&&e->after[0]?e->after:"La lumière de ce lieu est revenue.");return;}
 if(e->kind==E_PORTAL&&e->target_world>(int)g->world_index&&!luma_missions_complete(g)){luma_notice(g,"Le chapitre attend encore vos découvertes. Consultez le carnet (J).");return;}
 if(e->kind==E_PORTAL&&e->target_world<0&&!luma_missions_complete(g)){luma_notice(g,"Les derniers liens attendent d’être renoués. Consultez le carnet (J).");return;}
 if(e->kind==E_SHRINE){
  for(unsigned n=0;n<g->world->entity_count;n++){unsigned k=g->world->entities[n].kind;if((k==E_ENEMY||k==E_BOSS)&&g->actors[n].alive&&dist2(g->actors[n].x-e->x,g->actors[n].y-e->y)<100*100){luma_notice(g,"Les ombres troublent la balise. Repoussez-les avec l'épée ou l'arc.");return;}}
  if(g->crystals<e->cost){luma_notice(g,"Il manque des éclats. Cherchez les cristaux et les coffres.");return;}
  g->crystals-=e->cost;g->activated|=bit;g->flags|=e->grants;unlock(g,e->vehicle);g->health=g->hearts;
  luma_notice(g,e->after);
 } else if(e->kind==E_CHEST){g->collected|=bit;g->flags|=e->grants;g->crystals+=e->cost?e->cost:4;g->secrets++;unlock(g,e->vehicle);luma_notice(g,e->after);}
 else if(e->kind==E_PORTAL){g->flags|=e->grants;g->activated|=bit;if(e->target_world<0){g->won=1;g->ending_open=1;}luma_notice(g,e->after);if(e->target_world>=0){luma_enter(g,(unsigned)e->target_world,e->target_x,e->target_y);return;}}
 g->talked|=bit;g->dirty=1;burst(g,e->x,e->y,0xaffe);
}
static int projectile_clear(const LumaGame *g,float x,float y){int tx=(int)floorf(x/g->world->tile),ty=(int)floorf(y/g->world->tile);if(tx<0||ty<0||tx>=g->world->width||ty>=g->world->height)return 0;char c=g->world->terrain[ty*g->world->width+tx];if(c=='#'||c=='t'||c=='H')return 0;for(unsigned i=0;i<g->world->entity_count;i++){const LumaEntity *e=g->world->entities+i;if((e->kind==E_CRATE||e->kind==E_MIRROR||(e->kind==E_DOOR&&!luma_entity_enabled(g,e)))&&fabsf(g->actors[i].x-x)<12&&fabsf(g->actors[i].y-y)<12)return 0;}return 1;}
static void shoot(LumaGame *g){if(g->fire>0)return;for(unsigned i=0;i<LUMA_SHOTS;i++)if(!g->shots[i].live){g->shots[i]=(LumaShot){g->x,g->y-8,g->face_x*230,g->face_y*230,0,1,0};g->fire=.28f;g->shots_fired++;break;}}
void luma_step(LumaGame *g,LumaInput in){
 if(g->ending_open){if(in.pressed&(B_INTERACT|B_PAUSE|B_ATTACK)){g->ending_open=0;luma_notice(g,"Votre voyage continue. Les anciens chemins gardent encore des secrets.");}return;}
 const float dt=1.f/LUMA_HZ;if(in.pressed&B_PAUSE)g->paused=!g->paused;
 if(in.pressed&B_HELP)g->help=!g->help;
 if(in.pressed&B_MAP)g->map=!g->map;if(in.pressed&B_JOURNAL)g->journal=!g->journal;
 if(g->paused)return;
 if((in.pressed&B_RESET)&&g->world->indoors){unsigned mask=0xff000000U;for(unsigned i=0;i<g->world->entity_count;i++){const LumaEntity *e=g->world->entities+i;if(e->kind==E_SWITCH||e->kind==E_TARGET||e->kind==E_PLATE||e->kind==E_SEQUENCE||e->kind==E_RECEIVER)mask|=e->grants;if(e->kind==E_MIRROR)g->mirror_orientation[i]=e->cost&1;if(e->kind==E_CRATE){g->actors[i].x=e->x;g->actors[i].y=e->y;}}g->flags&=~mask;g->x=g->world->spawn_x;g->y=g->world->spawn_y;g->camera_x=g->x;g->camera_y=g->y;g->vx=g->vy=0;g->dirty=1;g->light_dirty=1;luma_notice(g,"Salle réinitialisée. Vos trésors et les autres salles sont conservés.");}
 luma_plates_update(g);luma_light_update(g);
 if(in.pressed&B_INTERACT)interact(g);
 if(g->puzzle>=0){unsigned choice=in.pressed&B_CHOICE1?0:in.pressed&B_CHOICE2?1:in.pressed&B_CHOICE3?2:3;if(choice<3){const LumaMission *m=g->world->missions+g->puzzle;if(choice==m->answer){g->mission_steps[g->puzzle]=1;g->talked|=UINT64_C(1)<<m->target;g->dialogue=-1;g->puzzle=-1;}else luma_notice(g,m->feedback);}}
 luma_plates_update(g);luma_light_update(g);luma_missions_update(g);
 if(g->dialogue>=0||g->map||g->journal||g->help||g->ending_open)return;
 g->tick++;g->time+=dt;g->invincible=fmaxf(0,g->invincible-dt);g->attack=fmaxf(0,g->attack-dt);g->fire=fmaxf(0,g->fire-dt);g->notice_time=fmaxf(0,g->notice_time-dt);
 if((in.pressed&B_VEHICLE)&&!g->world->indoors){unsigned v=g->vehicle;for(unsigned n=0;n<VEHICLES;n++){v=(v+1)%VEHICLES;if((g->unlocked&(1U<<v))&&pass(g,g->x,g->y,v)){g->vehicle=v;luma_notice(g,luma_vehicle_names[v]);break;}}}
 if((in.pressed&B_ATTACK)&&!g->attack){g->attack=.3f;for(unsigned i=0;i<g->world->entity_count;i++){unsigned k=g->world->entities[i].kind;float dx=g->actors[i].x-g->x,dy=g->actors[i].y-g->y;if((k==E_ENEMY||k==E_BOSS)&&dist2(dx,dy)<43*43&&(dx*g->face_x+dy*g->face_y)>-9)hit_actor(g,i,1);}}
 if(in.held&B_SHOOT)shoot(g);
 float len=sqrtf(dist2(in.dx,in.dy));if(len>1){in.dx/=len;in.dy/=len;}if(len>.1f){g->face_x=in.dx/fmaxf(len,1);g->face_y=in.dy/fmaxf(len,1);float d=sqrtf(dist2(g->face_x,g->face_y));g->face_x/=d;g->face_y/=d;}
 unsigned v=g->vehicle;float speed=speeds[v],accel=(v==CAR||v==PLANE)?2.5f:12;
 if(v==PLANE&&len<.1f){in.dx=g->face_x*.55f;in.dy=g->face_y*.55f;}
 int air=v==PLANE||v==GLIDER||v==PARACHUTE;
 if(air){g->stamina=fmaxf(0,g->stamina-dt*(v==PLANE?3:5));if(g->stamina<=0&&pass(g,g->x,g->y,WALK)){g->vehicle=WALK;luma_notice(g,"Retour au sol. Reposez-vous pour reprendre votre souffle.");}}
 else g->stamina=fminf(100,g->stamina+dt*10);
 g->vx+=(in.dx*speed-g->vx)*accel*dt;g->vy+=(in.dy*speed-g->vy)*accel*dt;
 float x=g->x+g->vx*dt,y=g->y+g->vy*dt;if(pass(g,x,g->y,g->vehicle))g->x=x;else g->vx=0;if(pass(g,g->x,y,g->vehicle))g->y=y;else g->vy=0;
 g->camera_x+=(g->x-g->camera_x)*.09f;g->camera_y+=(g->y-g->camera_y)*.09f;
 int region=(int)(g->x/(g->world->width*g->world->tile/4.f))+(int)(g->y/(g->world->height*g->world->tile/4.f))*4;if(region>=0&&region<16)g->visited|=1U<<region;
 g->nearby=-1;float near=48*48;
 for(unsigned i=0;i<g->world->entity_count;i++){
  const LumaEntity *e=g->world->entities+i;LumaActor *a=g->actors+i;uint64_t bit=UINT64_C(1)<<i;
  float dx=g->x-a->x,dy=g->y-a->y,d=dist2(dx,dy);a->stun=fmaxf(0,a->stun-dt);a->cooldown=fmaxf(0,a->cooldown-dt);
  if(e->kind==E_ENEMY||e->kind==E_BOSS){if(!a->alive||!luma_entity_enabled(g,e))continue;
   if(!e->behavior&&d<190*190&&d>15*15){float inv=1/sqrtf(d),s=e->kind==E_BOSS?36:48,nx=a->x+dx*inv*s*dt,ny=a->y+dy*inv*s*dt;if(pass(g,nx,a->y,WALK))a->x=nx;if(pass(g,a->x,ny,WALK))a->y=ny;}
   if(d<20*20&&!air)hurt(g,a->x,a->y);
   if((e->kind==E_BOSS||e->behavior==1)&&d<300*300&&!a->cooldown){for(unsigned n=0;n<LUMA_SHOTS;n++)if(!g->shots[n].live){float angle=atan2f(dy,dx);g->shots[n]=(LumaShot){a->x,a->y,cosf(angle)*105,sinf(angle)*105,0,1,1};break;}a->cooldown=e->shot_period>0?e->shot_period:e->kind==E_BOSS?.8f:1.4f;}
  }else if(e->kind==E_CRYSTAL){if(!(g->collected&bit)&&d<20*20){g->collected|=bit;g->crystals++;g->dirty=1;burst(g,e->x,e->y,0x9fff);}}
  else if(e->kind!=E_LAMP&&e->kind!=E_PLATE&&e->kind!=E_TARGET&&e->kind!=E_EMITTER&&e->kind!=E_RECEIVER&&d<48*48){float score=d;if((e->kind==E_CRATE||e->kind==E_MIRROR)&&d>0){float facing=(-dx*g->face_x-dy*g->face_y)/sqrtf(d);score+=1024*(1-clamp(facing,-1,1));}if(score<near){g->nearby=(int)i;near=score;}}
 }
 for(unsigned i=0;i<LUMA_SHOTS;i++){LumaShot *s=g->shots+i;if(!s->live)continue;s->x+=s->vx*dt;s->y+=s->vy*dt;s->age+=dt;if(s->age>1.8f||!projectile_clear(g,s->x,s->y)){s->live=0;continue;}
  if(s->hostile){if(dist2(s->x-g->x,s->y-g->y)<14*14){hurt(g,s->x,s->y);s->live=0;}}
  else for(unsigned n=0;n<g->world->entity_count;n++){const LumaEntity *target=g->world->entities+n;if(target->kind==E_TARGET&&luma_entity_enabled(g,target)&&dist2(s->x-g->actors[n].x,s->y-g->actors[n].y)<18*18){g->flags^=target->grants;g->talked|=UINT64_C(1)<<n;g->dirty=1;s->live=0;burst(g,target->x,target->y,0xaffe);break;}unsigned k=g->world->entities[n].kind;LumaActor *a=g->actors+n;if((k==E_ENEMY||k==E_BOSS)&&a->alive&&luma_entity_enabled(g,g->world->entities+n)&&dist2(s->x-a->x,s->y-a->y)<18*18){hit_actor(g,n,1);s->live=0;break;}}
 }
 for(unsigned i=0;i<LUMA_PARTICLES;i++){LumaParticle *p=g->particles+i;if(p->live){p->age+=dt;p->x+=p->vx*dt;p->y+=p->vy*dt;p->vy+=35*dt;if(p->age>.7f)p->live=0;}}
 g->x=clamp(g->x,0,g->world->width*g->world->tile-1);g->y=clamp(g->y,0,g->world->height*g->world->tile-1);luma_plates_update(g);luma_light_update(g);luma_missions_update(g);
}
