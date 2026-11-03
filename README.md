# Console FPGA — Tang Mega Pro Dock & Tang Neo

**A hardware graphics engine, Linux on RISC-V, and games rendered on a Gowin FPGA.**

**[Watch the demonstration video on YouTube](https://youtu.be/G8LfKqb-1sY)**

An Electrosens R&D project for the Gowin **GW5AST-138** family and Sipeed boards.
The AE350/A25 processor runs game logic at **800 MHz**; FPGA logic accelerates
rendering, reads shared DDR3 and composes the display. This is real-time
rendering on the board, **not playback of a generated video**.

The project combines bare-metal demonstrations, Linux applications, a hardware
text console and a developing exploration game with multiple activities.
The Pro Dock runs the demonstrations and Linux games. Neo support and the
complete SD/USB installation experience are still being developed.

| Board | Display | Status — 4 November 2026 |
|---|---|---|
| **Tang Mega Pro Dock 138K** | **800 × 480 LCD** | R6: LCD graphics, Linux, games and SD boot work; SD loading is slow; USB software installation is in development |
| **Tang Neo / Console 138K** | **1280 × 720 HDMI** | Displays HDMI test patterns; graphics debugging is ongoing and games are not ready to use |

## Documentation

| Purpose | Guide |
|---|---|
| What works, what does not, and the evidence | [Current status](docs/STATUS.md) |
| Tools, configuration, installation and builds | [Installation](docs/INSTALLATION.md) |
| Linux connection, commands, layouts and games | [Linux console](docs/LINUX_CONSOLE.md) |
| Loading through the normal PC connection | [SOFT-USB transport](docs/USB_TRANSPORT.md) |
| Graphics, clocks, memory and software responsibilities | [Architecture](docs/ARCHITECTURE.md) |
| Libraries, interfaces and application development | [API reference](docs/API_REFERENCE.md) · [Development](docs/SOFTWARE_DEVELOPMENT.md) |
| Games, demonstrations, controls and content | [Games](docs/GAMES.md) |
| Neo differences and current investigation | [Neo port](docs/NEO_PORT.md) |
| Performance and its measurement | [Optimization](docs/OPTIMIZATION.md) · [SD/SPI](docs/SD_SPI.md) |
| Regressions and hardware qualification | [Testing](docs/TESTING.md) |
| Sources, archives, third-party material and contribution | [Repository](docs/REPOSITORY.md) |

## Download, program and rebuild

| Board | Selected FPGA | What to expect | Downloads and exact build recipe |
|---|---|---|---|
| **Pro Dock** | **R6** | LCD, GPU, Linux from SD and automatic game startup; slow SD loading | [R6 FPGA](releases/fpga/prodock_r6/README.md) · [SD files](releases/prodock-sd/README.md) |
| **Neo** | **REJECT R1 diagnostic** | HDMI test pattern and GPU diagnostic access; the graphics port is unfinished | [Neo diagnostic FPGA](releases/fpga/neo_reject_r1/README.md) |

Start with the **[board release and programming guide](docs/RELEASES.md)**.
It explains temporary SRAM loading, persistent flash programming, checksums and
rebuilding each selected version. Earlier experimental bitstreams are retained
in Git history rather than presented as competing downloads.

The **Pro Dock SD boot works**: the resident loader reads U-Boot, U-Boot reads
Linux, and Linux starts the game automatically. Loading is currently slow.
The published SD boot observation used the R6 configuration loaded into FPGA
SRAM; persistent FPGA flash startup is listed separately in the release guide.

Connect **SOFT-USB** for the Linux terminal. Its link runs in USB 2.0 High-Speed
mode (480 Mbit/s link rate). Software transfer support exists experimentally;
the complete USB installation/update workflow is still in development.
[USB details](docs/USB_TRANSPORT.md) · [Debugger pinout](docs/DEBUGGING.md)

## Graphics implemented

| Engine | Capabilities |
|---|---|
| **Composition** | RGB565 background; 16 indexed/tiled layers; priorities, windows and pixel scrolling |
| **2D sprites** | 64 hardware sprites, up to 32 × 32 pixels, flips and transparent index zero |
| **Tiles and text** | 8/16/32-pixel tiles; hardware glyph rendering for the Linux terminal |
| **2D drawing** | Rectangles, copies, text, scaling and affine drawing into render surfaces |
| **Rasterization** | Perspective-correct textured triangles, RGB565 targets, 16-bit depth, scissor |
| **Effects** | ARGB4444 alpha, additive blending, modulation, fog and prepared mip levels |
| **G3D1 geometry** | DDR mesh fetch, matrices, clipping, projection, back-face culling and directional lighting |
| **Presentation** | Double buffering and vertical-blank descriptor commit |

The CPU handles gameplay, camera decisions, collisions and object matrices.
Hardware geometry avoids projecting every mesh vertex on the CPU. Textures,
meshes and some cinematic trajectories are prepared beforehand; the display
is rendered at runtime.

“3D sprites” are textured quads submitted to geometry/rasterization, separate
from the 64 compositor sprites. Indexed layers use a transparent color key;
per-pixel alpha belongs to the raster drawing path. Affine drawing is not a
rotation control on compositor sprites. There are no programmable shaders or
qualified OpenGL/Vulkan drivers. Sixteen layer descriptors do not guarantee
sixteen full-screen layers at every resolution or bandwidth.

## Linux alongside the game

```text
                 Pro Dock LCD: 800 × 480
┌─────────────────────────┬─────────────────────────┐
│ Game: 400 × 240         │ Linux text terminal     │
├─────────────────────────┴─────────────────────────┤
│ GPU / USB / SD dashboard: tables, lights, counters │
└───────────────────────────────────────────────────┘
```

Switch to a full-screen game, full-screen terminal or the shared layout.
Applications are ordinary RISC-V executables using project-specific GPU
interfaces. On an already booted compatible package:

```sh
prodockctl layout split
prodockctl layout game
prodockctl layout console
prodockctl display
# If installed in the selected package:
luma3d-maze --festival
```

The exact MAZE version demonstrated on the board is available as a
[source and executable package](releases/luma3d-maze-20261103/README.md),
with instructions to rebuild it. The older game Makefile builds a different
development version.

## Games and demonstrations

| Name | Experience |
|---|---|
| **[LUMA](games/luma/README.md)** | Forest adventure, animated hero, combat, portal and luminous finale |
| **[ORBITAL](games/orbital/README.md)** | First-person corridor, drones, shooting and effects |
| **[ASTRILLA](games/astrilla/README.md)** | Space voyage, hardware 3D ships, black-hole effects, battle and landing |
| **[NEBULA](games/nebula/README.md)** | Linux space shooter with sectors, explosions and bosses |
| **[LUMA3D / MAZE](games/luma3d/README.md)** | Developing 3D exploration world and a festival of puzzle, board and arcade activities |

The game aims for varied locations and hours of play. This is a content goal,
not a completed campaign claim. Performance varies substantially by scene;
the latest hardware log contains windows from **5.55 to 32.91 FPS**, not a
uniform 30/60 FPS guarantee. See [the game guide](docs/GAMES.md) for scope,
controls, assets and outstanding work.

## Build from source

The [installation guide](docs/INSTALLATION.md) gives the dependencies and complete
commands for firmware, FPGA, Linux, U-Boot and SD packages. Build paths are
relative to the checkout; external tools are selected through configuration.
No separate logic-analyser project is required.

```sh
# Install the pinned baseline inputs supplied with this repository.
python3 tools/bootstrap_build.py

# Configure your installed Gowin IDE, then run the local regression suite.
export GOWIN_IDE="$HOME/gowin/IDE"
python3 tools/run_board_regressions.py --out TESTS/dual_board/my_check_01

# Rebuild Linux for the Pro Dock from the current sources.
make -C linux BOARD=prodock BUILD_ARGS=--candidate all JOBS=4
```

To reconstruct a selected FPGA version from its frozen inputs, use its linked
release recipe above. Rebuilding current development sources and rebuilding a
published version are separate commands. [Testing](docs/TESTING.md) explains
simulation, timing and board checks.

Gowin performs full-console synthesis and routing. The
[optimization workbench](optimizer/README.md) adds report analysis and bounded
experiments; nextpnr/Yosys/Apicula do not currently replace the complete vendor
flow for this design.

## What remains to finish

- **Installation:** qualify persistent FPGA startup and complete software
  installation through SOFT-USB; SD-to-Linux/game startup already works.
- **Loading and performance:** speed up SD access and improve frame pacing in
  the larger game scenes.
- **Neo support:** resolve the graphics problems before offering a usable game
  image for this board.
- **Hardware validation:** working demonstrations exist, but some older builds
  still have documented timing and occasional USB terminal issues.

See [project status](docs/STATUS.md) for what visitors can use today. Detailed
build results and measurements are linked from that page.

## Sources and distribution

`tang/` contains RTL and board profiles; `fw_console/` contains bare-metal code;
`linux/` contains OS integration, drivers and user APIs; `games/` contains
all games, demonstrations and their artwork; `tools/`, `optimizer/`, `TESTS/` and `docs/`
contain tooling, evidence and documentation.

Shared Pro Dock/Neo sources remain shared. Board-specific adaptations are
classified in [`tang/boards/ownership.json`](tang/boards/ownership.json).

**Original project development: personal, non-commercial use only**, under the
[Electrosens R&D Personal Non-Commercial License](LICENSE). Commercial or
professional exploitation requires prior written permission. Free sharing for
personal use must preserve the license and notices.

[License scope and exceptions](LICENSE_SCOPE.md) are essential: existing
file/component licenses take precedence, and this update does not revoke
previous grants or relicense third-party material. In particular, GPL/MIT
components and combined game binaries cannot be declared exclusively
non-commercial by adding a root license. See also
[distribution notes](docs/REPOSITORY.md). This is a source-available project,
not a claim of unrestricted open-source licensing or vendor endorsement.
