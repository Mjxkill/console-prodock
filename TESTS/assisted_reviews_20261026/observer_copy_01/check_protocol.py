#!/usr/bin/env python3
"""Test the real new observer and unchanged NCP bus; no board or PnR."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=ROOT/'TESTS/neo_720p_20261012/local_capture_20261026'
IVL=Path('/tmp/console-usb-sim-tools/extracted/usr')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def replace_once(text,old,new):
 assert text.count(old)==1,old
 return text.replace(old,new)

def main():
 p=argparse.ArgumentParser();p.add_argument('--helper',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 a.helper=a.helper.resolve();a.out=a.out.resolve();a.out.mkdir(parents=True)
 tb=(OLD/'capture_tb.sv').read_text()
 tb=replace_once(tb,'reg hsel=0,hwrite=0;', 'reg [3:0] mem_events=0;\nreg hsel=0,hwrite=0;')
 tb=replace_once(tb,'neo_capture_local cap(.clk(gclk),.resetn(resetn),.sample(sample),',
                 'neo_capture_local cap(.clk(gclk),.resetn(resetn),.sample(sample),.mem_events(mem_events),')
 tb=replace_once(tb,"trace[63:56]!==8'hc1", "trace[63:60]!==4'hd")
 tb=replace_once(tb,' // No indefinite wait on AHB when GPU clock stops.', '''
 // No events are inherited from before ARM. Events remain live after the
 // packet capture completes; HELD changes only on an explicit snapshot.
 scenario=60;mem_events=4'hf;repeat(5)@(negedge gclk);mem_events=0;
 arm();snapshot();if(trace[59:56]!==0)$fatal(1,"Events before ARM survived");checks++;
 // CLEAR passes issue -> producer -> pending -> accepted at separate edges.
 @(negedge gclk);mem_events=1;@(negedge gclk);mem_events=2;
 @(negedge gclk);mem_events=4;@(negedge gclk);mem_events=8;
 @(negedge gclk);mem_events=0;snapshot();
 if(trace[59:56]!==15)$fatal(1,"CLEAR sticky path missing");checks++;
 // Re-arm drops old history. COPY bypasses native_issue and must record E.
 scenario=61;arm();packet(8'h10,1,0,0);
 @(negedge gclk);mem_events=2;@(negedge gclk);mem_events=4;
 @(negedge gclk);mem_events=8;@(negedge gclk);mem_events=0;snapshot();
 if(trace[59:56]!==14 || trace[50]!==1)$fatal(1,"COPY sticky path/capture missing");checks++;
 first_trace=held;
 @(negedge gclk);mem_events=1;repeat(20)@(negedge gclk);mem_events=0;
 if(held!==first_trace)$fatal(1,"HELD changed without SNAP");checks++;
 snapshot();if(trace[59:56]!==15)$fatal(1,"Events after first SNAP not retained");checks++;
 // Missing issue/valid/pending/ACK remain distinguishable; no implication
 // is invented by the observer itself.
 for(integer mask=0;mask<16;mask++)begin
   arm();@(negedge gclk);mem_events=mask;@(negedge gclk);mem_events=0;
   snapshot();if(trace[59:56]!==mask)$fatal(1,"Independent events collapsed %h",mask);checks++;
 end
 arm();snapshot();if(trace[59:56]!==0)$fatal(1,"No-event arm not empty");checks++;
 // No indefinite wait on AHB when GPU clock stops.''')
 tb=replace_once(tb,'resetn=0;start=0;ce=0;rst=0;drop=0;', 'resetn=0;mem_events=0;start=0;ce=0;rst=0;drop=0;')
 bench=a.out/'tb.sv';bench.write_text(tb)
 files=[bench,OLD/'neo_capture_bus.v',a.helper,
        ROOT/'tang/impl/console_neo_n56r15_reset50ms/source/tang/boards/neo/neo_gpu_debug.v']
 result={'passed':False,'hardware_access':False,'scope':'Observer protocol with unchanged NCP AHB/CDC; controlled fault samples, not an application RTL replacement',
         'inputs':{str(f):sha(f) for f in [Path(__file__),OLD/'capture_tb.sv',*files]}}
 try:
  commands=[('compile',[str(IVL/'bin/iverilog'),'-B',str(IVL/'lib/x86_64-linux-gnu/ivl'),'-g2012','-s','tb','-o',str(a.out/'sim.vvp'),*map(str,files)]),
            ('simulation',[str(IVL/'bin/vvp'),str(a.out/'sim.vvp')])]
  for name,command in commands:
   with (a.out/(name+'.log')).open('w') as log:subprocess.run(command,stdout=log,stderr=log,timeout=90,check=True)
  assert 'PASS local capture checks=' in (a.out/'simulation.log').read_text()
  for path,digest in result['inputs'].items():assert sha(Path(path))==digest,path
  result['passed']=True
 except Exception as e:result['error']=repr(e)
 finally:
  result['logs']={p.name:sha(p) for p in a.out.glob('*.log')}
  (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
