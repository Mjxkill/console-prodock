# Bounded independent failure analysis

Own only owned/analyse.py and owned/REPORT.md, below1000 lines each. No tools
may launch Gowin, network, hardware, or modify frozen context. Read bounded logs,
facts and Tcl docs. Implement analyse(facts) in analyse.py returning a JSONable
dict with r4_returncode, r2_returncode, r3_returncode, r4_has_bitstream,
r4_has_postroute_vo, r3_r4_same_sdc, r4_report_queries, r2_r3_same_vg,
r3_r4_same_vg, r3_r4_same_incremental_anchor, root_cause_proven (bool).
Add independent behavioral assertions in your source if useful.

Report established/unknown reasons for R4 failing at STA after90%, and minimal
reuse plan of R4VG+R4PR without synthesis, newRTL, waivedSTA, or hardware.
Compare R2−11, R3success, R4return1; cannot infer R4SIGSEGV or FPGA timing cause.
R3 changed report queries AND incremental anchor. Check cmd.do normalization.
Review old resume helper hard-coded R2 assumptions that cannot be reused blind.
There is no accessible coredumpctl command nor matching journalctl record; not
proof that no internal crash happened. Root will decide any restart.

Run fixed tests first, then implement compact analysis and report, then tests
AFTER last write. Aim below30 useful tool calls, no artificial requests quota.
