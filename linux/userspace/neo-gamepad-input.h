// SPDX-License-Identifier: GPL-2.0-or-later
// Linux evdev consumer. FPGA ports exist even while their pads are unplugged.
#include <linux/input.h>

enum { PAD_NOVA=1, PAD_START=2, PAD_VIEW=4 };
typedef struct {
    int fd,x,y,next_x,next_y,dropped;
    unsigned keys,next_keys,pressed;
} NeoPad;

static void neo_pad_event(NeoPad *p,const struct input_event *e)
{
    if(e->type==EV_SYN && e->code==SYN_DROPPED) {
        p->dropped=1;p->x=p->y=0;p->keys=p->pressed=0;return;
    }
    if(e->type==EV_SYN && e->code==SYN_REPORT) {
        if(p->dropped) {
            struct input_absinfo x={0},y={0};
            unsigned long bits[(KEY_MAX+8*sizeof(unsigned long))/(8*sizeof(unsigned long))]={0};
            p->next_keys=0;p->next_x=p->next_y=0;
            if(!ioctl(p->fd,EVIOCGABS(ABS_X),&x) && !ioctl(p->fd,EVIOCGABS(ABS_Y),&y)) {
                p->next_x=x.value;p->next_y=y.value;
            }
            if(!ioctl(p->fd,EVIOCGKEY(sizeof(bits)),bits)) {
                const unsigned codes[]={BTN_SOUTH,BTN_START,BTN_SELECT};
                for(unsigned k=0;k<3;++k)
                    if(bits[codes[k]/(8*sizeof(unsigned long))] &
                       (1UL<<(codes[k]%(8*sizeof(unsigned long)))))p->next_keys|=1U<<k;
            }
            p->keys=p->next_keys;p->dropped=0; /* suppress synthetic presses */
        } else p->pressed|=p->next_keys&~p->keys;
        p->x=p->next_x;p->y=p->next_y;p->keys=p->next_keys;
        return;
    }
    if(p->dropped)return;
    if(e->type==EV_ABS) {
        int value=e->value<0?-1:e->value>0?1:0;
        if(e->code==ABS_X)p->next_x=value;
        if(e->code==ABS_Y)p->next_y=value;
    } else if(e->type==EV_KEY) {
        unsigned mask=e->code==BTN_SOUTH?PAD_NOVA:e->code==BTN_START?PAD_START:e->code==BTN_SELECT?PAD_VIEW:0;
        if(e->value)p->next_keys|=mask;else p->next_keys&=~mask;
    }
}

static void neo_pads_open(NeoPad p[2])
{
    for(unsigned n=0;n<16;++n) {
        char path[64],name[80]={0};snprintf(path,sizeof(path),"/dev/input/event%u",n);
        int fd=open(path,O_RDONLY|O_NONBLOCK|O_CLOEXEC);
        if(fd<0)continue;
        int port=-1;
        if(ioctl(fd,EVIOCGNAME(sizeof(name)),name)>=0) {
            if(!strcmp(name,"Tang Neo gamepad 1"))port=0;
            if(!strcmp(name,"Tang Neo gamepad 2"))port=1;
        }
        if(port>=0 && p[port].fd<0)p[port].fd=fd;else close(fd);
    }
}

static void neo_pad_read(NeoPad *p)
{
    p->pressed=0;
    if(p->fd<0)return;
    struct input_event events[32];ssize_t n;
    // Bound work/frame if a faulty source continuously floods the fd.
    for(unsigned batch=0;batch<8;++batch) {
        n=read(p->fd,events,sizeof(events));
        if(n<0 && (errno==EAGAIN || errno==EINTR))return;
        if(n<=0 || n%(ssize_t)sizeof(events[0])) {
            close(p->fd);*p=(NeoPad){.fd=-1};return;
        }
        for(unsigned i=0;i<(unsigned)n/sizeof(events[0]);++i)neo_pad_event(p,&events[i]);
    }
}
