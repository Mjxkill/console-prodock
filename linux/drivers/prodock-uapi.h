/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef PRODOCK_UAPI_H
#define PRODOCK_UAPI_H
#include <linux/types.h>
#include <linux/ioctl.h>
#define PRODOCK_ABI 1
#define PRODOCK_GPU_BASE 0x00800000U
#define PRODOCK_GPU_BYTES 0x05600000U
/* Last 2 MiB belong to the display manager (fonts and double-buffered maps). */
#define PRODOCK_RESERVED_BYTES 0x05800000U
#define PRODOCK_BATCH_MAX 64
struct prodock_info {
    __u32 abi, memory_base, memory_bytes, width, height, caps;
    __u32 done, errors, underflows, frames, checksum, faulted;
};
struct prodock_batch { __u32 count, reserved; __u32 commands[PRODOCK_BATCH_MAX][8]; };
struct prodock_scene {
    __u32 base, stride, format, layers_enabled, sprites_enabled, reserved[3];
    __u32 layers[16][8], sprites[64][4];
};
struct prodock_palette { __u32 rgb[256]; };
struct prodock_font { __u8 bytes[4096]; };
#define PRODOCK_INFO _IOR('P', 0, struct prodock_info)
#define PRODOCK_SUBMIT _IOW('P', 1, struct prodock_batch)
#define PRODOCK_PRESENT _IOW('P', 2, struct prodock_scene)
#define PRODOCK_PALETTE _IOW('P', 3, struct prodock_palette)
#define PRODOCK_FONT _IOW('P', 4, struct prodock_font)

/* Independent from exclusive accelerator ownership: usable while a game runs. */
#define PRODOCK_SPLIT 0U
#define PRODOCK_GAME 1U
#define PRODOCK_TERMINAL 2U
struct prodock_layout { __u32 mode, reserved[3]; };
struct prodock_display_info {
    __u32 mode, columns, rows, text_updates, game_presents;
    __u32 sent_lo, sent_hi, frames, done, errors, underflows;
    __u32 line_cycles, invalid_layers, invalid_sprites, usb_status, faulted, checksum;
    __u32 feed_us, wait_us, cache_us, present_us, text_us;
};
struct prodock_debug_text { __u16 cells[100 * 15]; };
#define PRODOCK_LAYOUT _IOW('D', 0, struct prodock_layout)
#define PRODOCK_DISPLAY_INFO _IOR('D', 1, struct prodock_display_info)
#define PRODOCK_DEBUG_TEXT _IOW('D', 2, struct prodock_debug_text)
#endif
