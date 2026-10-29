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
module GSR (GSRI);

input GSRI;

wire GSRO;

assign GSRO = GSRI;

endmodule //GSR (global set/reset control)
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