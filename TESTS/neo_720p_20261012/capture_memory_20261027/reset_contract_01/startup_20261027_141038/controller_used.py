#!/usr/bin/env python3
"""One reviewed Neo SRAM startup trial; no UART command or DDR/GPU write."""
import argparse
import fcntl
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE.parent))
import warm_mode1_trial as prior

BUILD=ROOT/'tang/impl/console_neo_n56r21r2_resetqual_coupled'
NET='4eace9a4feabe65a1a47e726500b23dd256b4edc3ea4f037b36a9d4d14e08ae4'
ANCHOR=HERE.parent/'warm_mode1_20261027_094017/result.json'
ANCHOR_SHA='d7133f11f50b7c2540c436dc7e6cc42de0185721cc5441eeaaa48c2be077fd87'


def dependency_files():
    # Bind the imported legacy guards/IO, not just this small orchestrator.
    files={ROOT/'tools/neo/ae350_espprog.cfg',Path('/usr/local/bin/openocd'),
           Path.home()/'.local/bin/openFPGALoader',Path('/usr/bin/ffmpeg')}
    for module in tuple(sys.modules.values()):
        name=getattr(module,'__file__',None)
        if name:
            path=Path(name).resolve()
            if path.is_file() and path.suffix=='.py' and path.is_relative_to(ROOT) and not path.is_relative_to(HERE):
                files.add(path)
    return sorted(files)


def local_checks(review_path):
    review=json.loads(review_path.read_text())
    assert review['board']=='neo' and review['scope']=='parked_startup_only'
    assert review['hardware_ready'] is True
    assert review['controller_sha256']==prior.t.sha(Path(__file__))
    assert review['netlist_sha256']==NET and review['parent_r19_sha256']==prior.t.R19_SHA
    assert Path(review['build']).resolve()==BUILD
    assert prior.t.sha(BUILD/'console_neo.vg')==NET
    bit=BUILD/'impl/pnr/console_neo.fs'
    assert prior.t.sha(bit)==review['bitstream_sha256']
    assert prior.t.sha(prior.t.R19/'impl/pnr/console_neo.fs')==prior.t.R19_SHA
    assert prior.t.sha(ANCHOR)==ANCHOR_SHA
    anchor=json.loads(ANCHOR.read_text())
    assert anchor['left_startup_verified'] and anchor['last_programmed_sha256']==prior.t.R19_SHA
    for name,h in anchor['files'].items():assert prior.t.sha(ANCHOR.parent/name)==h,name
    dependencies=dependency_files()
    assert all(str(path) in review['proof_files'] for path in dependencies),'Missing hardware IO/config dependency in review'
    for path,h in review['proof_files'].items():assert prior.t.sha(Path(path))==h,path
    code=prior.check_code(0)
    assert not any(s in code for s in ('write_memory','load_image','dump_image','resume','reset halt','reset run'))
    return review,bit


def execute(io,report,save,bit):
    touched=False
    try:
        io.observe('r19_initial_guard',prior.check_code(0),'WARM_CHECK_0')
        report['baseline_startup_verified']=True
        save()
        io.camera('r19_before')
        touched=True
        io.program('program_coupled',bit,report['candidate_sha256'])
        io.camera('coupled_before_dmi')
        io.observe('coupled_startup',prior.check_code(0),'WARM_CHECK_0')
        report.update(candidate_startup_verified=True,left_startup_verified=True,
                      left_state='Coupled candidate, CPU halted in parking ROM, fresh GPU/NCP, internal bars selected; visual review pending')
        save()
    except BaseException as exc:
        report['error']=repr(exc)
        save()
        if touched:
            report['restore_attempted']=True
            # Only the bounded fallback ignores further interruption signals.
            for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,signal.SIG_IGN)
            try:
                io.program('restore_r19',prior.t.R19/'impl/pnr/console_neo.fs',prior.t.R19_SHA)
                io.observe('restored_guard',prior.check_code(0),'WARM_CHECK_0')
                report.update(left_startup_verified=True,
                              left_state='R19 restored, CPU halted, fresh GPU/NCP, internal bars selected')
                save()
                io.camera('r19_restored')
            except BaseException as fallback:
                report['fallback_error']=repr(fallback)
                save()
        raise


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--review',required=True,type=Path)
    ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args();review_path=args.review.resolve()
    assert review_path.is_relative_to(HERE)
    review,bit=local_checks(review_path)
    if args.check_only:
        print(json.dumps(dict(ready=True,hardware_access=False,bitstream_sha256=review['bitstream_sha256'])))
        return
    def interrupt(sig,frame):raise KeyboardInterrupt('Signal '+str(sig))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,interrupt)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
                               '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True,timeout=5)
        assert active.returncode==1 and not active.stdout.strip(),'Another debug tool is active'
        identity=prior.hw.usb_identity()
        assert identity['neo']['serial']=='2025041420' and identity['neo']['path'].endswith('/3-4.4.1')
        assert identity['esp']['path'].endswith('/3-4.4.2')
        out=HERE/('startup_'+time.strftime('%Y%m%d_%H%M%S'))
        out.mkdir(exist_ok=False)
        (out/'controller_used.py').write_bytes(Path(__file__).read_bytes())
        report=dict(board='neo',candidate=True,qualification_status=review['qualification_status'],
                    root_review_sha256=prior.t.sha(review_path),anchor_sha256=ANCHOR_SHA,
                    candidate_sha256=review['bitstream_sha256'],last_programmed_sha256=prior.t.R19_SHA,
                    left_startup_verified=False,candidate_startup_verified=False,
                    identity=identity,jtag_khz=100,started_unix=time.time(),
                    UART_commands=False,DDR_written=False,GPU_commands=False,SD_written=False,
                    flash_written=False,Linux_loaded=False,CPU_resume_command=False,
                    CPU_ROM_restart_possible=True)
        def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        save()
        try:
            execute(prior.IO(out,report,save),report,save,bit)
        finally:
            report['finished_unix']=time.time()
            report['files']={p.name:prior.t.sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
            save()
            print(json.dumps(dict(output=str(out),**report)),flush=True)


if __name__=='__main__':main()
