# Task neo_copy_width_discriminant_01

Owner root/game_visual_followup, fpga/test_design, medium. Only scenario.svh
and REPORT.md writable. No hardware/route/production changes. Run official
fixed tests before first edit and after final edit. Maximum report70lines.

Root board facts: existing R19 SHA1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c.
MD12 COPY empty with originalsource12000000 and then source=dst12000020 both
finish done2/busy0/rejected1. Last result root_same_base_run_01 restoredtrue.
MD13 TARGET→CLEAR0→COPY0: CLEAR0done2/rej0, COPY0done3/rej1. CPUreadback only
for older nonemptyCOPY showed seed128B. Lastsamebase has32/32/0images, final
memory unobserved. Native signals NOT physically exposed. No cause established.

One next proposed change: keep samebaseMD12 and change sourcew2 00100001
(width16,height1) to00010001(width1,height1). All addresses,strides,height,
requestedextent0×0 unchanged; src_end stays12000040. Width affects descriptor
checks and source-clipping bound, but empty requestedextent still means noDMA.

Implement actual scenario using protected helpers: reset8hclk negedges,
release20negedges, send_packet0, observe1 into target_reject, assert0,
inject_after_target, send_packet8, observe2 into copy_reject, finish_check.
Do NOT inspect injection to fake observed outputs; protected oracle checks
CSR and FIFO records. There are10cases width16/1 ×injection0..4; healthy
phaseoffset also tested. Each actual RTL chain is unmodified R19.

Injected logical alternatives:1target_valid=0 afterTARGET;
2one COPY-local packetbit84 (sourcewidth bit4) forced0;
3childcopy_bad forced1;4pixelbad_header forced1. They are NOT observations
of hardware. Width1 should remove only fault2's trigger in this bounded model.
Healthy widths both pass. Otherfaults produce equal CSRrejecttuples. Compare
geom_cycles4: its RTL increments outside IDLE/PASS, so it cannot timestamp
pixel validation depth. No CSR exposes descriptor_bad or target_valid.

Explain why a success atwidth1 would narrow a data-dependent path, without
proving localbit84fault; if both fail currentCSRcannot identify the gate.
Recommend only this one conditional nexttest, no list. Clock evidence: exact
R19SDC has bus80MHz/DDRUI75MHz/reference50MHz. u_accel hclk=vid_hclk from
PLL80; mem_clk=gpu_clk=wr_clk=IPclk_out75. DDRbridgeHCLK=clk50 is different.
Protected bench uses ideal80/75MHz clocks, two phases; no physical clock or
jitter measurement. Ignore old header comments in inherited wiring scaffold.
