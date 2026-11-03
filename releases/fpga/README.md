# Frozen FPGA build selections

These packages make two **exact historical input selections** available outside
the original workstation. They do not select arbitrary files from the current
development tree and do not load hardware.

| Board | Selection | Rebuild operation | Status |
|---|---|---|---|
| Tang Mega Pro Dock 138K | [R6](prodock_r6/README.md) | Synthesize the frozen application sources with their pre-generated vendor IP, then route | Selected Pro Dock SD-boot baseline; a rebuild is a new candidate |
| Tang Neo 138K | [REJECT R1](neo_reject_r1/README.md) | Reroute the exact mapped diagnostic netlist | Experimental: COPY rejection unresolved and timing not closed |

Each directory contains a readable `manifest.json`, a deterministic
`inputs.tar.gz`, relative-path TCL recipes and a separately compressed exact
historical bitstream, `historical.fs.gz`. The manifests identify every input by
size and SHA-256. Files in these archives are immutable evidence snapshots,
including generated/encrypted vendor IP; they are not competing maintained
sources. Historical comments and unused IP-generation metadata may retain the
original machine paths. The public TCL recipes do not use those paths.

## Prepare without Gowin

Run from the repository root with Python 3.10 or newer:

```sh
python3 tools/rebuild_release.py --board prodock --out /tmp/prodock-r6-prepare --prepare-only
python3 tools/rebuild_release.py --board neo --out /tmp/neo-reject-r1-prepare --prepare-only
```

Use a **new directory** each time. Preparation verifies the archive, inventory,
each extracted file and the relative TCL input paths. It refuses replacement of
existing outputs, symlinks, traversal, unexpected files and modified recipes.
No installed Gowin, license, programmer, board or old `tang/impl` directory is
needed for this step. `PREPARATION.json` records its result; it is not a timing
or hardware qualification.

The supplied historical bitstream is separate from the rebuild output. To
inspect it, decompress it to a filename of your choice and compare its SHA-256
with the board manifest. The rebuild script never flashes or loads it.

## Synthesize or route with Gowin

Install a compatible licensed Gowin EDA distribution for the stated device.
The original tool was **V1.9.12.03**. Select the installation explicitly:

```sh
export GOWIN_IDE="$HOME/gowin/IDE"
python3 tools/rebuild_release.py --board prodock --out /tmp/prodock-r6-synthesis --stage syn
python3 tools/rebuild_release.py --board prodock --out /tmp/prodock-r6-rebuild --stage all
python3 tools/rebuild_release.py --board neo --out /tmp/neo-reject-r1-reroute --stage all
```

These are separate fresh builds; the last two commands run place-and-route.
`--stage syn` is deliberately rejected for Neo because that package is already
a mapped netlist. No vendor tool was run while validating this publication.

The shared toolchain selector keeps an existing `~/gowin/IDE` before considering
`gw_sh` on `PATH` when `GOWIN_IDE` is unset. An invalid explicit setting fails
instead of selecting another version. The original Ubuntu FreeType workaround
is retained; another host may set `GOWIN_FREETYPE` to an absolute compatible
library, or `off` to disable automatic preloading. These settings affect only
the compiler subprocess environment.

R6 runs its original synthesis recipe, then the existing project's
`resolve_constraints()` function, then its netlist routing recipe. The resolver
source is pinned in the manifest; a change requires a reviewed manifest update.
Neo preserves the application netlist and constraints exactly. Its former
N56r19 source include directory is replaced by local `rtl;.` search paths;
the mapped netlist has no source include/readmem dependencies, and its memory
INIT contents are unchanged.

The current-development builders and protected G22/R17 guards are untouched.
This separate path validates a complete frozen release package. It cannot be
used to silently promote current development changes as an old reference.

Inspect `*.log`, `*.result.json`, `RESULT.json`, the generated resource/timing
reports and the final output hash after a build. A successful tool exit or an
FS file is **not** timing closure, electrical qualification or proof that a new
bitstream behaves like the supplied historical one. A different tool version
or a new implementation run may produce different bytes and routes. Hardware
validation remains a separate operation with an identified board and image.

## Verification supplied here

```sh
python3 -m unittest discover -s tools/tests -p test_gowin_toolchain.py -v
python3 -m unittest discover -s tools/tests -p test_rebuild_release.py -v
```

The first suite has 12 selection/environment checks; the second has 12 package,
integrity, failure-reporting and adversarial extraction checks. No fake vendor
execution is represented as an actual FPGA compile. In addition,
[PREPARATION_TEST.json](PREPARATION_TEST.json) records preparing both actual
packages from an independent temporary tree: all 140 R6 inputs and six Neo
inputs were byte-identical, and both compressed historical bitstreams matched
their original hashes. This checks packaging and relocation only.
