#!/usr/bin/env python3
"""Les essais adversariaux physiques sont réservés au disque DDR identifié."""
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import check_usb_disk_faults as probe


class MediaGateTests(unittest.TestCase):
    def test_sd_and_unknown_media_refused_before_usb(self):
        for current in ({'MEDIA':'SD','SERVING':'1'}, {},
                        {'MEDIA':'DDR','SERVING':'0'}):
            disk=Mock()
            with self.subTest(current=current),patch.object(probe,'state',return_value=current):
                with self.assertRaises(probe.Fail):probe.require_ddr(None,disk)
            disk.transfer.assert_not_called()
            disk.write.assert_not_called()

    def test_wrong_capacity_refused(self):
        for capacity in (struct.pack('>II',65536,512),struct.pack('>II',65535,1024),b''):
            disk=Mock();disk.transfer.side_effect=[(0,0,b''),(0,0,capacity)]
            with self.subTest(capacity=capacity),patch.object(probe,'state',return_value={'MEDIA':'DDR','SERVING':'1'}):
                with self.assertRaises(probe.Fail):probe.require_ddr(None,disk)
            disk.write.assert_not_called()

    def test_ddr_ready_and_exact_capacity(self):
        disk=Mock();disk.transfer.side_effect=[(1,0,b''),(0,0,b''),(0,0,struct.pack('>II',65535,512))]
        with patch.object(probe,'state',return_value={'MEDIA':'DDR','SERVING':'1'}):
            probe.require_ddr(None,disk)
        disk.sense.assert_called_once()
        disk.write.assert_not_called()


if __name__=='__main__':unittest.main()
