// Essais sur PC du pilote SD et de FatFs contre le modèle de carte : montage, liste, lectures comparées
// octet par octet, écriture puis relecture, erreurs injectées. Usage : sd_test IMAGE DOSSIER_ATTENDU.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "sd.h"
#include "ff.h"
void model_load(uint8_t *,uint32_t); void model_present(int); void model_corrupt_reads(unsigned); void model_reject_writes(unsigned);
void model_corrupt_csd(int);
unsigned model_violations(void); unsigned model_speed(void); void disk_speed(unsigned); const sd_card *disk_card(void);
static int failures;
#define CHECK(condition) do { if (!(condition)) { printf("FAIL line %d: %s\n",__LINE__,#condition); ++failures; } } while (0)
static uint8_t *load(const char *path, long *size)
{ FILE *f=fopen(path,"rb"); if (!f) { perror(path); exit(2); } fseek(f,0,SEEK_END); *size=ftell(f); rewind(f); uint8_t *d=malloc(*size+1); if (fread(d,1,*size,f)!=(size_t)*size) exit(2); fclose(f); return d; }
static void compare(const char *name, const char *expected_dir)
{
    char path[512]; long size; snprintf(path,sizeof path,"%s/%s",expected_dir,name); uint8_t *expected=load(path,&size);
    FIL file; UINT got; uint8_t *data=malloc(size+1); long done=0;
    CHECK(f_open(&file,name,FA_READ)==FR_OK); CHECK((long)f_size(&file)==size);
    while (done<size) { UINT ask=size-done>70000 ? 70000 : (UINT)(size-done); CHECK(f_read(&file,data+done,ask,&got)==FR_OK); if (got!=ask) { CHECK(0); break; } done+=got; }
    CHECK(f_close(&file)==FR_OK); CHECK(!memcmp(data,expected,size)); printf("read %s %ld bytes\n",name,size); free(data); free(expected);
}
int main(int argc, char **argv)
{
    if (argc!=3) return 2;
    long size; uint8_t *image=load(argv[1],&size); FATFS fs; DIR dir; FILINFO info; FIL file; UINT count; sd_card card;
    // Références des CRC : valeurs de la spécification SD (CMD0, CMD17 bloc 0) et CRC16 de 512 octets 0xFF.
    uint8_t cmd0[5]={0x40,0,0,0,0}, cmd17[5]={0x51,0,0,0,0}, ones[512]; memset(ones,0xff,512);
    CHECK(sd_crc7(cmd0,5)==0x95); CHECK(sd_crc7(cmd17,5)==0x55); CHECK(sd_crc16(ones,512)==0x7fa1);
    // Carte absente, puis présente.
    model_load(image,(uint32_t)(size/512)); model_present(0); CHECK(sd_init(&card,20000000)==SD_NO_CARD);
    model_present(1); CHECK(sd_init(&card,20000000)==SD_OK);
    CHECK(card.high_capacity && card.version2 && card.sectors==(uint32_t)(size/512) && model_speed()==20000000);
    // Une capacité dont le CRC est faux ne doit pas produire une carte prête.
    model_corrupt_csd(1); CHECK(sd_init(&card,20000000)==SD_CRC && !card.ready);
    model_corrupt_csd(0); CHECK(sd_init(&card,20000000)==SD_OK);
    CHECK(sd_read(&card,card.sectors,ones,1)==SD_PARAMETER);
    CHECK(sd_write(&card,card.sectors-1,ones,2)==SD_PARAMETER);
    CHECK(sd_read(&card,0xffffffffU,ones,2)==SD_PARAMETER);
    // Système de fichiers : liste, lectures comparées aux originaux.
    disk_speed(20000000); CHECK(f_mount(&fs,"",1)==FR_OK);
    CHECK(f_opendir(&dir,"/")==FR_OK); unsigned files=0;
    while (f_readdir(&dir,&info)==FR_OK && info.fname[0]) { printf("dir %-12s %lu\n",info.fname,(unsigned long)info.fsize); ++files; }
    CHECK(files==4); f_closedir(&dir);
    compare("SMALL.TXT",argv[2]); compare("BLOCK.BIN",argv[2]); compare("BIG.BIN",argv[2]); compare("SUB/DEEP.BIN",argv[2]);
    // Bloc corrompu deux fois : relu, compté, sans changer de fréquence ; quatre fois : fréquence réduite.
    model_corrupt_reads(2); compare("BLOCK.BIN",argv[2]); CHECK(disk_card()->crc_errors==2 && disk_card()->downshifts==0);
    model_corrupt_reads(4); compare("BLOCK.BIN",argv[2]); CHECK(disk_card()->crc_errors==6 && disk_card()->downshifts==1 && model_speed()==10000000);
    // Écriture, refus injecté une fois, puis relecture.
    static uint8_t out[70001], back[70001]; for (unsigned i=0;i<sizeof out;++i) out[i]=(uint8_t)(i*131+i/251);
    model_reject_writes(1);
    CHECK(f_open(&file,"WRITE.BIN",FA_WRITE|FA_CREATE_ALWAYS)==FR_OK); CHECK(f_write(&file,out,sizeof out,&count)==FR_OK && count==sizeof out); CHECK(f_close(&file)==FR_OK);
    CHECK(f_open(&file,"WRITE.BIN",FA_READ)==FR_OK); CHECK(f_read(&file,back,sizeof back,&count)==FR_OK && count==sizeof back); CHECK(f_close(&file)==FR_OK);
    CHECK(!memcmp(out,back,sizeof out)); CHECK(disk_card()->retries>=7);
    // Carte retirée : l'initialisation suivante échoue proprement.
    model_present(0); CHECK(sd_init(&card,20000000)==SD_NO_CARD); model_present(1);
    CHECK(model_violations()==0);
    FILE *f=fopen(argv[1],"wb"); fwrite(image,1,size,f); fclose(f);      // l'image modifiée est relue par mtools
    printf(failures ? "SD HOST FAIL %d\n" : "SD HOST PASS crc_errors=%u retries=%u downshifts=%u\n",failures ? (unsigned)failures : disk_card()->crc_errors,disk_card()->retries,disk_card()->downshifts);
    return failures!=0;
}
