# ANALYSIS — bounded MD12 completion-field correction (review round, software only)

Scope note: this is a parser/test correction task per REVIEW_FINDINGS.md. The FPGA
diagnosis was NOT redone, no hardware/board access happened, and no fix is claimed
for the board failure. All evidence below is from bounded software execution over
the exact protected bytes.

## 1. What the fixed official run showed BEFORE any edit (tool: taskbox_run_tests, run 1)

Actual result: 38 tests, 9 failures, task FAIL. The protected baseline passed first
("FULL_CHAIN_COMPILE_PASS BASELINE_PASS"; binary sha256 aa2a1a06…; 8 interpreter
model cases, instructions 288–950, all classifications as expected).

The 9 failures, verbatim evidence:

* 7 failures in protected `test_md12_expected.ExactMD12Contract.
  test_all_reserved_extent_lastword_mutations`, one per contract subtest:
  `(index=24, value=0)`, `(index=24, value=2)`, `(index=25, value=0)`,
  `(index=25, value=301990016)` [= 0x12000080], `(index=26, value=1)`,
  `(index=27, value=1)`, `(index=31, value=1)` — each
  `AssertionError: True is not false`. Owned candidate `microdma_decode_v2.py`
  still had no checks for words 24/25/26/27/31, so mutated completion claims were
  promoted to passed=True. (`test_actual_healthy_completion` was already ok.)
* 2 failures in `adversarial.ProductionDefectReproduction`
  (`test_md12_completed_claim_with_conflicting_words_must_not_pass`,
  `test_md12_single_bit_reserved_fault_silent`) — the intentionally red
  reproductions of the confirmed original-decoder laxity, e.g.:
  "True is not false : PRODUCTION DEFECT in microdma_r1/decode_journal.py:
  reserved26 bit flip (word[26] planted to 0x1) silently promoted to passed=True;
  issues=[]".
* The remaining 29 adversarial reader/log/journal/provenance tests: all ok.

## 2. Rejected inference (mine) vs the reviewer's correction

* My earlier defect fixture assumed `command_words_remaining` (word 24) would be 0
  once all 8 command stores returned ("all command words consumed") and demanded
  the decoder refuse `word24!=0`. That inference is WRONG and was rejected.
  microdma.S stores this field immediately BEFORE each command word and never
  clears it afterwards, so the final journaled value is 1 even after all 8 stores
  return. The healthy completed fixture must carry word24=1. The payload was not
  edited to match the mistaken test.
* Hardware corroboration read directly from the protected artifacts (read-only
  unpack of run02/journal.bin and run03/journal.bin, sha256 17f453c3… each):
  both real journals carry `words[24:32] = [1, 0x1200007c, 0, 0, 32, 32, 0, 0]`
  — i.e. command_words_remaining=1, last_ddr_address=0x1200007c, reserved26=0,
  reserved27=0, seed/target compared words=32, clear_compared_words=0 (the clear
  compare never ran) and reserved31=0, on the failed phase8/result-5 CLEAR runs.
  The value 1 is therefore what this payload actually journals, completed or not.

## 3. Files changed (owned files only; nothing protected touched)

* `microdma_decode_v2.py` (owned candidate; 87 lines): adds exactly the
  reviewer-confirmed bounded checks, leaving every other check/issue label/returned
  key identical to the original ABI:
  - words 26/27/31 must be zero in any well-formed journal →
    `reserved_words_nonzero`;
  - on a completed phase10/result1 claim, word 24 must be exactly 1 →
    `command_words_remaining_not_one`, and word 25 exactly 0x1200007c →
    `last_ddr_address_wrong_extent`. The gate follows the reviewer's stated scope
    ("on completed phase10/result1"), so genuine partial journals gain no invented
    issues — verified on the real artifacts (their format words already match, and
    they stay FAIL for their genuine reasons).
* `adversarial.py` (owned; 619 lines):
  - completion fixture corrected: word24 0→1 (word25 pinned to 0x1200007c), with
    the rejected inference documented in the docstrings;
  - the old `ProductionDefectReproduction` replaced by `CandidateHardenedDecoder`
    (healthy claim accepted; every contract mutation and single-bit reserved
    corruption refused with the right issue label; real run02/run03 remain FAIL
    under the candidate with no added issues) and `OriginalDecoderLaxityObservation`
    (the protected original keeps accepting every corrupted claim — preserved as an
    EXPECTED observation, plus an original-vs-candidate divergence test), so the
    defect is reproduced and documented, not hidden, while the suite can pass with
    the candidate in place;
  - the other 29 reader/log classes (guard refusals, completed-journal mutations,
    hang/trap, real journals, footprint/provenance) are byte-for-byte unchanged.

## 4. Evidence after the edits (exploration runs via exec, before the final fixed run)

* `python3 -B -m unittest test_md12_expected -v` → "Ran 2 tests … OK" (healthy
  completion passes; all 7 contract mutation subtests reject).
* `python3 -B -m unittest adversarial` → "Ran 41 tests … OK", no skips.
* Line budgets: adversarial.py 619, microdma_decode_v2.py 87 (<1000 each).
* Protected inputs re-hashed unchanged: run02/run03 journal.bin 17f453c3…,
  microdma_r1/decode_journal.py 98e54a8f…, readback.bin aa2a1a06….

Final verification is the fixed `taskbox_run_tests` executed after this report was
written; no file is written afterwards.

## 5. Findings vs limitations

* Confirmed (software-level): the protected `microdma_r1/decode_journal.py`
  accepts a phase10/result1 completion claim corrupted in any of words 24/25/26/27/31;
  observation preserved in `OriginalDecoderLaxityObservation`. The bounded fix
  exists only in the owned candidate; the original stays as-is (read-only), so any
  deployment should adopt the v2 decoder for MD12 completion verdicts.
* run02/run03 remain genuinely incomplete CLEAR runs (phase8/result-5,
  clear_compared_words=0, all-zero clear image never measured); the journal-format
  laxity did NOT cause the board failure, consistent with the reviewer's note; the
  new readback256B code/binary is unaffected.
* Not modeled / out of scope: physical CSR/cache/DDR/arbitration timing, GPU native
  request/acceptance behavior, any board-side phenomena. No hardware, network,
  keys or vendor builds were used.