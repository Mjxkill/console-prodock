"""Full exact R19 chain, changing only COPY source word from the prior empty test."""
import hashlib,json,re,shutil,struct,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'copy_empty_01'
SOURCES=HERE.parent/'clear_chain_01/deepseek_execution_02/isolation/tree'


def main():
    text=(OLD/'bench_used.sv').read_text()
    assert hashlib.sha256(text.encode()).hexdigest()=='4051e96e2a2482b364fd96c03ff7c6ae746b7d48434dacfce3417cbfeaf67cac'
    needle="words[9]  = 32'h12000000;"
    assert text.count(needle)==1
    text=text.replace(needle,"words[9]  = 32'h12000020;")
    # Unlike accepted-transaction counters, this also detects a request whose
    # readiness stays low. No empty operation should even assert valid.
    text=text.replace('    // Global bounded watchdog for the whole scenario.',
      '    always @(posedge mem_clk) if(resetn && (valid || men || mwen))\n'
      '        $fatal(1,"EMPTY_NATIVE_REQUEST");\n\n'
      '    // Global bounded watchdog for the whole scenario.')
    table={int(i):int(v,16) for i,v in re.findall(r"words\[(\d+)\]\s*=\s*32'h([0-9a-fA-F]+);",text)}
    assert sorted(table)==list(range(16))
    binary=(HERE/'build_01/microdma.bin').read_bytes()
    assert list(struct.unpack('<16I',binary[-64:]))==[table[i] for i in range(16)]
    (HERE/'bench_used.sv').write_text(text)
    with tempfile.TemporaryDirectory(prefix='copy-same-chain-') as raw:
        tmp=Path(raw)
        for p in SOURCES.iterdir():
            if p.suffix in ('.v','.hex'):shutil.copyfile(p,tmp/p.name)
        (tmp/'bench.sv').write_text(text)
        cmd=['/usr/bin/verilator','--binary','--timing','-j','2','-Wno-fatal',
          '-MAKEFLAGS','VM_PARALLEL_BUILDS=0','--top-module','bench','--Mdir',str(tmp/'obj'),'bench.sv']
        cmd += [p.name for p in sorted(tmp.glob('*.v'))]
        c=subprocess.run(cmd,cwd=tmp,text=True,capture_output=True,timeout=55)
        (HERE/'chain_compile.log').write_text(c.stdout+c.stderr);assert c.returncode==0
        cases=[]
        for seed,fault in [(1,0),(8,0),(1,1),(1,2)]:
            r=subprocess.run([str(tmp/'obj/Vbench'),f'+seed={seed}',f'+fault={fault}'],cwd=tmp,
              text=True,capture_output=True,timeout=3)
            log=r.stdout+r.stderr;(HERE/f'chain_seed{seed}_fault{fault}.log').write_text(log)
            assert r.returncode==0 and 'COPY_RESULT reads=0 returns=0 writes=0 words=16' in log,log
            cases.append(dict(seed=seed,fault=fault,passed=True))
        result=dict(passed=True,hardware=False,cases=cases,
          firmware_sha256=hashlib.sha256(binary).hexdigest(),bench_sha256=hashlib.sha256(text.encode()).hexdigest(),
          packets_bound_to_binary=True,RTL_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp.glob('*.v')},
          scope='AHB/FIFO/geometry/pixels/arbiter exactRTL; no native request at all. No physical timing/DDR.')
        (HERE/'chain_result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(passed=True,cases=len(cases))))

if __name__=='__main__':main()
