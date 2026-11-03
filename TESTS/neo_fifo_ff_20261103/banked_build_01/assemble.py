#!/usr/bin/env python3
"""Graft the already-qualified banked helper twice; never synthesize or route.

Uses the frozen original FF substitution/inverse implementation. The application
is not regenerated. Only two SDPB cell types and their twelve defparams change.
"""
import gzip,hashlib,importlib.util,json,re,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RECIPE=ROOT/'TESTS/neo_fifo_ff_20261102/build_review_01/recipe.py'
RECIPE_SHA='9bc4bfc1e93316fd714690cd4fe7c02e0d64d20e906bdb6de5e11f04aabcdb5e'
HELP=ROOT/'TESTS/neo_fifo_ff_20261102/banked_storage_01'
DELIVERY_SHA='8472ba616e3065e2b1c89d6b1e0f73f74724ec338cc22c8c02ca9f2f997cd1a9'
QUAL_SHA='9087c9301555169e79356904c41fbceb5d1a34a0b7442893e249f20ea02e3721'
HELP_SHA='e5c576bdb1f439870279e1051ef790e16fcea9b107dc4df9375b4efb115de41f'
TARGET_PREFIXES=['u_accel/u_commands/g_inferred_storage.mem_g_inferred_storage.mem_0_0_s',
                 'u_accel/u_blitter/cmem_cmem_0_0_s']

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def need(ok,why):
 if not ok:raise ValueError(why)
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def load_recipe():
 need(sha(RECIPE)==RECIPE_SHA,'Frozen recipe changed')
 s=importlib.util.spec_from_file_location('frozen_two_fifo_builder',RECIPE)
 r=importlib.util.module_from_spec(s);s.loader.exec_module(r);return r

def guards():
 r=load_recipe();r.guards()
 need(sha(HELP/'DELIVERY.json')==DELIVERY_SHA and sha(HELP/'QUALIFICATION.json')==QUAL_SHA,'Helper proof changed')
 d=json.loads((HELP/'DELIVERY.json').read_text());q=json.loads((HELP/'QUALIFICATION.json').read_text())
 need(d['passed'] and q['passed'] and q['helper_sha256']==HELP_SHA,'Helper not qualified')
 for name,h in d['files'].items():
  p=HELP/name;need(p.resolve().is_relative_to(HELP) and not p.is_symlink() and sha(p)==h,'Helper delivery dependency changed '+name)
 for name,h in q['files'].items():need(sha(ROOT/name)==h,'Qualification dependency changed '+name)
 vg=HELP/'stage_02/helper/neo_command_ff128.vg';need(sha(vg)==HELP_SHA,'Helper bytes changed')
 return r,d,q,vg

def exact_graft(candidate,application,helper):
 need(candidate==application+'\n\n'+helper+'\n','Candidate is not the exact two-cell graft plus qualified helper')

def main():
 started=time.monotonic();r,d,q,vg=guards();out=HERE/'assembly_01';need(not out.exists(),'Assembly already exists')
 original=(r.BASE/'console_neo.vg').read_text();helper=vg.read_text()
 application,rows=r.replace_memories(original) # Includes byte-exact inverse and every original port check.
 a=r.modules_api();hm=a.modules(helper);base=a.modules(original);after=a.modules(application)
 need(set(hm)=={'neo_command_ff128'} and not set(base)&set(hm),'Helper hierarchy collision')
 need(sum(c['kind']=='neo_command_ff128' for b in after.values()for c in a.instances(b).values())==2,'Wrong helper instance count')
 need(set(base)==set(after),'Application module inventory changed')
 # The frozen transformation checks all original instances/ports in both modified modules.
 # Prove the full inverse again by exact restoration of just these two modules.
 inverse=application
 for module in r.TARGETS:inverse=inverse.replace(after[module],base[module],1)
 need(inverse==original,'Full application inverse not byte exact')
 cst=(r.BASE/'neo.cst').read_text();anchors=re.findall(r'^INS_LOC\s+"([^"]+)"',cst,re.M)
 changed_targets=[x for x in anchors if any(x==p or x.startswith(p+'/') for p in TARGET_PREFIXES)]
 need(not changed_targets,'A replaced primitive is anchored by inherited CST')
 s400=ROOT/'tang/impl/console_neo_s400_20261031_r1'
 need(all((r.BASE/n).read_bytes()==(s400/n).read_bytes()for n in ['neo.cst','neo.sdc']),'S400 routing constraints differ from REJECT R1')
 merged=application+'\n\n'+helper+'\n';exact_graft(merged,application,helper)
 # Adversarial checks target the exact-graft invariant, no repeated simulation.
 mutants={'unrelated_application_byte':merged.replace('module ', 'module  ',1),
          'helper_bytes_changed':merged[:-1]+' ',
          'target_clock_changed':merged.replace('.CLKA(vid_hclk)', '.CLKA(gpu_clk)',1)}
 negative={}
 for name,text in mutants.items():
  need(text!=merged,'Mutation was not effective '+name)
  try:exact_graft(text,application,helper)
  except ValueError:negative[name]=True
  else:raise ValueError('Graft mutant escaped '+name)
 out.mkdir();archive=out/'console_neo.vg.gz';archive.write_bytes(gzip.compress(merged.encode(),mtime=0))
 record={'passed':True,'netlist_sha256':digest(merged),'archive_sha256':sha(archive),'base_sha256':digest(original),
  'helper_sha256':HELP_SHA,'helper_instance_count':2,'SDPB_removed':2,'removed_defparams':12,
  'application_modules':len(base),'unchanged_application_modules':len(base)-2,
  'application_inverse_exact':True,'connection_changes':0,'other_RAM_replacements':0,
  'constraints':r.PINS,'inherited_INS_LOC_count':len(anchors),'anchors_into_replaced_primitives':changed_targets,
  'constraints_equal_REJECT_R1_and_S400':True,'substitutions':rows,'graft_mutants_detected':negative,
  'PNR':False,'hardware':False,'application_resynthesized':False,'elapsed_seconds':time.monotonic()-started}
 save(out/'assembly.json',record)
 files=[archive,out/'assembly.json',Path(__file__),RECIPE,vg,HELP/'DELIVERY.json',HELP/'QUALIFICATION.json']
 files += [ROOT/n for n in q['files']]
 files += [r.BASE/n for n in ['console_neo.vg','neo.cst','neo.sdc']]
 qual={'passed':True,'netlist_sha256':record['netlist_sha256'],'helper_qualification_sha256':QUAL_SHA,
  'application_inverse_exact':True,'connections_changed':0,'helper_instances':2,
  'scope':'Qualified helper reused twice; exact source-netlist graft. No application simulation/STA/PNR.',
  'independent_parent_review':'pending','files':{str(p.relative_to(ROOT)):sha(p) for p in files},'PNR':False,'hardware':False}
 save(HERE/'QUALIFICATION.json',qual)
 print(json.dumps({k:record[k] for k in ['passed','netlist_sha256','application_modules','unchanged_application_modules','elapsed_seconds']},indent=2))
if __name__=='__main__':main()
