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

adapter speed 100
irscan neo.cpu 0x10
set ready [drscan neo.cpu 32 0]
if {$ready ne "00007071"} {error "DTM state differs from reviewed first read: $ready"}
# DMI address 0x10 (DMCONTROL), 32 zero data bits, op=1 (READ).
# 41 bits = 7 address + 32 data + 2 operation. No op=2 writes.
irscan neo.cpu 0x11
echo "DMCONTROL_REQUEST [drscan neo.cpu 41 0x4000000001]"
foreach idle_cycles {1000 10000 100000} {
    runtest $idle_cycles
    echo "DMCONTROL_RESPONSE idle_cycles=$idle_cycles raw=[drscan neo.cpu 41 0]"
}
irscan neo.cpu 0x10
echo "DTMCS_AFTER_READ [drscan neo.cpu 32 0]"

# DMIRESET only clears sticky status; unlike DTMHARDRESET it does not
# cancel an outstanding DMI request. No DMCONTROL write is performed.
for {set i 0} {$i < 2} {incr i} {
    runtest 100000
    irscan neo.cpu 0x10
    echo "STICKY_CLEAR_BEFORE index=$i raw=[drscan neo.cpu 32 0x10000]"
    runtest 1000
    echo "STICKY_CLEAR_AFTER index=$i raw=[drscan neo.cpu 32 0]"
    irscan neo.cpu 0x11
    runtest 1000
    echo "DMCONTROL_AFTER_CLEAR index=$i raw=[drscan neo.cpu 41 0]"
    irscan neo.cpu 0x10
    echo "DTMCS_AFTER_NOP index=$i raw=[drscan neo.cpu 32 0]"
}
shutdown
