# Repository, distribution and contribution

## Directory map

| Path | Purpose |
|---|---|
| `tang/rtl/` | Shared graphics, buses, board integration and vendor IP wrappers |
| `tang/boards/` | Board profiles, ownership inventory, Neo adaptations and protected-reference identities |
| `tang/constraints/` and board constraint paths | Pin/timing inputs selected by each builder |
| `fw_console/` | Bare-metal runtime, graphics API and demonstrations |
| `linux/` | Pinned OS build, device trees, drivers, U-Boot/OpenSBI integration, userspace |
| `games/` | Maintained game sources and development content |
| `assets/` | Prepared graphical resources and conversion inputs |
| `releases/` | Explicitly frozen reproducibility snapshots; not parallel maintained source trees |
| `tools/` | Build, diagnostics, board checks and project dashboard |
| `optimizer/` | Gowin report/placement workbench and bounded experiments |
| `TESTS/` | Tests and selected dated evidence; large local artifacts are excluded |
| `docs/` | Current English manual |
| `ARCHI/` | Detailed architecture and historical French records |
| `bitstreams/` | Release identities, retained references and selected historical binaries |

A build snapshot is immutable evidence. It is not permission to maintain a
second divergent copy of common code. The latest MAZE archive exists because
its exact demonstrated sources differ from the older canonical game; the
archive documents that distinction and supplies a reproducible baseline.

## Common versus board-specific code

Read [ownership.json](../tang/boards/ownership.json) and
[compatibility](../ARCHI/COMPATIBILITE_CARTES.md) before changing builders or RTL.
`prodock-*` filenames do not imply Pro Dock-only ownership. Several Linux
interfaces and the SPI engine are shared by both profiles.

Board-specific changes include pinout, physical output, clocks/integration,
DDR FIFO experiments and Neo host input. Experimental snapshot transformations
must remain explicit. A change to shared code invalidates prior local qualification;
a candidate flag does not substitute for running the regressions.

## Licensing and provenance

The [root license](../LICENSE) now permits personal, non-commercial use of
eligible original project development. Commercial/professional exploitation
requires prior written permission. It is a custom source-available license.

Read [the scope notice](../LICENSE_SCOPE.md): per-file/component licenses retain
precedence, previous grants are not revoked, and existing combined GPL-dependent
executables are not made exclusively non-commercial by this update. Third-party
terms remain unchanged.

| Material | Where to inspect terms/provenance |
|---|---|
| Linux/OpenSBI/BusyBox/musl/U-Boot/toolchain | [`linux/PROVENANCE.md`](../linux/PROVENANCE.md), pinned source manifest and upstream notices |
| Shared SPI implementation | SPDX `GPL-2.0-or-later` in the source files |
| Neo USB host | [`tang/boards/neo/usbhost/LICENSE`](../tang/boards/neo/usbhost/LICENSE) and its provenance |
| Hardware text font | [`FONT_LICENSE.txt`](../tang/rtl/video/FONT_LICENSE.txt) |
| Sipeed/Gowin-derived RTL and generated IP | [`tang/rtl/PROVENANCE.md`](../tang/rtl/PROVENANCE.md) and per-component sources |
| Artwork and generated assets | Asset-specific provenance and release notes; no blanket artwork grant is asserted |

Third-party material remains outside the project's personal-use license.
Preserve its existing notices. This licensing update makes no new assertion
about vendor permissions and does not change vendor files or their terms.

## Publication hygiene

The public snapshot excludes local agent runtime authentication/configuration,
OpenCode caches/databases, build objects and unrelated temporary environments.
Small sanitized metrics, tests and evidence remain useful. The audit found
historical loopback proxy tokens in already tracked runtime configurations;
those configurations are removed from the current index while preserving local
files. The historical Git blobs are not rewritten by this release. These were
per-run local proxy credentials, not confirmed upstream Ollama API keys; the
scope and limits are in the [audit](../TESTS/publication_20261103/audit/PUBLICATION_AUDIT.md).

Do not commit `controller/opencode.json`, tool caches, personal authentication
files or secrets in reports. An ignore rule does not erase a file already in
Git history. Public visibility is a separate repository-owner decision and is
not changed by this documentation update.

## Project dashboard

[`tools/project_dashboard`](../tools/project_dashboard/README.md) is a read-only
HTTP/SSE service for workstream state, functionality/tests, evidence and workers.
It refreshes from files and observed processes; it does not flash boards, run
workers, connect over SSH or certify that a previously observed board is still
running. Missing evidence becomes unknown rather than PASS.

Bind it to localhost or your own private Tailscale address. It has no independent
public authentication layer; it is not an internet-facing management service.
The lab registry includes local evidence paths that a clone will not contain.
Adapt the registry to your project rather than showing those entries as live.

## Engineering rules

- Diagnose before correcting. Show the causal mechanism and a discriminating
  test; a hypothesis alone is not a production fix.
- Keep configuration, normal work, diagnostics and recovery separate.
- Propagate errors; no silent retries, downclocking or success conversion to
  hide an unlocated problem.
- Maintain one shared implementation and explicit board profiles.
- Keep project-controlled code files at most 1,000 physical lines, modular and
  commented. Existing vendor/generated/archive exceptions and historical debt
  must be visible; minification is not compliance.
- Keep function implementations in source files; headers declare interfaces.
- Preserve protected references, source manifests, test failures and other
  sessions' work. Inventory before broad cleanup.
- Separate RTL, mapping, timing and hardware results for each board.
- Keep board-specific connectors and target settings documented in
  [Debugging connections](DEBUGGING.md).

Existing historical files may predate these conventions.
