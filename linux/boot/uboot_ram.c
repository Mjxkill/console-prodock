// SPDX-License-Identifier: MIT
/* Volatile U-Boot qualification before installing any files on the SD. */
#include <stdio.h>
#include <stdint.h>
#include "ae350.h"
#include "cache.h"
#include "image.h"
#include "uboot_payload.h"
int main(void)
{
    clear_csr(NDS_MSTATUS,8); write_csr(NDS_MIE,0);
    const unsigned div=(80000000U+8U*115200)/(16U*115200);
    AE350_UART2->LCR=0x83; AE350_UART2->DLL=div&255; AE350_UART2->DLM=div>>8;
    AE350_UART2->LCR=3; AE350_UART2->FCR=7;
    puts("PRODOCK UBOOT RAM: verification");
    ae350_dcache_flush_all();
    if (*(volatile uint32_t *)0xe9000000 != 0x47505531 ||
        *(volatile uint32_t *)0xe9001030 != 0x1ff ||
        pd_crc((const void *)0x06000000, UBOOT_BYTES)!=UBOOT_CRC) {
        puts("PRODOCK UBOOT RAM FAIL");for(;;){}
    }
    puts("PRODOCK UBOOT RAM: CRC OK");
    while (!(AE350_UART2->LSR&0x40)) {}
    AE350_GPIO->DOUTSET=1;
    ae350_dcache_flush_all(); set_csr(NDS_MCACHE_CTL,3);
    ae350_icache_invalidate_all();
    __asm__ volatile("fence iorw,iorw\n.word 0x0000100f\nli a0,0\nli a1,0\njr %0"
                     ::"r"(0x06000000):"a0","a1","memory");
    __builtin_unreachable();
}
