/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef PRODOCK_VALIDATE_H
#define PRODOCK_VALIDATE_H
#include <linux/errno.h>
#include "prodock-uapi.h"
static inline int prodock_range(__u32 base, __u64 size)
{
    return size && base >= PRODOCK_GPU_BASE && base < PRODOCK_GPU_BASE + PRODOCK_GPU_BYTES &&
        size <= (__u64)PRODOCK_GPU_BASE + PRODOCK_GPU_BYTES - base;
}
static inline int prodock_surface(__u32 base, __u32 w, __u32 h, __u32 pitch,
                                  unsigned maxw, unsigned maxh)
{
    return !(base & 31) && w && w <= maxw && h && h <= maxh &&
        !(pitch & 31) && pitch >= w * 2 && pitch <= 65535 && prodock_range(base, (__u64)h * pitch);
}
/* Exactly the G3D1 fixed-point divider limit: floor((pixels << 32) / focal)
 * must be <= 8 * 65536. Cross multiplication avoids a 64-bit division on RV32.
 */
static inline int prodock_geom_slope(__u32 pixels, __u32 focal)
{
    return ((__u64)pixels << 32) < (__u64)focal * 524289U;
}
static inline int prodock_geometry_command(const __u32 *c)
{
    unsigned w, h, x, y, vertices, faces;
    if (c[0] & 0x00ffffffU) return -EINVAL;
    switch (c[0] >> 24) {
    case PRODOCK_GEOM_MATRIX:
        if (c[1] > 2 || c[6] || c[7]) return -EINVAL;
        /* Every signed Q16.16 coefficient bit pattern is representable. */
        return 0;
    case PRODOCK_GEOM_CAMERA:
        if (c[7]) return -EINVAL;
        w = c[6] >> 16; h = c[6] & 65535;
        x = c[5] >> 16; y = c[5] & 65535;
        if ((__s32)c[1] < 4096 || (__s32)c[2] <= (__s32)c[1] ||
            (__s32)c[3] < 65536 || (__s32)c[4] < 65536 ||
            c[3] > 0x10000000U || c[4] > 0x10000000U ||
            !w || w > 1024 || !h || h > 512 || x > w || y > h)
            return -ERANGE;
        if (!prodock_geom_slope(x, c[3]) || !prodock_geom_slope(w - x, c[3]) ||
            !prodock_geom_slope(y, c[4]) || !prodock_geom_slope(h - y, c[4]))
            return -ERANGE;
        /* Matching the last TARGET and invalidation on TARGET are checked
         * by the FPGA, including across batches. CAMERA must follow TARGET. */
        return 0;
    case PRODOCK_GEOM_LIGHT:
        if (c[2] >> 16 || c[4] || c[5] || c[6] || c[7]) return -EINVAL;
        return (c[3] & 65535) <= 256 && (c[3] >> 16) <= 256 ? 0 : -ERANGE;
    case PRODOCK_GEOM_DRAW:
        if (c[4] > 1 || c[5] || c[6] || c[7]) return -EINVAL;
        vertices = c[3] >> 16; faces = c[3] & 65535;
        if ((c[1] & 31) || (c[2] & 31) || !vertices ||
            vertices > PRODOCK_GEOM_MAX_VERTICES || !faces ||
            !prodock_range(c[1], (__u64)vertices * 32) ||
            !prodock_range(c[2], (__u64)faces * 32)) return -ERANGE;
        return 0;
    default: return -EINVAL;
    }
}
static inline int prodock_command(const __u32 *c)
{
    unsigned op = c[0] >> 24, w, h, p, z;
    if (op >= PRODOCK_GEOM_MATRIX) return prodock_geometry_command(c);
    if (!op) return -EINVAL;
    if (op == 22) {
        w = c[3] >> 16; h = c[3] & 65535; p = c[4] >> 16; z = c[4] & 65535;
        if (!prodock_surface(c[1], w, h, p, 1024, 512) ||
            !prodock_surface(c[2], w, h, z, 1024, 512) ||
            ((__u64)c[1] < (__u64)c[2] + h * z && (__u64)c[2] < (__u64)c[1] + h * p)) return -ERANGE;
    }
    if (op == 24 && !prodock_surface(c[1], c[2] >> 16, c[2] & 65535,
                                    c[3] & 65535, 512, 512)) return -ERANGE;
    if (op == 29 && !prodock_surface(c[1], c[2] >> 16, c[2] & 65535,
                                    c[3], 1024, 512)) return -ERANGE;
    return 0;
}
static inline int prodock_scene_valid_for(const struct prodock_scene *s, unsigned width, unsigned height)
{
    unsigned i, w, h, bpp;
    if (!((width == 800 && height == 480) || (width == 1280 && height == 720))) return -EINVAL;
    if (s->format != 1 && s->format != 3 && s->format != 7) return -EINVAL;
    if (s->layers_enabled > 1 || s->sprites_enabled > 1 || s->reserved[0] || s->reserved[1] || s->reserved[2]) return -EINVAL;
    w = s->format == 7 ? width / 2 : width; h = s->format == 7 ? height / 2 : height;
    bpp = s->format == 1 ? 1 : 2;
    if ((s->base & 31) || (s->stride & 31) || s->stride < w * bpp || s->stride > 65535 ||
        (s->format == 1 && s->stride != width) || !prodock_range(s->base, (__u64)s->stride * h)) return -ERANGE;
    for (i = 0; i < 16; ++i) {
        const __u32 *l = s->layers[i];
        if (!s->layers_enabled || !(l[6] & 1)) continue;
        if ((l[0] & 31) || l[7] || (l[6] & ~31U)) return -EINVAL;
        if (l[6] & 4) {
            unsigned x = l[5] & 15, y = (l[5] >> 4) & 15, code = (l[5] >> 8) & 3;
            if (x < 4 || code == 3 || x + code > 12 || y + code > 12 || (l[5] & ~1023U) ||
                (l[1] & 31) || !prodock_range(l[0], 2ULL << (x + y)) ||
                !prodock_range(l[1], 8192ULL << (6 + 2 * code))) return -ERANGE;
        } else {
            w = l[1] & 65535; h = l[1] >> 16;
            if (!w || !h || (l[5] & ~65535U) || l[5] < w ||
                !prodock_range(l[0], (__u64)h * l[5])) return -ERANGE;
        }
    }
    for (i = 0; i < 64; ++i) {
        const __u32 *p = s->sprites[i];
        if (!s->sprites_enabled || !(p[2] & (1U << 16))) continue;
        w = p[2] & 255; h = (p[2] >> 8) & 255;
        if ((p[0] & 31) || !w || w > 32 || !h || h > 32 || p[3] ||
            (p[2] & ~0x00f7ffffU) || !prodock_range(p[0], h * 32U)) return -ERANGE;
    }
    return 0;
}
static inline int prodock_scene_valid(const struct prodock_scene *s)
{
    return prodock_scene_valid_for(s, 800, 480);
}
#endif
