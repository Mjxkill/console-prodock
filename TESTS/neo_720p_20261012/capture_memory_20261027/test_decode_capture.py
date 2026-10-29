#!/usr/bin/env python3
"""Exercise trace interpretation with actual mapped fault-injection outputs."""
import hashlib
import json
from pathlib import Path
import re

from decode_capture import decode

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROOF = ROOT / 'TESTS/assisted_reviews_20261026/observer_copy_01/mapped_copy_02'


def main():
    proof = json.loads((PROOF / 'result.json').read_text())
    assert proof['passed']
    expected = [
        ['COPY_WIDTH_CAPTURE_CONSISTENT'],
        ['COPY_CAPTURE_ENABLE_NOT_SEEN_AT_TRIGGER'],
        ['COPY_WIDTH_Q_DOES_NOT_MATCH_CAPTURED_D'],
        ['COPY_INPUT_WIDTH_DIFFERS'],
    ]
    results = []
    for fault in range(4):
        path = PROOF / f'fault_{fault}.log'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == proof['logs'][path.name]
        match = re.search(r'trace=([0-9a-fA-F]{16})', path.read_text())
        assert match, path
        raw = int(match[1], 16)
        report = decode(raw, 1, 16)
        assert report['findings'] == expected[fault], report
        results.append({'fault': fault, 'raw': report['raw'], 'finding': report['findings']})
    # CLEAR need not trigger COPY. All 16 sticky combinations must decode
    # independently of absent COPY samples, including SNAP-only events.
    for epoch in range(2):
        for mask in range(16):
            raw = (0xd << 60) | (mask << 56) | (epoch << 54) | (1 << 51)
            report = decode(raw, epoch)
            assert report['at_trigger'] is None and report['next_clock'] is None
            assert report['memory_event_mask'] == mask and report['findings'] == []
            assert sum(int(v) << i for i, v in enumerate(report['memory_events_seen'].values())) == mask
    for args in [(0xc2670010100d0010, 1), (0xd2e70010100d0010, 1),
                 (0xd2670010100d0010, 0), (-1, 0), (1 << 64, 0),
                 (0xd2670010100d0010, True), (0xd2670010100d0010, 1, 256)]:
        try:
            decode(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f'Invalid trace accepted: {args}')
    result = {'passed': True, 'hardware': False, 'mapped_cases': results,
              'event_combinations': 32, 'invalid_inputs_rejected': 7,
              'inputs': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (Path(__file__), HERE/'decode_capture.py', PROOF/'result.json')}}
    out = HERE/'decoder_result.json'
    assert not out.exists(), 'Keep the prior result; choose a new result version'
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
