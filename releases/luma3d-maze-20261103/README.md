# LUMA3D / MAZE — immutable software release

This directory publishes the **exact game restored on the second Pro Dock on
3 November 2026**. It contains source and an executable, not a kernel, FPGA
bitstream, proprietary IP or vendor toolchain. See the
[board test record](../../TESTS/prodock_game_restore_20261103/TEST_RECORD.md)
and [game guide](../../docs/GAMES.md).

| File | Purpose | Size |
|---|---|---:|
| `source.tar.gz` | 132 frozen source/resource files | 5,824,641 bytes |
| `luma3d-riscv.gz` | Exact static RV32 Linux executable, gzip-compressed | 5,049,075 bytes |
| `MANIFEST.json` | Every source hash, original ELF hashes, compiler arguments and line-count debt | Small JSON |
| `build.py` | Verify/extract the immutable archive and build in a new directory | Python 3 |

The source archive SHA-256 is
`5a651fdff7e81df48fcd18c3cf6e48e865d4553acd7d102c945e3f48ebeaa3bd`.
The executable gzip SHA-256 is
`a8318fb5b4e796d43267afd1efd95528ad6e82ae21cffce47f2766e842a9b5e9`.
After decompression, the executable is 16,684,812 bytes with SHA-256
`2e552dd1cc9b73756b68040b75c4c0a8f9c62c6584dbadd4fcb38e7933c4b985`.

## Verify and rebuild without a board

From the repository root:

```sh
python3 releases/luma3d-maze-20261103/build.py --verify-only
python3 releases/luma3d-maze-20261103/build.py --target host --cc gcc --out /tmp/maze-host-new
```

The output directory must not exist. The verifier rejects missing/extra archive
members, symlinks, unsafe paths, sizes and SHA mismatches. Only the original
132 files are extracted, as read-only files in the new build directory.

For RV32, supply an **absolute path** to a compatible compiler wrapper:

```sh
python3 releases/luma3d-maze-20261103/build.py --target riscv --cc /absolute/path/to/riscv32-prodock-linux-gcc --out /tmp/maze-riscv-new
```

The tested project wrapper uses `-march=rv32imfdc_zicsr_zifencei`,
`-mabi=ilp32d`, and the project's musl specs. The toolchain/libc must be prepared
separately. The build script supplies the original source list, include paths,
optimisation flags and static-link option; it does not download dependencies.
Logs and a result with the ELF hash are stored in the new directory.

Both host and RV32 builds were performed from this archive during publication.
With the existing toolchain they reproduced the historical ELF hashes exactly.
Other compiler/libc versions may change the binary: the script reports that
comparison rather than silently claiming byte-identical reproduction.

For a host smoke check, use the generated executable with `--host`; running
it without that option attempts to open the target GPU device. Host success
is not an FPGA timing or board-performance result.

## Provenance and maintenance

The archive is the `maze_publish_20261102_r1/build_01/source` snapshot. The
original build manifest SHA is recorded in MANIFEST.json. The snapshot has
17 files identical to the current maintained tree, 13 different game files
and 102 game files absent from that older tree. Shared GPU/UAPI files in the
snapshot match the maintained versions at publication.

This is a frozen release archive, **not a second maintained source tree**.
It makes the demonstrated version available without overwriting an older
canonical game or silently depending on ignored local candidate directories.
Future development belongs in reviewed source modules; a new release must have
a new identity and new tests. The old game Makefile alone does not reproduce
this release.

The snapshot retains historical generated resources and their known debt:
ten C/header resource files exceed 1,000 physical lines, as do two world JSON
resources. Their exact paths and counts are in `line_count_debt`. Historical
header function bodies also remain frozen. No line-count or modularity cleanup
is falsely claimed by compressing these files into an archive. New maintained
code must follow the project's modularity and header rules.

## Deployment scope

For installation and game commands, see [Installation](../../docs/INSTALLATION.md)
and [Games](../../docs/GAMES.md).

The recorded restoration used a diagnostic RAM boot, left the SD unmounted and
did not write flash or SD. It does not prove autonomous startup after power-off.
No loader in this directory touches hardware. The game requires the compatible
Linux GPU driver, G3D1 and correct board profile; the Neo remains a separate
qualification task.
