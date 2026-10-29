#!/usr/bin/env python3
"""Guarded Neo-only RGB test of N56r9_route2's scanout observer; SRAM, no SD.

Requires an exact bitstream hash and fresh post-route observer evidence.
The explicit route2 recovery diagnostic retains FAIL; hold, removal,
pulse, mapping, source and board-identity checks remain mandatory.
The current board must still be the stopped R8 fallback-bars experiment.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BUILD=ROOT/'tang/impl/console_neo_n56r9_route2'
R8SHA='51841fe4ae76a7eb635a0398534f35b6c7030fa8b768d88b892fede3b1601c35'
NETSHA='0b5ea22b83faf2bae943f399bdb734dc1e66c8507310dc25e054290e24ad6157'
FRAMESHA='57413e03d1654272510868072b876627261d9f3c6fcf7ca22512681b4ffd20fe'
ROUTE2SHA='150bd72724ef7ec79c511afe2cc1c01f5976113ec00c39e8fc15e1f272731a01'
sys.path.insert(0,str(ROOT/'tools/neo'))
from load_linux import check_fpga,check_program_status

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise RuntimeError(message)

GUARD='''init
halt
echo CPU_HALTED
riscv set_enable_virt2phys off
if {[lindex [reg satp] 2]!=0 || [lindex [reg priv] 2]!=3} {error "Expected M-mode parking, no Linux"}
set pc [lindex [reg pc] 2]
if {$pc!=0x80000000 && $pc!=0x80000004} {error "CPU is not parked"}
set rom [read_memory 0x80000000 32 2]
if {[lindex $rom 0]!=0x10500073 || [lindex $rom 1]!=0xffdff06f} {error "Parking ROM differs"}
if {[lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Not Neo 1280x720 geometry"}
'''
SNAPSHOT='''proc snapshot {name} {
    if {[lindex [read_memory 0xe9006000 32 1] 0]!=0x4e474442} {error "Observer ID missing"}
    set before [lindex [read_memory 0xe900600c 32 1] 0]
    write_memory 0xe9006004 32 {1}
    set completed 0
    for {set i 0} {$i<50} {incr i} {
        sleep 1
        set status [lindex [read_memory 0xe9006004 32 1] 0]
        set sequence [lindex [read_memory 0xe900600c 32 1] 0]
        if {$status==6 && $sequence==(($before+1)&0xffffffff)} {set completed 1;break}
    }
    if {!$completed} {error "Snapshot handshake failed"}
    set words [read_memory 0xe9006020 32 8]
    set repeated [read_memory 0xe9006020 32 8]
    if {$words ne $repeated || [lindex [read_memory 0xe900600c 32 1] 0]!=$sequence || [lindex [read_memory 0xe9006004 32 1] 0]!=6} {error "Snapshot changed while being read"}
    if {([lindex $words 7]>>8)!=0x53434e} {error "Scanout snapshot signature differs"}
    echo "SNAP_$name $words"
    echo "SCAN_$name [read_memory 0xe9000000 32 32]"
}
'''

def decode(words):
    require(len(words)==8 and all(0<=w<=0xffffffff for w in words),'Invalid snapshot words')
    f,rgb=words[0],words[2]
    names=['mrst0','mrst1','request_sync0','request_sync1','reserved',
        'acknowledge','line_pending','dispatch_line','rgb_phase','rgb_start',
        'rgb_done','reader_start','reader_done','done_pending','cache_busy',
        'prefetch_active','rgb565','halfres','layers','sprites','returned_valid','fetch_valid']
    state=(rgb>>21)&7
    return dict(raw_words=words,line=f>>22,flags={name:bool(f&(1<<i)) for i,name in enumerate(names)},
        line_base=words[1],rgb_state=state,rgb_state_name={0:'IDLE',1:'SEND',2:'WAIT',3:'NEXT',4:'FINISH',5:'PIPE'}.get(state,'INVALID'),issued=(rgb>>14)&127,
        position=(rgb>>7)&127,last=rgb&127,accepted_by_queue=words[3],
        accepted_by_arbiter=words[4],returned=words[5],last_arbiter_word_address=words[6],
        signature=words[7]>>8,handshakes=words[7]&63,
        handshake_flags={name:bool(words[7]&(1<<i)) for i,name in enumerate(
            ['reset_up','data_valid','arb_ready','arb_valid','scan_ready','scan_valid'])},
        queued_not_accepted_by_arbiter=(words[3]-words[4])&0xffffffff,
        arbiter_accepted_not_returned=(words[4]-words[5])&0xffffffff)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bitstream-sha256',required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--check-only',action='store_true')
    p.add_argument('--allow-route2-recovery-diagnostic',action='store_true',
        help='User-requested parked-CPU trial of exact route2 SHA; retains setup/recovery FAIL')
    a=p.parse_args()
    require(bool(re.fullmatch('[a-f0-9]{64}',a.bitstream_sha256)),'Exact SHA required')
    q=json.loads((BUILD/'qualification.json').read_text())
    require(q['bitstream_sha256']==a.bitstream_sha256,'Wrong candidate bitstream')
    if a.allow_route2_recovery_diagnostic:
        require(a.bitstream_sha256==ROUTE2SHA and q['status']=='FAIL' and
            q['timing_checks_ns']==dict(setup=-1.848,hold=0.124,recovery=-1.418,removal=0.179),
            'Recovery experiment is limited to the reviewed route2 result')
    q,bit=check_fpga(BUILD,a.bitstream_sha256 if q['status']=='FAIL' else None,
        diagnostic_recovery_min_ns=-1.418 if a.allow_route2_recovery_diagnostic else None,
        preflight_only=a.allow_route2_recovery_diagnostic)
    require(sha(BUILD/'console_neo.vg')==NETSHA,'Synthesis netlist drift')
    require(json.loads((BUILD/'sources.json').read_text())==
        {str(f.relative_to(BUILD/'source')):sha(f) for f in (BUILD/'source').rglob('*') if f.is_file()},'Source drift')
    audit=json.loads((BUILD/'scan_observer_audit.json').read_text())
    for name,wanted in audit['sha256'].items():require(sha(Path(name))==wanted,'Stale audit: '+name)
    reset_proof=None
    if audit['passed'] is not True:
        require(audit['errors']==['Observer register function/clock/reset/init changed after synthesis'],
            'Observer audit contains an unreviewed failure')
        proof_file=BUILD/'scan_observer_reset_alias_proof.json'
        reset_proof=json.loads(proof_file.read_text())
        require(reset_proof['passed'] is True and reset_proof['all_other_register_fields_identical'] is True
            and reset_proof['reset_function']=='!vid_hrstn'
            and reset_proof['reset_alias_count']==dict(CLEAR=2,RESET=372)
            and reset_proof['original_fail_preserved']==str(BUILD/'scan_observer_audit.json')
            and reset_proof['controls']==audit['controls'] and not reset_proof['global_scanout_ce'],
            'Reset alias proof is not the reviewed Boolean equivalence')
        for name,wanted in reset_proof['sha256'].items():require(sha(Path(name))==wanted,'Stale reset proof: '+name)
    anchor=HERE/'r8_fallback_bars/result.json'
    prior=json.loads(anchor.read_text())
    require(prior['complete'] and prior['bitstream_sha256']==R8SHA and prior['cpu_left_halted']
        and prior['visual_confirmation']=='user: Les bandes sont visibles'
        and not prior['linux_running'] and not prior['sd_written'],'Expected stopped R8 fallback evidence')
    require(not (HERE/'r8_fallback_anchor_consumed.json').exists(),'R8 fallback anchor already consumed')
    frame=HERE/'r8_rgb_only/framebuffer.bin'
    require(sha(frame)==FRAMESHA and frame.stat().st_size==1843200,'Reference frame differs')
    expected=sum(struct.unpack('<460800I',frame.read_bytes()))&0xffffffff
    if a.check_only:
        print(json.dumps(dict(checks_passed=True,hardware_access=False,qualification_status=q['status'],
            bitstream_sha256=a.bitstream_sha256,expected_fetch_sum=expected,
            recovery_diagnostic=a.allow_route2_recovery_diagnostic,
            reset_alias_equivalence=reset_proof is not None),indent=2));return 0
    out=a.out.resolve()
    require(out.is_relative_to(HERE) and not any(c in str(out) for c in '{}\\\n\r'),'Invalid output path')
    out.mkdir(exist_ok=False)
    report=dict(passed=False,trial_completed=False,cpu_left_halted=False,sd_written=False,flash_written=False,
        build=str(BUILD),
        bitstream_sha256=a.bitstream_sha256,qualification_status=q['status'],
        timing_checks_ns=q['timing_checks_ns'],
        recovery_diagnostic=a.allow_route2_recovery_diagnostic,
        reset_alias_proof_sha256=sha(BUILD/'scan_observer_reset_alias_proof.json') if reset_proof else None,
        qualification_limit='Functional diagnostic only; setup and recovery violations are not waived for qualification or Linux.',
        previous_bitstream_sha256=R8SHA,framebuffer_sha256=FRAMESHA,expected_fetch_sum=expected,
        script_sha256=sha(Path(__file__)),observer_audit_sha256=sha(BUILD/'scan_observer_audit.json'))
    def openocd(name,code,timeout=120):
        script=out/(name+'.tcl');script.write_text(code)
        with (out/(name+'.log')).open('w') as log:
            subprocess.run(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
                '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(script)],
                stdout=log,stderr=log,check=True,timeout=timeout)
        return (out/(name+'.log')).read_text()
    try:
        devices=[d for d in Path('/sys/bus/usb/devices').iterdir()
            if (d/'serial').exists() and (d/'serial').read_text().strip()=='2025041420']
        require(len(devices)==1,'Neo programmer not uniquely identified')
        device=devices[0]
        require((device/'idVendor').read_text().strip()=='0403' and (device/'idProduct').read_text().strip()=='6010','Wrong programmer')
        busdev=':'.join((device/n).read_text().strip() for n in ('busnum','devnum'))
        report['programmer_busdev']=busdev
        with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            openocd('guard',GUARD+'''if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Not the recorded fallback display"}
echo R8_PARKING_CONFIRMED
shutdown
''',30)
            report['cpu_left_halted']=True
            with (HERE/'r8_fallback_anchor_consumed.json').open('x') as marker:
                json.dump(dict(bitstream_sha256=a.bitstream_sha256,out=str(out),time=time.time()),marker)
            report['cpu_left_halted']=False
            with (out/'program.log').open('w') as log:
                subprocess.run([str(Path.home()/'.local/bin/openFPGALoader'),'--busdev-num',busdev,
                    '-b','tangconsole','-m','--verbose','--freq','6000000',str(bit)],stdout=log,stderr=log,check=True,timeout=120)
            report['program_status']=check_program_status((out/'program.log').read_text())
            code='riscv expose_csrs 1994,1996,2000\n'+GUARD+'''reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display not reset"}
'''+SNAPSHOT+'snapshot DISABLED\n'
            code+=f'load_image {{{frame}}} 0x01700000 bin\nverify_image {{{frame}}} 0x01700000 bin\necho FRAME_VERIFIED\n'
            code+='''write_memory 0xe9000004 32 {0x01700000}
write_memory 0xe900006c 32 {2560}
write_memory 0xe9000030 32 {0}
write_memory 0xe9000040 32 {0}
write_memory 0xe9000008 32 {3}
write_memory 0xe900000c 32 {1}
sleep 200
snapshot RGB0
sleep 1000
snapshot RGB1
echo SCAN_OBSERVER_TRIAL_COMPLETE
shutdown
'''
            try:log=openocd('rgb_observer',code)
            finally:
                if (out/'rgb_observer.log').exists():
                    report['cpu_left_halted']='CPU_HALTED' in (out/'rgb_observer.log').read_text()
            report['snapshots']={name:decode([int(w,0) for w in words.split()]) for name,words in re.findall(r'^SNAP_(\w+) (.+)$',log,re.M)}
            before,after=(report['snapshots'][name] for name in ('RGB0','RGB1'))
            report['traffic_delta']={key:(after[key]-before[key])&0xffffffff
                for key in ('accepted_by_queue','accepted_by_arbiter','returned')}
            report['counter_scope']='Arbiter counter records enqueue acceptance, not native DDR commands. Differences are modulo 2**32 since reset.'
            samples={name:[int(w,0) for w in words.split()] for name,words in re.findall(r'^SCAN_(\w+) (.+)$',log,re.M)}
            report['samples']=samples
            first,last=samples['RGB0'],samples['RGB1']
            require(len(first)==len(last)==32,'Incomplete scanout samples')
            for key,index in [('frame_delta',6),('fetch_frame_delta',9),('underflow_delta',7)]:report[key]=(last[index]-first[index])&0xffffffff
            report['trial_completed']='SCAN_OBSERVER_TRIAL_COMPLETE' in log and 'FRAME_VERIFIED' in log
            report['passed']=(report['trial_completed'] and report['frame_delta']>0 and report['fetch_frame_delta']>0
                and report['underflow_delta']==0 and last[3]==0 and last[5]==1 and last[8]==expected)
    except Exception as error:report['error']=str(error)
    finally:
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
