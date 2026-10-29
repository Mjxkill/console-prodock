// ahb_exts_bridge.v — pont registré entre l'interface AHB étendue (EXTS) du SoC AE350 et ses deux esclaves de fabric : ext_regs (0)
// et la carte vidéo ahb_video (1, haddr[24] = 1). Pourquoi : l'entrée EXTS_HREADYIN du bloc dur consomme ≈ 9 ns de budget à elle seule
// (builds V5_p11 : un registre → HREADYIN à −0,03 ns ; p12-p14 : un mux devant HREADYIN à −5 / −8 ns). Ici le SoC ne voit que des
// registres : m_hready et m_hrdata sont des bascules, sans logique devant. Un accès prend 4 cycles (5 pour une lecture d'ext_regs) :
// I (adresse acceptée) → DATA (hwdata capturé, adresse relayée à l'esclave) → ADDR (esclave en phase de données) → WAIT (sa réponse)
// → I. Un seul accès en vol (le SoC est retenu). Les esclaves gardent leur protocole AHB-lite d'origine, inchangés.
`default_nettype none
module ahb_exts_bridge (
    input  wire        hclk,
    input  wire        hresetn,
    // côté SoC (EXTS)
    input  wire        m_hsel,
    input  wire [31:0] m_haddr,
    input  wire [1:0]  m_htrans,
    input  wire        m_hwrite,
    input  wire [31:0] m_hwdata,
    output reg  [31:0] m_hrdata,
    output reg         m_hready,
    // côté esclaves (0 = ext_regs, 1 = vidéo) : adresse/données partagées, sélection séparée
    output reg  [1:0]  s_hsel,
    output reg  [1:0]  s_htrans,
    output reg         s_hwrite,
    output reg  [31:0] s_haddr,
    output reg  [31:0] s_hwdata,
    input  wire [31:0] s0_hrdata,
    input  wire        s0_hready,
    input  wire [31:0] s1_hrdata,
    input  wire        s1_hready
);
    localparam I = 0, DATA = 1, ADDR = 2, WAIT = 3;
    reg [3:0] st; reg wr, tgt; reg [31:0] addr;
    wire        t_hready = tgt ? s1_hready : s0_hready;
    wire [31:0] t_hrdata = tgt ? s1_hrdata : s0_hrdata;
    always @(posedge hclk) begin
        if (!hresetn) begin st <= 4'b0001; wr <= 1'b0; tgt <= 1'b0; addr <= 32'd0; s_hsel <= 2'b00; s_htrans <= 2'b00; s_hwrite <= 1'b0; s_haddr <= 32'd0; s_hwdata <= 32'd0; m_hrdata <= 32'd0; m_hready <= 1'b1; end
        else begin
            s_hsel <= 2'b00; s_htrans <= 2'b00;
            // All reachable IDLE cycles have HREADY=1. Assign its complete
            // next value every cycle: avoid a second, long slave-ready
            // decode through the clock enable of the hard-core return FF.
            m_hready <= (st[I] && !(m_hsel && m_htrans[1])) || (st[WAIT] && t_hready);
            // One-hot transitions keep the hard macro's HREADY -> HSEL
            // round trip off a binary next-state decoder.
            st[I] <= (st[I] && !(m_hsel && m_htrans[1])) || (st[WAIT] && t_hready);
            st[DATA] <= st[I] && m_hsel && m_htrans[1];
            st[ADDR] <= st[DATA];
            st[WAIT] <= st[ADDR] || (st[WAIT] && !t_hready);
            case (1'b1)
                st[I]: begin
                    // Sample private payload while idle. Only acceptance
                    // advances to DATA; unselected samples are never issued.
                    // Keep the hard-core HREADYIN -> HSEL path off the
                    // 34 payload register enables without adding latency.
                    wr <= m_hwrite; addr <= m_haddr; tgt <= m_haddr[24];
                    // HREADY is always high in reachable IDLE, including
                    // immediately after reset or completion of WAIT.
                end
                st[DATA]: begin s_hwdata <= m_hwdata; s_hsel <= tgt ? 2'b10 : 2'b01; s_htrans <= 2'b10; s_hwrite <= wr; s_haddr <= addr; end
                // The SoC only consumes HRDATA when registered HREADY rises.
                // Sampling during stalls removes ready from 32 data enables.
                st[WAIT]: m_hrdata <= t_hrdata;
                default: ;
            endcase
        end
    end
endmodule
`default_nettype wire
