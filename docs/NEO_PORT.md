# Tang Mega Neo / Tang Console 138K port

Status date: **3 November 2026**. This page describes the port and its evidence;
it is not a release announcement for a working Neo console.

The Pro Dock is the working application platform. The Neo shares the GPU and
software architecture, but its complete DDR-backed graphics path is **not yet
qualified on hardware**. The latest experiment replacing both command memories
with banked flip-flop storage failed to route: **4,243 unrouted connections and
no bitstream**. The preceding implementation failed with 6,960.

For routine operation, the intended deployment path is **SD autoboot and the
SOFT-USB console**. J-Link/OpenOCD RAM loading is a diagnostic facility retained
in the repository, not the normal Linux/game installation procedure. Its use
requires agreement on the diagnostic, exclusive ownership of the target and a
verified board identity. The intended Neo SD/USB workflow must not be described
as an already qualified end-to-end installation.

## 1. Platform differences and shared architecture

| Item | Mega Pro Dock | Mega Neo / Tang Console 138K |
|---|---|---|
| FPGA profile used by this project | GW5AST-138B, FPG676 | GW5AST-138C, PG484 |
| Physical display | LCD, 800×480 | TMDS HDMI/DVI output, 1280×720 |
| Nominal pixel clock in the profiles | 35 MHz | 74.375 MHz |
| Raster totals | 1193×533 | 1650×750 |
| Theoretical refresh from those values | about 55.04 Hz | about 60.10 Hz |
| AE350 core / AHB clock targets | 800 / 80 MHz | 800 / 80 MHz |
| Selected DDR baseline | DDR3 IP 5.9, 300 MHz memory | DDR3 IP 5.9, 300 MHz memory |
| DDR user interface / GPU target | 75 MHz | 75 MHz |
| Typical scene render size before ×2 scaling | 400×240 | 640×360 |
| Shared/full text console geometry | 50×15 / 100×30 | 80×22 / 160×45 |
| PC connection | SOFT-USB2 HS | SOFT-USB2 HS; BL616 serial relay also present |
| Additional gamepad ports in the Neo source profile | — | two limited low-speed USB hosts |

Clock values in this table are design settings, not a simultaneous physical
frequency measurement. The Neo timing is close to nominal 720p60 at 74.25 MHz
but is not exactly that standard clock. The current output does not implement
HDMI audio, EDID/DDC mode negotiation or HDCP.

The shared GPU provides layers, sprites, tilemaps, text, RGB565 framebuffers,
blitting and raster/geometry acceleration. Its rendering surfaces and physical
scanout have different limits: the raster target remains at most 1024×512 in
this generation, while the Neo scanout and text can span 1280×720. A 720p output
does not imply that every 3D pass is rendered at 1280×720.

The source profile includes SOFT-USB2 High-Speed, **480 Mbit/s**, not USB3. The
two USB-A hosts are a separate implementation for the tested low-speed gamepad
class, including the 081f:e401 device. They are not generic USB2 high-speed
hosts: arbitrary hubs, keyboards, full-speed devices and universal HID parsing
are not supported by that implementation. Source presence and simulation are
separate from validation on the complete Neo hardware build.

See [the original port architecture](../ARCHI/PORT_NEO_720P.md) for pin/profile
details and historical experiments, and [the common project architecture](../ARCHI/PROJET.md)
for the overall system.

## 2. Source ownership and protection of the working Pro Dock

The rules are defined in [board compatibility](../ARCHI/COMPATIBILITE_CARTES.md)
and the machine-readable [ownership manifest](../tang/boards/ownership.json).
A file named `prodock-*` may still be shared by both boards; its filename is
not an ownership rule.

The principal boundaries are:

| Area | Canonical location / role |
|---|---|
| Common board/DDR logic | `tang/rtl/board/` |
| Common graphics implementation | `tang/rtl/video/` and its declared dependencies |
| Neo integration, pinout and timing profile | `tang/boards/neo/` |
| Neo candidate transformations and diagnostics | `tools/neo/` |
| Neo source build and rerouting entry points | `tools/build_console_neo.py`, `tools/route_console_neo.py` |
| Linux board descriptions | `linux/prodock-linux.dts`, `linux/neo-linux.dts` |
| Historical, immutable experiment inputs and results | named folders under `TESTS/` and `tang/impl/` |

