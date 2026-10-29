#!/usr/bin/env python3
"""R19 controlled experiment: one CE routing constraint, identical R18r1 logic."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import build_capture as b
from board_trial import preflight

HERE=b.HERE
SRC=b.ROOT/'tang/impl/console_neo_n56r18r1_local_capture'
DEST=b.ROOT/'tang/impl/console_neo_n56r19_capture_ce_local'
NET='u_accel/u_v1/u_pixels/n37565_3'
RULE='CLOCK_LOC "'+NET+'" LOCAL_CLOCK;'

def evidence():
    preflight()
    trial=HERE/'repeat_capture_01/result.json';r=json.loads(trial.read_text())
    assert r['measurement_complete'] and not r['fpga_reloaded'] and len(r['results'])==8
    for name,digest in r['files'].items():assert b.sha(trial.parent/name)==digest,name
    for result in r['results']:
        at=result['capture']['at'];after=result['capture']['after']
        assert result['capture']['complete'] and result['capture']['finding']=='CAPTURE_ENABLE_ABSENT'
        assert at['start']==at['idle']==1 and at['ce']==at['reset']==0
        assert at['d']==result['opcode'] and after['q']==0 and result['v1_rejected_delta']==1
    # The observed net is the output of START & IDLE, not an inferred name.
    text=(SRC/'impl/pnr/console_neo.vo').read_text()
    pattern=r'LUT2 \\u_accel/u_v1/u_pixels/n37565_s0\s+\((.*?)\);\s*defparam \\u_accel/u_v1/u_pixels/n37565_s0\s+\.INIT=4\x27h8;'
    m=re.search(pattern,text,re.S);assert m
    normalize=lambda s:re.sub(r'\s+','',s).replace('\\','')
    pins={k:normalize(v) for k,v in re.findall(r'\.(\w+)\(([^()]+)\)',m[1])}
    assert pins==dict(I0='u_accel/u_v1/shader_start',I1='u_accel/u_v1/u_pixels/state[0]',F=NET)
    assert re.search(r'^\s*'+re.escape(NET)+r'\s*\|\s*LW\s*\|', (SRC/'impl/pnr/console_neo.rpt.txt').read_text(),re.M)
    return trial

def prepare():
    trial=evidence();contract=b.before_build('neo',candidate=True)
    cst=SRC/'source/tang/boards/neo/neo.cst';old=cst.read_text()
    assert not re.search(r'^\s*(?:CLOCK_LOC|NET_LOC) "'+re.escape(NET)+'"',old,re.M)
    DEST.mkdir(exist_ok=False);shutil.copytree(SRC/'source',DEST/'source')
    for n in ('console_neo.vg','font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex'):
        (DEST/n).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SRC/n,DEST/n)
    (DEST/'source/tang/boards/neo/neo.cst').write_text(old+'\n// R19: measured missing START & IDLE capture-enable; one-net physical comparison.\n'+RULE+'\n')
    (DEST/'build.tcl').write_text((SRC/'build.tcl').read_text().replace(str(SRC),str(DEST)))
    original=json.loads((SRC/'sources.json').read_text());current=b.manifest(DEST/'source')
    assert set(original)==set(current)
    assert [n for n in original if original[n]!=current[n]]==['tang/boards/neo/neo.cst']
    b.save(DEST/'sources.json',current)
    assert b.sha(DEST/'console_neo.vg')==b.sha(SRC/'console_neo.vg')
    b.record_build(DEST,contract)
    docs=Path('/home/michael/gowin/IDE/doc/EN/SUG1018-1.7E_Arora Ⅴ Design Physical Constraints User Guide.pdf')
    b.save(DEST/'experiment.json',dict(candidate=True,loaded=False,gao=False,parent=str(SRC),
        hypothesis='The measured absent CE may depend on its physical route. Change only its CLOCK_LOC; retain the observer.',
        not_demonstrated='No general LW erratum or repaired GPU claim before A/B hardware comparison.',
        netlist_sha256=b.sha(DEST/'console_neo.vg'),rule=RULE,same_CST_prefix=True,
        source_changes=['tang/boards/neo/neo.cst'],same_SDC=True,same_PNR_options=True,
        source_RTL_changed=False,common_sources_changed=False,
        evidence=str(trial),evidence_sha256=b.sha(trial),builder_sha256=b.sha(Path(__file__)),
        constraint_document=dict(path=str(docs),sha256=b.sha(docs),section='2.7, printed pages 14-15',
            semantics='LOCAL_CLOCK routes the selected net on local non-clock wiring.'),
        mapped_integration_proof=str(HERE/'integration_format_02/result.json'),
        mapped_integration_proof_sha256=b.sha(HERE/'integration_format_02/result.json'),
        inputs={n:b.sha(DEST/n) for n in ('console_neo.vg','sources.json','build.tcl','source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc')},
        pending=['Final route must prove the CE is absent from global/LW allocations.',
                 'Re-audit observer delays and whole-design timing; keep all failures explicit.',
                 'Repeat the same capture protocol and error counters on Neo only.',
                 'Other scanout, DDR and GPU failures remain separate until measured.']))
    shutil.copy2(Path(__file__),DEST/'route_local_ce.py')
    print('Prepared '+str(DEST),flush=True)

def route():
    evidence();r=json.loads((DEST/'experiment.json').read_text())
    assert r['builder_sha256']==b.sha(Path(__file__))
    for n,h in r['inputs'].items():assert b.sha(DEST/n)==h,n
    assert b.manifest(DEST/'source')==json.loads((DEST/'sources.json').read_text())
    proof=Path(r['mapped_integration_proof']);assert b.sha(proof)==r['mapped_integration_proof_sha256']
    b.verify_proof(proof);assert json.loads(proof.read_text())['netlist_sha256']==r['netlist_sha256']
    b.record_build(DEST,b.before_build('neo',candidate=True))
    tool=b.PARENT/'public_license_runtime/bin/gw_sh';assert b.sha(tool)==b.sha(b.IDE/'bin/gw_sh')
    with (DEST/'route.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);assert not (DEST/'route_launch.json').exists()
        started=time.time()
        with (DEST/'build.log').open('x') as log:
            child=subprocess.Popen([str(tool),'build.tcl'],cwd=DEST,env=b.environment(),stdout=log,stderr=log)
            b.save(DEST/'route_launch.json',dict(pid=child.pid,started_unix=started,tool=str(tool),tool_sha256=b.sha(tool),candidate=str(DEST),loaded=False,gao=False))
            print('R19_CE_COMPARISON_ROUTE_STARTED pid='+str(child.pid),flush=True);rc=child.wait()
        log=(DEST/'build.log').read_text();ok=rc==0 and not re.search(r'^ERROR',log,re.M) and 'Bitstream generation completed' in log
        b.save(DEST/'route_result.json',dict(returncode=rc,status='ROUTED_NOT_QUALIFIED' if ok else 'ROUTING_FAILED',started_unix=started,finished_unix=time.time(),loaded=False))
        if not ok:raise SystemExit('Routing failed; evidence retained')
        print('R19 routed; post-route comparison and hardware still pending',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--route',action='store_true');a=p.parse_args()
    route() if a.route else prepare()
