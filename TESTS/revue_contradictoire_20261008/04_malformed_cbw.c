// Test de revue : le firmware de production est compilé sans modification.
#define main existing_suite_main
#include "TESTS/host/usb_msc_test.c"
#undef main

static void reset_fixture(void) {
    rx_head=rx_tail=tx_pushed=tx_committed=tx_taken=packets=0;
    status_flags=0x60; lost=host_lazy=host_stopped=0; max_packet=512;
    memset(media,0,sizeof media);
    usb_msc_init(&disk);
    for(unsigned i=0;i<20 && !usb_msc_serving();++i) usb_msc_poll();
    uint8_t tur[6]={0}; uint32_t residue;
    CHECK(bot(tur,6,0,0,NULL,&residue)==1); // UNIT ATTENTION initiale
    rx_head=rx_tail=tx_pushed=tx_committed=tx_taken=packets=0;
}
int main(void) {
    const char *names[]={"valid_control","CDB_length_1_for_WRITE10","reserved_flags","reserved_CDB_length_bits","bad_signature_then_WRITE10_without_reset"};
    unsigned reproduced=0;
    for(unsigned test=0;test<5;++test) {
        reset_fixture();
        uint8_t cb[10]={0x2a,0,0,0,0,23,0,0,1,0};
        queue_command(cb,10,0,512);
        if(test==1)rx[14]=1;
        if(test==2)rx[12]=1;
        if(test==3)rx[14]=0xea;
        if(test==4){rx[0]=0;queue_command(cb,10,0,512);}
        memset(rx+rx_tail,0xa5,512);rx_tail+=512;
        CHECK(usb_msc_poll()==1);
        while(tx_taken!=tx_committed)host_take();
        unsigned changed=0;for(unsigned i=0;i<512;++i)changed+=media[23*512+i]!=0;
        unsigned status=tx_pushed==13 ? tx[12] : 255;
        printf("CASE %s: changed_bytes=%u csw_status=%u written_blocks=%u resyncs=%u\n",names[test],changed,status,usb_msc_statistics()->written_blocks,usb_msc_statistics()->resyncs);
        if(test==0) CHECK(changed==512 && status==0);
        else if(changed==512 && status==0)++reproduced;
    }
    printf("MALFORMED_WRITES_REPRODUCED=%u (expected safe count=0)\n",reproduced);
    return reproduced==4 ? 0 : 1;
}
