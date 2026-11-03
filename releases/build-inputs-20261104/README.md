# Build and regression inputs

From the repository root, run:

```sh
python3 tools/bootstrap_build.py
```

This installs the immutable source snapshots and USB simulation export needed
by the full-system builders and regression suite. Everything is included in
`build-inputs.tar.gz`; no sibling project or personal filesystem path is needed.
The installer verifies the archive and every selected file with SHA-256,
preserves existing identical files, and refuses to overwrite different files.

Contents:

- The protected Pro Dock reference archives and their required extracted inputs.
- The C37 source baseline and C28 build recipe used by the geometry builder.
- The official HS USB controller simulation export used by the USB regression.

These are frozen build inputs, not independently maintained copies of the live
sources. Original hashes, component notices and archived evidence are preserved.
Historical metadata may record the original workstation; the build recipe is
relocated by the builder. Gowin itself and the AE350 SDK are installed separately
as described in [the installation guide](../../docs/INSTALLATION.md).

For the two selected board images and their exact reconstruction commands, use
[the release guide](../../docs/RELEASES.md). This archive does not select or
program a board and does not replace a working installation.
