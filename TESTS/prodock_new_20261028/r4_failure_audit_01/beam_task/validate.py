import pathlib,json,sys,hashlib,importlib.util
r=pathlib.Path(__file__).resolve().parent
for n,h in json.loads((r/'PROTECTED.json').read_text()).items(): assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
s=importlib.util.spec_from_file_location('owned_analysis',r/'owned/analyse.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
f=json.loads((r/'context/facts.json').read_text());a=m.analyse(f)
want=dict(r4_returncode=1,r2_returncode=-11,r3_returncode=0,r4_has_bitstream=False,r4_has_postroute_vo=False,r3_r4_same_sdc=True,r4_report_queries=0,r2_r3_same_vg=True,r3_r4_same_vg=False,r3_r4_same_incremental_anchor=False,root_cause_proven=False)
for k,v in want.items(): assert a[k]==v,(k,a[k],v)
assert len((r/'owned/REPORT.md').read_text())>500,'Missing reasoned report'
assert all(len((r/'owned'/n).read_text().splitlines())<=1000 for n in ('analyse.py','REPORT.md'))
print('PASS 11 factual checks; protected inputs unchanged; report still requires independent review')
