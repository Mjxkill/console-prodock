# Gowin Workbench

Gowin Workbench provides reproducible FPGA experiments, timing-report analysis
and interactive placement comparisons. It complements the Gowin toolchain and
also includes a separate Yosys → nextpnr → Apicula flow for supported standalone
designs.

It does not program a board. A placement proposal is an experiment to measure,
not a prediction of timing closure. Simulation, synthesis, static timing and
hardware results remain separate throughout the reports.

For the current console status, see [Neo port](../docs/NEO_PORT.md) and
[optimization](../docs/OPTIMIZATION.md). For the selected historical FPGA images
and their reproducible input packages, see [FPGA releases](../releases/fpga/README.md).
The Neo console is still under diagnosis; the open-source flow has not been
shown to build the complete AE350/DDR3/USB console.

## Capabilities

- Install pinned tool versions with archive-size and SHA-256 checks.
- Synthesize standalone RTL with Yosys, place and route with nextpnr, and pack
  bitstreams with Apicula, preserving commands and seed-specific results.
- Check that expected primitives are present in the mapped design.
- Read Gowin setup, hold, recovery, removal and pulse-width reports, including
  WNS, TNS, per-clock violations, resources, detailed arcs and fanout.
- Separate logic, routing and clock-to-Q contributions for published paths.
- Inspect PRIMARY/LW/HCLK allocation and clock-constraint warnings, including
  CT1018/PR1014. An LW allocation alone is not evidence of a functional defect.
- Group comparable runs by netlist, timing constraints, pins, device and tool.
  A frequency change creates a different comparison group.
- Export a self-contained HTML dashboard with filters, path selection, resource
  comparisons, placement views and a graphical candidate-region selector.
- Propose regional `INS_LOC` constraints for critical LUT/DFF cells while
  preserving pin constraints and existing placement anchors.
- Prepare up to three region candidates and execute a frozen, sequential Neo
  Gowin experiment plan with hashes, logs and qualification checks.
- Retain failures and incomplete runs. No hardware loading is performed.

## Installation

Requirements: a recent system Python, `curl`, and Linux x86-64. Installation is
local to this directory and does not modify system packages.

```sh
python3 optimizer/bootstrap.py
python3 optimizer/bootstrap.py --component legacy-pack
python3 optimizer/optimize.py doctor --out optimizer/runs/doctor.json
```

The pinned OSS CAD Suite release is **2026-10-13**: Yosys
`0.69+286 / 37f25dae9`, nextpnr `0.11.1-59 / 837d0eed`, and bundled Apicula
`0.35.dev2+g834c9e891`. The optional Apicula **0.32** installation is separate.
It is selected explicitly for the DSP example because the bundled packer failed
on the missing `get_MULT12X12_fuses` support for `GW5AST_138C` after routing.
There is no silent fallback between packer versions.

[toolchain.lock.json](toolchain.lock.json) and
[apicula-legacy.lock.json](apicula-legacy.lock.json) record downloads, sizes,
hashes and origins. `--archive PATH` accepts an already downloaded archive.
Tools live in `.tools/` and generated runs in `runs/`; both are ignored by Git.
Allow several gigabytes for installation and generated files.

## Standalone open-source builds

Run the included examples from the repository root:

```sh
python3 optimizer/optimize.py open \
  --project optimizer/examples/neo_probe/project.json \
  --out optimizer/runs/probe_new --seeds 1 7 42

python3 optimizer/optimize.py open \
  --project optimizer/examples/neo_dsp/project.json \
  --out optimizer/runs/dsp_new --seeds 1 7 42
```

`neo_probe` infers RAM and multiplies signed 18-bit values. With the pinned
Yosys version that expression uses LUTs rather than an inferred GW5A DSP.
`neo_dsp` explicitly instantiates a pipelined `MULT12X12` and selects
`packer: legacy-0.32`. Historical builds produced bitstreams for all three
seeds, with two BSRAMs in each example and one `MULT12X12` in the DSP example.

The reported nextpnr Fmax ranges were 95.329–96.927 MHz and
350.754–378.644 MHz, respectively, against a 50 MHz constraint. These designs
have different functions and latencies: the figures are not a console speedup
or a measured operating frequency on hardware.

A project JSON specifies `top`, `device`, `family`, `synth_family`, `sources`,
`cst`, `frequency_mhz`, and optionally `sdc`, `required_cells` and `packer`.
Paths are relative to the project. The adapter accepts standalone
Verilog/SystemVerilog; it does not automatically import source includes,
external ROM files or encrypted vendor IP.

Exploration options are `--placer heap|sa`, `--router router1|router2`,
`--seeds ...` and `--timeout SECONDS`. Each build needs a new output directory.
Outputs include copied sources, JSON netlists, commands, durations, logs,
placement data and a `design.fs` for each successful seed.

`COMPILED` means that this flow finished, generated a bitstream, and reported
Fmax above its requested constraints. It is not a substitute for the console's
hold, pulse-width, CDC or hardware validation.

