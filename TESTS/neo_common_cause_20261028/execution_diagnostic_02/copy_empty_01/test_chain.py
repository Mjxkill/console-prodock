"""Run the existing exact R19 chain with empty COPY; preserve prior proofs."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
PARENT=HERE.parent/'copy_probe_01'
SOURCES=HERE.parent/'clear_chain_01/deepseek_execution_02/isolation/tree'


def main():
    text=(PARENT/'bench_used.sv').read_text()
    assert hashlib.sha256(text.encode()).hexdigest()=='35124bcce0d322ce86f91d19ce0679ba9745ce0b6d9563a9a07ad8f0c2aeec8d'
    assert text.count("words[14] = 32'h00100001;")==1
    text=text.replace("words[14] = 32'h00100001;","words[14] = 32'h00000000;")
    assert text.count('accepted != 1')==2
    text=text.replace('accepted != 1','accepted != 0')
    text=text.replace('read_accepts != 1 || read_returns != 1','read_accepts != 0 || read_returns != 0')
    (HERE/'bench_used.sv').write_text(text)
    with tempfile.TemporaryDirectory(prefix='copy-empty-chain-') as raw:
        tmp=Path(raw)
        for path in SOURCES.iterdir():
            if path.suffix in ('.v','.hex'):shutil.copyfile(path,tmp/path.name)
        (tmp/'bench.sv').write_text(text)
        cmd=['/usr/bin/verilator','--binary','--timing','-j','2','-Wno-fatal',
             '-MAKEFLAGS','VM_PARALLEL_BUILDS=0','--top-module','bench','--Mdir',str(tmp/'obj'),
             'bench.sv']+[p.name for p in sorted(tmp.glob('*.v'))]
        compile_result=subprocess.run(cmd,cwd=tmp,text=True,capture_output=True,timeout=55)
        (HERE/'chain_compile.log').write_text(compile_result.stdout+compile_result.stderr)
        assert compile_result.returncode==0
        cases=[]
        for seed,fault in ((1,0),(8,0),(1,1),(1,2)):
            run=subprocess.run([str(tmp/'obj/Vbench'),f'+seed={seed}',f'+fault={fault}'],
                               cwd=tmp,text=True,capture_output=True,timeout=3)
            log=run.stdout+run.stderr
            (HERE/f'chain_seed{seed}_fault{fault}.log').write_text(log)
            assert run.returncode==0 and 'COPY_RESULT reads=0 returns=0 writes=0 words=16' in log,log
            cases.append(dict(seed=seed,fault=fault,passed=True))
        result={'passed':True,'hardware':False,'cases':cases,'bench_sha256':hashlib.sha256(text.encode()).hexdigest(),
                'RTL_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp.glob('*.v')},
                'scope':'Exact RTL, two clock phases and native readiness held low; no physical DDR'}
        (HERE/'chain_result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'passed':True,'cases':len(cases)}))


if __name__=='__main__':main()
