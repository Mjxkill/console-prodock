#!/usr/bin/env python3
"""Protected firmware, range, latency and return-data counterexamples."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
from build_local import build
from rv32_model import GPU,MASK,SCRATCH
from copy_model import CopyCPU

HERE=Path(__file__).resolve().parent
TARGET=[0x16000000,SCRATCH+32,SCRATCH+64,0x100001,0x200020,0,0,0]
COPY=[0x1d000000,SCRATCH,0x100001,32,0,0,0x100001,0]
SEED=[(SCRATCH+4*i)^0xa5396c17 for i in range(32)]

class ReturnWrong(CopyCPU):
    def gpu_read(self,address,size):
        data=bytearray(super().gpu_read(address,size));data[0]^=1
        return bytes(data)
class CanaryWrong(CopyCPU):
    def gpu_write(self,address,data):
        super().gpu_write(address,data)
        self.put(SCRATCH+64,self.word(SCRATCH+64)^1)
class MissingWrite(CopyCPU):
    def gpu_write(self,address,data):pass
class ReadOutside(CopyCPU):
    def gpu_read(self,address,size):return super().gpu_read(address+128,size)
class WriteOutside(CopyCPU):
    def gpu_write(self,address,data):return super().gpu_write(address+128,data)
class DelayCopy(CopyCPU):
    delay=25
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.pending_copy=None;self.remaining=0
    def command(self,words):
        if words[0]==COPY[0]:
            self.pending_copy=words[:];self.remaining=self.delay
        else:super().command(words)
    def access(self,address,write=False,value=0):
        if not write and address==GPU+8 and self.pending_copy is not None:
            self.remaining-=1
            if self.remaining<=0:
                packet=self.pending_copy;self.pending_copy=None
                super().command(packet)
        result=super().access(address,write,value)
        return 1 if not write and address==GPU+4 and self.pending_copy is not None else result
class LateCopy(DelayCopy):delay=50001
class BusyDone(CopyCPU):
    def access(self,address,write=False,value=0):
        result=super().access(address,write,value)
        return 1 if not write and address==GPU+4 and self.done==2 else result

def main():
    with tempfile.TemporaryDirectory(prefix='copy-fw-') as tmp:
        binary=build(Path(tmp)/'out').read_bytes();old=(HERE/'baseline.bin').read_bytes()
        assert hashlib.sha256(old).hexdigest()=='dbf293d4ed9c739e4641f0ff531374c5fb9ad8ec7b2b7795f0bf4e609baa934c'
        if '--infra' in sys.argv:
            assert binary==old,'Installed assembler does not reproduce BIN02'
            print('INFRA_PASS exact928B BIN02 reconstructed');return
        assert len(binary)==len(old)==928
        differences=[i for i in range(0,len(old),4) if binary[i:i+4]!=old[i:i+4]]
        assert differences and set(differences)<=({0x2b8,0x2bc}|set(range(0x380,0x3a0,4))),differences
        assert list(struct.unpack_from('<8I',binary,0x360))==TARGET
        assert list(struct.unpack_from('<8I',binary,0x380))==COPY
        results=[]
        variants=[('healthy',CopyCPU,None,1),('delayed',DelayCopy,None,1),
                  ('late_completion',LateCopy,None,-5),('done_but_busy',BusyDone,None,-5),
                  ('wrong_return',ReturnWrong,None,-6),('missing_write',MissingWrite,None,-6),
                  ('canary',CanaryWrong,None,-6),('bad_seed',CopyCPU,'seed_corrupt',-2),
                  ('target_touch',CopyCPU,'target_touch',-4),('target_timeout',CopyCPU,'target_timeout',-3),
                  ('cache_on',CopyCPU,'cache_on',-1),('ilm_bad',CopyCPU,'ilm_bad',-1),
                  ('load_trap',CopyCPU,'load_trap',-7)]
        for name,kind,fault,want in variants:
            cpu=kind(binary,fault,cache=2 if fault=='cache_on' else 0,
                     milmb=0xa0000000 if fault=='ilm_bad' else 0xa0000001)
            journal=cpu.run();assert journal[:2]==[0x4d443132,1]
            assert journal[3]==(want&MASK),(name,journal[:32])
            writes=[a for w,a,v in cpu.accesses if w and SCRATCH<=a<SCRATCH+128]
            assert writes==([] if fault in ('cache_on','ilm_bad') else list(range(SCRATCH,SCRATCH+128,4)))
            assert cpu.csr[0x305]==0x80000000
            if want==1:
                assert journal[2]==10 and journal[18:21]==[0,1,2] and journal[28:31]==[32]*3
                assert journal[32:64]==journal[64:96]==SEED
                assert journal[96:128]==SEED[:8]+SEED[:8]+SEED[16:]
                assert cpu.commands==[TARGET,COPY]
                assert cpu.gpu_reads==list(range(SCRATCH,SCRATCH+32))
                assert cpu.gpu_byte_writes==list(range(SCRATCH+32,SCRATCH+64))
            if name=='wrong_return':assert journal[13]==SCRATCH+32 and journal[16]==1
            if name=='missing_write':assert journal[16]==8
            if name=='canary':assert journal[13]==SCRATCH+64 and journal[16]==1
            results.append({'name':name,'passed':True,'result':want,'steps':cpu.steps})
        for name,kind in [('native_read_outside',ReadOutside),('native_write_outside',WriteOutside)]:
            try:kind(binary).run()
            except (ValueError,AssertionError) as exc:
                assert 'scratch' in str(exc).lower(),(name,str(exc))
                results.append({'name':name,'passed':True,'bounded_rejection':str(exc)})
            else:raise AssertionError(name+' silently accepted out-of-range access')
        # Public ABI test, independent of this firmware's packet constants:
        # source16x1, requested1x16 clips to1x1 (2B), high16 is width.
        cpu=CopyCPU(binary)
        for i,value in enumerate(SEED):cpu.put(SCRATCH+4*i,value)
        cpu.command(TARGET);transpose=COPY[:];transpose[6]=0x00010010;cpu.command(transpose)
        assert cpu.gpu_reads==[SCRATCH,SCRATCH+1]
        assert cpu.gpu_byte_writes==[SCRATCH+32,SCRATCH+33]
        results.append({'name':'transposed_dimensions_clip_one_pixel','passed':True})
        print(json.dumps({'passed':True,'cases':results,'binary_sha256':hashlib.sha256(binary).hexdigest(),
                          'word_offsets_changed':differences,'hardware':False},indent=2))

if __name__=='__main__':main()
