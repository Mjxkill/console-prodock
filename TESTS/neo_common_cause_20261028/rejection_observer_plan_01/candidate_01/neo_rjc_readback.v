// Combinational overlay of the existing registered AHB read response.
// Existing selectors/handshake/latency are reused, including byte-local copies.
`default_nettype none
module neo_rjc_readback(
    input wire [31:0] legacy,
    input wire [67:0] select,
    input wire [319:0] snapshot,
    output wire [31:0] merged
);
    genvar lane;
    generate for(lane=0;lane<4;lane=lane+1)begin: bytes
        wire hit=select[lane*17+4] | select[lane*17+5] |
            (|select[lane*17+8+:8]);
        reg [7:0] value;
        integer word_index;
        always @* begin
            value=({8{select[lane*17+4]}} & snapshot[256+lane*8+:8]) |
                  ({8{select[lane*17+5]}} & snapshot[288+lane*8+:8]);
            for(word_index=0;word_index<8;word_index=word_index+1)
                value=value | ({8{select[lane*17+8+word_index]}} &
                               snapshot[word_index*32+lane*8+:8]);
        end
        assign merged[lane*8+:8]=hit ? value : legacy[lane*8+:8];
    end endgenerate
endmodule
`default_nettype wire
