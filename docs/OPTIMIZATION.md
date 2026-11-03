# Optimization, placement analysis and qualification

Status date: **3 November 2026**. Optimization in this project is evidence-led:
define the bottleneck, measure it, change one relevant variable, and validate
the resulting behavior. A faster demonstration, a lower LUT count or a positive
setup slack alone is not a complete qualification.

This page covers the FPGA workbench and the reasoning needed to use it. The
current Neo outcome and outstanding hardware diagnosis are documented in
[NEO_PORT.md](NEO_PORT.md). Routine Linux/game deployment is through SD autoboot
and SOFT-USB; JTAG is reserved for explicitly agreed diagnostics, not an
optimization loop that repeatedly reloads Linux or games.

## 1. Two complementary implementation flows

The local `optimizer/` package provides:

| Flow | What it does | Established limitation |
|---|---|---|
| Gowin analysis and experiment preparation | reads reports, compares timing/resources, proposes regional constraints, freezes and runs sequential candidates | Gowin still performs actual placement and routing |
| Yosys → nextpnr → Apicula | synthesizes and builds supported standalone examples with pinned tools | complete console support is not established |

The workbench is not a decoder/editor for Gowin's protected placement files,
and it is not an independent congestion-aware replacement for its router.
Its dashboard visualizes published evidence, not a reconstructed set of all
physical wires in the chip.

Implementation modules are under [optimizer/](../optimizer/README.md):
`reports.py`, `dashboard.py`, `placement.py`, `search.py`, `gowinflow.py`,
`openflow.py` and `runtime.py`. `optimize.py` is their command-line entry point.
The historical French README contains experiment chronology; dates and build
names in that chronology must not be read as the current board state.

## 2. Install and inspect the pinned open toolchain

The bootstrap uses local installation directories and checks archive hashes.
It does not replace system packages. Requirements include Linux x86-64,
Python 3, `curl`, disk space for the unpacked tools and a browser for the HTML
report. The commercial Gowin flow separately requires an appropriate installed
IDE and valid license.

```sh
python3 optimizer/bootstrap.py
python3 optimizer/bootstrap.py --component legacy-pack
python3 optimizer/optimize.py doctor --out optimizer/runs/doctor.json
```

The checked-in [toolchain lock](../optimizer/toolchain.lock.json) pins the
OSS CAD Suite release dated 2026-10-13, including the archive SHA-256. The
recorded installed versions for those experiments were Yosys 0.69+286,
nextpnr 0.11.1-59 and bundled Apicula 0.35.dev2. Treat those as recorded tool
identities, not a claim that they are the latest upstream releases.

The separate [legacy packer lock](../optimizer/apicula-legacy.lock.json) pins
Apicula 0.32. It was selected explicitly for the DSP example because the
installed newer packer failed on the GW5AST_138C `MULT12X12` support path.
There is no silent packer fallback. If an archive is already available, the
bootstrap's `--archive PATH` option avoids downloading another copy.

Tools live under `optimizer/.tools/`; generated runs live under
`optimizer/runs/`. Both are local build artifacts. `doctor` records versions
and whether the installed database includes the target device. It does not
test the board or certify that every device primitive is supported.

## 3. Read existing results without building or programming

An analysis-only example for the latest command-memory experiment is:

```sh
python3 optimizer/optimize.py report \
  tang/impl/console_neo_reject_20261102_r1 \
  tang/impl/console_neo_fifo_ff_20261102_r1 \
  tang/impl/console_neo_fifo_banked_20261103_r1 \
  --out optimizer/runs/my_fifo_comparison
```

Those directories are local experiment artifacts; use available build folders
in a fresh checkout. The command writes `comparison.json` and a standalone
`index.html`, without invoking synthesis, PNR or a programmer. The HTML works
locally without a hosted service or CDN.

The workbench reports:

- setup, hold, recovery, removal and pulse-width checks when present;
- WNS, TNS and violated endpoints/paths without conflating their counts;
- resource use and capacities;
- clocks, PRIMARY/LW/HCLK assignments and relevant warnings;
- detailed paths, logic delay, routing delay and loads when the report includes
  those arcs;
- hash/qualification information and optional explicitly supplied board results.

`--board-results PATH...` attaches hardware results by matching bitstream
SHA-256. Merely having a similarly named result file is not a match.

Statuses include `INCOMPLETE`, `BUILD_FAILED`, `UNVERIFIED`, `TIMING_FAIL` and
`TIMING_PASS`. They describe the available report/verification state, not a
universal release verdict. A specialized netlist-only diagnostic may remain
`UNVERIFIED` in the generic reader while showing real negative timing; its
dedicated receipt is still required. The current two FF candidates correctly
appear as `BUILD_FAILED` with no WNS/TNS because no timing report was produced.

