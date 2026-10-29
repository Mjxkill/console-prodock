#!/usr/bin/env python3
"""Candidate packet test: full R19 command path, bounded native COPY terminal."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
SRC=HERE.parent/'clear_chain_01/deepseek_execution_02/isolation/tree'

# Test terminal uses known address-XOR bytes independently of GPU arithmetic.
MEMORY=r'''
    reg [255:0] native_response_data=0;
    reg native_response_valid=0;
    wire [255:0] blit_response_data;
    wire blit_response_valid;
    integer read_accepts=0,read_returns=0,read_delay=0;
    reg [255:0] source_line;
    initial begin
        for(integer k=0;k<8;k=k+1)
            source_line[k*32+:32]=(32'h12000000+4*k)^32'ha5396c17;
    end
    always @(posedge mem_clk)begin
        native_response_valid<=0;
        if(!resetn)begin read_accepts<=0;read_returns<=0;read_delay<=0;end
        else begin
            if(read_delay>0)begin
                read_delay<=read_delay-1;
                if(read_delay==1)begin
                    native_response_data<=source_line;
                    native_response_valid<=1;
                    read_returns<=read_returns+1;
                end
            end
            if(men && mrdy && mcmd==1)begin
                if(read_accepts!=0 || maddr!==29'h04800000 || mwen)
                    $fatal(1,"COPY_BAD_READ_OR_DUPLICATE");
                read_accepts<=read_accepts+1;read_delay<=5;
            end
            if(men && mrdy && mcmd!=0 && mcmd!=1)$fatal(1,"COPY_BAD_COMMAND");
            if(mwen && !(men && mrdy && mwrdy && mcmd==0))
                $fatal(1,"COPY_UNPAIRED_WRITE");
        end
    end
'''

def main():
    result={'hardware':False,'RTL_modified':False,'cases':[]}
    with tempfile.TemporaryDirectory(prefix='r19-copy-') as t:
        task=Path(t)
        for f in SRC.iterdir():
            if f.suffix in {'.v','.hex'}:shutil.copyfile(f,task/f.name)
        original=(SRC/'bench.sv').read_text()
        assert hashlib.sha256(original.encode()).hexdigest()=='730576cc4633cc824c03157b31da3cece0ea7130ce3e2af746c7899c6ac2c5ac'
        code=original.replace('    gpu_accel #',MEMORY+'\n    gpu_accel #',1)
        code=code.replace('.ready(gpu_native_ready), .rd_data(256\'d0), .rd_valid(1\'b0)', '.ready(gpu_native_ready), .rd_data(blit_response_data), .rd_valid(blit_response_valid)')
        code=code.replace('.b_ready(arb_b_ready), .b_rd_data(), .b_rd_valid()', '.b_ready(arb_b_ready), .b_rd_data(blit_response_data), .b_rd_valid(blit_response_valid)')
        code=code.replace('.m_wr_ready(mwrdy), .m_rd_data(256\'d0), .m_rd_valid(1\'b0),\n        .m_rd_end(1\'b0)', '.m_wr_ready(mwrdy), .m_rd_data(native_response_data), .m_rd_valid(native_response_valid),\n        .m_rd_end(native_response_valid)')
        code=code.replace("native_accept && mcmd !== 3'b000", "native_accept && mcmd !== 3'b000 && mcmd !== 3'b001")
        code=code.replace("mdata !== {16{16'h6b4d}}",'mdata !== source_line')
        code=code.replace('accepted != 1 || received != 16 || stalls == 0','accepted != 1 || received != 16 || read_accepts != 1 || read_returns != 1')
        old=[0x1c000000,1,0x6b4d,0,0,0x00100001,0,0]
        new=[0x1d000000,0x12000000,0x00100001,0x20,0,0,0x00100001,0]
        for i,(a,b) in enumerate(zip(old,new),8):
            before=f"words[{i}]"+('  ' if i<10 else ' ')+f"= 32'h{a:08x};"
            after=f"words[{i}]"+('  ' if i<10 else ' ')+f"= 32'h{b:08x};"
            assert before in code,before;code=code.replace(before,after)
        code=code.replace('        $finish;\n    end\n\n    // Global bounded', '        $display("COPY_RESULT reads=%0d returns=%0d writes=%0d words=%0d",read_accepts,read_returns,accepted,received);\n        $finish;\n    end\n\n    // Global bounded')
        (task/'bench.sv').write_text(code);(HERE/'bench_used.sv').write_text(code)
        cmd=['/usr/bin/verilator','--binary','--timing','-j','2','-Wno-fatal','-MAKEFLAGS','VM_PARALLEL_BUILDS=0','--top-module','bench','--Mdir',str(task/'obj'),'bench.sv']+[f.name for f in sorted(task.glob('*.v'))]
        r=subprocess.run(cmd,cwd=task,capture_output=True,text=True,timeout=48)
        (HERE/'compile.log').write_text(r.stdout+r.stderr);assert r.returncode==0,'compilation failed'
        for seed,fault in [(1,0),(8,0),(1,1),(1,2)]:
            r=subprocess.run([str(task/'obj/Vbench'),f'+seed={seed}',f'+fault={fault}'],cwd=task,capture_output=True,text=True,timeout=3)
            log=r.stdout+r.stderr;(HERE/f'seed{seed}_fault{fault}.log').write_text(log)
            ok=(r.returncode==0 and 'COPY_RESULT reads=1 returns=1 writes=1 words=16' in log) if fault==0 else (r.returncode!=0 and 'CHECK_FAIL COMPLETION' in log and 'accepted=0' in log)
            result['cases'].append({'seed':seed,'fault':fault,'returncode':r.returncode,'passed':ok})
        result.update(passed=all(x['passed'] for x in result['cases']),packet=new,
                      bench_sha256=hashlib.sha256(code.encode()).hexdigest(),
                      RTL_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in task.glob('*.v')})
        (HERE/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
        return int(not result['passed'])

if __name__=='__main__':raise SystemExit(main())