## Read and compare reports

The following example uses historical complete build directories. Substitute
ones available locally; these old generated directories are not installed by
a fresh clone.

```sh
python3 optimizer/optimize.py report \
  tang/impl/console_neo_n18 tang/impl/console_neo_n18r2 \
  optimizer/runs/neo_probe_001 optimizer/runs/neo_dsp_legacy_002 \
  --out optimizer/runs/dashboard
```

Open `optimizer/runs/dashboard/index.html` in a browser. No server, account,
CDN or network access is required. `comparison.json` retains the full parsed
path set; the HTML displays every negative path and up to 40 positive paths
per build.

The Gowin map displays **only cells mentioned in published timing paths**.
The nextpnr view can show all placed cells. Drawn edges connect cells; they
are not detailed physical routing tracks. nextpnr X/Y coordinates are not
converted to Gowin row/column coordinates. Proprietary `.p` and `.pr` placement
files are neither decoded nor edited.

Gowin report states are `INCOMPLETE`, `BUILD_FAILED`, `UNVERIFIED`,
`TIMING_FAIL` and `TIMING_PASS`. Truncated reports, changed sources, uncovered
constraints and routing errors must not become `TIMING_PASS`. Project-specific
qualification is displayed separately and its hashes are checked.

The generic reader also refuses `TIMING_PASS` if any of the four detailed
setup/hold/recovery/removal analyses is empty. A design without a reset can be
legitimate, but the reader does not infer the structural justification for
missing reset checks. A completed run is not necessarily a qualified one.

To attach hardware evidence, add `--board-results path/to/result.json ...` to
`report`. Each result must contain `bitstream_sha256` and a Boolean `passed`.
The hash must match a bitstream in the report; directory names are not used as
identity. Contradictory results remain visible. Reading evidence does not
perform a hardware operation or extend the scope of the supplied tests.

## Propose and measure placement with Gowin

This historical example reproduces the regional constraint investigated for
N18; it requires the original complete parent build:

```sh
python3 optimizer/optimize.py place \
  --build tang/impl/console_neo_n18 \
  --cst tang/impl/console_neo_n18/source/tang/boards/neo/neo.cst \
  --region 'R[80:100]C[146:160]' --paths 2 \
  --out optimizer/runs/new_region/neo.cst
```

Selection excludes DSPs, BSRAMs, PLLs, I/O, existing anchors and internal
`u_soc/` / `u_usb_` cells. Available site counts are geometric bounds only;
Gowin still determines electrical and placement legality. The adjacent JSON
records selected cells and their previous positions.

Create an `experiments.json` array, for example:

```json
[
  {"name":"console_neo_region_trial","place":3,"route":2,"replicate":0,
   "cst":"optimizer/runs/new_region/neo.cst"},
  {"name":"console_neo_strategy_trial","place":4,"route":2,"replicate":0}
]
```

```sh
python3 optimizer/optimize.py plan --parent tang/impl/console_neo_n18 \
  --experiments experiments.json --out optimizer/runs/new_region/plan.json
python3 optimizer/optimize.py run optimizer/runs/new_region/plan.json
```

The plan freezes the netlist, CST, SDC, manifest, TCL and build/qualification
scripts before execution. The router rechecks the parent's frozen sources.
Each experiment creates a new `tang/impl/NAME` directory. A lock prevents
concurrent execution of the same plan; the queue runs sequentially and does
not stop unrelated compilations. Completed jobs are not rerun. An interrupted
job still marked `RUNNING` requires inspection before any restart.

Automatic region preparation does not itself run a compiler:

```sh
python3 optimizer/optimize.py search --parent tang/impl/console_neo_n18 \
  --out optimizer/runs/auto_regions_new --prefix console_neo_auto --trials 3
python3 optimizer/optimize.py run optimizer/runs/auto_regions_new/plan.json
```

The search uses the footprint of negative-setup cells and two contractions.
It is a starting heuristic, not a forecast of improved timing. `--split-paths`
creates separate regions for groups sharing cells; overlapping groups merge
transitively. Existing anchors remain intact. Automatic grouping refuses
cross-clock paths, which require a prior CDC analysis.

```sh
python3 optimizer/optimize.py search --parent tang/impl/console_neo_n21 \
  --out optimizer/runs/n21_groups_new --prefix console_neo_groups \
  --trials 1 --paths 2 --split-paths
```

The Gowin adapter uses `tools/route_console_neo.py` and requires the appropriate
Gowin installation and license. It can read Pro Dock reports, but a dedicated
Pro Dock experiment queue is not implemented. Select the installation through
`GOWIN_IDE`; see [FPGA release instructions](../releases/fpga/README.md).

## Clock, reset and constraint experiments

`check_constraint_semantics.py` runs isolated characterization circuits. These
commands compile experiments; they do not load hardware:

