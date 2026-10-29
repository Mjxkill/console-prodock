#!/usr/bin/env python3
"""Stage read-only exact RTL and an executable baseline for model execution."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / 'clear_chain_01'


def main():
    out = OUT / 'deepseek_task'
    out.mkdir(parents=True)
    source = ROOT / 'tang/impl/console_neo_n56r19_capture_ce_local/source'
    video = ['gpu_accel', 'gpu_geometry', 'gpu_v1', 'gpu_raster', 'gpu_blit_dma',
             'blitter', 'font_ram', 'gpu_copy565', 'gpu_texture_cache', 'gpu_triangle',
             'gpu_perspective', 'gpu_geom_div', 'video_bus_stage']
    board = ['ddr_dcfifo', 'cdc_word', 'ahb_exts_bridge', 'ddr_gpu_arb']
    files = [source / f'tang/rtl/video/{name}.v' for name in video]
    files += [source / f'tang/rtl/board/{name}.v' for name in board]
    files += [source / 'tang/boards/neo/neo_gpu_debug.v', source / 'tang/rtl/video/font8x16.hex']
    for path in files:
        shutil.copyfile(path, out / path.name)
    original = (ROOT / 'TESTS/rtl/neo_gpu_bus_chain_tb.sv').read_text()
    original = original.replace('module neo_gpu_bus_chain_tb;', 'module bench;')
    original = original.replace('"tang/rtl/video/font8x16.hex"', '"font8x16.hex"')
    original = original.replace('.ready(1\'b1),.rd_data', '.ready(native_ready),.rd_data')
    # The following baseline preserves real bridge/stage/GPU/observer and adds
    # exact arbiter ports. The model owns tests/bench only, never these RTL files.
    marker = '    task access('
    index = original.index(marker)
    prefix = original[:index]
    prefix = prefix.replace('    neo_gpu_debug debug_port', '    wire native_ready;\n    neo_gpu_debug debug_port')
    arb = '''
    integer tick=0,accepted=0,stalls=0;
    wire men,mwen,mwend;wire[2:0]mcmd;wire[28:0]maddr;
    wire[255:0]mdata;wire[31:0]mmask;
    wire mrdy=(tick%7!=0 && tick%7!=1),mwrdy=(tick%5!=0);
    ddr_gpu_arb arb(.clk(mem_clk),.rst_n(resetn),
      .c_en(1'b0),.c_cmd(3'd0),.c_addr(29'd0),.c_ready(),
      .c_wr_en(1'b0),.c_wr_end(1'b0),.c_wr_data(256'd0),.c_wr_mask(32'hffffffff),
      .c_wr_ready(),.c_rd_data(),.c_rd_valid(),.c_rd_end(),
      .g_valid(1'b0),.g_addr(29'd0),.g_ready(),.g_data(),.g_data_valid(),
      .b_valid(valid),.b_write(write),.b_addr(addr),.b_wr_data(wr_data),.b_wr_mask(wr_mask),
      .b_ready(native_ready),.b_rd_data(),.b_rd_valid(),.m_en(men),.m_cmd(mcmd),.m_addr(maddr),
      .m_ready(mrdy),.m_wr_en(mwen),.m_wr_end(mwend),.m_wr_data(mdata),.m_wr_mask(mmask),
      .m_wr_ready(mwrdy),.m_rd_data(256'd0),.m_rd_valid(1'b0),.m_rd_end(1'b0));
    always @(posedge mem_clk)begin
      tick<=tick+1;
      if(resetn && valid && !native_ready)stalls<=stalls+1;
      if(resetn && men && mrdy)begin
        if(mcmd!=0 || !mwen || !mwrdy || !mwend || maddr!==29'h04800008 ||
           mmask!==0 || mdata!=={16{16'h6b4d}})$fatal(1,"CHECK_FAIL FOOTPRINT");
        accepted<=accepted+1;
      end
    end
'''
    task = original[index:original.index('    reg [31:0] value,words')]
    tail = '''
    reg[31:0]value,words[0:15];integer received=0;
    always @(posedge mem_clk)if(resetn && gpu.command_we)begin
      if(received>=16 || gpu.queue_data!==words[received])$fatal(1,"CHECK_FAIL PAYLOAD");
      received=received+1;
    end
    task wait_done(input[31:0]wanted);
      integer polls;begin
       polls=0;value=0;
       while(value!=wanted && polls<400)begin
        access(0,32'he9001008,0,value);polls=polls+1;
       end
       if(value!=wanted)$fatal(1,"CHECK_FAIL COMPLETION done=%0d want=%0d",value,wanted);
      end
    endtask
    initial begin
      words[0]='h16000000;words[1]='h12000020;words[2]='h12000040;
      words[3]='h00100001;words[4]='h00200020;words[5]=0;words[6]=0;words[7]=0;
      words[8]='h1c000000;words[9]=1;words[10]='h6b4d;words[11]=0;
      words[12]=0;words[13]='h00100001;words[14]=0;words[15]=0;
      repeat(8)@(negedge hclk);resetn=1;repeat(20)@(negedge hclk);
      access(0,'he9001000,0,value);if(value!=='h424c5432)$fatal(1,"CHECK_FAIL ID");
      for(integer i=0;i<8;i++)access(1,'he9001010,words[i],value);
      wait_done(1);if(accepted!=0)$fatal(1,"CHECK_FAIL TARGET_DMA");
      for(integer i=8;i<16;i++)access(1,'he9001010,words[i],value);
      wait_done(2);repeat(40)@(negedge hclk);
      access(0,'he9001004,0,value);if(value!=0)$fatal(1,"CHECK_FAIL BUSY");
      access(0,'he9001034,0,value);if(value!=0)$fatal(1,"CHECK_FAIL REJECT");
      if(accepted!=1 || received!=16 || stalls==0)$fatal(1,"CHECK_FAIL COVERAGE");
      $display("BASELINE_PASS accepted=%0d words=%0d stalls=%0d",accepted,received,stalls);
      $finish;
    end
    initial begin #1000000;$fatal(1,"CHECK_FAIL WATCHDOG");end
endmodule
'''
    (out / 'bench.sv').write_text(prefix + arb + task + tail)
    inputs = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    (out / 'INPUTS.json').write_text(json.dumps(inputs, indent=2)+'\n')
    (out / 'ANALYSIS.md').write_text('# Pending model implementation and measured test results\n')
    print(out)


if __name__ == '__main__':
    main()
