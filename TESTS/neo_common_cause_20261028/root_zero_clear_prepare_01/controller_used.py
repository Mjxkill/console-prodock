#!/usr/bin/env python3
"""Run a reviewed 128-byte CPU/GPU diagnostic, then restore exact Neo R19.

No new bitstream is built. DDR writes are CPU128B/GPU32B in reserved diagnostic
scratch, except revision3 whose zero-flag CLEAR must issue no GPU DDR traffic.
The journal is read from ILM even when its comparison fails.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
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
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--firmware-revision', type=int, choices=FIRMWARE_PROFILES, required=True)
    parser.add_argument('--capture-gpu', action='store_true',
                        help='Capture coherent R19 command state before and after the same payload')
    parser.add_argument('--cpu-readback', action='store_true',
                        help='After BIN02 timeout, run guarded CPU-only reads into a separate ILM journal')
    args = parser.parse_args()
    assert __debug__ and not args.out.exists()
    assert not args.cpu_readback or (args.firmware_revision == 2 and args.capture_gpu), \
        'CPU readback requires BIN02 and before/after GPU captures'
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
    readback = HERE / 'execution_diagnostic_02/readback_r1'
    readback_sha = None
    if args.cpu_readback:
        binary = readback / 'build_01/readback.bin'
        readback_sha = hashlib.sha256(binary.read_bytes()).hexdigest()
        assert binary.stat().st_size == 588
        assert readback_sha == 'aa2a1a061c87de6cc47a567a217b6d4078df1d3c982242bfe2275ef7bcc50503'
        # Preserve the original timeout and coherent snapshots before creating
        # CPU traffic: a CPU read itself may affect the DDR arbiter selection.
        second_stage = f'''
set md [read_memory 0xa0006000 32 30]
if {{[llength $md] != 30}} {{error "Incomplete previous journal"}}
foreach i {{0 1 2 3}} want {{0x4d443132 1 8 0xfffffffb}} {{
    if {{[lindex $md $i] != $want}} {{error "Readback requires BIN02 CLEAR timeout"}}
}}
if {{[lindex $md 28] != 32 || [lindex $md 29] != 32}} {{error "Seed/target verification missing"}}
load_image {{{binary}}} 0xa0005000 bin
verify_image {{{binary}}} 0xa0005000 bin
resume 0xa0005000
sleep 2000
halt 1000
echo "READBACK_PC [reg pc]"
dump_image {{{out / 'readback.bin'}}} 0xa0006400 256
microdma_capture_r19 READBACK_AFTER
sleep 100
microdma_capture_r19 READBACK_AFTER100
echo READBACK_COLLECTED
'''
        code = code.replace('echo MICRODMA_COLLECTED', second_stage + '\necho MICRODMA_COLLECTED')
    (out / 'prepared.tcl').write_text(code)
    report = dict(hardware=args.run, diagnostic_passed=False, restored=False,
                  firmware_sha256=firmware_sha, firmware_revision=args.firmware_revision,
                  r19_sha256=previous.R19_SHA,
                  scratch_address='0x12000000', scratch_bytes=128,
                  code_address='0xa0004000', journal_address='0xa0006000',
                  code_bytes=928, journal_bytes=512, sd_writes=0)
    report.update(clear_flags=0 if args.firmware_revision == 3 else 1,
                  gpu_expected_write_bytes=0 if args.firmware_revision == 3 else 32,
                  scope='zero-flag CLEAR control' if args.firmware_revision == 3 else 'one-burst CLEAR')
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
                if args.cpu_readback and (out / 'readback.bin').exists():
                    try:
                        decoder = load('readback_decode', readback / 'decode.py')
                        report['readback'] = decoder.decode((out / 'readback.bin').read_bytes())
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
