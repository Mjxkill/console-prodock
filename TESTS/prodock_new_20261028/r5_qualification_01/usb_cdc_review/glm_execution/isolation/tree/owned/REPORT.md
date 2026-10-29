# R5 counter-review — exact USB CDC / reset release analysis (GW5AST-138)

State reviewed: R5 frozen snapshot after SD bringup, pending. Evidence base: RTL
whose R5 and G22 SHA-256 agree (`SOURCE_PROVENANCE.json`), selected
post-layout named-primitive taps (`netlist_taps.vo`), the parsed Gowin timing
report (`timing.json`, tool V1.9.12.03, dated 2026-10-29 07:04) and the R5
diagnostic SDC (`timing_reports.sdc`, whose hash differs from G22). All values
below were machine-derived by `owned/inspect_cdc.py` from these exact bytes;
the fixed validator re-derives them independently. No RTL patch, no
constraint edit, no Gowin run, no hardware.

## 1. The exact reset-release chain (what makes `rst_usb` what it is)

`console_top.v:168` declares `rst_usb`; three cascaded `usb_reset_release`
instances (`usb_reset_release.v:4-26`) produce and qualify it:

- `u_usb_ref_start` at `console_top.v:169-170`: `clk`=50 MHz board clock,
  holds `pll_b_reset` 104000 cycles (2.08 ms) after `pll_f_lock`.
- `u_usb_phy_start` at `console_top.v:178-179`: `locked = pll_f_lock &
  pll_b_lock & ~pll_b_reset`, yields `phy_lock_reset`.
- `u_usb_controller_start` at `console_top.v:180-181`: **`clk(phy_clk)`**,
  `locked(~phy_lock_reset)`, `HOLD_CYCLES=64`, output **`rst_usb`**. This is
  what pins `reset_source_clock='phy_clk'`.

`usb_reset_release.v:14-26` asserts its reset **asynchronously** on
`negedge locked` (works with a stopped clock) and de-asserts it only
**registered**, after 2 synchronizer stages plus `HOLD_CYCLES` stable clock
cycles. The netlist confirms the mapped behaviour for the controller stage:
`netlist_taps.vo:28-35` — `DFFPE u_usb_controller_start/reset_s4`,
`CLK(phy_clk)`, `PRESET(phy_lock_reset)`, `INIT=1'b1`, `Q(rst_usb)`:
async preset (assertion), registered D-input release through
`u_usb_controller_start/n29_9`. `console_top.v:202` aliases
`RESET = rst_usb`, and `console_top.v:205` forms
`usb_app_reset = RESET | usb_busreset` (all inside the phy_clk domain).

The three "worst-path" reset nets therefore all exist and are used exactly as
the RTL says; the question is only their *fanout discipline*.

## 2. The four worst paths, classified (timing.json + taps)

| # | Report arm | Slack (ns) | Path (from → to) | Clocks | Classification |
|---|-----------|-----------:|------------------|--------|----------------|
| 1 | setup | −7.789 | `.../u_usb_init/s_highspeed_s0/Q → u_usb_msc_port/hs_s_0_s0/D` | PHY_CLKOUT → bus80_clk | **intended two-stage synchronizer entrance** (path 1) |
| 2 | hold | −3.451 | `wr_gray_1_s0/Q → wr_gray_s1_1_s0/D` | bus80_clk → PHY_CLKOUT | **intended Grey-pointer synchronizer entrance** (path 2) |
| 3 | recovery | −12.298 | `u_usb_controller_start/reset_s4/Q → gather_7_s0/CLEAR` | PHY_CLKOUT → bus80_clk | **unsynchronized reset fanout** (path 3) |
| 4 | removal | −2.265 | `u_usb_phy_start/reset_s4/Q → u_usb_controller_start/count_1_s1/CLEAR` | clk50 → PHY_CLKOUT | **unsynchronized reset release across domains, but re-qualified locally** (path 4) |

These are the same four paths the review contract names, so the report's
endpoint list is not a symptom of a different, unknown problem.

### Path 1 — `hs_s[0]` data sync (`timing.json paths.setup.worst`)

