#!/usr/bin/env python3
"""Same R15 DDR write through legacy engine, bypassing failed V1 capture."""
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
from framebuffer_trial import HERE, ROOT, BIT_SHA, GUARD, DISABLED, CACHE, preflight, hw
from gpu_copy_trial import QUEUE, packet

def main():
    preflight()
    prior=json.loads((HERE/'command_observer_01/result.json').read_text())
    assert prior['measurement_complete'] and prior['bitstream_sha256']==BIT_SHA
    out=HERE/'legacy_memory_01';out.mkdir(exist_ok=False)
    shutil.copy2(Path(__file__),out/'controller.py')
    seed=bytes((i*29+7)&255 for i in range(128))
    expected=seed[:32]+b'\xa6'*32+seed[64:]
    (out/'seed.bin').write_bytes(seed);(out/'expected.bin').write_bytes(expected)
    code='riscv expose_csrs 1994,1996,2000\n'+GUARD+DISABLED+CACHE+QUEUE
    code+=f'load_image {{{out/"seed.bin"}}} 0x00800000 bin\nverify_image {{{out/"seed.bin"}}} 0x00800000 bin\n'
    code+='echo "GPU_BEFORE [read_memory 0xe9001000 32 26]"\n'
    code+=packet('LEGACY_FILL',[0x0100a600,32<<16,(32<<16)|1,0,0,0,0,0])
    code+=f'dump_image {{{out/"after.bin"}}} 0x00800000 128\n'
    code+='echo "GPU_AFTER [read_memory 0xe9001000 32 26]"\n'+DISABLED+'echo LEGACY_TRIAL_COMPLETE\nshutdown\n'
    (out/'probe.tcl').write_text(code)
    report=dict(bitstream_sha256=BIT_SHA,qualification='FAIL',passed=False,scope='128 bytes volatile DDR, one 32-byte legacy fill, CPU halted and mire unchanged',script_sha256=hw.p.sha(Path(__file__)))
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
            '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip()
        report['identity']=hw.usb_identity()
        assert report['identity']['neo']['path'].endswith('/3-4.4.1') and report['identity']['esp']['path'].endswith('/3-4.4.2')
        try:
            hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
                '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled',
                '-f',str(out/'probe.tcl')],out/'probe.log',30)
            got=(out/'after.bin').read_bytes()
            report['wrong_bytes']=sum(a!=b for a,b in zip(got,expected))
            report['unchanged']=got==seed
            report['passed']=got==expected and 'LEGACY_TRIAL_COMPLETE' in (out/'probe.log').read_text()
        except Exception as exc:report['error']=repr(exc)
        report['log_sha256']=hw.p.sha(out/'probe.log')
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='identity'}),flush=True)
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
