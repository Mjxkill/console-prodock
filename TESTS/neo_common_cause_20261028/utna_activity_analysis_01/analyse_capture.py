"""Verify real activity evidence and map nonzero words to physical bank classes."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
CAPTURE=ROOT/'TESTS/neo_common_cause_20261027/utna_activity_prepared_01/activity_20261028_000942/result.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads(CAPTURE.read_text())
assert sha(CAPTURE)=='1c39884c0dab5fca3a1217eef887cbd1ac7e8fca21f250174070ce85bfdf342d'
for name,digest in d['files'].items():assert sha(CAPTURE.parent/name)==digest,name
assert d['left_startup_verified'] and d['last_programmed_sha256']=='1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c'
blocks=d['observation']['blocks'];assert len(blocks)==8
rows=[]
for i in range(0,8,2):
 first,repeat=blocks[i:i+2];assert first['words']==repeat['words']
 assert first['words'][0]==0x55544e41 and first['words'][1]==0 and first['words'][2]==first['command']
 rows.append(dict(phase=first['phase'],sequence=first['sequence'],command=first['command'],ticks=first['words'][3],armed=bool(first['words'][31]&0x400),nonzero=[dict(word=j,address=hex(0xe9002040+4*j),value=v,value_hex=hex(v),lane=j%4,validity_row=j//4,data_half=j//16) for j,v in enumerate(first['words']) if v]))
words=sorted(set(x['word'] for row in rows for x in row['nonzero']))
assert words==[0,2,3,16,31]
assert d['observation']['activity']==dict(arm_ticks=0,disarm_ticks=26061045,stopped_ticks=26061046,stable_ticks=26061046,armed=[False,True,False,False])
result=dict(hardware_access=False,capture_sha256=sha(CAPTURE),capture_files_verified=True,restored_R19=True,phases=rows,
            observed_nonzero_words=words,observed_nonzero_lanes=sorted(set(i%4 for i in words)),observed_nonzero_validity_rows=sorted(set(i//4 for i in words)),
            lane1_words=[dict(word=i,address=hex(0xe9002040+4*i),all_captures_zero=all(b['words'][i]==0 for b in blocks)) for i in range(1,32,4)],
            unknowns=['No independent nonzero stimulus in lane1 words5/9/13/17/21/25/29.','Values are data observations, not direct internal-node measurements or frequency/USB-speed qualification.'])
(HERE/'capture_analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(verified=True,nonzero_words=words,nonzero_lanes=result['observed_nonzero_lanes'],hardware_access=False)))
