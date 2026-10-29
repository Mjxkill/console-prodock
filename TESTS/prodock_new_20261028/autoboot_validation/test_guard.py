"""Offline guard tests: no real port opened; production syscalls replaced by fakes."""
import json
import hashlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import serial_guard as g

IDENT={'usb_path':str(g.USB),'port':str(g.PORT),'idVendor':'359f','idProduct':'2011','serial':'11252024','speed':'480','tty':'ttyACM9','tty_usb_parent':str(g.USB.resolve()),'rdev':166,'busnum':'3','devnum':'9'}
class Tests(unittest.TestCase):
 def review(self):
  return {'target_programmer':g.PROGRAMMER,'port':str(g.PORT),'usb_topology':'3-7.1','manifest_sha256':'a'*64,'package_manifest_sha256':g.PACKAGE_SHA,'kernel_manifest_sha256':g.KERNEL_MANIFEST_SHA,'game_sha256':g.GAME_SHA,'host':g.HOST,'reviewed_unix':100,'new_console_binding_confirmed':True,'passive_capture_authorized':True,'old_board_untouched':True,'no_other_console_session':True,'bitstream_validation_reviewed':True}
 def test_review(self):
  self.assertTrue(g.validate_review(self.review(),'a'*64,g.HOST,101))
  for k,v in [('target_programmer','2023112818'),('port',str(g.PORT).replace('7.1','7.3')),('host','ax15'),('reviewed_unix',200),('new_console_binding_confirmed',False),('bitstream_validation_reviewed',False),('package_manifest_sha256','0'*64)]:
   r=self.review();r[k]=v
   with self.assertRaises(RuntimeError):g.validate_review(r,'a'*64,g.HOST,101)
 def test_topology(self):
  self.assertEqual(g.validate_identity(dict(IDENT)),IDENT)
  for k,v in [('tty_usb_parent',str(g.USB).replace('7.1','7.3')),('usb_path',str(g.USB).replace('7.1','7.3')),('speed','12'),('serial','other'),('tty','ttyUSB9')]:
   d=dict(IDENT);d[k]=v
   with self.assertRaises(RuntimeError):g.validate_identity(d)
 def test_fuser(self):
  g.quiet_owner(SimpleNamespace(returncode=1,stdout=b'',stderr=b''))
  for rc,out,err in [(0,b'123',b''),(1,b'',b'warning'),(2,b'',b''),(1,b'123',b'')]:
   with self.assertRaises(RuntimeError):g.quiet_owner(SimpleNamespace(returncode=rc,stdout=out,stderr=err))
 def test_program_result(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'result.json';proof={'target_serial':g.PROGRAMMER,'configuration_completed':True,'bitstream_sha256':'d'*64,'flash_writes':0};raw=json.dumps(proof).encode();p.write_bytes(raw)
   review={'program_result_path':str(p),'program_result_sha256':hashlib.sha256(raw).hexdigest(),'bitstream_sha256':'d'*64}
   self.assertEqual(g.verify_program_result(review)['flash_writes'],0)
   for key,value in [('target_serial','2023112818'),('configuration_completed',False),('bitstream_sha256','c'*64)]:
    bad=dict(proof);bad[key]=value;raw=json.dumps(bad).encode();p.write_bytes(raw);r=dict(review,program_result_sha256=hashlib.sha256(raw).hexdigest())
    with self.assertRaises(RuntimeError):g.verify_program_result(r)
 def test_real_lock_exclusion(self):
  with tempfile.TemporaryDirectory() as t,mock.patch.object(g,'LOCK',Path(t)/'guard.lock'):
   with g.diagnostic_lock():
    with self.assertRaises(BlockingIOError):
     with g.diagnostic_lock():pass
   with g.diagnostic_lock():pass
 def test_open_readonly_and_close(self):
  io=g.PassiveUART.__new__(g.PassiveUART);io.fd=None;io.identity=None
  attrs=[0,0,g.termios.CS8|g.termios.CLOCAL|g.termios.CREAD,0,g.termios.B115200,g.termios.B115200,[0]*32]
  with mock.patch.object(g,'snapshot',return_value=IDENT),mock.patch.object(g.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'')),mock.patch.object(g.os,'open',return_value=123) as opened,mock.patch.object(g.os,'close') as closed,mock.patch.object(g.os,'fstat',return_value=SimpleNamespace(st_rdev=166)),mock.patch.object(g.fcntl,'ioctl'),mock.patch.object(g.tty,'setraw'),mock.patch.object(g.termios,'tcgetattr',return_value=attrs),mock.patch.object(g.termios,'tcsetattr'):
   self.assertEqual(io.open(),IDENT)
   flags=opened.call_args.args[1];self.assertEqual(flags&g.os.O_ACCMODE,g.os.O_RDONLY)
   self.assertEqual(opened.call_args.args[0],g.PORT)
   with self.assertRaises(RuntimeError):io.write(b'\n')
   io.close();closed.assert_called_once_with(123)
 def test_open_race_refused_and_closed(self):
  io=g.PassiveUART.__new__(g.PassiveUART);io.fd=None
  with mock.patch.object(g,'snapshot',return_value=IDENT),mock.patch.object(g.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=b'')),mock.patch.object(g.os,'open',return_value=123),mock.patch.object(g.os,'close') as closed,mock.patch.object(g.os,'fstat',return_value=SimpleNamespace(st_rdev=999)),mock.patch.object(g.fcntl,'ioctl'):
   with self.assertRaises(RuntimeError):io.open()
   closed.assert_called_once_with(123)
if __name__=='__main__':unittest.main()
