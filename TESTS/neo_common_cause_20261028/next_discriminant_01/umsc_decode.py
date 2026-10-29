#!/usr/bin/env python3
"""Strict offline UMSC transcript decoder; this module has no transport.

Records are six ordered individual 32-bit reads: ID, status, version twice.
CDC flags remain observations. They are not converted into USB functionality
or clock-frequency claims. Reading this peripheral refreshes its watchdog.
"""
import argparse
import json
from pathlib import Path

BASE = 0xE9003000
IDENTITY = 0x554D5343
ORDER = (BASE, BASE + 4, BASE + 0x28) * 2
FIELDS = {
    0: 'rx_gathered_available', 1: 'tx_level_zero', 2: 'seen_bus_reset',
    3: 'seen_bot_reset', 4: 'quiet', 5: 'online_sampled',
    6: 'highspeed_sampled', 7: 'lost', 8: 'owner_sampled',
    9: 'serve_requested', 10: 'halted_sampled',
}


def word(value, name):
    """No bool coercion, negative values, overflow, or implied address aliases."""
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError(f'{name}: expected uint32')
    return value


def decode(records):
    """Decode a complete transcript or a strict prefix after interrupted I/O.

    Errors preserve raw observations; partial reads never receive PASS.
    Unexpected owner/request is an operating-context failure, not silicon proof.
    Online/HS and owner/request can transiently disagree across synchronizers.
    """
    if type(records) is not list or len(records) > len(ORDER):
        raise ValueError('expected a list of at most six reads')
    errors, observations, statuses = [], [], []
    for index, record in enumerate(records):
        if type(record) is not dict or set(record) != {'seq', 'address', 'value'}:
            raise ValueError(f'record {index}: expected seq/address/value only')
        seq = word(record['seq'], 'seq')
        address = word(record['address'], 'address')
        value = word(record['value'], 'value')
        if seq != index or address != ORDER[index]:
            raise ValueError(f'record {index}: wrong tag/order/address')
        observations.append(dict(record))
        if address == BASE and value != IDENTITY:
            errors.append(f'{index}:identity_not_UMSC')
        elif address == BASE + 0x28 and value != 1:
            errors.append(f'{index}:version_not_one')
        elif address == BASE + 4:
            status = {'seq': index, 'raw': value, 'tx_level': value >> 16}
            status.update({name: bool(value & (1 << bit)) for bit, name in FIELDS.items()})
            statuses.append(status)
            if value & 0xF800:
                errors.append(f'{index}:reserved_bits_nonzero')
            if value & 0x300:
                errors.append(f'{index}:unexpected_firmware_ownership_context')
            if bool(value & 2) != ((value >> 16) == 0):
                errors.append(f'{index}:tx_level_zero_combinational_mismatch')
    complete = len(records) == len(ORDER)
    if not complete:
        errors.append('partial_transcript')
    transitions = []
    for first, second in zip(statuses, statuses[1:]):
        transitions.append({
            'from_seq': first['seq'], 'to_seq': second['seq'],
            'changed_fields': [name for name in ['tx_level', *FIELDS.values()]
                               if first[name] != second[name]],
        })
    return {
        'schema': 1, 'complete': complete, 'contract_passed': not errors,
        'hardware_qualified': False, 'errors': errors,
        'observations': observations, 'statuses': statuses,
        'transitions': transitions,
        'watchdog_refreshed': bool(records),
        'usb_functionality': 'not_tested', 'clock_frequency': 'not_measured',
        'limits': ['separately_synchronized_flags',
                   'reads_refresh_watchdog', 'no_host_traffic'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='JSON list of captured reads')
    args = parser.parse_args()
    result = decode(json.loads(args.input.read_text()))
    print(json.dumps(result, indent=2))
    return 0 if result['contract_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
