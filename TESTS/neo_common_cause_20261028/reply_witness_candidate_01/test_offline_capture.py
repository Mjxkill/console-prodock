#!/usr/bin/env python3
"""Adversarial future-format checks; every fixture is explicitly synthetic."""
from copy import deepcopy
import json
from pathlib import Path
import re
import subprocess
import sys
import offline_capture as oc
import prepare_candidate as pc
HERE=Path(__file__).resolve().parent

def fixture():
 # Reuse actual local simulation bank contents, not an invented board capture.
 log=(HERE/'integration_tests_02/case0_mode0.log').read_text()
 bank={int(i):int(v,16) for i,v in re.findall(r'BANK seq=4 word=(\d+) value=([0-9a-f]+)',log)}
 assert len(bank)==32
 n=4;values={4*i+0x40:bank[i] for i in range(32)}
 values.update({0xc0:0x55545731,0xc4:0x10001,0xc8:oc.ID,0xcc:1,0xd0:2,0xd4:1,
  0xd8:n,0xdc:n,0xe0:n,0xe4:n*32,0xe8:n,0xec:0,0xf0:0x003f0007,0xf4:n-1,0xf8:n-1,0xfc:n-1})
 return dict(schema=oc.SCHEMA,origin='synthetic',board='neo',candidate_netlist_sha256=oc.NET_SHA,
  bitstream_sha256=None,expected_sequence=n,expected_command=2,
  reads={p:[dict(address=oc.BASE+a,value=({0:oc.ID,4:0,8:n} if p in ('before','after') else values)[a]) for a in oc.EXPECTED_OFFSETS[p]] for p in oc.PHASES})

def set_word(packet,offset,value,phases=('image_a','image_b')):
 for phase in phases:
  for row in packet['reads'][phase]:
   if row['address']==oc.BASE+offset:row['value']=value;break
  else:raise AssertionError('missing word')

def jsonl(packet):
 return ''.join(json.dumps(dict(phase=phase,**row))+'\n' for phase in oc.PHASES for row in packet['reads'][phase])

