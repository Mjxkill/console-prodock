"""Protected full chain CSR observer; exact readonly RTL and payload checks."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,tempfile
HERE=Path(__file__).resolve().parent

def main():
  for n,s in json.loads((HERE/'INPUTS.json').read_text()).items():assert hashlib.sha256((HERE/n).read_bytes()).hexdigest()==s,n
  with tempfile.TemporaryDirectory(prefix='copy-width-csr-') as raw:
    out=Path(raw)
    cmd=['/usr/bin/verilator','--binary','--timing','-j','2','-Wno-fatal','-MAKEFLAGS','VM_PARALLEL_BUILDS=0','--top-module','bench','--Mdir',str(out/'obj'),'bench.sv']
    cmd += [p.name for p in sorted(HERE.glob('*.v'))]
    b=subprocess.run(cmd,cwd=HERE,text=True,capture_output=True,timeout=48)
    assert b.returncode==0,(b.stdout+b.stderr)[-4000:]
    results=[]
    for seed,width,inj in [(1,w,i) for w in (16,1) for i in range(5)]+[(8,16,0),(8,1,2)]:
      r=subprocess.run([str(out/'obj/Vbench'),f'+seed={seed}',f'+width={width}',f'+injection={inj}'],cwd=HERE,text=True,capture_output=True,timeout=2)
      assert r.returncode==0,r.stdout+r.stderr
      if '--infra' in sys.argv:print('COMPILE_EXEC_INFRA_PASS');return
      rows=re.findall(r'^OBS width=(\d+) injection=(\d+) done=(\d+) busy=(\d+) reject=(\d+) errors=(\d+) lost=(\d+) geom_errors=(\d+) geom_cycles=(\d+) words=(\d+) native=(\d+)$',r.stdout,re.M)
      assert len(rows)==1,r.stdout
      wanted=[width,inj,2,0,0 if inj==0 or (inj==2 and width==1) else 1,0,0,0,4,16,0]
      assert list(map(int,rows[0]))==wanted,(rows,wanted)
      results.append(dict(seed=seed,width=width,injection=inj,observed=wanted,stdout=r.stdout))
    print(json.dumps(dict(passed=True,hardware=False,cases=results)))
if __name__=='__main__':main()