`netlist_taps.vo:10-17`: `DFFCE hs_s_0_s0`, `D = usb_highspeed` raw output of
the phy_clk-domain register `s_highspeed_s0` (the timing report's start
point), `CLK(vid_hclk)`, `CE(VCC)`, `CLEAR(GND)`. `netlist_taps.vo:19-26`:
second stage `hs_s_1_s0` samples `hs_s[0]`. RTL `usb_msc_port.v:92`
(2-bit declaration, ASYNC_REG) and `usb_msc_port.v:105`
(`hs_s <= {hs_s[0], highspeed}` on `posedge hclk`, *no reset branch*) agree.
**It is a genuine two-stage synchronizer**: first synchronizer stage, cleanly
clocked, reset-pin intentionally tied off. `usb_highspeed` changes only at
enumeration, then is stable. The −7.789 ns setup slack is the STA of an
asynchronous crossing which the synchronizer exists precisely to absorb —
it is **not a proven failure**. But this must not be read as “CDC therefore
false path”: in the R5 diagnostic build this path was *timed*, not waived
(see §5/§6), and any waiver must be restricted to the synchronizer entrance
pins, with the two-stage structure locked in (taps above are that proof).

### Path 2 — `wr_gray` pointer sync (`timing.json paths.hold.worst`)

`netlist_taps.vo:55-62`: source pointer reg `wr_gray_1_s0` clocked on
`vid_hclk` with `CE(accept)`; `netlist_taps.vo:64-80`: `wr_gray_s1_1_s0`
samples `wr_gray[1]` on `phy_clk`, and `wr_gray_s2_1_s0` samples `wr_gray_s1`
— two phy_clk stages, `CE(VCC)`. RTL `ddr_dcfifo.v:36-43` (binary+Gray
pointers, `bin2gray`/`gray2bin`), `ddr_dcfifo.v:73` (encode before the
crossing), `ddr_dcfifo.v:101` (`wr_gray_s1 <= wr_gray; wr_gray_s2 <=
wr_gray_s1;`) and `ddr_dcfifo.v:84` (decode only from `wr_gray_s2`) prove the
standard Gray two-flop crossing on `usb_idle_trace/u_commands` (32×2 FIFO,
`usb_idle_trace.v:45-47`; the same `ddr_dcfifo` also moves MSC bulk bytes in
`usb_msc_port.v:279-287` and `352-359`).
**Again a real two-stage synchronizer first stage.** Hold between unrelated
clocks is not meant to be met; the −3.451 ns is the same non-waived
asynchronous crossing. One mapper-level observation, not a bug we may patch:
RTL `ddr_dcfifo.v:16/25` comments say `wr_rst`/`rd_rst` are **synchronous**
to their domain (`always @(posedge rd_clk) if (rd_rst)`, `ddr_dcfifo.v:97-101`),
but the tap places `RESET(n5312_3)` — the `ureset = !ur[2] || !hu[1]`
(`usb_idle_trace.v:32`) net, produced by phy_clk-domain registers — on the
**asynchronous** RESET pin of both sync stages (`netlist_taps.vo:68,77`).
Assertion direction is safe (hold-reset), and the releasing net is registered
in the target domain, so per-domain alignment is preserved; nonetheless the
RTL-vs-netlist reset-semantics difference should be checked once (§4, U4).

### Path 3 — `rst_usb` raw into the `vid_hclk` async clear fanout

This is the structural finding. `netlist_taps.vo:1-8`:
`DFFCE u_usb_msc_port/gather_7_s0`, `CLK(vid_hclk)`,
`CE(\u_usb_msc_port/gather_7_10)`, `CLEAR(n6_5)` — and `netlist_taps.vo:82-87`:
`LUT2 \u_usb_idle_trace/n6_s1` with `I0(rst_usb)`, `I1(vid_hrstn)`,
`INIT=4'hB`. `raw_clear_lut_init='B'`; bits indexed by (I1,I0) give
`[1,1,0,1]` — i.e. `F = !(I1 & !I0) = !(vid_hrstn && !rst_usb)`. That is
exactly the RTL async-clear expression of both USB AHB slaves:
`console_top.v:137` and `:121` (`.reset_n(vid_hrstn && !rst_usb)`), used with
`negedge reset_n` in every `usb_msc_port`/`usb_idle_trace` async block (e.g.
`usb_msc_port.v:76,79,129,204`; the `gather/gathered` registers themselves,
`usb_msc_port.v:209-241`). So `rst_usb` — released, remember, on *phy_clk*
edges — crosses to `vid_hclk` **raw**: there is no vid_hclk register between
`u_usb_controller_start/reset_s4` and the tapped CLEAR pin. That is why
`gather_raw_async_reset=True`, `gather_clock='vid_hclk'`,
`reset_source_clock='phy_clk'`, and why the tool found a **−12.298 ns
recovery** path from `rst_usb` to `gather_7_s0/CLEAR` — the concrete
worst-path realisation of this unsynchronized fanout, not an abstraction.