Generated snapshots are evidence, not alternate source trees to maintain.
Every experimental substitution must identify its source, destination, original
hash and replacement hash. Common fixes require the two-board regression suite;
an isolated Neo netlist experiment must not silently replace the Pro Dock RTL.

The protected historical Pro Dock reference is G22r0 / NEBULA R17, with FPGA
SHA-256:

```text
fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f
```

Its files and archives are listed in
[the reference manifest](../tang/boards/prodock/reference.json). Historical
hardware success is retained together with its documented timing/USB limits;
the word “reference” does not retroactively make every static check pass.

## 3. DDR baseline and the first FIFO experiment

The selected baseline is **DDR3 IP 5.9 at 300 MHz**, using the original adapter
and arbiters. The default Neo builder profile is `neo-fifo-registers`.
DDR IP 6.0 and its 300/325/400 MHz variants remain explicit historical
experiments. They are not the selected baseline and their existence is not
evidence that increasing memory frequency fixes this port.

The [Pro Dock DDR profile](../tang/boards/ddr_prodock.json) identifies twenty
reference files. The [Neo FIFO override](../tang/boards/neo/ddr_fifo_registers.json)
substitutes storage only in the Neo build copy. It keeps the same DDR IP,
adapters, arbiters, Gray pointers, flags, resets and read latency.

Two different FIFO investigations must not be confused:

1. **CPU↔DDR CDC FIFOs:** four entries of 100 and 64 bits. The Neo storage
   substitution uses 656 flip-flops. The N32/N33 comparison reduced the targeted
   test from 976 errors in 3,168 reads to zero; CPU/JTAG test patterns also
   matched. This is a useful controlled observation of that implementation,
   not proof of a universal Gowin RAM or FIFO silicon defect. N33 still had
   timing violations and did not qualify the complete GPU or Linux system.
2. **GPU command memories:** two 128×32 stores later in the command path.
   These are the subject of the November experiments described below. The
   CPU FIFO substitution did not replace them.

The Neo board's memory was identified by the owner as Hynix EFR. Pin mapping,
geometry, speed grade, IP parameters and physical timing must be checked for
the actual board. Sharing RTL with Pro Dock does not imply identical package
pins, routing, reset distribution or board-level delays.

The detailed comparison and its limitations are preserved in
[the port record](../ARCHI/PORT_NEO_720P.md). A successful CPU DDR read does not
prove the scanout/blitter DMA path, and DDR calibration completion does not
prove sustained data integrity.

## 4. Startup/reset: what changed and what is established

The startup investigation separated PLL readiness, DDR initialization, the
AE350 POR/HW inputs, HRESETN and downstream video reset. A constant sampled
clock level is not proof that the clock is absent; clocks must be measured or
observed with suitable activity witnesses.

The SDK example contained a **20 ms delay**. The project selected **50 ms** as
a conservative startup margin after synchronization of PLL/DDR readiness.
At a 50 MHz reference this is 2,500,000 cycles. Subsequent synchronization
releases the CPU reset in its AHB domain; the sequencer does not feed back into
PLL or DDR reset in a way that would make readiness depend on its own release.

The public evidence must retain the distinction between design and causality:

- 20 ms was observed in an example; it was **not established as a specified
  minimum AE350 reset requirement**.
- The first 50 ms candidate restored the internal color bars, DMI access and
  CPU/AHB reads on the tested Neo. The candidate had also been rerouted.
- The same-bitstream short/long startup comparison was not established as a
  complete proof of the original failure mechanism. A warm-reset comparison
  is also different from configuration-time startup.
- Helper RTL and mapped simulations validate the sequencer contract. The
  installed AE350 macro simulation model does not model all internal hard-CPU
  behavior; simulation cannot establish that internal cause.

See [the reset sequencing experiment](../TESTS/neo_720p_20261012/reset_sequence_20261025/README.md).
It preserves failed attempts, post-route findings, hardware observations and
the limitations of the GAO captures. The shared source tree and every older
snapshot do not automatically contain all later diagnostic changes: a build
manifest, not its informal name, determines its reset implementation.

