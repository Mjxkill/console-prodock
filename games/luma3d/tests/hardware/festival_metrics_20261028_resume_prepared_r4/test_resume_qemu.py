#!/usr/bin/env python3
"""Real RV32 RX2 + Linux + actual stage.segment; saved-prefix resume oracle."""
import argparse,hashlib,importlib.util,json,subprocess,sys,time
from pathlib import Path
import stage,probe_channel as p,sender
HERE=Path(__file__).resolve().parent
ROOT=next(x for x in HERE.parents if (x/'ARCHI/COMPATIBILITE_CARTES.md').is_file())
RX=ROOT/'games/luma3d/candidates/uart_rx2_buffered_20261028_r1'
spec=importlib.util.spec_from_file_location('rx_qemu',RX/'run_qemu.py');q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(exist_ok=False);out=a.out.resolve();plan=stage.load_plan();payload=(HERE/plan['payload_file']).read_bytes();passed=False;records=[];c=None
 kernel=ROOT/'games/luma3d/build-kernel/prodock_g3d1_20261024_r1/kernel/arch/riscv/boot/Image';bios=ROOT/'linux/build/opensbi-qemu-virt/platform/generic/firmware/fw_dynamic.bin';fixture=RX/'tests_r1/initrd.gz'
 cmd=['qemu-system-riscv32','-machine','virt','-cpu','rv32','-m','256M','-smp','1','-nographic','-monitor','none','-no-reboot','-bios',str(bios),'-kernel',str(kernel),'-initrd',str(fixture),'-append','console=ttyS0 earlycon=sbi panic=1 rdinit=/init kunit.enable=0 prodock.selftest=0']
 with (out/'qemu.log').open('wb') as log:
  proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);io=q.IO(proc,log)
  class Uart:
   def read(self,n,timeout):return io.read(timeout)
   def write(self,b):return io.write(b)
  try:
   io.until(b'RX2_PROMPT> ',40);io.quiet();io.command(b"PS1='prodock# '\n",b'prodock# ');io.quiet();c=p.Channel(Uart(),out);c.initial_shell()
   c.run('fixture_receiver','busybox cat /receiver > '+plan['rx2_executable']+' && busybox chmod 700 '+plan['rx2_executable'])
   # Seed through the actual receiver, committing exactly the real checkpoint.
   s=sender.Session(c,'1'*32,payload,idle_ms=5000,total_ms=900000,pause=0);c.current=s;c.shell=False;c.text(s.command(plan['rx2_executable'],plan['remote_payload']));s.begin()
   while s.offset<904192:s.block()
   s.finish(stop=True);c.restore_shell(s);assert s.offset==904192
   # Wrong reviewed offset refuses before any DATA; finite passive cleanup.
   try:stage.segment(c,plan,resume=True,expected_offset=786432,pause=0)
   except ValueError:assert c.current.sent_frames==0;c.restore_shell(c.current)
   else:raise AssertionError('wrong checkpoint accepted')
   expected=904192
   while expected<len(payload):
    row=stage.segment(c,plan,resume=True,expected_offset=expected,pause=0);records.append(row);expected=row['offset'];print(json.dumps(row),flush=True)
   assert len(records)==5 and records[-1]['complete'] and expected==len(payload)
   # Exact final byte comparison via emulated serial, larger bounded dump.
   c.text(('/inspect '+plan['remote_payload']+'\n').encode());raw=bytearray();end=time.monotonic()+90
   while b'INSPECT_END' not in raw:
    if time.monotonic()>end or len(raw)>len(payload)*3:raise RuntimeError('dump bound')
    raw.extend(c.read(.05))
   body=raw.split(('INSPECT_BEGIN '+str(len(payload))+'\r\n').encode(),1)[1].split(b'INSPECT_END',1)[0];assert bytes.fromhex(body.decode())==payload;passed=True
  except BaseException as e:records.append(dict(error=repr(e)));print(repr(e),flush=True)
  finally:
   if c:c.close()
   proc.terminate()
   try:proc.wait(5)
   except subprocess.TimeoutExpired:proc.kill();proc.wait()
 result=dict(passed=passed,hardware=False,scope='Actual stage.segment with exact buffered RV32 ELF in Linux/QEMU; no board identity emulation',plan_sha256=hashlib.sha256((HERE/'plan.json').read_bytes()).hexdigest(),fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),initial_prefix=904192,exact_final_payload=passed,records=records)
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');return not passed
if __name__=='__main__':raise SystemExit(main())
