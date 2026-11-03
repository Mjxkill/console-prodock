"""Do not confuse candidate simulations with a preserved hardware release."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import board_contract as bc


class BoardContractTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.names = ['tang/rtl/common.v', 'tang/boards/neo/top.v', 'linux/prodock-linux.dts']
        owners = ['shared', 'neo', 'prodock']
        files = {}
        for name, owner in zip(self.names, owners):
            self.write(name, 'original\n')
            files[name] = dict(owner=owner, kind='source', prodock_commit_sha256=bc.sha(self.root/name))
        self.write(bc.CATALOG, json.dumps(dict(files=files)))
        self.write('reference.fs', 'preserved bitstream')
        self.write(bc.REFERENCE, json.dumps(dict(commit='measured', bitstream_sha256=bc.sha(self.root/'reference.fs'),
            protected_files={'reference.fs':bc.sha(self.root/'reference.fs')})))
        self.write('games/nebula/assets/packed/nebula.bin', 'assets')
        self.mock = patch.object(bc, 'discover', side_effect=lambda root:list(self.names))
        self.mock.start(); self.addCleanup(self.mock.stop)

    def write(self, name, content):
        p = self.root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)

    def stamp(self):
        result = dict(passed=True, inputs_digest=bc.digest(bc.regression_inputs(self.root)), tests=[])
        for name in bc.REQUIRED_TESTS:
            log = 'TESTS/dual_board/run/'+name+'.log'; self.write(log, 'PASS\n')
            result['tests'].append(dict(name=name, passed=True, log=log, log_sha256=bc.sha(self.root/log)))
        path = 'TESTS/dual_board/run/result.json'; self.write(path, json.dumps(result))
        self.write(bc.CACHE, json.dumps(dict(result=path, sha256=bc.sha(self.root/path))))

    def test_runtime_build_script_is_not_ignored_as_generated(self):
        self.assertTrue(bc.production_path('linux/build.py'))
        self.assertTrue(bc.production_path('tools/build_gpu.py'))
        self.assertFalse(bc.production_path('linux/build/src/kernel/foo.c'))
        self.assertFalse(bc.production_path('tang/rtl/ae350/temp/FIFO/old.v'))

    def test_unknown_deleted_and_symlinked_source_rejected(self):
        self.names.append('tang/rtl/new.v')
        with self.assertRaises(ValueError): bc.inventory(self.root)
        self.names.pop(); (self.root/self.names[0]).unlink()
        with self.assertRaises(ValueError): bc.inventory(self.root)
        (self.root/self.names[0]).symlink_to(self.root/'reference.fs')
        with self.assertRaises(ValueError): bc.inventory(self.root)

    def test_reference_corruption_blocks_both_boards_even_as_candidates(self):
        self.stamp(); self.write('reference.fs', 'corruption')
        for board in ('neo', 'prodock'):
            with self.assertRaises(ValueError): bc.before_build(board, candidate=True, root=self.root)

    def test_shared_change_requires_explicit_candidate_and_current_regression(self):
        self.write(self.names[0], 'changed'); self.stamp()
        with self.assertRaises(ValueError): bc.before_build('prodock', root=self.root)
        result = bc.before_build('prodock', candidate=True, root=self.root)
        self.assertFalse(result['release_qualified'])
        self.assertEqual(result['prodock_hardware_validation'], 'pending_for_changed_inputs')
        self.assertFalse(result['local_regressions']['hardware_validation'])
        self.write(self.names[0], 'changed again')
        for board in ('neo', 'prodock'):
            with self.assertRaises(ValueError): bc.before_build(board, candidate=True, root=self.root)

    def test_neo_file_is_individual_but_invalidates_local_test_inputs(self):
        self.stamp(); self.write(self.names[1], 'changed Neo')
        self.assertEqual(bc.audit(self.root)['changes_since_prodock'], [])
        with self.assertRaises(ValueError): bc.require_local_regressions(self.root)

    def test_failed_missing_or_changed_evidence_never_passes(self):
        with self.assertRaises(ValueError): bc.require_local_regressions(self.root)
        self.stamp(); self.write('TESTS/dual_board/run/bridge.log', 'FAIL')
        with self.assertRaises(ValueError): bc.require_local_regressions(self.root)
        self.stamp()
        path = self.root/'TESTS/dual_board/run/result.json'
        data=json.loads(path.read_text());data['tests'].pop();path.write_text(json.dumps(data))
        self.write(bc.CACHE,json.dumps(dict(result=str(path.relative_to(self.root)),sha256=bc.sha(path))))
        with self.assertRaises(ValueError): bc.require_local_regressions(self.root)


if __name__ == '__main__':
    unittest.main()
