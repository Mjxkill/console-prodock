# Games and real-time demonstrations

## Choose a game or demo

All five applications are part of this project. LUMA and LUMA3D are different
programs; the MAZE release does not replace the earlier demonstrations.

| Application | What you see | Runtime | Where to start |
|---|---|---|---|
| **LUMA — The Firefly Sanctuary** | Automatic forest adventure and a GPU effects finale | Bare-metal AE350 firmware | [Resources](../games/luma/assets/README.md), [program](../games/luma/src/luma_main.c) |
| **ORBITAL — Station Aurora** | Automatic first-person station tour, drones and combat | Bare-metal AE350 firmware | [Resources](../games/orbital/assets/README.md), [program](../games/orbital/src/orbital_main.c) |
| **ASTRILLA** | Five-minute space journey, black hole, battle and alien landscape | Bare-metal AE350 firmware; a later variant uses G3D1 | [Cinematic design](../ARCHI/ASTRILLA.md), [program](../games/astrilla/src/astrilla_main.c) |
| **NEBULA — Rift Raiders** | Playable space shooter with an automatic demo | Linux | [Controls and tests](../linux/NEBULA.md), [program](../games/nebula/src/nebula.c) |
| **LUMA3D / MAZE** | Third-person exploration, a 3D maze and a festival of activities | Linux | [Exact release](../releases/luma3d-maze-20261103/README.md), sections below |

The applications in this repository combine RISC-V game logic with rendering
and display composition in a Gowin FPGA. They are not video playback. Textures,
meshes and some cinematic backgrounds are prepared offline; the board evaluates
the animation and submits graphics commands while the application runs.

The current Linux game is **LUMA3D / MAZE**, demonstrated on the Sipeed Tang Mega
Pro Dock. Its [source and executable package](../releases/luma3d-maze-20261103/README.md)
includes the exact version tested on **3 November 2026**, with instructions to
rebuild it. Developers can find the binary identities and test conditions in
the [hardware test record](../TESTS/prodock_game_restore_20261103/TEST_RECORD.md).

## LUMA3D: exploration and activities

LUMA3D is a native Linux game with a third-person 3D world. The existing
adventure contains two small regions: a valley and terraces with a basin and
observatory. The player can walk, run and jump, talk to inhabitants, complete
short quests, open routes and enter activities. It is a working prototype,
not a finished multi-hour campaign.

The adventure's activity set includes:

| Activity | What is implemented |
|---|---|
| Firefly circuit | Rotate connections to complete a circuit. |
| Falling blocks | Move and rotate pieces, clear rows and handle defeat/restart. |
| Shape workshop | Align and place coloured shapes on their targets. |
| Crystal 1024 | Slide and merge numbered tiles under deterministic rules. |
| House of lights / MAZE | Explore a 3D maze, collect lights and evade pursuers. |
| Simon | Repeat a colour sequence, with animated lighting. |
| Space shooter | Move a ship, shoot enemies and face a boss. |
| Platform tower | Navigate a 3D obstacle challenge. |

The newer festival adds a garden hub, four table games and a separate Memory
scene: **Othello**, **Solitaire**, **Chroma** (a colour-card game), **Hangman**
and **Memory**. These are present in the released executable. Card, board and
actor presentation includes interpolated movement; simulation state remains
separate from visual interpolation. The automatic tour uses ordinary game
actions and bounded visits. An unfinished table does not become a completed
game merely because the tour moves to the next stand.

The older [content inventory](../games/luma3d/CONTENT_STATUS.md) and
[minigame rules](../games/luma3d/minigames/README.md) describe dated milestones.
They predate some festival additions. The immutable release sources are the
authority for the executable named above; the old canonical Makefile alone
does not reconstruct it.

## How the 3D scene is drawn

The CPU handles input, simulation, collisions, camera movement, object matrices
and conservative visibility decisions. It generates or reuses scene resources
and submits commands. The **G3D1 hardware** reads indexed meshes from DDR,
transforms vertices, clips triangles, projects them and computes directional
lighting. **GPU V1** then performs textured rasterisation, perspective
correction, depth tests and colour writes.

The house maze uses real 3D wall and actor meshes. Its static walls are reused;
animated actor geometry uses alternating buffers. The camera is evaluated at
runtime, rather than selected from a sequence of rendered maze pictures.
The MAZE release adds an ordered texture-cache invalidation after the initial
CPU texture upload. That is a correctness change, not a measured FPS increase.

