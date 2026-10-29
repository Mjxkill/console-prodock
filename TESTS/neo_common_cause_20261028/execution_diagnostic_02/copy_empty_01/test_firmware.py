"""Execute exact empty-COPY firmware under bounded RV32 fault injection."""
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
EMPTY=[0x1d000000,SCRATCH,0x00100001,32,0,0,0,0]
SEED=[(SCRATCH+4*i)^0xa5396c17 for i in range(32)]


class EmptyCPU(CopyCPU):
    def gpu_read(self,*args):raise AssertionError('Unexpected native GPU read for empty COPY')
    def gpu_write(self,*args):raise AssertionError('Unexpected native GPU write for empty COPY')


class ChangedCanary(EmptyCPU):
    corrupt=64
    def command(self,words):
        super().command(words)
        if words[0]==EMPTY[0]:self.put(SCRATCH+self.corrupt,self.word(SCRATCH+self.corrupt)^1)


class ChangedDestination(ChangedCanary):corrupt=32


class Rejected(EmptyCPU):
    def command(self,words):
        if words[0]==EMPTY[0]:self.done+=1;self.rejected+=1
        else:super().command(words)


class Delayed(EmptyCPU):
    delay=25
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.pending=None;self.wait=0
    def command(self,words):
        if words[0]==EMPTY[0]:self.pending=words[:];self.wait=self.delay
        else:super().command(words)
    def access(self,address,write=False,value=0):
        if not write and address==GPU+8 and self.pending:
            self.wait-=1
            if self.wait==0:
                words=self.pending;self.pending=None;super().command(words)
        value=super().access(address,write,value)
        return 1 if address==GPU+4 and self.pending else value


class NeverDone(Delayed):delay=50001


class BusyDone(EmptyCPU):
    def access(self,address,write=False,value=0):
        value=super().access(address,write,value)
        return 1 if address==GPU+4 and self.done==2 else value


def main():
    binary=(HERE/'build_01/microdma.bin').read_bytes()
    old=(PARENT/'build_01/microdma.bin').read_bytes()
    assert len(binary)==len(old)==928
    diff=[i for i in range(0,len(binary),4) if binary[i:i+4]!=old[i:i+4]]
    assert diff==[432,920]
    assert struct.unpack_from('<I',binary,432)[0]==0x00000593 # addi a1,x0,0
    assert list(struct.unpack_from('<8I',binary,864))==TARGET
    assert list(struct.unpack_from('<8I',binary,896))==EMPTY
    cases=[]
    variants=[('healthy',EmptyCPU,None,{},1),('delayed',Delayed,None,{},1),
              ('timeout',NeverDone,None,{},-5),('done_but_busy',BusyDone,None,{},-5),
              ('rejected',Rejected,None,{},-5),('canary_changed',ChangedCanary,None,{},-6),
              ('destination_changed',ChangedDestination,None,{},-6),
              ('seed_bad',EmptyCPU,'seed_corrupt',{},-2),
              ('target_touch',EmptyCPU,'target_touch',{},-4),
              ('target_timeout',EmptyCPU,'target_timeout',{},-3),
              ('cache_on',EmptyCPU,None,{'cache':2},-1),
              ('ilm_bad',EmptyCPU,None,{'milmb':0xa0010001},-1),
              ('trap',EmptyCPU,'load_trap',{},-7)]
    for name,kind,fault,kwargs,want in variants:
        cpu=kind(binary,fault,**kwargs);journal=cpu.run()
        assert journal[3]==(want&MASK),(name,journal[:32])
        assert not cpu.gpu_reads and not cpu.gpu_byte_writes
        writes=[a for w,a,v in cpu.accesses if w and SCRATCH<=a<SCRATCH+128]
        assert writes==([] if kwargs else list(range(SCRATCH,SCRATCH+128,4)))
        assert cpu.csr[0x305]==0x80000000
        if want==1:
            assert journal[2]==10 and journal[18:21]==[0,1,2]
            assert journal[21:24]==[0,0,0] and journal[28:31]==[32,32,32]
            assert journal[32:64]==journal[64:96]==journal[96:128]==SEED
            assert cpu.commands==[TARGET,EMPTY]
            (HERE/'healthy_journal.bin').write_bytes(struct.pack('<128I',*journal))
        if name=='rejected':assert journal[20]==2 and journal[23]==1 and journal[30]==0
        if name in ('canary_changed','destination_changed'):
            assert journal[13]==SCRATCH+kind.corrupt and journal[16]==1
        cases.append(dict(name=name,passed=True,result=want,steps=cpu.steps,
                          cpu_seed_words=len(writes),gpu_read_bytes=0,gpu_write_bytes=0))
    result={'passed':True,'hardware':False,'binary_sha256':hashlib.sha256(binary).hexdigest(),
            'changed_offsets':diff,'cases':cases,
            'scope':'RV32 control-flow and fixed valid empty descriptor; no hardware timing model'}
    (HERE/'firmware_tests.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'cases':len(cases),'binary_sha256':result['binary_sha256']}))


if __name__=='__main__':main()
