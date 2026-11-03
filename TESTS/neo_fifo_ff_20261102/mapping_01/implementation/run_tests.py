"""Vendor/scoreboard equivalence and mutation controls; never invokes Gowin."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

HERE=Path(__file__).resolve().parent
TOOLS=Path('/tmp/console-usb-sim-tools/extracted/usr')
IVL=TOOLS/'lib/x86_64-linux-gnu/ivl'
PRIM=Path('/home/michael/gowin/IDE/simlib/gw5a/prim_sim.v')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(command):
    began=time.monotonic()
    try:
        p=subprocess.run(command,capture_output=True,text=True,timeout=90)
        return p.returncode,p.stdout+p.stderr,time.monotonic()-began
    except subprocess.TimeoutExpired as error:
        def text(value):return value.decode(errors='replace') if isinstance(value,bytes) else value or ''
        return 124,text(error.stdout)+text(error.stderr)+'\nRUNNER_TIMEOUT_90S\n',time.monotonic()-began


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',type=Path,default=HERE/'neo_command_ff128.v')
    parser.add_argument('--primitives',type=Path,default=PRIM)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--mutants',action='store_true')
    args=parser.parse_args();out=args.out.resolve()
    if not out.is_relative_to(HERE.parent) or out.exists():raise ValueError('New owned output required')
    out.mkdir();started=time.monotonic();cases=[]
    source=args.candidate.resolve();primitives=args.primitives.resolve()
    with tempfile.TemporaryDirectory(prefix='neo-fifo-ff-') as temporary:
        temp=Path(temporary)
        def compile_one(name,path):
            exe=temp/(name+'.vvp')
            cmd=[str(TOOLS/'bin/iverilog'),'-B',str(IVL),'-g2012','-s','tb','-o',str(exe),str(primitives),str(path),str(HERE/'tb_storage.sv')]
            rc,log,seconds=run(cmd);(out/(name+'_compile.log')).write_text(log)
            if rc:raise RuntimeError('Compile failure '+name)
            return exe
        exe=compile_one('candidate',source)
        for name,arguments in [
            ('ahb80_gpu75',['+AHALF=6.25','+BHALF=6.667','+PHASE=2']),
            ('near_below',['+AHALF=4','+BHALF=4.0032','+PHASE=0.5']),
            ('near_above',['+AHALF=4','+BHALF=3.9936','+PHASE=3.5']),
            ('coincident_separate',['+AHALF=6.25','+BHALF=6.25','+PHASE=0']),
            ('same_clock_with_reset',['+AHALF=6.667','+SYNC=1']),
            ('cmem_exact_constants',['+AHALF=6.667','+SYNC=1','+CMEM=1'])]:
            rc,log,seconds=run([str(TOOLS/'bin/vvp'),'-M',str(IVL),str(exe),*arguments])
            (out/(name+'.log')).write_text(log)
            cases.append(dict(name=name,passed=rc==0 and 'STORAGE_EQUIVALENCE_PASS' in log,rc=rc,seconds=seconds))
            print(cases[-1],flush=True)
        if args.mutants:
            text=(HERE/'neo_command_ff128.v').read_text()
            mutations={
                'read_index':('32*ADB[11:5]+:32','32*(ADB[11:5]^7\'d1)+:32'),
                'wrong_data':('.D(DI[bit_index])','.D(~DI[bit_index])'),
                'reset_gated_by_ce':('.RESET(RESET)', '.RESET(RESET && read_enabled)'),
                'reset_erases_storage':('.RESET(1\'b0)', '.RESET(RESET)'),
                'extra_read_cycle':('wire [31:0] selected=words[32*ADB[11:5]+:32];',
                    'reg [31:0] delayed=0; always @(posedge CLKB) delayed<=words[32*ADB[11:5]+:32]; wire [31:0] selected=delayed;')}
            for name,(old,new) in mutations.items():
                if text.count(old)!=1:raise RuntimeError('Mutation anchor changed '+name)
                path=temp/(name+'.v');path.write_text(text.replace(old,new,1));mutant=compile_one(name,path)
                rc,log,seconds=run([str(TOOLS/'bin/vvp'),'-M',str(IVL),str(mutant)])
                (out/(name+'.log')).write_text(log)
                cases.append(dict(name=name,mutation_control=True,detected=rc!=0 and 'MISMATCH' in log,
                                  passed=rc!=0 and 'MISMATCH' in log,rc=rc,seconds=seconds))
                print(cases[-1],flush=True)
    result={'passed':all(c['passed']for c in cases),'cases':cases,'seconds':time.monotonic()-started,
       'sources_sha256':{str(p):sha(p)for p in(source,primitives,HERE/'tb_storage.sv',Path(__file__))},
       'synthesis':False,'hardware':False,'SDF':False,
       'limits':['Simulation of reachable 128x32 SDPB contract; no physical CDC/metastability model.',
                 'No same-address simultaneous active read/write qualification: UG300 forbids it.',
                 'Global GSR remains inactive as in target; runtime RESET only resets DO.',
                 'No command FIFO pointer or complete GPU integration test in this bench.']}
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    raise SystemExit(not result['passed'])


if __name__=='__main__':main()
