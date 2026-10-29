#!/usr/bin/env python3
"""Read the published bit-sliced fabric ROM from a Gowin post-route VO.

This checks the netlist initialization, not FPGA configuration memory on a
physical board. The supported layout is deliberately narrow: 32 SP primitives,
each 16K x 1, direct ILMADDR[15:2], one direct ILMRDATA output bit. Unsupported
layouts fail instead of guessing lane ordering or interpreting encrypted data.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decode(text):
    """Return 64 KiB in CPU byte order, plus checked primitive metadata.

    The official gw5a SP model initializes ram_MEM as INIT_RAM_3F through
    INIT_RAM_00, with omitted INIT parameters defaulting to zero. BIT_WIDTH=1
    reads ram_MEM[AD], so address k in each slice is bit k of that concatenation.
    """
    params = {}
    pattern = r'^defparam (\\\S+/u_vc_ilm_ram/\S+)\s*\.(\w+)\s*=\s*(.*?);'
    for m in re.finditer(pattern, text, re.M):
        key = (m[1], m[2])
        if key in params:
            raise ValueError('Duplicate ROM parameter: ' + repr(key))
        if key[1].startswith('INIT_RAM_') and not re.fullmatch(r'INIT_RAM_[0-3][0-9A-F]', key[1]):
            raise ValueError('Unsupported ROM INIT block: ' + repr(key))
        params[key] = m[3]
    cells = {}
    pattern = r'^SP (\\\S+/u_vc_ilm_ram/\S+)\s*\((.*?)\);'
    for m in re.finditer(pattern, text, re.M | re.S):
        name = m[1]
        pairs = re.findall(r'\.(\w+)\(([^()]*)\)', m[2])
        ports = dict(pairs)
        if len(ports) != len(pairs):
            raise ValueError('Duplicate ROM port: ' + name)
        compact = {k: re.sub(r'\s+', '', v) for k, v in ports.items()}
        width = params.get((name, 'BIT_WIDTH'))
        if width != '1':
            raise ValueError('Unsupported ROM width for ' + name)
        if not re.fullmatch(r'\{\\\S+/ILMADDR\[15:2\]\}', compact.get('AD', '')):
            raise ValueError('ROM address mapping differs: ' + name)
        output = re.fullmatch(
            r'\{\\\S+/DO(?:_\d+)?\[31:1\],\\\S+/ILMRDATA\[(\d+)\]\}',
            compact.get('DO', ''))
        if not output:
            raise ValueError('ROM output mapping differs: ' + name)
        bit = int(output[1])
        if bit not in range(32) or bit in cells:
            raise ValueError('Duplicate or out-of-range ROM output bit')
        if compact.get('BLKSEL') != '{GND,GND,GND}':
            raise ValueError('Unsupported ROM bank selector')
        if params.get((name, 'BLK_SEL')) != "3'b000":
            raise ValueError('Unsupported ROM bank parameter')
        chunks = []
        for chunk in range(64):
            value = params.get((name, f'INIT_RAM_{chunk:02X}'), "256'h0")
            match = re.fullmatch(r"256'h([0-9a-fA-F]{1,64})", value)
            if not match:
                raise ValueError('Unknown ROM initialization: ' + name)
            chunks.append(int(match[1], 16))
        cells[bit] = dict(instance=name, chunks=chunks)
    if sorted(cells) != list(range(32)):
        raise ValueError('Expected exactly 32 distinct ROM output bits')
    image = bytearray(65536)
    for bit, cell in cells.items():
        for chunk, value in enumerate(cell['chunks']):
            for index in range(256):
                if (value >> index) & 1:
                    image[(chunk * 256 + index) * 4 + bit // 8] |= 1 << (bit % 8)
    details = [dict(output_bit=bit, instance=cells[bit]['instance']) for bit in range(32)]
    return bytes(image), details


def compare(image, binary):
    """Check exactly the payload extent; report padding separately, never hide it."""
    if not binary or len(binary) > len(image):
        raise ValueError('Expected binary must fit the 64 KiB ROM and be nonempty')
    differences = [i for i, (a, b) in enumerate(zip(image, binary)) if a != b]
    return dict(
        passed=not differences, payload_bytes=len(binary),
        expected_sha256=sha(binary), observed_payload_sha256=sha(image[:len(binary)]),
        full_rom_sha256=sha(image), differing_payload_bytes=len(differences),
        first_difference=(dict(offset=differences[0],
                               byte_address=f'0x{0x80000000 + differences[0]:08x}',
                               expected=binary[differences[0]], observed=image[differences[0]])
                          if differences else None),
        padding_bytes=len(image)-len(binary),
        padding_nonzero_bytes=sum(x != 0 for x in image[len(binary):]),
        hardware_validated=False, qualification='POST_ROUTE_VO_ROM_INITIALIZATION_ONLY')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vo', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    vo = args.vo.read_bytes()
    binary = args.binary.read_bytes()
    image, cells = decode(vo.decode())
    result = compare(image, binary)
    result.update(schema=1, inputs={str(args.vo): sha(vo), str(args.binary): sha(binary)},
                  decoder_sha256=sha(Path(__file__).read_bytes()), cells=cells)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'rom_65536.bin').write_bytes(image)
    (args.out / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('cells', 'inputs')}, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
