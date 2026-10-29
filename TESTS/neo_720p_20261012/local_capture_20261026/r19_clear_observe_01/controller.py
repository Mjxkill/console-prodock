#!/usr/bin/env python3
"""Observe the preserved R19 CLEAR stall; no reset, command or DDR write."""
import fcntl
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import time
from board_trial_r19 import HERE, ROOT, BIT_SHA, BASE_GUARD, DISABLED, hw, sha, preflight

GUARD = BASE_GUARD + '''
foreach {addr expected} {0xe9005080 0x4e435031 0xe9005088 9 0xe900508c 9 0xe9001004 1 0xe9001008 10 0xe9001034 0} {
    if {[lindex [read_memory $addr 32 1] 0]!=$expected} {error "R19 stalled-state anchor changed"}
}
'''
SNAPSHOT = '''proc gpu_snapshot {label} {
    if {[lindex [read_memory 0xe9005000 32 1] 0]!=0x4e474442} {error "Debug signature"}
    if {([lindex [read_memory 0xe9005004 32 1] 0]&5)!=4} {error "Debug not ready"}
    set expected [expr {([lindex [read_memory 0xe900500c 32 1] 0]+1)&0xffffffff}]
    write_memory 0xe9005004 32 {1}
    set complete 0
    for {set i 0} {$i<50} {incr i} {
        sleep 1
        if {[lindex [read_memory 0xe9005004 32 1] 0]==6 && [lindex [read_memory 0xe900500c 32 1] 0]==$expected} {set complete 1;break}
    }
    if {!$complete} {error "Snapshot timeout"}
    set first [read_memory 0xe9005020 32 8]
    set second [read_memory 0xe9005020 32 8]
    if {$first ne $second || [lindex [read_memory 0xe900500c 32 1] 0]!=$expected} {error "Unstable snapshot"}
    echo "GPU_SNAPSHOT $label [read_memory 0xe9005000 32 16]"
    echo "GPU_COUNTERS $label [read_memory 0xe9001000 32 26]"
    echo "RAW_HEADERS $label [read_memory 0xe9005018 32 2] [read_memory 0xe9005040 32 1]"
}
'''

def main():
    preflight()
    anchor=HERE/'r19_memory_01/result.json'
    prior=json.loads(anchor.read_text())
    assert prior['bitstream_sha256']==BIT_SHA and not prior['passed']
    for name,digest in prior['files'].items(): assert sha(anchor.parent/name)==digest,name
    assert 'GPU completion timeout' in (anchor.parent/'clear.log').read_text()
    spec=importlib.util.spec_from_file_location('gpu_decoder', ROOT/'tools/neo/probe_gpu_debug.py')
    import sys
    sys.path.insert(0,str(ROOT/'tools/neo'))
    decoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(decoder)
    out=HERE/'r19_clear_observe_01'
    assert not out.exists()
    result=dict(bitstream_sha256=BIT_SHA,anchor_sha256=sha(anchor),qualification='FAIL',
        scope='Read stalled GPU and DDR; only writes are snapshot request registers',
        fpga_reloaded=False,gpu_reset=False,gpu_command_sent=False,ddr_written=False,
        cpu_resumed=False,sd_written=False,flash_written=False,complete=False)
    def save(): (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    def run(name,code):
        script=out/(name+'.tcl');script.write_text(code+'\nshutdown\n')
        log=out/(name+'.log')
        hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled',
            '-f',str(script)],log,40)
        return log.read_text()
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip(),active.stdout
        result['identity']=hw.usb_identity()
        assert result['identity']['neo']['path'].endswith('/3-4.4.1') and result['identity']['esp']['path'].endswith('/3-4.4.2')
        out.mkdir();shutil.copy2(Path(__file__),out/'controller.py')
        result['started_unix']=time.time();save()
        try:
            text=run('snapshots',GUARD+SNAPSHOT+hw.p.SNAPSHOT+'''
gpu_snapshot first
sleep 100
gpu_snapshot second
sleep 100
gpu_snapshot third
snapshot DISABLED
echo STALLED_SNAPSHOTS_COMPLETE
''')
            snapshots=[]
            for label,words in re.findall(r'^GPU_SNAPSHOT (\w+) (.+)$',text,re.M):
                raw=[int(w,0) for w in words.split()]
                snapshots.append(dict(label=label,raw=raw,decoded=decoder.decode(raw)))
            assert len(snapshots)==3 and 'STALLED_SNAPSHOTS_COMPLETE' in text
            result['gpu_snapshots']=snapshots
            result['scanout_snapshots']=[dict(label=name,raw=words,decoded=hw.p.decode(words))
                for name,words in [(name,[int(w,0) for w in raw.split()]) for name,raw in
                re.findall(r'^SNAP_(\w+) (.+)$',text,re.M)]]
            save();print('SNAPSHOTS_SAVED',flush=True)
            code=GUARD
            regions=[('color',0x12000000,4096,'seed',0x5aa5),
                     ('depth',0x12010000,4096,'zseed',0x7bde),
                     ('source',0x12020000,16384,'source',None)]
            for name,base,size,seed,value in regions:
                code+=f'dump_image {{{out/(name+".bin")}}} {base-32:#x} {size+64}\n'
            code+=DISABLED+'echo "GPU_FINAL [read_memory 0xe9001000 32 26]"\necho DDR_OBSERVATION_COMPLETE\n'
            text=run('ddr',code);assert 'DDR_OBSERVATION_COMPLETE' in text
            result['ddr_regions']=[]
            for name,base,size,seed,value in regions:
                before=(anchor.parent/(seed+'.bin')).read_bytes();after=(out/(name+'.bin')).read_bytes()
                assert len(before)==len(after)==size+64
                a=list(struct.unpack('<'+str(size//2)+'H',after[32:-32]))
                b=list(struct.unpack('<'+str(size//2)+'H',before[32:-32]))
                changed=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
                result['ddr_regions'].append(dict(name=name,base=base,size=size,unchanged=before==after,
                    guards_unchanged=before[:32]==after[:32] and before[-32:]==after[-32:],
                    changed_halfwords=len(changed),first_changed=changed[:32],last_changed=changed[-32:],
                    full_expected_clear=value is not None and all(x==value for x in a),
                    halfwords_equal_clear=sum(x==value for x in a) if value is not None else None,
                    first_halfwords=a[:32]))
            result['gpu_final']=[int(w,0) for w in re.search(r'^GPU_FINAL (.+)$',text,re.M)[1].split()]
            result['complete']=True
        except BaseException as exc: result['error']=repr(exc);raise
        finally:
            result['finished_unix']=time.time()
            result['files']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
            save();print(json.dumps({k:v for k,v in result.items() if k not in ('files','identity','gpu_snapshots')}),flush=True)

if __name__=='__main__': main()
