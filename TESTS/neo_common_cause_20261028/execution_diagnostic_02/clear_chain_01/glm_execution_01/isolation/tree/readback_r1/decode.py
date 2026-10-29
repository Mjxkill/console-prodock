#!/usr/bin/env python3
"""Decode CPU readback separately from GPU completion; no hardware access."""
import argparse
import json
from pathlib import Path
import struct

NAMES = ['magic','version','phase','result','cache_before','cache_after','milmb',
         'old_mtvec','old_mstatus','old_mie','mcause','mtval','mepc','first_bad_address',
         'first_expected','first_actual','error_count','gpu_identity','done_before','done_after',
         'status_before','status_after','errors_before','errors_after','lost_before','lost_after',
         'rejected_before','rejected_after','last_ddr_address','words_read','reserved30','reserved31']


def decode(data):
    if len(data) != 256:
        raise ValueError('Expected exact 256B journal')
    words = list(struct.unpack('<64I', data))
    if words[:2] != [0x52423132, 1]:
        raise ValueError('Wrong readback identity/version')
    header = dict(zip(NAMES, words[:32]))
    if header['result'] >= 0x80000000:
        header['result'] -= 0x100000000
    complete = header['result'] == 1 and header['phase'] == 3 and header['words_read'] == 32
    issues = []
    if not complete:
        issues.append('readback_incomplete')
    if words[4:7] != [0, 0, 0xa0000001] or words[8]&8 or words[9]:
        issues.append('cache_ilm_interrupt_guard')
    if any(words[10:13]):
        issues.append('trap_recorded')
    if words[17] != 0x424c5432:
        issues.append('gpu_identity')
    image = words[32:]
    seed = [(0x12000000+4*i)^0xa5396c17 for i in range(32)]
    clear = seed[:8]+[0x6b4d6b4d]*8+seed[16:]
    mismatches = [i for i, (a,b) in enumerate(zip(image, clear)) if a != b]
    if complete:
        first = mismatches[0] if mismatches else None
        expected_error = [0,0,0] if first is None else [0x12000000+first*4, clear[first], image[first]]
        if words[13:16] != expected_error or words[16] != len(mismatches):
            issues.append('comparison_record_inconsistent')
        if words[28] != 0x1200007c or any(words[30:32]):
            issues.append('extent_or_reserved')
    classification = 'unobserved'
    if complete and not issues:
        classification = ('clear_exact_canaries_intact' if image == clear else
                          'seed_unchanged' if image == seed else 'other_or_partial_change')
    return {'readback_valid': complete and not issues, 'gpu_passed': False,
            'classification': classification, 'header': header, 'image': image, 'issues': issues,
            'limit': '32 sequential CPU loads, not an atomic memory snapshot. GPU completion is separately observed.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('journal', type=Path)
    args = parser.parse_args()
    result = decode(args.journal.read_bytes())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['readback_valid'] else 1)