The Gowin view shows cells present in published timing paths. It does not show
all placed cells. Its connecting lines are explanatory links, not actual
physical tracks. nextpnr can supply a fuller placement map, but its X/Y
coordinates are not silently translated into Gowin R/C coordinates.

## 4. Correct interpretation of timing and physical resources

Keep the following distinctions explicit:

| Quantity | Valid interpretation | Invalid shortcut |
|---|---|---|
| Setup slack | margin for a reported constrained path | all startup/reset/IO behavior is correct |
| Recovery/removal | constraints around asynchronous control release | a static reset level makes every reset transition safe |
| Missing path | not available in the inspected report/coverage | zero delay or positive slack |
| CLS usage | allocated physical cluster resources | percentage of routing channels occupied |
| Logical fanout | number of connected input pins | capacitance, physical distance or measured delay |
| LW/PRIMARY/HCLK label | selected distribution resource | proof that the signal is faulty |
| Route return code 0 and FS | the tool completed its flow | all timing and board tests passed |
| Fence/done advancement | command processing reached a completion event | no command rejection or data error |

A constraint must name the intended mapped objects, be active in the actual
report and use the correct clock relationships. A syntactically valid SDC is
not sufficient evidence of coverage. Source manifests, generated-clock periods,
exceptions, bounded CDC paths and actual PNR options are checked separately.

The project recorded a historical DDR clock-relation test in which rounding
13.333/3.333 ns differently changed whether an inter-domain path was reported.
That finding concerns constraint coverage; it must not be treated as a fix to
the hardware. `optimizer/check_constraint_semantics.py` contains the associated
test entry points. An asynchronous exception must never be introduced simply
to remove a negative path from the report.

The latest FF example is concrete: banking saved 1,144 LUT and 289 CLS, leaving
61,717/69,120 CLS allocated (89.29%). It reduced the total PR0004 count from
6,960 to 4,243, but neither report identifies the affected nets. The remaining
7,403 CLS do not prove sufficient routing capacity near the relevant cells.

## 5. Preparing a measured Gowin placement experiment

Start from a specific failing path and a frozen parent build. Preserve the
engine version, netlist, clocks, IO/bank configuration and unchanged constraints.
Write down the expected discriminating result before running another build.
Changing seeds repeatedly without such a question is not a diagnosis.

The workbench can propose a region for eligible LUT/DFF cells in published
critical paths:

```sh
python3 optimizer/optimize.py place \
  --build tang/impl/BUILD_NAME \
  --cst tang/impl/BUILD_NAME/source/tang/boards/neo/neo.cst \
  --region 'R[80:100]C[146:160]' --paths 2 \
  --out optimizer/runs/my_region/neo.cst
```

This is a template: replace `BUILD_NAME`, confirm its source layout and choose
a region justified by that build's report. The generator excludes protected
blocks, existing anchors and unsupported cell classes. Its geometric capacity
estimate is not a proof of legal placement or electrical routability.

To freeze a plan, supply an `experiments.json` with the intended candidate name,
placement/routing settings and optional CST, then run:

```sh
python3 optimizer/optimize.py plan --parent tang/impl/BUILD_NAME \
  --experiments experiments.json --out optimizer/runs/my_plan/plan.json
```

Review the plan and its input hashes first. The separate command
`python3 optimizer/optimize.py run optimizer/runs/my_plan/plan.json` actually
launches Gowin; it must not be mistaken for inspection. No such new route is
authorized merely by reading this document. A plan uses new output directories,
a lock and sequential execution; it must not interrupt another project's jobs.

`search` prepares up to three regional proposals; `--split-paths` separates
non-overlapping path groups. These are heuristics, not guaranteed improvements.
Inter-clock paths require CDC analysis before automated placement proposals.
There is no automatic hardware programming step in Workbench.

The historical Neo experiment chain uses `tools/route_console_neo.py`.
Pro Dock reports are readable, but that does not authorize the Neo routing
adapter to rebuild a protected Pro Dock reference. See
[board compatibility](../ARCHI/COMPATIBILITE_CARTES.md).

## 6. Open-flow examples and their limits

The two small projects under `optimizer/examples/` are suitable for exercising
the pinned Yosys/nextpnr/Apicula installation:

