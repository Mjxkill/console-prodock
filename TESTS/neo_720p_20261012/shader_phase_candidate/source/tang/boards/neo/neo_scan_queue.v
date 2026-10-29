// Neo's scanout and DDR arbiter can be placed far apart. Two local request
// slots keep the arbiter READY/calibration decode off the tile reader's
// address/counter enables. Responses remain on the original ordered path.
`default_nettype none
module neo_scan_queue (
    input wire clk, resetn,
    input wire in_valid,
    input wire [28:0] in_addr,
    output wire in_ready,
    output wire out_valid,
    output wire [28:0] out_addr,
    input wire out_ready
);
    reg [1:0] up /* synthesis syn_preserve=1 */ = 0;
    always @(posedge clk or negedge resetn)
        if (!resetn) up <= 0;
        else up <= {up[0],1'b1};

    reg [1:0] count=0;
    reg write_slot=0,read_slot=0;
    reg [28:0] slot0,slot1;
    assign in_ready=up[1] && count!=2;
    assign out_valid=up[1] && count!=0;
    assign out_addr=read_slot ? slot1:slot0;
    wire push=in_valid && in_ready;
    wire pop=out_valid && out_ready;
    always @(posedge clk) begin
        if (!up[1]) begin count<=0;write_slot<=0;read_slot<=0;end
        else begin
            case ({push,pop})
                2'b10:count<=count+1'b1;
                2'b01:count<=count-1'b1;
                default:;
            endcase
            // Payload writes depend only on local input acceptance. A
            // shifting head/tail implementation put downstream READY on
            // both 29-bit data enables, recreating the long return path.
            if (push)begin
                if(write_slot)slot1<=in_addr;else slot0<=in_addr;
                write_slot<=!write_slot;
            end
            if(pop)read_slot<=!read_slot;
        end
    end
endmodule
`default_nettype wire