```sh
python3 optimizer/check_constraint_semantics.py --suite hdmi-dce-place \
  --columns 160 150 140 --out /tmp/neo_hdmi_placement_trial

python3 optimizer/check_constraint_semantics.py --suite hdmi-clock-pressure \
  --dce-sites pg0 sg0 sg8 --out /tmp/neo_clock_pressure_trial
```

Additional suites include `ddr-clock-relations`, `cdc-generated`,
`hdmi-dce-sites --dce-sites sg0 --columns 150 160 170`, and
`hdmi-incremental --reference-build <complete-reference-probe>`.
`complete: true` means the compilation finished, **not** that timing passed.
Check every analysis type and verify that expected paths are present. An
experiment that hides checks through a multicycle exception is not a successful
closure result.

The optional `tools/neo/timing_closure.py` profile checks the 18 expected HDMI
reset controls and effective CDC bounds after routing. Changes in source-clock
latency can invalidate a normalized bound; the original effective 8 ns budget
must not be relaxed. `--cdc-clock-origins-zero` provides another explicitly
audited clock-origin experiment. Isolated tests do not qualify the full console.

Clock-pressure circuits load eight counter domains and compare PRIMARY/LW/HCLK
allocation. They do not model DDR or USB traffic. Keeping the same `CLOCK_LOC`
statements does not prove that the actual allocated resources are unchanged.
The optional `--hdmi-reset-placement sg0-c150` profile therefore checks the
routed DCE site and all eight expected PRIMARY clock assignments.

`--system-reset-tree` distributes the bus reset through seven registers with
the same specified function and latency, inside a frozen source copy. Its
audit rejects merged registers, changed D/clock/enable/reset/INIT or unrelated
DDR-profile changes. Post-route checks inspect the actual mapped registers;
RTL equivalence alone does not qualify their physical reset distribution.

The Neo router supports `--incremental-from <complete-build>` with
`--incremental-mode place` (default) or `pnr`. It copies and hashes the Gowin
cache into a new build. Netlist, pins, clocks and timing constraints must stay
the same; only `INS_LOC` placement may change. An old timing-failing build can
supply a physical reference without transferring its qualification. Isolated
incremental tests passed, but the historical full N45r4 `pnr` experiment failed
with 115,791 unrouted connections. Incremental results are design-specific.

## Results and boundaries

On the same complete N18 netlist, placing 13 LUT/DFF cells inside
`R[80:100]C[146:160]` changed the reported setup WNS from −0.249 ns to
+0.135 ns, setup violations from two to zero, and setup TNS from −0.393 ns to
zero. Pins, clock constraints and CDC budgets were retained. **The hardware
DDR test still failed.** This was a Gowin result from Workbench-generated
constraints, not a nextpnr implementation of the console.

Improving one path is not sufficient: a historical N20 regional trial improved
its worst slack from −1.178 ns to −0.699 ns while increasing setup violations
from 13 to 58 and worsening total negative slack. It was rejected. Reports
with detailed arcs can distinguish routing, combinational logic and clock-to-Q;
they cannot manufacture those measurements when the tool report omits them.

The pinned open-source flow has two important demonstrated limitations:

- Importing the complete encrypted N43 netlist stopped at a `pragma protect`
  block. Encrypted IP was not replaced by black boxes to claim a full build.
- A two-clock reset reproducer synthesized, but nextpnr reported BUFG usage
  `2/1` and refused placement. That is the capacity exposed by the installed
  device database, not a measurement of the FPGA's physical resource count.

The final reset reproducer retained four explicit DFFCE cells with matching
D/CLK/CE/CLEAR inputs, but no routed or hardware comparison resulted. The
single-clock examples therefore do not establish full-console support.

The latest Neo FF-memory candidates are also not working releases: the direct
FF implementation and banked version ended with 6,960 and 4,243 unrouted
connections. The banked placement used 61,717/69,120 CLS (89.29%). Aggregate
counts do not identify the unrouted nets or prove a silicon FIFO defect.
Current diagnostic evidence and next experiments are described in
[Neo port status](../docs/NEO_PORT.md).

## Tests

```sh
python3 -m unittest discover -s optimizer/tests -v
node optimizer/tests/test_dashboard.cjs
```

Python tests cover incomplete reports, inactive constraints, changed inputs,
stale qualification, preserved pins/anchors, evidence association and HTML
injection. The optional browser test uses an installed Playwright and Chrome
(`PLAYWRIGHT_MODULE` and `CHROME_BIN` can override their locations). It checks
filters, paths, region selection, suggested commands and mobile rendering.

The tool does not contain a complete Gowin congestion model or an independent
replacement for the vendor router. There is no automatic creation of CDC
exceptions and no automatic hardware loading.

## Upstream projects

- [nextpnr](https://github.com/YosysHQ/nextpnr)
- [Apicula](https://github.com/YosysHQ/apicula)
- [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build)
- [Gowin user guide](https://cdn.gowinsemi.com.cn/SUG100E.pdf)

Regional constraints follow the Arora V SUG1018 manual. Use the documentation
matching the installed tool version when interpreting clock, reset and
placement semantics.
