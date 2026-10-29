#!/usr/bin/env python3
"""Root-only one-shot external flash write coordinator.

Scope
-----
This module owns the *whole* write path of the external SPI flash of the
GW5AST-138 (board ``tangmega138k``) behind the FTDI 0403:6010 programmer
serial ``2025071717``:

``prepare()``
    An explicitly **offline** step.  It validates the root request, the
    read-only detection, the two independent read-only backups, the SRAM
    candidate result and the explicit root acceptance attestation, exports the
    ``.fs`` candidate with the pinned ``export_fs`` tool, builds the 64 KiB
    tail preserving image with the pinned ``offline.prepare`` and checks the
    RawParser route with the pinned ``raw_route_check``.  No hardware guard
    is opened; only the two pinned offline parser processes run.

``execute()``
    The single write attempt.  It revalidates the plan and every input, holds
    **one** hardware guard across the program pass and the full capacity
    readback, programs the image exactly once with the reviewed
    ``target_guard.command(..., 'program', image=...)`` argv and reads the
    whole flash back exactly once.  Nothing is retried, unprotected, bulk
    erased or rolled back.

Identity and limits
-------------------
The production root is fixed at ``/home/michael/console-validation-20261001``,
the host must be ``michael-AX15`` and the programmer serial is ``2025071717``.
There is no path, root or identity override: the old dock 2023112818, UART
7.3 and every J-Link stay forbidden and are never referenced here.  Only the
Python API may inject a root, a runner or a guard factory, and only for the
offline tests.

What a success does and does not mean
--------------------------------------
A program pass followed by a matching full capacity readback proves the
*flash content* only.  It proves no cold boot, no GPU function and no
power cycle: those stay ``False`` in every result and the status of a
complete run is ``coldboot_pending``.  Preparing or programming a flash
access erases the SRAM FPGA configuration of the GW5AST
(reference/src/gowin.cpp:1220), so the Linux that currently runs on the FPGA
stops during the program pass and during the readback; that interruption is
an expectation, never a measured fact.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import proofs  # noqa: E402  (local module)
import program_log  # noqa: E402  (local module)

ROOT = proofs.ROOT
MIN_TIMEOUT = proofs.MIN_TIMEOUT
MAX_TIMEOUT = proofs.MAX_TIMEOUT
DEFAULT_TIMEOUT = 900

PLAN_NAME = 'plan.json'
MANIFEST_NAME = 'manifest.json'
RESULT_NAME = 'result.json'
PROGRAM_LOG = 'program.log'
READBACK_LOG = 'readback.log'
READBACK_BIN = 'readback.bin'

CONSEQUENCES = (
    'Root only: the production root is fixed at %s, the host must be %s and '
    'the programmer serial is %s. There is no path, root or identity override.'
    % (ROOT, proofs.HOST_REQUIRED, proofs.SERIAL),
    'Programming the external SPI flash interrupts the SRAM FPGA '
    'configuration of the GW5AST-138 (reference/src/gowin.cpp:1220): the Linux '
    'that currently runs on the FPGA stops during the program pass and during '
    'the full readback. The interruption is an expectation, not a measurement.',
    'The program pass runs exactly once. A failed, timed out or interrupted '
    'program is never repeated, unprotected, bulk erased or rolled back here.',
    'A program pass with a matching full readback proves the flash content '
    'only. It proves no cold boot, no GPU function and no power cycle.',
)

NOTES = (
    'The program argv is built by the reviewed target_guard helper and runs '
    'exactly once.',
    'The full capacity readback covers the untouched tail outside the rounded '
    'programmed region, not only a CRC or the internal --verify.',
    'The number of completed flash writes is not measured: an attempt is not '
    'a completed write.',
)


def _tool(root):
    """The pinned wrapper path inside the fixed root."""
    return Path(root) / 'bin' / 'openFPGALoader'


def _entry(path):
    """{path, sha256, bytes} of an existing regular file."""
    return proofs.file_entry(path)


def _open_guard(root, guard_factory):
    """Open the single hardware guard that spans program and readback."""
    if guard_factory is not None:
        return guard_factory(root)
    return proofs.flash_readonly().default_guard_factory(root)


def _default_runner(argv, stdout, timeout):
    """The pinned process guard owns the child; no other process path exists."""
    return proofs.process_guard().run_programmer(argv, stdout, timeout)


def _run_logged(runner, argv, log_path, timeout, info):
    """Run one reviewed command and keep its full log, even on failure.

    The caller owns ``info``: the record of the attempt therefore survives
    an exception of the runner (a timeout, a signal or a failed cleanup).
    """
    info.update({'command': [str(item) for item in argv], 'log': str(log_path),
                 'returncode': None, 'timeout': False, 'error': None, 'attempted': False})
    try:
        handle = open(log_path, 'xb')
    except FileExistsError:
        raise proofs.ProofError('refusing to overwrite the existing log %s' % log_path)
    except OSError as error:
        raise proofs.ProofError('cannot create the log %s: %r' % (log_path, error))
    try:
        try:
            info['attempted'] = True  # runner boundary; not a measured flash write
            info['returncode'] = int(runner([str(item) for item in argv], handle,
                                            timeout))
        except subprocess.TimeoutExpired:
            info['timeout'] = True
            info['error'] = 'timeout after %ss' % timeout
        except BaseException as error:
            # A failed cleanup or a signal keeps the partial log on disk and
            # must never be reported as a success.
            info['error'] = repr(error)
            raise
        finally:
            try:
                handle.flush()
                handle.close()
            except OSError:
                pass
    finally:
        if os.path.exists(log_path):
            info['log_sha256'] = proofs.sha256_file(log_path)
    return info


# --------------------------------------------------------------------------
# prepare: the offline half.
# --------------------------------------------------------------------------
def prepare(request_path, request_sha, out_dir, *, root=ROOT):
    """Validate proofs and write local preparation artifacts; no hardware access.

    The returned dictionary is the plan that was written to ``out_dir``.
    """
    root = Path(root)
    proofs.verify_dependencies()
    request = proofs.load_request(request_path, request_sha, root)
    jedec = request['jedec']
    capacity = request['capacity']

    detection = proofs.validate_detection(root, request['detection']['path'],
                                          request['detection']['sha256'],
                                          jedec, capacity)
    sectors = detection['parsed']['sectors']
    backups = proofs.validate_backups(root, request['backups']['path'],
                                      request['backups']['sha256'],
                                      detection, jedec, sectors, capacity)
    sram = proofs.validate_sram_result(root, request['sram_result']['path'],
                                       request['sram_result']['sha256'],
                                       request['bitstream']['path'],
                                       request['bitstream']['sha256'])
    acceptance = proofs.validate_acceptance(
        root, request['acceptance']['path'], request['acceptance']['sha256'],
        bitstream_sha=request['bitstream']['sha256'],
        sram_sha=request['sram_result']['sha256'],
        dump_sha=request['backups']['sha256'])

    bitstream = Path(request['bitstream']['path'])
    fs_before = proofs.sha256_file(bitstream)
    out = proofs.make_output_dir(root, out_dir)
    prepared = out / 'prepared'
    image = prepared / 'program.bin'
    payload = out / 'payload.bin'
    try:
        export = proofs.export_payload(bitstream, payload)
        fs_after = proofs.sha256_file(bitstream)
        if fs_after != fs_before:
            raise proofs.ProofError('the .fs candidate changed during the export')
        try:
            report = proofs.offline().prepare(payload, backups['dumps']['a']['file'],
                                              backups['dumps']['b']['file'],
                                              capacity, prepared)
        except (ValueError, OSError) as error:
            raise proofs.ProofError('the offline preparation refused: %r' % error)
        route = proofs.check_raw_route(bitstream, image)
        plan = _build_plan(root, out, request, detection, backups, sram,
                           acceptance, report, export, route, prepared, image,
                           payload)
        proofs.write_json(out / PLAN_NAME, plan)
        plan_sha = proofs.sha256_file(out / PLAN_NAME)
        manifest_plan = dict(plan)
        manifest_plan['plan_sha256'] = plan_sha
        proofs.write_manifest(out, manifest_plan)
    except BaseException as error:
        # Preserve the failure, but never leave a usable prepared image.
        removed = _discard_image(image)
        _record_prepare_failure(out, error, removed)
        raise
    plan['plan_path'] = str(out / PLAN_NAME)
    plan['plan_sha256'] = proofs.sha256_file(out / PLAN_NAME)
    return plan


def _build_plan(root, out, request, detection, backups, sram, acceptance,
                report, export, route, prepared, image, payload):
    """Assemble the plan document that ``execute`` revalidates."""
    readonly = proofs.flash_readonly()
    tool = _tool(root)
    with proofs.pinned_errors('the reviewed program command'):
        program_command = [str(item) for item in
                           proofs.target_guard().command(tool, 'program',
                                                         image=str(image))]
    inputs = {
        'request': _entry(request['path']),
        'bitstream': _entry(request['bitstream']['path']),
        'sram_result': _entry(request['sram_result']['path']),
        'detection': _entry(request['detection']['path']),
        'backups': _entry(request['backups']['path']),
        'acceptance': _entry(request['acceptance']['path']),
        'backup_a': _entry(backups['dumps']['a']['file']),
        'backup_b': _entry(backups['dumps']['b']['file']),
    }
    proof_logs = {
        'detection': _entry(detection['summary']['log_path']),
        'dump_a': _entry(backups['dumps']['a']['log']),
        'dump_b': _entry(backups['dumps']['b']['log']),
    }
    return {
        'version': 1,
        'kind': 'flash-write-plan',
        'created_unix': time.time(),
        'root': str(root),
        'out_dir': str(out),
        'host_required': proofs.HOST_REQUIRED,
        'host_observed': socket.gethostname(),
        'target': {'serial': proofs.SERIAL, 'vendor': proofs.VENDOR,
                   'product': proofs.PRODUCT, 'board': proofs.BOARD,
                   'physical_idcode': proofs.PHYSICAL_IDCODE},
        'flash': {'jedec': detection['parsed']['jedec'],
                  'model': detection['parsed']['model'],
                  'sectors': detection['parsed']['sectors'],
                  'capacity': detection['parsed']['capacity']},
        'request': {'path': request['path'], 'sha256': request['sha256']},
        'inputs': inputs,
        'proof_logs': proof_logs,
        'image': _entry(image),
        'payload': _entry(payload),
        'offline_report': _entry(prepared / 'plan.json'),
        'expected_full_sha256': report['expected_full_sha256'],
        'preserved_last_sector_bytes': report['preserved_last_sector_bytes'],
        'preserved_tail_bytes': report['preserved_tail_bytes'],
        'payload_sha256': export['payload_sha256'],
        'raw_route': {'payload_bytes': route['route_payload_bytes'],
                      'total_bytes': route['route_total_bytes']},
        'dependencies': proofs.dependency_digests(),
        'program_command': program_command,
        'readback': {'action': 'dump', 'size': detection['parsed']['capacity']},
        'sram_interrupt_expected': True,
        'boot_tested': False,
        'gpu_tested': False,
        'powercycle_tested': False,
        'consequences': list(CONSEQUENCES),
        'notes': list(NOTES),
        'evidence': {'detection': detection['summary'],
                     'backups': {'path': backups['path'],
                                 'sha256': backups['sha256'],
                                 'comparison': backups['comparison']},
                     'sram_result': {'path': sram['path'], 'sha256': sram['sha256']},
                     'acceptance': {'path': acceptance['path'],
                                    'sha256': acceptance['sha256']}},
    }


def _discard_image(image):
    """Remove only our failed regular image; report cleanup truthfully."""
    try:
        if image.is_symlink():
            return False
        if not image.exists():
            return True
        if not image.is_file():
            return False
        image.unlink()
        return True
    except OSError:
        return False


def _record_prepare_failure(out, error, removed):
    """Keep failure and actual cleanup outcome; never claim an unseen unlink."""
    try:
        proofs.write_json(out / 'prepare_error.json',
                          {'kind': 'flash-write-prepare-error',
                           'created_unix': time.time(), 'error': repr(error),
                           'prepared_image_removed': removed})
    except proofs.ProofError:
        pass


# --------------------------------------------------------------------------
# execute: the single write attempt.
# --------------------------------------------------------------------------
def execute(plan_path, plan_sha, out_dir, *, root=ROOT, runner=None,
            guard_factory=None, timeout=DEFAULT_TIMEOUT):
    """Program the image once and read the whole flash back once.

    Refused identities or proofs raise ``ProofError`` *before* any program
    attempt; the returned dictionary describes the outcome of the attempt.
    """
    root = Path(root)
    proofs.verify_dependencies()
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not (MIN_TIMEOUT <= timeout <= MAX_TIMEOUT):
        raise proofs.ProofError('timeout must be between %d and %d seconds'
                                % (MIN_TIMEOUT, MAX_TIMEOUT))
    path = proofs.require_file(plan_path, 'the plan file', base=root / 'TESTS')
    expected = proofs.require_sha256(str(plan_sha).strip().lower(),
                                     'the plan sha256')
    proofs.check_sha256(path, expected, 'the plan file')
    try:
        plan = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise proofs.ProofError('the plan file is not readable JSON: %r' % error)
    image_path = proofs.revalidate_plan(plan, path, root)

    inputs = plan['inputs']
    request = proofs.load_request(inputs['request']['path'], inputs['request']['sha256'], root)
    for name in ('bitstream', 'sram_result', 'detection', 'backups', 'acceptance'):
        if any(inputs[name][key] != request[name][key] for key in ('path', 'sha256')):
            raise proofs.ProofError('Plan input differs from the bound request: ' + name)
    if (plan['flash']['jedec'], plan['flash']['capacity']) != (request['jedec'], request['capacity']):
        raise proofs.ProofError('Plan flash geometry differs from the request')
    for name in ('detection', 'backups', 'sram_result', 'acceptance', 'bitstream'):
        entry = inputs.get(name)
        if not isinstance(entry, dict) or not entry.get('path'):
            raise proofs.ProofError('the plan lacks the %r input' % name)
    jedec = (plan.get('flash') or {}).get('jedec')
    sectors = (plan.get('flash') or {}).get('sectors')
    capacity = (plan.get('flash') or {}).get('capacity')
    if (plan.get('target') or {}).get('serial') != proofs.SERIAL:
        raise proofs.ProofError('the plan targets another programmer serial')
    if (plan.get('target') or {}).get('physical_idcode') != proofs.PHYSICAL_IDCODE:
        raise proofs.ProofError('the plan targets another physical idcode')

    # Every proof is revalidated here, the root acceptance included.
    detection = proofs.validate_detection(root, inputs['detection']['path'],
                                          inputs['detection']['sha256'],
                                          jedec, capacity)
    proofs.validate_backups(root, inputs['backups']['path'],
                            inputs['backups']['sha256'], detection, jedec,
                            sectors, capacity)
    proofs.validate_sram_result(root, inputs['sram_result']['path'],
                                inputs['sram_result']['sha256'],
                                inputs['bitstream']['path'],
                                inputs['bitstream']['sha256'])
    proofs.validate_acceptance(root, inputs['acceptance']['path'],
                               inputs['acceptance']['sha256'],
                               bitstream_sha=inputs['bitstream']['sha256'],
                               sram_sha=inputs['sram_result']['sha256'],
                               dump_sha=inputs['backups']['sha256'])

    tool = _tool(root)
    with proofs.pinned_errors('the reviewed program command'):
        program_command = [str(item) for item in
                           proofs.target_guard().command(tool, 'program',
                                                         image=str(image_path))]
    planned = [str(item) for item in (plan.get('program_command') or [])]
    if planned and planned != program_command:
        raise proofs.ProofError('the program command differs from the planned one')

    out = proofs.make_output_dir(root, out_dir)
    result = {
        'version': 1,
        'kind': 'flash-write-result',
        'status': 'failed',
        'passed': False,
        'passed_means': 'flash_content_integrity_only',
        'program_attempted': False,
        'program_returncode': None,
        'full_readback_matches': None,
        'boot_tested': False,
        'gpu_tested': False,
        'powercycle_tested': False,
        'sram_interrupt_expected': True,
        'completed_flash_writes': None,
        'root': str(root),
        'out_dir': str(out),
        'plan': {'path': str(path), 'sha256': expected},
        'image': plan.get('image'),
        'expected_full_sha256': plan.get('expected_full_sha256'),
        'target': None,
        'logs': {},
        'program_log': None,
        'readback_log': None,
        'error': None,
        'started_unix': time.time(),
    }
    active_runner = runner or _default_runner
    try:
        with _open_guard(root, guard_factory) as identity:
            result['target'] = proofs.flash_readonly()._identity(identity)
            if not _run_program(result, out, plan, program_command, image_path,
                                root, active_runner, timeout, jedec, sectors):
                return result
            _run_readback(result, out, plan, root, active_runner, timeout,
                          jedec, sectors, capacity)
    except BaseException as error:
        result['error'] = repr(error)
        result['status'] = 'inconclusive' if result['program_attempted'] else 'failed'
        result['passed'] = False
        if isinstance(error, proofs.flash_readonly()._Abort):
            # A signal keeps the written result but leaves the exit status
            # to the caller: the run was interrupted, it did not succeed.
            raise
    finally:
        result['finished_unix'] = time.time()
        result['result_json'] = str(out / RESULT_NAME)
        try:
            proofs.write_json(out / RESULT_NAME, result)
        except proofs.ProofError as error:
            # Without a durable result the run is not a success.
            result['passed'] = False
            result['status'] = 'failed'
            result['result_write_error'] = repr(error)
    return result


def _run_program(result, out, plan, program_command, image_path, root, runner,
                 timeout, jedec, sectors):
    """Run the single program pass; return False when no readback may follow."""
    log_path = out / PROGRAM_LOG
    info = {'command': [str(item) for item in program_command],
            'log': str(log_path), 'returncode': None, 'timeout': False,
            'error': None}
    result['logs']['program'] = info
    try:
        _run_logged(runner, program_command, log_path, timeout, info)
    finally:
        result['program_attempted'] = bool(info.get('attempted'))
        result['program_returncode'] = info.get('returncode')
    result['program_returncode'] = info['returncode']
    if info['error']:
        raise proofs.ProofError('the program pass failed: %s' % info['error'])
    if info['returncode'] != 0:
        result['status'] = 'failed'
        result['error'] = 'the program pass exited with %s' % info['returncode']
        return False
    try:
        parsed = program_log.parse_program(log_path.read_bytes(), jedec=jedec,
                                            sectors=sectors)
    except proofs.ProofError as error:
        # An unknown strict grammar is a failure of this pass, never a
        # silent relaxation of the grammar.
        result['status'] = 'inconclusive'
        result['error'] = 'the program log does not match the strict grammar: %r' % error
        return False
    result['program_log'] = parsed
    return True


def _run_readback(result, out, plan, root, runner, timeout, jedec, sectors,
                  capacity):
    """Read the whole flash back once and compare every byte."""
    readonly = proofs.flash_readonly()
    tool = _tool(root)
    dump_path = out / READBACK_BIN
    log_path = out / READBACK_LOG
    with proofs.pinned_errors('the reviewed dump command'):
        argv = readonly.build_command('dump', tool, output=dump_path,
                                      size=capacity)
    info = {'command': [str(item) for item in argv], 'log': str(log_path),
            'returncode': None, 'timeout': False, 'error': None}
    result['logs']['readback'] = info
    _run_logged(runner, argv, log_path, timeout, info)
    if info['error']:
        raise proofs.ProofError('the readback failed: %s' % info['error'])
    if info['returncode'] != 0:
        result['status'] = 'failed'
        result['error'] = 'the readback exited with %s' % info['returncode']
        return False
    parsed = readonly.parse_dump_log(log_path.read_bytes(), jedec=jedec,
                                      sectors=sectors)
    result['readback_log'] = parsed
    if not dump_path.exists():
        result['status'] = 'failed'
        result['error'] = 'the readback produced no file'
        return False
    size = os.lstat(dump_path).st_size
    result['readback_bytes'] = size
    if size != capacity:
        result['status'] = 'failed'
        result['error'] = 'the readback holds %d bytes, expected %d' % (size, capacity)
        return False
    report_path = (plan.get('offline_report') or {}).get('path')
    try:
        report = proofs.offline().verify(str(report_path), dump_path)
    except (ValueError, OSError) as error:
        result['full_readback_matches'] = False
        result['status'] = 'failed'
        result['error'] = 'the full readback differs from the intended bytes: %r' % error
        return False
    matches = bool(report.get('full_readback_matches'))
    result['full_readback_matches'] = matches
    if not matches:
        result['status'] = 'failed'
        result['error'] = 'the full readback does not match the intended bytes'
        return False
    if report.get('sha256') != plan.get('expected_full_sha256'):
        result['full_readback_matches'] = False
        result['status'] = 'failed'
        result['error'] = 'the readback digest differs from the planned one'
        return False
    result['status'] = 'coldboot_pending'
    result['passed'] = True
    return True


# --------------------------------------------------------------------------
# Command line.
# --------------------------------------------------------------------------
def _summary(plan, out_dir):
    """The dry inspection view of a plan: no lock, no process, no output."""
    return {
        'mode': 'inspect',
        'root': plan.get('root'),
        'out_dir': str(out_dir),
        'target': plan.get('target'),
        'flash': plan.get('flash'),
        'image': plan.get('image'),
        'payload': plan.get('payload'),
        'expected_full_sha256': plan.get('expected_full_sha256'),
        'program_command': plan.get('program_command'),
        'readback': plan.get('readback'),
        'sram_interrupt_expected': plan.get('sram_interrupt_expected'),
        'boot_tested': False,
        'gpu_tested': False,
        'powercycle_tested': False,
        'consequences': plan.get('consequences'),
        'notes': ['This inspection opens no lock, starts no process and '
                  'creates no output file.'],
    }


def build_parser():
    """The command line of the coordinator; there is no root or path override."""
    parser = argparse.ArgumentParser(
        prog='flash_write.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Root-only one-shot external flash write coordinator.\n\n'
                    'prepare is explicitly offline; program inspects by '
                    'default and needs --run for the single write attempt.',
        epilog='\n'.join(CONSEQUENCES))
    subs = parser.add_subparsers(dest='command', required=True)

    offline = subs.add_parser(
        'prepare', help='offline preparation: validate the proofs and build '
                        'the program image (offline parser processes only)')
    offline.add_argument('--request', required=True,
                         help='the root request JSON under ROOT/TESTS')
    offline.add_argument('--request-sha', required=True,
                         help='the exact SHA-256 of the request JSON')
    offline.add_argument('--out', required=True,
                         help='a new output directory under ROOT/TESTS')

    program = subs.add_parser(
        'program', help='inspect the plan (default) or run the single write '
                        'attempt with --run')
    program.add_argument('--plan', required=True, help='the plan JSON')
    program.add_argument('--plan-sha', required=True,
                         help='the exact SHA-256 of the plan JSON')
    program.add_argument('--out', required=True,
                         help='a new output directory under ROOT/TESTS')
    program.add_argument('--run', action='store_true',
                         help='perform the real program and readback')
    program.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT,
                         help='seconds per command, %d..%d'
                              % (MIN_TIMEOUT, MAX_TIMEOUT))
    return parser


def main(argv=None):
    """Entry point.  0 on a completed request, 1 on a failed run, 2 on a refusal."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        try:
            plan = prepare(args.request, args.request_sha, args.out, root=ROOT)
        except proofs.ProofError as error:
            print(json.dumps({'error': repr(error)}, indent=2, sort_keys=True))
            return 2
        print(json.dumps({'plan': plan.get('plan_path'),
                          'plan_sha256': plan.get('plan_sha256'),
                          'image': plan.get('image'),
                          'expected_full_sha256': plan.get('expected_full_sha256'),
                          'out_dir': plan.get('out_dir')},
                         indent=2, sort_keys=True))
        return 0

    # program
    if args.timeout is not None and not (MIN_TIMEOUT <= args.timeout <= MAX_TIMEOUT):
        print(json.dumps({'error': 'timeout must be between %d and %d seconds'
                                  % (MIN_TIMEOUT, MAX_TIMEOUT)}, indent=2))
        return 2
    if not args.run:
        try:
            path = proofs.require_file(args.plan, 'the plan file',
                                       base=ROOT / 'TESTS')
            expected = proofs.require_sha256(str(args.plan_sha).strip().lower(),
                                             'the plan sha256')
            proofs.check_sha256(path, expected, 'the plan file')
            plan = json.loads(path.read_text())
            proofs.revalidate_plan(plan, path, ROOT)
        except proofs.ProofError as error:
            print(json.dumps({'error': repr(error)}, indent=2, sort_keys=True))
            return 2
        print(json.dumps(_summary(plan, args.out), indent=2, sort_keys=True))
        return 0

    readonly = proofs.flash_readonly()
    previous = readonly._install_signal_handlers()
    try:
        result = execute(args.plan, args.plan_sha, args.out, root=ROOT,
                         timeout=args.timeout)
    except proofs.ProofError as error:
        print(json.dumps({'error': repr(error)}, indent=2, sort_keys=True))
        return 2
    except readonly._Abort as error:
        print(json.dumps({'error': repr(error)}, indent=2, sort_keys=True))
        return 130
    finally:
        readonly._restore_signal_handlers(previous)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get('status') == 'coldboot_pending' else 1


if __name__ == '__main__':
    sys.exit(main())
