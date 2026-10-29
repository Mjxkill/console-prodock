# R4 failure analysis and minimal reuse plan

## Scope

Bounded independent analysis. Inputs were `context/facts.json`, `context/*_pnr.log`,
`context/*_cmd.do`, `context/*_timing.sdc`, `context/*_build.tcl`, the official
Tcl excerpt, and `context/resume_sd_fpga.py`. No Gowin tool, network, hardware,
or frozen context was started or modified. This report describes established
facts and unknowns only; it does not certify timing or hardware readiness.

## Observed stage results

| Run | Return code | Routed to STA? | Bitstream | Post-route `.vo` | Post-route TR/SDF |
|---|---:|---|---:|---:|---:|
| R2 | -11 | R2 log reaches `Running timing analysis...` then stops | no | no | no |
| R3 | 0 | yes, `Timing analysis completed` | yes | yes | yes |
| R4 | 1 | R4 log reaches `Running timing analysis...` then stops | no | no | no |

R4 therefore fails after placement/routing, during or before completion of
static timing analysis/output generation. It does not produce the files needed for
post-route simulation, timing review, or hardware programming.

## Factual deltas

| Item | R2 | R3 | R4 |
|---|---|---|---|
| Netlist (`.vg`) SHA-256 | `68939b82...` | `68939b82...` (same as R2) | `6358e266...` (different) |
| SDC SHA-256 | `beb5fce8...` | `f50b4cf3...` (same as R4) | `f50b4cf3...` |
| Custom `report_timing` queries | 5 | 0 | 0 |
| Incremental anchor (`-inc_pnr`) | `reference_g22r0.pr` | `reference_sd_r2.pr` | `reference_g22r0.pr` |
| Routed `.pr` size | 335,301,361 | 390,381,804 | 335,303,259 |
| Design `.db` SHA-256 | `327866ac...` | `b8c2ce1c...` | `327866ac...` |

## What is established

1. All three runs complete placement and routing through Routing Phase 3 and then
   enter `Running timing analysis...`.
2. R4 creates no `.fs`, `.vo`, `.tr`, or `.sdf`; R3 creates all of them. R4's
   failure is before post-route artifact generation.
3. R3 and R4 share the same SDC, including removal of the five extra
   `report_timing` queries that R2 retained. Thus R3's success cannot be
   attributed solely to deleting report queries: R4 keeps those queries absent
   and still fails.
4. R3 changed two relevant variables at once: it removed report queries and
   switched the incremental anchor from `reference_g22r0.pr` to
   `reference_sd_r2.pr`. The confounded change prevents a single-factor root
   cause.
5. R4 retains R2's older `reference_g22r0.pr` anchor but uses a resynthesized,
   differently hashed netlist. That configuration still routes but fails at STA.
6. R2 returns -11; R4 returns 1. These are different return codes. The
   evidence does not establish that R4 hit the same internal crash as R2, nor
   that R4 is only a timing failure.
7. `cmd.do` normalization leaves stage paths canonicalized, so the remaining
   meaningful differences are the netlist, SDC query count, and incremental
   anchor.
8. No run is marked hardware-validated. R3 is a successful PnR result, not proof
   of correct FPGA timing or hardware behavior.

## What is not established

- Whether R4 encountered an internal crash or a normal STA/BIT tool error. The
  available evidence has no accessible `coredumpctl` output or matching
  `journalctl` record, but absence of such evidence is not proof that no
  internal crash happened.
- Whether FPGA timing passes. R4 has no timing report or SDF.
- Whether the `reference_g22r0.pr` anchor is incompatible with the R4 netlist.
- Whether the R4 netlist change is functionally significant or merely a build
  artifact difference.
- The exact STA query, clock, path, or constraint responsible for the failure.
- The content of any Gowin-internal STA diagnostic that may have been intended
  for the `.rpt.txt` file.

`root_cause_proven` is therefore false.

## R3 hypothesis review

`resume_sd_fpga.py` removed five `report_timing` queries and concluded that the
crash may occur while printing extra path reports, but explicitly called that
hypothesis unestablished. R4's outcome weakens it: R4 also has zero custom
queries and still fails. The hypothesis is not disproven, but it is not sufficient.
The anchor change in R3 remains an uncontrolled co-variable.

## Old resume helper limitations

`context/resume_sd_fpga.py` is R2-specific and must not be reused blindly for
R4:

- It hard-codes `prodock_sd_boot_20261028_r2` as source and
  `prodock_sd_boot_20261028_r3` as destination.
- It asserts the old R2 return code -11 and the absence of R2 bitstream.
- It assumes five removed report queries and asserts exactly five.
- It copies `rtl` and `source`, generates assumptions from R2's build driver,
  and uses R2's routed database as the new anchor.
- It was written to create R3, not to diagnose or reuse R4.

For R4, a new harness must instead bind explicitly to R4's exact netlist,
incremental PR, CST, SDC, log, and hashes, with no implicit source/destination or
query count.

## Minimal reuse plan using R4 VG and R4 PR

Goal: determine whether R4 can complete timing without synthesis, RTL changes,
STA waiver, or hardware. Reuse the existing R4 netlist and PnR database as
immutable inputs.

1. Create an isolated copy/read-only mount of the R4 build artifacts. Do not
   modify `R4_build.tcl`, `R4_cmd.do`, RTL, CST, or SDC.
2. Record immutable hashes before any run: `.vg` `6358e266...`, `.pr`
   `7f6a7938...`, SDC `f50b4cf3...`, CST as supplied.
3. Repeat the exact R4 PnR command once in the isolated copy, preserving the
   full tool log, timestamp, return code, and any core/coredump file metadata.
   This tests whether rc1 is deterministic.
4. If it completes, collect `.fs`, `.vo`, `.tr`, `.sdf`, hashes, and the timing
   report; compare with R3 before any hardware claim.
5. If it still returns 1, run a controlled PnR-only matrix while keeping every
   constraint and report intact:
   - R4 `.vg` + R4 `.pr` (native repeat, already failed once)
   - R4 `.vg` + `reference_sd_r2.pr` (R3's successful anchor style)
   - R3 `.vg` + R3 `.pr` (known-good baseline)
   - R3 `.vg` + `reference_g22r0.pr` (anchor-only test, if tool permits)
   No synthesis or RTL edits are allowed; only `-inc_pnr` changes.
6. For every failed run, preserve logs and report whether completion stopped at
   placement, routing, STA, bitstream, or power analysis. Do not waive STA.
7. Do not program hardware or call timing success until R4 has a complete `.tr`,
   `.sdf`, `.vo`, bitstream, and independent timing review.
8. Root decides whether to restart or re-run, because no definitive crash
   record exists. This report only supplies the bounded evidence and a safe
   experiment plan.

## Bottom line

R4 is not yet a usable post-route result. The evidence shows it reached STA and
did not emit the required post-route artifacts. R3's success is confounded by
simultaneous query and anchor changes. A deterministic rerun plus a small
incremental-anchor matrix on the immutable R4 netlist is the safest next step.