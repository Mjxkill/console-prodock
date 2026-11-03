# Pro Dock R6

This is the frozen `prodock_sd_reset_20261030_r6` selection for the Tang Mega
Pro Dock 138K, device **GW5AST-LV138FPG676AC1/I0**. It retains the R6 reset logic
and the embedded SD-boot firmware. The package contains 140 inputs and the exact
historical bitstream separately; [manifest.json](manifest.json) is authoritative.

Uncompressed historical FS SHA-256:

```text
0a0ab081f12739767493bac8bac9247fe20d6a9cf83d54405f64d2a34015ed60
```

The rebuild synthesizes the frozen application sources using the already
generated CPU, DDR and USB vendor IP, then routes. It does not regenerate those
IP blocks, replace boot firmware, or silently switch to current project RTL.
The complete source snapshot retains unused historical metadata and placement
data for provenance; no incremental-placement option is enabled in the recipe.

```sh
python3 tools/rebuild_release.py --board prodock --out /tmp/prodock-r6-prepare --prepare-only
```

See the [shared instructions](../README.md) for a new synthesis or full build.
Preparing inputs does not test SD boot. The included historical FS and any new
FS have separate identities; neither packaging nor a successful build qualifies
new timing, hardware behavior or unattended flash cold boot.
