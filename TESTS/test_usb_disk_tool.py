#!/usr/bin/env python3
"""Contrat du test PC : aucune écriture SD implicite, cible USB identifiée."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_usb_disk as disk


class DiskTool(unittest.TestCase):
    def run_tool(self, media, allow=False):
        dev = MagicMock(bus=3, address=52, speed=3, bcdDevice=0x100)
        dev.get_active_configuration.return_value = [
            NSInterface(0, 2, [0x83]), NSInterface(1, 10, [2, 0x82]),
            NSInterface(2, 8, [1, 0x81])]
        state = f'USBDISK MEDIA={media} TIMEOUTS=0 LOSSES=0 RESYNCS=0'
        snapshot = dict(bus=3, address=52, speed_mbps=480)
        port = NS(device='/dev/ttyTEST', vid=disk.VID, pid=disk.PID, serial_number='11252024')
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(disk, 'console_snapshot', return_value=snapshot), \
                patch.object(disk.usb.core, 'find', return_value=dev) as find, \
                patch.object(disk.list_ports, 'comports', return_value=[port]), \
                patch.object(disk.serial, 'Serial') as serial, \
                patch.object(disk, 'command', side_effect=['USBDISK R1', state, state]), \
                patch.object(disk, 'file_view') as files, \
                patch.object(disk, 'raw_view') as raw, \
                patch.object(disk.time, 'sleep'), \
                patch.object(sys, 'argv', ['check_usb_disk', '--out', tmp] +
                             (['--allow-sd-write'] if allow else [])):
            with self.assertRaises(SystemExit) as result:
                disk.main()
            self.assertEqual(result.exception.code, 0)
            find.assert_called_once_with(idVendor=disk.VID, idProduct=disk.PID, bus=3, address=52)
            self.assertTrue(serial.call_args.kwargs['exclusive'])
            self.assertEqual(files.call_count, int(media == 'DDR' or allow))
            self.assertEqual(raw.call_args.args[3], allow)
            report = json.loads((Path(tmp) / 'usb_disk.json').read_text())
            self.assertTrue(report['pass'])
            if media == 'SD' and not allow:
                self.assertEqual(report['files'], {'skipped': 'SD read-only'})

    def test_sd_default(self):
        self.run_tool('SD')

    def test_sd_explicit_write(self):
        # Simulation seulement : aucun accès matériel ni écriture de carte.
        self.run_tool('SD', allow=True)

    def test_ddr_default(self):
        self.run_tool('DDR')


class NSInterface(list):
    def __init__(self, number, kind, endpoints):
        super().__init__(NS(bEndpointAddress=x) for x in endpoints)
        self.bInterfaceNumber, self.bInterfaceClass = number, kind


if __name__ == '__main__':
    unittest.main()
