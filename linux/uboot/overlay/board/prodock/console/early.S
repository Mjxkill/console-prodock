/* SPDX-License-Identifier: GPL-2.0-or-later */
.section .text
.globl harts_early_init
harts_early_init:
    csrci 0x7d0, 8
    csrsi 0x7d0, 4
    csrsi 0x7ca, 3
    ret
