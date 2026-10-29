# RJC1 Decoder Adversarial Review

Scope: strict, offline decoding review of synthetic RJC1 records and transcripts.
No hardware, RTL, routing, board evidence, or timing source was used.

## Test suite

- File: `test_adversarial.py`
- Cases: 35 independently named unittest cases.
- Shared fixtures and decoder were used unchanged.

## Coverage

- Stale or unconsumed prime rejection.
- Differing bank tags, generations, status, sequences, and round payloads.
- Unexpected JSON keys, booleans used as integers, and ARM/counter wrap.
- Parent-at-freeze versus child-at-check provenance and header mismatch.
- Reset, anomaly, DQ-error, freeze-pending, engine-reset, and parent-state checks.
- Source-end overflow predicate reporting.
- Reason contradictions, including HEADER priority over target evidence.
- Coherent all-true/all-false descriptor flag acceptance.
- Predicate-versus-captured-D mismatch reported as a phenomenon, not a cause.
- All six positive fixture kinds accepted.

## Results

- Baseline before edits: 1 failing placeholder test.
- Final `taskbox_run_tests`: 35 passing, 0 failures, 0 errors.
- No protected decoder defect was found; no criterion was weakened.

## Limits

- `physical_cause_established` remains false in every result.
- `gpu_or_ddr_qualified` remains false in every result.
- `freshness_established` remains false; transcript checks only protocol coherence.
- Decoder output is register decision evidence only. Root timing and identity
  qualification are outside this tool and must be established separately.
"