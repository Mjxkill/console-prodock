`timescale 1ns/1ps
module gpu_registers_tb;
    reg hclk=0,pixel_clk=0,mem_clk=0;
    always #5 hclk=~hclk;
    always #11 pixel_clk=~pixel_clk;
    always #7 mem_clk=~mem_clk;
    reg resetn=0,hsel=0,hwrite=0;
    reg [1:0] htrans=0;
    reg [31:0] haddr=0,hwdata=0;
    wire hready;
    wire [31:0] hrdata;
    integer a,pass,stalls=0;
    gpu_scanout #(.WIDTH(64),.HEIGHT(8),.H_TOTAL(96),.V_TOTAL(12),
                  .H_START(8),.V_START(2),.H_SYNC(4),.V_SYNC(1)) dut (
        .hclk(hclk),.hresetn(resetn),.hsel(hsel),.hwrite(hwrite),
        .haddr(haddr),.hwdata(hwdata),.htrans(htrans),.hrdata(hrdata),.hready(hready),
        .pixel_clk(pixel_clk),.mem_clk(mem_clk),
        .fetch_ready(1'b1),.fetch_data(256'd0),.fetch_data_valid(1'b0),
        .fetch_valid(),.fetch_addr(),.lcd_en(),.lcd_hs(),.lcd_vs(),
        .lcd_r(),.lcd_g(),.lcd_b());
    task write_register(input [31:0] addr,input [31:0] data);
        @(negedge hclk); hsel=1;htrans=2;hwrite=1;haddr=addr;
        @(negedge hclk); hsel=0;htrans=0;hwrite=0;hwdata=data;
        @(negedge hclk);
        while(!hready) begin stalls=stalls+1; @(negedge hclk); end
    endtask
    initial begin
        repeat(4) @(negedge hclk);
        resetn=1;
        for(pass=0;pass<3;pass=pass+1) begin
            write_register(4,32'h00812340+pass*32);
            write_register('h30,1);
            write_register('h40,pass&1);
            write_register('hc,1);
            // This write waits for the vertical commit; read selection must hold.
            write_register('h800,0);
            for(a=0;a<4096;a=a+1) begin
                @(negedge hclk);
                haddr=pass==1 ? 4095-a : a;
                hsel=a[0]; htrans=a[1:0]; hwrite=0;
            end
            @(negedge hclk); resetn=0;
            repeat(3) @(negedge hclk);
            resetn=1;
        end
        if(stalls==0) $fatal(1,"Missing commit wait coverage");
        $display("GPU register address sweep PASS: 12288 addresses, %0d wait cycles",stalls);
        $finish;
    end
    initial begin #10000000; $fatal(1,"timeout"); end
endmodule
