# Current status and evidence

Snapshot: **3 November 2026**. “Implemented” means code exists; “tested” needs a
scope. Simulation, timing, a photograph and a hardware endurance run answer
different questions.

## Board and release identities

| Identity | Meaning | Qualification boundary |
|---|---|---|
| Pro Dock G22r0 / NEBULA R17 | Protected historical reference | Hardware demonstrations; timing/CDC limits retained |
| Second Pro Dock, programmer ending **1717**, FPGA **R6** | SD boot development and latest MAZE run | SRAM-loaded FPGA and Linux game observed; not proof of persistent cold boot |
| First Pro Dock, programmer ending **2818** | Separate working board | Untouched by the latest second-board restoration |
| Neo REJECT R1 / D128 diagnosis | Instrumented GPU rejection investigation | Pattern/diagnostic access, not complete Linux console |
| Neo banked flip-flop FIFO candidate | Two command memories replaced | Local tests pass; full route fails, no usable bitstream |

R6/R19-style labels are not globally unique. Retain board, source manifest,
build directory and SHA-256 with each result.

## Feature and delivery matrix

| Area | Available | Missing or limited |
|---|---|---|
| Pro Dock graphics | Hardware 2D/3D, layers, sprites, tiles, text, alpha, geometry | Every changed build needs its own hardware/timing qualification |
| Linux graphics | Custom GPU/display drivers, userspace API, terminal/dashboard | No general desktop/OpenGL/Vulkan stack |
| Game execution | Shell-launched executables and automatic festival mode | Complete reproducible end-user installer |
| SD startup | U-Boot and Linux startup observed with candidate FPGA | Repeated persistent cold-power boot to game |
| SOFT-USB | HS CDC terminal, experimental application/DDR transfers | Qualified complete software/update path and sustained throughput |
| USB storage | Firmware CDC + optional MSC/BOT | Not a general Linux export of its mounted SD |
| SD/SPI | Native AE350 SPI, shared PIO and failure tests | Throughput cause incomplete; production DMA not integrated |
| Neo display | HDMI 720p patterns | Full graphics/Linux qualification |
| Neo input | Two USB2 host ports designed for controllers | End-to-end validation with the completed console |
| Game content | Exploration, puzzle, board and arcade activities | Frame pacing, polish, long-campaign completion |
| Build system | Pinned Linux inputs, ownership and regression checks | Some external/local baseline dependencies remain |

## Latest Pro Dock game observation

On 3 November, the second Pro Dock ran `/bin/luma3d-maze --festival`. Recovery
used CPU JTAG: **a historical diagnostic operation, not normal installation**.
Routine J-Link loading has since been stopped at the owner's request.

| Item | Observed result |
|---|---|
| R6 FPGA SHA-256 | `0a0ab081f12739767493bac8bac9247fe20d6a9cf83d54405f64d2a34015ed60` |
| Game ELF SHA-256 | `2e552dd1cc9b73756b68040b75c4c0a8f9c62c6584dbadd4fcb38e7933c4b985` |
| ELF bytes | 16,684,812 |
| Linux release | `6.12.112-prodock-luma3d-g3d1-sdoptin-r1` |
| Graphics-ready log | 4.606784 seconds |
| Four FPS windows | 5.55, 13.36, 32.91, 28.12 |
| GPU counters before launch | Error, fault and underflow zero |

The FPS values describe different windows/scenes, not one benchmark mean.
No post-run counters were collected because the game was left running. This
particular recovery has no new user visual confirmation. The first board,
SD files and nonvolatile FPGA flash were unchanged. See
[the test record](../TESTS/prodock_game_restore_20261103/TEST_RECORD.md).

The package embeds the game in a RAM root filesystem. This does not prove SD
asset streaming. Replacing a previously silent diagnostic Linux recovered the
console, but did not establish the cause of that silence.

## Measurements that must not be mixed

| Measurement | Scope | Result / limitation |
|---|---|---|
| SPI chunks | 411 internal 512-byte exchanges | PIO mean about 7.106 ms; complete chunk mean 7.394 ms, range 6.194–8.795 ms |
| Application reads | Three complete 512-byte `pread` calls | Mean 20.576 ms, range 19.148–22.985 ms; different population/path |
| Historic ORBITAL R6 | Older hardware/software campaign | 54.81 FPS; not MAZE performance |
| Publication regression | Current common sources on the host | 15 groups PASS; no board access |

All 411 chunks confirmed 512 bytes transmitted/received. This does not measure
SCK at the connector. Nominal configuration and physical frequency are distinct.
See [SD/SPI](SD_SPI.md) and [optimization](OPTIMIZATION.md).

## Neo experiment result

The instrumented rejection snapshot reported COPY `width_zero`/`height_zero`
despite nonzero submitted parameters. This was not an independent readback of
the private width/height flip-flops; REJECT R1 also remains FAIL in timing.
TARGET and SCISSOR were accepted. A shared header does not establish correct
capture of subsequent words.

Two command memories were replaced with flip-flop storage in isolated candidates.
The banked version reduced logic relative to the first replacement but still
finished with **4,243 unrouted connections**. No loadable bitstream or valid
final timing result was produced. Local tests do not prove a board fix.

There is no established model-specific Gowin FIFO silicon erratum or complete
root cause. Reset, command capture, DDR and HDMI observations are tracked
separately in [the Neo guide](NEO_PORT.md).

## Completion priorities

1. Finish normal Pro Dock deployment: persistent configuration, verified SD
   Linux boot and working SOFT-USB terminal, without routine debugger loading.
2. Qualify USB transfer/recovery, then kernel, game, asset and SD updates.
3. Isolate SPI cost with consistent timing scopes; integrate DMA only with
   correct ownership, completion and failure contracts.
4. Finish the discriminating Neo command experiment and routing, then test
   graphics, DDR load, USB, Linux and input on that exact board.
5. Improve game frame pacing and content using comparable scene measurements.
6. Package a fresh-clone build/install flow and settle redistribution terms.

These are acceptance criteria, not completed features.
