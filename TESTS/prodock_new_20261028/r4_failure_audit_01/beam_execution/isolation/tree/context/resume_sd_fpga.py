#!/usr/bin/env python3
"""Retry the crashed SD candidate using its exact netlist and routed database.

Only verbose report_timing queries are omitted; clock definitions, exceptions,
pins and logic remain identical. Gowin incremental PnR may still reroute nets,
so this is a new candidate requiring full timing and hardware review.
"""
import json
from pathlib import Path
import shutil
import subprocess
import time

from build_sd_fpga import ROOT, IDE, sha, json_file, environment
from build_sd_fpga import before_build, record_build, reference_check


def main():
    source = ROOT / 'tang/impl/prodock_sd_boot_20261028_r2'
    dest = ROOT / 'tang/impl/prodock_sd_boot_20261028_r3'
    old = 'console_' + source.name
    new = 'console_' + dest.name
    failure = json.loads((source / 'build_result.json').read_text())
    assert failure['tool_returncode'] == -11
    assert not (source / f'impl/pnr/{old}.fs').exists()
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
    pr = dest / 'reference_sd_r2.pr'
    shutil.copy2(parent_pr, pr)
    shutil.copy2(source / 'constraints_resolved.cst', dest / 'constraints_resolved.cst')
    sdc = dest / 'source/diagnostics/timing_reports.sdc'
    original = sdc.read_text().splitlines(keepends=True)
    removed = [line for line in original if line.startswith('report_timing ')]
    assert len(removed) == 5
    sdc.write_text(''.join(line for line in original if not line.startswith('report_timing ')))
    assert [line for line in original if not line.startswith('report_timing ')] == sdc.read_text().splitlines(keepends=True)
    manifest['diagnostics/timing_reports.sdc'] = sha(sdc)
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
                 target_programmer='2025071717', original_returncode=-11,
                 netlist_sha256=sha(vg), routed_reference_sha256=sha(pr),
                 cst_sha256=sha(dest / 'constraints_resolved.cst'), removed_queries=removed,
                 timing_constraints_changed=False, resynthesis_requested=False,
                 hypothesis='Crash may occur while printing extra path reports; not established',
                 started=time.time())
    json_file(dest / 'resume_proof.json', proof)
    print(json.dumps(dict(prepared=str(dest), netlist_sha256=sha(vg))), flush=True)
    with (dest / 'build.log').open('x') as log:
        result = subprocess.run([str(IDE / 'bin/gw_sh'), 'build.tcl'], cwd=dest,
                                env=environment(), stdout=log, stderr=subprocess.STDOUT)
    raw = (dest / 'build.log').read_text()
    proof.update(returncode=result.returncode, finished=time.time(),
                 resynthesized='Running GowinSynthesis' in raw,
                 bitstream_generated=(dest / f'impl/pnr/{new}.fs').is_file())
    json_file(dest / 'resume_result.json', proof)
    assert sha(vg) == proof['netlist_sha256'] and sha(parent_pr) == proof['routed_reference_sha256']
    reference_check()
    if result.returncode or proof['resynthesized'] or not proof['bitstream_generated']:
        raise RuntimeError('Incremental retry incomplete: retain logs and original failure')
    print(json.dumps(dict(returncode=result.returncode, timing_review_pending=True)), flush=True)


if __name__ == '__main__':
    main()
