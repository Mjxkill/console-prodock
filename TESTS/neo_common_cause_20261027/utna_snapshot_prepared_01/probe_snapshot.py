#!/usr/bin/env python3
"""One R19 SNAPSHOT, individual/block read comparison, exact R19 rollback."""
import argparse, fcntl, hashlib, json, re, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
READONLY=HERE.parent/'utna_readonly_prepared_01'
sys.path.insert(0,str(READONLY))
import read_utna as ro
prior=ro.prior
sha=ro.sha
require=ro.require
StopRequest=prior.StopRequest
ANCHOR=READONLY/'read_20261027_231817/result.json'
ANCHOR_SHA='c27a721e34c07b438aa30216d572c9681ed6fe6d12856dd2a41b12299327de1a'
R19=prior.base.prior.t.R19/'impl/pnr/console_neo.fs'
R19_SHA=prior.base.prior.t.R19_SHA

def code():
    return prior.base.prior.check_code(0)+(HERE/'snapshot_body.tcl').read_text()

def dependencies():
    files={Path(__file__),HERE/'snapshot_body.tcl',HERE/'snapshot.tcl',HERE/'test_snapshot.py',
           HERE/'test_signals.py',HERE/'tests_result.json',HERE/'signals_result.json',ANCHOR,
           ro.ANCHOR,R19,ROOT/'tools/neo/ae350_espprog.cfg',Path('/usr/local/bin/openocd'),
           Path.home()/'.local/bin/openFPGALoader'}
    for module in tuple(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if name:
            p=Path(name).resolve()
            if p.is_file() and p.suffix=='.py' and p.is_relative_to(ROOT) and not p.is_relative_to(HERE):files.add(p)
    return sorted(files)

def local_checks(path,ready=True):
    r=json.loads(path.read_text())
    require(r['board']=='neo' and r['scope']=='R19_snapshot_individual_block_restore','Wrong scope')
    require(r['qualification_status']=='FAIL','Diagnostic is not qualification')
    require(not ready or r['hardware_ready'] is True,'Root review pending')
    require(r['controller_sha256']==sha(Path(__file__)),'Controller changed')
    require(sha(ANCHOR)==ANCHOR_SHA==r['anchor_sha256'],'Read-only anchor changed')
    a=json.loads(ANCHOR.read_text())
    require('finished_unix' in a and a['observations_completed'] and not a['signals_received'],'Anchor incomplete')
    require(a['r19_sha256']==R19_SHA==r['r19_sha256']==sha(R19),'Wrong R19')
    require(a['MMIO_writes']==a['FPGA_writes']==a['CPU_resume_commands']==0,'Anchor was not read-only')
    require(a['observation']['control_fresh_before_after'] and a['observation']['initial_bank_all_zero'],'Fresh state not established')
    require(a['anchor_sha256']==ro.ANCHOR_SHA==sha(ro.ANCHOR),'R19 restoration anchor changed')
    for anchor in (ANCHOR,ro.ANCHOR):
        old=json.loads(anchor.read_text())
        for name,digest in old['files'].items():require(sha(anchor.parent/name)==digest,'Anchor evidence changed: '+name)
    old=json.loads(ro.ANCHOR.read_text())
    require(old['left_startup_verified'] and old['last_programmed_sha256']==R19_SHA,'Missing R19 restoration')
    require(all(str(p.resolve()) in r['proof_files'] for p in dependencies()),'Missing dependency')
    for name,digest in r['proof_files'].items():require(sha(Path(name))==digest,'Dependency changed: '+name)
    text=(HERE/'snapshot.tcl').read_text();require(text==code(),'Tcl changed')
    require(re.findall(r'write_memory\s+(0x[0-9a-f]+)\s+32\s+\{([^}]+)\}',text)==[('0xe900200c','2')],'Unexpected observer write')
    require(not re.search(r'\b(load_image|dump_image|mww|mwh|mwb|resume|irscan|drscan|reset)\b',text),'Forbidden Tcl operation')
    for name in ('tests_result.json','signals_result.json'):
        t=json.loads((HERE/name).read_text());require(t['passed'] is True and not t['hardware_access'],'Missing offline proof')
    return r,text

def parse(raw):
    rows=re.findall(r'^SNAPSHOT_READ (\d+) (pre|post) (\S+) (\S+)\r?$',raw,re.M)
    addresses=[0xe9002000,0xe9002004,0xe9002008,0xe9002040,0xe9002044,0xe9002048]
    expected=[(str(p),side,addr) for p in range(2) for side in ('pre','post') for addr in addresses]
    require(len(rows)==len(expected),'Incomplete individual read capture')
    individual=[]
    for (p,side,addr,v),want in zip(rows,expected):
        require((p,side,int(addr,0))==want,'Read order mismatch')
        value=int(v,0);require(0<=value<=0xffffffff,'Invalid word')
        individual.append(dict(passage=int(p),side=side,address=int(addr,0),value=value))
    blocks=[]
    for p,count,words in re.findall(r'^SNAPSHOT_BLOCK (\d+) (3|32) (.+)\r?$',raw,re.M):
        values=[int(v,0) for v in words.split()]
        require(len(values)==int(count) and all(0<=v<=0xffffffff for v in values),'Wrong block length/value')
        blocks.append(dict(passage=int(p),count=int(count),values=values))
    require([(b['passage'],b['count']) for b in blocks]==[(0,3),(0,32),(1,3),(1,32)],'Incomplete blocks')
    require(re.search(r'^SNAPSHOT_ACK 1\r?$',raw,re.M),'Missing ACK1')
    require(len(re.findall(r'^SNAPSHOT_WRITE 2\r?$',raw,re.M))==1,'Not exactly one SNAPSHOT')
    require(re.search(r'^SNAPSHOT_READS_DONE\r?$',raw,re.M),'Capture incomplete')
    controls=re.findall(r'^SNAPSHOT_CONTROL (\w+) (.+)\r?$',raw,re.M)
    require([x[0] for x in controls]==['INITIAL','ACK','PASS0','PASS1'],'Missing controls')
    require([int(v,0) for v in controls[0][1].split()]==[0x55544e41,0,0],'Initial control not fresh')
    require(all([int(v,0) for v in s.split()]==[0x55544e41,0,1] for _,s in controls[1:]),'Control changed')
    headers=[];errors=[]
    for p in range(2):
        for side in ('pre','post'):
            values=[x['value'] for x in individual if x['passage']==p and x['side']==side]
            require(values[:3]==[0x55544e41,0,1],'Individual control changed')
            headers.append(dict(source=f'{p}_{side}_individual',words=values[3:]))
    for b in blocks:headers.append(dict(source=f"{b['passage']}_block{b['count']}",words=b['values'][:3]))
    for h in headers:
        if h['words']!=[0x55544e41,1,2]:errors.append('Header differs: '+h['source'])
    if blocks[1]['values']!=blocks[3]['values']:errors.append('32-word bank differs between repetitions')
    return dict(individual=individual,blocks=blocks,headers=headers,protocol_errors=errors,
                protocol_passed=not errors,capture_complete=True,expected_header=[0x55544e41,1,2])

def execute(io,report,save,text,stop=None):
    stop=stop if stop is not None else StopRequest()
    report['signals_received']=stop.received
    touched=False
    try:
        stop.checkpoint()
        io.observe('r19_initial_guard',prior.restoration_guard(),'RESTORED_UTNA_FRESH')
        stop.checkpoint()
        report['baseline_verified']=True
        save()
        stop.checkpoint()
        touched=True
        stop.checkpoint()
        raw=io.observe('r19_snapshot',text,'SNAPSHOT_READS_DONE')
        stop.checkpoint()
        report['observation']=parse(raw)
        save()
        require(report['observation']['protocol_passed'],'SNAPSHOT data contract failed: '+repr(report['observation']['protocol_errors']))
        report['observations_completed']=True
        save()
        stop.checkpoint()
    except BaseException as exc:
        report['error']=repr(exc)
        try:save()
        except BaseException as log_error:report.setdefault('error_log_errors',[]).append(repr(log_error))
        raise
    finally:
        if touched:
            def cleanup_save():
                try:save()
                except BaseException as exc:report.setdefault('cleanup_log_errors',[]).append(repr(exc))
            if hasattr(io,'save'):io.save=cleanup_save
            report['restore_attempted']=True
            cleanup_save()
            try:
                io.program('restore_r19',R19,R19_SHA)
                io.observe('restored_guard',prior.restoration_guard(),'RESTORED_UTNA_FRESH')
                report.update(left_startup_verified=True,left_state='R19 restored, parked CPU, fresh GPU/NCP/UTNA, internal bars')
                cleanup_save()
            except BaseException as exc:
                report['restore_error']=repr(exc)
                cleanup_save()
                raise
    try:stop.checkpoint()
    except KeyboardInterrupt as exc:
        report['error']=repr(exc)
        try:save()
        except BaseException as log_error:report.setdefault('error_log_errors',[]).append(repr(log_error))
        raise

def main():
    if sys.flags.optimize:raise SystemExit('assertions disabled: refusing to run')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',type=Path,required=True);p.add_argument('--check-only',action='store_true');args=p.parse_args()
    path=args.review.resolve();require(path.is_relative_to(HERE),'Review must be in prepared folder')
    review,text=local_checks(path,not args.check_only)
    if args.check_only:print(json.dumps(dict(preflight_passed=True,hardware_access=False,hardware_ready=review['hardware_ready'])));return
    stop=StopRequest();stop.install();stop.checkpoint()
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True,timeout=5)
        require(active.returncode==1 and not active.stdout.strip(),'Another debug tool is active')
        stop.checkpoint();identity=prior.base.prior.hw.usb_identity();ro.check_identity(identity);stop.checkpoint()
        out=HERE/('snapshot_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir(exist_ok=False)
        (out/'controller_used.py').write_bytes(Path(__file__).read_bytes())
        report=dict(board='neo',qualification_status='FAIL',hardware_review_sha256=sha(path),anchor_sha256=ANCHOR_SHA,
                    r19_sha256=R19_SHA,last_programmed_sha256=R19_SHA,left_startup_verified=False,
                    observations_completed=False,identity=identity,started_unix=time.time(),observer_commands=[2],
                    observer_write_address=0xe900200c,observer_mutation=True,R21r2_programming=False,
                    UART_commands=False,DDR_written=False,GPU_commands=False,SD_written=False,flash_written=False,
                    Linux_loaded=False,CPU_resume_command=False,CPU_ROM_restart_possible=True)
        def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        save()
        try:execute(prior.base.prior.IO(out,report,save),report,save,text,stop)
        finally:
            report['finished_unix']=time.time();report['files']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
            save();print(json.dumps(dict(output=str(out),**report)),flush=True)
if __name__=='__main__':main()
