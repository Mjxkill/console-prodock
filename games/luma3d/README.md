# LUMA3D / MAZE

LUMA3D is a native Linux adventure prototype for the console's G3D1 geometry
engine and GPU V1 rasterizer. It combines a third-person 3D world with puzzles,
arcade activities and table games. It is real-time rendering, not video playback.
The current content is a working prototype rather than the finished multi-hour
campaign envisaged for the project.

The demonstrated **MAZE release of 3 November 2026** has a
[frozen source and executable package](../../releases/luma3d-maze-20261103/README.md).
That package is the reproducible reference for the released game. The older
canonical sources and Makefile in this directory are a development baseline;
they do not reconstruct every later festival feature by themselves.

| Topic | Guide |
|---|---|
| Activities, controls, graphics and measured performance | [Game guide](../../docs/GAMES.md) |
| Linux installation and SD packages | [Installation](../../docs/INSTALLATION.md) |
| Terminal connection, layouts and launching applications | [Linux console](../../docs/LINUX_CONSOLE.md) |
| Graphics API and development | [Software development](../../docs/SOFTWARE_DEVELOPMENT.md) |
| Detailed dated content inventory | [CONTENT_STATUS.md](CONTENT_STATUS.md) |
| Arcade activity rules | [Minigames](minigames/README.md) |

## Rendering architecture

The CPU computes simulation, collisions, camera movement and object matrices.
Models and textures live in GPU-reserved DDR. G3D1 transforms vertices, clips
triangles to the view volume, projects them and calculates lighting; GPU V1
handles textured rasterization, depth, fog and composition. Camera and character
coordinates are calculated at runtime. The autopilot uses the game's movement
and interaction paths.

The Pro Dock profile renders a 400×240 RGB565 scene scaled to its 800×480 LCD.
The 640×360 scene / 1280×720 Neo profile is covered by local software tests;
that does not qualify physical Neo rendering. [Architecture](../../docs/ARCHITECTURE.md)
separates mesh rendering, native 2D sprites, composition layers and their uses.

Prepared artwork and textures supply materials for the 3D scene; they do not
replace the landscape with a prerecorded movie. The release manifest records
its source/resource identities. The MAZE texture-publication change is a cache
correctness fix, not a claimed FPS improvement.

## Rebuild the released version

From the repository root:

```sh
python3 releases/luma3d-maze-20261103/build.py --verify-only
python3 releases/luma3d-maze-20261103/build.py --target host --cc gcc --out /tmp/maze-host-new
python3 releases/luma3d-maze-20261103/build.py --target riscv \
  --cc /absolute/path/to/riscv32-prodock-linux-gcc --out /tmp/maze-riscv-new
```

Use a new output directory and a compatible project RV32 compiler wrapper.
The script verifies the frozen archive, preserves its source bytes, and records
compiler output and executable hashes. A host executable uses `--host`; its
software execution time is not an FPGA frame-rate measurement.

To work on the older canonical baseline instead:

```sh
make -C games/luma3d all riscv
make -C games/luma3d test
python3 games/luma3d/tests/test_render_contract.py \
  --out games/luma3d/build/render-contract-new
```

The Linux kernel must expose G3D1 commands 31–34 and geometry status. The game
checks these capabilities before rendering; the historical NEBULA R17 kernel
without the geometry extension is a different platform package.

## Run and control

Once Linux and the executable are installed, launch the automatic festival:

```sh
/bin/luma3d-maze --festival
```

The world uses WASD to move, I/U/K/L for the camera, space to jump, E to interact,
J for the journal and T for automatic mode. Activities interpret keys according
to their rules. Tab returns from festival activities; Q is context-sensitive
and can enter a letter in Hangman. Return to the world before quitting.
Only one rendering application owns the GPU at a time.

## Evidence and remaining work

The [3 November hardware record](../../TESTS/prodock_game_restore_20261103/TEST_RECORD.md)
identifies the released executable, conditions and telemetry. Its four measured
windows were 5.55, 13.36, 32.91 and 28.12 FPS, not a whole-game average or constant
cadence. Performance varies substantially by scene; broader optimization and
campaign development remain open.

Earlier renderer, collision, save-game and activity tests remain under `tests/`.
[The G22r0 feature audit](tests/G22R0_FEATURE_AUDIT.md) records which hardware
facilities the earlier renderer used. Dated reports and Git history preserve
the old R1–R6/GM1 measurements and build identities. Old process IDs and temporary
paths are historical observations, not current launch instructions. See
[the test guide](../../docs/TESTING.md) for the distinction between software
simulation, reference images, FPGA timing and board validation.
