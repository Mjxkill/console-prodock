"""Reset recovery failures must not be classified as setup-only diagnostics."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from neo.timing import timing_checks


class TimingTests(unittest.TestCase):
    def test_real_tables_not_table_of_contents(self):
        text='\t3.1.1 Setup Paths Table\n\t3.1.2 Hold Paths Table\n'
        for i,(label,slack) in enumerate(zip(('Setup','Hold','Recovery','Removal'),(-.1,.2,-6.51,.3)),1):
            text+=f'3.1.{i} {label} Paths Table\n Path Slack\n 1 {slack:.3f} from to\n 2 9.000 from to\n'
        text+='3.2 Summary\n'
        self.assertEqual(timing_checks(text),dict(setup=-.1,hold=.2,recovery=-6.51,removal=.3))
        with self.assertRaises(ValueError):timing_checks(text.replace('Recovery Paths Table','Missing'))


if __name__=='__main__':unittest.main()
