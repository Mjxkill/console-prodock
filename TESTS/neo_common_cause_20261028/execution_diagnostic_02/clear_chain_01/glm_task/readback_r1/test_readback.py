#!/usr/bin/env python3
"""Adversarial control-flow/footprint test of the exact compiled reader bytes."""
import hashlib
import json
from pathlib import Path
import struct
from readback_model import Reader, JOURNAL, OLD, SCRATCH
from decode import decode

HERE = Path(__file__).resolve().parent


def main():
    binary = (HERE/'build_01/readback.bin').read_bytes()
    cases = []
    for scenario, kwargs, expected in [
        ('cleared', {}, 'clear_exact_canaries_intact'),
        ('unchanged', {}, 'seed_unchanged'), ('partial', {}, 'other_or_partial_change'),
        ('canary', {}, 'other_or_partial_change'), ('trap', {}, 'unobserved'),
        ('bad_prior', {}, 'unobserved'), ('cleared', {'cache': 1}, 'unobserved'),
        ('cleared', {'milmb': 0xa0010001}, 'unobserved')]:
        cpu = Reader(binary, scenario, **kwargs)
        result = cpu.run()
        assert cpu.commands == [] and cpu.gpu_writes == []
        assert all(JOURNAL <= address < JOURNAL+256 for write, address, _ in cpu.accesses if write)
        assert cpu.original_old == [cpu.word(OLD+4*i) for i in range(128)]
        decoded = decode(struct.pack('<64I', *result[:64]))
        assert decoded['classification'] == expected
        if expected != 'unobserved':
            assert cpu.ddr_reads == list(range(SCRATCH, SCRATCH+128, 4))
            assert decoded['readback_valid'] and not decoded['gpu_passed']
        elif scenario == 'trap':
            assert decoded['header']['result'] == -7 and decoded['header']['words_read'] == 7
            assert decoded['header']['mtval'] == SCRATCH+28
        else:
            assert decoded['header']['result'] == -1 and not cpu.ddr_reads
        cases.append({'scenario': scenario, 'guards': kwargs, 'instructions': cpu.steps,
                      'ddr_reads': len(cpu.ddr_reads), 'classification': decoded['classification'],
                      'result': decoded['header']['result']})
    report = {'passed': True, 'hardware_access': False, 'cases': cases,
              'binary_sha256': hashlib.sha256(binary).hexdigest(),
              'limit': 'Instruction/control-flow and address allowlist only; no physical DDR or AE350 timing.'}
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    main()
