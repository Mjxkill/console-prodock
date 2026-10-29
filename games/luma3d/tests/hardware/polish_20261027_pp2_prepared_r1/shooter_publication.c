/* Local proof of publication coverage, using the unchanged R6 implementation. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "luma3d_render.h"
#include "shooter_render.c"
int main(int argc,char **argv){
 assert(argc==3);unsigned wide=atoi(argv[1]);L3Render r={0};r.host=1;r.width=wide?640:400;r.height=wide?360:240;r.memory=malloc(L3_MAP_BYTES);assert(r.memory);memset(r.memory,0xa5,L3_MAP_BYTES);
 assert(l3_shooter_art_open(&r));unsigned w=r.width*2-272,h=r.height*2-96,field=align32(w)*h*4,atlas=sizeof(sh_pixels);
 FILE *f=fopen(argv[2],"rb");assert(f);assert(!fseek(f,FIELD_BASE,SEEK_SET));uint8_t *reference=malloc(4u<<20);assert(reference);assert(fread(reference,1,4u<<20,f)==4u<<20);assert(!fclose(f));
 unsigned holes=0,full_diff=0,defined=0;
 for(unsigned i=0;i<L3_MAP_BYTES;i++){
  int used=(i>=FIELD_BASE&&i<FIELD_BASE+field)||(i>=ART_BASE&&i<ART_BASE+atlas);
  if(used){assert(r.memory[i]==reference[i-FIELD_BASE]);defined++;}
  else{assert(r.memory[i]==0xa5);if(i>=FIELD_BASE){assert(reference[i-FIELD_BASE]==0);holes++;}}
  if(i>=FIELD_BASE&&r.memory[i]!=reference[i-FIELD_BASE])full_diff++;
 }
 assert(defined==r.shooter_upload_bytes&&full_diff==holes);
 /* Every possible field scroll, both layers, aligned source fetch rows. */
 unsigned rows=0;for(unsigned layer=0;layer<2;layer++)for(unsigned scroll=0;scroll<h;scroll++)for(unsigned y=0;y<h;y++){
  unsigned start=FIELD_BASE+layer*field/2+(scroll+y)*align32(w);assert(start>=FIELD_BASE&&start+align32(w)<=FIELD_BASE+field);rows++;
 }
 /* Every atlas entry, including sprite tile padding, stays in its publication. */
 for(unsigned i=0;i<sizeof(sh_art)/sizeof(sh_art[0]);i++){
  const L3ShooterArt *a=sh_art+i;unsigned bytes=a->layer?a->pitch*a->h:tiles(a)*1024;
  assert(a->offset<=atlas&&bytes<=atlas-a->offset);
 }
 printf("SHOOTER_PUBLICATION_PASS wide=%u field_offset=%u field_bytes=%u atlas_offset=%u atlas_bytes=%u published=%u unused=%u poison_mismatch=%u rows=%u\n",wide,FIELD_BASE,field,ART_BASE,atlas,defined,holes,full_diff,rows);
 free(reference);free(r.memory);return 0;
}
