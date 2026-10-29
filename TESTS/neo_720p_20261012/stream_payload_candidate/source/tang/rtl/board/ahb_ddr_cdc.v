// AE350 AHB64 -> DDR UI128. Both commands and completions cross through
// dual-clock FIFOs; no request, ready, empty or completion bypasses them.
// One AHB data phase is outstanding. SEQ beats are handled like NONSEQ;
// the master retains address/data while HREADY is low, including cache bursts.
// rst_n is the common transaction reset: downstream DDR arbitration/read tags
// must be reset with it (the integration uses loss of DDR calibration).
`default_nettype none
module ahb_ddr_cdc (
    input wire hclk, ui_clk, rst_n,
    input wire [31:0] haddr,
    input wire [2:0] hsize,
    input wire hwrite,
    input wire [1:0] htrans,
    input wire [63:0] hwdata,
    output wire hready,
    output wire [1:0] hresp,
    output reg [63:0] hrdata,
    input wire cmd_ready, wr_ready,
    output wire cmd_en, wr_en,
    output wire [2:0] cmd,
    output wire [28:0] addr,
    output wire [127:0] wr_data,
    output wire [15:0] wr_mask,
    input wire [127:0] rd_data,
    input wire rd_valid,
    output wire [15:0] dbg
);
    // Assertion is asynchronous even when either clock is stopped. The FIFO
    // itself resets synchronously: each local release holds it reset for at
    // least three edges. Exchange release levels before permitting traffic,
    // so a stopped peer cannot publish its pre-reset pointer/head on restart.
    (* ASYNC_REG = "TRUE" *) reg [2:0] h_release = 0, u_release = 0;
    (* ASYNC_REG = "TRUE" *) reg [1:0] u_up_h = 0, h_up_u = 0;
    always @(posedge hclk or negedge rst_n)
        if (!rst_n) begin h_release<=0; u_up_h<=0; end
        else begin h_release<={h_release[1:0],1'b1}; u_up_h<={u_up_h[0],u_release[2]}; end
    always @(posedge ui_clk or negedge rst_n)
        if (!rst_n) begin u_release<=0; h_up_u<=0; end
        else begin u_release<={u_release[1:0],1'b1}; h_up_u<={h_up_u[0],h_release[2]}; end
    wire h_reset = !h_release[2] || !u_up_h[1];
    wire u_reset = !u_release[2] || !h_up_u[1];

    localparam H_IDLE=3'd0, H_DATA=3'd1, H_WAIT=3'd2, H_REPLY=3'd3,
               H_ERROR1=3'd4, H_ERROR2=3'd5;
    reg [2:0] hs=H_IDLE;
    reg write_q;
    reg [26:0] address_q;
    reg [7:0] mask_q;
    wire request_ready, request_valid, request_pop;
    wire [99:0] request;
    wire response_ready, response_valid;
    wire [63:0] response;
    wire request_push = !h_reset && hs==H_DATA && request_ready;
    wire response_pop = !h_reset && hs==H_WAIT && response_valid;
    assign hready = !h_reset && (hs==H_IDLE || hs==H_REPLY || hs==H_ERROR2);
    assign hresp = (hs==H_ERROR1 || hs==H_ERROR2) ? 2'b01 : 2'b00;
    wire invalid = hsize>3 || haddr[31:30]!=0 ||
                   (hsize==1 && haddr[0]) ||
                   (hsize==2 && |haddr[1:0]) ||
                   (hsize==3 && |haddr[2:0]);
    wire [7:0] byte_enable = hsize==0 ? (8'h01 << haddr[2:0]) :
                            hsize==1 ? (8'h03 << haddr[2:0]) :
                            hsize==2 ? (8'h0f << haddr[2:0]) : 8'hff;
    always @(posedge hclk) begin
        if (h_reset) begin hs<=H_IDLE; hrdata<=0; write_q<=0; address_q<=0; mask_q<=8'hff; end
        else begin
            case (hs)
                H_IDLE,H_REPLY,H_ERROR2: begin
                    hs<=H_IDLE;
                    if (htrans[1]) begin
                        write_q<=hwrite; address_q<=haddr[29:3]; mask_q<=~byte_enable;
                        hs<=invalid ? H_ERROR1 : H_DATA;
                    end
                end
                H_DATA: if(request_ready) hs<=H_WAIT;
                H_WAIT: if(response_valid) begin hrdata<=response; hs<=H_REPLY; end
                H_ERROR1: hs<=H_ERROR2;
                default: hs<=H_IDLE;
            endcase
        end
    end

    ddr_dcfifo #(.WIDTH(100),.DEPTH_LOG2(2)) u_requests (
        .wr_clk(hclk),.wr_rst(h_reset),.wr_valid(request_push),
        .wr_data({write_q,address_q,mask_q,hwdata}),.wr_ready(request_ready),
        .wr_full(),.wr_lost(),.wr_count(),
        .rd_clk(ui_clk),.rd_rst(u_reset),.rd_valid(request_valid),
        .rd_data(request),.rd_ready(request_pop),.rd_count());

    localparam U_IDLE=2'd0, U_ISSUE=2'd1, U_READ=2'd2, U_REPLY=2'd3;
    reg [1:0] us=U_IDLE;
    reg [99:0] active;
    reg [63:0] result;
    wire is_write=active[99];
    wire upper=active[72]; // byte address bit 3, within the aligned 16-byte UI beat
    assign request_pop = !u_reset && us==U_IDLE && request_valid;
    assign cmd_en = !u_reset && us==U_ISSUE && cmd_ready && (!is_write || wr_ready);
    assign wr_en = cmd_en && is_write;
    assign cmd = is_write ? 3'b000 : 3'b001;
    assign addr = {active[98:73],3'b000}; // 16-bit words, aligned to 16 bytes
    assign wr_data = {active[63:0],active[63:0]};
    assign wr_mask = upper ? {active[71:64],8'hff} : {8'hff,active[71:64]};
    wire [63:0] read_half = upper ? rd_data[127:64] : rd_data[63:0];
    wire response_push = !u_reset && us==U_REPLY && response_ready;
    always @(posedge ui_clk) begin
        if(u_reset) begin us<=U_IDLE; active<=0; result<=0; end
        else case(us)
            U_IDLE: if(request_valid) begin active<=request; us<=U_ISSUE; end
            U_ISSUE: if(cmd_en) begin
                if(is_write) begin result<=0; us<=U_REPLY; end
                else if(rd_valid) begin result<=read_half; us<=U_REPLY; end
                else us<=U_READ;
            end
            U_READ: if(rd_valid) begin result<=read_half; us<=U_REPLY; end
            U_REPLY: if(response_ready) us<=U_IDLE;
        endcase
    end
    ddr_dcfifo #(.WIDTH(64),.DEPTH_LOG2(2)) u_responses (
        .wr_clk(ui_clk),.wr_rst(u_reset),.wr_valid(response_push),
        .wr_data(result),.wr_ready(response_ready),.wr_full(),.wr_lost(),.wr_count(),
        .rd_clk(hclk),.rd_rst(h_reset),.rd_valid(response_valid),
        .rd_data(response),.rd_ready(response_pop),.rd_count());
    // Local-domain state only; debug is observational, never handshake logic.
    assign dbg={8'b0,h_reset,response_valid,request_ready,hs,2'b0};
endmodule
`default_nettype wire
