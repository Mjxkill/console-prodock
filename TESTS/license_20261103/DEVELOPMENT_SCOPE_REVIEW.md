# Existing development licence boundaries — 3 November 2026

Read-only local audit for the owner preparing a new personal/non-commercial
licence. No file relicensed, no contributor ownership inferred, no external
model, no web request. Vendor investigation was stopped on the user's request;
this report concerns existing project notices and build dependencies only.

**The new root licence must not overwrite existing per-file grants.** Preserve
those notices and explicitly exclude their covered versions/content. Previously
distributed MIT/GPL permissions must not be described as retroactively withdrawn.
This is an inventory of actual notices and dependencies, not a title/ownership
verification or a final determination of a combined binary's licence.

## Concrete exclusions and scope conflicts

| Actual path/evidence | Existing declaration / consequence for the scope document |
|---|---|
| `linux/drivers/prodock-uapi.h:1` | `GPL-2.0 WITH Linux-syscall-note`. Preserve this exact exception; it is distinct from implementation headers. Normal UAPI use is not evidence that an application itself is GPL. |
| `linux/drivers/prodock-validate.h:1,6-115` | `GPL-2.0-or-later`, **without** syscall exception; contains executable inline validation functions. |
| `games/luma3d/src/render.c:4,38` | Includes that implementation header and calls `prodock_command`; it is not merely an ioctl declaration dependency. |
| `games/luma_adventure/src/video.c:1,5,23,232` | File is MIT, but includes the same GPL implementation header and calls `prodock_command` / `prodock_scene_valid_for`. Do not describe the resulting combined executable as solely covered by a restrictive root licence. |
| `games/luma3d/candidates/maze_publish_20261102_r1/build_01/source/games/luma3d/src/render.c:16` | The latest built candidate also includes the GPL validator. This is not limited to an obsolete canonical build. Its archived `submit_diag.c:1` says `SPDX-License-Identifier: custom`, an ambiguous label rather than a defined licence text. Preserve archive identity; do not silently replace its notice. |
| `linux/userspace/nebula.c:1`, `prodock-game.c:1`, `prodock-terminal.c:1`, `prodock-text-test.c:1`, `prodock-dashboard.h:1`, `neo-gamepad-input.h:1` | Explicit `GPL-2.0-or-later`; these are locally developed userspace programs/helpers and still must be excluded from a blanket non-commercial grant. |
| `linux/drivers/prodock-{gpu,spi,spi-pio}.c`, `prodock-spi-pio.h`, `prodock-{cache,text,text-model,validate}.h`, `prodock-kunit.c` | Explicit GPL-2.0-or-later. `neo-gamepads.c` is GPL-2.0-only. Preserve file-specific identifiers. |
| `fw_console/Makefile:9-11` | Firmware using `sd_ae350.c` links the same GPL SPI core. A blanket licence for all firmware binaries would ignore this actual dependency. No conclusion about third-party SDK compatibility was established here. |
| `games/luma_adventure/{src,include,audio}` and selected tests/tools | Many files explicitly MIT; exact inventory in `EXISTING_NOTICES.json`. Preserve prior grants even though they are project-developed files. |
| `linux/boot/*` marked MIT; `linux/userspace/{prodock-runtime,prodockctl}.c:1` | Existing MIT grants. |
| `linux/{prodock,neo}-linux.dts:1`, `linux/uboot/overlay/arch/riscv/dts/prodock-console.dts:1` | `GPL-2.0-or-later OR MIT`; preserve the licence choice. |
| `linux/overlay/opensbi/platform/generic/prodock.c:1` | BSD-2-Clause project adaptation, not subject to a blanket replacement. |
| `linux/uboot/overlay/{board/prodock/console,drivers/spi,include/configs}` files with SPDX | GPL-2.0-or-later declarations. |
| `linux/tests/spi_register_model.{c,h}`, `linux/tests/spi_uboot_model.c:1` | GPL-2.0-or-later tests/models also require a scope exception. |

`linux/PROVENANCE.md:16` broadly labels user programs and boot diagnostics MIT.
That sentence is less precise than the actual GPL notices above. Preserve the
per-file notices as controlling evidence and clarify that the summary does not
relicense the GPL userspace programs.

## Safe wording boundary for the owner

Limit the new licence to original project material for which the owner can grant
rights and which is not already covered by another explicit licence or inherited
content. List excluded component families and state that per-file notices,
provenance and historical grants remain applicable. Do not claim that all source,
all games or all generated binaries are personal/non-commercial-only. Separate
source-file permissions from redistribution of an executable combining differently
licensed implementation code. No ownership or licensing decision has been made
for missing/ambiguous notices by this audit.

## Verification and limits

Deterministic `git ls-files` + local notice search found 200 notice occurrences
in 191 tracked files (large build snapshots and TESTS archives excluded from this
initial inventory); targeted source/build reads verified the dependencies above.
The latest MAZE archive was read separately only to confirm the validator use.
No code compilation or functional test was needed or run. The audit does not
establish an exhaustive dependency/licence closure for every binary or asset.
