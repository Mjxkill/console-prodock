#!/usr/bin/env python3
"""Offline analysis of retained probes; no hardware access or inferred verdict."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent
CAPTURES = ('read1.bin', 'read2.bin', 'cpu_jtag_written.bin',
            'cpu_written.bin', 'jtag_cpu_written.bin', 'ilm_read.bin')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def analyze(name):
    folder = ROOT / ('memory_gpu_cpu_' + name)
    raw = (folder / 'pattern.bin').read_bytes()
    assert len(raw) == 4096
    expected = struct.unpack('<1024I', raw)
    assert expected[:256] == (0, 0xffffffff, 0xaaaaaaaa, 0x55555555) * 64
    assert expected[256:512] == tuple(1 << i for i in range(32)) * 8
    result = dict(probe=str(folder), expected_sha256=digest(raw), captures={})
    data = {}
    for filename in CAPTURES:
        actual = (folder / filename).read_bytes()
        assert len(actual) == len(raw)
        data[filename] = actual
        words = struct.unpack('<1024I', actual)
        item = dict(sha256=digest(actual), segments={})
        for start, end, label in ((0, 1024, 'repeating_16_bytes'),
                                  (1024, 2048, 'walking_one_128_bytes'),
                                  (2048, 4096, 'pseudorandom')):
            errors = [i for i in range(start, end) if actual[i] != raw[i]]
            ids = range(start // 4, end // 4)
            events = [(i, bit) for i in ids for bit in range(32)
                      if (words[i] ^ expected[i]) >> bit & 1]
            item['segments'][label] = dict(
                offset=start, size=end-start, bad_bytes=len(errors),
                bad_byte_offset_mod16=dict(sorted(Counter(i % 16 for i in errors).items())),
                bad_words_by_phase_mod4=[sum(words[i] != expected[i] for i in ids if i % 4 == phase)
                                         for phase in range(4)],
                bit_errors=dict(sorted(Counter(bit for i, bit in events).items())),
                bit_directions=[dict(bit=bit, word_phase=phase, expected=old,
                                     actual=new, occurrences=count)
                    for (bit, phase, old, new), count in Counter(
                        (bit, i % 4, expected[i] >> bit & 1, words[i] >> bit & 1)
                        for i, bit in events).most_common(8)])
        # Explicitly tested address-pair hypotheses, restricted to random data.
        # The best source is allowed to vary by word: this is not a proof of
        # a fixed stuck address bit, and read/write fault origin is unresolved.
        ids = [i for i in range(512, 1024) if i % 4 == 2]
        aliases = []
        for byte_mask in (4, 8, 16, 32, 64, 128, 256, 512, 1024):
            other = [i ^ (byte_mask // 4) for i in ids]
            assert all(512 <= j < 1024 for j in other)
            direct = [(words[i] ^ expected[i]).bit_count() for i in ids]
            alternate = [(words[i] ^ expected[j]).bit_count() for i, j in zip(ids, other)]
            distance = [min(a, b) for a, b in zip(direct, alternate)]
            aliases.append(dict(address_xor_bytes=byte_mask, words=len(ids),
                                alternate_closer=sum(b < a for a, b in zip(direct, alternate)),
                                residual_bit_errors=sum(distance),
                                residual_histogram=dict(sorted(Counter(distance).items()))))
        item['word_phase2_address_candidates'] = sorted(aliases, key=lambda a: a['residual_bit_errors'])
        result['captures'][filename] = item
    first, second = data['read1.bin'], data['read2.bin']
    ea = {i for i in range(4096) if first[i] != raw[i]}
    eb = {i for i in range(4096) if second[i] != raw[i]}
    same_wrong = sum(first[i] == second[i] for i in ea & eb)
    varying = sum(a != b for a, b in zip(first, second))
    assert len(ea | eb) == same_wrong + varying
    result['successive_reads_same_write'] = dict(
        errors_first=len(ea), errors_second=len(eb), same_wrong_bytes=same_wrong,
        error_positions_in_both=len(ea & eb), error_positions_union=len(ea | eb),
        bytes_differing_between_reads=varying)
    if name == 'n32':
        words = struct.unpack('<1024I', first)
        result['address_pair_example'] = [
            dict(address=hex(0x12000000 + offset),
                 expected=f'0x{expected[offset // 4]:08x}',
                 read=f'0x{words[offset // 4]:08x}')
            for offset in (0x808, 0x848)]
    return result


if __name__ == '__main__':
    result = dict(scope='Retained 4096-byte captures; offline, no new writes or reloads',
                  limitations=[
                      'Only two successive JTAG reads per retained write; not an endurance distribution.',
                      'The first two regions are periodic inputs; address hypotheses use only pseudorandom data.',
                      'Bit numbers refer to reconstructed CPU words, not proven physical DDR DQ lanes.',
                      'Address-pair resemblance does not distinguish write, storage, read or transport faults.',
                      'N31 and N32 also have different adapters, netlists and routing; not a routing-only comparison.'],
                  builds={name: analyze(name) for name in ('n32', 'n31', 'n21r1b')})
    target = ROOT / 'n32_corruption_patterns.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    for name, build in result['builds'].items():
        print(name, json.dumps(build['successive_reads_same_write']))
        item = build['captures']['read1.bin']
        print('random bad words by phase:', item['segments']['pseudorandom']['bad_words_by_phase_mod4'])
        print('best address-pair hypothesis:', item['word_phase2_address_candidates'][0])
    print(target)