The world, table games and older demos exercise different combinations of the
GPU. A scene does not automatically use all 16 composition layers or all 64
native sprites. Mesh characters and 3D billboards are not those native 2D
sprites. See [architecture](ARCHITECTURE.md) for the distinction between
composition, raster effects and geometry acceleration.

## Running and controlling the released game

After the platform has booted Linux and the executable is installed:

```sh
/bin/luma3d-maze --festival
```

This starts the automatic festival tour. The program also supports a manual
mode, world showcase and individual festival windows; the release source's
`main.c` defines the exact options. Do not launch a second GPU application
while another owns the accelerator.

World controls use the terminal keyboard: WASD movement, I/U/K/L camera,
space to jump, E to interact, J for the journal and T for the autopilot.
Activities interpret keys according to their rules. Tab returns from festival
activities; Q is context-sensitive, including letter input in Hangman, so it
is not an unconditional process-termination key. Use the normal return path
to the world before quitting.

The 1280×720 host profile is useful for software regression. It does not
qualify the Neo board, and it must not be selected as the physical output
profile for the Pro Dock's 800×480 LCD. The [release guide](RELEASES.md)
identifies the working Pro Dock FPGA and the separate SD-boot and game tests.

## Application files and resources

The packaged graphics are runtime resources, not prerecorded game videos.
Keep them with the matching program; resource headers, CRCs and manifests are
checked by the relevant applications.

```text
assets/
  luma/source/          forest, hero, enemies, final portrait
  luma/packed/          luma.bin + luma_fw.bin + manifests
  orbital/source/      station textures, sky, weapon and drones
  orbital/packed/       orbital.bin + orbital_fw.bin + manifests
  astrilla/source/     ships, planets, wormhole and alien vegetation
  astrilla/packed/      astrilla.bin + astrilla_fw.bin + manifests
  nebula/source/       fleet and space illustrations
  nebula/packed/        nebula.bin + manifest
fw_console/            bare-metal programs and shared GPU interfaces
linux/userspace/       NEBULA and the Linux graphics library
games/luma3d/          maintained game sources and activity modules
releases/luma3d-maze-20261103/
  source.tar.gz        exact 132-file MAZE source/resource snapshot
  luma3d-riscv.gz       exact tested RV32 Linux executable
  MANIFEST.json        source hashes, compiler arguments and provenance
```

| Resource package | Bytes | Companion program |
|---|---:|---|
| [LUMA](../games/luma/assets/packed/manifest.json) | 3,245,216 | `luma_fw.bin`, 27,128 bytes |
| [ORBITAL](../games/orbital/assets/packed/manifest.json) | 5,781,728 | `orbital_fw.bin`, 45,056 bytes |
| [ASTRILLA](../games/astrilla/assets/packed/manifest.json) | 9,849,408 | `astrilla_fw.bin`, 61,776 bytes; this checked-in pair is the older C37 variant |
| [NEBULA](../games/nebula/assets/packed/manifest.json) | 435,584 | `nebula` Linux executable |
| [MAZE](../releases/luma3d-maze-20261103/MANIFEST.json) | Resources embedded in the executable | 16,684,812-byte uncompressed RV32 ELF |

The checked-in LUMA/ORBITAL firmware manifests name the earlier R31 reference;
the ASTRILLA firmware manifest names C37. These historical bindings are retained
as evidence. They do not assert that every packaged demo was retested with the
current R6 release. G3D1 ASTRILLA is built separately by
[`build_geometry_apps.py`](../tools/build_geometry_apps.py), with the exact
geometry-enabled FPGA stage supplied to `--stage`; it preserves the older pack.

### Build entry points

See [software development](SOFTWARE_DEVELOPMENT.md) and
[installation](INSTALLATION.md) for toolchains. The relevant source entry points
are:

