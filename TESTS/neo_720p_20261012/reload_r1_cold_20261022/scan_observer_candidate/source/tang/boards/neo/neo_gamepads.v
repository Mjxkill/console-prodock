// Two independent USB-A low-speed hosts, same 80 MHz clock as the AHB port.
// Reading each port's STATUS snapshots its complete report for coherent reads.
`default_nettype none
module neo_gamepads (
    input wire clk, resetn, hsel, hwrite,
    input wire [1:0] htrans,
    input wire [31:0] haddr,
    output reg [31:0] hrdata,
    output wire hready,
    inout wire [1:0] dp, dm
);
    wire [31:0] status[0:1], identity[0:1], reports[0:1];
    wire [63:0] report_data[0:1];
    reg [31:0] snap_id[0:1],snap_count[0:1];
    reg [63:0] snap_report[0:1];
    for(genvar p=0;p<2;p=p+1) begin : g_port
        // Local copy per port. Both host and report state are synchronous
        // to clk; one extra reset cycle cuts the distant video-reset route
        // before the host/session-reset fanout. Preserve the two copies.
        reg rst /* synthesis syn_preserve=1 */ = 1'b1;
        always @(posedge clk)rst<=!resetn;
        usb_gamepad #(.ROM_FILE("rtl/usbhost/usb_hid_host_rom.hex")) u_pad(
            .clk(clk),.rst(rst),.usb_dp(dp[p]),.usb_dm(dm[p]),.buttons(),
            .status(status[p]),.identity(identity[p]),
            .report_count(reports[p]),.report_data(report_data[p]));
    end
    assign hready=1'b1;
    integer i;
    always @(posedge clk) begin
        if(!resetn) begin
            hrdata<=0;
            for(i=0;i<2;i=i+1) begin
                snap_id[i]<=0;snap_count[i]<=0;snap_report[i]<=0;
            end
        end else begin
            // HRDATA is consumed only for a selected read. Decode every
            // cycle so address selection does not also drive 32 enables.
            hrdata<=0;
            case(haddr[7:0])
                8'h00: hrdata<=32'h4e504144; // NPAD
                8'h04: hrdata<=32'h00010002; // ABI 1, two ports
                default: ;
            endcase
            for(i=0;i<2;i=i+1) begin
                case(haddr[7:0])
                    (i+1)*32: begin
                        hrdata<=status[i];
                        if(hsel && htrans[1] && !hwrite)begin
                            snap_id[i]<=identity[i];snap_count[i]<=reports[i];
                            snap_report[i]<=report_data[i];
                        end
                    end
                    (i+1)*32+4: hrdata<=snap_id[i];
                    (i+1)*32+8: hrdata<=snap_count[i];
                    (i+1)*32+12: hrdata<=snap_report[i][31:0];
                    (i+1)*32+16: hrdata<=snap_report[i][63:32];
                    default: ;
                endcase
            end
        end
    end
endmodule
`default_nettype wire
