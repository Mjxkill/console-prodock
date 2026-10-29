# CPU liveness with blocked CLEAR — bounded simulation report

## Scope and evidence status

This report is **simulation-only**. It drives the protected composition bench
(`ddr_ui_adapt` + `ddr_gpu_arb` + real `gpu_v1` + byte-addressed terminal) and
the protected serial CPU128 proxy. It does **not** model the AE350 core, the
AHB/DDR bridge, CDC, DDR IP/PHY, calibration, or physical timing. An accepted
native command is the model's handshake, not proof of a real DDR write ACK:
there is no write-response port. `m_ready`/`m_wr_ready` are terminal inputs and
`b_ready` is arbiter acceptance.

No claim is made that the R19 hardware root cause is reproduced. The scan
requests in case 4 are deliberately synthetic pending history; they do **not**
imply scanout was active on R19 (its framebuffer was off).

## Driver construction

TARGET is always the protected 16x1 packet (colour `0x12000020`, Z `0x12000040`,
stride 32). CLEAR is opcode `0x1c`, flags 1, RGB565 `0x6b4d`, rectangle 16x1.
All stimulus changes occur at negedge. The five fault controls are real
top-level bench inputs, never force/deposit operations. Internal values are
read-only observations only. Every case emits exactly one `blocked` and one
`final` observation; the CPU reader remains the protected independent oracle.
Total simulated cycles were at most 408, well below the 12000-cycle watchdog.

## Measured observations

Labels: `done/busy` = GPU `gpu_done_count`/`gpu_busy`; CPU = completed/sent;
`rd/wr/ret` = terminal reads/writes/returns; `scan` = scan returns; `F/T/A` =
arbiter full / arbiter tag occupancy / adapter tag occupancy; `pend` =
arbiter `cpu_pending`; `take/pref` = `take_blitter`/`prefer_blitter`; feedback =
`gpu_valid`/`gpu_ready`; `CR/WR` = `command_ready`/`write_ready`. Memory means
scratch bytes 0x20..0x3f: **seed** unchanged, **cleared** all `0x6b4d`.

| case/label | done/busy | CPU | rd/wr/ret | scan | F/T/A | pend | take/pref | feedback | CR/WR | memory | cycle |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 blocked | 2/0 | 16/16 | 16/1/16 | 0 | 0/0/0 | 0 | 0/1 | 0/0 | 1/1 | cleared | 183 |
| 0 final | 2/0 | 32/32 | 32/1/32 | 0 | 0/0/0 | 0 | 0/1 | 0/0 | 1/1 | cleared | 331 |
| 1 blocked | 1/1 | 0/1 | 0/0/0 | 0 | 0/0/1 | 1 | 1/1 | 1/0 | 0/1 | seed | 116 |
| 1 final | 2/0 | 32/32 | 32/1/32 | 0 | 0/0/0 | 0 | 0/1 | 0/0 | 0/1 | cleared | 402 |
| 2 blocked | 1/1 | 0/1 | 0/0/0 | 0 | 0/0/1 | 1 | 1/1 | 1/0 | 1/0 | seed | 116 |
| 2 final | 2/0 | 32/32 | 32/1/32 | 0 | 0/0/0 | 0 | 0/1 | 0/0 | 0/1 | cleared | 402 |
| 3 blocked | 1/1 | 8/8 | 8/43/8 | 0 | 0/0/0 | 0 | 1/0 | 1/0 | 1/1 | cleared | 153 |
| 3 final | 1/1 | 32/32 | 32/125/32 | 0 | 0/0/0 | 0 | 0/0 | 1/0 | 1/1 | cleared | 373 |
| 4 blocked | 1/1 | 0/1 | 16/0/0 | 0 | 1/16/1 | 1 | 0/1 | 0/0 | 1/0 | seed | 54 |
| 4 final | 2/0 | 32/32 | 48/1/48 | 16 | 0/0/0 | 0 | 0/1 | 0/0 | 0/1 | cleared | 353 |
| 5 blocked | 1/1 | 32/32 | 32/0/32 | 0 | 0/0/0 | 0 | 0/1 | 1/0 | 0/1 | seed | 325 |
| 5 final | 1/1 | 32/32 | 32/0/32 | 0 | 0/0/0 | 0 | 0/1 | 1/0 | 1/1 | seed | 333 |
| 6 blocked | 1/1 | 0/1 | 1/35/0 | 0 | 0/1/1 | 0 | 0/0 | 1/0 | 1/0 | cleared | 124 |
| 6 final | 1/1 | 32/32 | 32/141/32 | 0 | 0/0/0 | 0 | 0/0 | 1/0 | 1/1 | cleared | 408 |
| 7 blocked | 1/1 | 32/32 | 32/0/32 | 0 | 0/0/0 | 0 | 0/1 | 1/0 | 0/0 | seed | 325 |
| 7 final | 1/1 | 32/32 | 32/0/32 | 0 | 0/0/0 | 0 | 0/1 | 1/0 | 1/0 | seed | 333 |

