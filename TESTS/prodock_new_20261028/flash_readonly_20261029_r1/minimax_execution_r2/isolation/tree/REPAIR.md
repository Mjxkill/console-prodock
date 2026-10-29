# Bounded completion of MiniMax attempt1 (its immutable proof remains FAILED)
The first attempt spent24steps/442seconds, left test_owned.py and REPORT.md stubs, and stopped before integration tests. Its exact protected suite now has1failure: missing own tests. The partial code is NOT approved. Do not repeat exploratory reads of the whole reference; finish the concrete implementation and tests. The installed runner allows32steps but a900s total budget; use complete multi-function edits, then real tests, then repair observed failures. No hardware access.

Verified defects to repair, not merely discuss:
1. runtime path is ROOT/runtime/openFPGALoader, NEVER ROOT/bin/runtime/...
2. Import only reference/target_guard.py beside this module, verify exact SHA47c4e095d6dab667f8c7d30ecf8c581e9f6bcdf278080242e92ba68616eaff5c BEFORE exec. No arbitrary sys.path import or silent local command fallback. Reuse guard.command and guarded_target with pinned runtime/loader.
3. Dump log MUST contain exactly one found1/index0/idcode1081b, JEDEC record and Detected geometry; cannot omit identification. Validate it matches detection; completion comes after the read100% marker.
4. prepare(dump) wrongly reads evidence[capacity]; actual return is evidence[parsed][capacity]. Test prepare after fake detect.
5. _write_result currently swallows errors while keeping passedTrue. No result-provenance write may fail and still return success.
6. Preexisting output directory is refused WITHOUT overwriting its existing detect.json/dump.json in finally. Track directory creation ownership. A refusal before creating output must not mutate someone else's evidence.
7. Remove --root and PRODOCK_ROOT production overrides; an internal constructor root injection is okay for fakes. Refuse symlink/traversal output components rather than silently resolving them.
8. Preserve full/partial log of timed-out or interrupted second process and failed JSON; result entry should identify attempted command even if runner raises. Real subprocess must terminate/reap on signals before lock release (subprocess.run handles exceptions by killing/waiting; ensure main handlers cooperate).
9. A log can end with historical auto_boot_1st_fail after Done (protected fixture), not an error; do not accept invented '[0] found...' logs. Existing protected3 pure groups already pass. Keep<=1000lines; simplify if needed but do not minify.

Provide owned integration tests at actual runner boundary (fake only runner/guard), detect then2dumps, mismatch-before-command, both dump failure variants, second interruption, timeout, no overwrite, same lock across2invocations, runtime exact. Update REPORT before final run_tests; report hardware pending and SRAM interruption. Do not fabricate hardware validation or code-quality score.
