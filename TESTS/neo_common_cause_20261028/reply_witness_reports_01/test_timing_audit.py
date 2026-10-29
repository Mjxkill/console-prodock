#!/usr/bin/env python3
"""Synthetic report parser counterexamples, no STA or hardware claims."""
import json
from pathlib import Path
import audit_timing as a

def make(slack='0.125',pin='D',active=True,empty=False):
 command='report_timing -setup -to [get_pins {x/D}] -max_paths 10000 -max_common_paths 3'
 body='No timing paths to report!\n' if empty else '''Path Summary:
Slack : SLACK
From : source
To : x
Launch Clk : clk:[R]
Latch Clk : clk:[R]
Data Arrival Path:
 0.1 0.1 tNET RR 1 LOC x/PIN
Data Required Path:
 0.1 0.1 tNET RR 1 LOC x/CLK
'''.replace('SLACK',slack).replace('PIN',pin)
 return 'Report Command:'+command+'\n'+body+'\nTC_REPORT_TIMING '+('Actived' if active else 'Inactive')+' '+command+'\n'

def main():
 cases=[];cells={'x':('DFFRE',{'D':'net'}),'source':('DFFRE',{'Q':'net'})}
 def check(name,text,expected,c=cells):
  r=a.analyze(text,['x/D'],c);row=next(x for x in r['coverage'] if x['analysis']=='setup')
  if row['status']!=expected:raise AssertionError((name,row))
  cases.append(dict(name=name,passed=True))
 check('positive endpoint reported',make(),'REPORTED_NONNEGATIVE')
 check('negative slack preserved',make('-0.2'),'NEGATIVE_SLACK')
 check('wrong actual pin rejected',make(pin='CE'),'UNPROVEN')
 check('inactive query rejected',make(active=False),'UNPROVEN')
 check('empty dynamic endpoint unproven',make(empty=True),'UNPROVEN')
 check('empty direct constant explicit',make(empty=True),'CONSTANT_NO_TIMING_PATH',{'x':('DFFRE',{'D':'net'}),'one':('VCC',{'V':'net'})})
 check('missing exact query unproven','No timing paths to report!','UNPROVEN')
 check('duplicate query rejected',make()+make(),'UNPROVEN')
 check('missing endpoint rejected',make(),'UNPROVEN',{})
 check('malformed slack rejected',make('nan'),'UNPROVEN')
 check('capped report rejected',make().replace('-max_paths 10000','-max_paths 1'),'UNPROVEN')
 check('constant with dynamic path contradictory',make(),'UNPROVEN',{'x':('DFFRE',{'D':'net'}),'one':('VCC',{'V':'net'})})
 r=a.analyze(make(),['x/D'],cells)
 if r['all_targets_resolved'] or r['target_report_slacks_nonnegative']:raise AssertionError('missing hold coverage passed')
 cases.append(dict(name='positive setup cannot replace missing hold',passed=True))
 p=Path(__file__).resolve();out=p.parent/'timing_audit_tests.json'
 out.write_text(json.dumps(dict(passed=True,synthetic_only=True,cases=cases,inputs={str(x):a.p.sha(x) for x in [p,Path(a.__file__)]}),indent=2)+'\n')
 print(json.dumps(dict(passed=True,cases=len(cases))))
if __name__=='__main__':main()
