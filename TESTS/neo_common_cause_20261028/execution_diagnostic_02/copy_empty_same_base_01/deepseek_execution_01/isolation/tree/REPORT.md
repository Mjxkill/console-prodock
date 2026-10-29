# COPY same-base boundary report

## Exact condition under test

For `gpu_copy565`, with `src_end = w1 + w3[15:0]*w2[15:0]` and
`dst_end = dst_base + dst_stride*dst_height`, the overlap interval is:

```
overlap = (w1 < dst_end) && (dst_base < src_end)
```

Overlap is rejected unless the descriptor uses the identical base/stride
layout. The relevant validation term is:

```
descriptor_bad[2] = (src_end > 33'h040000000)
                 || (w7 != 0)
                 || (overlap && (w1 != dst_base || w3[15:0] != dst_stride))
```

The fixed bench inputs are `dst_base=0x12000020`, `dst_stride=32`,
`dst_height=1`, hence `dst_end=0x12000040`. All ten stimuli request a
`0x0` clip extent, so accepted descriptors complete without memory traffic.
The source base is varied between the original `0x12000000` and the
same-base value `0x12000020`.

## Observations (all are real Verilator simulation)

| case | bad expected/observed | requests | cycles | interpretation |
|---|---|---|---|---|
| original_empty | 0/0 | 0 | 7 | `src_end == dst_base`; strict overlap is false, accepted. |
| same_base_empty | 0/0 | 0 | 7 | identical base and stride satisfy the layout exception. |
| overlap_wrong_base | 1/1 | 0 | 4 | height 2 overlaps; differing source base rejects. |
| same_layout_taller | 0/0 | 0 | 7 | height 2 overlaps; identical base/stride is permitted. |
| same_base_wrong_stride | 1/1 | 0 | 4 | overlap remains; stride 64 != dst_stride 32 rejects. |
| same_base_height_zero | 1/1 | 0 | 4 | zero height is rejected independently of overlap. |
| same_base_misaligned | 1/1 | 0 | 4 | source base `0x12000022` violates base alignment. |
| same_base_reserved_word | 1/1 | 0 | 4 | nonzero reserved `w7` is rejected. |
| original_forced_end | 1/1 | 0 | 4 | forced `src_end=0x12000060` makes overlap; different base rejects. |
| same_base_forced_end | 0/0 | 0 | 7 | same forced overlap, matching base/stride still accepted. |

For every row the bench observed exactly one `done` pulse (including the 20
post-completion cycles), the expected `bad` value, zero `valid` assertions and
therefore zero requests even with `ready=0`. Rejected descriptors finish in
4 cycles; accepted empty descriptors finish in 7.

## Why the forced `src_end` counterexample matters, and its limit

Forcing `src_end` isolates the range term from address arithmetic: with the
original base it still rejects, while with the same base and stride it still
passes. This shows the overlap rejection is neutralized specifically by the
base/stride equality term, not merely by the rectangle becoming empty.

It is not a physical diagnosis. `force` overwrites the RTL register, bypassing
the real `w1 + stride*height` computation. The proposed firmware change moves
the source base from `0x12000000` to `0x12000020`, which changes both
`src_end` and the base comparison at once. A future success therefore cannot
uniquely attribute behaviour to the overlap term, the changed range, or another
descriptor effect. No board or hardware test is claimed here.

## Limitations

- Results are simulation only; no hardware, board, or global DDR operation.
- Only the ten specified descriptor boundary cases were exercised.
- All requests use zero clip extent, so no final memory read or write occurs.
- Bench inputs fix `dst_base`, `dst_stride`, `clip_r=16`, and `clip_b=1`;
  these results do not prove same-layout validity for arbitrary descriptors.
- The forced-end cases are artificial fault injection, not observable hardware
  states, and the `ready=0` condition only shows no `valid` assertion for these
  inputs.
