#!/usr/bin/env python3
"""Run a reviewed 128-byte CPU/GPU diagnostic, then restore exact Neo R19.

No new bitstream is built. DDR writes are CPU128B/GPU32B in reserved diagnostic
scratch, except revision3 whose zero-flag CLEAR must issue no GPU DDR traffic.
Revision4 instead copies one32B burst through the COPY565 path (one read/write).
Revision5 requests an empty COPY rectangle: validation runs, no DMA is expected.
The journal is read from ILM even when its comparison fails.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIRMWARE_PROFILES = {
    1: ('microdma_r1/build_01', '3180912273bb65ae3b2df2bba48a772f1482033698f2a2b914e355e46a304fa2'),
    2: ('microdma_r1/build_02', 'dbf293d4ed9c739e4641f0ff531374c5fb9ad8ec7b2b7795f0bf4e609baa934c'),
    3: ('zero_clear_01/firmware_r1/build_01', 'd9ad3f70166045fd7a210033603f43af2c6124f858eeb3ee675ca9d102fcadba'),
    4: ('copy_probe_01/firmware_delivery_01/build_01', '4d3b91ee5fd7aae44abd7d55ab712c24f78167ec1ac318f7a9a21aea000a8684'),
    5: ('copy_empty_01/build_01', '0e9b249f276a9c660bebf2a74774b7930cdaa02bb9fbfffc01136d7f0eb8bbc7'),
}
READBACK_PROFILES = {
    2: ('readback_r1', 'aa2a1a061c87de6cc47a567a217b6d4078df1d3c982242bfe2275ef7bcc50503',
        '5eeba4bc283e75bce035157f54a7f8bc1388ce6abfb26af7710abdff45ae2edf'),
    4: ('copy_readback_r1', '15dfe11fd3f11edd3330d835420562494a7d170f7a95b5e1b1c3d451462ae0d2',
        'b03d14c413daad8f9ad4e07b05bdce74ed3f405d0347cc7c00d878a18509a36f'),
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def readback_stage(binary, out):
    """ILM-only freshness checks; preserve a partial journal before PC refusal."""
    return f'''
set md [read_memory 0xa0006000 32 30]
if {{[llength $md] != 30}} {{error "Incomplete previous journal"}}
foreach i {{0 1 2 3}} want {{0x4d443132 1 8 0xfffffffb}} {{
    if {{[lindex $md $i] != $want}} {{error "Readback requires reviewed phase8 result-5"}}
}}
if {{[lindex $md 28] != 32 || [lindex $md 29] != 32}} {{error "Seed/target verification missing"}}
set rb_before_pc [lindex [reg pc] 2]
if {{$rb_before_pc != 0x80000000 && $rb_before_pc != 0x80000004}} {{error "CPU not parked before reader"}}
mww 0xa0006400 0 64
set rb_empty [read_memory 0xa0006400 32 64]
if {{[llength $rb_empty] != 64}} {{error "Incomplete cleared reader journal"}}
foreach value $rb_empty {{if {{$value != 0}} {{error "Reader journal clear not verified"}}}}
echo READBACK_ZERO_VERIFIED
load_image {{{binary}}} 0xa0005000 bin
verify_image {{{binary}}} 0xa0005000 bin
echo READBACK_START
resume 0xa0005000
sleep 2000
halt 1000
set rb_after_pc [lindex [reg pc] 2]
echo "READBACK_PC [reg pc]"
dump_image {{{out / 'readback.bin'}}} 0xa0006400 256
if {{$rb_after_pc != 0x80000000 && $rb_after_pc != 0x80000004}} {{error "CPU did not return to ROM after reader"}}
echo READBACK_RETURN_VERIFIED
microdma_capture_r19 READBACK_AFTER
sleep 100
microdma_capture_r19 READBACK_AFTER100
echo READBACK_COLLECTED
'''


def decode_readback(raw, log, revision, firmware_sha, readback):
    """Decoded content alone cannot prove this run produced the observation."""
    _, reader_sha, decoder_sha = READBACK_PROFILES[revision]
    path = readback / 'decode.py'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == decoder_sha
    decoder = load('readback_decode', path)
    if revision == 4:
        result = decoder.decode_bound(raw, stage_sha256=firmware_sha, reader_sha256=reader_sha)
    else:
        result = decoder.decode(raw)
    markers = ['READBACK_ZERO_VERIFIED', 'READBACK_START', 'READBACK_RETURN_VERIFIED',
               'READBACK_COLLECTED']
    positions = [list(re.finditer(r'^'+name+r'\s*$', log, re.M)) for name in markers]
    fresh = all(len(p)==1 for p in positions)
    fresh = fresh and all(positions[i][0].start()<positions[i+1][0].start() for i in range(3))
    result['controller_freshness_verified'] = fresh
    if not fresh:
        result['readback_valid'] = False
        result['classification'] = 'unobserved'
        result['issues'].append('reader_execution_freshness_unverified')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--firmware-revision', type=int, choices=FIRMWARE_PROFILES, required=True)
    parser.add_argument('--capture-gpu', action='store_true',
                        help='Capture coherent R19 command state before and after the same payload')
    parser.add_argument('--cpu-readback', action='store_true',
                        help='After reviewed CLEAR/COPY phase8 failure, run guarded CPU-only reads into ILM')
    args = parser.parse_args()
    assert __debug__ and not args.out.exists()
    assert not args.cpu_readback or (args.firmware_revision in READBACK_PROFILES and args.capture_gpu), \
        'CPU readback requires reviewed revision2/4 and before/after GPU captures'
    build, firmware_sha = FIRMWARE_PROFILES[args.firmware_revision]
    firmware = HERE / 'execution_diagnostic_02' / build / 'microdma.bin'
    assert firmware.stat().st_size == 928
    assert hashlib.sha256(firmware.read_bytes()).hexdigest() == firmware_sha
    previous = load('microdma_restore', HERE / 'combined_gpu_usb_prepared_01/controller.py')
    context = load('microdma_context', HERE / 'root_cpu_context_01.py')
    assert hashlib.sha256(previous.R19.read_bytes()).hexdigest() == previous.R19_SHA
    args.out.mkdir()
    out = args.out.resolve()
    # No DDR accesses are made by OpenOCD: all comparisons use CPU instructions.
    code = context.SCRIPT.rsplit('shutdown', 1)[0] + f'''
if {{[lindex [reg csr1994] 2] != 0}} {{error "Caches are enabled"}}
if {{[lindex [reg csr1984] 2] != 0xa0000001}} {{error "Unexpected ILM mapping"}}
load_image {{{firmware}}} 0xa0004000 bin
verify_image {{{firmware}}} 0xa0004000 bin
resume 0xa0004000
sleep 2000
halt 1000
echo "MICRODMA_PC [reg pc]"
dump_image {{{out / 'journal.bin'}}} 0xa0006000 512
echo "MICRODMA_GPU [read_memory 0xe9001000 32 14]"
echo MICRODMA_COLLECTED
'''
    capture = HERE / 'execution_diagnostic_02/board_analysis_02/capture_r19.tcl'
    capture_sha = None
    if args.capture_gpu:
        # This readout adds only snapshot requests: no DDR accesses, commands,
        # clock/reset changes, or additional CPU instructions after the payload.
        capture_text = capture.read_text()
        capture_sha = hashlib.sha256(capture.read_bytes()).hexdigest()
        assert capture_sha == 'f54489031f9dc5c8b4b3059d195f1c2661cbb402391ddd7d7322dbc7a5901e36'
        code = capture_text + '\n' + code
        code = code.replace(f'load_image {{{firmware}}}',
                            f'microdma_capture_r19 BEFORE\nload_image {{{firmware}}}', 1)
        code = code.replace('echo MICRODMA_COLLECTED', '''microdma_capture_r19 AFTER
sleep 100
microdma_capture_r19 AFTER100
echo MICRODMA_COLLECTED''', 1)
        (out / 'capture_used.tcl').write_text(capture_text)
    readback = None
    readback_sha = None
    if args.cpu_readback:
        folder, expected_reader_sha, expected_decoder_sha = READBACK_PROFILES[args.firmware_revision]
        readback = HERE / 'execution_diagnostic_02' / folder
        binary = readback / 'build_01/readback.bin'
        readback_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
        assert binary.stat().st_size == 588
        assert readback_sha == expected_reader_sha
        assert hashlib.sha256((readback/'decode.py').read_bytes()).hexdigest() == expected_decoder_sha
        # Preserve the original timeout and coherent snapshots before creating
        # CPU traffic: a CPU read itself may affect the DDR arbiter selection.
        second_stage = readback_stage(binary, out)
        code = code.replace('echo MICRODMA_COLLECTED', second_stage + '\necho MICRODMA_COLLECTED')
    (out / 'prepared.tcl').write_text(code)
    report = dict(hardware=args.run, diagnostic_passed=False, restored=False,
                  firmware_sha256=firmware_sha, firmware_revision=args.firmware_revision,
                  r19_sha256=previous.R19_SHA,
                  scratch_address='0x12000000', scratch_bytes=128,
                  code_address='0xa0004000', journal_address='0xa0006000',
                  code_bytes=928, journal_bytes=512, sd_writes=0)
    report.update(clear_flags={1: 1, 2: 1, 3: 0, 4: None, 5: None}[args.firmware_revision],
                  gpu_expected_write_bytes=0 if args.firmware_revision in (3, 5) else 32,
                  gpu_expected_read_bytes=32 if args.firmware_revision == 4 else 0,
                  scope={1: 'one-burst CLEAR', 2: 'one-burst CLEAR',
                         3: 'zero-flag CLEAR control', 4: 'one-burst COPY565',
                         5: 'empty COPY565 control, zero GPU DMA expected'}[args.firmware_revision])
    report.update(capture_requested=args.capture_gpu, capture_sha256=capture_sha,
                  capture_scope='Command state only; native DDR request/ready are not exposed by R19')
    report.update(cpu_readback_requested=args.cpu_readback, readback_sha256=readback_sha,
                  readback_scope='32 sequential CPU loads, no DDR/GPU writes by second stage')
    def save():
        temporary = out / 'result.json.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(out / 'result.json')
    save()
    (out / 'controller_used.py').write_bytes(Path(__file__).read_bytes())
    if not args.run:
        print(json.dumps(dict(prepared=True, hardware=False)))
        return
    cleanup = False
    def interrupted(number, frame):
        report.setdefault('signals', []).append(number)
        if not cleanup:
            raise InterruptedError('Requested interruption')
    handlers = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        fd = os.open(ROOT / 'TESTS/neo_board.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            clients = subprocess.run(['ps', '-C', 'openocd', '-C', 'openFPGALoader', '-C',
                                      'gao_sh', '-C', 'gao_analyzer', '-C', 'jtagserver',
                                      '-o', 'pid=,comm='], capture_output=True, text=True, timeout=5)
            assert not clients.stdout.strip(), 'Another hardware client is active'
            io = previous.prior.base.prior.IO(out, report, save)
            started = time.monotonic()
            try:
                # Reuse the tested hardware identity selection before any target write.
                identity = previous.prior.base.prior.hw.usb_identity()
                assert identity['neo']['serial'] == '2025041420'
                assert identity['neo']['path'].endswith('/3-4.4.1')
                report['usb_identity'] = identity
                io.observe('microdma', code, 'MICRODMA_COLLECTED')
            except BaseException as error:
                report['error'] = repr(error)
            finally:
                cleanup = True
                journal = out / 'journal.bin'
                if journal.exists() and journal.stat().st_size == 512:
                    words = struct.unpack('<128I', journal.read_bytes())
                    report['journal_words'] = list(words)
                    report['phase'] = words[2]
                    report['cpu_result'] = struct.unpack('<i', struct.pack('<I', words[3]))[0]
                    report['diagnostic_passed'] = words[:4] == (0x4d443132, 1, 10, 1)
                    if args.firmware_revision == 4:
                        decoder_path = HERE / 'execution_diagnostic_02/copy_probe_01/firmware_delivery_01/decode_copy.py'
                        try:
                            copy_decoder = load('copy_decode', decoder_path)
                            report['copy_observation'] = copy_decoder.decode(journal.read_bytes())
                            report['diagnostic_passed'] = report['copy_observation']['copy_test_passed']
                        except Exception as error:
                            report['diagnostic_passed'] = False
                            report['copy_decode_error'] = repr(error)
                    if args.firmware_revision == 5:
                        decoder_path = HERE / 'execution_diagnostic_02/copy_empty_01/decode_empty.py'
                        try:
                            assert hashlib.sha256(decoder_path.read_bytes()).hexdigest() == \
                                'a3e20a02e895a82510540a395dedee2134e362ed5011ef046aac46c7d259f206'
                            empty_decoder = load('empty_copy_decode', decoder_path)
                            report['empty_copy_observation'] = empty_decoder.decode(
                                journal.read_bytes(), firmware_sha256=firmware_sha)
                            report['diagnostic_passed'] = report['empty_copy_observation']['empty_copy_test_passed']
                        except Exception as error:
                            report['diagnostic_passed'] = False
                            report['empty_copy_decode_error'] = repr(error)
                if args.cpu_readback and (out / 'readback.bin').exists():
                    try:
                        log = (out / 'microdma.log').read_text(errors='replace')
                        report['readback'] = decode_readback((out / 'readback.bin').read_bytes(),
                            log, args.firmware_revision, firmware_sha, readback)
                    except Exception as error:
                        report['readback_decode_error'] = repr(error)
                save()
                io.program('restore_r19', previous.R19, previous.R19_SHA)
                io.observe('restored_guard', previous.prior.restoration_guard(), 'RESTORED_UTNA_FRESH')
                report.update(restored=True, elapsed_seconds=time.monotonic() - started)
                save()
    except BaseException as error:
        report['controller_error'] = repr(error)
    finally:
        for number, handler in handlers.items():
            signal.signal(number, handler)
        save()
    print(json.dumps({k: report.get(k) for k in ('diagnostic_passed', 'phase', 'cpu_result', 'restored', 'error', 'controller_error')}))


if __name__ == '__main__':
    main()
