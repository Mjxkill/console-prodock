// SPDX-License-Identifier: MIT
/* Downloaded in ILM after the payload; verifies it before entering OpenSBI. */
#include <stdio.h>
#include <stdint.h>
#include "ae350.h"
#include "cache.h"
#include "payload.h"
#ifdef PAYLOAD_RLE_STAGE
#include "unpack.h"
#endif
static uint32_t crc32(const volatile uint8_t *p, unsigned n)
{
    uint32_t crc = ~0U;
    while (n--) {
        crc ^= *p++;
        for (unsigned i = 0; i < 8; ++i) crc = (crc >> 1) ^ (0xedb88320U & (0U - (crc & 1)));
    }
    return ~crc;
}
int main(void)
{
    unsigned isa, satp, check;
    __asm__ volatile("csrwi mie,0\ncsrci mstatus,8" ::: "memory");
    const unsigned div = (80000000U + 8U * 115200) / (16U * 115200);
    AE350_UART2->LCR = 0x83; AE350_UART2->DLL = div & 255;
    AE350_UART2->DLM = div >> 8; AE350_UART2->LCR = 3; AE350_UART2->FCR = 7;
    puts("PRODOCK LINUX: verification image DDR");
    __asm__ volatile("csrr %0,misa" : "=r"(isa));
    if (!(isa & (1U << 18))) { puts("LINUX FAIL supervisor absent"); for (;;) {} }
    __asm__ volatile("csrr %0,0x180" : "=r"(satp));
    __asm__ volatile("csrw 0x180,%0" :: "r"(0x80000000U) : "memory");
    __asm__ volatile("csrr %0,0x180" : "=r"(check));
    __asm__ volatile("csrw 0x180,%0" :: "r"(satp) : "memory");
    __asm__ volatile(".word 0x12000073" ::: "memory");
    if (!(check & 0x80000000U)) { puts("LINUX FAIL Sv32 absent"); for (;;) {} }
    ae350_dcache_flush_all();
#ifdef PAYLOAD_RLE_STAGE
    _Static_assert(PAYLOAD_BYTES <= 0x02000000, "Decoded payload too large");
    _Static_assert(PAYLOAD_LOAD + PAYLOAD_BYTES <= 0x10000000, "RLE buffers overlap");
    puts("PRODOCK LINUX: expansion transport JTAG compact");
    if (crc32((const volatile uint8_t *)0x10000000, PAYLOAD_RLE_BYTES) != PAYLOAD_RLE_CRC ||
        !prodock_unpack((const uint8_t *)0x10000000, PAYLOAD_RLE_BYTES,
                         (uint8_t *)PAYLOAD_LOAD, PAYLOAD_BYTES)) {
        puts("LINUX FAIL compact transport"); for (;;) {}
    }
    ae350_dcache_flush_all();
#endif
#ifdef PAYLOAD_USB_STAGE
    /* USB writes the 32 MiB volatile disk at 128 MiB, never the SD.
     * Destination is LOWER than source: copying forward is overlap-safe.
     * Strict RV32 kernel W^X alignment makes the payload larger than 16 MiB. */
    _Static_assert(PAYLOAD_BYTES <= 0x02000000, "USB staging overflow");
    _Static_assert(PAYLOAD_LOAD < 0x08000000, "Forward copy requires lower destination");
    puts("PRODOCK LINUX: copie depuis le disque DDR USB");
    for (unsigned i=0; i<PAYLOAD_BYTES; ++i)
        ((volatile uint8_t *)PAYLOAD_LOAD)[i] = ((const volatile uint8_t *)0x08000000)[i];
    ae350_dcache_flush_all();
#endif
    if (crc32((const volatile uint8_t *)PAYLOAD_LOAD, PAYLOAD_BYTES) != PAYLOAD_CRC) {
        puts("LINUX FAIL payload CRC"); for (;;) {}
    }
    puts("PRODOCK LINUX: CRC OK, lancement OpenSBI");
    while (!(AE350_UART2->LSR & 0x40)) {}
    ae350_dcache_flush_all();
    /* Cold DDR atomics also need the OpenSBI/kernel/libc workarounds. */
    set_csr(NDS_MCACHE_CTL, 3);
    ae350_icache_invalidate_all();
    __asm__ volatile("fence iorw,iorw\n.word 0x0000100f\nli a0,0\nli a1,0\njr %0"
                     :: "r"(PAYLOAD_LOAD) : "a0", "a1", "memory");
    __builtin_unreachable();
}
