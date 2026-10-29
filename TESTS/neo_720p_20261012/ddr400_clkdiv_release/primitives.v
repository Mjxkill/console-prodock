`timescale 1ns/1ps
module GSR (GSRI);

input GSRI;

wire GSRO;

assign GSRO = GSRI;

endmodule //GSR (global set/reset control)
module CLKDIV(CLKOUT, CALIB, HCLKIN, RESETN); 

input HCLKIN;
input RESETN;
input CALIB;
output CLKOUT;

parameter DIV_MODE = "2"; //"1","2","3","3.5","4","5","6","7","8"

reg reset_0;
reg calib_0,calib_1,calib_2,calib_state;
wire calib_en,calib_resetn,cnt_enable;
reg select_no_3p5,select3p5,select5,select3,select6,select7;
wire dsel_en,clk_div_0,clk_div2,clk_div7_8,clk_div;
reg d_sel,cnt_0,cnt_1,cnt_2,clk_div_1;
wire dsel_clk;

wire grstn;
assign grstn = GSR.GSRO;

initial begin
    cnt_0 = 1'b0;
    cnt_1 = 1'b0;
    cnt_2 = 1'b0;
    d_sel = 1'b0;
    calib_state = 1'b0;
    clk_div_1 = 1'b0;

    if (DIV_MODE == "3.5") begin
        select3p5 = 1'b1;
        select_no_3p5 = 1'b0;
    end else
    begin
        select_no_3p5 = 1'b1;
        select3p5 = 1'b0;
    end

    if (DIV_MODE == "5")
    begin
        select5 = 1'b1;
    end else begin
        select5 = 1'b0;        
    end
    if (DIV_MODE == "3")
    begin
        select3 = 1'b1;
    end else begin
        select3 = 1'b0;        
    end
    if (DIV_MODE == "6")
    begin
        select6 = 1'b1;
    end else begin
        select6 = 1'b0;        
    end
    if (DIV_MODE == "7")
    begin
        select7 = 1'b1;
    end else begin
        select7 = 1'b0;        
    end

end

always @(posedge HCLKIN or negedge grstn or negedge RESETN) begin
    if (!grstn) begin
        reset_0 <= 1'b0;
    end else if (!RESETN) begin
        reset_0 <= 1'b0;
    end else begin
        reset_0 <= 1'b1;
    end
end

always @(posedge HCLKIN or negedge reset_0) begin
    if (!reset_0) begin
        calib_0 <= 1'b0;
    end else begin
        calib_0 <= ~CALIB;
    end
end

always @(posedge HCLKIN or negedge reset_0) begin
    if (!reset_0) begin
        calib_1 <= 0;
    end else begin
        calib_1 <= calib_0;
    end
end

always @(posedge HCLKIN or negedge reset_0) begin
    if (!reset_0) begin
        calib_2 <= 1'b0;
    end else begin
        calib_2 <= calib_1;
    end
end

assign calib_resetn =  ~(calib_1 && (~calib_2));
assign calib_en = ~(calib_resetn | (~select_no_3p5));

always @ (posedge HCLKIN or negedge reset_0)
begin
    if (!reset_0)  begin
        calib_state <= 1'b0;
    end else begin
        if (calib_en == 1'b1) begin
            calib_state <= ~calib_state;
        end else begin
            calib_state <= calib_state;
        end
    end
end

assign cnt_enable = (~((~calib_resetn)&calib_state) & select_no_3p5) | (calib_resetn & select3p5);

assign dsel_en = (d_sel& cnt_0 & cnt_1 & select3p5) | (calib_resetn & (~d_sel) & (~cnt_0) & cnt_1 & select3p5);

assign dsel_clk = HCLKIN ^ d_sel;
always @(posedge dsel_clk or negedge reset_0) begin
    if (!reset_0) begin
        d_sel  <= 1'b0;
    end else if(dsel_en == 1'b1) begin
        d_sel  <= ~d_sel;
    end else if(dsel_en == 1'b0) begin
        d_sel <= d_sel;
    end
end

assign cnt_reset = ((select3&((~cnt_2)&cnt_1&(~cnt_0))) | (select6&(cnt_2&(~cnt_1)&cnt_0)) | (select7&(cnt_2&cnt_1&(~cnt_0))) | (select5&(cnt_2&(~cnt_1)&(~cnt_0)))) | (select3p5 & (~d_sel) & (~cnt_0) & cnt_1);

always @(posedge HCLKIN or negedge reset_0) begin
    if (!reset_0) begin
        cnt_0  <= 1'b1;
    end else if(cnt_enable == 1'b1) begin
        cnt_0  <= ~(cnt_0 | cnt_reset);
    end else if(cnt_enable == 1'b0) begin
        cnt_0 <= cnt_0;
    end
end

always @(posedge HCLKIN or negedge reset_0) begin
    if (!reset_0) begin
        cnt_1  <= 1'b1;
    end else if(cnt_enable == 1'b1) begin
        cnt_1  <= ~(cnt_reset | (cnt_0 ^~ cnt_1));
    end else if(cnt_enable == 1'b0) begin
        cnt_1 <= cnt_1;
    end
end

always @(posedge HCLKIN or negedge reset_0) begin
    if (!reset_0) begin
        cnt_2  <= 1'b0;
    end else if(cnt_enable == 1'b1) begin
        cnt_2  <= ~(cnt_reset | (cnt_2 ^~ (cnt_0 & cnt_1)));
    end else if(cnt_enable == 1'b0) begin
        cnt_2 <= cnt_2;
    end
end

assign clk_div_0 = ~cnt_1;
always @(negedge HCLKIN or negedge reset_0) begin
    if(!reset_0)
        clk_div_1 <= 1'b0;
    else
        clk_div_1 <= clk_div_0;
end

assign clk_div = (d_sel == 1'b1) ? clk_div_1 : clk_div_0;
assign clk_div2 = ~cnt_0;
assign clk_div7_8 = cnt_2;

assign CLKOUT = (DIV_MODE == "1")? HCLKIN: ((DIV_MODE == "2")? clk_div2 : (((DIV_MODE == "7") || (DIV_MODE == "8")) ? clk_div7_8 : clk_div));

endmodule