#!/usr/bin/env python3
"""Exercise game rules and real command/scene validators under sanitizers."""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[2]
SOURCE=r'''
#define NEBULA_HOST
#define main nebula_program_main
#include "nebula.c"
#undef main
#include <assert.h>
#include "prodock-validate.h"
int main(int argc,char **argv)
{
    assert(argc==2 || argc==3);
    unsigned width=argc==3?1280:800,height=argc==3?720:480;
    NeoPad pad={.fd=-1},other={.fd=-1};
    struct input_event ev={.type=EV_ABS,.code=ABS_X,.value=-1};
    neo_pad_event(&pad,&ev);assert(pad.x==0); /* atomic at SYN_REPORT */
    ev=(struct input_event){.type=EV_KEY,.code=BTN_SOUTH,.value=1};neo_pad_event(&pad,&ev);
    ev=(struct input_event){.type=EV_SYN,.code=SYN_REPORT};neo_pad_event(&pad,&ev);
    assert(pad.x==-1 && pad.pressed==PAD_NOVA && !other.x && !other.keys);
    pad.pressed=0;neo_pad_event(&pad,&ev);assert(!pad.pressed); /* held != press */
    ev=(struct input_event){.type=EV_KEY,.code=BTN_SOUTH,.value=0};neo_pad_event(&pad,&ev);
    ev=(struct input_event){.type=EV_SYN,.code=SYN_REPORT};neo_pad_event(&pad,&ev);
    assert(!pad.keys && !pad.pressed);
    ev=(struct input_event){.type=EV_KEY,.code=BTN_START,.value=1};neo_pad_event(&other,&ev);
    ev=(struct input_event){.type=EV_SYN,.code=SYN_REPORT};neo_pad_event(&other,&ev);
    assert(other.pressed==PAD_START && !pad.pressed);
    ev=(struct input_event){.type=EV_SYN,.code=SYN_DROPPED};neo_pad_event(&other,&ev);
    ev=(struct input_event){.type=EV_KEY,.code=BTN_SELECT,.value=1};neo_pad_event(&other,&ev);
    ev=(struct input_event){.type=EV_SYN,.code=SYN_REPORT};neo_pad_event(&other,&ev);
    assert(!other.keys && !other.pressed && !other.x && !other.y);
    Game g;
    reset_game(&g,0,0,0);
    key(&g,27);key(&g,'[');key(&g,'D');assert(g.tx==176 && !g.escape);
    key(&g,'d');assert(g.tx==200);
    key(&g,'p');update(&g,1);assert(g.time==0);key(&g,'p');
    g.invincible=0;damage(&g);assert(g.health==4 && g.damage_taken==1);
    damage(&g);assert(g.health==4); /* one hit cannot drain all health */
    for(unsigned i=0;i<4;++i){g.invincible=0;damage(&g);}
    assert(g.finished && !g.won);key(&g,'r');assert(!g.finished && g.health==5);
    g.hostile[0]=(Shot){.live=1};g.enemies[0]=(Enemy){.live=1,.x=100,.y=80,.hp=2};
    nova(&g);assert(!g.hostile[0].live && !g.enemies[0].live && g.bombs==2 && g.kills==1);
    nova(&g);assert(g.bombs==2); /* held space cannot spend all charges at once */
    reset_game(&g,0,2,1);g.time=5;g.boss_hp=0;update(&g,.02f);assert(g.phase==2);
    for(unsigned i=0;i<210;++i)update(&g,.02f);
    assert(g.finished && g.won && g.sector==3);
    reset_game(&g,0,0,0);g.time=5;g.fire=1;g.spawn=1;
    g.enemies[0]=(Enemy){.live=1,.x=100,.y=100,.hp=1,.fire=1};
    g.shots[0]=(Shot){.live=1,.x=100,.y=100};update(&g,.001f);
    assert(g.kills==1 && !g.enemies[0].live && !g.shots[0].live);
    Video v={.fd=-1,.display=-1,.host=1,.scale=1,.used=3*1024*1024};
    assert(!geometry(&v,width,height));
    v.mem=calloc(1,MAP_BYTES);assert(v.mem);assert(!assets(&v,argv[1]));
    unsigned checks=0,command_count=0,wins=0,losses=0,last_finished=0,highest_sector=0;
    reset_game(&g,1,0,0);
    for(unsigned tick=0;tick<18000;++tick) {
        update(&g,1.f/55);
        assert(isfinite(g.x) && isfinite(g.y) && g.x>=16 && g.x<=384 && g.y>=35 && g.y<=218);
        assert(g.health>=0 && g.health<=5 && g.bombs>=0 && g.bombs<=3);
        if((unsigned)g.sector>highest_sector)highest_sector=(unsigned)g.sector;
        if(g.finished && !last_finished){if(g.won)++wins;else ++losses;}
        last_finished=g.finished;
        if(tick%5)continue;
        v.scale=(tick/5)&1?1:2;render(&v,&g);assert(!v.failed && v.sprites<=64);
        assert(!prodock_scene_valid_for(&v.scene,width,height));
        for(unsigned i=12;i<16;++i)assert(!v.scene.layers[i][6]);
        for(unsigned i=0;i<64;++i)assert(((v.scene.sprites[i][2]>>20)&15)<12);
        for(unsigned i=0;i<v.capture_count;++i){assert(!prodock_command(v.capture_commands[i]));++command_count;}
        ++checks;
    }
    fprintf(stderr,"campaign wins=%u losses=%u highest=%u sprites=%u layers=%u memory=%u dropped=%u\n",wins,losses,highest_sector,v.max_sprites,v.max_layers,v.used,v.fx_dropped);
    assert(v.used<MAP_BYTES && v.max_sprites>20 && v.max_layers>=8 && highest_sector==3);
    assert(wins>=1 && losses==0);
    assert(!v.fx_dropped);
    reset_game(&g,0,0,0);g.time=5;
    for(unsigned i=0;i<ENEMIES;++i)g.enemies[i]=(Enemy){.live=1,.x=200,.y=100};
    for(unsigned i=0;i<SHOTS;++i)g.shots[i]=(Shot){.live=1,.x=200,.y=100};
    for(unsigned i=0;i<HOSTILE;++i)g.hostile[i]=(Shot){.live=1,.x=200,.y=100};
    for(unsigned i=0;i<10;++i)effect(&g,200,100,2);
    unsigned pickups=0;for(unsigned i=0;i<EFFECTS;++i)pickups+=g.fx[i].live && g.fx[i].kind==2;
    assert(pickups==4);
    for(unsigned i=0;i<16;++i)effect(&g,200,100,1);
    render(&v,&g);assert(v.sprites==64 && v.fx_dropped==6 && !v.failed);
    for(unsigned i=50;i<54;++i)assert(v.scene.sprites[i][0]==v.assets+v.art[NA_PICKUP_1+(v.scale==2?NA_PICKUP_2-NA_PICKUP_1:0)].offset);
    key(&g,'q');assert(stopping);
    free(v.mem);
    printf("PASS NEBULA: input, inertia, pause, hit immunity, death/retry, nova, collisions, victory; %u scenes / %u commands; autoplay wins=%u losses=%u highest_sector=%u; memory=%u sprites=%u layers=%u\n",
           checks,command_count,wins,losses,highest_sector,v.used,v.max_sprites,v.max_layers);
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='nebula-test-') as tmp:
    work=Path(tmp);(work/'test.c').write_text(SOURCE)
    subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-fno-omit-frame-pointer',
                    '-I',str(ROOT/'linux/userspace'),'-I',str(ROOT/'linux/drivers'),
                    str(work/'test.c'),'-lm','-o',str(work/'test')],check=True)
    subprocess.run([str(work/'test'),str(ROOT/'assets/nebula/packed/nebula.bin')],check=True)

    subprocess.run([str(work/'test'),str(ROOT/'assets/nebula/packed/nebula.bin'),'720p'],check=True)
