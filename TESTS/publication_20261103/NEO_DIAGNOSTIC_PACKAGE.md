# Neo diagnostic publication subset

This subset preserves the current banked flip-flop command-storage candidate, its tests, the isolated two-memory netlist substitution recipe, and compact source evidence for the two failed full routes. It is an archive of a diagnostic experiment, not a released Neo bitstream.

The first FF route ended with PR0004 and 6,960 unrouted connections; the banked route ended with PR0004 and 4,243. Neither produced a bitstream. Banked placement used 61,717 / 69,120 CLS (89.29%). These counts do not identify the unrouted nets or prove a silicon/FIFO defect. See the published `SUPERVISOR_REVIEW.md`, `NATIVE_CHECKS.json` and original resource reports.

`banked_storage_01/banked_words32.v` is the current helper. The packed-vector `neo_command_ff128.v` beside it is a frozen predecessor used to prove the representation-only change; it is not an alternative maintained source. Snapshot RTL under the integration test is immutable R19 evidence, not the production source tree. Its existing files over 1,000 lines are explicitly inventoried in `neo_files.json`.

## Reproduction boundaries

The helper test compares against Gowin's official SDPB model. The full `gw5a/prim_sim.v` is not redistributed; its exact SHA-256 and the original tool paths are recorded in `neo_files.json` and the test scripts. Install the corresponding vendor library and Icarus toolchain separately before reproducing the archived command:

```sh
python3 TESTS/neo_fifo_ff_20261102/banked_storage_01/test_banked.py --out TESTS/neo_fifo_ff_20261102/banked_storage_01/public_replay_01 --mutants
```

The archived script requires a fresh output directory and the original tool/library locations. A different installation must explicitly adapt paths in a separate copy, preserving the original as evidence.

The real-source integration bench uses Verilator 5.020, GCC, make and a small project-authored primitive shim. Its original invocation is:

```sh
cd TESTS/neo_fifo_ff_20261103/command_path_tests_01/supervisor_replay/project
python3 owned/run.py
```

Its frozen `INPUTS.json` verifies 44 inputs. Three vendor extracts (SDPB, DFFRE and GSR) are intentionally excluded from this public subset, including two unused reference models. The build must fail with `INPUT_HASH_FAIL` until those exact reference bytes are supplied from the vendor library. Do not disable the guard or replace it silently. The package does not claim a fresh clone passes the full bench without these dependencies. Prior results remain available as historical evidence; the integration bench is source-level and does not qualify physical CDC, the complete mapped application or timing.

The frozen application assembler and route adapters are published for review, but are not a self-contained public FPGA build. They require the exact protected REJECT R1 netlist, synthesized helper, Gowin template, tool installation and historical proof closure. Large VG/VO, encrypted IP workspaces, binaries and OpenCode gateway/runtime data are excluded. The adapters deliberately keep their original fail-closed dependency hashes. The compact original `build.tcl`, CST, SDC and route logs establish what was actually attempted. Do not run their PNR entry point as an installation step.

No source, hardware, synthesis, PNR or simulation was changed or executed during this publication curation. Selection integrity, all 44 archived integration-input hashes and Python parsing were checked. No completed route, timing closure, diagnosis of the silicon, or successful Neo hardware fix is asserted.
