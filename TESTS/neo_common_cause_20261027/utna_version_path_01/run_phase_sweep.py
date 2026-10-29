"""Functional phase/ratio stress of exact netlist; no hardware or SDF."""
import concurrent.futures,hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'utna_header_netlist_01'
OUT=HERE/'phase_sweep_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 OUT.mkdir(exist_ok=False)
 pairs=[(6.25,8.333333),(8.333333,6.25),(6.25,6.25),(8.333333,8.341),(4.166667,8.333333),(12.5,4.166667)]
 tasks=[(i,h,u,p) for i,(h,u,p) in enumerate((h,u,p) for h,u in pairs for p in (0,.001,.317,3.713))]
 def run(task):
  i,h,u,p=task;cmd=['nice','-n','10','/tmp/console-usb-sim-tools/extracted/usr/bin/vvp',str(BASE/'test.vvp'),f'+hp={h}',f'+up={u}',f'+phase={p}']
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
  log=OUT/f'case_{i:02}.log';log.write_text(r.stdout+r.stderr)
  return dict(index=i,half_period_h_ns=h,half_period_u_ns=u,phase_ns=p,returncode=r.returncode,passed=r.returncode==0 and 'PASS EXACT SNAPSHOT seq=4' in r.stdout,log_sha256=sha(log))
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:records=list(pool.map(run,tasks))
 result=dict(hardware_access=False,SDF_annotation=False,passed=all(x['passed'] for x in records),cases=records,
             input_sha256={str(p):sha(p) for p in [Path(__file__),BASE/'test.vvp',BASE/'tb.sv',BASE/'exact_modules.v']},
             limits=['Four commands/case, model timing only. No analog metastability or actual reset waveform model.','Stress clock ratios do not assert those frequencies are supported hardware settings.','Passing does not reproduce or resolve the hardware version0.'])
 (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(passed=result['passed'],cases=len(records),hardware_access=False)))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
