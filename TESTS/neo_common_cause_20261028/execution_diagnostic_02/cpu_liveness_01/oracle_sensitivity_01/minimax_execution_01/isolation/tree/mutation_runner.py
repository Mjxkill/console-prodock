"""Real compile/run mutation trials for the CPU/CLEAR simulation oracle.

Every trial below is executed for real:

  * the reference sources are *copied* (never linked, never edited in place)
    into a fresh ``tempfile.TemporaryDirectory``;
  * the trial's targeted mutation is applied to that disposable copy only and
    the anchor text must match exactly once, otherwise the trial aborts;
  * the copy is compiled with the real Verilator (``/usr/bin/verilator
    --binary --timing -j2 -Wno-fatal -MAKEFLAGS VM_PARALLEL_BUILDS=0
    --top-module bench --Mdir <tmp>/obj``) and the reference SOURCES;
  * the produced ``Vbench`` binary is executed for real with ``+case=0``.

Nothing is synthesised.  A compile failure, a missing binary or an external
subprocess timeout is reported as such (compile_returncode / timeout) instead
of being dressed up as a detection: only a non-zero exit of the executed
binary whose own log carries the endpoint/byte-oracle message counts.

The trials are external bench-side stimuli only.  They say nothing about
physical DDR/GPU faults: no FPGA, board or PHY is involved here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Reference compile set, identical to the protected test_liveness.py list.
SOURCES = ['bench.sv', 'native_memory.sv', 'ddr_ui_adapt.v', 'ddr_gpu_arb.v',
           'gpu_v1.v', 'gpu_triangle.v', 'gpu_copy565.v', 'gpu_texture_cache.v',
           'gpu_perspective.v']
# scenario.svh is not listed as a source: bench.sv pulls it in with
# `include "scenario.svh"`, so it must sit next to the copied bench.sv.
SUPPORT = SOURCES + ['scenario.svh']

VERILATOR = '/usr/bin/verilator'
COMPILE_TIMEOUT = 48.0        # CONTRACT.md: compilation each <= 48 s
RUN_TIMEOUT = 3.0             # CONTRACT.md: binary <= 3 s
SCENARIO = '+case=0'          # healthy composition: 32 CPU reads + 2 GPU done
MAX_COMPILE_DETAIL = 4000     # bounded detail kept when a compile fails

# Trial catalogue.  Each mutation is a targeted replacement inside ONE
# disposable copy of ONE reference file; the anchor must occur exactly once.
#
#   baseline       no modification at all (reference sources, byte for byte)
#   return_low     native_memory.sv: corrupt the low word of the returned beat
#   return_upper   native_memory.sv: corrupt bit 128 (upper 128-bit half)
#   return_missing native_memory.sv: accept the read but never emit the reply
#   write_mask     bench.sv: XOR one mask bit on the arbiter .b_wr_mask wire
#   write_address  bench.sv: XOR 0x00800000 on the arbiter .b_addr wire
MUTATIONS = {
    'return_low': {
        'file': 'native_memory.sv',
        'old': 'rd_data<=replies[rp];',
        'new': "rd_data<=replies[rp] ^ 256'd1;",
        'note': 'XOR 1 into the low word of the native return',
    },
    'return_upper': {
        'file': 'native_memory.sv',
        'old': 'rd_data<=replies[rp];',
        'new': "rd_data<=replies[rp] ^ (256'd1 << 128);",
        'note': 'XOR bit 128 into the native return (upper 128-bit half)',
    },
    'return_missing': {
        'file': 'native_memory.sv',
        'old': 'if(!hold_returns && rp<wp && tick>=due[rp])begin',
        'new': "if(1'b0 && !hold_returns && rp<wp && tick>=due[rp])begin",
        'note': 'suppress return emission, keep native read acceptance',
    },
    'write_mask': {
        'file': 'bench.sv',
        'old': '.b_wr_mask(b_wr_mask),',
        'new': ".b_wr_mask(b_wr_mask ^ 32'h00000001),",
        'note': 'XOR 1 into the write mask at the arbiter .b_wr_mask connection',
    },
    'write_address': {
        'file': 'bench.sv',
        'old': '.b_addr(b_addr),',
        'new': ".b_addr(b_addr ^ 29'h00800000),",
        'note': 'XOR 0x00800000 words (+32 MiB) into the arbiter .b_addr connection',
    },
}

TRIAL_NAMES = ('baseline', 'return_low', 'return_upper',
               'return_missing', 'write_mask', 'write_address')


def _compile_cmd(obj: Path):
    """Exact Verilator invocation mandated by CONTRACT.md."""
    return [VERILATOR, '--binary', '--timing', '-j', '2', '-Wno-fatal',
            '-MAKEFLAGS', 'VM_PARALLEL_BUILDS=0', '--top-module', 'bench',
            '--Mdir', str(obj), *SOURCES]


def _as_text(blob) -> str:
    """Normalise captured stdout/stderr chunks (bytes or str) to text."""
    if blob is None:
        return ''
    if isinstance(blob, bytes):
        return blob.decode('utf-8', 'replace')
    return blob


def _join(out, err) -> str:
    """Concatenate captured stdout and stderr without gluing two lines."""
    log = _as_text(out)
    err = _as_text(err)
    if err:
        if log and not log.endswith('\n'):
            log += '\n'
        log += err
    return log


def _materialise(name: str, work: Path) -> None:
    """Copy the reference sources into `work` and apply this trial's mutation.

    The copies are real copies (shutil.copy2), never links, so the reference
    tree is never touched.  The targeted replacement is refused unless its
    anchor matches exactly once in the copied file.
    """
    for src in SUPPORT:
        dst = work / src
        shutil.copy2(HERE / src, dst)
        os.chmod(dst, 0o644)          # reference files are shipped read-only
    spec = MUTATIONS.get(name)
    if spec is None:
        return                        # baseline: untouched copies
    target = work / spec['file']
    text = target.read_text()
    hits = text.count(spec['old'])
    if hits != 1:
        raise RuntimeError(
            f'trial {name}: anchor matched {hits} times in {spec["file"]}, expected exactly 1')
    target.write_text(text.replace(spec['old'], spec['new']))


def _run_trial(name: str) -> dict:
    """Compile and execute one trial on its own disposable copy."""
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f'sens-{name}-') as tmp:
        work = Path(tmp)
        _materialise(name, work)
        obj = work / 'obj'
        compile_rc = None
        compile_detail = ''
        timed_out = False
        try:
            comp = subprocess.run(_compile_cmd(obj), cwd=str(work),
                                  capture_output=True, text=True,
                                  timeout=COMPILE_TIMEOUT)
            compile_rc = comp.returncode
            compile_detail = _join(comp.stdout, comp.stderr)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            compile_rc = 124          # conventional "command timed out" code
            compile_detail = _join(exc.stdout, exc.stderr)

        binary = obj / 'Vbench'
        executed = False
        run_rc = None
        log = ''
        if compile_rc == 0 and binary.exists():
            try:
                run = subprocess.run([str(binary), SCENARIO], cwd=str(work),
                                     capture_output=True, text=True,
                                     timeout=RUN_TIMEOUT)
                executed = True
                run_rc = run.returncode
                log = _join(run.stdout, run.stderr)
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                executed = True       # the process was started and killed
                log = _join(exc.stdout, exc.stderr)
                log += (f'\nEXTERNAL TIMEOUT after {RUN_TIMEOUT:.1f}s '
                        '(not a detection)\n')
        else:
            reason = ('compile failed' if compile_rc != 0
                      else 'no Vbench binary produced')
            log = (f'{reason} (compile_returncode={compile_rc}); '
                   'no binary executed\n')
            log += compile_detail[-MAX_COMPILE_DETAIL:]

        return {
            'name': name,
            'compile_returncode': compile_rc,
            'timeout': timed_out,
            'executed_binary': executed,
            'returncode': run_rc,
            'log': log,
            'elapsed_seconds': round(time.monotonic() - started, 3),
        }


def _worker_count(trials: int) -> int:
    """Parallel compiles, but never more workers than usable CPUs."""
    try:
        available = len(os.sched_getaffinity(0))
    except AttributeError:                    # pragma: no cover - portability
        available = os.cpu_count() or 1
    return max(1, min(trials, available))


def run_suite(names):
    """Run exactly the requested trials and return one real record per trial.

    `names` is the explicit list of trials asked for (the fixed acceptance
    harness asks for three of them per group).  Each trial owns a fresh
    disposable directory; the compiles of the requested trials run in parallel
    because they are completely independent.
    """
    requested = list(names)
    unknown = [n for n in requested if n not in TRIAL_NAMES]
    if unknown:
        raise ValueError(f'unknown trial name(s): {unknown}')
    if not requested:
        return []
    with ThreadPoolExecutor(max_workers=_worker_count(len(requested))) as pool:
        records = list(pool.map(_run_trial, requested))
    return records


if __name__ == '__main__':
    import json
    import sys
    wanted = sys.argv[1:] or list(TRIAL_NAMES)
    print(json.dumps(run_suite(wanted), indent=2))
