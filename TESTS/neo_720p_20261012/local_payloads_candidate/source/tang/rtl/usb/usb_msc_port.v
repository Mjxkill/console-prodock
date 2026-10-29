// usb_msc_port.v — accès du firmware aux deux endpoints bulk du disque USB
// (interface stockage de masse, EP1 OUT et EP1 IN). Le protocole Bulk-Only
// et SCSI est entièrement dans le firmware ; ce module ne transporte que des
// octets et garantit les frontières de paquets en émission.
//
// Fenêtre AHB (0xE9003000) :
//   +00 R  identité 0x554d5343 (« UMSC »)
//   +04 R  état : bit0 octet reçu disponible, bit1 émission vide (tout octet
//          validé a été acquitté par l'hôte), bit2 reset du bus vu,
//          bit3 reset Bulk-Only vu, bit4 purge en cours, bit5 configuré,
//          bit6 High Speed, bit7 perte (émission ou réception saturée),
//          bit8 le firmware sert le disque, bit9 service demandé,
//          bit10 garde BOT verrouillé (jusqu'au reset hôte),
//          bits 31:16 octets émis non encore acquittés
//   +08 R  octet reçu : bit31 = 1 si aucun octet, sinon bits 7:0 et retrait
//   +0c W  octet à émettre (bits 7:0)
//   +10 W  validation : tous les octets écrits deviennent visibles de l'hôte
//   +14 W  commande : bit0 purge des deux sens, bit1 demande à servir le
//          disque, bit2 efface « reset du bus », bit3 efface « reset
//          Bulk-Only », bit5 rend le disque, bit6 verrouille BOT, bit7 efface « perte »
//   +18 R  octets écrits (15:0) et acquittés (31:16), compteurs modulo 65536
//   +1c W  quatre octets à émettre, celui des bits 7:0 en premier
//   +20 R  quatre octets reçus, le premier dans les bits 7:0, et retrait.
//          À ne lire que si +24 en annonce au moins quatre ; sinon la lecture
//          rend ce qu'elle a après 15 cycles et lève « perte »
//   +24 R  nombre d'octets reçus disponibles (valeur prudente)
//   +28 R  version du contrat BOT : 1 = frontières de paquets + STALL
//
// Émission : les octets et le marqueur de validation traversent la même FIFO
// double horloge, donc dans l'ordre. Côté USB, usb_fifo n'annonce à l'hôte
// que min(validés − acquittés, taille de paquet) : un bloc en cours
// d'écriture n'est jamais pris pour un paquet court. Écrire tant que le
// niveau non acquitté (bits 31:16 de l'état) ne dépasse pas 3 576 ; au-delà l'octet est
// refusé et « perte » est levé.
// Aucune attente AHB ne dépend de l'horloge USB.
//
// Lecteur sans carte : tant qu'aucun firmware ne sert le disque, ce module
// répond lui-même à l'hôte comme un lecteur de cartes vide (INQUIRY et
// REQUEST SENSE réussis, « support absent » pour le reste, phases de données
// respectées). Sans cela, un firmware qui ignore le disque laisserait l'hôte
// sans réponse : il réinitialiserait le périphérique entier, port série
// compris. Le firmware demande le disque (bit1 de la commande) et l'obtient
// entre deux commandes de l'hôte (bit8 de l'état). Il le garde tant qu'il
// accède à cette fenêtre : après 2^WATCHDOG_BITS cycles AHB sans accès
// (processeur arrêté, autre programme chargé), le lecteur redevient vide.
`default_nettype none
module usb_msc_port #(
    parameter WATCHDOG_BITS = 29        // 6,7 s à 80 MHz
) (
    input  wire        clk,            // 60 MHz, domaine du contrôleur USB
    input  wire        reset_n,        // asynchrone, commun aux deux domaines
    input  wire        bus_reset,      // clk : reset du bus USB
    input  wire        bot_reset,      // clk : impulsion, requête Bulk-Only Reset
    input  wire        online,         // clk
    input  wire        highspeed,      // clk
    input  wire        ep_halted,      // clk : erreur du garde BOT
    output wire        halt_request,   // clk : demande firmware synchronisée
    output wire        ep_flush,       // clk : remet à zéro les tampons EP1 de usb_fifo
    output reg         ep_tx_dval,
    output reg  [7:0]  ep_tx_data,
    output reg  [15:0] ep_tx_committed,
    input  wire [15:0] ep_tx_sent,
    output wire        ep_rx_rdy,
    input  wire        ep_rx_dval,
    input  wire [7:0]  ep_rx_data,
    input  wire        hclk, hsel, hwrite,
    input  wire [1:0]  htrans,
    input  wire [31:0] haddr, hwdata,
    output reg  [31:0] hrdata,
    output wire        hready
);
    // Sortie de reset propre à chaque horloge, puis vue croisée (comme usb_idle_trace).
    // syn_preserve : sinon la synthèse fusionne ces bascules avec celles, identiques, de usb_idle_trace.
    (* ASYNC_REG="TRUE" *) reg [2:0] hr /* synthesis syn_preserve=1 */ = 0, ur /* synthesis syn_preserve=1 */ = 0;
    (* ASYNC_REG="TRUE" *) reg [1:0] hu /* synthesis syn_preserve=1 */ = 0, uh /* synthesis syn_preserve=1 */ = 0;
    always @(posedge hclk or negedge reset_n)
        if (!reset_n) begin hr <= 0; uh <= 0; end
        else begin hr <= {hr[1:0], 1'b1}; uh <= {uh[0], ur[2]}; end
    always @(posedge clk or negedge reset_n)
        if (!reset_n) begin ur <= 0; hu <= 0; end
        else begin ur <= {ur[1:0], 1'b1}; hu <= {hu[0], hr[2]}; end

    // Assert immediately, release each domain through its own synchronizer.
    // The last local reset flop drives the state, rather than the distant
    // shared reset expression; hr/ur also retain the cross-domain ready gate.
    // Purge avec acquittement aller-retour : une horloge USB arrêtée ne
    // peut plus manquer la demande entière. Après observation côté USB,
    // tenir le reset 128 cycles AHB ; attendre ensuite son retrait observé
    // avant les 127 cycles de garde. L'AHB reste toujours consultable.
    reg  [7:0] flush_count;
    wire       flush_h = flush_count[7];
    // Même valeur que (flush_count != 0), sans décodeur combinatoire devant
    // le reset des FIFO et le multiplexeur du rassembleur RX4.
    reg        quiet_h /* synthesis syn_preserve=1 */;
    (* ASYNC_REG="TRUE" *) reg [1:0] flush_s = 0, busrst_s = 0, online_s = 0, hs_s = 0;
    reg        flush_u;
    (* ASYNC_REG="TRUE" *) reg [1:0] flush_ack_h = 0;
    always @(posedge hclk or negedge hr[2])
        if(!hr[2]) flush_ack_h<=0;
        else flush_ack_h<={flush_ack_h[0],flush_u};
    always @(posedge clk) begin
        flush_s <= {flush_s[0], flush_h};
        flush_u <= flush_s[1];
    end
    always @(posedge hclk) begin
        busrst_s <= {busrst_s[0], bus_reset};
        online_s <= {online_s[0], online};
        hs_s     <= {hs_s[0], highspeed};
    end
    // Propriété du disque. want_h : le firmware le demande et reste actif.
    // owner_u : accordé côté USB, uniquement entre deux commandes de l'hôte.
    // abandoned : le firmware a cessé de répondre (chien de garde) ; il a pu
    // laisser une commande en plan, les tampons sont alors purgés. Quand il
    // rend le disque lui-même (entre deux commandes), rien n'est purgé : une
    // commande de l'hôte arrivant à cet instant n'est pas perdue.
    reg                     serve, abandoned;
    reg  [2:0]              abandon_delay;
    reg [WATCHDOG_BITS:0]   watchdog;            // le bit de poids fort passe à 1 à l'expiration
    wire                    want_h = serve;      // registre : source propre pour le synchroniseur
    (* ASYNC_REG="TRUE" *) reg [1:0] want_s = 0, owner_s = 0, abandoned_s = 0;
    reg        owner_u;
    reg  [5:0] handback;                 // purge côté USB quand le firmware rend ou perd le disque
    reg        handback_active /* synthesis syn_preserve=1 */;
    wire       empty_idle;               // le lecteur vide est entre deux commandes, émission terminée
    wire       owner_h = owner_s[1];
    always @(posedge clk) begin want_s <= {want_s[0], want_h}; abandoned_s <= {abandoned_s[0], abandoned}; end
    always @(posedge hclk) owner_s <= {owner_s[0], owner_u};
    wire ubase  = !ur[2] || !hu[1] || bus_reset;
    wire uflush = flush_u || handback_active;
    assign ep_flush = uflush;
    always @(posedge clk or negedge ur[2]) begin
        if (!ur[2]) begin owner_u <= 1'b0; handback <= 6'd0; handback_active<=0; end
        else begin
            // Same cycles as (handback != 0), without a counter reduction
            // in front of the distributed endpoint/FIFO reset and enables.
            if (handback != 0) begin handback <= handback - 1'b1; handback_active<=handback!=1; end
            // Un reset du bus ne retire pas le disque au firmware : il le voit et purge.
            if (!ur[2] || !hu[1]) owner_u <= 1'b0;
            else if (!owner_u) begin
                if (want_s[1] && empty_idle && !handback_active) owner_u <= 1'b1;
                else if (bot_reset) begin handback <= 6'd63; handback_active<=1; end
            end else if (!want_s[1]) begin owner_u <= 1'b0; if (abandoned_s[1]) begin handback <= 6'd63; handback_active<=1; end end
        end
    end
    // Les FIFO vers le firmware restent en reset tant qu'il n'a pas le disque.
    wire hreset = !hr[2] || !uh[1] || busrst_s[1] || quiet_h || !owner_h;
    wire ureset = ubase || uflush || !owner_u;

    // ---- interface AHB ----------------------------------------------------
    reg        write_pending, read_pending;
    reg  [7:0] address;
    reg        seen_bus_reset, seen_bot_reset, lost;
    reg        halt_toggle;
    (* ASYNC_REG="TRUE" *) reg [2:0] halt_s = 0;
    (* ASYNC_REG="TRUE" *) reg [1:0] halted_h = 0;
    always @(posedge clk or negedge ur[2])
        if(!ur[2])halt_s<=0;
        else halt_s<={halt_s[1:0],halt_toggle};
    always @(posedge hclk or negedge hr[2])
        if(!hr[2])halted_h<=0;
        else halted_h<={halted_h[0],ep_halted};
    assign halt_request=halt_s[2]!=halt_s[1];
    reg [15:0] pushed;
    wire       tx_wr_ready;
    wire       rx_valid;
    wire [7:0] rx_byte;
    wire [9:0] rx_rd_count;
    wire [15:0] sent_h;
    wire [15:0] level_h = pushed - sent_h;
    wire       tx_byte   = write_pending && address == 8'h0c;
    wire       tx_quad   = write_pending && address == 8'h1c;
    wire       tx_write  = tx_byte || tx_quad;
    // Place calculée un cycle plus tôt : deux écritures AHB consécutives peuvent
    // la dépasser d'un mot, d'où le seuil à 3 576 pour une limite réelle de 3 584.
    reg        tx_room;
    wire       tx_commit = write_pending && address == 8'h10;
    wire       tx_push   = (tx_write && tx_room || tx_commit) && tx_wr_ready && !hreset;
    // Réception : les octets de la FIFO sont rassemblés par quatre. Une lecture
    // de mot attend au plus 15 cycles AHB que le mot soit complet ; les octets
    // annoncés par +24 sont déjà dans ce domaine, l'attente ne dépend donc pas
    // de l'horloge USB.
    reg [31:0] gather;
    reg  [2:0] gathered;
    reg  [3:0] quad_timer;
    wire       rx_one     = read_pending && address == 8'h08 && gathered != 0 && !hreset;   // jamais pendant quad_wait
    // quad_wait prolonge l'attente d'une lecture de mot dans un registre à part :
    // read_pending garde ainsi la même logique que dans les autres esclaves.
    reg        quad_wait;
    wire       quad_read  = (read_pending || quad_wait) && address == 8'h20;
    wire       quad_stall = quad_read && gathered != 3'd4 && quad_timer != 4'd15 && !hreset;
    wire       quad_done  = quad_read && !quad_stall;
    wire       rx_pop     = rx_valid && !hreset && gathered != 3'd4 && !quad_done;
    // Octets déjà rassemblés + octets en mémoire de la FIFO. L'octet de tête
    // n'est pas ajouté : le compte de la FIFO, en retard d'un cycle, le contient
    // encore quand il vient d'en sortir. La valeur ne dépasse jamais le réel.
    wire [10:0] rx_available = {8'd0, gathered} + {1'b0, rx_rd_count};
    assign hready = !read_pending && !quad_wait;

    // Reset Bulk-Only et pertes : évènements du domaine USB, passés par bascule.
    reg  bot_toggle = 1'b0, lost_toggle = 1'b0;
    (* ASYNC_REG="TRUE" *) reg [2:0] bot_s = 0, lost_s = 0;
    always @(posedge hclk) begin
        bot_s  <= {bot_s[1:0], bot_toggle};
        lost_s <= {lost_s[1:0], lost_toggle};
    end

    always @(posedge hclk or negedge hr[2]) begin
        if (!hr[2]) begin
            write_pending <= 1'b0; read_pending <= 1'b0; address <= 8'd0; hrdata <= 32'd0;
            flush_count <= 8'd0; quiet_h <= 1'b0; seen_bus_reset <= 1'b0; seen_bot_reset <= 1'b0; lost <= 1'b0;
            pushed <= 16'd0; serve <= 1'b0; watchdog <= {1'b1, {WATCHDOG_BITS{1'b1}}}; tx_room <= 1'b0;
            abandoned <= 1'b0; abandon_delay <= 3'd0;
            gather <= 32'd0; gathered <= 3'd0; quad_timer <= 4'd0; quad_wait <= 1'b0;
            halt_toggle <= 1'b0;
        end else begin
            // Tout accès à la fenêtre prouve que le firmware est vivant. À
            // l'expiration, « abandonné » précède de quatre cycles le retrait
            // de la demande : le domaine USB les voit dans cet ordre.
            // (Accès vu par ses registres : rien ici ne dépend du chemin HREADY.)
            tx_room <= level_h <= 16'd3576;
            if (write_pending || read_pending) watchdog <= {1'b0, {WATCHDOG_BITS{1'b1}}};
            else if (!watchdog[WATCHDOG_BITS]) watchdog <= watchdog - 1'b1;
            else if (serve) begin
                abandoned <= 1'b1; abandon_delay <= abandon_delay + 1'b1;
                if (abandon_delay == 3'd4) serve <= 1'b0;
            end
            write_pending <= hsel && htrans[1] && hwrite && hready;
            read_pending  <= hsel && htrans[1] && !hwrite && hready;
            quad_wait     <= quad_stall;
            quad_timer <= quad_stall ? quad_timer + 1'b1 : 4'd0;
            if (hreset || quad_done) gathered <= 3'd0;
            else if (rx_one) begin
                gather <= {8'd0, gather[31:8]};
                if (rx_pop) gather[8 * (gathered - 3'd1) +: 8] <= rx_byte;
                else gathered <= gathered - 1'b1;
            end else if (rx_pop) begin
                gather[8 * gathered[1:0] +: 8] <= rx_byte;
                gathered <= gathered + 1'b1;
            end
            if (quad_done && gathered != 3'd4) lost <= 1'b1;
            if (hready) address <= haddr[7:0];
            if (flush_count != 0 && (!flush_h || flush_ack_h[1]) &&
                (flush_count != 8'h7f || !flush_ack_h[1]))
                flush_count <= flush_count - 1'b1;
            if (flush_count == 8'd1) quiet_h <= 1'b0;
            // Hors service, le compteur suit les octets émis par le lecteur vide :
            // le niveau d'émission vaut zéro quand le firmware obtient le disque.
            if (busrst_s[1] || quiet_h) pushed <= 16'd0;
            else if (!owner_h) pushed <= sent_h;
            else if (tx_write && tx_push) pushed <= pushed + (tx_quad ? 16'd4 : 16'd1);
            if ((tx_write || tx_commit) && !tx_push) lost <= 1'b1;
            if (lost_s[2] != lost_s[1]) lost <= 1'b1;
            if (bot_s[2] != bot_s[1]) seen_bot_reset <= 1'b1;
            if (busrst_s[1]) seen_bus_reset <= 1'b1;
            if (write_pending && address == 8'h14) begin
                if (hwdata[0]) begin flush_count <= 8'hff; quiet_h <= 1'b1; end
                if (hwdata[1]) begin serve <= 1'b1; abandoned <= 1'b0; abandon_delay <= 3'd0; end
                if (hwdata[5]) serve <= 1'b0;
                if (hwdata[6]) halt_toggle <= !halt_toggle;
                if (hwdata[2] && !busrst_s[1]) seen_bus_reset <= 1'b0;
                if (hwdata[3]) seen_bot_reset <= 1'b0;
                if (hwdata[7]) lost <= 1'b0;
            end
            if ((read_pending || quad_wait) && !quad_stall) begin
                case (address)
                    8'h00: hrdata <= 32'h554d5343;
                    8'h04: hrdata <= {level_h, 5'd0, halted_h[1], serve, owner_h, lost, hs_s[1], online_s[1], quiet_h,
                                      seen_bot_reset, seen_bus_reset, level_h == 0, gathered != 0 && !hreset};
                    8'h08: hrdata <= (gathered != 0 && !hreset) ? {24'd0, gather[7:0]} : 32'h80000000;
                    8'h18: hrdata <= {sent_h, pushed};
                    8'h20: hrdata <= gather;
                    8'h24: hrdata <= hreset ? 32'd0 : {21'd0, rx_available};
                    8'h28: hrdata <= 32'd1;
                    default: hrdata <= 32'd0;
                endcase
            end
        end
    end

    // ---- émission : AHB -> USB ---------------------------------------------
    // Un élément : marqueur de validation, nombre d'octets − 1, jusqu'à quatre
    // octets. Côté USB, un octet part tous les deux cycles (30 Mo/s, au-delà du
    // débit utile d'un endpoint bulk High Speed).
    wire        tx_valid;
    wire [34:0] tx_word;
    reg  [23:0] serial;
    reg  [1:0]  serial_left;
    reg         serial_gap;
    wire        serial_busy = serial_left != 0 || serial_gap;
    wire        serial_emit = serial_left != 0 && !serial_gap;
    ddr_dcfifo #(.WIDTH(35), .DEPTH_LOG2(10)) u_tx (
        .wr_clk(hclk), .wr_rst(hreset), .wr_valid(tx_push),
        .wr_data({tx_commit, tx_quad ? 2'd3 : 2'd0, hwdata}),
        .wr_ready(tx_wr_ready), .wr_full(), .wr_lost(), .wr_count(),
        .rd_clk(clk), .rd_rst(ureset), .rd_valid(tx_valid), .rd_data(tx_word),
        .rd_ready(!ureset && !serial_busy), .rd_count());
    reg [15:0] pushed_u;
    wire tx_take = tx_valid && !ureset && !serial_busy;
    wire tx_first = tx_take && !tx_word[34];
    always @(posedge clk or negedge ur[2]) begin
        if (!ur[2]) begin serial <= 24'd0; serial_left <= 2'd0; serial_gap <= 1'b0; end
        else if (ureset) begin serial_left <= 2'd0; serial_gap <= 1'b0; end
        else begin
            serial_gap <= 1'b0;
            if (tx_first) begin serial <= tx_word[31:8]; serial_left <= tx_word[33:32]; serial_gap <= 1'b1; end
            else if (serial_emit) begin serial <= {8'd0, serial[23:8]}; serial_left <= serial_left - 1'b1; serial_gap <= 1'b1; end
        end
    end
    wire        empty_tx_dval, empty_tx_commit, empty_rx_rdy;
    wire [7:0]  empty_tx_data;
    wire        empty_reset = ubase || uflush || owner_u;
    wire        tx_idle_u = pushed_u == ep_tx_sent && ep_tx_committed == pushed_u;
    wire        tx_room_u = (pushed_u - ep_tx_sent) < 16'd3584;
    reg [15:0] committed_u;
    // Un étage commun pour octet, validité et compteur publié : aucun
    // marqueur ne dépasse ses données. Il coupe le chemin reset du
    // contrôleur -> sélection/sérialisation -> écriture BSRAM de EP1.
    // Le reset EP1 annule aussi l'octet déjà dans cet étage. tx_idle_u tient
    // compte du compteur publié, donc de cette latence supplémentaire.
    always @(posedge clk or negedge ur[2]) begin
        if (!ur[2]) begin ep_tx_dval <= 1'b0; ep_tx_data <= 8'd0; ep_tx_committed <= 16'd0; end
        else if (ubase || uflush) begin ep_tx_dval <= 1'b0; ep_tx_data <= 8'd0; ep_tx_committed <= 16'd0; end
        else begin
            ep_tx_dval <= owner_u ? tx_first || serial_emit : empty_tx_dval;
            ep_tx_data <= owner_u ? (serial_emit ? serial[7:0] : tx_word[7:0]) : empty_tx_data;
            ep_tx_committed <= committed_u;
        end
    end
    always @(posedge clk or negedge ur[2]) begin
        if (!ur[2]) begin pushed_u <= 16'd0; committed_u <= 16'd0; end
        else if (ubase || uflush) begin pushed_u <= 16'd0; committed_u <= 16'd0; end
        else if (!owner_u) begin
            if (empty_tx_dval) pushed_u <= pushed_u + 1'b1;
            if (empty_tx_commit) committed_u <= pushed_u + {15'd0, empty_tx_dval};
        end else begin
            if (tx_first || serial_emit) pushed_u <= pushed_u + 1'b1;
            if (tx_take && tx_word[34]) committed_u <= pushed_u;
        end
    end
    usb_msc_empty u_empty (
        .clk(clk), .reset(empty_reset),
        .rx_rdy(empty_rx_rdy), .rx_dval(ep_rx_dval && !owner_u), .rx_data(ep_rx_data),
        .tx_room(tx_room_u), .tx_idle(tx_idle_u),
        .tx_dval(empty_tx_dval), .tx_data(empty_tx_data), .tx_commit(empty_tx_commit),
        .idle(empty_idle));
    cdc_word #(.WIDTH(16)) u_sent (.src_clk(clk), .src_data(ep_tx_sent), .dst_clk(hclk), .dst_data(sent_h));

    // ---- réception : USB -> AHB --------------------------------------------
    // usb_rx_buf peut encore livrer deux octets après la retombée de rdy :
    // on la retire avec douze places libres.
    wire       rx_wr_ready;
    wire [9:0] rx_wr_count;
    assign ep_rx_rdy = owner_u ? !ureset && rx_wr_count <= 10'd500 : empty_rx_rdy;
    ddr_dcfifo #(.WIDTH(8), .DEPTH_LOG2(9)) u_rx (
        .wr_clk(clk), .wr_rst(ureset), .wr_valid(ep_rx_dval && owner_u), .wr_data(ep_rx_data),
        .wr_ready(rx_wr_ready), .wr_full(), .wr_lost(), .wr_count(rx_wr_count),
        .rd_clk(hclk), .rd_rst(hreset), .rd_valid(rx_valid), .rd_data(rx_byte),
        .rd_ready(rx_pop), .rd_count(rx_rd_count));
    always @(posedge clk) begin
        if (bot_reset) bot_toggle <= !bot_toggle;
        if (ep_rx_dval && owner_u && !rx_wr_ready) lost_toggle <= !lost_toggle;
    end
endmodule
`default_nettype wire
