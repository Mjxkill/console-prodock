# License scope — original project development

The [Electrosens R&D Personal Non-Commercial License 1.0](LICENSE) applies to
original project-owned development that is not already governed by another
license. It permits personal experimentation, learning and hobby use, including
private modifications and FPGA synthesis. Commercial/professional use and
exploitation for profit require prior written permission. Free sharing for
personal non-commercial use is permitted with the license and notices intact.

This is **source-available**, not an unrestricted open-source license.

## How to determine the applicable terms

1. Check the file's license notice/SPDX identifier and the component's LICENSE
   and provenance documents. Those terms take precedence for that material.
2. Third-party code, vendor IP, fonts and third-party assets retain their own
   terms. This document neither changes nor interprets those terms.
3. Otherwise, original material owned by the project and released with the root
   license uses the personal non-commercial license. This includes eligible
   project RTL, firmware, game code, tools, tests and documentation.
4. A modified file does not become wholly project-owned merely because the
   project changed it. Separate licensing obligations remain applicable.
5. Earlier grants remain earlier grants. Adding a root license does not remove
   commercial rights already granted by an applicable MIT, GPL or other license.

The root license covers only rights the project actually owns or is authorized
to license. No rights are asserted over an asset solely because it was generated
by a tool or stored in this repository.

## Existing project files with separate terms

Examples confirmed in the repository; this is not an exhaustive replacement
for per-file notices:

| Component / examples | Existing terms retained |
|---|---|
| `linux/drivers/prodock-spi-pio.c`, Linux drivers | GPL-2.0-or-later and the corresponding per-file notices |
| `linux/drivers/prodock-uapi.h` | GPL-2.0 WITH Linux-syscall-note |
| `linux/drivers/prodock-validate.h` | GPL-2.0-or-later; no syscall exception in that header |
| `linux/userspace/nebula.c`, `prodock-game.c`, `prodock-terminal.c` | GPL-2.0-or-later |
| `linux/userspace/prodockctl.c`, `prodock-runtime.c` | MIT |
| Other explicitly licensed project or dependency files | Their existing applicable license |

In particular, `games/luma3d/src/render.c` and the published MAZE snapshot use
inline code from `prodock-validate.h`; Luma Adventure's renderer also includes
that header. **Do not describe these combined executables as newly or exclusively
non-commercial merely because a root LICENSE has been added.** Their dependency
and distribution obligations require separate treatment. This update does not
relicense their GPL dependencies or change the frozen executable/source archives.

The policy for eligible original development is personal non-commercial use.
It is not a claim that every existing file or complete system image can now be
restricted that way. No new blanket rights are granted for Linux, U-Boot, their
derivatives or components already distributed under other licenses.

## Releases, archives and contributions

Keep a copy of the applicable license and this scope notice with redistributions
of covered material. Preserve the original notices of separately licensed
components. Historical snapshots and binary hashes are not rewritten by this
licensing update; consult their source notices and provenance as well.

For a new contribution, the contributor must have authority to license it and
identify any third-party or separately licensed material. A contribution to a
separately licensed component must respect that component's terms. Submission
alone is not a transfer of copyright ownership.

Requests for commercial or other non-personal permissions should go to the
repository owner/Electrosens R&D maintainer through the project's existing
contact channels. This license does not invent an email address, entity
registration, governing jurisdiction or permission from another copyright holder.
