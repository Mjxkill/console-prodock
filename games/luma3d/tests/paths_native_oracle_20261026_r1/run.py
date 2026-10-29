#!/usr/bin/env python3
"""RV32 producer comparison only; no hardware device access or kernel build."""
import gzip,hashlib,json,re,stat,subprocess,zlib
from pathlib import Path
D=Path(__file__).resolve().parent; ROOT=D.parents[3]
K=ROOT/'games/luma3d/build-kernel/prodock_g3d1_20261024_r1'
ELF=ROOT/'games/luma3d/build/amber_paths_20261026_r4/luma3d-riscv'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cpio(entries):
 out=bytearray()
 for i,(name,data,mode) in enumerate([*entries,('TRAILER!!!',b'',0)]):
  name=name.encode()+b'\0';fields=[i+1,mode,0,0,1,0,len(data),0,0,0,0,len(name),0]
  out+=b'070701'+''.join(f'{v:08x}' for v in fields).encode()+name
  out+=b'\0'*(-len(out)%4);out+=data;out+=b'\0'*(-len(out)%4)
 return bytes(out)
assert sha(ELF)=='0daa38a57d1dfc149222e35887437bb8c1f5d768cd3ecafdafa526d628a7c0b4'
cc=ROOT/'linux/build/userbin/riscv32-prodock-linux-gcc'
subprocess.run([cc,'-std=c11','-O2','-Wall','-Wextra','-Werror','-static',D/'init.c','-o',D/'init'],check=True)
entries=[('init',(D/'init').read_bytes(),stat.S_IFREG|0o755),('game',ELF.read_bytes(),stat.S_IFREG|0o755),('garden.save',(D/'garden.save').read_bytes(),stat.S_IFREG|0o644),('baseline.memory',(D/'host.memory').read_bytes(),stat.S_IFREG|0o644)]
(D/'initrd.cpio.gz').write_bytes(gzip.compress(cpio(entries),mtime=0))
cmd=['qemu-system-riscv32','-machine','virt','-cpu','rv32','-m','256M','-smp','1','-nographic','-monitor','none','-no-reboot','-bios',str(ROOT/'linux/build/opensbi-qemu-virt/platform/generic/firmware/fw_dynamic.bin'),'-kernel',str(K/'kernel/arch/riscv/boot/Image'),'-initrd',str(D/'initrd.cpio.gz'),'-append','console=ttyS0 earlycon=sbi panic=1 rdinit=/init kunit.enable=0 prodock.selftest=0']
(D/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
with (D/'qemu.log').open('wb') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=90)
assert r.returncode==0
log=(D/'qemu.log').read_text();assert 'ORACLE_EXIT 0' in log and 'ORACLE_DONE ' in log
for ext,n,c in re.findall(r'ORACLE_FILE ([\w.]+) (\d+) ([0-9a-f]{8})',log):
 b=bytearray(int(n));used=bytearray(int(n))
 for off,h in re.findall(r'ORACLE_HEX '+re.escape(ext)+r' (\d+) ([0-9a-f]+)',log):
  off=int(off);v=bytes.fromhex(h);assert off+len(v)<=len(b) and not any(used[off:off+len(v)])
  b[off:off+len(v)]=v;used[off:off+len(v)]=b'\1'*len(v)
 assert all(used) and zlib.crc32(b)==int(c,16);(D/('native.'+ext)).write_bytes(b)
n,old,new=re.search(r'ORACLE_MEMORY (\d+) ([0-9a-f]{8}) ([0-9a-f]{8})',log).groups();b=bytearray((D/'host.memory').read_bytes());assert len(b)==int(n) and zlib.crc32(b)==int(old,16)
last=-1;changed=0
for off,h in re.findall(r'ORACLE_DIFF (\d+) ([0-9a-f]+)',log):
 off=int(off);v=bytes.fromhex(h);assert off>last and off+len(v)<=len(b);last=off+len(v)-1;b[off:off+len(v)]=v;changed+=len(v)
assert zlib.crc32(b)==int(new,16);(D/'native.memory').write_bytes(b)
report=dict(passed=True,hardware=False,elf_sha256=sha(ELF),kernel_sha256=sha(K/'kernel/arch/riscv/boot/Image'),memory_changed_bytes=changed,command_bytes_identical=(D/'native.commands').read_bytes()==(D/'host.commands').read_bytes(),scope='Unchanged RV32 executable under QEMU virt; not AE350 GPU emulation')
(D/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
