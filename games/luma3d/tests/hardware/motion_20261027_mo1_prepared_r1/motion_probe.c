#define _POSIX_C_SOURCE 200809L
/* Measurement executable, never the installed playable/demo binary.
 * The unpresented prelude uses legal showcase controls. Fixed-frame runs
 * compare identical simulation states; --wall uses a real 60Hz accumulator. */
#include "luma3d_render.h"
#include "luma3d_showcase.h"
#include <time.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <signal.h>
static volatile sig_atomic_t stopped;
static void stop_signal(int n){(void)n;stopped=1;}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static uint32_t crc(const void *data,size_t n){const unsigned char *p=data;uint32_t v=~0u;while(n--){v^=*p++;for(unsigned b=0;b<8;b++)v=(v>>1)^(0xedb88320u&-(v&1));}return ~v;}
int main(int argc,char **argv){
 unsigned kind=99,frames=0,wall=0,wide=0,host=0;const char *capture=NULL;
 for(int i=1;i<argc;i++){
  if(!strcmp(argv[i],"--host"))host=1;
  else if(!strcmp(argv[i],"--720p"))wide=1;
  else if(!strcmp(argv[i],"--capture")&&i+1<argc)capture=argv[++i];
  else if((!strcmp(argv[i],"--kind")||!strcmp(argv[i],"--frames")||!strcmp(argv[i],"--wall"))&&i+1<argc){
   const char *arg=argv[i];char *end;errno=0;unsigned long n=strtoul(argv[++i],&end,10);if(errno||!*argv[i]||*end||n>3600)return 2;
   if(!strcmp(arg,"--kind"))kind=(unsigned)n;else if(!strcmp(arg,"--frames"))frames=(unsigned)n;else wall=(unsigned)n;
  }else return 2;
 }
 if((kind!=L3_ARCADE_MAZE&&kind!=L3_ARCADE_SHOOTER)||(!frames==!wall)||(capture&&(!host||frames!=1))||(host&&wall))return 2;
 signal(SIGINT,stop_signal);signal(SIGTERM,stop_signal);signal(SIGHUP,stop_signal);
 L3World w;L3Game g;L3Showcase tour;L3Render r;l3_world_init(&w);if(!l3_game_init(&g,&w,1))return 1;l3_showcase_init(&tour,&g,1);
 unsigned replay=0;while(tour.status==1&&g.activities.arcade.active!=kind+1&&replay<100000&&!stopped){l3_showcase_step(&tour,&g,1.f/60);if(!(replay%10))l3_showcase_presented(&tour);replay++;}
 if(stopped||g.activities.arcade.active!=kind+1)return 1;
 printf("MOTION_PROBE kind=%u replay_steps=%u replay_without_render=1 fixed_frames=%u wall_seconds=%u hardware=%u saves=disabled\n",kind,replay,frames,wall,!host);fflush(stdout);
 if(!l3_render_open(&r,host,wide)){l3_render_close(&r);return 1;}l3_presentation_bind(&r,&g);if(!l3_presentation_clock(&r,0,1)){l3_render_close(&r);return 1;}
 if(capture){char path[1024];if(snprintf(path,sizeof path,"%s.commands",capture)>=(int)sizeof path){l3_render_close(&r);return 2;}r.capture=fopen(path,"wb");if(!r.capture){l3_render_close(&r);return 1;}}
 double start=now(),previous=start,complete=start,clock=0,acc=0,sim=0,prep=0,sum=0,max_frame=0;unsigned hist[256]={0},count=0,ok=1,activity_exit=0;
 while(!stopped&&((frames&&count<frames)||(wall&&now()-start<wall))){
  double t=now(),sim_start=t;if(frames)acc=1./60;else{double dt=t-previous;if(dt>.25)dt=.25;if(dt<0)dt=0;acc+=dt;}previous=t;
  while(acc>=1./60){clock+=1./60;if(!l3_presentation_clock(&r,clock,1)){ok=0;break;}l3_showcase_step(&tour,&g,1.f/60);acc-=1./60;}
  if(!ok||!l3_presentation_clock(&r,clock+acc,1)){ok=0;break;}
  if(g.activities.arcade.active!=kind+1){if(frames)ok=0;activity_exit=1;break;}
  sim+=now()-sim_start;double before=now(),feed=r.feed_seconds,present=r.present_seconds;
  if(!l3_render_frame(&r,&g)){ok=0;break;}double end=now();prep+=end-before-(r.feed_seconds-feed)-(r.present_seconds-present);
  double interval=end-complete;complete=end;sum+=interval;if(interval>max_frame)max_frame=interval;hist[interval>=1.02?255:(unsigned)(interval*250)]++;count++;l3_showcase_presented(&tour);
 }
 if(capture){if(fclose(r.capture))ok=0;r.capture=NULL;if(!l3_render_dump(&r,capture))ok=0;}
 unsigned p95=0,p99=0,n=0;for(unsigned i=0;i<256;i++){n+=hist[i];if(!p95&&(uint64_t)n*100>=(uint64_t)count*95)p95=(i+1)*4;if(!p99&&(uint64_t)n*100>=(uint64_t)count*99)p99=(i+1)*4;}
 unsigned char save[L3_ARCADE_SAVE_MAX];size_t encoded=l3_arcade_encode(&g.activities.arcade,save,sizeof save);if(!encoded)ok=0;
 printf("MOTION_COMPLETION activity_exit=%u showcase_status=%u active=%u\n",activity_exit,tour.status,g.activities.arcade.active);
 printf("MOTION_RESULT kind=%u frames=%u simulated=%.6f wall=%.6f simulation=%.6f preparation=%.6f submit=%.6f present=%.6f ui_raster=%.6f ui_publish=%.6f scan_bytes=%llu restore_bytes=%llu ui_bytes=%u commands=%u batches=%u p95_upper_ms=%u p99_upper_ms=%u overflow=%u max_frame=%.6f frame_sum=%.6f state_crc32=%08x moves=%u teleports=%u queue_overflows=%u hardware=%u ok=%u\n",kind,count,clock,now()-start,sim,prep,r.feed_seconds,r.present_seconds,r.mini_raster_seconds,r.mini_publish_seconds,(unsigned long long)r.mini_scan_bytes,(unsigned long long)r.mini_restore_bytes,r.mini_bytes,r.total_commands,r.total_flushes,p95==1024?0:p95,p99==1024?0:p99,hist[255],max_frame,sum,crc(save,encoded),r.maze_motion.moves,r.maze_motion.teleports,r.maze_motion.overflows,!host,ok&&!stopped);fflush(stdout);
 if(!l3_render_close(&r))ok=0;return !ok||stopped;
}
