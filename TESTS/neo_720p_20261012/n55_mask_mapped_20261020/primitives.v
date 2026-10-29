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

endmodule // DFFCE (positive clock edge; asynchronous clear; clock enable)
module GSR (GSRI);

input GSRI;

wire GSRO;

assign GSRO = GSRI;

endmodule //GSR (global set/reset control)
module LUT2 (F, I0, I1);

parameter INIT = 4'h0;

input I0, I1;
output F;

MUX4 lut_2 (F, INIT[0], INIT[1], INIT[2], INIT[3], I0, I1);

endmodule //lut2
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