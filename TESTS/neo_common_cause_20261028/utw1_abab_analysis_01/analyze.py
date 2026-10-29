#!/usr/bin/env python3
"""Read-only comparison of completed R19/R22r1 acquisitions."""
from pathlib import Path
import hashlib,json,re
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(x,m):
 if not x:raise ValueError(m)
def load(path):
 p=ROOT/path;d=json.loads(p.read_text());need(d.get('finished_unix'),'capture unfinished')
 need(d['left_startup_verified'] and d['last_programmed_sha256']==d['r19_sha256'] and not d.get('restore_error'),'not restored')
 need(not d['signals_received'],'interrupted capture')
 for name,digest in d['files'].items():need(sha(p.parent/name)==digest,'log changed '+name)
 return p,d

def main():
 names=[('A1','R19','TESTS/neo_common_cause_20261027/utna_activity_prepared_01/activity_20261028_000942/result.json'),
 ('B1','R22r1','TESTS/neo_common_cause_20261028/utw1_collector_prepared_01/capture_20261028_124213/result.json'),
 ('A2','R19','TESTS/neo_common_cause_20261027/utna_activity_prepared_01/activity_20261028_124422/result.json'),
 ('B2','R22r1','TESTS/neo_common_cause_20261028/utw1_collector_prepared_01/capture_20261028_124454/result.json')]
 results=[];inputs={}
 for label,build,path in names:
  p,d=load(path);inputs[str(p)]=sha(p);obs=d['observation'];rows=[]
  if build=='R19':
   raw=(p.parent/'r19_activity.log').read_text();logged=re.findall(r'^ACTIVITY_BANK (\w+) (\d+) (\d+) (first|repeat) (.+)$',raw,re.M)
   need(len(logged)==8,'not eight R19 banks')
   for i,b in enumerate(obs['blocks']):need([int(x,0) for x in logged[i][4].split()]==b['words'],'stored R19 bank/log mismatch')
   need(len(obs['protocol_errors'])==8 and all(x.startswith('Version0: ') for x in obs['protocol_errors']),'R19 failure beyond observed version zero')
   for i in range(0,8,2):
    b=obs['blocks'][i];words=b['words'];need(words==obs['blocks'][i+1]['words'],'unstable R19 bank')
    rows.append(dict(phase=b['phase'],sequence=b['sequence'],bank_version=words[1],ticks=words[3],armed=bool(words[31]&1024),sof_cycles=words[16],repeated_bank_equal=True,raw_witness=None))
  else:
   need(not d.get('error') and obs['coherent'] and obs['protocol_passed'] and not obs['activity_errors'],'R22 capture error')
   raw=(p.parent/'candidate_utw1_capture.log').read_text();logged=re.findall(r'^UTW1_READ (\w+) (.+)$',raw,re.M);need(len(logged)==408,'not 408 R22 read records')
   at=0
   for c in obs['captures']:
    packet=c['packet'];images=packet['reads']
    for phase in ['before','image_a','image_b','after']:
     for row in images[phase]:
      clabel,line=logged[at];at+=1;q=json.loads(line);need(clabel==c['label'] and q['phase']==phase and int(q['address'],0)==row['address'] and int(q['value'],0)==row['value'],'stored R22 read/log mismatch')
    need(images['image_a']==images['image_b'],'unstable R22 images')
    values={r['address']-0xe9002000:r['value'] for r in images['image_a']};v=lambda offset:values[offset];n=packet['expected_sequence']
    need(v(0x44)==v(0xcc)==v(0xd4)==1,'version not one on R22')
    need([v(x) for x in [0xd8,0xdc,0xe0,0xe8]]==[n]*4 and v(0xe4)==n*32 and v(0xec)==0 and v(0xf0)==0x3f0007,'witness progression invalid')
    need([v(x) for x in [0xf4,0xf8,0xfc]]==[n-1]*3,'witness tags invalid')
    rows.append(dict(phase=c['label'],sequence=n,bank_version=v(0x44),ticks=v(0x4c),armed=bool(v(0xbc)&1024),sof_cycles=v(0x80),repeated_bank_equal=True,
     raw_witness=v(0xcc),raw_alias=v(0xd4),counts=[v(x) for x in [0xd8,0xdc,0xe0]],total=v(0xe4),frames=v(0xe8),outside_busy=v(0xec),flags=v(0xf0),tags=[v(x) for x in [0xf4,0xf8,0xfc]]))
  need([r['armed'] for r in rows]==[False,True,False,False],'wrong activity progression')
  need(rows[0]['ticks']==0 and rows[2]['ticks']==rows[1]['ticks']+1 and rows[3]['ticks']==rows[2]['ticks'],'ticks contract failed')
  results.append(dict(label=label,build=build,input=str(p),sha256=sha(p),rows=rows,restored_exact_R19=True,
    qualification_status=d['qualification_status'],error=d.get('error')))
 report=dict(passed=True,scope='Evidence integrity and comparison only',hardware_access=False,hardware_qualified=False,global_qualification='FAIL',results=results,
  conclusion='The constant version result follows the tested build across A/B/A/B: R19 returns zero, R22r1 returns one in the bank and witness. No captured disagreement between raw witness and bank.',
  changed_variables=['Added witness taps, load, 402 FF and combinational logic','Added 32 hrdata input muxes','Complete new placement/routing','R22 collector also reads extension words; read cadence differs from R19 activity collector'],
  not_established=['Root cause','FIFO fault versus bank validity/data fault','Silicon erratum','USB enumeration or negotiated speed','Physical clock frequencies','GPU functionality','DDR integrity'],
  first_failed_attempt=dict(path='TESTS/neo_common_cause_20261028/utw1_collector_prepared_01/capture_20261028_105428',reason='libusb_init() failed with LIBUSB_ERROR_OTHER before initial guard; no programming and no hardware observation; excluded from comparison'),
  inputs=inputs)
 (HERE/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,sha256=sha(HERE/'result.json'),build_versions=[[x['label'],[r['bank_version'] for r in x['rows']]] for x in results])))
if __name__=='__main__':main()
