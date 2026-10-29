#!/usr/bin/env python3
"""TESTS-only CSR candidates; four-state equivalence and real full GPU benches."""
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
IVL = Path('/tmp/console-usb-sim-tools/extracted/usr')
PROFILES = {
    'neo': ROOT / 'tang/impl/console_neo_n56r19_capture_ce_local/source/tang',
    'prodock': ROOT / 'tang/impl/gpu_geometry_g22r0/source/tang',
    'shared': ROOT / 'tang',
}
OLD = '''        integer k;
        always @* begin
            response_data[response_byte*8+:8]=8'd0;
            for(k=0;k<26;k=k+1)
                response_data[response_byte*8+:8]=response_data[response_byte*8+:8] |
                    ({8{read_select[response_byte*26+k]}} & register_value[k][response_byte*8+:8]);
        end'''
NEW = '''        integer k;
        reg [7:0] accumulator;
        always @* begin
            accumulator=8'd0;
            for(k=0;k<26;k=k+1)
                accumulator=accumulator |
                    ({8{read_select[response_byte*26+k]}} & register_value[k][response_byte*8+:8]);
            response_data[response_byte*8+:8]=accumulator;
        end'''

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def rel(p):
    return str(p.relative_to(ROOT))

def run_ivl(out, bench, sources, marker, timeout=120):
    command = [str(IVL/'bin/iverilog'), '-B', str(IVL/'lib/x86_64-linux-gnu/ivl'),
               '-g2012', '-s', 'tb', '-o', str(out/'sim.vvp'), str(bench), *map(str,sources)]
    with (out/'compile.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=log, cwd=out, timeout=90, check=True)
    with (out/'simulation.log').open('w') as log:
        subprocess.run([str(IVL/'bin/vvp'), str(out/'sim.vvp')], stdout=log,
                       stderr=log, cwd=out, timeout=timeout, check=True)
    assert marker in (out/'simulation.log').read_text()
    return {'passed':True, 'command':command,
            'logs':{p.name:sha(p) for p in out.glob('*.log')}}

def mux_bench(candidate):
    # Extract exact changed generate block. The oracle evaluates independent
    # per-bit Boolean OR reductions, preserving Verilog four-state semantics.
    block = candidate[candidate.index('    genvar response_byte;'):]
    block = block[:block.index('    end endgenerate')+len('    end endgenerate')]
    return '''`timescale 1ns/1ps
module tb;
reg [103:0] read_select=0;
reg [31:0] register_value[0:25];
reg [31:0] response_data;
reg [31:0] expected;
reg acc;
integer checks=0,seed=32'h7412a9;
''' + block + '''
task automatic verify;
  #1;
  for(integer b=0;b<32;b++)begin
    acc=0;
    for(integer k=0;k<26;k++)acc=acc | (read_select[(b/8)*26+k] & register_value[k][b]);
    expected[b]=acc;
  end
  if(response_data !== expected)$fatal(1,"CSR mismatch got=%h expected=%h",response_data,expected);
  checks++;
endtask
initial begin
  // Every byte address, including unaligned and unmapped addresses, for
  // deterministic, random and X/Z register payloads.
  for(integer pattern=0;pattern<12;pattern++)begin
    for(integer k=0;k<26;k++)begin
      case(pattern)
        0:register_value[k]=0;
        1:register_value[k]=32'hffffffff;
        2:register_value[k]=32'h424c5432 ^ (32'h1020304*k);
        3:register_value[k]=32'hxxxxxxxx;
        4:register_value[k]=32'hzzzzzzzz;
        5:register_value[k]={8'hxx,8'hzz,8'h0,8'hff};
        default:register_value[k]=$random(seed);
      endcase
    end
    for(integer a=0;a<256;a++)begin
      for(integer i=0;i<104;i++)read_select[i]=(a==(i%26)*4);
      verify();
    end
  end
  // This includes states not reachable from a decoded CSR read: multiple
  // selects, unknown and high-impedance selectors across individual bytes.
  for(integer test=0;test<512;test++)begin
    for(integer k=0;k<26;k++)register_value[k]=$random(seed);
    for(integer i=0;i<104;i++)begin
      case(($unsigned($random(seed)))%4)
        0:read_select[i]=0;1:read_select[i]=1;
        2:read_select[i]=1'bx;3:read_select[i]=1'bz;
      endcase
    end
    verify();
  end
  $display("PASS CSR FOUR STATE checks=%0d addresses=256 patterns=12 arbitrary_selectors=512",checks);
  $finish;
end
initial begin #100000;$fatal(1,"CSR bounded timeout");end
endmodule
'''

def main():
    out=HERE/'csr_candidates_01'
    out.mkdir()
    manifest=json.loads((HERE/'rtl_inputs.json').read_text())
    for name,digest in manifest['sources'].items():
        assert sha(ROOT/name)==digest,name
    relative_sources=[Path(p).relative_to(PROFILES['neo'].relative_to(ROOT))
                      for p in manifest['sources']]
    result={'passed':False,'hardware_access':False,'shared_sources_modified':False,
            'scope':'TESTS-only CSR delta-event fix; arithmetic equivalence and complete application RTL, no hardware/timing qualification',
            'started_unix':time.time(),'inputs':{rel(Path(__file__)):sha(Path(__file__))},'profiles':{}}
    try:
        for profile,base in PROFILES.items():
            folder=out/profile
            folder.mkdir()
            source=base/'rtl/video/gpu_accel.v'
            original=source.read_text()
            assert original.count(OLD)==1,profile
            candidate=original.replace(OLD,NEW)
            path=folder/'gpu_accel.v'
            path.write_text(candidate)
            (folder/'candidate.diff').write_text(''.join(difflib.unified_diff(
                original.splitlines(True),candidate.splitlines(True),fromfile=rel(source),tofile=rel(path))))
            result['inputs'][rel(source)]=sha(source)
            p={'source':rel(source),'source_sha256':sha(source),'candidate':rel(path),
               'candidate_sha256':sha(path),'only_change':'four byte-local CSR accumulators','tests':{}}
            result['profiles'][profile]=p
            mux=folder/'mux'
            mux.mkdir()
            bench=mux/'tb.sv'
            bench.write_text(mux_bench(candidate))
            p['tests']['mux']=run_ivl(mux,bench,[],'PASS CSR FOUR STATE')
            p['tests']['mux']['bench_sha256']=sha(bench)
            if profile=='shared':
                continue
            sources=[]
            for relative in relative_sources:
                real=base/relative
                assert real.is_file(),real
                result['inputs'][rel(real)]=sha(real)
                if relative.suffix=='.v':
                    sources.append(path if relative.name=='gpu_accel.v' else real)
            for task,bench_name,marker in [('clear','tb_reviewed_r3.sv','PASS R19 REAL SLOT CLEAR'),
                                          ('copy','tb_copy.sv','PASS R19 REAL SLOT COPY')]:
                run=folder/task
                run.mkdir()
                text=(HERE/bench_name).read_text()
                if profile=='prodock':
                    old=',\n        .debug_state(),.debug_accept(),.observe_packet_words()'
                    assert text.count(old)==1
                    text=text.replace(old,'')
                bench=run/'tb.sv'
                bench.write_text(text)
                shutil.copy2(base/'rtl/video/font8x16.hex',run/'font8x16.hex')
                p['tests'][task]=run_ivl(run,bench,sources,marker)
                p['tests'][task]['bench_sha256']=sha(bench)
                p['tests'][task]['adaptations']=[] if profile=='neo' else ['remove three absent diagnostic output port connections only']
        for name,digest in result['inputs'].items():
            assert sha(ROOT/name)==digest,name
        result['passed']=True
    except Exception as exc:
        result['error']=repr(exc)
    finally:
        result['finished_unix']=time.time()
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result),flush=True)
    if not result['passed']:
        raise SystemExit(1)

if __name__=='__main__':
    main()
