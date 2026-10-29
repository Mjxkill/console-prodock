#!/usr/bin/env python3
"""Strict grammar of the Gowin external flash program log.

Scope
-----
``parse_program`` decides whether the log of one ``--write-flash --verify``
pass really shows a completed write *and* a completed internal verification.
It never judges the exit code of the tool: a zero exit status is a separate
fact that the caller checks on its own.

Grammar
-------
The real ``Gowin::programExtFlash`` initialises the SPI flash (one
``read_id``) and then reads the identification again explicitly, so the log
may carry **one or two** JEDEC / geometry records.  Two records are accepted
only when they are identical; disagreeing records are a refusal.  The
physical chain stays unique: one ``found 1 devices``, one ``index 0:`` and
the idcode 0x1081b of the tangmega138k.

The accepted order is exactly:

    Writing ... 100.00%
    Done
    Verifying write (May take time)
    Reading ... 100.00%
    Done

A completion line that is followed by a device or flash record is refused,
and so is any error word (except the narrowly documented historical
``auto_boot_1st_fail`` flag of the read-only coordinator).

The text ``after program flash`` is printed *before* the operation starts;
it is therefore never accepted as evidence of anything.  This module only
reports whether it was present.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# The sibling module is loaded from this very directory, whatever the cwd is.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import proofs  # noqa: E402  (local module, loaded from this directory only)

ANSI_RE = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]'
                      r'|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)'
                      r'|\x1b[@-Z\\-_]')

WRITING_RE = re.compile(r'^\s*writing\b[^\n]*?(?<![\d.])100\.00\s*%[^\n]*$', re.IGNORECASE | re.MULTILINE)
READING_RE = re.compile(r'^\s*reading\b[^\n]*?(?<![\d.])100\.00\s*%[^\n]*$', re.IGNORECASE | re.MULTILINE)
VERIFY_RE = re.compile(r'verifying\s+write(?:\s*\(\s*may\s+take\s+time\s*\))?',
                       re.IGNORECASE)
AFTER_PROGRAM_RE = re.compile(r'after\s+program\s+flash', re.IGNORECASE)



def _as_text(raw):
    """Decode a log to text without ever raising on odd bytes."""
    if isinstance(raw, (bytes, bytearray, memoryview)):
        return bytes(raw).decode('utf-8', errors='replace')
    return str(raw)


def _normalise(raw):
    """Drop ANSI colour sequences and turn progress carriage returns into lines."""
    text = _as_text(raw).replace('\r\n', '\n').replace('\r', '\n')
    return ANSI_RE.sub('', text)


def _done_lines(lines):
    """Indices of the bare "Done" completion lines."""
    return [index for index, line in enumerate(lines) if line.strip() == 'Done']


def _records(text, pattern, what):
    """Return every match of `pattern` in the text."""
    return list(pattern.finditer(text))


def _line_index(text, position):
    """Line index of a character position."""
    return text.count('\n', 0, position)


def _check_identification(readonly, text, jedec, sectors):
    """Validate the unique physical chain and the JEDEC / geometry records.

    One or two identical JEDEC and geometry records are accepted, because the
    reviewed program path reads the flash identification twice.
    """
    what = 'program log'
    readonly._check_physical_header(text, what)

    jedec_any = readonly.JEDEC_ANY_RE.findall(text)
    if len(jedec_any) not in (1, 2):
        raise proofs.ProofError('%s: expected one or two JEDEC ID records, got %d'
                                % (what, len(jedec_any)))
    jedec_matches = readonly.JEDEC_RE.findall(text)
    if len(jedec_matches) != len(jedec_any):
        raise proofs.ProofError('%s: unsupported flash identification %r'
                                % (what, jedec_any))
    observed = {value.lower() for value in jedec_matches}
    if len(observed) != 1:
        raise proofs.ProofError('%s: the two JEDEC records disagree: %r'
                                % (what, sorted(observed)))
    jedec_value = observed.pop()
    expected_jedec = str(jedec).strip().lower()
    if jedec_value != expected_jedec:
        raise proofs.ProofError('%s: JEDEC %s differs from the expected %s'
                                % (what, jedec_value, expected_jedec))

    detected = readonly.DETECTED_LINE_RE.findall(text)
    if len(detected) != len(jedec_matches):
        raise proofs.ProofError('%s: expected one or two "Detected:" flash records,'
                                ' got %d' % (what, len(detected)))
    models = []
    sector_counts = []
    for line in detected:
        model, count, _size = readonly._parse_detected(line, what)
        models.append(model)
        sector_counts.append(count)
    if len(set(models)) != 1:
        raise proofs.ProofError('%s: the two flash records disagree on the model: %r'
                                % (what, models))
    if len(set(sector_counts)) != 1:
        raise proofs.ProofError('%s: the two flash records disagree on the geometry'
                                % (what, sector_counts))
    if sector_counts[0] != int(sectors):
        raise proofs.ProofError('%s: %d sectors differ from the expected %s'
                                % (what, sector_counts[0], sectors))
    return {'jedec': jedec_value, 'model': models[0], 'sectors': sector_counts[0],
            'capacity': sector_counts[0] * proofs.SECTOR_BYTES,
            'jedec_records': len(jedec_matches), 'detected_records': len(detected)}


def _check_phases(readonly, text, lines):
    """Require the write phase, then the internal verification, in order."""
    what = 'program log'
    writing = _records(text, WRITING_RE, what)
    reading = _records(text, READING_RE, what)
    verify = _records(text, VERIFY_RE, what)
    if not writing or not reading or len(verify) != 1:
        raise proofs.ProofError('Expected write progress and one verification phase')
    write_lines = [_line_index(text, m.start()) for m in writing]
    read_lines = [_line_index(text, m.start()) for m in reading]
    write_at, read_at = write_lines[0], read_lines[0]
    verify_at = _line_index(text, verify[0].start())
    if not write_at < verify_at < read_at:
        raise proofs.ProofError('Write and verification are not in order')
    # The last non-forced sample may round to 100.00%, before done() prints
    # exactly 100.00% again. Accept repeated progress, never a second Done.
    dones = _done_lines(lines)
    write_done = [i for i in dones if write_at < i < verify_at]
    final_done = [i for i in dones if i > read_at]
    if len(write_done) != 1 or len(final_done) != 1:
        raise proofs.ProofError('Each write/verify phase requires exactly one Done')
    write_done, final_done = write_done[0], final_done[0]
    if any(i >= write_done for i in write_lines) or any(i <= verify_at or i >= final_done for i in read_lines):
        raise proofs.ProofError('Progress crosses a completed phase')
    for pattern in (readonly.JEDEC_ANY_RE, readonly.DETECTED_LINE_RE,
                    readonly.FOUND_RE, readonly.INDEX_RE, readonly.IDCODE_RE):
        if any(_line_index(text, m.start()) >= write_at for m in pattern.finditer(text)):
            raise proofs.ProofError('Identification appears after writing began')
    for line in lines[final_done + 1:]:
        if not line.strip():
            continue
        if readonly._is_significant(line):
            raise proofs.ProofError('%s: a device or flash record follows the final '
                                    '"Done" line' % what)
    return {'write_done_line': write_done, 'final_done_line': final_done,
            'write_progress_line': write_at, 'verify_line': verify_at,
            'read_progress_line': read_at}


def parse_program(raw, *, jedec, sectors):
    """Parse a program log into a strict summary.

    Raises ``ProofError`` (a ValueError, RuntimeError and OSError) for an
    unknown or inconsistent identification, a missing write or verification
    phase, an out of order sequence, an error word or a record that follows
    the completion line.
    """
    readonly = proofs.flash_readonly()
    text = _normalise(raw)
    lines = text.splitlines()
    what = 'program log'

    context = readonly._error_context(text)
    if context:
        raise proofs.ProofError('%s reports an error status: %r' % (what, context))

    summary = _check_identification(readonly, text, jedec, sectors)
    summary.update(_check_phases(readonly, text, lines))
    summary['write_verified'] = True
    summary['verify_observed'] = True
    summary['after_program_flash_text'] = bool(AFTER_PROGRAM_RE.search(text))
    summary['bytes'] = len(_as_text(raw))
    return summary
