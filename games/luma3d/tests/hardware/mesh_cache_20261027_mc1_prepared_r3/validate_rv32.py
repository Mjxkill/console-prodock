#!/usr/bin/env python3
"""RV32 diagnostic fixture bytes and controlled-window states, no board access."""
import argparse,gzip,hashlib,json,re,stat,subprocess,zlib
from pathlib import Path
from probe_metrics import parse
C=Path(__file__).resolve().parent;R=C.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cpio(entries):
 out=bytearray()
 for i,(name,data,mode) in enumerate([*entries,('TRAILER!!!',b'',0)]):
  name=name.encode()+b'\0';fields=[i+1,mode,0,0,1,0,len(data),0,0,0,0,len(name),0]
  out+=b'070701'+''.join(f'{v:08x}' for v in fields).encode()+name;out+=b'\0'*(-len(out)%4);out+=data;out+=b'\0'*(-len(out)%4)
 return bytes(out)
p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--windows',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();q=a.probe.resolve();cap=a.fixtures.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
m=json.loads((q/'manifest.json').read_text());fp=json.loads((cap/'result.json').read_text());wp=json.loads((a.windows/'result.json').read_text());assert fp['passed'] and wp['passed'] and fp['probe_manifest_sha256']==wp['probe_manifest_sha256']==sha(q/'manifest.json')
cc=R/'linux/build/userbin/riscv32-prodock-linux-gcc';K=R/'games/luma3d/build-kernel/prodock_g3d1_20261024_r1/kernel/arch/riscv/boot/Image'
original=(C.parent/'adventure_paths_resume_r1/qemu_init.c').read_text();records=[]
def run(d,init,entries):
 (d/'init.c').write_text(init);subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-static',d/'init.c','-o',d/'init'],check=True)
 (d/'initrd.cpio.gz').write_bytes(gzip.compress(cpio([('init',(d/'init').read_bytes(),stat.S_IFREG|0o755),*entries]),mtime=0))
 cmd=['qemu-system-riscv32','-machine','virt','-cpu','rv32','-m','256M','-smp','1','-nographic','-monitor','none','-no-reboot','-bios',str(R/'linux/build/opensbi-qemu-virt/platform/generic/firmware/fw_dynamic.bin'),'-kernel',str(K),'-initrd',str(d/'initrd.cpio.gz'),'-append','console=ttyS0 earlycon=sbi panic=1 rdinit=/init kunit.enable=0 prodock.selftest=0']
 (d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
 with (d/'qemu.log').open('wb') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=180)
 r.check_returncode();return (d/'qemu.log').read_text()
