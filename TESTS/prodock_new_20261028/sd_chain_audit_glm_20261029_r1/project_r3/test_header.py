import unittest,struct,zlib,pathlib
import audit
class Header(unittest.TestCase):
 def test_actual_headers(self):
  for name,kind in [('UBOOT.BIN',1),('LUMA.BIN',3),('ORBITAL.BIN',4)]:
   b=pathlib.Path('inputs/sd',name).read_bytes();self.assertIs(audit.validate_header(b[:40],len(b),kind),True,name)
 def test_corrupt_resigned_fields(self):
  b=pathlib.Path('inputs/sd/UBOOT.BIN').read_bytes()
  for off,value in [(8,2),(12,3),(16,0x06000004),(20,0x06000004),(24,0),(32,0x1fe)]:
   h=bytearray(b[:40]);struct.pack_into('<I',h,off,value);struct.pack_into('<I',h,36,zlib.crc32(h[:36]))
   self.assertIs(audit.validate_header(bytes(h),len(b),1),False,(off,value))
  h=bytearray(b[:40]);h[36]^=1;self.assertIs(audit.validate_header(bytes(h),len(b),1),False)
  self.assertIs(audit.validate_header(b[:39],len(b),1),False)
  self.assertIs(audit.validate_header(b[:40],len(b)+1,1),False)
 def test_over_capacity_with_consistent_length(self):
  b=pathlib.Path('inputs/sd/UBOOT.BIN').read_bytes();h=bytearray(b[:40]);struct.pack_into('<I',h,24,0x800001);struct.pack_into('<I',h,36,zlib.crc32(h[:36]));self.assertIs(audit.validate_header(bytes(h),40+0x800001,1),False)
if __name__=='__main__': unittest.main()
