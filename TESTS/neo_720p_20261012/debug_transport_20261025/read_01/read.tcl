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
foreach speed {100 1000 100} {
    adapter speed $speed
    irscan neo.cpu 0x01
    set ident [drscan neo.cpu 32 0]
    if {$ident ne "1000563d"} {error "Unexpected AE350 IDCODE: $ident"}
    echo "TRANSPORT_ID speed_khz=$speed raw=$ident"
    irscan neo.cpu 0x10
    for {set i 0} {$i < 4} {incr i} {
        runtest 1000
        set raw [drscan neo.cpu 32 0]
        echo "TRANSPORT_DTMCS speed_khz=$speed index=$i raw=$raw"
    }
}
shutdown