binary=q/'candidate-riscv';assert sha(binary)==next(x['elf_sha256'] for x in m['records'] if x['variant']=='candidate' and x['target']=='riscv')
for case in fp['records']:
 name=case['name'];prefix=cap/name;d=o/name;d.mkdir();kind=case['kind'];frames=case['frames'];wide=case['width']==1280
 start=original.index('execl(');end=original.index(';_exit(127)',start)
 args=['/game','/game','--host','--kind',str(kind),'--fixture','--frames',str(frames),'--capture','/native']+(['--720p'] if wide else [])+(['--restart-at',str(case['restart_at'])] if case['restart_at'] else [])+(['--back-at',str(case['back_at'])] if case['back_at'] else [])
 init=original[:start]+'execl('+','.join(json.dumps(x) for x in args)+',(char*)0)'+original[end:]
 log=run(d,init,[('game',binary.read_bytes(),stat.S_IFREG|0o755),('baseline.memory',prefix.with_suffix('.memory').read_bytes(),stat.S_IFREG|0o644)])
 assert 'ORACLE_EXIT 0' in log and 'ORACLE_DONE' in log;parse(log.encode(),kind,frames,True,False,case['restart_at'],case['back_at'])
 for ext,n,c in re.findall(r'ORACLE_FILE ([\w.]+) (\d+) ([0-9a-f]{8})',log):
  data=bytearray(int(n));used=bytearray(int(n))
  for off,h in re.findall(r'ORACLE_HEX '+re.escape(ext)+r' (\d+) ([0-9a-f]+)',log):
   off=int(off);v=bytes.fromhex(h);assert off+len(v)<=len(data) and not any(used[off:off+len(v)]);data[off:off+len(v)]=v;used[off:off+len(v)]=b'\1'*len(v)
  assert all(used) and zlib.crc32(data)==int(c,16);(d/('native.'+ext)).write_bytes(data)
 n,old,new=re.search(r'ORACLE_MEMORY (\d+) ([0-9a-f]{8}) ([0-9a-f]{8})',log).groups();data=bytearray(prefix.with_suffix('.memory').read_bytes());assert len(data)==int(n)==32<<20 and zlib.crc32(data)==int(old,16)
 changes=0;last=-1
 for off,h in re.findall(r'ORACLE_DIFF (\d+) ([0-9a-f]+)',log):
  off=int(off);v=bytes.fromhex(h);assert off>last and off+len(v)<=len(data);last=off+len(v)-1;data[off:off+len(v)]=v;changes+=len(v)
 assert zlib.crc32(data)==int(new,16)
 row=dict(name=name,memory_changed_bytes=changes,commands_identical=(d/'native.commands').read_bytes()==prefix.with_suffix('.commands').read_bytes(),overlay_identical=json.loads((d/'native.overlay.json').read_text())==json.loads(prefix.with_suffix('.overlay.json').read_text()),elf_sha256=sha(binary))
 assert changes==0 and row['commands_identical'] and row['overlay_identical'];row['passed']=True;records.append(row);print(name,flush=True)
# One additional boot runs all four windows with the actual two RV32 probes.
# No renderer source is replaced; only the common showcase scheduler is declared.
d=o/'windows';d.mkdir();body=''
for variant in ('baseline','candidate'):
 for kind in (4,8):
  body+=f'pid=fork();if(!pid){{execl("/{variant}","/{variant}","--host","--kind","{kind}","--frames","360",(char*)0);_exit(127);}}waitpid(pid,&status,0);if(status){{puts("WINDOW_FAIL");goto end;}}\n'
init='#define _GNU_SOURCE\n#include <stdio.h>\n#include <unistd.h>\n#include <sys/wait.h>\n#include <sys/reboot.h>\nint main(void){setvbuf(stdout,0,_IONBF,0);int status=0;pid_t pid;'+body+'puts("WINDOWS_DONE");end:sync();reboot(RB_POWER_OFF);return 0;}\n'
log=run(d,init,[(v,(q/(v+'-riscv')).read_bytes(),stat.S_IFREG|0o755) for v in ('baseline','candidate')]);assert 'WINDOWS_DONE' in log and 'WINDOW_FAIL' not in log
chunks=re.split(r'(?=^GPU_PROBE )',log,flags=re.M)[1:];assert len(chunks)==4;windows=[]
for chunk,(variant,kind) in zip(chunks,[(v,k) for v in ('baseline','candidate') for k in (4,8)]):
 value=parse(chunk.encode(),kind,360,False,False);host=next(x['result'] for x in wp['records'] if x['variant']==variant and x['kind']==kind and x['width']==800)
 keys=('frames','commands','batches','ui_bytes','rasters','static_bytes','dynamic_bytes','moves','teleports','queue_overflows','contacts','contact_fallbacks','state_crc32')
 assert [{k:x[k] for k in keys} for x in value['phases']]==[{k:x[k] for k in keys} for x in host['phases']]
 windows.append(dict(variant=variant,kind=kind,passed=True,result=value))
(o/'result.json').write_text(json.dumps(dict(passed=True,hardware=False,probe_manifest_sha256=sha(q/'manifest.json'),fixtures_sha256=sha(cap/'result.json'),windows_sha256=sha(a.windows/'result.json'),kernel_sha256=sha(K),runner_sha256=sha(Path(__file__)),records=records,windows=windows,scope='RV32 diagnostic capture bytes and logical windows; no GPU hardware timing'),indent=2)+'\n');print('RV32_PROBE_PASS')
