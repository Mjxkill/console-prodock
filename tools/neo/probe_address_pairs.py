#!/usr/bin/env python3
"""Test address coupling on a stopped Neo diagnostic, in 4 KiB of scratch DDR."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from load_linux import recovery_commands

ROOT = Path(__file__).resolve().parents[2]
BASE = 0x12000000


def cases():
    result = []
    for bit in range(4, 12):
        for anchor in (0, 0x580):
            for phase in range(4):
                a = BASE + ((anchor & ~(1 << bit)) | (phase * 4))
                b = a ^ (1 << bit)
                for invert in (0, 1):
                    va = (0x13579bdf ^ (bit << 20) ^ (phase * 0x01020304) ^ anchor)
                    if invert:
                        va ^= 0xffffffff
                    vb = va ^ 0xffffffff
                    for order in ('AB', 'BA'):
                        assert BASE <= a < BASE + 4096 and BASE <= b < BASE + 4096
                        assert a % 4 == b % 4 == 0 and a != b
                        result.append(dict(id=len(result), bit=bit, anchor=anchor,
                                           word_phase=phase, inverted=invert, order=order,
                                           a=a, b=b, expected_a=va, expected_b=vb))
    return result


def phase_cases():
    selected = [dict(t) for t in cases() if t['bit'] == 6 and t['anchor'] == 0]
    for index, t in enumerate(selected):
        t['id'] = index
        # Repeated reads cover every modulo-four transaction phase for each
        # address. Odd lengths shift that phase before the next sequence.
        t['read_order'] = 'a' * 17 + 'b' * 17 + 'ab' * 9 + 'ba' * 9
    return selected


def commands(previous, trials):
    result = recovery_commands(previous)[:-3]
    result += ['reg priv 3', 'reg satp 0', 'reg mstatus 0', 'reg mie 0',
               'reg csr1996 6', 'reg csr1994 0',
               'echo NEO_ADDRESS_PAIRS_BEGIN']
    for t in trials:
        for label in t['order'].lower():
            result.append(f'write_memory {t[label]:#x} 32 {{{t["expected_" + label]:#x}}}')
        # Eight separate read transactions, with both address orders. No
        # inference about raw physical DQ/column pins is made from these reads.
        for index, label in enumerate(t.get('read_order', 'abbaabba')):
            result.append(f'echo "PAIR {t["id"]} {index} {label} [read_memory {t[label]:#x} 32 1]"')
    result += ['echo NEO_ADDRESS_PAIRS_COMPLETE', 'shutdown', '']
    return result


def analyze(trials, log):
    rows = re.findall(r'^PAIR (\d+) (\d+) ([ab]) (0x[0-9a-fA-F]+|\d+)\s*$', log, re.M)
    observed = {}
    for trial, index, label, value in rows:
        key = (int(trial), int(index))
        if key in observed:
            raise ValueError('Duplicate pair observation')
        observed[key] = (label, int(value, 0))
    expected_keys = {(t['id'], i) for t in trials for i in range(len(t.get('read_order', 'abbaabba')))}
    complete = ('NEO_ADDRESS_PAIRS_COMPLETE' in log and set(observed) == expected_keys)
    details = []
    for t in trials:
        item = dict(t, reads=[], bad_reads=0, closer_to_other=0)
        for index, label in enumerate(t.get('read_order', 'abbaabba')):
            hit = observed.get((t['id'], index))
            if hit is None:
                continue
            if hit[0] != label:
                raise ValueError('Unexpected address read order')
            value = hit[1]
            own = t['expected_' + label]
            other = t['expected_' + ('b' if label == 'a' else 'a')]
            own_distance, other_distance = (value ^ own).bit_count(), (value ^ other).bit_count()
            item['reads'].append(dict(index=index, address_label=label, value=value,
                                      bit_errors=own_distance, other_bit_errors=other_distance))
            item['bad_reads'] += own_distance != 0
            item['closer_to_other'] += other_distance < own_distance
        item['varying_a'] = len({r['value'] for r in item['reads'] if r['address_label'] == 'a'}) > 1
        item['varying_b'] = len({r['value'] for r in item['reads'] if r['address_label'] == 'b'}) > 1
        details.append(item)
    return dict(complete=complete,
                passed=complete and all(t['bad_reads'] == 0 for t in details),
                expected_reads=len(expected_keys), captured_reads=len(observed),
                bad_reads=sum(t['bad_reads'] for t in details),
                closer_to_other=sum(t['closer_to_other'] for t in details), trials=details)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--failed-load', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--read-phases', action='store_true',
                   help='Focus on address bit 6; repeated same-address reads across FIFO phases')
    args = p.parse_args()
    out = args.out.resolve()
    if any(c in str(out) for c in '{}\\\r\n'):
        p.error('Unsafe output path')
    trials = phase_cases() if args.read_phases else cases()
    script = '\n'.join(['riscv expose_csrs 1994,1996,2000'] + commands(args.failed_load, trials))
    previous = json.loads((args.failed_load / 'result.json').read_text())
    out.mkdir(parents=True, exist_ok=False)
    (out / 'cases.json').write_text(json.dumps(trials, indent=2) + '\n')
    (out / 'probe.tcl').write_text(script)
    transport_error = None
    with (out / 'openocd.log').open('w') as log:
        try:
            subprocess.run(['/usr/local/bin/openocd', '-f', str(ROOT / 'tools/neo/ae350_espprog.cfg'),
                            '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled',
                            '-f', str(out / 'probe.tcl')], stdout=log, stderr=subprocess.STDOUT,
                           check=True, timeout=180)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            transport_error = str(e)
    log = (out / 'openocd.log').read_text()
    result = analyze(trials, log)
    result.update(transport_error=transport_error,
                  bitstream_sha256=previous['bitstream_sha256'],
                  bitstream_identity='From the preceding failed-load record; no independent FPGA readback',
                  sd_written=False, flash_written=False,
                  requested_writes=f'{len(trials)} pairs of 32-bit writes, confined to volatile DDR 0x12000000..0x12000fff; cache/control CSRs only',
                  script_sha256=hashlib.sha256(script.encode()).hexdigest())
    result['passed'] &= transport_error is None
    # The recovery helper's terminal marker is omitted with its shutdown;
    # BEGIN is emitted only after its parking-PC and instruction checks.
    result['cpu_left_halted'] = result['complete'] and 'NEO_ADDRESS_PAIRS_BEGIN' in log
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'trials'}, indent=2))
    if not result['complete']:
        raise SystemExit('Incomplete probe; partial evidence saved')
    if not result['passed']:
        raise SystemExit('Address-pair errors detected; evidence saved')


if __name__ == '__main__':
    main()
