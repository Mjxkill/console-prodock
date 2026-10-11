#!/usr/bin/env python3
"""Recent GPU throughput, native bar composition and bounded text commands."""
import ctypes
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from render_astrilla import Scene
from check_astrilla import status

class HudTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.scene=Scene();cls.lib=cls.scene.lib
  cls.lib.meter_reset.argtypes=[ctypes.c_uint64]
  cls.lib.meter_frame.argtypes=[ctypes.c_uint64,ctypes.c_uint]
 def test_half_second_window_and_long_uptime(self):
  start=(1<<32)*100+123
  self.lib.meter_reset(start)
  for i in range(1,28):self.lib.meter_frame(start+i*14545455,1000)
  self.assertEqual(self.lib.meter_fps(),0)
  self.lib.meter_frame(start+28*14545455,1000)
  self.assertEqual(self.lib.meter_fps(),550)
  self.assertEqual(self.lib.meter_cps(),55000)
 def test_slow_window_measures_actual_completions(self):
  self.lib.meter_reset(0)
  for i in range(1,6):self.lib.meter_frame(i*80000000,i*100)
  self.assertEqual(self.lib.meter_fps(),100)
  self.assertEqual(self.lib.meter_cps(),3000)
  self.lib.meter_frame(1200000000,123)
  self.assertEqual(self.lib.meter_fps(),10)
  self.assertEqual(self.lib.meter_cps(),123)
  self.lib.meter_reset(1200000000)
  self.assertEqual((self.lib.meter_fps(),self.lib.meter_cps()),(0,0))
 def test_command_bounds_and_font_coverage(self):
  for fps,cps,ns,nl in [(0,0,0,2),(550,123456,48,5),(999,4294967295,64,16)]:
   self.assertIn(self.scene.hud(fps,cps,ns,nl),(6,7))
   pixels=self.scene.hud_pixels
   self.assertEqual(len(pixels),25600)
   self.assertTrue(all(v in (1,33,50) for v in pixels))
   self.assertEqual(pixels[18:782],bytes([50])*764)
 def test_wire_counter_preserves_high_word(self):
  d=status('ASTRILLA gpu_cmd_total=17 gpu_cmd_hi=3 gpu_done=65535 hud_crc=abcdef12')
  self.assertEqual(d['gpu_cmd_total'],(3<<32)+17)
  self.assertEqual(d['hud_crc'],0xabcdef12)
  self.assertEqual(status('gpu_cmd_total=29')['gpu_cmd_total'],29)
 def test_native_counts_and_bars_above_cuts(self):
  for t in [0,100,1925,3850,5500,7150,7400,8800,10450,12375,14300,15675,16499]:
   layers,sprites,info=self.scene.layers(t)
   self.assertEqual(sum(bool(s[2]&65536) for s in sprites),info.sprites)
   self.assertEqual(layers[14][2],0)
   self.assertEqual(layers[14][3],36*65536+800)
   self.assertEqual(layers[15][2],448*65536)
   self.assertEqual(layers[15][3],32*65536+800)
   self.assertTrue(layers[14][6]&1 and layers[15][6]&1)
   for s in sprites:
    if s[2]&65536:self.assertLessEqual((s[2]>>20)&15,10)

if __name__=='__main__':unittest.main()
