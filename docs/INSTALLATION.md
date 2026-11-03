# Installation, configuration and builds

This guide covers the host workstation, firmware, FPGA and Linux build paths.
It does **not** claim that a fresh clone currently produces a complete console
without additional inputs. Read the dependency table before starting a long build.

## Supported and experimental targets

| Target | Software profile | Output | Current use |
|---|---|---|---|
| Tang Mega Pro Dock 138K | `prodock` | 800 × 480 LCD | Working demonstrations and SD/USB development |
| Tang Neo / Console 138K | `neo` | 1280 × 720 HDMI | Port under diagnosis; not a ready-to-install release |

Use the matching board profile, pin constraints, memory configuration and image.
A shared processor family does not make the bitstreams interchangeable.

## Hardware connections

1. Use the board's supported power input and verify its polarity/rating against
   that board revision. The development Pro Docks use their auxiliary 12 V input.
2. Connect the Pro Dock LCD or the Neo HDMI display as appropriate.
3. Connect **SOFT-USB** to the PC for the normal console and software-transfer path.
4. Connect the separate FPGA programmer when initially provisioning the FPGA.
5. Insert the intended SD only after identifying which board/card is being updated.

The CPU JTAG connector and the FPGA programmer are different interfaces. A J-Link
is not part of the normal installation/run workflow. Do not connect a CPU probe
by guessing header pins: use the board revision's schematic and connector labels.

With several identical boards, map programmer serial numbers and physical USB
paths before writing anything. SOFT-USB serial strings alone may not be unique.
Never infer the target from `/dev/ttyACM0` or `/dev/sdX` allocation order.

## Host prerequisites

The development host is Linux x86-64. Build components use Python 3, GNU Make,
a C compiler, Git and ordinary archive utilities. The Linux source extractor
uses `tarfile` extraction filters; Python 3.12 is the tested baseline.

Install the packages appropriate to the parts you will use:

| Work | Dependencies |
|---|---|
| Host game/model tests | C compiler, Make, Python 3, Pillow for image output |
| Linux/U-Boot | Git, curl, patch, Make, flex, bison, OpenSSL/ELF development libraries, dtc, cpio, xz/gzip/bzip2 |
| RTL tests | Icarus Verilog, Verilator, C++ compiler; vendor primitive models for relevant tests |
| Mapping/optimizer experiments | Yosys and the separately installed supported tools; see optimizer guide |
| Host USB console/tools | Python `pyserial`; `pyusb` for direct USB tools; usbutils |
| Dashboard checks | Python standard library, Node.js for JavaScript checks |
| Full FPGA build | Licensed Gowin tools and the matching vendor IP/primitive support |

A typical Debian/Ubuntu package base is shown below; names may vary by distro:

```sh
sudo apt install git build-essential python3 python3-venv python3-pil \
  python3-serial python3-usb curl patch flex bison libssl-dev libelf-dev \
  device-tree-compiler cpio xz-utils bzip2 iverilog verilator usbutils
```

This is a prerequisite list, not a tested automated workstation installer.
Do not upgrade a tool underneath another running build. Record versions in
results when reproducing an old candidate.

## Clone and inspect

```sh
git clone https://github.com/Mjxkill/console-prodock.git
cd console-prodock
git rev-parse HEAD
```

Do not initialize FPGA/SD hardware merely to read the documentation or run
host-only game tests. The published MAZE snapshot has its own build recipe in
[`releases/luma3d-maze-20261103`](../releases/luma3d-maze-20261103/README.md).

## Remaining external dependencies

| Input | Current location/contract | Fresh-clone consequence |
|---|---|---|
| Gowin installation | Central path in `tools/gowin_toolchain.py`; lab uses `/home/michael/gowin/IDE`, V1.9.12.03 | Configure the central path for your installation; no documented environment override exists yet |
| Primitive models | `simlib/gw5a/prim_sim.v` under that IDE | Some simulations require the vendor library |
| Firmware toolchain support | `fw_console/Makefile` includes `/home/michael/logic_analyser_wifi/ae350/toolchain.mk` | Separate project support files are still required; not supplied by cloning this repo |
| AE350 SDK | Gowin AE350 SDK v1.3 library used by the firmware toolchain | Obtain under its vendor terms |
| Firmware helper | External `ae350/tools/itcm_init.py`, compatibility headers/linker support | Not yet packaged as a self-contained public dependency |
| Pro Dock FPGA baseline | Geometry builder uses local C37/C28 build snapshots | Full build cannot be reproduced from a bare clone without those inputs |
| Protected reference archives | Paths/checksums in `tang/boards/prodock/reference.json` | Integrity checks require the exact archived material; some archives remain local |
| Linux source archives | Pinned URLs/checksums in `linux/sources.json` | Prepare stage downloads/verifies them; network access required |

Do not create empty placeholders or disable guards to make a missing dependency
appear satisfied. A portable packaging task remains open. Editing installation
paths does not qualify the resulting hardware build.

The firmware build also contains an absolute repository linker-script path.
If relocating it, update that configuration deliberately and retain the same
linker contract; do not scatter copies of common files into board folders.

## Linux source and toolchain versions

The pinned source manifest currently selects:

