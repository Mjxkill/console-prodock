// Candidate Neo only: SDPB storage replacement for exactly the two command
// memories inventoried in MAPPING.json. Pointers/protocol/latency stay external.
// Contract: WIDTH32, READ_MODE0, RESET_MODE SYNC, BLK_SEL0/1=000,
// ADA/ADB[13:12]=0 (128 reachable words), GSR permanently inactive after load.
// Explicit FF primitives prevent RAM inference. RESET affects DO, never words.
`default_nettype none
module neo_command_ff128(
    output wire [31:0] DO,
    input wire [31:0] DI,
    input wire [2:0] BLKSELA,BLKSELB,
    input wire [13:0] ADA,ADB,
    input wire CLKA,CLKB,CEA,CEB,OCE,RESET
);
    wire [4095:0] words;
    wire write_enabled=CEA && (BLKSELA==3'b000);
    wire read_enabled=CEB && (BLKSELB==3'b000);
    // The low write-address bits are byte enables, not part of the word index.
    genvar slot,bit_index;
    generate for(slot=0;slot<128;slot=slot+1)begin: cell_word
        for(bit_index=0;bit_index<32;bit_index=bit_index+1)begin: cell_bit
            wire enable=write_enabled && ADA[11:5]==slot && ADA[bit_index/8];
            DFFRE ff(.Q(words[32*slot+bit_index]),.D(DI[bit_index]),
                .CLK(CLKA),.CE(enable),.RESET(1'b0));
            defparam ff.INIT=1'b0;
        end
    end endgenerate
    wire [31:0] selected=words[32*ADB[11:5]+:32];
    // Bypass is one CLKB edge; OCE only controls the unused pipeline register.
    // RESET precedes CEB, matching SDPB even when the read port is paused.
    generate for(bit_index=0;bit_index<32;bit_index=bit_index+1)begin: output_bit
        DFFRE ff(.Q(DO[bit_index]),.D(selected[bit_index]),.CLK(CLKB),
            .CE(read_enabled),.RESET(RESET));
        defparam ff.INIT=1'b0;
    end endgenerate
endmodule
`default_nettype wire
