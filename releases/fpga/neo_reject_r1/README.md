# Neo REJECT R1 — diagnostic only

This is the exact mapped netlist from `console_neo_reject_20261102_r1`, device
**GW5AST-LV138PG484AC1/I0**. It is an experimental diagnostic image, **not a
working Neo game release**. COPY command rejection remains unresolved and the
original routed design has timing violations.

Uncompressed historical FS SHA-256:

```text
f9f379e6aea82dda358aef1f34508c246920c89c877e9a5847162e32c3919e15
```

[manifest.json](manifest.json) records the six exact inputs: mapped application,
CST, SDC and ROM/font data. The application netlist SHA-256 is
`76d56bd49776d12919c8051f5460bb5e7cadf73fb388ac2bd2cddea63c63b255`.
The package does not include either failed FF-memory replacement route.

```sh
python3 tools/rebuild_release.py --board neo --out /tmp/neo-reject-r1-prepare --prepare-only
```

See the [shared instructions](../README.md) for the optional netlist reroute.
This operation does not synthesize Neo RTL, reproduce the original placement,
fix the COPY rejection or qualify a new image. `--stage syn` is rejected
explicitly. The historical bitstream remains separate from any rerouted output.
