#!/usr/bin/env python3
"""Read guards and generate a TCL string only; never prepare/run the PNR directory."""
import hashlib,importlib.util,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def main():
 start=time.monotonic();spec=importlib.util.spec_from_file_location('banked_route_entry',HERE/'route.py')
 e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
 if e.OUT.exists():raise ValueError('Candidate directory already exists; this is not a fresh dry-run')
 b=e.route.configured(HERE/'route.py',HERE,e.OUT,e.NET,e.DELIVERY)
 guard=b.guards();script=b.script()
 base=ROOT/'tang/impl/console_neo_reject_20261102_r1'
 expected=(base/'build.tcl').read_text()
 for name in ['console_neo.vg','neo.cst','neo.sdc']:expected=expected.replace(str(base/name),str(e.OUT/name))
 if script!=expected:raise ValueError('Routing options changed beyond three input paths')
 if e.OUT.exists():raise ValueError('Dry-run created a build directory')
 result={'passed':True,'PNR':False,'hardware':False,'output_directory_created':False,
  'candidate':str(e.OUT.relative_to(ROOT)),'netlist_sha256':e.NET,
  'route_options_equal_REJECT_R1_except_paths':True,'generated_tcl_sha256':hashlib.sha256(script.encode()).hexdigest(),
  'local_regressions':guard['local_regressions'],'mapped_delivery_sha256':e.DELIVERY,
  'elapsed_seconds':time.monotonic()-start,'limits':'Guard/TCL generation only; frontend/place/route not executed.'}
 (HERE/'DRY_RUN.json').write_text(json.dumps(result,indent=2)+'\n');(HERE/'build_expected.tcl').write_text(script)
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
