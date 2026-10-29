# COPY565 firmware, model, and bounded evidence

## Firmware (`microdma.S`)

Built from the frozen BIN02 diagnostic (928 bytes). Unchanged layout:
code at `0xa0004000` (4000 limit), journal at `0xa0006000` (512 B), and
scratch `[0x12000000,0x12000080)`. TARGET remains the 16x1 descriptor with
color `0x12000020`, Z `0x12000040`, stride 32. Guards, cache/ILM checks,
polling limits, and result codes are unchanged.

CLEAR was replaced by the COPY packet at the same eight-word data slot
(`0x380..0x39f`):

```
1d000000 12000000 00100001 00000020 00000000 00000000 00100001 00000000
```

This reads the 16x1 source at `0x12000000` (stride 32) and writes only 32
bytes at `0x12000020`. The Z word and the other 96 scratch bytes remain
untouched canaries. `verify_memory` now expects the replicated source seed
at offsets 32..63 using `addi t3,t0,-32; xor t3,t3,t2` in place of the old
CLEAR constant.

Allowed word offsets changed: `0x2b8,0x2bc` (the two verify instructions)
and `0x380,0x384,0x388,0x38c,0x394,0x398` (packet data). `0x390` and
`0x39c` are still zero and are therefore unchanged.

Exact binary SHA-256:
`4d3b91ee5fd7aae44abd7d55ab712c24f78167ec1ac318f7a9a21aea000a8684`

## COPY model (`copy_model.py`)

`CopyCPU(RV32)` keeps TARGET and all non-COPY behavior through
`super().command()`. It decodes the public ABI: source base, packed source
width/height (HIGH16/LOW16), stride, signed source and destination pixel
coordinates, and packed requested width/height. It clips the request against
both the source extent and the TARGET rectangle, then copies RGB565 pixels as
bytes. All source rows are read before destination writes.

`gpu_reads` and `gpu_byte_writes` contain byte addresses. `gpu_read` and
`gpu_write` validate the complete scratch range before logging or modifying
memory; failures raise with `scratch` in the message. Malformed descriptors
and overlapping source/destination rectangles are rejected with no GPU I/O
and increment `rejected`. A legal copy increments `done` after completion.
A fully clipped request completes with no byte traffic.

The model is a logical byte-level checker, not a native bus/RTL model. The
one-native-read/one-native-write footprint must come from the separate exact
RTL bench. It models neither DDR/PHY behavior nor physical CPU/CDC timing.

## Observed fixed-test results

Official `taskbox_run_tests` passed all cases:

- healthy: result 1, done2/busy0, 16 command words, 32-byte read and write;
- delayed completion: result 1;
- late completion (delay 50001): result -5 timeout;
- done2 but busy1: result -5;
- wrong read return: result -6, first mismatch `0x12000020`, 1 bad word;
- missing write: result -6, 8 bad words;
- canary corruption: result -6, first mismatch `0x12000040`, 1 bad word;
- bad seed: -2; target touch: -4; target timeout: -3;
- cache enabled: -1; bad MILMB: -1; load trap: -7;
- injected native read/write outside scratch: bounded rejection containing
  `scratch`;
- public-ABI transposed request: source 16x1, requested 1x16 clips to 1x1;
  reads `0x12000000..01`, writes `0x12000020..21`.

Limits: only the exercised non-overlapping descriptors in the 128-byte
scratch are supported; unknown malformed layouts are rejected rather than
emulated. No hardware result is claimed. Test success does not qualify all
DDR, the arbiter, or timing-dependent faults.
