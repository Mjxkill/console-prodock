// USB low-speed engine extracted from nand2mario/usb_hid_host, Apache-2.0.
// LA16 changes: 12 MHz clock enable on clk100, complete reset, synchronized
// inputs and tri-state during reset. See PROVENANCE.md and LICENSE.
module la16_usb_ls_engine #(
    parameter ROM_FILE = "rtl/usbhost/usb_hid_host_rom.hex",
    parameter integer ENUM_TIMEOUT_TICKS = 24000000 // 2 s at 12 MHz CE
) (
    input usbrst_n,
    input usbclk,
    input usb_ce,				// 12MHz clock
    inout usb_dp, usb_dm,		// D+, D-
    output usb_oe,
    output reg ukprdy, 			// data frame is outputing
    output ukpstb,				// strobe for a byte within the frame
    output reg [7:0] ukpdat,	// output data when ukpstb=1
    output reg save,			// save: regs[save_r] <= dat[save_b]
    output reg [3:0] save_r, save_b,
    output reg connected,
    output conerr,
    output reg session_reset,
    output reg packet_done, packet_good,
    output reg [7:0] packet_pid,
    output [27:0] debug
);

    parameter S_OPCODE = 0;
    parameter S_LDI0 = 1;
    parameter S_LDI1 = 2;
    parameter S_B0 = 3;
    parameter S_B1 = 4;
    parameter S_B2 = 5;
    parameter S_S0 = 6;
    parameter S_S1 = 7;
    parameter S_S2 = 8;
    parameter S_TOGGLE0 = 9;
    parameter S_TOGGLE1 = 10;

    wire [3:0] inst;
    reg  [3:0] insth;
    wire sample;						// 1: an IN sample is available
    // reg connected = 0;
    reg inst_ready = 0, up = 0, um = 0, cond = 0, nak = 0, dmis = 0;
    reg ug, ugw, nrzon;					// ug=1: output enabled, 0: hi-Z
    reg bank = 0, record1 = 0;
    reg [1:0] mbit = 0;					// 1: out4/outb is transmitting
    reg [3:0] state = 0, stated;
    reg [7:0] wk = 0;					// W register
    reg [7:0] sb = 0;					// out value
    reg [3:0] sadr;						// out4/outb write ptr
    reg [13:0] pc = 0, wpc;				// program counter, wpc = next pc
    reg [2:0] timing = 0;				// T register (0~7)
    reg [3:0] lb4 = 0, lb4w;
    reg [13:0] interval = 0;
    reg [6:0] bitadr = 0;				// 0~127
    reg [7:0] data = 0;					// received data
    reg [2:0] nrztxct, nrzrxct;			// NRZI trans/recv count for bit stuffing
    wire interval_cy = interval == 12001;
    wire next = ~(state == S_OPCODE & (
        inst ==2 & dmi |								// start
        (inst==4 || inst==5) & timing != 0 |			// out0/hiz
        inst ==13 & (~sample | (dpi | dmi) & wk != 1) |	// in 
        inst ==14 & ~interval_cy						// wait
    ));
    wire branch = state == S_B1 & cond;
    wire retpc  = state == S_OPCODE && inst==7  ? 1 : 0;
    wire jmppc  = state == S_OPCODE && inst==15 ? 1 : 0;
    wire dbit   = sb[7-sadr[2:0]];
    wire record;
    reg  dmid;
    reg [23:0] conct;
    reg [$clog2(ENUM_TIMEOUT_TICKS + 1)-1:0] enum_age;
    localparam [$clog2(ENUM_TIMEOUT_TICKS + 1)-1:0] ENUM_LAST = ENUM_TIMEOUT_TICKS - 1;
    reg [13:0] response_wait;
    wire awaiting_response = inst_ready && state == S_OPCODE && inst == 4'd2;
    assign conerr = conct[23] || ~usbrst_n;
    // START retries clear conct even if the control transfer never progresses.
    // Bound the entire enumeration independently, and reset every engine state
    // plus the caller's descriptor/report state, not merely the program counter.
    // Register the request before distributing it to the engine, reports and
    // IOB pipeline. A wide counter decode must not drive their reset pins.
    always @(posedge usbclk) begin
        if (!usbrst_n) session_reset <= 1'b0;
        else session_reset <= usb_ce && (conct[23:22] == 2'b11 || enum_age == ENUM_LAST);
    end

    // The interpreter consumes instructions only on the 3/20 CE. Capture
    // the synchronous ROM output on the intermediate 80 MHz edges: this
    // breaks BRAM -> decode timing without changing any 12 MHz CE sample.
    wire [3:0] rom_inst;
    reg [3:0] decoded_inst /* synthesis syn_preserve=1 */ = 0;
    always @(posedge usbclk)decoded_inst<=rom_inst;
    assign inst=decoded_inst;
    usb_hid_host_rom #(.ROM_FILE(ROM_FILE)) ukprom(.clk(usbclk), .ce(usb_ce), .adr(pc), .data(rom_inst));

    (* syn_preserve=1 *) reg [1:0] dp_sync = 0, dm_sync = 0;
    always @(posedge usbclk) begin
        dp_sync <= {dp_sync[0], usb_dp};
        dm_sync <= {dm_sync[0], usb_dm};
    end

    always @(posedge usbclk) begin
        if(~usbrst_n || session_reset) begin
            pc <= 0; connected <= 0; cond <= 0; inst_ready <= 0; state <= S_OPCODE; timing <= 0; 
            mbit <= 0; bitadr <= 0; nak <= 1; ug <= 0;
            up <= 0; um <= 0; dpi <= 0; dmi <= 0; dmid <= 0;
            ukprdy <= 0; ukprdyd <= 0; ukpdat <= 0; save <= 0;
            save_r <= 0; save_b <= 0; conct <= 0; interval <= 0;
            nrzon <= 0; nrztxct <= 0; nrzrxct <= 0; dmis <= 0;
            insth <= 0; wk <= 0; sb <= 0; sadr <= 0; wpc <= 0;
            lb4 <= 0; lb4w <= 0; record1 <= 0; bank <= 0; nakd <= 0;
            response_wait <= 0;
            data <= 0; enum_age <= 0;
        end else if (usb_ce) begin
            if (connected) enum_age <= 0;
            else if (enum_age != 0 || dmi) enum_age <= enum_age + 1'b1;
            if (awaiting_response && dmi) response_wait <= response_wait + 1'b1;
            else response_wait <= 0;
            dpi <= dp_sync[1]; dmi <= dm_sync[1];
            save <= 0;		// ensure pulse
            if (inst_ready) begin
                // Instruction decoding
                case(state)
                    S_OPCODE: begin
                        insth <= inst;
                        if(inst==1) state <= S_LDI0;						// op=ldi
                        if(inst==3) begin sadr <= 3; state <= S_S0; end		// op=out4
                        if(inst==4) begin ug <= 1'b1; up <= 0; um <= 0; end
                        if(inst==5) begin ug <= 0; end
                        if(inst==6) begin sadr <= 7; state <= S_S0; end		// op=outb
                        if (inst[3:2]==2'b10) begin							// op=10xx(BZ,BC,BNAK,DJNZ)
                            state <= S_B0;
                            case (inst[1:0])
                                2'b00: cond <= ~dmi;
                                2'b01: cond <= connected;
                                2'b10: cond <= nak;
                                2'b11: cond <= wk != 1;
                            endcase
                        end
                        if(inst==11 | inst==13 & sample) wk <= wk - 8'd1;	// op=DJNZ,IN
                        if(inst==15) begin state <= S_B2; cond <= 1; end	// op=jmp
                        if(inst==12) state <= S_TOGGLE0;
                    end
                    // Instructions with operands
                    // ldi
                    S_LDI0: begin	wk[3:0] <= inst; state <= S_LDI1;	end
                    S_LDI1: begin	wk[7:4] <= inst; state <= S_OPCODE; end
                    // branch/jmp
                    S_B2: begin lb4w <= inst; state <= S_B0; end
                    S_B0: begin lb4  <= inst; state <= S_B1; end
                    S_B1: state <= S_OPCODE;
                    // out
                    S_S0: begin sb[3:0] <= inst; state <= S_S1; end
                    S_S1: begin sb[7:4] <= inst; state <= S_S2; mbit <= 1; end
                    // toggle and save
                    S_TOGGLE0: begin 
                        if (inst == 15) connected <= ~connected;// toggle
                        else save_r <= inst;                    // save
                        state <= S_TOGGLE1;
                      end
                    S_TOGGLE1: begin
                        if (inst != 15) begin
                            save_b <= inst;
                            save <= 1;
                        end
                        state <= S_OPCODE;
                    end
                endcase
                // pc control
                if (mbit==0) begin 
                    if(jmppc) wpc <= pc + 4;
                    if (next | branch | retpc) begin
                        if(retpc) pc <= wpc;					// ret
                        else if(branch)
                            if(insth==15)						// jmp
                                pc <= { inst, lb4, lb4w, 2'b00 };
                            else								// branch
                                pc <= { 4'b0000, inst, lb4, 2'b00 };
                        else	pc <= pc + 1;					// next
                        inst_ready <= 0;
                    end
                end
            end
            else inst_ready <= 1;
            // bit transmission (out4/outb)
            if (mbit==1 && timing == 0) begin
                if(ug==0) nrztxct <= 0;
                else
                    if(dbit) nrztxct <= nrztxct + 1;
                    else     nrztxct <= 0;
                if(insth == 4'd6) begin
                    if(nrztxct!=6) begin up <= dbit ?  up : ~up; um <= dbit ? ~up :  up; end
                    else           begin up <= ~up; um <= up; nrztxct <= 0; end
                end else begin
                    up <=  sb[{1'b1,sadr[1:0]}]; um <= sb[sadr[2:0]];
                end
                ug <= 1'b1; 
                if(nrztxct!=6) sadr <= sadr - 4'd1;
                if(sadr==0) begin mbit <= 0; state <= S_OPCODE; end
            end
            // start instruction
            dmid <= dmi;
            if (inst_ready & state == S_OPCODE & inst == 4'b0010) begin // op=start 
                bitadr <= 0; nak <= 1; nrzrxct <= 0;
            end else 
                if(ug==0 && dmi!=dmid) timing <= 1;
                else                   timing <= timing + 1;
            // IN instruction
            if (sample) begin
                // Classify the complete PID. The old first-bit shortcut treated
                // ACK like NAK; a control-read OUT status needs that distinction.
                if (bitadr == 16)
                    nak <= data != 8'hd2 && data != 8'hc3 && data != 8'h4b;
                if(nrzrxct!=6) begin
                    data[6:0] <= data[7:1]; 
                    data[7] <= dmis ~^ dmi;		    // ~^/^~ is XNOR, testing bit equality
                    bitadr <= bitadr + 1; nrzon <= 0;
                end else nrzon <= 1;
                dmis <= dmi;
                if(dmis ~^ dmi) nrzrxct <= nrzrxct + 1;
                else           nrzrxct <= 0;
                if (~dmi && ~dpi) begin
                    ukprdy <= 0;
                    // NAK branch in the ROM retries corrupt data without ACK.
                    if (!packet_finished && data_pid && !valid_data_packet) nak<=1;
                end      // SE0: packet is finished. Mouses send length 4 reports.
            end
            if (ug==0) begin
                if(bitadr==24) ukprdy <= 1;			// ignore first 3 bytes
                if(bitadr==88) ukprdy <= 0;			// output next 8 bytes
            end
            if ((bitadr>11 & bitadr[2:0] == 3'b000) & (timing == 2)) ukpdat <= data;
            // Timing
            interval <= interval_cy ? 0 : interval + 1;
            record1 <= record;
            if (~record & record1) bank <= ~bank;
            // Connection status & WDT
            ukprdyd <= ukprdy;
            nakd <= nak;
            if (ukprdy && ~ukprdyd || inst_ready && state == S_OPCODE && inst == 4'b0010) 
                conct <= 0;     // reset watchdog on data received or START instruction
            else begin 
                if(conct[23:22]!=2'b11) conct <= conct + 1;
            end 
            // START formerly waited forever on an idle bus. Return a NAK-like
            // result to the caller after 1 ms, allowing retry/disconnect logic.
            if (awaiting_response && dmi && response_wait == 14'd12000) begin
                pc <= wpc; state <= S_OPCODE; inst_ready <= 0;
                ukprdy <= 0; bitadr <= 0; nak <= 1; ug <= 0;
                response_wait <= 0;
            end
        end
    end

    // Validate DATA packets before software can observe a report. CRC16 is
    // folded one decoded bit at a time; the residue including the two wire
    // CRC bytes must be B001. START resets the validator for every response.
    reg [15:0] packet_crc;
    reg packet_bad, packet_finished;
    wire rx_bit = dmis ~^ dmi;
    wire data_pid = packet_pid == 8'hc3 || packet_pid == 8'h4b;
    wire valid_data_packet = data_pid && !packet_bad &&
        bitadr >= 32 && bitadr[2:0] == 0 && packet_crc == 16'hb001;
    always @(posedge usbclk) begin
        if (!usbrst_n || session_reset) begin
            packet_crc<=16'hffff;packet_pid<=0;packet_bad<=0;
            packet_done<=0;packet_good<=0;packet_finished<=0;
        end else if (usb_ce) begin
            packet_done<=0;
            if (inst_ready && state == S_OPCODE && inst == 4'd2) begin
                packet_crc<=16'hffff;packet_pid<=0;packet_bad<=0;
                packet_good<=0;packet_finished<=0;
            end else if (sample && !packet_finished) begin
                if (bitadr == 16) packet_pid<=data;
                if (!dpi && !dmi) begin
                    packet_done<=1;packet_good<=valid_data_packet;
                    packet_finished<=1;
                end else if (dpi && dmi) packet_bad<=1;
                else if (nrzrxct == 6) begin
                    if (rx_bit) packet_bad<=1;
                end else if (bitadr >= 16) begin
                    packet_crc <= (packet_crc >> 1) ^
                        ((packet_crc[0] ^ rx_bit) ? 16'ha001:16'h0000);
                end
            end
        end
    end

    // Keep the instruction/bit-select logic in fabric. Only simple pipeline
    // registers drive the IOBs; this shifts all TX edges together by 10 ns.
    reg pad_dp, pad_dm, pad_oe;
    always @(posedge usbclk) begin
        // Data are unobservable while OE is clear. Keep reset off the IOB
        // data flops: distributing the engine reset to their dedicated RESET
        // pins caused a >12 ns path in G57 r3. OE still clears on either reset;
        // usbrst_n also releases the pins asynchronously in the assignments.
        pad_dp <= up;
        pad_dm <= um;
        if (!usbrst_n || session_reset) pad_oe <= 0;
        else pad_oe <= ug;
    end
    assign usb_dp = (pad_oe && usbrst_n) ? pad_dp : 1'bZ;
    assign usb_dm = (pad_oe && usbrst_n) ? pad_dm : 1'bZ;
    assign usb_oe = pad_oe && usbrst_n;
    assign debug = {pc[9:0], wpc[9:0], state, dp_sync[1], dm_sync[1], ug, nak};
    assign sample = inst_ready & state == S_OPCODE & inst == 4'b1101 & timing == 4; // IN
    assign record = connected & ~nak;
    assign ukpstb = ~nrzon & ukprdy & (bitadr[2:0] == 3'b100) & (timing == 2);
    reg    dpi, dmi; 
    reg    ukprdyd;
    reg    nakd;
endmodule
