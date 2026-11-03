"""Offline checks on the actual immutable parent, never invoke Gowin."""
import unittest
import recipe as r

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=(r.BASE/'console_neo.vg').read_text();cls.a=r.modules_api()
    def test_exact_allowed_delta(self):
        candidate,rows=r.replace_memories(self.base)
        old=self.a.modules(self.base);new=self.a.modules(candidate)
        self.assertEqual(set(k for k in old if old[k]!=new[k]),set(r.TARGETS))
        self.assertEqual(len(rows),2)
        self.assertEqual(sum(len(row['removed_defparams']) for row in rows),12)
        for module,instance in r.TARGETS.items():
            self.assertEqual(self.a.instances(new[module])[instance]['kind'],r.TOP)
    def test_changed_memory_parameter_rejected(self):
        changed=self.base.replace('defparam cmem_cmem_0_0_s.READ_MODE=1\'b0;',
                                  'defparam cmem_cmem_0_0_s.READ_MODE=1\'b1;',1)
        self.assertNotEqual(changed,self.base)
        with self.assertRaises(ValueError):r.replace_memories(changed)
    def test_target_missing_rejected(self):
        changed=self.base.replace('SDPB cmem_cmem_0_0_s (','SDPX9B cmem_cmem_0_0_s (',1)
        with self.assertRaises(ValueError):r.replace_memories(changed)

if __name__=='__main__':unittest.main()
