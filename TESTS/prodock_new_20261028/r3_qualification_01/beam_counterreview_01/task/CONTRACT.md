# Independent ROM verifier counter-review

You own only owned/test_adversarial.py and owned/REPORT.md. The decoder is
read-only and may NOT be patched. Write a real unittest suite that imports
rom_check.decode/compare, exercises them, and can be rerun. No network, board,
compiler, install, or modifications outside owned paths. Use /tmp for temporary
artifacts. No code file you write may exceed 1000 physical lines.

Read the supplied official SP model and actual old R3 SP cell snapshot. That
snapshot is an archive of generated vendor cells (>1000 lines), not a new
maintained source. The actual R3 ROM contains G22 legacy data, whereas
expected.bin and the 4 itcm files are the intended new SD bootstrap. Root did
not load R3. A VO comparison is not a physical FPGA/bitstream readback.

Required behavioral tests: real old R3 rejected vs expected.bin (first byte
mismatch 41, 20556 mismatching bytes); all four lanes interleave to expected.bin;
an independently generated supported SP fixture with expected data is accepted;
bit/lane ordering at word and INIT boundaries; one-bit data mutation fails;
unknown AD/DO layouts, missing or duplicate output slices, wrong BIT_WIDTH,
unknown or duplicate INIT declarations and duplicate ports must be refused.
Exercise compare invalid lengths and distinguish payload from padding.

Actively seek a counterexample: valid syntax but unsupported mapping that the
checker accepts or wrong bytes it fails to detect. If found, preserve a minimal
reproducer and state the precise limit; do NOT loosen expected outcomes or edit
the checker to obtain green. Absence of a new counterexample is not proof of
complete correctness. The report must distinguish source-ROM proof, VO proof,
and future physical readback, and explain omitted INIT zero defaults from SP.

Run official taskbox_run_tests before editing. Implement actual assertions,
run tests, fix YOUR test defects based on observed failures. Write REPORT.md
before your last official tests call (the last mutation must be validated).
No need to spend requests artificially; finish after useful evidence exists.
