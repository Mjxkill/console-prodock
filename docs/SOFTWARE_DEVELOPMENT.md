# Software development

The project has three software layers: reusable command builders, platform
adapters and applications. Linux and bare-metal applications share command
formats, but differ in ownership, cache maintenance, completion and boot paths.
The [API reference](API_REFERENCE.md) describes those contracts; the
[main README](../README.md) points to installation and current board status.

## Build the demonstrated MAZE version

Use the [immutable MAZE source release](../releases/luma3d-maze-20261103/README.md)
to reconstruct the executable actually restored on 3 November. It includes
132 source/resource files, a manifest, exact original compiler arguments and
the compressed executable. No ignored candidate directory is required.

```sh
python3 releases/luma3d-maze-20261103/build.py --verify-only
python3 releases/luma3d-maze-20261103/build.py --target host --cc gcc --out /tmp/maze-host-new
/tmp/maze-host-new/luma3d-host --host --frames 12
```

For RV32, supply the absolute path of the configured Linux compiler wrapper:

```sh
python3 releases/luma3d-maze-20261103/build.py --target riscv --cc /absolute/path/to/riscv32-prodock-linux-gcc --out /tmp/maze-riscv-new
```

The publication test rebuilt both targets and reproduced their historical
hashes exactly with the existing tools. This is a measured result for that
environment, not a guarantee across compiler/libc versions. The project wrapper
uses RV32 `imfdc_zicsr_zifencei`, the `ilp32d` ABI and the prepared musl specs.
Do not substitute an arbitrary RV32 binary or toolchain ABI.

The canonical [LUMA3D Makefile](../games/luma3d/Makefile) still describes an
older, smaller application. Its `make`, `make riscv` and `make test` targets
are useful for that source tree; they do not produce the current festival/MAZE
release. The release archive is immutable evidence, not a maintained fork.

## Code map and reusable interfaces

| Layer | Sources | Responsibility |
|---|---|---|
| Command encoding | [gpu_v1.c](../fw_console/gpu_v1.c), [gpu_geometry.c](../fw_console/gpu_geometry.c) and their headers | Validate descriptors and emit eight-word commands through a callback. |
| Bare-metal transport | [gpu.c](../fw_console/gpu.c) | MMIO command submission, completion and display tables. |
| Linux ABI | [prodock-uapi.h](../linux/drivers/prodock-uapi.h), [prodock-gpu.c](../linux/drivers/prodock-gpu.c) | Exclusive owner, validated batches, mmap window, cache service, synchronous submit/present and diagnostics. |
| Application example | [LUMA3D renderer](../games/luma3d/src/render.c) | Resource upload, camera matrices, batched emission and presentation. This link is the canonical example; the release contains its exact later variant. |
| Smaller native example | [prodock-game.c](../linux/userspace/prodock-game.c) | Open the GPU/display devices, manage buffers and draw a scene. |
| Inspection tool | [prodockctl.c](../linux/userspace/prodockctl.c) | Query layout, capabilities and counters through the public interfaces. |

The CPU computes game state, physics and camera/object matrices. G3D1 transforms
mesh vertices and performs clipping/projection; GPU V1 handles pixel work.
A host command capture can validate the exact submissions and feed an independent
reference renderer. It is not proof of FPGA execution or board FPS.

## Command emission and errors

A typical application uses the existing builder functions in this order:

1. Open the GPU exclusively; inspect `PRODOCK_INFO`, dimensions and fault/error
   state. Probe `PRODOCK_GEOMETRY_INFO` before relying on G3D1.
2. Map only the allowed GPU memory window and allocate disjoint colour, depth,
   textures and mesh storage with the required alignment.
3. Bind a `gpu_v1_context` to an emitter. In Linux the emitter collects up to
   64 commands and submits them through `PRODOCK_SUBMIT`. Bare-metal uses its
   own single producer and explicit wait.
4. Set target/scissor/material/texture and camera/matrix/light state; submit
   mesh DRAWs or raster operations. Check builder return values and the
   emitter's separate error state: its callback returns `void`.
5. Publish resources and enqueue texture invalidation when their bytes change.
   Wait before CPU reuse or readback. After successful drawing, present the
   inactive colour surface and descriptor bank.

The source examples above are complete programs, unlike a short call-order
excerpt. Do not turn a failed builder, ioctl or timeout into a successful frame.
A failed geometry DRAW can have written earlier faces, so its partial output
must not be presented. The current Linux driver latches uncertain transfer
outcomes as faults; reopening the device is not an automatic fault reset.

