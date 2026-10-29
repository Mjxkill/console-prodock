#!/usr/bin/env python3
"""Execute exact flags0 firmware; negative side-effect and completion controls."""
import hashlib
import json
from pathlib import Path
import struct
import time
from rv32_model import BASE,GPU,JOURNAL,MASK,RV32,SCRATCH

HERE=Path(__file__).resolve().parent
ORIGINAL=HERE.parents[1]/'microdma_r1/build_02/microdma.bin'

class FaultCPU(RV32):
    def command(self,words):
        if self.fault=='unexpected_gpu_write' and words[0]==0x1c000000:
            assert words[1]==0
            words=words[:];words[1]=1
        super().command(words)
    def access(self,address,write=False,value=0):
        result=super().access(address,write,value)
        if self.fault=='busy_after_done' and address==GPU+4 and self.done==2:return 1
        return result

def main():
    started=time.monotonic();binary=(HERE/'build_01/microdma.bin').read_bytes()
    old=ORIGINAL.read_bytes();assert len(binary)==len(old)==928
    diffs=[]
    for offset in range(0,len(binary),4):
        a,b=struct.unpack_from('<I',old,offset)[0],struct.unpack_from('<I',binary,offset)[0]
        if a!=b:diffs.append({'offset':offset,'old':hex(a),'new':hex(b)})
    # Exactly one li a1,1 -> li a1,0 and the CLEAR flags data word1 ->0.
    assert len(diffs)==2 and {(x['old'],x['new']) for x in diffs}=={('0x100593','0x593'),('0x1','0x0')},diffs
    cases=[]
    expected=[(None,1,2),('seed_corrupt',-2,0),('target_touch',-4,1),
              ('target_timeout',-3,1),('clear_timeout',-5,2),
              ('unexpected_gpu_write',-6,2),('clear_canary',-6,2),
              ('busy_after_done',-5,2),('load_trap',-7,0),
              ('cache_on',-1,0),('ilm_bad',-1,0)]
    pattern=[(SCRATCH+4*i)^0xa5396c17 for i in range(32)]
    for fault,want,packets in expected:
        cpu=FaultCPU(binary,fault,cache=2 if fault=='cache_on' else 0,
                     milmb=0xa0000000 if fault=='ilm_bad' else 0xa0000001)
        journal=cpu.run()
        assert journal[:2]==[0x4d443132,1] and journal[3]==(want&MASK),(fault,journal[:32])
        assert len(cpu.commands)==packets and cpu.csr[0x305]==0x80000000
        stores=[a for w,a,v in cpu.accesses if w and SCRATCH<=a<SCRATCH+128]
        assert stores==([] if fault in ('cache_on','ilm_bad') else list(range(SCRATCH,SCRATCH+128,4)))
        if packets==2:
            assert cpu.commands[1]==[0x1c000000,0,0x6b4d,0,0,0x00100001,0,0]
        if fault is None:
            assert journal[2]==10 and journal[18:21]==[0,1,2]
            assert journal[28:31]==[32,32,32] and journal[16]==0
            assert journal[32:64]==journal[64:96]==journal[96:128]==pattern
            assert cpu.gpu_writes==[] and cpu.done==2
        if fault=='unexpected_gpu_write':assert journal[13]==SCRATCH+32 and journal[16]==8
        if fault=='clear_canary':assert journal[13]==SCRATCH+64 and journal[16]==1
        if fault=='load_trap':assert journal[10:12]==[5,SCRATCH]
        if fault=='busy_after_done':assert journal[2]==8 and cpu.done==2
        cases.append({'fault':fault or 'healthy','expected_result':want,'passed':True,
                      'steps':cpu.steps,'gpu_packets':len(cpu.commands),'gpu_halfword_writes':len(cpu.gpu_writes)})
    result={'passed':True,'hardware':False,'binary_sha256':hashlib.sha256(binary).hexdigest(),
            'original_sha256':hashlib.sha256(old).hexdigest(),'word_differences':diffs,
            'elapsed_seconds':time.monotonic()-started,'cases':cases,
            'limits':['RV32 instruction interpreter, not physical AE350','No GPU native emission proven separately by exactRTL fullchain']}
    (HERE/'tests_01.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
