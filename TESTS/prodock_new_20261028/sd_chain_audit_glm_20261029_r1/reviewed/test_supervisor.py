"""Adversarial checks of the audit itself; original inputs are never changed."""
import copy
import struct
import unittest
from unittest.mock import patch
import zlib
import audit


class AuditChecks(unittest.TestCase):
    def setUp(self):
        audit.CHECKS.clear()
        audit.FINDINGS.clear()
        audit.LIMITS.clear()
        audit.D.clear()
        audit.D['bm'] = audit.rj('inputs/binary_measurements.json')
        audit.D['pkr'] = audit.rj('inputs/sd/package_result.json')

    def test_large_header_magic_abi_crc_and_missing_measurement(self):
        baseline = copy.deepcopy(audit.D['bm'])
        for field in ('magic', 'abi', 'missing_crc', 'missing_sha', 'missing_header'):
            with self.subTest(field=field):
                audit.D['bm'] = copy.deepcopy(baseline)
                record = audit.D['bm']['LINUX.BIN']
                if field in ('magic', 'abi'):
                    h = bytearray.fromhex(record['header_hex'])
                    if field == 'magic':
                        h[0] ^= 1
                    else:
                        struct.pack_into('<I', h, 32, 0)
                    struct.pack_into('<I', h, 36, zlib.crc32(h[:36]))
                    record['header_hex'] = h.hex()
                    record['header_crc_actual'] = zlib.crc32(h[:36])
                elif field == 'missing_crc':
                    record.pop('payload_crc_actual')
                elif field == 'missing_sha':
                    record.pop('sha256')
                else:
                    record.pop('header_hex')
                audit.s07_delegated()
                self.assertFalse(audit.CHECKS[-1]['passed'], audit.CHECKS[-1])

    def test_kernel_option_disabled_is_not_present_enabled(self):
        real_rt = audit.rt

        def read(rel):
            value = real_rt(rel)
            return value.replace('CONFIG_MMC=y', 'CONFIG_MMC=n') if rel.endswith('kernel.config') else value

        with patch.object(audit, 'rt', side_effect=read):
            audit.s10_linux()
        check = next(c for c in audit.CHECKS if c['name'] == 'linux_kernel_sd_stack')
        self.assertFalse(check['passed'])

    def test_scratch_extent_includes_header(self):
        audit.s09_uboot()
        check = next(c for c in audit.CHECKS if c['name'] == 'uboot_sd_bootpath')
        self.assertTrue(check['passed'], check)
        self.assertIn('0x1187c070', check['evidence'])
        self.assertIn('25673840', check['evidence'])


if __name__ == '__main__':
    unittest.main()
