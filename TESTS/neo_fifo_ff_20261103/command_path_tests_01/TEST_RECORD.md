# Command path + banked FF memory observers — 2026-11-03

The independent replay passed eight invocations. This is a real R19 `gpu_accel`
source pipeline, driven through AHB, with the two qualified banked FF helpers
observing the actual storage pins. It is not the substituted placed netlist.

The stress run queued TARGET + SCISSOR + 40 COPY16×2 commands: 336 accepted
words, 42 completions/captures, 80 reads and 80 writes. Input occupancy reached
128; both FIFO-full signals were observed. Every stored/read word was compared
in both helper observers. Added supervisor assertions measured `lost=0/0`,
`bad=0`, `rejected=0`, exact `done=42`, and both queues drained.

The 11 AHB full-stall samples belong only to the initial DDR-held window, not
the total run. FULL551 and command-full2232 count sampled cycles, not transitions.
Three clock ratios and the reserved w7=1 rejection pass. Two packet mutations
are caught; rerunning one in stress mode catches it before saturation. No
pressure-specific corrupt-master mutation was qualified. Forty identical COPY
packets cannot discriminate a whole-packet reorder among identical commands.

Replay:

```
python3 -B TESTS/neo_fifo_ff_20261103/command_path_tests_01/supervisor_replay/project/owned/run.py
```

This regenerates a temporary native build and RESULT.json. Preserve the current
DELIVERY if rerunning: any resulting file changes invalidate its hash receipt.
Verilator5.020, GCC, no Gowin/STA/SDF/hardware. The functional DFFRE shim excludes
runtime GSR and physical CDC/metastability; actual helper SDPB equivalence is a
separate pre-existing qualification.

`FINAL_REVIEW.json` is the authoritative supervisor scope, evidence and caveats;
`DELIVERY.json` pins it and the independent replay. Raw OpenCode attempts remain
under run_01..run_07, including failures and truncations. R5=81/100 and R7=85/100
are supervisor judgments accepted after test/scope edits, not model self-scores.
Local metrics evaluation identifiers are1 and2. Global import is pending root's
registry synchronization; no new model remains active and no r8 was started.
