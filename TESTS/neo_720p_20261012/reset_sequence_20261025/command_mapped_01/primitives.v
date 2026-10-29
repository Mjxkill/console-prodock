`timescale 1ns/1ps
primitive mux2 (O, I0, I1, S);
output O;
input I0, I1, S;
table
// I0  I1  S     O
   0   ?   0  :  0 ;
   1   ?   0  :  1 ;
   x   ?   0  :  x ;
   ?   0   1  :  0 ;
   ?   1   1  :  1 ;
   ?   x   1  :  x ;
   0   0   x  :  0 ;
   0   1   x  :  x ;
   1   0   x  :  x ;
   1   1   x  :  1 ;
   ?   x   x  :  x ;
   x   ?   x  :  x ;
endtable
endprimitive
module ALU (SUM, COUT, I0, I1, I3, CIN);

input I0;
input I1;
input I3;
input CIN;
output SUM;
output COUT;

parameter ADD = 0;
parameter SUB = 1;
parameter ADDSUB = 2;
parameter NE = 3;
parameter GE = 4;
parameter LE = 5;
parameter CUP = 6;
parameter CDN = 7;
parameter CUPCDN = 8;

parameter ALU_MODE = 0;

reg S, C;

assign SUM = S ^ CIN;
assign COUT = S? CIN : C;

always @(I0, I1, I3,CIN) begin
	case (ALU_MODE)
		ADD: begin // adder; LSB CIN must be 1'b0
			S = I0 ^ I1;
			C = I0;
		end
		SUB: begin // subtractor; LSB CIN must be 1'b1
			S = I0 ^ ~I1;
			C = I0;
		end
		ADDSUB: begin // adder subtractor;
			S = I3? I0 ^ I1 : I0 ^ ~I1;
			C = I0;
		end
		NE: begin // not equal to; LSB CIN must be 1'b0
			S = I0 ^ ~I1;
			C = 1'b1;
		end
		GE: begin // greater than or equal to; LSB CIN must be 1'b1
			S = I0 ^ ~I1;
			C = I0;
		end
		LE: begin // less than or equal to; LSB CIN must be 1'b1
			S = ~I0 ^ I1;
			C = I1;
		end
		CUP: begin // up counter; LSB CIN must be 1'b1
			S = I0;
			C = 1'b0; // or equivalently, I0
		end
		CDN: begin // down counter; LSB CIN must be 1'b0
			S = ~I0;
			C = 1'b1; // or equivalently, I0
		end
		CUPCDN: begin // up down counter; I3 as select bit - 1'b0: down counter, LSB CIN must be 1'b0; 1'b1: up counter, LSB CIN must be 1'b1
			S = I3? I0 : ~I0;
			C = I0;
		end
		default: begin
		//	$display ("%d: Unsupported ALU mode\n", ALU_PARAM);
		//	$finish;
		end
	endcase
end

endmodule
module DFFCE (Q, D, CLK, CE, CLEAR);

input D, CLK, CLEAR, CE;
output Q;

parameter INIT = 1'b0;
reg Q_reg;
wire gsrt = GSR.GSRO;

initial Q_reg = INIT;

always @(gsrt or CLEAR) begin
	if(!gsrt)
		assign Q_reg = INIT;
	else if(CLEAR)
		assign Q_reg = 1'b0;
	else
		deassign Q_reg;
end

always @(posedge CLK) begin
	if (CE)
		Q_reg <= D;
end

assign Q = Q_reg;

endmodule
module DFFRE (Q, D, CLK, CE, RESET);

input D, CLK, RESET, CE;
output Q;

parameter INIT = 1'b0;
reg Q_reg;
wire gsrt = GSR.GSRO;

initial Q_reg = INIT;

always @(gsrt) begin
	if(!gsrt)
		assign Q_reg = INIT;
	else
		deassign Q_reg;
end

always @(posedge CLK) begin
	if (RESET)
		Q_reg <= 1'b0;
	else if (CE)
		Q_reg <= D;
end

assign Q = Q_reg;

endmodule
module DFFSE (Q, D, CLK, CE, SET);

input D, CLK, SET, CE;
output Q;

parameter INIT = 1'b1;
reg Q_reg;
wire gsrt = GSR.GSRO;

initial Q_reg = INIT;

always @(gsrt)begin
	if(!gsrt)
		assign Q_reg = INIT;
	else
		deassign Q_reg;
end

always @(posedge CLK) begin
	if (SET)
		Q_reg <= 1'b1;
	else if (CE)
		Q_reg <= D;
end

assign Q = Q_reg;

endmodule
module DPX9B (DOA, DOB, DIA, DIB, BLKSELA, BLKSELB, ADA, ADB, WREA, WREB, CLKA, CLKB, CEA, CEB, OCEA, OCEB, RESETA, RESETB);

parameter READ_MODE0 = 1'b0; // 1'b0: bypass mode; 1'b1: pipeline mode
parameter READ_MODE1 = 1'b0; // 1'b0: bypass mode; 1'b1: pipeline mode
parameter WRITE_MODE0 = 2'b00; // 2'b00: normal mode; 2'b01: write-through mode; 2'b10: read-before-write mode
parameter WRITE_MODE1 = 2'b00; // 2'b00: normal mode; 2'b01: write-through mode; 2'b10: read-before-write mode
parameter BIT_WIDTH_0 = 18; // 9, 18
parameter BIT_WIDTH_1 = 18; // 9, 18
parameter BLK_SEL_0 = 3'b000;
parameter BLK_SEL_1 = 3'b000;
parameter RESET_MODE = "SYNC"; //SYNC,ASYNC
parameter INIT_RAM_00 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000; 
parameter INIT_RAM_01 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_02 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_03 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_04 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_05 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_06 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_07 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_08 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_09 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0A = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0B = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0C = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0D = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0E = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0F = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_10 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_11 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_12 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_13 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_14 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_15 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_16 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_17 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_18 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_19 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1A = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1B = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1C = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1D = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1E = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1F = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_20 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_21 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_22 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_23 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_24 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_25 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_26 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_27 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_28 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_29 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2A = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2B = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2C = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2D = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2E = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2F = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_30 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_31 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_32 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_33 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_34 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_35 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_36 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_37 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_38 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_39 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3A = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3B = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3C = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3D = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3E = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3F = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;

input CLKA, CEA, CLKB, CEB;
input OCEA, OCEB; // clock enable of memory output register
input RESETA, RESETB; // resets output registers, not memory contents
input WREA, WREB; // 1'b0: read enabled; 1'b1: write enabled
input [13:0] ADA, ADB;
input [17:0] DIA, DIB;
input [2:0] BLKSELA, BLKSELB;
output [17:0] DOA, DOB;
reg [17:0] bpa_reg, bpb_reg,bpa_reg_async, bpb_reg_async,bpa_reg_sync, bpb_reg_sync;
reg [17:0] pla_reg, plb_reg,pla_reg_async, plb_reg_async,pla_reg_sync, plb_reg_sync;
reg [18431:0] ram_MEM = {INIT_RAM_3F, INIT_RAM_3E, INIT_RAM_3D, INIT_RAM_3C,INIT_RAM_3B, INIT_RAM_3A, INIT_RAM_39, INIT_RAM_38,INIT_RAM_37, INIT_RAM_36, INIT_RAM_35, INIT_RAM_34,INIT_RAM_33, INIT_RAM_32, INIT_RAM_31, INIT_RAM_30,INIT_RAM_2F, INIT_RAM_2E, INIT_RAM_2D, INIT_RAM_2C,INIT_RAM_2B, INIT_RAM_2A, INIT_RAM_29, INIT_RAM_28,INIT_RAM_27, INIT_RAM_26, INIT_RAM_25, INIT_RAM_24,INIT_RAM_23, INIT_RAM_22, INIT_RAM_21, INIT_RAM_20,INIT_RAM_1F, INIT_RAM_1E, INIT_RAM_1D, INIT_RAM_1C,INIT_RAM_1B, INIT_RAM_1A, INIT_RAM_19, INIT_RAM_18,INIT_RAM_17, INIT_RAM_16, INIT_RAM_15, INIT_RAM_14,INIT_RAM_13, INIT_RAM_12, INIT_RAM_11, INIT_RAM_10,INIT_RAM_0F, INIT_RAM_0E, INIT_RAM_0D, INIT_RAM_0C, INIT_RAM_0B, INIT_RAM_0A, INIT_RAM_09, INIT_RAM_08,INIT_RAM_07, INIT_RAM_06, INIT_RAM_05, INIT_RAM_04,INIT_RAM_03, INIT_RAM_02, INIT_RAM_01, INIT_RAM_00};
reg [BIT_WIDTH_0-1:0] mem_a;
reg [BIT_WIDTH_1-1:0] mem_b;
reg mc,bs_ena,bs_enb;
wire pcea,pceb;
integer bit_width_d0 = BIT_WIDTH_0;
integer bit_width_d1 = BIT_WIDTH_1;
integer bit_width_a0, bit_width_a1; // ADDR_WIDTH
reg [14:0] addr_a, addr_b;
wire grstn = GSR.GSRO;

initial begin
    bpa_reg = 0;
    bpb_reg = 0;
    pla_reg = 0;
    plb_reg = 0;
    bpa_reg_async = 0;
    bpa_reg_sync = 0;
    pla_reg_async = 0;
    pla_reg_sync = 0;
    bpb_reg_async = 0;
    bpb_reg_sync = 0;
    plb_reg_async = 0;
    plb_reg_sync = 0;
    mc = 1'b0;
end

initial begin
	case(bit_width_d0)
		9: bit_width_a0 = 11;
		18: bit_width_a0 = 10;
		default: begin
		//	$display ("%d: Unsupported data width\n", bit_width_d0);
		//	$finish;
		end
	endcase
	case(bit_width_d1)
		9: bit_width_a1 = 11;
		18: bit_width_a1 = 10;
		default: begin
		//	$display ("%d: Unsupported data width\n", bit_width_d1);
		//	$finish;
		end
	endcase
end

assign DOA = (READ_MODE0 == 1'b0)? bpa_reg : pla_reg;
assign DOB = (READ_MODE1 == 1'b0)? bpb_reg : plb_reg;

assign pcea = CEA && bs_ena && grstn;
assign pceb = CEB && bs_enb && grstn;
always @ (BLKSELA, BLKSELB)
begin
	if(BLKSELA == BLK_SEL_0) begin
		bs_ena = 1;
	end else begin
		bs_ena = 0;
	end

    if(BLKSELB == BLK_SEL_1) begin
		bs_enb = 1;
	end else begin
		bs_enb = 0;
	end
end

always@(ADA, ADB, bit_width_a0, bit_width_a1,WREA, WREB,mc)begin
    if(bit_width_a0==11)begin
		addr_a[14:0] = ADA[13:3]*bit_width_d0;
		mem_a[8:0]={ ram_MEM[addr_a+8],ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]};
	end
	else if(bit_width_a0==10)begin
		addr_a[14:0] = ADA[13:4]*bit_width_d0;
		mem_a[17:0]={ram_MEM[addr_a+17],ram_MEM[addr_a+16],ram_MEM[addr_a+15],ram_MEM[addr_a+14],ram_MEM[addr_a+13],ram_MEM[addr_a+12],ram_MEM[addr_a+11],ram_MEM[addr_a+10],ram_MEM[addr_a+9],ram_MEM[addr_a+8],ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]};
	end
	
	if(bit_width_a1==11)begin
		addr_b[14:0] = ADB[13:3]*bit_width_d1;
		mem_b[8:0]={ram_MEM[addr_b+8],ram_MEM[addr_b+7],ram_MEM[addr_b+6],ram_MEM[addr_b+5],ram_MEM[addr_b+4],ram_MEM[addr_b+3],ram_MEM[addr_b+2],ram_MEM[addr_b+1],ram_MEM[addr_b]};
	end
	else if(bit_width_a1==10)begin
		addr_b[14:0] = ADB[13:4]*bit_width_d1;
		mem_b[17:0]={ram_MEM[addr_b+17],ram_MEM[addr_b+16],ram_MEM[addr_b+15],ram_MEM[addr_b+14],ram_MEM[addr_b+13],ram_MEM[addr_b+12],ram_MEM[addr_b+11],ram_MEM[addr_b+10],ram_MEM[addr_b+9],ram_MEM[addr_b+8],ram_MEM[addr_b+7],ram_MEM[addr_b+6],ram_MEM[addr_b+5],ram_MEM[addr_b+4],ram_MEM[addr_b+3],ram_MEM[addr_b+2],ram_MEM[addr_b+1],ram_MEM[addr_b]};
	end
end

always @ (bpa_reg_async or bpa_reg_sync or pla_reg_async or pla_reg_sync or bpb_reg_async or bpb_reg_sync or plb_reg_async or plb_reg_sync) begin
    if(RESET_MODE == "ASYNC") begin
        bpa_reg <= bpa_reg_async;
        pla_reg <= pla_reg_async;
        bpb_reg <= bpb_reg_async;
        plb_reg <= plb_reg_async;
    end
    else begin
        bpa_reg <= bpa_reg_sync;
        pla_reg <= pla_reg_sync;
        bpb_reg <= bpb_reg_sync;
        plb_reg <= plb_reg_sync;
    end
end

always @(posedge CLKA) begin
	if (pcea) begin
		if (WREA) begin
			if (bit_width_d0 == 9)
				{ ram_MEM[addr_a+8],ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a] } <= DIA[8:0];
			else if(bit_width_d0 == 18) begin
				if(ADA[0] == 1'b1)
					{ ram_MEM[addr_a+8],ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a] } <= DIA[8:0];
				if(ADA[1] == 1'b1)
					{ ram_MEM[addr_a+17],ram_MEM[addr_a+16],ram_MEM[addr_a+15],ram_MEM[addr_a+14],ram_MEM[addr_a+13],ram_MEM[addr_a+12],ram_MEM[addr_a+11],ram_MEM[addr_a+10],ram_MEM[addr_a+9]} <= DIA[17:9];
			end
			mc <= ~mc;
		end
	end
end

always @(posedge CLKA or posedge RESETA or negedge grstn) begin
	if (!grstn) begin
		pla_reg_async <= 0;
		bpa_reg_async <= 0;
	end else if (RESETA) begin
		pla_reg_async <= 0;
		bpa_reg_async <= 0;
	end else begin
		if(OCEA) begin
			pla_reg_async <= bpa_reg;
		end
		if (pcea) begin
			if (WREA) begin
				if (WRITE_MODE0 == 2'b01) begin
					bpa_reg_async[BIT_WIDTH_0-1:0] <= mem_a[BIT_WIDTH_0-1:0];
                    if (bit_width_d0 == 9)
					    bpa_reg_async[8:0] <= DIA[8:0];
				    else if(bit_width_d0 == 18) begin
					    if(ADA[0] == 1'b1)
						    bpa_reg_async[8:0] <= DIA[8:0];
					    if(ADA[1] == 1'b1)
						    bpa_reg_async[17:9] <= DIA[17:9];
				    end
				end

				if (WRITE_MODE0 == 2'b10) begin
					bpa_reg_async[BIT_WIDTH_0-1:0] <= mem_a[BIT_WIDTH_0-1:0];
				end

			end else begin // WREA==0, read
				bpa_reg_async[BIT_WIDTH_0-1:0] <= mem_a[BIT_WIDTH_0-1:0];
			end

		end
	end
end

always @(posedge CLKA or negedge grstn) begin
	if (!grstn) begin
		pla_reg_sync <= 0;
		bpa_reg_sync <= 0;
	end else if (RESETA) begin
		pla_reg_sync <= 0;
		bpa_reg_sync <= 0;
	end else begin	
		if(OCEA) begin
			pla_reg_sync <= bpa_reg;
		end
		if (pcea) begin
			if (WREA) begin
				if (WRITE_MODE0 == 2'b01) begin
					bpa_reg_sync[BIT_WIDTH_0-1:0] <= mem_a[BIT_WIDTH_0-1:0];
                    if (bit_width_d0 == 9)
					    bpa_reg_sync[8:0] <= DIA[8:0];
				    else if(bit_width_d0 == 18) begin
					    if(ADA[0] == 1'b1)
						    bpa_reg_sync[8:0] <= DIA[8:0];
					    if(ADA[1] == 1'b1)
						    bpa_reg_sync[17:9] <= DIA[17:9];
				    end
				end

				if (WRITE_MODE0 == 2'b10) begin
					bpa_reg_sync[BIT_WIDTH_0-1:0] <= mem_a[BIT_WIDTH_0-1:0];
				end

			end else begin // WREA==0, read
				bpa_reg_sync[BIT_WIDTH_0-1:0] <= mem_a[BIT_WIDTH_0-1:0];
			end

		end
	end
end

always @(posedge CLKB) begin
	if (pceb) begin
		if (WREB) begin
			if (bit_width_d1 == 9)
				{ ram_MEM[addr_b+8],ram_MEM[addr_b+7],ram_MEM[addr_b+6],ram_MEM[addr_b+5],ram_MEM[addr_b+4],ram_MEM[addr_b+3],ram_MEM[addr_b+2],ram_MEM[addr_b+1],ram_MEM[addr_b] } <= DIB[8:0];
			else if(bit_width_d1 == 18) begin
				if(ADB[0] == 1'b1)
					{ ram_MEM[addr_b+8],ram_MEM[addr_b+7],ram_MEM[addr_b+6],ram_MEM[addr_b+5],ram_MEM[addr_b+4],ram_MEM[addr_b+3],ram_MEM[addr_b+2],ram_MEM[addr_b+1],ram_MEM[addr_b] } <= DIB[8:0];
				if(ADB[1] == 1'b1)
					{ram_MEM[addr_b+17],ram_MEM[addr_b+16],ram_MEM[addr_b+15],ram_MEM[addr_b+14],ram_MEM[addr_b+13],ram_MEM[addr_b+12],ram_MEM[addr_b+11],ram_MEM[addr_b+10], ram_MEM[addr_b+9]} <= DIB[17:9];
			end
			mc <= ~mc;
		end
	end
end

always @(posedge CLKB or posedge RESETB or negedge grstn) begin
	if (!grstn) begin
		plb_reg_async <= 0;
		bpb_reg_async <= 0;
	end else if (RESETB) begin
		plb_reg_async <= 0;
		bpb_reg_async <= 0;
	end else begin
		if(OCEB) begin
			plb_reg_async <= bpb_reg;
		end
		if (pceb) begin
			if (WREB) begin
				if (WRITE_MODE1 == 2'b01) begin
					bpb_reg_async[BIT_WIDTH_1-1:0] <= mem_b[BIT_WIDTH_1-1:0];
                    if (bit_width_d1 == 9)
					    bpb_reg_async[8:0] <= DIB[8:0];
				    else if(bit_width_d1 == 18) begin
					    if(ADB[0] == 1'b1)
						    bpb_reg_async[8:0] <= DIB[8:0];
				    	if(ADB[1] == 1'b1)
						    bpb_reg_async[17:9] <= DIB[17:9];
				    end
				end

				if (WRITE_MODE1 == 2'b10) begin
					bpb_reg_async[BIT_WIDTH_1-1:0] <= mem_b[BIT_WIDTH_1-1:0];
				end

			end else begin
				bpb_reg_async[BIT_WIDTH_1-1:0] <= mem_b[BIT_WIDTH_1-1:0];
			end
		end
	end
end

always @(posedge CLKB or negedge grstn) begin
	if (!grstn) begin
		plb_reg_sync <= 0;
		bpb_reg_sync <= 0;
	end else if (RESETB) begin
		plb_reg_sync <= 0;
		bpb_reg_sync <= 0;
	end else begin
		if(OCEB) begin
			plb_reg_sync <= bpb_reg;
		end
		if (pceb) begin
			if (WREB) begin
				if (WRITE_MODE1 == 2'b01) begin
					bpb_reg_sync[BIT_WIDTH_1-1:0] <= mem_b[BIT_WIDTH_1-1:0];
                    if (bit_width_d1 == 9)
					    bpb_reg_sync[8:0] <= DIB[8:0];
				    else if(bit_width_d1 == 18) begin
					    if(ADB[0] == 1'b1)
						    bpb_reg_sync[8:0] <= DIB[8:0];
				    	if(ADB[1] == 1'b1)
						    bpb_reg_sync[17:9] <= DIB[17:9];
				    end
				end

				if (WRITE_MODE1 == 2'b10) begin
					bpb_reg_sync[BIT_WIDTH_1-1:0] <= mem_b[BIT_WIDTH_1-1:0];
				end

			end else begin
				bpb_reg_sync[BIT_WIDTH_1-1:0] <= mem_b[BIT_WIDTH_1-1:0];
			end
		end
	end
end

endmodule
module GND (G);

output G;

wire G;

assign G = 1'b0;

endmodule
module GSR (GSRI);

input GSRI;

wire GSRO;

assign GSRO = GSRI;

endmodule
module INV (O, I);

input  I;
output O;

assign O = !I;
        
endmodule
module LUT2 (F, I0, I1);

parameter INIT = 4'h0;

input I0, I1;
output F;

MUX4 lut_2 (F, INIT[0], INIT[1], INIT[2], INIT[3], I0, I1);

endmodule
module LUT3 (F, I0, I1, I2);

parameter INIT = 8'h00;

input I0, I1, I2;
output F;

MUX8 lut_3 (F, INIT[0], INIT[1], INIT[2], INIT[3], INIT[4], INIT[5], INIT[6], INIT[7], I0, I1, I2);

endmodule
module LUT4 (F, I0, I1, I2, I3);

parameter INIT = 16'h0000;

input I0, I1, I2, I3;
output F;

MUX16 lut_4(F, INIT[0], INIT[1], INIT[2], INIT[3], INIT[4], INIT[5], INIT[6], INIT[7], INIT[8], INIT[9], INIT[10], INIT[11], INIT[12], INIT[13], INIT[14], INIT[15], I0, I1, I2, I3);

endmodule
module MULT12X12 (DOUT, A, B, CLK, CE, RESET);

parameter AREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter AREG_CE = "CE0"; // "CE0","CE1"
parameter AREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter BREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter BREG_CE = "CE0"; // "CE0","CE1"
parameter BREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter PREG_CE = "CE0"; // "CE0","CE1"
parameter PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter OREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter OREG_CE = "CE0"; // "CE0","CE1"
parameter OREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter MULT_RESET_MODE = "SYNC";// SYNC,ASYNC

output [23:0] DOUT;
input  [11:0] A, B;
input  [1:0] CLK, CE, RESET;

reg A_CLK,A_CE,A_RESET,B_CLK,B_CE,B_RESET,P_CLK,P_CE,P_RESET,O_CLK,O_CE,O_RESET;
reg [11:0] ina_reg_async,ina_reg_sync,ina,ina_reg;
reg [11:0] inb_reg_async,inb_reg_sync,inb,inb_reg;
wire [23:0] a0,b0,mult_out0;
reg [23:0] out0_reg_async,out0_reg_sync,out0,out0_reg;
wire [23:0] m_out0;
reg [23:0] out_reg_async,out_reg_sync,out_reg,d_out;

wire grstn = GSR.GSRO;


    always @(ina_reg_async or ina_reg_sync or inb_reg_async or inb_reg_sync or out0_reg_async or out0_reg_sync or out_reg_sync or out_reg_async)
    begin
        if (MULT_RESET_MODE == "ASYNC")
        begin
            ina_reg <= ina_reg_async;
            inb_reg <= inb_reg_async;
            out0_reg <= out0_reg_async;
            out_reg <= out_reg_async;
        end
        else if (MULT_RESET_MODE == "SYNC")
        begin
            ina_reg <= ina_reg_sync;
            inb_reg <= inb_reg_sync;
            out0_reg <= out0_reg_sync;
            out_reg <= out_reg_sync;
        end
    end

    //clk,ce,reset mux
    //AREG
    always @(CLK)
    begin
        if (AREG_CLK == "CLK0")
            A_CLK = CLK[0];
        else if (AREG_CLK == "CLK1")
            A_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (AREG_CE == "CE0")
            A_CE = CE[0];
        else if (AREG_CE == "CE1")
            A_CE = CE[1];
    end

    always @(RESET)
    begin
        if (AREG_RESET == "RESET0")
            A_RESET = RESET[0];
        else if (AREG_RESET == "RESET1")
            A_RESET = RESET[1];
    end

    //BREG
    always @(CLK)
    begin
        if (BREG_CLK == "CLK0")
            B_CLK = CLK[0];
        else if (BREG_CLK == "CLK1")
            B_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (BREG_CE == "CE0")
            B_CE = CE[0];
        else if (BREG_CE == "CE1")
            B_CE = CE[1];
    end

    always @(RESET)
    begin
        if (BREG_RESET == "RESET0")
            B_RESET = RESET[0];
        else if (BREG_RESET == "RESET1")
            B_RESET = RESET[1];
    end

    //PREG
    always @(CLK)
    begin
        if (PREG_CLK == "CLK0")
            P_CLK = CLK[0];
        else if (PREG_CLK == "CLK1")
            P_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (PREG_CE == "CE0")
            P_CE = CE[0];
        else if (PREG_CE == "CE1")
            P_CE = CE[1];
    end

    always @(RESET)
    begin
        if (PREG_RESET == "RESET0")
            P_RESET = RESET[0];
        else if (PREG_RESET == "RESET1")
            P_RESET = RESET[1];
    end

    //OREG
    always @(CLK)
    begin
        if (OREG_CLK == "CLK0")
            O_CLK = CLK[0];
        else if (OREG_CLK == "CLK1")
            O_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (OREG_CE == "CE0")
            O_CE = CE[0];
        else if (OREG_CE == "CE1")
            O_CE = CE[1];
    end

    always @(RESET)
    begin
        if (OREG_RESET == "RESET0")
            O_RESET = RESET[0];
        else if (OREG_RESET == "RESET1")
            O_RESET = RESET[1];
    end

    // in reg
    always @(posedge A_CLK or posedge A_RESET or negedge grstn)
    begin
        if (!grstn) begin
            ina_reg_async <= 0;
        end else if (A_RESET == 1'b1)
        begin
            ina_reg_async <= 0;
        end
        else if (A_CE == 1'b1)
        begin
            ina_reg_async <= A;
        end
    end

    always @(posedge A_CLK or negedge grstn)
    begin
        if (!grstn) begin
            ina_reg_sync <= 0; 
        end else if (A_RESET == 1'b1)
        begin
            ina_reg_sync <= 0;
        end
        else if (A_CE == 1'b1)
        begin
            ina_reg_sync <= A;
        end
    end

    always @(A or ina_reg)
    begin
        if (AREG_CLK == "BYPASS")
        begin
            ina = A;
        end else
        begin
            ina = ina_reg;
        end
    end

    always @(posedge B_CLK or posedge B_RESET or negedge grstn)
    begin
        if (!grstn) begin
            inb_reg_async <= 0;
        end else if (B_RESET == 1'b1)
        begin
            inb_reg_async <= 0;
        end
        else if (B_CE == 1'b1)
        begin
            inb_reg_async <= B;
        end
    end

    always @(posedge B_CLK or negedge grstn)
    begin
        if (!grstn) begin
            inb_reg_sync <= 0; 
        end else if (B_RESET == 1'b1)
        begin
            inb_reg_sync <= 0;
        end
        else if (B_CE == 1'b1)
        begin
            inb_reg_sync <= B;
        end
    end

    always @(B or inb_reg)
    begin
        if (BREG_CLK == "BYPASS")
        begin
            inb = B;
        end else
        begin
            inb = inb_reg;
        end
    end

    assign a0[23:0] = {{12{ina[11]}},ina[11:0]};
    assign b0[23:0] = {{12{inb[11]}},inb[11:0]};

    assign mult_out0 = a0 * b0 ;

    // pipeline reg
    always @(posedge P_CLK or posedge P_RESET or negedge grstn)
    begin
        if (!grstn) begin
            out0_reg_async <= 0;
        end else if (P_RESET == 1'b1)
        begin
            out0_reg_async <= 0;
        end
        else if (P_CE == 1'b1)
        begin
            out0_reg_async <= mult_out0;
        end
    end

    always @(posedge P_CLK or negedge grstn)
    begin
        if (!grstn) begin
            out0_reg_sync <= 0;
        end else if (P_RESET == 1'b1)
        begin
            out0_reg_sync <= 0;
        end
        else if (P_CE == 1'b1)
        begin
            out0_reg_sync <= mult_out0;
        end
    end

    always @(mult_out0 or out0_reg)
    begin
        if (PREG_CLK == "BYPASS")
        begin
            out0 = mult_out0;
        end else
        begin
            out0 = out0_reg;
        end
    end

    // output reg
    always @(posedge O_CLK or posedge O_RESET or negedge grstn)
    begin
        if (!grstn) begin
            out_reg_async <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_reg_async <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_reg_async <= out0;
        end
    end

    always @(posedge O_CLK or negedge grstn)
    begin
        if (!grstn) begin
            out_reg_sync <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_reg_sync <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_reg_sync <= out0;
        end
    end

    always @(out0 or out_reg)
    begin
        if (OREG_CLK == "BYPASS")
        begin
            d_out = out0;
        end else
        begin
            d_out = out_reg;
        end
    end

    assign DOUT = d_out[23:0];

endmodule
module MULT27X36 (DOUT, A, B, D, PSEL, PADDSUB, CLK, CE, RESET);

parameter AREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter AREG_CE = "CE0"; // "CE0","CE1"
parameter AREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter BREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter BREG_CE = "CE0"; // "CE0","CE1"
parameter BREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter DREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter DREG_CE = "CE0"; // "CE0","CE1"
parameter DREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter PADDSUB_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter PADDSUB_IREG_CE = "CE0"; // "CE0","CE1"
parameter PADDSUB_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter PREG_CE = "CE0"; // "CE0","CE1"
parameter PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter PSEL_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter PSEL_IREG_CE = "CE0"; // "CE0","CE1"
parameter PSEL_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter OREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter OREG_CE = "CE0"; // "CE0","CE1"
parameter OREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter MULT_RESET_MODE = "SYNC";// SYNC,ASYNC
parameter DYN_P_SEL = "FALSE";//"TRUE","FALSE"
parameter P_SEL = 1'b0;//1'b0: select direct INA; 1'b1: select preadder
parameter DYN_P_ADDSUB = "FALSE";//"TRUE","FALSE"
parameter P_ADDSUB = 1'b0;//1'b0:add; 1'b1:sub

output [62:0] DOUT;
input  [26:0] A;
input  [35:0] B;
input  [25:0] D;
input  [1:0] CLK, CE, RESET;
input  PSEL;
input  PADDSUB;

reg A_CLK,A_CE,A_RESET,B_CLK,B_CE,B_RESET,D_CLK,D_CE,D_RESET,PADDSUB_ICLK,PADDSUB_ICE,PADDSUB_IRESET,PSEL_ICLK,PSEL_ICE,PSEL_IRESET,P_CLK,P_CE,P_RESET,O_CLK,O_CE,O_RESET;
reg [26:0] ina_reg_async,ina_reg_sync,ina,ina_reg,a_in;
reg [35:0] inb_reg_async,inb_reg_sync,inb,inb_reg;
reg [25:0] ind_reg_async,ind_reg_sync,ind,ind_reg;
wire [26:0] ina_ext,ind_ext;
wire [62:0] a0,b0,mult_out0;
reg [62:0] out0_reg_async,out0_reg_sync,out0,out0_reg;
reg [62:0] out_reg_async,out_reg_sync,out_reg,d_out;
wire preadd_en,p_addsub_sig;
reg paddsub_reg0_async,paddsub_reg0_sync,paddsub_reg0,paddsub_0;
reg psel_reg_async,psel_reg_sync,psel_reg,psel_0;

wire grstn = GSR.GSRO;


always @(ina_reg_async or ina_reg_sync or inb_reg_async or inb_reg_sync or ind_reg_async or ind_reg_sync or paddsub_reg0_async or paddsub_reg0_sync or psel_reg_async or psel_reg_sync or out0_reg_async or out0_reg_sync or out_reg_sync or out_reg_async)
    begin
        if (MULT_RESET_MODE == "ASYNC")
        begin
            ina_reg <= ina_reg_async;
            inb_reg <= inb_reg_async;
            ind_reg <= ind_reg_async;
            paddsub_reg0 <= paddsub_reg0_async;
            psel_reg <= psel_reg_async;
            out0_reg <= out0_reg_async;
            out_reg <= out_reg_async;
        end
        else if (MULT_RESET_MODE == "SYNC")
        begin
            ina_reg <= ina_reg_sync;
            inb_reg <= inb_reg_sync;
            ind_reg <= ind_reg_sync;
            paddsub_reg0 <= paddsub_reg0_sync;
            psel_reg <= psel_reg_sync;
            out0_reg <= out0_reg_sync;
            out_reg <= out_reg_sync;
        end
    end

    //clk,ce,reset mux
    //AREG
    always @(CLK)
    begin
        if (AREG_CLK == "CLK0")
            A_CLK = CLK[0];
        else if (AREG_CLK == "CLK1")
            A_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (AREG_CE == "CE0")
            A_CE = CE[0];
        else if (AREG_CE == "CE1")
            A_CE = CE[1];
    end

    always @(RESET)
    begin
        if (AREG_RESET == "RESET0")
            A_RESET = RESET[0];
        else if (AREG_RESET == "RESET1")
            A_RESET = RESET[1];
    end

    //BREG
    always @(CLK)
    begin
        if (BREG_CLK == "CLK0")
            B_CLK = CLK[0];
        else if (BREG_CLK == "CLK1")
            B_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (BREG_CE == "CE0")
            B_CE = CE[0];
        else if (BREG_CE == "CE1")
            B_CE = CE[1];
    end

    always @(RESET)
    begin
        if (BREG_RESET == "RESET0")
            B_RESET = RESET[0];
        else if (BREG_RESET == "RESET1")
            B_RESET = RESET[1];
    end

    //DREG
    always @(CLK)
    begin
        if (DREG_CLK == "CLK0")
            D_CLK = CLK[0];
        else if (DREG_CLK == "CLK1")
            D_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (DREG_CE == "CE0")
            D_CE = CE[0];
        else if (DREG_CE == "CE1")
            D_CE = CE[1];
    end

    always @(RESET)
    begin
        if (DREG_RESET == "RESET0")
            D_RESET = RESET[0];
        else if (DREG_RESET == "RESET1")
            D_RESET = RESET[1];
    end

    //PADDSUB_IREG
    always @(CLK)
    begin
        if (PADDSUB_IREG_CLK == "CLK0")
            PADDSUB_ICLK = CLK[0];
        else if (PADDSUB_IREG_CLK == "CLK1")
            PADDSUB_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (PADDSUB_IREG_CE == "CE0")
            PADDSUB_ICE = CE[0];
        else if (PADDSUB_IREG_CE == "CE1")
            PADDSUB_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (PADDSUB_IREG_RESET == "RESET0")
            PADDSUB_IRESET = RESET[0];
        else if (PADDSUB_IREG_RESET == "RESET1")
            PADDSUB_IRESET = RESET[1];
    end

    //PSEL_IREG
    always @(CLK)
    begin
        if (PSEL_IREG_CLK == "CLK0")
            PSEL_ICLK = CLK[0];
        else if (PSEL_IREG_CLK == "CLK1")
            PSEL_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (PSEL_IREG_CE == "CE0")
            PSEL_ICE = CE[0];
        else if (PSEL_IREG_CE == "CE1")
            PSEL_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (PSEL_IREG_RESET == "RESET0")
            PSEL_IRESET = RESET[0];
        else if (PSEL_IREG_RESET == "RESET1")
            PSEL_IRESET = RESET[1];
    end


    //PREG
    always @(CLK)
    begin
        if (PREG_CLK == "CLK0")
            P_CLK = CLK[0];
        else if (PREG_CLK == "CLK1")
            P_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (PREG_CE == "CE0")
            P_CE = CE[0];
        else if (PREG_CE == "CE1")
            P_CE = CE[1];
    end

    always @(RESET)
    begin
        if (PREG_RESET == "RESET0")
            P_RESET = RESET[0];
        else if (PREG_RESET == "RESET1")
            P_RESET = RESET[1];
    end

    //OREG
    always @(CLK)
    begin
        if (OREG_CLK == "CLK0")
            O_CLK = CLK[0];
        else if (OREG_CLK == "CLK1")
            O_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (OREG_CE == "CE0")
            O_CE = CE[0];
        else if (OREG_CE == "CE1")
            O_CE = CE[1];
    end

    always @(RESET)
    begin
        if (OREG_RESET == "RESET0")
            O_RESET = RESET[0];
        else if (OREG_RESET == "RESET1")
            O_RESET = RESET[1];
    end

    // in reg
    always @(posedge A_CLK or posedge A_RESET or negedge grstn)
    begin
        if (!grstn) begin
            ina_reg_async <= 0;
        end else if (A_RESET == 1'b1)
        begin
            ina_reg_async <= 0;
        end
        else if (A_CE == 1'b1)
        begin
            ina_reg_async <= A;
        end
    end

    always @(posedge A_CLK or negedge grstn)
    begin
        if (!grstn) begin
            ina_reg_sync <= 0; 
        end else if (A_RESET == 1'b1)
        begin
            ina_reg_sync <= 0;
        end
        else if (A_CE == 1'b1)
        begin
            ina_reg_sync <= A;
        end
    end

    always @(A or ina_reg)
    begin
        if (AREG_CLK == "BYPASS")
        begin
            ina = A;
        end else
        begin
            ina = ina_reg;
        end
    end

    always @(posedge B_CLK or posedge B_RESET or negedge grstn)
    begin
        if (!grstn) begin
            inb_reg_async <= 0;
        end else if (B_RESET == 1'b1)
        begin
            inb_reg_async <= 0;
        end
        else if (B_CE == 1'b1)
        begin
            inb_reg_async <= B;
        end
    end

    always @(posedge B_CLK or negedge grstn)
    begin
        if (!grstn) begin
            inb_reg_sync <= 0; 
        end else if (B_RESET == 1'b1)
        begin
            inb_reg_sync <= 0;
        end
        else if (B_CE == 1'b1)
        begin
            inb_reg_sync <= B;
        end
    end

    always @(B or inb_reg)
    begin
        if (BREG_CLK == "BYPASS")
        begin
            inb = B;
        end else
        begin
            inb = inb_reg;
        end
    end

    always @(posedge D_CLK or posedge D_RESET or negedge grstn)
    begin
        if (!grstn) begin
            ind_reg_async <= 0;
        end else if (D_RESET == 1'b1)
        begin
            ind_reg_async <= 0;
        end
        else if (D_CE == 1'b1)
        begin
            ind_reg_async <= D;
        end
    end

    always @(posedge D_CLK or negedge grstn)
    begin
        if (!grstn) begin
            ind_reg_sync <= 0; 
        end else if (D_RESET == 1'b1)
        begin
            ind_reg_sync <= 0;
        end
        else if (D_CE == 1'b1)
        begin
            ind_reg_sync <= D;
        end
    end

    always @(D or ind_reg)
    begin
        if (DREG_CLK == "BYPASS")
        begin
            ind = D;
        end else
        begin
            ind = ind_reg;
        end
    end

    //PADD or not
    assign ina_ext = {ina[25],ina[25:0]};
    assign ind_ext = {ind[25],ind[25:0]};

    assign preadd_en = (DYN_P_SEL == "TRUE")? PSEL : ((P_SEL == 1'b1)? 1'b1 : 1'b0);
    assign p_addsub_sig = (DYN_P_ADDSUB == "TRUE")? PADDSUB : P_ADDSUB;

    always @(posedge PADDSUB_ICLK or posedge PADDSUB_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            paddsub_reg0_async <= 0;
        end else if (PADDSUB_IRESET == 1'b1)
        begin
            paddsub_reg0_async <= 0;
        end
        else if (PADDSUB_ICE == 1'b1)
        begin
            paddsub_reg0_async <= p_addsub_sig;
        end
    end

    always @(posedge PADDSUB_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            paddsub_reg0_sync <= 0;
        end else if (PADDSUB_IRESET == 1'b1)
        begin
            paddsub_reg0_sync <= 0;
        end
        else if (PADDSUB_ICE == 1'b1)
        begin
            paddsub_reg0_sync <= p_addsub_sig;
        end
    end

    always @(p_addsub_sig or paddsub_reg0)
    begin
        if (PADDSUB_IREG_CLK == "BYPASS")
        begin
            paddsub_0 <= p_addsub_sig;
        end else
        begin
            paddsub_0 <= paddsub_reg0;
        end
    end

    always @(posedge PSEL_ICLK or posedge PSEL_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            psel_reg_async <= 0;
        end else if (PSEL_IRESET == 1'b1)
        begin
            psel_reg_async <= 0;
        end
        else if (PSEL_ICE == 1'b1)
        begin
            psel_reg_async <= preadd_en;
        end
    end

    always @(posedge PSEL_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            psel_reg_sync <= 0;
        end else if (PSEL_IRESET == 1'b1)
        begin
            psel_reg_sync <= 0;
        end
        else if (PSEL_ICE == 1'b1)
        begin
            psel_reg_sync <= preadd_en;
        end
    end

    always @(preadd_en or psel_reg)
    begin
        if (PSEL_IREG_CLK == "BYPASS")
        begin
            psel_0 <= preadd_en;
        end else
        begin
            psel_0 <= psel_reg;
        end
    end

    always@(ina_ext or ind_ext or ina or psel_0 or paddsub_0)
    begin
        if(psel_0 == 1'b1)
        begin
            if(paddsub_0 == 1'b0) begin
                a_in = ina_ext + ind_ext;
            end else begin
                a_in = ina_ext - ind_ext;
            end
        end else begin
            a_in = ina;
        end
    end

    assign a0[62:0] = {{36{a_in[26]}},a_in[26:0]};
    assign b0[62:0] = {{27{inb[35]}},inb[35:0]};

    assign mult_out0 = a0 * b0 ;

    // pipeline reg
    always @(posedge P_CLK or posedge P_RESET or negedge grstn)
    begin
        if (!grstn) begin
            out0_reg_async <= 0;
        end else if (P_RESET == 1'b1)
        begin
            out0_reg_async <= 0;
        end
        else if (P_CE == 1'b1)
        begin
            out0_reg_async <= mult_out0;
        end
    end

    always @(posedge P_CLK or negedge grstn)
    begin
        if (!grstn) begin
            out0_reg_sync <= 0;
        end else if (P_RESET == 1'b1)
        begin
            out0_reg_sync <= 0;
        end
        else if (P_CE == 1'b1)
        begin
            out0_reg_sync <= mult_out0;
        end
    end

    always @(mult_out0 or out0_reg)
    begin
        if (PREG_CLK == "BYPASS")
        begin
            out0 = mult_out0;
        end else
        begin
            out0 = out0_reg;
        end
    end

    // output reg
    always @(posedge O_CLK or posedge O_RESET or negedge grstn)
    begin
        if (!grstn) begin
            out_reg_async <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_reg_async <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_reg_async <= out0;
        end
    end

    always @(posedge O_CLK or negedge grstn)
    begin
        if (!grstn) begin
            out_reg_sync <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_reg_sync <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_reg_sync <= out0;
        end
    end

    always @(out0 or out_reg)
    begin
        if (OREG_CLK == "BYPASS")
        begin
            d_out = out0;
        end else
        begin
            d_out = out_reg;
        end
    end

    assign DOUT = d_out[62:0];

endmodule
module MULTADDALU12X12 (DOUT, CASO, A0, B0, A1, B1, CASI, ACCSEL, CASISEL, ADDSUB, CLK, CE, RESET);

parameter A0REG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter A0REG_CE = "CE0"; // "CE0","CE1"
parameter A0REG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter A1REG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter A1REG_CE = "CE0"; // "CE0","CE1"
parameter A1REG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter B0REG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter B0REG_CE = "CE0"; // "CE0","CE1"
parameter B0REG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter B1REG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter B1REG_CE = "CE0"; // "CE0","CE1"
parameter B1REG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter ACCSEL_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ACCSEL_IREG_CE = "CE0"; // "CE0","CE1"
parameter ACCSEL_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter CASISEL_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter CASISEL_IREG_CE = "CE0"; // "CE0","CE1"
parameter CASISEL_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter ADDSUB0_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ADDSUB0_IREG_CE = "CE0"; // "CE0","CE1"
parameter ADDSUB0_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter ADDSUB1_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ADDSUB1_IREG_CE = "CE0"; // "CE0","CE1"
parameter ADDSUB1_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter PREG0_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"     //mult0 pipeline register
parameter PREG0_CE = "CE0"; // "CE0","CE1"
parameter PREG0_RESET = "RESET0"; //"RESET0", "RESET1"

parameter PREG1_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"     //mult1 pipeline register
parameter PREG1_CE = "CE0"; // "CE0","CE1"
parameter PREG1_RESET = "RESET0"; //"RESET0", "RESET1"

parameter FB_PREG_EN = "FALSE"; // "FALSE";"TRUE"      //feedback acc pipeline register,same clk/ce/reset as OREG

parameter ACCSEL_PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ACCSEL_PREG_CE = "CE0"; // "CE0","CE1"
parameter ACCSEL_PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter CASISEL_PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter CASISEL_PREG_CE = "CE0"; // "CE0","CE1"
parameter CASISEL_PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter ADDSUB0_PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ADDSUB0_PREG_CE = "CE0"; // "CE0","CE1"
parameter ADDSUB0_PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter ADDSUB1_PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ADDSUB1_PREG_CE = "CE0"; // "CE0","CE1"
parameter ADDSUB1_PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter OREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter OREG_CE = "CE0"; // "CE0","CE1"
parameter OREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter MULT_RESET_MODE = "SYNC";// SYNC,ASYNC
parameter PRE_LOAD = 48'h000000000000;
parameter DYN_ADD_SUB_0 = "FALSE";//"TRUE","FALSE"
parameter ADD_SUB_0 = 1'b0;//1'b0: '+'; 1'b1: '-'
parameter DYN_ADD_SUB_1 = "FALSE";//"TRUE","FALSE"
parameter ADD_SUB_1 = 1'b0;//1'b0: '+'; 1'b1: '-'

parameter DYN_CASI_SEL = "FALSE";//"TRUE","FALSE"
parameter CASI_SEL = 1'b0;//1'b0: select 0; 1'b1:select casi
parameter DYN_ACC_SEL = "FALSE";//"TRUE","FALSE"
parameter ACC_SEL = 1'b0;//1'b0: PRE_LOAD;1'b1: DOUT feedback;

output [47:0] DOUT, CASO;
input  [11:0] A0, B0, A1, B1;
input  [47:0] CASI;
input  ACCSEL;
input  CASISEL;
input  [1:0] ADDSUB;
input  [1:0] CLK, CE, RESET;

reg A0_CLK,A0_CE,A0_RESET,A1_CLK,A1_CE,A1_RESET,B0_CLK,B0_CE,B0_RESET,B1_CLK,B1_CE,B1_RESET,ACCSEL_ICLK,ACCSEL_ICE,ACCSEL_IRESET,CASISEL_ICLK,CASISEL_ICE,CASISEL_IRESET,ADDSUB0_ICLK,ADDSUB0_ICE,ADDSUB0_IRESET,ADDSUB1_ICLK,ADDSUB1_ICE,ADDSUB1_IRESET,P0_CLK,P0_CE,P0_RESET,P1_CLK,P1_CE,P1_RESET,ACCSEL_PCLK,ACCSEL_PCE,ACCSEL_PRESET,CASISEL_PCLK,CASISEL_PCE,CASISEL_PRESET,ADDSUB0_PCLK,ADDSUB0_PCE,ADDSUB0_PRESET,ADDSUB1_PCLK,ADDSUB1_PCE,ADDSUB1_PRESET,O_CLK,O_CE,O_RESET;
reg [11:0] ina0_reg_async,ina0_reg_sync,ina1_reg_async,ina1_reg_sync,ina0,ina0_reg,ina1,ina1_reg,ina_preg_async,ina_preg_sync,ina_preg,a_src;
reg [11:0] inb0_reg_async,inb0_reg_sync,inb1_reg_async,inb1_reg_sync,inb0,inb0_reg,inb1,inb1_reg;
reg accsel0_reg_async,accsel0_reg_sync,accsel_0,accsel0_reg,accsel1_reg_async,accsel1_reg_sync,accsel_1,accsel1_reg;
reg casisel0_reg_async,casisel0_reg_sync,casisel_0,casisel0_reg,casisel1_reg_async,casisel1_reg_sync,casisel_1,casisel1_reg;
reg addsub0_reg0_async,addsub0_reg0_sync,addsub0_reg0,addsub0_0,addsub0_reg1_async,addsub0_reg1_sync,addsub0_reg1,addsub0_1;
reg addsub1_reg0_async,addsub1_reg0_sync,addsub1_reg0,addsub1_0,addsub1_reg1_async,addsub1_reg1_sync,addsub1_reg1,addsub1_1;
wire [23:0] a0,b0,mult_out0,a1,b1,mult_out1;
reg [23:0] out0_reg_async,out0_reg_sync,out0,out0_reg,out1_reg_async,out1_reg_sync,out1,out1_reg;
reg [48:0] d_out,out_preg_async,out_preg_sync,out_preg,dout_reg,alu_out;
wire [47:0] m_out0,m_out1,acc_load,d_casi;
reg [48:0] out_reg_async,out_reg_sync,out_reg;
wire accsel_sig,casisel_sig,addsub0_sig,addsub1_sig;
reg [1:0] accsel_int;
reg [1:0] accsel_int0_reg_async,accsel_int0_reg_sync,accsel_int0,accsel_int0_reg,accsel_int1_reg_async,accsel_int1_reg_sync,accsel_int1,accsel_int1_reg;


wire grstn = GSR.GSRO;


always @(ina0_reg_async or ina0_reg_sync or ina1_reg_async or ina1_reg_sync or inb0_reg_async or inb0_reg_sync or inb1_reg_async or inb1_reg_sync or ina_preg_async or ina_preg_sync or accsel0_reg_async or accsel0_reg_sync or accsel1_reg_async or accsel1_reg_sync or casisel0_reg_async or casisel0_reg_sync or casisel1_reg_async or casisel1_reg_sync or addsub0_reg0_async or addsub0_reg0_sync or addsub0_reg1_async or addsub0_reg1_sync or addsub1_reg0_async or addsub1_reg0_sync or addsub1_reg1_async or addsub1_reg1_sync or out0_reg_async or out0_reg_sync or out1_reg_async or out1_reg_sync or out_preg_async or out_preg_sync or out_reg_sync or out_reg_async or accsel_int0_reg_async or accsel_int0_reg_sync or accsel_int0_reg or accsel_int1_reg_async or accsel_int1_reg_sync or accsel_int1_reg)
    begin
        if (MULT_RESET_MODE == "ASYNC")
        begin
            ina0_reg <= ina0_reg_async;
            ina1_reg <= ina1_reg_async;
            inb0_reg <= inb0_reg_async;
            inb1_reg <= inb1_reg_async;
            accsel0_reg <= accsel0_reg_async;
            accsel1_reg <= accsel1_reg_async;
            addsub0_reg0 <= addsub0_reg0_async;
            addsub0_reg1 <= addsub0_reg1_async;
            addsub1_reg0 <= addsub1_reg0_async;
            addsub1_reg1 <= addsub1_reg1_async;
            casisel0_reg <= casisel0_reg_async;
            casisel1_reg <= casisel1_reg_async;
            out0_reg <= out0_reg_async;
            out1_reg <= out1_reg_async;
            out_preg <= out_preg_async;
            ina_preg <= ina_preg_async;
            out_reg <= out_reg_async;
            accsel_int0_reg <= accsel_int0_reg_async;
            accsel_int1_reg <= accsel_int1_reg_async;
        end
        else if (MULT_RESET_MODE == "SYNC")
        begin
            ina0_reg <= ina0_reg_sync;
            ina1_reg <= ina1_reg_sync;
            inb0_reg <= inb0_reg_sync;
            inb1_reg <= inb1_reg_sync;
            accsel0_reg <= accsel0_reg_sync;
            accsel1_reg <= accsel1_reg_sync;
            addsub0_reg0 <= addsub0_reg0_sync;
            addsub0_reg1 <= addsub0_reg1_sync;
            addsub1_reg0 <= addsub1_reg0_sync;
            addsub1_reg1 <= addsub1_reg1_sync;
            casisel0_reg <= casisel0_reg_sync;
            casisel1_reg <= casisel1_reg_sync;
            out0_reg <= out0_reg_sync;
            out1_reg <= out1_reg_sync;
            out_preg <= out_preg_sync;
            ina_preg <= ina_preg_sync;
            out_reg <= out_reg_sync;
            accsel_int0_reg <= accsel_int0_reg_sync;
            accsel_int1_reg <= accsel_int1_reg_sync;
         end
    end

    //clk,ce,reset mux
    //A0REG
    always @(CLK)
    begin
        if (A0REG_CLK == "CLK0")
            A0_CLK = CLK[0];
        else if (A0REG_CLK == "CLK1")
            A0_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (A0REG_CE == "CE0")
            A0_CE = CE[0];
        else if (A0REG_CE == "CE1")
            A0_CE = CE[1];
    end

    always @(RESET)
    begin
        if (A0REG_RESET == "RESET0")
            A0_RESET = RESET[0];
        else if (A0REG_RESET == "RESET1")
            A0_RESET = RESET[1];
    end

    //A1REG
    always @(CLK)
    begin
        if (A1REG_CLK == "CLK0")
            A1_CLK = CLK[0];
        else if (A1REG_CLK == "CLK1")
            A1_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (A1REG_CE == "CE0")
            A1_CE = CE[0];
        else if (A1REG_CE == "CE1")
            A1_CE = CE[1];
    end

    always @(RESET)
    begin
        if (A1REG_RESET == "RESET0")
            A1_RESET = RESET[0];
        else if (A1REG_RESET == "RESET1")
            A1_RESET = RESET[1];
    end

    //B0REG
    always @(CLK)
    begin
        if (B0REG_CLK == "CLK0")
            B0_CLK = CLK[0];
        else if (B0REG_CLK == "CLK1")
            B0_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (B0REG_CE == "CE0")
            B0_CE = CE[0];
        else if (B0REG_CE == "CE1")
            B0_CE = CE[1];
    end

    always @(RESET)
    begin
        if (B0REG_RESET == "RESET0")
            B0_RESET = RESET[0];
        else if (B0REG_RESET == "RESET1")
            B0_RESET = RESET[1];
    end

    //B1REG
    always @(CLK)
    begin
        if (B1REG_CLK == "CLK0")
            B1_CLK = CLK[0];
        else if (B1REG_CLK == "CLK1")
            B1_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (B1REG_CE == "CE0")
            B1_CE = CE[0];
        else if (B1REG_CE == "CE1")
            B1_CE = CE[1];
    end

    always @(RESET)
    begin
        if (B1REG_RESET == "RESET0")
            B1_RESET = RESET[0];
        else if (B1REG_RESET == "RESET1")
            B1_RESET = RESET[1];
    end
    
    //IREG
    always @(CLK)
    begin
        if (ACCSEL_IREG_CLK == "CLK0")
            ACCSEL_ICLK = CLK[0];
        else if (ACCSEL_IREG_CLK == "CLK1")
            ACCSEL_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (ACCSEL_IREG_CE == "CE0")
            ACCSEL_ICE = CE[0];
        else if (ACCSEL_IREG_CE == "CE1")
            ACCSEL_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (ACCSEL_IREG_RESET == "RESET0")
            ACCSEL_IRESET = RESET[0];
        else if (ACCSEL_IREG_RESET == "RESET1")
            ACCSEL_IRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (ADDSUB0_IREG_CLK == "CLK0")
            ADDSUB0_ICLK = CLK[0];
        else if (ADDSUB0_IREG_CLK == "CLK1")
            ADDSUB0_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (ADDSUB0_IREG_CE == "CE0")
            ADDSUB0_ICE = CE[0];
        else if (ADDSUB0_IREG_CE == "CE1")
            ADDSUB0_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (ADDSUB0_IREG_RESET == "RESET0")
            ADDSUB0_IRESET = RESET[0];
        else if (ADDSUB0_IREG_RESET == "RESET1")
            ADDSUB0_IRESET = RESET[1];
    end
    
    always @(CLK)
    begin
        if (ADDSUB1_IREG_CLK == "CLK0")
            ADDSUB1_ICLK = CLK[0];
        else if (ADDSUB1_IREG_CLK == "CLK1")
            ADDSUB1_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (ADDSUB1_IREG_CE == "CE0")
            ADDSUB1_ICE = CE[0];
        else if (ADDSUB1_IREG_CE == "CE1")
            ADDSUB1_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (ADDSUB1_IREG_RESET == "RESET0")
            ADDSUB1_IRESET = RESET[0];
        else if (ADDSUB1_IREG_RESET == "RESET1")
            ADDSUB1_IRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (CASISEL_IREG_CLK == "CLK0")
            CASISEL_ICLK = CLK[0];
        else if (CASISEL_IREG_CLK == "CLK1")
            CASISEL_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (CASISEL_IREG_CE == "CE0")
            CASISEL_ICE = CE[0];
        else if (CASISEL_IREG_CE == "CE1")
            CASISEL_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (CASISEL_IREG_RESET == "RESET0")
            CASISEL_IRESET = RESET[0];
        else if (CASISEL_IREG_RESET == "RESET1")
            CASISEL_IRESET = RESET[1];
    end

    //PREG0
    always @(CLK)
    begin
        if (PREG0_CLK == "CLK0")
            P0_CLK = CLK[0];
        else if (PREG0_CLK == "CLK1")
            P0_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (PREG0_CE == "CE0")
            P0_CE = CE[0];
        else if (PREG0_CE == "CE1")
            P0_CE = CE[1];
    end

    always @(RESET)
    begin
        if (PREG0_RESET == "RESET0")
            P0_RESET = RESET[0];
        else if (PREG0_RESET == "RESET1")
            P0_RESET = RESET[1];
    end

    //PREG1
    always @(CLK)
    begin
        if (PREG1_CLK == "CLK0")
            P1_CLK = CLK[0];
        else if (PREG1_CLK == "CLK1")
            P1_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (PREG1_CE == "CE0")
            P1_CE = CE[0];
        else if (PREG1_CE == "CE1")
            P1_CE = CE[1];
    end

    always @(RESET)
    begin
        if (PREG1_RESET == "RESET0")
            P1_RESET = RESET[0];
        else if (PREG1_RESET == "RESET1")
            P1_RESET = RESET[1];
    end

    //PREG
    always @(CLK)
    begin
        if (ACCSEL_PREG_CLK == "CLK0")
            ACCSEL_PCLK = CLK[0];
        else if (ACCSEL_PREG_CLK == "CLK1")
            ACCSEL_PCLK = CLK[1];
    end

    always @(CE)
    begin
        if (ACCSEL_PREG_CE == "CE0")
            ACCSEL_PCE = CE[0];
        else if (ACCSEL_PREG_CE == "CE1")
            ACCSEL_PCE = CE[1];
    end

    always @(RESET)
    begin
        if (ACCSEL_PREG_RESET == "RESET0")
            ACCSEL_PRESET = RESET[0];
        else if (ACCSEL_PREG_RESET == "RESET1")
            ACCSEL_PRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (ADDSUB0_PREG_CLK == "CLK0")
            ADDSUB0_PCLK = CLK[0];
        else if (ADDSUB0_PREG_CLK == "CLK1")
            ADDSUB0_PCLK = CLK[1];
    end

    always @(CE)
    begin
        if (ADDSUB0_PREG_CE == "CE0")
            ADDSUB0_PCE = CE[0];
        else if (ADDSUB0_PREG_CE == "CE1")
            ADDSUB0_PCE = CE[1];
    end

    always @(RESET)
    begin
        if (ADDSUB0_PREG_RESET == "RESET0")
            ADDSUB0_PRESET = RESET[0];
        else if (ADDSUB0_PREG_RESET == "RESET1")
            ADDSUB0_PRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (ADDSUB1_PREG_CLK == "CLK0")
            ADDSUB1_PCLK = CLK[0];
        else if (ADDSUB1_PREG_CLK == "CLK1")
            ADDSUB1_PCLK = CLK[1];
    end

    always @(CE)
    begin
        if (ADDSUB1_PREG_CE == "CE0")
            ADDSUB1_PCE = CE[0];
        else if (ADDSUB1_PREG_CE == "CE1")
            ADDSUB1_PCE = CE[1];
    end

    always @(RESET)
    begin
        if (ADDSUB1_PREG_RESET == "RESET0")
            ADDSUB1_PRESET = RESET[0];
        else if (ADDSUB1_PREG_RESET == "RESET1")
            ADDSUB1_PRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (CASISEL_PREG_CLK == "CLK0")
            CASISEL_PCLK = CLK[0];
        else if (CASISEL_PREG_CLK == "CLK1")
            CASISEL_PCLK = CLK[1];
    end

    always @(CE)
    begin
        if (CASISEL_PREG_CE == "CE0")
            CASISEL_PCE = CE[0];
        else if (CASISEL_PREG_CE == "CE1")
            CASISEL_PCE = CE[1];
    end

    always @(RESET)
    begin
        if (CASISEL_PREG_RESET == "RESET0")
            CASISEL_PRESET = RESET[0];
        else if (CASISEL_PREG_RESET == "RESET1")
            CASISEL_PRESET = RESET[1];
    end

    //OREG
    always @(CLK)
    begin
        if (OREG_CLK == "CLK0")
            O_CLK = CLK[0];
        else if (OREG_CLK == "CLK1")
            O_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (OREG_CE == "CE0")
            O_CE = CE[0];
        else if (OREG_CE == "CE1")
            O_CE = CE[1];
    end

    always @(RESET)
    begin
        if (OREG_RESET == "RESET0")
            O_RESET = RESET[0];
        else if (OREG_RESET == "RESET1")
            O_RESET = RESET[1];
    end

    // in reg
    always @(posedge A0_CLK or posedge A0_RESET or negedge grstn)
    begin
        if (!grstn) begin
            ina0_reg_async <= 0;
        end else if (A0_RESET == 1'b1)
        begin
            ina0_reg_async <= 0;
        end
        else if (A0_CE == 1'b1)
        begin
            ina0_reg_async <= A0;
        end
    end

    always @(posedge A0_CLK or negedge grstn)
    begin
        if (!grstn) begin
            ina0_reg_sync <= 0; 
        end else if (A0_RESET == 1'b1)
        begin
            ina0_reg_sync <= 0;
        end
        else if (A0_CE == 1'b1)
        begin
            ina0_reg_sync <= A0;
        end
    end

    always @(posedge A1_CLK or posedge A1_RESET or negedge grstn)
    begin
        if (!grstn) begin
            ina1_reg_async <= 0;
        end else if (A1_RESET == 1'b1)
        begin
            ina1_reg_async <= 0;
        end
        else if (A1_CE == 1'b1)
        begin
            ina1_reg_async <= A1;
        end
    end

    always @(posedge A1_CLK or negedge grstn)
    begin
        if (!grstn) begin
            ina1_reg_sync <= 0; 
        end else if (A1_RESET == 1'b1)
        begin
            ina1_reg_sync <= 0;
        end
        else if (A1_CE == 1'b1)
        begin
            ina1_reg_sync <= A1;
        end
    end

    always @(A0 or ina0_reg)
    begin
        if (A0REG_CLK == "BYPASS")
        begin
            ina0 = A0;
        end else
        begin
            ina0 = ina0_reg;
        end
    end

    always @(A1 or ina1_reg)
    begin
        if (A1REG_CLK == "BYPASS")
        begin
            ina1 = A1;
        end else
        begin
            ina1 = ina1_reg;
        end
    end

    always @(posedge B0_CLK or posedge B0_RESET or negedge grstn)
    begin
        if (!grstn) begin
            inb0_reg_async <= 0;
        end else if (B0_RESET == 1'b1)
        begin
            inb0_reg_async <= 0;
        end
        else if (B0_CE == 1'b1)
        begin
            inb0_reg_async <= B0;
        end
    end

    always @(posedge B0_CLK or negedge grstn)
    begin
        if (!grstn) begin
            inb0_reg_sync <= 0; 
        end else if (B0_RESET == 1'b1)
        begin
            inb0_reg_sync <= 0;
        end
        else if (B0_CE == 1'b1)
        begin
            inb0_reg_sync <= B0;
        end
    end

    always @(posedge B1_CLK or posedge B1_RESET or negedge grstn)
    begin
        if (!grstn) begin
            inb1_reg_async <= 0;
        end else if (B1_RESET == 1'b1)
        begin
            inb1_reg_async <= 0;
        end
        else if (B1_CE == 1'b1)
        begin
            inb1_reg_async <= B1;
        end
    end

    always @(posedge B1_CLK or negedge grstn)
    begin
        if (!grstn) begin
            inb1_reg_sync <= 0; 
        end else if (B1_RESET == 1'b1)
        begin
            inb1_reg_sync <= 0;
        end
        else if (B1_CE == 1'b1)
        begin
            inb1_reg_sync <= B1;
        end
    end

    always @(B0 or inb0_reg)
    begin
        if (B0REG_CLK == "BYPASS")
        begin
            inb0 = B0;
        end else
        begin
            inb0 = inb0_reg;
        end
    end

    always @(B1 or inb1_reg)
    begin
        if (B1REG_CLK == "BYPASS")
        begin
            inb1 = B1;
        end else
        begin
            inb1 = inb1_reg;
        end
    end

    assign accsel_sig = (DYN_ACC_SEL == "FALSE") ? ACC_SEL : ACCSEL;
    assign casisel_sig = (DYN_CASI_SEL == "FALSE") ? CASI_SEL : CASISEL;
    
    assign addsub0_sig = (DYN_ADD_SUB_0 == "FALSE")? ADD_SUB_0 : ADDSUB[0];
    assign addsub1_sig = (DYN_ADD_SUB_1 == "FALSE")? ADD_SUB_1 : ADDSUB[1];

    always@(accsel_sig)
    begin
        if(accsel_sig == 1'b0)
        begin
            accsel_int = 2'b01;
        end else if(accsel_sig == 1'b1)
        begin
            accsel_int = 2'b10;
        end
    end

    always @(posedge ACCSEL_ICLK or posedge ACCSEL_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            accsel0_reg_async <= 1'b0;
            accsel_int0_reg_async <= 2'b0;
        end else if (ACCSEL_IRESET == 1'b1)
        begin
            accsel0_reg_async <= 1'b0;
            accsel_int0_reg_async <= 2'b0;
        end
        else if (ACCSEL_ICE == 1'b1)
        begin
            accsel0_reg_async <= accsel_sig;
            accsel_int0_reg_async <= accsel_int;
        end
    end

    always @(posedge ACCSEL_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            accsel0_reg_sync <= 1'b0; 
            accsel_int0_reg_sync <= 2'b0; 
        end else if (ACCSEL_IRESET == 1'b1)
        begin
            accsel0_reg_sync <= 1'b0;
            accsel_int0_reg_sync <= 2'b0; 
        end
        else if (ACCSEL_ICE == 1'b1)
        begin
            accsel0_reg_sync <= accsel_sig;
            accsel_int0_reg_sync <= accsel_int;
        end
    end

    always @(accsel_sig or accsel0_reg or accsel_int or accsel_int0_reg)
    begin
        if (ACCSEL_IREG_CLK == "BYPASS")
        begin
            accsel_0 <= accsel_sig;
            accsel_int0 <= accsel_int;
        end else
        begin
            accsel_0 <= accsel0_reg;
            accsel_int0 <= accsel_int0_reg;
        end
    end

    always @(posedge ACCSEL_PCLK or posedge ACCSEL_PRESET or negedge grstn)
    begin
        if (!grstn) begin
            accsel1_reg_async <= 1'b0;
            accsel_int1_reg_async <= 2'b0;
        end else if (ACCSEL_PRESET == 1'b1)
        begin
            accsel1_reg_async <= 1'b0;
            accsel_int1_reg_async <= 2'b0;
        end
        else if (ACCSEL_PCE == 1'b1)
        begin
            accsel1_reg_async <= accsel_0;
            accsel_int1_reg_async <= accsel_int0;
        end
    end

    always @(posedge ACCSEL_PCLK or negedge grstn)
    begin
        if (!grstn) begin
            accsel1_reg_sync <= 1'b0; 
            accsel_int1_reg_sync <= 2'b0; 
        end else if (ACCSEL_PRESET == 1'b1)
        begin
            accsel1_reg_sync <= 1'b0; 
            accsel_int1_reg_sync <= 2'b0; 
        end
        else if (ACCSEL_PCE == 1'b1)
        begin
            accsel1_reg_sync <= accsel_0;
            accsel_int1_reg_sync <= accsel_int0;
        end
    end

    always @(accsel_0 or accsel1_reg or accsel_int0 or accsel_int1_reg)
    begin
        if (ACCSEL_PREG_CLK == "BYPASS")
        begin
            accsel_1 <= accsel_0;
            accsel_int1 <= accsel_int0;
        end else
        begin
            accsel_1 <= accsel1_reg;
            accsel_int1 <= accsel_int1_reg;
        end
    end

    always @(posedge CASISEL_ICLK or posedge CASISEL_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            casisel0_reg_async <= 0;
        end else if (CASISEL_IRESET == 1'b1)
        begin
            casisel0_reg_async <= 0;
        end
        else if (CASISEL_ICE == 1'b1)
        begin
            casisel0_reg_async <= casisel_sig;
        end
    end

    always @(posedge CASISEL_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            casisel0_reg_sync <= 0; 
        end else if (CASISEL_IRESET == 1'b1)
        begin
            casisel0_reg_sync <= 0;
        end
        else if (CASISEL_ICE == 1'b1)
        begin
            casisel0_reg_sync <= casisel_sig;
        end
    end

    always @(casisel_sig or casisel0_reg)
    begin
        if (CASISEL_IREG_CLK == "BYPASS")
        begin
            casisel_0 <= casisel_sig;
        end else
        begin
            casisel_0 <= casisel0_reg;
        end
    end

    always @(posedge CASISEL_PCLK or posedge CASISEL_PRESET or negedge grstn)
    begin
        if (!grstn) begin
            casisel1_reg_async <= 0;
        end else if (CASISEL_PRESET == 1'b1)
        begin
            casisel1_reg_async <= 0;
        end
        else if (CASISEL_PCE == 1'b1)
        begin
            casisel1_reg_async <= casisel_0;
        end
    end

    always @(posedge CASISEL_PCLK or negedge grstn)
    begin
        if (!grstn) begin
            casisel1_reg_sync <= 0; 
        end else if (CASISEL_PRESET == 1'b1)
        begin
            casisel1_reg_sync <= 0;
        end
        else if (CASISEL_PCE == 1'b1)
        begin
            casisel1_reg_sync <= casisel_0;
        end
    end

    always @(casisel_0 or casisel1_reg)
    begin
        if (CASISEL_PREG_CLK == "BYPASS")
        begin
            casisel_1 <= casisel_0;
        end else
        begin
            casisel_1 <= casisel1_reg;
        end
    end

    always @(posedge ADDSUB0_ICLK or posedge ADDSUB0_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            addsub0_reg0_async <= 0;
        end else if (ADDSUB0_IRESET == 1'b1)
        begin
            addsub0_reg0_async <= 0;
        end
        else if (ADDSUB0_ICE == 1'b1)
        begin
            addsub0_reg0_async <= addsub0_sig;
        end
    end

    always @(posedge ADDSUB0_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            addsub0_reg0_sync <= 0; 
        end else if (ADDSUB0_IRESET == 1'b1)
        begin
            addsub0_reg0_sync <= 0;
        end
        else if (ADDSUB0_ICE == 1'b1)
        begin
            addsub0_reg0_sync <= addsub0_sig;
        end
    end

    always @(addsub0_sig or addsub0_reg0)
    begin
        if (ADDSUB0_IREG_CLK == "BYPASS")
        begin
            addsub0_0 <= addsub0_sig;
        end else
        begin
            addsub0_0 <= addsub0_reg0;
        end
    end

    always @(posedge ADDSUB0_PCLK or posedge ADDSUB0_PRESET or negedge grstn)
    begin
        if (!grstn) begin
            addsub0_reg1_async <= 0;
        end else if (ADDSUB0_PRESET == 1'b1)
        begin
            addsub0_reg1_async <= 0;
        end
        else if (ADDSUB0_PCE == 1'b1)
        begin
            addsub0_reg1_async <= addsub0_0;
        end
    end

    always @(posedge ADDSUB0_PCLK or negedge grstn)
    begin
        if (!grstn) begin
            addsub0_reg1_sync <= 0; 
        end else if (ADDSUB0_PRESET == 1'b1)
        begin
            addsub0_reg1_sync <= 0;
        end
        else if (ADDSUB0_PCE == 1'b1)
        begin
            addsub0_reg1_sync <= addsub0_0;
        end
    end

    always @(addsub0_0 or addsub0_reg1)
    begin
        if (ADDSUB0_PREG_CLK == "BYPASS")
        begin
            addsub0_1 <= addsub0_0;
        end else
        begin
            addsub0_1 <= addsub0_reg1;
        end
    end

    always @(posedge ADDSUB1_ICLK or posedge ADDSUB1_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            addsub1_reg0_async <= 0;
        end else if (ADDSUB1_IRESET == 1'b1)
        begin
            addsub1_reg0_async <= 0;
        end
        else if (ADDSUB1_ICE == 1'b1)
        begin
            addsub1_reg0_async <= addsub1_sig;
        end
    end

    always @(posedge ADDSUB1_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            addsub1_reg0_sync <= 0; 
        end else if (ADDSUB1_IRESET == 1'b1)
        begin
            addsub1_reg0_sync <= 0;
        end
        else if (ADDSUB1_ICE == 1'b1)
        begin
            addsub1_reg0_sync <= addsub1_sig;
        end
    end

    always @(addsub1_sig or addsub1_reg0)
    begin
        if (ADDSUB1_IREG_CLK == "BYPASS")
        begin
            addsub1_0 <= addsub1_sig;
        end else
        begin
            addsub1_0 <= addsub1_reg0;
        end
    end

    always @(posedge ADDSUB1_PCLK or posedge ADDSUB1_PRESET or negedge grstn)
    begin
        if (!grstn) begin
            addsub1_reg1_async <= 0;
        end else if (ADDSUB1_PRESET == 1'b1)
        begin
            addsub1_reg1_async <= 0;
        end
        else if (ADDSUB1_PCE == 1'b1)
        begin
            addsub1_reg1_async <= addsub1_0;
        end
    end

    always @(posedge ADDSUB1_PCLK or negedge grstn)
    begin
        if (!grstn) begin
            addsub1_reg1_sync <= 0; 
        end else if (ADDSUB1_PRESET == 1'b1)
        begin
            addsub1_reg1_sync <= 0;
        end
        else if (ADDSUB1_PCE == 1'b1)
        begin
            addsub1_reg1_sync <= addsub1_0;
        end
    end

    always @(addsub1_0 or addsub1_reg1)
    begin
        if (ADDSUB1_PREG_CLK == "BYPASS")
        begin
            addsub1_1 <= addsub1_0;
        end else
        begin
            addsub1_1 <= addsub1_reg1;
        end
    end

    assign a0[23:0] = {{12{ina0[11]}},ina0[11:0]};
    assign b0[23:0] = {{12{inb0[11]}},inb0[11:0]};
    assign a1[23:0] = {{12{ina1[11]}},ina1[11:0]};
    assign b1[23:0] = {{12{inb1[11]}},inb1[11:0]};

    assign mult_out0 = a0 * b0 ;
    assign mult_out1 = a1 * b1 ;

    // pipeline reg
    always @(posedge P0_CLK or posedge P0_RESET or negedge grstn)
    begin
        if (!grstn) begin
            out0_reg_async <= 0;
        end else if (P0_RESET == 1'b1)
        begin
            out0_reg_async <= 0;
        end
        else if (P0_CE == 1'b1)
        begin
            out0_reg_async <= mult_out0;
        end
    end

    always @(posedge P0_CLK or negedge grstn)
    begin
        if (!grstn) begin
            out0_reg_sync <= 0;
        end else if (P0_RESET == 1'b1)
        begin
            out0_reg_sync <= 0;
        end
        else if (P0_CE == 1'b1)
        begin
            out0_reg_sync <= mult_out0;
        end
    end

    always @(posedge P1_CLK or posedge P1_RESET or negedge grstn)
    begin
        if (!grstn) begin
            out1_reg_async <= 0;
        end else if (P1_RESET == 1'b1)
        begin
            out1_reg_async <= 0;
        end
        else if (P1_CE == 1'b1)
        begin
            out1_reg_async <= mult_out1;
        end
    end

    always @(posedge P1_CLK or negedge grstn)
    begin
        if (!grstn) begin
            out1_reg_sync <= 0;
        end else if (P1_RESET == 1'b1)
        begin
            out1_reg_sync <= 0;
        end
        else if (P1_CE == 1'b1)
        begin
            out1_reg_sync <= mult_out1;
        end
    end

    always @(posedge O_CLK or posedge O_RESET or negedge grstn)
    begin
        if (!grstn) begin
            out_preg_async <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_preg_async <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_preg_async <= d_out;
        end
    end

    always @(posedge O_CLK or negedge grstn)
    begin
        if (!grstn) begin
            out_preg_sync <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_preg_sync <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_preg_sync <= d_out;
        end
    end

    always @(mult_out0 or out0_reg)
    begin
        if (PREG0_CLK == "BYPASS")
        begin
            out0 = mult_out0;
        end else
        begin
            out0 = out0_reg;
        end
    end

    always @(mult_out1 or out1_reg)
    begin
        if (PREG1_CLK == "BYPASS")
        begin
            out1 = mult_out1;
        end else
        begin
            out1 = out1_reg;
        end
    end

    always @(d_out or out_preg)
    begin
        if (FB_PREG_EN == "FALSE")
        begin
            dout_reg = d_out;
        end else
        begin
            dout_reg = out_preg;
        end
    end

    assign m_out0 = {{24{out0[23]}},out0[23:0]};
    assign m_out1 = {{24{out1[23]}},out1[23:0]};

    assign acc_load = (accsel_int1 == 2'b10 || accsel_int1 == 2'b11) ? dout_reg : ((accsel_int1 == 2'b01) ? PRE_LOAD : 48'b0);
    assign d_casi = (casisel_1 == 1'b1) ? CASI : 48'b0;

    always @(acc_load or m_out0 or m_out1 or d_casi or addsub0_1 or addsub1_1)
    begin
        if(addsub0_1 == 1'b0 && addsub1_1 == 1'b0) begin
            alu_out = acc_load + m_out0 + m_out1 + d_casi;
        end else if(addsub0_1 == 1'b0 && addsub1_1 == 1'b1) begin
            alu_out = acc_load + m_out0 - m_out1 + d_casi;        
        end else if(addsub0_1 == 1'b1 && addsub1_1 == 1'b0) begin
            alu_out = acc_load - m_out0 + m_out1 + d_casi;        
        end else if(addsub0_1 == 1'b1 && addsub1_1 == 1'b1) begin
            alu_out = acc_load - m_out0 - m_out1 + d_casi;        
        end
    end

    // output reg
    always @(posedge O_CLK or posedge O_RESET or negedge grstn)
    begin
        if (!grstn) begin
            out_reg_async <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_reg_async <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_reg_async <= alu_out;
        end
    end

    always @(posedge O_CLK or negedge grstn)
    begin
        if (!grstn) begin
            out_reg_sync <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_reg_sync <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_reg_sync <= alu_out;
        end
    end

    always @(alu_out or out_reg)
    begin
        if (OREG_CLK == "BYPASS")
        begin
            d_out = alu_out;
        end else
        begin
            d_out = out_reg;
        end
    end

    assign DOUT = d_out[47:0];
    assign CASO = d_out[47:0];

endmodule
module MULTALU27X18 (DOUT, CASO, SOA, A, B, C, D, SIA, CASI, PSEL, ASEL, CSEL, CASISEL, PADDSUB, ACCSEL, ADDSUB, CLK, CE, RESET);

parameter AREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter AREG_CE = "CE0"; // "CE0","CE1"
parameter AREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter BREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter BREG_CE = "CE0"; // "CE0","CE1"
parameter BREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter DREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter DREG_CE = "CE0"; // "CE0","CE1"
parameter DREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter C_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter C_IREG_CE = "CE0"; // "CE0","CE1"
parameter C_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter PSEL_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter PSEL_IREG_CE = "CE0"; // "CE0","CE1"
parameter PSEL_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter PADDSUB_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter PADDSUB_IREG_CE = "CE0"; // "CE0","CE1"
parameter PADDSUB_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter ADDSUB0_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ADDSUB0_IREG_CE = "CE0"; // "CE0","CE1"
parameter ADDSUB0_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter ADDSUB1_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ADDSUB1_IREG_CE = "CE0"; // "CE0","CE1"
parameter ADDSUB1_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter CSEL_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter CSEL_IREG_CE = "CE0"; // "CE0","CE1"
parameter CSEL_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter CASISEL_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter CASISEL_IREG_CE = "CE0"; // "CE0","CE1"
parameter CASISEL_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter ACCSEL_IREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ACCSEL_IREG_CE = "CE0"; // "CE0","CE1"
parameter ACCSEL_IREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter PREG_CE = "CE0"; // "CE0","CE1"
parameter PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter ADDSUB0_PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ADDSUB0_PREG_CE = "CE0"; // "CE0","CE1"
parameter ADDSUB0_PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter ADDSUB1_PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ADDSUB1_PREG_CE = "CE0"; // "CE0","CE1"
parameter ADDSUB1_PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter CSEL_PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter CSEL_PREG_CE = "CE0"; // "CE0","CE1"
parameter CSEL_PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter CASISEL_PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter CASISEL_PREG_CE = "CE0"; // "CE0","CE1"
parameter CASISEL_PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter ACCSEL_PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter ACCSEL_PREG_CE = "CE0"; // "CE0","CE1"
parameter ACCSEL_PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter C_PREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter C_PREG_CE = "CE0"; // "CE0","CE1"
parameter C_PREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter FB_PREG_EN = "FALSE"; // "FALSE";"TRUE"      //feedback acc pipeline register,same clk/ce/reset as OREG
parameter SOA_PREG_EN = "FALSE"; // "FALSE";"TRUE"      //soa pipeline register,,same clk/ce/reset as AREG

parameter OREG_CLK = "BYPASS"; // "BYPASS","CLK0","CLK1"
parameter OREG_CE = "CE0"; // "CE0","CE1"
parameter OREG_RESET = "RESET0"; //"RESET0", "RESET1"

parameter MULT_RESET_MODE = "SYNC";// SYNC,ASYNC
parameter PRE_LOAD = 48'h000000000000;

parameter DYN_P_SEL = "FALSE";//"TRUE","FALSE"
parameter P_SEL = 1'b0;//1'b0: select direct INA; 1'b1: select preadder
parameter DYN_P_ADDSUB = "FALSE";//"TRUE","FALSE"
parameter P_ADDSUB = 1'b0;//1'b0: '+'; 1'b1: '-'
parameter DYN_A_SEL = "FALSE";//"TRUE","FALSE"
parameter A_SEL = 1'b0;//1'b0:select A; 1'b1:select SIA.

parameter DYN_ADD_SUB_0 = "FALSE";//"TRUE","FALSE"
parameter ADD_SUB_0 = 1'b0;//1'b0: '+'; 1'b1: '-'
parameter DYN_ADD_SUB_1 = "FALSE";//"TRUE","FALSE"
parameter ADD_SUB_1 = 1'b0;//1'b0: '+'; 1'b1: '-'

parameter DYN_C_SEL = "FALSE";//"TRUE","FALSE"
parameter C_SEL = 1'b1;//1'b0: select 0; 1'b1: select C input
parameter DYN_CASI_SEL = "FALSE";//"TRUE","FALSE"
parameter CASI_SEL = 1'b0;//1'b0: select 0; 1'b1:select casi
parameter DYN_ACC_SEL = "FALSE";//"TRUE","FALSE"
parameter ACC_SEL = 1'b0;//1'b0: PRE_LOAD;1'b1: DOUT feedback;

parameter MULT12X12_EN = "FALSE";//"TRUE","FALSE"


output [47:0] DOUT, CASO;
output [26:0] SOA;
input  [26:0] A, SIA;
input  [17:0] B;
input  [47:0] C;
input  [25:0] D;
input  [47:0] CASI;
input  ACCSEL;
input  PSEL;
input  ASEL;
input  PADDSUB;
input  CSEL, CASISEL;
input  [1:0] ADDSUB;
input  [1:0] CLK, CE, RESET;

reg A_CLK,A_CE,A_RESET,B_CLK,B_CE,B_RESET,C_ICLK,C_ICE,C_IRESET,C_PCLK,C_PCE,C_PRESET,D_CLK,D_CE,D_RESET,PSEL_ICLK,PSEL_ICE,PSEL_IRESET,ACCSEL_ICLK,ACCSEL_ICE,ACCSEL_IRESET,CSEL_ICLK,CSEL_ICE,CSEL_IRESET,CASISEL_ICLK,CASISEL_ICE,CASISEL_IRESET,ADDSUB0_ICLK,ADDSUB0_ICE,ADDSUB0_IRESET,ADDSUB1_ICLK,ADDSUB1_ICE,ADDSUB1_IRESET,PADDSUB_ICLK,PADDSUB_ICE,PADDSUB_IRESET,P_CLK,P_CE,P_RESET,ACCSEL_PCLK,ACCSEL_PCE,ACCSEL_PRESET,CSEL_PCLK,CSEL_PCE,CSEL_PRESET,CASISEL_PCLK,CASISEL_PCE,CASISEL_PRESET,ADDSUB0_PCLK,ADDSUB0_PCE,ADDSUB0_PRESET,ADDSUB1_PCLK,ADDSUB1_PCE,ADDSUB1_PRESET,O_CLK,O_CE,O_RESET;
reg [26:0] ina_reg_async,ina_reg_sync,ina,ina_reg,a_src,a_in,ina_preg_async,ina_preg_sync,ina_preg,SOA;
wire [26:0] ina_ext,ind_ext;
wire [11:0] ina_12_ext, ind_12_ext;
reg [11:0] a_12_in;
reg [17:0] inb_reg_async,inb_reg_sync,inb,inb_reg;
reg [25:0] ind_reg_async,ind_reg_sync,ind,ind_reg;
reg [47:0] inc_ireg_async,inc_ireg_sync,inc_0,inc_ireg,inc_preg_async,inc_preg_sync,inc_1,inc_preg;
reg accsel0_reg_async,accsel0_reg_sync,accsel_0,accsel0_reg,accsel1_reg_async,accsel1_reg_sync,accsel_1,accsel1_reg;
reg addsub0_reg0_async,addsub0_reg0_sync,addsub0_reg0,addsub0_0,addsub0_reg1_async,addsub0_reg1_sync,addsub0_reg1,addsub0_1;
reg addsub1_reg0_async,addsub1_reg0_sync,addsub1_reg0,addsub1_0,addsub1_reg1_async,addsub1_reg1_sync,addsub1_reg1,addsub1_1;
reg casisel0_reg_async,casisel0_reg_sync,casisel_0,casisel0_reg,casisel1_reg_async,casisel1_reg_sync,casisel1_reg,casisel_1;
reg csel0_reg_async,csel0_reg_sync,csel_0,csel0_reg,csel1_reg_async,csel1_reg_sync,csel1_reg,csel_1;
wire [44:0] a0,b0,mult_out;
reg [44:0] out0_reg_async,out0_reg_sync,out0,out0_reg;
reg [48:0] d_out,out_preg_async,out_preg_sync,out_preg,dout_reg,alu_out;
wire [47:0] m_out0,acc_load,d_casi,c_sig;
reg [48:0] out_reg_async,out_reg_sync,out_reg;
wire preadd_en,p_addsub_sig;
reg paddsub_reg0_async,paddsub_reg0_sync,paddsub_reg0,paddsub_0;
reg psel_reg_async,psel_reg_sync,psel_reg,psel_0;
wire a_sel_sig,accsel_sig,casisel_sig,csel_sig,addsub0_sig,addsub1_sig;
reg [1:0] accsel_int;
reg [1:0] accsel_int0_reg_async,accsel_int0_reg_sync,accsel_int0,accsel_int0_reg,accsel_int1_reg_async,accsel_int1_reg_sync,accsel_int1,accsel_int1_reg;

wire grstn = GSR.GSRO;


always @(ina_reg_async or ina_reg_sync or inb_reg_async or inb_reg_sync or ind_reg_async or ind_reg_sync or inc_ireg_async or inc_ireg_sync or inc_preg_async or inc_preg_sync or psel_reg_async or psel_reg_sync or csel0_reg_async or csel0_reg_sync or csel1_reg_async or csel1_reg_sync or casisel0_reg_async or casisel0_reg_sync or casisel1_reg_async or casisel1_reg_sync or accsel0_reg_async or accsel0_reg_sync or accsel1_reg_async or accsel1_reg_sync or addsub0_reg0_async or addsub0_reg0_sync or addsub0_reg1_async or addsub0_reg1_sync or addsub1_reg0_async or addsub1_reg0_sync or addsub1_reg1_async or addsub1_reg1_sync or paddsub_reg0_async or paddsub_reg0_sync or out0_reg_async or out0_reg_sync or out_preg_async or out_preg_sync or ina_preg_sync or ina_preg_async or out_reg_sync or out_reg_async or accsel_int0_reg_async or accsel_int0_reg_sync or accsel_int0_reg or accsel_int1_reg_async or accsel_int1_reg_sync or accsel_int1_reg)
    begin
        if (MULT_RESET_MODE == "ASYNC")
        begin
            ina_reg <= ina_reg_async;
            inb_reg <= inb_reg_async;
            inc_ireg <= inc_ireg_async;
            inc_preg <= inc_preg_async;
            ind_reg <= ind_reg_async;
            psel_reg <= psel_reg_async;
            accsel0_reg <= accsel0_reg_async;
            accsel1_reg <= accsel1_reg_async;
            csel0_reg <= csel0_reg_async;
            csel1_reg <= csel1_reg_async;
            casisel0_reg <= casisel0_reg_async;
            casisel1_reg <= casisel1_reg_async;
            addsub0_reg0 <= addsub0_reg0_async;
            addsub0_reg1 <= addsub0_reg1_async;
            addsub1_reg0 <= addsub1_reg0_async;
            addsub1_reg1 <= addsub1_reg1_async;
            paddsub_reg0 <= paddsub_reg0_async;
            out0_reg <= out0_reg_async;
            out_preg <= out_preg_async;
            ina_preg <= ina_preg_async;
            out_reg <= out_reg_async;
            accsel_int0_reg <= accsel_int0_reg_async;
            accsel_int1_reg <= accsel_int1_reg_async;
         end
        else if (MULT_RESET_MODE == "SYNC")
        begin
            ina_reg <= ina_reg_sync;
            inb_reg <= inb_reg_sync;
            ind_reg <= ind_reg_sync;
            inc_ireg <= inc_ireg_sync;
            inc_preg <= inc_preg_sync;
            psel_reg <= psel_reg_sync;
            accsel0_reg <= accsel0_reg_sync;
            accsel1_reg <= accsel1_reg_sync;
            casisel0_reg <= casisel0_reg_sync;
            casisel1_reg <= casisel1_reg_sync;
            csel0_reg <= csel0_reg_sync;
            csel1_reg <= csel1_reg_sync;
            addsub0_reg0 <= addsub0_reg0_sync;
            addsub0_reg1 <= addsub0_reg1_sync;
            addsub1_reg0 <= addsub1_reg0_sync;
            addsub1_reg1 <= addsub1_reg1_sync;
            paddsub_reg0 <= paddsub_reg0_sync;
            out0_reg <= out0_reg_sync;
            out_preg <= out_preg_sync;
            ina_preg <= ina_preg_sync;
            out_reg <= out_reg_sync;
            accsel_int0_reg <= accsel_int0_reg_sync;
            accsel_int1_reg <= accsel_int1_reg_sync;
         end
    end

    //clk,ce,reset mux
    //AREG
    always @(CLK)
    begin
        if (AREG_CLK == "CLK0")
            A_CLK = CLK[0];
        else if (AREG_CLK == "CLK1")
            A_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (AREG_CE == "CE0")
            A_CE = CE[0];
        else if (AREG_CE == "CE1")
            A_CE = CE[1];
    end

    always @(RESET)
    begin
        if (AREG_RESET == "RESET0")
            A_RESET = RESET[0];
        else if (AREG_RESET == "RESET1")
            A_RESET = RESET[1];
    end

    //BREG
    always @(CLK)
    begin
        if (BREG_CLK == "CLK0")
            B_CLK = CLK[0];
        else if (BREG_CLK == "CLK1")
            B_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (BREG_CE == "CE0")
            B_CE = CE[0];
        else if (BREG_CE == "CE1")
            B_CE = CE[1];
    end

    always @(RESET)
    begin
        if (BREG_RESET == "RESET0")
            B_RESET = RESET[0];
        else if (BREG_RESET == "RESET1")
            B_RESET = RESET[1];
    end

    //CREG
    always @(CLK)
    begin
        if (C_IREG_CLK == "CLK0")
            C_ICLK = CLK[0];
        else if (C_IREG_CLK == "CLK1")
            C_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (C_IREG_CE == "CE0")
            C_ICE = CE[0];
        else if (C_IREG_CE == "CE1")
            C_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (C_IREG_RESET == "RESET0")
            C_IRESET = RESET[0];
        else if (C_IREG_RESET == "RESET1")
            C_IRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (C_PREG_CLK == "CLK0")
            C_PCLK = CLK[0];
        else if (C_PREG_CLK == "CLK1")
            C_PCLK = CLK[1];
    end

    always @(CE)
    begin
        if (C_PREG_CE == "CE0")
            C_PCE = CE[0];
        else if (C_PREG_CE == "CE1")
            C_PCE = CE[1];
    end

    always @(RESET)
    begin
        if (C_PREG_RESET == "RESET0")
            C_PRESET = RESET[0];
        else if (C_PREG_RESET == "RESET1")
            C_PRESET = RESET[1];
    end

    
    //DREG
    always @(CLK)
    begin
        if (DREG_CLK == "CLK0")
            D_CLK = CLK[0];
        else if (DREG_CLK == "CLK1")
            D_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (DREG_CE == "CE0")
            D_CE = CE[0];
        else if (DREG_CE == "CE1")
            D_CE = CE[1];
    end

    always @(RESET)
    begin
        if (DREG_RESET == "RESET0")
            D_RESET = RESET[0];
        else if (DREG_RESET == "RESET1")
            D_RESET = RESET[1];
    end

    
    //IREG
    always @(CLK)
    begin
        if (ACCSEL_IREG_CLK == "CLK0")
            ACCSEL_ICLK = CLK[0];
        else if (ACCSEL_IREG_CLK == "CLK1")
            ACCSEL_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (ACCSEL_IREG_CE == "CE0")
            ACCSEL_ICE = CE[0];
        else if (ACCSEL_IREG_CE == "CE1")
            ACCSEL_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (ACCSEL_IREG_RESET == "RESET0")
            ACCSEL_IRESET = RESET[0];
        else if (ACCSEL_IREG_RESET == "RESET1")
            ACCSEL_IRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (ADDSUB0_IREG_CLK == "CLK0")
            ADDSUB0_ICLK = CLK[0];
        else if (ADDSUB0_IREG_CLK == "CLK1")
            ADDSUB0_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (ADDSUB0_IREG_CE == "CE0")
            ADDSUB0_ICE = CE[0];
        else if (ADDSUB0_IREG_CE == "CE1")
            ADDSUB0_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (ADDSUB0_IREG_RESET == "RESET0")
            ADDSUB0_IRESET = RESET[0];
        else if (ADDSUB0_IREG_RESET == "RESET1")
            ADDSUB0_IRESET = RESET[1];
    end
    
    always @(CLK)
    begin
        if (ADDSUB1_IREG_CLK == "CLK0")
            ADDSUB1_ICLK = CLK[0];
        else if (ADDSUB1_IREG_CLK == "CLK1")
            ADDSUB1_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (ADDSUB1_IREG_CE == "CE0")
            ADDSUB1_ICE = CE[0];
        else if (ADDSUB1_IREG_CE == "CE1")
            ADDSUB1_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (ADDSUB1_IREG_RESET == "RESET0")
            ADDSUB1_IRESET = RESET[0];
        else if (ADDSUB1_IREG_RESET == "RESET1")
            ADDSUB1_IRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (PSEL_IREG_CLK == "CLK0")
            PSEL_ICLK = CLK[0];
        else if (PSEL_IREG_CLK == "CLK1")
            PSEL_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (PSEL_IREG_CE == "CE0")
            PSEL_ICE = CE[0];
        else if (PSEL_IREG_CE == "CE1")
            PSEL_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (PSEL_IREG_RESET == "RESET0")
            PSEL_IRESET = RESET[0];
        else if (PSEL_IREG_RESET == "RESET1")
            PSEL_IRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (PADDSUB_IREG_CLK == "CLK0")
            PADDSUB_ICLK = CLK[0];
        else if (PADDSUB_IREG_CLK == "CLK1")
            PADDSUB_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (PADDSUB_IREG_CE == "CE0")
            PADDSUB_ICE = CE[0];
        else if (PADDSUB_IREG_CE == "CE1")
            PADDSUB_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (PADDSUB_IREG_RESET == "RESET0")
            PADDSUB_IRESET = RESET[0];
        else if (PADDSUB_IREG_RESET == "RESET1")
            PADDSUB_IRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (CSEL_IREG_CLK == "CLK0")
            CSEL_ICLK = CLK[0];
        else if (CSEL_IREG_CLK == "CLK1")
            CSEL_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (CSEL_IREG_CE == "CE0")
            CSEL_ICE = CE[0];
        else if (CSEL_IREG_CE == "CE1")
            CSEL_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (CSEL_IREG_RESET == "RESET0")
            CSEL_IRESET = RESET[0];
        else if (CSEL_IREG_RESET == "RESET1")
            CSEL_IRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (CASISEL_IREG_CLK == "CLK0")
            CASISEL_ICLK = CLK[0];
        else if (CASISEL_IREG_CLK == "CLK1")
            CASISEL_ICLK = CLK[1];
    end

    always @(CE)
    begin
        if (CASISEL_IREG_CE == "CE0")
            CASISEL_ICE = CE[0];
        else if (CASISEL_IREG_CE == "CE1")
            CASISEL_ICE = CE[1];
    end

    always @(RESET)
    begin
        if (CASISEL_IREG_RESET == "RESET0")
            CASISEL_IRESET = RESET[0];
        else if (CASISEL_IREG_RESET == "RESET1")
            CASISEL_IRESET = RESET[1];
    end

    //PREG
    always @(CLK)
    begin
        if (PREG_CLK == "CLK0")
            P_CLK = CLK[0];
        else if (PREG_CLK == "CLK1")
            P_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (PREG_CE == "CE0")
            P_CE = CE[0];
        else if (PREG_CE == "CE1")
            P_CE = CE[1];
    end

    always @(RESET)
    begin
        if (PREG_RESET == "RESET0")
            P_RESET = RESET[0];
        else if (PREG_RESET == "RESET1")
            P_RESET = RESET[1];
    end

    always @(CLK)
    begin
        if (ACCSEL_PREG_CLK == "CLK0")
            ACCSEL_PCLK = CLK[0];
        else if (ACCSEL_PREG_CLK == "CLK1")
            ACCSEL_PCLK = CLK[1];
    end

    always @(CE)
    begin
        if (ACCSEL_PREG_CE == "CE0")
            ACCSEL_PCE = CE[0];
        else if (ACCSEL_PREG_CE == "CE1")
            ACCSEL_PCE = CE[1];
    end

    always @(RESET)
    begin
        if (ACCSEL_PREG_RESET == "RESET0")
            ACCSEL_PRESET = RESET[0];
        else if (ACCSEL_PREG_RESET == "RESET1")
            ACCSEL_PRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (ADDSUB0_PREG_CLK == "CLK0")
            ADDSUB0_PCLK = CLK[0];
        else if (ADDSUB0_PREG_CLK == "CLK1")
            ADDSUB0_PCLK = CLK[1];
    end

    always @(CE)
    begin
        if (ADDSUB0_PREG_CE == "CE0")
            ADDSUB0_PCE = CE[0];
        else if (ADDSUB0_PREG_CE == "CE1")
            ADDSUB0_PCE = CE[1];
    end

    always @(RESET)
    begin
        if (ADDSUB0_PREG_RESET == "RESET0")
            ADDSUB0_PRESET = RESET[0];
        else if (ADDSUB0_PREG_RESET == "RESET1")
            ADDSUB0_PRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (ADDSUB1_PREG_CLK == "CLK0")
            ADDSUB1_PCLK = CLK[0];
        else if (ADDSUB1_PREG_CLK == "CLK1")
            ADDSUB1_PCLK = CLK[1];
    end

    always @(CE)
    begin
        if (ADDSUB1_PREG_CE == "CE0")
            ADDSUB1_PCE = CE[0];
        else if (ADDSUB1_PREG_CE == "CE1")
            ADDSUB1_PCE = CE[1];
    end

    always @(RESET)
    begin
        if (ADDSUB1_PREG_RESET == "RESET0")
            ADDSUB1_PRESET = RESET[0];
        else if (ADDSUB1_PREG_RESET == "RESET1")
            ADDSUB1_PRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (CSEL_PREG_CLK == "CLK0")
            CSEL_PCLK = CLK[0];
        else if (CSEL_PREG_CLK == "CLK1")
            CSEL_PCLK = CLK[1];
    end

    always @(CE)
    begin
        if (CSEL_PREG_CE == "CE0")
            CSEL_PCE = CE[0];
        else if (CSEL_PREG_CE == "CE1")
            CSEL_PCE = CE[1];
    end

    always @(RESET)
    begin
        if (CSEL_PREG_RESET == "RESET0")
            CSEL_PRESET = RESET[0];
        else if (CSEL_PREG_RESET == "RESET1")
            CSEL_PRESET = RESET[1];
    end

    always @(CLK)
    begin
        if (CASISEL_PREG_CLK == "CLK0")
            CASISEL_PCLK = CLK[0];
        else if (CASISEL_PREG_CLK == "CLK1")
            CASISEL_PCLK = CLK[1];
    end

    always @(CE)
    begin
        if (CASISEL_PREG_CE == "CE0")
            CASISEL_PCE = CE[0];
        else if (CASISEL_PREG_CE == "CE1")
            CASISEL_PCE = CE[1];
    end

    always @(RESET)
    begin
        if (CASISEL_PREG_RESET == "RESET0")
            CASISEL_PRESET = RESET[0];
        else if (CASISEL_PREG_RESET == "RESET1")
            CASISEL_PRESET = RESET[1];
    end

    //OREG
    always @(CLK)
    begin
        if (OREG_CLK == "CLK0")
            O_CLK = CLK[0];
        else if (OREG_CLK == "CLK1")
            O_CLK = CLK[1];
    end

    always @(CE)
    begin
        if (OREG_CE == "CE0")
            O_CE = CE[0];
        else if (OREG_CE == "CE1")
            O_CE = CE[1];
    end

    always @(RESET)
    begin
        if (OREG_RESET == "RESET0")
            O_RESET = RESET[0];
        else if (OREG_RESET == "RESET1")
            O_RESET = RESET[1];
    end

    //PADD or not
    assign a_sel_sig = (DYN_A_SEL == "TRUE") ? ASEL : A_SEL;
    
    always @(A or SIA or a_sel_sig)
    begin
        if(a_sel_sig == 1'b0)
        begin
            a_src = A;
        end else begin
            a_src = SIA;
        end
    end

    assign preadd_en = (DYN_P_SEL == "TRUE")? PSEL : P_SEL;
    assign p_addsub_sig = (DYN_P_ADDSUB == "TRUE")? PADDSUB : P_ADDSUB;

    always @(posedge PADDSUB_ICLK or posedge PADDSUB_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            paddsub_reg0_async <= 0;
        end else if (PADDSUB_IRESET == 1'b1)
        begin
            paddsub_reg0_async <= 0;
        end
        else if (PADDSUB_ICE == 1'b1)
        begin
            paddsub_reg0_async <= p_addsub_sig;
        end
    end

    always @(posedge PADDSUB_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            paddsub_reg0_sync <= 0;
        end else if (PADDSUB_IRESET == 1'b1)
        begin
            paddsub_reg0_sync <= 0;
        end
        else if (PADDSUB_ICE == 1'b1)
        begin
            paddsub_reg0_sync <= p_addsub_sig;
        end
    end

    always @(p_addsub_sig or paddsub_reg0)
    begin
        if (PADDSUB_IREG_CLK == "BYPASS")
        begin
            paddsub_0 <= p_addsub_sig;
        end else
        begin
            paddsub_0 <= paddsub_reg0;
        end
    end

    always @(posedge PSEL_ICLK or posedge PSEL_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            psel_reg_async <= 0;
        end else if (PSEL_IRESET == 1'b1)
        begin
            psel_reg_async <= 0;
        end
        else if (PSEL_ICE == 1'b1)
        begin
            psel_reg_async <= preadd_en;
        end
    end

    always @(posedge PSEL_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            psel_reg_sync <= 0;
        end else if (PSEL_IRESET == 1'b1)
        begin
            psel_reg_sync <= 0;
        end
        else if (PSEL_ICE == 1'b1)
        begin
            psel_reg_sync <= preadd_en;
        end
    end

    always @(preadd_en or psel_reg)
    begin
        if (PSEL_IREG_CLK == "BYPASS")
        begin
            psel_0 <= preadd_en;
        end else
        begin
            psel_0 <= psel_reg;
        end
    end

    assign ina_ext = {ina[25],ina[25:0]};
    assign ind_ext = {ind[25],ind[25:0]};

    assign ina_12_ext = {ina[10],ina[10:0]};
    assign ind_12_ext = {ind[10],ind[10:0]};

    always@(ina_ext or ind_ext or ina or psel_0 or paddsub_0 or ina_12_ext or ind_12_ext)
    begin
        if(MULT12X12_EN == "FALSE")
        begin
            if(psel_0 == 1'b1)
            begin
                if(paddsub_0 == 1'b0) begin
                    a_in = ina_ext + ind_ext;
                end else begin
                    a_in = ina_ext - ind_ext;
                end
            end else begin
                a_in = ina;
            end
        end else if(MULT12X12_EN == "TRUE")
        begin
            if(psel_0 == 1'b1)
            begin
                if(paddsub_0 == 1'b0) begin
                    a_12_in = ina_12_ext + ind_12_ext;
                end else begin
                    a_12_in = ina_12_ext - ind_12_ext;
                end
            end else begin
                a_12_in = ina[11:0];
            end
        end

    end

    // in reg
    always @(posedge A_CLK or posedge A_RESET or negedge grstn)
    begin
        if (!grstn) begin
            ina_reg_async <= 0;
        end else if (A_RESET == 1'b1)
        begin
            ina_reg_async <= 0;
        end
        else if (A_CE == 1'b1)
        begin
            ina_reg_async <= a_src;
        end
    end

    always @(posedge A_CLK or negedge grstn)
    begin
        if (!grstn) begin
            ina_reg_sync <= 0; 
        end else if (A_RESET == 1'b1)
        begin
            ina_reg_sync <= 0;
        end
        else if (A_CE == 1'b1)
        begin
            ina_reg_sync <= a_src;
        end
    end
    
    always @(a_src or ina_reg)
    begin
        if (AREG_CLK == "BYPASS")
        begin
            ina = a_src;
        end else
        begin
            ina = ina_reg;
        end
    end

    always @(posedge B_CLK or posedge B_RESET or negedge grstn)
    begin
        if (!grstn) begin
            inb_reg_async <= 0;
        end else if (B_RESET == 1'b1)
        begin
            inb_reg_async <= 0;
        end
        else if (B_CE == 1'b1)
        begin
            inb_reg_async <= B;
        end
    end

    always @(posedge B_CLK or negedge grstn)
    begin
        if (!grstn) begin
            inb_reg_sync <= 0; 
        end else if (B_RESET == 1'b1)
        begin
            inb_reg_sync <= 0;
        end
        else if (B_CE == 1'b1)
        begin
            inb_reg_sync <= B;
        end
    end

    always @(B or inb_reg)
    begin
        if (BREG_CLK == "BYPASS")
        begin
            inb = B;
        end else
        begin
            inb = inb_reg;
        end
    end

    always @(posedge C_ICLK or posedge C_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            inc_ireg_async <= 0;
        end else if (C_IRESET == 1'b1)
        begin
            inc_ireg_async <= 0;
        end
        else if (C_ICE == 1'b1)
        begin
            inc_ireg_async <= C;
        end
    end

    always @(posedge C_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            inc_ireg_sync <= 0;
        end else if (C_IRESET == 1'b1)
        begin
            inc_ireg_sync <= 0;
        end
        else if (C_ICE == 1'b1)
        begin
            inc_ireg_sync <= C;
        end
    end

    always @(C or inc_ireg)
    begin
        if (C_IREG_CLK == "BYPASS")
        begin
            inc_0 = C;
        end else
        begin
            inc_0 = inc_ireg;
        end
    end

    always @(posedge C_PCLK or posedge C_PRESET or negedge grstn)
    begin
        if (!grstn) begin
            inc_preg_async <= 0;
        end else if (C_PRESET == 1'b1)
        begin
            inc_preg_async <= 0;
        end
        else if (C_PCE == 1'b1)
        begin
            inc_preg_async <= inc_0;
        end
    end

    always @(posedge C_PCLK or negedge grstn)
    begin
        if (!grstn) begin
            inc_preg_sync <= 0;
        end else if (C_PRESET == 1'b1)
        begin
            inc_preg_sync <= 0;
        end
        else if (C_PCE == 1'b1)
        begin
            inc_preg_sync <= inc_0;
        end
    end

    always @(inc_0 or inc_preg)
    begin
        if (C_PREG_CLK == "BYPASS")
        begin
            inc_1 = inc_0;
        end else
        begin
            inc_1 = inc_preg;
        end
    end

    always @(posedge D_CLK or posedge D_RESET or negedge grstn)
    begin
        if (!grstn) begin
            ind_reg_async <= 0;
        end else if (D_RESET == 1'b1)
        begin
            ind_reg_async <= 0;
        end
        else if (D_CE == 1'b1)
        begin
            ind_reg_async <= D;
        end
    end

    always @(posedge D_CLK or negedge grstn)
    begin
        if (!grstn) begin
            ind_reg_sync <= 0; 
        end else if (D_RESET == 1'b1)
        begin
            ind_reg_sync <= 0;
        end
        else if (D_CE == 1'b1)
        begin
            ind_reg_sync <= D;
        end
    end

    always @(D or ind_reg)
    begin
        if (DREG_CLK == "BYPASS")
        begin
            ind = D;
        end else
        begin
            ind = ind_reg;
        end
    end

    assign accsel_sig = (DYN_ACC_SEL == "FALSE") ? ACC_SEL : ACCSEL;
    assign casisel_sig = (DYN_CASI_SEL == "FALSE") ? CASI_SEL : CASISEL;
    assign csel_sig = (DYN_C_SEL == "FALSE")?  C_SEL: CSEL;
    
    assign addsub0_sig = (DYN_ADD_SUB_0 == "FALSE")? ADD_SUB_0 : ADDSUB[0];
    assign addsub1_sig = (DYN_ADD_SUB_1 == "FALSE")? ADD_SUB_1 : ADDSUB[1];

    always@(accsel_sig)
    begin
        if(accsel_sig == 1'b0)
        begin
            accsel_int = 2'b01;
        end else if(accsel_sig == 1'b1)
        begin
            accsel_int = 2'b10;
        end
    end

    always @(posedge ACCSEL_ICLK or posedge ACCSEL_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            accsel0_reg_async <= 1'b0;
            accsel_int0_reg_async <= 2'b00;
        end else if (ACCSEL_IRESET == 1'b1)
        begin
            accsel0_reg_async <= 1'b0;
            accsel_int0_reg_async <= 2'b0;
        end
        else if (ACCSEL_ICE == 1'b1)
        begin
            accsel0_reg_async <= accsel_sig;
            accsel_int0_reg_async <= accsel_int;
        end
    end

    always @(posedge ACCSEL_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            accsel0_reg_sync <= 1'b0; 
            accsel_int0_reg_sync <= 2'b0; 
        end else if (ACCSEL_IRESET == 1'b1)
        begin
            accsel0_reg_sync <= 1'b0;
            accsel_int0_reg_sync <= 2'b0;
        end
        else if (ACCSEL_ICE == 1'b1)
        begin
            accsel0_reg_sync <= accsel_sig;
            accsel_int0_reg_sync <= accsel_int;
        end
    end

    always @(accsel_sig or accsel0_reg or accsel_int or accsel_int0_reg)
    begin
        if (ACCSEL_IREG_CLK == "BYPASS")
        begin
            accsel_0 <= accsel_sig;
            accsel_int0 <= accsel_int;
        end else
        begin
            accsel_0 <= accsel0_reg;
            accsel_int0 <= accsel_int0_reg;
        end
    end

    always @(posedge ACCSEL_PCLK or posedge ACCSEL_PRESET or negedge grstn)
    begin
        if (!grstn) begin
            accsel1_reg_async <= 1'b0;
            accsel_int1_reg_async <= 2'b0;
        end else if (ACCSEL_PRESET == 1'b1)
        begin
            accsel1_reg_async <= 1'b0;
            accsel_int1_reg_async <= 2'b0;
        end
        else if (ACCSEL_PCE == 1'b1)
        begin
            accsel1_reg_async <= accsel_0;
            accsel_int1_reg_async <= accsel_int0;
        end
    end

    always @(posedge ACCSEL_PCLK or negedge grstn)
    begin
        if (!grstn) begin
            accsel1_reg_sync <= 1'b0; 
            accsel_int1_reg_sync <= 2'b0; 
        end else if (ACCSEL_PRESET == 1'b1)
        begin
            accsel1_reg_sync <= 1'b0;
            accsel_int1_reg_sync <= 2'b0;
        end
        else if (ACCSEL_PCE == 1'b1)
        begin
            accsel1_reg_sync <= accsel_0;
            accsel_int1_reg_sync <= accsel_int0;
        end
    end

    always @(accsel_0 or accsel1_reg or accsel_int0 or accsel_int1_reg)
    begin
        if (ACCSEL_PREG_CLK == "BYPASS")
        begin
            accsel_1 <= accsel_0;
            accsel_int1 <= accsel_int0;
        end else
        begin
            accsel_1 <= accsel1_reg;
            accsel_int1 <= accsel_int1_reg;
        end
    end

    always @(posedge CASISEL_ICLK or posedge CASISEL_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            casisel0_reg_async <= 0;
        end else if (CASISEL_IRESET == 1'b1)
        begin
            casisel0_reg_async <= 0;
        end
        else if (CASISEL_ICE == 1'b1)
        begin
            casisel0_reg_async <= casisel_sig;
        end
    end

    always @(posedge CASISEL_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            casisel0_reg_sync <= 0; 
        end else if (CASISEL_IRESET == 1'b1)
        begin
            casisel0_reg_sync <= 0;
        end
        else if (CASISEL_ICE == 1'b1)
        begin
            casisel0_reg_sync <= casisel_sig;
        end
    end

    always @(casisel_sig or casisel0_reg)
    begin
        if (CASISEL_IREG_CLK == "BYPASS")
        begin
            casisel_0 <= casisel_sig;
        end else
        begin
            casisel_0 <= casisel0_reg;
        end
    end

    always @(posedge CASISEL_PCLK or posedge CASISEL_PRESET or negedge grstn)
    begin
        if (!grstn) begin
            casisel1_reg_async <= 0;
        end else if (CASISEL_PRESET == 1'b1)
        begin
            casisel1_reg_async <= 0;
        end
        else if (CASISEL_PCE == 1'b1)
        begin
            casisel1_reg_async <= casisel_0;
        end
    end

    always @(posedge CASISEL_PCLK or negedge grstn)
    begin
        if (!grstn) begin
            casisel1_reg_sync <= 0; 
        end else if (CASISEL_PRESET == 1'b1)
        begin
            casisel1_reg_sync <= 0;
        end
        else if (CASISEL_PCE == 1'b1)
        begin
            casisel1_reg_sync <= casisel_0;
        end
    end

    always @(casisel_0 or casisel1_reg)
    begin
        if (CASISEL_PREG_CLK == "BYPASS")
        begin
            casisel_1 <= casisel_0;
        end else
        begin
            casisel_1 <= casisel1_reg;
        end
    end

    always @(posedge CSEL_ICLK or posedge CSEL_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            csel0_reg_async <= 0;
        end else if (CSEL_IRESET == 1'b1)
        begin
            csel0_reg_async <= 0;
        end
        else if (CSEL_ICE == 1'b1)
        begin
            csel0_reg_async <= csel_sig;
        end
    end

    always @(posedge CSEL_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            csel0_reg_sync <= 0; 
        end else if (CSEL_IRESET == 1'b1)
        begin
            csel0_reg_sync <= 0;
        end
        else if (CSEL_ICE == 1'b1)
        begin
            csel0_reg_sync <= csel_sig;
        end
    end

    always @(csel_sig or csel0_reg)
    begin
        if (CSEL_IREG_CLK == "BYPASS")
        begin
            csel_0 <= csel_sig;
        end else
        begin
            csel_0 <= csel0_reg;
        end
    end

    always @(posedge CSEL_PCLK or posedge CSEL_PRESET or negedge grstn)
    begin
        if (!grstn) begin
            csel1_reg_async <= 0;
        end else if (CSEL_PRESET == 1'b1)
        begin
            csel1_reg_async <= 0;
        end
        else if (CSEL_PCE == 1'b1)
        begin
            csel1_reg_async <= csel_0;
        end
    end

    always @(posedge CSEL_PCLK or negedge grstn)
    begin
        if (!grstn) begin
            csel1_reg_sync <= 0; 
        end else if (CSEL_PRESET == 1'b1)
        begin
            csel1_reg_sync <= 0;
        end
        else if (CSEL_PCE == 1'b1)
        begin
            csel1_reg_sync <= csel_0;
        end
    end

    always @(csel_0 or csel1_reg)
    begin
        if (CSEL_PREG_CLK == "BYPASS")
        begin
            csel_1 <= csel_0;
        end else
        begin
            csel_1 <= csel1_reg;
        end
    end


    always @(posedge ADDSUB0_ICLK or posedge ADDSUB0_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            addsub0_reg0_async <= 0;
        end else if (ADDSUB0_IRESET == 1'b1)
        begin
            addsub0_reg0_async <= 0;
        end
        else if (ADDSUB0_ICE == 1'b1)
        begin
            addsub0_reg0_async <= addsub0_sig;
        end
    end

    always @(posedge ADDSUB0_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            addsub0_reg0_sync <= 0; 
        end else if (ADDSUB0_IRESET == 1'b1)
        begin
            addsub0_reg0_sync <= 0;
        end
        else if (ADDSUB0_ICE == 1'b1)
        begin
            addsub0_reg0_sync <= addsub0_sig;
        end
    end

    always @(addsub0_sig or addsub0_reg0)
    begin
        if (ADDSUB0_IREG_CLK == "BYPASS")
        begin
            addsub0_0 <= addsub0_sig;
        end else
        begin
            addsub0_0 <= addsub0_reg0;
        end
    end

    always @(posedge ADDSUB0_PCLK or posedge ADDSUB0_PRESET or negedge grstn)
    begin
        if (!grstn) begin
            addsub0_reg1_async <= 0;
        end else if (ADDSUB0_PRESET == 1'b1)
        begin
            addsub0_reg1_async <= 0;
        end
        else if (ADDSUB0_PCE == 1'b1)
        begin
            addsub0_reg1_async <= addsub0_0;
        end
    end

    always @(posedge ADDSUB0_PCLK or negedge grstn)
    begin
        if (!grstn) begin
            addsub0_reg1_sync <= 0; 
        end else if (ADDSUB0_PRESET == 1'b1)
        begin
            addsub0_reg1_sync <= 0;
        end
        else if (ADDSUB0_PCE == 1'b1)
        begin
            addsub0_reg1_sync <= addsub0_0;
        end
    end

    always @(addsub0_0 or addsub0_reg1)
    begin
        if (ADDSUB0_PREG_CLK == "BYPASS")
        begin
            addsub0_1 <= addsub0_0;
        end else
        begin
            addsub0_1 <= addsub0_reg1;
        end
    end

    always @(posedge ADDSUB1_ICLK or posedge ADDSUB1_IRESET or negedge grstn)
    begin
        if (!grstn) begin
            addsub1_reg0_async <= 0;
        end else if (ADDSUB1_IRESET == 1'b1)
        begin
            addsub1_reg0_async <= 0;
        end
        else if (ADDSUB1_ICE == 1'b1)
        begin
            addsub1_reg0_async <= addsub1_sig;
        end
    end

    always @(posedge ADDSUB1_ICLK or negedge grstn)
    begin
        if (!grstn) begin
            addsub1_reg0_sync <= 0; 
        end else if (ADDSUB1_IRESET == 1'b1)
        begin
            addsub1_reg0_sync <= 0;
        end
        else if (ADDSUB1_ICE == 1'b1)
        begin
            addsub1_reg0_sync <= addsub1_sig;
        end
    end

    always @(addsub1_sig or addsub1_reg0)
    begin
        if (ADDSUB1_IREG_CLK == "BYPASS")
        begin
            addsub1_0 <= addsub1_sig;
        end else
        begin
            addsub1_0 <= addsub1_reg0;
        end
    end

    always @(posedge ADDSUB1_PCLK or posedge ADDSUB1_PRESET or negedge grstn)
    begin
        if (!grstn) begin
            addsub1_reg1_async <= 0;
        end else if (ADDSUB1_PRESET == 1'b1)
        begin
            addsub1_reg1_async <= 0;
        end
        else if (ADDSUB1_PCE == 1'b1)
        begin
            addsub1_reg1_async <= addsub1_0;
        end
    end

    always @(posedge ADDSUB1_PCLK or negedge grstn)
    begin
        if (!grstn) begin
            addsub1_reg1_sync <= 0; 
        end else if (ADDSUB1_PRESET == 1'b1)
        begin
            addsub1_reg1_sync <= 0;
        end
        else if (ADDSUB1_PCE == 1'b1)
        begin
            addsub1_reg1_sync <= addsub1_0;
        end
    end

    always @(addsub1_0 or addsub1_reg1)
    begin
        if (ADDSUB1_PREG_CLK == "BYPASS")
        begin
            addsub1_1 <= addsub1_0;
        end else
        begin
            addsub1_1 <= addsub1_reg1;
        end
    end


    assign a0[44:0] = (MULT12X12_EN == "FALSE")? {{18{a_in[26]}},a_in[26:0]} : {{33{a_12_in[11]}},a_12_in[11:0]};
    assign b0[44:0] = (MULT12X12_EN == "FALSE")? {{27{inb[17]}},inb[17:0]} : {{33{inb[11]}}, inb[11:0]};

    assign mult_out = a0 * b0 ;

    // pipeline reg
    always @(posedge P_CLK or posedge P_RESET or negedge grstn)
    begin
        if (!grstn) begin
            out0_reg_async <= 0;
        end else if (P_RESET == 1'b1)
        begin
            out0_reg_async <= 0;
        end
        else if (P_CE == 1'b1)
        begin
            out0_reg_async <= mult_out;
        end
    end

    always @(posedge P_CLK or negedge grstn)
    begin
        if (!grstn) begin
            out0_reg_sync <= 0;
        end else if (P_RESET == 1'b1)
        begin
            out0_reg_sync <= 0;
        end
        else if (P_CE == 1'b1)
        begin
            out0_reg_sync <= mult_out;
        end
    end

    always @(posedge O_CLK or posedge O_RESET or negedge grstn)
    begin
        if (!grstn) begin
            out_preg_async <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_preg_async <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_preg_async <= d_out;
        end
    end

    always @(posedge O_CLK or negedge grstn)
    begin
        if (!grstn) begin
            out_preg_sync <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_preg_sync <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_preg_sync <= d_out;
        end
    end

    always @(mult_out or out0_reg)
    begin
        if (PREG_CLK == "BYPASS")
        begin
            out0 = mult_out;
        end else
        begin
            out0 = out0_reg;
        end
    end

    always @(d_out or out_preg)
    begin
        if (FB_PREG_EN == "FALSE")
        begin
            dout_reg = d_out;
        end else
        begin
            dout_reg = out_preg;
        end
    end

    assign m_out0 = {{3{out0[44]}},out0[44:0]};


    assign acc_load = (accsel_int1 == 2'b10 || accsel_int1 == 2'b11) ? dout_reg : ((accsel_int1 == 2'b01) ? PRE_LOAD : 48'b0);
    assign d_casi = (casisel_1 == 1'b1) ? CASI : 48'b0;
    assign c_sig = (csel_1 == 1'b1) ? inc_1 : 48'b0;

    always @(acc_load or m_out0 or d_casi or c_sig or addsub0_1 or addsub1_1)
    begin
        if(addsub0_1 == 1'b0 && addsub1_1 == 1'b0) begin
            alu_out = acc_load + m_out0 + c_sig + d_casi;
        end else if(addsub0_1 == 1'b0 && addsub1_1 == 1'b1) begin
            alu_out = acc_load + m_out0 - c_sig + d_casi;
        end else if(addsub0_1 == 1'b1 && addsub1_1 == 1'b0) begin
            alu_out = acc_load - m_out0 + c_sig + d_casi;
        end else if(addsub0_1 == 1'b1 && addsub1_1 == 1'b1) begin
            alu_out = acc_load - m_out0 - c_sig + d_casi;
        end

    end

    //SOA
    always @(posedge A_CLK or posedge A_RESET or negedge grstn)
    begin
        if (!grstn) begin
            ina_preg_async <= 0;
        end else if (A_RESET == 1'b1)
        begin
            ina_preg_async <= 0;
        end
        else if (A_CE == 1'b1)
        begin
            ina_preg_async <= ina;
        end
    end

    always @(posedge A_CLK or negedge grstn)
    begin
        if (!grstn) begin
            ina_preg_sync <= 0;
        end else if (A_RESET == 1'b1)
        begin
            ina_preg_sync <= 0;
        end
        else if (A_CE == 1'b1)
        begin
            ina_preg_sync <= ina;
        end
    end

    always @(ina or ina_preg)
    begin
        if (SOA_PREG_EN == "FALSE")
        begin
            SOA = ina;
        end else
        begin
            SOA = ina_preg;
        end
    end
      
    // output reg
    always @(posedge O_CLK or posedge O_RESET or negedge grstn)
    begin
        if (!grstn) begin
            out_reg_async <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_reg_async <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_reg_async <= alu_out;
        end
    end

    always @(posedge O_CLK or negedge grstn)
    begin
        if (!grstn) begin
            out_reg_sync <= 0;
        end else if (O_RESET == 1'b1)
        begin
            out_reg_sync <= 0;
        end
        else if (O_CE == 1'b1)
        begin
            out_reg_sync <= alu_out;
        end
    end

    always @(alu_out or out_reg)
    begin
        if (OREG_CLK == "BYPASS")
        begin
            d_out = alu_out;
        end else
        begin
            d_out = out_reg;
        end
    end

    assign DOUT = d_out[47:0];
    assign CASO = d_out[47:0];

endmodule
module MUX16(O, I0, I1, I2, I3, I4, I5, I6, I7, I8, I9, I10, I11, I12, I13, I14, I15, S0, S1, S2, S3);

input I0, I1, I2, I3, I4, I5, I6, I7, I8, I9, I10, I11, I12, I13, I14, I15;
input S0, S1, S2, S3;
output O;

wire O1, O2;

MUX8  mux8_1(O1, I0, I1, I2, I3, I4, I5, I6, I7, S0, S1, S2);
MUX8  mux8_2(O2, I8, I9, I10, I11, I12, I13, I14, I15, S0, S1, S2);

MUX2 mux2_o(O, O1, O2, S3);

endmodule
module MUX2 (O, I0, I1, S0);

input I0,I1;
input S0;
output O;

mux2 mux2_0 (O, I0, I1, S0);

endmodule
module MUX2_LUT5 (O, I0, I1, S0);

input I0,I1;
input S0;
output O;

MUX2 mux2_lut5 (O, I0, I1, S0);

endmodule
module MUX2_LUT6 (O, I0, I1, S0);

input I0,I1;
input S0;
output O;

MUX2 mux2_lut6 (O, I0, I1, S0);

endmodule
module MUX2_LUT7 (O, I0, I1, S0);

input I0,I1;
input S0;
output O;

MUX2 mux2_lut7 (O, I0, I1, S0);

endmodule
module MUX2_LUT8 (O, I0, I1, S0);

input I0,I1;
input S0;
output O;

MUX2 mux2_lut8 (O, I0, I1, S0);

endmodule
module MUX4 (O, I0, I1, I2, I3, S0, S1);

input I0, I1, I2, I3;
input S0, S1;
output O;

wire O1,O2;

MUX2 mux2_1(O1, I0, I1, S0);
MUX2 mux2_2(O2, I2, I3, S0);
MUX2 mux2_0(O, O1, O2, S1);

endmodule
module MUX8 (O, I0, I1, I2, I3, I4, I5, I6, I7, S0, S1, S2);

input I0, I1, I2, I3, I4, I5, I6, I7;
input S0, S1, S2;
output O;

wire O1, O2;

MUX4 mux4_1(O1, I0, I1, I2, I3, S0, S1);
MUX4 mux4_2(O2, I4, I5, I6, I7, S0, S1);
MUX2 mux2_0(O, O1, O2, S2);

endmodule
module SDPB (DO, DI, BLKSELA, BLKSELB, ADA, ADB, CLKA, CLKB, CEA, CEB, OCE, RESET);

parameter READ_MODE = 1'b0; // 1'b0: bypass mode; 1'b1: pipeline mode
parameter BIT_WIDTH_0 = 32; // 1, 2, 4, 8, 16, 32
parameter BIT_WIDTH_1 = 32; // 1, 2, 4, 8, 16, 32
parameter BLK_SEL_0 = 3'b000;
parameter BLK_SEL_1 = 3'b000;
parameter RESET_MODE = "SYNC"; //SYNC,ASYNC
parameter INIT_RAM_00 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_01 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_02 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_03 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_04 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_05 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_06 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_07 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_08 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_09 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0A = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0B = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0C = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0D = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0E = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0F = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_10 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_11 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_12 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_13 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_14 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_15 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_16 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_17 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_18 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_19 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1A = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1B = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1C = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1D = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1E = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1F = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_20 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_21 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_22 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_23 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_24 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_25 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_26 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_27 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_28 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_29 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2A = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2B = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2C = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2D = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2E = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2F = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_30 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_31 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_32 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_33 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_34 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_35 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_36 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_37 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_38 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_39 = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3A = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3B = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3C = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3D = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3E = 256'h0000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3F = 256'h0000000000000000000000000000000000000000000000000000000000000000;

input CLKA, CEA, CLKB, CEB;
input OCE; // clock enable of memory output register
input RESET; // resets output registers, not memory contents
input [13:0] ADA, ADB;
input [31:0] DI;
input [2:0] BLKSELA, BLKSELB;
output [31:0] DO;

reg [31:0] pl_reg,pl_reg_async,pl_reg_sync;
reg [31:0] bp_reg,bp_reg_async,bp_reg_sync;
reg [16383:0] ram_MEM ={INIT_RAM_3F, INIT_RAM_3E, INIT_RAM_3D, INIT_RAM_3C,INIT_RAM_3B, INIT_RAM_3A, INIT_RAM_39, INIT_RAM_38,INIT_RAM_37, INIT_RAM_36, INIT_RAM_35, INIT_RAM_34,INIT_RAM_33, INIT_RAM_32, INIT_RAM_31, INIT_RAM_30,INIT_RAM_2F, INIT_RAM_2E, INIT_RAM_2D, INIT_RAM_2C,INIT_RAM_2B, INIT_RAM_2A, INIT_RAM_29, INIT_RAM_28,INIT_RAM_27, INIT_RAM_26, INIT_RAM_25, INIT_RAM_24,INIT_RAM_23, INIT_RAM_22, INIT_RAM_21, INIT_RAM_20,INIT_RAM_1F, INIT_RAM_1E, INIT_RAM_1D, INIT_RAM_1C,INIT_RAM_1B, INIT_RAM_1A, INIT_RAM_19, INIT_RAM_18,INIT_RAM_17, INIT_RAM_16, INIT_RAM_15, INIT_RAM_14,INIT_RAM_13, INIT_RAM_12, INIT_RAM_11, INIT_RAM_10,INIT_RAM_0F, INIT_RAM_0E, INIT_RAM_0D, INIT_RAM_0C, INIT_RAM_0B, INIT_RAM_0A, INIT_RAM_09, INIT_RAM_08,INIT_RAM_07, INIT_RAM_06, INIT_RAM_05, INIT_RAM_04,INIT_RAM_03, INIT_RAM_02, INIT_RAM_01, INIT_RAM_00} ;
reg [BIT_WIDTH_0-1:0] mem_a;
reg [BIT_WIDTH_1-1:0] mem_b;
reg [13:0] addr_a, addr_b;
reg mc,bs_ena,bs_enb;
wire pcea;
wire pceb;
wire grstn = GSR.GSRO;

integer bit_width_d0 = BIT_WIDTH_0;
integer bit_width_d1 = BIT_WIDTH_1;
integer bit_width_a0, bit_width_a1; // ADDR_WIDTH

initial begin
    bp_reg = 0;
    pl_reg = 0;
    bp_reg_async = 0;
    bp_reg_sync = 0;
    pl_reg_async = 0;
    pl_reg_sync = 0;
    mc = 1'b0;
end

initial begin
	case(bit_width_d0)
		1: bit_width_a0 = 14;
		2: bit_width_a0 = 13;
		4: bit_width_a0 = 12;
		8: bit_width_a0 = 11;
		16: bit_width_a0 = 10;
		32: bit_width_a0 = 9;
		default: begin
		//	$display ("%d: Unsupported data width\n", bit_width_d0);
		//	$finish;
		end
	endcase
	case(bit_width_d1)
		1: bit_width_a1 = 14;
		2: bit_width_a1 = 13;
		4: bit_width_a1 = 12;
		8: bit_width_a1 = 11;
		16: bit_width_a1 = 10;
		32: bit_width_a1 = 9;
		default: begin
		//	$display ("%d: Unsupported data width\n", bit_width_d1);
		//	$finish;
		end
	endcase
end

assign DO = (READ_MODE == 1'b0)? bp_reg: pl_reg;

assign pcea = CEA && bs_ena && grstn;   
assign pceb = CEB && bs_enb;

always @ (BLKSELA, BLKSELB)
begin
	if(BLKSELA == BLK_SEL_0) begin
		bs_ena = 1;
	end else begin
		bs_ena = 0;
	end

    if(BLKSELB == BLK_SEL_1) begin
		bs_enb = 1;
	end else begin
		bs_enb = 0;
	end
end

always@(ADA,ADB,bit_width_a0,bit_width_a1,mc)begin
	if(bit_width_a0==14)begin
		addr_a[13:0] = ADA[13:0];
		mem_a[0] = ram_MEM[addr_a];
	end
	else if(bit_width_a0==13)begin
		addr_a[13:0] = {ADA[13:1],1'b0};
		mem_a[1:0] = {ram_MEM[addr_a+1],ram_MEM[addr_a]};
	end
	else if(bit_width_a0==12)begin
		addr_a[13:0] = {ADA[13:2],2'b00};
		mem_a[3:0] = {ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]};
	end
	else if(bit_width_a0==11)begin
		addr_a[13:0] = {ADA[13:3],3'b000};
		mem_a[7:0] = {ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]};
	end
	else if(bit_width_a0==10)begin
		addr_a[13:0] = {ADA[13:4],4'b0000};
		mem_a[15:0] = {ram_MEM[addr_a+15],ram_MEM[addr_a+14],ram_MEM[addr_a+13],ram_MEM[addr_a+12],ram_MEM[addr_a+11],ram_MEM[addr_a+10],ram_MEM[addr_a+9],ram_MEM[addr_a+8],ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]};
	end
	else if(bit_width_a0==9)begin
		addr_a[13:0] = {ADA[13:5],5'b00000};
		mem_a[31:0] = {ram_MEM[addr_a+31],ram_MEM[addr_a+30],ram_MEM[addr_a+29],ram_MEM[addr_a+28],ram_MEM[addr_a+27],ram_MEM[addr_a+26],ram_MEM[addr_a+25],ram_MEM[addr_a+24],ram_MEM[addr_a+23],ram_MEM[addr_a+22],ram_MEM[addr_a+21],ram_MEM[addr_a+20],ram_MEM[addr_a+19],ram_MEM[addr_a+18],ram_MEM[addr_a+17],ram_MEM[addr_a+16],ram_MEM[addr_a+15],ram_MEM[addr_a+14],ram_MEM[addr_a+13],ram_MEM[addr_a+12],ram_MEM[addr_a+11],ram_MEM[addr_a+10],ram_MEM[addr_a+9],ram_MEM[addr_a+8],ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]};
	end
	if(bit_width_a1==14)begin
		addr_b[13:0] = ADB[13:0];
		mem_b[0]=ram_MEM[addr_b];
	end
	else if(bit_width_a1==13)begin
		addr_b[13:0] = {ADB[13:1],1'b0};
		mem_b[1:0]={ram_MEM[addr_b+1],ram_MEM[addr_b]};
	end
	else if(bit_width_a1==12)begin
		addr_b[13:0] = {ADB[13:2],2'b00};
		mem_b[3:0]={ram_MEM[addr_b+3],ram_MEM[addr_b+2],ram_MEM[addr_b+1],ram_MEM[addr_b]};
	end
	else if(bit_width_a1==11)begin
		addr_b[13:0] = {ADB[13:3],3'b000};
		mem_b[7:0]={ram_MEM[addr_b+7],ram_MEM[addr_b+6],ram_MEM[addr_b+5],ram_MEM[addr_b+4],ram_MEM[addr_b+3],ram_MEM[addr_b+2],ram_MEM[addr_b+1],ram_MEM[addr_b]};
	end
	else if(bit_width_a1==10)begin
		addr_b[13:0] = {ADB[13:4],4'b0000};
		mem_b[15:0]={ram_MEM[addr_b+15],ram_MEM[addr_b+14],ram_MEM[addr_b+13],ram_MEM[addr_b+12],ram_MEM[addr_b+11],ram_MEM[addr_b+10],ram_MEM[addr_b+9],ram_MEM[addr_b+8],ram_MEM[addr_b+7],ram_MEM[addr_b+6],ram_MEM[addr_b+5],ram_MEM[addr_b+4],ram_MEM[addr_b+3],ram_MEM[addr_b+2],ram_MEM[addr_b+1],ram_MEM[addr_b]};

	end
	else if(bit_width_a1==9)begin
		addr_b[13:0] = {ADB[13:5],5'b00000};
		mem_b[31:0]={ ram_MEM[addr_b+31],ram_MEM[addr_b+30],ram_MEM[addr_b+29],ram_MEM[addr_b+28],ram_MEM[addr_b+27],ram_MEM[addr_b+26],ram_MEM[addr_b+25],ram_MEM[addr_b+24],ram_MEM[addr_b+23],ram_MEM[addr_b+22],ram_MEM[addr_b+21],ram_MEM[addr_b+20],ram_MEM[addr_b+19],ram_MEM[addr_b+18],ram_MEM[addr_b+17],ram_MEM[addr_b+16],ram_MEM[addr_b+15],ram_MEM[addr_b+14],ram_MEM[addr_b+13],ram_MEM[addr_b+12],ram_MEM[addr_b+11],ram_MEM[addr_b+10],ram_MEM[addr_b+9],ram_MEM[addr_b+8],ram_MEM[addr_b+7],ram_MEM[addr_b+6],ram_MEM[addr_b+5],ram_MEM[addr_b+4],ram_MEM[addr_b+3],ram_MEM[addr_b+2],ram_MEM[addr_b+1],ram_MEM[addr_b]};

	end
end

always @(posedge CLKA) begin
	if (pcea) begin
	    if(bit_width_d0==1)
			ram_MEM[addr_a] <= DI[0];
		else if(bit_width_d0==2)
			{ram_MEM[addr_a+1],ram_MEM[addr_a]}<=DI[BIT_WIDTH_0-1:0];
		else if(bit_width_d0==4)
			{ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]}<=DI[BIT_WIDTH_0-1:0];
		else if(bit_width_d0==8)
			{ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]}<=DI[BIT_WIDTH_0-1:0];
		else if(bit_width_d0==16) begin
			if(ADA[0] == 1'b1)
				{ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]}<=DI[7:0];
			if(ADA[1] ==1'b1)
				{ram_MEM[addr_a+15],ram_MEM[addr_a+14],ram_MEM[addr_a+13],ram_MEM[addr_a+12],ram_MEM[addr_a+11],ram_MEM[addr_a+10],ram_MEM[addr_a+9],ram_MEM[addr_a+8]}<=DI[15:8];
		end
		else if(bit_width_d0==32) begin
			if(ADA[0] == 1'b1)
				{ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]}<=DI[7:0];
			if(ADA[1] == 1'b1)
				{ram_MEM[addr_a+15],ram_MEM[addr_a+14],ram_MEM[addr_a+13],ram_MEM[addr_a+12],ram_MEM[addr_a+11],ram_MEM[addr_a+10],ram_MEM[addr_a+9],ram_MEM[addr_a+8]}<=DI[15:8];
			if(ADA[2] == 1'b1)
				{ram_MEM[addr_a+23],ram_MEM[addr_a+22],ram_MEM[addr_a+21],ram_MEM[addr_a+20],ram_MEM[addr_a+19],ram_MEM[addr_a+18],ram_MEM[addr_a+17],ram_MEM[addr_a+16]} <=DI[23:16];
			if(ADA[3] == 1'b1)
				{ram_MEM[addr_a+31],ram_MEM[addr_a+30],ram_MEM[addr_a+29],ram_MEM[addr_a+28],ram_MEM[addr_a+27],ram_MEM[addr_a+26],ram_MEM[addr_a+25],ram_MEM[addr_a+24]} <=DI[31:24];
		end
		mc <= ~mc;
	end
end

always @ (bp_reg_async or bp_reg_sync or pl_reg_async or pl_reg_sync) begin
    if(RESET_MODE == "ASYNC") begin
        bp_reg <= bp_reg_async;
        pl_reg <= pl_reg_async;
    end
    else begin
        bp_reg <= bp_reg_sync;
        pl_reg <= pl_reg_sync;
    end
end

always @(posedge CLKB or posedge RESET or negedge grstn) begin
	if (!grstn) begin
		pl_reg_async <= 0;
		bp_reg_async <= 0;
	end else if (RESET) begin
		pl_reg_async <= 0;
		bp_reg_async <= 0;
	end else begin
		if(OCE) begin
			pl_reg_async <= bp_reg;
		end
		if (pceb) begin
			bp_reg_async[BIT_WIDTH_1-1:0] <= mem_b[BIT_WIDTH_1-1:0];
		end
	end
end

always @(posedge CLKB or negedge grstn) begin
	if (!grstn) begin
		pl_reg_sync <= 0;
		bp_reg_sync <= 0;
	end else if (RESET) begin
		pl_reg_sync <= 0;
		bp_reg_sync <= 0;
	end else begin
		if(OCE) begin
			pl_reg_sync <= bp_reg;
		end
		if (pceb) begin
			bp_reg_sync[BIT_WIDTH_1-1:0] <= mem_b[BIT_WIDTH_1-1:0];
		end
	end
end

endmodule
module SDPX9B (DO, DI, BLKSELA, BLKSELB, ADA, ADB, CLKA, CLKB, CEA, CEB, OCE, RESET);

parameter READ_MODE = 1'b0; // 1'b0: bypass mode; 1'b1: pipeline mode
parameter BIT_WIDTH_0 = 36; // 9, 18, 36
parameter BIT_WIDTH_1 = 36; // 9, 18, 36
parameter BLK_SEL_0 = 3'b000;
parameter BLK_SEL_1 = 3'b000;
parameter RESET_MODE = "SYNC"; //SYNC,ASYNC
parameter INIT_RAM_00 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000; 
parameter INIT_RAM_01 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_02 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_03 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_04 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_05 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_06 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_07 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_08 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_09 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0A = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0B = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0C = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0D = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0E = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_0F = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_10 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_11 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_12 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_13 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_14 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_15 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_16 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_17 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_18 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_19 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1A = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1B = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1C = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1D = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1E = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_1F = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_20 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_21 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_22 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_23 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_24 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_25 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_26 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_27 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_28 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_29 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2A = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2B = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2C = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2D = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2E = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_2F = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_30 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_31 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_32 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_33 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_34 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_35 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_36 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_37 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_38 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_39 = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3A = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3B = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3C = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3D = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3E = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;
parameter INIT_RAM_3F = 288'h000000000000000000000000000000000000000000000000000000000000000000000000;

input CLKA, CEA, CLKB, CEB;
input OCE; // clock enable of memory output register
input RESET; // resets output registers, not memory contents
input [13:0] ADA, ADB;
input [2:0] BLKSELA, BLKSELB;
input [35:0] DI;
output [35:0] DO;

reg [35:0] bp_reg,bp_reg_async,bp_reg_sync;
reg [35:0] pl_reg,pl_reg_async,pl_reg_sync;
reg [18431:0] ram_MEM = {INIT_RAM_3F, INIT_RAM_3E, INIT_RAM_3D, INIT_RAM_3C,INIT_RAM_3B, INIT_RAM_3A, INIT_RAM_39, INIT_RAM_38,INIT_RAM_37, INIT_RAM_36, INIT_RAM_35, INIT_RAM_34,INIT_RAM_33, INIT_RAM_32, INIT_RAM_31, INIT_RAM_30,INIT_RAM_2F, INIT_RAM_2E, INIT_RAM_2D, INIT_RAM_2C,INIT_RAM_2B, INIT_RAM_2A, INIT_RAM_29, INIT_RAM_28,INIT_RAM_27, INIT_RAM_26, INIT_RAM_25, INIT_RAM_24,INIT_RAM_23, INIT_RAM_22, INIT_RAM_21, INIT_RAM_20,INIT_RAM_1F, INIT_RAM_1E, INIT_RAM_1D, INIT_RAM_1C,INIT_RAM_1B, INIT_RAM_1A, INIT_RAM_19, INIT_RAM_18,INIT_RAM_17, INIT_RAM_16, INIT_RAM_15, INIT_RAM_14,INIT_RAM_13, INIT_RAM_12, INIT_RAM_11, INIT_RAM_10,INIT_RAM_0F, INIT_RAM_0E, INIT_RAM_0D, INIT_RAM_0C, INIT_RAM_0B, INIT_RAM_0A, INIT_RAM_09, INIT_RAM_08,INIT_RAM_07, INIT_RAM_06, INIT_RAM_05, INIT_RAM_04,INIT_RAM_03, INIT_RAM_02, INIT_RAM_01, INIT_RAM_00};
reg [BIT_WIDTH_0-1:0] mem_a;
reg [BIT_WIDTH_1-1:0] mem_b;
reg [14:0] addr_a, addr_b;
reg mc,bs_ena,bs_enb;
wire pcea,pceb;
integer bit_width_d0 = BIT_WIDTH_0;
integer bit_width_d1 = BIT_WIDTH_1;
integer bit_width_a0, bit_width_a1; // ADDR_WIDTH
wire grstn = GSR.GSRO;

initial begin
    bp_reg = 0;
    pl_reg = 0;
    bp_reg_async = 0;
    bp_reg_sync = 0;
    pl_reg_async = 0;
    pl_reg_sync = 0;
    mc = 1'b0;
end

initial begin
	case(bit_width_d0)
		9: bit_width_a0 = 11;
		18: bit_width_a0 = 10;
		36: bit_width_a0 = 9;
		default: begin
		//	$display ("%d: Unsupported data width\n", bit_width_d0);
		//	$finish;
		end
	endcase
	case(bit_width_d1)
		9: bit_width_a1 = 11;
		18: bit_width_a1 = 10;
		36: bit_width_a1 = 9;
		default: begin
		//	$display ("%d: Unsupported data width\n", bit_width_d1);
		//	$finish;
		end
	endcase
end

assign DO = (READ_MODE == 1'b0)? bp_reg: pl_reg;

assign pcea = CEA && bs_ena && grstn;   
assign pceb = CEB && bs_enb;
always @ (BLKSELA, BLKSELB)
begin
	if(BLKSELA == BLK_SEL_0) begin
		bs_ena = 1;
	end else begin
		bs_ena = 0;
	end

    if(BLKSELB == BLK_SEL_1) begin
		bs_enb = 1;
	end else begin
		bs_enb = 0;
	end
end

always@(ADA,ADB,bit_width_a0,bit_width_a1,mc)begin
	if(bit_width_a0==11)begin
		addr_a[14:0] = ADA[13:3]*bit_width_d0;
		mem_a[8:0] = {ram_MEM[addr_a+8],ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]};
	end
	else if(bit_width_a0==10)begin
		addr_a[14:0] = ADA[13:4]*bit_width_d0;
		mem_a[17:0] = {ram_MEM[addr_a+17],ram_MEM[addr_a+16],ram_MEM[addr_a+15],ram_MEM[addr_a+14],ram_MEM[addr_a+13],ram_MEM[addr_a+12],ram_MEM[addr_a+11],ram_MEM[addr_a+10],ram_MEM[addr_a+9],ram_MEM[addr_a+8],ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]};
	end
	else if(bit_width_a0==9)begin
		addr_a[14:0] = ADA[13:5]*bit_width_d0;
		mem_a[35:0] = {ram_MEM[addr_a+35],ram_MEM[addr_a+34],ram_MEM[addr_a+33],ram_MEM[addr_a+32],ram_MEM[addr_a+31],ram_MEM[addr_a+30],ram_MEM[addr_a+29],ram_MEM[addr_a+28],ram_MEM[addr_a+27],ram_MEM[addr_a+26],ram_MEM[addr_a+25],ram_MEM[addr_a+24],ram_MEM[addr_a+23],ram_MEM[addr_a+22],ram_MEM[addr_a+21],ram_MEM[addr_a+20],ram_MEM[addr_a+19],ram_MEM[addr_a+18],ram_MEM[addr_a+17],ram_MEM[addr_a+16],ram_MEM[addr_a+15],ram_MEM[addr_a+14],ram_MEM[addr_a+13],ram_MEM[addr_a+12],ram_MEM[addr_a+11],ram_MEM[addr_a+10],ram_MEM[addr_a+9],ram_MEM[addr_a+8],ram_MEM[addr_a+7],ram_MEM[addr_a+6],ram_MEM[addr_a+5],ram_MEM[addr_a+4],ram_MEM[addr_a+3],ram_MEM[addr_a+2],ram_MEM[addr_a+1],ram_MEM[addr_a]};
	end

	if(bit_width_a1==11)begin
		addr_b[14:0] = ADB[13:3]*bit_width_d1;
		mem_b[8:0] = {ram_MEM[addr_b+8],ram_MEM[addr_b+7],ram_MEM[addr_b+6],ram_MEM[addr_b+5],ram_MEM[addr_b+4],ram_MEM[addr_b+3],ram_MEM[addr_b+2],ram_MEM[addr_b+1],ram_MEM[addr_b]};
	end
	else if(bit_width_a1==10)begin
		addr_b[14:0] = ADB[13:4]*bit_width_d1;
		mem_b[17:0] = {ram_MEM[addr_b+17],ram_MEM[addr_b+16],ram_MEM[addr_b+15],ram_MEM[addr_b+14],ram_MEM[addr_b+13],ram_MEM[addr_b+12],ram_MEM[addr_b+11],ram_MEM[addr_b+10],ram_MEM[addr_b+9],ram_MEM[addr_b+8],ram_MEM[addr_b+7],ram_MEM[addr_b+6],ram_MEM[addr_b+5],ram_MEM[addr_b+4],ram_MEM[addr_b+3],ram_MEM[addr_b+2],ram_MEM[addr_b+1],ram_MEM[addr_b]};
	end
	else if(bit_width_a1==9)begin
		addr_b[14:0] = ADB[13:5]*bit_width_d1;
		mem_b[35:0] = {ram_MEM[addr_b+35],ram_MEM[addr_b+34],ram_MEM[addr_b+33],ram_MEM[addr_b+32],ram_MEM[addr_b+31],ram_MEM[addr_b+30],ram_MEM[addr_b+29],ram_MEM[addr_b+28],ram_MEM[addr_b+27],ram_MEM[addr_b+26],ram_MEM[addr_b+25],ram_MEM[addr_b+24],ram_MEM[addr_b+23],ram_MEM[addr_b+22],ram_MEM[addr_b+21],ram_MEM[addr_b+20],ram_MEM[addr_b+19],ram_MEM[addr_b+18],ram_MEM[addr_b+17],ram_MEM[addr_b+16],ram_MEM[addr_b+15],ram_MEM[addr_b+14],ram_MEM[addr_b+13],ram_MEM[addr_b+12],ram_MEM[addr_b+11],ram_MEM[addr_b+10],ram_MEM[addr_b+9],ram_MEM[addr_b+8],ram_MEM[addr_b+7],ram_MEM[addr_b+6],ram_MEM[addr_b+5],ram_MEM[addr_b+4],ram_MEM[addr_b+3],ram_MEM[addr_b+2],ram_MEM[addr_b+1],ram_MEM[addr_b]};
	end
end

always @(posedge CLKA) begin		
	if (pcea) begin
		if(bit_width_d0 == 9) begin
			{ram_MEM [addr_a+8],ram_MEM [addr_a+7], ram_MEM [addr_a+6], ram_MEM [addr_a+5], ram_MEM [addr_a+4], ram_MEM [addr_a+3], ram_MEM [addr_a+2], ram_MEM [addr_a+1], ram_MEM [addr_a]} <= DI[8:0];
		end else if(bit_width_d0 == 18) begin
			if(ADA[0] == 1'b1)
				{ram_MEM [addr_a+8],ram_MEM [addr_a+7], ram_MEM [addr_a+6], ram_MEM [addr_a+5], ram_MEM [addr_a+4], ram_MEM [addr_a+3], ram_MEM [addr_a+2], ram_MEM [addr_a+1], ram_MEM [addr_a]} <= DI[8:0];
			if(ADA[1] == 1'b1)
				{ram_MEM[addr_a+17],ram_MEM[addr_a+16],ram_MEM[addr_a+15],ram_MEM[addr_a+14],ram_MEM[addr_a+13],ram_MEM[addr_a+12],ram_MEM[addr_a+11],ram_MEM[addr_a+10],ram_MEM[addr_a+9]} <= DI[17:9];
		end
		else if(bit_width_d0 == 36) begin
			if(ADA[0] == 1'b1)
				{ram_MEM [addr_a+8],ram_MEM [addr_a+7], ram_MEM [addr_a+6], ram_MEM [addr_a+5], ram_MEM [addr_a+4], ram_MEM [addr_a+3], ram_MEM [addr_a+2], ram_MEM [addr_a+1], ram_MEM [addr_a]} <= DI[8:0];
			if(ADA[1] == 1'b1)
				{ram_MEM[addr_a+17],ram_MEM[addr_a+16],ram_MEM[addr_a+15],ram_MEM[addr_a+14],ram_MEM[addr_a+13],ram_MEM[addr_a+12],ram_MEM[addr_a+11],ram_MEM[addr_a+10],ram_MEM[addr_a+9]} <= DI[17:9];
			if(ADA[2] == 1'b1)
				{ram_MEM[addr_a+26],ram_MEM[addr_a+25],ram_MEM[addr_a+24],ram_MEM[addr_a+23],ram_MEM[addr_a+22],ram_MEM[addr_a+21],ram_MEM[addr_a+20],ram_MEM[addr_a+19],ram_MEM[addr_a+18]} <= DI[26:18];
			if(ADA[3] == 1'b1)
				{ram_MEM[addr_a+35],ram_MEM[addr_a+34],ram_MEM[addr_a+33],ram_MEM[addr_a+32],ram_MEM[addr_a+31],ram_MEM[addr_a+30],ram_MEM[addr_a+29],ram_MEM[addr_a+28],ram_MEM[addr_a+27]} <= DI[35:27];
		end
		mc <= ~mc;
	end
end	

always @ (bp_reg_async or bp_reg_sync or pl_reg_async or pl_reg_sync) begin
    if(RESET_MODE == "ASYNC") begin
        bp_reg <= bp_reg_async;
        pl_reg <= pl_reg_async;
    end
    else begin
        bp_reg <= bp_reg_sync;
        pl_reg <= pl_reg_sync;
    end
end

always @(posedge CLKB or posedge RESET or negedge grstn) begin
	if (!grstn) begin
		bp_reg_async <=0;
		pl_reg_async <= 0;
	end else if (RESET) begin
		bp_reg_async <=0;
		pl_reg_async <= 0;
	end else begin
		if(OCE) begin
			pl_reg_async <= bp_reg;
		end
		if (pceb) begin
			bp_reg_async[BIT_WIDTH_1-1:0] <= mem_b[BIT_WIDTH_1-1:0];
		end
	end
end

always @(posedge CLKB or negedge grstn) begin
	if (!grstn) begin
		bp_reg_sync <=0;
		pl_reg_sync <= 0;
	end else if (RESET) begin
		bp_reg_sync <=0;
		pl_reg_sync <= 0;
	end else begin
		if(OCE) begin
			pl_reg_sync <= bp_reg;
		end
		if (pceb) begin
			bp_reg_sync[BIT_WIDTH_1-1:0] <= mem_b[BIT_WIDTH_1-1:0];
		end
	end
end

endmodule
module VCC (V);

output V;

wire V;

assign V = 1'b1;

endmodule