// Neo diagnostic candidate only. Never drives the application datapath.
// Same NCP bus protocol and two-cycle COPY capture as R19. Four sticky event
// bits distinguish producer issue/valid, slot capture and acknowledgement.
`default_nettype none
module neo_capture_local(
    input wire clk, resetn,
    input wire [23:0] sample,
    input wire [3:0] mem_events,
    input wire arm_req, snap_req,
    output reg arm_ack=0, snap_ack=0,
    output wire ready, heartbeat,
    output reg [63:0] held=0
);
    reg [1:0] up=0;
    reg [1:0] arm_sync=0,snap_sync=0;
    reg [8:0] beat=0;
    reg armed=0,pending=0,complete=0,seen_reset=0,seen_ce=0;
    reg [1:0] valid=0;
    reg [23:0] at_event=0,after_event=0;
    reg [3:0] mem_seen=0;
    // Format D*: bits59:56 are sticky memory events. Include events on the
    // snapshot edge itself. Repeated snapshots accumulate until the next ARM.
    wire [63:0] report={4'hd,(mem_seen|mem_events),1'b0,arm_ack,seen_ce,seen_reset,
                       armed,complete,valid,after_event,at_event};
    assign ready=up[1];
    assign heartbeat=beat[8];
    always @(posedge clk or negedge resetn)
        if(!resetn)up<=0;else up<={up[0],1'b1};
    always @(posedge clk or negedge resetn)begin
        if(!resetn)begin
            arm_sync<=0;snap_sync<=0;arm_ack<=0;snap_ack<=0;held<=0;beat<=0;
            armed<=0;pending<=0;complete<=0;seen_reset<=0;seen_ce<=0;
            valid<=0;at_event<=0;after_event<=0;mem_seen<=0;
        end else if(!up[1])begin
            arm_sync<=0;snap_sync<=0;arm_ack<=0;snap_ack<=0;held<=0;beat<=0;
            armed<=0;pending<=0;complete<=0;seen_reset<=0;seen_ce<=0;
            valid<=0;at_event<=0;after_event<=0;mem_seen<=0;
        end else begin
            arm_sync<={arm_sync[0],arm_req};snap_sync<={snap_sync[0],snap_req};
            beat<=beat+1'b1;
            if(arm_sync[1]!=arm_ack)begin
                // ARM has priority over simultaneous events and SNAP. The
                // host waits for arm_ack before submitting any GPU command.
                arm_ack<=arm_sync[1];armed<=1;pending<=0;complete<=0;
                seen_reset<=0;seen_ce<=0;valid<=0;at_event<=0;after_event<=0;
                mem_seen<=0;
            end else begin
                mem_seen<=mem_seen|mem_events;
                if(armed)begin
                    seen_reset<=seen_reset|sample[17];seen_ce<=seen_ce|sample[16];
                    if(pending)begin
                        after_event<=sample;valid[1]<=1;pending<=0;armed<=0;complete<=1;
                    end else if(sample[18])begin
                        at_event<=sample;valid[0]<=1;pending<=1;
                    end
                end
                // Data stays stable while the acknowledgement crosses HCLK.
                if(snap_sync[1]!=snap_ack)begin held<=report;snap_ack<=snap_sync[1];end
            end
        end
    end
endmodule
`default_nettype wire
