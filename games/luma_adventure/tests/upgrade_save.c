/* Cross-content-version save fixture; not a gameplay-duration measurement. */
#include "luma.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc,char **argv){
 assert(argc>=3);LumaGame g;luma_init(&g,&luma_world);
 if(!strcmp(argv[1],"reject")){LumaGame before=g;assert(luma_load(&g,argv[2])!=0);assert(!memcmp(&g,&before,sizeof(g)));puts("LUMA_DOWNGRADE_REJECT_PASS state_and_file_preserved");return 0;}
 if(!strcmp(argv[1],"write")){
  unsigned world=argc>3?(unsigned)atoi(argv[3]):1;assert(!luma_enter(&g,world,0,0));g.health=3;g.crystals=173;g.unlocked=255;g.flags=511;g.missions=(1U<<g.world->mission_count)-1;g.progress[0].flags=7;printf("w:%u\n",world);
  for(unsigned i=0;i<g.world->mission_count;i++)printf("m:%s\n",g.world->missions[i].id);
  for(unsigned i=0;i<g.world->entity_count;i++)if(g.world->entities[i].kind==E_CHEST){g.collected|=UINT64_C(1)<<i;printf("c:%s\n",g.world->entities[i].id);}
  assert(!luma_save(&g,argv[2]));return 0;
 }
 unsigned world=1;for(int a=3;a<argc;a++)if(!strncmp(argv[a],"w:",2))world=(unsigned)atoi(argv[a]+2);
 assert(!luma_load(&g,argv[2]));assert(g.world_index==world&&g.health==3&&g.crystals==173&&g.unlocked==255&&g.flags==511&&g.progress[0].flags==7);
 unsigned preserved=0,added=0;
 for(unsigned i=0;i<g.world->mission_count;i++){
  int old=0;for(int a=3;a<argc;a++)if(!strncmp(argv[a],"m:",2)&&!strcmp(argv[a]+2,g.world->missions[i].id))old=1;
  assert(!!(g.missions&(1U<<i))==old);if(old)preserved++;else added++;
 }
 for(int a=3;a<argc;a++)if(!strncmp(argv[a],"c:",2)){
  int found=0;for(unsigned i=0;i<g.world->entity_count;i++)if(!strcmp(argv[a]+2,g.world->entities[i].id)){assert(g.collected&(UINT64_C(1)<<i));found=1;}assert(found);
 }
 for(unsigned i=16;i<luma_world_count;i++)assert(!g.progress[i].flags&&!g.progress[i].missions&&!g.progress[i].collected);
 if(!strcmp(argv[1],"migrate"))assert(argc>3&&!luma_save(&g,argv[3]));
 printf("LUMA_SAVE_UPGRADE_PASS worlds=%u missions_preserved=%u new_missions_unset=%u health_inventory_loot_preserved=1\n",luma_world_count,preserved,added);return 0;
}
