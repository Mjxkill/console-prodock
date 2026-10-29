#!/usr/bin/env python3
"""Adversarial tests for ROM lane ordering and refusal of unknown layouts."""
import hashlib
from pathlib import Path
import re
import unittest

from rom_check import compare, decode

ROOT = Path(__file__).resolve().parents[3]
BOOT = ROOT/'tang/impl/prodock_sd_boot_20261028_r3/source/boot_firmware'
R3 = ROOT/'tang/impl/prodock_sd_boot_20261028_r3/impl/pnr/console_prodock_sd_boot_20261028_r3.vo'
G22 = ROOT/'tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.vo'


def fixture(binary):
    """Encode each CPU word's bits into independent, little-address INIT slices."""
    padded = binary + bytes(65536-len(binary))
    words = [int.from_bytes(padded[i:i+4], 'little') for i in range(0, 65536, 4)]
    lines = []
    for bit in range(32):
        name = '\\fixture/u_vc_ilm_ram/lane_' + str(bit)
        lines.append(f'''SP {name} (
 .AD({{\\fixture/ILMADDR [15:2]}}),
 .DO({{\\fixture/DO [31:1], \\fixture/ILMRDATA [{bit}]}}),
 .BLKSEL({{GND, GND, GND}}));
defparam {name} .BIT_WIDTH=1;
defparam {name} .BLK_SEL=3'b000;''')
        for chunk in range(64):
            bits = ''.join(str((word >> bit) & 1)
                           for word in reversed(words[256*chunk:256*(chunk+1)]))
            value = int(bits, 2)
            if value:
                lines.append(f"defparam {name} .INIT_RAM_{chunk:02X}=256'h{value:064X};")
    return '\n'.join(lines)


class Check(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = (BOOT/'sd_boot.bin').read_bytes()
        cls.good = fixture(cls.expected)
        cls.image, cls.cells = decode(cls.good)

    def test_expected_lanes_are_exact_binary(self):
        lanes = [bytes(int(x, 16) for x in (BOOT/'itcm'/f'itcm{i}').read_text().split())
                 for i in range(4)]
        self.assertEqual([len(x) for x in lanes], [5234]*4)
        self.assertEqual(bytes(x for word in zip(*lanes) for x in word), self.expected)
        self.assertTrue(compare(self.image, self.expected)['passed'])
        self.assertEqual(len(self.cells), 32)
        self.assertFalse(any(self.image[len(self.expected):]))

    def test_bit_and_chunk_boundaries(self):
        data = bytearray(65536)
        for index, value in [(0, 0x12345678), (1, 0xfedcba98), (255, 0x10000801),
                             (256, 0x80402010), (16383, 0x80000001)]:
            data[index*4:index*4+4] = value.to_bytes(4, 'little')
        image, _ = decode(fixture(bytes(data)))
        self.assertEqual(image, bytes(data))

    def test_real_r3_is_rejected_and_equals_old_g22(self):
        actual, _ = decode(R3.read_text())
        golden, _ = decode(G22.read_text())
        self.assertEqual(actual, golden)
        result = compare(actual, self.expected)
        self.assertFalse(result['passed'])
        self.assertEqual(result['differing_payload_bytes'], 20556)
        self.assertEqual(result['first_difference']['offset'], 41)
        self.assertEqual(hashlib.sha256(actual).hexdigest(),
                         '11e18421c8f8a729a7fc7897d0a67e89328f110551de5a06b81d2bb6fbd89195')

    def test_one_changed_payload_byte_fails(self):
        changed = bytearray(self.image)
        changed[77] ^= 4
        result = compare(changed, self.expected)
        self.assertFalse(result['passed'])
        self.assertEqual(result['differing_payload_bytes'], 1)

    def test_invalid_lengths(self):
        for binary in [b'', bytes(65537)]:
            with self.assertRaises(ValueError):
                compare(self.image, binary)

    def test_unknown_address_layout(self):
        with self.assertRaises(ValueError):
            decode(self.good.replace('ILMADDR [15:2]', 'ILMADDR [14:1]', 1))

    def test_unknown_width_or_bank(self):
        for before, after in [('BIT_WIDTH=1', 'BIT_WIDTH=2'),
                              ("BLK_SEL=3'b000", "BLK_SEL=3'b001")]:
            with self.assertRaises(ValueError):
                decode(self.good.replace(before, after, 1))

    def test_duplicate_or_unknown_output(self):
        for changed in ['ILMRDATA [1]', 'ILMRDATA [32]', 'OTHER [0]']:
            with self.assertRaises(ValueError):
                decode(self.good.replace('ILMRDATA [0]', changed, 1))

    def test_duplicate_or_unknown_init(self):
        first = re.search(r'^defparam .*INIT_RAM_00=.*;$', self.good, re.M)[0]
        with self.assertRaises(ValueError):
            decode(self.good+'\n'+first)
        with self.assertRaises(ValueError):
            decode(self.good.replace(first, first.replace("256'h", "256'hx", 1), 1))

    def test_missing_slice(self):
        changed = re.sub(r'^SP .*lane_31\s*\(.*?\);', '', self.good,
                         count=1, flags=re.M | re.S)
        with self.assertRaises(ValueError):
            decode(changed)

    def test_unknown_init_block_and_duplicate_port(self):
        first = re.search(r'^defparam .*INIT_RAM_00=.*;$', self.good, re.M)[0]
        with self.assertRaises(ValueError):
            decode(self.good+'\n'+first.replace('INIT_RAM_00', 'INIT_RAM_40'))
        with self.assertRaises(ValueError):
            decode(self.good.replace('.BLKSEL({GND, GND, GND})',
                                     '.BLKSEL({GND, GND, GND}),.BLKSEL({GND, GND, GND})', 1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
