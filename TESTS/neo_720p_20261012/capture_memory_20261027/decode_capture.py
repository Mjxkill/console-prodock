#!/usr/bin/env python3
"""Decode the D* observer, without treating sampled events as timing proof."""
import argparse
import json


def unsigned(value, bits, name):
    if type(value) is not int or not 0 <= value < (1 << bits):
        raise ValueError(f'{name} must be an unsigned {bits}-bit integer')
    return value


def sample(value):
    unsigned(value, 24, 'sample')
    result = {'raw': f'0x{value:06x}', 'width_d': value & 255,
              'width_q': (value >> 8) & 255}
    names = ('ce', 'engine_reset', 'copy_start', 'idle', 'check',
             'validate', 'bad', 'done')
    result.update({name: bool(value & (1 << (16 + bit)))
                   for bit, name in enumerate(names)})
    return result


def decode(value, epoch, expected_width=None):
    unsigned(value, 64, 'capture')
    unsigned(epoch, 1, 'epoch')
    if value >> 60 != 0xd or (value >> 55) & 1:
        raise ValueError('Not the D* capture format, or reserved bit set')
    if ((value >> 54) & 1) != epoch:
        raise ValueError('Capture belongs to another acknowledged ARM epoch')
    if expected_width is not None:
        unsigned(expected_width, 8, 'expected_width')
    event_mask = (value >> 56) & 15
    valid = (value >> 48) & 3
    before, after = sample(value & 0xffffff), sample((value >> 24) & 0xffffff)
    complete = bool((value >> 50) & 1)
    armed = bool((value >> 51) & 1)
    findings = []
    # The two samples describe the COPY trigger and next clock only. Later
    # bad/done, packet words and DDR transaction order are not in this report.
    if expected_width is not None:
        if valid != 3 or not complete or armed:
            findings.append('COPY_CAPTURE_INCOMPLETE')
        elif not before['copy_start']:
            findings.append('COPY_TRIGGER_NOT_PRESENT_IN_SAMPLE')
        else:
            if before['width_d'] != expected_width:
                findings.append('COPY_INPUT_WIDTH_DIFFERS')
            if not before['ce']:
                findings.append('COPY_CAPTURE_ENABLE_NOT_SEEN_AT_TRIGGER')
            if before['engine_reset'] or after['engine_reset']:
                findings.append('COPY_ENGINE_RESET_SEEN')
            if before['ce'] and after['width_q'] != before['width_d']:
                findings.append('COPY_WIDTH_Q_DOES_NOT_MATCH_CAPTURED_D')
            if not findings:
                findings.append('COPY_WIDTH_CAPTURE_CONSISTENT')
    return {
        'raw': f'0x{value:016x}', 'format': 'D*', 'arm_epoch': epoch,
        'memory_event_mask': event_mask,
        'memory_events_seen': {name: bool(event_mask & (1 << bit)) for bit, name
            in enumerate(('native_issue', 'pixel_producer_valid',
                          'slot_pending', 'slot_accepted'))},
        'armed': armed, 'complete': complete, 'valid_samples': valid,
        'seen_capture_enable': bool((value >> 53) & 1),
        'seen_engine_reset': bool((value >> 52) & 1),
        'at_trigger': before if valid & 1 else None,
        'next_clock': after if valid & 2 else None,
        'findings': findings,
        'limits': 'Eight COPY width bits only; event flags mean seen since ARM, '
                  'not event counts/order or final descriptor validation. '
                  'A capture does not establish post-route timing correctness.'
    }


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=lambda s: int(s, 0))
    p.add_argument('--epoch', type=int, required=True, choices=(0, 1))
    p.add_argument('--width', type=int)
    a = p.parse_args()
    print(json.dumps(decode(a.capture, a.epoch, a.width), indent=2))
