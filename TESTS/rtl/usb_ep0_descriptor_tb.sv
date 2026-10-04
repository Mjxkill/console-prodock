// A/B du contrat rxrdy EP0. Aucun force ni accès aux internes fournisseur.
`timescale 1ns/1ps
module usb_ep0_descriptor_tb;
    reg clk=0, reset=1, rxready=0;
    always #8.333 clk=~clk;
    reg [7:0] rxdata=0;
    reg rxvalid=0,rxactive=0,rxerror=0;
    reg [1:0] linestate=2'b01;
    wire [7:0] txdata,app_rxdata,descdata,desctype,descindex;
    wire [15:0] descaddr;
    wire txvalid,busreset,highspeed,online,suspend,phyreset,termselect;
    wire setup,app_rxvalid,app_rxactive,app_rxpktvalid;
    wire app_txactive,app_txpop,app_txfinish;
    wire [1:0] opmode,xcvrselect;
    wire [3:0] endpoint;
    integer ready_option=0,requested=18,hs_option=0;
    integer tx_cycles=0;
    always @(posedge clk) if(!txvalid)tx_cycles<=0;else tx_cycles<=tx_cycles+1;
    wire txready=txvalid && tx_cycles>=3 && (highspeed || ((tx_cycles-3)%40==0));
    USB_EP0_Controller_Model dut(.*);
    byte packet[0:255],response[0:255];
    integer response_len=0,responses=0;
    bit previous_tx=0;
    reg [6:0] address=0;
    string phase="boot";
    integer queries_completed=0;
    always @(posedge clk) begin
        if(txvalid && !previous_tx)response_len=0;
        if(txvalid && txready && opmode==0)begin
            if(response_len==256)$fatal(1,"RESPONSE_OVERFLOW");
            response[response_len]=txdata;response_len++;
        end
        if(!txvalid && previous_tx && response_len)begin
            responses++;
            $write("RESPONSE t=%0t phase=%s ready=%b ep=%0d len=%0d data=",$time,phase,rxready,endpoint,response_len);
            for(integer i=0;i<response_len;i++)$write("%02x",response[i]);
            $display("");$fflush();
        end
        previous_tx=txvalid;
    end
    always @(busreset or phyreset or highspeed or opmode)
        $display("STATE t=%0t reset=%b phyreset=%b HS=%b opmode=%b",$time,busreset,phyreset,highspeed,opmode);
    initial begin #100000000;$fatal(1,"TIMEOUT phase=%s",phase);end
    task automatic gap(input integer n);repeat(n)@(negedge clk);endtask
    function automatic [4:0] crc5(input [10:0] value);
        reg [4:0] c;reg mix;
        begin c=5'h1f;for(integer i=0;i<11;i++)begin mix=c[0]^value[i];c=c>>1;if(mix)c=c^5'h14;end crc5=~c;end
    endfunction
    function automatic [15:0] crc16(input [15:0] value,input [7:0] data);
        reg [15:0] c;
        begin c=value^data;for(integer i=0;i<8;i++)c=c[0]?(c>>1)^16'ha001:c>>1;crc16=c;end
    endfunction
    function automatic byte expected_desc(input integer i);
        case(i)
            0:expected_desc=18;1:expected_desc=1;
            2:expected_desc=hs_option?0:8'h10;3:expected_desc=hs_option?2:1;
            4:expected_desc=2;5,6:expected_desc=0;7:expected_desc=64;
            8:expected_desc=8'h9f;9:expected_desc=8'h35;
            10:expected_desc=8'h10;11:expected_desc=8'h20;
            12:expected_desc=8'h12;13:expected_desc=1;
            14:expected_desc=1;15:expected_desc=2;16:expected_desc=3;17:expected_desc=1;
            default:expected_desc=8'hff;
        endcase
    endfunction
    task automatic receive_packet(input integer n);
        begin
            @(negedge clk);rxactive=1;linestate=2'b01;gap(2);
            for(integer i=0;i<n;i++)begin
                rxdata=packet[i];rxvalid=1;gap(1);rxvalid=0;
                gap(highspeed?1:39);
            end
            gap(2);rxactive=0;linestate=highspeed?2'b00:2'b01;gap(4);
        end
    endtask
    task automatic token(input byte pid);
        reg [10:0] bits;
        begin bits={4'd0,address};packet[0]=pid;packet[1]=bits[7:0];packet[2]={crc5(bits),bits[10:8]};receive_packet(3);end
    endtask
    task automatic await_response(input integer old);
        integer n;
        begin n=0;while(responses==old && n<12000)begin gap(1);n++;end
            if(responses==old)$fatal(1,"NO_RESPONSE phase=%s address=%0d ready=%b setup=%b descaddr=%0d",phase,address,rxready,setup,descaddr);
        end
    endtask
    task automatic require_ack;
        if(response_len!=1 || response[0]!=8'hd2)
            $fatal(1,"ACK_REQUIRED phase=%s address=%0d got=%02x length=%0d",phase,address,response[0],response_len);
    endtask
    task automatic host_ack;
        begin gap(60);packet[0]=8'hd2;receive_packet(1);gap(60);end
    endtask
    task automatic setup_request(input byte typ,input byte req,input [15:0] val,input [15:0] len);
        reg [15:0] crc;integer old;
        begin
            token(8'h2d);gap(60);
            packet[0]=8'hc3;packet[1]=typ;packet[2]=req;packet[3]=val[7:0];packet[4]=val[15:8];
            packet[5]=0;packet[6]=0;packet[7]=len[7:0];packet[8]=len[15:8];
            crc=16'hffff;for(integer i=1;i<=8;i++)crc=crc16(crc,packet[i]);
            crc=~crc;packet[9]=crc[7:0];packet[10]=crc[15:8];
            old=responses;receive_packet(11);await_response(old);require_ack();gap(100);
        end
    endtask
    task automatic get_descriptor(input integer length);
        integer old,n;reg [15:0] crc;
        begin
            phase="descriptor_setup";setup_request(8'h80,8'h06,16'h0100,16'(length));
            phase="descriptor_data";old=responses;token(8'h69);await_response(old);
            n=length<18?length:18;
            if(response_len!=n+3 || response[0]!=8'h4b)$fatal(1,"DATA_REQUIRED phase=%s len=%0d pid=%02x",phase,response_len,response[0]);
            crc=16'hffff;for(integer i=1;i<response_len;i++)crc=crc16(crc,response[i]);
            if(crc!==16'hb001)$fatal(1,"DATA_CRC phase=%s crc=%04x",phase,crc);
            for(integer i=0;i<n;i++)if(response[i+1]!==expected_desc(i))
                $fatal(1,"DESCRIPTOR_BYTE index=%0d got=%02x expected=%02x",i,response[i+1],expected_desc(i));
            $display("DATA_PASS requested=%0d received=%0d address=%0d",length,n,address);
            host_ack();phase="descriptor_status_out";token(8'he1);gap(60);
            packet[0]=8'h4b;packet[1]=0;packet[2]=0;
            old=responses;receive_packet(3);await_response(old);require_ack();gap(100);
            queries_completed++;$display("DESCRIPTOR_PASS requested=%0d address=%0d ready=%b",length,address,rxready);
        end
    endtask
    task automatic set_address;
        integer old;
        begin
            phase="set_address_setup";setup_request(0,5,7,0);
            phase="set_address_status_in";old=responses;token(8'h69);await_response(old);
            if(response_len!=3 || response[0]!=8'h4b || response[1]!=0 || response[2]!=0)
                $fatal(1,"ADDRESS_STATUS_NOT_DATA1_ZLP");
            host_ack();address=7;#2000000;gap(2);
        end
    endtask
    task automatic negotiate_hs;
        begin
            linestate=0;wait(opmode==2 && txvalid);wait(!txvalid);gap(100);
            for(integer i=0;i<3;i++)begin linestate=2;gap(3000);linestate=1;gap(3000);end
            linestate=0;wait(highspeed===1);wait(busreset===0);gap(100);
        end
    endtask
    initial begin
        if($value$plusargs("READY=%d",ready_option))begin end
        if($value$plusargs("LENGTH=%d",requested))begin end
        if($value$plusargs("HS=%d",hs_option))begin end
        rxready=ready_option!=0;
        gap(10);reset=0;wait(busreset===0);
        phase="attach_wait";wait(opmode===0);gap(1000);
        if(hs_option)negotiate_hs();
        else begin
            phase="bus_reset";linestate=0;gap(600000);linestate=1;
            wait(busreset===0);wait(opmode===0);gap(1000);
        end
        $display("BOOT_PASS ready=%b highspeed=%b requested=%0d",rxready,highspeed,requested);
        if(highspeed!==1'(hs_option))$fatal(1,"WRONG_SPEED");
        get_descriptor(requested);set_address();get_descriptor(requested);get_descriptor(requested);
        $display("PASS_EP0 ready=%b requested=%0d queries=%0d",rxready,requested,queries_completed);$finish;
    end
endmodule
