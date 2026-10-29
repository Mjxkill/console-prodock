# Measured chain behaviour: seeds, stalls and fault isolation

All statements below are **simulation observations** from the protected
`test_bench.py` harness. Nothing here is a hardware measurement, a root-cause
claim, or proof that an RTL mechanism is correct on silicon.

## Tested configuration

- RTL is untouched; only `bench.sv` drives the external AHB master and DDR
  readiness model.
- Exact chain: AHB master -> `ahb_exts_bridge` -> `video_bus_stage` ->
  `gpu_accel` command FIFO -> blitter/geometry extended engine ->
  `ddr_gpu_arb` -> modeled DDR boundary.
- The native DDR side is a bench model (`m_ready`, `m_wr_ready`). Its
  handshake is not the real memory controller.
- Case set: `(seed,fault)` = `(1,0)`, `(8,0)`, `(1,1)`, `(1,2)`, `(1,3)`,
  `(1,4)`.
- Watchdogs are bounded per AHB access, per completion poll, per pending
  wait and globally; a simulator abort alone would not count as coverage.

## Seeds are genuinely different models

The seeds select different clock/stall timing, not a label:

| seed | hclk half | mem_clk half | mem_clk phase | stall phase |
| ---: | --------: | -----------: | ------------: | ----------: |
| 1 | 6 ns | 7 ns | 1 ns | 0 |
| 8 | 5 ns | 8 ns | 3 ns | 3 |

Both healthy runs produced the required exact footprint and completion:

```text
CASE seed=1 fault=0 returncode=0
CLOCK_CONFIG seed=1 hclk_half_ns=6 memclk_half_ns=7 memclk_phase_ns=1 stall_offset=0 fault=0
BASELINE_PASS accepted=1 words=16 stalls=1 seed=1

CASE seed=8 fault=0 returncode=0
CLOCK_CONFIG seed=8 hclk_half_ns=5 memclk_half_ns=8 memclk_phase_ns=3 stall_offset=3 fault=0
BASELINE_PASS accepted=1 words=16 stalls=3 seed=8
```

Observed healthy invariants in both runs:

- exactly 16 command words observed externally;
- exactly 1 accepted native write, no rejected write and no late duplicate;
- `done` advanced to 2 and `busy` returned to 0;
- one observed native footprint: address `0x04800008`, mask `0`, data
  `16 * 0x6b4d`;
- at least one, and fewer than ten, native stall cycles (1 and 3 measured).

The differing stall counts are an **observation under two timing models**.
They do not establish which clock or FIFO relationship caused the difference.

## Fault 1: `m_ready` withheld

After TARGET completed, `m_ready` was held low. The run terminated at a
bounded `CHECK_FAIL COMPLETION`, not at the global watchdog:

```text
FAULT_STATE time=50784000 seed=1 fault=1 accepted=0 words=16 stalls=3401
FAULT_STATE packet_word0=1c000000 pixel_word0=1c000000 ext_command0=1c000000
FAULT_STATE blitter_ext_active=1 v1_pending=1 arb_take_blitter=1 arb_full=0
FAULT_STATE m_ready=0 m_wr_ready=1 arb_b_ready=0 gpu_native_ready=0
FAULT_STATE done=1 busy=1 command_we=0 queue_valid=0 queue_data=00000000
CHECK_FAIL COMPLETION done=1 want=2 accepted=0 words=16
```

Observed: 16 CLEAR command words were received, the extended engine became
active and one native write was presented, but no native write was accepted.
This demonstrates the bench can hold the DDR `m_ready` side and observe a
bounded stall; it does not identify a hardware fault.

## Fault 2: `m_wr_ready` withheld

Same procedure with `m_wr_ready` held low after TARGET:

```text
FAULT_STATE time=50784000 seed=1 fault=2 accepted=0 words=16 stalls=3401
FAULT_STATE packet_word0=1c000000 pixel_word0=1c000000 ext_command0=1c000000
FAULT_STATE blitter_ext_active=1 v1_pending=1 arb_take_blitter=1 arb_full=0
FAULT_STATE m_ready=0 m_wr_ready=0 arb_b_ready=0 gpu_native_ready=0
FAULT_STATE done=1 busy=1 command_we=0 queue_valid=0 queue_data=00000000
CHECK_FAIL COMPLETION done=1 want=2 accepted=0 words=16
```