Two mitigations are *present and proved by the netlist*; a third is only an
argument:

- (proved) The same clear expression feeds the `hr/uh` and `ur/hu` local
  release guards of both modules below, so the guard registers are released
  in the same event, and the local synchronous reset continues to dominate
  the datapath for several further cycles (see §3).
- (proved) `gather[7]`'s async CLEAR overrides its CE regardless of the D/CE
  state (`DFFCE` semantics), so the datapath cannot “win” against a held
  clear.
- (argument, not proof) after raw release, `hreset` remains 1 for ≥2 vid_hclk
  cycles (`!hr[2] || !uh[1]`, `usb_msc_port.v:143` — `hr` needs 3 shifts,
  `uh[1]` needs `ur[2]` (3 phy_clk edges) plus 2 shifts), so a metastable
  release of any gathered bit is re-cleared synchronously at the following
  edges. This is a behaviour argument from RTL reading; it is **not** an STA
  recovery/removal waiver, and digital simulation cannot prove
  metastability safety.

### Path 4 — `phy_lock_reset` → `count CLEAR` / `rst_usb PRESET` (phy_clk)

`netlist_taps.vo:46-53`: `u_usb_phy_start/reset_s4` (`CLK(clk_d)` = the
50 MHz board clock net, async PRESET from `n6_5`, `INIT=1'b1`) produces
`phy_lock_reset`; it drives the async `CLEAR` of the hold counter
(`netlist_taps.vo:37-44`, `count_1_s1`, `CLK(phy_clk)`) and the async
`PRESET` of `rst_usb` (`netlist_taps.vo:28-35`). The release edge of
`phy_lock_reset` is a 50 MHz-domain edge; the sampling registers are on
`phy_clk` — hence the −2.265 ns **removal** (clk50 → PHY_CLKOUT) at exactly
the review's fourth worst path. The structure is deliberately safer than a
bare crossing: assertion of the whole chain is asynchronous (safe direction:
“lock lost ⇒ everything stays in reset”, `usb_reset_release.v:14-19`), and
`rst_usb`'s release itself is re-qualified *in the phy_clk domain* (2 sync +
64 hold, `console_top.v:180`): if a PRESET/CLEAR release lands inside a
phy_clk recovery window and lets `rst_usb`/`count` misbehave for one cycle,
the next phy_clk edge re-asserts reset while `!lock_sync[1]`
(`usb_reset_release.v:15-24`), and the ±1-cycle counting uncertainty is
harmless against `HOLD_CYCLES=64`. Again: bounded *and re-qualified*, but
not — at STA level — waived in the R5 data.

## 3. Local `hr`/`ur` guards, and the CE/D picture

`usb_msc_port.v:74-83` declares, with `ASYNC_REG` and `syn_preserve`,
`hr/ur` (3-bit release counters) and `hu/uh` (2-bit cross-observation
shifters); `usb_msc_port.v:78` samples `ur[2]` into hclk, `:81` samples
`hr[2]` into phy_clk; the local resets are `usb_msc_port.v:143-144`:
`hreset = !hr[2] || !uh[1] || busrst_s[1] || quiet_h || !owner_h` and
`ureset = ubase || uflush || !owner_u` with `ubase = !ur[2] || !hu[1] ||
bus_reset` (line 125). `usb_idle_trace.v:24-32` contains the identical idiom.
Consequence: **each domain's local reset is held until the *other* clock is
observed restarting after `reset_n`** — the FIFO/PURGE machinery
(`usb_msc_port.v:279-287, 352-359`), the AHB window, and the trace
(`usb_idle_trace.v:45-53`) ride the *guarded* local resets, not `rst_usb`
raw. This is why the guard is real (`msc_local_release_guard=True`) and why
releasing `rst_usb` badly does not immediately corrupt the dual-clock FIFOs.

