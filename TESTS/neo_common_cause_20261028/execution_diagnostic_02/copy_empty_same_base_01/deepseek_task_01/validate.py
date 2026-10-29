"""Protected exact RTL cases; the model implements only construction of stimuli."""
from pathlib import Path
import hashlib,importlib.util,json,re,subprocess,sys,tempfile
HERE=Path(__file__).resolve().parent

def main():
  pins=json.loads((HERE/'INPUTS.json').read_text())
  for n,s in pins.items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==s,n
  fixtures=json.loads((HERE/'expected.json').read_text())
  if '--infra' in sys.argv:cases=fixtures[:1]
  else:
    spec=importlib.util.spec_from_file_location('case_module',HERE/'cases.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);cases=mod.cases()
    assert cases==fixtures,'Construct all10specified boundary cases exactly, including independent expectations'
  with tempfile.TemporaryDirectory(prefix='copy-same-base-') as raw:
    tmp=Path(raw)
    cmd=['/usr/bin/verilator','--binary','--timing','-j','2','-Wno-fatal',
      '-MAKEFLAGS','VM_PARALLEL_BUILDS=0','--top-module','bench','--Mdir',str(tmp/'obj'),
      str(HERE/'bench.sv'),str(HERE/'gpu_copy565.v')]
    build=subprocess.run(cmd,text=True,capture_output=True,timeout=40)
    assert build.returncode==0,(build.stdout+build.stderr)[-4000:]
    results=[]
    for c in cases:
      (tmp/'packet.hex').write_text(''.join(f'{w:08x}\n' for w in c['command']))
      run=subprocess.run([str(tmp/'obj/Vbench'),f'+force_end={c["force_end"]}'],cwd=tmp,
        text=True,capture_output=True,timeout=2)
      assert run.returncode==0,run.stdout+run.stderr
      found=re.findall(r'^RESULT done=(\d+) bad=(\d+) requests=(\d+) cycles=(\d+)$',run.stdout,re.M)
      assert len(found)==1,run.stdout
      got=list(map(int,found[0]));assert got[:3]==[1,c['bad'],0] and 0<got[3]<200,(c,got)
      results.append(dict(case=c['name'],observed=got,stdout=run.stdout))
    print(json.dumps(dict(passed=True,hardware=False,infrastructure_only='--infra' in sys.argv,cases=results)))
if __name__=='__main__':main()
