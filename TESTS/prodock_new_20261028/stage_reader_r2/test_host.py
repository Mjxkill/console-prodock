#!/usr/bin/env python3
import hashlib,json,os,subprocess
from pathlib import Path
p=Path(__file__).resolve().parent;root=next(d for d in p.parents if (d/'ARCHI/COMPATIBILITE_CARTES.md').is_file())
driver=root/'games/luma3d/build-kernel/prodock_g3d1_20261024_r1/source/drivers/prodock/prodock-gpu.c';uapi=driver.with_name('prodock-uapi.h')
s=driver.read_text();u=uapi.read_text()
for token in ['off >= PRODOCK_GPU_BYTES','length > PRODOCK_GPU_BYTES - off','PRODOCK_GPU_BASE + off','pgprot_noncached','VM_SHARED','VM_EXEC']:assert token in s
assert '#define PRODOCK_GPU_BASE 0x00800000U' in u and '#define PRODOCK_GPU_BYTES 0x05600000U' in u
assert 0x00800000+0x03800000==0x04000000
assert 0x03800000+((5805324+4095)&~4095)<=0x05600000
cmd=['/usr/bin/gcc','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-pie','-no-pie',str(p/'test_host.c'),'-o',str(p/'host_tests')]
subprocess.run(cmd,check=True)
r=subprocess.run([str(p/'host_tests'),str(p/'fm4a.full.lz4'),str(root/'games/luma3d/build/festival_memory_metrics_20261028_r4/luma3d-riscv')],capture_output=True,text=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0:halt_on_error=1'),timeout=60)
(p/'host_tests.log').write_text(r.stdout+r.stderr);print(r.stdout+r.stderr);r.check_returncode()
files=[p/'stage_reader.c',p/'stage_reader',p/'test_host.c',driver,uapi]
result={'passed':True,'hardware':False,'cases':['Exact 16640496-byte output','Bad packed CRC rejected before creation','Truncated packed input rejected','Nested output path refused','Existing output preserved','Symlink output refused and target unchanged','Frozen mmap ABI offset/range matches'],'sanitizers':'ASan+UBSan; LeakSanitizer disabled under ptrace','driver_limit':'Kernel release calls fb_restore, though helper sends no ioctl and maps read-only','inputs':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
(p/'host_tests.json').write_text(json.dumps(result,indent=2)+'\n')
