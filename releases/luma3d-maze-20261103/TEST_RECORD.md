# Source-release verification — 3 November 2026

Purpose: publish the exact MAZE software and a reproducible build without
modifying canonical source, FPGA, Linux driver or either board.

## Inputs

The archive contains exactly the 132 regular files named in MANIFEST.json,
50,470,081 uncompressed bytes. Every hash matches the original candidate
manifest. No links, binaries outside that source list or build directories
were added. A scan for private-key/API-key assignment markers found no match;
this is a bounded hygiene check, not a general security audit.

The separately supplied executable gzip decompresses to the original RV32
ELF SHA `2e552dd1cc9b73756b68040b75c4c0a8f9c62c6584dbadd4fcb38e7933c4b985`.
No board-transfer package or privileged loader is included.

## Executed checks

| Check | Observed result |
|---|---|
| `build.py --verify-only` | PASS: all 132 paths, sizes and hashes. |
| Host rebuild with existing GCC | PASS, byte-identical historical ELF: `0e0611475fbd0f172cc2ef76ec1bf52cb87ea9e897d1bf4920b88768256917c4`. |
| RV32 rebuild with prepared musl wrapper | PASS, byte-identical historical ELF: `2e552dd1cc9b73756b68040b75c4c0a8f9c62c6584dbadd4fcb38e7933c4b985`. |
| Host `--host --frames 12` | PASS, 800×480 output profile / 400×240 internal render. |
| Host `--host --720p --frames 12` | PASS, 1280×720 output profile / 640×360 internal render. |
| Nine synthetic archive cases | Nominal accepted; missing, extra, duplicate, symlink, traversal, wrong size/content/archive hash refused. |
| Six documented Linux UAPI structure sizes | Verified by native C static assertions. |

Local logs and test scripts are retained under
`TESTS/publication_20261103/game_docs/` (local evidence, not all files are
published). Build logs retain the exact compiler command; no new common
regression campaign is claimed by this package test.

## Limits

This is software packaging and reconstruction. Host smoke checks do not
validate pixels, FPGA timing, Neo hardware or board FPS. The recorded
[Pro Dock restoration](../../TESTS/prodock_game_restore_20261103/TEST_RECORD.md)
is separate hardware evidence. Different compilers or libc versions may produce
different binaries and require their own validation. Generated-resource and
historical header debt is retained explicitly in the immutable archive.
