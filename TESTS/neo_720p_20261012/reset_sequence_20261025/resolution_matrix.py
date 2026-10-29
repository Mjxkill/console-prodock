#!/usr/bin/env python3
"""Compare full/half scanout without changing FPGA or stored image."""
import fcntl
import json
from pathlib import Path
import re
import signal
import struct
import subprocess
from framebuffer_trial import HERE, ROOT, BUILD, BIT_SHA, FRAME, FRAME_SHA, GUARD, DISABLED, CACHE, preflight, hw


def main():
    preflight()
    old=json.loads((HERE/'framebuffer_trial_01/result.json').read_text())
    assert old['memory_passed'] and old['frame_verified'] and old['restored_bars'] and not old['fpga_reloaded']
    assert old['bitstream_sha256']==BIT_SHA and hw.p.sha(FRAME)==FRAME_SHA
    out=HERE/'resolution_matrix_01'; out.mkdir(exist_ok=False)
    frame=FRAME.read_bytes()
    half=b''.join(frame[y*2560:y*2560+1280]*2 for y in range(360))
    # Reader still fetches each output line: half mode repeats each source row.
    sums={3:sum(struct.unpack('<460800I',frame))&0xffffffff,
          7:sum(struct.unpack('<230400I',half))&0xffffffff}
    report=dict(bitstream_sha256=BIT_SHA,qualification='FAIL',
        framebuffer_bytes_unchanged=True,ddr_written=False,fpga_reloaded=False,
        linux_started=False,expected_fetch_sums=sums,
        script_sha256=hw.p.sha(Path(__file__)),samples=[],restored_bars=False)
    def save(): (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def run(name,code,timeout=45):
        cfg=out/(name+'.tcl');cfg.write_text(code+'\nshutdown\n')
        log=out/(name+'.log')
        hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled',
            '-f',str(cfg)],log,timeout)
        return log.read_text()
    def interrupted(sig,frame):raise KeyboardInterrupt(str(sig))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,interrupted)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
            '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip()
        report['identity']=hw.usb_identity()
        assert report['identity']['neo']['path'].endswith('/3-4.4.1')
        assert report['identity']['esp']['path'].endswith('/3-4.4.2')
        save()
        mutated=False
        try:
            run('guard',GUARD+DISABLED)
            code='riscv expose_csrs 1994,1996,2000\n'+GUARD+DISABLED+CACHE
            code+='''write_memory 0xe9000004 32 {0x01700000}
write_memory 0xe900006c 32 {2560}
write_memory 0xe9000030 32 {0}
write_memory 0xe9000040 32 {0}
'''
            # Same stored image, cropped 640x360 and doubled for half mode.
            for trial,mode in enumerate([3,7,3,7]):
                code+=f'''write_memory 0xe9000008 32 {{{mode}}}
write_memory 0xe900000c 32 {{1}}
sleep 150
if {{[lindex [read_memory 0xe900000c 32 1] 0]!=0}} {{error "Commit pending"}}
write_memory 0xe900002c 32 {{1}}
sleep 100
'''
                for sample in range(8):
                    code+=f'echo "MODE_{trial}_{mode}_{sample} [read_memory 0xe9000000 32 30]"\nsleep 40\n'
            code+='echo MATRIX_COMPLETE\n'
            mutated=True
            text=run('matrix',code)
            for trial,mode,sample,raw in re.findall(r'^MODE_(\d+)_(\d+)_(\d+) (.+)$',text,re.M):
                words=[int(v,0) for v in raw.split()];assert len(words)==30
                report['samples'].append(dict(trial=int(trial),mode=int(mode),sample=int(sample),words=words))
            assert len(report['samples'])==32 and 'MATRIX_COMPLETE' in text
            report['trials']=[]
            for trial in range(4):
                group=[s for s in report['samples'] if s['trial']==trial]
                mode=group[0]['mode'];a,b=group[0]['words'],group[-1]['words']
                frames=(b[6]-a[6])&0xffffffff
                report['trials'].append(dict(trial=trial,mode=mode,
                    frame_delta=frames,fetch_frame_delta=(b[9]-a[9])&0xffffffff,
                    underflow_delta=(b[7]-a[7])&0xffffffff,
                    underflows_per_frame=((b[7]-a[7])&0xffffffff)/frames if frames else None,
                    max_line_cycles=max(s['words'][25] for s in group),
                    expected_sum=sums[mode],observed_sums=sorted(set(s['words'][8] for s in group)),
                    matching_samples=sum(s['words'][8]==sums[mode] for s in group)))
            report['measurement_complete']=True
        except BaseException as exc:report['error']=repr(exc)
        finally:
            if mutated:
                for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,signal.SIG_IGN)
                try:
                    text=run('restore',GUARD+'''write_memory 0xe9000008 32 {0}
write_memory 0xe900000c 32 {1}
sleep 300
'''+DISABLED+'echo BARS_RESTORED\n')
                    report['restored_bars']='BARS_RESTORED' in text
                except Exception as exc:
                    report['restore_error']=repr(exc)
                    hw.Hardware(out,report).program('reload_r15',BUILD/'impl/pnr/ao_0.fs',BIT_SHA)
                    report['fpga_reloaded']=True
                    text=run('restore_verify',GUARD+DISABLED+'echo BARS_RESTORED\n')
                    report['restored_bars']='BARS_RESTORED' in text
            report['logs']={p.name:hw.p.sha(p) for p in out.glob('*.log')}
            save()
            print(json.dumps({k:v for k,v in report.items() if k not in ['samples','identity']}),flush=True)
    if not report.get('measurement_complete') or not report['restored_bars']:raise SystemExit(1)


if __name__=='__main__':main()
