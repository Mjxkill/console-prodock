import importlib.util
from pathlib import Path
import unittest
s=importlib.util.spec_from_file_location('boot_log',Path(__file__).parent/'owned/boot_log.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
GOOD=b'''PRODOCK SD BOOT READY /PRODOCK/UBOOT.BIN
PRODOCK SD BOOT: U-Boot 258100 octets
PRODOCK SD BOOT: CRC OK, U-Boot
Pro Dock: lecture /PRODOCK/LINUX.BIN (25673840 octets)
Pro Dock: image verifiee, lancement
Linux version 6.12.112-prodock-luma3d-g3d1-sdoptin-r1 (prodock@builder) #1
PRODOCK_AUTOSTART: looking for the Pro Dock game on the SD card
PRODOCK_AUTOSTART: starting LUMA3D.ELF --festival
LUMA3D_GRAPHICS_READY seconds=0.35 base_art_loaded=1 scene_resources_pending=1 hardware=1
LUMA3D_PERF fps=10.2 cmd_s=2300 draws=4 triangles_in=350 objects=4 collected=0/4 auto=1 sim=2.30
'''
class Tests(unittest.TestCase):
 def check(self,data,pass_expected,launched=False):
  r=m.parse_boot(data);self.assertIs(r['boot_log_checks_passed'],pass_expected);self.assertIs(r['game_launch_observed'],launched)
  for k in ['gpu_tested','powercycle_validated','kernel_sha_measured','game_sha_measured']:self.assertIs(r[k],False)
 def test_complete(self):self.check(GOOD,True,True)
 def test_crlf(self):self.check(GOOD.replace(b'\n',b'\r\n'),True,True)
 def test_empty(self):self.check(b'',False)
 def test_launch_only(self):self.check(GOOD.split(b'LUMA3D_GRAPHICS_READY')[0],False)
 def test_host(self):self.check(GOOD.replace(b'hardware=1',b'hardware=0'),False)
 def test_wrong_kernel(self):self.check(GOOD.replace(b'sdoptin-r1',b'r1'),False,True)
 def test_late(self):self.check(GOOD[GOOD.index(b'Linux version'):],False,True)
 def test_new_attempt(self):self.check(GOOD+b'PRODOCK SD BOOT READY /PRODOCK/UBOOT.BIN\n',False)
 def test_panic(self):self.check(GOOD+b'Kernel panic - not syncing: fatal\n',False,True)
 def test_wrong_sha(self):self.check(GOOD.replace(b'PRODOCK_AUTOSTART: starting',b'PRODOCK_AUTOSTART: checksum mismatch\nPRODOCK_AUTOSTART: starting'),False,True)
 def test_binary(self):self.check(GOOD+b'\x00',False,True)
 def test_reversed(self):
  a=GOOD.splitlines(keepends=True);a[4],a[5]=a[5],a[4];self.check(b''.join(a),False,True)
 def test_echo(self):self.check(b'echo '+GOOD,False,True)
 def test_fragmented(self):self.check(b''.join(GOOD[i:i+3] for i in range(0,len(GOOD),3)),True,True)
 def test_unterminated_ready(self):self.check(GOOD[:GOOD.index(b'LUMA3D_PERF')].rstrip(b'\n'),False)
 def test_size(self):
  with self.assertRaises((ValueError,TypeError)):m.parse_boot(b'x'*(4*1024*1024+1))
if __name__=='__main__':unittest.main()
