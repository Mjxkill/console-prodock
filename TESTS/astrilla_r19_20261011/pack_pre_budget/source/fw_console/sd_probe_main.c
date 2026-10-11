// Sonde de la carte SD : application téléchargée en ILM qui affiche les octets bruts échangés
// (trame CMD0 puis CMD8) et les registres SPI/GPIO, pour relever un défaut de câblage ou de
// réglage avant d'accuser le pilote. Sortie en majuscules, commande r en minuscule (voir usb_disk_main.c).
#include <stdio.h>
#include "ae350.h"
#include "cache.h"
#include "sd.h"
unsigned sd_ae350_detect_raw(void);
static void put(unsigned c){while(!(AE350_UART2->LSR&0x20U)){}AE350_UART2->THR=c;}
long except_handler(long cause,long epc){const char *s="\r\nSDPROBE TRAP ";while(*s)put(*s++);unsigned v[3]={(unsigned)cause,(unsigned)epc,read_csr(NDS_MTVAL)};for(unsigned i=0;i<3;++i){for(int b=28;b>=0;b-=4)put("0123456789ABCDEF"[(v[i]>>b)&15]);put(' ');}for(;;){}}
static void dump(const char *name,const uint8_t *p,unsigned n){printf("SDPROBE %s",name);for(unsigned i=0;i<n;++i)printf(" %02X",p[i]);printf("\r\n");}
static void probe(unsigned hz)
{
    static const uint8_t cmd0[6]={0x40,0,0,0,0,0x95},cmd8[6]={0x48,0,0,1,0xaa,0x87};
    uint8_t in[16];
    sd_port_speed(hz);
    printf("SDPROBE HZ=%u TRANSFMT=%08X TIMING=%08X STATUS=%08X GPIO_IN=%08X DIR=%08X DETECT=%u\r\n",hz,(unsigned)AE350_SPI->TRANSFMT,
        (unsigned)AE350_SPI->TIMING,(unsigned)AE350_SPI->STATUS,(unsigned)AE350_GPIO->DATAIN,(unsigned)AE350_GPIO->CHANNELDIR,sd_ae350_detect_raw());
    sd_port_select(0);sd_port_exchange(NULL,in,16);dump("IDLE",in,16);
    // La broche de sélection est relue par GPIO 0 : 0 attendu une fois la carte sélectionnée.
    sd_port_select(1);unsigned low=(unsigned)AE350_GPIO->DATAIN,out_low=(unsigned)AE350_GPIO->DATAOUT;sd_port_select(0);
    printf("SDPROBE SELECT GPIO_IN=%08X DATAOUT=%08X THEN GPIO_IN=%08X DATAOUT=%08X\r\n",low,out_low,(unsigned)AE350_GPIO->DATAIN,(unsigned)AE350_GPIO->DATAOUT);
    for(unsigned attempt=0;attempt<3;++attempt){
        sd_port_select(1);sd_port_exchange(cmd0,NULL,6);sd_port_exchange(NULL,in,12);dump("CMD0",in,12);
        sd_port_select(0);sd_port_exchange(NULL,in,2);
    }
    sd_port_select(1);sd_port_exchange(cmd8,NULL,6);sd_port_exchange(NULL,in,12);dump("CMD8",in,12);
    sd_port_select(0);sd_port_exchange(NULL,in,2);
    // Échange simultané : l'octet lu pendant l'émission de 0xFF.
    static const uint8_t ones[8]={0xff,0xff,0xff,0xff,0xff,0xff,0xff,0xff};
    sd_port_select(1);sd_port_exchange(ones,in,8);dump("BOTH",in,8);sd_port_select(0);
    sd_card card;int result=sd_init(&card,hz>20000000?20000000:hz);
    printf("SDPROBE INIT=%d READY=%u V2=%u HC=%u SECTORS=%u\r\n",result,card.ready,card.version2,card.high_capacity,(unsigned)card.sectors);
}
int main(void)
{
    clear_csr(NDS_MSTATUS,8);write_csr(NDS_MIE,0);
    ae350_dcache_flush_all();ae350_icache_invalidate_all();
    __asm__ volatile("fence iorw,iorw\n.word 0x0000100f":::"memory");
    const unsigned div=(80000000UL+8UL*115200)/(16UL*115200);
    AE350_UART2->LCR=0x83;AE350_UART2->DLL=div&255;AE350_UART2->DLM=div>>8;AE350_UART2->LCR=3;AE350_UART2->FCR=7;
    printf("SDPROBE READY\r\n");
    // Quatre montages possibles : convention des validations SPI (GPIO 4) x sens déclaré de GPIO 0.
    // Pour chacun : fronts vus sur l'horloge et la commande pendant un transfert lent, puis CMD0.
    for(unsigned combo=0;combo<4;++combo){
        sd_port_speed(100000);
        if(combo&1)AE350_GPIO->DOUTSET=1U<<4;else AE350_GPIO->DOUTCLEAR=1U<<4;
        if(combo&2)AE350_GPIO->CHANNELDIR&=~1U;else AE350_GPIO->CHANNELDIR|=1U;
        unsigned clk_edges=0,cmd_edges=0,last=(unsigned)AE350_GPIO->DATAIN;
        static const uint8_t pattern[8]={0x55,0x55,0x55,0x55,0x55,0x55,0x55,0x55};
        while(AE350_SPI->STATUS&1U){}
        AE350_SPI->CTRL|=6U;while(AE350_SPI->CTRL&6U){}
        AE350_SPI->TRANSCTRL=(1U<<24)|(7U<<12)|7U;
        for(unsigned i=0;i<8;++i)AE350_SPI->DATA=pattern[i];
        AE350_SPI->CMD=0;
        for(unsigned i=0;i<4000;++i){unsigned now=(unsigned)AE350_GPIO->DATAIN;if((now^last)&4U)++clk_edges;if((now^last)&8U)++cmd_edges;last=now;}
        while(AE350_SPI->STATUS&1U){}
        printf("SDPROBE COMBO=%u OE_HIGH=%u DIR0=%u CLK_EDGES=%u CMD_EDGES=%u\r\n",combo,combo&1,(unsigned)AE350_GPIO->CHANNELDIR&1U,clk_edges,cmd_edges);
        probe(400000);
    }
    // R40 avait un sélecteur de polarité de diagnostic sur GPIO 4 : seul
    // COMBO=1 communique avec la SD. Le laisser dans cet état pour que le
    // programme suivant fonctionne aussi sans reset FPGA. Les RTL récents
    // fixent directement cette polarité et ignorent ce bit.
    AE350_GPIO->DOUTSET=1U<<4;AE350_GPIO->CHANNELDIR|=1U;
    printf("SDPROBE DONE\r\n");
    for(;;){if((AE350_UART2->LSR&1U)&&AE350_UART2->RBR=='r'){probe(400000);printf("SDPROBE DONE\r\n");}}
}