def main():
 out=pc.new_output(Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'offline_tests_final');good=fixture();cases=[]
 def run(name,packet,*,passed=False,coherent=False,status=None,expected_bitstream=None):
  result=oc.decode(packet,trusted_bitstream_sha256=expected_bitstream)
  pc.require(result['passed']==passed,name+' passed mismatch '+str(result))
  pc.require(result.get('coherent')==coherent,name+' coherence mismatch '+str(result))
  pc.require(result['hardware_qualified'] is False,name+' incorrectly qualifies hardware')
  if status:pc.require(result['status']==status,name+' status mismatch')
  cases.append(dict(name=name,passed=True,decoder_result=result))
 run('complete synthetic simulation-derived image',good,passed=True,coherent=True,status='VALID_LOCAL_OBSERVATION')
 (out/'synthetic_valid.json').write_text(json.dumps(good,indent=2)+'\n')
 for raw in [0,1]:
  packet=deepcopy(good);set_word(packet,0x44,0);set_word(packet,0xcc,raw);set_word(packet,0xd4,raw)
  run('version zero remains FAIL, raw'+str(raw),packet,coherent=True,status='COHERENT_ANOMALY_VERSION_ZERO')
  (out/f'synthetic_version0_raw{raw}.json').write_text(json.dumps(packet,indent=2)+'\n')
 # The same zero/zero tuple also describes a broken witness plus masked bank.
 # The decoder must retain the witness-failure alternative, not blame FIFO.
 packet=deepcopy(good);set_word(packet,0x44,0);set_word(packet,0xcc,0);set_word(packet,0xd4,0)
 pc.require('witness failure' in oc.decode(packet)['boundary_interpretation'],'overconfident FIFO attribution')
 cases.append(dict(name='zero/zero cannot exclude an internal witness fault',passed=True))
 for phase in oc.PHASES:
  packet=deepcopy(good);packet['reads'][phase].pop();run('partial '+phase,packet)
  packet=deepcopy(good);packet['reads'][phase].append(packet['reads'][phase][0]);run('extra '+phase,packet)
  packet=deepcopy(good);packet['reads'][phase][1]=deepcopy(packet['reads'][phase][0]);run('duplicate address '+phase,packet)
 for offset in [0xf4,0xf8,0xfc]:
  packet=deepcopy(good);set_word(packet,offset,2);run('stale/mixed tag '+hex(offset),packet)
 packet=deepcopy(good);set_word(packet,0xd4,0);run('aliases diverge',packet)
 packet=deepcopy(good);set_word(packet,0xcc,0);set_word(packet,0xd4,0);run('bank1 valid but witness1 zero',packet)
 packet=deepcopy(good);set_word(packet,0x4c,0x123,phases=('image_b',));run('second image changed data',packet)
 packet=deepcopy(good);set_word(packet,8,5,phases=('after',));run('sequence changed across images',packet)
 for phase in ['before','after']:
  for status in [1,2,3]:
   packet=deepcopy(good);set_word(packet,4,status,phases=(phase,));run('busy/rejected '+phase+str(status),packet)
 for offset in [0xd8,0xdc,0xe0,0xe4,0xe8]:
  packet=deepcopy(good);set_word(packet,offset,3);run('incomplete count '+hex(offset),packet)
 for bit in [3,4,5,6,8,16,21,31]:
  packet=deepcopy(good);set_word(packet,0xf0,0x003f0007^(1<<bit));run('bad F0 bit '+str(bit),packet)
 packet=deepcopy(good);set_word(packet,0xec,1)
 run('mixed busy frame: normal F0 and complete counters but EC1',packet)
 (out/'synthetic_mixed_busy.json').write_text(json.dumps(packet,indent=2)+'\n')
 for offset,value in [(0x40,0),(0x48,1),(0xc0,0),(0xc4,0),(0xc8,0),(0xd0,1),(0x44,7),(0xcc,7)]:
  packet=deepcopy(good);set_word(packet,offset,value);run('bad sentinel/version '+hex(offset),packet)
 for sequence in [0,0x08000000,-1,True,None]:
  packet=deepcopy(good);packet['expected_sequence']=sequence;run('invalid sequence '+str(sequence),packet)
 for value in [-1,0x100000000,True,'0x1','0X00000001','ffffffff',None,[]]:
  packet=deepcopy(good);packet['reads']['before'][0]['value']=value;run('invalid word '+str(value),packet)
 for key,value in [('board','prodock'),('candidate_netlist_sha256','0'*64),('schema','v0'),('expected_command',5)]:
  packet=deepcopy(good);packet[key]=value;run('wrong '+key,packet)
 packet=deepcopy(good);packet['origin']='hardware_capture';packet['bitstream_sha256']='a'*64
 run('declared hardware without expected SHA',packet)
 run('declared hardware wrong expected SHA',packet,expected_bitstream='b'*64)
 run('matching declared identity still never qualifies hardware',packet,expected_bitstream='a'*64,passed=True,coherent=True)
 stream=jsonl(good);collected=oc.collect_jsonl(stream,expected_sequence=4,expected_command=2)
 pc.require(collected==good,'collection roundtrip changed values');cases.append(dict(name='all 102 JSONL reads roundtrip',passed=True))
 (out/'synthetic_reads.jsonl').write_text(stream)
 for name,bad in [('truncated',stream.rsplit('\n',2)[0]+'\n'),('extra',stream+stream.splitlines()[0]+'\n'),
  ('wrong aperture',stream.replace(str(oc.BASE),str(oc.BASE+0x1000),1)),
  ('write operation',stream.replace('"phase": "before"','"phase": "before", "operation": "write"',1)),
  ('duplicate JSON key',stream.replace('"phase": "before"','"phase": "after", "phase": "before"',1)),
  ('bad phase',stream.replace('"phase": "before"','"phase": "after"',1)),
  ('invalid JSON',stream+'nonsense\n')]:
  try:oc.collect_jsonl(bad,expected_sequence=4,expected_command=2)
  except oc.Invalid as exc:cases.append(dict(name='reject JSONL '+name,passed=True,reason=str(exc)))
  else:raise AssertionError('accepted '+name)
 # Exercise the actual offline CLI, including preserving a version0 FAIL.
 (out/'duplicate_key.json').write_text(json.dumps(good).replace('"board": "neo"','"board": "prodock", "board": "neo"'))
 (out/'invalid_utf8.json').write_bytes(b'\xff')
 (out/'oversized.json').write_bytes(b' '*(oc.MAX_INPUT_BYTES+1))
 for filename,expected_rc in [('synthetic_valid.json',0),('synthetic_version0_raw0.json',1),('synthetic_mixed_busy.json',1),('duplicate_key.json',1),('invalid_utf8.json',1),('oversized.json',1)]:
  destination=out/(filename[:-5]+'_cli')
  proc=subprocess.run([sys.executable,str(HERE/'offline_capture.py'),'--capture',str(out/filename),'--out',str(destination)],capture_output=True,text=True,timeout=10)
  pc.require(proc.returncode==expected_rc,'CLI status '+filename)
  pc.require((destination/'result.json').exists(),'CLI failed to preserve report')
  report=json.loads((destination/'result.json').read_text())
  if filename=='oversized.json':pc.require(report['input_sha256'] is None,'hash for unread oversized file')
  else:pc.require(report['input_sha256']==pc.sha(out/filename),'actual input bytes hash mismatch')
  cases.append(dict(name='offline CLI '+filename,passed=True,returncode=proc.returncode))
 pc.save(out/'result.json',dict(passed=True,cases=cases,hardware_access=False,
  warning='All fixtures synthetic, including any declared hardware identity used for guard tests; not evidence of a loaded candidate.',
  inputs={str(p):pc.sha(p) for p in [Path(__file__),HERE/'offline_capture.py',HERE/'prepare_candidate.py',HERE/'integration_tests_02/case0_mode0.log']}))
 print(json.dumps(dict(passed=True,cases=len(cases))))
if __name__=='__main__':main()