CE/D picture, per the review's instruction to include unconditionally
updated control registers: all control registers in `usb_msc_port` are
updated every cycle of their clock without CE gating
(`usb_msc_port.v:95-106` samplers — no reset branch at all; `:128-141`
`owner_u/handback`; `:204+` the whole AHB block; `usb_idle_trace.v:90` the
UTMI tap). Since `DFFCE.CLEAR` (and `DFFPE.PRESET`, `DFFRE.RESET`) override
CE, every one of these registers is exposed to the raw-clear release event
regardless of CE/D; the protection discussed in §2 path 3 comes from the
*synchronous* local reset hold, not from CE gating. The tapped `hs_s` flip-
flops have `CE(VCC)` and `CLEAR(GND)` (`netlist_taps.vo:13,14,22,23`): they
take no reset at all, only `INIT`, and start sampling — consistent with
“passive status observer”, since they only feed the AHB status word
(`usb_msc_port.v:264`).

## 4. What is proved, what is only a concern

**Proved by these exact sources (digital evidence):** the exact four worst
path endpoints; the existence and true two-stage structure of the `hs_s` and
`wr_gray` synchronizers; Gray encoding before the `wr_gray` crossing and
decode after two stages; the raw (unbuffered-by-any-register) path
`rst_usb → LUT2(4'hB) → vid_hclk async CLEAR fanout` with `vid_hclk`/`phy_clk`
clocks; the async-assert / registered-release semantics of
`usb_reset_release` and all three instances; the `hr/ur` cross-view local
release guards in both USB AHB slaves; no CE gating anywhere that would
qualify a raw-clear release; the R5 timing report shows all four arms with
negative worst slack and 218 setup / 185 hold violated endpoints
(`timing.json summary`), while provenance states `timing_closed: false`,
`hardware_validated: false`, and the R5 SDC differs from the G22 one.

**Not proved (and not provable this way):** freedom from metastability,
recovery/removal safety of `rst_usb` into `vid_hclk`, or of `phy_lock_reset`/
`usb_app_reset` into `phy_clk` registers; digital simulations, gate-level or
not, cannot prove that (contract constraint). The local guards *protect
operation*; they do **not automatically waive** the asynchronous
recovery/removal requirements, and none of this review licenses saying “CDC,
therefore false path”.

## 5. Uncertainty (explicit)

- **U1 — SDC waiver mechanics.** `timing_reports.sdc:11` groups
  `PHY_CLKOUT/sclk/fclk_960M` as mutually async, and `:21` groups
  `clk50+sclk / bus80 / …`; sclk is created by `:3` with `-add` on an
  internal PHY net. Yet the R5 report *times* PHY_CLKOUT↔bus80_clk paths
  (worst setup/hold/recovery). Either the `-add`/hierarchical `sclk`
  reference invalidated that `set_clock_groups` statement, or Gowin's group
  semantics here are not transitive. Without a Gowin run (out of scope) this
  cannot be discriminated from the snapshot alone.
- **U2 — `VID_HCLK` has no clock definition in the R5 SDC** (only `clk50`,
  the PLL outputs, SoC clocks, `:2-19`); the tool labels all `vid_hclk`
  endpoints with `bus80_clk` (clock pairs in `timing.json`). Is `vid_hclk`
  `bus80_clk` (SDC comment `console_top.v` says HCLK; history says 50 MHz)
  or a divided derived clock? Unknown from the snapshot.
