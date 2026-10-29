#!/usr/bin/env python3
"""Reroute an immutable synthesized GPU stage after placement-only edits.

No synthesis netlist is edited. All sources, clock constraints and netlist
hashes are retained; changed INS_LOC commands are recorded. Does not load a
board. Intended for the regenerated HS3.5 Advance build_gpu.py stages.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

from build_gpu import ROOT, IDE, resolve_constraints, run
from gowin_toolchain import environment
from board_contract import before_build, record_build

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def placement(text):
    return dict(re.findall(r'^INS_LOC "([^"]+)" (.+);\s*$',text,re.M))

def other_constraints(text):
    return [line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith(('//','INS_LOC '))]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--name',required=True)
    p.add_argument('--candidate',action='store_true',help='Explicit unvalidated Pro Dock candidate')
    reuse=p.add_mutually_exclusive_group()
    reuse.add_argument('--incremental',action='store_true',
                   help='reuse the parent routed .pr using Gowin incremental PnR')
    reuse.add_argument('--incremental-placement',action='store_true',
                       help='reuse only the parent .p placement, reroute connections')
    p.add_argument('--cst',type=Path,default=ROOT/'tang/constr/gpu.cst')
    p.add_argument('--timing-paths',type=int,default=200,
                   help='Number of reported paths per clock group; changes no timing constraint')
    a=p.parse_args()
    if not 200<=a.timing_paths<=5000:p.error('timing-paths must be in 200..5000')
    if not re.fullmatch(r'[A-Za-z0-9_-]+',a.name):p.error('Invalid stage name')
    src=a.stage.resolve(strict=True);dst=ROOT/'tang/impl'/a.name
    if not src.is_relative_to(ROOT/'tang/impl'):p.error('Source must be a GPU build stage')
    manifest=json.loads((src/'sources.json').read_text())
    for name,digest in manifest.items():
        if sha(src/'source'/name)!=digest:raise RuntimeError('Snapshot altered: '+name)
    raw_rel='usb_phy_ip/gpu_base.cst'
    old=(src/'source'/raw_rel).read_text();new=a.cst.read_text()
    if other_constraints(old)!=other_constraints(new):
        raise RuntimeError('Only INS_LOC/comment edits are allowed; clocks and pins must match')
    before,after=placement(old),placement(new)
    changes={name:dict(before=before.get(name),after=after.get(name))
             for name in before.keys()|after.keys() if before.get(name)!=after.get(name)}
    if not changes and not (a.incremental or a.incremental_placement):raise RuntimeError('No placement changes')
    effective=(src/'source/tang/constr/gpu.cst').read_text()
    for name,change in changes.items():
        prior=f'INS_LOC "{name}" {change["before"]};'
        replacement=f'INS_LOC "{name}" {change["after"]};' if change['after'] is not None else ''
        if change['before'] is None:effective+='\n'+replacement+'\n'
        else:
            if effective.count(prior)!=1:raise RuntimeError('Ambiguous or transformed placement: '+name)
            effective=effective.replace(prior,replacement)
    old_name='console_'+src.name;new_name='console_'+a.name
    old_net=src/'impl/gwsynthesis'/(old_name+'.vg')
    net_digest=sha(old_net)
    contract=before_build('prodock',candidate=a.candidate)
    dst.mkdir(exist_ok=False)
    record_build(dst,contract)
    shutil.copytree(src/'source',dst/'source')
    (dst/'impl/gwsynthesis').mkdir(parents=True)
    net=dst/'impl/gwsynthesis'/(new_name+'.vg');shutil.copyfile(old_net,net)
    if sha(net)!=net_digest:raise RuntimeError('Netlist copy differs')
    shutil.copytree(src/'rtl',dst/'rtl')
    for name in ('usb_controller.json','usb_phy.json','build_options.json','geometry_build.json'):
        if (src/name).exists():shutil.copyfile(src/name,dst/name)
    (dst/'source'/raw_rel).write_text(new)
    constraints=dst/'source/tang/constr/gpu.cst';constraints.write_text(effective)
    for name in (raw_rel,'tang/constr/gpu.cst'):manifest[name]=sha(dst/'source'/name)
    provenance=dict(parent=str(src),ide=str(IDE),parent_manifest_sha256=sha(src/'sources.json'),
                    reused_netlist_sha256=net_digest,changes=changes,
                    scope='placement only; identical synthesized netlist; no SDC change')
    if a.timing_paths!=200:
        sdc=dst/'source/diagnostics/timing_reports.sdc'
        text=sdc.read_text()
        text,count=re.subn(r'(?<=-max_paths )\d+\b',str(a.timing_paths),text)
        if not count:raise RuntimeError('Expected timing report settings not found')
        sdc.write_text(text)
        manifest['diagnostics/timing_reports.sdc']=sha(sdc)
        provenance.update(timing_report_paths=a.timing_paths,
                          scope='identical synthesized netlist; placement/report settings only; clocks and timing exceptions unchanged')
    incremental=None
    if a.incremental or a.incremental_placement:
        suffix='.pr' if a.incremental else '.p'
        reference=src/'impl/pnr'/(old_name+suffix)
        incremental=dst/('source/diagnostics/incremental'+suffix)
        shutil.copyfile(reference,incremental)
        digest=sha(reference)
        if sha(incremental)!=digest:raise RuntimeError('Incremental reference copy differs')
        manifest['diagnostics/incremental'+suffix]=digest
        provenance['incremental_pnr' if a.incremental else 'incremental_placement']=dict(parent=str(reference),sha256=digest)
    provenance_path=dst/'source/diagnostics/reroute.json'
    provenance_path.write_text(json.dumps(provenance,indent=2)+'\n')
    manifest['diagnostics/reroute.json']=sha(provenance_path)
    tool_path=dst/'source/tools/reroute_gpu.py';shutil.copyfile(Path(__file__),tool_path)
    manifest['tools/reroute_gpu.py']=sha(tool_path)
    (dst/'sources.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Merely removing `run syn` is insufficient: Gowin automatically runs
    # synthesis when RTL files are present. A netlist-only project is needed.
    original=(src/'build.tcl').read_text().replace(str(src),str(dst)).replace(old_name,new_name)
    settings=[line for line in original.splitlines()
              if line.startswith(('set_device ','set_option '))
              and not line.startswith(('set_option -inc_place ', 'set_option -inc_pnr '))]
    if incremental is not None:
        option='inc_pnr' if a.incremental else 'inc_place'
        settings.append(f'set_option -{option} {{{incremental}}}')
    # V1.9.12 recognizes .vg by extension; its explicit `-type vg` spelling
    # is unsupported although documented by newer versions.
    tcl='\n'.join(settings)+f'\nadd_file {{{net}}}\n'
    tcl+=f'add_file {{{dst / "constraints_resolved.cst"}}}\n'
    tcl+=f'add_file {{{dst / "source/diagnostics/timing_reports.sdc"}}}\nrun pnr\n'
    (dst/'build.tcl').write_text(tcl)
    resolve_constraints(net,constraints,dst/'constraints_resolved.cst')
    env=environment()
    run([str(IDE/'bin/gw_sh'),'build.tcl'],dst,dst/'build.log',env)
    if sha(net)!=net_digest or 'Running GowinSynthesis' in (dst/'build.log').read_text():
        raise RuntimeError('Gowin resynthesized the design instead of routing the frozen netlist')
    for name in ('scanout','copy'):
        run([sys.executable,str(dst/f'source/tools/check_gpu_{name}_synthesis.py'),
             '--stage',str(dst),'--out',str(dst/f'{name}_synthesis.json')],dst,dst/f'{name}_synthesis.log')
    report=dst/f'impl/pnr/{new_name}.tr';text=report.read_text()
    slacks=[float(s) for s in re.findall(r'^Slack\s*:\s*([-\d.]+)',text,re.M)]
    tns=re.findall(r'^\s*\S+\s+(?:setup|hold)\s+([-\d.]+)\s+(\d+)\s*$',text,re.M)
    if not slacks or not tns or min(slacks)<0 or any(float(s)<0 or int(n) for s,n in tns):
        raise SystemExit(f'Timing check failed: {report}')
    bitstream=dst/f'impl/pnr/{new_name}.fs';digest=sha(bitstream)
    (dst/'bitstream.sha256').write_text(f'{digest}  {bitstream.name}\n')
    print(f'PASS timing: minimum slack {min(slacks):.3f} ns; SHA256 {digest}',flush=True)

if __name__=='__main__':main()
