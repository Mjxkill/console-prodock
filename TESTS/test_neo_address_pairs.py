import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/neo'))
from probe_address_pairs import BASE, analyze, cases, phase_cases


def captured(trials, alias=False):
    lines = ['NEO_ADDRESS_PAIRS_BEGIN']
    for t in trials:
        for i, label in enumerate(t.get('read_order', 'abbaabba')):
            value = t['expected_' + (t['order'][-1].lower() if alias else label)]
            lines.append(f'PAIR {t["id"]} {i} {label} {value:#x}')
    return '\n'.join(lines + ['NEO_ADDRESS_PAIRS_COMPLETE'])


class AddressPairs(unittest.TestCase):
    def test_all_cases_bounded_distinct_complementary_and_one_address_bit(self):
        trials = cases()
        self.assertEqual(len(trials), 256)
        for t in trials:
            self.assertEqual(t['a'] ^ t['b'], 1 << t['bit'])
            self.assertEqual(t['expected_a'] ^ t['expected_b'], 0xffffffff)
            self.assertTrue(all(BASE <= t[k] < BASE + 4096 and t[k] % 4 == 0 for k in ('a', 'b')))
        self.assertEqual({t['order'] for t in trials}, {'AB', 'BA'})

    def test_correct_memory(self):
        trials = cases()
        r = analyze(trials, captured(trials))
        self.assertTrue(r['passed'])
        self.assertEqual(r['captured_reads'], 2048)

    def test_last_write_wins_alias_is_recognized(self):
        trials = cases()
        r = analyze(trials, captured(trials, alias=True))
        self.assertTrue(r['complete'])
        self.assertFalse(r['passed'])
        self.assertEqual(r['bad_reads'], 1024)
        self.assertEqual(r['closer_to_other'], 1024)

    def test_same_address_repeats_cover_each_phase(self):
        trials = phase_cases()
        self.assertEqual(len(trials), 16)
        for t in trials:
            for label in 'ab':
                self.assertEqual({i % 4 for i, l in enumerate(t['read_order']) if l == label}, {0, 1, 2, 3})
        r = analyze(trials, captured(trials))
        self.assertTrue(r['passed'])
        self.assertEqual(r['captured_reads'], 1120)

    def test_missing_duplicate_and_wrong_label_cannot_pass(self):
        trials = cases()[:1]
        good = captured(trials)
        missing = good.replace(good.splitlines()[1], '')
        self.assertFalse(analyze(trials, missing)['complete'])
        with self.assertRaises(ValueError):
            analyze(trials, good + '\n' + good.splitlines()[1])
        with self.assertRaises(ValueError):
            analyze(trials, good.replace('PAIR 0 0 a ', 'PAIR 0 0 b '))


if __name__ == '__main__':
    unittest.main()