Observed: no native write was accepted, the pending CLEAR remained active,
and the failure was reported within the bounded completion poll. `m_ready`
reads 0 here because the arbiter does not raise it while the write-data
channel is unready; that is an observed handshake state, not a causal claim.

## Fault 3: arbiter accepts without GPU acceptance feedback

Only the bench connection from the arbiter `b_ready` to `gpu.ready` was cut.
The arbiter still saw its own ready and accepted the native write, while the
GPU never saw acceptance. The mismatch was caught as a second acceptance of
the still-pending write:

```text
CASE seed=1 fault=3 returncode=-6
CLOCK_CONFIG seed=1 hclk_half_ns=6 memclk_half_ns=7 memclk_phase_ns=1 stall_offset=0 fault=3
FAULT_STATE time=3214000 seed=1 fault=3 accepted=1 words=16 stalls=3
FAULT_STATE packet_word0=1c000000 pixel_word0=1c000000 ext_command0=1c000000
FAULT_STATE blitter_ext_active=1 v1_pending=1 arb_take_blitter=1 arb_full=0
FAULT_STATE m_ready=1 m_wr_ready=1 arb_b_ready=1 gpu_native_ready=0
FAULT_STATE done=1 busy=1 command_we=0 queue_valid=0 queue_data=00000000
CHECK_FAIL COMPLETION duplicate_native_write accepted=2
```

The printed state reports `accepted=1` (the count before the rejected
duplicate) and the public/hierarchical snapshot shows `done=1`, `busy=1`,
`v1_pending=1` and `gpu_native_ready=0`. This is a deliberately injected
feedback break; it is not evidence that the real arbiter or GPU has this bug.

## Fault 4: reset with CLEAR pending, then recovery

`m_ready`/`m_wr_ready` were withheld, CLEAR was submitted, and reset was
asserted while the native write was pending. The run then quarantined all
outputs, restored readiness, and submitted a fresh TARGET/CLEAR:

```text
CASE seed=1 fault=4 returncode=0
CLOCK_CONFIG seed=1 hclk_half_ns=6 memclk_half_ns=7 memclk_phase_ns=1 stall_offset=0 fault=4
RESET_EXERCISE pending=1 ext_active=1 accepted=0 words=16
RESET_QUARANTINE_CLEAR accepted=0 words=0
RESET_RECOVERY_PASS accepted=1 words=16 stalls=1 seed=1
```

Observed recovery invariants:

- during the 80-cycle quarantine after reset, `accepted=0`, `received=0`,
  `valid=0`, `ext_active=0` and `done=0`: no stale command, payload or
  native write replayed;
- after readiness restoration, exactly 16 fresh command words were received
  and one native write was accepted;
- final state was `done=2`, `busy=0`, no rejection and no late duplicate.

This shows the bench can reset the chain in the pending window and can
observe clean re-submission. It does not prove that the same reset sequence
recovers identically in hardware.

## Aggregate result

The protected harness reported `passed=true` with all six cases passing:

```json
{"passed": true, "cases": [
  {"seed": 1, "fault": 0, "passed": true},
  {"seed": 8, "fault": 0, "passed": true},
  {"seed": 1, "fault": 1, "passed": true},
  {"seed": 1, "fault": 2, "passed": true},
  {"seed": 1, "fault": 3, "passed": true},
  {"seed": 1, "fault": 4, "passed": true}]}
```

## Limitations

- Native DDR write acceptance is modeled; the real controller's ACK timing
  remains unobserved in this work.
- The healthy seed comparison shows a stall-count difference under two
  models only; no cause is established.
- Fault 3 is a bench-side cut of one connection, so it demonstrates
  detection coverage, not real arbiter behaviour.
- Fault 4 uses a TB reset and a synthetic pending window; hardware reset
  sequencing and stale-state behaviour are not reproduced.
- Hierarchical signals (`gpu.v1_pending`, `arb.take_blitter`, `arb.full`) are
  read-only simulation diagnostics and are not hardware-observable facts.
- The 3 s per-case harness timeout bounds the runs; real workloads are not
  characterized.
