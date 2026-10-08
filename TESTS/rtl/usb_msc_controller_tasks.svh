    // Séquence du disque USB contre le contrôleur officiel : énumération du
    // périphérique composite, requêtes de classe, transferts bulk EP1 dans
    // les deux sens avec ACK perdus, port série EP2 utilisé en parallèle.
    function automatic [7:0] msc_pattern(input integer n);
        msc_pattern = 8'((n * 73) ^ (n >> 8) ^ 8'h5a);
    endfunction
    task automatic ahb_write(input [31:0] a, input [31:0] d);
        begin
            @(negedge hclk); hsel = 1; htrans = 2; hwrite = 1; haddr = a;
            @(negedge hclk); hsel = 0; htrans = 0; hwdata = d;
            while (!hready) @(negedge hclk);
        end
    endtask
    task automatic ahb_read(input [31:0] a, output [31:0] d);
        begin
            @(negedge hclk); hsel = 1; htrans = 2; hwrite = 0; haddr = a;
            @(negedge hclk); hsel = 0; htrans = 0;
            @(negedge hclk); while (!hready) @(negedge hclk);
            d = hrdata;
        end
    endtask
    task automatic wait_status(input [31:0] mask, input [31:0] value);
        reg [31:0] s; integer guard;
        begin
            guard = 0; s = ~value;
            while ((s & mask) != value) begin
                ahb_read(32'h04, s); guard = guard + 1;
                if (guard > 100000) $fatal(1, "port status %h never matched %h/%h", s, mask, value);
            end
        end
    endtask
    integer fw_pushed = 0, fw_received = 0;
    task automatic fw_push(input integer n, input integer pause);
        begin
            // Mots de quatre octets, puis le reste octet par octet.
            for (integer i = 0; i < n; i++) begin
                if (n - i >= 4 && (i % 20) != 8) begin
                    ahb_write(32'h1c, {msc_pattern(fw_pushed + 3), msc_pattern(fw_pushed + 2), msc_pattern(fw_pushed + 1), msc_pattern(fw_pushed)});
                    fw_pushed += 4; i += 3;
                end else begin ahb_write(32'h0c, msc_pattern(fw_pushed)); fw_pushed++; end
                if (pause != 0 && (i % 37) >= 33) repeat (pause) @(negedge hclk);
            end
        end
    endtask
    task automatic fw_read(input integer n);
        reg [31:0] d; integer guard, left;
        begin
            guard = 0; left = n;
            while (left > 0) begin
                if (left >= 4) begin
                    ahb_read(32'h24, d);
                    for (integer w = d / 4; w > 0 && left >= 4; w--) begin
                        ahb_read(32'h20, d);
                        if (d !== {msc_pattern(fw_received + 3), msc_pattern(fw_received + 2), msc_pattern(fw_received + 1), msc_pattern(fw_received)})
                            $fatal(1, "EP1 OUT word at %0d: %08x", fw_received, d);
                        fw_received += 4; left -= 4; guard = 0;
                    end
                end
                if (left > 0) begin
                ahb_read(32'h08, d);
                if (d[31]) begin guard++; if (guard > 100000) $fatal(1, "firmware receive stalled at %0d", fw_received); end
                else begin
                    if (d[7:0] !== msc_pattern(fw_received)) $fatal(1, "EP1 OUT byte %0d: %02x expected %02x", fw_received, d[7:0], msc_pattern(fw_received));
                    fw_received++; left--; guard = 0;
                end
                end
            end
        end
    endtask

    task automatic setup_packet(input [7:0] bm, input [7:0] request, input [15:0] value,
                                input [15:0] index, input [15:0] length);
        reg [15:0] crc; integer old;
        begin
            token(8'h2d, host_address, 0); gap(8);
            packet[0] = 8'hc3; packet[1] = bm; packet[2] = request;
            packet[3] = value[7:0]; packet[4] = value[15:8];
            packet[5] = index[7:0]; packet[6] = index[15:8];
            packet[7] = length[7:0]; packet[8] = length[15:8];
            crc = 16'hffff;
            for (integer i = 1; i <= 8; i++) crc = crc16_byte(crc, packet[i]);
            crc = ~crc; packet[9] = crc[7:0]; packet[10] = crc[15:8];
            old = responses; receive_packet(11); await_response(old);
            if (response_len != 1 || response[0] != 8'hd2) $fatal(1, "SETUP %02x/%02x not ACKed", bm, request);
            gap(100);
            if(bm==8'h82 && request==0)$display("GUARD STATUS count=%0d setup=%016x query=%b halt=%b",u_guard.setup_count,u_guard.setup_bytes,u_guard.status_query,msc_halted);
        end
    endtask
    byte ctl_data[0:1023];
    byte ctl_copy[0:1023];
    integer ctl_len = 0, ctl_replays = 0;
    task automatic control_read(input [7:0] bm, input [7:0] request, input [15:0] value,
                                input [15:0] index, input [15:0] length, input bit lose_first_ack);
        reg [15:0] crc; integer old, n, naks, copy_len; byte pid; bit done, lose;
        begin
            setup_packet(bm, request, value, index, length);
            pid = 8'h4b; ctl_len = 0; done = 0; lose = lose_first_ack; naks = 0;
            while (!done) begin
                old = responses; token(8'h69, host_address, 0); await_response(old);
                if (response_len == 1 && response[0] == 8'h5a) begin
                    naks++; if (naks > 50) $fatal(1, "control read %02x/%02x: endless NAK", bm, request);
                    gap(20);
                end else begin
                    if (response_len < 3 || response[0] != pid)
                        $fatal(1, "control read %02x/%02x: unexpected response %02x len %0d", bm, request, response[0], response_len);
                    crc = 16'hffff;
                    for (integer i = 1; i < response_len; i++) crc = crc16_byte(crc, response[i]);
                    if (crc !== 16'hb001) $fatal(1, "control read: invalid DATA CRC");
                    if (lose) begin
                        // ACK perdu : la reprise doit être identique.
                        lose = 0; copy_len = response_len;
                        for (integer i = 0; i < response_len; i++) ctl_copy[i] = response[i];
                        gap(120);
                        old = responses; token(8'h69, host_address, 0); await_response(old);
                        if (response_len != copy_len) $fatal(1, "control retry changed length %0d -> %0d", copy_len, response_len);
                        for (integer i = 0; i < response_len; i++)
                            if (response[i] !== ctl_copy[i]) $fatal(1, "control retry changed byte %0d", i);
                        ctl_replays++;
                    end
                    n = response_len - 3;
                    for (integer i = 0; i < n; i++) begin ctl_data[ctl_len] = response[1 + i]; ctl_len++; end
                    ack(); pid = pid ^ 8'h88;
                    if (n < 64 || ctl_len >= length) done = 1;
                end
            end
            gap(15);
            token(8'he1, host_address, 0); gap(8);
            packet[0] = 8'h4b; packet[1] = 0; packet[2] = 0;
            old = responses; receive_packet(3); await_response(old);
            if (response_len != 1 || response[0] != 8'hd2) $fatal(1, "control read %02x/%02x: status not ACKed", bm, request);
            gap(100);
        end
    endtask
    task automatic control_nodata(input [7:0] bm, input [7:0] request, input [15:0] value, input [15:0] index);
        integer old;
        begin
            setup_packet(bm, request, value, index, 0);
            old = responses; token(8'h69, host_address, 0); await_response(old);
            if (response_len != 3 || response[0] != 8'h4b) $fatal(1, "control %02x/%02x: status is not a DATA1 ZLP", bm, request);
            ack(); gap(100);
        end
    endtask
    task automatic print_control(input [8*24-1:0] name);
        begin
            $write("%0s", name);
            for (integer i = 0; i < ctl_len; i++) $write(" %02x", ctl_data[i]);
            $display("");
        end
    endtask

    byte msc_out_pid = 8'hc3, msc_in_pid = 8'hc3;
    integer msc_out_count = 0, msc_in_count = 0, msc_out_naks = 0, msc_out_nyets = 0;
    integer msc_in_packets = 0, msc_in_naks = 0, msc_in_replays = 0, msc_in_pending = -1;
    byte payload[0:1023];
    bit expect_out_stall=0;
    // Envoie payload[0..n-1] sur EP1 OUT ; accepted = 0 si le contrôleur a répondu NAK.
    task automatic msc_send(input integer n, output bit accepted);
        reg [15:0] crc; integer old;
        begin
            token(8'he1, host_address, 1); gap(12);
            packet[0] = msc_out_pid;
            crc = 16'hffff;
            for (integer i = 0; i < n; i++) begin
                packet[1 + i] = payload[i];
                crc = crc16_byte(crc, packet[1 + i]);
            end
            crc = ~crc; packet[n + 1] = crc[7:0]; packet[n + 2] = crc[15:8];
            old = responses; receive_packet(n + 3); await_response(old);
            if(expect_out_stall)begin
                if(response_len!=1 || response[0]!=8'h1e)$fatal(1,"EP1 OUT missing STALL: %02x",response[0]);
                accepted=0;gap(20);
            end else begin
            if (response_len != 1 || (response[0] != 8'hd2 && response[0] != 8'h5a && response[0] != 8'h96))
                $fatal(1, "EP1 OUT: unexpected handshake %02x", response[0]);
            accepted = response[0] != 8'h5a;
            if (response[0] == 8'h96) msc_out_nyets++;
            if (accepted) msc_out_pid = msc_out_pid ^ 8'h88;
            else msc_out_naks++;
            gap(20);
            end
        end
    endtask
    task automatic msc_out(input integer n, output bit accepted);
        begin
            for (integer i = 0; i < n; i++) payload[i] = msc_pattern(msc_out_count + i);
            msc_send(n, accepted);
            if (accepted) msc_out_count += n;
        end
    endtask
    // Commande Bulk-Only adressée au lecteur sans carte, puis lecture de ses paquets.
    reg [31:0] bot_tag = 32'h20260000;
    bit check_pattern = 1;
    byte raw[0:1023];
    task automatic empty_command(input [7:0] opcode, input [7:0] byte1, input [31:0] length, input bit to_host);
        bit accepted; integer attempts;
        begin
            bot_tag = bot_tag + 32'h01020304;
            for (integer i = 0; i < 31; i++) payload[i] = 0;
            payload[0] = 8'h55; payload[1] = 8'h53; payload[2] = 8'h42; payload[3] = 8'h43;
            payload[4] = bot_tag[7:0]; payload[5] = bot_tag[15:8]; payload[6] = bot_tag[23:16]; payload[7] = bot_tag[31:24];
            payload[8] = length[7:0]; payload[9] = length[15:8]; payload[10] = length[23:16]; payload[11] = length[31:24];
            payload[12] = to_host ? 8'h80 : 8'h00; payload[14] = 10; payload[15] = opcode; payload[16] = byte1;
            accepted = 0; attempts = 0;
            while (!accepted) begin
                msc_send(31, accepted); attempts++;
                if (attempts > 20) $fatal(1, "empty reader never accepted a command");
            end
        end
    endtask
    task automatic empty_packet(input bit lose_ack, input integer expected_len);
        integer n, polls;
        begin
            n = -1; polls = 0;
            while (n < 0) begin
                msc_in(1, n); polls++;
                if (polls > 400) $fatal(1, "empty reader sent nothing (expected %0d bytes)", expected_len);
            end
            if (n != expected_len) $fatal(1, "empty reader packet of %0d bytes, expected %0d", n, expected_len);
            empty_packets_seen++;
        end
    endtask
    integer empty_packets_seen = 0;
    task automatic empty_status(input [7:0] status, input [31:0] residue);
        begin
            empty_packet(0, 13);
            if (raw[0] != 8'h55 || raw[1] != 8'h53 || raw[2] != 8'h42 || raw[3] != 8'h53 ||
                {raw[7], raw[6], raw[5], raw[4]} !== bot_tag || {raw[11], raw[10], raw[9], raw[8]} !== residue || raw[12] !== status)
                $fatal(1, "empty reader status %0d residue %0d, expected %0d and %0d", raw[12], {raw[11], raw[10], raw[9], raw[8]}, status, residue);
        end
    endtask
    // Une interrogation EP1 IN. n = -1 : NAK. Sans ACK, l'hôte considère le
    // paquet comme non reçu : la reprise doit être le même paquet.
    task automatic msc_in(input bit send_ack, output integer n);
        reg [15:0] crc; integer old;
        begin
            old = responses; token(8'h69, host_address, 1); await_response(old);
            if (response_len == 1 && response[0] == 8'h5a) begin
                if (msc_in_pending >= 0) $fatal(1, "EP1 IN: NAK instead of replaying %0d bytes", msc_in_pending);
                n = -1; msc_in_naks++; gap(20);
            end else begin
                if (response_len < 3 || response[0] != msc_in_pid)
                    $fatal(1, "EP1 IN: unexpected response %02x len %0d (expected PID %02x)", response[0], response_len, msc_in_pid);
                crc = 16'hffff;
                for (integer i = 1; i < response_len; i++) crc = crc16_byte(crc, response[i]);
                if (crc !== 16'hb001) $fatal(1, "EP1 IN: invalid DATA CRC");
                n = response_len - 3;
                if (msc_in_pending >= 0) begin
                    if (n != msc_in_pending) $fatal(1, "EP1 IN: replay changed length %0d -> %0d", msc_in_pending, n);
                    msc_in_replays++;
                end
                for (integer i = 0; i < n; i++) begin
                    raw[i] = response[1 + i];
                    if (check_pattern && response[1 + i] !== msc_pattern(msc_in_count + i))
                        $fatal(1, "EP1 IN byte %0d: %02x expected %02x", msc_in_count + i, response[1 + i], msc_pattern(msc_in_count + i));
                end
                if (send_ack) begin
                    ack(); msc_in_pid = msc_in_pid ^ 8'h88; msc_in_packets++; msc_in_pending = -1;
                    if (check_pattern) msc_in_count += n;
                end else begin
                    msc_in_pending = n; gap(120);
                end
            end
        end
    endtask
    task automatic expect_in(input bit send_ack, input integer expected_len);
        integer n;
        begin
            msc_in(send_ack, n);
            if (n != expected_len) $fatal(1, "EP1 IN: %0d bytes, expected %0d", n, expected_len);
        end
    endtask

    reg [31:0] port_value;
    bit out_accepted;
    integer in_len, slow_lengths [0:7], slow_count, out_done;
    bit slow_done;
    initial begin
        gap(10); reset = 0;
        wait(usb_busreset === 0);
        gap(1000);
        negotiate_hs();
        control_write(5, 7); host_address = 7;
        #2000000; gap(2);
        control_write(9, 1);
        if (!usb_online) $fatal(1, "controller not configured");
        ahb_read(32'h00, port_value); if (port_value !== 32'h554d5343) $fatal(1, "port identity %h", port_value);
        ahb_read(32'h04, port_value);
        if (!port_value[5] || !port_value[6]) $fatal(1, "port does not report configured High Speed: %h", port_value);
        ahb_write(32'h14, 32'h0c);

        // Descripteurs du périphérique composite.
        control_read(8'h80, 6, 16'h0100, 0, 18, 0);  print_control("DEVICE_DESCRIPTOR");
        control_read(8'h80, 6, 16'h0600, 0, 10, 0);  print_control("QUALIFIER_DESCRIPTOR");
        control_read(8'h80, 6, 16'h0200, 0, 9, 0);   print_control("CONFIG_HEADER");
        control_read(8'h80, 6, 16'h0200, 0, 255, 0); print_control("CONFIG_DESCRIPTOR");

        // Requêtes de classe : Get Max LUN (interface 2), avec ACK perdu, et
        // GET_LINE_CODING du port série resté intact avant et après.
        control_read(8'ha1, 8'h21, 0, 0, 7, 0);      print_control("LINE_CODING");
        if (ctl_len != 7 || ctl_data[0] != 8'h00 || ctl_data[1] != 8'hc2 || ctl_data[2] != 8'h01 || ctl_data[6] != 8'h08)
            $fatal(1, "GET_LINE_CODING changed");
        control_read(8'ha1, 8'hfe, 0, 2, 1, 0);      print_control("MAX_LUN");
        if (ctl_len != 1 || ctl_data[0] != 0) $fatal(1, "Get Max LUN: %0d bytes", ctl_len);
        control_read(8'ha1, 8'hfe, 0, 2, 1, 1);
        if (ctl_len != 1 || ctl_data[0] != 0 || ctl_replays != 1) $fatal(1, "Get Max LUN after lost ACK");
        control_read(8'ha1, 8'h21, 0, 0, 7, 1);
        if (ctl_len != 7 || ctl_data[1] != 8'hc2 || ctl_replays != 2) $fatal(1, "GET_LINE_CODING after Get Max LUN");
        control_nodata(8'h21, 8'hff, 0, 2);
        wait_status(32'h8, 32'h8);
        ahb_write(32'h14, 32'h8);
        $display("Class requests completed");

        // Une tentative CRC-invalide n'est pas un CBW reçu : ni ACK ni HALT.
        begin : bad_crc_ignored
            integer old;reg [15:0] crc;
            token(8'he1,host_address,1);gap(12);packet[0]=msc_out_pid;
            crc=16'hffff;
            for(integer i=1;i<=31;i++)begin packet[i]=0;crc=crc16_byte(crc,packet[i]);end
            crc=(~crc)^16'h0001;packet[32]=crc[7:0];packet[33]=crc[15:8];
            old=responses;receive_packet(34);gap(400);
            if(responses!=old || msc_halted)$fatal(1,"CRC-invalid CBW was accepted or halted BOT");
        end

        // Aucun firmware ne sert le disque : le matériel répond en lecteur sans
        // carte, comme Linux l'interroge au branchement. ACK perdu compris.
        check_pattern = 0;
        empty_command(8'h12, 0, 36, 1);
        // ACK OUT perdu : l'hôte répète le même DATA PID et le même CBW.
        // Le contrôleur doit ACKer sans le livrer une deuxième fois au garde.
        begin : repeated_cbw
            bit accepted;
            msc_out_pid=msc_out_pid^8'h88;
            msc_send(31,accepted);
            if(!accepted || msc_halted)$fatal(1,"duplicate OUT CBW changed BOT state");
        end
        msc_in_pending = -1;
        begin : lost_ack_on_inquiry
            integer n, polls;
            n = -1; polls = 0;
            while (n < 0 && polls < 400) begin msc_in(0, n); polls++; end
            if (n != 36) $fatal(1, "empty reader INQUIRY: %0d bytes", n);
        end
        empty_packet(0, 36);
        if (raw[0] != 0 || raw[1] != 8'h80 || raw[4] != 31 || raw[8] != "E" || raw[16] != "C" || raw[35] != "0") $fatal(1, "empty reader INQUIRY data");
        empty_status(0, 0);
        empty_command(8'h00, 0, 0, 0);    empty_status(1, 0);
        empty_command(8'h03, 0, 18, 1);   empty_packet(0, 18);
        if (raw[0] != 8'h70 || raw[2] != 2 || raw[12] != 8'h3a) $fatal(1, "empty reader sense data");
        empty_status(0, 0);
        empty_command(8'h1a, 0, 192, 1);  empty_packet(0, 192); empty_status(1, 192);
        empty_command(8'h28, 0, 1024, 1); empty_packet(0, 512); empty_packet(0, 512); empty_status(1, 1024);
        empty_command(8'h2a, 0, 512, 0);
        for (integer i = 0; i < 512; i++) payload[i] = 8'(i);
        begin : discarded_write
            bit accepted; integer attempts;
            accepted = 0; attempts = 0;
            while (!accepted && attempts < 20) begin msc_send(512, accepted); attempts++; end
            if (!accepted) $fatal(1, "empty reader refused write data");
        end
        empty_status(1, 512);
        append_byte(); gap(40); drain();              // le port série vit à côté
        ahb_read(32'h04, port_value); if (port_value[9:8] != 0) $fatal(1, "disk owned without request: %h", port_value);
        $display("Empty reader served by hardware: %0d packets", empty_packets_seen);
        // CBW mauvais, court, long, nul puis défaut signalé par le firmware.
        // Le vrai contrôleur doit produire STALL, EP0/CDC restent utilisables.
        for(integer fault=0;fault<6;fault++)begin : malformed
            integer old,n;
            bit accepted;
            for(integer i=0;i<32;i++)payload[i]=0;
            payload[0]=8'h55;payload[1]=8'h53;payload[2]=8'h42;payload[3]=8'h43;payload[14]=6;
            n=fault==1 ? 30 : fault==2 ? 32 : fault==3 ? 0 : 31;
            if(fault==0)payload[0]=0;
            if(fault==5)begin
                empty_command(8'h2a,0,512,0);
                for(integer i=0;i<16;i++)payload[i]=0;
                msc_send(16,accepted);
            end else if(fault==4)ahb_write(32'h14,32'h40);
            else msc_send(n,accepted);
            wait_status(32'h400,32'h400);
            old=responses;token(8'h69,host_address,1);await_response(old);
            if(response_len!=1 || response[0]!=8'h1e)$fatal(1,"bad CBW %0d: IN did not STALL (%02x)",fault,response[0]);
            control_read(8'h82,0,0,16'h81,2,1);
            if(ctl_len!=2 || ctl_data[0]!=1 || ctl_data[1]!=0)$fatal(1,"GET_STATUS halted IN: %02x",ctl_data[0]);
            control_read(8'h82,0,0,16'h01,2,0);
            if(ctl_len!=2 || ctl_data[0]!=1 || ctl_data[1]!=0)$fatal(1,"GET_STATUS halted OUT: %02x",ctl_data[0]);
            control_nodata(8'h02,1,0,16'h81); // CLEAR_FEATURE seul ne sort pas du verrou BOT
            old=responses;token(8'h69,host_address,1);await_response(old);
            if(response_len!=1 || response[0]!=8'h1e)$fatal(1,"CLEAR_FEATURE unlocked BOT");
            expect_out_stall=1;msc_send(31,accepted);expect_out_stall=0;
            append_byte();gap(40);drain();
            control_nodata(8'h21,8'hff,0,2);
            control_nodata(8'h02,1,0,16'h81);control_nodata(8'h02,1,0,16'h01);
            msc_out_pid=8'hc3;msc_in_pid=8'hc3;msc_in_pending=-1;
            wait_status(32'h400,0);ahb_write(32'h14,32'h8);
            control_read(8'h82,0,0,16'h81,2,0);
            if(ctl_data[0]!=0)$fatal(1,"GET_STATUS still halted after reset");
            empty_command(8'h00,0,0,0);empty_status(1,0);
            $display("BOT GUARD PASS fault=%0d STALL/GET_STATUS/CDC/reset",fault);
        end
        // Le firmware demande le disque et l'obtient entre deux commandes.
        // La suite suivante vérifie le transport brut, sans exécuter SCSI :
        // le garde de protocole est donc réinitialisé pendant ces seuls stimuli.
        guard_enable=0;gap(10);
        ahb_write(32'h14, 32'h2);
        wait_status(32'h100, 32'h100);
        check_pattern = 1;

        // Commande de 31 octets vers le firmware, puis rien à lire : NAK.
        msc_out(31, out_accepted); if (!out_accepted) $fatal(1, "first EP1 OUT refused");
        fw_read(31);
        expect_in(1, -1);
        // Octets non validés : toujours NAK. Validés : un paquet de 512, dont
        // l'ACK est perdu pendant que le port série émet et reçoit.
        // (le port émet un octet tous les deux cycles : 312 octets demandent 624 cycles)
        fw_push(200, 0); gap(800); expect_in(1, -1);
        fw_push(312, 0); gap(800); expect_in(1, -1);
        ahb_write(32'h10, 0); gap(60);
        expect_in(0, 512);
        append_byte(); gap(40); drain();
        fw_push(13, 0);                       // suite écrite pendant la reprise, non validée
        expect_in(0, 512);
        append_byte(); gap(40); drain();
        expect_in(1, 512);
        expect_in(1, -1);
        ahb_write(32'h10, 0); gap(60);
        expect_in(1, 13);
        wait_status(32'h2, 32'h2);

        // Firmware lent, hôte qui interroge sans arrêt : 1 037 octets validés
        // d'un coup doivent sortir en 512 + 512 + 13, sans paquet court avant.
        slow_count = 0; slow_done = 0;
        fork
            begin fw_push(1037, 23); ahb_write(32'h10, 0); slow_done = 1; end
            begin
                while (slow_count < 3) begin
                    msc_in(slow_count != 1 || msc_in_pending >= 0, in_len);
                    if (in_len >= 0 && msc_in_pending < 0) begin
                        if (!slow_done) $fatal(1, "EP1 IN: %0d bytes offered before validation", in_len);
                        slow_lengths[slow_count] = in_len; slow_count++;
                    end
                end
            end
        join
        if (slow_lengths[0] != 512 || slow_lengths[1] != 512 || slow_lengths[2] != 13)
            $fatal(1, "EP1 IN packet lengths %0d %0d %0d", slow_lengths[0], slow_lengths[1], slow_lengths[2]);
        wait_status(32'h2, 32'h2);

        // Écriture disque : 12 paquets de 512 octets alors que le firmware ne
        // lit pas ; le contrôleur doit refuser (NAK) sans rien perdre, puis
        // tout livrer une fois le firmware revenu.
        out_done = 0;
        for (integer attempts = 0; attempts < 14 && out_done < 12; attempts++) begin
            msc_out(512, out_accepted);
            if (out_accepted) out_done++;
        end
        if (msc_out_naks == 0) $fatal(1, "EP1 OUT accepted %0d packets without back-pressure", out_done);
        fork
            fw_read(12 * 512);
            begin
                while (out_done < 12) begin
                    msc_out(512, out_accepted);
                    if (out_accepted) out_done++; else gap(400);
                end
            end
        join
        ahb_read(32'h08, port_value); if (!port_value[31]) $fatal(1, "unexpected extra EP1 OUT byte");
        ahb_read(32'h04, port_value); if (port_value[7]) $fatal(1, "port reports a loss: %h", port_value);
        append_byte(); gap(40); drain();
        // Le firmware rend le disque : le matériel répond de nouveau.
        ahb_write(32'h14, 32'h20);
        wait_status(32'h300, 32'h000);
        guard_enable=1;gap(10);
        check_pattern = 0;
        empty_command(8'h00, 0, 0, 0); empty_status(1, 0);
        if (fin_endpoint_mismatches != 0) $fatal(1, "FIN endpoint mismatches");
        $display("PASS USB disk with official controller HS=%b: IN %0d bytes/%0d packets, %0d replays, %0d NAK; OUT %0d bytes, %0d NAK, %0d NYET; serial %0d bytes",
                 usb_highspeed, msc_in_count, msc_in_packets, msc_in_replays, msc_in_naks,
                 msc_out_count, msc_out_naks, msc_out_nyets, delivered);
        $finish;
    end
