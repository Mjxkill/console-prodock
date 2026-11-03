# Games and real-time demonstrations

The applications in this repository combine RISC-V game logic with rendering
and display composition in a Gowin FPGA. They are not video playback. Textures,
meshes and some cinematic backgrounds are prepared offline; the board evaluates
the animation and submits graphics commands while the application runs.

The current Linux executable is **LUMA3D / MAZE**, restored on the second Sipeed
Tang Mega Pro Dock on **3 November 2026** with FPGA R6. Its SHA-256 is
`2e552dd1cc9b73756b68040b75c4c0a8f9c62c6584dbadd4fcb38e7933c4b985`.
The [source and executable release](../releases/luma3d-maze-20261103/README.md)
preserves that exact version. The [restoration test record](../TESTS/prodock_game_restore_20261103/TEST_RECORD.md)
identifies what was actually checked on the board.

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
profile for the Pro Dock's 800×480 LCD. SD boot and SOFT-USB are the intended
normal deployment route. J-Link is reserved for explicitly agreed diagnostics;
the recent RAM restoration is a recorded diagnostic procedure, not a normal
installation requirement or proof of complete USB deployment.

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
| [LUMA — The Firefly Sanctuary](../assets/luma/README.md) | Automatic forest adventure, bare-metal | Scrolling indexed scenery, animated characters and effects, followed by a GPU effects finale. Scripted staging, not a playable campaign; no sound in that version. |
| [ORBITAL — Station Aurora](../assets/orbital/README.md) | Automatic first-person station tour, bare-metal | Perspective textures, depth, fog, translucent/additive effects, tilemaps and HUD. Rooms, enemies and combat are scripted. The dated C37/R6 test reports 54.81 FPS; this is not a LUMA3D benchmark. |
| [ASTRILLA](../ARCHI/ASTRILLA.md) | Five-minute automatic space journey, bare-metal | Later versions use G3D1 for animated mesh objects. Distant illustrated panoramas and prepared camera views remain part of the cinematic background system. It is not a freely navigable 3D campaign. |
| [NEBULA — Rift Raiders](../linux/NEBULA.md) | Playable Linux space shooter with an automatic demo | Three sectors, enemy waves, bosses and novas. Uses native 2D sprites, layers, tiles and raster effects rather than the G3D1 world path. |

These applications are original project demonstrations. They are not commercial
game ports or claims of compatibility with a commercial console API.
