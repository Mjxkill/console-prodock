// Disque USB de la console : application téléchargée en ILM (le firmware incorporé reste gpu_diag).
// La console apparaît sur le PC comme un port série (journal, commandes) ET comme un disque
// amovible. Le disque est la carte SD si elle répond ; sinon un disque de 32 Mio en DDR, formaté
// FAT16 au démarrage avec un fichier LISEZMOI.TXT, perdu à l'extinction.
// Tant que cette application ne tourne pas, le matériel présente au PC un lecteur sans carte ;
// elle prend le disque au démarrage (le PC voit arriver un support) et peut le rendre.
// Commandes UART : ? identité, s état et compteurs, m recherche la carte SD et change de support,
// v CRC32 de la zone d'essai du disque en DDR (voir tools/check_usb_disk.py), q rend le disque
// au matériel, g le reprend ; d sélectionne le disque DDR sans toucher à la carte SD.
// Les commandes sont en minuscules et tout ce que l'application écrit est en majuscules, sans
// point d'interrogation : si le PC renvoie le texte reçu (terminal avec écho, sonde de modem à
// l'ouverture du port), l'application ne peut pas se commander elle-même.
#include <stdio.h>
#include <string.h>
#include "ae350.h"
#include "cache.h"
#include "sd.h"
#include "usb_msc.h"
#define RAM_DISK ((uint8_t *)0x08000000UL)       // DDR, au-delà des ressources des démonstrations
#define RAM_BLOCKS 65536U                        // 32 Mio
static sd_card card;
static int on_sd;
static unsigned long long cycles(void){unsigned hi,lo,again;do{__asm__ volatile("rdcycleh %0":"=r"(hi));__asm__ volatile("rdcycle %0":"=r"(lo));__asm__ volatile("rdcycleh %0":"=r"(again));}while(hi!=again);return ((unsigned long long)hi<<32)|lo;}
unsigned usb_msc_ms(void){return (unsigned)(cycles()/800000ULL);}
static void put(unsigned c){while(!(AE350_UART2->LSR&0x20U)){}AE350_UART2->THR=c;}
long except_handler(long cause,long epc){const char *s="\r\nUSBDISK TRAP ";while(*s)put(*s++);unsigned v[3]={(unsigned)cause,(unsigned)epc,read_csr(NDS_MTVAL)};for(unsigned i=0;i<3;++i){for(int b=28;b>=0;b-=4)put("0123456789ABCDEF"[(v[i]>>b)&15]);put(' ');}for(;;){}}
static uint32_t crc32(const uint8_t *p,unsigned n){static uint32_t table[256];if(!table[1])for(unsigned i=0;i<256;++i){uint32_t c=i;for(unsigned b=0;b<8;++b)c=(c>>1)^(0xedb88320U&(0U-(c&1)));table[i]=c;}uint32_t c=~0U;for(unsigned i=0;i<n;++i)c=table[(c^p[i])&255]^(c>>8);return ~c;}

static int ram_read(void *context,uint32_t block,uint8_t *data,uint32_t count){(void)context;memcpy(data,RAM_DISK+block*512U,count*512U);return 0;}
static int ram_write(void *context,uint32_t block,const uint8_t *data,uint32_t count){(void)context;memcpy(RAM_DISK+block*512U,data,count*512U);return 0;}
static int card_read(void *context,uint32_t block,uint8_t *data,uint32_t count){(void)context;return sd_read(&card,block,data,count)!=SD_OK;}
static int card_write(void *context,uint32_t block,const uint8_t *data,uint32_t count){(void)context;return sd_write(&card,block,data,count)!=SD_OK;}

