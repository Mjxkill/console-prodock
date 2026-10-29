# R19 COPY rejection: bounded independent descriptor bench

## Scope and method

This work adds only a standalone bench (`bench.sv`) and this report. The exact
read-only `gpu_copy565.v` is instantiated as `dut`; no RTL, firmware, project,
synthesis, routing, or package files are modified. The bench is not the full
system chain: it supplies the copy engine with a stable command, a clean reset,
and an external native 32-byte memory terminal.

The protected harness was run before implementation and failed on the
intentional scaffold (`BENCH_NOT_IMPLEMENTED`). After the final edit the same
harness reports 14/14 cases passing. Every `RESULT` field is measured from the
DUT's public ports:

- `done`: number of observed one-cycle `done` pulses (expected exactly 1);
- `bad`: `bad` sampled at the first `done`;
- `reads`/`writes`: handshakes counted only on `valid && ready`;
- `payload_ok`: `wr_data` compared numerically with the documented memory
  formula plus address/mask/ordering checks, not a precomputed verdict;
- `late_io`: any `valid && ready` in the 20-cycle window after `done`;
- `cycles`: cycle at which `done` was first observed (deadline 1000).

`descriptor_bad` and `state` are additionally displayed with read-only
hierarchical references at `CHECK`/`VALIDATE`. Nothing is forced, deposited, or
driven into the DUT from those observations.

## Stimulus and memory terminal

`cases.hex` holds 14 records of 15 32-bit words: command words `w0..w7` followed
by `dst_base`, `dst_stride`, `dst_height`, `clip_l`, `clip_t`, `clip_r`,
`clip_b`. `+case=N` selects record `N`. The 256-bit command is assembled as
`{w7,w6,w5,w4,w3,w2,w1,w0}`; reset is held for four edges, then `start` is
pulsed for one cycle while the command and descriptor inputs are stable.

`ready` is continuously high. A read request is accepted only on
`valid && ready && !write`, and the terminal returns one 256-bit response after
four cycles with a one-cycle `rd_valid`. The response is stable during that
pulse. For a read word address `A`, the native byte address is `A*4`, and the
response word `i` is

    rd_data[32*i +: 32] = (A*4 + 4*i) ^ 32'ha5396c17

The write handshake is checked at the DUT's `wr_data`, `wr_mask`, and `addr`
outputs. The bench waits 20 cycles after `done` to catch late traffic.

## Measured results (actual harness output)

`descriptor_bad` is shown as the 3-bit RTL value `[2:0]`.

| case | name | descriptor_bad | done | bad | reads | writes | payload_ok | late | cycles |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | exact_board_packet | 000 | 1 | 0 | 1 | 1 | 1 | 0 | 21 |
| 1 | zero_extent | 000 | 1 | 0 | 0 | 0 | 1 | 0 | 7 |
| 2 | src_misaligned | 101 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |
| 3 | src_high_address | 101 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |
| 4 | source_width_zero | 001 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |
| 5 | source_width_too_large | 011 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |
| 6 | source_height_zero | 010 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |
| 7 | source_height_too_large | 110 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |
| 8 | stride_reserved | 010 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |
| 9 | stride_unaligned | 110 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |
| 10 | stride_too_small | 010 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |
| 11 | source_end_beyond_limit | 100 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |
| 12 | overlap_wrong_base | 100 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |
| 13 | reserved_word7 | 100 | 1 | 1 | 0 | 0 | 1 | 0 | 4 |

For case 0 the bench also printed:

    OBS case=0 state=VALIDATE descriptor_bad=000
    OBS board_read addr=04800000
    OBS board_write addr=04800008 mask=00000000 payload_match=1

No case produced native traffic except case 0. No case produced a second
`done` or any post-`done` transaction.

## Exact rejection predicates in the RTL

Field extraction from the registered packet:

- `w1 = command[63:32]`, `w2 = command[95:64]`, `w3 = command[127:96]`,
  `w4 = command[159:128]`, `w5 = command[191:160]`, `w6 = command[223:192]`,
  `w7 = command[255:224]`.
- Source dimensions: `W = w2[31:16]`, `H = w2[15:0]`, source stride
  `S = w3[15:0]`.
- Coordinates: `sx/sy = signed16(w4[31:16])/signed16(w4[15:0])`,
  `dx/dy = signed16(w5[31:16])/signed16(w5[15:0])`.
- Rectangle extent used for clipping: `w6[31:16]` (width) and `w6[15:0]`
  (height), added to `dx`/`dy`.
