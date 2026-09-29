// Compare the actual scanout read mux with its previous address-based mux.
module gpu_registers_equiv(
    input wire hclk,hresetn,hready,
    input wire [31:0] haddr,hrdata,
    input wire [31:0] value_0,
    input wire [31:0] value_1,
    input wire [31:0] value_2,
    input wire [31:0] value_3,
    input wire [31:0] value_4,
    input wire [31:0] value_5,
    input wire [31:0] value_6,
    input wire [31:0] value_7,
    input wire [31:0] value_8,
    input wire [31:0] value_9,
    input wire [31:0] value_10,
    input wire [31:0] value_11,
    input wire [31:0] value_12,
    input wire [31:0] value_13,
    input wire [31:0] value_14,
    input wire [31:0] value_15,
    input wire [31:0] value_16,
    input wire [31:0] value_17,
    input wire [31:0] value_18,
    input wire [31:0] value_19,
    input wire [31:0] value_20,
    input wire [31:0] value_21,
    input wire [31:0] value_22,
    input wire [31:0] value_23);
    reg [11:0] reference_addr;
    reg [31:0] expected;
    integer cycles=0;
    always @(posedge hclk)
        if (!hresetn) reference_addr<=0;
        else if (hready) reference_addr<=haddr[11:0];
    always @* begin
        case(reference_addr)
            12'h000: expected=value_0;
            12'h004: expected=value_1;
            12'h008: expected=value_2;
            12'h00c: expected=value_3;
            12'h010: expected=value_4;
            12'h014: expected=value_5;
            12'h018: expected=value_6;
            12'h01c: expected=value_7;
            12'h020: expected=value_8;
            12'h024: expected=value_9;
            12'h028: expected=value_10;
            12'h02c: expected=value_11;
            12'h030: expected=value_12;
            12'h034: expected=value_13;
            12'h038: expected=value_14;
            12'h03c: expected=value_15;
            12'h040: expected=value_16;
            12'h044: expected=value_17;
            12'h048: expected=value_18;
            12'h04c: expected=value_19;
            12'h050: expected=value_20;
            12'h054: expected=value_21;
            12'h058: expected=value_22;
            12'h05c: expected=value_23;
            default: expected=0;
        endcase
    end
    always @(negedge hclk) begin
        if(cycles>0 && hrdata!==expected)
            $fatal(1,"GPU read mismatch address=%h actual=%h expected=%h",reference_addr,hrdata,expected);
        cycles=cycles+1;
    end
    final $display("GPU register equivalence PASS: %0d bus cycles",cycles);
endmodule

bind gpu_scanout gpu_registers_equiv u_registers_equiv (
    .hclk(hclk),.hresetn(hresetn),.hready(hready),.haddr(haddr),.hrdata(hrdata),
    .value_0(32'h47505531),
    .value_1(shadow_base),
    .value_2({31'b0, shadow_enable}),
    .value_3({31'b0, busy}),
    .value_4(r_base),
    .value_5({31'b0, enabled_sync[1]}),
    .value_6(r_frames),
    .value_7(r_underflows),
    .value_8(r_checksum),
    .value_9(r_fetch_frames),
    .value_10(16),
    .value_11(r_max_cycles),
    .value_12({31'b0,shadow_layers}),
    .value_13({31'b0,layers_sync[1]}),
    .value_14(r_invalid_layers),
    .value_15(64),
    .value_16({31'b0,shadow_sprites}),
    .value_17({31'b0,sprites_sync[1]}),
    .value_18(r_invalid_sprites),
    .value_19(r_max_sprites),
    .value_20(r_cache_cycles),
    .value_21(r_max_sprite_pixels),
    .value_22(r_cache_loads),
    .value_23(32'h00000d07));
