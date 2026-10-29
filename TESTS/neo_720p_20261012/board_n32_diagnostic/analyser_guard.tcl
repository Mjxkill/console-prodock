init
poll
if {[nds.cpu curstate] ne "halted"} {error "Analyser CPU is not already halted"}
if {[lindex [reg priv] 2] != 3 || [lindex [reg satp] 2] != 0} {error "Not the standalone DDR diagnostic"}
set pc [lindex [reg pc] 2]
if {$pc != 0xa000086a && $pc != 0xa000086c && $pc != 0xa000086e} {error "Not the DDR diagnostic terminal loop"}
riscv set_enable_virt2phys off
verify_image {/home/michael/console/TESTS/neo_720p_20261012/board_n32_diagnostic/analyser_ddr_reference/ddr_diag.elf}
verify_image {/home/michael/console/TESTS/neo_720p_20261012/board_n32_diagnostic/analyser_ddr_reference/results.bin} 0xa0201000 bin
echo NEO_ANALYSER_DDR_DIAGNOSTIC_CONFIRMED
shutdown
