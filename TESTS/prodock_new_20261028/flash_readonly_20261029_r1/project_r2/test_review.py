import unittest, tempfile, pathlib, json
import flash_readonly as f
DUMP=b"found 1 devices\nindex 0:\n\tidcode 0x1081b\ndump flash (May take time)\nOpen dump file DONE\nRead flash 100.00%\nDone\n"
class Review(unittest.TestCase):
 def test_runtime_path(self):
  c=f.Coordinator(phase='detect',out_dir=f.ROOT/'TESTS/review-only')
  self.assertEqual(str(c.runtime),str(f.ROOT/'runtime/openFPGALoader'))
 def test_dump_identity_mandatory(self):
  with self.assertRaises((ValueError,RuntimeError)):
   f.parse_dump_log(DUMP,jedec='ef4018',sectors=256)
 def test_existing_proof_not_overwritten(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);out=root/'TESTS/existing';out.mkdir(parents=True)
   evidence=out/'detect.json';evidence.write_bytes(b'previous proof preserved')
   result=f.Coordinator(phase='detect',out_dir=out,root=root).execute()
   self.assertFalse(result['passed'])
   self.assertEqual(evidence.read_bytes(),b'previous proof preserved')
if __name__=='__main__': unittest.main()
