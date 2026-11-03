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

| Board | Display | Status — 3 November 2026 |
|---|---|---|
| **Tang Mega Pro Dock 138K** | **800 × 480 LCD** | Runs graphics demonstrations and Linux games; automatic SD startup and USB installation remain in development |
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

These English guides describe the current project. Older French documents in
[`ARCHI/`](ARCHI) and dated test reports remain design history; an old PASS
does not qualify a later build.

## Intended user experience: SD boot and SOFT-USB

The normal workflow is **power on → boot Linux from SD → launch a game**, with
**SOFT-USB for the terminal, software transfer and updates**. Users should not
need a CPU debugger to load or run games.

SOFT-USB is an **USB 2.0 High-Speed device connection (480 Mbit/s link rate)**.
The CDC terminal exists, and experimental checked application/DDR transfers
exist. A complete reliable USB loading/update workflow is **not yet qualified**;
its remaining work is documented rather than presented as a finished installer.

**J-Link is a development/debugging tool, not the normal loading path.** Some
historical demonstrations were restored through CPU JTAG; that proves execution,
not autonomous boot or successful USB deployment. Routine J-Link loading has
been stopped. A blank FPGA still needs its initial configuration before its
own SOFT-USB logic can enumerate.

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
| **LUMA** | Forest adventure, animated hero, combat, portal and luminous finale |
| **ORBITAL** | First-person corridor, drones, shooting and effects |
| **ASTRILLA** | Space voyage, hardware 3D ships, black-hole effects, battle and landing |
| **NEBULA** | Linux space shooter with sectors, explosions and bosses |
| **LUMA3D / MAZE** | Developing 3D exploration world and a festival of puzzle, board and arcade activities |

The game aims for varied locations and hours of play. This is a content goal,
not a completed campaign claim. Performance varies substantially by scene;
the latest hardware log contains windows from **5.55 to 32.91 FPS**, not a
uniform 30/60 FPS guarantee. See [the game guide](docs/GAMES.md) for scope,
controls, assets and outstanding work.

## Reproduce carefully

The [installation guide](docs/INSTALLATION.md) explains tool versions and
remaining workstation-specific dependencies. This is **not yet a one-command,
fresh-clone FPGA distribution**: protected reference archives, vendor tools/IP
and some baseline build snapshots are external or local.

Useful software-only checks after installing their dependencies:

```sh
make -C games/luma3d test
python3 tools/run_board_regressions.py --out TESTS/dual_board/my_check_01
```

The second command also requires protected reference material; its integrity
checks must not be bypassed. The publication campaign passed **15 local test
groups**, with hardware validation explicitly false. Routing, timing closure
and testing on each board remain separate steps.

Gowin performs full-console synthesis and routing. The
[optimization workbench](optimizer/README.md) adds report analysis and bounded
experiments; nextpnr/Yosys/Apicula do not currently replace the complete vendor
flow for this design.

## What remains to finish

- **Installation:** complete and test automatic startup from SD and software
  installation through SOFT-USB.
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
`linux/` contains OS integration, drivers and user APIs; `games/` and `assets/`
contain game code and artwork; `tools/`, `optimizer/`, `TESTS/` and `docs/`
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
