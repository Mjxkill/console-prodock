#!/usr/bin/env python3
"""Frozen R1 with only the HDMI DCE placement SG[0] -> PG[0].

No RTL, netlist, DDR, SDC, reset placement, USB or frequency change.
Metadata records the new intended site; all eight primary-clock requirements
remain mandatory. No hardware is accessed and no prior PASS is copied.
"""
import argparse
import difflib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent/'n55_gpu_diagnosis_20261021'))
from build_timing_placement import (PARENT, SHA_BIT, SHA_NET, SHA_SDC, sha,
    dump, inputs as parent_inputs, before_build, record_build, IDE, environment)

NAME = 'console_neo_n56r7_hdmi_pg0'
OUT = ROOT/'tang/impl'/NAME
PREPARED = HERE/'n56r7_hdmi_pg0_prepared'


def inputs():
    p = parent_inputs()
    assert sha(PARENT/'impl/pnr/console_neo.fs') == SHA_BIT
    old = 'INS_LOC "u_video_fast" SG[0];'
    new = 'INS_LOC "u_video_fast" PG[0];'
    assert p['original_cst'].count(old) == 1
    cst = p['original_cst'].replace(old, new, 1)
    profile_path = Path('tang/boards/neo/timing_closure.json')
    profile = json.loads((PARENT/'source'/profile_path).read_text())
    assert profile['hdmi_dce_site'] == 'SG[0]'
    assert profile['hdmi_reset_column'] == 160
    assert len(profile['required_primary_clocks']) == 8
    profile['hdmi_dce_site'] = 'PG[0]'
    evidence = {}
    for directory, bitsha, visual in [
        ('hdmi_dce_trial', '2043ca8b654108f1dd5abbe93559c564f73ad7eea3cdf47957d8a5c9252070d5', 'user: Oui, la mire est visible'),
        ('hdmi_sg0_trial', 'bf5070142d249704967d23d463a96dd15ff8ff5ce020d950dab62244c946cbcd', 'user: Non, aucun signal'),
        ('hdmi_auto_return_trial', '2043ca8b654108f1dd5abbe93559c564f73ad7eea3cdf47957d8a5c9252070d5', 'user: Oui, la mire est revenue'),
    ]:
        path = HERE/directory/'result.json'
        item = json.loads(path.read_text())
        assert item['programmed'] and item['bitstream_sha256'] == bitsha
        assert item['visual_confirmation'] == visual
        evidence[str(path)] = sha(path)
    settings = [line.replace(str(PARENT), str(OUT))
        for line in (PARENT/'build.tcl').read_text().splitlines()
        if line.startswith(('set_device ', 'set_option '))]
    assert not any('inc_place' in l or 'inc_pnr' in l for l in settings)
    tcl = '\n'.join(settings + [f'add_file {{{OUT/"console_neo.vg"}}}',
        f'add_file {{{OUT/"source/tang/boards/neo/neo.cst"}}}',
        f'add_file {{{OUT/"source/tang/boards/neo/neo.sdc"}}}', 'run pnr', ''])
    return dict(parent=str(PARENT), parent_bitstream_sha256=SHA_BIT,
        name=NAME, source_manifest=p['source_manifest'],
        parent_inputs_sha256=p['parent_inputs_sha256'],
        original_cst=p['original_cst'], candidate_cst=cst,
        profile_path=str(profile_path), candidate_profile=profile,
        candidate_tcl=tcl, evidence_sha256=evidence,
        changed_source_files=['tang/boards/neo/neo.cst', str(profile_path)],
        netlist_sha256=SHA_NET, sdc_sha256=SHA_SDC,
        unchanged_local_controls=p['unchanged_local_controls'],
        ddr_profile=p['ddr_profile'], hardware_access=False,
        limits=['Recomputes placement/routing of the whole design.',
                'HDMI-only board evidence does not qualify full GPU or DDR.',
                'Full STA, clocks, reset and local-control audits required.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only', action='store_true')
    mode.add_argument('--build-reviewed', metavar='MANIFEST_SHA256')
    args = parser.parse_args()
    record = inputs()
    contract = before_build('neo', candidate=True)
    record['local_regressions'] = contract['local_regressions']
    if args.prepare_only:
        PREPARED.mkdir(exist_ok=False)
        (PREPARED/'neo.cst').write_text(record['candidate_cst'])
        dump(PREPARED/'timing_closure.json', record['candidate_profile'])
        (PREPARED/'build.tcl').write_text(record['candidate_tcl'])
        (PREPARED/'constraints.diff').write_text(''.join(difflib.unified_diff(
            record['original_cst'].splitlines(True), record['candidate_cst'].splitlines(True),
            fromfile='N56r1/neo.cst', tofile='N56r7/neo.cst')))
        record['prepared_sha256'] = {p.name: sha(p) for p in PREPARED.iterdir()}
        dump(PREPARED/'manifest.json', record)
        print(json.dumps(dict(prepared=str(PREPARED), manifest_sha256=sha(PREPARED/'manifest.json')), indent=2))
        return
    assert sha(PREPARED/'manifest.json') == args.build_reviewed
    reviewed = json.loads((PREPARED/'manifest.json').read_text())
    hashes = reviewed.pop('prepared_sha256')
    assert reviewed == record, 'Inputs changed since preparation'
    for name, checksum in hashes.items():
        assert sha(PREPARED/name) == checksum
    OUT.mkdir(exist_ok=False)
    record_build(OUT, contract)
    shutil.copytree(PARENT/'source', OUT/'source')
    (OUT/'source/tang/boards/neo/neo.cst').write_text(record['candidate_cst'])
    dump(OUT/'source'/record['profile_path'], record['candidate_profile'])
    shutil.copy2(PARENT/'console_neo.vg', OUT/'console_neo.vg')
    for name in ('font8x16.hex', 'rtl/video/font8x16.hex', 'rtl/usbhost/usb_hid_host_rom.hex'):
        target = OUT/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PARENT/name, target)
        assert sha(target) == sha(PARENT/name)
    assert sha(OUT/'console_neo.vg') == SHA_NET
    updated = {str(p.relative_to(OUT/'source')): sha(p)
        for p in (OUT/'source').rglob('*') if p.is_file()}
    old = record['source_manifest']
    assert set(updated) == set(old)
    assert sorted(k for k in updated if updated[k] != old[k]) == record['changed_source_files']
    assert sha(OUT/'source/tang/boards/neo/neo.sdc') == SHA_SDC
    dump(OUT/'sources.json', updated)
    observer = json.loads((PARENT/'observer_build.json').read_text())
    observer.update(source_manifest_sha256=sha(OUT/'sources.json'), routing_parent=str(PARENT),
        routing_parent_observer_manifest_sha256=sha(PARENT/'observer_build.json'))
    dump(OUT/'observer_build.json', observer)
    dump(OUT/'route.json', dict(parent=str(PARENT), netlist_sha256=SHA_NET,
        hdmi_pg0_manifest_sha256=args.build_reviewed))
    for path in PREPARED.iterdir():
        shutil.copy2(path, OUT/('hdmi_pg0_'+path.name))
    (OUT/'build.tcl').write_text(record['candidate_tcl'])
    with (OUT/'build.log').open('w') as log:
        done = subprocess.run([str(IDE/'bin/gw_sh'), 'build.tcl'], cwd=OUT,
            env=environment(), stdout=log, stderr=subprocess.STDOUT)
    log = (OUT/'build.log').read_text()
    failed = bool(done.returncode or re.search(r'^ERROR', log, re.M)
                  or 'Bitstream generation completed' not in log)
    dump(OUT/'route_result.json', dict(status='ROUTING_FAILED' if failed else 'ROUTED_NOT_QUALIFIED',
        child_returncode=done.returncode, manifest_sha256=args.build_reviewed, hardware_access=False))
    if failed:
        raise SystemExit('Routing failed; retain diagnostic log')
    print(OUT)


if __name__ == '__main__':
    main()
