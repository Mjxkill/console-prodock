# CPU liveness while CLEAR is blocked — bounded execution task

Owner of allowed edits: `scenario.svh` and `ANALYSIS.md` only. RTL, harness,
endpoint and Python checker are protected. Implement driver, run fixed MCP
`run_tests`, inspect failures, correct, write report, then run fixed tests LAST.
Do not write after the final passing fixed test. No hardware or synthesis.
Mastered code <=1000 lines/file; immutable RTL inputs are evidence snapshots.

## Proven context and limits

R19 hardware run03: TARGET completed; 16 command words = TARGET8+CLEAR8
consumed. CLEAR opcode1c, ext_active1/busy1 blitter SETUP, done1, errors0;
NGDB snapshots stable for100ms. GPU v1 native VALID/READY not observable there.
No CPU readback after blocked CLEAR has yet been executed on the board.
Actual completed CPU seed test before CLEAR was32loads/32stores over128B.
No USB absence conclusion is relevant here.

Existing full-chain bench verified exact R19 AHB bridge/FIFO/geometry/blitter/
gpu_v1/arb, but CPU and scanout were idle. This mission fills that specific gap.
INPUTS.json proves adapter+arb identical to G22r0. GPU v1 and several children
are **exact R19**, differing from G22r0; don't claim entire chains identical.
The protected harness uses real gpu_v1 TARGET/CLEAR at its packet boundary and
real adapter+arb. Serial CPU128 proxy is NOT the hard AE350, AHB DDR bridge,
CDC, DDR IP/PHY, or physical timing. Accepted native command is the model's
handshake, not proof of a real DDR write ACK (there is no write response port).
`m_ready` and `m_wr_ready` are terminal inputs; `b_ready` is arbiter acceptance.

## Tasks and scenarios

Replace scaffold `scenario.svh`. Shared tasks drive only top-level inputs,
at negedge, never force/deposit internals. Internal hierarchical read-only
observations in report are simulation-only. Reset/start TARGET then CLEAR.
TARGET packet is already correct16x1, color12000020/Z12000040, stride32.
CLEAR flags1, RGB5656b4d, dimensions16x1. CPU reader starts via `cpu_begin=1`
once, then performs exactly32 sequential single-outstanding reads. It has
its own independent data oracle for all32 values and rejects wrong results.
Use bounded waits (<12000totalcycles) and preserve normal requested packets.

Each case emits exactly `report("blocked")`, `report("final")`. In healthy
case label blocked is the observation window, not an assertion of blockage.
Fixed checker then verifies interface counts/queues/data outcomes.

0 healthy: TARGET/CLEAR finishes, CPU32read completes; one native write.
1 hold_command=1 beforeCLEAR: waitnativeVALID; startCPU; hold>=80cycles,
  record blocked (pendingCPU, no native read/write). Release, complete32.
2 hold_write=1 beforeCLEAR: same. Determine whether arbiter stallsCPU reads
  despite command_ready remaining available. Release, complete32.
3 cut_feedback=1 beforeCLEAR: terminal still accepts writes, GPU never sees
  b_ready; after>=40cyclesstartCPU. CPU32 can finish while GPUbusy1/done1.
  Keep fault throughout final; record repeated native writes, no claimsFIFO.
4 hold_returns=1; BEFORE CLEAR enqueue exactly16 scan reads (g_addr valid
  scratch native address, e.g.12000060/4), wait arb.full via actual accepts.
  Stop scan stimulus; startCLEAR, CPU; record full/tags16/no returns.
  Release returns, complete32CPU +16scan replies +oneCLEAR. Prior scan reads
  model a synthetic pending history; do NOT imply actual scanout was active
  on R19 (framebuffer off). No forced queue state allowed.
5 suppress_request=1 beforeCLEAR: GPU nativeVALID physically withheld from
  arb, feedback also withheld by harness. StartCPU afterpending;32complete
  with unchangedseed memory, GPUbusy1. This is an explicit path-fault model,
  not a claim that such a fault occurred in FPGA.
6 cut_feedback=1 and hold_returns=1 beforeCLEAR; writes accepted repeatedly.
  StartCPU, wait>=80cycles; one CPU native read accepted, response missing,
  adaptertag1/arbitertag1 notfull, CPU0. Release onlyreturns;32CPUcomplete
  while GPUbusy and writescontinue. Shows missingreturn vs fullqueue.
7 suppress_request=1 AND hold_write=1:32CPUreads complete, zeroGPUwrites,
  demonstrating write-channel not-ready alone needn't inhibit CPU reads;
  compare case2 with competing GPUVALID. Keep both faults throughout final.

Let CPU finish and settle several cycles before final; no forced completed
counters. Fixed harness CPU reader selects 32-bit lane from aligned16B UIbeat,
not a claim the physical AE350 never combines loads. Endpoint128B byte memory
checks every write footprint/mask/payload, all commands, bounded queued reads.

## Deliver report

Table measured per case: GPUdone/busy,32CPUcompleted/nativeaccepted/returned,
full/tags/cpu_pending/take/prefer, acceptance feedback, memory(seed/cleared).
Explain observation equivalence: busy1/done1 alone does not identifycause;
CPU success narrows possibilities but doesn't locate unknown physicalfault.
CPU timeout alone remains ambiguous (arb grant, readiness, returns, physical
CPU/CDC). This mission has no claim that R19 hardware root cause is reproduced.
State any unexpected DUT behaviour with exact counterexample and limits.
