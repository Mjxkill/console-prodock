"""Evidence/identity boundaries of the local project dashboard; no hardware."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

try:
    from . import collector as c
except ImportError:
    import collector as c


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root/'tools/project_dashboard').mkdir(parents=True)
        (self.root/'TESTS').mkdir()

    def write(self,name,value):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value));return path

    def spec(self,**extra):
        return dict(level='simulation',status='PASS',detail='Exemple local',evidence='TESTS/proof.json',
                    conditions=[dict(field='passed',equals=True)],**extra)

    def registry(self,tests=None,state='HOST_VALIDATED'):
        test=self.spec()
        data=dict(topics=[dict(id='example',title='Exemple',status='PARTIAL',summary='Contexte',
            loaded='Une référence historique',loaded_check=test,done=[test],next=['Mesurer carte'],
            features=[dict(name='Simulation',state=state,tests=[test] if tests is None else tests)])],builds=[],events=[])
        self.write('tools/project_dashboard/data.json',data)
        return data

    def test_missing_evidence_never_passes(self):
        self.registry()
        with patch.object(c,'_workers',return_value=[]):out=c.collect(self.root)
        topic=out['topics'][0]
        self.assertEqual(topic['status'],'UNKNOWN')
        self.assertEqual(topic['features'][0]['state'],'UNKNOWN')
        self.assertEqual(topic['done'],[])
        self.assertTrue(topic['loaded'].startswith('INCONNU'))

    def test_matching_evidence_keeps_validation_level(self):
        self.registry();self.write('TESTS/proof.json',{'passed':True})
        with patch.object(c,'_workers',return_value=[]):out=c.collect(self.root)
        feature=out['topics'][0]['features'][0]
        self.assertEqual(feature['state'],'HOST_VALIDATED')
        self.assertEqual(feature['tests'][0]['level'],'simulation')
        self.assertEqual(feature['tests'][0]['status'],'PASS')
        json.dumps(out)

    def test_malformed_or_wrong_type_is_unknown(self):
        for value in ({'passed':1},{'passed':False},{'another':True},[],None):
            self.write('TESTS/proof.json',value)
            self.assertEqual(c._check(self.root,self.spec())['status'],'UNKNOWN')
        (self.root/'TESTS/proof.json').write_text('{broken')
        self.assertEqual(c._check(self.root,self.spec())['status'],'UNKNOWN')

    def test_file_presence_alone_cannot_be_pass(self):
        self.write('TESTS/proof.json',{'passed':True})
        spec=self.spec();spec['conditions']=[]
        self.assertEqual(c._check(self.root,spec)['status'],'UNKNOWN')

    def test_size_symlink_escape_secrets_refused(self):
        (self.root/'TESTS/big.json').write_bytes(b' '*(c.MAX_BYTES+1))
        (self.root/'TESTS/link.json').symlink_to('/etc/passwd')
        for name in ('/etc/passwd','TESTS/../../etc/passwd','TESTS/secrets.json',
                     'TESTS/.private/proof.json','TESTS/big.json','TESTS/link.json','TESTS/raw.log'):
            with self.subTest(name=name):self.assertIsNotNone(c.evidence(self.root,name)[1])

    def test_explicit_benchmark_reports_only(self):
        path=self.root/'TESTS/benchmark_candidate.log';path.write_text('LUMA fps=6.73')
        self.assertIsNone(c.evidence(self.root,'TESTS/benchmark_candidate.log')[1])
        self.assertIsNotNone(c.evidence(self.root,'TESTS/another.log')[1])

    def test_architecture_and_exact_game_docs_only(self):
        for name in ('ARCHI/GPU.md','games/luma3d/README.md',
                     'games/luma3d/CONTENT_STATUS.md','games/luma3d/DESIGN.md'):
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('Document public')
            self.assertIsNone(c.evidence(self.root,name)[1])
        for name in ('games/luma3d/PRIVATE.md','games/luma3d/src/main.c',
                     'ARCHI/secret.md','ARCHI/.private.json','ARCHI/other.log'):
            self.assertIsNotNone(c.evidence(self.root,name)[1])

    def test_worker_label_does_not_change_identity_or_liveness(self):
        row=dict(model='beam',task='village_01',state='STOPPED',elapsed_s=4)
        labels={'village_01':dict(title='Décor 3D',detail='Végétation',state='RUNNING',task='other')}
        labelled=c._label_workers([row],labels)[0]
        self.assertEqual(labelled['title'],'Décor 3D')
        for field in row:self.assertEqual(labelled[field],row[field])
        self.assertNotIn('title',row)
        self.assertEqual(c._label_workers([row],{'village_01':'bad'}),[row])
        self.assertEqual(c._label_workers([row],{'village_01':{'title':'x'*301}}),[row])

    def test_collect_worker_labels_from_explicit_registry(self):
        data=self.registry()
        data['worker_labels']={'task_01':{'title':'Lisible','detail':'Sans prompt'}}
        self.write('tools/project_dashboard/data.json',data)
        row=dict(task='task_01',model='beam',state='FAILED')
        with patch.object(c,'_workers',return_value=[row]):out=c.collect(self.root)
        self.assertEqual(out['workers'][0]['title'],'Lisible')
        self.assertEqual(out['workers'][0]['state'],'FAILED')

    def test_planned_without_tests_remains_planned(self):
        for state in ('TODO','PLANNED','PENDING'):
            self.registry(tests=[],state=state)
            with patch.object(c,'_workers',return_value=[]):out=c.collect(self.root)
            feature=out['topics'][0]['features'][0]
            self.assertEqual(feature['state'],state)
            self.assertEqual(feature['tests'][0]['status'],'NOT_TESTED')
        self.registry(tests=[],state='PASS')
        with patch.object(c,'_workers',return_value=[]):out=c.collect(self.root)
        self.assertEqual(out['topics'][0]['features'][0]['state'],'UNKNOWN')

    def test_process_disappeared_and_pid_identity_unknown(self):
        self.write('TESTS/started.json',{'pid':123,'start_ticks':42})
        spec=dict(name='Router',started='TESTS/started.json',result='TESTS/final.json')
        module=types.ModuleType('workers')
        key=(c.__package__+'.workers') if c.__package__ else 'workers'
        for live,expected in (('ABSENT','STOPPED_NO_RESULT'),('REUSED','STOPPED_NO_RESULT'),
                              ('UNKNOWN','UNKNOWN'),('RUNNING','RUNNING')):
            module.process_state=lambda pid,tick,state=live:dict(state=state)
            with patch.dict(sys.modules,{key:module}):out=c._build(self.root,spec)
            self.assertEqual(out['state'],expected)

    def test_route_success_is_not_timing_or_hardware_pass(self):
        self.write('TESTS/final.json',{'returncode':0})
        spec=dict(name='Router',result='TESTS/final.json',qualification='TESTS/timing.json')
        self.assertEqual(c._build(self.root,spec)['state'],'ROUTED')
        self.write('TESTS/timing.json',{'passed':False,'rom_passed':True})
        self.assertEqual(c._build(self.root,spec)['state'],'FAIL')

    def test_hash_change_and_false_status_are_not_relabelled(self):
        self.write('TESTS/proof.json',{'passed':False})
        spec=self.spec();spec['conditions'][0]['equals']=False;spec['status']='FAIL'
        self.assertEqual(c._check(self.root,spec)['status'],'FAIL')
        spec['sha256']='0'*64
        self.assertEqual(c._check(self.root,spec)['status'],'UNKNOWN')


if __name__=='__main__':unittest.main(verbosity=2)
