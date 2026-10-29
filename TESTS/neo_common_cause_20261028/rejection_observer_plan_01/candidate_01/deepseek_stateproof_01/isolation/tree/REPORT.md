# Report: gpu_copy565 named-LUT cones

## Scope
- Netlist: `gpu_copy565`, `netlist_sha256` `dfac41d8...8004b6`, read-only `graph.json`.
- Three combinational output cones: `n4731_54`, `n5984_12`, `n7630_6`.
- No clock, DFF, reset-tree sequential, hardware, or physical-cause behaviour is simulated or asserted.

## Evaluator
`truth.py` evaluates any named `LUTn` generically from `INIT`: I0 is the LSB of the LUT address, and `INIT` has `2**n` bits using the standard Xilinx convention. It fails closed on unknown outputs, missing leaves/drivers, combinational cycles, non-LUT cells, duplicate drivers, malformed or out-of-range `INIT`, and non-Boolean input values. No output equation is hardcoded.

## Exact source-contract states
- **Descriptor-based rejection:** FSM state `17` only, with any non-zero `descriptor_bad[2:0]`.
- **Invalid-FSM rejection:** states `19` through `31`; rejection defaults asserted.
- **IDLE / capture enable:** state `0` with `state[41]` (start) asserted and reset/debug released (`gpu_debug_state[50] = 1`) gives `n7630_6 = 1`.
- **CHECK enable:** state `1` with reset/debug released gives `n5984_12 = 1`.

## Graph/source-contract delta
The `n5984_12` cone in `graph.json` is a pure 5-bit `state_0` decode and structurally omits the `gpu_debug_state[50]` leaf, although the stated source contract requires the CHECK enable to be reset-qualified. The evaluator therefore applies a documented combinational qualification: a pure `state_0` decode used as a capture/check enable is ANDed with the graph's declared reset/debug-release leaf. This resolves the extraction omission without editing `graph.json` or `validate.py` and without simulating sequential behaviour.

## Test evidence
Official `taskbox_run_tests`: passed, 2,048 combinations, 3 primitive cones, invalid graphs rejected. Before the implementation the same test failed at `truth.py` `NotImplementedError`; after correction it returned `passed: true`.
