"""Protected exact-RTL harness, public observations plus independent scoreboard."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,tempfile
HERE=Path(__file__).resolve().parent

def main():
    pins=json.loads((HERE/'INPUTS.json').read_text())
    for name,sha in pins.items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha,name
    with tempfile.TemporaryDirectory(prefix='r19-sequence-') as raw:
        out=Path(raw)
        cmd=['/usr/bin/verilator','--binary','--timing','-j','2','-Wno-fatal',
          '-MAKEFLAGS','VM_PARALLEL_BUILDS=0','--top-module','bench','--Mdir',str(out/'obj'),'bench.sv']
        cmd += [p.name for p in sorted(HERE.glob('*.v'))]
        build=subprocess.run(cmd,cwd=HERE,text=True,capture_output=True,timeout=48)
        assert build.returncode==0,(build.stdout+build.stderr)[-5000:]
        cases=[]
        for seed,inj,fault in [(1,0,0),(8,0,0),(1,0,1),(1,0,2),(1,1,0),(1,2,0),(1,3,0)]:
            run=subprocess.run([str(out/'obj/Vbench'),f'+seed={seed}',f'+injection={inj}',f'+fault={fault}'],cwd=HERE,text=True,capture_output=True,timeout=2)
            assert run.returncode==0,run.stdout+run.stderr
            if '--infra' in sys.argv:
                print('COMPILE_AND_EXEC_INFRA_PASS');return
            values=re.findall(r'^SEQUENCE_RESULT injection=(\d+) clear_reject=(\d+) copy_reject=(-?\d+) done=(\d+) words=(\d+) native=(\d+)$',run.stdout,re.M)
            assert len(values)==1,run.stdout
            wanted=[inj,1 if inj==1 else 0,-1 if inj==1 else int(inj>1),2 if inj==1 else 3,16 if inj==1 else 24,0]
            assert list(map(int,values[0]))==wanted,(values,wanted)
            cases.append(dict(seed=seed,injection=inj,readiness_fault=fault,observed=wanted,stdout=run.stdout))
        print(json.dumps(dict(passed=True,hardware=False,cases=cases)))
if __name__=='__main__':main()