| Application | Build entry point | Important input |
|---|---|---|
| LUMA | [`tools/build_luma.py`](../tools/build_luma.py) | Matching images and bare-metal toolchain; historical R31 binding |
| ORBITAL | [`tools/build_orbital.py`](../tools/build_orbital.py) | Matching images and bare-metal toolchain; historical R31 binding |
| ASTRILLA | [`tools/build_astrilla.py`](../tools/build_astrilla.py) | Original image pack and meshes; C37 variant |
| G3D1 ASTRILLA | [`tools/build_geometry_apps.py`](../tools/build_geometry_apps.py) | Explicit geometry-enabled FPGA stage and its source manifest |
| NEBULA | [`linux/build.py`](../linux/build.py), rootfs stage | [`build_nebula_assets.py`](../tools/build_nebula_assets.py) and Linux userspace compiler |
| Exact MAZE release | [`releases/luma3d-maze-20261103/build.py`](../releases/luma3d-maze-20261103/build.py) | Verified immutable archive and host/RV32 compiler |

The older bare-metal builders retain historical local toolchain/reference
dependencies. Read their manifests and the installation dependency list before
using them in a fresh clone. Rebuilding current sources is distinct from
reproducing a previously measured executable.

### Launch paths

In the existing U-Boot console, the implemented commands are:

```sh
prodockboot luma
prodockboot orbital
prodockboot linux
```

The [U-Boot command implementation](../linux/uboot/overlay/board/prodock/console/board.c)
loads the corresponding `PRODOCK/LUMA.BIN` + `LUMA.DAT`, `ORBITAL.BIN` +
`ORBITAL.DAT`, or `LINUX.BIN` from SD and validates their wrappers and CRCs.
The packed `.bin` files under `assets/` are raw application/resource inputs;
they are not interchangeable with these `PDCKBOOT`-wrapped SD files.
ASTRILLA is not an option in this U-Boot menu yet.

Under Linux, once the programs and their resources are installed:

```sh
nebula --demo
# After leaving NEBULA, start the separate game:
/bin/luma3d-maze --festival
```

NEBULA's data package is installed as `/usr/share/nebula/nebula.bin` by the
Linux rootfs builder. MAZE embeds its resources. Only one application should
own the GPU at a time. These commands name existing applications; they do not
assert that every software package automatically installs all five demos.

## Performance and remaining work

The 3 November restoration produced four distinct telemetry windows:
**5.55, 13.36, 32.91 and 28.12 FPS**. They are neither an overall average nor
a constant-frame-rate claim. Graphics became ready after 4.607 seconds. The
game was left running; that run includes no final campaign-wide GPU counter
check and no user visual confirmation at the time of the record.

Earlier tours and profiling show uneven performance and long frames. The
current diagnostic work separates simulation, UI preparation, GPU submission
and presentation waits. Host timing and image equivalence are useful tests,
but they do not establish FPS on the FPGA board. Improvements to CPU clearing
or publication traffic must be measured on the same scene before a speedup
is claimed.

The principal unfinished areas are:

- A sustained campaign with enough distinct content for several hours.
- More consistent frame pacing and better performance in heavy views.
- Integrated audio and gamepad input for this game.
- Qualified persistent saves across reboot; `/tmp` saves are volatile.
- Mounts, vehicles and the broader traversal systems proposed for the future.
- Complete visual and endurance qualification of every activity on each board.

## Earlier applications

These demonstrate different workloads; their performance cannot be transferred
to the larger Linux game without measurement.

| Application | Scope | Rendering and limits |
|---|---|---|
| [LUMA — The Firefly Sanctuary](../games/luma/assets/README.md) | Automatic forest adventure, bare-metal | Scrolling indexed scenery, animated characters and effects, followed by a GPU effects finale. Scripted staging, not a playable campaign; no sound in that version. |
| [ORBITAL — Station Aurora](../games/orbital/assets/README.md) | Automatic first-person station tour, bare-metal | Perspective textures, depth, fog, translucent/additive effects, tilemaps and HUD. Rooms, enemies and combat are scripted. The dated C37/R6 test reports 54.81 FPS; this is not a LUMA3D benchmark. |
| [ASTRILLA](../ARCHI/ASTRILLA.md) | Five-minute automatic space journey, bare-metal | Later versions use G3D1 for animated mesh objects. Distant illustrated panoramas and prepared camera views remain part of the cinematic background system. It is not a freely navigable 3D campaign. |
| [NEBULA — Rift Raiders](../linux/NEBULA.md) | Playable Linux space shooter with an automatic demo | Three sectors, enemy waves, bosses and novas. Uses native 2D sprites, layers, tiles and raster effects rather than the G3D1 world path. |

These applications are original project demonstrations. They are not commercial
game ports or claims of compatibility with a commercial console API.
