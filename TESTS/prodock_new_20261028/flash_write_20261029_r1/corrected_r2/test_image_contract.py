"""Pre-write consistency and source-binding tests; only fake programmer I/O."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

import flash_write as w
from fixture_factory import Fixture, sha, store, BACKUP

SOURCE = Path(__file__).resolve().parent


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.f = Fixture(self.temp.name, SOURCE)
        self.prepared = self.f.tests/'prepared'
        self.run = self.f.tests/'run'

    def prepare(self):
        w.prepare(self.f.request, sha(self.f.request), self.prepared, root=self.f.root)
        self.plan_path = self.prepared/'plan.json'
        self.plan = json.loads(self.plan_path.read_text())
        self.image = Path(self.plan['image']['path'])
        self.payload = Path(self.plan['payload']['path'])
        self.report_path = Path(self.plan['offline_report']['path'])
        self.f.after = self.image.read_bytes() + BACKUP[self.image.stat().st_size:]

    def execute(self):
        return w.execute(self.plan_path, sha(self.plan_path), self.run, root=self.f.root,
            runner=self.f.runner, guard_factory=lambda root:self.f.guard())

    def changed_image(self):
        data = bytearray(self.image.read_bytes()); data[65535] ^= 0x80
        self.image.write_bytes(data)
        self.plan['image']['sha256'] = sha(self.image)

    def save_plan(self):
        store(self.plan_path, self.plan)

    def assert_prewrite_refusal(self):
        try:
            result = self.execute()
        except (ValueError, RuntimeError, OSError):
            result = None
        if result is not None:
            self.assertFalse(result['program_attempted'], result)
            self.assertEqual(result['status'], 'failed', result)
        self.assertEqual(self.f.calls, [])

    def test_valid_bytes_checked_twice_and_written_once(self):
        self.prepare()
        self.assertTrue(self.plan['image_contract']['verified'])
        r = self.execute()
        self.assertTrue(r['image_contract']['verified'], r)
        self.assertEqual(r['status'], 'coldboot_pending')
        self.assertEqual(len(self.f.calls), 2)

    def test_change_after_first_native_check_refused_during_prepare(self):
        original = w.proofs.check_raw_route
        def check_then_change(fs, image):
            record = original(fs, image)
            data = bytearray(image.read_bytes());data[-1] ^= 0x80
            image.write_bytes(data)
            return record
        with patch.object(w.proofs, 'check_raw_route', side_effect=check_then_change):
            with self.assertRaises((ValueError,RuntimeError)):self.prepare()
        self.assertFalse((self.prepared/'prepared/program.bin').exists())
        self.assertTrue((self.prepared/'prepare_error.json').exists())
        self.assertEqual(self.f.calls, [])

    def test_change_after_final_native_check_is_detected(self):
        original=w.proofs.check_raw_route
        calls=[]
        def check_then_change(fs,image):
            calls.append(1);r=original(fs,image)
            if len(calls)==2:
                data=bytearray(image.read_bytes());data[-1]^=1;image.write_bytes(data)
            return r
        with patch.object(w.proofs,'check_raw_route',side_effect=check_then_change):
            with self.assertRaises((ValueError,RuntimeError)):self.prepare()
        self.assertEqual(len(calls),2)
        self.assertEqual(self.f.calls,[])

    def test_image_changed_between_prepare_and_program(self):
        self.prepare();self.changed_image()  # Keep original plan file unchanged.
        self.assert_prewrite_refusal()

    def test_image_digest_rehashed_but_original_report_still_bound(self):
        self.prepare();self.changed_image();self.save_plan()
        self.assert_prewrite_refusal()

    def test_image_and_report_rehashed_cannot_zero_preserved_tail(self):
        self.prepare();self.changed_image()
        report=json.loads(self.report_path.read_text())
        report['program_sha256']=sha(self.image)
        store(self.report_path,report)
        self.plan['offline_report']['sha256']=sha(self.report_path)
        self.plan['offline_report']['bytes']=self.report_path.stat().st_size
        self.save_plan();self.assert_prewrite_refusal()

    def test_expected_full_hash_must_derive_from_backups(self):
        self.prepare();self.plan['expected_full_sha256']='0'*64
        self.save_plan();self.assert_prewrite_refusal()

    def test_report_and_plan_expected_full_hash_cannot_disagree_with_bytes(self):
        self.prepare();report=json.loads(self.report_path.read_text())
        report['expected_full_sha256']='1'*64
        store(self.report_path,report)
        self.plan['offline_report']['sha256']=sha(self.report_path)
        self.plan['offline_report']['bytes']=self.report_path.stat().st_size
        self.plan['expected_full_sha256']='1'*64
        self.save_plan();self.assert_prewrite_refusal()

    def test_wrong_preserved_tail_length_rejected(self):
        self.prepare();report=json.loads(self.report_path.read_text())
        report['preserved_last_sector_bytes']-=1
        store(self.report_path,report)
        self.plan['offline_report']['sha256']=sha(self.report_path)
        self.plan['offline_report']['bytes']=self.report_path.stat().st_size
        self.plan['preserved_last_sector_bytes']-=1
        self.save_plan();self.assert_prewrite_refusal()

    def test_payload_changed_between_prepare_and_program(self):
        self.prepare();data=bytearray(self.payload.read_bytes());data[-1]^=1
        self.payload.write_bytes(data)
        self.assert_prewrite_refusal()

    def test_internally_consistent_payload_change_still_refuses_accepted_fs_mismatch(self):
        self.prepare()
        payload=bytearray(self.payload.read_bytes());payload[-1]^=1;payload=bytes(payload)
        self.payload.write_bytes(payload)
        image=payload+BACKUP[len(payload):65536];self.image.write_bytes(image)
        report=json.loads(self.report_path.read_text())
        report.update(payload_sha256=sha(self.payload),program_sha256=sha(self.image),
                      expected_full_sha256=hashlib.sha256(payload+BACKUP[len(payload):]).hexdigest())
        store(self.report_path,report)
        for name,path in [('payload',self.payload),('image',self.image),('offline_report',self.report_path)]:
            self.plan[name].update(sha256=sha(path),bytes=path.stat().st_size)
        self.plan.update(payload_sha256=report['payload_sha256'],expected_full_sha256=report['expected_full_sha256'])
        self.save_plan();self.assert_prewrite_refusal()

    def test_report_schema_bool_is_not_integer_one(self):
        self.prepare();report=json.loads(self.report_path.read_text());report['schema']=True
        store(self.report_path,report)
        self.plan['offline_report'].update(sha256=sha(self.report_path),bytes=self.report_path.stat().st_size)
        self.save_plan();self.assert_prewrite_refusal()


if __name__=='__main__':unittest.main()
