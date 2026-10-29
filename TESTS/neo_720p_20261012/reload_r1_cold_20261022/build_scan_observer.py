#!/usr/bin/env python3
"""Build the tested Neo scanout observer from immutable N56r8 sources."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from prepare_scan_observer import ROOT,HERE,PARENT,CANDIDATE,SHA,MONITOR,sha,transforms

sys.path.insert(0,str(ROOT/'tools'))
from board_contract import before_build,record_build
from check_ddr_profile import audit
from gowin_toolchain import IDE,environment

def manifest(directory):
    expected=json.loads((directory/'sources.json').read_text())
    actual={str(p.relative_to(directory/'source')):sha(p) for p in (directory/'source').rglob('*') if p.is_file()}
    if actual!=expected:
        raise ValueError('Source tree drift: '+str(directory))
    return expected

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    out=ROOT/'tang/impl/console_neo_n56r9_scan_observer'
    if out.exists():
        raise ValueError('Output already exists')
    assert sha(PARENT/'impl/pnr/console_neo.fs')==SHA
    old=manifest(PARENT);new=manifest(CANDIDATE)
    observation=json.loads((CANDIDATE/'observation.json').read_text())
    assert observation['source_manifest_sha256']==sha(CANDIDATE/'sources.json')
    assert observation['script_sha256']==sha(HERE/'prepare_scan_observer.py')
    edited=transforms({n:(PARENT/'source'/n).read_text() for n in observation['changed']})
    assert all((CANDIDATE/'source'/n).read_text()==text for n,text in edited.items())
    assert (CANDIDATE/'source/tang/boards/neo/neo_scan_observe.v').read_text()==MONITOR
    assert set(new)-set(old)==set(observation['added'])
    assert {n for n in old if old[n]!=new[n]}==set(observation['changed'])
    ddr=audit(CANDIDATE/'source',variant='neo-fifo-registers')
    assert ddr['passed']
    sim=json.loads((HERE/'scan_observer_sim/result.json').read_text())
    assert sim['passed'] and all(sha(Path(n))==h for n,h in sim['sources_sha256'].items())
    contract=before_build('neo',candidate=True)
    synthesis=ROOT/'tang/impl/console_neo_n55_selector'
    syn_tcl=(synthesis/'build.tcl').read_text()
    listed=re.findall(r'^add_file \{([^}]+)\}$',syn_tcl,re.M)
    relative=[str(Path(n).relative_to(synthesis/'source')) for n in listed]
    assert len(relative)==len(set(relative)) and all(n in new for n in relative)
    options=[line.replace(str(PARENT),str(out)) for line in (PARENT/'build.tcl').read_text().splitlines()
        if line.startswith(('set_device ','set_option '))]
    tcl='\n'.join(options+[f'add_file {{{out/"source"/n}}}' for n in relative+observation['added']]+['run all',''])
    report=dict(parent=str(PARENT),parent_bitstream_sha256=SHA,
        source_manifest_sha256=sha(CANDIDATE/'sources.json'),
        observation_sha256=sha(CANDIDATE/'observation.json'),
        simulation_result_sha256=sha(HERE/'scan_observer_sim/result.json'),
        script_sha256=sha(Path(__file__)),compiler=str(IDE),
        ddr_profile=ddr,changed=observation['changed'],added=observation['added'],
        constraints_unchanged={n:new[n] for n in new if n.endswith(('.cst','.sdc'))},
        local_regressions=contract['local_regressions'],hardware_access=False)
    if args.check_only:
        print(json.dumps(report,indent=2));return
    out.mkdir()
    record_build(out,contract)
    shutil.copytree(CANDIDATE/'source',out/'source')
    shutil.copy2(CANDIDATE/'sources.json',out/'sources.json')
    for name in ('font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex'):
        target=out/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(PARENT/name,target)
    (out/'build.tcl').write_text(tcl)
    (out/'scan_observer_build.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'observer_build.json').write_text(json.dumps(report,indent=2)+'\n')
    with (out/'build.log').open('w') as log:
        result=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=out,env=environment(),stdout=log,stderr=log)
    log=(out/'build.log').read_text()
    failed=bool(result.returncode or re.search(r'^ERROR',log,re.M) or 'Bitstream generation completed' not in log)
    (out/'build_result.json').write_text(json.dumps(dict(
        status='BUILD_FAILED' if failed else 'ROUTED_NOT_QUALIFIED',returncode=result.returncode,hardware_access=False),indent=2)+'\n')
    if failed:raise SystemExit('Build failed; retained logs at '+str(out))
    print(out,flush=True)
    with (out/'qualification_automatic.log').open('x') as log:
        checked=subprocess.run([sys.executable,str(ROOT/'tools/check_neo_timing.py'),str(out)],
            cwd=ROOT,stdout=log,stderr=log,timeout=600)
    (out/'automatic_checks.json').write_text(json.dumps(dict(
        qualification_returncode=checked.returncode,hardware_access=False,
        note='Review timing, resets, clock allocation and observation mapping before any board load.'),indent=2)+'\n')
    if checked.returncode:raise SystemExit('Qualification failed; retain full reports')

if __name__=='__main__':
    main()
