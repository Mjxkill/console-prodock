# Publication audit — 3 November 2026

**Finding: the tracked tree contains 33 historical local-proxy authentication
values in OpenCode configuration files. No real external-provider credential or
private key was confirmed by this audit.** This is a scoped, heuristic result,
not a guarantee that the repository contains no secrets.

## Scope and evidence

HEAD remained `cb99ba087f192f25f13821a9364a352b081ed642` during the full scan.
The repository is not shallow. `gitleaks` and `trufflehog` were unavailable.
The local scanner checked 29,699 tracked worktree files, the current index,
18,105 reachable Git blobs and 20 commit messages from all refs. It read
3,994,592,573 bytes including duplicate worktree/history versions, in 212.19 s.
A separate path audit traversed all 20 commit trees (144,918 entries).

The archive pass read 42 current tracked tar archives, 1,853 file members and
473,371,934 decoded bytes, without extraction or following links. It found no
candidate credential and skipped no member. Duration: 21.05 s.

Reports contain paths, line numbers, types and redacted evidence only. No
credential values were printed, stored in the reports or sent to a model.
Five synthetic tests verify matching, line numbers, redaction and indirect
credential-reference handling (`SCANNER_TESTS.json`). No network authentication
or credential-validity check was attempted.

## Credential and runtime findings

| Finding | Evidence and classification |
|---|---|
| 33 current `controller/opencode.json` files | Each contains a literal 48-character `provider.task-provider.options.apiKey`; exact paths/field metadata in `RUNTIME_CONFIG_REVIEW.json`. |
| Same 33 configurations in reachable history | 66 occurrences across worktree and Git versions. Removing a current file does not remove its historic blob. |
| Local proxy token provenance | All 33 endpoints are loopback. The local runner generates `secrets.token_hex(24)` (`agent_provider.py:26`) and places `self.proxy.token` in `apiKey` (`agent_backend.py:86`). These are per-run proxy tokens, not evidence of the real Ollama cloud key being copied. |
| Historical lifecycle | Every associated run has a final gateway receipt and a terminal COMPLETED/FAILED/INCOMPLETE status. Tokens are ephemeral by design; their current validity was not tested. See `TOKEN_TRIAGE.json`. |
| Nine other matches | Synthetic test credentials in isolation/redaction fixtures, including historical duplicate blobs. Reviewed contexts are redacted in `FIXTURE_REVIEW.json`. |
| OpenCode runtime files | 67 current tracked files: 33 configs, 33 logs and one session-diff file. No tracked or historical `opencode.db`, `.env`, private-key filename or `auth.json` was found by the complete commit-tree name audit. |

The scanner reported 75 occurrences total, all classified above. No private-key
marker or supported external-provider token format matched. Known provider
formats and common quoted credential assignments were checked; arbitrary,
encoded or unusually named secrets can escape these rules.

Before publishing the current snapshot, exclude or sanitize the 33 runtime
configs. Keep the local evidence if needed. No tracked small code/document
file (<=2 MiB) referenced these exact 67 runtime paths; this does not rule out
dynamic references. The configs/logs are runtime artifacts rather than the
maintained source or test outputs needed to understand the results.

High-confidence ignore candidates, for the repository owner to apply:

```gitignore
TESTS/**/controller/opencode.json
TESTS/**/controller/data/
TESTS/**/controller/cache/
TESTS/**/controller/state/
```

Ignore rules do not untrack existing files. This audit did not remove files,
change the index, rewrite history, rotate tokens or authorize those actions.
Keep sanitized `metrics.json`, test results, source hashes and final receipts;
those are distinct from the runtime directory. No history rewrite is implied.

## Licence and provenance visibility

| Component | Visible repository evidence | Remaining publication description |
|---|---|---|
| Project as a whole | No root LICENSE/COPYING/NOTICE was tracked at audit start. | State component-specific terms; do not assign a blanket licence without the owners' decision. |
| Linux/OpenSBI/BusyBox/musl/U-Boot/toolchain | `linux/PROVENANCE.md` lists origins, versions and licence identifiers; `linux/sources.json` pins upstream archives. | Link this inventory from the English documentation; generated binaries and upstream archives remain separate. |
| Shared SPI core | `linux/drivers/prodock-spi-pio.c` has GPL-2.0-or-later SPDX and is shared by Linux, U-Boot and firmware builds. | Describe the actual shared source and its licence, not independent copies. |
| Neo USB host | Apache-2.0 text and pinned upstream provenance exist under `tang/boards/neo/usbhost/`. | Preserve notices and modification history. |
| Font | `tang/rtl/video/FONT_LICENSE.txt` contains the Terminus Font OFL notice/text. | Preserve the font-specific notice. |
| Sipeed/Gowin RTL and generated/encrypted IP | `tang/rtl/PROVENANCE.md` and `board/sipeed/PROVENANCE.md` identify origins and some modifications. | The blanket upstream-example licence statement does not document a separate redistribution grant for every generated/encrypted IP file. The audit did not establish those permissions. |

These are visibility/provenance observations, not legal conclusions.

## Coherent SPI source snapshot

`SPI_SNAPSHOT.json` lists **12 newly maintained files that were untracked at
audit start**, with SHA-256, plus 20 related tracked files. The new core,
register/FIFO models, four SPI/MMC Python tests and two MMC patches are required
by the modified build/test/inventory files. Omitting them would leave broken
references in the published snapshot. The experimental DMA provider patches,
phase-measurement kernels and J-Link candidates under TESTS remain diagnostic
artifacts; this audit does not promote them into maintained production code.

## Limits and final staging check

The worktree pass was not an atomic snapshot while documentation work continued.
Untracked/ignored files were outside that pass. Historical compressed variants,
nested archives, reflog-only/dangling objects and arbitrary encoded secrets were
not decoded or scanned. The scanner is heuristic; dedicated scanners were absent.
No hardware, SD, FPGA, SSH or production-source modification was performed.

After the final `git add`, the owner can run:

```sh
python3 -B TESTS/publication_20261103/audit/scan_staged.py
```

This scans the exact added/modified staged blobs, records the index SHA-256 and
checks index stability. Inspect its candidates before commit/push; it supplements
this history audit and does not automatically approve publication.
