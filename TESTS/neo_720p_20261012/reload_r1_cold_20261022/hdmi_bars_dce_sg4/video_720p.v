// video_720p.v — générateur de timing 1280×720 @ 60 Hz (CEA-861 : 1650 × 750, pixel 74,25 MHz) — ARCHI_V4 § 9.4.
// Ligne : 1280 actifs, porche avant 110, hsync 40, porche arrière 220 ; trame : 720 actives, porche avant 5, vsync 5, porche
// arrière 20 ; polarités positives. Sorties registrées : de, hs, vs, x (0..1649), y (0..749), et `frame` (impulsion au début).
`default_nettype none
module video_720p (
    input  wire        pclk,
    input  wire        rst,
    output reg         de,
    output reg         hs,
    output reg         vs,
    output reg  [10:0] x,
    output reg  [9:0]  y,
    output reg         frame
);
    localparam H_ACT = 1280, H_FP = 110, H_SYNC = 40, H_TOT = 1650;
    localparam V_ACT = 720,  V_FP = 5,   V_SYNC = 5,  V_TOT = 750;
    reg [10:0] hc;
    reg [9:0]  vc;
    always @(posedge pclk) begin
        if (rst) begin hc <= 0; vc <= 0; de <= 0; hs <= 0; vs <= 0; x <= 0; y <= 0; frame <= 0; end
        else begin
            if (hc == H_TOT - 1) begin
                hc <= 0;
                vc <= (vc == V_TOT - 1) ? 10'd0 : vc + 10'd1;
            end else hc <= hc + 11'd1;
            x  <= hc; y <= vc;
            de <= (hc < H_ACT) && (vc < V_ACT);
            hs <= (hc >= H_ACT + H_FP) && (hc < H_ACT + H_FP + H_SYNC);
            vs <= (vc >= V_ACT + V_FP) && (vc < V_ACT + V_FP + V_SYNC);
            frame <= (hc == 0) && (vc == 0);
        end
    end
endmodule
`default_nettype wire