All eight fixed acceptance cases passed. Case 4 final `returned` is 48 because
the terminal counts all returned reads (16 scan + 32 CPU); the checker verifies
`scan_returns=16` and `native_reads=48` instead of `returned=32` there.

## Interpretation for a future hardware reader

### What each case establishes

* **Case 0 (healthy).** TARGET and CLEAR finish, exactly one 32-byte native
  write clears 0x20..0x3f, and all 32 CPU reads return correctly. This is the
  baseline composition and data oracle.
* **Case 1 (`hold_command`).** With terminal command ready held low, the GPU
  is `done=1,busy=1`, the CPU has one command buffered (`adapter_tags=1`,
  `cpu_pending=1`, `take_blitter=1`), and no native read or write occurs. After
  release, CLEAR and all 32 CPU reads complete normally.
* **Case 2 (`hold_write`).** The same outer signature appears, but
  `command_ready=1` while `write_ready=0`. The arbiter's blitter grant requires
  terminal write readiness, so a competing blitter write stalls CPU reads even
  though the command port claims readiness. `command_ready` alone is therefore
  not a CPU-liveness guarantee.
* **Case 3 (`cut_feedback`).** The arbiter/terminal accept repeated writes
  (`native_writes` grows from 43 to 125) while the GPU never observes `b_ready`
  and remains `done=1,busy=1`. The CPU still completes all 32 reads. The write
  path allocates no response tags (`full/tags=0`); no FIFO claim is made for
  writes.
* **Case 4 (held returns + synthetic scan history).** Sixteen real
  `g_valid`/`g_ready` accepts issue 16 scan reads, and held returns fill the
  arbiter (`full=1,tags=16,adapter_tags=1`). With `command_ready=1` but
  `write_ready=0`, CLEAR cannot issue. Releasing returns produces 16 scan
  replies followed by 32 CPU replies and one CLEAR write. This isolates queue
  fullness from terminal readiness.
* **Case 5 (`suppress_request`).** The GPU still shows `busy=1,done=1` and its
  raw `gpu_valid=1`, but the arbiter never sees that request and
  `native_writes=0`. All 32 CPU reads complete against unchanged seed memory.
  This is an explicit path-fault model.
* **Case 6 (`cut_feedback` + `hold_returns`).** Repeated writes are accepted
  (`native_writes=35` at the observation) while exactly one CPU read has been
  accepted at the terminal (`native_reads=1`) with no return
  (`returned=0`), one adapter tag and one arbiter tag, but `full=0`. Releasing
  only returns lets all 32 CPU reads finish while the GPU stays busy and writes
  continue. This distinguishes a *missing return* from a *full queue*.
* **Case 7 (`suppress_request` + `hold_write`).** All 32 CPU reads complete
  with `native_writes=0` even though the write channel is not ready. Comparing
  with case 2 shows that write-channel not-ready alone need not inhibit CPU
  reads; a competing GPU VALID that owns the arbiter grant does.

### Observation equivalence and ambiguity

`busy=1,done=1` alone does **not** identify a cause. It is the common final
signature of cases 3, 5, 6 and 7, and also appears while blocked in cases 1 and
2. The differentiating evidence is in the counters: terminal writes, return
counts, tag occupancy, adapter occupancy, and the raw versus filtered
valid/ready signals.

A CPU timeout by itself remains ambiguous. It could be arbiter grant (cases
1 and 2), readiness (case 2's write channel), a missing return (case 6), a full
queue (case 4), or a physical CPU/CDC fault that this bench does not model.
Conversely, CPU success narrows the failure to the GPU/write/feedback side, but
does not locate an unknown physical fault.

Note that the reported `gpu_valid` is the GPU's raw blitter valid, before the
bench's `suppress_request` mask. Cases 5 and 7 therefore show `gpu_valid=1`
with zero native writes, while case 4 shows `gpu_valid=0` during the blocked
window simply because CLEAR had not issued yet while the arbiter was full.

### Limits

The serial CPU128 proxy issues one upstream 128-bit beat per requested 32-bit
load and selects one lane; it is not a claim that the physical AE350 never
combines loads. The terminal checks every write footprint/mask/payload and
bounds queued reads, but it is not a DDR PHY. Finally, no assertion is made
that any of these fault models occurred on R19 hardware.
