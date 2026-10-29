# R19 TARGET -> CLEAR(flags=0) -> empty COPY: sequence analysis

Scope: exact R19 bitstream `1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c`,
protected `bench.sv`/`validate.py`, and the unmodified RTL.  All results below are
simulation observations (`hardware=false`); no physical cause is measured here.
G22 COPY RTL is different and is not covered by this analysis.

## Exact gates and packet boundaries

**TARGET (opcode 22, packet words 0..7)**
`gpu_v1` DECODE first clears the sticky bit (`target_valid<=0`) and captures
`color_base=w1[29:0]`, `z_base=w2[29:0]`, `width=w3[31:16]`,
`height=w3[15:0]`, `color_stride=w4[31:16]`, `z_stride=w4[15:0]`, then walks
`TARGET_WAIT -> TARGET_CHECK -> TARGET_PIPE -> TARGET_VALIDATE`.

The registered reject terms are:

```
target_bad[0] <= w1[31:30]!=0 || w2[31:30]!=0 || color_base[4:0]!=0 || z_base[4:0]!=0;
target_bad[1] <= width==0 || width>1024 || height==0 || height>512;
target_bad[2] <= color_stride[4:0]!=0 || z_stride[4:0]!=0 ||
                 color_stride<width*2 || z_stride<width*2;
target_bad[3] <= color_end>33'h040000000 || z_end>33'h040000000;
target_bad[4] <= color_base<z_end && z_base<color_end;
target_bad[5] <= w5!=0 || w6!=0 || w7!=0;
bad_target <= |target_bad;
```

At `TARGET_VALIDATE`: bad -> BAD; otherwise `target_valid<=1`, scissor becomes
`(0,0,width,height)`, then FINISH.  Our packet `0x16000000, 0x12000020,
0x12000040, 0x00100001, 0x00200020, 0,0,0` is a 16x1 target with 32-byte
strides: all bases/strides are 32-byte aligned, `color_end=0x12000040`,
`z_end=0x12000060`, and the overlap term is false because
`z_base<color_end` is `0x12000040<0x12000040`.  Only this validation edge sets
`target_valid`.

**CLEAR flags=0 (opcode 28, packet words 8..15)**
The only reject gate is:

```
bad_clear <= !target_valid || w1>3 || w2>65535 || w3>65535 || (|word_nonzero[7:6]);
```

`w4`/`w5` are not validated by `bad_clear`; they are the rectangle origin and
extent.  Our `w1=0` selects neither colour nor depth (`clear_flags=0`), so
`RECT_SETUP` takes `clear_flags==0 -> FINISH` and issues no native traffic even
though `w5=0x00100001` describes a 16x1 rectangle.  CLEAR success therefore only
proves `!bad_clear` at its registered DECODE sample: it proves `target_valid`
was 1 at that edge, not that the TARGET fields were revalidated.

**COPY empty (opcode 29, packet words 16..23)**
`gpu_v1` DECODE has `29: state <= target_valid ? COPY_START : BAD`; there is no
target-field recheck at this point.  The child `gpu_copy565` then validates its
own descriptor (aligned source, non-zero/in-range dimensions, stride, 32-byte
source end, overlap layout, `w7==0`) and clips.  Our source
`0x12000000, 0x00100001, 0x00000020` is a valid 16x1, stride-32 source;
`w6=0` makes `l=t=r=b=0`, so `CLIP` reaches FINISH with `bad=0`.  In
`gpu_v1` COPY_WAIT: `copy_bad ? BAD : FINISH`.  Thus the empty copy increments
`done` but does not increment `rejected`, and it neither reads the 128-byte seed
nor writes the destination.  The CPU-visible `+0x34` value is the cumulative
V1 rejected count, not a COPY status and not a native-traffic observation.

## Observations from this sequence

| run | clear | copy | done | words | meaning |
|---|---:|---:|---:|---:|---|
| seed 1 / seed 8, injection 0 | 0 | 0 | 3 | 24 | TARGET, CLEAR0, empty COPY complete; no reject |
| readiness fault 1 or 2, injection 0 | 0 | 0 | 3 | 24 | no-op path is insensitive to withheld DDR ready |
| injection 1 | 1 | -1 (not sent) | 2 | 16 | CLEAR saw `!target_valid`; submission aborted |
| injection 2 | 0 | 1 | 3 | 24 | forced child `copy_bad` reached BAD after CLEAR |
| injection 3 | 0 | 1 | 3 | 24 | forced target invalidation reached COPY decode |