```sh
python3 optimizer/optimize.py open \
  --project optimizer/examples/neo_probe/project.json \
  --out optimizer/runs/my_probe --seeds 1
python3 optimizer/optimize.py open \
  --project optimizer/examples/neo_dsp/project.json \
  --out optimizer/runs/my_dsp --seeds 1
```

Unlike `report`, `open` really invokes synthesis, placement, routing and packing.
The earlier documented examples each produced bitstreams with two BSRAMs;
the explicit DSP example retained a `MULT12X12`. A multiplication expression
and an explicit pipelined DSP are different designs and cannot be compared
as a console FPS optimization.

A project JSON specifies top, device/family, sources, constraints, target
frequency and optionally required primitive cells and packer selection.
External ROMs, includes and encrypted IP are not imported magically.

The complete console is still outside the proven scope of this open flow:

- an attempted import of the complete N43 netlist stopped on protected vendor
  content; it was not replaced with black boxes to claim success;
- a reset/JTAG reproducer reached a BUFG allocation limitation in the installed
  nextpnr device database; that is not a measurement of the real chip's complete
  clock capacity;
- AE350, DDR3, USB PHY, IO/CDC and full timing coverage remain separate issues.

`COMPILED` on a small open-flow example therefore does not qualify the console's
hold/pulse/reset/CDC paths or prove that its hardware runs. The evidence and
tool versions are described in [the workbench record](../optimizer/README.md).

## 7. Graphics and software performance methodology

The optimization target is useful frame time, not the number of GPU features
enabled at once. Layers, sprites, geometry, blits and text accelerate different
work. A sprite can avoid repeated drawing of an unchanged object; it does not
remove all compositing or memory traffic. A 3D pipeline can reduce CPU geometry
work while still being limited by rasterization, transfers or scanout.

Separate at least:

1. input/simulation time and the amount of game state updated;
2. CPU geometry and command construction;
3. submitted command count/bytes, queue stalls and GPU completion;
4. memory transfers, cache maintenance, display fetch and underflow counters;
5. present/swap timing and measured frame cadence.

Use fractional or fixed-point motion and interpolate display positions when
logical game state advances on a grid. Sliding cards/tiles and progressive
alpha/lighting are presentation work, not a reason to change game rules or
inflate simulation rate. Batch text and drawing work where the existing API
permits it, retain unchanged assets and surfaces, and avoid unnecessary full
frame copies. Do not claim that an optimization exists merely because the
hardware could support it.

For a single uncompressed RGB565 source plane, 1280×720 at roughly 60.1 Hz
represents about 110.8 MB/s of visible pixel data, versus about 42.3 MB/s for
800×480 at roughly 55.0 Hz. These are illustrative lower-order traffic estimates,
not measured DDR throughput. Layers, overfetch, arbitration, blending, writes
and cache traffic add work. Scaling may reread source lines; a ×2 view does
not automatically divide memory traffic by four.

For SD/SPI performance, distinguish requested file bytes from raw sectors,
metadata reads, cached reads, commands, retries and inter-byte/inter-block gaps.
Configured SCK is not a scope measurement. UART logging, diagnostics and timer
reads must be measured as possible instrumentation overhead, not guessed away.
Keep SD observations separate from Neo routing diagnosis; the working Pro Dock
can be used as an explicit reference without silently changing its software.

## 8. Regression, cleanup and publication

Useful software checks for Workbench are:

```sh
python3 -m unittest discover -s optimizer/tests -v
node optimizer/tests/test_dashboard.cjs
```

The browser test may require an existing Playwright/Chrome installation, with
`PLAYWRIGHT_MODULE` and `CHROME_BIN` pointing to it. Do not convert a missing
dependency into a fictitious pass. A shared-source or builder change also
requires the project-level two-board regression command documented in
[NEO_PORT.md](NEO_PORT.md).

Every experiment should retain a concise test record: objective, exact inputs
and hashes, tool versions, commands, expected outcome, actual result, limits
and next discriminating observation. Keep failed builds and counterexamples
needed for the diagnosis. Delete only owned temporary artifacts whose use has
been checked; never sweep protected references or another session's work.

Code produced by this project is expected to remain modular, commented and at
most 1,000 physical lines per file. Vendor IP and immutable historical evidence
must be identified explicitly rather than rewritten or artificially split to
hide their size. Shared functionality has one maintained source plus board
profiles, not a fork per board.

Large netlists, encrypted IP, generated bitstreams and local experiment logs
may be absent from a public checkout. Publish the source/configuration needed
to reproduce work and a curated, hashed evidence bundle where redistribution
permits it. Never publish license files, credentials or machine secrets.
No source simulation, model review or report export should be advertised as
a successful hardware test that has not actually been performed.
