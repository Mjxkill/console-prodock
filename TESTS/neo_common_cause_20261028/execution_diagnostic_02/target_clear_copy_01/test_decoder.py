"""Actual firmware fault journals plus independent metadata mutations."""
import hashlib,json,struct
from pathlib import Path
from decode_sequence import decode,FIRMWARE_SHA256
HERE=Path(__file__).resolve().parent
raw=(HERE/'healthy_journal.bin').read_bytes()
good=decode(raw,firmware_sha256=FIRMWARE_SHA256)
assert good['sequence_test_passed'] and good['clear_control_passed']
assert good['classification']=='seed_unchanged'
cases=['healthy']
for name,index,value in [('phase',2,10),('result',3,0xfffffffb),('cache',4,2),
  ('trap',10,5),('done',20,2),('rejected',23,1),('packet_remaining',24,0),
  ('extent',25,0x12000080),('clear_done',26,1),('clear_rejected',27,1),
  ('reserved',31,1),('read_count',30,31),('memory_word',104,0),('compare_count',16,1)]:
    data=bytearray(raw);struct.pack_into('<I',data,index*4,value)
    r=decode(data,firmware_sha256=FIRMWARE_SHA256)
    assert not r['sequence_test_passed'],name
    if name=='read_count':assert r['classification']=='unobserved'
    if name in ('clear_done','clear_rejected'):assert not r['clear_control_passed']
    cases.append(name)
for name,data,sha in [('length',raw[:-1],FIRMWARE_SHA256),('identity',bytes(512),FIRMWARE_SHA256),
  ('binding',raw,'0'*64),('old_MD12',struct.pack('<I',0x4d443132)+raw[4:],FIRMWARE_SHA256)]:
    try:decode(data,firmware_sha256=sha)
    except ValueError:cases.append(name)
    else:raise AssertionError(name)
for path in sorted((HERE/'model_journals').glob('*.bin')):
    r=decode(path.read_bytes(),firmware_sha256=FIRMWARE_SHA256)
    healthy=path.stem in ('healthy','copy_delayed','clear_delayed')
    assert r['sequence_test_passed']==healthy,(path,r)
    if path.stem in ('clear_rejected','target_lost_before_clear'):
        assert r['observation']=='clear_control_completed_rejected'
    if path.stem in ('copy_rejected','target_lost_before_copy'):
        assert r['observation']=='clear_control_passed_copy_completed_rejected'
    if path.stem in ('clear_timeout','copy_timeout'):
        assert r['observation']=='incomplete_or_other_failure'
    cases.append('firmware:'+path.stem)
(HERE/'decoder_tests.json').write_text(json.dumps(dict(passed=True,hardware=False,cases=cases,
  decoder_sha256=hashlib.sha256((HERE/'decode_sequence.py').read_bytes()).hexdigest()),indent=2)+'\n')
print(json.dumps({'passed':True,'cases':len(cases)}))
