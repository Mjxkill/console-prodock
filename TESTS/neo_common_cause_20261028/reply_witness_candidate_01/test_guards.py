#!/usr/bin/env python3
"""Offline negative guards and byte-identical reverse proof, no tool launch."""
from pathlib import Path
import json
import tempfile
import prepare_candidate as pc
HERE=Path(__file__).resolve().parent

def main():
 out=pc.new_output(HERE/'guard_tests_01');records=[]
 def reject(name,call,contains):
  try:call()
  except (RuntimeError,FileExistsError) as exc:
   pc.require(contains in str(exc),'wrong rejection '+str(exc));records.append(dict(name=name,passed=True,error=str(exc)));return
  raise RuntimeError('guard accepted '+name)
 original=(pc.PARENT/'console_neo.vg').read_text()
 helper=pc.block((HERE/'mapping_02/helper_mapped.v').read_text(),'neo_usb_reply_witness')
 with tempfile.TemporaryDirectory(prefix='utw_identity_') as temp:
  fake=Path(temp);(fake/'console_neo.vg').write_text('wrong parent')
  reject('wrong parent netlist SHA',lambda:pc.parent_guard(fake),'parent identity console_neo.vg')
 reject('output outside isolated folder',lambda:pc.new_output(Path('/tmp/utw_forbidden')),'output must be')
 reject('existing output',lambda:pc.new_output(out),'File exists')
 old=pc.block(original,'usb_idle_trace')
 # All mutants exist only in Python strings. The frozen parent is never edited.
 for pin,value in [('CLK','GND'),('RESET','GND'),('CE','VCC'),('Q','wrong_output')]:
  cell=pc.cells(old)['hrdata_0_s0'][1]
  before='  DFFRE hrdata_0_s0 ('
  start=old.index(before);end=old.index(');',start)+2
  segment=old[start:end]
  segment=pc.once(segment,'.'+pin+'('+cell[pin]+')','.'+pin+'('+value+')')
  mutant=original.replace(old,old[:start]+segment+old[end:],1)
  reject('unexpected read '+pin,lambda m=mutant:pc.transform(m,helper),'read register mismatch')
 reject('preexisting witness',lambda:pc.transform(original+'\n// neo_usb_reply_witness\n',helper),'already present')
 reject('reserved name collision',lambda:pc.transform(original.replace(old,old.replace('endmodule','wire utw_collision;\nendmodule'),1),helper),'reserved name collision')
 # Exhaustively verify the added mux truth table independently of simulation.
 for select in range(2):
  for witness in range(2):
   for baseline in range(2):
    got=(0xca>>(baseline+2*witness+4*select))&1
    pc.require(got==(witness if select else baseline),'bad LUT3 truth table')
 records.append(dict(name='all eight mux cofactors',passed=True))
 merged,observer,audit=pc.transform(original,helper)
 expected=(HERE/'candidate_01/console_neo.vg').read_text()
 pc.require(merged==expected,'nonreproducible transform')
 pc.require(audit['original_recovered_byte_identical'],'not reversible')
 records.append(dict(name='exact assembly reproduced and reverse SHA baseline',passed=True,netlist_sha256=pc.sha(HERE/'candidate_01/console_neo.vg')))
 pc.parent_guard()
 result=dict(passed=True,hardware_access=False,tool_launched=False,cases=records,
  inputs={str(p):pc.sha(p) for p in [Path(__file__),HERE/'prepare_candidate.py',HERE/'candidate_01/assembly.json']})
 pc.save(out/'result.json',result);print(json.dumps(dict(passed=True,cases=len(records))))
if __name__=='__main__':main()
