#!/usr/bin/env python3
"""Executable local tests: real SQLite processes, hashes and adversarial inputs."""
import csv
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import metrics as m


def concurrent_import(db, document, queue):
    try:
        queue.put(('ok', m.import_run(db, document)))
    except Exception as exc:
        queue.put(('error', type(exc).__name__ + ': ' + str(exc)))


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root/'registry.sqlite3'
        self.index = 0

    def tearDown(self):
        self.tmp.cleanup()

    def document(self, data, prefix='doc'):
        self.index += 1
        path = self.root/f'{prefix}_{self.index}.json'
        path.write_text(json.dumps(data, ensure_ascii=False))
        return path

    def run_data(self, run_id='run1', **changes):
        folder=self.root/run_id;folder.mkdir(exist_ok=True)
        output=folder/'answer.txt';output.write_text('A synthetic answer for '+run_id)
        data=dict(schema=1,event='finished',run_id=run_id,task_id='task1',project=str(self.root),
            provider='ollama-cloud',model='beam',domain='rtl',task_type='review',difficulty='medium',
            dataset=None,task_family=None,model_config={'version':'1','reasoning_effort':'low'},
            status=m.SUCCESS,truncated=False,queued_at=None,started_at=None,finished_at=None,
            elapsed_seconds=2,queue_delay_seconds=None,tokens={'input':None,'output':None},
            output_path=str(output),output_sha256=m.sha256(output),automatic_quality_score=None)
        data.update(changes)
        return data

    def import_one(self, run_id='run1', **changes):
        data=self.run_data(run_id,**changes);path=self.document(data)
        self.assertEqual(m.import_run(self.db,path),'imported')
        return data,path

    def evaluation(self, run, evaluation_id='eval1', **changes):
        evidence=self.root/(evaluation_id+'.txt');evidence.write_text('Independent test evidence: all assertions passed.')
        data=dict(evaluation_id=evaluation_id,run_id=run['run_id'],evaluator_type='human',evaluator_id='reviewer_alice',
            evaluator_model=None,rubric_version='1',verdict='accepted',tests='pass',justification='Synthetic acceptance criteria verified against the evidence.',
            scores={'correctness':5,'relevance':4,'completeness':3,'actionability':2},
            review_seconds=None,rework_seconds=None,evidence_path=str(evidence),
            evidence_sha256=m.sha256(evidence),output_sha256=run['output_sha256'])
        data.update(changes)
        return data

    def eval_one(self, run, evaluation_id='eval1', **changes):
        data=self.evaluation(run,evaluation_id,**changes);path=self.document(data)
        result=m.add_evaluation(self.db,path)
        self.assertIsInstance(result,int)
        return data,path,result

    def test_duplicate_and_conflict_exact_bytes(self):
        run,path=self.import_one()
        self.assertEqual(m.import_run(self.db,path),'duplicate')
        copy=self.root/'identical.json';copy.write_bytes(path.read_bytes())
        self.assertEqual(m.import_run(self.db,copy),'duplicate')
        path.write_text(json.dumps(run,indent=2))
        with self.assertRaisesRegex(ValueError,'conflict'):m.import_run(self.db,path)
        self.assertEqual(m.build_report(self.db)['n_runs'],1)

    def test_real_concurrent_imports(self):
        run=self.run_data();path=self.document(run)
        ctx=multiprocessing.get_context('spawn');queue=ctx.Queue()
        workers=[ctx.Process(target=concurrent_import,args=(str(self.db),str(path),queue)) for _ in range(8)]
        for worker in workers:worker.start()
        replies=[queue.get(timeout=40) for _ in workers]
        for worker in workers:
            worker.join(40);self.assertEqual(worker.exitcode,0)
        self.assertEqual(replies.count(('ok','imported')),1,replies)
        self.assertEqual(replies.count(('ok','duplicate')),7,replies)
        with sqlite3.connect(self.db) as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM runs').fetchone()[0],1)

    def test_concurrent_conflicting_runs(self):
        a=self.run_data();b=dict(a,elapsed_seconds=3)
        pa,pb=self.document(a),self.document(b)
        ctx=multiprocessing.get_context('spawn');queue=ctx.Queue()
        workers=[ctx.Process(target=concurrent_import,args=(str(self.db),str(p),queue)) for p in [pa,pb]]
        for worker in workers:worker.start()
        replies=[queue.get(timeout=40) for _ in workers]
        for worker in workers:worker.join(40);self.assertEqual(worker.exitcode,0)
        self.assertEqual(sum(r==('ok','imported') for r in replies),1,replies)
        self.assertEqual(sum(r[0]=='error' and 'conflict' in r[1] for r in replies),1,replies)

    def test_missing_measurements_remain_null(self):
        run,_=self.import_one(elapsed_seconds=None)
        report=m.build_report(self.db);c=report['cohorts'][0]
        self.assertEqual(c['n_unevaluated'],1)
        self.assertIsNone(c['model_seconds']['median'])
        self.assertEqual(c['model_seconds']['unknown'],1)
        self.assertIsNone(c['tokens_observed']['input']['total'])
        self.assertEqual(c['cost_observed'],[])
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('SELECT queued_at,started_at,finished_at,elapsed_seconds FROM runs').fetchone(),(None,None,None,None))
        self.eval_one(run,scores=None,verdict='inconclusive',tests='unknown')
        c=m.build_report(self.db)['cohorts'][0]
        self.assertEqual(c['n_evaluated'],0);self.assertEqual(c['n_assessed'],1)

    def test_history_weighted_scores_and_times(self):
        run,_=self.import_one()
        first,path,identity=self.eval_one(run,review_seconds=10,rework_seconds=0)
        self.assertEqual(m.add_evaluation(self.db,path),identity)
        self.eval_one(run,'eval2',scores={k:5 for k in m.WEIGHTS},verdict='edited',review_seconds=3,rework_seconds=20)
        report=m.build_report(self.db);cohort=report['cohorts'][0]
        self.assertEqual(report['n_evaluations_history'],2)
        self.assertEqual(cohort['evaluations_by_rubric'][0]['score']['median'],100)
        self.assertEqual(cohort['human_review_seconds']['total'],13)
        self.assertEqual(cohort['human_rework_seconds']['total'],20)
        self.assertEqual(m.weighted_score(first['scores']),78)
        self.assertFalse(cohort['evaluations_by_rubric'][0]['suggestion_eligible'])

    def test_self_evaluation_and_same_author_alias_refused(self):
        run,_=self.import_one()
        for changes in [dict(evaluator_type='model',evaluator_id='review-agent',evaluator_model='beam'),
                        dict(evaluator_type='model',evaluator_id='review-agent',evaluator_model='ollama-cloud/BEAM'),
                        dict(evaluator_id='beam')]:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):m.add_evaluation(self.db,self.document(self.evaluation(run,**changes)))
        self.eval_one(run,evaluator_type='model',evaluator_id='second-agent',evaluator_model='deepseek-v4.1-flash')

    def test_scores_bounds_and_missing(self):
        run,_=self.import_one()
        for invalid in [-1,5.01,True,float('nan'),float('inf'),'5',None]:
            scores={k:5 for k in m.WEIGHTS};scores['correctness']=invalid
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):m.add_evaluation(self.db,self.document(self.evaluation(run,scores=scores)))
        data=self.evaluation(run);del data['scores']
        with self.assertRaises(ValueError):m.add_evaluation(self.db,self.document(data))
        with self.assertRaises(ValueError):m.add_evaluation(self.db,self.document(self.evaluation(run,rubric_version='new')))
        with self.assertRaises(ValueError):m.add_evaluation(self.db,self.document(self.evaluation(run,justification='')))

    def test_failed_and_truncated_no_quality_score(self):
        for i,status in enumerate(['FAILED','TIMEOUT','INTERRUPTED','INCOMPLETE_LENGTH']):
            run,_=self.import_one('run'+str(i),status=status,truncated=status=='INCOMPLETE_LENGTH',elapsed_seconds=999)
            with self.assertRaises(ValueError):m.add_evaluation(self.db,self.document(self.evaluation(run,'e'+str(i))))
            self.eval_one(run,'e'+str(i),scores=None,verdict='inconclusive',tests='unknown')
        c=m.build_report(self.db)['cohorts'][0]
        self.assertEqual((c['n_failed'],c['n_truncated'],c['n_evaluated']),(3,1,0))
        self.assertIsNone(c['model_seconds']['median'])
        self.assertEqual(c['all_attempt_seconds']['median'],999)

    def test_output_and_evidence_hashes(self):
        run,_=self.import_one()
        data=self.evaluation(run);Path(data['evidence_path']).write_text('tampered')
        with self.assertRaisesRegex(ValueError,'Evidence'):m.add_evaluation(self.db,self.document(data))
        data=self.evaluation(run,output_sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'different output'):m.add_evaluation(self.db,self.document(data))
        data=self.evaluation(run);Path(run['output_path']).write_text('changed')
        with self.assertRaisesRegex(ValueError,'Output changed'):m.add_evaluation(self.db,self.document(data))
        with self.assertRaisesRegex(ValueError,'Output bytes'):m.import_run(self.db,self.document(run))

    def test_absent_failed_output_keeps_null_without_fake_hash(self):
        run,_=self.import_one(status='FAILED',output_sha256=None,tokens=None)
        self.eval_one(run,scores=None,verdict='inconclusive',tests='unknown')
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute('SELECT output_sha256,score FROM evaluations').fetchone(),(None,None))
        self.assertEqual(m.build_report(self.db)['cohorts'][0]['n_evaluated'],0)
        self.assertIsNone(m.build_report(self.db)['cohorts'][0]['tokens_observed']['input']['total'])

    def test_evaluation_id_conflict_preserves_history(self):
        run,_=self.import_one();evaluation,path,identity=self.eval_one(run)
        changed=dict(evaluation,tests='fail')
        with self.assertRaisesRegex(ValueError,'evaluation_id conflict'):m.add_evaluation(self.db,self.document(changed))
        self.assertEqual(m.build_report(self.db)['n_evaluations_history'],1)

    def test_timestamps_and_nonfinite_times_refused(self):
        for name in ['elapsed_seconds','queue_delay_seconds']:
            for value in [-1,float('inf'),float('nan'),True,'1']:
                with self.subTest(name=name,value=value):
                    with self.assertRaises(ValueError):m.import_run(self.db,self.document(self.run_data(**{name:value})))
        for changes in [dict(started_at='2026-10-28T12:00:00'),dict(started_at='yesterday'),
                        dict(started_at='2026-10-28T12:00:00Z',finished_at='2026-10-28T11:00:00Z')]:
            with self.assertRaises(ValueError):m.import_run(self.db,self.document(self.run_data(**changes)))
        run,_=self.import_one()
        for name in ['review_seconds','rework_seconds']:
            with self.assertRaises(ValueError):m.add_evaluation(self.db,self.document(self.evaluation(run,**{name:-.01})))

    def test_sql_and_export_injection(self):
        label="'); DROP TABLE runs; --<script>alert(1)</script>"
        run,_=self.import_one(task_id=label,domain=label,model='=HYPERLINK("evil")')
        self.eval_one(run)
        report=m.build_report(self.db)
        self.assertEqual(report['n_runs'],1)
        page=m.html_report(report)
        self.assertNotIn('<script>alert',page);self.assertIn('&lt;script&gt;',page)
        row=list(csv.DictReader(io.StringIO(m.csv_report(report))))[0]
        self.assertTrue(row['model'].startswith("'="))

    def test_threshold_and_cohort_configuration(self):
        for i in range(10):
            run,_=self.import_one('run'+str(i),task_id='t'+str(i%3),elapsed_seconds=i)
            self.eval_one(run,'e'+str(i),scores={k:5 for k in m.WEIGHTS})
            eligible=m.build_report(self.db)['cohorts'][0]['evaluations_by_rubric'][0]['suggestion_eligible']
            self.assertEqual(eligible,i==9)
        report=m.build_report(self.db)
        self.assertEqual(report['cohorts'][0]['model_seconds']['p90'],8)
        self.assertEqual(report['cohorts'][0]['model_seconds']['median'],4.5)
        self.assertEqual(report['cohorts'][0]['model_seconds']['mean'],4.5)
        self.import_one('different',model_config={'version':'2'})
        self.assertEqual(len(m.build_report(self.db)['cohorts']),2)
        with self.assertRaises(ValueError):m.build_report(self.db,9,3)
        with self.assertRaises(ValueError):m.build_report(self.db,10,2)

    def test_task_diversity_threshold(self):
        for i in range(10):
            run,_=self.import_one('run'+str(i),task_id='same-task')
            self.eval_one(run,'e'+str(i))
        self.assertFalse(m.build_report(self.db)['cohorts'][0]['evaluations_by_rubric'][0]['suggestion_eligible'])

    def test_observed_tokens_costs_and_unknowns(self):
        self.import_one(tokens={'input':123,'output':0},cost={'value':0,'currency':'USD','source':'provider event'},cost_observed=0,cost_source='opencode.step_finish.cost')
        self.import_one('missing')
        c=m.build_report(self.db)['cohorts'][0]
        self.assertEqual(c['tokens_observed']['input']['total'],123)
        self.assertEqual(c['tokens_observed']['input']['unknown'],1)
        self.assertEqual(c['cost_observed'][0]['total'],0)
        self.assertEqual(c['cost_unknown'],1)
        self.assertIsNone(c['cost_without_currency_observed'][0]['currency'])
        self.assertEqual(c['cost_without_currency_observed'][0]['total'],0)
        for value in [-1,1.3,True]:
            with self.assertRaises(ValueError):m.import_run(self.db,self.document(self.run_data('invalid',tokens={'input':value})))

    def test_symlink_and_duplicate_json_keys(self):
        run,path=self.import_one()
        link=self.root/'link.json';link.symlink_to(path)
        with self.assertRaises(ValueError):m.import_run(self.db,link)
        dbl=self.root/'double.json';dbl.write_text('{"schema":1,"schema":1}')
        with self.assertRaisesRegex(ValueError,'Duplicate'):m.import_run(self.db,dbl)
        db_link=self.root/'link.db';db_link.symlink_to(self.db)
        with self.assertRaises(ValueError):m.build_report(db_link)

    def test_cli_json_csv_html_and_no_clobber(self):
        run,path=self.import_one()
        for fmt in ['json','csv','html']:
            out=self.root/('report.'+fmt)
            cmd=[sys.executable,str(Path(m.__file__)),'--db',str(self.db),'report','--format',fmt,'--out',str(out)]
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=10);self.assertEqual(p.returncode,0,p.stderr)
            self.assertGreater(out.stat().st_size,20)
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=10);self.assertNotEqual(p.returncode,0)


if __name__=='__main__':
    unittest.main(verbosity=2)
