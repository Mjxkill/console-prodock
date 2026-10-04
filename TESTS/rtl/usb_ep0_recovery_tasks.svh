// Isolated HS control-transfer recovery scenarios. Included in a generated
// copy of usb_controller_packet_tb; production and vendor RTL remain intact.
integer recovery_case=0, ep0_pops=0, ep0_finishes=0;
always @(posedge phy_clk) if(!usb_app_reset && endpt_sel==0)begin
    if(usb_txpop)ep0_pops++;
    if(usb_txpktfin)ep0_finishes++;
end
task automatic recovery_get(input integer n);
    begin
        cdc_setup(n==7?8'ha1:8'ha0,8'h21,n==7?16'd0:16'hd1a6,0,16'(n));
    end
endtask
task automatic recovery_check(input integer n);
    reg [15:0] crc;
    byte wanted;
    begin
        if(response_len!=n+3 || response[0]!==8'h4b)
            $fatal(1,"EP0 reply framing: got PID=%02x length=%0d expected DATA1 length=%0d",
                   response[0],response_len,n+3);
        crc=16'hffff;
        for(integer i=1;i<response_len;i++)crc=crc16_byte(crc,response[i]);
        if(crc!==16'hb001)$fatal(1,"EP0 reply CRC mismatch");
        for(integer i=0;i<n;i++)begin
            if(n==32)wanted=8'(i);
            else case(i)
                1:wanted=8'hc2;
                2:wanted=1;
                6:wanted=8;
                default:wanted=0;
            endcase
            if(response[i+1]!==wanted)
                $fatal(1,"EP0 byte %0d got=%02x expected=%02x",i,response[i+1],wanted);
        end
    end
endtask
task automatic recovery_in(input integer n);
    integer old;
    begin
        old=responses;token(8'h69,host_address,0);await_response(old);
        recovery_check(n);
    end
endtask
task automatic recovery_finish;
    integer old;
    begin
        ack();gap(15);
        token(8'he1,host_address,0);gap(12);
        packet[0]=8'h4b;packet[1]=0;packet[2]=0;
        old=responses;receive_packet(3);await_response(old);
        if(response_len!=1 || response[0]!==8'hd2)
            $fatal(1,"EP0 status OUT DATA1 ZLP not ACKed");
        gap(100);
    end
endtask
initial begin : recovery_test
    integer n,pops_before,finishes_before;
    if($value$plusargs("RECOVERY_CASE=%d",recovery_case))begin end
    gap(10);reset=0;
    wait(usb_busreset===0);gap(1000);
    negotiate_hs();
    control_write(5,7);host_address=7;
    #2000000;gap(2);
    control_write(9,1);
    if(!usb_online || !usb_highspeed)$fatal(1,"HS controller not configured");
    cdc_open_configuration();
    // Positive controls: exact ordinary and diagnostic replies, with status.
    recovery_get(7);recovery_in(7);recovery_finish();
    recovery_get(32);recovery_in(32);recovery_finish();
    $display("NORMAL EP0 PASS: CDC7 + diagnostic32, DATA1, CRC and status");
    if(recovery_case==1 || recovery_case==2)begin
        n=recovery_case==1?7:32;
        recovery_get(n);
        pops_before=ep0_pops;finishes_before=ep0_finishes;
        recovery_in(n);
        // DATA was received, but host ACK is lost. No new SETUP or reset.
        gap(120);
        $display("LOST ACK n=%0d pops=%0d finishes=%0d send=%b data=%02x sub_stage=%0d",
                 n,ep0_pops-pops_before,ep0_finishes-finishes_before,
                 endpt0_send,endpt0_dat,u_usb_uart_config.sub_stage);
        recovery_in(n);recovery_finish();
    end else if(recovery_case==3 || recovery_case==4)begin
        recovery_get(32);
        if(recovery_case==4)begin recovery_in(32);gap(120);end
        // A new SETUP abandons the preceding unconsumed/unacknowledged reply.
        recovery_get(7);recovery_in(7);recovery_finish();
        // Reverse the lengths as well, to detect stale length or snapshot.
        recovery_get(7);
        if(recovery_case==4)begin recovery_in(7);gap(120);end
        recovery_get(32);recovery_in(32);recovery_finish();
    end
    // Standard internally handled control must still work after the scenario.
    get_configuration();
    $display("PASS HS EP0 recovery case=%0d pops=%0d finishes=%0d",recovery_case,ep0_pops,ep0_finishes);
    $finish;
end
