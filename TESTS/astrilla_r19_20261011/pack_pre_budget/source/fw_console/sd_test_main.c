// Essai de la carte SD sur la console : application téléchargée en ILM (le firmware incorporé reste
// gpu_diag). Initialise la carte, monte le système FAT, lit chaque fichier de la racine en DDR avec
// CRC32 et débit, écrit puis relit un fichier. Commandes UART : ? identité, R relance l'essai,
// L charge /ORBITAL.BIN à l'adresse des ressources d'Orbital et affiche son CRC32.
#include <stdio.h>
#include <string.h>
#include "ae350.h"
#include "cache.h"
#include "sd.h"
#include "ff.h"
void disk_speed(unsigned hz); const sd_card *disk_card(void); unsigned sd_ae350_detect_raw(void); unsigned sd_ae350_spi_id(void);
#define BUFFER ((uint8_t *)0x06000000UL)        // DDR, au-delà des ressources des démonstrations
#define ORBITAL ((uint8_t *)0x05000000UL)
static FATFS fs;
static unsigned long long cycles(void){unsigned hi,lo,again;do{__asm__ volatile("rdcycleh %0":"=r"(hi));__asm__ volatile("rdcycle %0":"=r"(lo));__asm__ volatile("rdcycleh %0":"=r"(again));}while(hi!=again);return ((unsigned long long)hi<<32)|lo;}
static void put(unsigned c){while(!(AE350_UART2->LSR&0x20U)){}AE350_UART2->THR=c;}
long except_handler(long cause,long epc){const char *s="\r\nSDTEST TRAP ";while(*s)put(*s++);unsigned v[3]={(unsigned)cause,(unsigned)epc,read_csr(NDS_MTVAL)};for(unsigned i=0;i<3;++i){for(int b=28;b>=0;b-=4)put("0123456789abcdef"[(v[i]>>b)&15]);put(' ');}for(;;){}}
static uint32_t crc32(const uint8_t *p,unsigned n){static uint32_t table[256];if(!table[1])for(unsigned i=0;i<256;++i){uint32_t c=i;for(unsigned b=0;b<8;++b)c=(c>>1)^(0xedb88320U&(0U-(c&1)));table[i]=c;}uint32_t c=~0U;for(unsigned i=0;i<n;++i)c=table[(c^p[i])&255]^(c>>8);return ~c;}
// Lit un fichier entier en DDR ; renvoie sa taille ou -1.
static long load(const char *name,uint8_t *where,unsigned *ms)
{
    FIL file;UINT got;long done=0;unsigned long long start=cycles();
    if(f_open(&file,name,FA_READ)!=FR_OK)return -1;
    long size=(long)f_size(&file);
    while(done<size){UINT ask=size-done>65536?65536U:(UINT)(size-done);if(f_read(&file,where+done,ask,&got)!=FR_OK||got!=ask){f_close(&file);return -1;}done+=got;}
    f_close(&file);*ms=(unsigned)((cycles()-start)/800000ULL);return size;
}
static int test(unsigned hz)
{
    int errors=0;DIR dir;FILINFO info;FIL file;UINT count;unsigned ms=0;
    printf("SDTEST spi_id=%08x detect_raw=%u ask_hz=%u\r\n",sd_ae350_spi_id(),sd_ae350_detect_raw(),hz);
    disk_speed(hz);FRESULT mounted=f_mount(&fs,"",1);const sd_card *card=disk_card();
    printf("SDTEST mount=%d ready=%u v2=%u hc=%u sectors=%u hz=%u\r\n",(int)mounted,card->ready,card->version2,card->high_capacity,(unsigned)card->sectors,card->hz);
    if(mounted!=FR_OK){printf("SDTEST FAIL mount\r\n");return 1;}
    if(f_opendir(&dir,"/")!=FR_OK){printf("SDTEST FAIL opendir\r\n");return 1;}
    while(f_readdir(&dir,&info)==FR_OK&&info.fname[0]){
        if(info.fattrib&AM_DIR){printf("SDTEST dir %s\r\n",info.fname);continue;}
        long size=load(info.fname,BUFFER,&ms);
        if(size<0){printf("SDTEST FAIL read %s\r\n",info.fname);++errors;continue;}
        printf("SDTEST file %s bytes=%u crc=%08x ms=%u kbps=%u\r\n",info.fname,(unsigned)size,(unsigned)crc32(BUFFER,(unsigned)size),ms,ms?(unsigned)((unsigned long long)size*8/ms):0U);
    }
    f_closedir(&dir);
    // Écriture de 256 Kio, relecture et comparaison.
    for(unsigned i=0;i<262144;++i)BUFFER[i]=(uint8_t)(i*131+i/251);
    unsigned long long start=cycles();
    if(f_open(&file,"CONSOLE.TST",FA_WRITE|FA_CREATE_ALWAYS)!=FR_OK||f_write(&file,BUFFER,262144,&count)!=FR_OK||count!=262144||f_close(&file)!=FR_OK){printf("SDTEST FAIL write\r\n");++errors;}
    else{unsigned wms=(unsigned)((cycles()-start)/800000ULL);memset(BUFFER,0,262144);long size=load("CONSOLE.TST",BUFFER,&ms);int same=size==262144;
        for(unsigned i=0;same&&i<262144;++i)same=BUFFER[i]==(uint8_t)(i*131+i/251);
        printf("SDTEST write bytes=262144 ms=%u read_ms=%u same=%d\r\n",wms,ms,same);if(!same)++errors;}
    card=disk_card();
    printf("SDTEST %s errors=%d crc_errors=%u retries=%u downshifts=%u hz=%u\r\n",errors?"FAIL":"PASS",errors,card->crc_errors,card->retries,card->downshifts,card->hz);
    return errors;
}
int main(void)
{
    clear_csr(NDS_MSTATUS,8);write_csr(NDS_MIE,0);
    ae350_dcache_flush_all();ae350_icache_invalidate_all();
    __asm__ volatile("fence iorw,iorw\n.word 0x0000100f":::"memory");
    const unsigned div=(80000000UL+8UL*115200)/(16UL*115200);
    AE350_UART2->LCR=0x83;AE350_UART2->DLL=div&255;AE350_UART2->DLM=div>>8;AE350_UART2->LCR=3;AE350_UART2->FCR=7;
    printf("SDTEST READY R1 ILM core=800MHz\r\n");
    test(20000000);
    for(;;){
        if(!(AE350_UART2->LSR&1U))continue;
        unsigned char c=AE350_UART2->RBR;
        if(c=='?')printf("SDTEST R1 SD SPI AE350\r\n");
        else if(c=='R')test(20000000);
        else if(c=='H')test(40000000);
        else if(c=='S')test(10000000);
        else if(c=='L'){unsigned ms=0;long size=load("ORBITAL.BIN",ORBITAL,&ms);
            if(size<0)printf("SDTEST LOAD FAIL\r\n");
            else{ae350_dcache_flush_all();printf("SDTEST LOAD bytes=%u crc=%08x ms=%u\r\n",(unsigned)size,(unsigned)crc32(ORBITAL,(unsigned)size),ms);}}
    }
}
