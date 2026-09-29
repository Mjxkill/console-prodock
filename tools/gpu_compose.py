#!/usr/bin/env python3
"""Host composition of GPU descriptors: surfaces, tile maps and sprites.

Independent of the RTL and of the firmware reference: every pixel comes from
one direct memory lookup. `read(address, count)` returns DDR bytes and must
fail outside the memory the scene owns.
"""
import struct

W, H = 800, 480
LAYER_ENABLE, LAYER_KEY_ZERO, LAYER_TILES, LAYER_WRAP_X, LAYER_WRAP_Y = 1, 2, 4, 8, 16
TILE_INDEX, TILE_FLIP_X, TILE_FLIP_Y = 0x1fff, 0x4000, 0x8000
DDR_END = 0x40000000


def signed16(value):
    return value if value < 32768 else value - 65536


def compose_surface(indices, words, read):
    base, wh, xy, view, scroll, stride, flags, _ = words
    x, y = signed16(xy & 65535), signed16(xy >> 16)
    sw, sh = wh & 65535, wh >> 16
    vw, vh = view & 65535, view >> 16
    sx, sy = scroll & 65535, scroll >> 16
    left, right = max(0, x), min(W, x + vw, x + sw - sx)
    top, bottom = max(0, y), min(H, y + vh, y + sh - sy)
    if left >= right or top >= bottom:
        return
    if stride < sw:
        raise SystemExit('Invalid source stride')
    for yy in range(top, bottom):
        row = read(base + (sy + yy - y) * stride + sx + left - x, right - left)
        at = yy * W + left
        if flags & LAYER_KEY_ZERO:
            row = bytes(p if p else old for p, old in zip(row, indices[at:at + len(row)]))
        indices[at:at + len(row)] = row


def tile_layer_valid(words):
    """Rules of the hardware: a rejected layer is counted and not displayed."""
    code, wlog, hlog = (words[5] >> 8) & 3, words[5] & 15, (words[5] >> 4) & 15
    if code == 3 or wlog < 4 or wlog + code + 3 > 15 or hlog + code + 3 > 15:
        return False
    if (words[0] | words[1]) & 31:
        return False
    return (words[0] + (1 << (wlog + hlog + 1)) <= DDR_END
            and words[1] + (8192 << (2 * (code + 3))) <= DDR_END)


def compose_tiles(indices, words, read):
    if not tile_layer_valid(words):
        return
    base, atlas, xy, view, scroll, geometry, flags, _ = words
    shift = ((geometry >> 8) & 3) + 3
    size, wlog = 1 << shift, geometry & 15
    wpx, hpx = size << wlog, size << ((geometry >> 4) & 15)
    x, y = signed16(xy & 65535), signed16(xy >> 16)
    vw, vh = view & 65535, view >> 16
    sx, sy = scroll & 65535, scroll >> 16
    for yy in range(max(0, y), min(H, y + vh)):
        my = sy + yy - y
        if flags & LAYER_WRAP_Y:
            my %= hpx
        elif my >= hpx:
            break
        for xx in range(max(0, x), min(W, x + vw)):
            mx = sx + xx - x
            if flags & LAYER_WRAP_X:
                mx %= wpx
            elif mx >= wpx:
                break
            entry, = struct.unpack('<H', read(base + (((my >> shift) << wlog) + (mx >> shift)) * 2, 2))
            tx, ty = mx % size, my % size
            if entry & TILE_FLIP_X:
                tx = size - 1 - tx
            if entry & TILE_FLIP_Y:
                ty = size - 1 - ty
            value = read(atlas + (entry & TILE_INDEX) * size * size + ty * size + tx, 1)[0]
            if value or not flags & LAYER_KEY_ZERO:
                indices[yy * W + xx] = value


def compose_sprites(indices, sprites, layer, read):
    for base, xy, prop, _ in sprites:
        if not prop & 65536 or (prop >> 20) & 15 != layer:
            continue
        x, y = signed16(xy & 65535), signed16(xy >> 16)
        width, height = prop & 255, (prop >> 8) & 255
        for yy in range(max(0, y), min(H, y + height)):
            for xx in range(max(0, x), min(W, x + width)):
                sx = width - 1 - (xx - x) if prop & 131072 else xx - x
                sy = height - 1 - (yy - y) if prop & 262144 else yy - y
                value = read(base + sy * 32 + sx, 1)[0]
                if value:
                    indices[yy * W + xx] = value


def compose(layers, sprites, read):
    """layers: 16 tuples of 8 words; sprites: 64 tuples of 4 words, or None."""
    indices = bytearray(W * H)
    for number, words in enumerate(layers):
        if words[6] & LAYER_ENABLE:
            (compose_tiles if words[6] & LAYER_TILES else compose_surface)(indices, words, read)
        if sprites is not None:
            compose_sprites(indices, sprites, number, read)
    return indices


def frame_hash(indices):
    """Ordered hash of register 0x020 in layer mode."""
    rotate = lambda v, n: ((v << (n & 31)) | (v >> ((32 - n) & 31))) & 0xffffffff
    checksum = 0
    for offset in range(0, len(indices), 32):
        block = 0
        for i, word in enumerate(struct.unpack_from('<8I', indices, offset)):
            block ^= rotate(word, i * 4)
        checksum = rotate(checksum, 5) ^ block
    return checksum


def palette_rgb(raw):
    """256 RGB666 palette words to the 8-bit components of a PNG palette."""
    colors = []
    for (rgb,) in struct.iter_unpack('<I', raw):
        colors.extend((((rgb >> shift) & 63) * 255 + 31) // 63 for shift in (12, 6, 0))
    return colors
