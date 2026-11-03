#!/usr/bin/env python3
"""Prepare/run the single reviewed RJC1 diagnostic, without hardware access.

R19 application, pins, clocks and timing constraints are frozen. Only the
reviewed diagnostic netlist differs. A completed route is not qualification.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CAND = HERE / 'candidate_01'
PARENT = ROOT / 'tang/impl/console_neo_n56r19_capture_ce_local'
OUT = ROOT / 'tang/impl/console_neo_rjc1_20261029_r1'
NET_SHA = '63643b24d07d549d13feff4d3f532d79dedf31669466b98c62e86c617f3a6f15'
PARENT_SHA = 'dfac41d80eecaa0b6a3c152d36d8fcdb902060cecbd450647ede445d1c8004b6'
sys.path.insert(0, str(ROOT/'tools'))
from board_contract import before_build, record_build
from gowin_toolchain import IDE, environment


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def need(ok, message):
    if not ok:
        raise RuntimeError(message)


def save(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def guards():
    delivery = json.loads((CAND/'DELIVERY.json').read_text())
    for name, digest in delivery['inputs'].items():
        need(sha(Path(name)) == digest, 'Changed reviewed input: '+name)
    need(sha(PARENT/'console_neo.vg') == PARENT_SHA, 'Changed R19 netlist')
    need(sha(CAND/'assembly_04/console_neo.vg') == NET_SHA, 'Changed RJC1 netlist')
    review = json.loads((CAND/'root_review_01/review.json').read_text())
    need(review['reviewer'] == 'Codex root', 'Root review missing')
    for name, digest in review['inputs'].items():
        need(sha(CAND/name) == digest, 'Changed root replay: '+name)
    need(json.loads((CAND/'root_review_01/primitives.json').read_text())['passed'],
         'Primitive compatibility failed')
    source_manifest = json.loads((PARENT/'sources.json').read_text())
    for name, digest in source_manifest.items():
        need(sha(PARENT/'source'/name) == digest, 'Changed R19 source: '+name)
    return before_build('neo', candidate=True)


def script():
    text = (PARENT/'build.tcl').read_text()
    need(text.count('run pnr') == 1 and text.rstrip().endswith('run pnr'),
         'Unexpected parent build script')
    need(not re.search(r'\binc_(pnr|place)\b|run\s+syn', text),
         'Changed graph must not reuse a prior incremental placement')
    return text.replace(str(PARENT), str(OUT))


def prepare():
    contract = guards()
    need(not OUT.exists(), 'Candidate output already exists')
    OUT.mkdir()
    shutil.copytree(PARENT/'source', OUT/'source')
    shutil.copy2(PARENT/'sources.json', OUT/'sources.json')
    shutil.copy2(CAND/'assembly_04/console_neo.vg', OUT/'console_neo.vg')
    for name in ('font8x16.hex', 'rtl/video/font8x16.hex', 'rtl/usbhost/usb_hid_host_rom.hex'):
        target = OUT/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PARENT/name, target)
    (OUT/'build.tcl').write_text(script())
    record_build(OUT, contract)
    inputs = ('console_neo.vg', 'sources.json', 'build.tcl',
              'source/tang/boards/neo/neo.cst', 'source/tang/boards/neo/neo.sdc',
              'font8x16.hex', 'rtl/video/font8x16.hex', 'rtl/usbhost/usb_hid_host_rom.hex')
    save(OUT/'preparation.json', dict(
        candidate=True, board='neo', parent=str(PARENT), netlist_sha256=NET_SHA,
        hardware_access=False, incremental=False, new_constraints=False,
        source_scope='Frozen R19 reference snapshot; application unchanged, RJC1 graft in VG',
        script_sha256=sha(Path(__file__)), tool=str(IDE/'bin/gw_sh'),
        tool_sha256=sha(IDE/'bin/gw_sh'),
        inputs={name: sha(OUT/name) for name in inputs},
        local_regressions=contract['local_regressions']))
    print(json.dumps(dict(prepared=str(OUT), routing=False)))


def check():
    contract = guards()
    record = json.loads((OUT/'preparation.json').read_text())
    need(record['script_sha256'] == sha(Path(__file__)), 'Builder changed')
    need(record['tool_sha256'] == sha(IDE/'bin/gw_sh'), 'Tool changed')
    for name, digest in record['inputs'].items():
        need(sha(OUT/name) == digest, 'Prepared input changed: '+name)
    need((OUT/'build.tcl').read_text() == script(), 'Options changed')
    for name, digest in json.loads((OUT/'sources.json').read_text()).items():
        need(sha(OUT/'source'/name) == digest, 'Snapshot source changed: '+name)
    return contract


def run():
    contract = check()
    with (OUT/'route.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        need(not (OUT/'route_launch.json').exists() and not (OUT/'build.log').exists(),
             'Already launched; no automatic retry')
        record_build(OUT, contract)
        started = time.time()
        with (OUT/'build.log').open('x') as log:
            child = subprocess.Popen([str(IDE/'bin/gw_sh'), 'build.tcl'], cwd=OUT,
                                     env=environment(), stdout=log, stderr=log)
            save(OUT/'route_launch.json', dict(pid=child.pid, started_unix=started,
                 netlist_sha256=NET_SHA, preparation_sha256=sha(OUT/'preparation.json'),
                 candidate=True, hardware_access=False, loaded=False))
            print('RJC1_PNR_STARTED pid='+str(child.pid), flush=True)
            try:
                rc = child.wait()
            except BaseException:
                # Preserve the process identity if this launcher is interrupted;
                # never stop another project's compiler or start a duplicate.
                save(OUT/'launcher_interrupted.json', dict(pid=child.pid, time=time.time()))
                raise
        text = (OUT/'build.log').read_text(errors='replace')
        fs = OUT/'impl/pnr/console_neo.fs'
        ok = (rc == 0 and fs.is_file() and 'Bitstream generation completed' in text
              and not re.search(r'^\s*ERROR', text, re.M))
        save(OUT/'route_result.json', dict(returncode=rc, finished_unix=time.time(),
             status='ROUTED_NOT_QUALIFIED' if ok else 'FAILED', hardware_access=False,
             loaded=False, bitstream_sha256=sha(fs) if fs.is_file() else None,
             log_sha256=sha(OUT/'build.log')))
        need(ok, 'RJC1 route failed; evidence retained, no retry')
        print('RJC1 routed; structural/timing review and hardware pending', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare', action='store_true')
    group.add_argument('--check', action='store_true')
    group.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.check:
        check()
        print('RJC1 preparation PASS')
    else:
        run()
