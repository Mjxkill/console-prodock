"""Protected bounded simulator driver; case expectations are external inputs."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
RTL_SHA='c0cbb102eb701ae861cc389b30827b7ac856e3b4b3ff341cda092fd61ecd0741'


def main():
    assert hashlib.sha256((HERE/'gpu_copy565.v').read_bytes()).hexdigest()==RTL_SHA
    cases=json.loads((HERE/'cases.json').read_text())
    results=[]
    with tempfile.TemporaryDirectory(prefix='copy-rejection-') as raw:
        out=Path(raw)
        cmd=['/usr/bin/verilator','--binary','--timing','-j','2','-Wno-fatal',
             '-MAKEFLAGS','VM_PARALLEL_BUILDS=0','--top-module','bench',
             '--Mdir',str(out/'obj'),'bench.sv','gpu_copy565.v']
        build=subprocess.run(cmd,cwd=HERE,text=True,capture_output=True,timeout=40)
        assert build.returncode==0,(build.stdout+build.stderr)[-6000:]
        if '--infra' in sys.argv:
            run=subprocess.run([str(out/'obj/Vbench'),'+case=0'],cwd=HERE,
                               text=True,capture_output=True,timeout=2)
            assert run.returncode==0,run.stdout+run.stderr
            print('INFRA_COMPILE_EXEC_PASS; no functional claim for scaffold')
            return
        for i,case in enumerate(cases):
            run=subprocess.run([str(out/'obj/Vbench'),f'+case={i}'],cwd=HERE,
                               text=True,capture_output=True,timeout=2)
            assert run.returncode==0,case['name']+': '+run.stdout+run.stderr
            lines=re.findall(r'^RESULT case=(\d+) done=(\d+) bad=(\d+) reads=(\d+) writes=(\d+) payload_ok=(\d+) late_io=(\d+) cycles=(\d+)$',run.stdout,re.M)
            assert len(lines)==1,(case['name'],run.stdout)
            values=list(map(int,lines[0]))
            assert values[:7]==[i,1,case['bad'],case['reads'],case['writes'],1,0],(case,values)
            assert 0<values[7]<=1000,(case,values)
            results.append({'case':case['name'],'observed':values,'log':run.stdout})
    print(json.dumps({'passed':True,'cases':results,'scope':'RTL copy engine; not synthesized netlist or hardware'}))


if __name__=='__main__':main()
