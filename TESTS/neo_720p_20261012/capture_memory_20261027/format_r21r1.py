#!/usr/bin/env python3
"""Move only newly-added wire declarations before use for Gowin's reader."""
import difflib
import json
from pathlib import Path
import re
import shutil
import build_memory_capture as b

OUT=b.ROOT/'tang/impl/console_neo_n56r21r1_capture_memory'
DECLS={
 'gpu_accel':'wire trace_pixel_valid;\n',
 'gpu_v1':'wire [23:0] trace_copy_sample;\n',
 'gpu_copy565':'wire trace_copy_idle,trace_copy_low_one,trace_copy_check,trace_copy_validate;\n'}

def main():
 b.prepared_guard();guard=b.before_build('neo',candidate=True)
 failed=json.loads((b.OUT/'route_result.json').read_text());assert failed['status']=='ROUTING_FAILED'
 log=(b.OUT/'build.log').read_text()
 assert "Net 'trace_copy_sample' is used in module'gpu_v1' but not declared in wire list" in log
 assert "Net 'trace_pixel_valid' is used in module'gpu_accel' but not declared in wire list" in log
 assert not re.search(r'Placement|Routing progress',log)
 assembly=json.loads((b.OUT/'assembly.json').read_text())
 assert b.sha(b.OUT/'console_neo.vg')==assembly['netlist_sha256']
 for name,h in assembly['inputs'].items():assert b.sha(b.OUT/name)==h,name
 original=(b.OUT/'console_neo.vg').read_text();merged=original;changes={}
 for name,declaration in DECLS.items():
  before=b.block(original,name);assert before.count(declaration)==1
  after=b.once(before,declaration,'')
  first=re.search(r'^wire ',after,re.M).start()
  after=after[:first]+declaration+after[first:]
  assert b.cells(before)==b.cells(after) and b.params(before)==b.params(after)
  assert sorted(re.findall(r'^assign [^;]+;',before,re.M))==sorted(re.findall(r'^assign [^;]+;',after,re.M))
  assert sorted(re.findall(r'^wire [^;]+;',before,re.M))==sorted(re.findall(r'^wire [^;]+;',after,re.M))
  assert b.once(before,declaration,'')==b.once(after,declaration,'')
  changes[name]=(before,after)
  merged=b.once(merged,before,after)
 undone=merged
 for before,after in changes.values():undone=b.once(undone,after,before)
 assert undone==original
 OUT.mkdir(exist_ok=False);shutil.copytree(b.OUT/'source',OUT/'source')
 for name in ['sources.json','font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex']:
  p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(b.OUT/name,p)
 shutil.copytree(b.OUT/'capture_ip',OUT/'capture_ip')
 (OUT/'console_neo.vg').write_text(merged)
 (OUT/'build.tcl').write_text((b.OUT/'build.tcl').read_text().replace(str(b.OUT),str(OUT)))
 assert b.manifest(OUT/'source')==json.loads((b.OUT/'sources.json').read_text())
 diff=''.join(difflib.unified_diff(original.splitlines(True),merged.splitlines(True),fromfile='R21/console_neo.vg',tofile='R21r1/console_neo.vg'))
 (OUT/'format.diff').write_text(diff)
 shutil.copy2(Path(__file__),OUT/'format_r21r1.py')
 proofs=[b.HERE/'root_review_01.json',b.HERE/'assembled_test_01/result.json',b.HERE/'wiring_audit.json']
 for proof in proofs:assert json.loads(proof.read_text())['passed']
 b.save(OUT/'format_assembly.json',dict(passed=True,candidate=True,hardware_access=False,routing_started=False,
  parent=str(b.OUT),parent_netlist_sha256=b.sha(b.OUT/'console_neo.vg'),netlist_sha256=b.sha(OUT/'console_neo.vg'),
  parent_assembly_sha256=b.sha(b.OUT/'assembly.json'),parent_failure_log_sha256=b.sha(b.OUT/'build.log'),
  parent_failure_result_sha256=b.sha(b.OUT/'route_result.json'),builder_sha256=b.sha(Path(__file__)),
  only_change='Move three new observation wire declarations before first wire/use; no token changes to cells/ports/assigns/parameters',
  moved_declarations=DECLS,parent_recovered_by_undo=True,same_sources=True,same_CST_SDC_DDR_PLL=True,
  proof_sha256={str(p):b.sha(p) for p in proofs},
  inputs={n:b.sha(OUT/n) for n in ['console_neo.vg','sources.json','build.tcl','format.diff',
     'source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc']}))
 b.record_build(OUT,guard)
 print('R21r1 format prepared, no route; netlist '+b.sha(OUT/'console_neo.vg'),flush=True)

if __name__=='__main__':main()
