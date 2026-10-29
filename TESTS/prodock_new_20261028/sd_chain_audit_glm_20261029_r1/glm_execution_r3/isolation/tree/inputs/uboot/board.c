// SPDX-License-Identifier: GPL-2.0-or-later
#include <command.h>
#include <cpu_func.h>
#include <fs.h>
#include <init.h>
#include <irq_func.h>
#include <asm/io.h>
#include <asm/csr.h>
#include <linux/string.h>
#include <u-boot/crc.h>
#include "image.h"
int board_init(void)
{
    writel(0x80000000, (void *)0xf0100050);
    return 0;
}
static int select_sd(void)
{
    if (!fs_set_blk_dev("mmc", "0:1", FS_TYPE_FAT)) return 0;
    return fs_set_blk_dev("mmc", "0:0", FS_TYPE_FAT);
}
static int image(const char *path, unsigned kind, struct pd_image *im)
{
    uint8_t *buffer = (void *)0x10000000;
    loff_t size, actual;
    if (select_sd() || fs_size(path, &size) || size < PD_HEADER || size > PD_HEADER + 0x02000000)
        return -1;
    printf("Pro Dock: lecture %s (%llu octets)\n", path, (unsigned long long)size);
    if (select_sd() || fs_read(path, (ulong)buffer, 0, size, &actual) || actual != size ||
        pd_header(buffer, size, kind, im) || crc32(0, buffer + PD_HEADER, im->size) != im->crc)
        return -1;
    memcpy((void *)(ulong)im->load, buffer + PD_HEADER, im->size);
    return 0;
}
static int do_prodockboot(struct cmd_tbl *cmdtp, int flag, int argc, char *const argv[])
{
    struct pd_image app, assets;
    bool linux_mode = argc == 2 && !strcmp(argv[1], "linux");
    if (argc != 2) return CMD_RET_USAGE;
    if (readl((void *)0xe9000000) != 0x47505531 || readl((void *)0xe9001030) != 0x1ff)
        return CMD_RET_FAILURE;
    if (linux_mode) {
        ulong old, check;
        if (!(csr_read(CSR_MISA) & BIT(18))) return CMD_RET_FAILURE;
        old = csr_read(CSR_SATP); csr_write(CSR_SATP, 0x80000000);
        check = csr_read(CSR_SATP); csr_write(CSR_SATP, old);
        asm volatile("sfence.vma" ::: "memory");
        if (!(check & 0x80000000)) return CMD_RET_FAILURE;
        if (image("/PRODOCK/LINUX.BIN", PD_LINUX, &app)) goto bad;
    } else if (!strcmp(argv[1], "luma")) {
        if (image("/PRODOCK/LUMA.DAT", PD_LUMA_ASSETS, &assets) ||
            image("/PRODOCK/LUMA.BIN", PD_LUMA, &app)) goto bad;
    } else if (!strcmp(argv[1], "orbital")) {
        if (image("/PRODOCK/ORBITAL.DAT", PD_ORBITAL_ASSETS, &assets) ||
            image("/PRODOCK/ORBITAL.BIN", PD_ORBITAL, &app)) goto bad;
    } else return CMD_RET_USAGE;
    puts("Pro Dock: image verifiee, lancement\n");
    disable_interrupts();
    writel(1, (void *)0xf0700030); /* release SD CS */
    asm volatile("csrw 0x180,zero\nsfence.vma\nfence rw,rw\nfence.i" ::: "memory");
    /* DDR atomics require cached memory on the real A25. Publish copied
     * code before the new stage fetches it, then retain enabled L1. */
    asm volatile("csrw 0x7cc,%0\nfence iorw,iorw\nfence.i\ncsrsi 0x7ca,3"
                 :: "r"(6) : "memory");
    ((void (*)(ulong, ulong))(ulong)app.entry)(0, 0);
    return CMD_RET_FAILURE;
bad:
    puts("Pro Dock: SD/image invalide; aucun repli ni saut\n");
    return CMD_RET_FAILURE;
}
U_BOOT_CMD(prodockboot, 2, 0, do_prodockboot, "Linux ou demo sans Linux",
           "linux | luma | orbital : verifier puis charger depuis /PRODOCK");
