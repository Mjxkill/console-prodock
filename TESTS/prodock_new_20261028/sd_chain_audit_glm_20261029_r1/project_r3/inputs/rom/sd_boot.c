// SPDX-License-Identifier: MIT
#include <stdio.h>
#include <stdint.h>
#include "ae350.h"
#include "cache.h"
#include "fatfs/ff.h"
#include "image.h"
static FATFS volume;
static FIL file;
static int boot(void)
{
    uint8_t header[PD_HEADER]; UINT got; struct pd_image image;
    if (f_mount(&volume, "", 1) != FR_OK || f_open(&file, "/PRODOCK/UBOOT.BIN", FA_READ) != FR_OK) return -1;
    uint32_t size = f_size(&file);
    if (f_read(&file, header, sizeof(header), &got) != FR_OK || got != sizeof(header) ||
        pd_header(header, size, PD_UBOOT, &image)) { f_close(&file); return -1; }
    printf("PRODOCK SD BOOT: U-Boot %u octets\r\n", (unsigned)image.size);
    uint8_t *dest = (uint8_t *)(uintptr_t)image.load;
    for (uint32_t off=0; off<image.size;) {
        unsigned n=image.size-off; if(n>32768)n=32768;
        if(f_read(&file,dest+off,n,&got)!=FR_OK || got!=n){f_close(&file);return -1;}
        off+=n;
    }
    f_close(&file);
    if (pd_crc(dest,image.size)!=image.crc) return -1;
    puts("PRODOCK SD BOOT: CRC OK, U-Boot");
    while (!(AE350_UART2->LSR & 0x40)) {}
    AE350_GPIO->DOUTSET=1;
    ae350_dcache_flush_all(); set_csr(NDS_MCACHE_CTL,3);
    ae350_icache_invalidate_all();
    __asm__ volatile("csrwi mie,0\ncsrci mstatus,8\nfence iorw,iorw\n.word 0x0000100f\nli a0,0\nli a1,0\njr %0"
                     ::"r"(image.entry):"a0","a1","memory");
    __builtin_unreachable();
}
int main(void)
{
    clear_csr(NDS_MSTATUS,8); write_csr(NDS_MIE,0);
    const unsigned div=(80000000U+8U*115200)/(16U*115200);
    AE350_UART2->LCR=0x83; AE350_UART2->DLL=div&255; AE350_UART2->DLM=div>>8;
    AE350_UART2->LCR=3; AE350_UART2->FCR=7;
    puts("PRODOCK SD BOOT READY /PRODOCK/UBOOT.BIN");
    if (*(volatile uint32_t *)0xe9000000 != 0x47505531 ||
        *(volatile uint32_t *)0xe9001030 != 0x1ff) {puts("SD BOOT FAIL GPU ABI");for(;;){}}
    boot();
    puts("PRODOCK SD BOOT: SD/image absente ou invalide; b pour retenter");
    for(;;) {
        if(!(AE350_UART2->LSR&1))continue;
        unsigned c=AE350_UART2->RBR;
        if(c=='b') {boot();puts("SD BOOT FAILED");}
        if(c=='?')puts("MegaPro GPU SD boot R1 core=800MHz");
        if(c=='c')puts("RASTER PAUSED");
    }
}
