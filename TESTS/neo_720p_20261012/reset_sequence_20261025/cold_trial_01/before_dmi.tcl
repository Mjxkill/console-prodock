adapter driver ftdi
ftdi vid_pid 0x0403 0x6010
ftdi channel 0
ftdi layout_init 0x0008 0xf00b
ftdi device_desc "Dual RS232-HS"
transport select jtag
adapter speed 100
gdb_port disabled
tcl_port disabled
telnet_port disabled
jtag newtap neo cpu -irlen 5 -expected-id 0x1000563d
init
irscan neo.cpu 0x01
set ident [drscan neo.cpu 32 0]
if {$ident ne "1000563d"} {error "Unexpected AE350 IDCODE: $ident"}
echo "TRANSPORT_ID $ident"
irscan neo.cpu 0x10
set dtmcs [drscan neo.cpu 32 0]
echo "DTMCS_BEFORE $dtmcs"
if {$dtmcs ne "00007071"} {error "Unexpected initial DTMCS: $dtmcs"}
irscan neo.cpu 0x11
echo "DMCONTROL_REQUEST [drscan neo.cpu 41 0x4000000001]"
foreach idle_cycles {1000 10000 100000} {
    runtest $idle_cycles
    echo "DMCONTROL_RESPONSE cycles=$idle_cycles raw=[drscan neo.cpu 41 0]"
}
irscan neo.cpu 0x10
echo "DTMCS_AFTER [drscan neo.cpu 32 0]"
shutdown
