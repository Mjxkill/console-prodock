# Racer

Road-racing game embedded in the bare-metal GPU diagnostic. No separate main program or graphics package is required.

## Files

- [`src/racer_scene.h`](src/racer_scene.h): application source.

## Build or preview

Run from the repository root after configuring the toolchain described in
[installation](../../docs/INSTALLATION.md):

```sh
python3 tools/render_racer.py --output /tmp/racer.png
```

The repository-level tools keep their existing command names; they now read
the sources and assets here. Shared GPU APIs, Linux drivers and AE350 support
remain in `fw_console/` and `linux/`. No hardware is accessed by the build commands.

## Provenance and limits

The 4 November layout change moves the existing code and data; it does not
alter gameplay or qualify a new FPGA image. Historical manifests may name the
former `fw_console/`, `assets/` or `linux/userspace/` locations. They describe
the original build and are not rewritten to imply a new validation. A new build
writes a new manifest using the relocated paths. Existing header-function and
generated-resource size debt remains; this move does not claim to refactor it.

See the [game catalogue](../../docs/GAMES.md) for rendering features and measured
test scope, and [board releases](../../docs/RELEASES.md) for supported images.
