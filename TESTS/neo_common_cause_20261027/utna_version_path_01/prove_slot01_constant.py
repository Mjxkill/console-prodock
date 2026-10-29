"""Exhaustive LUT cofactor proof: ID bit0 and version bit0 share forced DI0=1."""
import itertools,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
cells=json.loads((HERE/'routed_cells.json').read_text())
checks=[]
for name,forced,want in [('n155_s66',{0:0,1:0},1),
                         ('n181_s53',{0:0,1:0,2:1,3:1},1),
                         ('n181_s43',{2:1},0),('n181_s36',{3:0},0),
                         ('n181_s34',{0:0},0),('n181_s33',{2:0},1)]:
 c=cells['u_usb_idle_trace/'+name];n=int(c['kind'][3:]);init=int(c['parameters']['INIT'].split("'h")[1],16)
 free=[i for i in range(n) if i not in forced];cases=[]
 for values in itertools.product((0,1),repeat=len(free)):
  pins=dict(forced);pins.update(zip(free,values));index=sum(v<<i for i,v in pins.items());got=(init>>index)&1
  assert got==want,(name,pins,got,want)
  cases.append(dict(inputs=pins,output=got))
 checks.append(dict(cell=name,vo_line=c['line'],INIT=c['parameters']['INIT'],ports=c['ports'],forced_pins=forced,required_output=want,cases=cases))
report=dict(passed=True,hardware_access=False,method='Exhaustive truth-table cofactors of actual routed LUT INIT',checks=checks,
 conclusion='For snapshot[32]=1 and send_index[4:1]=0, SDPB DI0 is forced to1 independently of send_index[0] and other mux inputs.',
 limits=['Proof of the compiled Boolean network, not a measurement of live internal nodes or FPGA configuration readback.',
         'Does not prove temporal correctness of pointer/enable/storage logic, nor rule out a transient on other select bits or reset.'])
(HERE/'slot01_constant_proof.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,luts=len(checks),input_assignments=sum(len(c['cases']) for c in checks))))
