# Board releases and exact versions

There is one selected FPGA version for each board. **Pro Dock R6 is the
current working console image. Neo REJECT R1 is a diagnostic reference, not
a working game-console release.** FPGA images must match their board.

## Tang Mega Pro Dock: R6

Download the [R6 package](../releases/fpga/prodock_r6/README.md). The uncompressed
file is `console_prodock_sd_reset_20261030_r6.fs`, **41,688,837 bytes**:

```text
SHA-256 0a0ab081f12739767493bac8bac9247fe20d6a9cf83d54405f64d2a34015ed60
```

The [compressed bitstream](../releases/fpga/prodock_r6/historical.fs.gz) is
3,457,193 bytes. Its compressed SHA-256 is recorded in the
[release manifest](../releases/fpga/prodock_r6/manifest.json).

This is the full Pro Dock design, including the AE350, DDR3-backed graphics,
800×480 LCD output, SOFT-USB console and SD bootstrap. It has run the Linux console and MAZE on the Pro Dock. Selecting
R6 does not mean that its timing report is closed; retain the package's
timing report and limitations when reproducing it.

### What has actually worked

| Path | Observed result | Scope |
|---|---|---|
| R6 ROM → U-Boot on SD → Linux on SD → game | Linux console, game graphics-ready marker and game telemetry observed on 30 October | Boot is functional, but slow. The FPGA had been loaded into SRAM; this was not a flash power-cycle qualification. |
| R6 + Linux + published MAZE executable | Game started on 3 November; four telemetry windows of 5.55, 13.36, 32.91 and 28.12 FPS | These are separate windows, not an average or a guaranteed frame rate. See the [test record](../TESTS/prodock_game_restore_20261103/TEST_RECORD.md). |
| R6 SOFT-USB | Fresh 480 Mbit/s USB enumeration and console communication recorded | USB signalling speed is not the measured application-transfer throughput. |

The October SD observation belongs to its original software package. The
November MAZE test used a separate Linux RAM package. Do not combine these
records into a claim that the latest MAZE executable has already passed a
complete power-on SD installation test. The retained
[SD boot observation](../TESTS/prodock_new_20261028/sd_update_20261030_01/boot_observation.json)
records the earlier successful chain and its exact software identity.

### Matching software

Download the [SD boot package](../releases/prodock-sd/README.md) for the
verified Linux startup sequence. It includes U-Boot, Linux, LUMA, ORBITAL and
the LUMA3D executable used in that test.

The current game is published as the
[LUMA3D / MAZE source and executable package](../releases/luma3d-maze-20261103/README.md).
Its decompressed ELF SHA-256 is:

```text
2e552dd1cc9b73756b68040b75c4c0a8f9c62c6584dbadd4fcb38e7933c4b985
```

This executable needs the Linux GPU driver and G3D1 support. It is not an FPGA
configuration or a `PDCKBOOT` image. See [installation](INSTALLATION.md) for
Linux/SD packaging and [all games](GAMES.md) for the separate bare-metal demos.
The `LINUX.BIN`, `UBOOT.BIN` and game file identities must be retained together
when an SD image is assembled; replacing one component creates a new package.

## Tang Neo / Console: REJECT R1 diagnostic

The [Neo diagnostic package](../releases/fpga/neo_reject_r1/README.md) identifies
the exact image and preserved routed-design inputs. It is useful for reproducing
the HDMI test pattern and command-path investigation. Linux/game rendering is
not qualified on this image: COPY commands still expose the fault under study.
The later experiment replacing command memories with flip-flops did not finish
routing and produced **no usable bitstream**.

The selected [compressed diagnostic image](../releases/fpga/neo_reject_r1/historical.fs.gz)
is 3,466,697 bytes. Its uncompressed `console_neo.fs` is **42,303,585 bytes**,
SHA-256 `f9f379e6aea82dda358aef1f34508c246920c89c877e9a5847162e32c3919e15`.

Use the Neo package's own pins, clock constraints and DDR integration. A Pro
Dock image, or merely selecting a 720p software profile, cannot replace that
board-specific FPGA work. Rebuilding the diagnostic reproduces an experiment;
it does not resolve its known functional fault.

## Program an FPGA image

