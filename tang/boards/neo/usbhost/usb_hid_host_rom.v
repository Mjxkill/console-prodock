module usb_hid_host_rom #(parameter ROM_FILE = "rtl/usbhost/usb_hid_host_rom.hex") (clk, ce, adr, data);
    input clk;
    input ce;
    input [13:0] adr;
    output [3:0] data;
    reg [3:0] data; 
    reg [3:0] mem [0:679];
    initial $readmemh(ROM_FILE, mem);
    always @(posedge clk) if (ce) data <= mem[adr];
endmodule
