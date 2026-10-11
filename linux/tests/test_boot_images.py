#!/usr/bin/env python3
"""Le vrai décodeur C rejette corruption, mauvaise cible et débordements."""
import ctypes as c
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zlib
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from sd_package import wrap, LAYOUT


class Image(c.Structure):
    _fields_ = [(n, c.c_uint32) for n in ['kind', 'load', 'entry', 'size', 'crc']]


with tempfile.TemporaryDirectory(prefix='prodock-images-') as directory:
    so = Path(directory) / 'image.so'
    subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                    str(HERE / 'boot/image.c'), '-o', str(so)], check=True)
    lib = c.CDLL(str(so))
    lib.pd_header.argtypes = [c.c_char_p, c.c_uint32, c.c_uint32, c.POINTER(Image)]
    lib.pd_crc.argtypes = [c.c_char_p, c.c_uint32]; lib.pd_crc.restype = c.c_uint32
    def check(data, kind, valid, size=None):
        out = Image()
        result = lib.pd_header(data, len(data) if size is None else size, kind, c.byref(out))
        if (result == 0) != valid: raise RuntimeError((kind, result, data[:40]))
        return out
    payload = bytes(range(256)) * 17
    if lib.pd_crc(payload, len(payload)) != zlib.crc32(payload): raise RuntimeError('CRC incompatible')
    for kind in LAYOUT:
        data = wrap(payload, kind)
        im = check(data, kind, True)
        if (im.load, im.entry, im.size, im.crc) != (*LAYOUT[kind][:2], len(payload), zlib.crc32(payload)):
            raise RuntimeError('Champs incorrects')
        for off in range(40):
            bad = bytearray(data); bad[off] ^= 1
            check(bytes(bad), kind, False)
        for size in [0, 39, len(data)-1, len(data)+1, 0xffffffff]: check(data, kind, False, size)
        for other in range(8):
            if other != kind: check(data, other, False)
        for field, value in [(8, 2), (16, 0xfffffff0), (20, 0xa0010000),
                             (24, 0), (24, 0xffffffff), (32, 0x3ff)]:
            bad = bytearray(data)
            struct.pack_into('<I', bad, field, value)
            struct.pack_into('<I', bad, 36, zlib.crc32(bad[:36]))
            check(bytes(bad), kind, False)
print('PASS: six types, CRC, en-têtes corrompus, cibles, tailles et débordements')
