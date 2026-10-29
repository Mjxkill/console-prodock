"""Counterexamples to overbroad COPY model claims, independent of firmware."""
import json
from pathlib import Path
from copy_model import CopyCPU
from rv32_model import SCRATCH
from validate import COPY,TARGET,SEED

def main():
    binary=(Path(__file__).parent/'build_01/microdma.bin').read_bytes();results=[]
    variants=[('stride_not32',3,34,1),('source_unaligned',1,SCRATCH+65,1),
              ('source_above_1GiB',1,0x40000000,1),('reserved_word',7,1,1),
              ('empty_width_legal',6,1,0),('empty_height_legal',6,0x100000,0)]
    for name,index,value,reject in variants:
        cpu=CopyCPU(binary)
        for i,word in enumerate(SEED):cpu.put(SCRATCH+4*i,word)
        cpu.command(TARGET);words=COPY[:];words[index]=value
        error=None
        try:cpu.command(words)
        except Exception as exc:error=repr(exc)
        ok=(error is None and cpu.done==2 and cpu.rejected==reject
            and not cpu.gpu_reads and not cpu.gpu_byte_writes)
        results.append({'name':name,'passed':ok,'done':cpu.done,'rejected':cpu.rejected,
                        'read_bytes':len(cpu.gpu_reads),'written_bytes':len(cpu.gpu_byte_writes),'error':error})
    result={'passed':all(r['passed'] for r in results),'cases':results};print(json.dumps(result,indent=2))
    return int(not result['passed'])

if __name__=='__main__':raise SystemExit(main())
