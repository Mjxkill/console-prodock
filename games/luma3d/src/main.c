#define _POSIX_C_SOURCE 200809L
#include "luma3d_render.h"
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stop;
static void signal_stop(int n) {(void)n;stop=1;}
static double seconds(void) {struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static int number(const char *s,unsigned *out) {char *end;errno=0;unsigned long x=strtoul(s,&end,10);if(errno||!*s||*end||x>1000000)return 0;*out=(unsigned)x;return 1;}
int main(int argc,char **argv) {
    int host=0,wide=0,automatic=1,benchmark=0,warmup_set=0;
    unsigned frames=0,advance=0,warmup=3;const char *capture=NULL;
    for(int i=1;i<argc;i++) {
        if(!strcmp(argv[i],"--host"))host=1;
        else if(!strcmp(argv[i],"--720p"))wide=1;
        else if(!strcmp(argv[i],"--manual"))automatic=0;
        else if(!strcmp(argv[i],"--benchmark"))benchmark=1;
        else if(!strcmp(argv[i],"--warmup")&&i+1<argc) {warmup_set=1;if(!number(argv[++i],&warmup)||warmup<2)return 2;}
        else if(!strcmp(argv[i],"--frames")&&i+1<argc) {if(!number(argv[++i],&frames))return 2;}
        else if(!strcmp(argv[i],"--advance")&&i+1<argc) {if(!number(argv[++i],&advance))return 2;}
        else if(!strcmp(argv[i],"--capture")&&i+1<argc)capture=argv[++i];
        else {fprintf(stderr,"Usage: %s [--host] [--720p] [--manual] [--frames N] [--advance simulation_steps] [--capture prefix] [--benchmark --warmup N]\n",argv[0]);return 2;}
    }
    if((benchmark&&!frames)||(warmup_set&&!benchmark)||(benchmark&&capture)) {fputs("Benchmark requires --frames N; --warmup requires benchmark, without capture\n",stderr);return 2;}
    if(host&&!frames)frames=1;
    if(capture&&(!host||frames!=1)) {fputs("Capture requires --host --frames 1\n",stderr);return 2;}
    L3World world;L3Game game;L3Render renderer;l3_world_init(&world);
    if(!l3_game_init(&game,&world,automatic)) {fputs("Invalid world\n",stderr);return 1;}
    for(unsigned i=0;i<advance;i++)l3_game_step(&game,NULL,1.0f/60);
    if(!l3_render_open(&renderer,host,wide)) {fputs("GPU initialization failed; G3D1 Linux candidate required\n",stderr);l3_render_close(&renderer);return 1;}
    char path[1024];
    if(capture) {
        if(snprintf(path,sizeof(path),"%s.commands",capture)>=(int)sizeof(path)) {l3_render_close(&renderer);return 1;}
        renderer.capture=fopen(path,"wb");if(!renderer.capture) {perror(path);l3_render_close(&renderer);return 1;}
    }
    signal(SIGINT,signal_stop);signal(SIGTERM,signal_stop);
    struct termios saved,raw;int terminal=!host&&!benchmark&&isatty(STDIN_FILENO)&&!tcgetattr(STDIN_FILENO,&saved);
    int stdin_flags=-1;
    if(terminal) {raw=saved;raw.c_lflag&=~(ICANON|ECHO);raw.c_cc[VMIN]=raw.c_cc[VTIME]=0;
        if(tcsetattr(STDIN_FILENO,TCSANOW,&raw))terminal=0;
        else {stdin_flags=fcntl(STDIN_FILENO,F_GETFL);if(stdin_flags>=0)fcntl(STDIN_FILENO,F_SETFL,stdin_flags|O_NONBLOCK);}}
    puts("LUMA3D — Le Val des Courriers. WASD move, IJKL camera, space jump, E interact, T auto, Q quit.");fflush(stdout);
    double start=seconds(),previous=start,accumulator=0,held_until=0,look_until=0,report=start;
    unsigned report_frames=0,report_commands=0;L3Input input={0};int ok=1;
    struct prodock_geometry_info previous_gpu=renderer.initial_geometry;
    struct prodock_display_info previous_display=renderer.initial;
    struct prodock_geometry_info benchmark_gpu=renderer.initial_geometry;
    struct prodock_display_info benchmark_display=renderer.initial;
    uint64_t geometry_cycles_total=0;
    unsigned measured_frame=0,measured_commands=0,measured_batches=0;
    double measured_feed=0,measured_present=0;
    if(benchmark) {printf("LUMA3D_BENCHMARK pose=%u warmup=%u measured_frames=%u fixed_pose=1 hardware=%d\n",advance,warmup,frames,!host);fflush(stdout);}
    while(!stop&&(!frames||renderer.frame<frames+(benchmark?warmup:0))) {
        if(benchmark&&renderer.frame==warmup) {
            /* Both pages and the sky cache have been exercised. Start the
             * measurement after counter reads; keep this exact pose frozen. */
            if(!host&&(ioctl(renderer.fd,PRODOCK_GEOMETRY_INFO,&previous_gpu)||ioctl(renderer.display,PRODOCK_DISPLAY_INFO,&previous_display))) {perror("LUMA3D benchmark counters");ok=0;break;}
            benchmark_gpu=previous_gpu;benchmark_display=previous_display;
            measured_frame=report_frames=renderer.frame;
            measured_commands=report_commands=renderer.total_commands;
            measured_batches=renderer.total_flushes;
            measured_feed=renderer.feed_seconds;measured_present=renderer.present_seconds;
            geometry_cycles_total=0;
            start=previous=report=seconds();
        }
        double now=seconds(),dt=now-previous;previous=now;
        if(terminal) {
            unsigned char bytes[64];ssize_t n=read(STDIN_FILENO,bytes,sizeof(bytes));
            for(ssize_t j=0;j<n;j++) {
                int c=bytes[j];if(c=='q'||c=='Q')stop=1;
                else if(c=='t'||c=='T')input.pressed|=L3_TOGGLE_AUTO;
                else if(c==' ')input.pressed|=L3_JUMP;
                else if(c=='e'||c=='E')input.pressed|=L3_INTERACT;
                else if(c=='i'||c=='j'||c=='k'||c=='l') {
                    input.look_x=c=='j'?-1:c=='l'?1:0;
                    input.look_y=c=='i'?-1:c=='k'?1:0;look_until=now+.16;
                }
                else if(c=='w'||c=='W'||c=='s'||c=='S'||c=='a'||c=='A'||c=='d'||c=='D') {
                    input.move_x=(c=='a'||c=='A')?-1:(c=='d'||c=='D')?1:0;
                    input.move_z=(c=='w'||c=='W')?1:(c=='s'||c=='S')?-1:0;held_until=now+.16;
                    input.held=c>='A'&&c<='Z'?L3_SPRINT:0;
                }
            }
            if(now>held_until) {input.move_x=input.move_z=0;input.held=0;}
            if(now>look_until)input.look_x=input.look_y=0;
        }
        if(benchmark) { /* Deliberately no game/camera/animation advancement. */ }
        else if(host) {if(renderer.frame)l3_game_step(&game,&input,1.0f/60);}
        else {
            if(dt>.25)dt=.25;accumulator+=dt;
            while(accumulator>=1.0/60) {l3_game_step(&game,&input,1.0f/60);input.pressed=0;accumulator-=1.0/60;}
        }
        if(!l3_render_frame(&renderer,&game)) {ok=0;break;}
        double finished=seconds();
        if(!host&&(!benchmark||measured_frame)&&finished-report>=5) {
            printf("LUMA3D_PERF fps=%.2f cmd_s=%.0f draws=%u triangles_in=%u objects=%u collected=%u/4 auto=%d sim=%.2f\n",(renderer.frame-report_frames)/(finished-report),(renderer.total_commands-report_commands)/(finished-report),renderer.draws,renderer.triangles,renderer.instances,game.collected_count,game.autopilot,game.time);fflush(stdout);
            report_frames=renderer.frame;report_commands=renderer.total_commands;report=finished;
            struct prodock_geometry_info gpu;struct prodock_display_info display;
            if(ioctl(renderer.fd,PRODOCK_GEOMETRY_INFO,&gpu)||ioctl(renderer.display,PRODOCK_DISPLAY_INFO,&display)) {perror("LUMA3D counters");ok=0;break;}
            uint32_t cycles=gpu.cycles-previous_gpu.cycles;geometry_cycles_total+=cycles;
            printf("LUMA3D_WINDOW cycles=%u cycles_accumulated=%llu vertices=%u raster_triangles=%u culled=%u intersections=%u slivers=%u feed_us=%u wait_us=%u cache_us=%u present_us=%u\n",cycles,(unsigned long long)geometry_cycles_total,gpu.vertices-previous_gpu.vertices,gpu.triangles-previous_gpu.triangles,gpu.culled-previous_gpu.culled,gpu.intersections-previous_gpu.intersections,gpu.slivers-previous_gpu.slivers,display.feed_us-previous_display.feed_us,display.wait_us-previous_display.wait_us,display.cache_us-previous_display.cache_us,display.present_us-previous_display.present_us);fflush(stdout);
            previous_gpu=gpu;previous_display=display;
        }
    }
    double elapsed=seconds()-start;
    if(benchmark&&!host&&measured_frame) {
        struct prodock_geometry_info gpu;struct prodock_display_info display;
        if(ioctl(renderer.fd,PRODOCK_GEOMETRY_INFO,&gpu)||ioctl(renderer.display,PRODOCK_DISPLAY_INFO,&display)) {perror("LUMA3D final benchmark counters");ok=0;}
        else {
            geometry_cycles_total+=(uint32_t)(gpu.cycles-previous_gpu.cycles);
            printf("LUMA3D_BENCHMARK_COUNTERS cycles=%llu vertices=%u raster_triangles=%u culled=%u intersections=%u slivers=%u feed_us=%u wait_us=%u cache_us=%u present_us=%u\n",(unsigned long long)geometry_cycles_total,gpu.vertices-benchmark_gpu.vertices,gpu.triangles-benchmark_gpu.triangles,gpu.culled-benchmark_gpu.culled,gpu.intersections-benchmark_gpu.intersections,gpu.slivers-benchmark_gpu.slivers,display.feed_us-benchmark_display.feed_us,display.wait_us-benchmark_display.wait_us,display.cache_us-benchmark_display.cache_us,display.present_us-benchmark_display.present_us);
        }
    }
    if(capture) {if(fclose(renderer.capture))ok=0;renderer.capture=NULL;if(!l3_render_dump(&renderer,capture))ok=0;}
    unsigned completed=renderer.frame-measured_frame;
    if(benchmark&&(!measured_frame||completed!=frames))ok=0;
    printf("LUMA3D_RESULT frames=%u elapsed=%.3f fps=%.2f commands=%u batches=%u feed_seconds=%.3f present_seconds=%.3f draws_last=%u triangles_last=%u benchmark=%d hardware=%d warmup=%u\n",completed,elapsed,elapsed>0?completed/elapsed:0,renderer.total_commands-measured_commands,renderer.total_flushes-measured_batches,renderer.feed_seconds-measured_feed,renderer.present_seconds-measured_present,renderer.draws,renderer.triangles,benchmark,!host,benchmark?warmup:0);fflush(stdout);
    if(terminal) {tcsetattr(STDIN_FILENO,TCSANOW,&saved);if(stdin_flags>=0)fcntl(STDIN_FILENO,F_SETFL,stdin_flags);}
    if(!l3_render_close(&renderer))ok=0;return !ok;
}
