#!/usr/bin/env python3
"""Collect existing JSONL reads and decode UTW1 offline; never opens hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import re

BASE=0xe9002000
ID=0x55544e41
NET_SHA='0eb5638a63c4c2562f78db1dc71474830b7425b23c30b56674639bac4a4cb191'
SCHEMA='neo-utw1-offline-v1'
PHASES=('before','image_a','image_b','after')
CONTROL=(0,4,8)
IMAGE=tuple(range(0x40,0x100,4))
EXPECTED_OFFSETS={'before':CONTROL,'image_a':IMAGE,'image_b':IMAGE,'after':CONTROL}
MAX_INPUT_BYTES=262144

class Invalid(ValueError):pass
def need(condition,message):
 if not condition:raise Invalid(message)
def strict_json(text):
 def object_pairs(pairs):
  result={}
  for key,value in pairs:
   need(key not in result,'duplicate JSON key '+key);result[key]=value
  return result
 def bad_constant(value):raise Invalid('non-JSON numeric constant '+value)
 return json.loads(text,object_pairs_hook=object_pairs,parse_constant=bad_constant)
def u32(value):
 if isinstance(value,str):
  need(re.fullmatch(r'0x[0-9a-fA-F]{8}',value) is not None,'word string must be 0x plus eight hex digits')
  return int(value,16)
 need(type(value) is int and 0<=value<=0xffffffff,'word must be unsigned 32-bit integer')
 return value
def rows(entries,offsets):
 need(type(entries) is list,'reads must be a list')
 need(len(entries)==len(offsets),'partial or extra read list')
 result={}
 for item,offset in zip(entries,offsets):
  need(type(item) is dict and set(item)=={'address','value'},'read entry keys')
  address=u32(item['address']);value=u32(item['value'])
  need(address==BASE+offset,'unexpected/duplicate/out-of-order MMIO address '+hex(address))
  result[offset]=value
 return result

def collect_jsonl(text,*,expected_sequence,expected_command,origin='synthetic',bitstream_sha256=None):
 """Group a finite existing log; refuse writes, other windows, and reordering."""
 flat=[]
 for number,line in enumerate(text.splitlines(),1):
  need(line.strip()!='','blank JSONL record '+str(number))
  try:item=strict_json(line)
  except json.JSONDecodeError as exc:raise Invalid('invalid JSONL record '+str(number)) from exc
  need(type(item) is dict and set(item)=={'phase','address','value'},'unexpected log operation/keys')
  flat.append(item)
 expected=[(phase,offset) for phase in PHASES for offset in EXPECTED_OFFSETS[phase]]
 need(len(flat)==len(expected),'partial or extra acquisition log')
 phases={phase:[] for phase in PHASES}
 for item,(phase,offset) in zip(flat,expected):
  need(item['phase']==phase,'wrong phase order')
  need(u32(item['address'])==BASE+offset,'unexpected log MMIO address')
  phases[phase].append(dict(address=BASE+offset,value=u32(item['value'])))
 return dict(schema=SCHEMA,origin=origin,board='neo',candidate_netlist_sha256=NET_SHA,
  bitstream_sha256=bitstream_sha256,expected_sequence=expected_sequence,
  expected_command=expected_command,reads=phases)

def decode(packet,*,trusted_bitstream_sha256=None):
 """A coherent version-zero observation is still passed=False/FAIL.

 Identity fields are declarations supplied by the acquisition owner, not a
 physical attestation. Even a valid observation never qualifies the FPGA.
 """
 result=dict(passed=False,status='INVALID_CAPTURE',coherent=False,qualification='FAIL',
  hardware_qualified=False,hardware_access=False,errors=[],boundary_interpretation=None)
 errors=result['errors']
 try:
  need(type(packet) is dict,'capture must be an object')
  need(set(packet)=={'schema','origin','board','candidate_netlist_sha256','bitstream_sha256','expected_sequence','expected_command','reads'},'capture keys')
  need(packet['schema']==SCHEMA and packet['board']=='neo','wrong schema or board')
  need(packet['candidate_netlist_sha256']==NET_SHA,'wrong candidate netlist identity')
  need(packet['origin'] in ('synthetic','hardware_capture'),'unknown origin')
  if packet['origin']=='hardware_capture':
   need(type(trusted_bitstream_sha256) is str and re.fullmatch('[0-9a-f]{64}',trusted_bitstream_sha256) is not None,'hardware log requires separately supplied expected bitstream SHA')
   need(packet['bitstream_sha256']==trusted_bitstream_sha256,'declared bitstream differs from expected SHA')
  else:need(packet['bitstream_sha256'] is None,'synthetic fixture cannot claim a loaded bitstream')
  n=u32(packet['expected_sequence']);command=u32(packet['expected_command'])
  need(1<=n<=0xffffffff//32,'sequence must be positive and before total-counter wrap')
  need(command in (1,2,6),'unsupported diagnostic command')
  need(type(packet['reads']) is dict and set(packet['reads'])==set(PHASES),'missing/extra read phases')
  phases={phase:rows(packet['reads'][phase],EXPECTED_OFFSETS[phase]) for phase in PHASES}
 except (Invalid,TypeError) as exc:
  errors.append(str(exc));return result
 before,first,second,after=(phases[p] for p in PHASES)
 def check(condition,message):
  if not condition:errors.append(message)
 check(before==after,'control changed across the two images')
 check(before[0]==ID and after[0]==ID,'wrong UTNA identity')
 check(before[4]==after[4]==0,'busy/rejected control must be zero before and after')
 check(before[8]==after[8]==n,'snapshot sequence mismatch')
 check(first==second,'the two full images differ')
 check(first[0x40]==ID,'bank word0 sentinel')
 check(first[0x48]==command,'bank word2 command')
 check(first[0xc0]==0x55545731,'witness identity')
 check(first[0xc4]==0x10001,'witness ABI')
 check(first[0xc8]==ID,'witness raw0 sentinel')
 check(first[0xd0]==command,'witness raw2 command')
 check(first[0xcc]==first[0xd4],'raw1 aliases diverge')
 for offset in (0xd8,0xdc,0xe0,0xe8):check(first[offset]==n,'capture/frame count at '+hex(offset))
 check(first[0xe4]==32*n,'total word count')
 check(first[0xec]==0,'event outside busy (EC is mandatory even if F0 is normal)')
 check(first[0xf0]==0x003f0007,'incomplete/order/duplicate/overflow or unexpected progression status')
 for offset in (0xf4,0xf8,0xfc):check(first[offset]==n-1,'capture tag at '+hex(offset))
 bank1,raw1=first[0x44],first[0xcc]
 check(bank1 in (0,1),'unexpected bank version value')
 check(raw1 in (0,1),'unexpected witness version value')
 check(not(bank1==1 and raw1==0),'bank1=1/raw1=0 contradicts witness boundary')
 result.update(origin=packet['origin'],declared_bitstream_sha256=packet['bitstream_sha256'],
  sequence=n,command=command,bank_version=bank1,witness_version=raw1,
  aliases_are_same_register=True,identity_is_declared_not_attested=True)
 if errors:return result
 result['coherent']=True
 if bank1==0:
  errors.append('bank version is zero, expected one; hardware anomaly remains FAIL')
  result['status']='COHERENT_ANOMALY_VERSION_ZERO'
  result['boundary_interpretation']=(
   'Witness=1: discrepancy downstream of the sampled boundary, conditional on witness/read-path validity.' if raw1==1 else
   'Witness=0: zero already observed at the boundary OR witness failure; FIFO cause not established.')
 else:
  result.update(passed=True,status='VALID_LOCAL_OBSERVATION',qualification='NOT_QUALIFIED')
  result['boundary_interpretation']='Version anomaly not reproduced in these declared reads; no cause established.'
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 group=parser.add_mutually_exclusive_group(required=True)
 group.add_argument('--capture',type=Path);group.add_argument('--jsonl',type=Path)
 parser.add_argument('--sequence',type=int);parser.add_argument('--command',type=int)
 parser.add_argument('--origin',choices=['synthetic','hardware_capture'],default='synthetic')
 parser.add_argument('--declared-bitstream-sha256');parser.add_argument('--expected-bitstream-sha256')
 parser.add_argument('--out',type=Path,required=True)
 args=parser.parse_args();source=args.capture or args.jsonl;raw='';data=None
 try:
  need(source.is_file(),'input must be an existing regular saved log')
  need(source.stat().st_size<=MAX_INPUT_BYTES,'input exceeds bounded log size')
  with source.open('rb') as handle:data=handle.read(MAX_INPUT_BYTES+1)
  need(len(data)<=MAX_INPUT_BYTES,'input exceeds bounded log size')
  raw=data.decode('utf-8')
  if args.capture:packet=strict_json(raw)
  else:packet=collect_jsonl(raw,expected_sequence=args.sequence,expected_command=args.command,
   origin=args.origin,bitstream_sha256=args.declared_bitstream_sha256)
  result=decode(packet,trusted_bitstream_sha256=args.expected_bitstream_sha256)
 except (Invalid,json.JSONDecodeError,UnicodeError,OSError) as exc:
  packet=None;result=dict(passed=False,status='INVALID_CAPTURE',qualification='FAIL',hardware_qualified=False,hardware_access=False,errors=[str(exc)])
 result['input_sha256']=hashlib.sha256(data).hexdigest() if data is not None and len(data)<=MAX_INPUT_BYTES else None
 args.out.mkdir(exist_ok=False)
 if packet is not None:(args.out/'capture.json').write_text(json.dumps(packet,indent=2)+'\n')
 (args.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
