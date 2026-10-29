from pathlib import Path
import importlib.util,json,tempfile,shutil
p=Path(__file__).resolve().parent.parent/'deepseek_execution/isolation/tree'
s=importlib.util.spec_from_file_location('a',p/'owned/analyze.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
r=m.analyze(p/'context')
assert r['pullup_equivalent'] is True,r
assert r['clkdiv_reset_equivalent'] is True,r
assert r['alu_i3_mode01_equivalent'] is True,r
assert r['critical_parameter_changes']==[],r
for marker,expected in [('n19_6_s','pullup_equivalent'),('n24_6_0_s0','clkdiv_reset_equivalent')]:
 with tempfile.TemporaryDirectory() as d:
  q=Path(d)/'context';shutil.copytree(p/'context',q)
  f=q/'changed_cones.json';x=json.loads(f.read_text());names=[n for n in x['r5'] if n.endswith('/'+marker)];assert len(names)==1
  cell=x['r5'][names[0]];old=cell['params']['INIT'];cell['params']['INIT']="4'hE" if marker=='n19_6_s' else "2'h2";f.chmod(0o600);f.write_text(json.dumps(x))
  changed=m.analyze(q);assert changed[expected] is False,(marker,changed)
with tempfile.TemporaryDirectory() as d:
 q=Path(d)/'context';shutil.copytree(p/'context',q);f=q/'critical_cells.json';x=json.loads(f.read_text());key='\\u_pll_f/PLL_inst';x['r5'][key]['params']['ODIV0_SEL']='24';f.chmod(0o600);f.write_text(json.dumps(x));assert m.analyze(q)['critical_parameter_changes']
assert len((p/'owned/REPORT.md').read_text())>600
assert len((p/'owned/analyze.py').read_text().splitlines())<=1000
print('PASS baseline exact graph + two LUT inversion counterexamples + PLL param mutation; report still needs independent review')