static void put16(uint8_t *p,unsigned v){p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);}
static void put32(uint8_t *p,uint32_t v){put16(p,v&0xffffU);put16(p+2,v>>16);}
// Volume FAT16 sans table de partitions : 1 secteur réservé, 2 FAT de 64 secteurs, racine de
// 512 entrées, grappes de 4 secteurs (16 343 grappes), un fichier dans la grappe 2.
static void format_ram_disk(void)
{
    static const char text[]="Console MegaPro : disque USB en memoire (DDR), efface a l'extinction.\r\n"
                             "Le port serie du meme cable donne le journal du firmware.\r\n";
    enum{FAT_SECTORS=64,ROOT_SECTOR=1+2*FAT_SECTORS,DATA_SECTOR=ROOT_SECTOR+32};
    memset(RAM_DISK,0,(size_t)RAM_BLOCKS*512U);
    uint8_t *b=RAM_DISK;
    b[0]=0xeb;b[1]=0x3c;b[2]=0x90;memcpy(b+3,"CONSOLE ",8);
    put16(b+11,512);b[13]=4;put16(b+14,1);b[16]=2;put16(b+17,512);put16(b+19,0);b[21]=0xf8;put16(b+22,FAT_SECTORS);
    put16(b+24,63);put16(b+26,255);put32(b+28,0);put32(b+32,RAM_BLOCKS);
    b[36]=0x80;b[38]=0x29;put32(b+39,0x20261005);memcpy(b+43,"CONSOLE    FAT16   ",19);b[510]=0x55;b[511]=0xaa;
    for(unsigned copy=0;copy<2;++copy){uint8_t *fat=RAM_DISK+(1+copy*FAT_SECTORS)*512U;fat[0]=0xf8;fat[1]=0xff;fat[2]=0xff;fat[3]=0xff;fat[4]=0xff;fat[5]=0xff;}
    uint8_t *root=RAM_DISK+ROOT_SECTOR*512U;
    memcpy(root,"CONSOLE    ",11);root[11]=0x08;
    memcpy(root+32,"LISEZMOITXT",11);root[32+11]=0x20;put16(root+32+24,((2026U-1980U)<<9)|(10U<<5)|5U);put16(root+32+26,2);put32(root+32+28,sizeof text-1);
    memcpy(RAM_DISK+DATA_SECTOR*512U,text,sizeof text-1);
}
static void choose_media(int announce)
{
    usb_msc_disk disk={0,0,NULL,NULL,NULL,NULL};
    int result=sd_init(&card,20000000);
    if(result==SD_OK&&card.sectors){on_sd=1;disk.blocks=card.sectors;disk.read=card_read;disk.write=card_write;}
    else{on_sd=0;disk.blocks=RAM_BLOCKS;disk.read=ram_read;disk.write=ram_write;}
    printf("USBDISK MEDIA=%s BLOCKS=%u SD_INIT=%d\r\n",on_sd?"SD":"DDR",(unsigned)disk.blocks,result);
    if(announce)usb_msc_media(&disk);else usb_msc_init(&disk);
}
static void state(void)
{
    const usb_msc_stats *s=usb_msc_statistics();int hs=0;int online=usb_msc_online(&hs);
    printf("USBDISK MEDIA=%s SERVING=%d TAKEOVERS=%u ONLINE=%d HS=%d COMMANDS=%u FAILED=%u READ=%u WRITTEN=%u RESETS=%u RESYNCS=%u TIMEOUTS=%u LOSSES=%u LAST=%02X PORT=%08X\r\n",
        on_sd?"SD":"DDR",usb_msc_serving(),(unsigned)s->takeovers,online,hs,(unsigned)s->commands,(unsigned)s->failed,(unsigned)s->read_blocks,(unsigned)s->written_blocks,
        (unsigned)s->resets,(unsigned)s->resyncs,(unsigned)s->timeouts,(unsigned)s->losses,s->last_opcode,(unsigned)usb_msc_reg_read(4));
    if(on_sd)printf("USBDISK SD CRC_ERRORS=%u RETRIES=%u DOWNSHIFTS=%u HZ=%u\r\n",card.crc_errors,card.retries,card.downshifts,card.hz);
}
int main(void)
{
    clear_csr(NDS_MSTATUS,8);write_csr(NDS_MIE,0);
    ae350_dcache_flush_all();ae350_icache_invalidate_all();
    __asm__ volatile("fence iorw,iorw\n.word 0x0000100f":::"memory");
    const unsigned div=(80000000UL+8UL*115200)/(16UL*115200);
    AE350_UART2->LCR=0x83;AE350_UART2->DLL=div&255;AE350_UART2->DLM=div>>8;AE350_UART2->LCR=3;AE350_UART2->FCR=7;
    if(usb_msc_reg_read(0)!=0x554d5343U){printf("USBDISK FAIL PORT ABSENT : BITSTREAM SANS DISQUE USB\r\n");for(;;){}}
    if(usb_msc_reg_read(0x28)!=1){printf("USBDISK FAIL BOT GUARD ABSENT : CHARGER LE FPGA CORRIGE\r\n");for(;;){}}
    format_ram_disk();
    choose_media(0);
    printf("USBDISK READY R4 ILM CORE=800MHZ PORT=%08X\r\n",(unsigned)usb_msc_reg_read(0));
    int was_online=-1,was_serving=-1,released=0;
    for(;;){
        if(!released)usb_msc_poll();
        int serving=usb_msc_serving();
        if(serving!=was_serving){was_serving=serving;printf("USBDISK %s\r\n",serving?"SERVING THE DISK":"DISK LEFT TO HARDWARE (EMPTY READER)");}
        if(!(AE350_UART2->LSR&1U)){
            int hs=0;int online=usb_msc_online(&hs);
            if(online!=was_online){was_online=online;printf("USBDISK HOST %s%s\r\n",online?"CONFIGURED":"ABSENT",online?(hs?" HS":" FS"):"");}
            continue;
        }
        unsigned char c=AE350_UART2->RBR;
        if(c=='?')printf("USBDISK R4 CDC + MSC BOT_GUARD=1 SD_STATUS=1\r\n");
        else if(c=='s')state();
        else if(c=='m')choose_media(1);
        else if(c=='d'){
            usb_msc_disk disk={RAM_BLOCKS,0,NULL,ram_read,ram_write,NULL};
            on_sd=0;
            if(released){released=0;usb_msc_init(&disk);}else usb_msc_media(&disk);
            printf("USBDISK MEDIA=DDR BLOCKS=%u FORCED=1\r\n",RAM_BLOCKS);
        }
        else if(c=='q'){released=1;usb_msc_release();}
        else if(c=='g'){released=0;choose_media(0);}
        else if(c=='v'){
            // Zone d'essai : 8 Mio à partir du bloc 32768, écrits par le PC. CRC32 pour comparaison.
            printf("USBDISK VERIFY CRC=%08X\r\n",(unsigned)crc32(RAM_DISK+32768U*512U,8U<<20));
        }
    }
}
