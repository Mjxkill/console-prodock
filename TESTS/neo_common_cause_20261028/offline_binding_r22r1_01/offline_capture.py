#!/usr/bin/env python3
"""Offline UTW1 decoder bound to the syntax-normalized R22r1, never hardware."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
FROZEN=ROOT/'TESTS/neo_common_cause_20261028/reply_witness_candidate_01'
NET_SHA='0eb5638a63c4c2562f78db1dc71474830b7425b23c30b56674639bac4a4cb191'
ORIGINAL_NET_SHA='fa0185400736119ed68d6792656b6a80e328742acfa1deff7e7acdc02e4f24d1'
FILES={
 'TESTS/neo_common_cause_20261028/reply_witness_candidate_01/offline_capture.py':'668f4dc7d14e1491f0bc97a4a14e2ee7e589eceab450273c6aff8e22b83708ae',
 'tang/impl/console_neo_n56r22r1_utw1_format/console_neo.vg':NET_SHA,
 'tang/impl/console_neo_n56r22r1_utw1_format/format_assembly.json':'51dc9f89927ec99123004b0883f505c6a5008e36d8d85faf7fb1003790a8ee97',
 'tang/impl/console_neo_n56r22r1_utw1_format/serialization_proof.json':'4cf5086cfa0dacf8ccd210676224038a731977b8ec49951ba0078b263f63f0e7',
 'TESTS/neo_common_cause_20261028/reply_witness_format_r1/tests_02/result.json':'7fab061d416ef2fa40d6c9a94f068a2153fb81dd6874b9ac8e9479443b79ec7e',
 'tang/impl/console_neo_n56r22r1_utw1_reports/reports_assembly.json':'d017b413e3839644000e71432167f9d5e56541d922341d76642769fef5e51899',
}

def file_sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def verify_files(root=ROOT,files=None):
 for name,digest in (FILES if files is None else files).items():
  if file_sha(root/name)!=digest:raise ValueError('provenance input changed: '+name)

def load_decoder():
 original=(FROZEN/'offline_capture.py').read_bytes();new=(HERE/'decoder_bound.py').read_bytes()
 old_token=("NET_SHA='"+ORIGINAL_NET_SHA+"'").encode();new_token=("NET_SHA='"+NET_SHA+"'").encode()
 if original.count(old_token)!=1 or new!=original.replace(old_token,new_token,1):raise ValueError('bound decoder changed beyond exact identity literal')
 # Only import after verifying its complete bytes against the frozen decoder.
 if file_sha(FROZEN/'offline_capture.py')!=FILES[str((FROZEN/'offline_capture.py').relative_to(ROOT))]:raise ValueError('frozen decoder changed')
 spec=importlib.util.spec_from_file_location('_utw1_r22r1_bound_decoder',HERE/'decoder_bound.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module

_decoder=load_decoder()
BASE,ID,SCHEMA,PHASES,CONTROL,IMAGE,EXPECTED_OFFSETS,MAX_INPUT_BYTES=(_decoder.BASE,_decoder.ID,_decoder.SCHEMA,_decoder.PHASES,_decoder.CONTROL,_decoder.IMAGE,_decoder.EXPECTED_OFFSETS,_decoder.MAX_INPUT_BYTES)
Invalid,need,strict_json,u32,rows=(_decoder.Invalid,_decoder.need,_decoder.strict_json,_decoder.u32,_decoder.rows)

def provenance():
 verify_files()
 original=(FROZEN/'offline_capture.py').read_bytes();bound=(HERE/'decoder_bound.py').read_bytes()
 need(bound==original.replace(("NET_SHA='"+ORIGINAL_NET_SHA+"'").encode(),("NET_SHA='"+NET_SHA+"'").encode(),1),'bound decoder file changed after import')
 proof=json.loads((ROOT/'tang/impl/console_neo_n56r22r1_utw1_format/serialization_proof.json').read_text())
 need(proof['passed'] and proof['primitive_pins_and_parameters_equivalent'] and proof['alias_bit_graph_equivalent'] and proof['parent_recovered_byte_identical'],'format equivalence not established')
 return dict(original_netlist_sha256=ORIGINAL_NET_SHA,normalized_netlist_sha256=NET_SHA,
  decoder_original_sha256=file_sha(FROZEN/'offline_capture.py'),decoder_bound_sha256=file_sha(HERE/'decoder_bound.py'),
  adapter_sha256=file_sha(Path(__file__)),binding_kind='exact decoder identity literal substitution; behavior and packet schema unchanged',
  pinned_inputs=FILES,hardware_attestation=False)

def collect_jsonl(text,*,expected_sequence,expected_command,origin='synthetic',bitstream_sha256=None):
 provenance()
 return _decoder.collect_jsonl(text,expected_sequence=expected_sequence,expected_command=expected_command,
  origin=origin,bitstream_sha256=bitstream_sha256)

def decode(packet,*,trusted_bitstream_sha256=None):
 try:binding=provenance()
 except (OSError,ValueError,KeyError) as exc:
  return dict(passed=False,status='INVALID_PROVENANCE',coherent=False,qualification='FAIL',hardware_qualified=False,
   hardware_access=False,errors=[str(exc)],boundary_interpretation=None)
 result=_decoder.decode(packet,trusted_bitstream_sha256=trusted_bitstream_sha256)
 result['decoder_provenance']=binding
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
 group.add_argument('--capture',type=Path);group.add_argument('--jsonl',type=Path)
 parser.add_argument('--sequence',type=int);parser.add_argument('--command',type=int)
 parser.add_argument('--origin',choices=['synthetic','hardware_capture'],default='synthetic')
 parser.add_argument('--declared-bitstream-sha256');parser.add_argument('--expected-bitstream-sha256')
 parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
 source=args.capture or args.jsonl;data=None;packet=None
 try:
  provenance();need(source.is_file(),'input must be an existing regular saved log');need(source.stat().st_size<=MAX_INPUT_BYTES,'input exceeds bounded log size')
  with source.open('rb') as handle:data=handle.read(MAX_INPUT_BYTES+1)
  need(len(data)<=MAX_INPUT_BYTES,'input exceeds bounded log size');text=data.decode('utf-8')
  packet=strict_json(text) if args.capture else collect_jsonl(text,expected_sequence=args.sequence,expected_command=args.command,
   origin=args.origin,bitstream_sha256=args.declared_bitstream_sha256)
  result=decode(packet,trusted_bitstream_sha256=args.expected_bitstream_sha256)
 except (ValueError,TypeError,UnicodeError,OSError) as exc:
  packet=None;result=dict(passed=False,status='INVALID_CAPTURE',qualification='FAIL',hardware_qualified=False,hardware_access=False,errors=[str(exc)])
 result['input_sha256']=hashlib.sha256(data).hexdigest() if data is not None and len(data)<=MAX_INPUT_BYTES else None
 args.out.mkdir(exist_ok=False)
 if packet is not None:(args.out/'capture.json').write_text(json.dumps(packet,indent=2)+'\n')
 (args.out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
