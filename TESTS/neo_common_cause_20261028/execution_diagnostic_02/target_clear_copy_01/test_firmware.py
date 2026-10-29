"""Exact RV32 binary: sequence, scratch footprint and failure-stage provenance."""
import hashlib
import json
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
PARENT=HERE.parent/'copy_probe_01/firmware_delivery_01'
sys.path.insert(0,str(PARENT))
from copy_model import CopyCPU
from rv32_model import GPU,SCRATCH,MASK

TARGET=[0x16000000,SCRATCH+32,SCRATCH+64,0x00100001,0x00200020,0,0,0]
CLEAR=[0x1c000000,0,0x6b4d,0,0,0x00100001,0,0]
COPY=[0x1d000000,SCRATCH,0x00100001,32,0,0,0,0]
SEED=[(SCRATCH+4*i)^0xa5396c17 for i in range(32)]


class SequenceCPU(CopyCPU):
    def gpu_read(self,*args):raise AssertionError('No-op issued GPU read')
    def gpu_write(self,*args):raise AssertionError('No-op issued GPU write')


class Rejected(SequenceCPU):
    reject_op=COPY[0]
    def command(self,words):
        if words[0]==self.reject_op:self.done+=1;self.rejected+=1
        else:super().command(words)


class ClearRejected(Rejected):reject_op=CLEAR[0]


class Corrupt(SequenceCPU):
    corrupt=64
    def command(self,words):
        super().command(words)
        if words[0]==COPY[0]:self.put(SCRATCH+self.corrupt,self.word(SCRATCH+self.corrupt)^1)


class DestCorrupt(Corrupt):corrupt=32


class Delayed(SequenceCPU):
    delay=25
    delay_op=COPY[0]
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.pending=None;self.wait=0
    def command(self,words):
        if words[0]==self.delay_op:self.pending=words[:];self.wait=self.delay
        else:super().command(words)
    def access(self,address,write=False,value=0):
        if not write and address==GPU+8 and self.pending:
            self.wait-=1
            if not self.wait:
                words=self.pending;self.pending=None;super().command(words)
        result=super().access(address,write,value)
        return 1 if not write and address==GPU+4 and self.pending else result


class ClearDelayed(Delayed):delay_op=CLEAR[0]
class CopyTimeout(Delayed):delay=50001
class ClearTimeout(ClearDelayed):delay=50001


class Busy(SequenceCPU):
    hold_done=3
    def access(self,address,write=False,value=0):
        result=super().access(address,write,value)
        return 1 if not write and address==GPU+4 and self.done==self.hold_done else result


class ClearBusy(Busy):hold_done=2


class LostTarget(SequenceCPU):
    after_op=TARGET[0]
    def command(self,words):
        super().command(words)
        if words[0]==self.after_op:self.target=None


class LostAfterClear(LostTarget):after_op=CLEAR[0]


def main():
    binary=(HERE/'build_01/microdma.bin').read_bytes()
    assert 0<len(binary)<=4096 and 0xa0004000+len(binary)<0xa0005000
    # Locate the contiguous packet table independently of instruction offsets.
    expected=struct.pack('<24I',*(TARGET+CLEAR+COPY))
    assert binary.endswith(expected) and binary.count(expected)==1
    variants=[('healthy',SequenceCPU,None,{},1,12),
      ('copy_delayed',Delayed,None,{},1,12),('clear_delayed',ClearDelayed,None,{},1,12),
      ('copy_timeout',CopyTimeout,None,{},-5,10),('clear_timeout',ClearTimeout,None,{},-8,8),
      ('copy_done_busy',Busy,None,{},-5,10),('clear_done_busy',ClearBusy,None,{},-8,8),
      ('copy_rejected',Rejected,None,{},-5,10),('clear_rejected',ClearRejected,None,{},-8,8),
      ('target_lost_before_clear',LostTarget,None,{},-8,8),
      ('target_lost_before_copy',LostAfterClear,None,{},-5,10),
      ('canary_changed',Corrupt,None,{},-6,11),('destination_changed',DestCorrupt,None,{},-6,11),
      ('seed_bad',SequenceCPU,'seed_corrupt',{},-2,3),('target_touch',SequenceCPU,'target_touch',{},-4,6),
      ('target_timeout',SequenceCPU,'target_timeout',{},-3,5),
      ('cache_on',SequenceCPU,None,{'cache':2},-1,1),('ilm_bad',SequenceCPU,None,{'milmb':0xa0010001},-1,1),
      ('trap',SequenceCPU,'load_trap',{},-7,3)]
    cases=[]
    for name,kind,fault,kwargs,want,phase in variants:
        cpu=kind(binary,fault,**kwargs);j=cpu.run()
        assert j[:2]==[0x4d443133,1]
        assert j[2:4]==[phase,want&MASK],(name,j[:32])
        assert not cpu.gpu_reads and not cpu.gpu_byte_writes and not cpu.gpu_writes
        writes=[a for w,a,v in cpu.accesses if w and SCRATCH<=a<SCRATCH+128]
        assert writes==([] if kwargs else list(range(SCRATCH,SCRATCH+128,4)))
        assert cpu.csr[0x305]==0x80000000 and cpu.csr[0x7ca]==kwargs.get('cache',0)
        assert cpu.reg[2]==0 # no stack use
        if phase>=9:assert j[26:28]==[2,0],(name,j[:32])
        if phase==8:assert cpu.commands==[TARGET,CLEAR]
        if want==1:
            assert j[18:21]==[0,1,3] and j[21:24]==[0,0,0]
            assert j[28:31]==[32,32,32] and j[31]==0
            assert j[32:64]==j[64:96]==j[96:128]==SEED
            assert cpu.commands==[TARGET,CLEAR,COPY]
            (HERE/'healthy_journal.bin').write_bytes(struct.pack('<128I',*j))
        if name=='copy_rejected':assert j[20]==3 and j[23]==1 and j[30]==0
        if name in ('clear_rejected','target_lost_before_clear'):assert j[26:28]==[2,1] and j[20]==0
        (HERE/'model_journals').mkdir(exist_ok=True)
        (HERE/'model_journals'/f'{name}.bin').write_bytes(struct.pack('<128I',*j))
        cases.append(dict(name=name,passed=True,result=want,phase=phase,steps=cpu.steps,
          commands=len(cpu.commands),cpu_seed_words=len(writes),gpu_native_model_bytes=0))
    r=dict(passed=True,hardware=False,binary_sha256=hashlib.sha256(binary).hexdigest(),cases=cases,
      model_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (PARENT/'copy_model.py',PARENT/'rv32_model.py')},
      scope='Exact instruction control/footprint, logical ABI model; not AE350/RTL/physical timing')
    (HERE/'firmware_tests.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({'passed':True,'cases':len(cases),'sha256':r['binary_sha256']}))

if __name__=='__main__':main()
