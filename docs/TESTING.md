# Testing and qualification

## What a result means

| Evidence | Establishes | Does not establish |
|---|---|---|
| Host/model test | Behavior under the tested model and inputs | FPGA routing, external memory or physical USB |
| RTL simulation | Behavior of the simulated RTL/environment | Mapped primitive equivalence or board behavior |
| Mapped simulation | Behavior of the chosen synthesized netlist/model | Real PVT/board timing |
| Synthesis utilization | Resources for the exact elaborated design | Video-IP-only utilization unless separately measured |
| Completed timing analysis | Constraints met or violated for analyzed paths | Completeness of constraints or external protocol correctness |
| Hardware test | Observed behavior on the specified board/image | Every future build or indefinite reliability |
| Visual confirmation | The user's observed scene and stability | Pixel-exact correctness or all counters |

A passing simulation and an apparently static register do not justify ignoring
capture timing. A calibration flag does not prove DDR data integrity. A test
pattern does not prove Linux has booted.

## Publication campaign

The campaign under `TESTS/dual_board/publication_20261103` completed with
**15 groups PASS**, inputs unchanged, **hardware_validation=false**:

| Group | Coverage |
|---|---|
| `contract` | Ownership/reference guards and rejection of invalid states |
| `bridge` | AHB bridge equivalence against the protected reference |
| `ddr_prodock` | Original DDR adapter CDC/arbitration test |
| `ddr_neo` | Same adapter with the explicit Neo register-FIFO substitution |
| `usb_msc` | USB MSC model/simulation contract |
| `geometry` | Geometry and mixed raster, invalid descriptors, reset phases |
| `scanout_prodock` | NEBULA composition at 800 × 480 |
| `scanout_neo` | NEBULA composition at 1280 × 720 |
| `text_both` | Text rendering on both profiles |
| `dashboard_both` | Dashboard rendering on both profiles |
| `nebula_both` | Game logic/command generation on both profiles |
| `spi_pio` | Shared synchronous SPI/FIFO contract and errors |
| `spi_uboot` | U-Boot adapter/register behavior |
| `spi_linux` | Linux adapter/register behavior |
| `mmc_spi_init` | Initialization ordering and clock behavior |

Result and input hashes: [result.json](../TESTS/dual_board/publication_20261103/result.json).
This suite does not automatically test every isolated Neo snapshot experiment,
all game content or the whole HTTP dashboard service.

Run a new campaign in a unique directory:

```sh
python3 tools/run_board_regressions.py --out TESTS/dual_board/my_run_01
```

The audit checks protected archives and source ownership before running. A fresh
clone without those local reference inputs can fail at that prerequisite; this
is intentional and documented in [installation](INSTALLATION.md). Do not disable
the check to manufacture PASS. New/changed shared inputs invalidate earlier results.

## Smaller host checks

```sh
make -C games/luma3d test
python3 -B -m unittest discover -s tools/project_dashboard -p 'test_*.py'
node --check tools/project_dashboard/app.js
```

The first tests the canonical base game, not every later MAZE candidate. The
[MAZE release snapshot](../releases/luma3d-maze-20261103/README.md) has its own
manifest, build recipe and verification results. Matching its executable hash
proves reproducibility for that compiler/input combination, not a new hardware
performance result.

## Hardware acceptance by subsystem

| Subsystem | Required observations |
|---|---|
| Reset/clocks | Power-up and reload sequencing, independent running-clock evidence, expected reset release |
| DDR | Address patterns, boundaries, repeated data checks, CPU/GPU concurrency and calibration state |
| Command path | Full packet identity, FIFO backpressure/wrap, width/height capture, explicit rejection reason |
| Raster | Known reference pixels, depth/alpha/scissor boundaries, invalid inputs and resets |
| Display | Active scanout, underflow counters, vblank commits, physical output and visual stability |
| USB | Actual HS negotiation, EP0/data traffic, reconnect/reload, cancellation and no stale replay |
| SD | Exact lengths/checksums, explicit errors, separated controller/MMC/application timings |
| Linux | Package identity, shell, devices, ownership, launch/exit and normal cold boot |
| Game | Fixed-scene comparisons, frame-time distribution, content progression and controls |

The two boards require separate results. A working Pro Dock does not qualify
Neo; a Neo experiment must not replace the protected Pro Dock reference.
Before hardware access, identify the board, bitstream and software, obtain
exclusive ownership, and preserve another active board. J-Link is now restricted
to explicitly agreed diagnosis, not routine loading.

## Test record format

Each meaningful campaign should retain:

1. Objective and the hypothesis/contract being tested.
2. Board profile, exact source and binary hashes, tool versions.
3. Environment, clock settings, test preparation and procedure.
4. Expected result, including negative/adversarial cases.
5. Observed result, raw logs/data and failures.
6. Scope limits, remaining steps and whether hardware was involved.

A mutation test is useful only if it detects a specific incorrect behavior.
Changing a golden result to match new output is not validation. Preserve failed
attempts and distinguish harness errors from implementation failures.

## Public evidence versus local artifacts

Selected small reports and logs are committed. Large vendor workspaces, simulator
objects, temporary agent environments and most bitstreams remain local. A path
mentioned as local evidence is not a downloadable artifact or reproducible
public release. Reports with absolute workstation paths retain their historical
identity; the public guides use repository-relative links for included files.

The [publication audit](../TESTS/publication_20261103/audit/PUBLICATION_AUDIT.md)
records the credential/provenance scan and its limitations. Its result is separate
from software and hardware correctness.
