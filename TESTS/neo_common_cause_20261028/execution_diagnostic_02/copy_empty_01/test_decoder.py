"""Reject malformed/incomplete/wrong-operation empty-COPY results."""
import hashlib
import json
from pathlib import Path
import struct
from decode_empty import decode,FIRMWARE_SHA256

HERE=Path(__file__).resolve().parent
raw=(HERE/'healthy_journal.bin').read_bytes()
good=decode(raw,firmware_sha256=FIRMWARE_SHA256)
assert good['empty_copy_test_passed'] and good['classification']=='seed_unchanged'
cases=['healthy']
for name,index,value in [('phase',2,8),('result',3,0xfffffffb),('cache',4,2),
                         ('trap',10,5),('done',20,1),('rejected',23,1),
                         ('remaining_count',24,0),('extent',25,0x12000080),
                         ('reserved',31,1),('read_count',30,31),('memory_word',104,0)]:
    data=bytearray(raw);struct.pack_into('<I',data,index*4,value)
    result=decode(data,firmware_sha256=FIRMWARE_SHA256)
    assert not result['empty_copy_test_passed'],name
    if name=='read_count':assert result['classification']=='unobserved'
    cases.append(name)
for name,data,sha in [('length',raw[:-1],FIRMWARE_SHA256),
                      ('identity',bytes(512),FIRMWARE_SHA256),('binding',raw,'0'*64)]:
    try:decode(data,firmware_sha256=sha)
    except ValueError:cases.append(name)
    else:raise AssertionError(name)
result={'passed':True,'hardware':False,'cases':cases,
        'decoder_sha256':hashlib.sha256((HERE/'decode_empty.py').read_bytes()).hexdigest()}
(HERE/'decoder_tests.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'cases':len(cases)}))
