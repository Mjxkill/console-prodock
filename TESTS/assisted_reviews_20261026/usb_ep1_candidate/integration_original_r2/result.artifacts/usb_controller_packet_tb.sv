// Original vendor controller, project descriptor/configuration and actual FIFO.
// Host injects UTMI packets; no force or edits to vendor internals.
`timescale 1ns/1fs
module usb_controller_packet_tb;
    reg phy_clk = 0, reset = 1;
    reg [6:0] host_address=0;
    integer ack_delay=20;
    initial if($value$plusargs("ACK_DELAY=%d",ack_delay)) begin end
    localparam ENDPT_UART_CONFIG=4'd0;
    localparam [511:0] cdc_diagnostic_pattern =
        512'h3f3e3d3c3b3a393837363534333231302f2e2d2c2b2a292827262524232221201f1e1d1c1b1a191817161514131211100f0e0d0c0b0a09080706050403020100;
    reg serial_mode=0;
`ifndef WITH_SERIAL_PHY
    always #8.333 phy_clk = ~phy_clk;
`endif
    wire        usb_highspeed, usb_online, usb_suspend, usb_busreset, usb_sof;
    // The controller registers usbrst_o with a synchronous SET. It cannot
    // propagate lock loss while phy_clk is stopped. Reset all application
    // state together with the UART bridge, also during that interval.
    wire        usb_app_reset = RESET | usb_busreset;
    wire [1:0] PHY_XCVRSELECT, PHY_OPMODE;
    reg [1:0] boot_PHY_LINESTATE=2'b01;
    wire PHY_TERMSELECT, PHY_TXVALID;
    reg boot_PHY_RXVALID=0, boot_PHY_RXACTIVE=0, boot_PHY_RXERROR=0;
    wire [7:0] PHY_DATAOUT;
    reg [7:0] boot_PHY_DATAIN=0;
    wire        PHY_RESET;
    wire [15:0] DESC_DEV_ADDR, DESC_DEV_LEN, DESC_QUAL_ADDR, DESC_QUAL_LEN,
                DESC_FSCFG_ADDR, DESC_FSCFG_LEN, DESC_HSCFG_ADDR, DESC_HSCFG_LEN,
                DESC_OSCFG_ADDR, DESC_BOS_ADDR, DESC_BOS_LEN,
                DESC_STRLANG_ADDR, DESC_STRVENDOR_ADDR, DESC_STRVENDOR_LEN,
                DESC_STRPRODUCT_ADDR, DESC_STRPRODUCT_LEN,
                DESC_STRSERIAL_ADDR, DESC_STRSERIAL_LEN;
    wire [7:0]  DESCROM_RDAT, DESC_INDEX, DESC_TYPE;
    wire [15:0] DESCROM_RADDR;
    wire        DESCROM_HAVE_STRINGS;
    wire        RESET = reset;
    wire        setup_active;
    wire [3:0]  endpt_sel;
    wire        usb_rxval, usb_rxact, usb_rxpktval, usb_rxrdy;
    wire [7:0]  usb_rxdat;
    wire        usb_txact, usb_txpop, usb_txpktfin, usb_txcork;
    wire [7:0]  usb_txdat;
    wire [11:0] usb_txdat_len;
    wire [7:0]  endpt0_dat;
    wire        endpt0_send;
    wire [11:0] uart_config_txdat_len;
    wire        ep_usb_rxrdy, ep_usb_txcork, ep2_rx_dval;
    wire [11:0] ep_usb_txlen; wire [7:0] ep_usb_txdat;
    wire [7:0]  ep2_rx_data;
    wire [7:0]  inf_alter_i, inf_alter_o, inf_sel_o;
    wire        inf_set_o;
    reg  [7:0]  interface0_alter, interface1_alter;
    wire        uart_en;
    wire [31:0] uart_dte_rate;
    wire [7:0]  uart_char_format, uart_parity_type, uart_data_bits;
    reg         uart_rx_data_val = 0;      // EP2 TX : impulsion par octet (console AE350)
    reg [7:0] uart_rx_data = 0;
    wire ep2_rx_rdy = 1;


    `include "usb_msc_controller_decl.svh"
    usb_fifo u_usb_fifo (
        .i_ep1_tx_clk  (phy_clk),
        .i_ep1_tx_max  (usb_highspeed ? 12'd512 : 12'd64),
        .i_ep1_tx_dval (msc_tx_dval),
        .i_ep1_tx_data (msc_tx_data),
        .i_ep1_flush   (msc_flush),
        .i_ep1_tx_committed(msc_tx_committed),
        .o_ep1_tx_sent (msc_tx_sent),
        .i_ep1_rx_clk  (phy_clk),
        .i_ep1_rx_rdy  (msc_rx_rdy && !msc_halted),
        .o_ep1_rx_dval (msc_rx_dval),
        .o_ep1_rx_data (msc_rx_data),
        .diagnostic_data(),
        .i_clk         (phy_clk),
        .i_reset       (usb_app_reset),
        .i_usb_endpt   (endpt_sel),
        .i_usb_rxact   (usb_rxact),
        .i_usb_rxval   (usb_rxval),
        .i_usb_rxpktval(usb_rxpktval),
        .i_usb_rxdat   (usb_rxdat),
        .o_usb_rxrdy   (ep_usb_rxrdy),
        .i_usb_txact   (usb_txact),
        .i_usb_txpop   (usb_txpop),
        .i_usb_txpktfin(usb_txpktfin),
        .o_usb_txcork  (ep_usb_txcork),
        .o_usb_txlen   (ep_usb_txlen),
        .o_usb_txdat   (ep_usb_txdat),
        .i_ep2_tx_clk  (phy_clk),
        .i_ep2_tx_max  (12'd64),
        .i_ep2_tx_dval (uart_rx_data_val & usb_online),
        .i_ep2_tx_data (uart_rx_data[7:0]),
        .i_ep2_rx_clk  (phy_clk),
        .i_ep2_rx_rdy  (ep2_rx_rdy),
        .o_ep2_rx_dval (ep2_rx_dval),
        .o_ep2_rx_data (ep2_rx_data)
    );
    assign usb_rxrdy     = (endpt_sel == ENDPT_UART_CONFIG) ? 1'b1 : (endpt_sel==1 && msc_halted) ? 1'b0 : ep_usb_rxrdy;
    assign usb_txcork    = (endpt_sel == ENDPT_UART_CONFIG) ? 1'b0 : (endpt_sel==1 && msc_halted) ? 1'b1 : ep_usb_txcork;
    assign usb_txdat     = (endpt_sel == ENDPT_UART_CONFIG) ? endpt0_dat : ep_usb_txdat;
    assign usb_txdat_len = (endpt_sel == ENDPT_UART_CONFIG) ? uart_config_txdat_len : ep_usb_txlen;

    always @(posedge phy_clk or posedge RESET) begin
        if (RESET) begin
            interface0_alter <= 8'd0; interface1_alter <= 8'd0;
        end else if (inf_set_o) begin
            if (inf_sel_o == 8'd0)      interface0_alter <= inf_alter_o;
            else if (inf_sel_o == 8'd1) interface1_alter <= inf_alter_o;
        end
    end
    assign inf_alter_i = (inf_sel_o == 8'd0) ? interface0_alter :
                         (inf_sel_o == 8'd1) ? interface1_alter : 8'd0;

`ifdef CONSOLE_USB_FULL_SPEED
    localparam USB_HS_SUPPORT = 0;
`else
    localparam USB_HS_SUPPORT = 1;
`endif
    USB_HS_Controller_Model u_hs_model(
        .phy_clk(phy_clk),
        .RESET(RESET),
        .usb_txdat(usb_txdat),
        .endpt0_send(endpt0_send),
        .usb_txdat_len(usb_txdat_len),
        .usb_txcork(usb_txcork),
        .usb_rxrdy(usb_rxrdy),
        .inf_alter_i(inf_alter_i),
        .usb_busreset(usb_busreset),
        .usb_highspeed(usb_highspeed),
        .usb_suspend(usb_suspend),
        .usb_online(usb_online),
        .usb_sof(usb_sof),
        .usb_txpop(usb_txpop),
        .usb_txact(usb_txact),
        .usb_txpktfin(usb_txpktfin),
        .usb_rxdat(usb_rxdat),
        .usb_rxval(usb_rxval),
        .usb_rxact(usb_rxact),
        .usb_rxpktval(usb_rxpktval),
        .setup_active(setup_active),
        .endpt_sel(endpt_sel),
        .inf_alter_o(inf_alter_o),
        .inf_sel_o(inf_sel_o),
        .inf_set_o(inf_set_o),
        .PHY_DATAOUT(controller_dataout),
        .PHY_TXVALID(PHY_TXVALID),
        .PHY_TXREADY(PHY_TXREADY),
        .PHY_DATAIN(PHY_DATAIN),
        .PHY_RXACTIVE(PHY_RXACTIVE),
        .PHY_RXVALID(PHY_RXVALID),
        .PHY_RXERROR(PHY_RXERROR),
        .PHY_LINESTATE(PHY_LINESTATE),
        .PHY_OPMODE(PHY_OPMODE),
        .PHY_XCVRSELECT(PHY_XCVRSELECT),
        .PHY_TERMSELECT(PHY_TERMSELECT),
        .PHY_RESET(PHY_RESET)
    );

    usb_uart_config u_usb_uart_config (
        .diagnostic_data(cdc_diagnostic_pattern),
        .PHY_CLKOUT(phy_clk), .RESET_IN(usb_app_reset),
        .setup_active(setup_active), .endpt_sel(endpt_sel),
        .usb_rxval(usb_rxval), .usb_rxact(usb_rxact), .usb_rxdat(usb_rxdat),
        .usb_txact(usb_txact), .usb_txpop(usb_txpop),
        .usb_txpktfin(usb_txpktfin),
        .usb_txdat_len_o(uart_config_txdat_len),
        .endpt0_dat_o(endpt0_dat), .endpt0_send_o(endpt0_send), .msc_reset_o(msc_bot_reset),
        .uart1_en_o(uart_en), .uart1_BAUD_RATE_o(uart_dte_rate),
        .uart1_PARITY_BIT_o(uart_parity_type), .uart1_STOP_BIT_o(uart_char_format),
        .uart1_DATA_BITS_o(uart_data_bits)
    );
    defparam u_usb_uart_config.ENDPT_UART_CONFIG = ENDPT_UART_CONFIG;
    defparam u_usb_uart_config.MSC = 1;

    byte packet[0:1023];
    always @(PHY_OPMODE,PHY_XCVRSELECT,usb_busreset,usb_highspeed)
        if($test$plusargs("DEBUG")) begin
            $display("state %t op=%b xcvr=%b reset=%b HS=%b",$realtime,PHY_OPMODE,PHY_XCVRSELECT,usb_busreset,usb_highspeed);
            $fflush();
        end
    integer tx_cycles=0;
    always @(posedge phy_clk)
        if(!PHY_TXVALID) tx_cycles<=0;
        else tx_cycles<=tx_cycles+1;
    wire boot_PHY_TXREADY=PHY_TXVALID && tx_cycles>=3 &&
        (usb_highspeed || ((tx_cycles-3)%40==0));
    byte response[0:1023];
    integer response_len=0, responses=0;
    bit previous_tx=0;
`ifdef WITH_SERIAL_PHY
    `include "usb_controller_phy_link.svh"
`else
    wire PHY_TXREADY=boot_PHY_TXREADY;
    wire [1:0] PHY_LINESTATE=boot_PHY_LINESTATE;
    wire [7:0] PHY_DATAIN=boot_PHY_DATAIN;
    wire PHY_RXVALID=boot_PHY_RXVALID,PHY_RXACTIVE=boot_PHY_RXACTIVE,PHY_RXERROR=boot_PHY_RXERROR;
`endif
    integer fin_events=0, fin_endpoint_mismatches=0;
    always @(posedge phy_clk) begin
        if (usb_txpktfin) begin
            fin_events=fin_events+1;
            if (endpt_sel !== u_usb_fifo.s_endpt_sel) begin
                fin_endpoint_mismatches=fin_endpoint_mismatches+1;
                $display("FIN_ENDPOINT_MISMATCH at %t current=%0d buffered=%0d", $realtime,
                         endpt_sel,u_usb_fifo.s_endpt_sel);
            end
        end
        if(usb_txpop && $test$plusargs("DEBUG"))
            $display("POP at %t EP=%0d len=%0d cork=%b pending=%b",$realtime,endpt_sel,usb_txdat_len,usb_txcork,u_usb_fifo.tx_pending[2]);
        if(usb_txpktfin) $display("FIN at %t EP=%0d act=%b pop=%b len=%0d clr=%b isync=%b",$realtime,endpt_sel,usb_txact,usb_txpop,usb_txdat_len,
            1'b0,
            1'b0);
        if (!serial_mode && PHY_TXVALID && !previous_tx) response_len=0;
        if (!serial_mode && PHY_TXVALID && PHY_TXREADY && PHY_OPMODE==0) begin
            response[response_len]=PHY_DATAOUT;
            response_len=response_len+1;
        end
        if (!serial_mode && !PHY_TXVALID && previous_tx && response_len!=0) begin
            responses=responses+1;
            $write("TX at %t ep%0d len=%0d: ", $realtime, endpt_sel, response_len);
            for(integer i=0;i<response_len;i=i+1) $write("%02x ",response[i]);
            $display("");
        end
        previous_tx=PHY_TXVALID;
    end
    task automatic gap(input integer n);
        repeat(n) @(negedge phy_clk);
    endtask
    task automatic negotiate_hs;
        begin
            $display("Start HS negotiation at %t",$realtime);$fflush();
            boot_PHY_LINESTATE=2'b00;
            wait(PHY_OPMODE==2 && PHY_TXVALID);
            $display("Device chirp at %t",$realtime);$fflush();
            wait(!PHY_TXVALID);
            $display("Device chirp ends at %t",$realtime);$fflush();
            gap(100);
            for(integer i=0;i<3;i++)begin
                boot_PHY_LINESTATE=2'b10;gap(3000);
                boot_PHY_LINESTATE=2'b01;gap(3000);
            end
            boot_PHY_LINESTATE=2'b00;
            wait(usb_highspeed===1);
            wait(usb_busreset===0);
            gap(100);
            $display("High speed negotiated at %t",$realtime);
        end
    endtask
    task automatic receive_packet(input integer n);
`ifdef WITH_SERIAL_PHY
        if(serial_mode)serial_send(n);
        else
`endif
        begin
        @(negedge phy_clk); boot_PHY_RXACTIVE=1;
        // The ideal UTMI stub must report line activity too. Holding SE0
        // throughout all packets incorrectly asks for a 3 ms USB reset
        // once a longer test crosses that duration after HS negotiation.
        if(usb_highspeed)boot_PHY_LINESTATE=2'b01;
        gap(2);
        for (integer i=0;i<n;i=i+1) begin
            boot_PHY_RXVALID=1; boot_PHY_DATAIN=packet[i];
            gap(1); boot_PHY_RXVALID=0;
            gap(1);
        end
        gap(2); boot_PHY_RXACTIVE=0;
        if(usb_highspeed)boot_PHY_LINESTATE=2'b00;
        gap(4);
        end
    endtask
    function automatic [4:0] crc5(input [10:0] value);
        reg [4:0] crc;
        reg mix;
        begin
            crc=5'h1f;
            for(integer i=0;i<11;i=i+1) begin
                mix=crc[0]^value[i]; crc=crc>>1;
                if(mix) crc=crc^5'h14;
            end
            crc5=~crc;
        end
    endfunction
    function automatic [15:0] crc16_byte(input [15:0] value,input [7:0] data);
        reg [15:0] crc;
        begin
            crc=value^data;
            for(integer i=0;i<8;i=i+1)
                crc=crc[0] ? (crc>>1)^16'ha001 : crc>>1;
            crc16_byte=crc;
        end
    endfunction
    task automatic token(input byte pid,input [6:0] address,input [3:0] ep);
        reg [10:0] bits;
        begin
            bits={ep,address};
            packet[0]=pid;packet[1]=bits[7:0];packet[2]={crc5(bits),bits[10:8]};
            receive_packet(3);
        end
    endtask
    task automatic ack;
        gap(ack_delay);
        packet[0]=8'hd2;receive_packet(1);gap(15);
    endtask
    task automatic get_configuration;
        reg [15:0] crc;
        integer old;
        begin
            token(8'h2d,host_address,0);gap(8);
            packet[0]=8'hc3;packet[1]=8'h80;packet[2]=8;
            packet[3]=0;packet[4]=0;packet[5]=0;packet[6]=0;
            packet[7]=1;packet[8]=0;
            crc=16'hffff;
            for(integer i=1;i<=8;i++)crc=crc16_byte(crc,packet[i]);
            crc=~crc;packet[9]=crc[7:0];packet[10]=crc[15:8];
            old=responses;receive_packet(11);await_response(old);
            if(response_len!=1 || response[0]!=8'hd2)$fatal(1,"GET_CONFIGURATION setup not ACKed");
            gap(100);
            old=responses;token(8'h69,host_address,0);await_response(old);
            if(response_len!=4 || response[0]!=8'h4b || response[1]!=1)
                $fatal(1,"GET_CONFIGURATION data invalid");
            ack();gap(15);
            token(8'he1,host_address,0);gap(8);
            packet[0]=8'h4b;packet[1]=0;packet[2]=0;
            old=responses;receive_packet(3);await_response(old);
            if(response_len!=1 || response[0]!=8'hd2)$fatal(1,"GET_CONFIGURATION status not ACKed");
            gap(100);
            $display("GET_CONFIGURATION completed");
        end
    endtask
    task automatic await_response(input integer old);
        integer timeout_cycles;
        begin
            timeout_cycles=0;
            while(responses==old && timeout_cycles<1200) begin gap(1);timeout_cycles++;end
            if(responses==old) $fatal(1,"controller did not respond ep=%0d online=%b reset=%b HS=%b opmode=%b xcvr=%b",endpt_sel,usb_online,usb_busreset,usb_highspeed,PHY_OPMODE,PHY_XCVRSELECT);
        end
    endtask
    task automatic control_write(input byte request,input byte value);
        reg [15:0] crc;
        integer old;
        begin
            token(8'h2d,host_address,0);gap(8);
            packet[0]=8'hc3;
            packet[1]=0;packet[2]=request;packet[3]=value;packet[4]=0;
            packet[5]=0;packet[6]=0;packet[7]=0;packet[8]=0;
            crc=16'hffff;
            for(integer i=1;i<=8;i++)crc=crc16_byte(crc,packet[i]);
            crc=~crc;packet[9]=crc[7:0];packet[10]=crc[15:8];
            old=responses;receive_packet(11);await_response(old);
            if(response_len!=1 || response[0]!=8'hd2)$fatal(1,"SETUP not ACKed");
            gap(100);
            old=responses;token(8'h69,host_address,0);await_response(old);
            if(response_len!=3 || response[0]!=8'h4b)$fatal(1,"Control status not DATA1 ZLP");
            ack();gap(100);
            $display("Control write %02x=%02x complete",request,value);
        end
    endtask
    `include "usb_controller_cdc_tasks.svh"
    byte expected[0:8191];
    byte last_accepted[0:1023];
    integer produced=0, delivered=0, accepted_packets=0, duplicates=0, empty_packets=0;
    integer last_length=0, polls=0;
    integer bulk_blocks=0, full64_packets=0;
    byte host_pid=8'hc3;
    byte host_out_pid=8'hc3;
    byte out_expected[0:8191];
    integer out_produced=0,out_delivered=0,out_naks=0;
    always @(posedge phy_clk)if(ep2_rx_dval && !usb_app_reset)begin
        if(out_delivered>=out_produced || ep2_rx_data!==out_expected[out_delivered])
            $fatal(1,"OUT FIFO byte %0d differs: got=%02x expected=%02x queued=%0d",out_delivered,ep2_rx_data,out_expected[out_delivered],out_produced);
        out_delivered++;
    end
    task automatic notification_poll;
        integer old;
        begin
            if($test$plusargs("INTERRUPT_POLLS"))begin
                // cdc_acm also polls the notification IN endpoint. It has
                // no producer here and must not consume EP2 data or its PID.
                // Descriptor bEndpointAddress = 0x83 for CDC notifications.
                old=responses;token(8'h69,host_address,3);await_response(old);
                if(response_len!=1 || response[0]!=8'h5a)
                    $fatal(1,"Empty notification endpoint did not NAK");
                gap(20);
            end
        end
    endtask
    reg [10:0] frame_number=0;
    task automatic sof_context;
        realtime next_microframe;
        begin
            if($test$plusargs("SOF_CONTEXT"))begin
                // Exercise frame boundaries only between transactions. Keep
                // the HS 125 us grid and the 1 ms (not 125 us) frame number.
                // This is a sparse test, not a complete periodic scheduler.
                next_microframe=($floor($realtime/125000.0)+1)*125000.0;
                #(next_microframe-$realtime);
                frame_number=11'($rtoi($floor($realtime/1000000.0)));
                packet[0]=8'ha5;packet[1]=frame_number[7:0];
                packet[2]={crc5(frame_number),frame_number[10:8]};
                receive_packet(3);gap(20);
            end
        end
    endtask
    task automatic out_command;
        reg [15:0] crc;
        integer old,attempts,remaining;
        bit accepted;
        begin
            if($test$plusargs("CDC_CONTEXT"))cdc_get_line_coding(1,0);
            if($test$plusargs("INTERLEAVE_OUT"))begin
                // Actual application request E, length 1, test byte. OUT
                // traffic can occur while a preceding IN still awaits ACK.
                out_expected[out_produced]=8'h45;out_expected[out_produced+1]=1;
                out_expected[out_produced+2]=0;out_expected[out_produced+3]=8'(produced*73+17);
                out_produced+=4;accepted=0;attempts=0;
                while(!accepted && attempts<12)begin
                    token(8'he1,host_address,2);gap(12);
                    packet[0]=host_out_pid;packet[1]=8'h45;
                    packet[2]=1;packet[3]=0;packet[4]=8'(produced*73+17);
                    crc=16'hffff;
                    for(integer i=1;i<=4;i++)crc=crc16_byte(crc,packet[i]);
                    crc=~crc;packet[5]=crc[7:0];packet[6]=crc[15:8];
                    old=responses;receive_packet(7);await_response(old);
                    if(response_len!=1 || (response[0]!=8'hd2 && response[0]!=8'h5a))
                        $fatal(1,"Unexpected bulk OUT handshake");
                    accepted=response[0]==8'hd2;
                    if(!accepted)out_naks++;
                    attempts++;gap(20);
                end
                if(!accepted)$fatal(1,"Bulk OUT retry budget exhausted");
                host_out_pid=host_out_pid^8'h88;
                remaining=100;
                while(out_delivered<out_produced && remaining>0)begin gap(1);remaining--;end
                if(out_delivered!=out_produced)$fatal(1,"ACKed OUT was not delivered exactly once");
            end
        end
    endtask
    task automatic append_byte;
        byte value;
        begin
            value=8'(produced*73+17);
            expected[produced]=value;produced++;
            @(negedge phy_clk);uart_rx_data=value;uart_rx_data_val=1;
            gap(1);uart_rx_data_val=0;
        end
    endtask
    task automatic consume_response(input bit send_ack);
        reg [15:0] crc;
        begin
            polls++;
            if(response_len==1 && response[0]==8'h5a) begin
                // Allow host inter-packet spacing and PHY receive re-enable.
                // Twenty UTMI clocks exceed 88 HS bit times.
                gap(20);
            end
            else begin
                if(response_len<3 || (response[0]!=8'hc3 && response[0]!=8'h4b))
                    $fatal(1,"Unexpected EP2 response");
                crc=16'hffff;
                for(integer i=1;i<response_len;i++)crc=crc16_byte(crc,response[i]);
                if(crc!==16'hb001)$fatal(1,"Invalid DATA CRC");
                if(response[0]==host_pid) begin
                    for(integer i=1;i<response_len-2;i++)begin
                        if(delivered>=produced || response[i]!==expected[delivered])
                            $fatal(1,"Host byte %0d differs: got=%02x expected=%02x produced=%0d",delivered,response[i],expected[delivered],produced);
                        delivered++;
                    end
                    for(integer i=0;i<response_len;i++)last_accepted[i]=response[i];
                    last_length=response_len;
                    accepted_packets++;
                    if(response_len==67)full64_packets++;
                    if(response_len==3)empty_packets++;
                    host_pid=host_pid^8'h88;
                end else begin
                    if(response_len!=last_length)
                        $fatal(1,"Retry changed payload length, including ZLP: %0d -> %0d",last_length,response_len);
                    for(integer i=0;i<response_len;i++)
                        if(response[i]!==last_accepted[i])
                            $fatal(1,"Retry changed byte %0d: %02x -> %02x",i,last_accepted[i],response[i]);
                    duplicates++;
                end
                if(send_ack) ack();
                else gap(120); // host accepted DATA but its ACK is lost
            end
        end
    endtask
    task automatic poll(input bit send_ack);
        integer old;
        begin
            old=responses;token(8'h69,host_address,2);await_response(old);
            consume_response(send_ack);
        end
    endtask
    task automatic drain;
        integer attempts;
        begin
            attempts=0;
            // Retry an ACKed-by-host DATA even when no bytes remain to deliver.
            poll(1);
            while(delivered<produced && attempts<12)begin poll(1);attempts++;end
            gap(40);
            if(delivered!=produced)$fatal(1,"Queued bytes not delivered within retry budget: produced=%0d delivered=%0d",produced,delivered);
        end
    endtask
    `include "usb_msc_controller_tasks.svh"
    initial begin #120000000;$fatal(1,"USB disk timeout");end
endmodule