The following syntax was checked against **openFPGALoader 1.1.1**. Its board
list contains `tangmega138k` and `tangconsole`; `-m` selects volatile SRAM,
`-f` selects persistent flash, and `--verify` applies to flash writes.

Identify the intended programmer before selecting it:

```sh
openFPGALoader --scan-usb
```

Set `FPGA_SERIAL` to the programmer serial reported by the scan, then
decompress and verify the selected R6 image:

```sh
FPGA_SERIAL=YOUR_PROGRAMMER_SERIAL
gzip -dc releases/fpga/prodock_r6/historical.fs.gz > console_prodock_sd_reset_20261030_r6.fs
sha256sum console_prodock_sd_reset_20261030_r6.fs
openFPGALoader --usb-serial-num "$FPGA_SERIAL" -b tangmega138k \
  -m console_prodock_sd_reset_20261030_r6.fs
```

Compare the printed SHA-256 with the complete value above before programming.

That SRAM command has been executed successfully for R6. SRAM contents are
lost at power-off. To write persistent FPGA flash, the corresponding command is:

```sh
openFPGALoader --usb-serial-num "$FPGA_SERIAL" -b tangmega138k \
  -f --verify console_prodock_sd_reset_20261030_r6.fs
```

Use the FPGA programmer serial from the scan. Flash programming replaces the board's previous startup image.
The syntax above is checked, but a successful R6 flash write/readback followed
by a cold SD boot is a separate acceptance test; the cited SRAM test does not
claim that result. The Neo diagnostic uses board selector `tangconsole` and
its own image and programmer serial.

## Rebuild the selected version

Use the frozen inputs in the
[Pro Dock R6 package](../releases/fpga/prodock_r6/README.md) or the
[Neo REJECT R1 package](../releases/fpga/neo_reject_r1/README.md), rather than
building an arbitrary current checkout and giving it an old release name.
Their recipes explain source/tool identities and the distinction between
full synthesis and rerouting an archived mapped netlist.

Prepare and verify the frozen input packages without starting Gowin:

```sh
python3 tools/rebuild_release.py --board prodock --out /tmp/prodock-r6-prepare --prepare-only
python3 tools/rebuild_release.py --board neo --out /tmp/neo-reject-prepare --prepare-only
```

With the compatible licensed Gowin **V1.9.12.03** configured, use a different,
new output directory for an actual build:

```sh
python3 tools/rebuild_release.py --board prodock --out /tmp/prodock-r6-build --stage all
python3 tools/rebuild_release.py --board neo --out /tmp/neo-reject-build --stage all
```

Pro Dock synthesis uses the archived application sources and frozen vendor IP;
`--stage syn` stops after synthesis. Neo uses the archived mapped application
netlist and reroutes it; that is not a from-RTL Neo rebuild. No vendor IP is
regenerated by these recipes. Preparation tests verify the archive and paths,
not synthesis, timing or hardware operation.

A new synthesis or route may produce a different binary even with identical
RTL. Record its manifest, utilization and timing, and validate that result
before treating it as equivalent on hardware. The original bitstream SHA
identifies the demonstrated image; it is not inferred from the source filename.

For the exact MAZE software, the independent rebuild is available now:

```sh
python3 releases/luma3d-maze-20261103/build.py --verify-only
python3 releases/luma3d-maze-20261103/build.py --target host --cc gcc --out /tmp/maze-host-new
```

The [MAZE package guide](../releases/luma3d-maze-20261103/README.md) gives the
RV32 compiler contract and command. It publishes all 132 frozen source/resource
files used for that executable, rather than depending on a local ignored build.

## Historical references

G22r0 and NEBULA R17 remain protected regression references. G22r0's original
bitstream SHA is `fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f`.
Its recorded setup slack is −0.564 ns with nine setup violations; historical
USB character duplication is also documented. These limits were not erased
by selecting a newer application demo. The
[reference manifest](../tang/boards/prodock/reference.json) and
[NEBULA test record](../TESTS/NEBULA_20261012.md) preserve that history.

Other old `.fs` files and standalone FS/HS USB tests are development evidence,
not additional recommended console downloads. No broken Neo experiment is
offered as a working game image.
