// Extension inside the existing Neo diagnostic AHB slave. Its existing address
// phase registers and wait state remain authoritative. No additional bus master.
`default_nettype none
module neo_capture_bus(
    input wire clk, resetn, legacy_wait, write_pending, write_bit,
    input wire [7:0] write_addr, read_addr,
    input wire [31:0] legacy_data,
    output wire [31:0] hrdata,
    output reg arm_req=0, snap_req=0,
    input wire arm_ack,snap_ack,ready,heartbeat,
    input wire [63:0] held
);
    reg [1:0] up=0;
    reg [1:0] arm_sync=0,snap_sync=0,ready_sync=0,beat_sync=0;
    reg [63:0] shadow=0;
    reg [31:0] sequence_id=0,arm_count=0,heartbeat_count=0;
    reg arm_busy=0,snap_busy=0,snapshot_valid=0,rejected=0,beat_last=0;
    reg [1:0] settle=0;
    reg [7:0] read_latched=0;
    reg [31:0] response=0;
    assign hrdata=read_latched[7] ? response:legacy_data;
    always @(posedge clk or negedge resetn)
        if(!resetn)up<=0;else up<={up[0],1'b1};
    always @(posedge clk or negedge resetn)begin
        if(!resetn)begin
            arm_sync<=0;snap_sync<=0;ready_sync<=0;beat_sync<=0;beat_last<=0;
            arm_req<=0;snap_req<=0;arm_busy<=0;snap_busy<=0;snapshot_valid<=0;
            rejected<=0;settle<=0;shadow<=0;sequence_id<=0;arm_count<=0;
            heartbeat_count<=0;read_latched<=0;response<=0;
        end else if(!up[1])begin
            arm_sync<=0;snap_sync<=0;ready_sync<=0;beat_sync<=0;beat_last<=0;
            arm_req<=0;snap_req<=0;arm_busy<=0;snap_busy<=0;snapshot_valid<=0;
            rejected<=0;settle<=0;shadow<=0;sequence_id<=0;arm_count<=0;
            heartbeat_count<=0;read_latched<=0;response<=0;
        end else begin
            arm_sync<={arm_sync[0],arm_ack};snap_sync<={snap_sync[0],snap_ack};
            ready_sync<={ready_sync[0],ready};beat_sync<={beat_sync[0],heartbeat};
            if(beat_sync[1]!=beat_last)begin heartbeat_count<=heartbeat_count+1'b1;beat_last<=beat_sync[1];end
            if(arm_busy && arm_sync[1]==arm_req)arm_busy<=0;
            if(snap_busy && snap_sync[1]==snap_req)begin
                // Two further AHB cycles after synchronized ACK before copying
                // held. Physical held->shadow delay must be audited after PNR.
                if(settle==2)begin
                    shadow<=held;sequence_id<=sequence_id+1'b1;snapshot_valid<=1;snap_busy<=0;settle<=0;
                end else settle<=settle+1'b1;
            end
            if(write_pending && !legacy_wait && write_bit &&
               (write_addr==8'h84 || write_addr==8'h88))begin
                if(!ready_sync[1] || arm_busy || snap_busy)rejected<=1;
                else if(write_addr==8'h84)begin
                    arm_req<=~arm_req;arm_busy<=1;arm_count<=arm_count+1'b1;snapshot_valid<=0;rejected<=0;
                end else begin snap_req<=~snap_req;snap_busy<=1;settle<=0;snapshot_valid<=0;end
            end
            if(!legacy_wait)read_latched<=read_addr;
            case(read_latched)
                8'h80:response<=32'h4e435031; // NCP1
                8'h84:response<={25'd0,rejected,arm_req,snap_req,snapshot_valid,ready_sync[1],snap_busy,arm_busy};
                8'h88:response<=arm_count;
                8'h8c:response<=sequence_id;
                8'h90:response<=shadow[31:0];
                8'h94:response<=shadow[63:32];
                8'h98:response<=heartbeat_count;
                default:response<=0;
            endcase
        end
    end
endmodule
`default_nettype wire
