#!/usr/bin/env python3
"""Repeat opcode-only configuration captures on the already loaded R18r1."""
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
from board_trial import HERE,ROOT,BIT_SHA,BASE_GUARD,CAPTURE,DISABLED,preflight,hw,sha,decode

def main():
    preflight();anchor=HERE/'board_trial_02/result.json';prior=json.loads(anchor.read_text())
    assert prior['configured'] and prior['measurement_complete'] and not prior['restored_r15']
    assert prior['bitstream_sha256']==BIT_SHA
    for n,h in prior['files'].items():assert sha(anchor.parent/n)==h,n
    out=HERE/'repeat_capture_01';assert not out.exists()
    cases=[dict(index=i,opcode=0x16 if i%2==0 else 0x1e,
        words=[0x16000000,0x12000000,0x12010000,0x00800010,0x01000100,0,0,0] if i%2==0 else [0x1e000000]+[0]*7) for i in range(8)]
    code=BASE_GUARD+'''if {[lindex [read_memory 0xe9001008 32 1] 0]!=1 || [lindex [read_memory 0xe9001034 32 1] 0]!=1} {error "R18r1 counter anchor changed"}
if {[lindex [read_memory 0xe9005080 32 1] 0]!=0x4e435031 || [lindex [read_memory 0xe9005088 32 1] 0]!=1 || [lindex [read_memory 0xe900508c 32 1] 0]!=1} {error "R18r1 observer anchor changed"}
'''
    for case in cases:
        i=case['index'];c=CAPTURE
        c=c.replace('[lindex $gpu 2]!=0','[lindex $gpu 2]!='+str(i+1))
        c=c.replace('foreach index {3 7 9 13 19}','foreach index {3 7 9 19}')
        c=c.replace('0x16000000 0x12000000 0x12010000 0x00800010 0x01000100 0 0 0',' '.join(hex(w) for w in case['words']))
        c=c.replace('[lindex $gpu 2]==1','[lindex $gpu 2]=='+str(i+2))
        code+='echo CASE_BEGIN_'+str(i)+'\n'+c+'echo CASE_END_'+str(i)+'\n'
    code+=DISABLED+'echo REPEAT_COMPLETE\nshutdown\n'
    r=dict(bitstream_sha256=BIT_SHA,qualification='FAIL',anchor_sha256=sha(anchor),
        configured=False,fpga_reloaded=False,DDR_written=False,SD_written=False,flash_written=False,
        cases=cases,measurement_complete=False)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip(),active.stdout
        r['identity']=hw.usb_identity()
        assert r['identity']['neo']['path'].endswith('/3-4.4.1') and r['identity']['esp']['path'].endswith('/3-4.4.2')
        out.mkdir();shutil.copy2(Path(__file__),out/'controller.py');(out/'probe.tcl').write_text(code)
        r['started_unix']=time.time()
        try:
            hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
                '-c','adapter speed 1000; gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(out/'probe.tcl')],out/'probe.log',55)
            text=(out/'probe.log').read_text();results=[]
            for case in cases:
                i=case['index'];block=re.search(r'^CASE_BEGIN_'+str(i)+r'\n(.*?)^CASE_END_'+str(i)+r'$',text,re.M|re.S)[1]
                epoch=int(re.search(r'^ARMED ([01]) ',block,re.M)[1])
                rows=[[int(w,0) for w in words.split()] for _,words in re.findall(r'^NCP_(\d) (.+)$',block,re.M)]
                assert len(rows)==3 and all(len(v)==7 for v in rows)
                assert rows[0][:6]==rows[1][:6]==rows[2][:6]
                assert rows[0][0]==0x4e435031 and rows[0][2]==i+2 and rows[0][3]==i+2
                assert ((rows[0][1]>>5)&1)==epoch
                gpu={n:[int(w,0) for w in s.split()] for n,s in re.findall(r'^GPU_(\w+) (.+)$',block,re.M)}
                result=dict(index=i,opcode=case['opcode'],snapshot=rows,
                    capture=decode(rows[0][4]|rows[0][5]<<32,case['opcode'],epoch),gpu=gpu,
                    v1_rejected_delta=(gpu['AFTER'][13]-gpu['BEFORE'][13])&0xffffffff)
                results.append(result)
            r.update(measurement_complete='REPEAT_COMPLETE' in text,results=results,mire_parked=True)
        except BaseException as exc:r['error']=repr(exc);raise
        finally:
            r['finished_unix']=time.time();r['files']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
            (out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
            print(json.dumps(dict(complete=r['measurement_complete'],error=r.get('error'),
                captures=[dict(index=x['index'],opcode=x['opcode'],finding=x['capture']['finding'],at=x['capture']['at'],after=x['capture']['after'],rejected=x['v1_rejected_delta']) for x in r.get('results',[])])))

if __name__=='__main__':main()
