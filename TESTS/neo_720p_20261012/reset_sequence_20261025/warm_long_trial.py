#!/usr/bin/env python3
"""Repeat the existing 50ms reset on R15, then inspect V1 capture; no reroute."""
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import serial
from framebuffer_trial import HERE, ROOT, BUILD, BIT_SHA, GUARD, DISABLED, CACHE, preflight, hw
from gpu_copy_trial import QUEUE, packet
sys.path.insert(0,str(ROOT/'tools/neo'))
from console import UART,select_relay

def main():
    preflight()
    assert json.loads((HERE/'legacy_memory_01/result.json').read_text())['passed']
    out=HERE/'warm_long_01';out.mkdir(exist_ok=False)
    shutil.copy2(Path(__file__),out/'controller.py')
    report=dict(bitstream_sha256=BIT_SHA,qualification='FAIL',script_sha256=hw.p.sha(Path(__file__)),
        scope='One warm reset in 50ms mode; same loaded FPGA, PLL and DDR resets unchanged; CPU ROM parking',
        measurement_complete=False,fpga_reloaded=False,reset_frame_hex='a55a52313501fe0d')
    def save(): (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(name,code):
        cfg=out/(name+'.tcl');cfg.write_text(code+'\nshutdown\n')
        log=out/(name+'.log')
        hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled',
            '-f',str(cfg)],log,30)
        return log.read_text()
    probe=GUARD+DISABLED+'echo "GPU [read_memory 0xe9001000 32 26]"\necho "SCAN [read_memory 0xe9000000 32 30]"\n'
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
            '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip()
        report['identity']=hw.usb_identity()
        assert report['identity']['neo']['path'].endswith('/3-4.4.1') and report['identity']['esp']['path'].endswith('/3-4.4.2')
        sent=False
        try:
            run('guard',probe)
            with serial.Serial(UART,2000000,timeout=.1,exclusive=True) as link:
                transcript=select_relay(link,2000000)
                (out/'relay.txt').write_bytes(transcript)
                before=run('before',probe)
                report['gpu_before']=[int(v,0) for v in re.search(r'^GPU (.+)$',before,re.M)[1].split()]
                assert report['gpu_before'][2]>=16 and report['gpu_before'][1]==0
                data=bytes.fromhex(report['reset_frame_hex'])
                sent=True;report['sent_unix']=time.time();save()
                assert link.write(data)==len(data)
                link.flush();time.sleep(.25)
                (out/'uart_after.bin').write_bytes(link.read(4096))
            after=run('after',probe)
            report['gpu_after']=[int(v,0) for v in re.search(r'^GPU (.+)$',after,re.M)[1].split()]
            assert report['gpu_after'][1]==0 and report['gpu_after'][2]==0 and report['gpu_after'][13]==0,'Warm reset not demonstrated by cleared GPU counters'
            report['reset_observed']=True;save()
            code='riscv expose_csrs 1994,1996,2000\n'+GUARD+DISABLED+CACHE+QUEUE
            for name,words in [('TARGET',[22<<24,0x12000000,0x12010000,(128<<16)|16,(256<<16)|256,0,0,0]),('INVALIDATE',[30<<24,0,0,0,0,0,0,0])]:
                code+=packet(name,words)
                code+=f'sleep 2\necho "GPU_{name} [read_memory 0xe9001000 32 26]"\n'
                for i in range(3):code+=f'echo "RAW_{name}_{i} [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"\nsleep 2\n'
            log=run('commands',code+DISABLED+'echo WARM_TRIAL_COMPLETE\n')
            report['gpu']={n:[int(w,0) for w in s.split()] for n,s in re.findall(r'^GPU_(\w+) (.+)$',log,re.M)}
            report['raw']={n:[int(w,0) for w in s.split()] for n,s in re.findall(r'^RAW_(\w+) (.+)$',log,re.M)}
            report['measurement_complete']='WARM_TRIAL_COMPLETE' in log
            report['mire_parked']=True
        except Exception as exc:
            report['error']=repr(exc)
            if sent:
                try:
                    run('recovery_guard',probe)
                    report['mire_parked']=True
                except Exception:
                    hw.Hardware(out,report).program('reload_same_r15',BUILD/'impl/pnr/ao_0.fs',BIT_SHA)
                    report['fpga_reloaded']=True
                    run('reloaded_guard',probe)
                    report['mire_parked']=True
        finally:
            report['logs']={p.name:hw.p.sha(p) for p in out.glob('*.log')}
            save();print(json.dumps({k:v for k,v in report.items() if k!='identity'}),flush=True)
    if not report['measurement_complete']:raise SystemExit(1)

if __name__=='__main__':main()
