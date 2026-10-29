#define _POSIX_C_SOURCE 200809L
/* Diagnostic only. No save file is opened. Real showcase controls are used;
 * fixed-frame windows compare states, --wall uses the ordinary accumulator. */
#include "luma3d_render.h"
#include "luma3d_showcase.h"
#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
static volatile sig_atomic_t stopped;
static void stop_signal(int n){(void)n;stopped=1;}
double l3_probe_time(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
typedef struct {uint64_t bytes[2];double seconds[2];} MeshCost;
static MeshCost mesh_cost;
void l3_probe_mesh_publish(unsigned offset,unsigned bytes,double seconds){unsigned i=offset>=(26u<<20);mesh_cost.bytes[i]+=bytes;mesh_cost.seconds[i]+=seconds;}
typedef struct {unsigned moves,teleports,overflows,contacts,fallbacks;} Motion;
static Motion motion(const L3Render *r){
#ifdef L3_MOTION_CANDIDATE
 return (Motion){r->maze_motion.moves,r->maze_motion.teleports,r->maze_motion.overflows,r->maze_motion.contacts,r->maze_motion.contact_fallbacks};
#else
 (void)r;return (Motion){0};
#endif
}
static unsigned delta(unsigned old,unsigned value){return value>=old?value-old:value;}
static void accumulate(Motion *sum,Motion a,Motion b){sum->moves+=delta(a.moves,b.moves);sum->teleports+=delta(a.teleports,b.teleports);sum->overflows+=delta(a.overflows,b.overflows);sum->contacts+=delta(a.contacts,b.contacts);sum->fallbacks+=delta(a.fallbacks,b.fallbacks);}
static int presentation_clock(L3Render *r,double t){
#ifdef L3_MOTION_CANDIDATE
 return l3_presentation_clock(r,t,1);
#else
 (void)r;(void)t;return 1;
#endif
}
static uint32_t crc(const void *data,size_t n){const unsigned char *p=data;uint32_t c=~0u;while(n--){c^=*p++;for(unsigned b=0;b<8;b++)c=(c>>1)^(0xedb88320u&-(c&1));}return ~c;}
typedef struct {unsigned index,page,commands,draws,triangles,ui_bytes,rasters;double total,simulation,preparation,submit,present,mesh_publish;} Frame;
typedef struct {
 const char *name;unsigned frames,hist[256],max_index,commands,batches,ui_bytes,rasters;
 double wall,sum,simulation,preparation,submit,present,max;
 MeshCost mesh;Frame top[8];unsigned top_count;Motion motion;
 struct prodock_display_info display_before,display_after;
 struct prodock_geometry_info geometry_before,geometry_after;
 uint32_t state_crc;unsigned exited;
} Phase;
static int counters(L3Render *r,struct prodock_display_info *d,struct prodock_geometry_info *g){
 memset(d,0,sizeof *d);memset(g,0,sizeof *g);if(r->host)return 1;
 return !ioctl(r->display,PRODOCK_DISPLAY_INFO,d)&&!ioctl(r->fd,PRODOCK_GEOMETRY_INFO,g)&&g->signature==PRODOCK_GEOMETRY_SIGNATURE&&!g->errors&&!d->errors&&!d->underflows&&!d->invalid_layers&&!d->invalid_sprites&&!d->faulted;
}
static void top_insert(Phase *p,Frame f){unsigned n=p->top_count;if(n<8)p->top_count++;else if(f.total<=p->top[7].total)return;else n=7;while(n&&p->top[n-1].total<f.total){p->top[n]=p->top[n-1];n--;}p->top[n]=f;}
static unsigned percentile(const Phase *p,unsigned percent){unsigned n=0;for(unsigned i=0;i<256;i++){n+=p->hist[i];if((uint64_t)n*100>=(uint64_t)p->frames*percent)return i==255?0:(i+1)*4;}return 0;}
static int run_phase(Phase *p,L3Render *r,L3Game *g,L3Showcase *tour,unsigned kind,unsigned limit,unsigned wall,unsigned advance,double *clock){
 if(!counters(r,&p->display_before,&p->geometry_before))return 0;
 unsigned cmd=r->total_commands,batches=r->total_flushes,ui=r->mini_bytes,rasters=r->mini_rasterizations;
 double feed=r->feed_seconds,present=r->present_seconds;MeshCost old_mesh=mesh_cost;
 double start=l3_probe_time(),previous=start,complete=start,acc=0;
 while(!stopped&&((limit&&p->frames<limit)||(wall&&l3_probe_time()-start<wall))){
  double t=l3_probe_time(),sim_start=t;Motion before_motion=motion(r);
  if(advance){if(limit)acc=1./60;else{double dt=t-previous;if(dt>.25)dt=.25;if(dt<0)dt=0;acc+=dt;}}
  previous=t;
  while(acc>=1./60){*clock+=1./60;if(!presentation_clock(r,*clock))return 0;Motion old=motion(r);l3_showcase_step(tour,g,1.f/60);accumulate(&p->motion,old,motion(r));acc-=1./60;}
  (void)before_motion;
  if(!presentation_clock(r,*clock+acc))return 0;
  if(g->activities.arcade.active!=kind+1){p->exited=1;break;}
  Frame f={.index=r->frame,.page=r->frame&1};f.simulation=l3_probe_time()-sim_start;
  double before=l3_probe_time(),old_feed=r->feed_seconds,old_present=r->present_seconds;
  double pub=mesh_cost.seconds[0]+mesh_cost.seconds[1];unsigned old_ui=r->mini_bytes,old_raster=r->mini_rasterizations;
  if(!l3_render_frame(r,g))return 0;double end=l3_probe_time();
  f.submit=r->feed_seconds-old_feed;f.present=r->present_seconds-old_present;f.preparation=end-before-f.submit-f.present;
  f.total=end-complete;complete=end;f.mesh_publish=mesh_cost.seconds[0]+mesh_cost.seconds[1]-pub;
  f.commands=r->commands;f.draws=r->draws;f.triangles=r->triangles;f.ui_bytes=r->mini_bytes-old_ui;f.rasters=r->mini_rasterizations-old_raster;
  p->sum+=f.total;p->simulation+=f.simulation;p->preparation+=f.preparation;
  if(f.total>p->max){p->max=f.total;p->max_index=f.index;}
  p->hist[f.total>=1.02?255:(unsigned)(f.total*250)]++;p->frames++;top_insert(p,f);l3_showcase_presented(tour);
 }
 p->wall=l3_probe_time()-start;p->submit=r->feed_seconds-feed;p->present=r->present_seconds-present;
 p->commands=r->total_commands-cmd;p->batches=r->total_flushes-batches;p->ui_bytes=r->mini_bytes-ui;p->rasters=r->mini_rasterizations-rasters;
 for(unsigned i=0;i<2;i++){p->mesh.bytes[i]=mesh_cost.bytes[i]-old_mesh.bytes[i];p->mesh.seconds[i]=mesh_cost.seconds[i]-old_mesh.seconds[i];}
 unsigned char data[L3_ARCADE_SAVE_MAX];size_t n=l3_arcade_encode(&g->activities.arcade,data,sizeof data);if(!n)return 0;p->state_crc=crc(data,n);
 return !stopped&&p->frames&&counters(r,&p->display_after,&p->geometry_after);
}
static void print_phase(const Phase *p,unsigned kind,unsigned hardware){
 printf("GPU_PHASE kind=%u name=%s frames=%u wall=%.9f frame_sum=%.9f simulation=%.9f preparation=%.9f submit=%.9f present=%.9f commands=%u batches=%u ui_bytes=%u rasters=%u static_bytes=%llu dynamic_bytes=%llu static_publish=%.9f dynamic_publish=%.9f p95_upper_ms=%u p99_upper_ms=%u overflow=%u max_frame=%.9f max_index=%u moves=%u teleports=%u queue_overflows=%u contacts=%u contact_fallbacks=%u exited=%u state_crc32=%08x hardware=%u\n",kind,p->name,p->frames,p->wall,p->sum,p->simulation,p->preparation,p->submit,p->present,p->commands,p->batches,p->ui_bytes,p->rasters,(unsigned long long)p->mesh.bytes[0],(unsigned long long)p->mesh.bytes[1],p->mesh.seconds[0],p->mesh.seconds[1],percentile(p,95),percentile(p,99),p->hist[255],p->max,p->max_index,p->motion.moves,p->motion.teleports,p->motion.overflows,p->motion.contacts,p->motion.fallbacks,p->exited,p->state_crc,hardware);
 const struct prodock_display_info *a=&p->display_before,*b=&p->display_after;const struct prodock_geometry_info *x=&p->geometry_before,*y=&p->geometry_after;
 printf("GPU_COUNTERS name=%s feed_us=%u wait_us=%u cache_us=%u present_us=%u presents=%u vertices=%u triangles=%u culled=%u slivers=%u cycles_mod32=%u hardware=%u\n",p->name,b->feed_us-a->feed_us,b->wait_us-a->wait_us,b->cache_us-a->cache_us,b->present_us-a->present_us,b->game_presents-a->game_presents,y->vertices-x->vertices,y->triangles-x->triangles,y->culled-x->culled,y->slivers-x->slivers,y->cycles-x->cycles,hardware);
 for(unsigned i=0;i<p->top_count;i++){const Frame *f=&p->top[i];printf("GPU_TOP name=%s rank=%u index=%u page=%u total=%.9f simulation=%.9f preparation=%.9f submit=%.9f present=%.9f mesh_publish=%.9f commands=%u draws=%u triangles=%u ui_bytes=%u rasters=%u\n",p->name,i,f->index,f->page,f->total,f->simulation,f->preparation,f->submit,f->present,f->mesh_publish,f->commands,f->draws,f->triangles,f->ui_bytes,f->rasters);}
}
int main(int argc,char **argv){
 unsigned kind=99,frames=0,wall=0,host=0,wide=0,fixture=0;const char *capture=NULL;
 for(int i=1;i<argc;i++){
  if(!strcmp(argv[i],"--host"))host=1;else if(!strcmp(argv[i],"--720p"))wide=1;else if(!strcmp(argv[i],"--fixture"))fixture=1;
  else if(!strcmp(argv[i],"--capture")&&i+1<argc)capture=argv[++i];
  else if((!strcmp(argv[i],"--kind")||!strcmp(argv[i],"--frames")||!strcmp(argv[i],"--wall"))&&i+1<argc){const char *key=argv[i],*value=argv[++i];char *end;errno=0;unsigned long n=strtoul(value,&end,10);if(errno||!*value||*end||n>3600)return 2;if(!strcmp(key,"--kind"))kind=n;else if(!strcmp(key,"--frames"))frames=n;else wall=n;}
  else return 2;
 }
 if((kind!=1&&kind!=3&&kind!=4&&kind!=5&&kind!=6)||(!frames==!wall)||(host&&wall)||(fixture&&(frames>63||wall))||(capture&&(!host||!fixture)))return 2;
 signal(SIGINT,stop_signal);signal(SIGTERM,stop_signal);signal(SIGHUP,stop_signal);
 L3World w;L3Game g;L3Showcase tour;L3Render r;l3_world_init(&w);if(!l3_game_init(&g,&w,1))return 1;l3_showcase_init(&tour,&g,1);
 unsigned replay=0;while(tour.status==1&&g.activities.arcade.active!=kind+1&&replay<100000&&!stopped){l3_showcase_step(&tour,&g,1.f/60);if(!(replay%10))l3_showcase_presented(&tour);replay++;}
 if(stopped||g.activities.arcade.active!=kind+1)return 1;
 printf("GPU_PROBE kind=%u replay_steps=%u replay_without_render=1 fixed_frames=%u wall_seconds=%u fixture=%u hardware=%u saves=disabled\n",kind,replay,frames,wall,fixture,!host);fflush(stdout);
 if(!l3_render_open(&r,host,wide)){l3_render_close(&r);return 1;}
#ifdef L3_MOTION_CANDIDATE
 l3_presentation_bind(&r,&g);
#endif
 double clock=0;if(!presentation_clock(&r,0)){l3_render_close(&r);return 1;}
 if(capture){char path[1024];if(snprintf(path,sizeof path,"%s.commands",capture)>=(int)sizeof path){l3_render_close(&r);return 2;}r.capture=fopen(path,"wb");if(!r.capture){l3_render_close(&r);return 1;}}
 Phase phases[3]={{.name="entry"},{.name="rest"},{.name="moving"}};unsigned count=fixture?1:3;int ok=run_phase(&phases[0],&r,&g,&tour,kind,fixture?frames:2,0,fixture&&frames>1,&clock);
 if(ok&&!fixture)ok=run_phase(&phases[1],&r,&g,&tour,kind,12,0,0,&clock);
 if(ok&&!fixture)ok=run_phase(&phases[2],&r,&g,&tour,kind,frames,wall,1,&clock);
 if(capture){long n=ftell(r.capture);if(n<0||n%32)ok=0;else r.commands=(unsigned)(n/32);if(fclose(r.capture))ok=0;r.capture=NULL;if(!l3_render_dump(&r,capture))ok=0;}
 for(unsigned i=0;i<count;i++)if(phases[i].frames)print_phase(&phases[i],kind,!host);
 printf("GPU_DONE ok=%u active=%u showcase=%u simulated=%.9f hardware=%u\n",ok&&!stopped,g.activities.arcade.active,tour.status,clock,!host);fflush(stdout);
 if(!l3_render_close(&r))ok=0;return !ok||stopped;
}
