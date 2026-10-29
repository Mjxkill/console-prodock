# Exact USB CDC/reset counter-review, pending after SD bringup

Own only owned/inspect_cdc.py and owned/REPORT.md; protected RTL/netlist/SDC
are from exact R5 frozen snapshot, with G22 hashes. Do not edit RTL/constraints,
run Gowin, use hardware/network, or claim metastability from a digital test.
Implement inspect(context: pathlib.Path)->dict in your owned Python module,
with findings derived from exact sources. Keys: hs_two_stage (bool),
gray_two_stage (bool), gather_raw_async_reset (bool),
gather_clock ('vid_hclk'), reset_source_clock ('phy_clk'),
raw_clear_lut_init ('B'), raw_clear_truth_table (four 0/1 values indexed I1I0),
msc_local_release_guard (bool), timing_closed (bool).
Run actual assertions/test code and deliver a reasoned report with line anchors.

Investigate four worst paths: highspeed PHY→MSC hs_s[0] data sync;
wr_gray bus→PHY wr_gray_s1 pointer sync; rst_usb from phy_clk→gather CLEAR
in vid_hclk; phy_lock_reset clk50→controller count CLEAR at phy_clk.
Classify first synchronizer stages versus unsynchronized reset fanout, but
do NOT say CDC therefore false path. Inspect local hr/ur guards and CE/D
behavior (including unconditionally updated control regs) before deciding
what is proved. Digital simulations cannot prove recovery/metastability safe.
Local reset-release/lock_sync can protect operation but cannot automatically
waive all async recovery/removal. Distinguish a concern from a proven failure.
Propose precise follow-up tests/constraints review only after bringup; no patch.

Read bounded source sections. Run fixed tests before editing. Implement code
and report, then final official test AFTER last write. Keep code<1000 lines.
