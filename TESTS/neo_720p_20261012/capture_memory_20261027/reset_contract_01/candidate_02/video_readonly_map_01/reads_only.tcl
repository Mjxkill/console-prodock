# Insert only after independent parked CPU/ROM/device checks.
# This fragment has no write_memory, load_image, resume or reset command.
foreach label {T0 T100 T200 T1200} {
    if {$label eq "T100" || $label eq "T200"} {sleep 100}
    if {$label eq "T1200"} {sleep 1000}
    echo "VIDEO_TIME $label [clock milliseconds]"
    echo "VIDEO_SCAN $label [read_memory 0xe9000000 32 30]"
    echo "VIDEO_GPU $label [read_memory 0xe9001000 32 26]"
    echo "VIDEO_GPU_DEBUG $label [read_memory 0xe9005000 32 17]"
    echo "VIDEO_SCAN_DEBUG $label [read_memory 0xe9006000 32 17]"
}
