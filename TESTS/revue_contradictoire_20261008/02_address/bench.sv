module address_accept_tb;
reg vid_hsel,usb_trace_selected,blit_selected,scan_hready,blit_hready,usb_trace_hready,usb_msc_hready;
reg [31:0] vid_haddr=0;
wire vid_hready;
wire        usb_leg_hready = blit_selected ? usb_msc_hready : usb_trace_hready;
wire blit_address_ready = usb_trace_selected ? usb_leg_hready : (blit_selected || scan_hready);
assign vid_hready = usb_trace_selected ? usb_leg_hready : (blit_selected ? blit_hready : scan_hready);
wire old_sel = vid_hsel && !vid_haddr[13] && vid_haddr[12] && vid_hready;
wire new_sel = vid_hsel && !vid_haddr[13] && vid_haddr[12] && blit_address_ready;
initial begin
    for(integer b=0;b<512;b++)begin
        {vid_hsel,vid_haddr[13:12],usb_trace_selected,blit_selected,scan_hready,
          blit_hready,usb_trace_hready,usb_msc_hready}=9'(b);
        #1;
        if ((old_sel && blit_hready) !== (new_sel && blit_hready))
            $fatal(1,"AHB address acceptance differs: %b",9'(b));
    end
    $display("PASS 512 AHB address acceptance combinations");
    $finish;
end
endmodule
