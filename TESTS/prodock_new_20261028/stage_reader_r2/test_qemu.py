#!/usr/bin/env python3
"""Run exact RV32 helper against a sparse-file mmap fixture under frozen Linux."""
import gzip,hashlib,importlib.util,json,stat,subprocess
from pathlib import Path
p=Path(__file__).resolve().parent;root=next(d for d in p.parents if (d/'ARCHI/COMPATIBILITE_CARTES.md').is_file());out=p/'qemu_r1';out.mkdir(exist_ok=False)
cpio_source=root/'games/luma3d/candidates/festival_transport_guard_20261027_r1/run_receiver_exact.py';spec=importlib.util.spec_from_file_location('cpio_source',cpio_source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
cmd=[str(root/'linux/build/userbin/riscv32-prodock-linux-gcc'),'-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-static',str(p/'qemu_init.c'),'-o',str(out/'init')];subprocess.run(cmd,check=True)
elf=root/'games/luma3d/build/festival_memory_metrics_20261028_r4/luma3d-riscv';kernel=root/'games/luma3d/build-kernel/prodock_g3d1_20261024_r1/kernel/arch/riscv/boot/Image';bios=root/'linux/build/opensbi-qemu-virt/platform/generic/firmware/fw_dynamic.bin'
inputs=[p/'stage_reader',p/'stage_reader.c',p/'fm4a.full.lz4',p/'qemu_init.c',elf,kernel,bios];hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs}
entries=[(name,f.read_bytes(),stat.S_IFREG|0o755) for name,f in [('reader',p/'stage_reader'),('packed',p/'fm4a.full.lz4'),('expected',elf),('init',out/'init')]];(out/'initrd.gz').write_bytes(gzip.compress(m.cpio(entries),mtime=0))
cmd=['qemu-system-riscv32','-machine','virt','-cpu','rv32','-m','256M','-smp','1','-nographic','-monitor','none','-no-reboot','-bios',str(bios),'-kernel',str(kernel),'-initrd',str(out/'initrd.gz'),'-append','console=ttyS0 earlycon=sbi panic=1 rdinit=/init kunit.enable=0 prodock.selftest=0']
with (out/'qemu.log').open('wb') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=180)
log=(out/'qemu.log').read_text();cases=['EXACT_RV32','EXISTING_PRESERVED','SYMLINK_REJECTED','BAD_CRC_REJECTED'];unchanged=all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==s for f,s in hashes.items());passed=r.returncode==0 and all(x+' 1' in log for x in cases) and 'STAGE_READER_QEMU_PASS' in log and unchanged
result={'passed':passed,'hardware':False,'cases':{x:x+' 1' in log for x in cases},'inputs':hashes,'inputs_unchanged':unchanged,'limits':['Exact RV32 ELF under Linux; GPU file simulated with sparse regular file at exact offset','No physical GPU/DDR/JTAG proof','Frozen production driver mmap ABI checked separately']};(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(not passed)
