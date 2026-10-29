import json,unittest
from test_boot_log import m,GOOD
class Counterexamples(unittest.TestCase):
 def test_json_serializable(self):json.dumps(m.parse_boot(GOOD))
 def test_graphics_without_launch(self):
  self.assertFalse(m.parse_boot(b"LUMA3D_GRAPHICS_READY seconds=0.35 base_art_loaded=1 scene_resources_pending=1 hardware=1\n")['game_launch_observed'])
 def test_path_suffix(self):
  self.assertFalse(m.parse_boot(GOOD.replace(b"/PRODOCK/LINUX.BIN (",b"/PRODOCK/LINUX.BIN.evil ("))['boot_log_checks_passed'])
 def test_ready_suffix(self):
  self.assertFalse(m.parse_boot(GOOD.replace(b"LUMA3D_GRAPHICS_READY ",b"LUMA3D_GRAPHICS_READY_EVIL "))['boot_log_checks_passed'])
 def test_hardware_field(self):
  self.assertFalse(m.parse_boot(GOOD.replace(b"hardware=1",b"nothardware=1"))['boot_log_checks_passed'])
if __name__=='__main__':unittest.main()
