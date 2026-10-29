"""One changed packet field; reuse the frozen prior RV32 fault classes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'copy_empty_01'
spec=importlib.util.spec_from_file_location('prior_empty_tests',OLD/'test_firmware.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
from rv32_model import SCRATCH,MASK

TARGET=[0x16000000,SCRATCH+32,SCRATCH+64,0x00100001,0x00200020,0,0,0]
EMPTY=[0x1d000000,SCRATCH+32,0x00100001,32,0,0,0,0]
SEED=[(SCRATCH+4*i)^0xa5396c17 for i in range(32)]


def main():
    binary=(HERE/'build_01/microdma.bin').read_bytes();old=(OLD/'build_01/microdma.bin').read_bytes()
    assert hashlib.sha256(old).hexdigest()=='0e9b249f276a9c660bebf2a74774b7930cdaa02bb9fbfffc01136d7f0eb8bbc7'
    assert len(binary)==len(old)==928
    changed=[i for i in range(len(old)) if old[i]!=binary[i]]
    assert changed==[900] and old[900]==0 and binary[900]==32
    assert binary[:896]==old[:896] # every instruction + TARGET unchanged
    assert list(struct.unpack_from('<8I',binary,864))==TARGET
    assert list(struct.unpack_from('<8I',binary,896))==EMPTY
    assert struct.unpack_from('<I',old,900)[0]==SCRATCH
    cases=[]
    variants=[('healthy',prior.EmptyCPU,None,{},1),('delayed',prior.Delayed,None,{},1),
      ('timeout',prior.NeverDone,None,{},-5),('done_but_busy',prior.BusyDone,None,{},-5),
      ('rejected',prior.Rejected,None,{},-5),('canary_changed',prior.ChangedCanary,None,{},-6),
      ('destination_changed',prior.ChangedDestination,None,{},-6),
      ('seed_bad',prior.EmptyCPU,'seed_corrupt',{},-2),('target_touch',prior.EmptyCPU,'target_touch',{},-4),
      ('target_timeout',prior.EmptyCPU,'target_timeout',{},-3),('cache_on',prior.EmptyCPU,None,{'cache':2},-1),
      ('ilm_bad',prior.EmptyCPU,None,{'milmb':0xa0010001},-1),('trap',prior.EmptyCPU,'load_trap',{},-7)]
    (HERE/'model_journals').mkdir(exist_ok=True)
    for name,kind,fault,kwargs,want in variants:
        cpu=kind(binary,fault,**kwargs);j=cpu.run()
        assert j[3]==want&MASK,(name,j[:32])
        assert not cpu.gpu_reads and not cpu.gpu_byte_writes and not cpu.gpu_writes
        writes=[a for w,a,v in cpu.accesses if w and SCRATCH<=a<SCRATCH+128]
        assert writes==([] if kwargs else list(range(SCRATCH,SCRATCH+128,4)))
        assert cpu.csr[0x305]==0x80000000 and cpu.reg[2]==0
        if want==1:
            assert j[2]==10 and j[18:21]==[0,1,2] and j[21:24]==[0,0,0]
            assert j[28:31]==[32,32,32] and j[32:64]==j[64:96]==j[96:128]==SEED
            assert cpu.commands==[TARGET,EMPTY]
            (HERE/'healthy_journal.bin').write_bytes(struct.pack('<128I',*j))
        if name=='rejected':assert j[20]==2 and j[23]==1 and j[30]==0
        (HERE/'model_journals'/f'{name}.bin').write_bytes(struct.pack('<128I',*j))
        cases.append(dict(name=name,passed=True,result=want,steps=cpu.steps,cpu_seed_words=len(writes),gpu_bytes=0))
    r=dict(passed=True,hardware=False,binary_sha256=hashlib.sha256(binary).hexdigest(),changed_byte_offsets=changed,
      cases=cases,prior_fault_classes_sha256=hashlib.sha256((OLD/'test_firmware.py').read_bytes()).hexdigest(),
      scope='Exact RV32 footprint/control; valid fixed empty descriptor. Descriptor overlap checks are independently RTL-tested.')
    (HERE/'firmware_tests.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps(dict(passed=True,cases=len(cases),sha256=r['binary_sha256'])))

if __name__=='__main__':main()
