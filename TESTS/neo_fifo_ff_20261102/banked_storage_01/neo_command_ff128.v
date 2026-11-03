// Neo experiment only. Same SDPB128x32 binding as mapping_01/CONTRACT.md.
// Storage/DO FF, clocks, enables, reset and one-edge read latency are unchanged.
// Read selection: shared one-hot decoders, eight local banks of sixteen words.
// Explicit LUT primitives preserve the intended AND/OR network through synthesis.
// Contract: binary stable address/control at the clock; prohibited same-address
// simultaneous read/write and runtime global GSR are NOT newly qualified here.
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
    genvar slot,bit_index,bank,pair_index;
    generate for(slot=0;slot<128;slot=slot+1)begin: cell_word
        for(bit_index=0;bit_index<32;bit_index=bit_index+1)begin: cell_bit
            wire enable=write_enabled && ADA[11:5]==slot && ADA[bit_index/8];
            DFFRE ff(.Q(words[32*slot+bit_index]),.D(DI[bit_index]),
                .CLK(CLKA),.CE(enable),.RESET(1'b0));
            defparam ff.INIT=1'b0;
        end
    end endgenerate
    wire [15:0] row_select;
    wire [7:0] bank_select;
    generate for(slot=0;slot<16;slot=slot+1)begin: decode_row
        LUT4 eq(.F(row_select[slot]),.I0(ADB[5]),.I1(ADB[6]),.I2(ADB[7]),.I3(ADB[8]));
        defparam eq.INIT=16'h0001<<slot;
    end
    for(bank=0;bank<8;bank=bank+1)begin: decode_bank
        LUT3 eq(.F(bank_select[bank]),.I0(ADB[9]),.I1(ADB[10]),.I2(ADB[11]));
        defparam eq.INIT=8'h01<<bank;
    end endgenerate
    wire [255:0] bank_value;
    generate for(bank=0;bank<8;bank=bank+1)begin: local_bank
        for(bit_index=0;bit_index<32;bit_index=bit_index+1)begin: column
            wire [7:0] pair_value;
            wire low_value,high_value;
            for(pair_index=0;pair_index<8;pair_index=pair_index+1)begin: pair_gate
                // F=(I0&I1)|(I2&I3). A decoded row selects only one stored word.
                LUT4 gate_pair(.F(pair_value[pair_index]),
                    .I0(words[32*(16*bank+2*pair_index)+bit_index]),.I1(row_select[2*pair_index]),
                    .I2(words[32*(16*bank+2*pair_index+1)+bit_index]),.I3(row_select[2*pair_index+1]));
                defparam gate_pair.INIT=16'hF888;
            end
            LUT4 lo(.F(low_value),.I0(pair_value[0]),.I1(pair_value[1]),.I2(pair_value[2]),.I3(pair_value[3]));
            defparam lo.INIT=16'hFFFE;
            LUT4 hi(.F(high_value),.I0(pair_value[4]),.I1(pair_value[5]),.I2(pair_value[6]),.I3(pair_value[7]));
            defparam hi.INIT=16'hFFFE;
            LUT2 combine(.F(bank_value[32*bank+bit_index]),.I0(low_value),.I1(high_value));
            defparam combine.INIT=4'hE;
        end
    end endgenerate
    wire [31:0] read_selected;
    generate for(bit_index=0;bit_index<32;bit_index=bit_index+1)begin: select_output
        wire [3:0] pair_value;
        for(pair_index=0;pair_index<4;pair_index=pair_index+1)begin: bank_pair
            LUT4 gate_pair(.F(pair_value[pair_index]),
                .I0(bank_value[64*pair_index+bit_index]),.I1(bank_select[2*pair_index]),
                .I2(bank_value[64*pair_index+32+bit_index]),.I3(bank_select[2*pair_index+1]));
            defparam gate_pair.INIT=16'hF888;
        end
        LUT4 reduce_banks(.F(read_selected[bit_index]),.I0(pair_value[0]),.I1(pair_value[1]),.I2(pair_value[2]),.I3(pair_value[3]));
        defparam reduce_banks.INIT=16'hFFFE;
    end endgenerate
    wire [31:0] selected=read_selected;
    // RESET precedes CEB, only DO is cleared; OCE controls no stage in READ_MODE0.
    generate for(bit_index=0;bit_index<32;bit_index=bit_index+1)begin: output_bit
        DFFRE ff(.Q(DO[bit_index]),.D(selected[bit_index]),.CLK(CLKB),
            .CE(read_enabled),.RESET(RESET));
        defparam ff.INIT=1'b0;
    end endgenerate
endmodule
`default_nettype wire
