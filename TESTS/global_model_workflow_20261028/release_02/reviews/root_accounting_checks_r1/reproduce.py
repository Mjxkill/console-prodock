"""Local-only accounting counterexamples, on temporary copies of the code.

Never reads credentials or invokes a provider. SQLite, queue states and outputs
are temporary synthetic fixtures. The runtime files under pack remain untouched.
"""
import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exercise():
    with tempfile.TemporaryDirectory(prefix='accounting-adverse-', dir='/tmp') as temporary:
        copied = Path(temporary)
        for name in ('pack', 'tests'):
            shutil.copytree(ROOT / name, copied / name)
        sys.path[:0] = [str(copied / 'pack'), str(copied / 'tests')]
        import metrics
        import dispatch_queue as queue
        import runner
        from test_metrics import RegistryTests
        from test_queue import QueueTests
        f = RegistryTests()
        f.setUp()
        try:
            f.import_one('legacy')
            f.import_one('review_unknown', execution_mode='review')
            f.import_one('review_zero', execution_mode='review', model_requests=0,
                         tool_calls=0, test_runs=0, test_failures=0)
            f.import_one('execution', execution_mode='execution', model_requests=3,
                         tool_calls=2, test_runs=1, test_failures=0)
            with metrics.database(f.db) as con:
                before = [dict(r) for r in con.execute('SELECT * FROM runs ORDER BY run_id')]
            report = metrics.build_report(f.db)
            csv_rows = list(csv.DictReader(io.StringIO(metrics.csv_report(report))))
            html = metrics.html_report(report)
            with metrics.database(f.db) as con:
                after = [dict(r) for r in con.execute('SELECT * FROM runs ORDER BY run_id')]
            assert before == after
            modes = {c['cohort']['execution_mode']: c for c in report['cohorts']}
            assert set(modes) == {'legacy_unspecified', 'review', 'execution'}
            assert modes['legacy_unspecified']['execution_counts']['model_requests']['total'] is None
            assert modes['review']['execution_counts']['model_requests']['total'] == 0
            assert modes['review']['execution_counts']['model_requests']['unknown'] == 1
            assert all(m in html for m in modes)
            assert {row['execution_mode'] for row in csv_rows} == set(modes)
            legacy_csv = next(r for r in csv_rows if r['execution_mode'] == 'legacy_unspecified')
            assert legacy_csv['model_requests_total'] == '' and legacy_csv['model_requests_unknown'] == '1'
            accounting = dict(rows_unchanged=True, modes=sorted(modes),
                              csv=csv_rows, execution_counts={m: c['execution_counts'] for m, c in modes.items()})
        finally:
            f.tearDown()
        args = ['--project', str(copied), '--out', str(copied / 'unused'),
                '--packet', 'unused', '--model', 'beam', '--task-id', 'advice',
                '--domain', 'test', '--task-type', 'review',
                '--acceptance-criteria', 'No provider access']
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            try:
                runner.arguments(args)
            except SystemExit as error:
                runner_missing_mode_refused = error.code == 2 and 'required: --mode' in captured.getvalue()
        assert runner_missing_mode_refused
        q = QueueTests()
        q.setUp()
        try:
            a, b = q.job('a'), q.job('b', [{'task_id': 'a', 'condition': 'on_success'}])
            refused = []
            for mode in (None, 'execution', 'legacy_unspecified'):
                job = dict(a)
                if mode is None:
                    job.pop('execution_mode')
                else:
                    job['execution_mode'] = mode
                try:
                    queue.validate_queue(q.document([job]), q.project)
                except ValueError:
                    refused.append(mode)
            assert refused == [None, 'execution', 'legacy_unspecified']
            doc = queue.validate_queue(q.document([a, b]), q.project)
            output = q.session / 'runs' / a['run_id']
            output.mkdir()
            foreign = dict(run_id=a['run_id'], task_id=a['task_id'], model=a['model'],
                           input_sha256=a['packet_sha256'], execution_mode='execution',
                           model_config={'execution_mode': 'execution'},
                           exit_code=0, status=queue.SUCCESS, truncated=False)
            absent = {k: v for k, v in foreign.items() if k != 'execution_mode'}
            cases = [('execution_result', foreign), ('missing_mode', absent),
                     ('conflicting_config', dict(foreign, execution_mode='review')),
                     ('nonobject_config', dict(foreign, execution_mode='review', model_config=[]))]
            queue_results = []
            for label, record in cases:
                state = queue.reconcile(doc, None, q.project, q.session)
                state['jobs']['a']['status'] = 'RUNNING'
                for name in ('status.json', 'metrics.json'):
                    (output / name).write_text(json.dumps(record))
                (output / 'registry_import.json').write_text(json.dumps({
                    'passed': True, 'metrics_sha256': sha(output / 'metrics.json')}))
                error = None
                try:
                    queue.runner_status(q.session, a)
                except ValueError as exc:
                    error = str(exc)
                reconciled = queue.reconcile(doc, state, q.project, q.session)
                queue.settle(reconciled)
                queue_results.append(dict(case=label, requested_mode=a['execution_mode'],
                    declared_mode=record.get('execution_mode'), refusal=error,
                    adopted_status=reconciled['jobs']['a']['status'],
                    dependent_status=reconciled['jobs']['b']['status'],
                    success_dependent_ready=queue.ready(reconciled['jobs']['b'], reconciled),
                    wrong_mode_refused=(reconciled['jobs']['a']['status'] != queue.SUCCESS)))
        finally:
            q.doCleanups()
        return dict(hardware_access=False, network_access=False, credentials_access=False,
                    registry_rows_unchanged=accounting['rows_unchanged'], accounting=accounting,
                    startup_refusals=refused, runner_missing_mode_refused=runner_missing_mode_refused,
                    queue_result_mode_cases=queue_results,
                    sources={name: sha(copied / 'pack' / name) for name in
                             ('metrics.py', 'runner.py', 'dispatch_queue.py')})


if __name__ == '__main__':
    print(json.dumps(exercise(), indent=2))
