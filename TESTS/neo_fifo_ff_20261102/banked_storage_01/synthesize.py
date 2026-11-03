#!/usr/bin/env python3
"""Only one isolated helper synthesis; reuse frozen project/process recipe.

No application netlist, assembler, PNR or hardware entry point is exposed.
Root coordinates global Gowin availability before --run is permitted.
"""
import argparse,hashlib,importlib.util,json,signal,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RECIPE=HERE.parent/'build_review_01/recipe.py'
TOP='neo_command_ff128'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load():
 spec=importlib.util.spec_from_file_location('frozen_ff_build',RECIPE)
 r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r);return r

def prepare(stage):
 if stage.exists() or not stage.is_relative_to(HERE):raise ValueError('Fresh owned stage required')
 r=load();e=r.engine();r.guards()
 test=json.loads((HERE/'rtl_02/RESULT.json').read_text())
 if not test['passed']:raise ValueError('RTL equivalence not passed')
 source=HERE/'banked_words32.v'
 if test['files'].get(str(source))!=sha(source):raise ValueError('Tested source mismatch')
 stage.mkdir();(stage/'sources').mkdir();(stage/'helper').mkdir()
 (stage/'sources'/f'{TOP}.v').write_bytes(source.read_bytes());r.project(stage)
 record={'source_sha256':sha(source),'builder_sha256':sha(Path(__file__)),
  'recipe_sha256':sha(RECIPE),'test_sha256':sha(HERE/'rtl_02/RESULT.json'),
  'tool':str(e.IDE/'bin/GowinSynthesis'),'tool_sha256':sha(e.IDE/'bin/GowinSynthesis'),
  'primitive_library_sha256':sha(e.PRIMITIVES),'template_sha256':sha(r.TEMPLATE),
  'files':{str(p.relative_to(stage)):sha(p) for p in stage.rglob('*') if p.is_file()},
  'PNR':False,'hardware':False,'application_synthesis':False}
 (stage/'stage.json').write_text(json.dumps(record,indent=2)+'\n')

def check(stage,regressions):
 r=load();r.guards();e=r.engine();j=json.loads((stage/'stage.json').read_text())
 for name,h in j['files'].items():
  if sha(stage/name)!=h:raise ValueError('Staged input changed '+name)
 for field,path in [('builder_sha256',Path(__file__)),('recipe_sha256',RECIPE),
  ('test_sha256',HERE/'rtl_02/RESULT.json'),('source_sha256',HERE/'banked_words32.v'),
  ('tool_sha256',e.IDE/'bin/GowinSynthesis'),('primitive_library_sha256',e.PRIMITIVES),
  ('template_sha256',r.TEMPLATE)]:
  if j[field]!=sha(path):raise ValueError('Changed dependency '+field)
 guard=e.before_build('neo',candidate=True) if regressions else e.reference_check()
 return j,None,guard

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','check','run']);p.add_argument('--stage',type=Path,required=True);p.add_argument('--root-coordinated-helper-only',action='store_true');a=p.parse_args();stage=a.stage.resolve()
 if not stage.is_relative_to(HERE):raise ValueError('Outside ownership')
 if a.action=='prepare':prepare(stage)
 elif a.action=='check':check(stage,False)
 else:
  if not a.root_coordinated_helper_only:raise ValueError('Root coordination required')
  e=load().engine()
  # Same explicit configurable runner interface used by the original FF recipe.
  e.JOBS={'helper':(TOP,[TOP+'.v'])};e.check=lambda selected:check(selected,True)
  def interrupted(signum,frame):raise InterruptedError('Signal '+str(signum))
  old={s:signal.signal(s,interrupted) for s in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]}
  try:e.synthesize(stage)
  finally:
   for s,handler in old.items():signal.signal(s,handler)
 print('HELPER_ACTION_DONE',a.action,flush=True)
if __name__=='__main__':main()
