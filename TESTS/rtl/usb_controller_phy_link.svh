// Included only by the WITH_SERIAL_PHY controller test.
// Bootstrap at ideal UTMI; then connect the original PHY through its public
// ports. Enumeration is deliberately outside the physical-link test scope.
reg fclk=0, serial_clock_run=0, serial_phy_reset=1;
reg host_drive=1, host_dp=1, host_dn=0;
tri dp,dn,term_dp,term_dn;
assign dp=host_drive ? host_dp : 1'bz;
assign dn=host_drive ? host_dn : 1'bz;
pulldown(dp,dn);
wire [7:0] real_rxdata;
wire real_rxvalid,real_rxactive,real_rxerror,real_txready;
wire [1:0] real_linestate;
wire PHY_TXREADY=serial_mode ? real_txready : boot_PHY_TXREADY;
wire [7:0] PHY_DATAIN=serial_mode ? real_rxdata : boot_PHY_DATAIN;
wire [1:0] PHY_LINESTATE=serial_mode ? real_linestate : boot_PHY_LINESTATE;
wire PHY_RXVALID=serial_mode ? real_rxvalid : boot_PHY_RXVALID;
wire PHY_RXACTIVE=serial_mode ? real_rxactive : boot_PHY_RXACTIVE;
wire PHY_RXERROR=serial_mode ? real_rxerror : boot_PHY_RXERROR;
real host_ppm=0,card_ppm=0,phase_ns=0.317,local_phase_ns=0,bit_ns,card_half_ns;
real next_host_edge,last_serial_edge=0;
real device_packet_end=0;
integer serial_frames=0,framing_differences=0;
integer host_packet_sequence=0,latest_host_sequence=0,latest_token_endpoint=-1;
reg [7:0] latest_host_pid=0,latest_token_pid=0;
real latest_host_eop=0;
reg host_nrzi;
// Observation only: identify whether an ACK reaches an enabled receiver.
// The generated net alias moved in PHY 3.4. The register and its Q port keep
// the same name in the original and 3.4 Normal models. Advance has different
// internals; availability is checked by the runner, without changing stimulus.
`ifdef PHY_INTERNAL_OBSERVERS
localparam PHY_OBSERVERS_AVAILABLE=1;
wire observed_rx_enable = phy.\usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/rx_en_s0 .Q;
wire [1:0] observed_rx_state = phy.\usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/s_state ;
// Bits 6:5 of the original optimized netlist are unconnected. Observe only
// physical state bits, without interpreting those unused Z bits as an error.
wire [7:0] observed_tx_counter_bus = phy.\usb2_0_softphy/u_usb_20_phy_utmi/u_usb2_0_softphy/u_usb_phy_hs/i_rx_phy/u_cdr_serdes_x8_dx/q_tx_cnt ;
wire [7:0] observed_tx_counter = {observed_tx_counter_bus[7],2'b00,observed_tx_counter_bus[4:0]};
`else
localparam PHY_OBSERVERS_AVAILABLE=0;
wire observed_rx_enable=1'bx;
wire [1:0] observed_rx_state=2'bxx;
wire [7:0] observed_tx_counter=8'hxx;
`endif

USB2_0_SoftPHY_Top phy (
    .clk_i(serial_clock_run ? phy_clk : 1'b0),.fclk_i(fclk),.rst_i(PHY_RESET|serial_phy_reset),
    .pll_locked_i(serial_clock_run),
    .utmi_data_out_i(PHY_DATAOUT),.utmi_txvalid_i(PHY_TXVALID),
    .utmi_op_mode_i(PHY_OPMODE),.utmi_xcvrselect_i(PHY_XCVRSELECT),
    .utmi_termselect_i(PHY_TERMSELECT),
    .utmi_data_in_o(real_rxdata),.utmi_rxvalid_o(real_rxvalid),
    .utmi_rxactive_o(real_rxactive),.utmi_rxerror_o(real_rxerror),
    .utmi_txready_o(real_txready),.utmi_linestate_o(real_linestate),
    .usb_dxp_io(dp),.usb_dxn_io(dn),.usb_rxdp_i(dp),.usb_rxdn_i(dn),
    .usb_term_dp_io(term_dp),.usb_term_dn_io(term_dn)
);

initial begin : link_clocks
    real deadline;
    if($value$plusargs("HOST_PPM=%f",host_ppm))begin end
    if($value$plusargs("CARD_PPM=%f",card_ppm))begin end
    if($value$plusargs("PHASE_NS=%f",phase_ns))begin end
    if($value$plusargs("LOCAL_PHASE_NS=%f",local_phase_ns))begin end
    bit_ns=(1000.0/480.0)/(1.0+host_ppm/1e6);
    card_half_ns=(1000.0/1920.0)/(1.0+card_ppm/1e6);
    deadline=0;
    // Keep 60 MHz continuous across the handoff. The independent process
    // below offsets 960 MHz only, with exactly the same frequency ratio.
    forever begin
        deadline=deadline+16*card_half_ns;
        #(deadline-$realtime);phy_clk=~phy_clk;
    end
end

initial begin : serializer_clock
    real deadline;
    // Avoid simulating the serializer during the 20 ms UTMI bootstrap.
    // At phase zero, this is the former clock schedule: the first 960 MHz
    // rising edge is one half period after the next 60 MHz falling edge.
    wait(serial_clock_run);
    @(negedge phy_clk);
    deadline=$realtime+local_phase_ns;
    forever begin
        deadline=deadline+card_half_ns;
        #(deadline-$realtime);fclk=~fclk;
    end
end

task automatic start_serial_link;
    begin
        gap(10);#0.001;serial_clock_run=1;
        gap(20);host_dp=0;host_dn=0;
        gap(20);serial_phy_reset=0;
        gap(1500);host_drive=0;serial_mode=1;
        gap(10);
        if(PHY_OPMODE!==0 || PHY_XCVRSELECT!==0 || !usb_highspeed)
            $fatal(1,"PHY handoff did not retain HS state");
        $display("Original PHY connected at %t",$realtime);$fflush();
        $display("PHY_OBSERVERS available=%0d",PHY_OBSERVERS_AVAILABLE);
    end
endtask

always @(posedge phy_clk)if(serial_mode && $test$plusargs("DEBUG"))begin
    if(real_rxvalid)$display("PHY RX %t %02x act=%b error=%b",$realtime,real_rxdata,real_rxactive,real_rxerror);
    if(PHY_TXVALID && real_txready)$display("PHY TX %t %02x",$realtime,PHY_DATAOUT);
end
always @(observed_rx_enable) if(serial_mode && $test$plusargs("DEBUG"))
    $display("PHY RX enable %t en=%b state=%b counter=%0d",$realtime,observed_rx_enable,observed_rx_state,observed_tx_counter);
always @(observed_rx_state) if(serial_mode && $test$plusargs("DEBUG"))
    $display("PHY RX state %t state=%b counter=%0d gap_from_device_ns=%0.6f",$realtime,observed_rx_state,observed_tx_counter,$realtime-device_packet_end);

task automatic serial_bit(input bit value);
    begin
        if(!value)host_nrzi=~host_nrzi;
        host_dp=host_nrzi;host_dn=~host_nrzi;
        next_host_edge=next_host_edge+bit_ns;
        #(next_host_edge-$realtime);
    end
endtask

task automatic serial_send(input integer n);
    integer ones;
    begin
        // The host keeps an independent free-running bit-time grid.
        next_host_edge=phase_ns+($floor(($realtime-phase_ns)/bit_ns)+1)*bit_ns;
        #(next_host_edge-$realtime);
        host_packet_sequence++;
        if(n==3 && (packet[0]==8'h69 || packet[0]==8'he1 || packet[0]==8'h2d))begin
            latest_token_pid=packet[0];
            latest_token_endpoint={packet[2][2:0],packet[1][7]};
        end
        if($test$plusargs("DEBUG"))
            $display("HOST SOP %t pid=%02x len=%0d gap_from_device_ns=%0.6f rx_en=%b state=%b counter=%0d",$realtime,packet[0],n,$realtime-device_packet_end,observed_rx_enable,observed_rx_state,observed_tx_counter);
        host_drive=1;host_nrzi=1;
        repeat(31)serial_bit(0);
        serial_bit(1);ones=1;
        for(integer i=0;i<n;i++)for(integer b=0;b<8;b++)begin
            serial_bit(packet[i][b]);
            if(packet[i][b])ones++;else ones=0;
            if(ones==6)begin serial_bit(0);ones=0;end
        end
        // HS SOF is the exception: 40 EOP bits, against eight for every
        // other packet (USB 2.0 electrical compliance EL_55 / EL_25).
        serial_bit(0);
        if(packet[0]==8'ha5)repeat(39)serial_bit(1);
        else repeat(7)serial_bit(1);
        host_dp=0;host_dn=0;host_drive=0;
        latest_host_eop=$realtime;latest_host_pid=packet[0];latest_host_sequence=host_packet_sequence;
        $display("HOST_EOP seq=%0d pid=%02x token_pid=%02x endpoint=%0d time_ns=%0.6f",latest_host_sequence,latest_host_pid,latest_token_pid,latest_token_endpoint,latest_host_eop);
        // Tasks must return before a fast device reply can complete.
    end
endtask

always @(dp or dn) begin
    #0.001;
    if((dp===0 && dn===1)||(dp===1 && dn===0))last_serial_edge=$realtime;
end

task automatic serial_receive;
    real sample_time,previous_sample,first_k,after_eop,host_eop_snapshot,first_k_width;
    bit previous_level,value,sync_found,eop;
    integer symbols,ones,bits,host_sequence_snapshot,token_endpoint_snapshot;
    reg [7:0] current_byte,host_pid_snapshot,token_pid_snapshot;
    begin
        first_k=$realtime;
        host_eop_snapshot=latest_host_eop;host_pid_snapshot=latest_host_pid;
        token_pid_snapshot=latest_token_pid;token_endpoint_snapshot=latest_token_endpoint;
        host_sequence_snapshot=latest_host_sequence;
        $display("DEVICE_SOP host_seq=%0d host_pid=%02x token_pid=%02x endpoint=%0d first_k_ns=%0.6f host_eop_ns=%0.6f response_delay_ns=%0.6f",host_sequence_snapshot,host_pid_snapshot,token_pid_snapshot,token_endpoint_snapshot,first_k,host_eop_snapshot,first_k-host_eop_snapshot);
        wait(dp===1 && dn===0);
        first_k_width=$realtime-first_k;
        if(($realtime-first_k)>1.55*bit_ns || ($realtime-first_k)<0.45*bit_ns)
            framing_differences++;
        sample_time=$realtime+bit_ns/2;
        previous_sample=$realtime;previous_level=0;sync_found=0;symbols=0;
        while(!sync_found)begin
            #(sample_time-$realtime);
            if(symbols>=12 && previous_level==0 && dp===0)sync_found=1;
            if(dp!==!dn)$fatal(1,"Invalid differential SYNC");
            previous_level=dp;symbols++;
            if(symbols>40)$fatal(1,"No end of SYNC");
            if(last_serial_edge>previous_sample)sample_time=last_serial_edge+bit_ns/2;
            previous_sample=$realtime;sample_time=sample_time+bit_ns;
        end
        response_len=0;ones=1;bits=0;current_byte=0;eop=0;
        while(!eop)begin
            #(sample_time-$realtime);
            if(dp!==!dn)$fatal(1,"Truncated serial DATA before EOP");
            value=(dp===previous_level);previous_level=dp;
            if(ones==6)begin
                if(value)eop=1; // HS EOP: intentional bit-stuff violation
                else ones=0;   // stuffed zero is not part of the byte
            end else begin
                current_byte[bits]=value;bits++;
                if(value)ones++;else ones=0;
                if(bits==8)begin
                    if(response_len>=1024)$fatal(1,"Serial packet overflow");
                    response[response_len]=current_byte;response_len++;bits=0;
                end
            end
            if(last_serial_edge>previous_sample)sample_time=last_serial_edge+bit_ns/2;
            previous_sample=$realtime;sample_time=sample_time+bit_ns;
        end
        if(bits!=7)$fatal(1,"EOP not on byte boundary: %0d residual bits",bits);
        after_eop=$realtime+bit_ns/2;
        wait(dp===0 && dn===0);
        device_packet_end=$realtime;
        if($realtime-after_eop>bit_ns)framing_differences++;
        $display("RESPONSE_TIMING host_seq=%0d host_pid=%02x token_pid=%02x endpoint=%0d response_pid=%02x host_eop_ns=%0.6f first_k_ns=%0.6f response_delay_ns=%0.6f first_k_width_ns=%0.6f eop_tail_ns=%0.6f",host_sequence_snapshot,host_pid_snapshot,token_pid_snapshot,token_endpoint_snapshot,response[0],host_eop_snapshot,first_k,first_k-host_eop_snapshot,first_k_width,$realtime-after_eop);
        responses++;serial_frames++;
        $write("WIRE at %t ep%0d len=%0d: ",$realtime,endpt_sel,response_len);
        for(integer i=0;i<response_len;i++)$write("%02x ",response[i]);
        $display("");$fflush();
    end
endtask

initial begin
    wait(serial_mode);
    forever begin
        wait(!host_drive && dp===0 && dn===1);
        serial_receive();
    end
end
