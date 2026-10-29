import pathlib,json,hashlib,importlib.util
r=pathlib.Path(__file__).resolve().parent
for n,h in json.loads((r/'PROTECTED.json').read_text()).items():assert hashlib.sha256((r/n).read_bytes()).hexdigest()==h,n
s=importlib.util.spec_from_file_location('inspect_cdc',r/'owned/inspect_cdc.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
v=m.inspect(r/'context')
want=dict(hs_two_stage=True,gray_two_stage=True,gather_raw_async_reset=True,gather_clock='vid_hclk',reset_source_clock='phy_clk',raw_clear_lut_init='B',raw_clear_truth_table=[1,1,0,1],msc_local_release_guard=True,timing_closed=False)
for k,x in want.items():assert v[k]==x,(k,v[k],x)
assert len((r/'owned/REPORT.md').read_text())>600,'Reasoned report required'
assert len((r/'owned/inspect_cdc.py').read_text().splitlines())<=1000
print('PASS 9 grounded source/netlist checks; manual interpretation still required')
