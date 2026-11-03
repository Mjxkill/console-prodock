#!/usr/bin/env python3
"""Reuse the frozen SDPB equivalence bench; outputs stay in this candidate only."""
import argparse,hashlib,importlib.util,json,subprocess,tempfile,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'mapping_01/implementation'
TOOLS=Path('/tmp/console-usb-sim-tools/extracted/usr')
IVL=TOOLS/'lib/x86_64-linux-gnu/ivl'
PRIM=Path('/home/michael/gowin/IDE/simlib/gw5a/prim_sim.v')
CASES=[('ahb80_gpu75',['+AHALF=6.25','+BHALF=6.667','+PHASE=2']),
 ('near_below',['+AHALF=4','+BHALF=4.0032','+PHASE=0.5']),
 ('near_above',['+AHALF=4','+BHALF=3.9936','+PHASE=3.5']),
 ('coincident_separate',['+AHALF=6.25','+BHALF=6.25','+PHASE=0']),
 ('same_clock_with_reset',['+AHALF=6.667','+SYNC=1']),
 ('cmem_exact_constants',['+AHALF=6.667','+SYNC=1','+CMEM=1'])]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,default=HERE/'banked_words32.v');p.add_argument('--out',type=Path,required=True);p.add_argument('--mutants',action='store_true');a=p.parse_args()
 out=a.out.resolve()
 if not out.is_relative_to(HERE) or out.exists():raise ValueError('Fresh owned output required')
 out.mkdir();started=time.monotonic();cases=[]
 # Import only the existing bounded process helper. No old main/global overrides.
 spec=importlib.util.spec_from_file_location('frozen_storage_test',OLD/'run_tests.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 with tempfile.TemporaryDirectory(prefix='neo-banked-') as t:
  temp=Path(t)
  def build(name,source):
   exe=temp/(name+'.vvp');cmd=[str(TOOLS/'bin/iverilog'),'-B',str(IVL),'-g2012','-s','tb','-o',str(exe),str(PRIM),str(source),str(OLD/'tb_storage.sv')]
   rc,log,seconds=m.run(cmd);(out/(name+'_compile.log')).write_text(log)
   if rc:raise RuntimeError('Compile failed '+name)
   return exe
  def execute(name,exe,args,mutant=False):
   rc,log,sec=m.run([str(TOOLS/'bin/vvp'),'-M',str(IVL),str(exe),*args]);(out/(name+'.log')).write_text(log)
   passed=rc!=0 and 'MISMATCH' in log if mutant else rc==0 and 'STORAGE_EQUIVALENCE_PASS' in log
   cases.append(dict(name=name,passed=passed,returncode=rc,seconds=sec,mutation_control=mutant));print(cases[-1],flush=True)
  exe=build('candidate',a.candidate)
  with ThreadPoolExecutor(max_workers=3) as workers:
   pending=[workers.submit(execute,name,exe,args) for name,args in CASES]
   for future in pending:future.result()
  if a.mutants:
   text=a.candidate.read_text()
   changes={'row_index':("eq.INIT=16'h0001<<slot;","eq.INIT=16'h0001<<(slot^1);"),
    'wrong_data':('.D(DI[bit_index])','.D(~DI[bit_index])'),
    'reset_gated_by_ce':('.RESET(RESET)', '.RESET(RESET && read_enabled)'),
    'reset_erases_storage':(".RESET(1'b0)",'.RESET(RESET)'),
    'extra_read_cycle':('wire [31:0] selected=read_selected;', 'reg [31:0] delayed=0; always @(posedge CLKB) delayed<=read_selected; wire [31:0] selected=delayed;')}
   jobs=[]
   for name,(before,after) in changes.items():
    if text.count(before)!=1:raise ValueError('Mutation anchor not unique '+name)
    path=temp/(name+'.v');path.write_text(text.replace(before,after));jobs.append((name,build(name,path)))
   with ThreadPoolExecutor(max_workers=3) as workers:
    pending=[workers.submit(execute,name,exe,[],True) for name,exe in jobs]
    for future in pending:future.result()
 result={'passed':all(x['passed']for x in cases),'cases':cases,'elapsed_seconds':time.monotonic()-started,'files':{str(x):sha(x) for x in [a.candidate,PRIM,OLD/'tb_storage.sv',OLD/'run_tests.py',Path(__file__)]},'synthesis':False,'PNR':False,'hardware':False,'limits':['Same documented SDPB reachable128x32 contract, no physical CDC qualification','Same-address simultaneous read/write forbidden by vendor; collision outputs excluded by original bench','Runtime global GSR inactive; addresses/control binary','Pointer/protocol and full GPU not simulated here']}
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');raise SystemExit(not result['passed'])
if __name__=='__main__':main()
