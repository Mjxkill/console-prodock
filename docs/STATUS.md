# Project status

Updated **3 November 2026**.

**The Tang Mega Pro Dock runs the project's graphics demonstrations and Linux
games. The Tang Neo port is still in development.** The next major delivery is
a complete installation and startup experience: boot from SD, connect through
SOFT-USB, and load games without a CPU debugger.

[Watch the demonstration video](https://youtu.be/G8LfKqb-1sY) ·
[Explore the games](GAMES.md) · [Installation guide](INSTALLATION.md)

## Which board can run it?

| Board | What works today | What remains to finish |
|---|---|---|
| **Tang Mega Pro Dock 138K** | Real-time 2D/3D graphics and Linux games on its **800 × 480 LCD**, with a text terminal and on-screen diagnostics | Reliable automatic startup from SD, a complete USB loading/update workflow, and faster game loading |
| **Tang Neo / Console 138K** | **720p HDMI test patterns** have been displayed | The graphics engine still needs debugging before Linux games can be offered on this board |

These boards are two targets for the same console project. They use shared
graphics and software components, with adaptations for their display, pinout
and hardware connections. Working Pro Dock demonstrations do not mean the Neo
port is ready to use.

## What can the console do?

The following capabilities have been demonstrated on the **Pro Dock**:

| Feature | What it provides |
|---|---|
| Hardware 2D graphics | Scrolling backgrounds, tiles, sprites, text and image copies |
| Hardware 3D graphics | Textured objects, depth testing, perspective and lighting |
| Visual effects | Transparency, additive blending and fog |
| Linux applications | Games run as executables launched from the console shell |
| Shared display | Game, Linux terminal and GPU/USB/SD status visible together |
| Full-screen modes | Switch between the game, terminal and shared layout |
| USB terminal | Connect a PC to the board's SOFT-USB port to enter commands |
| Games and demonstrations | Space shooters, cinematic demonstrations, exploration, puzzles and board-game activities |

The graphics engine supports 16 composition layers and 64 native 2D sprites.
A particular scene may use fewer; performance depends on its drawing and memory
workload. The [architecture guide](ARCHITECTURE.md) explains how the CPU and FPGA
share the rendering work.

## What is still being developed?

### Installation, startup and updates

Linux has booted from an SD card during development. The full sequence from
power-on to an automatically launched game still needs to be completed and
repeatedly tested.

SOFT-USB is intended for both the terminal and software transfers. The terminal
exists; the complete game/kernel installation and update workflow is unfinished.
USB2 High-Speed is the target. A CPU debugger is not part of the normal user
experience. See [SOFT-USB](USB_TRANSPORT.md) for the implementation status.

The repository includes source code, build tools and a reproducible snapshot
of the demonstrated game. Some full-system build dependencies still need to be
prepared separately, so this is not yet a download-and-play console release.
The [installation guide](INSTALLATION.md) identifies those dependencies.

### Loading speed and game performance

SD reads are slower than expected. Work is ongoing to locate the cost in the
controller, driver and operating-system path before changing the implementation.
This affects boot and loading times.

Game performance also varies by scene. Earlier compact demonstrations are
smoother than some views in the larger exploration game. More consistent frame
times, richer scenery and polished activities remain active development goals.
Measurements and their conditions are in [optimization](OPTIMIZATION.md) and
[SD performance](SD_SPI.md).

### Game content

The project includes several demonstrations and a developing exploration game
with arcade, puzzle and board-game activities. The ambition is a varied world
with hours of play; the current version is not a finished multi-hour campaign.
Integrated audio, broader movement/vehicle systems and persistent saves still
need work. See [the game guide](GAMES.md) for the actual content and controls.

### Tang Neo support

HDMI test patterns work, but the full graphics engine is not yet reliable on
the Neo. Some drawing commands are rejected, and the latest experimental FPGA
build could not finish routing. There is no ready-to-use Neo game image at this
stage. The investigation is documented in [the Neo port guide](NEO_PORT.md).

## What can visitors try now?

- Watch the video and explore the architecture, graphics API and source code.
- Build the [published game snapshot](../releases/luma3d-maze-20261103/README.md)
  and run its host-side checks without a board.
- Follow the [Linux console guide](LINUX_CONSOLE.md) to launch installed games
  on a Pro Dock already running a compatible FPGA/Linux package.
- Use the [testing guide](TESTING.md) to reproduce the available software and
  simulation checks, with their stated dependencies.

The public code is a development platform. Demonstrated operation does not mean
every later FPGA build, USB reconnect sequence or game scene has been tested.
Some older working builds retain documented timing and USB issues; exact
results belong to the technical records below.

## Technical records

Developers can find build identifiers, hashes, measurements and outstanding
hardware checks in these documents:

- [Detailed development snapshot](development/STATUS_20261103.md)
- [Test coverage and results](TESTING.md)
- [Neo investigation](NEO_PORT.md)
- [Latest Pro Dock game test record](../TESTS/prodock_game_restore_20261103/TEST_RECORD.md)

The personal non-commercial license for eligible original development and its
component exceptions are described in [the license scope](../LICENSE_SCOPE.md).
