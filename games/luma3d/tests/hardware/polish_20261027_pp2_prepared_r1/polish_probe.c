#define _POSIX_C_SOURCE 200809L
/* Diagnostic only: replay legal showcase inputs without presenting the replay,
 * then render one exact, frozen state. Never a playable/demo executable. */
#include "luma3d_render.h"
#include "luma3d_showcase.h"
#include <errno.h>
#include <stdlib.h>
#include <string.h>

int main(int argc,char **argv) {
    int host=0,wide=0;unsigned advance=0;const char *capture=NULL;
    for(int i=1;i<argc;i++) {
        if(!strcmp(argv[i],"--host"))host=1;
        else if(!strcmp(argv[i],"--720p"))wide=1;
        else if(!strcmp(argv[i],"--capture")&&i+1<argc)capture=argv[++i];
        else if(!strcmp(argv[i],"--advance")&&i+1<argc) {
            char *end;errno=0;unsigned long n=strtoul(argv[++i],&end,10);
            if(errno||!*argv[i]||*end||n>1000000)return 2;advance=(unsigned)n;
        } else return 2;
    }
    if(capture&&!host)return 2;
    L3World world;L3Game game;L3Showcase tour={0};L3Render renderer;
    l3_world_init(&world);if(!l3_game_init(&game,&world,1))return 1;
    l3_showcase_init(&tour,&game,1);
    for(unsigned i=0;i<advance;i++) {
        l3_showcase_step(&tour,&game,1.0f/60);
        if(!(i%10))l3_showcase_presented(&tour);
    }
    printf("LUMA3D_POLISH_PROBE advance=%u replay_without_render=1 active=%u hardware=%d saves=disabled\n",advance,game.activities.arcade.active,!host);
    fflush(stdout);
    if(!l3_render_open(&renderer,host,wide)){l3_render_close(&renderer);return 1;}
    char path[1024];int ok=1;
    if(capture) {
        if(snprintf(path,sizeof(path),"%s.commands",capture)>=(int)sizeof(path)){l3_render_close(&renderer);return 2;}
        renderer.capture=fopen(path,"wb");if(!renderer.capture){l3_render_close(&renderer);return 1;}
    }
    if(!l3_render_frame(&renderer,&game))ok=0;
    if(capture) {
        if(fclose(renderer.capture))ok=0;renderer.capture=NULL;
        if(!l3_render_dump(&renderer,capture))ok=0;
    }
    printf("LUMA3D_POLISH_PROBE_RESULT frames=%u active=%u stage=%u commands=%u sprites=%u ok=%d hardware=%d\n",renderer.frame,game.activities.arcade.active,tour.stage,renderer.total_commands,renderer.sprite_count,ok,!host);
    l3_render_close(&renderer);return !ok;
}
