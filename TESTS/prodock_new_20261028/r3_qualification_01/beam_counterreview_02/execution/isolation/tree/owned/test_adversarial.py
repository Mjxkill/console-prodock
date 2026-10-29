import sys
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import rom_check

CONTEXT = ROOT / "context"
EXPECTED = (CONTEXT / "expected.bin").read_bytes()
R3_VO = (CONTEXT / "r3_rom_cells.vo").read_text()


def _itcm(n):
    return [int(x, 16) for x in (CONTEXT / ("itcm%d" % n)).read_text().split()]


ITCMS = [_itcm(i) for i in range(4)]
P = "\\g"


def _encode(data):
    out = []
    for bit in range(32):
        chunks = [0] * 64
        for addr in range(16384):
            off = addr * 4 + bit // 8
            if off < len(data) and ((data[off] >> (bit % 8)) & 1):
                chunks[addr // 256] |= 1 << (addr % 256)
        out.append(chunks)
    return out


def build_vo(data, skip_bit=None, duplicate_output_bit=False):
    chunks = _encode(data)
    lines = []
    for bit in range(32):
        if bit == skip_bit:
            continue
        out_bit = 0 if (duplicate_output_bit and bit == 1) else bit
        inst = "%s/u_vc_ilm_ram/s%d" % (P, bit)
        ad = "{" + P + "/ILMADDR[15:2]}"
        do = "{" + P + "/DO[31:1]," + P + "/ILMRDATA[%d]}" % out_bit
        lines.append("SP %s (\n  .BLKSEL({GND,GND,GND}),\n  .AD(%s),\n  .DO(%s)\n);"
                     % (inst, ad, do))
    for bit in range(32):
        if bit == skip_bit:
            continue
        inst = "%s/u_vc_ilm_ram/s%d" % (P, bit)
        lines.append("defparam %s .BIT_WIDTH=1;" % inst)
        lines.append("defparam %s .BLK_SEL=3'b000;" % inst)
        for ch, val in enumerate(chunks[bit]):
            lines.append("defparam %s .INIT_RAM_%02X=256'h%064x;" % (inst, ch, val))
    return "\n".join(lines) + "\n"


class TestIndependentCounterReview(unittest.TestCase):
    def test_real_r3_rejected(self):
        image, details = rom_check.decode(R3_VO)
        result = rom_check.compare(image, EXPECTED)
        self.assertFalse(result["passed"])
        fd = result["first_difference"]
        self.assertEqual(fd["offset"], 41)
        self.assertEqual(fd["expected"], 34)
        self.assertEqual(fd["observed"], 162)
        self.assertEqual(result["differing_payload_bytes"], 20556)
        self.assertEqual(len(details), 32)

    def test_four_lanes_interleave(self):
        per = len(ITCMS[0])
        merged = bytes(ITCMS[lane][i] for i in range(per) for lane in range(4))
        self.assertEqual(merged, EXPECTED)

    def test_generated_fixture_accepted(self):
        data = bytes((i * 37 + 11) & 0xFF for i in range(65536))
        vo = build_vo(data)
        image, _ = rom_check.decode(vo)
        self.assertEqual(image, data)
        result = rom_check.compare(image, data)
        self.assertTrue(result["passed"])
        self.assertEqual(result["differing_payload_bytes"], 0)
        self.assertEqual(result["padding_bytes"], 0)

    def test_bit_lane_ordering_boundaries(self):
        data = bytearray(65536)
        marks = [0, 3, 4, 7, 1020, 1023, 1024, 1027, 65532, 65535]
        for idx, pos in enumerate(marks):
            data[pos] = ((idx + 1) * 17) & 0xFF
        vo = build_vo(bytes(data))
        image, _ = rom_check.decode(vo)
        self.assertEqual(image, bytes(data))

    def test_one_bit_mutation_fails(self):
        data = bytes((i * 37 + 11) & 0xFF for i in range(65536))
        mutated = bytearray(data)
        mutated[100] ^= 1
        image, _ = rom_check.decode(build_vo(bytes(mutated)))
        result = rom_check.compare(image, data)
        self.assertFalse(result["passed"])
        self.assertEqual(result["differing_payload_bytes"], 1)

    def test_unknown_ad_layout_refused(self):
        vo = build_vo(bytes(65536)).replace(
            "  .AD({" + P + "/ILMADDR[15:2]})", "  .AD({" + P + "/ADDR[15:2]})", 1)
        with self.assertRaisesRegex(ValueError, "ROM address mapping differs"):
            rom_check.decode(vo)

    def test_unknown_do_layout_refused(self):
        vo = build_vo(bytes(65536)).replace(
            "  .DO({" + P + "/DO[31:1]," + P + "/ILMRDATA[0]})",
            "  .DO({" + P + "/DO[31:0]})", 1)
        with self.assertRaisesRegex(ValueError, "ROM output mapping differs"):
            rom_check.decode(vo)

    def test_missing_output_slice_refused(self):
        with self.assertRaisesRegex(ValueError, "Expected exactly 32 distinct ROM output bits"):
            rom_check.decode(build_vo(bytes(65536), skip_bit=5))

    def test_duplicate_output_slice_refused(self):
        with self.assertRaisesRegex(ValueError, "Duplicate or out-of-range ROM output bit"):
            rom_check.decode(build_vo(bytes(65536), duplicate_output_bit=True))

    def test_wrong_bit_width_refused(self):
        vo = build_vo(bytes(65536)).replace(".BIT_WIDTH=1;", ".BIT_WIDTH=2;", 1)
        with self.assertRaisesRegex(ValueError, "Unsupported ROM width"):
            rom_check.decode(vo)

    def test_unknown_init_declaration_refused(self):
        vo = build_vo(bytes(65536)) + "defparam %s/u_vc_ilm_ram/s0 .INIT_RAM_40=256'h1;\n" % P
        with self.assertRaisesRegex(ValueError, "Unsupported ROM INIT block"):
            rom_check.decode(vo)

    def test_duplicate_init_declaration_refused(self):
        vo = build_vo(bytes(65536))
        line = [x for x in vo.splitlines() if "INIT_RAM_00" in x][0]
        vo = vo + line + "\n"
        with self.assertRaisesRegex(ValueError, "Duplicate ROM parameter"):
            rom_check.decode(vo)

    def test_duplicate_port_refused(self):
        ad = "{" + P + "/ILMADDR[15:2]}"
        vo = build_vo(bytes(65536)).replace(
            "  .AD(%s),\n  .DO(" % ad, "  .AD(%s),\n  .AD(%s),\n  .DO(" % (ad, ad), 1)
        with self.assertRaisesRegex(ValueError, "Duplicate ROM port"):
            rom_check.decode(vo)

    def test_compare_invalid_lengths(self):
        image, _ = rom_check.decode(build_vo(bytes(65536)))
        with self.assertRaises(ValueError):
            rom_check.compare(image, b"")
        with self.assertRaises(ValueError):
            rom_check.compare(image, bytes(65537))
        result = rom_check.compare(image, bytes(100))
        self.assertTrue(result["passed"])
        self.assertEqual(result["payload_bytes"], 100)
        self.assertEqual(result["padding_bytes"], 65436)

    def test_compare_distinguishes_payload_padding(self):
        data = bytearray(65536)
        data[500] = 7
        image, _ = rom_check.decode(build_vo(bytes(data)))
        result = rom_check.compare(image, bytes(data[:100]))
        self.assertTrue(result["passed"])
        self.assertGreater(result["padding_nonzero_bytes"], 0)

    def test_shared_primitive_multiple_bits_accepted(self):
        lines = []
        inst = "%s/u_vc_ilm_ram/shared" % P
        for bit in range(32):
            ad = "{" + P + "/ILMADDR[15:2]}"
            do = "{" + P + "/DO[31:1]," + P + "/ILMRDATA[%d]}" % bit
            lines.append("SP %s (\n  .BLKSEL({GND,GND,GND}),\n  .AD(%s),\n  .DO(%s)\n);"
                         % (inst, ad, do))
        lines.append("defparam %s .BIT_WIDTH=1;" % inst)
        lines.append("defparam %s .BLK_SEL=3'b000;" % inst)
        image, details = rom_check.decode("\n".join(lines) + "\n")
        self.assertTrue(all(b == 0 for b in image))
        self.assertEqual(len(set(d["instance"] for d in details)), 1)


if __name__ == "__main__":
    unittest.main()
