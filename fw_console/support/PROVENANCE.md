# Firmware build support provenance

The console owns a local copy of the small GNU build adapters previously used
from the sibling `logic_analyser_wifi` project's `ae350/` directory. No external
project checkout is needed to build this firmware now. The Gowin AE350 SDK and
GNU/xPack cross-compiler remain explicit prerequisites, not bundled code.

Imported on 4 November 2026:

| Original relative path | SHA-256 read before import | Current treatment |
|---|---|---|
| `ae350/toolchain.mk` | `5a379da3af5c994991f23d35a71043668a5f28b7c5e834e08b81f574d6cb6e5c` | Adapted locally; behaviour/configuration documented below. |
| `ae350/andes_compat.h` | `ba5e0d7b730b1649cbeb1e12ff4e8226c57857fb161923043f7eddf83fc2bae5` | Unchanged bytes and original comments retained. |
| `ae350/gnu_symbols.ld` | `de111a91953d01243428941633d040a723d5a22da9618ddbc1e2ed522934b1d1` | Unchanged bytes and original comments retained. |
| `ae350/tools/itcm_init.py` | `48ef232981c6790b44fc3692f825bfa39cc413e27b2b19777fb28e166052a8d2` | Adapted locally; behaviour/configuration documented below. |

The original small support files have no explicit licence notice beyond their
comments; this import does not invent contributor ownership or add a third-party
licence grant. Their original comments are preserved in the unchanged adapters.
The new root licence scope and any established prior rights remain applicable.
This is project build glue, not an imported SDK or an IP netlist.

`toolchain.mk` retains the original RV32 IMAFDC / ILP32D flags, BSP source set,
intentional address-zero access options, and GNU linker symbol supplement.
`andes_compat.h` supplies only the original CSR-read macro required by the BSP;
it does not introduce header function definitions or fallback SDK behaviour.
`gnu_symbols.ld` retains the original symbol policy; the application linker
script supplies `_heap_end`.

`itcm_init.py` now has an explicit CLI and callable converter. The output format
is unchanged: at most 65,536 source bytes, zero padding only to the next 32-bit
word, four little-endian byte lanes, lower-case two-digit hex and CRLF. An
oversize image is rejected before changing any lane. All four generated files
are grouped Make targets, so deleting any lane correctly regenerates the set.

Configuration (run from the repository root):

```sh
make -C fw_console AE350_SDK=/path/to/sdk/library \
  CROSS_COMPILE=/path/to/toolchain/bin/riscv-none-elf-
make -s -C fw_console CROSS_COMPILE=/path/to/toolchain/bin/riscv-none-elf- print-nm
```

`AE350_SDK` defaults to `$HOME/ae350/sdk/RiscV_AE350_SOC_V1.3/library`.
`CROSS_COMPILE` defaults to `riscv-none-elf-` on PATH. The existing `TC` variable
is retained as an override for older callers. `CC`, `OBJCOPY`, `SIZE` and `NM`
use that single prefix. `print-nm` performs no build or SDK check. `PYTHON`
defaults to `python3`. GNU Make 4.3 or later is required for grouped lane targets.
No username or sibling project path is present in the maintained recipe.

`tools/tests/test_firmware_portability.py` runs without SDK or cross-compiler.
The dated test record also contains real SDK builds and byte-for-byte comparison
against the old recipe; it is not hardware qualification.
