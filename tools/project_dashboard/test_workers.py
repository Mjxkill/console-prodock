"""Adversarial worker-inventory tests, entirely using a fake /proc and runs."""
from datetime import datetime, timezone
import importlib.util
import json
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('dashboard_workers', Path(__file__).with_name('workers.py'))
workers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workers)


class WorkersTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workers-test-')
        self.base = Path(self.temp.name)
        self.root = self.base / 'console'
        self.proc = self.base / 'proc'
        self.root.mkdir()
        self.proc.mkdir()
        self.boot = 1700000000
        self.hz = os.sysconf('SC_CLK_TCK')
        (self.proc / 'stat').write_text(f'btime {self.boot}\n')
        (self.proc / 'uptime').write_text('1000.00 0.0\n')
        self.registry = self.root / 'metrics.sqlite'
        self.out = self.root / 'TESTS/run01'
        self.out.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def process(self, pid=100, ppid=1, ticks=None, argv=None, state='S', comm='python3'):
        ticks = 900 * self.hz if ticks is None else ticks
        directory = self.proc / str(pid)
        directory.mkdir(exist_ok=True)
        fields = [state, str(ppid)] + ['0'] * 17 + [str(ticks)] + ['0'] * 8
        (directory / 'stat').write_text(f'{pid} ({comm}) ' + ' '.join(fields))
        argv = ['/usr/bin/python3', '/safe/agent_runner.py', '--project', str(self.root),
                '--spec', str(self.root / 'never-read-spec.json'), '--out', str(self.out),
                '--model', 'beam', '--run-id', 'task-01', '--credential-file',
                '/private/SECRET_CREDENTIAL_PATH.env'] if argv is None else argv
        (directory / 'cmdline').write_bytes(b'\0'.join(arg.encode() for arg in argv) + b'\0')
        return ticks

    def child(self, model='beam', pid=101, ppid=100, ticks=None):
        return self.process(pid, ppid, ticks or 901 * self.hz,
            ['/usr/bin/opencode', 'run', '--model', 'task-provider/' + model,
             '--dir', str(self.out / 'controller')])

    def metadata(self, status='RUNNING', **values):
        data = dict(task_id='task-01', model='beam', status=status,
                    started_at=datetime.fromtimestamp(self.boot + 900, timezone.utc).isoformat())
        data.update(values)
        path = self.out / 'metrics.json'
        path.write_text(json.dumps(data))
        return path

    def registered(self, path=None, model='beam', project=None):
        with sqlite3.connect(self.registry) as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS runs(model,project,source_path,started_at)')
            connection.execute('INSERT INTO runs VALUES (?,?,?,?)',
                (model, str(project or self.root), str(path or self.out / 'metrics.json'), '2026-10-30'))

    def attempt(self, registry, directory, stamp, status, run_id):
        """Create one registered attempt without coupling its mtime to its date."""
        out=self.root/'TESTS'/directory
        out.mkdir(parents=True,exist_ok=True)
        registry.parent.mkdir(parents=True,exist_ok=True)
        meta=dict(task_id='same-mission',run_id=run_id,model='beam',
                  started_at=stamp,status=status)
        source=out/'metrics.json';source.write_text(json.dumps(meta))
        with sqlite3.connect(registry) as connection:
            connection.execute('CREATE TABLE IF NOT EXISTS runs(model,project,source_path,started_at)')
            connection.execute('INSERT INTO runs VALUES (?,?,?,?)',
                               ('beam',str(self.root),str(source),stamp))
        return source

    def collect(self):
        return workers.collect_workers(self.root, proc_root=self.proc, registry=self.registry)

    def beam(self):
        return next(row for row in self.collect() if row['model'] == 'beam')

    def test_empty_has_four_models_unknown_counts(self):
        rows = self.collect()
        self.assertEqual([row['model'] for row in rows], list(workers.MODELS))
        self.assertTrue(all(row['state'] == 'NO_ACTIVE' for row in rows))
        self.assertTrue(all(row['requests'] is None for row in rows))

    def test_running_requires_live_matching_child(self):
        self.process(); self.child(); self.metadata()
        row = self.beam()
        self.assertEqual(row['state'], 'RUNNING')
        self.assertEqual(row['elapsed_s'], 100)
        self.assertEqual(row['evidence']['opencode_pids'], [101])
        self.assertEqual(row['evidence']['start_ticks'], 900 * self.hz)

    def test_runner_without_child_is_starting(self):
        self.process(); self.metadata()
        self.assertEqual(self.beam()['state'], 'STARTING')

    def test_foreign_project_and_escaping_out_are_excluded(self):
        self.process(argv=['python3', '/safe/agent_runner.py', '--project', '/foreign',
                          '--out', str(self.out), '--model', 'beam'])
        self.assertEqual(self.beam()['state'], 'NO_ACTIVE')
        self.process(argv=['python3', '/safe/agent_runner.py', '--project', str(self.root),
                          '--out', '/foreign/run', '--model', 'beam'])
        self.assertEqual(self.beam()['state'], 'NO_ACTIVE')

    def test_out_symlink_escape_is_excluded(self):
        escape = self.base / 'outside'; escape.mkdir()
        link = self.root / 'link'; link.symlink_to(escape, target_is_directory=True)
        self.process(argv=['python3', '/safe/agent_runner.py', '--project', str(self.root),
                          '--out', str(link), '--model', 'beam'])
        self.assertEqual(self.beam()['state'], 'NO_ACTIVE')

    def test_no_credential_or_prompt_or_error_leak(self):
        self.process(); self.child()
        self.metadata(prompt='SECRET_PROMPT', error='SECRET_ERROR',
                      credential_file='/private/SECRET', argv=['SECRET_ARGV'])
        text = json.dumps(self.collect())
        self.assertNotIn('SECRET', text)
        self.assertNotIn('credential', text)
        self.assertNotIn('argv', text)

    def test_complete_result_is_not_running_without_pid(self):
        self.metadata(status='COMPLETED_REVIEW_PENDING_VALIDATION',
                      elapsed_seconds=12, model_requests=9, tool_calls=5, test_runs=3, test_failures=1)
        self.registered()
        row = self.beam()
        self.assertEqual(row['state'], 'REVIEW_PENDING')
        self.assertEqual([row[k] for k in ('requests','tool_calls','tests','failures')], [9,5,3,1])

    def test_stale_running_file_without_pid_is_stopped(self):
        self.metadata(); self.registered()
        self.assertEqual(self.beam()['state'], 'STOPPED')

    def test_pid_reused_explicit_check(self):
        self.process(ticks=950 * self.hz)
        self.assertEqual(workers.process_state(100, 900 * self.hz, proc_root=self.proc)['state'], 'REUSED')
        self.assertEqual(workers.process_state(111, 900 * self.hz, proc_root=self.proc)['state'], 'ABSENT')

    def test_matching_pid_with_old_run_time_is_unknown(self):
        self.process(ticks=950 * self.hz); self.child(ticks=951 * self.hz); self.metadata()
        row = self.beam()
        self.assertEqual(row['state'], 'UNKNOWN')
        self.assertIn('run_time_does_not_match_process', row['evidence']['notes'])

    def test_wrong_child_model_is_unknown(self):
        self.process(); self.child(model='glm-5.3-flash'); self.metadata()
        self.assertEqual(self.beam()['state'], 'UNKNOWN')

    def test_foreign_child_is_not_associated(self):
        self.process(); self.child(ppid=42); self.metadata()
        self.assertEqual(self.beam()['state'], 'STARTING')

    def test_nested_child_is_associated(self):
        self.process(); self.process(pid=105, ppid=100, ticks=901 * self.hz, argv=['wrapper'])
        self.child(ppid=105, ticks=902 * self.hz); self.metadata()
        self.assertEqual(self.beam()['state'], 'RUNNING')

    def test_zombie_child_is_not_running(self):
        self.process(); self.child(); self.metadata()
        text = (self.proc / '101/stat').read_text().replace(') S ', ') Z ')
        (self.proc / '101/stat').write_text(text)
        self.assertEqual(self.beam()['state'], 'STARTING')

    def test_truncated_json_does_not_create_fake_counters(self):
        self.process(); self.child()
        (self.out / 'metrics.json').write_text('{"tool_calls": 500,')
        row = self.beam()
        self.assertEqual(row['state'], 'RUNNING')
        self.assertIsNone(row['tool_calls'])
        self.assertIn('metrics.json:json_incomplete', row['evidence']['notes'])

    def test_metadata_symlink_cannot_read_secret_outside_run(self):
        self.process(); self.child()
        secret = self.root / 'outside-run.json'; secret.write_text('{"task_id":"SECRET","tool_calls":1}')
        (self.out / 'metrics.json').symlink_to(secret)
        row = self.beam()
        self.assertEqual(row['task'], 'task-01')
        self.assertNotIn('SECRET', json.dumps(row))

    def test_progress_counts_completed_tools_and_test_commands(self):
        self.process(); self.child(); self.metadata()
        audit = self.out / 'isolation/audit.jsonl'; audit.parent.mkdir()
        events = [{'event':'tool_start'}, {'event':'tool_finish'}, {'event':'tool_finish'},
                  {'event':'test_finish','returncode':1}]
        audit.write_text('\n'.join(map(json.dumps, events)) + '\n{"event":')
        (self.out / 'baseline.json').write_text('{"test_runs":1,"test_failures":1}')
        (self.out / 'gateway_0.json').write_text('[{}, {}, {}]')
        row = self.beam()
        self.assertEqual([row[k] for k in ('requests','tool_calls','tests','failures')], [3,2,2,2])
        self.assertEqual(row['state'], 'RUNNING')
        self.assertIn('includes initial baseline', row['evidence']['counter_scope'])

    def test_process_permissions_unknown(self):
        self.process(); self.metadata(); self.registered()
        original = Path.read_bytes
        def denied(path):
            if path == self.proc / '100/cmdline':
                raise PermissionError('SECRET_PERMISSION_ERROR')
            return original(path)
        with patch.object(Path, 'read_bytes', denied):
            row = self.beam()
        self.assertEqual(row['state'], 'UNKNOWN')
        self.assertNotIn('SECRET', json.dumps(row))

    def test_unreadable_proc_root_unknown(self):
        original = Path.iterdir
        def denied(path):
            if path == self.proc:
                raise PermissionError('denied')
            return original(path)
        with patch.object(Path, 'iterdir', denied):
            self.assertTrue(all(row['state']=='UNKNOWN' for row in self.collect()))

    def test_registry_foreign_project_excluded(self):
        self.metadata(status='FAILED'); self.registered(project='/foreign')
        self.assertEqual(self.beam()['state'], 'NO_ACTIVE')

    def test_final_metadata_with_live_process_is_finalizing(self):
        self.process(); self.child(); self.metadata(status='COMPLETED_REVIEW_PENDING_VALIDATION')
        self.assertEqual(self.beam()['state'], 'FINALIZING')

    def test_comm_with_parentheses_and_spaces(self):
        ticks = self.process(comm='python (worker) child')
        self.assertEqual(workers.process_state(100, ticks, proc_root=self.proc)['state'], 'RUNNING')

    def test_malformed_metadata_types_remain_safe(self):
        self.metadata(status={'bad':'type'}, elapsed_seconds=10**500,
                      model_requests=10**500, tool_calls=True)
        self.registered()
        row = self.beam()
        self.assertEqual(row['state'], 'UNKNOWN')
        self.assertIsNone(row['elapsed_s'])
        self.assertIsNone(row['requests'])
        self.assertIsNone(row['tool_calls'])

    def test_malformed_registry_path_is_ignored(self):
        self.registered()
        with sqlite3.connect(self.registry) as connection:
            connection.execute('UPDATE runs SET project=NULL,source_path=NULL')
        self.assertEqual(self.beam()['state'], 'NO_ACTIVE')

    def test_global_latest_attempt_across_registries_not_glob_order_or_mtime(self):
        old_db=self.root/'TESTS/model_first/metrics.sqlite'
        new_db=self.root/'TESTS/model_second/metrics.sqlite'
        old=self.attempt(old_db,'attempt_01','2026-10-30T09:29:00Z','FAILED','run-01')
        new=self.attempt(new_db,'attempt_02','2026-10-30T09:32:00Z',
                         'COMPLETED_REVIEW_PENDING_VALIDATION','run-02')
        os.utime(old,(1900000000,1900000000))
        os.utime(new,(1700000000,1700000000))
        original=Path.glob
        for order in ([old_db,new_db],[new_db,old_db]):
            def controlled(path,pattern):
                if path==self.root/'TESTS' and pattern=='model_*/metrics.sqlite':return iter(order)
                return original(path,pattern)
            with patch.object(Path,'glob',controlled):
                row=next(r for r in workers.collect_workers(self.root,proc_root=self.proc) if r['model']=='beam')
            self.assertEqual(row['state'],'REVIEW_PENDING')
            self.assertEqual(row['task'],'same-mission')
            self.assertEqual(row['run_id'],'run-02')
            self.assertEqual(row['evidence']['out'],'TESTS/attempt_02')

    def test_latest_order_uses_instants_not_timezone_text(self):
        old_db=self.root/'TESTS/model_first/metrics.sqlite'
        new_db=self.root/'TESTS/model_second/metrics.sqlite'
        self.attempt(old_db,'offset_old','2026-10-30T10:00:00+02:00','FAILED','run-01')
        self.attempt(new_db,'utc_new','2026-10-30T09:00:00Z','REVIEW_PENDING','run-02')
        row=next(r for r in workers.collect_workers(self.root,proc_root=self.proc) if r['model']=='beam')
        self.assertEqual(row['evidence']['out'],'TESTS/utc_new')

    def test_newest_incomplete_metadata_not_replaced_by_old_success(self):
        first=self.root/'TESTS/model_first/metrics.sqlite'
        second=self.root/'TESTS/model_second/metrics.sqlite'
        self.attempt(first,'old_good','2026-10-30T09:00:00Z','REVIEW_PENDING','run-01')
        newer=self.attempt(second,'new_incomplete','2026-10-30T10:00:00Z','FAILED','run-02')
        newer.write_text('{truncated')
        row=next(r for r in workers.collect_workers(self.root,proc_root=self.proc) if r['model']=='beam')
        self.assertEqual(row['state'],'UNKNOWN')
        self.assertEqual(row['evidence']['out'],'TESTS/new_incomplete')

    def test_run_id_is_distinct_and_sanitized_for_active_and_finished_rows(self):
        self.process();self.child();self.metadata(task_id='mission-01',run_id='attempt-02')
        row=self.beam()
        self.assertEqual(row['task'],'mission-01')
        self.assertEqual(row['run_id'],'attempt-02')
        self.metadata(run_id='SECRET path / credential')
        self.assertIsNone(self.beam()['run_id'])
        self.assertNotIn('SECRET',json.dumps(self.collect()))
        # Stale metadata remains visible as an archived attempt after exit.
        for pid in (100,101):
            (self.proc/str(pid)/'stat').unlink();(self.proc/str(pid)/'cmdline').unlink()
            (self.proc/str(pid)).rmdir()
        self.metadata(task_id='mission-01',run_id='attempt-02',status='REVIEW_PENDING')
        self.registered()
        self.assertEqual(self.beam()['run_id'],'attempt-02')

    def evaluation(self, *, verdict='edited', status='COMPLETED_REVIEW_PENDING_VALIDATION',
                   reviewer_type='model', reviewer='Codex-review', output='a'*64):
        source=self.metadata(status=status,run_id='attempt-02',output_sha256='a'*64)
        proof=self.out/'REVIEW.md';proof.write_text('Independent reviewed evidence.\n')
        with sqlite3.connect(self.registry) as db:
            db.execute('CREATE TABLE IF NOT EXISTS runs(run_id,model,project,source_path,started_at,output_sha256)')
            db.execute('INSERT INTO runs VALUES (?,?,?,?,?,?)',('attempt-02','beam',str(self.root),str(source),'2026-10-31T10:00:00Z','a'*64))
            db.execute('CREATE TABLE IF NOT EXISTS evaluations(id INTEGER PRIMARY KEY,evaluation_id,run_id,verdict,score,evaluator_type,evaluator_id,output_sha256,evidence_path,evidence_sha256,evaluated_at,recorded_at)')
            db.execute('INSERT INTO evaluations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(1,'eval-01','attempt-02',verdict,74,reviewer_type,reviewer,output,str(proof),hashlib.sha256(proof.read_bytes()).hexdigest(),'2026-10-31T11:00:00Z','2026-10-31T11:00:00Z'))
        return proof

    def test_review_accepted_after_changes_separate_runner(self):
        self.evaluation();r=self.beam()
        self.assertEqual(r['state'],'ACCEPTED_AFTER_CHANGES')
        self.assertEqual(r['runner_status'],'COMPLETED_REVIEW_PENDING_VALIDATION')
        self.assertEqual(r['review']['score'],74)
        self.assertEqual(r['review']['evidence'],'TESTS/run01/REVIEW.md')

    def test_wrong_answer_or_untrusted_reviewer_cannot_pass(self):
        self.evaluation(output='b'*64)
        self.assertEqual(self.beam()['state'],'REVIEW_UNKNOWN')
        with sqlite3.connect(self.registry) as db:
            db.execute("UPDATE evaluations SET output_sha256=?,evaluator_id='self-praise'",('a'*64,))
        self.assertEqual(self.beam()['state'],'REVIEW_UNKNOWN')

    def test_changed_or_missing_evidence_cannot_pass(self):
        proof=self.evaluation();proof.write_text('changed')
        self.assertEqual(self.beam()['state'],'REVIEW_UNKNOWN')
        proof.unlink();self.assertEqual(self.beam()['state'],'REVIEW_UNKNOWN')

    def test_other_attempt_does_not_hide_pending(self):
        self.evaluation()
        with sqlite3.connect(self.registry) as db:db.execute("UPDATE evaluations SET run_id='attempt-01'")
        self.assertEqual(self.beam()['state'],'REVIEW_PENDING')
        self.assertIsNone(self.beam()['review'])

    def test_review_never_marks_active_or_failed_process_completed(self):
        self.evaluation(status='FAILED')
        self.assertEqual(self.beam()['state'],'FAILED')
        self.assertEqual(self.beam()['review']['state'],'ACCEPTED_AFTER_CHANGES')
        self.process();self.child();self.metadata(status='RUNNING',run_id='attempt-02',output_sha256='a'*64)
        self.assertEqual(self.beam()['state'],'RUNNING')

    def test_newest_revision_inconclusive_overrules_old_positive(self):
        self.evaluation()
        with sqlite3.connect(self.registry) as db:
            db.execute("INSERT INTO evaluations SELECT 2,'eval-02',run_id,'inconclusive',NULL,evaluator_type,evaluator_id,output_sha256,evidence_path,evidence_sha256,evaluated_at,'2026-10-31T12:00:00Z' FROM evaluations WHERE id=1")
        self.assertEqual(self.beam()['state'],'REVIEW_INCONCLUSIVE')
        self.assertIsNone(self.beam()['review']['score'])

    def test_escaping_proof_and_free_text_never_published(self):
        self.evaluation()
        with sqlite3.connect(self.registry) as db:
            db.execute("UPDATE evaluations SET evidence_path='/private/SECRET',evaluation_id='bad SECRET value'")
        r=self.beam();self.assertEqual(r['state'],'REVIEW_UNKNOWN')
        self.assertNotIn('SECRET',json.dumps(r))


if __name__ == '__main__':
    unittest.main(verbosity=2)
