// Régressions adversariales MSC et propagation d'une erreur SD jusqu'au CSW.
#define main baseline_main
#include "usb_msc_test.c"
#undef main
#include "sd.h"
void model_load(uint8_t *,uint32_t);
void model_programming_errors(unsigned);
static sd_card card;
static int sd_callback(void *unused,uint32_t lba,const uint8_t *bytes,uint32_t n)
{ (void)unused;return sd_write(&card,lba,bytes,n)!=SD_OK; }
static void fixture(void)
{
    rx_head=rx_tail=tx_pushed=tx_committed=tx_taken=packets=0;
    status_flags=0x60;lost=host_lazy=host_stopped=0;max_packet=512;
    disk.write=disk_write;memset(media,0,sizeof media);usb_msc_init(&disk);
    for(unsigned i=0;i<20 && !usb_msc_serving();++i)usb_msc_poll();
    uint8_t tur[6]={0};uint32_t residue;
    CHECK(bot(tur,6,0,0,NULL,&residue)==1); // UNIT ATTENTION
    rx_head=rx_tail=tx_pushed=tx_committed=tx_taken=packets=0;
}
static void queued_write(void)
{
    uint8_t cb[10]={0x2a,0,0,0,0,23,0,0,1,0};queue_command(cb,10,0,512);
    memset(rx+rx_tail,0xa5,512);rx_tail+=512;
}
int main(void)
{
    for(unsigned fault=0;fault<5;++fault) {
        fixture();queued_write();
        if(fault==0)rx[14]=1;
        if(fault==1)rx[12]=1;
        if(fault==2)rx[14]=0xea;
        if(fault==3)rx[0]=0;
        if(fault==4)rx[13]=1;
        CHECK(usb_msc_poll()==1 && (status_flags & 0x400));
        CHECK(tx_pushed==0 && usb_msc_statistics()->written_blocks==0);
        // Nouvelle commande bien formée, sans reset : aucun effet.
        queued_write();CHECK(usb_msc_poll()==0 && tx_pushed==0);
        for(unsigned i=0;i<512;++i)CHECK(media[23*512+i]==0);
        usb_msc_media(&disk);CHECK(usb_msc_poll()==0);
        // Le reset hôte purge tout le suffixe et rend la commande suivante possible.
        status_flags|=8;CHECK(usb_msc_poll()==0 && !(status_flags & 0x400));
        uint8_t tur[6]={0};uint32_t residue;
        CHECK(bot(tur,6,0,0,NULL,&residue)==1); // changement de support testé ci-dessus
        uint8_t block[512];memset(block,0xa5,sizeof block);
        CHECK(rw(1,23,1,block,&residue)==0 && !memcmp(media+23*512,block,512));
        printf("MSC malformed %u: refused, sticky lock, BOT reset, next WRITE PASS\n",fault);
    }
    for(unsigned blocks=1;blocks<=2;++blocks) {
        fixture();model_load(media,BLOCKS);CHECK(sd_init(&card,20000000)==SD_OK);
        disk.write=sd_callback;usb_msc_media(&disk);
        uint8_t tur[6]={0};uint32_t residue;
        CHECK(bot(tur,6,0,0,NULL,&residue)==1);
        uint8_t block[1024];memset(block,0x5a,sizeof block);
        model_programming_errors(blocks);
        CHECK(rw(1,23,blocks,block,&residue)==1);
        CHECK(request_sense()==0x030c00 && usb_msc_statistics()->written_blocks==0);
        for(unsigned i=0;i<512*blocks;++i)CHECK(media[23*512+i]==0);
        CHECK(rw(1,23,blocks,block,&residue)==0 && !memcmp(media+23*512,block,512*blocks));
        printf("SD error -> MSC failed CSW + MEDIUM ERROR blocks=%u PASS\n",blocks);
    }
    puts("MSC FAULT PASS");return 0;
}
