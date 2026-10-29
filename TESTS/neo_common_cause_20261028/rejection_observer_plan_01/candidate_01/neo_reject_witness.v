// Diagnostic-only RJC1 record. No output is connected to application control.
// All inputs are taps in the existing gpu_clk domain; transport is external.
`default_nettype none
module neo_reject_witness (
    input wire clk, reset,
    input wire arm_ack_toggle, snapshot_request,
    input wire parent_reset, child_reset,
    input wire parent_capture, copy_capture, check_ce,
    input wire [255:0] parent_packet, copy_packet,
    input wire [57:0] parent_state,
    input wire [4:0] child_state,
    input wire parent_bad_d, parent_bad_q,
    input wire child_bad_d, child_bad_q, child_done,
    input wire bad_header, target_valid,
    input wire [2:0] descriptor_d, descriptor_q,
    input wire [31:0] target_base,
    input wire [15:0] target_stride, target_width, target_height,
    input wire [32:0] src_end, dst_end,
    input wire [11:0] live,
    output reg [639:0] record
);
    // Offsets within bank1. Bank0 is packet256/tag32/parent_w0.
    localparam TAG=320, BASE=352, STRIDE=384, WIDTH=400, HEIGHT=416;
    localparam SRCEND=432, DSTEND=465, PSTATE=498, CHECKSTATE=556;
    localparam BADSTATE=561, DESC_D=566, DESC_Q=569, DIFF=572;
    localparam FLAGS=580, REASON=593, CMDGEN=596, CHECKGEN=612, LIVE=628;
    localparam NONE=3'd0, HEADER=3'd1, TARGET=3'd2, CHILD_VALIDATE=3'd3;
    localparam CHILD_OTHER=3'd4, PARENT_OTHER=3'd5, INCONSISTENT=3'd6;
    localparam VALID=0, REJECTED=1, PACKET_CHILD=2, ASSOCIATED=3, Q_VALID=4;
    localparam PARENT_Q=5, HEADER_SEEN=6, TARGET_SEEN=7, RESET_SEEN=8;
    localparam CHECK_SEEN=9, ANOMALY=10, CHILD_BAD_SEEN=11, DQ_ERROR=12;

    reg arm_seen, armed, frozen, freeze_pending;
    reg [15:0] epoch, generation, copy_generation;
    reg copy_seen, check_valid, check_pending, check_q_valid;
    reg child_transition, reset_seen, anomaly;
    reg [4:0] bad_state;
    wire parent_onehot = parent_state != 0 &&
                          (parent_state & (parent_state - 1'b1)) == 0;
    wire active = parent_state != 58'd1;
    wire parent_bad_edge = parent_bad_d && !parent_bad_q && !parent_reset;
    wire child_bad_edge = child_bad_d && !child_bad_q && !child_reset;
    wire associated = copy_seen && check_valid && check_q_valid &&
                      copy_generation == generation &&
                      record[CHECKGEN+:16] == generation;
    wire use_child = parent_state[42] && associated;
    wire arm_event = arm_ack_toggle != arm_seen;
    wire [31:0] tag = {16'h4a31, epoch};
    reg [7:0] word_difference;
    integer word_index;
    always @* begin
        for (word_index=0; word_index<8; word_index=word_index+1)
            word_difference[word_index] =
                parent_packet[word_index*32+:32] != copy_packet[word_index*32+:32];
    end

    // Fields shared by CHECK, early parent rejection and a manual freeze.
    // When CHECK is absent, ends are raw observations, not validation operands.
    task context_now;
        begin
            record[BASE+:32] <= target_base;
            record[STRIDE+:16] <= target_stride;
            record[WIDTH+:16] <= target_width;
            record[HEIGHT+:16] <= target_height;
            record[SRCEND+:33] <= src_end;
            record[DSTEND+:33] <= dst_end;
        end
    endtask

    always @(posedge clk) begin
        if (reset) begin
            record <= 0;
            arm_seen <= 0; armed <= 0; frozen <= 0; freeze_pending <= 0;
            epoch <= 0; generation <= 0; copy_generation <= 0;
            copy_seen <= 0; check_valid <= 0; check_pending <= 0; check_q_valid <= 0;
            child_transition <= 0; bad_state <= 0; reset_seen <= 0; anomaly <= 0;
        end else if (arm_event) begin
            // ARM is a separate GPU-domain acknowledgement, already synchronized.
            arm_seen <= arm_ack_toggle;
            epoch <= epoch + 1'b1;
            armed <= epoch != 16'hffff;
            frozen <= 0; freeze_pending <= 0; record <= 0;
            record[256+:32] <= {16'h4a31, epoch+16'd1};
            record[TAG+:32] <= {16'h4a31, epoch+16'd1};
            record[FLAGS+ANOMALY] <= epoch == 16'hffff;
            copy_seen <= 0; check_valid <= 0; check_pending <= 0; check_q_valid <= 0;
            child_transition <= 0; bad_state <= 0;
            reset_seen <= parent_reset || child_reset;
            anomaly <= epoch == 16'hffff || active;
        end else if (armed && !frozen) begin
            if (freeze_pending) begin
                // The captured D is checked against the real FF Q one edge later.
                freeze_pending <= 0; frozen <= 1;
                record[FLAGS+VALID] <= 1;
                record[FLAGS+PARENT_Q] <= parent_bad_q;
                record[FLAGS+RESET_SEEN] <= record[FLAGS+RESET_SEEN] || parent_reset || child_reset;
                record[LIVE+11] <= 0;
                if (!parent_bad_q || parent_reset || child_reset) begin
                    record[FLAGS+ANOMALY] <= 1;
                    record[FLAGS+DQ_ERROR] <= !parent_bad_q;
                    record[REASON+:3] <= INCONSISTENT;
                end
            end else begin
                if (parent_reset || child_reset) begin
                    reset_seen <= 1;
                    copy_seen <= 0; check_valid <= 0; check_pending <= 0;
                    check_q_valid <= 0; child_transition <= 0;
                end
                if (parent_capture && !parent_reset) begin
                    generation <= generation + 1'b1;
                    copy_seen <= 0; check_valid <= 0; check_pending <= 0;
                    check_q_valid <= 0; child_transition <= 0;
                    if (generation == 16'hffff) anomaly <= 1;
                end
                if (copy_capture && !child_reset) begin
                    copy_generation <= generation; copy_seen <= 1;
                    if (parent_capture) anomaly <= 1;
                end
                if (check_pending) begin
                    record[DESC_Q+:3] <= descriptor_q;
                    check_pending <= 0; check_q_valid <= !child_reset;
                    if (child_reset || descriptor_q != record[DESC_D+:3]) begin
                        anomaly <= 1;
                        record[FLAGS+DQ_ERROR] <= 1;
                    end
                end
                if (check_ce && !child_reset) begin
                    record[255:0] <= copy_packet;
                    record[288+:32] <= parent_packet[31:0];
                    context_now();
                    record[CHECKSTATE+:5] <= child_state;
                    record[DESC_D+:3] <= descriptor_d;
                    record[DIFF+:8] <= word_difference;
                    record[CHECKGEN+:16] <= copy_generation;
                    check_valid <= copy_seen && copy_generation == generation;
                    check_pending <= 1; check_q_valid <= 0;
                    if (!copy_seen || copy_generation != generation || check_valid)
                        anomaly <= 1;
                end
                if (child_bad_edge) begin
                    child_transition <= 1; bad_state <= child_state;
                end
                if (parent_bad_edge) begin
                    freeze_pending <= 1;
                    record[256+:32] <= tag; record[TAG+:32] <= tag;
                    record[288+:32] <= parent_packet[31:0];
                    record[PSTATE+:58] <= parent_state;
                    record[BADSTATE+:5] <= bad_state;
                    record[CMDGEN+:16] <= generation;
                    record[LIVE+:12] <= {1'b1,1'b0,live[9:0]};
                    record[FLAGS+REJECTED] <= 1;
                    record[FLAGS+PACKET_CHILD] <= use_child;
                    record[FLAGS+ASSOCIATED] <= use_child;
                    record[FLAGS+Q_VALID] <= use_child;
                    record[FLAGS+HEADER_SEEN] <= bad_header;
                    record[FLAGS+TARGET_SEEN] <= target_valid;
                    record[FLAGS+RESET_SEEN] <= reset_seen || parent_reset || child_reset;
                    record[FLAGS+CHECK_SEEN] <= use_child;
                    record[FLAGS+CHILD_BAD_SEEN] <= child_transition;
                    record[FLAGS+ANOMALY] <= anomaly || !parent_onehot || check_pending;
                    if (!use_child) begin
                        record[255:0] <= parent_packet;
                        context_now();
                        record[CHECKSTATE+:5] <= 0;
                        record[DESC_D+:3] <= 0; record[DESC_Q+:3] <= 0;
                        record[DIFF+:8] <= 0; record[CHECKGEN+:16] <= 0;
                    end
                    if (anomaly || !parent_onehot || check_pending || reset_seen || child_reset)
                        record[REASON+:3] <= INCONSISTENT;
                    else if (parent_state[45] && bad_header)
                        record[REASON+:3] <= HEADER;
                    else if (parent_state[45] && parent_packet[31:24] == 8'h1d && !target_valid)
                        record[REASON+:3] <= TARGET;
                    else if (parent_state[42] && child_done && child_bad_q)
                        record[REASON+:3] <= use_child && child_transition &&
                            bad_state == 5'd17 && record[DESC_Q+:3] != 0 ?
                            CHILD_VALIDATE : CHILD_OTHER;
                    else record[REASON+:3] <= PARENT_OTHER;
                end else if (snapshot_request && active) begin
                    // The simultaneous NGDB held capture is deliberately discarded
                    // by the collector. A later snapshot sees this frozen record.
                    record <= 0;
                    record[255:0] <= parent_packet;
                    record[256+:32] <= tag; record[TAG+:32] <= tag;
                    record[288+:32] <= parent_packet[31:0];
                    context_now();
                    record[PSTATE+:58] <= parent_state;
                    record[CMDGEN+:16] <= generation;
                    record[FLAGS+VALID] <= 1;
                    record[FLAGS+HEADER_SEEN] <= bad_header;
                    record[FLAGS+TARGET_SEEN] <= target_valid;
                    record[FLAGS+RESET_SEEN] <= reset_seen || parent_reset || child_reset;
                    record[FLAGS+ANOMALY] <= anomaly || !parent_onehot;
                    record[LIVE+:12] <= {1'b0,1'b1,live[9:0]};
                    record[REASON+:3] <= NONE;
                    frozen <= 1;
                end
            end
        end
    end
endmodule
`default_nettype wire