- **U3 — full raw-clear fanout depth.** The tap file is a bounded, selected
  extraction (`SOURCE_PROVENANCE.json`: "Exact selected named primitive
  blocks…; no new logic"). `gather_7_s0` proves the class; the same LUT
  output almost certainly feeds `hr/uh/every async-cleared reg` of
  `u_usb_msc_port` and `u_usb_idle_trace` (RTL says so), but the complete
  fanout list and its STA coverage count (of 218/185 endpoints) are not in
  the snapshot.
- **U4 — synchronous-vs-async reset mapping.** RTL `ddr_dcfifo.v:16/25/64-65,
  97-101` declares the FIFO side resets synchronous; the tap shows `DFFRE
  .RESET` pins wired to `hreset`/`n5312_3` (`netlist_taps.vo:59,68,77`) and
  the raw `n6_5` on `gather_7_s0`. Either the mapper chose the async pin for
  a synchronously-declared reset (semantic change) or the RTL's reset net
  (`reset_n(vid_hrstn && !rst_usb)`, `console_top.v:121,137`) is genuinely
  async by `negedge reset_n` in `usb_msc_port.v:76/79/129` and only the
  `ddr_dcfifo`-internal resets are the synchronous part. Both readings are
  consistent with the taps shown; distinguishing them needs the full netlist.
- **U5 — report-internal inconsistency.** `timing.json` says 218 setup +
  185 hold violated endpoints with negative minima, yet `per_clock_tns` is
  `0.000` for every clock. The endpoint counts likely include cross-clock
  paths (exactly the ones a correct exception set would remove); cannot be
  reconciled from the JSON alone.
- **U6 — G22 comparison out of reach.** The G22-closed SDC (hash
  `beb5fce…`) is not in the snapshot; whether the closed build waived these
  four paths, restructured the reset fanout, or simply used a working
  exception syntax is unknown here.

## 6. Proposed discriminating controls (only after bring-up; no patch)

1. **SDC/group verification query (no design change):** re-run static
   timing with one added query report listing paths per clock pair before
   and after moving `sclk` creation earlier (or creating it without `-add`)
   in a *copy* of the diagnostic SDC — if PHY↔bus80 endpoints disappear from
   setup/hold (218/185 counts collapse), U1 is resolved; the intended async
   groups are honored. Keep the synchronizer taps (`hs_s`, `wr_gray_s*`) as
   the structural proof that no waiver hides a missing synchronizer.
2. **Recovery/removal audit:** for the raw-clear class, request a
   `report_timing -recovery/-removal` scoped to the async
   CLEAR/RESET/PRESET pins reachable from `rst_usb`/`phy_lock_reset`/`n6_5`,
   in the G22 build, to enumerate the real fanout (resolves U3) and to
   separate single-clock-constrained pins (already clean) from
   cross-domain ones that need a documented exception with the guard as
   justification (§2.3/3, not a blanket false path).
3. **Reset-domain crossing gate-sim (digital, scoped):** a short gate-level
   simulation whose only claim is functional survival — sweep the
   `rst_usb` release instant relative to `vid_hclk` edges (and
   `phy_lock_reset` vs `phy_clk`), asserting (a) `hreset/ureset` hold local
   state for ≥2 further cycles, (b) `gather/gathered` return to 0, (c)
   `usb_msc_port` +0 status (`usb_msc_port.v:264`) never reports `lost`
   (bit7) from a reset event alone. It cannot prove metastability freedom —
   it bounds the functional consequence (contract wording).
4. **Hardware observables (post bring-up):** repeated bus-reset/lock-drop
   cycles while watching `msc` AHB +04 state register bits (bit2 bus reset,
   bit3 BOT reset, bit7 lost — `usb_msc_port.v:264`/window header `:9-11`,
   the `usb_idle_trace` `resets/sofs/bad_response/first_fault` counters
   (`usb_idle_trace.v` command +0x08/0x0c), and LED0/LED2/LED3
   (`console_top.v:225-229`). Correlate any `first_fault` timestamp with the
   reset events; a repeated, timing-correlated pattern is what would convert
   the §2.3/§2.4 *concerns* into observed failures — not a digital test
   alone.
5. **Constraint review item (U2):** pin down `vid_hclk`'s actual source and
   either give it its own `create_generated_clock` or document it as
   `bus80_clk`, so future reports label the `hs_s`/`gather` endpoints with
   the clock the review actually reasons about.

## 7. Conclusion

The R5 snapshot contains three genuine, proved two-stage synchronizers
(`hs_s`, `wr_gray`, plus the `rd_gray` mirror and the `cdc_word u_sent`
helper, `usb_msc_port.v:343` whose first stages are what the timing report
flags — those flags are the *absence of working exceptions in the R5
diagnostic SDC*, not failures of the synchronizers. Separately, and not
excused by those synchronizers, `rst_usb` (phy_clk-domain release) and
`phy_lock_reset` (clk50-domain release) fan out raw into asynchronous
CLEAR/PRESET pins of `vid_hclk` and `phy_clk` registers respectively
(taps: `gather_7_s0/CLEAR`, `count_1_s1/CLEAR`, `reset_s4/PRESET`); that is
a real, unwaived reset-domain-crossing concern, partially and functionally
protected by the local `hr/ur` cross-view guards and by `usb_reset_release`'s
registered, in-domain re-qualification — a concern, not a proven failure.
Timing is not closed in this snapshot (`timing_closed=false`), the R5 SDC is
not the G22 one, and nothing here substitutes for the post-bring-up
constraint/hardware checks listed in §6.