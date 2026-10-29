// font_ram.v — alphabet programmable : 256 glyphes de 8 × 16 pixels = 4 096 octets en BSRAM double port. Octet
// (glyphe c, rangée r) à l'adresse c × 16 + r, bit 7 = pixel de gauche. Contenu initial : FONT_FILE (police console Terminus convertie,
// PROVENANCE.md). Écrit par le cœur (gpu_accel : FONT_ADDR / FONT_DATA, 80 MHz), lu par le blitter (op TEXT, 75 MHz). Lecture synchrone :
// `q` un cycle après `raddr`.
`default_nettype none
module font_ram #(
    parameter FONT_FILE = "rtl/video/font8x16.hex"
) (
    input  wire        wclk, rclk,
    input  wire        we,
    input  wire [11:0] waddr,
    input  wire [7:0]  wdata,
    input  wire [11:0] raddr,
    output reg  [7:0]  q
);
    reg [7:0] mem [0:4095];
    initial $readmemh(FONT_FILE, mem);
    always @(posedge wclk) if (we) mem[waddr] <= wdata;
    always @(posedge rclk) q <= mem[raddr];
endmodule
`default_nettype wire
