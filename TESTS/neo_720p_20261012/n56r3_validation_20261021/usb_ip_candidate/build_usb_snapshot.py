#!/usr/bin/env python3
"""Synthesize an isolated Neo snapshot with the two reviewed official USB IPs.

No route or programming; the GPU controls must be resolved against the new
netlist before routing. No shared source or reference is modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from board_contract import before_build, record_build
from check_ddr_profile import audit as audit_ddr
from gowin_toolchain import IDE, environment

PARENT = ROOT / 'tang/impl/console_neo_n56_observe'
DEST = ROOT / 'tang/impl/console_neo_n57_usb35_syn'
PREPARED = HERE / 'integration_prepared'
IPS = {'tang/rtl/usb/usb_device_controller.v':
       ('usb_ip', 'usb_device_controller.vg', 'f11307d3e31560be2b04dff32b020c969f0ada2610ef232ab648fef2f198ee2a'),
       'tang/rtl/usb/usb2_0_softphy.v':
       ('usb_phy_ip', 'usb2_0_softphy.vg', '5a1eb8388ad4afe13825dd5f650a3a82628f919e337c93426b9d60e41846abaa')}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, data):
    path.write_text(json.dumps(data, indent=2)+'\n')

def inputs():
    manifest = json.loads((PARENT/'sources.json').read_text())
    actual = {str(p.relative_to(PARENT/'source')):sha(p)
              for p in (PARENT/'source').rglob('*') if p.is_file()}
    if actual != manifest:
        raise ValueError('Parent snapshot changed')
    ddr = audit_ddr(PARENT/'source', variant='neo-fifo-registers')
    if not ddr['passed']:
        raise ValueError('Original DDR5.9/300 profile must remain intact')
    result = json.loads((HERE/'generated/result.json').read_text())
    if result['status'] != 'GENERATED_NOT_INTEGRATED':
        raise ValueError('Missing isolated IP generation result')
    replacements = {}
    for path, (directory, name, digest) in IPS.items():
        ip = HERE/'generated'/directory/name
        if sha(ip) != digest or result['ips'][directory]['netlist_sha256'] != digest:
            raise ValueError('Official generated IP identity differs')
        replacements[path] = dict(source=str(ip), old_sha256=manifest[path], new_sha256=digest)
    old = (PARENT/'build.tcl').read_text()
    if old.count('\nrun all\n') != 1:
        raise ValueError('Need complete N56 source project')
    tcl = old.replace(str(PARENT), str(DEST)).replace('\nrun all\n', '\nrun syn\n')
    return dict(parent=str(PARENT), destination=str(DEST),
        parent_sources=manifest, replacements=replacements, tcl=tcl, ddr=ddr,
        source_files_sha256={str(p):sha(p) for p in
            [Path(__file__),PARENT/'build.tcl',PARENT/'sources.json',
             HERE/'generated/result.json',HERE/'generated/reviewed_manifest.json',
             ROOT/'tools/gowin_toolchain.py',IDE/'bin/gw_sh']},
        scope='Synthesis only: two USB IP substitutions; no RTL, CST, SDC or DDR change',
        later_required=['Resolve GPU local controls semantically against new synthesis',
                        'Check USB hierarchy and clock/placement constraints',
                        'Route and qualify all timing and structural checks',
                        'Board HS enumeration and GPU/Linux tests'])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only', action='store_true')
    mode.add_argument('--synthesize-reviewed')
    args = parser.parse_args()
    record = inputs()
    contract = before_build('neo', candidate=True)
    if args.prepare_only:
        PREPARED.mkdir(exist_ok=False)
        dump(PREPARED/'manifest.json', record)
        (PREPARED/'build.tcl').write_text(record['tcl'])
        print(json.dumps(dict(manifest_sha256=sha(PREPARED/'manifest.json'),
                             changed=list(IPS), stage='syn', compiler_invoked=False), indent=2))
        return
    if sha(PREPARED/'manifest.json') != args.synthesize_reviewed:
        raise ValueError('Reviewed manifest differs')
    if json.loads((PREPARED/'manifest.json').read_text()) != record:
        raise ValueError('Inputs changed since review')
    DEST.mkdir(exist_ok=False)
    record_build(DEST, contract)
    shutil.copytree(PARENT/'source', DEST/'source')
    for relative, item in record['replacements'].items():
        shutil.copy2(item['source'], DEST/'source'/relative)
    files = {str(p.relative_to(DEST/'source')):sha(p)
             for p in (DEST/'source').rglob('*') if p.is_file()}
    if set(files) != set(record['parent_sources']) or sorted(
            k for k in files if files[k] != record['parent_sources'][k]) != sorted(IPS):
        raise ValueError('Unexpected source changes')
    dump(DEST/'sources.json', files)
    for name in ('font8x16.hex', 'rtl/video/font8x16.hex', 'rtl/usbhost/usb_hid_host_rom.hex'):
        target = DEST/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PARENT/name, target)
    observer = json.loads((PARENT/'observer_build.json').read_text())
    observer.update(source_manifest_sha256=sha(DEST/'sources.json'), usb_parent=str(PARENT),
                    usb_integration_manifest_sha256=args.synthesize_reviewed)
    dump(DEST/'observer_build.json', observer)
    shutil.copy2(PREPARED/'manifest.json', DEST/'usb_integration_manifest.json')
    (DEST/'build.tcl').write_text(record['tcl'])
    with (DEST/'build.log').open('w') as log:
        completed = subprocess.run([str(IDE/'bin/gw_sh'), 'build.tcl'], cwd=DEST,
                                   env=environment(), stdout=log, stderr=log)
    log = (DEST/'build.log').read_text(errors='replace')
    if completed.returncode or re.search(r'^ERROR', log, re.M):
        raise SystemExit('USB integration synthesis failed: '+str(DEST/'build.log'))
    net = DEST/'impl/gwsynthesis/console_neo.vg'
    if not net.is_file() or net.stat().st_size < 1000:
        raise SystemExit('Complete synthesized netlist missing')
    if {str(p.relative_to(DEST/'source')):sha(p)
        for p in (DEST/'source').rglob('*') if p.is_file()} != files:
        raise SystemExit('Snapshot changed during synthesis')
    dump(DEST/'usb_synthesis_result.json', dict(status='SYNTHESIZED_NOT_ROUTED',
        netlist_sha256=sha(net), netlist=str(net), log_sha256=sha(DEST/'build.log'),
        source_manifest_sha256=sha(DEST/'sources.json'), hardware_access=False))
    print(DEST)

if __name__ == '__main__':
    main()
