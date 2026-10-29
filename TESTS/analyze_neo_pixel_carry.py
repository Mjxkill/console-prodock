#!/usr/bin/env python3
"""Compare observed pixels with explicit missing-CHUNK-clear hypotheses.

This models the mask, color buffer and perspective selector, not the FPGA implementation.
Pixel colors come from the independently RTL-checked reference. An exact
match identifies an observable failure mode, not its physical cause.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
from test_gpu_v1 import Model, signed16
from test_gpu_accel import triangle_pixels


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vectors', type=Path, required=True)
    p.add_argument('--board', type=Path, required=True)
    p.add_argument('--order', nargs='+', required=True,
                   help='Actual execution order since FPGA reset; rectangles do not change these buffers')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    states = {(mask, data, selector): dict(active=set(), buffer=bytearray(32), selector=0)
              for mask in (False, True) for data in (False, True) for selector in (False, True)}
    results = {}
    inputs = {}
    for name in a.order:
        source, board = a.vectors/name, a.board/name
        words = [int(w, 16) for w in (source/'commands.hex').read_text().split()]
        if words[-8] != 27 << 24 or any(words[i] >> 24 in (27, 29, 34)
                                       for i in range(0, len(words)-8, 8)):
            raise ValueError('Need exactly one final raw triangle')
        m = Model()
        m.memory[:] = bytes.fromhex((source/'initial.hex').read_text())
        for i in range(0, len(words)-8, 8):
            m.apply(words[i:i+8])
        expected = bytes.fromhex((source/'expected.hex').read_text())
        actual = (board/'actual_0.bin').read_bytes()
        points = [(signed16(w >> 16), signed16(w)) for w in words[-7:-4]]
        pixels = list(triangle_pixels(*sum(([x, y] for x, y in points), []),
                                      width=m.width, height=m.height))
        if m.clip != (0, 0, m.width, m.height) or m.base != 0x800000 or m.stride % 32:
            raise ValueError('This small model requires an unclipped aligned surface')
        outcomes = {}
        for (clear_mask, clear_data, clear_selector), state in states.items():
            active, buf = state['active'], state['buffer']
            memory = bytearray(m.memory)
            for (y, chunk), group in itertools.groupby(pixels, lambda xy: (xy[1], xy[0]//16)):
                group = list(group)
                if clear_mask:
                    active.clear()
                if clear_data:
                    buf[:] = bytes(32)
                if clear_selector:
                    state['selector'] = 0
                offset = y*m.stride+chunk*32
                flags, alpha = m.mat[:2]
                needs_background = alpha != 256 or flags & 32 or (flags & 1 and m.tex[4])
                if needs_background:
                    buf[:] = memory[offset:offset+32]
                samples = list(group)
                if flags & 16:
                    # Restricted constant-Q diagnostic. Both dividers start at
                    # CHUNK with samples x and x+1. Selecting divider 1 first
                    # swaps those samples. PIX_ADDR then prepares x+2 in the
                    # consumed divider, so subsequent samples are in order.
                    if m.planes[2] != (65536, 0, 0):
                        raise ValueError('Selector model requires constant Q=65536')
                    if state['selector']:
                        if len(samples) < 2:
                            raise ValueError('Single-pixel stale divider is outside this model')
                        samples[:2] = reversed(samples[:2])
                for (x, _), (sample_x, _) in zip(group, samples):
                    lane = x % 16
                    active.add(lane)
                    at = y*m.stride+sample_x*2
                    buf[lane*2:lane*2+2] = expected[at:at+2]
                    state['selector'] ^= 1
                for lane in active:
                    memory[offset+lane*2:offset+lane*2+2] = buf[lane*2:lane*2+2]
            if clear_mask and clear_data and clear_selector and memory != expected:
                # Depth writes are outside this color-only model.
                if memory[:1 << 20] != expected[:1 << 20]:
                    raise ValueError('Correct block model disagrees with the independent color oracle')
            outcomes[f'clear_mask_{int(clear_mask)}_data_{int(clear_data)}_selector_{int(clear_selector)}'] = {
                'mismatch_bytes_to_board': sum(x != y for x, y in zip(memory, actual)),
                'mismatch_bytes_to_oracle': sum(x != y for x, y in zip(memory[:len(actual)], expected)),
                'bytes_compared': len(actual),
                'predicted_sha256': hashlib.sha256(memory[:len(actual)]).hexdigest()}
        results[name] = outcomes
        inputs[name] = {str(path): sha(path) for path in
                       (source/'commands.hex', source/'initial.hex', source/'expected.hex',
                        source/'result.json', board/'actual_0.bin', board/'result.json')}
    report = dict(scope=__doc__, execution_order=a.order, results=results, inputs=inputs,
                  script_sha256=sha(Path(__file__)))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