- `src_end = w1 + S*H` (33 bits); `dst_end = dst_base + dst_stride*dst_height`
  (33 bits); `overlap = (w1 < dst_end) && (dst_base < src_end)`.

At `CHECK`, three registered predicates are formed and evaluated at `VALIDATE`:

    bad[0] = (w1[31:30] != 2'b00)
          || (w1[4:0]   != 5'd0)
          || (W == 0)
          || (W > 1024)

    bad[1] = (H == 0)
          || (H > 512)
          || (w3[31:16] != 16'd0)
          || (w3[4:0]   != 5'd0)
          || (S < (W << 1))

    bad[2] = (src_end > 33'h040000000)          // 0x40000000 = 1 GiB
          || (w7 != 32'd0)
          || (overlap && ((w1 != {2'b00, dst_base}) || (S != dst_stride)))

    if (bad[0] | bad[1] | bad[2]) -> bad <= 1, FINISH; no native traffic.
    else                           -> BOUNDS -> SOURCE_CLIP -> CLIP.

The bounds pass and source-clip pass use signed 32-bit `max`/`min`:

    l = max(dx, clip_l);  t = max(dy, clip_t)
    r = min(dx + w6[31:16], clip_r)
    b = min(dy + w6[15:0],  clip_b)
    source_l = dx - sx;   source_t = dy - sy
    source_r = source_l + W; source_b = source_t + H
    l = max(l, source_l); t = max(t, source_t)
    r = min(r, source_r); b = min(b, source_b)
    if (l >= r || t >= b) -> FINISH (done, bad stays 0); no native traffic.

## Which gates fire for the fixed cases

The case names identify the intended gate, but several records trip more than
one predicate. The observed `descriptor_bad` values agree with the following
sub-predicates.

- case 0: none (`000`). Accepted.
- case 1: none (`000`); it is the later zero-extent path: `w6 = 0` makes
  `r = dx = 0` and `b = dy = 0`, so `l >= r` and `t >= b` at `CLIP`.
- case 2 `w1=0x12000002`: `w1[4:0]!=0` (`bad[0]`); `src_end=0x12000022`
  overlaps dst `[0x12000020,0x12000040)` and `w1!=dst_base` (`bad[2]`).
  Observed `101`.
- case 3 `w1=0x80000000`: `w1[31:30]=2'b10` (`bad[0]`); `src_end=0x80000020`
  exceeds `0x40000000` (`bad[2]`). Observed `101`.
- case 4 `w2=0x00000001`: `W=0` (`bad[0]`). Observed `001`.
- case 5 `w2=0x04010001`: `W=1025>1024` (`bad[0]`); also `S=32 < 2*W=2050`
  (`bad[1]`). Observed `011`.
- case 6 `w2=0x00100000`: `H=0` (`bad[1]`). Observed `010`.
- case 7 `w2=0x00100201`: `H=513>512` (`bad[1]`); `src_end=0x12004020`
  overlaps dst and `w1!=dst_base` (`bad[2]`). Observed `110`.
- case 8 `w3=0x00010020`: reserved high stride bits `w3[31:16]=1` (`bad[1]`).
  Observed `010`.
- case 9 `w3=0x00000022`: `w3[4:0]=2!=0` (`bad[1]`); `src_end=0x12000022`
  overlaps dst and `w1!=dst_base` (`bad[2]`). Observed `110`.
- case 10 `w2=0x00200001`: `W=32`, and `S=32 < 2*W=64` (`bad[1]`).
  Observed `010`.
- case 11 `w1=0x3fffffe0`, `H=2`: `src_end=0x40000020 > 0x40000000`
  (`bad[2]`). Observed `100`.
- case 12 `w2=0x00100002`, `src_end=0x12000040`, `dst_end=0x12000040`:
  `overlap` is true and `w1 (0x12000000) != dst_base (0x12000020)` (`bad[2]`).
  Observed `100`.
- case 13: `w7=1` (`bad[2]`). Observed `100`.

Every rejected case drives `bad=1`, exactly one `done` pulse, zero read/write
handshakes, and no post-`done` traffic.

## Exact board case (case 0)

Record values: `w1=0x12000000`, `w2=0x00100001` (`W=16`, `H=1`),
`w3=0x00000020` (`S=32`), `w4=0` (`sx=sy=0`), `w5=0` (`dx=dy=0`),
`w6=0x00100001`, `w7=0`, `dst_base=0x12000020`, `dst_stride=32`,
`dst_height=1`, clip `(0,0,16,1)`.

Interval arithmetic:

    src_end = 0x12000000 + 32*1 = 0x12000020
    dst_end = 0x12000020 + 32*1 = 0x12000040
    overlap = (0x12000000 < 0x12000040) && (0x12000020 < 0x12000020) = false

The source interval is `[0x12000000,0x12000020)` and the destination interval
is `[0x12000020,0x12000040)`. They touch at `source_end == destination_base`,
but the strict `<` in `overlap` makes them disjoint, so the packet is accepted.
This is the boundary the contract calls out: a source end equal to the
destination base is not an overlap.

Bounds are `l=0, t=0, r=16, b=1`; source bounds are the same, so clipping does
not shrink the rectangle. The engine runs one 16-pixel row:

    source row address      = 0x12000000
    destination row address = 0x12000020
    read  addr port (word)  = 0x04800000    // 0x12000000 / 4
    write addr port (word)  = 0x04800008    // 0x12000020 / 4
    source_lane = 0, dst_lane = 0, count = 16
    wr_mask = 0 (all 16 halfwords enabled)
    wr_data = rd_data

The read response is the documented block at byte address `0x12000000`:

    word i = (0x12000000 + 4*i) ^ 32'ha5396c17, i = 0..7

For example word 0 is `0xb7396c17` and word 7 is `0xb7396c0b`; the bench checks
the full 256-bit value, not these two examples. Measured result: one read, one
write, `payload_ok=1`, `bad=0`, `done` once, no late I/O, done at cycle 21.

## Board facts vs RTL rejection gates

Board/firmware facts available to this task:

- The exact COPY submission was TARGET then COPY and ended with
  `done2/status0/rejected1`.
- The firmware phase8/result-5 also covers a rejection path; it is not
  necessarily a timeout. Its final memory image was not read.
- A prior exact-RTL full chain accepted the same packets and one 32-byte
  read/write.

RTL bench facts measured here:

- The exact board packet (case 0) trips none of the three descriptor gates and
  does not hit the zero-extent path. It produces exactly the expected one
  native read and one native write with the documented payload.
- The 12 adversarial descriptor records and the zero-extent record are all
  rejected or short-circuited with no native traffic.

These are different observation layers. The board `rejected1` is a firmware/
board-level fact; this bench evaluates the copy engine's descriptor and clip
gates only. Because case 0 is accepted by the exact RTL, the hardware rejection
is not explained by these copy-engine descriptor gates for that packet. The
available facts do not identify whether the board rejection came from a
`target_valid`/capture prerequisite, firmware policy, a different captured
packet, or a state/timing effect. No FIFO, timing, or DDR fault is claimed:
there is no concrete reproduction of one in this bench.

## What the bench cannot distinguish on hardware

- **`target_valid`**: the bench drives `start` directly. Hardware may require a
  separate target-valid handshake or gate a target before the copy engine sees
  it; that path is not modelled and cannot be observed here.
- **Captured packet/fields**: the bench holds `command` stable and assumes the
  DUT captures it. Hardware packet capture may present different or stale
  fields (including `w7`, coordinates, or dimensions) that this bench cannot
  see.
- **Synthesized arithmetic/enables**: this is behavioral RTL, not the
  synthesized netlist. DSP inference, clock-enable restructuring, and
  timing-driven changes to the wide `src_end`/`dst_end`/overlap/row arithmetic
  are outside the bench's scope. The RTL annotates the packet register with
  `syn_preserve=1`, but behavioral simulation still does not prove that the
  synthesized clock-enable and arithmetic structure matches the RTL.
- **Transient reset/state**: the bench applies four clean reset edges and a
  one-cycle `start`. Reset release, partial resets, and transient `valid`,
  `ready`, `packet`, or state values on hardware are not reproduced.
- **Memory terminal**: `ready` is always high and read latency is fixed at four
  cycles. The bench therefore does not model FIFO backpressure, DDR latency, or
  interconnect faults, and cannot use a pass here to rule them in or out.

## Limitations

This bench can say precisely which descriptor/clip predicates the exact RTL
evaluates for the supplied packets and whether the board packet moves the
expected single native read/write. It cannot localize the board
`done2/status0/rejected1` to a particular hardware layer. Doing that needs
hardware-side evidence (for example the captured packet, `target_valid`, or
internal state at the rejection) or a synthesized-netlist check; it should not
be inferred from this RTL-only result. The firmware result-5 remains ambiguous
because its final memory image was not read.
