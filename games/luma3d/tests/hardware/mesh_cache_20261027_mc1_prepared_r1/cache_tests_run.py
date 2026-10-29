#!/usr/bin/env python3
import hashlib,json,os,subprocess
from pathlib import Path
C=Path(__file__).resolve().parents[1]
out=C/'tests/results_r3';out.mkdir(exist_ok=False)
records=[]
for mode,flags in [('strict',['-O2']),('asan',['-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer'])]:
 exe=out/mode
 cmd=['cc','-std=c11','-Wall','-Wextra','-Werror',*flags,'-I'+str(C/'include'),str(C/'tests/test_cache.c'),'-o',str(exe)]
 run=subprocess.run(cmd,capture_output=True);(out/(mode+'_compile.log')).write_bytes(run.stdout+run.stderr);run.check_returncode()
 env=os.environ.copy()
 if mode=='asan':env['ASAN_OPTIONS']='detect_leaks=0' # LSan is unsupported under this sandbox's ptrace; r1 failure retained.
 run=subprocess.run([exe],capture_output=True,env=env);(out/(mode+'.log')).write_bytes(run.stdout+run.stderr);run.check_returncode()
 records.append({'mode':mode,'command':cmd,'result':run.stdout.decode().strip()})
inputs={str(p.relative_to(C)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [C/'include/l3_mesh_cache.h',C/'src/mesh_cache.c',C/'tests/test_cache.c',Path(__file__)]}
(out/'result.json').write_text(json.dumps({'passed':True,'hardware':False,'records':records,'inputs':inputs,'limitation':'Address/undefined sanitizers enabled; LeakSanitizer disabled because sandbox ptrace is unsupported. Original r1 fatal diagnostic retained.'},indent=2)+'\n')
print(json.dumps(records,indent=2))
