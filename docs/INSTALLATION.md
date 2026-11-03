# Installation and reconstruction

There are two ways to start: install the selected board image and SD package,
or build from source. The commands below run from the repository root unless
stated otherwise.

## Choose your board

| Board | FPGA image | Display and software |
|---|---|---|
| **Tang Mega Pro Dock 138K** | [R6](../releases/fpga/prodock_r6/README.md) | 800 × 480 LCD, hardware graphics, Linux and SD game startup |
| **Tang Neo / Console 138K** | [REJECT R1 diagnostic](../releases/fpga/neo_reject_r1/README.md) | 720p HDMI test pattern and diagnostic access; games are not operational |

For downloads and **SRAM/flash programming commands**, start with
[Board releases](RELEASES.md). For the Pro Dock, copy the
[selected SD package](../releases/prodock-sd/README.md) to a FAT32 card.
The SD boot sequence works; its loading speed is a current optimization target.

Connect the board's power input, the LCD or HDMI display, the FPGA programmer,
and SOFT-USB. Connect the PC terminal as described in [Linux console](LINUX_CONSOLE.md).
The [debugger guide](DEBUGGING.md) gives CPU JTAG pins and connection settings.

## Host tools

The tested build host is x86-64 Linux with Python 3.12. On Debian/Ubuntu:

```sh
sudo apt install git build-essential python3 python3-venv python3-pil \
  python3-serial python3-usb curl patch flex bison libssl-dev libelf-dev \
  device-tree-compiler cpio xz-utils bzip2 iverilog verilator usbutils

git clone --depth 1 https://github.com/Mjxkill/console-prodock.git
cd console-prodock
```

Install **Gowin IDE V1.9.12.03** and configure its license using the vendor's
installer. For bare-metal firmware also install **Gowin AE350 SDK v1.3** and
GMD's RISC-V GCC toolchain. Set their locations; these are examples to adapt to
your installation:

```sh
export GOWIN_IDE="$HOME/gowin/IDE"
export AE350_SDK="$HOME/ae350/sdk/RiscV_AE350_SOC_V1.3/library"
export CROSS_COMPILE="$HOME/gowin/GMD_2025.01_linux/GMD/toolchain/gowin/gcc_riscv/bin/riscv-none-elf-"
```

`GOWIN_IDE` must contain `bin/gw_sh` and `simlib/gw5a/prim_sim.v`.
`AE350_SDK` must point to the **library** directory containing `bsp/`.
`CROSS_COMPILE` includes the trailing hyphen. A compiler installed on `PATH`
can instead use `export CROSS_COMPILE=riscv-none-elf-`.
The firmware Makefile also accepts the historical `TC` alias.

The Gowin launcher uses offscreen Qt. On systems needing a different FreeType
library, set `GOWIN_FREETYPE` to its absolute path, or `off` to disable the
host-library preload. Linux's application toolchain is downloaded separately
by the Linux build; it does not use the bare-metal compiler above.

## Rebuild exactly the selected FPGA version

The two packages contain their complete frozen build inputs, checksums and
recipes. Each command creates a **new output directory**:

```sh
# Pro Dock R6: synthesize application RTL and route with its frozen vendor IP.
python3 tools/rebuild_release.py --board prodock --out build/prodock-r6 --stage all

# Neo REJECT R1: reroute the published instrumented netlist.
python3 tools/rebuild_release.py --board neo --out build/neo-reject-r1 --stage all
```

Add `--prepare-only` with a fresh output directory to extract and verify inputs
without starting Gowin. Pro Dock also supports `--stage syn`. Neo's diagnostic
package is a **netlist reroute**, not a reconstruction of its instrumentation
from RTL; use the development builder below for a new Neo RTL build.

The release manifests identify the exact historical bitstreams. Rebuilding
produces a new bitstream whose timing and board operation must be checked.
The source snapshot and the current development tree have separate identities.

## Prepare the development build

The baseline inputs and reference archives needed by the development builders
are supplied in this repository. Install them once:

```sh
python3 tools/bootstrap_build.py
python3 tools/board_contract.py
python3 tools/run_board_regressions.py --out TESTS/dual_board/first_build
```

The bootstrap verifies SHA-256 and preserves existing files. If a local input
differs, it reports that file instead of overwriting it. The regression includes
both board profiles, DDR/USB/GPU simulations, text, game and SPI tests. Run it
again into a new output directory after changing build inputs.

