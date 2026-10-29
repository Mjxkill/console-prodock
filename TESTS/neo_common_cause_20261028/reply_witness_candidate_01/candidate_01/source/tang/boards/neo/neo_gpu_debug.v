// Neo diagnostic only: coherent GPU snapshots independent of cdc_word.
// No output controls the GPU. One outstanding request, held data until ACK.
`default_nettype none
module neo_gpu_debug (
    input wire hclk, resetn, mem_clk,
    input wire hsel, hwrite,
    input wire [1:0] htrans,
    input wire [31:0] haddr, hwdata,
    output reg [31:0] hrdata,
    output wire hready,
    input wire host_accept,
    input wire [255:0] live,
    input wire [63:0] observe_packet_words
);
    reg [1:0] mem_up=0;
    always @(posedge mem_clk or negedge resetn)
        if(!resetn)mem_up<=0;else mem_up<={mem_up[0],1'b1};
    reg request=0, ack=0;
    reg [1:0] req_s=0, ack_s=0, ready_s=0;
    reg [31:0] host_words=0, received=0, last_word=0;
    reg [319:0] held=0, snapshot=0;
    reg busy=0, valid=0;
    // Ungated observation path, independent of the snapshot handshake.
    // These per-bit synchronizers are NOT an atomic multi-bit capture. Read
    // only with the GPU idle, require repeated equal samples, and interpret
    // them as diagnostic evidence only. They never control the GPU or ACK.
    reg [63:0] observe_words_s1=0,observe_words_s2=0;
    reg [31:0] observe_meta_s1=0,observe_meta_s2=0;
    wire [31:0] observe_meta={8'd0,live[255:248],4'd0,valid,busy,
        ready_s,mem_up,ack_s,ack,req_s,request};
    always @(posedge hclk)begin
        if(!resetn)begin
            observe_words_s1<=0;observe_words_s2<=0;
            observe_meta_s1<=0;observe_meta_s2<=0;
        end else begin
            observe_words_s1<=observe_packet_words;observe_words_s2<=observe_words_s1;
            observe_meta_s1<=observe_meta;observe_meta_s2<=observe_meta_s1;
        end
    end
    reg [31:0] sequence_id=0;
    reg bus_write=0;
    reg [7:0] bus_addr=0;
    // One wait state separates address decode from the registered response.
    // Four identical selectors keep each decode local to one response byte.
    // Only this diagnostic slave changes latency; GPU commands are unaffected.
    reg read_wait=0;
    reg [67:0] read_select /* synthesis syn_preserve=1 */ = 0;
    assign hready=!read_wait;
    always @(posedge hclk)
        if(!resetn)read_wait<=0;
        else if(read_wait)read_wait<=0;
        else read_wait<=hsel && htrans[1] && !hwrite;
    genvar sel;
    generate for(sel=0;sel<68;sel=sel+1)begin: decode
        always @(posedge hclk)
            if(!resetn)read_select[sel]<=0;
            else if(hready)read_select[sel]<=(haddr[7:0]==(sel%17)*4);
    end endgenerate
    wire [31:0] register_value [0:16];
    assign register_value[0]=32'h4e474442; // NGDB
    assign register_value[1]={29'd0,ready_s[1],valid,busy};
    assign register_value[2]=host_words;
    assign register_value[3]=sequence_id;
    assign register_value[4]=snapshot[287:256];
    assign register_value[5]=snapshot[319:288];
    assign register_value[6]=observe_words_s2[31:0]; // geometry captured header
    assign register_value[7]=observe_words_s2[63:32]; // pixel captured header
    assign register_value[16]=observe_meta_s2; // raw handshake/opcode, not a snapshot
    genvar lane;
    generate for(lane=0;lane<8;lane=lane+1)begin: snapshot_word
        assign register_value[8+lane]=snapshot[lane*32+:32];
    end endgenerate
    wire [31:0] response_data;
    genvar byte_index;
    generate for(byte_index=0;byte_index<4;byte_index=byte_index+1)begin: response
        integer k;
        reg [7:0] selected_byte;
        assign response_data[byte_index*8+:8]=selected_byte;
        always @* begin
            selected_byte=0;
            for(k=0;k<17;k=k+1)
                selected_byte=selected_byte |
                    ({8{read_select[byte_index*17+k]}} & register_value[k][byte_index*8+:8]);
        end
    end endgenerate
    always @(posedge mem_clk)begin
        if(!mem_up[1])begin
            req_s<=0;ack<=0;held<=0;received<=0;last_word<=0;
        end else begin
            req_s<={req_s[0],request};
            if(live[36])begin // gpu_accel command_we, same mem_clk edge
                received<=received+1'b1;last_word<=live[223:192];
            end
            if(req_s[1]!=ack)begin
                held<={last_word,received,live};
                ack<=req_s[1];
            end
        end
    end
    always @(posedge hclk)begin
        if(!resetn)begin
            request<=0;ack_s<=0;ready_s<=0;host_words<=0;snapshot<=0;
            busy<=0;valid<=0;sequence_id<=0;bus_write<=0;bus_addr<=0;hrdata<=0;
        end else begin
            ack_s<={ack_s[0],ack};
            ready_s<={ready_s[0],mem_up[1]};
            if(hready)begin
                bus_write<=hsel && htrans[1] && hwrite;
                bus_addr<=haddr[7:0];
            end
            if(host_accept)host_words<=host_words+1'b1;
            if(bus_write && hready && bus_addr==8'h04 && hwdata[0] && !busy && ready_s[1])begin
                request<=~request;busy<=1;
            end
            if(busy && ack_s[1]==request)begin
                snapshot<=held;busy<=0;valid<=1;sequence_id<=sequence_id+1'b1;
            end
            hrdata<=response_data;
        end
    end
endmodule
`default_nettype wire