`done` increments on BAD/FINISH as well as on success, so it is a completion
counter, not a success count.  Rejected is cumulative.  Injection 2 and
injection 3 produce the same CPU-visible `copy_reject=1`, so this sequence
cannot distinguish "child copy_bad" from "target_valid false at COPY decode"
from the observed result alone.

## What this sequence can and cannot distinguish

Distinguishable: a healthy CLEAR sample from a CLEAR whose `!target_valid` term
is true (injection 1); a healthy empty COPY from a COPY that reaches BAD through
either injected path (injections 2/3); and completion with the expected 24-word
payload footprint from abort after CLEAR rejection (16 words).  Seeds 1 and 8
change hclk/mem_clk periods and phase, so the healthy path is shown to be stable
across two legal timing models in simulation.

Not distinguishable:
- TARGET completion alone does not reveal whether the descriptor is still valid
  later; `target_valid` is sticky and is not continuously re-derived.
- CLEAR0 success establishes target validity only at the CLEAR validation edge.
  Because flags=0, it exercises no native access and cannot demonstrate that any
  128-byte target data was preserved or that a write path works.
- Empty COPY success establishes only the COPY target-valid gate and the child
  descriptor/clip result.  It does not reread the source from final DDR, does not
  write the destination, and therefore gives no evidence about data integrity,
  address decode, or DDR timing.
- Readiness faults 1/2 are invisible to this sequence because it issues no
  native requests; no timing cause can be inferred from their passing.
- There is no public `target_valid` CSR and no native request tap on the board.
  Absence of native traffic is not measured on hardware, so a passing CPU-visible
  run is not evidence that no internal request occurred.

## Injected counterexamples vs. measured physical cause

Injections 1/2/3 are `force` statements on `gpu.u_v1.u_pixels.target_valid` or
`gpu.u_v1.u_pixels.copy_bad` made from the protected bench.  They are logical
counterexamples that verify gate reachability and observability; they are not
observations of the R19 board and must not be presented as a diagnosis.  The
readiness faults likewise alter only bench readiness inputs.  The only measured
facts here are the protected simulation outcomes in the table.  The board facts
(CLEAR flags1 hang, successful CLEAR flags0, rejected COPY variants, intact
128-byte seed follow-up) remain source facts from `root_empty_copy_run_01`;
this simulation neither reproduces nor contradicts a physical mechanism.

A successful CLEAR only says the sticky `target_valid` was still high when
`bad_clear` was registered.  It does not prove the target fields were valid at
TARGET time or later: a stale/stuck bit, a lost packet, or a forced value would
all look identical.  Likewise, adding padding or waiting longer can make a run
"succeed" by moving the sample past queue/CDC latency, but that success is
equally consistent with a changed clock phase, a command that was never issued,
or a monitor artifact.  Padding is not a unique causal proof, and the protected
scoreboard fixes the expected 24-word footprint; delayed/extra success is not
evidence of a particular physical cause.

## Proposed experiments (existing bitstream only, at most two)

1. **This sequence (implemented and run).**  TARGET 16x1 at `0x12000020`, CLEAR
   flags=0, then empty COPY `w6=0` from valid source 16x1/stride 32, with seeds
   1/8, readiness faults 1/2, and injections 0/1/2/3.  It distinguishes CPU
   completion/reject outcomes and abort behaviour, but not native traffic,
   source data, or timing cause.

2. **Same prefix followed by a nonempty COPY and CPU readback.**  On the same
   R19 bitstream and existing firmware path, keep TARGET and CLEAR0 identical,
   change only the COPY extent to `w6=0x00100001` (16x1), let it complete within
   the existing bounded deadline, then perform the existing CPU follow-up read
   of the 128-byte seed.  Compare its rejected count and source bytes with the
   empty-COPY run.  This is the smallest existing-hardware way to separate a
   no-op COPY (no DDR read/write) from a real source-read/destination-write
   path; it still cannot establish a timing cause without native taps.
