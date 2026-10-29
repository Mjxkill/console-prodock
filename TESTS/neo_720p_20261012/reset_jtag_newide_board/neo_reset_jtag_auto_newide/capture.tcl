adapter driver ftdi
ftdi vid_pid 0x0403 0x6010
ftdi channel 0
ftdi layout_init 0x0008 0xf00b
ftdi device_desc "Dual RS232-HS"
transport select jtag
adapter speed 1000
gdb_port disabled
tcl_port disabled
telnet_port disabled
jtag newtap resetprobe tap -irlen 5 -expected-id 0x1000563d
init
for {set i 0} {$i < 1000} {incr i} {
    irscan resetprobe.tap 2
    runtest 20
    echo "RESET_JTAG $i [drscan resetprobe.tap 163 0]"
    sleep 20
}
shutdown
