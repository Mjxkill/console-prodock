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

endmodule // ALU: 2-input arithmetic logic unit
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

endmodule // DFFRE (positive clock edge; synchronous reset takes precedence over clock enable)
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

endmodule // DFFSE (positive clock edge; synchronous set takes precedence over clock enable)
module GND (G);

output G;

wire G;

assign G = 1'b0;

endmodule
module GSR (GSRI);

input GSRI;

wire GSRO;

assign GSRO = GSRI;

endmodule //GSR (global set/reset control)
module INV (O, I);

input  I;
output O;

assign O = !I;
        
endmodule // inv
module LUT2 (F, I0, I1);

parameter INIT = 4'h0;

input I0, I1;
output F;

MUX4 lut_2 (F, INIT[0], INIT[1], INIT[2], INIT[3], I0, I1);

endmodule //lut2
module LUT3 (F, I0, I1, I2);

parameter INIT = 8'h00;

input I0, I1, I2;
output F;

MUX8 lut_3 (F, INIT[0], INIT[1], INIT[2], INIT[3], INIT[4], INIT[5], INIT[6], INIT[7], I0, I1, I2);

endmodule //lut3
module LUT4 (F, I0, I1, I2, I3);

parameter INIT = 16'h0000;

input I0, I1, I2, I3;
output F;

MUX16 lut_4(F, INIT[0], INIT[1], INIT[2], INIT[3], INIT[4], INIT[5], INIT[6], INIT[7], INIT[8], INIT[9], INIT[10], INIT[11], INIT[12], INIT[13], INIT[14], INIT[15], I0, I1, I2, I3);

endmodule //lut4
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

endmodule //MUX2
module MUX4 (O, I0, I1, I2, I3, S0, S1);

input I0, I1, I2, I3;
input S0, S1;
output O;

wire O1,O2;

MUX2 mux2_1(O1, I0, I1, S0);
MUX2 mux2_2(O2, I2, I3, S0);
MUX2 mux2_0(O, O1, O2, S1);

endmodule // MUX4
module MUX8 (O, I0, I1, I2, I3, I4, I5, I6, I7, S0, S1, S2);

input I0, I1, I2, I3, I4, I5, I6, I7;
input S0, S1, S2;
output O;

wire O1, O2;

MUX4 mux4_1(O1, I0, I1, I2, I3, S0, S1);
MUX4 mux4_2(O2, I4, I5, I6, I7, S0, S1);
MUX2 mux2_0(O, O1, O2, S2);

endmodule //MUX8
module VCC (V);

output V;

wire V;

assign V = 1'b1;

endmodule