#!/usr/bin/env python3
"""Test isolated Tcl ordering fix against held snapshots, without a hardware controller."""
import ast,importlib.util,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'combined_gpu_usb_prepared_01'
spec=importlib.util.spec_from_file_location('combined_frozen',OLD/'controller.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
def literal(path,name):
 t=ast.parse(path.read_text())
 return next(ast.literal_eval(n.value) for n in t.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id==name for x in n.targets))
base=literal(c.PARENT/'test_collector.py','HARNESS').split('source [lindex $argv 1]')[0]
extra=literal(OLD/'test_combined.py','EXTRA')
extra=extra.replace('set gpuwords 0','set gpuwords 0\narray set held {0xe9005000 0 0xe9006000 0}',1)
extra=extra.replace('global snap gpuwords gpudone fault','global snap gpuwords gpudone fault held')
extra=extra.replace('global snap gpuwords gpudone frames fault','global snap gpuwords gpudone frames fault held')
extra=extra.replace('incr snap($base);return', '''incr snap($base)
  set held($base) [expr {$base==0xe9005000?($fault eq "gpu_lost" && $gpuwords?7:$gpuwords):0}]
  if {$fault eq "second_snapshot_timeout" && $snap($base)>1} {incr snap($base) -1}
  return''')
extra=extra.replace('lset v 4 $gpuwords','lset v 4 $held($base)')
extra=extra.replace('16 {return [expr {$fault eq "gpu_lost" && $gpuwords?7:$gpuwords}]}','16 {return $held($base)}')
begin,finish=c.parts()
# A local candidate only: request GPU_AFTER_MATRIX after polling done, before
# comparing +0x10. Remove the former outside call so there is still one capture.
old=' set sent_after [lindex [read_memory 0xe9005008 32 1] 0]'
assert begin.count(old)==1
begin=begin.replace(old,' if {![cv_snapshot 0xe9005000 GPU_AFTER_MATRIX]} {return}\n'+old)
outside='\ncv_snapshot 0xe9005000 GPU_AFTER_MATRIX\ncv_video AFTER_MATRIX'
assert begin.count(outside)==1
begin=begin.replace(outside,'\ncv_video AFTER_MATRIX')
out=HERE/'snapshot_fix_tests';out.mkdir(exist_ok=False)
for name,text in [('harness.tcl',base+extra),('begin.tcl',begin),('finish.tcl',finish)]: (out/name).write_text(text)
cases=[]
for fault,want in [('good',True),('gpu_lost',False),('gpu_timeout',False),('second_snapshot_timeout',False),('source_stopped',False),('snapshot_timeout',False),('video_stopped',False),('version0',False),('raw0',False)]:
 p=subprocess.run(['tclsh',str(out/'harness.tcl'),fault,str(out/'begin.tcl'),str(out/'finish.tcl')],capture_output=True,text=True,timeout=10)
 (out/(fault+'.log')).write_text(p.stdout+p.stderr)
 assert p.returncode==0,(fault,p.stderr)
 r=c.parse(p.stdout,'a'*64,origin='synthetic')
 assert r['protocol_passed']==want,(fault,r['combined_errors'])
 if want:assert r['matrix']['AFTER'][:3]==[8,8,1] and r['snapshots']['GPU_AFTER_MATRIX'][3]==2
 cases.append(dict(name=fault,passed=True,protocol_passed=r['protocol_passed'],errors=r['combined_errors']))
result=dict(passed=True,hardware_access=False,controller_created=False,cases=cases,inputs={str(p):c.sha(p) for p in [OLD/'controller.py',OLD/'test_combined.py',c.PARENT/'test_collector.py',Path(__file__)]},outputs={str(p):c.sha(p) for p in out.iterdir() if p.is_file()})
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(cases),hardware_access=False)))
