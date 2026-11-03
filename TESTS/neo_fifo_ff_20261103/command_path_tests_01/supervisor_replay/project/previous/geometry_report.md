# Geometry COPY read-return gate report

Date: 2026-11-01. Scope: transaction simulation of the exact `prodock` (R6)
and `neo` (R19) `snapshot/*/gpu_geometry.v` with the real `gpu_v1` and
`gpu_copy565` children. No RTL, board, hardware, network, or synthesis change
was made. Cycle values below are simulation observations only.

## Question and method

Do the exact TARGET, SCISSOR, and COPY commands traverse real geometry and do
legitimate COPY read responses pass the geometry return gate and the
`dut.u_pixels` COPY_WAIT gate into `u_copy`? The bench stages TARGET then
SCISSOR, launches the captured COPY packet, and reuses the four latency cases
plus the missing-response case from the previous tested bench. It asserts the
gate at each cycle where an external `rd_valid` is presented while `u_copy` is
in WAIT0. It also counts `shader_start`/`shader_done` per command and records
the order of start, PASS, read response, COPY shader done, and geometry done.

The two snapshots gate the geometry read return differently: R6 qualifies
`rd_valid` with its specific geometry states, including PASS for COPY, while
R19 uses `shader_start || shader_read_phase`, with the retained phase set at
`shader_start` and cleared at `shader_done`. Both mechanisms were exercised by
the same COPY response sequence.

Reset observation: Pro Dock has no child reset port; Neo ties all six
`child_resetn` bits to `!rst` and reported `child_resetn=tied_to_rst bits=6`
after reset. TARGET and SCISSOR were accepted through geometry
(`shader_target_valid=1`, bounds 16x1, clip 0,0..16,1), with exactly one
shader start and done each.

## Positive COPY observations (both profiles)

| case | response_delay | first read | total cycles | starts/dones | gate_cycles |
|---|---:|---:|---:|---:|---:|
| stall_zero | 17 | P:13 N:16 | P:114 N:117 | 3/3 | 1 |
| stall_one | 17 | P:13 N:16 | P:114 N:117 | 3/3 | 1 |
| simul_one | 0 | P:13 N:16 | P:32 N:35 | 3/3 | 1 |
| short_delay | 1 | P:13 N:16 | P:46 N:49 | 3/3 | 1 |

P=prodock, N=neo. All four cases in both profiles reported `result=PASS`,
`rejects=0`, `done=1`, `bad=0`, `geom_errors=0`, read/write address
`0x04800008`, mask `0x00000000`, and the exact expected write payload. At the
first COPY read request the counters were `shader_starts=3` and
`shader_dones=2`, so no stale command accumulator had released COPY early.
Chronology was ordered: start (cycle 1), PASS (3), read response, COPY shader
done, geometry done. For example, short_delay was start=1, PASS=3, read=23,
COPY shader done=39, geometry done=41 (prodock); neo was 1, 3, 26, 42, 44.
The gate assertions checked both `dut.u_pixels.rd_valid` and
`dut.u_pixels.u_copy.rd_valid` while `u_copy` was in WAIT0; each positive case
had exactly one such legitimate response cycle and no assertion fired.

## Missing-response observation

In both profiles the read request was accepted, then no response was supplied
for 96 simulation cycles. COPY remained `busy=1`, `done=0`, `bad=0`,
`rejects=0`, `state=WAIT0`, with `valid=0`, `shader_starts=3`,
`shader_dones=2`, and `gate_cycles=0`. No read response and no COPY or
geometry completion occurred. The bench therefore distinguishes an allowed
finite response delay from an absent response within the bounded window. It
does not establish a physical cause for an absent response.

## Limits

- Transaction-level simulation only; no DDR PHY, board wiring, retiming,
  metastability, or hardware timing was tested.
- The 96-cycle negative window and all cycle counts are simulation bounds, not
  device guarantees.
- The assertions cover the presented read response cycles of these five fixed
  cases, not every possible command or memory traffic pattern.
- Profile behaviour is exactly the two supplied snapshots; no synthesis or
  on-board equivalence is claimed.
