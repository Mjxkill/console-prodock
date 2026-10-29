"""Keep advice, executed work and unknown history statistically distinct."""
import json
import tempfile
import unittest
from pathlib import Path

import metrics
import test_metrics


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_metrics.RegistryTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_identical_tasks_do_not_merge_modes_or_invent_requests(self):
        f = self.fixture
        f.import_one('old')
        f.import_one('review', execution_mode='review', model_requests=None,
                     tool_calls=0, test_runs=0, test_failures=0)
        f.import_one('agent', execution_mode='execution', model_requests=5,
                     tool_calls=4, test_runs=2, test_failures=1)
        report = metrics.build_report(f.db)
        self.assertEqual(report['n_runs'], 3)
        groups = {x['cohort']['execution_mode']: x for x in report['cohorts']}
        self.assertEqual(set(groups), {'legacy_unspecified', 'review', 'execution'})
        self.assertIsNone(groups['review']['execution_counts']['model_requests']['total'])
        self.assertEqual(groups['review']['execution_counts']['tool_calls']['total'], 0)
        self.assertEqual(groups['execution']['execution_counts']['test_failures']['total'], 1)
        self.assertIn('execution_mode', metrics.csv_report(report).splitlines()[0])
        self.assertIn('legacy_unspecified', metrics.html_report(report))
        # Reading reports does not rewrite historical records.
        with metrics.database(f.db) as con:
            old = json.loads(con.execute("SELECT raw_json FROM runs WHERE run_id='old'").fetchone()[0])
        self.assertNotIn('execution_mode', old)

    def test_impossible_or_ambiguous_counts_are_refused(self):
        f = self.fixture
        for changes in [dict(model_requests=-1), dict(tool_calls=True),
                        dict(test_runs=1, test_failures=2), dict(execution_mode='automatic'),
                        dict(execution_mode='review', model_config={'execution_mode': 'execution'})]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                metrics.import_run(f.db, f.document(f.run_data(**changes)))


if __name__ == '__main__':
    unittest.main()
