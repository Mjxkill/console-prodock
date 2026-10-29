#!/usr/bin/env python3
"""Execute exact compiled bytes against a bounded independent CPU/MMIO model."""
import hashlib
import json
from pathlib import Path
import time
from rv32_model import BASE,GPU,JOURNAL,MASK,RV32,SCRATCH

HERE=Path(__file__).resolve().parent

def main():
    binary=(HERE/'build_02/microdma.bin').read_bytes();started=time.monotonic()
    cases=[]
    for fault,want,packets in [(None,1,2),('seed_corrupt',-2,0),('target_touch',-4,1),
          ('target_timeout',-3,1),('clear_timeout',-5,2),('clear_missing',-6,2),
          ('clear_canary',-6,2),('load_trap',-7,0),('cache_on',-1,0),('ilm_bad',-1,0)]:
        cpu=RV32(binary,fault,cache=2 if fault=='cache_on' else 0,
                 milmb=0xa0000000 if fault=='ilm_bad' else 0xa0000001)
        journal=cpu.run()
        assert journal[0:2]==[0x4d443132,1]
        assert journal[3]==(want&MASK),(fault,journal[:32])
        assert len(cpu.commands)==packets
        assert cpu.csr[0x305]==0x80000000
        stores=[a for w,a,v in cpu.accesses if w and SCRATCH<=a<SCRATCH+128]
        if fault in ('cache_on','ilm_bad'):assert not stores
        else:assert stores==list(range(SCRATCH,SCRATCH+128,4))
        if fault is None:
            assert journal[2]==10 and journal[18:21]==[0,1,2]
            assert journal[28:31]==[32,32,32] and journal[16]==0
            pattern=[(SCRATCH+4*i)^0xa5396c17 for i in range(32)]
            assert journal[32:64]==pattern and journal[64:96]==pattern
            assert journal[96:128]==pattern[:8]+[0x6b4d6b4d]*8+pattern[16:]
            assert cpu.gpu_writes==list(range(SCRATCH+32,SCRATCH+64,2))
        if fault=='clear_canary':assert journal[13]==SCRATCH+64
        if fault=='load_trap':assert journal[10:12]==[5,SCRATCH] and BASE<=journal[12]<BASE+len(binary)
        cases.append(dict(fault=fault or 'healthy',result=want,steps=cpu.steps,
                          gpu_packets=len(cpu.commands),cpu_ddr_store_words=len(stores),passed=True))
    # Counterexample: the actual first binary encoded1x16. Its surfaces
    # overlap, so rejection is the correct GPU behavior, not a DDR fault.
    old=RV32((HERE/'build_01/microdma.bin').read_bytes());old_journal=old.run()
    assert old_journal[3]==(-3&MASK) and old.rejected==1 and len(old.commands)==1
    assert not old.gpu_writes and old.target is None
    cases.append(dict(fault='actual_build01_transposed_dimensions',result=-3,
                      rejected=old.rejected,gpu_packets=1,passed=True))
    # A transposed CLEAR with a valid16x1 target is clipped to1x1, not rejected.
    clear=RV32(binary);clear.command([0x16000000,SCRATCH+32,SCRATCH+64,0x100001,0x200020,0,0,0])
    clear.command([0x1c000000,1,0x6b4d,0,0,0x10010,0,0])
    assert clear.gpu_writes==[SCRATCH+32] and clear.rejected==0
    cases.append(dict(fault='transposed_clear_clips_to_one_pixel',written_bytes=2,passed=True))
    result=dict(passed=True,hardware_access=False,scope='RV32 instruction and footprint model only',
        physical_cpu_or_fpga_qualified=False,elapsed_seconds=time.monotonic()-started,cases=cases,
        inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
                [HERE/'build_02/microdma.bin',HERE/'rv32_model.py',Path(__file__)]})
    (HERE/'payload_test_02.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
