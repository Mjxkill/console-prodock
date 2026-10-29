/*
 *  SVO - Simple Video Out FPGA Core
 *
 *  Copyright (C) 2014  Clifford Wolf <clifford@clifford.at>
 *  
 *  Permission to use, copy, modify, and/or distribute this software for any
 *  purpose with or without fee is hereby granted, provided that the above
 *  copyright notice and this permission notice appear in all copies.
 *  
 *  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 *  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 *  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 *  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 *  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 *  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 *  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 *
 */

`timescale 1ns / 1ps
// (include svo_defines.vh retiré : aucune macro utilisée ici — LA16 2026-09-25)

module svo_tmds (
	input clk, resetn, de,
	input [1:0] ctrl,
	input [7:0] din,
	output reg [9:0] dout
);


	// Variable and function names below match the spec names for
	// better readability when comparing to spec encoder flow diagram.
	wire [7:0] D = din;

	function [3:0] N1;
		// Count the number of '1' bits.
		input [7:0] bits;
		integer i;
		begin
			N1 = 0;
			for (i = 0; i < 8; i = i+1)
				N1 = N1 + bits[i];
		end
	endfunction

	function [3:0] N0;
		// Count the number of '0' bits.
		input [7:0] bits;
		integer i;
		begin
			N0 = 0;
			for (i = 0; i < 8; i = i+1)
				N0 = N0 + !bits[i];
		end
	endfunction

	reg [9:0] q_out, q_out_next;
	reg [3:0] N0_q_m, N1_q_m;
	reg signed [7:0] cnt, cnt_next, cnt_tmp;
	reg [8:0] q_m;
	reg stage_resetn, stage_de;
	reg [1:0] stage_ctrl;
	wire use_xnor = (N1(D) > 4) || ((N1(D) == 4) && !D[0]);
	wire [7:0] prefix_xor = {^D[7:0], ^D[6:0], ^D[5:0], ^D[4:0], ^D[3:0], ^D[2:0], ^D[1:0], D[0]};
	always @(posedge clk) begin
		q_m <= {~use_xnor, prefix_xor ^ ({8{use_xnor}} & 8'hAA)};
		stage_resetn <= resetn;
		stage_de <= de;
		stage_ctrl <= ctrl;
	end

	always @(posedge clk) begin
		if (!stage_resetn) begin
			cnt   <= 0; // Data stream disparity count used for DC balance
			q_out <= 0;
		end else if (!stage_de) begin
			cnt   <= 0; // Reset disaprity when not actively displaying
			case (stage_ctrl) // See spec section "Control Period Coding"
				2'b00: q_out <= 10'b1101010100;
				2'b01: q_out <= 10'b0010101011;
				2'b10: q_out <= 10'b0101010100;
				2'b11: q_out <= 10'b1010101011;
			endcase
		end else begin
			// See spec flow diagram in section "Video Data Coding"
			N0_q_m = N0(q_m[7:0]);
			N1_q_m = N1(q_m[7:0]);

			if ((cnt == 0) | (N1_q_m == N0_q_m)) begin
				q_out_next[9]    = ~q_m[8];
				q_out_next[8]    =  q_m[8];
				q_out_next[7:0]  = (q_m[8] ? q_m[7:0] : ~q_m[7:0]);
				if (q_m[8] == 0) begin
					cnt_next = cnt + (N0_q_m - N1_q_m);
				end else begin
					cnt_next = cnt + (N1_q_m - N0_q_m);
				end
			end else if (((cnt > 0) & (N1_q_m > N0_q_m)) | (((cnt < 0) & (N0_q_m > N1_q_m)))) begin
				q_out_next[9]    =  1'b1;
				q_out_next[8]    =  q_m[8];
				q_out_next[7:0]  = ~q_m[7:0];
				cnt_tmp          = cnt + (N0_q_m - N1_q_m);
				if (q_m[8]) begin
					cnt_next = cnt_tmp + 2'h2;
				end else begin
					cnt_next = cnt_tmp;
				end
			end else begin
				q_out_next[9]    =  1'b0;
				q_out_next[8]    =  q_m[8];
				q_out_next[7:0]  =  q_m[7:0];
				cnt_tmp          = cnt + (N1_q_m - N0_q_m);
				if (q_m[8]) begin
					cnt_next = cnt_tmp;
				end else begin
					cnt_next = cnt_tmp - 2'h2;
				end
			end
			cnt   <= cnt_next;
			q_out <= q_out_next;
		end

		dout <= q_out;
	end
endmodule
