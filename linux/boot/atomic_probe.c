// SPDX-License-Identifier: MIT
/* Volatile ILM preflight. DDR contents and FPGA configuration stay intact. */
#include <stdio.h>
#include "ae350.h"
#include "cache.h"

static volatile unsigned probing, traps, last_cause;
static void put(unsigned c)
{
    while (!(AE350_UART2->LSR & 0x20)) {}
    AE350_UART2->THR = c;
}
long except_handler(long cause, long epc)
{
    if (probing && cause == 2) {
        ++traps;
        last_cause = (unsigned)cause;
        return epc + 4; /* All probed CSR instructions are 32 bits. */
    }
    const char *s = "\r\nPRODOCK PREFLIGHT FATAL\r\n";
    while (*s) put(*s++);
    for (;;) {}
}
static unsigned long long cycles(void)
{
    unsigned hi, lo, again;
    do {
        __asm__ volatile("rdcycleh %0" : "=r"(hi));
        __asm__ volatile("rdcycle %0" : "=r"(lo));
        __asm__ volatile("rdcycleh %0" : "=r"(again));
    } while (hi != again);
    return ((unsigned long long)hi << 32) | lo;
}
static unsigned long long timer(void)
{
    volatile unsigned *p = (volatile unsigned *)0xe6000000;
    unsigned hi, lo;
    do { hi = p[1]; lo = p[0]; } while (hi != p[1]);
    return ((unsigned long long)hi << 32) | lo;
}
int main(void)
{
    unsigned isa, satp = 0, check = 0, cache;
    clear_csr(NDS_MSTATUS, 8);
    write_csr(NDS_MIE, 0);
    const unsigned div = (80000000U + 8U * 115200) / (16U * 115200);
    AE350_UART2->LCR = 0x83;
    AE350_UART2->DLL = div & 255;
    AE350_UART2->DLM = div >> 8;
    AE350_UART2->LCR = 3;
    AE350_UART2->FCR = 7;
    printf("PRODOCK CSR cause=%08x epc=%08x tval=%08x vendor=%08x arch=%08x imp=%08x\r\n",
        read_csr(NDS_MCAUSE),read_csr(NDS_MEPC),read_csr(NDS_MTVAL),
        read_csr(NDS_MVENDORID),read_csr(NDS_MARCHID),read_csr(NDS_MIMPID));
    __asm__ volatile("csrr %0, misa" : "=r"(isa));
    __asm__ volatile("csrr %0, 0x7ca" : "=r"(cache));
    printf("PRODOCK PREFLIGHT misa=%08x supervisor=%u cache=%08x\r\n",
           isa, !!(isa & (1U << 18)), cache);
    if (isa & (1U << 18)) {
        probing = 1;
        __asm__ volatile("csrr %0, 0x180" : "+r"(satp));
        if (!traps) {
            __asm__ volatile("csrw 0x180, %0" :: "r"(0x80000000U) : "memory");
            __asm__ volatile("csrr %0, 0x180" : "+r"(check));
            __asm__ volatile("csrw 0x180, %0" :: "r"(satp) : "memory");
            __asm__ volatile(".word 0x12000073" ::: "memory"); /* sfence.vma */
        }
        probing = 0;
    }
    unsigned long long start = cycles(), tick = timer(), end;
    do { end = cycles(); } while (end - start < 80000000ULL);
    unsigned long long delta = timer() - tick;
    unsigned hz = (unsigned)(delta * 800000000ULL / (end - start));
    printf("PRODOCK PREFLIGHT satp_before=%08x satp_test=%08x sv32=%u traps=%u cause=%u plmt_hz=%u\r\n",
           satp, check, !!(check & 0x80000000U) && !traps, traps, last_cause, hz);
    unsigned misc=0, pma=0, old, result;
    probing=1;
    __asm__ volatile("csrr %0,0xfc2" : "+r"(misc));
    if(misc & (1U<<30)) __asm__ volatile("csrr %0,0xbc0" : "+r"(pma));
    probing=0;
    printf("PRODOCK ATOMIC config=%08x ppma=%u pmacfg0=%08x traps=%u\r\n",misc,!!(misc&(1U<<30)),pma,traps);
    volatile unsigned *word=(volatile unsigned *)0x07800000;
    set_csr(NDS_MCACHE_CTL,3);
    *word=0x12345678;
    printf("PRODOCK ATOMIC cached begin cache=%08x\r\n",read_csr(NDS_MCACHE_CTL));
    __asm__ volatile("amoswap.w %0,%2,(%1)" : "=r"(old) : "r"(word),"r"(0xdeadbeefU) : "memory");
    __asm__ volatile("lr.w %0,(%2)\nsc.w %1,%3,(%2)" : "=&r"(old),"=&r"(result) : "r"(word),"r"(0x11223344U) : "memory");
    printf("PRODOCK ATOMIC cached done old=%08x sc=%u value=%08x\r\n",old,result,*word);
    printf("PRODOCK ATOMIC cold begin\r\n");
    ae350_dcache_flush_all();
#ifdef PROBE_PRIME
    __asm__ volatile("lw zero,(%0)\nfence r,rw" :: "r"(word) : "memory");
#endif
    __asm__ volatile("amoswap.w %0,%2,(%1)" : "=r"(old) : "r"(word),"r"(0x55667788U) : "memory");
    printf("PRODOCK ATOMIC cold done old=%08x value=%08x\r\n",old,*word);
    word=(volatile unsigned *)0x07c40000;
    *word=0;
    printf("PRODOCK ATOMIC SBI hot begin\r\n");
    __asm__ volatile("mv a6,%1\nli a7,1\namoswap.w a6,a7,(a6)\nmv %0,a6" : "=r"(old) : "r"(word) : "a6","a7","memory");
    printf("PRODOCK ATOMIC SBI hot done old=%08x value=%08x\r\n",old,*word);
#ifdef PROBE_PRIME
    clear_csr(NDS_MMISC_CTL,8);
    set_csr(NDS_MMISC_CTL,4);
    for(unsigned i=0;i<1024;++i) {
        word=(volatile unsigned *)(0x07800000+(i*4096));
        *word=i; ae350_dcache_flush_all();
        __asm__ volatile("lw zero,(%1)\nfence r,rw\namoswap.w.aqrl %0,%2,(%1)"
                         : "=r"(old) : "r"(word),"r"(~i) : "memory");
        if(old!=i || *word!=~i) {puts("PRODOCK ATOMIC PRIME FAIL AMO");for(;;){}}
        ae350_dcache_flush_all();
        unsigned retries=1000;
        do {
            __asm__ volatile("lw zero,(%2)\nfence r,rw\nlr.w.aqrl %0,(%2)\nsc.w.aqrl %1,%3,(%2)"
                             : "=&r"(old),"=&r"(result) : "r"(word),"r"(i) : "memory");
        } while(result && --retries);
        if(!retries || old!=~i || *word!=i) {puts("PRODOCK ATOMIC PRIME FAIL LRSC");for(;;){}}
    }
    printf("PRODOCK ATOMIC PRIME PASS 1024 AMO + 1024 LRSC apres eviction\r\n");
#endif
    printf("PRODOCK PREFLIGHT READY\r\n");
    for (;;) {
        if (!(AE350_UART2->LSR & 1)) continue;
        unsigned c = AE350_UART2->RBR;
        if (c == '?') printf("MegaPro GPU Linux preflight R1 core=800MHz\r\n");
        if (c == 'c') printf("RASTER PAUSED\r\n");
    }
}
