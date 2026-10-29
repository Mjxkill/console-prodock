#!/usr/bin/env python3
"""Read-only setup/hold query coverage; never infers pass from missing paths."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import re
import prepare_reports as p
import audit_reports as routed

COMMAND=re.compile(r'^Report Command:(.*?)\s*$',re.M)
TARGET=re.compile(r'^report_timing -(setup|hold) -to \[get_pins \{([^{}\s]+)\}\] -max_paths (\d+) -max_common_paths (\d+)$')

def sections(text):
 starts=list(COMMAND.finditer(text))
 for i,m in enumerate(starts):yield m[1].strip(),text[m.end():starts[i+1].start() if i+1<len(starts) else len(text)]

def paths(body):
 result=[]
 for part in body.split('Path Summary:')[1:]:
  def field(name):
   m=re.search(r'^'+re.escape(name)+r'\s*:\s*(.*?)\s*$',part,re.M);return m[1] if m else None
  slack=field('Slack');source=field('From');dest=field('To')
  arrival=re.search(r'Data Arrival Path:\n(.*?)(?=\nData Required Path:)',part,re.S)
  rows=[] if arrival is None else [line.split() for line in arrival[1].splitlines() if re.match(r'\s*-?\d+\.\d+\s+',line)]
  pin=rows[-1][-1] if rows else None
  valid=bool(slack is not None and re.fullmatch(r'-?\d+(?:\.\d+)?',slack) and source and dest and pin)
  result.append(dict(valid=valid,slack_ns=float(slack) if valid else None,source=source,destination=dest,endpoint_pin=pin,
   launch_clock=field('Launch Clk'),latch_clock=field('Latch Clk')))
 return result

def analyze(text,endpoints,cells):
 expected={(mode,endpoint) for endpoint in endpoints for mode in ('setup','hold')}
 queries=defaultdict(list);globals=[];bad=[]
 for command,body in sections(text):
  if not command.startswith('report_timing '):continue
  m=TARGET.fullmatch(command);rows=paths(body)
  if m:
   mode,endpoint,cap,common=m.groups();key=(mode,endpoint)
   if key not in expected:bad.append(dict(reason='unexpected target report',command=command))
   queries[key].append(dict(command=command,rows=rows,cap=int(cap),common=int(common),empty_message='No timing paths to report!' in body))
  else:
   mode=re.search(r'^report_timing -(setup|hold|recovery|removal)(?: |$)',command)
   if mode:globals.append(dict(analysis=mode[1],command=command,reported_paths=len(rows),invalid_rows=sum(not row['valid'] for row in rows),
    minimum_slack_ns=min((row['slack_ns'] for row in rows if row['valid']),default=None)))
 drivers=routed.original.drivers(cells);coverage=[]
 states=defaultdict(list)
 for state,cmd in re.findall(r'^\s*TC_REPORT_TIMING\s+(\S+)\s+(report_timing [^\n]+?)\s*$',text,re.M):states[cmd].append(state)
 for mode,endpoint in sorted(expected):
  cell,pin=endpoint.rsplit('/',1);exists=cell in cells and pin in cells[cell][1]
  const=None
  if exists:
   origins=drivers.get(cells[cell][1][pin],set())
   if len(origins)==1 and next(iter(origins))[0]=='CONST':const=next(iter(origins))[1]
  found=queries.get((mode,endpoint),[]);row=dict(analysis=mode,endpoint=endpoint,cell_pin_exists=exists,constant_driver=const,query_count=len(found),status='UNPROVEN')
  if not exists:row['reason']='routed endpoint absent'
  elif len(found)!=1:row['reason']='missing or duplicated exact report command'
  else:
   q=found[0];items=q['rows'];row.update(reported_paths=len(items),minimum_slack_ns=min((r['slack_ns'] for r in items if r['valid']),default=None))
   active=states.get(q['command'],[])
   row['constraint_report_state']=active
   if active!=['Actived']:row['reason']='query not uniquely active in constraints report'
   elif not all(r['valid'] and r['destination']==cell and r['endpoint_pin']==endpoint for r in items):row['reason']='malformed path or wrong endpoint'
   elif len(items)>=q['cap']:row['reason']='report reached max_paths cap'
   elif not items:
    if const is not None and q['empty_message']:row.update(status='CONSTANT_NO_TIMING_PATH',reason='direct constant driver; no dynamic timing claim')
    else:row['reason']='no reported path without proven direct constant'
   elif const is not None:row['reason']='reported dynamic path contradicts direct constant classification'
   else:row.update(status='NEGATIVE_SLACK' if row['minimum_slack_ns']<0 else 'REPORTED_NONNEGATIVE',reason='reported worst endpoint paths; broader STA remains separate')
  coverage.append(row)
 summary={name:int(value) for name,value in re.findall(r'^<([^>]+)>:(\d+)\s*$',text,re.M) if name.startswith('Numbers of')}
 counts=Counter(row['status'] for row in coverage)
 return dict(query_errors=bad,coverage=coverage,status_counts=dict(counts),global_reports=globals,global_summary=summary,
  all_targets_resolved=counts.get('UNPROVEN',0)==0 and not bad,
  target_report_slacks_nonnegative=counts.get('UNPROVEN',0)==0 and counts.get('NEGATIVE_SLACK',0)==0 and not bad,
  hardware_qualified=False,qualification='NOT_QUALIFIED',
  limitation='Report coverage is conditional on STA constraints/models; constants have no dynamic-path claim. Global STA and functional hardware remain independent.')

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
 p.check();route=json.loads((p.OUT/'route_result.json').read_text());p.require(route['status']=='ROUTED_NOT_QUALIFIED','route incomplete or failed')
 pn=p.OUT/'impl/pnr';inputs=[pn/'console_neo.tr',pn/'console_neo.vo',p.OUT/'timing_report_requests.json',p.OUT/'route_result.json',Path(__file__)]
 hashes={str(x):p.sha(x) for x in inputs}
 requested=json.loads((p.OUT/'timing_report_requests.json').read_text())['endpoint_names']
 cells,_=routed.original.cells((pn/'console_neo.vo').read_text())
 report=analyze((pn/'console_neo.tr').read_text(),requested,cells)
 p.require(all(p.sha(Path(x))==v for x,v in hashes.items()),'inputs changed during timing audit')
 report.update(inputs=hashes,hardware_access=False)
 args.out.mkdir(exist_ok=False);p.save(args.out/'result.json',report)
 print(json.dumps({k:v for k,v in report.items() if k not in ('coverage','inputs')}))
 if not report['all_targets_resolved'] or not report['target_report_slacks_nonnegative']:raise SystemExit(1)
if __name__=='__main__':main()