## 5. HDMI: independent evidence from a DDR-free design

“No signal” on the monitor and incorrect framebuffer content are different
failure classes. A minimal 720p pattern generator with no CPU, DDR, USB or SD
was used to isolate the output path. The following results used a shared
synthesized design and controlled DCE placement variants:

| DCE placement | Static timing of the minimal design | Observation |
|---|---|---|
| Automatic PG0 | published checks positive | color bars visible |
| Explicit SG0 | published checks positive | monitor reported no signal |
| Original PG0 bitstream restored | unchanged | image returned |
| Explicit PG0, same rerouting procedure | published checks positive | image visible |
| Explicit SG4 | published checks positive | image visible |

This reproduces a placement/routing-dependent result in that particular design.
It does **not** establish a general SG resource failure: SG4 worked. The cited
Gowin documentation permits both PG and SG placement for this DCE family.
Clock phase, serializer behavior and electrical details were not fully resolved
by those observations. Likewise, seeing `LW` in a clock/resource report is not
by itself a diagnosis.

The exact bitstream identities and tests are recorded in
[the HDMI isolation report](../TESTS/neo_720p_20261012/reload_r1_cold_20261022/README.md).
Some complete Neo candidates then displayed the internal bars while DDR-backed
scanout still failed. The bars deliberately avoid that memory path.

## 6. Current COPY diagnosis and observability

The command path contains two stores before the private command captures:

```text
AHB command writes
  -> u_accel/u_commands: dual-clock ddr_dcfifo, 128 x 32
  -> u_accel/u_blitter/cmem: synchronous 128 x 32 command store
  -> assembled command / geometry stage
  -> gpu_v1 private packet
  -> gpu_copy565 private packet and descriptor validation
  -> DMA requests, arbiter and DDR
```

The first FIFO is already project RTL, not a newly substituted vendor FIFO IP.
Its inferred memory maps to SDPB in the relevant design. `cmem` also maps to
SDPB. Replacing storage with FF does not replace their pointer/control logic.

A Pro Dock witness executed the same 24 words—TARGET, SCISSOR, COPY—and completed
without GPU faults; the checked 96-byte memory region matched. Neo observations
depend on the exact instrumented build:

| Build/experiment | Observation | What it does not prove |
|---|---|---|
| S400 | TARGET/SCISSOR accepted; COPY remained BUSY after CHECK | the later rejection mask cannot be assigned retrospectively to this stall |
| REJECT R1 | TARGET/SCISSOR accepted; COPY completed with rejection | completion/fence advancement is not command success |
| REJECT R1 reason snapshot | mask `0x00006014`: zero width, zero height and descriptor groups 0/1 | it does not expose the full private operand packet |
| Same build, reserved-word sentinel `w7=1` | fresh epoch/sequence, still mask `0x6014` | not proof that every word is zero, or that capture CE failed |
| NGDB capture after sentinel | `received=32`, `last_word=1` | proves that last word reached the first FIFO's output, not that all words or later stages were correct |

The reason snapshot recorded opcode 29, child validation state 17, parent COPY
wait index 42, target valid and no bad header. The hardware descriptor's
dimensions were therefore inconsistent with the intended nonzero COPY
dimensions. **Where that divergence arises remains open.**

The current diagnostic exposes sticky first-fault reason plus context through
the stable NCP snapshot transport. Baseline and post-command photos use the
same armed epoch; sequence, version, photo ID and overflow/error guards prevent
silently combining stale banks. Capture completion, command completion and
command acceptance are three separate verdicts.

This is still an **exploratory** hardware observation. REJECT R1 routed, but
had setup −1.530 ns and recovery −0.211 ns; hold/removal were positive.
Some violations involve the new observer's reset-dependent capture logic.
Stable reset and coherent transport support interpretation but do not turn
the entire instrument into a timing-qualified measurement device.

### Existing register visibility

These addresses refer to the instrumented Neo profile, not a promised portable
application ABI:

