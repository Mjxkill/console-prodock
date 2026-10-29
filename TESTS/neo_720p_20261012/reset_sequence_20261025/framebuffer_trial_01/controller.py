#!/usr/bin/env python3
"""Bounded parked-CPU DDR/scanout trial on exact R15; restore bars on failure."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import random
import re
import signal
import struct
import subprocess
import time

from load_r15 import HERE, ROOT, COLD, BUILD, BIT_SHA, preflight, hw

FRAME = COLD / 'r8_rgb_only/framebuffer.bin'
FRAME_SHA = '57413e03d1654272510868072b876627261d9f3c6fcf7ca22512681b4ffd20fe'
ANCHOR = HERE / 'cpu_registers_02/result.json'
GUARD = '''init
halt
riscv set_enable_virt2phys off
set registers [get_reg -force {pc priv satp}]
set pc [dict get $registers pc]
if {($pc!=0x80000000 && $pc!=0x80000004) || [dict get $registers priv]!=3 || [dict get $registers satp]!=0} {error "Expected parked CPU in M mode, no Linux"}
set rom [read_memory 0x80000000 32 2]
if {[lindex $rom 0]!=0x10500073 || [lindex $rom 1]!=0xffdff06f} {error "Parking ROM differs"}
if {[lindex [read_memory 0xe9000000 32 1] 0]!=0x47505531 || [lindex [read_memory 0xe9000070 32 1] 0]!=0x02d00500} {error "Wrong GPU/geometry"}
echo "PARKED_R15 $pc"
'''
DISABLED = '''if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display is not parked on internal bars"}
if {[lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal pattern differs"}
'''
CACHE = '''reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
'''


def prepare(out):
    preflight()
    loaded = json.loads((HERE/'cold_trial_01/result.json').read_text())
    anchor = json.loads(ANCHOR.read_text())
    assert loaded['configured'] and not loaded['previous_restored'] and loaded['bitstream_sha256']==BIT_SHA
    assert anchor['complete'] and anchor['cpu_halted'] and anchor['pc'] in (0x80000000,0x80000004)
    assert anchor['bitstream_sha256']==BIT_SHA and hw.p.sha(HERE/'cpu_registers_02/registers.log')==anchor['log_sha256']
    assert hw.p.sha(FRAME)==FRAME_SHA and FRAME.stat().st_size==1843200
    out.mkdir(exist_ok=False)
    shutil_copy = __import__('shutil').copy2
    shutil_copy(Path(__file__),out/'controller.py')
    addresses=[0x00000000,0x00001000,0x00010000,0x00100000,0x01000000,
        0x01700000,0x01700800,0x01701000,0x02000000,0x04000000,
        0x08000000,0x10000000,0x12000000,0x20000000,0x30000000,0x3ffff800]
    # 2 KiB blocks deliberately include neighbors differing at address bit 11.
    patterns=[]
    for i,address in enumerate(addresses):
        rng=random.Random(0x138000+i)
        words=[(address ^ (j*0x9e3779b9) ^ rng.getrandbits(32)) & 0xffffffff for j in range(512)]
        data=struct.pack('<512I',*words)
        seed=out/f'pattern_{i:02d}.bin'; seed.write_bytes(data)
        patterns.append(dict(address=address,seed=seed.name,bytes=len(data),sha256=hw.p.sha(seed)))
    result=dict(bitstream_sha256=BIT_SHA,qualification='FAIL',anchor_sha256=hw.p.sha(ANCHOR),
        frame_sha256=FRAME_SHA,frame_bytes=FRAME.stat().st_size,
        expected_fetch_sum=sum(struct.unpack('<460800I',FRAME.read_bytes()))&0xffffffff,
        patterns=patterns,script_sha256=hw.p.sha(Path(__file__)),
        scope='CPU halted; physical DDR signatures then RGB565 scanout; no CPU execution, Linux, SD or flash',
        started=False,passed=False,restored_bars=False,fpga_reloaded=False)
    (out/'prepared.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    args=parser.parse_args()
    out=HERE/'framebuffer_trial_01'
    if args.prepare:
        r=prepare(out)
        print(json.dumps(dict(prepared=True,hardware=False,patterns=len(r['patterns']),bytes_per_region=2048,
            expected_fetch_sum=hex(r['expected_fetch_sum']))))
        return
    preflight()
    r=json.loads((out/'prepared.json').read_text())
    assert hw.p.sha(Path(__file__))==r['script_sha256'] and not (out/'result.json').exists()
    for pattern in r['patterns']: assert hw.p.sha(out/pattern['seed'])==pattern['sha256']
    assert hw.p.sha(FRAME)==r['frame_sha256'] and hw.p.sha(ANCHOR)==r['anchor_sha256']
    def save(): (out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
    def run(name,code,timeout=30):
        cfg=out/(name+'.tcl'); cfg.write_text(code+'\nshutdown\n')
        log=out/(name+'.log')
        hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled',
            '-f',str(cfg)],log,timeout)
        return log.read_text()
    def interrupt(signum,frame): raise KeyboardInterrupt('Signal '+str(signum))
    for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP): signal.signal(sig,interrupt)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
            '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip(),active.stdout
        identity=hw.usb_identity()
        assert identity['neo']['path'].endswith('/3-4.4.1') and identity['esp']['path'].endswith('/3-4.4.2')
        r.update(started=True,identity=identity,started_unix=time.time()); save()
        write_started=False
        try:
            run('guard',GUARD+DISABLED)
            r['guard_passed']=True; save()
            memory='riscv expose_csrs 1994,1996,2000\n'+GUARD+DISABLED+CACHE
            for p in r['patterns']:
                memory+=f'load_image {{{out/p["seed"]}}} {p["address"]:#x} bin\n'
            memory+='echo ALL_REGIONS_WRITTEN\n'
            # All signatures coexist before any read; do not hide aliases by rewriting.
            for repeat in range(2):
                for i,p in enumerate(r['patterns']):
                    memory+=f'dump_image {{{out/f"read_{repeat}_{i:02d}.bin"}}} {p["address"]:#x} {p["bytes"]}\n'
            memory+='echo MEMORY_CAPTURE_COMPLETE\n'
            write_started=True
            log=run('memory',memory,120)
            checks=[]
            for repeat in range(2):
                for i,p in enumerate(r['patterns']):
                    got=(out/f'read_{repeat}_{i:02d}.bin').read_bytes()
                    expected=(out/p['seed']).read_bytes()
                    wrong=[j for j,(a,b) in enumerate(zip(got,expected)) if a!=b]
                    checks.append(dict(repeat=repeat,address=p['address'],bytes=len(got),
                        sha256=hashlib.sha256(got).hexdigest(),error_bytes=len(wrong),first_errors=wrong[:16],
                        passed=len(got)==len(expected) and not wrong))
            r['memory_checks']=checks
            r['memory_passed']='MEMORY_CAPTURE_COMPLETE' in log and all(c['passed'] for c in checks)
            save()
            assert r['memory_passed'],'DDR signatures differ; no framebuffer activation'
            print('DDR_SIGNATURES_PASS 16 regions, two readbacks',flush=True)
            frame='riscv expose_csrs 1994,1996,2000\n'+GUARD+DISABLED+CACHE+hw.p.SNAPSHOT
            frame+='snapshot DISABLED\n'
            frame+=f'load_image {{{FRAME}}} 0x01700000 bin\nverify_image {{{FRAME}}} 0x01700000 bin\necho FRAME_VERIFIED\n'
            frame+='''write_memory 0xe9000004 32 {0x01700000}
write_memory 0xe900006c 32 {2560}
write_memory 0xe9000030 32 {0}
write_memory 0xe9000040 32 {0}
write_memory 0xe9000008 32 {3}
write_memory 0xe900000c 32 {1}
sleep 300
snapshot RGB0
sleep 1000
snapshot RGB1
echo FRAMEBUFFER_TRIAL_COMPLETE
'''
            log=run('framebuffer',frame,360)
            r['frame_verified']='FRAME_VERIFIED' in log
            r['snapshots']={n:hw.p.decode([int(w,0) for w in s.split()]) for n,s in re.findall(r'^SNAP_(\w+) (.+)$',log,re.M)}
            samples={n:[int(w,0) for w in s.split()] for n,s in re.findall(r'^SCAN_(\w+) (.+)$',log,re.M)}
            r['scan_samples']=samples
            a,b=samples['RGB0'],samples['RGB1']
            assert len(a)==len(b)==32
            for name,index in [('frame_delta',6),('fetch_frame_delta',9),('underflow_delta',7)]:
                r[name]=(b[index]-a[index])&0xffffffff
            r['observed_fetch_sum']=b[8]
            r['passed']=(r['frame_verified'] and 'FRAMEBUFFER_TRIAL_COMPLETE' in log and
                r['frame_delta']>0 and r['fetch_frame_delta']>0 and r['underflow_delta']==0 and
                b[3]==0 and b[5]==1 and b[8]==r['expected_fetch_sum'])
            save()
            assert r['passed'],'Frame stored correctly but scanout check failed'
            r['left_display']='RGB565 framebuffer, CPU halted'
            print('FRAMEBUFFER_PASS',flush=True)
        except BaseException as exc:
            r['error']=repr(exc)
            if write_started:
                for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP): signal.signal(sig,signal.SIG_IGN)
                try:
                    code=GUARD+'''write_memory 0xe9000008 32 {0}
write_memory 0xe900000c 32 {1}
sleep 300
'''+DISABLED+'''echo BARS_RESTORED
'''
                    log=run('restore_bars',code)
                    r['restored_bars']='BARS_RESTORED' in log
                except Exception as restore:
                    r['restore_command_error']=repr(restore)
                    try:
                        hw.Hardware(out,r).program('reload_same_r15',BUILD/'impl/pnr/ao_0.fs',BIT_SHA)
                        r['fpga_reloaded']=True
                        log=run('verify_reloaded_bars',GUARD+DISABLED+'echo BARS_RESTORED\n')
                        r['restored_bars']='BARS_RESTORED' in log
                    except Exception as fallback: r['restore_error']=repr(fallback)
                r['left_display']='R15 internal bars, CPU halted' if r['restored_bars'] else 'Unverified'
        finally:
            r['finished_unix']=time.time()
            r['logs']={p.name:hw.p.sha(p) for p in out.glob('*.log')}
            save()
            print(json.dumps({k:v for k,v in r.items() if k not in ['patterns','memory_checks','snapshots','scan_samples']}),flush=True)
        if not r['passed']: raise SystemExit(1)


if __name__=='__main__': main()
