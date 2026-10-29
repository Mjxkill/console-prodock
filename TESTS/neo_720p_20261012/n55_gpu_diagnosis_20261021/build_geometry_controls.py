#!/usr/bin/env python3
"""Prepare isolated N56r5 from exact N56r3; compile only an explicitly reviewed manifest.

Only CAMERA and FACE LOCAL_CLOCK constraints are added. No R4 placements,
synthesis, RTL/DDR/SDC/frequency changes or hardware access.
"""
import argparse
import difflib
import json
from pathlib import Path
import re
import shutil
import subprocess

from build_observer_placement import inputs as parent_integrity_inputs
from build_timing_placement import HERE, ROOT, SHA_NET, IDE, environment, sha, dump, before_build, record_build
from prove_geometry_controls import BUILD as PARENT

NAME='console_neo_n56r5'
PREPARED=HERE/'n56r5_geometry_controls'
EVIDENCE=HERE/'n56r5_control_inventory'
NETS=('u_accel/u_v1/n57378_3','u_accel/u_v1/n59467_5')
ADDITION='\n'+''.join(f'CLOCK_LOC "{net}" LOCAL_CLOCK;\n' for net in NETS)


def inputs():
    # Read-only integrity checks of the exact R3 parent; do not call the R4
    # preparation, placement proof or compilation entry point.
    record=parent_integrity_inputs()
    original=record['original_cst']
    if any(re.search(r'CLOCK_LOC\s+"'+re.escape(net)+'"',original) for net in NETS):
        raise ValueError('A proposed control already has a routing constraint')
    proof=json.loads((EVIDENCE/'geometry_controls_proof.json').read_text())
    inventory=json.loads((EVIDENCE/'inventory.json').read_text())
    if proof['passed'] is not True or inventory['compilation'] is not False:
        raise ValueError('Invalid evidence')
    docs=json.loads((EVIDENCE/'documentation_sources.json').read_text())
    for document in (proof,inventory,docs):
        for path,checksum in document['sha256'].items():
            if sha(Path(path))!=checksum:
                raise ValueError('Changed control evidence: '+path)
    expected={'CAMERA':(198,6,204),'FACE':(240,6,246)}
    for stage in ('synthesis','routed'):
        for entry in proof['stages'][stage]:
            if (entry['dff_ce_count'],entry['dsp_ce_count'],entry['load_count'])!=expected[entry['label']]:
                raise ValueError('Changed CE coverage')
            if entry['clock_pin_count']:
                raise ValueError('Refusing to constrain an actual clock')
    entries={e['net']:e for e in inventory['entries']}
    if any(not entries[n]['eligible_control_candidate'] or entries[n]['existing_constraint'] for n in NETS):
        raise ValueError('Invalid proposed control')
    files=[Path(__file__),HERE/'build_observer_placement.py',HERE/'prove_geometry_controls.py',
        HERE/'audit_gpu_control_inventory.py',EVIDENCE/'geometry_controls_proof.json',
        EVIDENCE/'inventory.json',EVIDENCE/'inventory.md',EVIDENCE/'documentation.md',
        EVIDENCE/'documentation_sources.json']
    record.update(name=NAME,candidate_cst=original+ADDITION,
        exact_added_lines=ADDITION.strip().splitlines(),new_local_controls=list(NETS),
        experiment='camera_and_face_control_routing_class',
        n56r4_placements_included=False,
        inventory_summary={k:inventory[k] for k in ('all_nonconstant_gpu_ce_nets','displayed_nets','unprotected_displayed_controls')},
        coverage=dict(camera=dict(dff_ce=198,dsp_ce=6,total=204),face=dict(dff_ce=240,dsp_ce=6,total=246)),
        limitations=['Other high-fanout controls remain unconstrained; no claim of preventing every promotion.',
                    'R3 reset4 already has LOCAL_CLOCK but routes on LW; its final route must be audited independently.',
                    'No timing exception or hardware qualification is added.'])
    record['parent_inputs_sha256'].update({str(p):sha(p) for p in files})
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare-only',action='store_true')
    mode.add_argument('--build-reviewed',metavar='MANIFEST_SHA256')
    args=parser.parse_args()
    record=inputs()
    contract=before_build('neo',candidate=True)
    record['local_regressions']=contract['local_regressions']
    if args.prepare_only:
        PREPARED.mkdir(exist_ok=False)
        (PREPARED/'neo.cst').write_text(record['candidate_cst'])
        (PREPARED/'constraints.diff').write_text(''.join(difflib.unified_diff(
            record['original_cst'].splitlines(True),record['candidate_cst'].splitlines(True),
            fromfile='N56r3/neo.cst',tofile='N56r5/neo.cst')))
        for name in ('geometry_controls_proof.json','inventory.json','documentation.md','documentation_sources.json'):
            shutil.copy2(EVIDENCE/name,PREPARED/name)
        record['prepared_sha256']={p.name:sha(p) for p in PREPARED.iterdir()}
        dump(PREPARED/'manifest.json',record)
        print(json.dumps(dict(prepared=str(PREPARED),manifest_sha256=sha(PREPARED/'manifest.json'),
            added=record['exact_added_lines']),indent=2))
        return
    if sha(PREPARED/'manifest.json')!=args.build_reviewed:
        raise ValueError('Different preparation manifest; review required')
    reviewed=json.loads((PREPARED/'manifest.json').read_text())
    expected=dict(reviewed)
    hashes=expected.pop('prepared_sha256')
    if expected!=record:
        raise ValueError('Inputs changed after review')
    for name,checksum in hashes.items():
        if sha(PREPARED/name)!=checksum:
            raise ValueError('Prepared evidence changed: '+name)
    out=ROOT/'tang/impl'/NAME
    out.mkdir(exist_ok=False)
    record_build(out,contract)
    shutil.copytree(PARENT/'source',out/'source')
    (out/'source/tang/boards/neo/neo.cst').write_text(record['candidate_cst'])
    shutil.copy2(PARENT/'console_neo.vg',out/'console_neo.vg')
    for name in ('font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex'):
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(PARENT/name,target)
    updated={str(p.relative_to(out/'source')):sha(p) for p in (out/'source').rglob('*') if p.is_file()}
    old=record['source_manifest']
    if set(updated)!=set(old) or sorted(k for k in updated if updated[k]!=old[k])!=['tang/boards/neo/neo.cst']:
        raise ValueError('Unexpected source mutation')
    dump(out/'sources.json',updated)
    observer=json.loads((PARENT/'observer_build.json').read_text())
    observer.update(source_manifest_sha256=sha(out/'sources.json'),routing_parent=str(PARENT),
        routing_parent_observer_manifest_sha256=sha(PARENT/'observer_build.json'))
    dump(out/'observer_build.json',observer)
    dump(out/'route.json',dict(parent=str(PARENT),netlist_sha256=SHA_NET,
        geometry_controls_manifest_sha256=args.build_reviewed))
    for name in ('manifest.json','geometry_controls_proof.json','constraints.diff','inventory.json'):
        shutil.copy2(PREPARED/name,out/('geometry_controls_'+name))
    shutil.copy2(PARENT/'local_controls_audit.json',out/'parent_local_controls_audit.json')
    settings=[line.replace(str(PARENT),str(out)) for line in (PARENT/'build.tcl').read_text().splitlines()
        if line.startswith(('set_device ','set_option '))]
    (out/'build.tcl').write_text('\n'.join(settings+[
        f'add_file {{{out/"console_neo.vg"}}}',f'add_file {{{out/"source/tang/boards/neo/neo.cst"}}}',
        f'add_file {{{out/"source/tang/boards/neo/neo.sdc"}}}','run pnr','']))
    with (out/'build.log').open('w') as log:
        completed=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=out,env=environment(),
            stdout=log,stderr=subprocess.STDOUT)
    if completed.returncode or re.search(r'^ERROR',(out/'build.log').read_text(),re.M):
        raise SystemExit('Routing failed')
    print(out)


if __name__=='__main__':
    main()
