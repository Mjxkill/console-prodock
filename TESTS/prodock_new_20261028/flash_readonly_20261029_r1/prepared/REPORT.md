# Flash read-only coordinator: implementation and actual test report

Status: implementation complete, **hardware validation pending** (no hardware was
accessed during this work). Everything below was observed in this sandbox with
fake subprocess/guard boundaries only; no result of a real `--run` against the
FTDI 0403:6010 programmer on `michael-AX15` is claimed here.

## 1. Files changed

| File | State | Lines |
|---|---|---|
| `flash_readonly.py` | rewritten coordinator (complete) | 971 |
| `test_owned.py` | new integration tests (21 cases) | 495 |
| `REPORT.md` | this report | - |

Unchanged and untouched: `CONTRACT.md`, `REPAIR.md`, `test_contract.py`,
`test_review.py`, `reference/target_guard.py`, `reference/load_fpga.py`.

## 2. SRAM interruption consequence (explicit)

Preparing a flash access erases the SRAM FPGA configuration of the GW5AST
(reference/src/gowin.cpp:1220). The **detect pass and both dump passes
interrupt the new SRAM candidate and the Linux it currently runs**; afterwards
the FPGA may reload the program already stored in flash. This coordinator never
reloads, restores or re-programs the FPGA and never retries automatically.

This consequence is printed in the `prepare` plan (`consequences`,
`sram_interrupted: true`) and is stored in every result JSON
(`sram_interrupted: true`, `flash_writes: 0`, `boot/gpu/powercycle: false`).
The `prepare` mode itself opens no resource, starts no process and creates no
file.

## 3. What the coordinator does

* One single target: FTDI `0403:6010`, serial `2025071717`, board
  `tangmega138k`, host `michael-AX15`. The old `2023112818` dock, UART7.3 and
  every J-Link are never referenced.
* Pinned identities (never inferred from the running host):
  * wrapper `1c0c245f4bcad2c537b5fbaf77d055c5eccf6b3b17835a24c79be631cd218066`
  * runtime `101c3c17456644f08217c3b11103aa78f8ab4debf4d2d133831c9c91c6d6d873`
    at `ROOT/runtime/openFPGALoader` (never `ROOT/bin/runtime/...`)
  * loader `f8387d5a0fa31ba2c832ebb5ed88e0c98594dbb75ad9df9a3321cc9574a970b4`
    at `ROOT/TESTS/prodock_new_20261028/load_fpga.py` (its `main()` is never
    called)
  * reviewed guard `47c4e095d6dab667f8c7d30ecf8c581e9f6bcdf278080242e92ba68616eaff5c`
    at `reference/target_guard.py` beside the module
* Phase `detect`: one reviewed invocation
  `--usb-serial-num 2025071717 -b tangmega138k --verbose --write-flash --detect`
  (the only `--write-flash` occurrence, the documented non-writing detect mode
  without a positional input file). The full log and a JSON with return code,
  target identity, tool/runtime SHA, observed JEDEC/model/sectors/bytes and
  `flash_writes: 0` are stored. Exit code 0 alone is never trusted: the log
  must parse.
* Phase `dump`: requires `--detection FILE --detection-sha SHA --jedec HEX
  --capacity BYTES`. The detection JSON (phase, `passed`, target, tool SHA,
  runtime SHA) and its exactly referenced log (SHA re-checked and re-parsed)
  are validated; the manual `--jedec`/`--capacity` must match the parsed
  identity and the sector-derived byte count. Both dumps then run inside **one
  single global guard lock**, as two separate invocations writing
  `backup_a.bin` and `backup_b.bin` (newly absent in the exclusive output
  directory) with `--dump-flash --file-size BYTES`, offset default 0. Each
  dump is checked for return code, log errors, physical ID, JEDEC, geometry and
  the completion tokens, plus exact regular non-symlink file length and SHA.
  After both dumps the full bytes are compared and a shared inode is refused.
  There is never an automatic retry.
* No flash write/erase/unprotect/bulk-erase command exists anywhere in the
  code; the only write flag is the non-writing detect mode.
* Timeouts: detect 120 s, each dump 900 s, `--timeout` bounded to 1..1800.
* Root cleanup of partial artifacts stays a separate root decision: nothing is
  deleted or restored by this tool.

### Pure API (used by the protected suites)

* `parse_detection(raw) -> {jedec, model, sectors, capacity}`; raises
  `FlashError` (a `ValueError`/`RuntimeError`/`OSError` subclass) for unknown,
  ambiguous or wrong devices, repeated records and error words.
* `backup_summary(path, capacity) -> {bytes, sha256}`; refuses symlinks,
  non-regular files and a wrong length.
* `compare_backups(a, b, capacity) -> {matching: true, ...}`; raises on a
  difference or on a shared inode.

## 4. Repairs of the verified defects (REPAIR.md 1-9)

1. **Runtime path** — the runtime is `ROOT/runtime/openFPGALoader`; `bin` never
   appears in its parts (checked in `PinnedIdentities.test_runtime_path_is_exact`).
2. **Guard import** — only `reference/target_guard.py` beside the module is
   accepted, its exact SHA `47c4e095...eaff5c` is verified *before* the module
   is executed, and `guard.command` / `guard.guarded_target` are reused with the
   pinned runtime and loader. There is no `sys.path` import of any guard and no
   silent fallback to a locally built command.
