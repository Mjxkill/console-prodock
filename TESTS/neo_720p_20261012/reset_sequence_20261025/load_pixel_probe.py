#!/usr/bin/env python3
"""Explicitly reviewed R16 diagnostic: one TARGET, no DDR/SD/flash writes."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
from pixel_trace import HERE, ROOT, BUILD, sha, audit_wrapper
from load_r15 import preflight as r15_preflight, BUILD as R15, BIT_SHA as R15_SHA, hw
from framebuffer_trial import GUARD, DISABLED

GUARD_R16 = GUARD.replace('PARKED_R15', 'PARKED_CPU') + DISABLED
BEFORE = '''set gpu [read_memory 0xe9001000 32 26]
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=2 || [lindex $gpu 13]!=2} {error "R15 warm-reset observation state changed; do not reconfigure"}
echo "R15_BEFORE $gpu"
'''
TARGET = '''set gpu [read_memory 0xe9001000 32 26]
echo "GPU_BEFORE $gpu"
if {[lindex $gpu 0]!=0x424c5432 || [lindex $gpu 1]!=0 || [lindex $gpu 2]!=0} {error "GPU has already executed/queued commands; initial capture ambiguous"}
foreach index {3 7 9 13 19} {
    if {[lindex $gpu $index]!=0} {error "Unexpected GPU error before first command"}
}
if {[lindex [read_memory 0xe9005000 32 1] 0]!=0x4e474442} {error "Wrong debug observer"}
echo "RAW_BEFORE [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
foreach w {0x16000000 0x12000000 0x12010000 0x00800010 0x01000100 0 0 0} {
    write_memory 0xe9001010 32 [list $w]
}
set complete 0
for {set i 0} {$i<100} {incr i} {
    set gpu [read_memory 0xe9001000 32 26]
    if {[lindex $gpu 1]==0 && [lindex $gpu 2]==1} {set complete 1; break}
    sleep 10
}
echo "GPU_AFTER $gpu"
for {set i 0} {$i<3} {incr i} {
    echo "RAW_AFTER_$i [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
    sleep 2
}
if {!$complete} {error "First TARGET did not terminate"}
echo TARGET_CAPTURE_REQUEST_COMPLETE
'''


def preflight(bit_sha, audit_sha):
    assert re.fullmatch('[0-9a-f]{64}', bit_sha)
    assert re.fullmatch('[0-9a-f]{64}', audit_sha)
    r15_preflight()
    audit = HERE/'pixel_probe_postroute_01/result.json'
    assert sha(audit) == audit_sha, 'Reviewed audit differs'
    proof = json.loads(audit.read_text())
    assert proof['observation_input_audit_passed'], 'Application/constraints audit not satisfied'
    assert proof['bitstream_sha256'] == bit_sha == sha(BUILD/'impl/pnr/ao_0.fs')
    assert not proof['missing_primary'], 'Required clock not routed as specified'
    for name, digest in proof['input_sha256'].items():
        assert sha(Path(name)) == digest, name
    # This is a bounded diagnosis, not a timing or release waiver.
    assert proof['qualification_status'] in ('FAIL', 'HARDWARE_PENDING')
    assert all(v['passed'] for k,v in proof['synthesis_audits'].items() if k != 'ddr_profile')
    assert proof['synthesis_audits']['ddr_profile']['changed'] == ['tang/rtl/board/ae350_soc.v']
    audit_wrapper()
    prior = HERE/'warm_long_01/result.json'
    assert sha(prior) == '8a8ef8c3e9936d25a38097f93c6aada29ff1582df923ba50e53ffdee89d8d829'
    assert json.loads(prior.read_text())['mire_parked']
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bit-sha', required=True)
    parser.add_argument('--audit-sha', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    proof = preflight(args.bit_sha, args.audit_sha)
    out = HERE/'pixel_probe_trial_01'
    assert not out.exists()
    if args.check_only:
        print(json.dumps(dict(ready=True, hardware_access=False, timing=proof['timing'],
                              qualification=proof['qualification_status'])))
        return
    def interrupt(sig, frame): raise KeyboardInterrupt('Signal '+str(sig))
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(sig, interrupt)
    r = dict(candidate=True, qualification=proof['qualification_status'], timing=proof['timing'],
        bitstream_sha256=args.bit_sha, audit_sha256=args.audit_sha,
        programming_attempted=False, configured=False, restored_r15=False,
        cpu_execution_requested=False, DDR_write_requested=False, SD_write_requested=False,
        flash_write_requested=False, first_gpu_command='TARGET 128x16 stride256, configuration only',
        first_command_terminated=False, GPU_qualified=False)
    def save(): (out/'result.json').write_text(json.dumps(r, indent=2)+'\n')
    def run(name, code):
        cfg=out/(name+'.tcl'); cfg.write_text(code+'\nshutdown\n')
        log=out/(name+'.log')
        hw.run_child(['/usr/local/bin/openocd', '-f', str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c', 'adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled',
            '-f', str(cfg)], log, 30)
        return log.read_text()
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps', '-C','openocd', '-C','openFPGALoader', '-C','gao_sh',
            '-C','gao_analyzer', '-C','jtagserver', '-o','pid=,comm='], capture_output=True, text=True)
        assert active.returncode == 1 and not active.stdout.strip(), active.stdout
        r['identity']=hw.usb_identity()
        assert r['identity']['neo']['path'].endswith('/3-4.4.1')
        assert r['identity']['esp']['path'].endswith('/3-4.4.2')
        out.mkdir()
        shutil.copy2(Path(__file__), out/'controller.py')
        r['started_unix']=time.time(); save()
        board=hw.Hardware(out,r)
        try:
            run('guard_r15', GUARD_R16+BEFORE)
            r['programming_attempted']=True; save()
            board.program('program_r16', BUILD/'impl/pnr/ao_0.fs', args.bit_sha)
            r['configured']=True; save()
            print('R16_CONFIGURED '+args.bit_sha, flush=True)
            text=run('first_target', GUARD_R16+TARGET+DISABLED+'echo MIRE_PARKED\n')
            r['first_command_terminated']='TARGET_CAPTURE_REQUEST_COMPLETE' in text
            r['mire_parked']='MIRE_PARKED' in text
            r['gpu']={n:[int(w,0) for w in s.split()] for n,s in re.findall(r'^GPU_(\w+) (.+)$',text,re.M)}
            r['raw']={n:[int(w,0) for w in s.split()] for n,s in re.findall(r'^RAW_(\w+) (.+)$',text,re.M)}
            before, after=r['gpu']['BEFORE'],r['gpu']['AFTER']
            assert len(before)==len(after)==26
            r['error_deltas']={name:(after[i]-before[i])&0xffffffff for name,i in
                [('transport',3),('queue_lost',7),('raster',9),('pixels_v1',13),('geometry',19)]}
            r['r15_rejection_reproduced']=r['error_deltas']['pixels_v1']==1
            r['target_accepted_without_error']=all(v==0 for v in r['error_deltas'].values())
            r['left_configured']='R16, CPU halted, internal bars; GAO initial capture pending read'
            save()
            try:
                hw.run_child(['/usr/bin/ffmpeg','-hide_banner','-loglevel','warning','-f','v4l2',
                    '-input_format','mjpeg','-video_size','1920x1080','-i','/dev/video0',
                    '-vf','select=gte(n\\,15)','-frames:v','1','-update','1','-n',str(out/'camera.jpg')],
                    out/'camera.log',15)
            except Exception as exc: r['camera_error']=repr(exc)
        except BaseException as error:
            r['error']=repr(error); save()
            if r['programming_attempted']:
                for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(sig,signal.SIG_IGN)
                try:
                    board.program('restore_r15',R15/'impl/pnr/ao_0.fs',R15_SHA)
                    r['restored_r15']=True
                    log=run('restored_guard',GUARD_R16+'echo R15_RESTORED\n')
                    r['restored_mire_parked']='R15_RESTORED' in log
                except Exception as fallback: r['fallback_error']=repr(fallback)
            raise
        finally:
            r['finished_unix']=time.time()
            r['files']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
            save()
            print(json.dumps({k:r[k] for k in ('configured','restored_r15','first_command_terminated',
                'error_deltas','r15_rejection_reproduced','error') if k in r}),flush=True)


if __name__ == '__main__': main()
