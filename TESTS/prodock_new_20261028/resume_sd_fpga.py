#!/usr/bin/env python3
"""Resume one failed SD candidate from its exact netlist and routed database.

No constraints or report queries are changed. Incremental PnR can still move
or reroute logic, so this produces a candidate requiring new STA/board review.
The previous R2→R3 procedure is preserved in R3/build_driver.py as evidence.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from build_sd_fpga import ROOT, IDE, sha, json_file, environment
from build_sd_fpga import before_build, record_build, reference_check


def prepare(source, dest):
    """Freeze the failed design; change only project paths and the PR anchor."""
    old = 'console_' + source.name
    new = 'console_' + dest.name
    failure = json.loads((source / 'build_result.json').read_text())
    assert failure['tool_returncode'] != 0, 'Only a failed build may be resumed'
    assert not (source / f'impl/pnr/{old}.fs').exists()
    candidate = json.loads((source / 'sd_boot_candidate.json').read_text())
    assert candidate['cpu_ip_regenerated'] and candidate['target_programmer'] == '2025071717'
    assert candidate['rom_post_route_verification_required']
    manifest = json.loads((source / 'sources.json').read_text())
    for relative, digest in manifest.items():
        assert sha(source / 'source' / relative) == digest, relative
    contract = before_build('prodock', candidate=True)
    dest.mkdir(exist_ok=False)
    record_build(dest, contract)
    shutil.copytree(source / 'source', dest / 'source')
    shutil.copytree(source / 'rtl', dest / 'rtl')
    (dest / 'impl/gwsynthesis').mkdir(parents=True)
    vg = dest / f'impl/gwsynthesis/{new}.vg'
    shutil.copy2(source / f'impl/gwsynthesis/{old}.vg', vg)
    parent_pr = source / f'impl/pnr/{old}.pr'
    pr = dest / 'reference_failed_route.pr'
    shutil.copy2(parent_pr, pr)
    shutil.copy2(source / 'constraints_resolved.cst', dest / 'constraints_resolved.cst')
    sdc = dest / 'source/diagnostics/timing_reports.sdc'
    assert sha(sdc) == sha(source / 'source/diagnostics/timing_reports.sdc')
    json_file(dest / 'sources.json', manifest)
    settings = [line for line in (source / 'build.tcl').read_text().splitlines()
                if line.startswith(('set_device ', 'set_option '))
                and not line.startswith('set_option -inc_pnr ')]
    text = '\n'.join(settings).replace(str(source), str(dest)).replace(old, new)
    text += (f'\nadd_file {{{vg}}}\nadd_file {{{dest / "constraints_resolved.cst"}}}\n'
             f'add_file {{{sdc}}}\nset_option -inc_pnr {{{pr}}}\nrun pnr\n')
    (dest / 'build.tcl').write_text(text)
    shutil.copy2(Path(__file__), dest / 'build_driver.py')
    proof = dict(parent=str(source), candidate=True, hardware_validated=False,
                 target_programmer='2025071717', original_returncode=failure['tool_returncode'],
                 netlist_sha256=sha(vg), routed_reference_sha256=sha(pr),
                 cst_sha256=sha(dest / 'constraints_resolved.cst'),
                 sdc_sha256=sha(sdc), sources_sha256=sha(dest / 'sources.json'),
                 tcl_sha256=sha(dest / 'build.tcl'), removed_queries=[],
                 timing_constraints_changed=False, resynthesis_requested=False,
                 hypothesis='Test the failed route itself as the incremental anchor; cause unknown',
                 prepared=time.time())
    candidate.update(parent=str(source), new_synthesis_required=False,
                     incremental_hint_sha256=sha(pr), tcl_sha256=sha(dest/'build.tcl'),
                     created_unix=time.time(), resume=True)
    json_file(dest / 'sd_boot_candidate.json', candidate)
    json_file(dest / 'resume_proof.json', proof)
    print(json.dumps(dict(prepared=str(dest), netlist_sha256=sha(vg))), flush=True)
    return proof


def run(dest, trace):
    """Run once; retain failed evidence and require exact ROM initialization."""
    proof = json.loads((dest / 'resume_proof.json').read_text())
    source = Path(proof['parent'])
    new = 'console_' + dest.name
    vg = dest / f'impl/gwsynthesis/{new}.vg'
    parent_pr = source / f'impl/pnr/console_{source.name}.pr'
    assert sha(vg) == proof['netlist_sha256']
    assert sha(dest / 'reference_failed_route.pr') == proof['routed_reference_sha256']
    assert sha(dest / 'build.tcl') == proof['tcl_sha256']
    assert sha(dest / 'constraints_resolved.cst') == proof['cst_sha256']
    assert sha(dest / 'source/diagnostics/timing_reports.sdc') == proof['sdc_sha256']
    assert sha(dest / 'sources.json') == proof['sources_sha256']
    for relative, digest in json.loads((dest / 'sources.json').read_text()).items():
        assert sha(dest / 'source' / relative) == digest, relative
    command = [str(IDE / 'bin/gw_sh'), 'build.tcl']
    if trace:
        # Only process lifecycle and signals: no environment, file contents,
        # network buffers or every-syscall overhead in the routing inner loops.
        command = ['/usr/bin/strace', '-f', '--seccomp-bpf', '-ttt', '-e',
                   'trace=clone,clone3,fork,vfork,wait4,waitid,exit,exit_group', '-e', 'signal=all',
                   '-o', str(dest / 'process_trace.log'), '--'] + command
    shutil.copy2(Path(__file__), dest / 'run_driver.py')
    proof.update(started=time.time(), command=command,
                 run_driver_sha256=sha(dest / 'run_driver.py'),
                 compiler_sha256=sha(IDE / 'bin/gw_sh'))
    json_file(dest / 'resume_started.json', proof)
    with (dest / 'build.log').open('x') as log:
        result = subprocess.run(command, cwd=dest,
                                env=environment(), stdout=log, stderr=subprocess.STDOUT)
    raw = (dest / 'build.log').read_text()
    proof.update(returncode=result.returncode, finished=time.time(),
                 resynthesized='Running GowinSynthesis' in raw,
                 bitstream_generated=(dest / f'impl/pnr/{new}.fs').is_file())
    json_file(dest / 'resume_result.json', proof)
    errors = bool(re.search(r'^ERROR', raw, re.M))
    record = dict(tool_returncode=result.returncode, tool_error=errors,
                  timing_review_pending=True, hardware_validated=False,
                  rom_post_route_verified=False)
    json_file(dest / 'build_result.json', record)
    assert sha(vg) == proof['netlist_sha256'] and sha(parent_pr) == proof['routed_reference_sha256']
    reference_check()
    complete = all((dest / f'impl/pnr/{new}.{ext}').is_file() for ext in ('fs', 'vo', 'tr'))
    if result.returncode or errors or proof['resynthesized'] or not complete:
        raise RuntimeError('Incremental retry incomplete: retain logs and original failure')
    checker = Path(__file__).parent / 'r3_qualification_01/rom_check.py'
    subprocess.run([sys.executable, '-B', str(checker),
                    '--vo', str(dest / f'impl/pnr/{new}.vo'),
                    '--binary', str(dest / 'source/boot_firmware/sd_boot.bin'),
                    '--out', str(dest / 'rom_verification')], check=True)
    record['rom_post_route_verified'] = True
    json_file(dest / 'build_result.json', record)
    print(json.dumps(dict(returncode=result.returncode, timing_review_pending=True)), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--candidate', action='store_true', required=True)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--prepared', action='store_true', help='Run a previously frozen preparation')
    parser.add_argument('--trace-process', action='store_true')
    args = parser.parse_args()
    for name in (args.source, args.name):
        assert re.fullmatch(r'prodock_sd_[a-z0-9_]+', name), name
    source, dest = [ROOT / 'tang/impl' / name for name in (args.source, args.name)]
    if args.prepared:
        proof = json.loads((dest / 'resume_proof.json').read_text())
        assert Path(proof['parent']) == source and args.run
        before_build('prodock', candidate=True)
    else:
        prepare(source, dest)
    if args.run:
        run(dest, args.trace_process)


if __name__ == '__main__':
    main()
