`timescale 1ns/1ps
// Disque USB : usb_msc_port + EP1 de usb_fifo, horloges 80 MHz (AHB) et
// 60 MHz (USB) indépendantes. Le modèle d'hôte interroge EP1 IN en continu,
// perd des ACK au hasard et vérifie que les seules longueurs de paquets vues
// sont celles que le firmware a validées : jamais de paquet court au milieu
// d'un bloc en cours d'écriture, même longueur et mêmes octets en reprise.
module usb_msc_port_tb #(
    parameter real USB_HALF_NS=8.333, BUS_HALF_NS=6.25, BUS_PHASE_NS=0.0
);
    reg clk = 0, hclk = 0;
    reg usb_clock_running=1;
    always #(USB_HALF_NS) if(usb_clock_running) clk = ~clk;
    initial begin #(BUS_PHASE_NS); forever #(BUS_HALF_NS) hclk = ~hclk; end
    reg reset = 1, bus_reset = 0, bot_reset = 0;
    reg [3:0] endpoint = 0;
    reg rxact = 0, rxval = 0, rxpktval = 0, txact = 0, txpop = 0, txfin = 0;
    reg [7:0] rxdat = 0;
    wire cork, rxrdy;
    wire [11:0] length;
    wire [7:0] out;
    wire flush, tx_dval, rx_rdy, rx_dval;
    wire [7:0] tx_data, rx_data;
    wire [15:0] committed, sent;
    wire halt_request;
    reg ep_halted=0;
    integer halt_requests=0;
    always @(posedge clk)if(halt_request)halt_requests++;
    reg hsel = 0, hwrite = 0;
    reg [1:0] htrans = 0;
    reg [31:0] haddr = 0, hwdata = 0;
    wire [31:0] hrdata;
    wire hready;
    wire fifo_reset = reset | bus_reset;
    usb_fifo u_fifo (.i_clk(clk), .i_reset(fifo_reset), .i_usb_endpt(endpoint),
        .i_usb_rxact(rxact), .i_usb_rxval(rxval), .i_usb_rxpktval(rxpktval), .i_usb_rxdat(rxdat),
        .o_usb_rxrdy(rxrdy),
        .i_usb_txact(txact), .i_usb_txpop(txpop), .i_usb_txpktfin(txfin),
        .o_usb_txcork(cork), .o_usb_txlen(length), .o_usb_txdat(out),
        .i_ep1_tx_clk(clk), .i_ep1_tx_max(12'd512), .i_ep1_tx_dval(tx_dval), .i_ep1_tx_data(tx_data),
        .i_ep1_flush(flush), .i_ep1_tx_committed(committed), .o_ep1_tx_sent(sent),
        .i_ep1_rx_clk(clk), .i_ep1_rx_rdy(rx_rdy), .o_ep1_rx_dval(rx_dval), .o_ep1_rx_data(rx_data),
        .i_ep2_tx_clk(clk), .i_ep2_tx_max(12'd64), .i_ep2_tx_dval(1'b0), .i_ep2_tx_data(8'd0),
        .i_ep2_rx_clk(clk), .i_ep2_rx_rdy(1'b1));
    usb_msc_port #(.WATCHDOG_BITS(15)) u_port (.clk(clk), .reset_n(!reset), .bus_reset(bus_reset), .bot_reset(bot_reset),
        .online(1'b1), .highspeed(1'b1), .ep_flush(flush),.ep_halted(ep_halted),.halt_request(halt_request),
        .ep_tx_dval(tx_dval), .ep_tx_data(tx_data), .ep_tx_committed(committed), .ep_tx_sent(sent),
        .ep_rx_rdy(rx_rdy), .ep_rx_dval(rx_dval), .ep_rx_data(rx_data),
        .hclk(hclk), .hsel(hsel), .hwrite(hwrite), .htrans(htrans), .haddr(haddr), .hwdata(hwdata),
        .hrdata(hrdata), .hready(hready));

    function automatic [7:0] pattern(input integer n); return 8'((n * 73) ^ (n >> 8) ^ 8'h5a); endfunction
    reg [31:0] rng_h = 32'h2468ace1, rng_u = 32'h13579bdf;
    function automatic [31:0] step(input [31:0] v); return (v << 1) ^ (v[31] ? 32'h04c11db7 : 0); endfunction

    // ---- maître AHB --------------------------------------------------------
    task automatic ahb_write(input [31:0] a, input [31:0] d);
        @(negedge hclk); hsel = 1; htrans = 2; hwrite = 1; haddr = a;
        @(negedge hclk); hsel = 0; htrans = 0; hwdata = d;
        while (!hready) @(negedge hclk);
    endtask
    task automatic ahb_read(input [31:0] a, output [31:0] d);
        @(negedge hclk); hsel = 1; htrans = 2; hwrite = 0; haddr = a;
        @(negedge hclk); hsel = 0; htrans = 0;
        @(negedge hclk); while (!hready) @(negedge hclk);
        d = hrdata;
    endtask
    task automatic idle_h(input integer n); repeat (n) @(negedge hclk); endtask
    task automatic wait_status(input [31:0] mask, input [31:0] value);
        reg [31:0] s; integer guard;
        guard = 0;
        do begin ahb_read(32'h04, s); guard++; if (guard > 200000) $fatal(1, "status %h never matched %h/%h", s, mask, value); end
        while ((s & mask) != value);
    endtask

    // ---- hôte : sorties EP1 OUT ---------------------------------------------
    // Une seule transaction à la fois sur le bus.
    semaphore usb_bus = new(1);
    integer out_sent = 0, out_packets = 0;
    task automatic host_out(input integer n);
        // Le contrôleur NAK tant que rxrdy est bas : l'hôte réessaie.
        usb_bus.get();
        @(negedge clk); endpoint = 1;
        repeat (3) @(negedge clk);
        while (!rxrdy) repeat (20) @(negedge clk);
        rxact = 1; repeat (4) @(negedge clk);
        for (integer i = 0; i < n; i++) begin rxval = 1; rxdat = pattern(out_sent + i); @(negedge clk); end
        rxval = 0; repeat (2) @(negedge clk);
        rxpktval = 1; @(negedge clk); rxpktval = 0;
        rxact = 0; repeat (4) @(negedge clk);
        endpoint = 0; out_sent += n; out_packets++;
        usb_bus.put();
    endtask

    // ---- hôte : interrogations EP1 IN ---------------------------------------
    integer in_taken = 0, in_packets = 0, in_retries = 0, in_naks = 0;
    integer expect_len [$];
    reg host_in_enable = 0;
    task automatic host_in_poll;
        integer n; bit accept;
        @(negedge clk); endpoint = 1; repeat (3) @(negedge clk);
        if (cork || length == 0) begin in_naks++; endpoint = 0; repeat (2) @(negedge clk); return; end
        n = length;
        if (expect_len.size() == 0) $fatal(1, "IN packet of %0d bytes offered, none expected", n);
        if (n != expect_len[0]) $fatal(1, "IN packet length %0d, expected %0d (packet %0d)", n, expect_len[0], in_packets);
        txact = 1; repeat (4) @(negedge clk);
        for (integer i = 0; i < n; i++) begin
            if (out !== pattern(in_taken + i)) $fatal(1, "IN byte %0d of packet %0d: %h expected %h", i, in_packets, out, pattern(in_taken + i));
            txpop = 1; @(negedge clk); txpop = 0;
            if (rng_u[4]) @(negedge clk);
        end
        repeat (4) @(negedge clk);
        rng_u = step(rng_u); accept = rng_u[6:5] != 0;
        if (accept) begin txfin = 1; @(negedge clk); txfin = 0; in_taken += n; in_packets++; void'(expect_len.pop_front()); end
        else in_retries++;
        txact = 0; repeat (1 + rng_u[1:0]) @(negedge clk);
        endpoint = 0; @(negedge clk);
    endtask
    always begin
        @(negedge clk);
        if (host_in_enable) begin
            rng_u = step(rng_u); repeat (rng_u[3:0]) @(negedge clk);
            usb_bus.get(); host_in_poll(); usb_bus.put();
        end
    end

    // ---- hôte : transactions Bulk-Only dirigées (lecteur sans carte) ---------
    reg [7:0] cbw [0:30];
    reg [7:0] got [0:1023];
    integer got_len;
    reg [31:0] bot_tag = 32'h1000;
    task automatic host_send(input integer n, input bit from_cbw, input [7:0] fill);
        usb_bus.get();
        @(negedge clk); endpoint = 1; repeat (3) @(negedge clk);
        while (!rxrdy) repeat (20) @(negedge clk);
        rxact = 1; repeat (4) @(negedge clk);
        for (integer i = 0; i < n; i++) begin rxval = 1; rxdat = from_cbw ? cbw[i] : fill; @(negedge clk); end
        rxval = 0; repeat (2) @(negedge clk);
        rxpktval = 1; @(negedge clk); rxpktval = 0;
        rxact = 0; repeat (4) @(negedge clk);
        endpoint = 0; out_packets++;
        usb_bus.put();
    endtask
    // Attend un paquet IN (avec une reprise sur ACK perdu si lose) et le range dans got.
    task automatic host_receive(input bit lose);
        integer guard, n; bit pending;
        guard = 0; pending = lose; got_len = -1;
        while (got_len < 0) begin
            usb_bus.get();
            @(negedge clk); endpoint = 1; repeat (3) @(negedge clk);
            if (cork || length == 0) begin
                guard++; if (guard > 20000) $fatal(1, "no IN packet from the empty reader: state %0d index %0d owner %b handback %0d pushed_u %0d committed %0d sent %0d count %0d length %0d", u_port.u_empty.state, u_port.u_empty.index, u_port.owner_u, u_port.handback, u_port.pushed_u, committed, sent, u_port.u_empty.count, u_port.u_empty.length);
                endpoint = 0; repeat (6) @(negedge clk);
            end else begin
                n = length; txact = 1; repeat (4) @(negedge clk);
                for (integer i = 0; i < n; i++) begin got[i] = out; txpop = 1; @(negedge clk); txpop = 0; end
                repeat (4) @(negedge clk);
                if (pending) pending = 0;
                else begin txfin = 1; @(negedge clk); txfin = 0; got_len = n; in_packets++; end
                txact = 0; repeat (2) @(negedge clk); endpoint = 0; @(negedge clk);
            end
            usb_bus.put();
        end
    endtask
    task automatic command_block(input [7:0] opcode, input [7:0] byte1, input [31:0] len, input bit to_host);
        bot_tag = bot_tag + 32'h01010101;
        for (integer i = 0; i < 31; i++) cbw[i] = 0;
        cbw[0] = 8'h55; cbw[1] = 8'h53; cbw[2] = 8'h42; cbw[3] = 8'h43;
        {cbw[7], cbw[6], cbw[5], cbw[4]} = bot_tag;
        {cbw[11], cbw[10], cbw[9], cbw[8]} = len;
        cbw[12] = to_host ? 8'h80 : 8'h00; cbw[14] = 10; cbw[15] = opcode; cbw[16] = byte1;
        host_send(31, 1, 0);
    endtask
    task automatic expect_status(input [7:0] status, input [31:0] residue);
        host_receive(0);
        if (got_len != 13 || {got[3], got[2], got[1], got[0]} !== 32'h53425355 || {got[7], got[6], got[5], got[4]} !== bot_tag
            || {got[11], got[10], got[9], got[8]} !== residue || got[12] !== status)
            $fatal(1, "empty reader status: %0d bytes, status %0d residue %0d (expected %0d, %0d)", got_len, got[12],
                   {got[11], got[10], got[9], got[8]}, status, residue);
    endtask
    // Le lecteur sans carte, tel que Linux l'interroge.
    task automatic empty_reader_checks;
        reg [8*28-1:0] text;
        text = "ElectrosConsole SD      1.00";
        command_block(8'h12, 0, 36, 1); host_receive(1);
        if (got_len != 36 || got[0] !== 0 || got[1] !== 8'h80 || got[2] !== 4 || got[3] !== 2 || got[4] !== 31) $fatal(1, "empty reader INQUIRY header");
        for (integer i = 0; i < 28; i++) if (got[8 + i] !== text[(27 - i) * 8 +: 8]) $fatal(1, "empty reader INQUIRY text byte %0d", i);
        expect_status(0, 0);
        command_block(8'h12, 0, 255, 1); host_receive(0);
        if (got_len != 255 || got[8] !== "E" || got[36] !== 0 || got[254] !== 0) $fatal(1, "empty reader long INQUIRY");
        expect_status(0, 219);
        command_block(8'h12, 1, 64, 1); host_receive(0);
        if (got_len != 64 || got[0] !== 0 || got[8] !== 0) $fatal(1, "empty reader EVPD INQUIRY must be zero padding");
        expect_status(1, 64);
        command_block(8'h00, 0, 0, 0); expect_status(1, 0);
        command_block(8'h03, 0, 18, 1); host_receive(0);
        if (got_len != 18 || got[0] !== 8'h70 || got[2] !== 2 || got[7] !== 10 || got[12] !== 8'h3a || got[13] !== 0) $fatal(1, "empty reader sense");
        expect_status(0, 0);
        command_block(8'h1a, 0, 192, 1); host_receive(1);
        if (got_len != 192 || got[0] !== 0 || got[191] !== 0) $fatal(1, "empty reader MODE SENSE padding");
        expect_status(1, 192);
        command_block(8'h28, 0, 1024, 1);
        host_receive(0); if (got_len != 512) $fatal(1, "empty reader READ first packet %0d", got_len);
        host_receive(1); if (got_len != 512) $fatal(1, "empty reader READ second packet %0d", got_len);
        expect_status(1, 1024);
        command_block(8'h2a, 0, 1024, 0);
        host_send(512, 0, 8'ha5); host_send(512, 0, 8'h5a);
        expect_status(1, 1024);
        // Octets parasites puis commande : resynchronisation sur la signature.
        host_send(7, 0, 8'h55);
        command_block(8'h25, 0, 8, 1); host_receive(0);
        if (got_len != 8 || got[0] !== 0) $fatal(1, "empty reader READ CAPACITY padding");
        expect_status(1, 8);
    endtask

    // ---- firmware -----------------------------------------------------------
    integer pushed = 0, received = 0;
    task automatic fw_send(input integer n, input integer slow);
        // Un bloc : n octets puis validation. L'hôte ne doit voir que des
        // paquets de 512 octets puis le reste.
        integer left;
        left = n;
        while (left > 512) begin expect_len.push_back(512); left -= 512; end
        expect_len.push_back(left);
        // Octets seuls et mots de quatre octets mêlés.
        for (integer i = 0; i < n; i++) begin
            rng_h = step(rng_h);
            if (n - i >= 4 && rng_h[12:11] != 0) begin
                ahb_write(32'h1c, {pattern(pushed + 3), pattern(pushed + 2), pattern(pushed + 1), pattern(pushed)});
                pushed += 4; i += 3; words_sent++;
            end else begin ahb_write(32'h0c, pattern(pushed)); pushed++; end
            if (slow && rng_h[3:0] == 0) idle_h(40 + rng_h[9:4]);
        end
        ahb_write(32'h10, 0);
    endtask
    integer words_sent = 0, words_received = 0;
    task automatic fw_receive(input integer n);
        reg [31:0] d; integer guard;
        guard = 0;
        while (n > 0) begin
            rng_h = step(rng_h);
            if (n >= 4 && rng_h[14:13] != 0) begin
                // Lecture par mots : autant que le compteur en annonce.
                ahb_read(32'h24, d);
                for (integer w = d / 4; w > 0 && n >= 4; w--) begin
                    ahb_read(32'h20, d);
                    if (d !== {pattern(received + 3), pattern(received + 2), pattern(received + 1), pattern(received)})
                        $fatal(1, "OUT word at %0d: %h", received, d);
                    received += 4; n -= 4; words_received++; guard = 0;
                end
            end
            if (n == 0) break;
            ahb_read(32'h08, d);
            if (d[31]) begin guard++; if (guard > 400000) $fatal(1, "receive stalled at %0d", received); end
            else begin
                if (d[7:0] !== pattern(received)) $fatal(1, "OUT byte %0d: %h expected %h", received, d[7:0], pattern(received));
                received++; n--; guard = 0;
            end
            rng_h = step(rng_h);
            if (rng_h[5:0] == 0) idle_h(200);
        end
    endtask

    reg [31:0] v;
    always @(negedge hclk)
        if (!reset && u_port.quiet_h !== (u_port.flush_count != 0))
            $fatal(1, "flush status differs from counter: %h", u_port.flush_count);
    initial begin
        repeat (10) @(negedge clk); reset = 0; repeat (40) @(negedge hclk);
        ahb_read(32'h00, v); if (v !== 32'h554d5343) $fatal(1, "identity %h", v);
        ahb_read(32'h04, v); if ((v & 32'hffff03ff) !== 32'h00000062) $fatal(1, "initial status %h", v);
        ahb_read(32'h08, v); if (v !== 32'h80000000) $fatal(1, "empty receive %h", v);

        // 0. Aucun firmware ne sert le disque : le matériel répond en lecteur
        //    sans carte. Un octet écrit par le firmware est alors refusé.
        empty_reader_checks();
        ahb_write(32'h0c, 8'h11);
        ahb_read(32'h04, v); if (!v[7]) $fatal(1, "write without the disk must be refused: %h", v);
        ahb_write(32'h14, 32'h80);
        // Demande du disque au milieu d'une commande de l'hôte : accordé
        // seulement après son état.
        command_block(8'h1a, 0, 192, 1);
        ahb_write(32'h14, 32'h2);
        repeat (20) begin ahb_read(32'h04, v); if (v[8]) $fatal(1, "disk granted in the middle of a host command"); idle_h(50); end
        if (!v[9]) $fatal(1, "service request not recorded");
        host_receive(0); if (got_len != 192) $fatal(1, "MODE SENSE during hand-over");
        expect_status(1, 192);
        wait_status(32'h100, 32'h100);
        ahb_read(32'h04, v); if ((v & 32'hffff03ff) !== 32'h00000362) $fatal(1, "status once the firmware owns the disk: %h", v);
        ahb_read(32'h18, v); if (v[15:0] !== v[31:16]) $fatal(1, "counters not aligned at hand-over: %h", v);
        pushed = v[15:0]; in_taken = pushed; in_packets = 0; out_packets = 0;

        // 1. Réception : une commande de 31 octets, puis 16 paquets de 512
        //    envoyés plus vite que le firmware ne lit (contre-pression rxrdy).
        fork
            begin host_out(31); for (integer p = 0; p < 16; p++) host_out(512); host_out(7); end
            fw_receive(31 + 16 * 512 + 7);
        join
        ahb_read(32'h08, v); if (v !== 32'h80000000) $fatal(1, "receive not empty after test: %h", v);
        $display("OUT %0d bytes in %0d packets", received, out_packets);

        // 2. Émission : rien n'est visible avant validation.
        host_in_enable = 1;
        for (integer i = 0; i < 100; i++) begin ahb_write(32'h0c, pattern(pushed)); pushed++; end
        idle_h(4000);
        if (in_packets != 0) $fatal(1, "uncommitted bytes reached the host");
        expect_len.push_back(100);
        ahb_write(32'h10, 0);
        wait_status(32'h00000002, 32'h00000002);
        if (in_packets != 1) $fatal(1, "committed short packet not delivered");

        // 3. Blocs écrits lentement pendant que l'hôte interroge : 512, 1024,
        //    2048 + 13 octets, puis un état de 13 octets seul.
        fw_send(512, 1);  wait_status(32'h2, 32'h2);
        fw_send(1024, 1); wait_status(32'h2, 32'h2);
        fw_send(2048 + 13, 1); wait_status(32'h2, 32'h2);
        fw_send(13, 0); wait_status(32'h2, 32'h2);
        // 4. Débit maximal : 64 secteurs par blocs de 512 validés un à un,
        //    en respectant le niveau d'émission.
        for (integer b = 0; b < 64; b++) begin
            do ahb_read(32'h04, v); while (v[31:16] > 16'd3064);
            fw_send(512, 0);
        end
        do ahb_read(32'h04, v); while (v[31:16] > 16'd3064);
        expect_len.push_back(13);
        for (integer i = 0; i < 13; i++) begin ahb_write(32'h0c, pattern(pushed)); pushed++; end
        ahb_write(32'h10, 0);
        wait_status(32'h2, 32'h2);
        if (expect_len.size() != 0 || in_taken != pushed) begin ahb_read(32'h18, v); $fatal(1, "IN accounting: %0d taken, %0d pushed, counters %h, committed %0d sent %0d pushed_u %0d", in_taken, pushed, v, committed, sent, u_port.pushed_u); end
        ahb_read(32'h04, v); if (v[7]) $fatal(1, "loss flag set in normal operation");
        ahb_read(32'h18, v); if (v !== {16'(in_taken), 16'(pushed)}) $fatal(1, "counters %h", v);
        $display("IN %0d bytes in %0d packets, %0d lost ACKs replayed, %0d empty polls", in_taken, in_packets, in_retries, in_naks);

        // 5. Purge : un bloc validé mais non lu disparaît, le suivant passe.
        host_in_enable = 0; repeat (200) @(negedge clk);
        for (integer i = 0; i < 50; i++) ahb_write(32'h0c, 8'hee);
        ahb_write(32'h10, 0);
        host_out(5);                       // octets reçus à jeter aussi
        idle_h(100);
        ahb_write(32'h14, 32'h1);
        wait_status(32'h10, 32'h0);
        ahb_read(32'h04, v); if ((v & 32'hffff0093) !== 32'h00000002) $fatal(1, "status after flush %h", v);
        ahb_read(32'h18, v); if (v !== 0) $fatal(1, "counters after flush %h", v);
        pushed = 0; in_taken = 0; out_sent = 0; received = 0;
        host_in_enable = 1; idle_h(3000);
        if (in_packets != 75) $fatal(1, "flushed packet reached the host");
        fw_send(20, 0); wait_status(32'h2, 32'h2);
        fork host_out(64); fw_receive(64); join

        // 6. Reset du bus pendant un bloc en attente : indicateur, puis reprise.
        host_in_enable = 0; repeat (200) @(negedge clk);
        for (integer i = 0; i < 30; i++) ahb_write(32'h0c, 8'hdd);
        ahb_write(32'h10, 0); idle_h(50);
        @(negedge clk); bus_reset = 1; repeat (600) @(negedge clk); bus_reset = 0;
        idle_h(20);
        ahb_read(32'h04, v); if ((v & 32'hffff0097) !== 32'h00000006) $fatal(1, "status after bus reset %h", v);
        ahb_write(32'h14, 32'h4);
        ahb_read(32'h04, v); if (v[2]) $fatal(1, "bus reset flag not cleared");
        pushed = 0; in_taken = 0; out_sent = 0; received = 0;
        host_in_enable = 1; idle_h(3000);
        if (in_packets != 76) $fatal(1, "packet survived bus reset");
        fw_send(600, 1); wait_status(32'h2, 32'h2);
        fork host_out(200); fw_receive(200); join

        // 7. Reset Bulk-Only signalé ; saturation signalée et sans débordement.
        @(negedge clk); bot_reset = 1; @(negedge clk); bot_reset = 0;
        wait_status(32'h8, 32'h8);
        ahb_write(32'h14, 32'h8);
        ahb_read(32'h04, v); if (v[3]) $fatal(1, "Bulk-Only reset flag not cleared");
        host_in_enable = 0; repeat (200) @(negedge clk);
        for (integer i = 0; i < 3577; i++) begin ahb_write(32'h0c, pattern(pushed)); pushed++; end
        ahb_read(32'h04, v); if (v[7] || v[31:16] != 16'd3577) $fatal(1, "status at limit %h", v);
        ahb_write(32'h0c, 8'h00);
        ahb_read(32'h04, v); if (!v[7] || v[31:16] != 16'd3577) $fatal(1, "overflow not reported: %h", v);
        ahb_write(32'h14, 32'h80);
        ahb_write(32'h1c, 32'h0);
        ahb_read(32'h04, v); if (!v[7] || v[31:16] != 16'd3577) $fatal(1, "word overflow not reported: %h", v);
        ahb_write(32'h14, 32'h80);
        // Mot lu sans qu'il soit annoncé : la lecture rend la main et le signale.
        ahb_read(32'h24, v); if (v !== 0) $fatal(1, "receive count not zero: %h", v);
        ahb_read(32'h20, v);
        ahb_read(32'h04, v); if (!v[7]) $fatal(1, "word read without data not reported: %h", v);
        ahb_write(32'h14, 32'h80);
        for (integer i = 0; i < 6; i++) expect_len.push_back(512);
        expect_len.push_back(505);
        ahb_write(32'h10, 0);
        host_in_enable = 1; wait_status(32'h82, 32'h02);
        if (in_taken != pushed) $fatal(1, "bytes at the limit: %0d taken, %0d pushed", in_taken, pushed);
        // 8. Le firmware rend le disque : le matériel répond de nouveau.
        host_in_enable = 0; repeat (200) @(negedge clk);
        ahb_write(32'h14, 32'h20);
        wait_status(32'h300, 32'h000);
        command_block(8'h00, 0, 0, 0); expect_status(1, 0);
        command_block(8'h12, 0, 36, 1); host_receive(0); if (got_len != 36) $fatal(1, "INQUIRY after release");
        expect_status(0, 0);
        // 9. Il le reprend, sert l'hôte, puis cesse tout accès (processeur
        //    arrêté) : le chien de garde rend le disque au matériel.
        ahb_write(32'h14, 32'h2); wait_status(32'h100, 32'h100);
        ahb_read(32'h18, v); pushed = v[15:0]; in_taken = pushed;
        fork host_out(64); fw_receive(64); join
        host_in_enable = 1; fw_send(700, 0); wait_status(32'h2, 32'h2);
        host_in_enable = 0; repeat (200) @(negedge clk);
        repeat (40000) @(negedge hclk);
        ahb_read(32'h04, v); if (v[9:8] !== 2'b00) $fatal(1, "watchdog did not release the disk: %h", v);
        command_block(8'h00, 0, 0, 0); expect_status(1, 0);
        command_block(8'h03, 0, 18, 1); host_receive(0); if (got_len != 18 || got[12] !== 8'h3a) $fatal(1, "sense after watchdog");
        expect_status(0, 0);
        // Une purge demandée avec l'horloge USB arrêtée reste en attente
        // jusqu'à son acquittement réel. L'AHB reste consultable. Un ancien
        // paquet validé avant l'arrêt doit disparaître à la reprise.
        ahb_write(32'h14, 32'h2); wait_status(32'h100, 32'h100);
        for(integer i=0;i<20;i++) ahb_write(32'h0c,8'hee);
        ahb_write(32'h10,0); idle_h(100);
        @(negedge clk); usb_clock_running=0;
        ahb_write(32'h14,1); idle_h(600);
        ahb_read(32'h00,v); if(v!==32'h554d5343)$fatal(1,"AHB blocked with USB clock stopped");
        ahb_read(32'h04,v); if(!v[4])$fatal(1,"flush completed without USB clock acknowledgement");
        ahb_write(32'h14,1); idle_h(300); // une nouvelle purge prolonge la précédente
        usb_clock_running=1;
        wait_status(32'h10,0);
        ahb_read(32'h18,v); if(v!==0)$fatal(1,"stale counters after stopped-clock flush: %h",v);
        pushed=0;in_taken=0;out_sent=0;received=0;
        host_in_enable=1;fw_send(37,0);wait_status(32'h82,2);
        fork host_out(64);fw_receive(64);join
        $display("STOPPED CLOCK FLUSH PASS USB_HALF=%0.3f BUS_HALF=%0.3f PHASE=%0.3f",USB_HALF_NS,BUS_HALF_NS,BUS_PHASE_NS);
        // Demande de verrouillage pendant l'arrêt du domaine USB : le toggle
        // doit être livré exactement une fois lorsque cette horloge reprend.
        @(negedge clk);usb_clock_running=0;
        ahb_write(32'h14,32'h40);idle_h(100);
        if(halt_requests!=0)$fatal(1,"HALT received with USB clock stopped");
        usb_clock_running=1;repeat(20)@(negedge clk);
        if(halt_requests!=1)$fatal(1,"HALT toggle lost or repeated: %0d",halt_requests);
        ep_halted=1;wait_status(32'h400,32'h400);
        ahb_write(32'h14,32'h1);wait_status(32'h10,0);
        wait_status(32'h400,32'h400); // une purge locale ne retire pas HALT
        ep_halted=0;wait_status(32'h400,0);
        $display("STOPPED CLOCK HALT PASS");
        // Reset exactement entre la sortie du registre d'émission et son
        // écriture dans la FIFO EP1 : l'octet en vol doit être annulé aussi.
        host_in_enable=0; repeat(200) @(negedge clk);
        ahb_write(32'h0c,8'hed);
        do @(negedge clk); while(!tx_dval);
        bus_reset=1;
        repeat(600) @(negedge clk); bus_reset=0;
        idle_h(20); ahb_write(32'h14,4);
        ahb_read(32'h18,v); if(v!==0)$fatal(1,"pending TX survived reset: %h",v);
        pushed=0;in_taken=0;out_sent=0;received=0;
        host_in_enable=1;fw_send(513,0);wait_status(32'h82,2);
        fork host_out(64);fw_receive(64);join
        $display("PENDING TX RESET PASS");
        // Le compteur publié est modulo 65536 : franchir son retour à zéro
        // avec des paquets en attente et des ACK perdus, sans purge entre eux.
        for(integer b=0;b<132;b++) begin
            do ahb_read(32'h04,v); while(v[31:16]>16'd3064);
            fw_send(512,0);
        end
        wait_status(32'h82,2);
        ahb_read(32'h18,v);
        if(in_taken!=pushed || v!=={16'(in_taken),16'(pushed)} || expect_len.size()!=0)
            $fatal(1,"TX wrap accounting: taken %0d pushed %0d counters %h",in_taken,pushed,v);
        $display("TX COUNTER WRAP PASS bytes=%0d",in_taken);
        if (words_sent < 1000 || words_received < 500) $fatal(1, "word accesses not exercised: %0d sent, %0d received", words_sent, words_received);
        $display("PASS usb_msc_port: %0d IN packets, %0d OUT packets, %0d words sent, %0d words received", in_packets, out_packets, words_sent, words_received);
        $finish;
    end
    initial begin #400000000; $fatal(1, "timeout"); end
endmodule
