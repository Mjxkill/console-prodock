#!/usr/bin/env python3
"""Assemble reset-only Neo candidate. No route or hardware access."""
from pathlib import Path
import sys,json,re,hashlib,shutil
HERE=Path(__file__).resolve().parent
ROOT=Path('/home/michael/console')
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(HERE.parents[1]))
from board_contract import before_build,record_build
from build_memory_capture import block,cells,params,manifest,once
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PARENT=ROOT/'tang/impl/console_neo_n56r21r1_capture_memory'
OUT=ROOT/'tang/impl/console_neo_n56r21r2_resetqual'
NET='3f49d84ccb8b2001e5afa156b36849705652003fbf4e2a741847dc23f1713338'
assert sha(PARENT/'console_neo.vg')==NET
assert sha(PARENT/'impl/pnr/console_neo.fs')=='2fd6f3b01bee26a835aefcef3c34712de649f0af4e1fa24ff5bb4983430200d7'
old_manifest=json.loads((PARENT/'sources.json').read_text());assert old_manifest==manifest(PARENT/'source')
cm=json.loads((HERE/'candidate_manifest.json').read_text())
for n,h in cm['candidate_files'].items():assert sha(HERE/n)==h,n
syn=HERE/'synthesis_02';sr=json.loads((syn/'result.json').read_text());assert sr['passed']
for n,h in sr['inputs'].items():assert sha(Path(n))==h,n
assert sha(syn/'neo_reset_trial.vg')==sr['netlist_sha256']
proof_paths=[HERE/n/'simulation.log' for n in ['vlt_v2_p1000','vlt_v2_p3125','vlt_v2_p11000','icarus_v2_p1000']]
for p in proof_paths:assert 'INVARIANTS_PASS' in p.read_text() and 'releases=15' in p.read_text(),p
contract=before_build('neo',candidate=True)
original=(PARENT/'console_neo.vg').read_text()
old_helper=block(original,'neo_reset_trial');new_helper=block((syn/'neo_reset_trial.vg').read_text(),'neo_reset_trial')
new_helper,n=re.subn(r'  GSR GSR \(\s*\.GSRI\(VCC\)\s*\);','',new_helper);assert n==1
# Keep the old UART implementation byte-identical; recompiled helper port contract is exact.
for s in (old_helper,new_helper):
 m=re.search(r'neo_reset_trial_rx u_rx \([^;]*;',s,re.S);assert m
 assert m.group()==re.search(r'neo_reset_trial_rx u_rx \([^;]*;',old_helper,re.S).group()
old_soc=block(original,'ae350_soc');new_soc=old_soc
clear='neo_qualified_clear'
assert clear not in original
first_wire=re.search(r'^wire ',new_soc,re.M).start()
new_soc=new_soc[:first_wire]+'wire '+clear+';\n'+new_soc[first_wire:]
for name in ['init_sync_0_s0','init_sync_1_s0']:
 pat=r'^  DFFCE '+name+r' \([^;]*;'
 c=re.search(pat,new_soc,re.M|re.S).group();assert '.CLEAR(ae350_rst_sync[1])' in c
 new_soc=once(new_soc,c,c.replace('.CLEAR(ae350_rst_sync[1])','.CLEAR('+clear+')'))
gate="""  LUT2 neo_qualified_clear_lut (
    .F(neo_qualified_clear),
    .I0(ae350_rst_sync[1]),
    .I1(trial_release)
);
defparam neo_qualified_clear_lut.INIT=4'hB;
"""
new_soc=once(new_soc,'endmodule',gate+'endmodule')
merged=once(once(original,old_helper,new_helper),old_soc,new_soc)
assert once(once(merged,new_soc,old_soc),new_helper,old_helper)==original
names=re.findall(r'^module (\w+)\b',original,re.M)
changed=[n for n in names if block(original,n)!=block(merged,n)]
assert set(changed)=={'neo_reset_trial','ae350_soc'}
assert len(re.findall(r'^\s*GSR GSR \(',merged,re.M))==1
oc,nc=cells(old_soc),cells(new_soc);op,np=params(old_soc),params(new_soc)
assert set(nc)-set(oc)=={'neo_qualified_clear_lut'}
assert {n for n in oc if oc[n]!=nc[n]}=={'init_sync_0_s0','init_sync_1_s0'}
assert all(np[k]==v for k,v in op.items())
OUT.mkdir(exist_ok=False);record_build(OUT,contract)
shutil.copytree(PARENT/'source',OUT/'source')
for name in ['neo_reset_trial.v','console_neo.v']:shutil.copy2(HERE/name,OUT/'source/tang/boards/neo'/name)
for n in ['font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex']:
 d=OUT/n;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/n,d)
(OUT/'console_neo.vg').write_text(merged)
(OUT/'build.tcl').write_text((PARENT/'build.tcl').read_text().replace(str(PARENT),str(OUT)))
new_manifest=manifest(OUT/'source')
assert set(new_manifest)==set(old_manifest)
assert sorted(n for n in new_manifest if new_manifest[n]!=old_manifest[n])==['tang/boards/neo/console_neo.v','tang/boards/neo/neo_reset_trial.v']
(OUT/'sources.json').write_text(json.dumps(new_manifest,indent=2)+'\n')
for n in ['neo.cst','neo.sdc']:assert (OUT/'source/tang/boards/neo'/n).read_bytes()==(PARENT/'source/tang/boards/neo'/n).read_bytes()
r=dict(candidate=True,passed=True,hardware_access=False,routing_started=False,release_qualified=False,parent=str(PARENT),build=str(OUT),parent_netlist_sha256=NET,parent_bitstream_sha256=sha(PARENT/'impl/pnr/console_neo.fs'),complete_parent_recovered_by_undo=True,changed_modules=changed,unchanged_module_count=len(names)-2,old_uart_preserved=True,soc_added_primitive='LUT2 neo_qualified_clear_lut INIT=B',soc_changed_pins=['init_sync_0_s0.CLEAR','init_sync_1_s0.CLEAR'],cst_unchanged=True,sdc_unchanged=True,pnr_options_unchanged=True,mode0_min_cycles=104000,mode1_wait_cycles=2500000,local_regressions=contract['local_regressions'],external_inputs={str(p):sha(p) for p in [Path(__file__),HERE/'candidate_manifest.json',HERE/'invariants_tb.sv',syn/'neo_reset_trial.vg',syn/'result.json',*proof_paths]},inputs={n:sha(OUT/n) for n in ['console_neo.vg','sources.json','build.tcl','source/tang/boards/neo/neo.cst','source/tang/boards/neo/neo.sdc']},limits=['Mapped integrated reset cone test must pass before route.','Physical recovery/removal and asynchronous minimum pulse width not qualified.','No evidence that reproduced RTL defects caused R21 board failure.'])
(OUT/'assembly.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(dict(build=str(OUT),netlist_sha256=sha(OUT/'console_neo.vg'),assembly_sha256=sha(OUT/'assembly.json'),changed_modules=changed),indent=2))
