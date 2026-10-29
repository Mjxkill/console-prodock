#!/usr/bin/env python3
"""Synthesize isolated reset helper only. No routing or hardware commands."""
from pathlib import Path
import sys,json,hashlib,subprocess,xml.etree.ElementTree as ET,argparse
HERE=Path(__file__).resolve().parent
ROOT=Path('/home/michael/console')
sys.path.insert(0,str(ROOT/'tools'))
from board_contract import before_build,record_build
from gowin_toolchain import environment
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
contract=before_build('neo',candidate=True)
ap=argparse.ArgumentParser();ap.add_argument('--out-name',default='synthesis_01');args=ap.parse_args()
assert args.out_name.isidentifier()
out=HERE/args.out_name
out.mkdir(exist_ok=False)
record_build(out,contract)
p=ET.Element('Project');ET.SubElement(p,'Version').text='beta'
ET.SubElement(p,'Device',id='GW5AST-138C',package='PBGA484A',speed='1',partNumber='GW5AST-LV138PG484AC1/I0')
files=ET.SubElement(p,'FileList')
inputs=[HERE/'neo_reset_trial.v',HERE/'neo_reset_trial_rx.v']
for f in inputs:ET.SubElement(files,'File',path=str(f),type='verilog')
opts=ET.SubElement(p,'OptionList')
for k,v in [('disable_insert_pad','1'),('enable_dsrm','0'),('output_file','neo_reset_trial.vg'),('top_module','neo_reset_trial'),('vcc','0.9'),('vccx','1.8'),('verilog_language','sysv-2017')]:ET.SubElement(opts,'Option',type=k,value=v)
ET.indent(p);ET.ElementTree(p).write(out/'trial.prj',encoding='utf-8',xml_declaration=True)
binary=ROOT/'tang/impl/console_neo_n56r15_reset50ms/public_license_runtime/bin/GowinSynthesis'
assert sha(binary)==sha(Path('/home/michael/gowin/IDE/bin/GowinSynthesis'))
r=dict(passed=False,scope='isolated helper synthesis only; no PnR, no hardware',inputs={str(f):sha(f) for f in inputs},tool_sha256=sha(binary),project_sha256=sha(out/'trial.prj'))
try:
 with (out/'synthesis.log').open('x') as log: c=subprocess.run([str(binary),'-prj',str(out/'trial.prj')],cwd=out,env=environment(),stdout=log,stderr=log,timeout=180)
 r['returncode']=c.returncode
 text=(out/'synthesis.log').read_text();assert c.returncode==0 and 'GowinSynthesis finish' in text
 vg=out/'neo_reset_trial.vg';assert vg.is_file()
 r.update(passed=True,netlist_sha256=sha(vg),log_sha256=sha(out/'synthesis.log'))
finally:
 r['script_sha256']=sha(Path(__file__));(out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
