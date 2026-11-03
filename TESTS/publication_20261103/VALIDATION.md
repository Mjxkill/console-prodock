# Publication validation — 3 November 2026

Objective: publish the maintained source checkpoint, a comprehensive English
manual and the exact demonstrated MAZE software, with honest board/transport
status. This operation does not qualify a new FPGA image or change repository
visibility. No board was programmed during documentation/publication work.

## Changes included

- README and thirteen English guides: architecture, APIs, development, games,
  installation, Linux console, SOFT-USB, SPI, status, Neo, optimization, tests and
  repository/provenance.
- The shared SPI PIO core, platform adapters and matching tests/patches already
  developed in the working tree. Linux/U-Boot/firmware share one implementation.
- Existing raster command-builder extraction into a C source and its build
  references; the current small raster RTL changes remain candidate inputs.
- Existing full-screen dashboard suppression and read-only HTTP dashboard.
- Existing PLL generator metadata synchronization; no new physical clock result
  is inferred from those files.
- Frozen MAZE source and executable archive, with an independent rebuild recipe.
- Compact regression and board-restoration evidence, plus the publication audit.
- Explicit operating rule: normal SD/USB loading; J-Link only agreed diagnosis.

This is a current development checkpoint, not a declaration that every included
source change has been synthesized, timing-closed and tested on both boards.

## Verification performed

| Check | Observed result | Limit |
|---|---|---|
| Two-board common-source regression | 15 groups PASS, hashes unchanged | Local tests, hardware_validation=false |
| Dashboard Python tests | 53 PASS | Local service behavior, no board access |
| Dashboard JavaScript syntax | PASS | Not a new browser visual campaign |
| Canonical LUMA3D `make test` | PASS, gameplay plus reference-render output | Older canonical game, not MAZE hardware FPS |
| Raster cube silhouette test, affine | 512 phases PASS;22,905,121 interior pixels | Host reference/command test |
| Raster cube silhouette test, perspective | Same coverage PASS | Host reference/command test |
| MAZE source archive verification | 132 file hashes PASS | Frozen release inputs |
| MAZE host and RV32 rebuilds | Exact original ELF hashes reproduced | Existing compiler/libc environment |
| MAZE host profiles | 12-frame800/720 smoke tests PASS | Not pixel or Neo hardware qualification |
| Archive validation | Nine cases; invalid archives rejected | Bounded adversarial suite |
| UAPI structure sizes | Six assertions PASS | Header ABI sizes, not all driver behavior |
| English manual/release links | 123 relative links included in the Git index across17 documents | External URLs not crawled |
| Source/document whitespace | PASS with CRLF recognized | Raw logs and patch-context whitespace preserved |
| Release credential scan | 132 source members plus ELF; zero heuristic findings | Not a guarantee or licensing clearance |

The initial staged scan checked151 added/modified blobs and found zero candidate
credentials with a stable index. A final staged scan is run after curation;
its local result records the exact index identity. The full baseline/history
scan is separately described in `audit/PUBLICATION_AUDIT.md`.

## Publication cleanup

The67 explicitly inventoried historical OpenCode runtime files were removed
from the current Git index, **not deleted locally**. They include33 configurations
with per-run loopback proxy tokens. Their historical blobs remain; no Git history
was rewritten. No real upstream provider credential or private key was confirmed
by the bounded audit. Runtime ignore rules prevent re-adding those directories.

Source notices and vendor provenance remain component-specific. No blanket
license or third-party redistribution permission was invented. This publication
does not change the GitHub repository's visibility or contact Gowin/Sipeed.

## Evidence boundaries

Full vendor tool workspaces, temporary model runtimes and most simulator outputs
remain local. Selected text reports retain exact measurements; logs are not
whitespace-normalized because their hashes are evidence. Diagnostic loaders in
historical records are not the recommended public loading procedure.

The latest game-restoration record proves execution of an identified ELF on
R6 after a volatile diagnostic load; it does not prove autonomous SD boot or
complete SOFT-USB deployment. Those missing steps remain visible in the manual.
