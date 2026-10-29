#!/usr/bin/env python3
"""Run the reviewed 128-byte CPU/GPU test, then restore exact Neo R19.

No new bitstream is built. The only DDR writes are CPU128B/GPU32B in reserved
diagnostic scratch. The journal is read from ILM even when its comparison fails.
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
    1: ('build_01', '3180912273bb65ae3b2df2bba48a772f1482033698f2a2b914e355e46a304fa2'),
    2: ('build_02', 'dbf293d4ed9c739e4641f0ff531374c5fb9ad8ec7b2b7795f0bf4e609baa934c'),
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
    args = parser.parse_args()
    assert __debug__ and not args.out.exists()
    build, firmware_sha = FIRMWARE_PROFILES[args.firmware_revision]
    firmware = HERE / 'execution_diagnostic_02/microdma_r1' / build / 'microdma.bin'
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
    (out / 'prepared.tcl').write_text(code)
    report = dict(hardware=args.run, diagnostic_passed=False, restored=False,
                  firmware_sha256=firmware_sha, firmware_revision=args.firmware_revision,
                  r19_sha256=previous.R19_SHA,
                  scratch_address='0x12000000', scratch_bytes=128,
                  code_address='0xa0004000', journal_address='0xa0006000',
                  code_bytes=928, journal_bytes=512, sd_writes=0)
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
