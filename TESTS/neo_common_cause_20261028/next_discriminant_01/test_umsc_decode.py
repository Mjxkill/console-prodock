"""No hardware or transport: malformed transcript and CDC interpretation tests."""
import unittest
from umsc_decode import BASE, IDENTITY, ORDER, decode


def transcript(first=2, second=2):
    return [dict(seq=i, address=address, value=value) for i, (address, value)
            in enumerate(zip(ORDER, (IDENTITY, first, 1, IDENTITY, second, 1)))]


class DecodeTests(unittest.TestCase):
    def test_idle_complete(self):
        result = decode(transcript())
        self.assertTrue(result['contract_passed'])
        self.assertFalse(result['hardware_qualified'])
        self.assertEqual(result['usb_functionality'], 'not_tested')

    def test_every_partial_prefix_fails_and_preserves(self):
        for count in range(6):
            records = transcript()[:count]
            result = decode(records)
            self.assertFalse(result['contract_passed'])
            self.assertEqual(result['observations'], records)

    def test_wrong_identity_or_version(self):
        for position in (0, 2, 3, 5):
            records = transcript()
            records[position]['value'] = 0
            self.assertFalse(decode(records)['contract_passed'])

    def test_no_address_alias_or_forbidden_read(self):
        for address in (4, BASE + 8, BASE + 0x20, BASE + 0x24, BASE + 0x10004):
            records = transcript()
            records[1]['address'] = address
            with self.assertRaises(ValueError):
                decode(records)

    def test_tags_duplicates_order_and_extra_records(self):
        records = transcript()
        records[2]['seq'] = 1
        with self.assertRaises(ValueError):
            decode(records)
        with self.assertRaises(ValueError):
            decode(transcript()[::-1])
        with self.assertRaises(ValueError):
            decode(transcript() + transcript()[:1])

    def test_integer_bounds(self):
        for key in ('seq', 'address', 'value'):
            for bad in (-1, 2**32, True, 3.5, '0x2', None):
                records = transcript()
                records[1][key] = bad
                with self.assertRaises(ValueError):
                    decode(records)

    def test_exact_fields_only(self):
        records = transcript()
        records[1]['write'] = False
        with self.assertRaises(ValueError):
            decode(records)

    def test_owner_and_request_bits_not_swapped(self):
        a, b = decode(transcript(0x102, 0x202))['statuses']
        self.assertEqual((a['owner_sampled'], a['serve_requested']), (True, False))
        self.assertEqual((b['owner_sampled'], b['serve_requested']), (False, True))
        self.assertFalse(decode(transcript(0x302, 2))['contract_passed'])

    def test_cdc_state_changes_are_not_hardware_errors(self):
        result = decode(transcript(0x42, 0x22))
        self.assertTrue(result['contract_passed'])
        self.assertEqual(result['transitions'][0]['changed_fields'],
                         ['online_sampled', 'highspeed_sampled'])
        self.assertEqual([s['raw'] for s in result['statuses']], [0x42, 0x22])

    def test_all_status_bits_and_level(self):
        result = decode(transcript(0x123404FD, 0x123404FD))
        status = result['statuses'][0]
        self.assertEqual(status['tx_level'], 0x1234)
        for key in ('rx_gathered_available', 'seen_bus_reset', 'seen_bot_reset',
                    'quiet', 'online_sampled', 'highspeed_sampled', 'lost', 'halted_sampled'):
            self.assertTrue(status[key])
        self.assertFalse(status['tx_level_zero'])

    def test_reserved_bits_and_combinational_relation(self):
        for value in (0x802, 0xF802, 0, 0x10002):
            self.assertFalse(decode(transcript(value, 2))['contract_passed'])

    def test_watchdog_side_effect(self):
        self.assertTrue(decode(transcript()[:1])['watchdog_refreshed'])
        self.assertFalse(decode([])['watchdog_refreshed'])


if __name__ == '__main__':
    unittest.main()
