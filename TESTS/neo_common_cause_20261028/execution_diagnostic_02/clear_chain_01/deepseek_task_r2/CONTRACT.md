# Exact R19 CLEAR command-chain test — independent model execution

Owner: `/root/game_visual_followup`. No hardware, syntheses, shared RTL edits,
network, credentials, dependencies or changes to the protected test harness.
Inputs are exact R19 snapshot files (INPUTS.json). They include legacy files
over1000lines as immutable evidence; newly authored source must stay <=1000lines.

Hardware fact: CPU128B readback PASS, TARGET16x1 done1/rejected0, CLEAR16x1
submitted, done remains1/busy1 after about2s. Missing NGDB observations are
being collected separately. Do NOT claim a timing/FIFO/DDR cause without a
reproduced causal counterexample. Injected faults demonstrate distinguishable
signatures, not physical cause. CLEAR color-only waits write acceptance, not
read data. No hard AE350/physical DDR/STA is modeled here.

The full baseline instantiates exact ahb_exts_bridge,video_bus_stage,
gpu_accel including async command FIFO,blitter,geometry,pixel engine,
neo_gpu_debug and ddr_gpu_arb. CPU/scanout arbiter clients are inactive.
Endpoint counts native writes and verifies address0x04800008,mask0,data
16*0x6b4d. TARGET uses width high16,height low16:0x00100001. Payload must not
change. Baseline tests are precompiled in the actual isolation before launch.

Implement bench.sv and ANALYSIS.md only:

1. Read and run protected test_bench.py. Two healthy clock/phase seeds1/8
   must execute actual different relative clock phase/period or stall phase.
   Count native writes externally, command words, and stalls; require one
   write,16 exact command words,done2,busy0,no rejection and no late duplicate.
2. fault1: hold m_ready low after TARGET; fault2: m_wr_ready low after TARGET.
   Each must independently produce bounded CHECK_FAIL COMPLETION with
   accepted=0. Do not treat a simulator crash as coverage.
3. fault3: suppress acceptance feedback to GPU while native arbiter can
   accept the request (intercept the output connection, do not modify RTL).
   Detect a bounded mismatch/duplicate/missing completion and print observed
   accepted count >=1. This separates actual write from completion feedback.
4. fault4: synchronously exercise a reset while a CLEAR is pending with
   native ready withheld. After reset, no stale command/write may replay.
   Restore readiness, submit fresh TARGET/CLEAR, require exact footprint and
   done2/idle. Print RESET_RECOVERY_PASS only after those checks.
5. In each failure emit coherent useful hierarchy/public state, including
   captured packet word0, blitter ext_active, v1_pending, arbiter take_blitter,
   full, readiness and accepted counts. Sampling inside simulation is allowed;
   do not pretend those unavailable signals were observed on real hardware.
6. Own bounded per-access/global watchdog. Run final protected test suite.
   Report measured cases and limits, especially snapshot/handshake versus
   physical CDC, clocks/DDR model, and whether the hardware failure reproduced
   without an injected fault. Keep code modular/readable, no fake PASS prints.

Compiler is `/usr/bin/verilator --binary --timing -j2 -MAKEFLAGS VM_PARALLEL_BUILDS=0`.
Use provided test command; build temporaries live in /tmp. Do not use `cc`
(alternatives path absent), install tools or increase sandbox limits.
