"""Injected lane1 validity fault versus baseline on exact routed graph."""
import hashlib,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;BASE=HERE/'routed_v2';OUT=HERE/'masked_activity'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
OUT.mkdir(exist_ok=False)
tb=(BASE/'tb_routed.sv').read_text()
tb=tb.replace("words[1]!==1 || words[2]!==value", "words[1]!==($test$plusargs(\"masked\")?0:1) || words[2]!==value")
needle='  $display("NETLIST_HEADER command='
offset=tb.index(needle)
tb=tb[:offset]+'  for(integer j=0;j<32;j=j+1)$display("BANK_WORD %0d %0d %08x",seq,j,words[j]);\n'+tb[offset:]
tb=tb.replace('  repeat(2000)@(negedge clk);', '  @(negedge clk);sof=1;@(negedge clk);sof=0;\n  repeat(2000)@(negedge clk);')
tb=tb.replace('endmodule'," initial begin #1;if($test$plusargs(\"masked\"))force dut.\\u_usb_idle_trace/bank_ER_RS_87 =1'b0;end\nendmodule")
(OUT/'tb.sv').write_text(tb)
vendor=Path('/home/michael/gowin/Gowin_V1.9.12_linux/IDE/simlib/gw5a/prim_sim.v')
r=subprocess.run(['/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog','-B','/tmp/console-usb-sim-tools/extracted/usr/lib/x86_64-linux-gnu/ivl','-g2012','-s','usb_idle_trace_protocol_tb','-o',str(OUT/'test.vvp'),str(OUT/'tb.sv'),str(BASE/'routed_cut.v'),str(vendor)],capture_output=True,text=True,timeout=30)
(OUT/'compile.log').write_text(r.stdout+r.stderr);assert r.returncode==0 and not r.stderr,r.stderr
cases=[]
for mode in ('baseline','masked'):
 r=subprocess.run(['/tmp/console-usb-sim-tools/extracted/usr/bin/vvp',str(OUT/'test.vvp')]+(['+masked'] if mode=='masked' else []),capture_output=True,text=True,timeout=20)
 (OUT/(mode+'.log')).write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
 words=[dict(sequence=int(s),word=int(i),value=int(v,16)) for s,i,v in re.findall(r'^BANK_WORD (\d+) (\d+) (\S+)$',r.stdout,re.M)]
 assert len(words)==128
 cases.append(dict(mode=mode,passed=True,words=words))
diff=[]
for a,b in zip(cases[0]['words'],cases[1]['words']):
 assert (a['sequence'],a['word'])==(b['sequence'],b['word'])
 if a['value']!=b['value']:diff.append(dict(sequence=a['sequence'],word=a['word'],baseline=a['value'],masked=b['value']))
assert diff==[dict(sequence=i,word=1,baseline=1,masked=0) for i in range(1,5)],diff
for case in cases:
 values={(w['sequence'],w['word']):w['value'] for w in case['words']}
 assert [values[i,16] for i in range(1,5)]==[0,1,1,1]
result=dict(passed=True,hardware_access=False,SDF_annotation=False,deliberately_injected_fault=True,cases=cases,differences=diff,
            input_sha256={str(p):sha(p) for p in [Path(__file__),OUT/'tb.sv',BASE/'routed_cut.v',vendor]},
            limits=['Counterexample showing the observed categories are compatible with a lane1 validity fault. It does not identify the physical fault.',
                    'Simulated ticks use bench timing and are not the recorded hardware tick values.','No timing qualification or hardware intervention.'])
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(passed=True,differences=diff,hardware_access=False)))
