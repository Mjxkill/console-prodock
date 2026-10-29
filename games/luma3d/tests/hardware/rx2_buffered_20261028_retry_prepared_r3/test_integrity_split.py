"""Verify that a count anomaly never skips exact readback or becomes PASS."""
import types
import unittest
from unittest.mock import patch
import trial


class Channel:
    shell = True
    current = None
    def text(self, command):
        pass
    def restore_shell(self, session):
        self.current = None
        self.shell = True


class FakeSession:
    def __init__(self, channel, nonce, data, **kwargs):
        self.offset = 0
        self.data = data
        self.retries = 2
        self.nack_events = 3
        self.returncode = 0
        self.sent_frames = 3
        self.send_seconds = self.wait_seconds = 0
        self.replies = []
    def command(self, *args):
        return b'launch'
    def begin(self):
        return types.SimpleNamespace(offset=0)
    def reset_times(self):
        pass
    def block(self, mutate=None):
        self.offset = len(self.data)
    def finish(self, **kwargs):
        pass


class Tests(unittest.TestCase):
    def test_anomaly_reads_every_byte_then_marks_only_stability_failed(self):
        data = b'exact payload'
        with patch.object(trial, 'TimedSession', FakeSession), patch.object(trial, 'payload_readback', return_value=dict(bytes=len(data), sha256='test')) as readback:
            result = trial.probe(Channel(), 'injected_anomaly', data)
        self.assertTrue(result['integrity_passed'])
        self.assertFalse(result['link_stability_passed'])
        self.assertEqual((result['retries'], result['nack_events']), (2, 3))
        self.assertEqual(readback.call_args.args[-1], data)

    def test_bad_readback_is_still_fatal(self):
        with patch.object(trial, 'TimedSession', FakeSession), patch.object(trial, 'payload_readback', side_effect=RuntimeError('mismatch')):
            with self.assertRaisesRegex(RuntimeError, 'mismatch'):
                trial.probe(Channel(), 'corrupt', b'bad')

    def test_receiver_deadline_is_still_fatal_without_readback_claim(self):
        with patch.object(trial, 'TimedSession', FakeSession), patch.object(FakeSession, 'block', side_effect=trial.sender.Uncertain('deadline')), patch.object(trial, 'payload_readback') as readback:
            with self.assertRaises(trial.sender.Uncertain):
                trial.probe(Channel(), 'timeout', b'pending')
            readback.assert_not_called()


if __name__ == '__main__':
    unittest.main()
