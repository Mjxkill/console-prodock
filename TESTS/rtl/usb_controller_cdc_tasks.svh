// Host-side CDC requests used by Linux/pyserial and the private diagnostic.
// Included inside usb_controller_packet_tb. Vendor internals are observed only.
// The diagnostic handler receives a fixed 64-byte ramp: this checks its exact
// transfer bytes and retry/endpoint interaction, not console counter semantics.
    integer cdc_controls=0, cdc_pending_controls=0;
    task automatic cdc_setup(input byte request_type,input byte request_code,
                             input [15:0] value,input [15:0] index,input [15:0] length);
        reg [15:0] crc;
        integer old;
        begin
            // Twelve 60 MHz clocks give approximately 96 HS bit times
            // between the host token and its following DATA packet.
            token(8'h2d,host_address,0);gap(12);
            packet[0]=8'hc3;packet[1]=request_type;packet[2]=request_code;
            packet[3]=value[7:0];packet[4]=value[15:8];
            packet[5]=index[7:0];packet[6]=index[15:8];
            packet[7]=length[7:0];packet[8]=length[15:8];
            crc=16'hffff;
            for(integer i=1;i<=8;i++)crc=crc16_byte(crc,packet[i]);
            crc=~crc;packet[9]=crc[7:0];packet[10]=crc[15:8];
            old=responses;receive_packet(11);await_response(old);
            if(response_len!=1 || response[0]!=8'hd2)
                $fatal(1,"CDC SETUP not ACKed type=%02x request=%02x",request_type,request_code);
            gap(100);
        end
    endtask
    task automatic cdc_status_in;
        integer old;
        begin
            old=responses;token(8'h69,host_address,0);await_response(old);
            if(response_len!=3 || response[0]!=8'h4b || response[1]!=0 || response[2]!=0)
                $fatal(1,"CDC write status is not DATA1 ZLP");
            ack();gap(100);
        end
    endtask
    task automatic cdc_open_configuration;
        reg [15:0] crc;
        integer old;
        begin
            // SET_LINE_CODING: 115200, one stop bit, no parity, eight bits.
            cdc_setup(8'h21,8'h20,0,0,7);
            token(8'he1,host_address,0);gap(12);
            packet[0]=8'h4b;packet[1]=0;packet[2]=8'hc2;packet[3]=1;packet[4]=0;
            packet[5]=0;packet[6]=0;packet[7]=8;
            crc=16'hffff;
            for(integer i=1;i<=7;i++)crc=crc16_byte(crc,packet[i]);
            crc=~crc;packet[8]=crc[7:0];packet[9]=crc[15:8];
            old=responses;receive_packet(10);await_response(old);
            if(response_len!=1 || response[0]!=8'hd2)$fatal(1,"SET_LINE_CODING data not ACKed");
            gap(100);cdc_status_in();
            if(uart_dte_rate!==115200 || uart_char_format!==0 || uart_parity_type!==0 || uart_data_bits!==8)
                $fatal(1,"SET_LINE_CODING UART parameters differ");
            cdc_setup(8'h21,8'h22,3,0,0);cdc_status_in();
            if(uart_en!==1)$fatal(1,"SET_CONTROL_LINE_STATE did not enable DTR");
            $display("CDC open configuration completed");
        end
    endtask
    task automatic cdc_get_line_coding(input bit diagnostic,input bit history_page);
        reg [15:0] crc;
        integer old,n;
        byte expected_byte;
        bit saved_pending,saved_pid,saved_clear;
        reg [11:0] saved_length;
        begin
            saved_pending=u_usb_fifo.tx_pending[2];
            saved_length=u_usb_fifo.tx_saved_len[2];
            saved_pid=u_usb_device_controller_top.\u_usb_device_controller/u_usb_device_controller_utmi/isync [2];
            saved_clear=u_usb_device_controller_top.\u_usb_device_controller/u_usb_device_controller_utmi/usbc_clr_in [2];
            n=diagnostic?32:7;
            // Exact usb_control_probe.py request: device recipient 0xa0,
            // GET_LINE_CODING 0x21, wValue d1a6/d1a7, interface index zero.
            cdc_setup(diagnostic?8'ha0:8'ha1,8'h21,
                      diagnostic?(history_page?16'hd1a7:16'hd1a6):16'd0,0,n);
            old=responses;token(8'h69,host_address,0);await_response(old);
            if(response_len!=n+3 || response[0]!=8'h4b)
                $fatal(1,"GET_LINE_CODING reply framing differs diagnostic=%b length=%0d",diagnostic,response_len);
            crc=16'hffff;
            for(integer i=1;i<response_len;i++)crc=crc16_byte(crc,response[i]);
            if(crc!==16'hb001)$fatal(1,"GET_LINE_CODING reply CRC differs");
            for(integer i=0;i<n;i++)begin
                if(diagnostic)expected_byte=8'(i+(history_page?32:0));
                else case(i)
                    1:expected_byte=8'hc2;
                    2:expected_byte=1;
                    6:expected_byte=8;
                    default:expected_byte=0;
                endcase
                if(response[i+1]!==expected_byte)
                    $fatal(1,"GET_LINE_CODING byte %0d differs: got=%02x expected=%02x",i,response[i+1],expected_byte);
            end
            ack();gap(15);
            token(8'he1,host_address,0);gap(12);
            packet[0]=8'h4b;packet[1]=0;packet[2]=0;
            old=responses;receive_packet(3);await_response(old);
            if(response_len!=1 || response[0]!=8'hd2)$fatal(1,"GET_LINE_CODING status not ACKed");
            gap(100);
            if(u_usb_fifo.tx_pending[2]!==saved_pending ||
               (saved_pending && u_usb_fifo.tx_saved_len[2]!==saved_length))
                $fatal(1,"CDC control changed pending bulk packet");
            if(saved_pending && u_usb_device_controller_top.\u_usb_device_controller/u_usb_device_controller_utmi/isync [2]!==saved_pid)
                $fatal(1,"CDC control changed pending bulk DATA toggle");
            cdc_controls++;
            if(saved_pending)cdc_pending_controls++;
            $display("CDC GET diagnostic=%b history=%b pending=%b pid=%b->%b clear=%b->%b",
                diagnostic,history_page,saved_pending,saved_pid,
                u_usb_device_controller_top.\u_usb_device_controller/u_usb_device_controller_utmi/isync [2],
                saved_clear,u_usb_device_controller_top.\u_usb_device_controller/u_usb_device_controller_utmi/usbc_clr_in [2]);
        end
    endtask