| Window / address | Meaning and limitation |
|---|---|
| `0xE9001000..0xE9001064` | GPU capabilities/status/counters; no general packet RAM readback |
| `0xE9001010` | command FIFO write port; reads return zero, not the last written parameter |
| `0xE9005000..0xE9005040` | NGDB state/snapshot interface |
| `0xE9005010`, `0xE9005014` | received count and last word from the last acknowledged NGDB snapshot |
| `0xE9005018`, `0xE900501C` | captured command headers; not all eight operand words |
| `0xE9005080..0xE9005098` | NCP5 transport; content version must match its decoder |
| `0xE9006000` | scanout diagnostic instance, not a COPY parameter window |

Reading an unimplemented offset or a write-only port as zero must not be
reported as a zero-valued packet. The existing build cannot read arbitrary
`gpu_v1.packet` or `gpu_copy565.packet` words. A future small local observer
could capture the actual retained Q values for parent/child w2 and w7, with
start/CE/reset witnesses, using a distinct content version. That proposal is
not a capability already available in the current bitstream.

## 7. Two command memories in flip-flops: exact experiment and outcome

The owner explicitly requested FF storage before considering a vendor FIFO-IP
comparison. The experiment preserves both 128×32 depths, pins, byte enables,
read cycle, clocks, resets and surrounding control. It does not shorten queues
or add pipeline cycles to make routing easier.

The helper follows the official SDPB model's relevant contract: registered
one-edge read for READ_MODE=0, output reset behavior, no reset of stored words,
and the existing address mapping. Same-address simultaneous cross-clock
read/write is not promoted into a physical guarantee by simulation.

Two helper implementations were evaluated:

| Per memory | FF + mux | Banked one-hot/OR FF |
|---|---:|---:|
| DFFRE | 4,128 | 4,128 |
| LUT | 4,113 | 3,541 |
| RAM primitives | 0 | 0 |
| Maximum reported combinational LUT depth | 6 | 6 |
| Logical sinks on read ADB[5] | 1,336 | 16 |

The banked helper reduces raw address fanout, but distributes row selections
to 256 inputs and a shared write-enable term to 512 inputs. It does not make
distribution cost disappear. Both complete variants failed placement/routing
completion with the same inherited constraints and settings:

| Complete Neo design | REJECT R1 | Two FF mux memories | Two banked FF memories |
|---|---:|---:|---:|
| LUT | 65,832 | 74,058 | 72,914 |
| Registers | 56,305 | 64,561 | 64,561 |
| CLS / 69,120 | 59,413 | 62,006 | 61,717 |
| CLS utilization, calculated | 85.96% | 89.71% | **89.29%** |
| BSRAM / 340 | 263 | 259 | 259 |
| Unrouted connections reported | route completed | 6,960 | **4,243** |
| New FF bitstream available | not an FF candidate | no | no |

No text report names the failed connections or locates them physically.
The `.vo` describes connectivity, not successful route continuity. The
protected placement file and binary database have not been decoded. Lower
LUT usage and fewer unrouted connections are observations; they do not prove
that a particular memory or high-fanout net caused the failure.

The next proposed comparison is **one command memory in FF at a time**, with
all other variables held fixed. `cmem` is a reasonable first discriminator
because the last sentinel word is known to have reached its input boundary.
A second test could replace only `u_commands`. Neither has been launched as
part of this analysis. Even success in one variant requires separation of
logical behavior from the changed whole-design placement.

## 8. What the tests cover

The storage helpers were compared with official primitives before and after
helper synthesis. Tests include all 128 addresses, enables, output reset,
clock pauses, differing phases and close frequencies. Mutants detect wrong
address/data, incorrect reset behavior and extra read latency. These are
digital functional tests, not analog CDC or SDF qualification.

A separate integration test drives the real R19 source command path through
AHB with two banked helpers observing the real storage signals. The stress
case accepts TARGET+SCISSOR+40 COPY16×2 commands: 336 words, 42 completions,
80 reads and 80 writes, FIFO occupancy reaching 128, zero loss/bad/rejection
counters and fully drained queues. Tests also check clock ratios and a w7
sentinel rejection. This uses source RTL and shadow memories, **not the full
substituted, placed application**. Identical repeated packets cannot detect
every possible whole-packet reorder. It is useful coverage, not a hardware
success claim.

