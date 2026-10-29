// Passive Neo diagnostic. All event inputs use the DDR UI clock.
// accepted_by_arbiter counts enqueueing, NOT native DDR command acceptance.
`default_nettype none
module neo_scan_observe(
    input wire clk,resetn,
    input wire scan_valid,scan_ready,arb_valid,arb_ready,data_valid,
    input wire [28:0] arb_addr,
    input wire [95:0] state_words,
    output wire [255:0] live
);
    reg [1:0] up=0;
    always @(posedge clk or negedge resetn)
        if(!resetn)up<=0;else up<={up[0],1'b1};
    reg [31:0] accepted_by_queue=0,accepted_by_arbiter=0,returned=0;
    reg [28:0] last_address=0;
    always @(posedge clk)begin
        if(!up[1])begin
            accepted_by_queue<=0;accepted_by_arbiter<=0;
            returned<=0;last_address<=0;
        end else begin
            if(scan_valid && scan_ready)accepted_by_queue<=accepted_by_queue+1'b1;
            if(arb_valid && arb_ready)begin
                accepted_by_arbiter<=accepted_by_arbiter+1'b1;
                last_address<=arb_addr;
            end
            if(data_valid)returned<=returned+1'b1;
        end
    end
    assign live={24'h53434e,2'b0,scan_valid,scan_ready,arb_valid,arb_ready,data_valid,up[1],
        3'b0,last_address,returned,accepted_by_arbiter,accepted_by_queue,state_words};
endmodule
`default_nettype wire
