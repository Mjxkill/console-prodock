/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Actual U-Boot wrapper under timed MMIO. Tick units do not predict throughput.
 * TX room appears at shifter load, RX only on completion. Audits survive reset
 * between chunks to verify CS, pointer progression and trailing clocks. */
#define _GNU_SOURCE
#include <dm.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include "prodock-spi-pio.h"

/* U-Boot API mechanics live in this translation unit, never in shim headers.
 * Driver private storage is allocated from the exported registration size. */
void *dev_get_priv(struct udevice *d) { return d->priv; }
void *dev_read_addr_index_ptr(struct udevice *d, unsigned i)
{ return i ? d->gpio : d->base; }
unsigned spi_chip_select(struct udevice *d) { return d->cs; }

static uint32_t registers[32], gpio_regs[32];
static struct {
    unsigned ticks, steps, selected, assertions, releases;
    unsigned reset_stuck, busy_stuck, rx_stuck, trailing_stuck;
    unsigned expected, written, read, completed, started, prime, credit;
    unsigned tx_count, tx_head, tx_tail, rx_count, rx_head, rx_tail;
    unsigned active, due, shifted, cmd_count, all_reads, violations, resets;
    uint8_t txq[16], rxq[16], shift_byte, wire[2048];
    unsigned sizes[32], cs[32], primes[32], wire_cs[2048];
} m;
static void check(int truth, const char *reason)
{ if (!truth) { fprintf(stderr,"FAIL: %s\n",reason); exit(1); } }
static uint8_t response(uint8_t tx, unsigned index)
{ return (uint8_t)(tx ^ 0xa7U ^ (index * 13U) ^ ((index >> 8) * 29U)); }
static uint8_t pattern(unsigned index)
{ return (uint8_t)(index * 53U + 7U + ((index >> 8) * 37U)); }
static void tick(void)
{
    check(++m.steps < 200000, "bounded MMIO model");
    ++m.ticks;
    if (!m.started || m.rx_stuck || (m.trailing_stuck && !m.selected)) return;
    if (m.active && m.ticks >= m.due) {
        check(m.rx_count < 16,"RX overflow");
        m.rxq[m.rx_tail++ % 16] = response(m.shift_byte,m.shifted-1);
        ++m.rx_count; ++m.completed; m.active=0;
    }
    if (!m.active && m.tx_count) {
        m.shift_byte=m.txq[m.tx_head++ % 16]; --m.tx_count;
        check(m.shifted < sizeof(m.wire),"wire audit overflow");
        m.wire[m.shifted]=m.shift_byte; m.wire_cs[m.shifted++]=m.selected;
        m.active=1; m.due=m.ticks+2;
    }
}
ulong get_timer(ulong start) { tick(); return (m.ticks/16U)-start; }
u32 readl(const volatile void *pointer)
{
    uintptr_t addr=(uintptr_t)pointer, base=(uintptr_t)registers, gpio=(uintptr_t)gpio_regs;
    if (addr>=gpio && addr<gpio+sizeof(gpio_regs)) return gpio_regs[(addr-gpio)/4];
    check(addr>=base && addr<base+sizeof(registers),"read address");
    unsigned reg=(unsigned)(addr-base);
    if (reg==0x34) {
        tick();
        return (m.busy_stuck || (m.started && m.completed<m.expected) ? 1U:0) |
            (!m.rx_count ? 1U<<14 : 0) | (!m.tx_count ? 1U<<22 : 0) |
            (m.tx_count>=4 ? 1U<<23 : 0);
    }
    if (reg==0x30) return m.reset_stuck ? 6U:0U;
    if (reg==0x2c) {
        check(m.started && m.rx_count,"RX DATA while empty");
        uint8_t value=m.rxq[m.rx_head++%16]; --m.rx_count;
        ++m.read; ++m.all_reads; m.credit=1;
        return value;
    }
    return registers[reg/4];
}
void writel(u32 value, volatile void *pointer)
{
    uintptr_t addr=(uintptr_t)pointer, base=(uintptr_t)registers, gpio=(uintptr_t)gpio_regs;
    if (addr>=gpio && addr<gpio+sizeof(gpio_regs)) {
        unsigned reg=(unsigned)(addr-gpio);
        if (reg==0x2c) { check(value==1,"CS clear mask");m.selected=1;++m.assertions; }
        if (reg==0x30) { check(value==1,"CS set mask");m.selected=0;++m.releases; }
        gpio_regs[reg/4]=value; return;
    }
    check(addr>=base && addr<base+sizeof(registers),"write address");
    unsigned reg=(unsigned)(addr-base);
    registers[reg/4]=value;
    if (reg==0x30) {
        ++m.resets;
        m.expected=m.written=m.read=m.completed=m.started=m.credit=0;
        m.tx_count=m.tx_head=m.tx_tail=m.rx_count=m.rx_head=m.rx_tail=m.active=0;
        registers[0x10/4]=registers[0x38/4]=registers[0x40/4]=0;
    } else if (reg==0x20) {
        /* A new length starts a transaction only after the preceding one is
         * fully drained. The common core deliberately retains configuration. */
        check(!m.active && !m.tx_count && !m.rx_count,"chunk boundary drained");
        m.written=m.read=m.completed=m.started=m.credit=0;
        m.expected=(value&511U)+1;
        check(((value>>12)&511U)+1==m.expected,"matched RX/TX lengths");
    } else if (reg==0x10) {
        check(value==(7U<<8),"byte mode, no DataMerge");
    } else if (reg==0x2c) {
        check(m.tx_count<4 && m.written<m.expected,"TX count/overflow");
        if(m.started) { if(!m.credit)++m.violations; m.credit=0; }
        m.txq[m.tx_tail++%16]=(uint8_t)value; ++m.tx_count; ++m.written;
    } else if (reg==0x24) {
        check(!m.started && m.tx_count && m.cmd_count<32,"single CMD per chunk");
        m.sizes[m.cmd_count]=m.expected; m.cs[m.cmd_count]=m.selected;
        m.primes[m.cmd_count++]=m.written; m.started=1;
    }
}
static void *controller;
static struct udevice bus, device;
static void setup(void)
{
    memset(&m,0,sizeof(m)); memset(registers,0,sizeof(registers)); memset(gpio_regs,0,sizeof(gpio_regs));
    free(controller); controller=calloc(1,prodock_spi.priv_auto);
    check(controller!=NULL,"driver private allocation");
    bus=(struct udevice){.priv=controller,.base=registers,.gpio=gpio_regs};
    device=(struct udevice){.parent=&bus}; registers[0x40/4]=0x201;
    registers[0x7c/4]=0x11; /* Four-entry TX/RX capacity, checked at init. */
    check(!prodock_spi.probe(&bus),"fixture controller init");
    check(!prodock_spi.ops->set_speed(&bus,20000000),"fixture transfer speed");
    memset(&m,0,sizeof(m)); /* Only audit history; actual driver remains ready. */
}
struct guard { uint8_t *mapping,*data;size_t page; };
static struct guard allocate(unsigned n)
{
    struct guard g;
    g.page=(size_t)sysconf(_SC_PAGESIZE);check(n<=g.page,"page size");
    g.mapping=mmap(NULL,g.page*3,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    check(g.mapping!=MAP_FAILED,"mmap");
    check(!mprotect(g.mapping+g.page,g.page,PROT_READ|PROT_WRITE),"mprotect");
    g.data=g.mapping+2*g.page-n; return g;
}
static void cleanup(struct guard *g) { check(!munmap(g->mapping,g->page*3),"munmap"); }
static void basic(unsigned n,unsigned mode_value)
{
    setup();struct guard tx=allocate(n),rx=allocate(n);
    for(unsigned i=0;i<n;++i){tx.data[i]=pattern(i);rx.data[i]=0xcc;}
    check(!mprotect(tx.mapping+tx.page,tx.page,PROT_READ),"TX readonly");
    int use_tx=mode_value!=1,use_rx=mode_value!=2;
    check(!prodock_spi.ops->xfer(&device,n*8,use_tx?tx.data:NULL,use_rx?rx.data:NULL,SPI_XFER_BEGIN|SPI_XFER_END),"xfer success");
    unsigned chunks=(n+511)/512;
    check(m.cmd_count==chunks+1,"chunks plus trailing byte");
    check(m.assertions==1 && m.releases==1 && !m.selected,"CS lifecycle");
    check(!m.violations,"RX before every refill");
    for(unsigned i=0;i<chunks;++i){
        unsigned size=n-i*512; if(size>512)size=512;
        check(m.sizes[i]==size && m.cs[i]==1,"chunk length/CS");
        check(m.primes[i]==(size<4?size:4),"min4 priming");
    }
    check(m.sizes[chunks]==1 && !m.cs[chunks] && m.primes[chunks]==1,"trailing command after CS");
    check(m.shifted==n+1 && m.all_reads==n+1,"all bytes including discarded RX");
    for(unsigned i=0;i<n;++i){
        uint8_t sent=use_tx?pattern(i):0xff;
        check(m.wire[i]==sent && m.wire_cs[i]==1,"TX pointers and CS");
        if(use_rx)check(rx.data[i]==response(sent,i),"RX pointer/data");
    }
    check(m.wire[n]==0xff && !m.wire_cs[n],"trailing FF");
    check(registers[0x40/4]==0x201,"TIMING unchanged");
    check(!m.resets,"successful transfers do not reset FIFO configuration");
    cleanup(&tx);cleanup(&rx);
}
static unsigned extra(void)
{
    unsigned cases=0;uint8_t tx[8]={1,2,3,4,5,6,7,8},rx[8]={0};
    setup();check(!prodock_spi.ops->xfer(&device,24,tx,rx,SPI_XFER_BEGIN),"split begin");
    check(m.selected && m.cmd_count==1 && !m.releases,"CS held across calls");
    check(!prodock_spi.ops->xfer(&device,40,tx+3,rx+3,SPI_XFER_END),"split end");
    check(m.cmd_count==3 && m.assertions==1 && m.releases==1 && !m.selected,"split CS/trailing");
    for(unsigned i=0;i<8;++i)check(rx[i]==response(tx[i],i),"split data");
    ++cases;
    setup();check(!prodock_spi.ops->xfer(&device,0,NULL,NULL,SPI_XFER_BEGIN|SPI_XFER_END),"zero length");
    check(m.cmd_count==1 && m.sizes[0]==1 && !m.cs[0] && m.wire[0]==255,"zero trailing only");++cases;
    setup();check(prodock_spi.ops->xfer(&device,7,tx,rx,SPI_XFER_BEGIN|SPI_XFER_END)==-EINVAL,"unaligned bits");
    check(!m.cmd_count && !m.assertions && !m.selected,"invalid bits emit no clocks");++cases;
    setup();check(!prodock_spi.ops->xfer(&device,8,tx,rx,SPI_XFER_BEGIN),"selected before bad length");
    check(prodock_spi.ops->xfer(&device,7,tx,rx,SPI_XFER_END)==-EINVAL,"bad length during selected transaction");
    check(!m.selected && m.cmd_count==1,"bad length releases selected CS");
    check(!prodock_spi.ops->xfer(&device,8,tx,rx,SPI_XFER_BEGIN|SPI_XFER_END),"bad length permits next valid transfer");++cases;
    setup();m.rx_stuck=1;check(prodock_spi.ops->xfer(&device,64,tx,rx,SPI_XFER_BEGIN|SPI_XFER_END)==-ETIMEDOUT,"RX timeout");
    check(!m.selected && m.assertions==1 && m.releases==1 && m.cmd_count==1,"timeout deselects, no trailing");
    check(m.resets==1 && registers[0x40/4]==0x201,"recovery restores clock after reset");
    m.rx_stuck=0;check(!prodock_spi.ops->xfer(&device,8,tx,rx,SPI_XFER_BEGIN|SPI_XFER_END),"RX timeout recovery permits transfer");++cases;
    setup();m.rx_stuck=m.reset_stuck=1;
    check(prodock_spi.ops->xfer(&device,8,tx,rx,SPI_XFER_BEGIN|SPI_XFER_END)==-ETIMEDOUT,"failed reset preserves original timeout");
    check(!m.selected && m.resets==1,"failed recovery leaves CS high");
    check(prodock_spi.ops->claim_bus(&device)==-EIO,"failed recovery blocks claim");
    m.rx_stuck=m.reset_stuck=0;check(!prodock_spi.probe(&bus),"explicit reinit after failed recovery");++cases;
    setup();m.busy_stuck=1;check(prodock_spi.ops->xfer(&device,8,tx,rx,SPI_XFER_BEGIN|SPI_XFER_END)==-ETIMEDOUT,"busy timeout");
    check(!m.selected && m.releases==1 && m.cmd_count==1,"completion busy error releases CS");
    check(prodock_spi.ops->claim_bus(&device)==-EIO,"busy recovery failure blocks claim");++cases;
    setup();m.trailing_stuck=1;
    check(prodock_spi.ops->xfer(&device,8,tx,rx,SPI_XFER_BEGIN|SPI_XFER_END)==-ETIMEDOUT,"trailing byte failure propagates");
    check(!m.selected && m.cmd_count==2 && m.resets==1,"trailing byte failure recovers with CS high");++cases;
    setup();check(!prodock_spi.probe(&bus),"probe");check(registers[0x40/4]==0x263,"400k configured divider");
    check(!prodock_spi.ops->set_speed(&bus,20000000) && registers[0x40/4]==0x201,"20M configured divider");
    check(prodock_spi.ops->set_speed(&bus,0)<0 && prodock_spi.ops->set_speed(&bus,1)<0,"invalid speed");
    check(registers[0x40/4]==0x201,"rejected speeds preserve divider");
    check(!prodock_spi.ops->set_mode(&bus,0) && prodock_spi.ops->set_mode(&bus,1)==-EINVAL,"mode constraints");++cases;
    setup();check(!prodock_spi.ops->claim_bus(&device),"claim bus");
    check(!m.cmd_count && !m.shifted && !m.selected,"claim keeps CS high without startup clocks");
    check(!prodock_spi.ops->release_bus(&device) && !m.cmd_count,"release also emits no clocks");
    ++cases;
    return cases;
}
int main(void)
{
    unsigned cases=0;const unsigned lengths[]={1,2,3,4,5,29,512,513};
    for(unsigned i=0;i<sizeof(lengths)/sizeof(lengths[0]);++i){basic(lengths[i],0);++cases;}
    basic(3,1);basic(513,1);basic(3,2);basic(513,2);cases+=4;
    cases+=extra();free(controller);
    printf("UBOOT SPI PASS: %u cases, separately linked wrapper and common core\n",cases);return 0;
}
