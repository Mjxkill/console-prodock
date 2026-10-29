"""Protected adversarial acceptance tests; the agent may not modify this file."""
import copy
import unittest
from agent_audit import summarize


def call(event, request=1, launch='launch1', name='run_tests'):
    return dict(event=event, launch_id=launch, request_id=request, name=name)


def outcome(index=0, rc=0, request=1, launch='launch1', **flags):
    return dict(event='test_finish', launch_id=launch, request_id=request,
                index=index, returncode=rc, timeout=flags.get('timeout', False),
                output_limited=flags.get('output_limited', False))


def complete(*outcomes, request=1, launch='launch1'):
    return [call('tool_start', request, launch), call('tool_finish', request, launch),
            *(outcomes or (outcome(request=request, launch=launch),))]


class AuditTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(summarize([]), dict(test_runs=0, test_failures=0, complete=True, test_calls=0))

    def test_commands_not_calls_and_no_mutation(self):
        records = complete(outcome(), outcome(1, 1), outcome(2, -9))
        saved = copy.deepcopy(records)
        self.assertEqual(summarize(records), dict(test_runs=3, test_failures=2, complete=True, test_calls=1))
        self.assertEqual(records, saved)

    def test_identical_duplicates_are_idempotent(self):
        records = complete(outcome(), outcome(1, 1))
        self.assertEqual(summarize(records + copy.deepcopy(records)), summarize(records))

    def test_conflicting_outcome_refused(self):
        with self.assertRaises(ValueError):
            summarize(complete(outcome()) + [outcome(rc=1)])

    def test_separate_launches_and_string_request(self):
        records = complete(request='r') + complete(request='r', launch='launch2')
        self.assertEqual(summarize(records)['test_runs'], 2)
        self.assertEqual(summarize(records)['test_calls'], 2)

    def test_partial_and_out_of_order(self):
        records = complete(outcome(), outcome(1, 1))
        self.assertEqual(summarize(records[::-1]), summarize(records))
        for partial in ([call('tool_start')], [call('tool_finish')], [outcome()],
                        [call('tool_start'), call('tool_finish')],
                        [call('tool_start'), outcome()]):
            self.assertFalse(summarize(partial)['complete'])
        self.assertEqual(summarize([outcome(rc=1)])['test_failures'], 1)

    def test_timeout_and_limit_even_when_returncode_zero(self):
        records = complete(outcome(timeout=True), outcome(1, output_limited=True))
        self.assertEqual(summarize(records)['test_failures'], 2)

    def test_other_tools_and_lifecycle_do_not_inflate(self):
        records = [dict(event='sandbox_start'), dict(event='launcher_exit'),
                   call('tool_start', request=2, name='read_file'),
                   call('tool_finish', request=2, name='read_file')]
        self.assertEqual(summarize(records), summarize([]))

    def test_bad_types_or_missing_fields(self):
        for key, invalids in {'index': [-1, 1024, True, '0'],
                             'returncode': [True, '0', -256, 256],
                             'timeout': [0, None], 'output_limited': [1, 'false'],
                             'request_id': [True, '', None], 'launch_id': ['', None]}.items():
            for invalid in invalids:
                records = complete()
                records[-1][key] = invalid
                with self.assertRaises(ValueError, msg=(key, invalid)):
                    summarize(records)
        records = complete()
        del records[-1]['returncode']
        with self.assertRaises(ValueError):
            summarize(records)
        for invalid in (None, {}, [None], [{'event': 1}]):
            with self.assertRaises(ValueError):
                summarize(invalid)


if __name__ == '__main__':
    unittest.main(verbosity=2)
