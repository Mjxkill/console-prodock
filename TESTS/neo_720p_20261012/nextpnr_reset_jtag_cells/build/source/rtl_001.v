// Standalone reset experiment, observed through the existing ESP-Prog JTAG.
// The reset core is shared with neo_reset_probe.v. No AE350, DDR or USB.
`default_nettype none
module neo_reset_jtag #(
    parameter BASE_WIDTH=512,
    parameter TICK_WIDTH=24
)(input wire clk,tck,tms,tdi,output reg tdo,output wire led_n);
    reg [TICK_WIDTH-1:0] ticks=0;
    reg [31:0] epoch=0;
    always @(posedge clk)begin
        ticks<=ticks+1'b1;
        if(&ticks)epoch<=epoch+1'b1;
    end
    wire resetn=|ticks[TICK_WIDTH-1:8];
    wire [3:0] reset_copies,mismatch_seen;
    wire [1:0] reference_reset;
    wire [31:0] mismatch_cycles;
    wire [63:0] signatures;
    neo_reset_probe_core #(.BASE_WIDTH(BASE_WIDTH)) u_probe(
        .clk(clk),.resetn(resetn),.reset_copies(reset_copies),
        .reference_reset(reference_reset),.mismatch_seen(mismatch_seen),
        .mismatch_cycles(mismatch_cycles),.signatures(signatures));
    assign led_n=!(|mismatch_seen);

    // Bundled-data mailbox: hold all 160 bits until a new request. The
    // acknowledgement crosses two TCK FFs before Capture-DR reads data.
    // TAP resets preserve mailbox state, so an outstanding request cannot
    // be lost or replayed merely because the host resets its TAP.
    reg request_toggle=0;
    reg [1:0] request_sync /* synthesis syn_preserve=1 */ =0;
    reg response_toggle=0;
    reg [159:0] snapshot_hold=0;
    reg [1:0] response_sync /* synthesis syn_preserve=1 */ =0;
    wire ready=response_sync[1]==request_toggle;
    always @(posedge clk)begin
        request_sync<={request_sync[0],request_toggle};
        if(request_sync[1]!=response_toggle)begin
            snapshot_hold<={16'h5251,mismatch_seen,reset_copies,6'd0,reference_reset,
                            epoch,mismatch_cycles,signatures};
            response_toggle<=request_sync[1];
        end
    end
    always @(posedge tck)response_sync<={response_sync[0],response_toggle};

    localparam TLR=0,IDLE=1,SELDR=2,CAPDR=3,SHIFTDR=4,EXIT1DR=5,
        PAUSEDR=6,EXIT2DR=7,UPDDR=8,SELIR=9,CAPIR=10,SHIFTIR=11,
        EXIT1IR=12,PAUSEIR=13,EXIT2IR=14,UPDIR=15;
    reg [3:0] state=TLR,next;
    reg [4:0] ir=1,ir_shift=1;
    reg [162:0] dr=0;
    always @*begin
        case(state)
        TLR:next=tms?TLR:IDLE;
        IDLE:next=tms?SELDR:IDLE;
        SELDR:next=tms?SELIR:CAPDR;
        CAPDR:next=tms?EXIT1DR:SHIFTDR;
        SHIFTDR:next=tms?EXIT1DR:SHIFTDR;
        EXIT1DR:next=tms?UPDDR:PAUSEDR;
        PAUSEDR:next=tms?EXIT2DR:PAUSEDR;
        EXIT2DR:next=tms?UPDDR:SHIFTDR;
        UPDDR:next=tms?SELDR:IDLE;
        SELIR:next=tms?TLR:CAPIR;
        CAPIR:next=tms?EXIT1IR:SHIFTIR;
        SHIFTIR:next=tms?EXIT1IR:SHIFTIR;
        EXIT1IR:next=tms?UPDIR:PAUSEIR;
        PAUSEIR:next=tms?EXIT2IR:PAUSEIR;
        EXIT2IR:next=tms?UPDIR:SHIFTIR;
        UPDIR:next=tms?SELDR:IDLE;
        default:next=TLR;
        endcase
    end
    always @(posedge tck)begin
        state<=next;
        if(state==TLR)ir<=1;
        if(state==CAPIR)ir_shift<=5'b00001;
        if(state==SHIFTIR)ir_shift<={tdi,ir_shift[4:1]};
        if(state==UPDIR)begin
            ir<=ir_shift;
            if(ir_shift==2 && ready)request_toggle<=!request_toggle;
        end
        if(state==CAPDR)begin
            if(ir==1)dr<={131'd0,32'h1000563d};
            else if(ir==2)dr<={request_toggle,response_sync[1],ready,snapshot_hold};
            else dr<=0;
        end
        if(state==SHIFTDR)begin
            if(ir==2)dr<={tdi,dr[162:1]};
            else if(ir==1)dr<={131'd0,tdi,dr[31:1]};
            else dr<={162'd0,tdi};
        end
    end
    always @(negedge tck)tdo<=state==SHIFTIR?ir_shift[0]:dr[0];
endmodule
`default_nettype wire
