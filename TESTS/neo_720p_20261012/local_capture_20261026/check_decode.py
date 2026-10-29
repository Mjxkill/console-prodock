#!/usr/bin/env python3
"""Check interpretation against mapped traces, plus diagnostic failure cases."""
import hashlib,json,re
from pathlib import Path
from decode_capture import decode
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    log=HERE/'integration_01/simulation.log';count=0;sample=None
    for op,forward,raw in re.findall(r'OBSERVER opcode=([0-9a-f]+) forwards=(\d) trace=([0-9a-f]+)',log.read_text()):
        value=int(raw,16);r=decode(value,int(op,16)>>24,(value>>54)&1)
        assert r['finding']==('OPCODE_CAPTURE_CONSISTENT' if int(forward) else 'NO_COMPLETE_CAPTURE')
        count+=1
        if int(op,16)==0x16000000:sample=value
    assert count==22 and sample is not None
    epoch=(sample>>54)&1;cases=0
    mutations=[(sample&~255,'WRONG_OPCODE_AT_D'),(sample&~(1<<16),'CAPTURE_ENABLE_ABSENT'),
               (sample|(1<<17),'RESET_ACTIVE_AT_CAPTURE'),(sample&~(255<<32),'OPCODE_NOT_CAPTURED'),
               (sample&~(1<<50),'NO_COMPLETE_CAPTURE')]
    for value,expected in mutations:
        assert decode(value,0x16,epoch)['finding']==expected;cases+=1
    for value,e in [(sample^(1<<56),epoch),(sample,epoch^1)]:
        try:decode(value,0x16,e)
        except ValueError:cases+=1
        else:raise AssertionError('Invalid identity accepted')
    result=dict(passed=True,mapped_reports=count,negative_cases=cases,hardware=False,
        inputs={str(p):sha(p) for p in [Path(__file__),HERE/'decode_capture.py',log]})
    with (HERE/'decoder_result.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))
if __name__=='__main__':main()
