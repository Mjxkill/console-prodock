# Sensitivity of the CPU/CLEAR simulation oracle

Concrete task: implement `mutation_runner.py::run_suite()` and ANALYSIS.md.
No other source may be changed. Reference RTL/harness are immutable. Work only
on fresh TemporaryDirectory copies. No network/hardware. No FPGA conclusions.

Current main bench passes8cases, but a passing oracle should be shown to reject
concrete wrong bytes, mask, address and absent responses. This task tests that
remaining gap, not more runs of unchanged healthy tests. R19/G22 identical only
for adapter/arb (see INPUTS), not all GPU files.

Return6records with name, compile_returncode, timeout(bool), executed_binary,
returncode, log (actual stdout+stderr), elapsed_seconds. Run actual Verilator
and actual binary for each case. Never synthesize/fake rows or expected logs.
Fixed `validate.py` checks records and reference hashes. Compilation failure,
external subprocess timeout or arbitrary crash does NOT count as detection.
Per-reference source copy, targeted replacement must match exactly once.

0 baseline: no modifications, run +case=0, mustcomplete32CPUreads and2GPUdone.
1 return_low: in copy native_memory.sv, XOR1 into rd_data<=replies[rp]. Expected
  CPU_DATA index0. Do not edit CPU oracle or RTL.
2 return_upper: XORbit128 into same return. ExpectedCPU_DATA index4; this proves
  upper128bit return selection, not only lowword checking.
3 return_missing: in copy native_memory.sv prevent return emission, preserving
  native read acceptance. Expected bounded scenario CPU progress timeout from
  simulation itself; no successful zero-filled memory inference.
4 write_mask: at bench arbiter .b_wr_mask connection only, XOR1 bit into mask.
  Actual gpu_v1 output/RTL untouched. Expected ENDPOINT unexpectedCLEARfootprint.
5 write_address: at bench arbiter .b_addr connection only, XOR0x00800000 into
  native word address (adds32MiB to byteaddress). Expected bounded address
  rejection, proving upper address bits are not silently wrapped by endpoint.

Use /usr/bin/verilator --binary --timing -j2 -Wno-fatal
 -MAKEFLAGS VM_PARALLEL_BUILDS=0 --top-module bench --Mdir <tmp>/obj
 followed by SOURCES from test_liveness.py. Compilation each≤48s, binary≤3s.
Batch currently six compiles expected≈24s within fixed60s wrapper. Capture
only runlogs on success (compile failure detail bounded), no needless output.
Use a fresh directory for each mutant; source files copied, never linked.
No baseline source changes allowed, and only connection/endpoint mutations.

Run official fixed MCP run_tests BEFORE editing and AFTER all edits including
report. Final action is successful fixed run_tests; no further write after.
Report every detected case, actual times, unexpected result if any, and limits
(no proof of physical fault, all mutations are external bench-side inputs).
