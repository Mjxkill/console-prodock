import unittest,subprocess,json,pathlib
class Complete(unittest.TestCase):
 def test_audit_completed_sections(self):
  run=subprocess.run(['python3','-B','audit.py'],text=True,capture_output=True,timeout=60)
  self.assertEqual(run.returncode,0,run.stderr);d=json.loads(run.stdout)
  self.assertFalse([c for c in d['checks'] if c['scope']=='runtime guard'],d)
  checks={c['name']:c for c in d['checks']}
  for name in ['pdckboot_decoder_source_contract','negative_header_boundaries','linux_launchers_bounds','package_and_media_history']:
   self.assertIn(name,checks);self.assertTrue(checks[name]['passed'],checks[name])
  self.assertIn('r3_post_route_rom',checks);self.assertFalse(checks['r3_post_route_rom']['passed'])
  self.assertIn('r4_post_route_rom',checks);self.assertFalse(checks['r4_post_route_rom']['passed'])
  self.assertFalse(d['hardware_validated']);self.assertFalse(d['r4_post_route_verified'])
if __name__=='__main__':unittest.main()
