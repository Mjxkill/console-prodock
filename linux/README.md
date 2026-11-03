# Linux on the Pro Dock and Neo console

This directory contains the pinned **Linux 6.12.112, OpenSBI 1.6, BusyBox 1.37.0
and musl 1.2.5** port for the console's Andes AE350/A25 CPU. The shared GPU,
text-console and SPI drivers serve the board profiles; display wiring, device
trees and Neo controller input remain profile-specific.

Start with the English manual:

| Topic | Guide |
|---|---|
| Prerequisites, builds and SD packages | [Installation](../docs/INSTALLATION.md) |
| SOFT-USB login, layouts and launching games | [Linux console](../docs/LINUX_CONSOLE.md) |
| GPU interfaces and memory ownership | [API reference](../docs/API_REFERENCE.md) |
| SPI implementation and measured performance | [SD and SPI](../docs/SD_SPI.md) |
| Neo hardware qualification | [Neo port](../docs/NEO_PORT.md) |
| CPU debugger wiring and target settings | [Debugging connections](../docs/DEBUGGING.md) |
| Versions, upstream archives and notices | [Provenance](PROVENANCE.md), [sources.json](sources.json) |

## What has run on hardware

Pro Dock runs Linux, its hardware text console, the GPU dashboard and native
games. The R6 test of 30 October 2026 demonstrated **resident ROM → U-Boot from
SD → Linux from SD → game autostart**, with graphics and telemetry observed
without CPU program injection or UART launch commands. The FPGA was loaded into
SRAM for that test; flash programming and FPGA power-on configuration were not
part of it. SD transfer speed remains under investigation. See the exact
[boot receipt](../TESTS/prodock_new_20261028/sd_update_20261030_01/boot_observation.json).

The Neo 720p profile shares the software interface, but the complete DDR-backed
GPU path is still under hardware diagnosis. Host simulation or Pro Dock results
do not qualify that board. [Current status](../docs/STATUS.md) separates these
results from historical versions.

## Runtime interfaces

| Function | Interface |
|---|---|
| Serial console | CPU `/dev/ttyS0` over FPGA CDC; host `/dev/ttyACM*`, 115200 baud |
| SD | `/dev/mmcblk0`, native ATCSPI200 plus Linux `mmc_spi` |
| Text console | `/dev/tty1`, framebuffer tileblit with hardware glyph composition |
| Layout and dashboard | `/dev/prodock-display`, `prodockctl layout` / `display` |
| Rendering accelerator | `/dev/prodock-gpu`, ioctl/mmap, one rendering owner |
| Geometry | G3D1 commands 31–34 and `PRODOCK_GEOMETRY_INFO` in compatible kernels |
| Applications | `prodock-game`, [NEBULA](NEBULA.md), [LUMA3D / MAZE](../docs/GAMES.md) |

Pro Dock split mode has a 400×240 game view at the upper left, text at the upper
right and diagnostic tables below. Full-screen game and console modes are
available. Linux reserves composition layers 12–15 and a separate display memory
area; applications use the exposed GPU window. The driver validates descriptors,
waits for completion and presents at vertical blank. The interface is for trusted
games; it is not a DRM/Mesa/OpenGL stack or hardware isolation for untrusted code.

Linux and bare-metal demonstrations are separate boot modes. The U-Boot menu
provides `prodockboot linux`, `prodockboot luma` and `prodockboot orbital` for
corresponding installed images. Linux does not run those bare-metal programs
concurrently with the kernel.

## Build and local checks

Prepare the dependencies and selected board profile using the installation guide.
From the repository root, a development build uses:

```sh
make -C linux BOARD=prodock BUILD_ARGS=--candidate all JOBS=4
make -C linux test
python3 linux/tests/test_boot_images.py
python3 linux/tests/test_orbital_api.py
python3 linux/tests/test_atomic_code.py
```

U-Boot and SD image preparation are separate steps:

```sh
make -C linux/uboot all JOBS=4
make -C linux sd-boot
python3 linux/sd_package.py --candidate
```

The SD packager writes local files under `linux/build/sd/PRODOCK/`; it does not
format or mount a physical card. It consumes the built U-Boot/Linux payloads
and prepared LUMA/ORBITAL assets. Its `PDCKBOOT` headers carry image type,
addresses, length, capabilities and CRC32; manifests add SHA-256. These checks
detect corruption, not an authenticated secure-boot signature. Package contents
and installation prerequisites are detailed in [Installation](../docs/INSTALLATION.md).

Sources, toolchains and outputs are kept under `linux/build/`. Archives are
pinned by SHA-256. The project compiler wrapper under `build/userbin/` uses the
adapted musl and RV32 ILP32D configuration; an arbitrary precompiled RISC-V
executable is not an equivalent test of this platform.

## AE350-specific integration

The port includes adaptations for this A25 configuration: single-core kernel
atomics, OpenSBI/musl atomic preloads, PTE/PMD synchronization and an SBI service
for CPU/GPU cache maintenance. The detailed origins are in [PROVENANCE.md](PROVENANCE.md).
`pgprot_noncached()` alone does not establish an uncached GPU window on this
configuration; the driver performs explicit synchronization at ownership
boundaries. Applications must keep surfaces and mesh data stable while used by
the accelerator. Cache/DMA integration is still a separate development topic.

The earlier C37/R12 and G22r0 desktop tests remain in
[Linux validation](../TESTS/LINUX_PRODOCK_20261009.md),
[shared display validation](../TESTS/LINUX_DESKTOP_20261011.md) and
[NEBULA validation](../TESTS/NEBULA_20261012.md). They record their own versions
and limits; the [current test guide](../docs/TESTING.md) describes the ongoing
qualification process.
