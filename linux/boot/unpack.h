/* SPDX-License-Identifier: MIT */
#ifndef PRODOCK_UNPACK_H
#define PRODOCK_UNPACK_H
#include <stdint.h>
#include <string.h>
/* Bounded zero-run transport, not an executable format. Each LE32 header
 * carries a nonzero length; bit31 means literal bytes follow. No overlap. */
static int prodock_unpack(const uint8_t *src, unsigned bytes, uint8_t *dst, unsigned size)
{
    unsigned in = 0, out = 0;
    while (in < bytes) {
        uint32_t word;
        unsigned n;
        if (bytes - in < 4) return 0;
        word = (uint32_t)src[in] | (uint32_t)src[in+1] << 8 |
               (uint32_t)src[in+2] << 16 | (uint32_t)src[in+3] << 24;
        in += 4; n = word & 0x7fffffffU;
        if (!n || n > size - out) return 0;
        if (word >> 31) {
            if (n > bytes - in) return 0;
            memcpy(dst + out, src + in, n); in += n;
        } else memset(dst + out, 0, n);
        out += n;
    }
    return out == size;
}
#endif
