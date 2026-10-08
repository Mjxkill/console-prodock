// Adversarial extension of the existing SD model; production sd.c is unchanged.
// Model time is virtual. No hardware, filesystems or physical cards are accessed.
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
static unsigned late_failure, pending_r2, delayed_last_block, cmd13_count, stop_count;
static void *review_copy(void *dst, const void *src, size_t n);
#define memcpy review_copy
#define sd_port_exchange baseline_exchange
#include "../host/sd_model.c"
#undef sd_port_exchange
#undef memcpy

static void *review_copy(void *dst, const void *src, size_t n)
{
    if (late_failure) { pending_r2=0x04; return dst; }
    return memcpy(dst,src,n);
}
void sd_port_exchange(const uint8_t *tx, uint8_t *rx, unsigned count)
{
    unsigned before=m.writes;
    int cmd13=tx && count==6 && tx[0]==(0x40|13);
    if (tx && count==1 && tx[0]==0xfd && m.writing && m.multi) ++stop_count;
    baseline_exchange(tx,rx,count);
    if (delayed_last_block && before<2 && m.writes==2) m.busy=400;
    // Add SEND_STATUS, absent from the baseline model. The R2 error is raised
    // after data acceptance, just as a programming failure can be on a card.
    if (cmd13) { ++cmd13_count; m.head=m.count=0; push(0xff); push(0); push(pending_r2); }
}
static unsigned probe_r2(void)
{
    uint8_t frame[6]={0x40|13,0,0,0,0,0}, value=0xff;
    frame[5]=sd_crc7(frame,5); sd_port_select(1);
    sd_port_exchange(frame,NULL,6);
    for (unsigned i=0;i<10 && value==0xff;++i) sd_port_exchange(NULL,&value,1);
    if (value!=0) { fprintf(stderr,"R1 probe failed: %u\n",value); exit(2); }
    sd_port_exchange(NULL,&value,1); sd_port_select(0); return value;
}
int main(void)
{
    static uint8_t media[4096*512], payload[1024];
    memset(payload,0xa5,sizeof payload);
    const char *names[]={"single_control","single_late_error","multi_control","multi_late_error","multi_stop_timeout"};
    unsigned reproduced=0;
    for (unsigned test=0;test<5;++test) {
        memset(media,0,sizeof media); model_load(media,4096);
        late_failure=test==1 || test==3; delayed_last_block=test==4;
        pending_r2=cmd13_count=stop_count=0;
        sd_card card; if (sd_init(&card,20000000)!=SD_OK) return 3;
        unsigned blocks=test>=2 ? 2:1;
        int result=sd_write(&card,23,payload,blocks);
        unsigned changed=0; for (unsigned i=0;i<512*blocks;++i) changed+=media[23*512+i]!=0;
        unsigned still_writing=m.writing, driver_cmd13=cmd13_count, stops=stop_count;
        unsigned r2=probe_r2();
        printf("CASE %s: result=%d changed=%u/%u driver_CMD13=%u R2=%02x stop_tokens=%u writing_after_return=%u\n",
               names[test],result,changed,512*blocks,driver_cmd13,r2,stops,still_writing);
        if (test==0 || test==2) {
            if (result!=SD_OK || changed!=512*blocks || r2 || still_writing) return 4;
        } else if (test==4) {
            if (result==SD_OK && stops==0 && still_writing) ++reproduced;
        } else if (result==SD_OK && changed==0 && r2!=0 && driver_cmd13==0) ++reproduced;
    }
    printf("SILENT_SD_FAILURES_REPRODUCED=%u (expected safe count=0)\n",reproduced);
    return reproduced==3 ? 0:1;
}
