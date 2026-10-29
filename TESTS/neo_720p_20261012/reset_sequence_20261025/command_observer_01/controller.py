#!/usr/bin/env python3
"""Trace R15 command configuration and one legacy fill, using existing observer."""
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from framebuffer_trial import HERE, ROOT, BIT_SHA, GUARD, DISABLED, CACHE, preflight, hw
from gpu_copy_trial import QUEUE, packet

def main():
    preflight()
    prior=json.loads((HERE/'gpu_copy_trial_01/result.json').read_text())
    assert prior['mire_parked'] and prior['bitstream_sha256']==BIT_SHA
    out=HERE/'command_observer_01';out.mkdir(exist_ok=False)
    shutil.copy2(Path(__file__),out/'controller.py')
    sys.path.insert(0,str(ROOT/'TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021'))
    from probe_observer import suite, decode_meta
    cases=suite()
    report=dict(bitstream_sha256=BIT_SHA,qualification='FAIL',script_sha256=hw.p.sha(Path(__file__)),
        configuration_only=True,measurement_complete=False)
    # Includes V1 and geometry counters which the first fill's fence did not check.
    observe='''proc observe {name} {
    sleep 2
    echo "GPU_$name [read_memory 0xe9001000 32 26]"
    for {set i 0} {$i<3} {incr i} {
        echo "RAW_${name}_$i [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
        sleep 2
    }
    set before [lindex [read_memory 0xe900500c 32 1] 0]
    set status [lindex [read_memory 0xe9005004 32 1] 0]
    if {($status&5)==4} {
        write_memory 0xe9005004 32 {1}
        sleep 10
    }
    echo "DEBUG_$name [read_memory 0xe9005000 32 17]"
}
'''
    code='riscv expose_csrs 1994,1996,2000\n'+GUARD+DISABLED+CACHE+QUEUE+observe
    code+='if {[lindex [read_memory 0xe9005000 32 1] 0]!=0x4e474442} {error "Wrong observer"}\nobserve INITIAL\n'
    for case in cases:
        code+=packet(case['name'],case['words'])+'observe '+case['name']+'\n'
    code+=DISABLED+'echo COMMAND_OBSERVATION_COMPLETE\nshutdown\n'
    (out/'probe.tcl').write_text(code)
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
                '-f',str(out/'probe.tcl')],out/'probe.log',45)
        except Exception as exc:report['error']=repr(exc)
        text=(out/'probe.log').read_text()
        report['gpu']={n:[int(w,0) for w in s.split()] for n,s in re.findall(r'^GPU_(\w+) (.+)$',text,re.M)}
        report['raw']={n:dict(words=[int(w,0) for w in s.split()],decoded=decode_meta(int(s.split()[-1],0))) for n,s in re.findall(r'^RAW_(\w+) (.+)$',text,re.M)}
        report['debug']={n:[int(w,0) for w in s.split()] for n,s in re.findall(r'^DEBUG_(\w+) (.+)$',text,re.M)}
        report['measurement_complete']='COMMAND_OBSERVATION_COMPLETE' in text
        report['log_sha256']=hw.p.sha(out/'probe.log')
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(dict(complete=report['measurement_complete'],error=report.get('error'),
            gpu=report['gpu'],raw=report['raw'])),flush=True)
    if not report['measurement_complete']:raise SystemExit(1)

if __name__=='__main__':main()
