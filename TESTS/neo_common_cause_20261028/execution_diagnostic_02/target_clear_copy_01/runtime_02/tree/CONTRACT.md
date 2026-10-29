# Controlled R19 sequence, task neo_target_clear_copy_01

Owner: root/game_visual_followup. Domain fpga; diagnosis/test_design; medium.
Hardware and provider credentials unavailable. Only scenario.svh and ANALYSIS.md
are writable. Implement a real sequential scenario using the protected bench
helpers, not simulated printouts. Read exact gpu_v1/gpu_copy565 gates and bench.
Run official taskbox_run_tests before modifying and after every final edit.

Board facts: R19 exact bitstream1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c.
CLEAR flags1 stays done1/busy1; CPU32loads later see all128B unchanged.
CLEAR flags0 completes done2/busy0/rejected0. Nonempty COPY and empty COPY both
complete done2/busy0/rejected1. Empty w6=0, valid source16x1, stride32.
COPY CPU followup sees128B seed intact; EMPTY latest does NOT reread final DDR.
Native request signals are not exposed on board; absence of traffic NOT measured.
The latest source fact is root_empty_copy_run_01/result.json. No timing cause established.
No public target_valid CSR. +0x64 is geom_cycles. G22 COPY RTL differs R19.

Implement TARGET then CLEAR0 then COPY0. Initialize reset using8 hclk negedges,
release reset and wait20 negedges. Send first packet with send_packet(0),
observe(1,r), require r0. Call inject_after_target after observation. Then send
packet8, observe2 and record observed_clear. Abort further submission if rejected.
Otherwise call inject_after_clear then send packet16, observe3 and record
observed_copy. Call protected finish_check. Hardware firmware likewise aborts
on CLEAR rejection. Readiness fault1/2 never blocks a no-op. Injection1 forces
invalid target before CLEAR; injection2 forces child copy_bad after CLEAR;
injection3 invalidates target only after successfulCLEAR. These are logical
counterexamples and must not be presented as a diagnosis of physical hardware.

ANALYSIS.md: exact relevant gates and boundaries; explain which outcomes
are distinguishable with this sequence and which aren't. At most2 proposed
experiments on existing bitstream; one must be this sequence. Do not invent
CSR target_valid, native taps or new hardware. Include why successfulCLEAR
only establishes target validity at its own validation edge and why padding
or delayed success is not a unique causal proof. Code <=1000lines/file.
Acceptance: protected 6cases/2clocks, independent stream/native/completion
scoreboard; no ignored failedtest; unchanged readonlyRTL; bounded completion.
