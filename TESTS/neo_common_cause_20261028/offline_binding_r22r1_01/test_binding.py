#!/usr/bin/env python3
"""Identity/provenance tests; only temporary local fixtures are mutated."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import offline_capture as oc
import test_inherited as inherited
HERE=Path(__file__).resolve().parent

def main():
 cases=[];good=inherited.fixture()
 spec=importlib.util.spec_from_file_location('frozen_original_decoder',oc.FROZEN/'offline_capture.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 def case(name,condition):
  if not condition:raise AssertionError(name)
  cases.append(dict(name=name,passed=True))
 case('adapter binds actual new identity',good['candidate_netlist_sha256']==oc.NET_SHA and oc.decode(good)['passed'])
 case('frozen original refuses new identity',not old.decode(good)['passed'])
 prior=copy.deepcopy(good);prior['candidate_netlist_sha256']=oc.ORIGINAL_NET_SHA
 case('new adapter refuses original identity',not oc.decode(prior)['passed'])
 case('frozen original accepts only its original fixture identity',old.decode(prior)['passed'])
 origbytes=(oc.FROZEN/'offline_capture.py').read_bytes();bound=(HERE/'decoder_bound.py').read_bytes()
 oldtok=("NET_SHA='"+oc.ORIGINAL_NET_SHA+"'").encode();newtok=("NET_SHA='"+oc.NET_SHA+"'").encode()
 case('decoder single exact literal substitution reversible',bound.replace(newtok,oldtok,1)==origbytes and origbytes.count(oldtok)==bound.count(newtok)==1)
 for key in ['reads','schema','origin','board','expected_command','expected_sequence','bitstream_sha256']:
  case('packet field retained '+key,good[key]==prior[key])
 with tempfile.TemporaryDirectory(prefix='utw1-binding-') as d:
  root=Path(d);(root/'dep').write_bytes(b'original');digest=oc.file_sha(root/'dep')
  oc.verify_files(root,{'dep':digest});case('expected dependency accepted',True)
  (root/'dep').write_bytes(b'mutated')
  try:oc.verify_files(root,{'dep':digest})
  except ValueError:case('modified dependency rejected',True)
  else:raise AssertionError('modified dependency accepted')
  (root/'decoder_bound.py').write_bytes(bound+b'\n# mutated\n')
  saved=oc.HERE
  try:
   oc.HERE=root;result=oc.decode(good)
   case('bound file mutation after import refuses decode',result['status']=='INVALID_PROVENANCE' and not result['passed'])
  finally:oc.HERE=saved
 # Every original semantic result stays identical; provenance is the only new result field.
 expected=old.decode(prior);got=oc.decode(good);got.pop('decoder_provenance')
 case('semantic result equals original for valid fixture',got==expected)
 for raw in (0,1):
  new=copy.deepcopy(good);inherited.set_word(new,0x44,0);inherited.set_word(new,0xcc,raw);inherited.set_word(new,0xd4,raw)
  prior=copy.deepcopy(new);prior['candidate_netlist_sha256']=oc.ORIGINAL_NET_SHA
  result=oc.decode(new);result.pop('decoder_provenance')
  case('version0 semantic result and FAIL retained raw'+str(raw),result==old.decode(prior) and result['qualification']=='FAIL' and not result['passed'])
 report=dict(passed=True,hardware_access=False,cases=cases,inputs={str(p):oc.file_sha(p) for p in [Path(__file__),HERE/'offline_capture.py',HERE/'decoder_bound.py',HERE/'test_inherited.py']})
 (HERE/'binding_tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(cases))))
if __name__=='__main__':main()
