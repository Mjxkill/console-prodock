// G2 adaptation of ../logic_analyser_wifi/tang/rtl/video/blitter.v.
// 800x480, 16 page slots of 1 MiB starting at DDR byte address 0x00800000.
// S/W/C use halfword addresses and active-high byte enables; gpu_blit_dma
// packs these into aligned native 256-bit DDR commands. This is not SDRAM.
// Source clipping, memmove row order and wide-coordinate arithmetic added.
// Command format/opcodes and integer rasterization follow the reference below.
// Commandes de 8 mots de 32 bits poussées une à une (`cmd_we`) dans une FIFO de 16 commandes, exécutées dans l'ordre.
// Pages 800 × 480 × 8 bits (octet bas = pixel de gauche), base = PAGE_BASE_WORDS + page × 0x80000 demi-mots.
// Tout est découpé aux bords de la page (rien n'est écrit hors page).
//   mot 0 : {op[31:24], page cible[23:20], page source[19:16], couleur[15:8], couleur 2[7:0]}
//   mot 1 : {x0[31:16], y0[15:0]} (signés)   mot 2 : {x1 / largeur / rayon[31:16], y1 / hauteur[15:0]}   mot 3 : {xs[31:16], ys[15:0]} (source)
//   op 1 FILL_RECT (x0, y0, largeur, hauteur, couleur) ; 2 GRAD_H, 3 GRAD_V, 4 GRAD_D (45°) : indices couleur → couleur 2 sur le
//   rectangle ; 5 LINE (x0, y0) → (x1, y1) ; 6 CIRCLE (x0, y0, rayon) ; 7 CIRCLE_FILL ; 8 COPY (source xs, ys de la page source →
//   x0, y0, largeur, hauteur de la page cible, décalage d'un pixel géré par octets) ; 9 TEXT (étape 4) : mot 2 = {nombre de
//   caractères ≤ 16, échelle 1 ou 2}, mots 4-7 = 16 caractères (octet 0 = le premier), couleur = avant-plan, couleur 2 = fond
//   (0 = transparent : les pixels de fond ne sont pas écrits), glyphes 8 × 16 lus dans font_ram. Mots 4 à 7 réservés (0) sinon.
// Mécanique : rectangles, dégradés, disques et copies passent par une mémoire de ligne d'octets (2 banques pair/impair, alignée sur la
// phase du mot cible) remplie à 1 pixel/cycle (2 par cycle en copie) puis écrite par le port W (rafales ≤ 512 mots, masques d'octets
// aux extrémités) ; lignes et cercles écrivent pixel par pixel par le port C (masque d'octet). Dégradés sans diviseur par pixel :
// t = i × (65536 / n) par accumulation (65536 / n calculé une fois par commande, diviseur séquentiel), indice = c0 ± (|c1 − c0| × t) >> 16.
// Jamais silencieux : commande refusée (FIFO pleine) et op inconnu comptés ; `busy`, `cmd_done` (compteur) pour le logiciel.
`default_nettype none
module blitter #(
    parameter WIDTH = 800, HEIGHT = 480,
    parameter [23:0] PAGE_BASE_WORDS = 24'h400000
) (
    input  wire        clk,
    input  wire        rst,
    // commandes
    input  wire        cmd_we,
    input  wire [31:0] cmd_data,
    output wire        cmd_full,
    output reg  [15:0] err_cmd_lost,
    output reg  [15:0] err_cmd_bad,
    output reg  [15:0] cmd_done,
    output wire        busy,
    // Ordered extension: native RGB565/depth engine owns DDR until ext_done.
    output reg         ext_start, ext_active,
    output wire [255:0] ext_command,
    input wire         ext_done,
    // port S (lecture : COPY)
    output reg         s_req,
    output reg  [23:0] s_addr,
    output reg  [9:0]  s_len,
    input  wire        s_valid,
    input  wire [15:0] s_data,
    input  wire        s_done,
    // port W (écriture en rafale)
    output reg         w_req,
    output reg  [23:0] w_addr,
    output reg  [9:0]  w_len,
    output wire [15:0] w_data,
    output wire [1:0]  w_mask,
    input  wire        w_ready,
    input  wire        w_done,
    // Constant span: direct native 32-byte writes, bypass the byte line RAM.
    output reg         f_req,
    output reg [24:0]   f_addr,
    output reg [10:0]   f_len,
    output reg [7:0]    f_color,
    input wire         f_done,
    // port C (pixel isolé)
    output reg         c_req,
    output reg  [23:0] c_addr,
    output reg  [15:0] c_wdata,
    output reg  [1:0]  c_wmask,
    input  wire        c_ack,
    // alphabet (font_ram, lecture synchrone : q un cycle après raddr)
    output wire [11:0] font_addr,
    input  wire [7:0]  font_q,
    output wire [95:0] debug_state
);
    localparam signed [15:0] X_MAX = WIDTH - 1, Y_MAX = HEIGHT - 1;
    // ------------------------------------------------------------------ FIFO de commandes : 16 × 8 mots -----------------------------
    reg  [31:0] cmem [0:127];
    reg  [7:0]  wp, rp;                          // pointeurs en mots (bit 7 = tour)
    wire [7:0]  fill = wp - rp;
    assign cmd_full = (fill > 8'd120);           // plus de place pour une commande complète
    wire cmd_avail = (fill >= 8'd8);
    always @(posedge clk) begin
        if (rst) begin wp <= 8'd0; err_cmd_lost <= 16'd0; end
        else if (cmd_we) begin
            if (fill == 8'd128) err_cmd_lost <= err_cmd_lost + 16'd1;
            else begin cmem[wp[6:0]] <= cmd_data; wp <= wp + 8'd1; end
        end
    end
    // ------------------------------------------------------------------ mémoire de ligne d'octets : 2 banques (pair / impair) ------
    reg [7:0] bank0 [0:WIDTH/2-1]; reg [7:0] bank1 [0:WIDTH/2-1];
    reg       bm0 [0:WIDTH/2-1]; reg bm1 [0:WIDTH/2-1];      // masque d'écriture par octet (0 = pixel transparent, non écrit : texte sans fond)
    reg        b0_we, b1_we; reg [9:0] b0_a, b1_a; reg [7:0] b0_d, b1_d; reg b0_m, b1_m;
    always @(posedge clk) begin if (b0_we) begin bank0[b0_a] <= b0_d; bm0[b0_a] <= b0_m; end if (b1_we) begin bank1[b1_a] <= b1_d; bm1[b1_a] <= b1_m; end end
    reg  [9:0] rj;                               // mot présenté au port W
    // Delay the row rewind through a register: geometry/last-pixel decoding
    // must not feed the inferred BSRAM read address. M_ROW_SEG still precedes
    // the DMA's first W_PACK cycle, so this consumes no transfer cycle.
    reg row_rewind;
    always @(posedge clk) begin
        if (rst || row_rewind) rj <= 10'd0;
        else if (w_ready) rj <= rj + 10'd1;
    end
    assign w_data = {bank1[rj], bank0[rj]};
    // ------------------------------------------------------------------ registres de commande et géométrie ---------------------------
    reg  [7:0]  op, c0, c1; reg [3:0] dpage, spage;
    reg signed [15:0] x0, y0, x1, y1, xs, ys;
    reg signed [15:0] cx0, cy0, cx1, cy1;        // rectangle découpé (inclusif)
    // M_CLIP follows the final bounds update and precedes RECT_INIT/TXT_START.
    // Resolve emptiness there, before it gates the shared setup/state logic.
    reg rectangle_empty;
    always @(posedge clk) rectangle_empty <= cy0 > cy1 || cx0 > cx1;
    reg  [10:0] rw, rx; reg [9:0] ry;            // ligne en cours : largeur, colonne de départ, ligne
    reg  [9:0]  rows_left;
    reg  [7:0]  dabs; reg dneg;
    reg  [16:0] recip;                           // 65536 / n du dégradé
    reg  [17:0] t_start, t_acc, t_step, t_row;   // position dans le dégradé (16 bits de fraction, ≤ 65536) : départ de ligne, courant, pas par pixel, pas par ligne
    reg  [16:0] dq; reg [27:0] drem; reg [4:0] dcnt; reg [16:0] dn;   // diviseur séquentiel 65536 / dn (restauration, 17 itérations)
    wire [23:0] dbase = PAGE_BASE_WORDS + {1'b0, dpage, 19'd0};
    wire [23:0] sbase = PAGE_BASE_WORDS + {1'b0, spage, 19'd0};
    function [23:0] row_addr; input [23:0] base; input [9:0] y; input [10:0] x;
        row_addr = base + y * (WIDTH / 2) + {14'd0, x[10:1]};
    endfunction
    // ------------------------------------------------------------------ machine principale --------------------------------------------
    // One bit per state keeps DDR handshakes out of a deep binary decode.
    localparam [63:0] M_IDLE = (64'd1 << 0), M_F0 = (64'd1 << 1), M_F1 = (64'd1 << 2), M_F2 = (64'd1 << 3), M_F3 = (64'd1 << 4), M_SETUP = (64'd1 << 5), M_DIV = (64'd1 << 6), M_RECT_INIT = (64'd1 << 7),
                     M_ROW_START = (64'd1 << 8), M_ROW_GEN = (64'd1 << 9), M_ROW_SEG = (64'd1 << 10), M_ROW_WAIT = (64'd1 << 11), M_ROW_ADV = (64'd1 << 12),
                     M_LINE = (64'd1 << 13), M_LINE_STEP = (64'd1 << 14), M_PIX = (64'd1 << 15), M_PIX_WAIT = (64'd1 << 16),
                     M_CIRC = (64'd1 << 17), M_CIRC_PTS = (64'd1 << 18), M_CFILL = (64'd1 << 19), M_CFILL_NEXT = (64'd1 << 20), M_CIRC_STEP = (64'd1 << 21),
                     M_COPY_RD = (64'd1 << 22), M_COPY_SEG = (64'd1 << 23), M_COPY_WAIT = (64'd1 << 24), M_DONE = (64'd1 << 25), M_CFILL_CALC = (64'd1 << 26), M_CFILL_GO = (64'd1 << 27),
                     M_F4 = (64'd1 << 28), M_F5 = (64'd1 << 29), M_F6 = (64'd1 << 30), M_F7 = (64'd1 << 31), M_TXT_INIT = (64'd1 << 32), M_TXT_START = (64'd1 << 33), M_TXT_ROW = (64'd1 << 34), M_TXT_FONT = (64'd1 << 35), M_TXT_BITS = (64'd1 << 36), M_TXT_NEXT = (64'd1 << 37),
                     M_CLIP = (64'd1 << 38), M_LINE_INIT = (64'd1 << 39), M_LINE_X = (64'd1 << 40), M_LINE_Y = (64'd1 << 41), M_COPY_COUNT = (64'd1 << 42), M_COPY_CLIP = (64'd1 << 43),
                     M_TRI_START = (64'd1 << 44), M_TRI_WAIT = (64'd1 << 45),
                     M_Z_INIT = (64'd1 << 46), M_Z_ROW = (64'd1 << 47), M_Z_ADDR = (64'd1 << 48), M_Z_READ = (64'd1 << 49),
                     M_Z_SAMPLE = (64'd1 << 50), M_Z_PIXEL = (64'd1 << 51), M_Z_ADV = (64'd1 << 52),
                     M_FILL_START = (64'd1 << 53), M_FILL_WAIT = (64'd1 << 54),
                     M_A_INIT=(64'd1<<55), M_A_ADDR=(64'd1<<56), M_A_READ=(64'd1<<57),
                     M_A_PAD=(64'd1<<58), M_A_BEGIN=(64'd1<<59), M_A_ROW=(64'd1<<60),
                     M_A_SAMPLE=(64'd1<<61), M_A_PIXEL=(64'd1<<62), M_A_ADV=(64'd1<<63);
    reg  [63:0] st, ret;                         // état courant, état de retour des sous-programmes (ligne / pixel)
    // Decode the opcode fetched in F0 while the seven other words are fetched,
    // before SETUP, rather than through every SETUP register CE.
    reg rectangle_opcode,line_opcode,circle_opcode,triangle_opcode,
        affine_setup_opcode,extended_opcode;
    always @(posedge clk)begin
        rectangle_opcode<=0;line_opcode<=0;circle_opcode<=0;triangle_opcode<=0;
        affine_setup_opcode<=0;extended_opcode<=0;
        if(!rst)case(op)
            8'd1,8'd2,8'd3,8'd4,8'd8,8'd9,8'd11,8'd13:rectangle_opcode<=1;
            8'd5:line_opcode<=1;
            8'd6,8'd7:circle_opcode<=1;
            8'd10:triangle_opcode<=1;
            8'd12:affine_setup_opcode<=1;
            8'd14,8'd15,8'd16,8'd17,8'd18,8'd19,8'd20,8'd21,
            8'd22,8'd23,8'd24,8'd25,8'd26,8'd27,8'd28,8'd29,8'd30,8'd31,8'd32,8'd33,8'd34:extended_opcode<=1;
            default:begin end
        endcase
    end
    assign busy = (!st[$clog2(M_IDLE)]) || cmd_avail;
    reg signed [16:0] ldx, ldy;
    // Signed 16-bit endpoints can produce deltas of 65535. The error can
    // exceed either delta after a step, so it needs an additional bit.
    reg signed [17:0] lerr; reg signed [15:0] lx, ly, lsx, lsy;
    reg signed [16:0] line_negative_dy;
    reg line_step_x, line_step_y;
    reg signed [18:0] ccx, ccy, cxv, cyv, cerr; reg [2:0] cpt;              // cercle (point médian)
    reg signed [18:0] px, py;                                               // pixel isolé
    reg signed [18:0] sp_y, sp_xa, sp_xb; reg sp_vis;                       // segment de disque : bornes (M_CFILL_CALC), découpe (M_CFILL), décision (M_CFILL_GO)
    wire signed [18:0] sp_left_clipped=sp_xa<0 ? 19'sd0:sp_xa;
    wire signed [18:0] sp_right_clipped=sp_xb>X_MAX ? X_MAX:sp_xb;
    reg [10:0] sp_width;
    // Le cycle de découpe prépare aussi la largeur. CFILL_GO ne chaîne
    // plus soustraction, incrément et sélection devant rw (r622 : -1,39 ns).
    // Les bornes et la décision de visibilité gardent leur cycle d'origine.
    always @(posedge clk)
        if(st[$clog2(M_CFILL)])sp_width<=sp_right_clipped[10:0]-sp_left_clipped[10:0]+11'd1;
    // texte : 16 caractères, glyphe 8 × 16 (font_ram), échelle 1 ou 2
    reg  [127:0] txt; reg [4:0] tn, tci; reg tscale, tsub, tdup, text_last_char; reg [3:0] trow; reg [2:0] tbit; reg [8:0] tpix;
    wire [7:0]  tchar = txt[tci * 8 +: 8];
    assign font_addr = {tchar, trow};
    wire signed [15:0] ty = y0 + $signed({11'd0, trow, tsub} >> (tscale ? 0 : 1));   // ligne d'écran de la rangée de glyphe courante
    reg  [10:0] wleft; reg [23:0] waddr; reg [10:0] gi; reg [1:0] m_first, m_last; reg [9:0] wj_end;   // écriture d'une ligne ; gi : 11 bits (sur 10 bits la ligne s'arrêtait à rw mod 1024 = 256 px pour 1280, build p31)
    // rw settles before ROW_START/Z_INIT/A_INIT. Store its final index so
    // last-pixel detection is an equality, without an arithmetic carry chain.
    reg [10:0] row_last_index;
    always @(posedge clk) row_last_index <= rw - 11'd1;
    wire [9:0]  seg_max = 10'd512 - {1'b0, waddr[8:0]};
    // Test the end position directly instead of subtracting the block offset
    // and then comparing that subtraction against the remaining word count.
    // wleft[10] means at least 1024 words, necessarily beyond this 512-word block.
    wire [10:0] seg_end = {2'b0,waddr[8:0]} + {1'b0,wleft[9:0]};
    wire seg_crosses = wleft[10] || seg_end[10] || (seg_end[9] && |seg_end[8:0]);
    wire [9:0]  seg_len = seg_crosses ? seg_max : wleft[9:0];
    assign w_mask = ((rj == 10'd0) ? m_first : 2'b11) & ((rj == wj_end) ? m_last : 2'b11) & {bm1[rj], bm0[rj]};
    wire [10:0] row_last = rx + rw - 11'd1;                                    // dernier pixel de la ligne
    wire [10:0] row_words = {1'b0, row_last[10:1]} - {1'b0, rx[10:1]} + 11'd1;   // mots couverts
    reg  [9:0]  cn; reg [10:0] copy_left; reg signed [15:0] sxx;             // copie : mot source n, mots restants, colonne source découpée
    // Fin de la copie dans le bloc de 512 mots. Calculer la longueur
    // restante directement évite soustraction -> comparaison -> mux ->
    // soustraction sur le chemin s_addr -> copy_left (c3 : 13 niveaux).
    wire [11:0] copy_segment_end={1'b0,copy_left}+{3'd0,s_addr[8:0]};
    wire copy_segment_crosses=|copy_segment_end[11:9];
    wire [11:0] copy_segment_remaining=copy_segment_end-12'd512;
    reg [9:0] source_row;
    // valeur de pixel du générateur : constante (FILL, disque) ou dégradé
    wire [25:0] prod = {18'd0, dabs} * {8'd0, t_acc};
    wire [7:0]  q = (prod[25:16] > 10'd255) ? 8'd255 : prod[23:16];
    wire [7:0]  gen_pix = (op == 8'd1 || op == 8'd7 || op == 8'd10) ? c0 : (dneg ? c0 - q : c0 + q);
    wire [10:0] gpos = gi + {10'd0, rx[0]};                           // position du pixel gi dans la mémoire de ligne
    reg [15:0] offx, offy;
    reg copy_reverse;
    reg [10:0] copy_limit0,copy_limit1;
    // Source coordinates are loaded in M_F3, several cycles before COPY_CLIP.
    // Prepare these bounds in that existing gap instead of cascading two
    // arithmetic operations and comparisons into the clipping register enables.
    reg signed [31:0] source_left,source_top,source_right,source_bottom;
    always @(posedge clk) begin
        source_left <= $signed(x0) - $signed(xs);
        source_top <= $signed(y0) - $signed(ys);
        source_right <= source_left + WIDTH - 1;
        source_bottom <= source_top + HEIGHT - 1;
    end
    wire triangle_busy,triangle_valid;
    wire [10:0] triangle_x,triangle_width;
    wire [9:0] triangle_y;
    gpu_triangle #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) u_triangle (
        .clk(clk),.rst(rst),.start(st[$clog2(M_TRI_START)]),
        .x0(x0),.y0(y0),.x1(x1),.y1(y1),.x2(xs),.y2(ys),
        .busy(triangle_busy),.valid(triangle_valid),.ready(st[$clog2(M_TRI_WAIT)]),
        .span_x(triangle_x),.span_width(triangle_width),.span_y(triangle_y));
    // ZOOM (11): word4={source width,height}, each 1..128; words5/6
    // unsigned 8.16 U/V steps; word7 reserved. Source and destination pages
    // must differ. Index zero and samples beyond the source rectangle are
    // transparent. Invalid descriptors complete without writes. Row cache
    // holds at most 65 halfwords (odd source origin), reused on enlargement.
    reg [15:0] zoom_cache [0:127];
    reg [15:0] zoom_q;
    reg [39:0] zu, zv, zu_start;
    reg [7:0] zoom_index, zoom_cached_y;
    reg zoom_cached;
    wire [15:0] zw=txt[31:16], zh=txt[15:0];
    // The crop arrives in F3/F4, several cycles before Z_INIT/A_INIT.
    // Resolve its bounds in that gap: an add followed by a wide compare
    // must not feed the one-hot state transitions in a single cycle.
    reg [16:0] crop_right, crop_bottom;
    reg source_crop_valid;
    always @(posedge clk) begin
        crop_right <= {1'b0,xs} + {1'b0,zw};
        crop_bottom <= {1'b0,ys} + {1'b0,zh};
        source_crop_valid <= zw!=0 && zw<=128 && zh!=0 && zh<=128 &&
                             xs>=0 && ys>=0 && crop_right<=WIDTH && crop_bottom<=HEIGHT;
    end
    wire [23:0] zstepx=txt[55:32], zstepy=txt[87:64];
    wire [8:0] zbyte={1'b0,zu[23:16]}+{8'd0,xs[0]};
    wire [7:0] zpixel=zbyte[0] ? zoom_q[15:8]:zoom_q[7:0];
    always @(posedge clk) begin
        if(st[$clog2(M_Z_READ)] && s_valid) zoom_cache[zoom_index[6:0]]<=s_data;
        zoom_q<=zoom_cache[zbyte[7:1]];
    end
    // L12: inverse affine sampling, signed Q16.16. The entire source crop
    // is captured before writing, including when source and target overlap.
    // Normalized cache pitch: 128 bytes; two pixels per BSRAM word.
    reg signed [31:0] a_u0,a_v0,a_dudx,a_dvdx,a_dudy,a_dvdy;
    reg a_configured;
    reg signed [47:0] a_u,a_v,a_row_u,a_row_v;
    reg signed [47:0] a_xu,a_xv,a_yu,a_yv,a_origin_u,a_origin_v;
    reg [15:0] affine_cache [0:8191];
    reg [15:0] a_q;
    reg [6:0] a_load_y,a_load_word;
    reg [7:0] a_previous_high;
    reg [10:0] a_gpos;
    reg a_last,a_inside,a_lane;
    wire [7:0] a_pixel=a_lane ? a_q[15:8]:a_q[7:0];
    wire [5:0] a_previous_word=a_load_word[5:0]-6'd1;
    always @(posedge clk) begin
        // Clipped offsets are stable throughout source loading. Registered
        // products and sums keep geometry out of the pixel accumulator path.
        a_xu <= $signed({1'b0,offx}) * a_dudx;
        a_xv <= $signed({1'b0,offx}) * a_dvdx;
        a_yu <= $signed({1'b0,offy}) * a_dudy;
        a_yv <= $signed({1'b0,offy}) * a_dvdy;
        a_origin_u <= a_xu + a_u0;
        a_origin_v <= a_xv + a_v0;
        if(st[$clog2(M_A_READ)] && s_valid) begin
            if(!xs[0]) affine_cache[{a_load_y,a_load_word[5:0]}]<=s_data;
            else if(a_load_word!=0)
                affine_cache[{a_load_y,a_previous_word}]<={s_data[7:0],a_previous_high};
        end else if(st[$clog2(M_A_PAD)] && xs[0] && zw[0])
            affine_cache[{a_load_y,zw[6:1]}]<={8'd0,a_previous_high};
        a_q<=affine_cache[{a_v[22:16],a_u[22:17]}];
        a_gpos<=gpos;
        a_last<=gi==row_last_index;
        a_inside<=a_u[47:23]==0 && {9'd0,a_u[22:16]}<zw &&
                  a_v[47:23]==0 && {9'd0,a_v[22:16]}<zh;
        a_lane<=a_u[16];
    end
    assign ext_command={txt,{xs,ys},{x1,y1},{x0,y0},{op,dpage,spage,c0,c1}};
    always @(posedge clk) begin
        if (rst) begin
            ext_start<=0;ext_active<=0;
            f_req<=0;f_addr<=0;f_len<=0;f_color<=0;
            a_u0<=0;a_v0<=0;a_dudx<=0;a_dvdx<=0;a_dudy<=0;a_dvdy<=0;a_configured<=0;
            a_u<=0;a_v<=0;a_row_u<=0;a_row_v<=0;a_load_y<=0;a_load_word<=0;a_previous_high<=0;
            zu<=0;zv<=0;zu_start<=0;zoom_index<=0;zoom_cached_y<=0;zoom_cached<=0;
            offx <= 16'd0; offy <= 16'd0; copy_reverse <= 1'b0; copy_limit0<=0;copy_limit1<=0; line_negative_dy <= 17'sd0; line_step_x <= 1'b0; line_step_y <= 1'b0;
            st <= M_IDLE; ret <= M_IDLE; rp <= 8'd0; err_cmd_bad <= 16'd0; cmd_done <= 16'd0; s_req <= 1'b0; s_addr <= 24'd0; s_len <= 10'd0;
            w_req <= 1'b0; w_addr <= 24'd0; w_len <= 10'd0; c_req <= 1'b0; c_addr <= 24'd0; c_wdata <= 16'd0; c_wmask <= 2'b00;
            b0_we <= 1'b0; b1_we <= 1'b0; b0_a <= 10'd0; b1_a <= 10'd0; b0_d <= 8'd0; b1_d <= 8'd0; row_rewind <= 1'b0;
            op <= 8'd0; c0 <= 8'd0; c1 <= 8'd0; dpage <= 4'd0; spage <= 4'd0; x0 <= 0; y0 <= 0; x1 <= 0; y1 <= 0; xs <= 0; ys <= 0;
            cx0 <= 0; cy0 <= 0; cx1 <= 0; cy1 <= 0; rw <= 11'd0; rx <= 11'd0; ry <= 10'd0; rows_left <= 10'd0; dabs <= 8'd0; dneg <= 1'b0;
            recip <= 17'd0; t_start <= 18'd0; t_acc <= 18'd0; t_step <= 18'd0; t_row <= 18'd0; dq <= 17'd0; drem <= 28'd0; dcnt <= 5'd0; dn <= 17'd1;
            ldx <= 0; ldy <= 0; lerr <= 0; lx <= 0; ly <= 0; lsx <= 0; lsy <= 0; ccx <= 0; ccy <= 0; cxv <= 0; cyv <= 0; cerr <= 0; cpt <= 3'd0; px <= 0; py <= 0; sp_y <= 0; sp_xa <= 0; sp_xb <= 0; sp_vis <= 1'b0;
            txt <= 128'd0; tn <= 5'd0; tci <= 5'd0; tscale <= 1'b0; tsub <= 1'b0; tdup <= 1'b0; text_last_char <= 1'b0; trow <= 4'd0; tbit <= 3'd0; tpix <= 9'd0; b0_m <= 1'b1; b1_m <= 1'b1;
            wleft <= 11'd0; waddr <= 24'd0; gi <= 11'd0; m_first <= 2'b11; m_last <= 2'b11; wj_end <= 10'd0; cn <= 10'd0; copy_left <= 11'd0; sxx <= 0; source_row <= 0;
        end else begin
            ext_start<=0;
            f_req<=0;
            s_req <= 1'b0; w_req <= 1'b0; c_req <= 1'b0; b0_we <= 1'b0; b1_we <= 1'b0;
            row_rewind <= 1'b0;
            if(ext_active)begin
                if(ext_done)begin ext_active<=0;st<=M_DONE;end
            end else case (1'b1) // synthesis parallel_case
                // ---------------- lecture d'une commande (4 mots utiles, 4 réservés) ----------------
                st[$clog2(M_IDLE)]: if (cmd_avail) st <= M_F0;
                st[$clog2(M_F0)]: begin {op, dpage, spage, c0, c1} <= cmem[rp[6:0]]; rp <= rp + 8'd1; st <= M_F1; end
                st[$clog2(M_F1)]: begin {x0, y0} <= cmem[rp[6:0]]; rp <= rp + 8'd1; st <= M_F2; end
                st[$clog2(M_F2)]: begin {x1, y1} <= cmem[rp[6:0]]; rp <= rp + 8'd1; st <= M_F3; end
                st[$clog2(M_F3)]: begin {xs, ys} <= cmem[rp[6:0]]; rp <= rp + 8'd1; st <= M_F4; end
                st[$clog2(M_F4)]: begin txt[31:0]   <= cmem[rp[6:0]]; rp <= rp + 8'd1; st <= M_F5; end
                st[$clog2(M_F5)]: begin txt[63:32]  <= cmem[rp[6:0]]; rp <= rp + 8'd1; st <= M_F6; end
                st[$clog2(M_F6)]: begin txt[95:64]  <= cmem[rp[6:0]]; rp <= rp + 8'd1; st <= M_F7; end
                st[$clog2(M_F7)]: begin txt[127:96] <= cmem[rp[6:0]]; rp <= rp + 8'd1; st <= (op == 8'd9) ? M_TXT_INIT : M_SETUP; end
                st[$clog2(M_TXT_INIT)]: begin                                                // texte : largeur = n × 8 × échelle, hauteur = 16 × échelle
                    tn <= (x1[15:0] > 16'd16) ? 5'd16 : x1[4:0]; tscale <= (y1 == 16'sd2);
                    x1 <= (y1 == 16'sd2) ? $signed({7'd0, ((x1[15:0] > 16'd16) ? 5'd16 : x1[4:0]), 4'd0}) : $signed({8'd0, ((x1[15:0] > 16'd16) ? 5'd16 : x1[4:0]), 3'd0});
                    y1 <= (y1 == 16'sd2) ? 16'sd32 : 16'sd16; st <= M_SETUP;
                end
                // ---------------- préparation : découpe, diviseur du dégradé ----------------
                st[$clog2(M_SETUP)]: begin
                    dabs <= (c1 >= c0) ? c1 - c0 : c0 - c1; dneg <= (c1 < c0);
                    case (1'b1) // synthesis parallel_case
                        rectangle_opcode: begin                 // rectangles et texte : x0, y0, largeur x1, hauteur y1
                            cx0 <= (x0 < 0) ? 16'sd0 : x0; cy0 <= (y0 < 0) ? 16'sd0 : y0;
                            cx1 <= (x0 + x1 - 1 > X_MAX) ? X_MAX : x0 + x1 - 16'sd1;
                            cy1 <= (y0 + y1 - 1 > Y_MAX) ? Y_MAX : y0 + y1 - 16'sd1;
                            dn <= (op == 8'd2) ? {1'b0, x1[15:0]} - 17'd1 : (op == 8'd3) ? {1'b0, y1[15:0]} - 17'd1 : {1'b0, x1[15:0]} + {1'b0, y1[15:0]} - 17'd2;
                            dcnt <= 5'd0; dq <= 17'd0; drem <= 28'd0;
                            copy_reverse <= (op == 8'd8 && dpage == spage && y0 > ys);
                            st <= (x1 <= 0 || y1 <= 0) ? M_DONE : (op == 8'd8 ? M_COPY_CLIP : M_CLIP);
                        end
                        line_opcode: begin                                                // ligne : Bresenham
                            ldx <= (x1 >= x0) ? x1 - x0 : x0 - x1; ldy <= (y1 >= y0) ? y1 - y0 : y0 - y1;
                            lsx <= (x1 >= x0) ? 16'sd1 : -16'sd1; lsy <= (y1 >= y0) ? 16'sd1 : -16'sd1; lx <= x0; ly <= y0;
                            st <= M_LINE_INIT;
                        end
                        circle_opcode: begin                                          // cercle : rayon x1 ≥ 0
                            ccx <= x0; ccy <= y0; cxv <= x1; cyv <= 16'sd0; cerr <= 16'sd1 - x1; cpt <= 3'd0; st <= (x1 < 0) ? M_DONE : M_CIRC;
                        end
                        triangle_opcode: st<=M_TRI_START;
                        affine_setup_opcode: begin
                            a_u0<={x0,y0};a_v0<={x1,y1};a_dudx<={xs,ys};
                            a_dvdx<=txt[31:0];a_dudy<=txt[63:32];a_dvdy<=txt[95:64];
                            a_configured<=txt[127:96]==0 && {dpage,spage,c0,c1}==0;
                            st<=M_DONE;
                        end
                        extended_opcode:begin ext_start<=1;ext_active<=1;end
                        default: begin err_cmd_bad <= err_cmd_bad + 16'd1; st <= M_DONE; end
                    endcase
                end
                st[$clog2(M_COPY_CLIP)]: begin
                    // Intersect destination with the translated source surface.
                    // Clamp the empty-rectangle sentinels before narrowing to 16 bits.
                    if (source_left > cx0) cx0 <= source_left > X_MAX ? X_MAX + 16'sd1 : source_left[15:0];
                    if (source_top > cy0) cy0 <= source_top > Y_MAX ? Y_MAX + 16'sd1 : source_top[15:0];
                    if (source_right < cx1) cx1 <= source_right < 0 ? -16'sd1 : source_right[15:0];
                    if (source_bottom < cy1) cy1 <= source_bottom < 0 ? -16'sd1 : source_bottom[15:0];
                    st <= M_CLIP;
                end
                st[$clog2(M_CLIP)]: begin
                    offx <= cx0 - x0; offy <= cy0 - y0;
                    st <= (op == 8'd9) ? M_TXT_START : (op == 8'd2 || op == 8'd3 || op == 8'd4) ? M_DIV : M_RECT_INIT;
                end
                st[$clog2(M_DIV)]: begin                                                     // 65536 / dn ; dn = 0 (un seul pixel) → 65536
                    if (dn == 17'd0) begin recip <= 17'd65536; st <= M_RECT_INIT; end
                    else begin : div_step
                        reg [27:0] r2; r2 = {drem[26:0], (dcnt == 5'd0) ? 1'b1 : 1'b0};   // dividende 1 puis 16 zéros
                        if (r2 >= {11'd0, dn}) begin drem <= r2 - {11'd0, dn}; dq <= {dq[15:0], 1'b1}; end
                        else begin drem <= r2; dq <= {dq[15:0], 1'b0}; end
                        if (dcnt == 5'd16) begin recip <= (r2 >= {11'd0, dn}) ? {dq[15:0], 1'b1} : {dq[15:0], 1'b0}; st <= M_RECT_INIT; end
                        else dcnt <= dcnt + 5'd1;
                    end
                end
                st[$clog2(M_RECT_INIT)]: begin                                               // lignes visibles ; t au départ de la première ligne découpée
                    if (rectangle_empty) st <= M_DONE;
                    else begin
                        ry <= copy_reverse ? cy1[9:0] : cy0[9:0]; rows_left <= cy1[9:0] - cy0[9:0] + 10'd1; rx <= cx0[10:0]; rw <= cx1[10:0] - cx0[10:0] + 11'd1;
                        case (op)
                            8'd2: begin t_start <= recip * offx; t_step <= {1'b0, recip}; t_row <= 18'd0; end
                            8'd3: begin t_start <= recip * offy; t_step <= 18'd0; t_row <= {1'b0, recip}; end
                            8'd4: begin t_start <= recip * ({1'b0, offy} + {1'b0, offx}); t_step <= {1'b0, recip}; t_row <= {1'b0, recip}; end
                            default: begin t_start <= 18'd0; t_step <= 18'd0; t_row <= 18'd0; end
                        endcase
                        st <= op==13 ? M_A_INIT:(op==11 ? M_Z_INIT:M_ROW_START);
                    end
                end
                // ---------------- une ligne du rectangle ----------------
                st[$clog2(M_ROW_START)]: begin
                    // Geometry is already stable. Prepare the DMA row here,
                    // keeping last-pixel/last-glyph decode off its enables.
                    waddr <= row_addr(dbase, ry, rx); wleft <= row_words;
                    gi <= 11'd0; t_acc <= t_start; cn <= 10'd0; ret <= M_ROW_ADV;
                    st <= (op == 8'd8) ? M_COPY_RD : (op==8'd1 ? M_FILL_START:M_ROW_GEN);
                end
                st[$clog2(M_ROW_GEN)]: begin                                                 // 1 pixel / cycle, banque de la position gi + rx[0]
                    if (gpos[0]) begin b1_we <= 1'b1; b1_a <= gpos[10:1]; b1_d <= gen_pix; b1_m <= 1'b1; end
                    else begin b0_we <= 1'b1; b0_a <= gpos[10:1]; b0_d <= gen_pix; b0_m <= 1'b1; end
                    t_acc <= t_acc + t_step;
                    if (gi == row_last_index) begin
                        wj_end <= row_words[9:0] - 10'd1;
                        m_first <= rx[0] ? 2'b10 : 2'b11; m_last <= row_last[0] ? 2'b11 : 2'b01; row_rewind <= 1'b1; st <= M_ROW_SEG;
                    end else gi <= gi + 11'd1;
                end
                st[$clog2(M_ROW_SEG)]: begin w_req <= 1'b1; w_addr <= waddr; w_len <= seg_len; st <= M_ROW_WAIT; end
                st[$clog2(M_ROW_WAIT)]: begin
                    // Advance when the DMA samples our registered request.
                    // It cannot finish until after packing/sending the data.
                    // Using w_len cuts segment selection from this adder,
                    // without adding a cycle to any request or completion.
                    if (w_req) begin
                        waddr <= waddr + {14'd0, w_len};
                        wleft <= wleft - {1'b0, w_len};
                    end
                    if (w_done) st <= (wleft != 11'd0) ? M_ROW_SEG : ret;
                end
                st[$clog2(M_ROW_ADV)]: begin                                                 // ligne suivante du rectangle
                    rows_left <= rows_left - 10'd1; ry <= copy_reverse ? ry - 10'd1 : ry + 10'd1; t_start <= t_start + t_row;
                    st <= (rows_left == 10'd1) ? M_DONE : M_ROW_START;
                end
                st[$clog2(M_Z_INIT)]: begin
                    zu_start<=offx*zstepx;zv<=offy*zstepy;zoom_cached<=0;
                    st<=M_Z_ROW;
                    if(!source_crop_valid ||
                       spage==dpage || txt[63:56]!=0 || txt[95:88]!=0) st<=M_DONE;
                end
                st[$clog2(M_Z_ROW)]: begin
                    waddr<=row_addr(dbase,ry,rx);wleft<=row_words;
                    gi<=0;zu<=zu_start;ret<=M_Z_ADV;zoom_index<=0;
                    source_row<=ys[9:0]+{2'b0,zv[23:16]};
                    if(zv[39:16]>={8'd0,zh})st<=M_Z_ADV;
                    else if(zoom_cached && zoom_cached_y==zv[23:16])st<=M_Z_SAMPLE;
                    else st<=M_Z_ADDR;
                end
                st[$clog2(M_Z_ADDR)]: begin
                    s_addr<=row_addr(sbase,source_row,xs[10:0]);
                    s_len<=({1'b0,zw[7:0]}+{8'd0,xs[0]}+9'd1)>>1;
                    s_req<=1;st<=M_Z_READ;zoom_cached_y<=zv[23:16];zoom_cached<=1;
                end
                st[$clog2(M_Z_READ)]: begin
                    if(s_valid)zoom_index<=zoom_index+1'b1;
                    if(s_done)st<=M_Z_SAMPLE;
                end
                st[$clog2(M_Z_SAMPLE)]: st<=M_Z_PIXEL; // synchronous cache read after U changes
                st[$clog2(M_Z_PIXEL)]: begin
                    if(gpos[0])begin b1_we<=1;b1_a<=gpos[10:1];b1_d<=zpixel;b1_m<=zpixel!=0 && zu[39:16]<{8'd0,zw};end
                    else begin b0_we<=1;b0_a<=gpos[10:1];b0_d<=zpixel;b0_m<=zpixel!=0 && zu[39:16]<{8'd0,zw};end
                    zu<=zu+{16'd0,zstepx};
                    if(gi==row_last_index)begin
                        wj_end<=row_words[9:0]-1'b1;
                        m_first<=rx[0]?2'b10:2'b11;m_last<=row_last[0]?2'b11:2'b01;row_rewind<=1'b1;st<=M_ROW_SEG;
                    end else begin gi<=gi+1'b1;st<=M_Z_SAMPLE;end
                end
                st[$clog2(M_Z_ADV)]: begin
                    rows_left<=rows_left-1'b1;ry<=ry+1'b1;zv<=zv+{16'd0,zstepy};
                    st<=rows_left==1 ? M_DONE:M_Z_ROW;
                end
                st[$clog2(M_A_INIT)]: begin
                    a_load_y<=0;a_load_word<=0;source_row<=ys[9:0];st<=M_A_ADDR;
                    if(!a_configured || !source_crop_valid ||
                       txt[127:32]!=0 || {c0,c1}!=0) st<=M_DONE;
                end
                st[$clog2(M_A_ADDR)]: begin
                    s_addr<=row_addr(sbase,source_row,xs[10:0]);
                    s_len<=({1'b0,zw[7:0]}+{8'd0,xs[0]}+9'd1)>>1;
                    s_req<=1;a_load_word<=0;st<=M_A_READ;
                end
                st[$clog2(M_A_READ)]: begin
                    if(s_valid)begin a_load_word<=a_load_word+1'b1;a_previous_high<=s_data[15:8];end
                    if(s_done)st<=M_A_PAD;
                end
                st[$clog2(M_A_PAD)]: begin
                    a_load_y<=a_load_y+1'b1;source_row<=source_row+1'b1;
                    st<=({9'd0,a_load_y}+16'd1==zh) ? M_A_BEGIN:M_A_ADDR;
                end
                st[$clog2(M_A_BEGIN)]: begin
                    a_row_u<=a_origin_u+a_yu;a_row_v<=a_origin_v+a_yv;st<=M_A_ROW;
                end
                st[$clog2(M_A_ROW)]: begin
                    waddr<=row_addr(dbase,ry,rx);wleft<=row_words;
                    a_u<=a_row_u;a_v<=a_row_v;gi<=0;ret<=M_A_ADV;st<=M_A_SAMPLE;
                end
                st[$clog2(M_A_SAMPLE)]: begin
                    a_u<=a_u+a_dudx;a_v<=a_v+a_dvdx;gi<=gi+1'b1;st<=M_A_PIXEL;
                end
                st[$clog2(M_A_PIXEL)]: begin
                    // Consume the registered BSRAM sample while the next one
                    // is being read: one destination pixel per GPU clock.
                    if(a_gpos[0])begin b1_we<=1;b1_a<=a_gpos[10:1];b1_d<=a_pixel;b1_m<=a_inside && a_pixel!=0;end
                    else begin b0_we<=1;b0_a<=a_gpos[10:1];b0_d<=a_pixel;b0_m<=a_inside && a_pixel!=0;end
                    a_u<=a_u+a_dudx;a_v<=a_v+a_dvdx;gi<=gi+1'b1;
                    if(a_last)begin
                        wj_end<=row_words[9:0]-1'b1;
                        m_first<=rx[0]?2'b10:2'b11;m_last<=row_last[0]?2'b11:2'b01;row_rewind<=1;st<=M_ROW_SEG;
                    end
                end
                st[$clog2(M_A_ADV)]: begin
                    rows_left<=rows_left-1'b1;ry<=ry+1'b1;
                    a_row_u<=a_row_u+a_dudy;a_row_v<=a_row_v+a_dvdy;
                    st<=rows_left==1 ? M_DONE:M_A_ROW;
                end
                st[$clog2(M_FILL_START)]: begin
                    f_addr<={row_addr(dbase,ry,rx),rx[0]};f_len<=rw;f_color<=c0;
                    f_req<=1;st<=M_FILL_WAIT;
                end
                st[$clog2(M_FILL_WAIT)]:if(f_done)st<=ret;
                st[$clog2(M_TRI_START)]: st<=M_TRI_WAIT;
                st[$clog2(M_TRI_WAIT)]: begin
                    rx<=triangle_x;ry<=triangle_y;rw<=triangle_width;
                    gi<=0;t_acc<=0;ret<=M_TRI_WAIT;
                    if(triangle_valid) st<=M_FILL_START;
                    else if(!triangle_busy) st<=M_DONE;
                end
                // ---------------- ligne : Bresenham, un pixel par M_PIX ----------------
                st[$clog2(M_LINE)]: begin px <= lx; py <= ly; ret <= (lx == x1 && ly == y1) ? M_DONE : M_LINE_STEP; st <= M_PIX; end
                st[$clog2(M_LINE_INIT)]: begin
                    lerr <= ldx - ldy; line_negative_dy <= -ldy; st <= M_LINE;
                end
                st[$clog2(M_LINE_STEP)]: begin : line_test
                    reg signed [18:0] error_twice;
                    error_twice = lerr <<< 1;
                    line_step_x <= error_twice > line_negative_dy;
                    line_step_y <= error_twice < ldx;
                    st <= M_LINE_X;
                end
                st[$clog2(M_LINE_X)]: begin
                    if (line_step_x) begin lerr <= lerr - ldy; lx <= lx + lsx; end
                    st <= M_LINE_Y;
                end
                st[$clog2(M_LINE_Y)]: begin
                    if (line_step_y) begin lerr <= lerr + ldx; ly <= ly + lsy; end
                    st <= M_LINE;
                end
                st[$clog2(M_PIX)]: begin                                                     // pixel isolé (découpé) par le port C
                    if (px < 0 || px > X_MAX || py < 0 || py > Y_MAX) st <= ret;
                    else begin c_req <= 1'b1; c_addr <= row_addr(dbase, py[9:0], px[10:0]); c_wdata <= {c0, c0}; c_wmask <= px[0] ? 2'b10 : 2'b01; st <= M_PIX_WAIT; end
                end
                st[$clog2(M_PIX_WAIT)]: if (c_ack) st <= ret;
                // ---------------- cercle : point médian, 8 points (contour) ou 4 segments (disque) par itération ----------------
                st[$clog2(M_CIRC)]: if (cxv < cyv) st <= M_DONE; else begin cpt <= 3'd0; st <= (op == 8'd6) ? M_CIRC_PTS : M_CFILL_CALC; end
                st[$clog2(M_CIRC_PTS)]: begin
                    case (cpt)
                        3'd0: begin px <= ccx + cxv; py <= ccy + cyv; end 3'd1: begin px <= ccx - cxv; py <= ccy + cyv; end
                        3'd2: begin px <= ccx + cxv; py <= ccy - cyv; end 3'd3: begin px <= ccx - cxv; py <= ccy - cyv; end
                        3'd4: begin px <= ccx + cyv; py <= ccy + cxv; end 3'd5: begin px <= ccx - cyv; py <= ccy + cxv; end
                        3'd6: begin px <= ccx + cyv; py <= ccy - cxv; end default: begin px <= ccx - cyv; py <= ccy - cxv; end
                    endcase
                    ret <= (cpt == 3'd7) ? M_CIRC_STEP : M_CIRC_PTS; cpt <= cpt + 3'd1; st <= M_PIX;
                end
                st[$clog2(M_CFILL_CALC)]: begin                                              // segment horizontal cpt : bornes (un cycle), découpe au suivant (chemin critique du build p13)
                    case (cpt) 3'd0: begin sp_y <= ccy + cyv; sp_xa <= ccx - cxv; sp_xb <= ccx + cxv; end 3'd1: begin sp_y <= ccy - cyv; sp_xa <= ccx - cxv; sp_xb <= ccx + cxv; end
                               3'd2: begin sp_y <= ccy + cxv; sp_xa <= ccx - cyv; sp_xb <= ccx + cyv; end default: begin sp_y <= ccy - cxv; sp_xa <= ccx - cyv; sp_xb <= ccx + cyv; end endcase
                    st <= M_CFILL;
                end
                st[$clog2(M_CFILL)]: begin                                                   // découpe (registrée), décision au cycle suivant
                    sp_xa <= sp_left_clipped; sp_xb <= sp_right_clipped;
                    sp_vis <= !(sp_y < 0 || sp_y > Y_MAX) && sp_left_clipped<=sp_right_clipped; st <= M_CFILL_GO;
                end
                st[$clog2(M_CFILL_GO)]: begin                                                // segment visible → la ligne l'écrit ; sinon le suivant
                    if (!sp_vis) st <= M_CFILL_NEXT;
                    else begin ry <= sp_y[9:0]; rx <= sp_xa[10:0]; rw <= sp_width; gi <= 11'd0; t_acc <= 18'd0; ret <= M_CFILL_NEXT; st <= M_FILL_START; end
                end
                st[$clog2(M_CFILL_NEXT)]: begin cpt <= cpt + 3'd1; st <= (cpt == 3'd3) ? M_CIRC_STEP : M_CFILL_CALC; end
                st[$clog2(M_CIRC_STEP)]: begin                                               // pas suivant du point médian
                    if (cerr < 0) begin cerr <= cerr + 2 * cyv + 16'sd3; cyv <= cyv + 16'sd1; end
                    else begin cerr <= cerr + 2 * (cyv - cxv) + 16'sd5; cyv <= cyv + 16'sd1; cxv <= cxv - 16'sd1; end
                    st <= M_CIRC;
                end
                // ---------------- copie : ligne source lue par S dans la mémoire de ligne, alignée sur la phase cible ----------------
                st[$clog2(M_COPY_RD)]: begin : cp
                    reg signed [15:0] sx_, sy_; sx_ = xs + (cx0 - x0); sy_ = ys + ($signed({6'd0, ry}) - y0);   // source décalée comme la cible découpée
                    sxx <= sx_; source_row <= sy_[9:0];
                    cn <= 10'd0; st <= M_COPY_COUNT;
                end
                st[$clog2(M_COPY_COUNT)]: begin
                    // Keep coordinate translation out of the row-address path.
                    s_addr <= row_addr(sbase, source_row, sxx[10:0]);
                    copy_left <= {1'b0, (sxx[10:0] + rw - 11'd1) >> 1} - {1'b0, sxx[10:1]} + 11'd1;
                    // Move the source parity across the range comparisons:
                    // 2*cn-parity < rw; 2*cn+1-parity < rw. Prepare their
                    // constant bounds here, before any source data can arrive.
                    copy_limit0<=rw+{10'd0,sxx[0]};
                    copy_limit1<=rw+{10'd0,sxx[0]}-11'd1;
                    st <= M_COPY_SEG;
                end
                st[$clog2(M_COPY_SEG)]: begin : seg
                    s_req <= 1'b1;
                    s_len <= copy_segment_crosses ? 10'd512-{1'b0,s_addr[8:0]} : copy_left[9:0];
                    copy_left <= copy_segment_crosses ? copy_segment_remaining[10:0] : 11'd0;
                    st <= M_COPY_WAIT;
                end
                st[$clog2(M_COPY_WAIT)]: begin
                    if (s_valid) begin : cw                                      // mot n : pixels 2n − sxx[0] (octet bas) et +1, à la position + rx[0]
                        reg signed [12:0] p0, p1; reg [10:0] q0, q1;
                        p0 = $signed({2'b00, cn, 1'b0}) - $signed({12'd0, sxx[0]}); p1 = p0 + 13'sd1;
                        q0 = p0[10:0] + {10'd0, rx[0]}; q1 = p1[10:0] + {10'd0, rx[0]};
                        if ((!sxx[0] || cn!=0) && {cn,1'b0}<copy_limit0) begin
                            if (q0[0]) begin b1_we <= 1'b1; b1_a <= q0[10:1]; b1_d <= s_data[7:0]; b1_m <= 1'b1; end else begin b0_we <= 1'b1; b0_a <= q0[10:1]; b0_d <= s_data[7:0]; b0_m <= 1'b1; end
                        end
                        if ({cn,1'b0}<copy_limit1) begin
                            if (q1[0]) begin b1_we <= 1'b1; b1_a <= q1[10:1]; b1_d <= s_data[15:8]; b1_m <= 1'b1; end else begin b0_we <= 1'b1; b0_a <= q1[10:1]; b0_d <= s_data[15:8]; b0_m <= 1'b1; end
                        end
                        cn <= cn + 10'd1;
                    end
                    if (s_done) begin
                        if (copy_left != 11'd0) begin s_addr <= s_addr + {14'd0, s_len}; st <= M_COPY_SEG; end
                        else begin
                            wj_end <= row_words[9:0] - 10'd1;
                            m_first <= rx[0] ? 2'b10 : 2'b11; m_last <= row_last[0] ? 2'b11 : 2'b01; row_rewind <= 1'b1; st <= M_ROW_SEG;
                        end
                    end
                end
                // ---------------- texte : une rangée de glyphe (× échelle) à la fois, par la mémoire de ligne et le port W ----------------
                st[$clog2(M_TXT_START)]: begin trow <= 4'd0; tsub <= 1'b0; st <= (rectangle_empty || tn == 5'd0) ? M_DONE : M_TXT_ROW; end
                st[$clog2(M_TXT_ROW)]: begin                                                 // rangée visible ? (cy0/cy1 découpés)
                    // These values are unused on a clipped row. Load them
                    // unconditionally to keep Y addition/comparison off the
                    // enable paths of the shared rectangle registers.
                    ry <= ty[9:0]; rx <= cx0[10:0]; rw <= cx1[10:0] - cx0[10:0] + 11'd1; tci <= 5'd0; tpix <= 9'd0;
                    if (ty < cy0 || ty > cy1) st <= M_TXT_NEXT;
                    else st <= M_TXT_FONT;
                end
                st[$clog2(M_TXT_FONT)]: begin
                    // No DMA starts until the entire glyph row is generated.
                    waddr <= row_addr(dbase, ry, rx); wleft <= row_words;
                    // Character index is stable for the entire glyph row.
                    text_last_char <= (tci + 5'd1 == tn);
                    tbit <= 3'd0; tdup <= 1'b0; st <= M_TXT_BITS;
                end   // font_q valide au cycle suivant (adresse = {caractère, rangée})
                st[$clog2(M_TXT_BITS)]: begin : tb                                           // 8 pixels (× échelle) du glyphe, découpés à gauche (offx) et à droite (rw)
                    reg on; reg [8:0] rel; reg [10:0] pos;
                    on = font_q[3'd7 - tbit]; rel = tpix - offx[8:0]; pos = {2'b00, rel} + {10'd0, rx[0]};
                    if (tpix >= {offx[8:0]} && {2'b00, rel} < rw) begin           // rw entier : à 256 px (16 caractères × échelle 2) rw[8:0] valait 0
                        if (pos[0]) begin b1_we <= 1'b1; b1_a <= pos[10:1]; b1_d <= on ? c0 : c1; b1_m <= on || (c1 != 8'd0); end
                        else begin b0_we <= 1'b1; b0_a <= pos[10:1]; b0_d <= on ? c0 : c1; b0_m <= on || (c1 != 8'd0); end
                    end
                    tpix <= tpix + 9'd1;
                    if (tscale && !tdup) tdup <= 1'b1;
                    else begin
                        tdup <= 1'b0;
                        if (tbit != 3'd7) tbit <= tbit + 3'd1;
                        else if (!text_last_char) begin tci <= tci + 5'd1; st <= M_TXT_FONT; end
                        else begin                                               // rangée finie : écriture
                            wj_end <= row_words[9:0] - 10'd1;
                            m_first <= rx[0] ? 2'b10 : 2'b11; m_last <= row_last[0] ? 2'b11 : 2'b01; row_rewind <= 1'b1; ret <= M_TXT_NEXT; st <= M_ROW_SEG;
                        end
                    end
                end
                st[$clog2(M_TXT_NEXT)]: begin                                                // rangée suivante (sous-rangée d'abord à l'échelle 2)
                    if (tscale && !tsub) begin tsub <= 1'b1; st <= M_TXT_ROW; end
                    else begin tsub <= 1'b0; if (trow == 4'd15) st <= M_DONE; else begin trow <= trow + 4'd1; st <= M_TXT_ROW; end end
                end
                st[$clog2(M_DONE)]: begin cmd_done <= cmd_done + 16'd1; st <= M_IDLE; end
                default: st <= M_IDLE;
            endcase
        end
    end
    assign debug_state={st,wp,rp,op,rst,cmd_we,cmd_full,cmd_avail,ext_active,ext_start,ext_done,busy};
endmodule
`default_nettype wire
