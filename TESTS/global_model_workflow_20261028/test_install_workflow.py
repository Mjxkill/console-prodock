#!/usr/bin/env python3
"""Install real fixture packs into temporary homes; never touch user globals."""
import copy
import fcntl
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import install_workflow as installer


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.source=self.root/'pack';self.source.mkdir()
        self.home=self.root/'codex-home'
        for name in installer.INSTALLABLE:
            (self.source/name).write_text('# synthetic install test '+name+'\n')
        (self.source/'GLOBAL_AGENTS.md').write_bytes(installer.BEGIN+b'\nManaged policy.\n'+installer.END+b'\n')
        installer.make_manifest(self.source)

    def tearDown(self):
        self.tmp.cleanup()

    def test_prepare_does_not_create_home(self):
        plan,updates=installer.prepare(self.source,self.home)
        self.assertTrue(plan['changed']);self.assertFalse(self.home.exists())
        self.assertEqual(updates[-1][0].name,installer.MANIFEST)

    def test_first_install_idempotent_and_explicit_allowlist(self):
        for name in ['secret.env','prompt.txt','test_runner.py','output.log','metrics.sqlite3']:
            (self.source/name).write_text('must not be published')
        first=installer.install(self.source,self.home)
        self.assertEqual(first['backups'],[])
        destination=self.home/'model-workflow'
        self.assertEqual({p.name for p in destination.iterdir()},set(installer.INSTALLABLE)|{installer.MANIFEST})
        before={p: p.read_bytes() for p in destination.iterdir()}
        second=installer.install(self.source,self.home)
        self.assertFalse(second['changed']);self.assertEqual(second['backups'],[])
        self.assertEqual(before,{p:p.read_bytes() for p in destination.iterdir()})
        self.assertEqual(first['manifest_sha256'],second['manifest_sha256'])

    def test_existing_instructions_override_settings_data_preserved(self):
        self.home.mkdir();agents=self.home/'AGENTS.md';override=self.home/'AGENTS.override.md'
        agents.write_text('Existing rules without final newline')
        override.write_text('Important override\n')
        config=self.home/'config.toml';config.write_text('model="keep-this"\n')
        destination=self.home/'model-workflow';destination.mkdir()
        database=destination/'metrics.sqlite3';database.write_bytes(b'untouched user database')
        data=destination/'data';data.mkdir();(data/'current.json').write_text('keep')
        result=installer.install(self.source,self.home)
        self.assertTrue(result['override_present']);self.assertIsNotNone(result['override_notice'])
        self.assertTrue(agents.read_text().startswith('Existing rules without final newline\n\n'))
        self.assertTrue(override.read_text().startswith('Important override\n\n'))
        self.assertEqual(config.read_text(),'model="keep-this"\n')
        self.assertEqual(database.read_bytes(),b'untouched user database')
        self.assertEqual((data/'current.json').read_text(),'keep')
        self.assertEqual(len(result['backups']),2)
        self.assertEqual({Path(p).read_text() for p in result['backups']},{'Existing rules without final newline','Important override\n'})
        again=installer.install(self.source,self.home);self.assertFalse(again['changed']);self.assertEqual(again['backups'],[])

    def test_upgrade_preserves_prefix_suffix_and_backs_up_only_changes(self):
        installer.install(self.source,self.home)
        agents=self.home/'AGENTS.md';old=agents.read_bytes()
        agents.write_bytes(b'Prefix\n'+old+b'Suffix\n')
        (self.source/'metrics.py').write_text('# new reviewed metrics\n')
        block=(self.source/'GLOBAL_AGENTS.md').read_bytes().replace(b'Managed policy.',b'New managed policy.')
        (self.source/'GLOBAL_AGENTS.md').write_bytes(block);installer.make_manifest(self.source)
        result=installer.install(self.source,self.home)
        self.assertEqual(agents.read_bytes(),b'Prefix\n'+block+b'Suffix\n')
        names={Path(p).name.split('.backup.')[0] for p in result['backups']}
        self.assertEqual(names,{'metrics.py','GLOBAL_AGENTS.md','AGENTS.md',installer.MANIFEST})

    def test_source_hash_conflict_refused_before_mutation(self):
        (self.source/'runner.py').write_text('# unexpected source edit\n')
        with self.assertRaisesRegex(ValueError,'Source manifest mismatch'):
            installer.install(self.source,self.home)
        self.assertFalse(self.home.exists())

    def test_installed_hash_conflict_not_overwritten(self):
        installer.install(self.source,self.home)
        path=self.home/'model-workflow/metrics.py';path.write_text('# local edit\n')
        before={p:p.read_bytes() for p in self.home.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError,'changed locally'):installer.install(self.source,self.home)
        self.assertEqual(before,{p:p.read_bytes() for p in self.home.rglob('*') if p.is_file()})

    def test_unmanaged_file_conflict_refused(self):
        destination=self.home/'model-workflow';destination.mkdir(parents=True)
        path=destination/'runner.py';path.write_text('do not overwrite')
        with self.assertRaisesRegex(ValueError,'Unmanaged conflicting file'):installer.install(self.source,self.home)
        self.assertEqual(path.read_text(),'do not overwrite')
        self.assertFalse((self.home/'AGENTS.md').exists())

    def test_symlinks_and_path_traversal_refused(self):
        alias=self.root/'linked-pack';alias.symlink_to(self.source,target_is_directory=True)
        with self.assertRaises(ValueError):installer.prepare(alias,self.home)
        with self.assertRaises(ValueError):installer.prepare(self.source,self.root/'x/../codex-home')
        self.home.mkdir();(self.home/'AGENTS.md').symlink_to(self.source/'WORKFLOW.md')
        with self.assertRaises(ValueError):installer.install(self.source,self.home)
        self.assertFalse((self.home/'model-workflow').exists())

    def test_malformed_blocks_refused_before_any_copy(self):
        self.home.mkdir()
        (self.home/'AGENTS.md').write_bytes(installer.BEGIN+b'\nUnterminated')
        with self.assertRaisesRegex(ValueError,'partial policy markers'):installer.install(self.source,self.home)
        self.assertFalse((self.home/'model-workflow').exists())

    def test_install_lock_exclusion(self):
        self.home.mkdir()
        with (self.home/'.model-workflow-install.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):installer.install(self.source,self.home)
        self.assertFalse((self.home/'model-workflow').exists())

    def test_source_manifest_extra_name_refused(self):
        path=self.source/installer.MANIFEST;value=json.loads(path.read_text())
        value['files']['secrets.env']={'sha256':'0'*64,'size':0};path.write_text(json.dumps(value))
        with self.assertRaises(ValueError):installer.install(self.source,self.home)

    def test_manifest_published_last_and_each_write_whole(self):
        calls=[];actual=installer.atomic_bytes
        def record(path,raw,mode=0o600):
            calls.append(path.name);actual(path,raw,mode)
            self.assertEqual(path.read_bytes(),raw)
        with mock.patch.object(installer,'atomic_bytes',record):installer.install(self.source,self.home)
        self.assertEqual(calls[-1],installer.MANIFEST)
        self.assertNotIn('config.toml',calls)


if __name__=='__main__':
    unittest.main(verbosity=2)
