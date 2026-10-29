#!/usr/bin/env python3
import argparse,gzip,hashlib,importlib.util,json,stat,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=next(p for p in HERE.parents if (p/'ARCHI/COMPATIBILITE_CARTES.md').is_file())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);out=a.out.resolve()
 source=ROOT/'games/luma3d/candidates/festival_transport_guard_20261027_r1/run_receiver_exact.py';spec=importlib.util.spec_from_file_location('cpio_source',source);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 base=ROOT/'games/luma3d/build/maze_events_20261027_r4/luma3d-riscv';target=ROOT/'games/luma3d/build/festival_memory_metrics_20261028_r4/luma3d-riscv';helper=HERE/'mc1-helper';delta=HERE/'metrics-r4.delta.lz4';kernel=ROOT/'games/luma3d/build-kernel/prodock_g3d1_20261024_r1/kernel/arch/riscv/boot/Image';bios=ROOT/'linux/build/opensbi-qemu-virt/platform/generic/firmware/fw_dynamic.bin'
 inputs={str(p.relative_to(ROOT)):sha(p) for p in [base,target,helper,delta,HERE/'helper_qemu.c',Path(__file__),source,kernel,bios]}
 q=subprocess.run([str(ROOT/'linux/build/userbin/riscv32-prodock-linux-gcc'),'-O2','-Wall','-Wextra','-Werror','-static',str(HERE/'helper_qemu.c'),'-o',str(out/'init')],capture_output=True);(out/'compile.log').write_bytes(q.stdout+q.stderr);q.check_returncode()
 entries=[(name,path.read_bytes(),stat.S_IFREG|0o755) for name,path in [('base',base),('expected',target),('delta',delta),('helper',helper),('init',out/'init')]];(out/'initrd.gz').write_bytes(gzip.compress(m.cpio(entries),mtime=0))
 cmd=['qemu-system-riscv32','-machine','virt','-cpu','rv32','-m','256M','-smp','1','-nographic','-monitor','none','-no-reboot','-bios',str(bios),'-kernel',str(kernel),'-initrd',str(out/'initrd.gz'),'-append','console=ttyS0 earlycon=sbi panic=1 rdinit=/init kunit.enable=0 prodock.selftest=0']
 with (out/'qemu.log').open('wb') as f:q=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=180)
 log=(out/'qemu.log').read_text();cases=['EXACT_RECONSTRUCTION','EXCLUSIVE_OUTPUT','WRONG_BASE_REJECT','CORRUPT_PACKED_REJECT'];unchanged=all(sha(ROOT/p)==v for p,v in inputs.items());passed=q.returncode==0 and all(k+' 1' in log for k in cases) and 'HELPER_QEMU_PASS' in log and unchanged
 result=dict(passed=passed,hardware=False,scope='Historical RV32 helper exact ELF reconstructs full metricsR4 from GM1, all16640496 output bytes compared to pinned expected ELF under Linux/QEMU',cases={k:k+' 1' in log for k in cases},inputs=inputs,inputs_unchanged=unchanged,artifacts={str(p.relative_to(out)):sha(p) for p in [out/'init',out/'initrd.gz',out/'qemu.log']});(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return not passed
if __name__=='__main__':raise SystemExit(main())
