#!/usr/bin/env python3
"""Run the frozen diagnostic producer under QEMU, never the AE350 GPU."""
import argparse,gzip,hashlib,json,re,shutil,stat,subprocess,zlib
from pathlib import Path
C=Path(__file__).resolve().parent;R=C.parents[3]
K=R/'games/luma3d/build-kernel/prodock_g3d1_20261024_r1/kernel/arch/riscv/boot/Image'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cpio(entries):
 out=bytearray()
 for i,(name,data,mode) in enumerate([*entries,('TRAILER!!!',b'',0)]):
  name=name.encode()+b'\0';fields=[i+1,mode,0,0,1,0,len(data),0,0,0,0,len(name),0]
  out+=b'070701'+''.join(f'{v:08x}' for v in fields).encode()+name;out+=b'\0'*(-len(out)%4);out+=data;out+=b'\0'*(-len(out)%4)
 return bytes(out)
def main():
 p=argparse.ArgumentParser();p.add_argument('--probe',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();b=a.probe.resolve();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False)
 m=json.loads((b/'result.json').read_text());assert m['passed'] and not m['hardware']
 for n,v in m['files'].items():assert sha(b/n)==v['sha256'],n
 original=(C.parent/'adventure_paths_resume_r1/qemu_init.c').read_text();start=original.index('execl(');end=original.index(';_exit(127)',start)
 capture=original[:start]+'execl("/game","/game","--host","--capture","/native",(char*)0)'+original[end:]
 replay=capture.replace('"--capture","/native"','"--replay","/tmp/ar-qemu.save"')
 start=replay.index('full("commands");');end=replay.index('fflush(stdout);reboot',start)
 replay=replay[:start]+'puts("REPLAY_DONE");'+replay[end:]
 # Replay init does not need the file extraction helpers.
 for mode,src in [('capture',capture),('replay',replay)]:
  (o/(mode+'_init.c')).write_text(src)
  subprocess.run([R/'linux/build/userbin/riscv32-prodock-linux-gcc','-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-unused-function','-static',o/(mode+'_init.c'),'-o',o/(mode+'_init')],check=True)
 records=[]
 for name in [*m['fixtures'],'replay']:
  d=o/name;d.mkdir();mode='replay' if name=='replay' else 'capture'
  entries=[('init',(o/(mode+'_init')).read_bytes(),stat.S_IFREG|0o755),('game',(b/'probe-riscv').read_bytes(),stat.S_IFREG|0o755),('tmp',b'',stat.S_IFDIR|0o755)]
  if mode=='capture':
   prefix=b/'fixtures'/name
   entries.extend([('native.save',prefix.with_suffix('.save').read_bytes(),stat.S_IFREG|0o644),('baseline.memory',prefix.with_suffix('.memory').read_bytes(),stat.S_IFREG|0o644)])
  (d/'initrd.cpio.gz').write_bytes(gzip.compress(cpio(entries),mtime=0))
  cmd=['qemu-system-riscv32','-machine','virt','-cpu','rv32','-m','256M','-smp','1','-nographic','-monitor','none','-no-reboot','-bios',str(R/'linux/build/opensbi-qemu-virt/platform/generic/firmware/fw_dynamic.bin'),'-kernel',str(K),'-initrd',str(d/'initrd.cpio.gz'),'-append','console=ttyS0 earlycon=sbi panic=1 rdinit=/init kunit.enable=0 prodock.selftest=0']
  (d/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
  with (d/'qemu.log').open('wb') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=120)
  assert r.returncode==0;log=(d/'qemu.log').read_text();assert 'ORACLE_EXIT 0' in log and 'AR_PASS' in log
  record=dict(name=name,passed=True,hardware=False,probe_sha256=sha(b/'probe-riscv'),kernel_sha256=sha(K))
  if mode=='capture':
   for ext,n,c in re.findall(r'ORACLE_FILE ([\w.]+) (\d+) ([0-9a-f]{8})',log):
    data=bytearray(int(n));used=bytearray(int(n))
    for off,h in re.findall(r'ORACLE_HEX '+re.escape(ext)+r' (\d+) ([0-9a-f]+)',log):
     off=int(off);v=bytes.fromhex(h);assert off+len(v)<=len(data) and not any(used[off:off+len(v)]);data[off:off+len(v)]=v;used[off:off+len(v)]=b'\1'*len(v)
    assert all(used) and zlib.crc32(data)==int(c,16);(d/('native.'+ext)).write_bytes(data)
   n,old,new=re.search(r'ORACLE_MEMORY (\d+) ([0-9a-f]{8}) ([0-9a-f]{8})',log).groups();data=bytearray(prefix.with_suffix('.memory').read_bytes());assert len(data)==int(n)==32<<20 and zlib.crc32(data)==int(old,16)
   changes=0;last=-1
   for off,h in re.findall(r'ORACLE_DIFF (\d+) ([0-9a-f]+)',log):
    off=int(off);v=bytes.fromhex(h);assert off>last and off+len(v)<=len(data);last=off+len(v)-1;data[off:off+len(v)]=v;changes+=len(v)
   assert zlib.crc32(data)==int(new,16) and changes==0
   assert (d/'native.commands').read_bytes()==prefix.with_suffix('.commands').read_bytes()
   assert json.loads((d/'native.overlay.json').read_text())==json.loads(prefix.with_suffix('.overlay.json').read_text())
   record.update(memory_changed_bytes=changes,commands_identical=True,overlay_identical=True)
  else:
   assert 'REPLAY_DONE' in log
   for marker in ['AR_COMPLETE','AR_RELOAD','ACTIVITY']:
    expected=re.findall('^'+marker+r' [^\r\n]+',(b/'replay_host.log').read_text(),re.M)
    actual=re.findall('^'+marker+r' [^\r\n]+',log,re.M);assert expected==actual,(marker,expected,actual)
   record['replay_identical']=True
  records.append(record);print(json.dumps(record),flush=True)
 report=dict(passed=True,hardware=False,probe_manifest_sha256=sha(b/'result.json'),records=records,scope='RV32 producer only; QEMU does not emulate the AE350 GPU')
 (o/'result.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
