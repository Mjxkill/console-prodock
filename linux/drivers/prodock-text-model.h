/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef PRODOCK_TEXT_MODEL_H
#define PRODOCK_TEXT_MODEL_H
#include "prodock-uapi.h"
#define PD_TEXT_BASE (PRODOCK_GPU_BASE + PRODOCK_GPU_BYTES)
#define PD_ATLAS_BYTES (8192 * 64)
#define PD_MAP_BYTES (128 * 64 * 2)
#define PD_MAP_OFFSET 0x100000U
#define PD_MAP_BANK_BYTES (4 * PD_MAP_BYTES)
static inline __u16 pd_text_cell(__u16 cell, int cursor)
{
    if (cursor) cell = (cell & 255) | ((cell & 0x0f00) << 4) | ((cell & 0xf000) >> 4);
    if (!(cell & 255)) cell |= 32;
    return cell;
}
static inline __u32 pd_text_pair(__u16 a, __u16 b, unsigned half, unsigned front)
{
    unsigned lo,hi;
    if (front) {
        lo = ((a >> 8) & 15) * 512 + (a & 255) * 2 + half;
        hi = ((b >> 8) & 15) * 512 + (b & 255) * 2 + half;
    } else { lo = (a >> 12) * 512 + half; hi = (b >> 12) * 512 + half; }
    return lo | (hi << 16);
}
/* 256 glyphs, two 8x8 halves, 16 foreground colours. Index zero is
 * transparent; palette 240..255 is owned by the terminal. Glyph 0 is solid
 * and supplies the independent background plane, including black. */
static inline void pd_text_atlas(__u8 *atlas, const __u8 *font)
{
    unsigned c, ch, y, x;
    for (c = 0; c < 16; ++c)
        for (ch = 0; ch < 256; ++ch)
            for (y = 0; y < 16; ++y)
                for (x = 0; x < 8; ++x)
                    atlas[c * 32768 + ch * 128 + y * 8 + x] =
                        !ch || (font[ch * 16 + y] & (128 >> x)) ? 240 + c : 0;
}
static inline void pd_text_map_sized(__u16 *back, __u16 *front, const __u16 *cells,
                               unsigned columns, unsigned rows, int cursor,
                               unsigned stride, unsigned map_width, unsigned map_height)
{
    unsigned y, x, half;
    for (y = 0; y < map_height; ++y)
        for (x = 0; x < map_width; ++x) {
            back[y * map_width + x] = 0;
            front[y * map_width + x] = 32 * 2;
        }
    for (y = 0; y < rows; ++y)
        for (x = 0; x < columns; ++x) {
            __u16 cell = cells[y * stride + x];
            unsigned ch = cell & 255, fg = (cell >> 8) & 15, bg = cell >> 12;
            if ((int)(y * stride + x) == cursor) { unsigned swap = fg; fg = bg; bg = swap; }
            if (!ch) ch = 32;
            for (half = 0; half < 2; ++half) {
                back[(y * 2 + half) * map_width + x] = bg * 512 + half;
                front[(y * 2 + half) * map_width + x] = fg * 512 + ch * 2 + half;
            }
        }
}
static inline void pd_text_layer_sized(__u32 *l, unsigned map_bank, unsigned plane,
                                  unsigned atlas_bank, unsigned x, unsigned y,
                                  unsigned width, unsigned height, unsigned map_w_log2, unsigned map_h_log2)
{
    unsigned map_bytes = 2U << (map_w_log2 + map_h_log2);
    l[0] = PD_TEXT_BASE + PD_MAP_OFFSET + (map_bank * 4 + plane) * map_bytes;
    l[1] = PD_TEXT_BASE + atlas_bank * PD_ATLAS_BYTES;
    l[2] = (y << 16) | x; l[3] = (height << 16) | width;
    l[4] = 0; l[5] = map_w_log2 | (map_h_log2 << 4); /* 128 x 64 tiles, 8x8 */
    l[6] = 5 | ((plane & 1) ? 2 : 0); l[7] = 0;
}
/* Legacy helpers retain their original 800x480 geometry for existing clients. */
static inline void pd_text_map(__u16 *back, __u16 *front, const __u16 *cells,
                               unsigned columns, unsigned rows, int cursor)
{
    pd_text_map_sized(back, front, cells, columns, rows, cursor, 100, 128, 64);
}
static inline void pd_text_layer(__u32 *l, unsigned bank, unsigned plane, unsigned atlas,
                                  unsigned x, unsigned y, unsigned width, unsigned height)
{
    pd_text_layer_sized(l, bank, plane, atlas, x, y, width, height, 7, 6);
}
#endif
