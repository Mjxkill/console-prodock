"""Extract and functionally simulate the exact routed observer, no board IO."""
import bisect,hashlib,json,re,subprocess
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parent;ROOT=BASE_DIR.parents[2];HERE=BASE_DIR/'routed_v2'
BUILD=ROOT/'tang/impl/console_neo_n56r19_capture_ce_local'
PREV=ROOT/'TESTS/neo_common_cause_20261027/utna_header_netlist_01'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 HERE.mkdir(exist_ok=False)
 vo=(BUILD/'impl/pnr/console_neo.vo').read_text();cells=[];used=set()
 for m in re.finditer(r'^([A-Z][A-Z0-9_]*)\s+(\\\S+|\w+)\s+\((.*?)\);',vo,re.M|re.S):
  name=m[2].lstrip('\\')
  if not name.startswith('u_usb_idle_trace/'):continue
  pins={k:re.sub(r'\s+','',v).replace('\\','') for k,v in re.findall(r'\.(\w+)\((.*?)\)(?:,|\s*$)',m[3],re.M)}
  for value in pins.values():
   used.update(re.sub(r'\[.*?\]','',x) for x in value.strip('{}').split(','))
  cells.append((name,m[0]))
 assert len(cells)==3729,len(cells)
 names={name for name,text in cells};parameters=[]
 for line in vo.splitlines():
  if line.startswith('defparam '):
   m=re.match(r'^defparam \\(\S+)\s*\.',line)
   if m and m[1] in names:parameters.append(line)
 declarations={m[2].lstrip('\\'):(m[1] or '',m[0]) for m in re.finditer(r'^wire\s+(\[[^]]+\]\s+)?(\\\S+|\w+)\s*;',vo,re.M)}
 inputs=['PHY_DATAIN','PHY_DATAOUT','PHY_RESET','PHY_RXACTIVE','PHY_RXERROR','PHY_RXVALID','PHY_TXREADY','PHY_TXVALID','bus_haddr','bus_htrans','bus_hwdata','bus_hwrite','endpt_sel','n949_8','n960_9','phy_clk','rst_usb','usb_sof','vid_hclk','vid_hrstn']
 outputs=['n6_5','read_pending','usb_trace_hrdata'];ports=inputs+outputs
 def ident(name):return '\\'+name+' ' if '/' in name or '.' in name else name
 text='`timescale 1ns/1ps\nmodule usb_idle_trace_routed(\n'+',\n'.join(('input' if name in inputs else 'output')+' wire '+declarations[name][0]+ident(name) for name in ports)+'\n);\n'
 for name in sorted(used-set(ports)):
  assert name in declarations,name
  text+=declarations[name][1]+'\n'
 text+='assign VCC=1\'b1;assign GND=1\'b0;\n'
 text+='\n'.join(v for n,v in cells)+'\n'+'\n'.join(parameters)+'\nendmodule\n'
 (HERE/'routed_cut.v').write_text(text)
 tb=(PREV/'tb.sv').read_text().replace('usb_idle_trace dut(','usb_idle_trace_routed dut(')
 start=tb.index('  .bus_haddr_0(');end=tb.index('  .PHY_DATAIN(',start)
 tb=tb[:start]+"  .bus_haddr(haddr[14:0] | 15'h2000),\n"+tb[end:]
 # Routed bus_htrans is [1:1], one bit, so the original scalar connection is exact.
 (HERE/'tb_routed.sv').write_text(tb)
 compiler='/tmp/console-usb-sim-tools/extracted/usr/bin/iverilog';lib='/tmp/console-usb-sim-tools/extracted/usr/lib/x86_64-linux-gnu/ivl'
 vendor=Path('/home/michael/gowin/Gowin_V1.9.12_linux/IDE/simlib/gw5a/prim_sim.v')
 r=subprocess.run([compiler,'-B',lib,'-g2012','-s','usb_idle_trace_protocol_tb','-o',str(HERE/'routed.vvp'),str(HERE/'tb_routed.sv'),str(HERE/'routed_cut.v'),str(vendor)],capture_output=True,text=True,timeout=40)
 (HERE/'compile.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr[-4000:]
 records=[]
 for i,args in enumerate([['+hp=6.25','+up=8.333333','+phase=.317'],['+hp=6.241','+up=8.342','+phase=3.713'],['+hp=8.342','+up=6.241','+phase=1.117']]):
  r=subprocess.run(['/tmp/console-usb-sim-tools/extracted/usr/bin/vvp',str(HERE/'routed.vvp')]+args,capture_output=True,text=True,timeout=20)
  (HERE/f'case_{i}.log').write_text(r.stdout+r.stderr)
  records.append(dict(args=args,returncode=r.returncode,passed=r.returncode==0 and 'PASS EXACT SNAPSHOT seq=4' in r.stdout,output=r.stdout))
 result=dict(hardware_access=False,Gowin_executed=False,SDF_annotation=False,passed=all(x['passed'] for x in records),routed_cells=len(cells),cases=records,
             input_sha256={str(p):sha(p) for p in [Path(__file__),BUILD/'impl/pnr/console_neo.vo',HERE/'routed_cut.v',HERE/'tb_routed.sv',vendor]},
             limits=['Exact routed primitive graph including two 16-bit SDPB memories; external clocks/reset/AHB are bench models.','No SDF, metastability or measured board startup waveform. Passing does not establish hardware correctness.'])
 (HERE/'routed_result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(passed=result['passed'],cases=len(records),hardware_access=False)))
 if not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