Icarus and Verilator must be on `PATH`. A separately installed Icarus can use
`IVERILOG`, `VVP` and, if needed, `IVL_ROOT` environment variables for the USB
simulation. Gowin primitive models come from `GOWIN_IDE`.

## Build bare-metal firmware

The firmware support, linker support and ITCM converter are now in
`fw_console/`; no sibling analyser checkout is needed.

```sh
make -C fw_console
make -C linux sd-boot

# Application packages; images/resources are under games/<name>/assets/packed/.
python3 tools/build_luma.py
python3 tools/build_orbital.py
python3 tools/build_astrilla.py
```

`fw_console/build/console_test.bin` is the default firmware output. The SD
loader uses `fw_console/build/linux_sd_boot/`. Each application builder writes
its own firmware and resource manifest. See [Games](GAMES.md) for all five
applications and their loading modes.

## Build current Linux

The versioned inputs in `linux/sources.json` are downloaded and checked:

| Component | Pinned version |
|---|---|
| Linux | 6.12.112 |
| OpenSBI | 1.6 |
| BusyBox | 1.37.0 |
| musl | 1.2.5 |
| Bootlin RV32 ILP32D toolchain | stable 2025.08-1 |
| U-Boot | 2025.10 |

Downloads are cached in `linux/downloads/`. Override with
`export CONSOLE_DOWNLOADS=/path/to/your/cache` to reuse a separate cache.

```sh
make -C linux BOARD=prodock BUILD_ARGS=--candidate all JOBS=4
# Experimental Neo software build:
make -C linux BOARD=neo BUILD_ARGS=--candidate all JOBS=4
```

The stages are `prepare`, `rootfs`, `kernel`, `opensbi`, `package`, `test`.
Pro Dock outputs are in `linux/build/`; Neo outputs are in `linux/build-neo/`.
The common cross-toolchain is kept under `linux/build/`. The application compiler
wrapper is `linux/build/userbin/riscv32-prodock-linux-gcc`.

## Build U-Boot and an SD package

After the Linux build and the LUMA/ORBITAL builders above:

```sh
make -C linux/uboot all JOBS=4
make -C linux sd-boot
python3 linux/sd_package.py --candidate
```

The output is `linux/build/sd/PRODOCK/`:

| File | Content |
|---|---|
| `UBOOT.BIN` | U-Boot with the console boot header |
| `LINUX.BIN` | OpenSBI, Linux, device tree and initramfs payload |
| `LUMA.BIN`, `LUMA.DAT` | LUMA executable and resources |
| `ORBITAL.BIN`, `ORBITAL.DAT` | ORBITAL executable and resources |

The resident loader reads `/PRODOCK/UBOOT.BIN`. These files use a 40-byte
`PDCKBOOT` v1 header with addresses, length and CRCs, rather than raw kernel
files. Copy the `PRODOCK` directory onto the mounted FAT32 SD filesystem, sync
and unmount. The [prebuilt package instructions](../releases/prodock-sd/README.md)
show the file layout and checksum verification.

A current default build contains NEBULA; the selected SD demonstration also
contains LUMA3D and its startup configuration. To build the newer MAZE snapshot:

```sh
python3 releases/luma3d-maze-20261103/build.py --target riscv \
  --cc "$PWD/linux/build/userbin/riscv32-prodock-linux-gcc" \
  --out build/maze-riscv
```

Its [release guide](../releases/luma3d-maze-20261103/README.md) gives the exact
executable and host-side build options. A rebuilt current SD package is a new
package, distinct from the downloadable SD boot reference.

## Build current FPGA development sources

After bootstrap and the current regression:

```sh
python3 tools/build_gpu_geometry.py --name prodock_my_build --candidate
python3 tools/build_console_neo.py --name neo_my_build --stage all
```

These create isolated snapshots under `tang/impl/`. `--candidate` records a
changed Pro Dock build; source-integrity checks remain enabled. The Neo default
uses the DDR3 5.9 / 300 MHz profile with its explicit FIFO adaptation.

Inspect Gowin's synthesis, routing and timing reports before programming a new
result. For selected known images, use [the release programming commands](RELEASES.md).

## Optional historical vendor comparisons

Some standalone diagnostic scripts compare against the original Sipeed example
models. They are separate from the supplied full regression inputs:

```sh
git clone https://github.com/sipeed/TangMega-138KPro-example.git external/TangMega-138KPro-example
export SIPEED_REFERENCE="$PWD/external/TangMega-138KPro-example"
```

The relevant scripts accept a model path or use this checkout. Their model/hash
checks still apply; a different upstream IP revision is not an equivalent model.