The validation stages must remain independent:

1. Source simulation and meaningful adverse cases.
2. Synthesis mapping, primitive modes, INIT/CE/reset/clock connectivity.
3. Complete routing and STA: setup, hold, recovery, removal, pulse width,
   active constraints and bounded CDC paths.
4. Board tests with exact bitstream, target identity, baseline and counters.
5. Linux, display, game and endurance tests on that same target/version.

## 9. Reproducing a source build or analysis

Run commands from the repository root. Use unique output names and inspect
the selected profile before executing a build. These commands create
candidates; none installs Linux or programs a board:

```sh
python3 tools/run_board_regressions.py --out TESTS/dual_board/my_neo_review
python3 tools/build_console_neo.py --help
python3 tools/build_console_neo.py --name console_neo_my_review \
  --stage syn --ddr-adapter neo-fifo-registers --replicate 0 --gpu-debug
```

`--stage all` also invokes full placement/routing. It is not an automatic
diagnostic strategy: define a discriminating experiment and preserve its
inputs first. The numerous experimental flags in the builder are not a list
of fixes to enable together.

For a complete ordinary source build with the expected frozen-source layout,
`python3 tools/check_neo_timing.py tang/impl/BUILD_NAME` checks hashes,
complete routing, clocks, timing and structural audits. Later netlist-only
instrumented builds have dedicated builders and post-route receipts; the
generic validator must not be bypassed or falsely reported as accepting them.

See [optimization and report workflows](OPTIMIZATION.md). A fresh source build
does not reproduce an old diagnostic solely by choosing the same name. Its
exact frozen netlist, helper substitution, CST/SDC, engine settings and
manifests determine that identity. Runtime JTAG loading scripts are retained
for explicitly agreed diagnostics only; routine deployment remains the
SD-autoboot/SOFT-USB workflow described by the main installation documentation.

## 10. Evidence index for maintainers and vendor discussion

The links above point to repository documents. The following are **local
experiment artifacts** and may not be included in a public checkout; request
the relevant hashed evidence bundle rather than assuming a broken link is
an executable installation step:

| Evidence directory | Purpose |
|---|---|
| `TESTS/neo_copy_dma_20261101/reject_hardware_20261102/` | first reason-mask hardware capture |
| `TESTS/neo_copy_dma_20261101/reject_sentinel_20261102/` | same-build sentinel, fresh epoch/sequence |
| `TESTS/neo_copy_dma_20261101/fifo_tail_readback_20261102/` | received=32, last_word=1 |
| `TESTS/neo_fifo_ff_20261102/mapping_01/` | exact SDPB mapping and original FF contract |
| `TESTS/neo_fifo_ff_20261102/banked_storage_01/` | qualified banked helper and fanout comparison |
| `TESTS/neo_fifo_ff_20261103/banked_build_01/` | reversible two-memory substitution |
| `TESTS/neo_fifo_ff_20261103/command_path_tests_01/` | integrated source-path stress test and limits |
| `TESTS/neo_fifo_ff_20261103/postroute_failure_01/mapping_review/` | 6,960/4,243 comparison, raw report hashes and independent review |

The tested REJECT R1 bitstream is
`f9f379e6aea82dda358aef1f34508c246920c89c877e9a5847162e32c3919e15`.
The failed banked candidate's assembled netlist is
`9026b77de01114a52fb87edc459a48417c4eb570c4ec0945025e18a44f9f7524`.
These identify different artifacts; a netlist hash is not a bitstream hash.

For Gowin/Sipeed review, the useful open questions are the missing parameter
divergence point, the precise physical cause of the isolated HDMI result, and
the named routing failures of the FF candidates. The project does not claim
an established GW5AST FIFO, RAM or clock-resource silicon erratum.

## Published diagnostic subset

The [publication subset guide](../TESTS/publication_20261103/NEO_DIAGNOSTIC_PACKAGE.md)
identifies the included flip-flop helpers, test benches, frozen integration
sources, recipes and compact failed-route reports. Its explicit manifest lists
122 files. Vendor primitive extracts and large protected parent netlists remain
external dependencies; their original integrity guards are retained. This is
diagnostic evidence, not a new loadable Neo release.
