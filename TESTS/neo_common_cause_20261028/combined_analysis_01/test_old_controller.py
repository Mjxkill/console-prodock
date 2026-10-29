#!/usr/bin/env python3
"""Counterexample to the old synthetic model: retain received until snapshot."""
import ast, importlib.util, json, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'combined_gpu_usb_prepared_01'
spec=importlib.util.spec_from_file_location('frozen_combined',OLD/'controller.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
tree=ast.parse((OLD/'test_combined.py').read_text())
extra=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='EXTRA' for x in n.targets))
pt=ast.parse((c.PARENT/'test_collector.py').read_text())
harness=next(ast.literal_eval(n.value) for n in pt.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='HARNESS' for x in n.targets)).split('source [lindex $argv 1]')[0]
# Change only the model of +16 to the actual held counter semantics.
extra=extra.replace('set gpuwords 0','set gpuwords 0\nset held_received 0',1)
extra=extra.replace('global snap gpuwords gpudone fault','global snap gpuwords gpudone fault held_received')
extra=extra.replace('global snap gpuwords gpudone frames fault','global snap gpuwords gpudone frames fault held_received')
extra=extra.replace('incr snap($base);return','incr snap($base);set held_received $gpuwords;return')
extra=extra.replace('16 {return [expr {$fault eq "gpu_lost" && $gpuwords?7:$gpuwords}]}','16 {return $held_received}')
assert '16 {return $held_received}' in extra
out=HERE/'old_controller_counterexample';out.mkdir(exist_ok=False)
begin,finish=c.parts()
for name,text in [('harness.tcl',harness+extra),('begin.tcl',begin),('finish.tcl',finish)]: (out/name).write_text(text)
p=subprocess.run(['tclsh',str(out/'harness.tcl'),'good',str(out/'begin.tcl'),str(out/'finish.tcl')],capture_output=True,text=True,timeout=10)
(out/'capture.log').write_text(p.stdout+p.stderr)
assert p.returncode==0,p.stderr
r=c.parse(p.stdout,'a'*64,origin='synthetic')
assert r['matrix']['AFTER'][:3]==[8,0,1]
assert r['snapshots']['GPU_AFTER_MATRIX'][4]==8
assert not r['protocol_passed']
assert r['combined_errors']==['MATRIX counters_or_completion','Matrix counters failed']
result=dict(passed=True,hardware_access=False,old_test_model_defect_reproduced=True,original_controller_sha256=c.sha(OLD/'controller.py'),errors=r['combined_errors'],before=r['matrix']['BEFORE'],after=r['matrix']['AFTER'],fresh_received=r['snapshots']['GPU_AFTER_MATRIX'][4])
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
