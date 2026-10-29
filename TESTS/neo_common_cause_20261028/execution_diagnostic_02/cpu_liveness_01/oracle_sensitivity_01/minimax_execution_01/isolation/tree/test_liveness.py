#!/usr/bin/env python3
"""Protected independent acceptance criteria; no physical-board claims."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
SOURCES=['bench.sv','native_memory.sv','ddr_ui_adapt.v','ddr_gpu_arb.v',
         'gpu_v1.v','gpu_triangle.v','gpu_copy565.v','gpu_texture_cache.v','gpu_perspective.v']

def main():
    with tempfile.TemporaryDirectory(prefix='cpu-liveness-') as t:
        obj=Path(t)/'obj'
        cmd=['/usr/bin/verilator','--binary','--timing','-j','2','-Wno-fatal',
             '-MAKEFLAGS','VM_PARALLEL_BUILDS=0','--top-module','bench','--Mdir',str(obj),*SOURCES]
        p=subprocess.run(cmd,cwd=HERE,capture_output=True,text=True,timeout=48)
        if p.returncode: print(p.stdout+p.stderr);return 1
        rows=[]
        for case in ([0] if '--infra' in sys.argv else range(8)):
            p=subprocess.run([str(obj/'Vbench'),f'+case={case}'],cwd=HERE,
                             capture_output=True,text=True,timeout=3)
            print(f'CASE {case} rc={p.returncode}\n{p.stdout}{p.stderr}')
            if '--infra' in sys.argv:
                return int(p.returncode!=0 or 'INFRA_PASS' not in p.stdout)
            obs=[json.loads(line[4:]) for line in p.stdout.splitlines() if line.startswith('OBS ')]
            by={r['label']:r for r in obs}
            ok=p.returncode==0 and set(by)=={'blocked','final'}
            if ok:
                a,b=by['blocked'],by['final']
                ok=(a['case']==b['case']==case and b['cpu']==b['sent']==32
                    and b['rejected']==0 and b['full']==b['tags']==b['adapter_tags']==0
                    and b['cpu_pending']==0)
                if case in (1,2):
                    ok=ok and a['cpu']==0 and a['native_reads']==0 and a['native_writes']==0
                    ok=ok and a['cpu_pending']==1 and a['take_blitter']==1 and a['full']==0
                    ok=ok and a['gpu_done']==1 and a['busy']==1
                elif case==4:
                    ok=ok and a['cpu']==0 and a['full']==1 and a['tags']==16
                    ok=ok and a['gpu_valid']==1 and a['full_ready_cycles']>=20
                    ok=ok and a['native_reads']==16 and a['returned']==0 and a['native_writes']==0
                    ok=ok and b['scan_returns']==16 and b['native_reads']==48
                elif case==6:
                    ok=ok and a['cpu']==0 and a['native_reads']==1 and a['returned']==0
                    ok=ok and a['adapter_tags']==1 and a['tags']==1 and a['full']==0
                    ok=ok and a['gpu_done']==1 and a['busy']==1 and a['native_writes']>1
                if case in (3,6):
                    ok=ok and b['gpu_done']==1 and b['busy']==1 and b['native_writes']>1
                elif case in (5,7):
                    ok=ok and b['gpu_done']==1 and b['busy']==1 and b['native_writes']==0
                else:
                    ok=ok and b['gpu_done']==2 and b['busy']==0 and b['native_writes']==1
                if case!=4:ok=ok and b['native_reads']==b['returned']==32
            rows.append({'case':case,'passed':ok,'observations':obs})
        print(json.dumps({'passed':all(x['passed'] for x in rows),'cases':rows}))
        return int(not all(x['passed'] for x in rows))

if __name__=='__main__':raise SystemExit(main())
