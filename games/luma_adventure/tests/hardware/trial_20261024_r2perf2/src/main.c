/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include "luma.h"
#include "video.h"
#include <errno.h>
#include <fcntl.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>
#ifdef LUMA_HOST
#include <SDL.h>
#else
#include "neo-gamepad-input.h"
#endif
static volatile sig_atomic_t stopping;
static void stop(int sig){(void)sig;stopping=1;}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static int number(const char *s,unsigned *out){char *end;unsigned long n=strtoul(s,&end,10);if(*end||n>10000000)return -1;*out=(unsigned)n;return 0;}
int main(int argc,char **argv){
 int host=0,headless=0,wide=0,demo=0,nosave=0,newgame=0,changed=0,rc=1;unsigned limit=0,start_world=0,warmup=0;
 const char *assets="build/luma.pak",*save="luma.sav",*snapshot=NULL;
#ifdef LUMA_HOST
 host=1;
#else
 assets="/tmp/luma.lz4";save="/tmp/luma.sav";
#endif
 for(int i=1;i<argc;i++){
  if(!strcmp(argv[i],"--headless"))headless=1;else if(!strcmp(argv[i],"--720p"))wide=1;else if(!strcmp(argv[i],"--demo"))demo=1;else if(!strcmp(argv[i],"--no-save"))nosave=1;else if(!strcmp(argv[i],"--new"))newgame=1;
  else if(i+1<argc&&!strcmp(argv[i],"--frames")){if(number(argv[++i],&limit)||!limit)return 2;}
  else if(i+1<argc&&!strcmp(argv[i],"--warmup")){if(number(argv[++i],&warmup))return 2;}
  else if(i+1<argc&&!strcmp(argv[i],"--world")){if(number(argv[++i],&start_world)||start_world>=luma_world_count)return 2;}
  else if(i+1<argc&&!strcmp(argv[i],"--assets"))assets=argv[++i];else if(i+1<argc&&!strcmp(argv[i],"--save"))save=argv[++i];else if(i+1<argc&&!strcmp(argv[i],"--snapshot"))snapshot=argv[++i];
  else {fprintf(stderr,"luma [--assets FILE] [--save FILE] [--new] [--no-save] [--headless] [--frames N] [--720p] [--snapshot PPM] [--demo] [--world N]\n");return 2;}
 }
 if(headless&&!host){fprintf(stderr,"headless is a PC preview option\n");return 2;}if(headless&&!limit)limit=1;
 LumaVideo video;struct termios saved={0},raw;
 printf("LUMA_BOOT assets=%s host=%d\n",assets,host);fflush(stdout);
 if(luma_video_open(&video,host,wide,assets)){luma_video_close(&video);return 1;}
 LumaGame game;luma_init(&game,&luma_world);if(start_world)luma_enter(&game,start_world,0,0);
 if(!nosave&&!newgame&&luma_load(&game,save)&&errno!=ENOENT){fprintf(stderr,"LUMA save rejected (%s); original preserved\n",strerror(errno));luma_video_close(&video);return 1;}
 if(luma_video_prepare(&video,game.world_index)){luma_video_close(&video);return 1;}
 signal(SIGTERM,stop);signal(SIGINT,stop);signal(SIGHUP,stop);
#ifdef LUMA_HOST
 SDL_Window *window=NULL;SDL_Renderer *renderer=NULL;SDL_Texture *texture=NULL;
 if(!headless){if(SDL_Init(SDL_INIT_VIDEO|SDL_INIT_EVENTS|SDL_INIT_GAMECONTROLLER)){fprintf(stderr,"SDL: %s\n",SDL_GetError());goto done;}window=SDL_CreateWindow("LUMA - Les Mondes Relies | aventure jouable",SDL_WINDOWPOS_CENTERED,SDL_WINDOWPOS_CENTERED,video.width*2,video.height*2,SDL_WINDOW_RESIZABLE);if(!window)goto done;renderer=SDL_CreateRenderer(window,-1,SDL_RENDERER_ACCELERATED|SDL_RENDERER_PRESENTVSYNC);if(!renderer)renderer=SDL_CreateRenderer(window,-1,SDL_RENDERER_SOFTWARE);if(!renderer)goto done;texture=SDL_CreateTexture(renderer,SDL_PIXELFORMAT_RGB565,SDL_TEXTUREACCESS_STREAMING,video.width*2,video.height*2);if(!texture)goto done;SDL_RenderSetLogicalSize(renderer,video.width*2,video.height*2);}
#else
 NeoPad pads[2]={{.fd=-1},{.fd=-1}};if(!demo){neo_pads_open(pads);if(tcgetattr(STDIN_FILENO,&saved)==0){raw=saved;raw.c_lflag&=~(ICANON|ECHO);raw.c_cc[VMIN]=0;raw.c_cc[VTIME]=0;if(tcsetattr(STDIN_FILENO,TCSANOW,&raw)==0)changed=1;}}
#endif
 printf("LUMA_START worlds=%u mode=%s board=%ux%u resources=GPU_RGB565_sprites_layers\n",luma_world_count,demo?"benchmark":"play",video.width*2,video.height*2);fflush(stdout);
 double start=now(),last=start,accumulator=0,last_save=start;double held_until[5]={0};int escape=0;unsigned updates=0,pending_pressed=0;
 unsigned frame_histogram[4096]={0},frame_samples=0,slow_frames=0;double max_frame=0;double simulation_seconds=0;luma_video_measure_begin(&video);
 while(!stopping&&!video.failed&&(!limit||video.frames<limit+warmup)){
  double stamp=now(),delta=headless?1.0/60:stamp-last;last=stamp;if(delta>.25)delta=.25;accumulator+=delta;LumaInput in={0};
#ifdef LUMA_HOST
  if(!headless){SDL_Event event;while(SDL_PollEvent(&event)){if(event.type==SDL_QUIT)stopping=1;if(event.type==SDL_KEYDOWN&&!event.key.repeat){switch(event.key.keysym.sym){case SDLK_q:case SDLK_ESCAPE:stopping=1;break;case SDLK_h:in.pressed|=B_HELP;break;case SDLK_r:in.pressed|=B_RESET;break;case SDLK_1:in.pressed|=B_CHOICE1;break;case SDLK_2:in.pressed|=B_CHOICE2;break;case SDLK_3:in.pressed|=B_CHOICE3;break;case SDLK_e:in.pressed|=B_INTERACT;break;case SDLK_SPACE:in.pressed|=B_ATTACK;break;case SDLK_v:case SDLK_TAB:in.pressed|=B_VEHICLE;break;case SDLK_m:in.pressed|=B_MAP;break;case SDLK_j:in.pressed|=B_JOURNAL;break;case SDLK_p:in.pressed|=B_PAUSE;break;default:break;}}}
   const Uint8 *keys=SDL_GetKeyboardState(NULL);in.dx=(keys[SDL_SCANCODE_D]||keys[SDL_SCANCODE_RIGHT])-(keys[SDL_SCANCODE_A]||keys[SDL_SCANCODE_LEFT]);in.dy=(keys[SDL_SCANCODE_S]||keys[SDL_SCANCODE_DOWN])-(keys[SDL_SCANCODE_W]||keys[SDL_SCANCODE_UP]);if(keys[SDL_SCANCODE_F]||keys[SDL_SCANCODE_X])in.held|=B_SHOOT;
  }
#else
  if(!demo){for(unsigned i=0;i<2;i++){neo_pad_read(&pads[i]);in.dx+=pads[i].x;in.dy+=pads[i].y;if(pads[i].pressed&PAD_NOVA)in.pressed|=B_ATTACK;if(pads[i].pressed&PAD_START)in.pressed|=B_PAUSE;if(pads[i].pressed&PAD_VIEW)in.pressed|=B_INTERACT;}
   struct pollfd p={STDIN_FILENO,POLLIN,0};if(poll(&p,1,0)>0&&(p.revents&POLLIN)){unsigned char bytes[64];ssize_t n=read(STDIN_FILENO,bytes,sizeof(bytes));for(ssize_t i=0;i<n;i++){unsigned c=bytes[i];if(escape==1){escape=c=='['?2:0;continue;}if(escape==2){if(c=='A')held_until[0]=stamp+.18;if(c=='B')held_until[1]=stamp+.18;if(c=='C')held_until[3]=stamp+.18;if(c=='D')held_until[2]=stamp+.18;escape=0;continue;}if(c==27){escape=1;continue;}if(c>='A'&&c<='Z')c+='a'-'A';switch(c){case 'w':held_until[0]=stamp+.18;break;case 's':held_until[1]=stamp+.18;break;case 'a':held_until[2]=stamp+.18;break;case 'd':held_until[3]=stamp+.18;break;case 'f':case 'x':held_until[4]=stamp+.25;break;case 'h':in.pressed|=B_HELP;break;case 'r':in.pressed|=B_RESET;break;case '1':in.pressed|=B_CHOICE1;break;case '2':in.pressed|=B_CHOICE2;break;case '3':in.pressed|=B_CHOICE3;break;case 'e':in.pressed|=B_INTERACT;break;case ' ':in.pressed|=B_ATTACK;break;case 'v':case '\t':in.pressed|=B_VEHICLE;break;case 'm':in.pressed|=B_MAP;break;case 'j':in.pressed|=B_JOURNAL;break;case 'p':in.pressed|=B_PAUSE;break;case 'q':stopping=1;break;default:break;}}}
   in.dx+=(held_until[3]>stamp)-(held_until[2]>stamp);in.dy+=(held_until[1]>stamp)-(held_until[0]>stamp);if(held_until[4]>stamp)in.held|=B_SHOOT;
  }
#endif
  if(demo){in.dx=sinf(game.time*.3f);in.dy=cosf(game.time*.3f);in.held=B_SHOOT;if(game.tick%90==0)in.pressed|=B_ATTACK;}
  double sim_start=now();pending_pressed|=in.pressed;in.pressed=pending_pressed;unsigned steps=0;while(accumulator>=1.0/LUMA_HZ&&steps<15){luma_step(&game,in);pending_pressed=0;in.pressed=0;accumulator-=1.0/LUMA_HZ;updates++;steps++;}
  simulation_seconds+=now()-sim_start;luma_render(&video,&game);
  if(warmup&&video.frames==warmup){printf("LUMA_WARMUP frames=%u seconds=%.3f\n",warmup,now()-start);luma_video_measure_begin(&video);start=now();updates=0;simulation_seconds=0;}
  if(!host&&video.frames>warmup&&(video.frames-warmup)%120==0){printf("LUMA_MEASURE frames=%u seconds=%.3f fps=%.2f\n",video.frames-warmup,now()-start,(video.frames-warmup)/fmax(now()-start,.001));fflush(stdout);}
#ifdef LUMA_HOST
  if(!headless){SDL_UpdateTexture(texture,NULL,video.pixels,video.width*4);SDL_RenderClear(renderer);SDL_RenderCopy(renderer,texture,NULL,NULL);SDL_RenderPresent(renderer);struct timespec delay={0,1000000};nanosleep(&delay,NULL);}
#endif
  if(!nosave&&((game.dirty&&stamp-last_save>2)||stamp-last_save>15)){if(luma_save(&game,save)){perror("LUMA autosave");luma_notice(&game,"Sauvegarde impossible. Votre carnet précédent est conservé.");}else game.dirty=0;last_save=stamp;}
  if(video.frames>warmup){double duration=now()-stamp;unsigned bucket=(unsigned)(duration*10000);if(bucket>4095)bucket=4095;frame_histogram[bucket]++;frame_samples++;if(duration>max_frame)max_frame=duration;if(duration>1.0/30)slow_frames++;}
 }
 if(snapshot&&luma_snapshot(&video,snapshot)){perror("LUMA snapshot");video.failed=1;}
 if(!nosave&&luma_save(&game,save)){perror("LUMA save");video.failed=1;}
 double elapsed=now()-start;unsigned measured_frames=video.frames>warmup?video.frames-warmup:0;printf("LUMA_RATE frames=%u seconds=%.3f fps=%.2f updates=%u commands=%u max_sprites=%u\n",measured_frames,elapsed,measured_frames/fmax(elapsed,.001),updates,video.commands,video.max_sprites);
 printf("LUMA_TIMING simulation=%.6f background_phase=%.6f scene_phase=%.6f hud_phase=%.6f submit_tail=%.6f present=%.6f\n",simulation_seconds,video.background_seconds,video.scene_seconds,video.hud_seconds,video.submit_seconds,video.present_seconds);
 unsigned p95=0,p99=0,cumulative=0;for(unsigned i=0;i<4096;i++){cumulative+=frame_histogram[i];if(!p95&&cumulative*100>=frame_samples*95)p95=i+1;if(!p99&&cumulative*100>=frame_samples*99)p99=i+1;}
 printf("LUMA_FRAME_TIME samples=%u p95_ms_upper=%.1f p99_ms_upper=%.1f max_ms=%.3f over_33_333_ms=%u\n",frame_samples,p95*.1,p99*.1,max_frame*1000,slow_frames);
 printf("LUMA_FLUSH all_calls=%u all_seconds=%.6f\n",video.flush_count,video.flush_seconds);
 printf("LUMA_DRIVER feed_us=%u wait_us=%u cache_us=%u present_us=%u text_us=%u\n",video.last.feed_us-video.measured.feed_us,video.last.wait_us-video.measured.wait_us,video.last.cache_us-video.measured.cache_us,video.last.present_us-video.measured.present_us,video.last.text_us-video.measured.text_us);
 printf("LUMA_RESULT world=%u flags=%u health=%u kills=%u crystals=%u shots=%u completed=%d status=%d\n",game.world_index,game.flags,game.health,game.kills,game.crystals,game.shots_fired,game.won,video.failed);rc=video.failed?1:0;
#ifdef LUMA_HOST
done:
 if(texture)SDL_DestroyTexture(texture);if(renderer)SDL_DestroyRenderer(renderer);if(window)SDL_DestroyWindow(window);SDL_Quit();
 (void)held_until;(void)escape;(void)saved;(void)raw;(void)changed;
#else
 for(unsigned i=0;i<2;i++)if(pads[i].fd>=0)close(pads[i].fd);if(changed)tcsetattr(STDIN_FILENO,TCSANOW,&saved);
#endif
 luma_video_close(&video);return rc;
}