3. **Dump identification** — a dump log must contain exactly one
   `found 1 devices`, one `index 0:`, the physical `idcode 0x1081b`, exactly one
   JEDEC record and exactly one `Detected:` geometry record; it must match the
   detection and its completion tokens (`dump flash (May take time)`,
   `Open dump file DONE`, `Read flash ... 100.00%`) must precede the final
   `Done` line. An omitted identification is refused.
4. **`prepare(dump)`** — reads `evidence['parsed']['capacity']`
   (`test_prepare_of_the_dump_phase_after_a_fake_detect`).
5. **Result provenance** — a failing result-JSON write clears `passed` and
   records `result_write_error`; it can never report a success
   (`test_failed_result_write_may_not_report_a_success`).
6. **Preexisting output directory** — the directory is created exclusively
   (`mkdir(exist_ok=False)`) and the ownership is tracked. An existing
   directory is refused *before* anything is created, so the existing
   `detect.json`/`dump.json` stays byte-identical
   (`test_preexisting_output_directory_is_refused_without_overwriting`).
7. **No production overrides** — `--root` and `PRODOCK_ROOT` are gone; only the
   internal constructor argument `root=` remains for the fakes. Symlinked or
   `..`-containing output components are refused instead of being resolved.
8. **Partial evidence** — a timed-out or interrupted run keeps the full/partial
   log, the partial dump file and a failed JSON; the result entry names the
   attempted command even when the runner itself raised. The real runner kills
   **and reaps** the child before the exception leaves it, so the global lock
   is released only after the tool is really gone; SIGINT/SIGTERM are handled
   cooperatively so the `finally` block still writes the JSON.
9. **Log grammar** — `auto_boot_1st_fail` after `Done` is a historical
   annotation and is not an error; invented `[0] found ...` logs are not
   accepted (the physical header must be exactly `found 1 devices`).

## 5. Integration tests (`test_owned.py`)

Only two boundaries are faked: the reviewed guard context and the runner that
executes the reviewed argv. The coordinator, the log grammar, the exclusive
output directory, the file length/SHA checks, the JSON evidence and the
`finally` block stay real. No hardware, no shell, no network, standard library
only.

* `DetectPhase` (5): full evidence in the JSON; refusal of a nonzero exit, of
  a log without identification and of a log with an error word; `prepare`
  opens nothing and states the SRAM consequence.
* `DumpPhase` (11): detect then two successful dumps; one lock across both
  dumps (the lock is held on every tool invocation); two separate invocations
  with two distinct output files; a mismatching detection SHA / JEDEC / capacity
  is refused *before any command*; four dump failure variants (short file with
  exit 0, failed log, log without identification, nonzero exit); a timeout of
  the second dump keeps the first file and log and writes a failed result; an
  interruption of the second dump behaves the same; a mismatching second dump
  is refused; a preexisting output directory is refused without overwriting; a
  second run into the same directory does not overwrite; a failing result write
  may not report a success.
* `PinnedIdentities` (5): exact runtime path; the reviewed guard receives the
  pinned tool/runtime/loader paths and SHAs; the reviewed guard is the only
  imported copy; every argv stays inside the allowlist (no erase/unprotect/
  bulk/verify/program, `--write-flash` only in the non-writing detect mode);
  `prepare` of the dump phase after a fake detect.

## 6. Actual test results (observed in this sandbox)

```
$ python3 -m unittest -v test_owned
Ran 21 tests in 0.031s
OK
```

Protected acceptance suite (`taskbox_run_tests`), three suites:

| Suite | Result |
|---|---|
| `test_contract.py` (4 tests) | OK |
| `test_owned.py` (21 tests) | OK |
| `test_review.py` (3 tests) | OK |

Total: 28 tests, 0 failures, 0 errors.

`prepare` mode was also executed for real to show the CLI and the plan
(`python3 flash_readonly.py --phase detect --out
/home/michael/console-validation-20261001/TESTS/NEW`): it printed the plan with
`"will_run": false`, `"sram_interrupted": true`, `"flash_writes": 0`, the
pinned wrapper/runtime/loader SHAs and the reviewed detect argv, and it created
no file and started no process. The run was refused by the host check on this
sandbox host, as expected (the review host is `michael-AX15`).

## 7. Limitations and pending items

* **Hardware validation is pending.** No `--run` was executed against the real
  programmer; the real flash contents, the real log shape and the real timing
  are unverified. The reviewed guard has never been allowed to open the
  device here.
* The tests use a small honest geometry (4 sectors of 64 KiB, 2 Mb displayed)
  and synthetic v1.1.1-shaped logs. They prove the coordinator's decisions,
  not the tool's output on real silicon.
* The coordinator is 971 physical lines: below the hard 1000-line limit but
  above the `<450` aim of the contract. It was not minified; the length comes
  from the documented pinned identities, the explicit grammar checks and the
  refusal messages.
* Root cleanup of partial logs/dumps after a failed or interrupted run is
  intentionally left to root; this tool never deletes or restores artifacts.
* No code-quality score is claimed here: only the measured test results above.
