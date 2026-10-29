#!/usr/bin/env python3
"""Build only the reviewed N55 observation copy, after dual-board checks."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from board_contract import before_build,record_build
from check_ddr_profile import audit as audit_ddr
from gowin_toolchain import IDE,environment
from prepare_observer import transforms


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verified_manifest(build):
    manifest=json.loads((build/'sources.json').read_text())
    actual={str(f.relative_to(build/'source')):sha(f)
            for f in (build/'source').rglob('*') if f.is_file()}
    if actual!=manifest:
        raise ValueError('Changed source tree: '+str(build))
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',required=True)
    p.add_argument('--check-only',action='store_true')
    a=p.parse_args()
    if not re.fullmatch(r'console_neo_[A-Za-z0-9_]+',a.name):
        p.error('Invalid isolated Neo build name')
    reference=ROOT/'tang/impl/console_neo_n55r2'
    synthesis=ROOT/'tang/impl/console_neo_n55_selector'
    candidate=HERE/'candidate'
    parent_files=verified_manifest(reference)
    synth_files=verified_manifest(synthesis)
    files=verified_manifest(candidate)
    observation=json.loads((candidate/'observation.json').read_text())
    wanted=set(observation['changes'])
    expected={'tang/rtl/video/'+n for n in ('gpu_v1.v','gpu_geometry.v','gpu_accel.v')}
    expected|={'tang/boards/neo/'+n for n in ('console_neo.v','neo_gpu_debug.v')}
    changed={k for k in parent_files if files.get(k)!=parent_files[k]}
    if set(files)!=set(parent_files) or changed!=expected or wanted!=expected:
        raise ValueError('Observer must change exactly the five reviewed files')
    originals={name:(reference/'source'/name).read_text() for name in wanted}
    transformed=transforms(originals)
    if any((candidate/'source'/name).read_text()!=transformed[name] for name in wanted):
        raise ValueError('Observer differs from reviewed transformation')
    ddr=audit_ddr(candidate/'source',variant='neo-fifo-registers')
    if not ddr['passed']:
        raise ValueError('DDR 5.9 reference profile changed')
    sim=json.loads((HERE/'observer_sim/result.json').read_text())
    if not sim.get('passed') or len(sim.get('cases',[]))!=4 or not all(c['passed'] for c in sim['cases']):
        raise ValueError('Observer simulations must pass')
    if any(sha(Path(name))!=wanted for name,wanted in sim['sources'].items()):
        raise ValueError('Observer simulation inputs changed')
    contract=before_build('neo',candidate=True)
    out=ROOT/'tang/impl'/a.name
    if out.exists():
        raise ValueError('Build already exists')
    tcl=(synthesis/'build.tcl').read_text()
    if len(re.findall(r'^run syn$',tcl,re.M))!=1 or 'run pnr' in tcl:
        raise ValueError('Expected full frozen synthesis file list')
    if len(re.findall(r'^set_option -replicate_resources 0$',tcl,re.M))!=1:
        raise ValueError('Resource replication must remain disabled')
    listed=re.findall(r'^add_file \{([^}]+)\}$',tcl,re.M)
    for name in listed:
        rel=Path(name).relative_to(synthesis/'source')
        if str(rel) not in synth_files or str(rel) not in files:
            raise ValueError('Untracked synthesis input: '+name)
    tcl=tcl.replace(str(synthesis),str(out))
    tcl=re.sub(r'^run syn$','run all',tcl,flags=re.M)
    record=dict(reference=str(reference),synthesis_file_list=str(synthesis),
        candidate=str(candidate),compiler=str(IDE),replicate_resources=0,
        changed=sorted(changed),ddr_profile=ddr,
        source_manifest_sha256=sha(candidate/'sources.json'),
        reference_manifest_sha256=sha(reference/'sources.json'),
        synthesis_tcl_sha256=sha(synthesis/'build.tcl'),
        script_sha256=sha(Path(__file__)),prepare_script_sha256=sha(HERE/'prepare_observer.py'),
        observation_sha256=sha(candidate/'observation.json'),
        simulation_result_sha256=sha(HERE/'observer_sim/result.json'),
        constraints_unchanged={name:files[name] for name in files if name.endswith(('.sdc','.cst'))},
        stage='all',hardware_access=False,check_only=a.check_only)
    if a.check_only:
        print(json.dumps(record,indent=2));return
    out.mkdir()
    record_build(out,contract)
    shutil.copytree(candidate/'source',out/'source')
    for src in (out/'source').rglob('*.hex'):
        targets=(out/'font8x16.hex',out/'rtl/video/font8x16.hex') if src.name=='font8x16.hex' else \
                (out/'rtl/usbhost/usb_hid_host_rom.hex',) if src.name=='usb_hid_host_rom.hex' else ()
        for dest in targets:
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
    (out/'sources.json').write_text(json.dumps(files,indent=2)+'\n')
    (out/'build.tcl').write_text(tcl)
    (out/'observer_build.json').write_text(json.dumps(record,indent=2)+'\n')
    with (out/'build.log').open('w') as log:
        completed=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=out,
            env=environment(),stdout=log,stderr=subprocess.STDOUT)
    if completed.returncode or re.search(r'^ERROR',(out/'build.log').read_text(),re.M):
        raise RuntimeError('Observer compile failed: '+str(out/'build.log'))
    print(out)


if __name__=='__main__':
    main()
