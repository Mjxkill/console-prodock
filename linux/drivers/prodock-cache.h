/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef PRODOCK_CACHE_H
#define PRODOCK_CACHE_H
#include <asm/sbi.h>
static inline int prodock_cache_probe(void)
{
    struct sbiret r = sbi_ecall(0x0900031e, 0x101, 0, 0, 0, 0, 0, 0);
    return r.error || r.value != 0x50444301 ? -ENODEV : 0;
}
static inline int prodock_cache_sync(void)
{
    struct sbiret r = sbi_ecall(0x0900031e, 0x100, 0, 0, 0, 0, 0, 0);
    return r.error ? -EIO : 0;
}
#endif