| Component | Version |
|---|---|
| Linux | 6.12.112 |
| OpenSBI | 1.6 |
| BusyBox | 1.37.0 |
| musl | 1.2.5 |
| Bootlin RV32 ILP32D musl toolchain | stable 2025.08-1 |
| U-Boot source archive expected by its Makefile | 2025.10 |

Use the manifest hashes as the authoritative archive identities. Do not replace
an archive just because its filename matches.

The generated application compiler wrapper is
`linux/build/userbin/riscv32-prodock-linux-gcc`. It uses the project's RV32
floating-point ABI and ISA choices. Do not assume a generic RV32 toolchain's
atomic instructions are valid for every DDR/cache path on this integration.

## Build Linux

First run the current board regression with the required protected inputs:

```sh
python3 tools/run_board_regressions.py --out TESTS/dual_board/my_build_01
```

Then build an explicitly marked candidate:

```sh
make -C linux BOARD=prodock BUILD_ARGS=--candidate all JOBS=4
# Experimental Neo software profile, not a qualified board release:
make -C linux BOARD=neo BUILD_ARGS=--candidate all JOBS=4
```

Stages are `prepare`, `rootfs`, `kernel`, `opensbi`, `package`, `test`.
The Pro Dock output is under `linux/build`; Neo uses `linux/build-neo` for
board outputs. Shared toolchain material remains under the common build area.

The package combines OpenSBI, the kernel, device tree and initramfs. A small
RAM launcher is a development artifact, not a required end-user loading step.
Inspect the generated manifest before associating an image with a demonstration.
The latest MAZE package differs from a default build: its game executable is
explicitly embedded and its SD autostart policy differs.

`--candidate` acknowledges changed inputs. It neither disables source-integrity
checks nor asserts timing/hardware validation.

## Build U-Boot and SD images

After the Linux toolchain and pinned U-Boot source archive are available:

```sh
make -C linux/uboot all JOBS=4
make -C linux sd-boot
python3 linux/sd_package.py --candidate
```

These are build/package commands, not writes to a physical card. The package
builder also requires matching prepared LUMA/ORBITAL assets and firmware.
It creates `linux/build/sd/PRODOCK/` and a manifest with these files:

| File | Purpose |
|---|---|
| `UBOOT.BIN` | Header-wrapped U-Boot |
| `LINUX.BIN` | Header-wrapped Linux/OpenSBI payload |
| `LUMA.BIN`, `LUMA.DAT` | Bare-metal LUMA code/resources |
| `ORBITAL.BIN`, `ORBITAL.DAT` | Bare-metal ORBITAL code/resources |

The `PDCKBOOT` v1 wrapper is 40 bytes and records type, load/entry addresses,
length, capability field and payload/header CRCs. It is not a raw kernel image
and is not a signed-update format. The resident SD loader looks for
`/PRODOCK/UBOOT.BIN`; verify the image format before copying or launching it.

The existing `tools/install_linux_sd.py` is **lab-specific**: it binds to one
USB medium geometry and boot-sector hash, preserves a witness file and refuses
an existing destination. It is not a generic SD formatter/installer. Its
`--check-package` option validates the package without card access:

```sh
python3 tools/install_linux_sd.py --pack linux/build/sd --check-package
```

Do not remove its target checks to use it on another card. A general installer
with explicit device selection is still to be packaged. For a manually managed
card, preserve its partition/filesystem layout expected by the chosen loader,
copy only a verified matching package to its mounted filesystem, sync, unmount,
and verify files after remount. Never format the development card by guessing
a Linux block-device name. Power down the console before removing its SD.

## Build FPGA candidates

Read [board compatibility](../ARCHI/COMPATIBILITE_CARTES.md) and the
[ownership inventory](../tang/boards/ownership.json). With the baseline inputs
and local regression satisfied, relevant entry points include:

```sh
python3 tools/build_gpu_geometry.py --help
python3 tools/build_console_neo.py --help
python3 tools/route_console_neo.py --help
```

A Pro Dock build requires `--candidate` when inputs differ from the protected
reference. Neo candidates are always experimental. Neo currently uses the
restored DDR 5.9 / 300 MHz base with its explicit FIFO adaptation; see its guide
before choosing experimental flags.

Full synthesis and place/route use Gowin. Report generation alone is not a build;
a failed route with unrouted nets does not provide a testable image. Keep the
source manifest, constraints, tool version, logs, utilization and timing beside
any resulting bitstream.

Do not program the first available device. The board tools include hardcoded
lab identities in several historical paths (`tools/load_linux.py`,
`tools/load_ilm.py`, `tools/check_gpu_reloads.py`). They are development scripts,
not safe generic commands for a visitor's machine. CPU JTAG loaders are not
part of normal setup.

## First successful installation: acceptance checklist

1. Correct board-specific persistent FPGA configuration loads after power-off.
2. SOFT-USB enumerates at HS and exposes the expected identity/console.
3. SD bootstrap finds and verifies U-Boot, then Linux; logs identify the package.
4. Linux exposes the display/GPU devices and a usable shell without a debugger.
5. The selected game launches and exits; layout switching remains operational.
6. USB transfer/readback and an application update work through the normal port.
7. Repeat cold boot and disconnect/reconnect, keeping the old image available.

The complete checklist is not yet qualified on Pro Dock, and Neo is further
from this state. Document an incomplete stage as incomplete; do not use J-Link
to silently turn a failed installation into a successful demo.
