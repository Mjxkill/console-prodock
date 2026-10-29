"""A mapping experiment must not silently retain RAM or lose a storage bit."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from check_neo_fifo_synthesis import audit


def fixture():
    text='module ahb_ddr_cdc ();\n  request_fifo u_requests ();\n  reply_fifo u_responses ();\nendmodule\n'
    for module, width in (('request_fifo', 100), ('reply_fifo', 64)):
        text+='module '+module+' ();\n'
        for slot in range(4):
            for bit in range(width):
                text+=f'  DFFRE \\g_register_storage.g_slot[{slot}].value_{bit}_s0 ();\n'
        text+='endmodule\n'
    return text


class MappingAudit(unittest.TestCase):
    def inspect(self, text):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test.vg';p.write_text(text)
            return audit(p)

    def test_complete_stores(self):
        self.assertTrue(self.inspect(fixture())['passed'])

    def test_missing_bit_or_hidden_ram_is_rejected(self):
        good=fixture()
        bad=good.replace('DFFRE \\g_register_storage.g_slot[2].value_63_s0 ();', '')
        self.assertFalse(self.inspect(bad)['passed'])
        bad=good.replace('module reply_fifo ();', 'module reply_fifo ();\n  RAM16SDP4 hidden ();')
        self.assertFalse(self.inspect(bad)['passed'])

    def test_unconnected_store_or_nested_memory_is_rejected(self):
        good=fixture()
        self.assertFalse(self.inspect(good.replace('reply_fifo u_responses', 'other_fifo u_responses'))['passed'])
        bad=good.replace('module reply_fifo ();', 'module reply_fifo ();\n  nested hidden ();')
        bad+='module nested ();\n  SDPX9B memory ();\nendmodule\n'
        self.assertFalse(self.inspect(bad)['passed'])


if __name__=='__main__': unittest.main()
