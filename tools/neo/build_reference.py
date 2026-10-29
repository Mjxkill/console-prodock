#!/usr/bin/env python3
"""Compile retained Neo sources with explicit mask and board-timing options.

No IP regeneration and no access to the board. The latest installed compiler
is used, with automatic register replication disabled. Reference files remain
unchanged. All variants retain the parking firmware and DDR5.9/300 configuration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from check_ddr_profile import audit as audit_ddr
from gowin_toolchain import IDE, environment
from pixel_mask import freeze as freeze_mask
from pixel_selector import freeze as freeze_selector
from board_contract import before_build, record_build


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from-build', type=Path, required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--pixel-mask-data', action='store_true')
    p.add_argument('--pixel-selector-data', action='store_true')
    p.add_argument('--timing-reference', type=Path,
                   help='Apply the previously characterized Neo HDMI distribution and CDC origins using this timing report')
    p.add_argument('--stage', choices=('syn', 'all'), default='syn')
    a = p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_]+', a.name):
        p.error('Invalid build name')
    parent = a.from_build.resolve(strict=True)
    manifest = json.loads((parent/'sources.json').read_text())
    if any(sha(parent/'source'/rel) != wanted for rel, wanted in manifest.items()):
        raise ValueError('Changed reference sources')
    ddr = audit_ddr(parent/'source', variant='neo-fifo-registers')
    if not ddr['passed']:
        raise ValueError('Reference is not the original DDR profile with register FIFOs')
    tcl = (parent/'build.tcl').read_text()
    if not re.search(r'^run (?:all|syn)$', tcl, re.M) or 'run pnr' in tcl:
        raise ValueError('Need a complete synthesis reference')
    contract = before_build('neo', candidate=True)
    out = ROOT/'tang/impl'/a.name
    out.mkdir(exist_ok=False)
    record_build(out, contract)
    shutil.copytree(parent/'source', out/'source')
    patch = freeze_mask(out/'source') if a.pixel_mask_data else None
    selector = freeze_selector(out/'source') if a.pixel_selector_data else None
    timing = None
    if a.timing_reference:
        from neo.timing_closure import (freeze, select_hdmi_placement,
                                       zero_clock_origins, focused_hdmi_reports, PROFILE)
        freeze(out/'source', a.timing_reference)
        select_hdmi_placement(out/'source', 'sg0-c150')
        zero_clock_origins(out/'source')
        focused_hdmi_reports(out/'source')
        timing = json.loads((out/'source'/PROFILE).read_text())
    files = {str(f.relative_to(out/'source')): sha(f)
             for f in (out/'source').rglob('*') if f.is_file()}
    changed = sorted(k for k in manifest if files.get(k) != manifest[k])
    added = sorted(set(files)-set(manifest))
    wanted_changes = ['tang/rtl/video/gpu_v1.v'] if patch or selector else []
    wanted_added = ['tang/boards/neo/gpu_pixel_mask.json'] if patch else []
    if selector:
        wanted_added += ['tang/boards/neo/gpu_pixel_selector.json']
    if timing:
        wanted_changes += ['tang/boards/neo/'+name for name in ('console_neo.v', 'neo.cst', 'neo.sdc')]
        wanted_added += ['tang/boards/neo/timing_closure.json']
    if changed != sorted(wanted_changes) or added != sorted(wanted_added):
        raise ValueError('Unexpected source difference from the reference')
    for src in (parent/'source').rglob('*.hex'):
        if src.name == 'font8x16.hex':
            targets = (out/'font8x16.hex', out/'rtl/video/font8x16.hex')
        elif src.name == 'usb_hid_host_rom.hex':
            targets = (out/'rtl/usbhost/usb_hid_host_rom.hex',)
        else:
            continue
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
    tcl = tcl.replace(str(parent), str(out))
    tcl, count = re.subn(r'^set_option -replicate_resources \d+$',
                        'set_option -replicate_resources 0', tcl, flags=re.M)
    if count != 1:
        raise ValueError('Missing/ambiguous replication setting')
    tcl = re.sub(r'^run (?:all|syn)$', 'run '+a.stage, tcl, flags=re.M)
    (out/'build.tcl').write_text(tcl)
    (out/'sources.json').write_text(json.dumps(files, indent=2)+'\n')
    (out/'reference_build.json').write_text(json.dumps(dict(parent=str(parent),
        compiler=str(IDE), source_manifest_sha256=sha(parent/'sources.json'),
        reference_tcl_sha256=sha(parent/'build.tcl'), changed=changed, added=added,
        patch=patch, selector=selector, timing=timing, ddr_profile=ddr, replicate_resources=0), indent=2)+'\n')
    with (out/'build.log').open('w') as log:
        result = subprocess.run([str(IDE/'bin/gw_sh'), 'build.tcl'], cwd=out,
                                env=environment(), stdout=log, stderr=subprocess.STDOUT)
    if result.returncode or re.search(r'^ERROR', (out/'build.log').read_text(), re.M):
        raise RuntimeError('Compilation failed: '+str(out/'build.log'))
    print(out)


if __name__ == '__main__':
    main()
