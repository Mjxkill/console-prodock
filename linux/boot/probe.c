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
    printf("PRODOCK PREFLIGHT READY\r\n");
    for (;;) {
        if (!(AE350_UART2->LSR & 1)) continue;
        unsigned c = AE350_UART2->RBR;
        if (c == '?') printf("MegaPro GPU Linux preflight R1 core=800MHz\r\n");
        if (c == 'c') printf("RASTER PAUSED\r\n");
    }
}
