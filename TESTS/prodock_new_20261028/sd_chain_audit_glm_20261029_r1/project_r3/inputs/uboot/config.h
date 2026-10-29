/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef PRODOCK_CONSOLE_H
#define PRODOCK_CONSOLE_H
#define CFG_SYS_SDRAM_BASE 0x06000000
#define CFG_SYS_NS16550_CLK 80000000
#define CFG_SYS_BOOTMAPSZ (64 << 20)
#define CFG_EXTRA_ENV_SETTINGS "loadaddr=0x10000000\0" \
    "bootmenu_0=Linux et pilotes Pro Dock=prodockboot linux\0" \
    "bootmenu_1=LUMA sans Linux=prodockboot luma\0" \
    "bootmenu_2=ORBITAL sans Linux=prodockboot orbital\0"
#endif