`PRODOCK_SUBMIT` synchronises caches, waits for completion and checks errors.
The geometry commands 31–34 are accepted through that same interface when the
hardware signature is present. Linux presentation waits for the new vertical-
blank commit; some bare-metal scene helpers only request it. See the API page
before sharing a buffer across CPU, GPU and scanout.

## Linux and bare-metal builds

The [Linux Makefile](../linux/Makefile) delegates to its Python builder and
selects a board profile. A modified Pro Dock build must be explicit:

```sh
make -C linux BOARD=prodock BUILD_ARGS=--candidate all JOBS=4
```

This is a build command, not a flash or SD installation command. External
SDK/toolchain/IP dependencies and the board contract must be satisfied first.
The kernel software does not itself set the FPGA's CPU/bus/pixel clocks;
those come from the selected hardware design and boot configuration.

The [bare-metal Makefile](../fw_console/Makefile) uses `MAIN` and `EXTRA_SRCS`
to select an application, linker script and additional modules. It currently
contains machine-specific toolchain/SDK references: configure those for a new
workstation rather than assuming a fresh clone builds without prerequisites.
Include the geometry implementation explicitly when the application needs it;
a header dependency alone does not add a translation unit to the link.

Normal deployment is intended to use SD boot and SOFT-USB. J-Link is only for
explicitly agreed diagnostics. The recent RAM restoration does not qualify
complete USB installation or autonomous SD startup; follow the installation
status instead of converting a diagnostic command into a routine workflow.

## Shared SPI implementation

The native AE350 SPI adapter is `linux/drivers/prodock-spi.c`; its common engine
is `linux/drivers/prodock-spi-pio.c`, with declarations in the matching `.h`.
It is shared by Linux and the relevant bare-metal/U-Boot adapters, not a
separate maintained copy for each board.

The current Linux adapter uses synchronous **PIO**, 8-bit mode 0 and GPIO chip
selection. Its software speed ceiling is **20 MHz**; initial configuration
requests 400 kHz. These values and `actual_hz` are calculated from the declared
clock source, not independent measurements of SCK. DMA development is separate
and is not enabled by this production transfer path.

Configuration belongs to `atcspi200_init`/`atcspi200_set_speed`. Linux setup
updates the divider when needed; a normal transfer does not reconfigure it.
The adapter deliberately uses that setup speed rather than stale per-transfer
metadata from `mmc_spi`. Per-transfer clock overrides are unsupported.

`SPI_Master_send_receive` sends and receives concurrently in chunks of up to
512 bytes, preserving the caller's CS state. NULL TX sends `0xff`; NULL RX
still drains the FIFO. Exact in-place buffers are supported; other overlap is
not. A zero-byte request performs no MMIO. On failure, partial RX is invalid.
The adapter must deassert CS before `atcspi200_recover`; the common engine
never changes GPIO, never replays data and cannot convert an error to success.

Keep SD protocol, SPI configuration, byte exchange and recovery responsibilities
separate. A low throughput measurement is not by itself proof of a wrong clock,
FIFO defect or hardware erratum. Record volumes, retries, token waits, polling,
cache effects and the measurement clock before changing a driver.

## Testing and optimisation

Separate the evidence:

- Unit tests establish rules, bounds, error propagation and save-state invariants.
- Host command/pixel comparisons establish a reference result for fixed inputs.
- RV32 compilation establishes build compatibility with that toolchain.
- Synthesis/timing and each board's measurements establish different properties.

For shared project changes the required board regression command is:

```sh
python3 tools/run_board_regressions.py --out TESTS/dual_board/a-new-review-name
```

Use a new output directory and preserve failures. This command must not race
another owner of its shared cache. Candidate-specific tests are additional;
a local PASS never becomes an unperformed hardware PASS.

Optimisation starts with a reproducible baseline and a discriminating measure.
Count simulation, preparation, submission and presentation separately; record
bytes actually cleared/published, commands and completion/error counters.
For frame timing, keep measurements in memory and print after the window.
Some diagnostic modes suppress periodic telemetry, which changes their workload
and must be stated in comparisons.

The MAZE lineage already includes reduced UI clearing and publication work.
Refactoring that existing implementation is not a new speedup. Long frames
remain a separate investigation. Keep captures equivalent when claiming a
pure optimisation; label intentional visual changes and report target results
without substituting host timing for board FPS.

New code should be modular, commented and at most 1,000 physical lines per
file, with prototypes/types/constants in headers and function bodies in `.c`.
Shared code stays unique; platform differences use explicit configuration or
adapters. Historical generated resources and header debt remain inventoried
in the immutable release instead of being silently represented as compliant.
