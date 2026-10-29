# Complete the offline audit; do not preserve accidental tautologies
Attempt1 exhausted24steps after writing audit.py, before syntax/test/report. Its immutable proof remains FAILED. This attempt has32steps and900seconds; work efficiently from supplied draft. Run tests first; then rewrite clear functions, no repeated giant file reads. REPORT must be written before final run_tests. No images, no hardware.

Concrete faults in draft requiring correction, not a happy-path patch:
- Invalid walrus assignments inside boolean expressions in aut_ok/game_ok/mount check stop compilation. Remove pointless aut_ok/mount_ev and ternaries. Remove ALL `or True`, dead `if False`, `x != x`, fake always-pass guards. A failed actual condition must produce failed check.
- pd_header overwrites observed entry with expected then tests entry!=entry. Require observed entry exact expected (load base differs from entry for LUMA/ORBITAL). whole[name] currently `reason != accept OR ...` accepts invalid headers; invert correctly. No unchecked 'okh'.
- Negative tests le(h0[36]) pass int instead of4byte slice, write4bytes atoffset39 outofbounds, variant recomputes CRC when intending badCRC. Use simple bytearray/header helpers with precise independent expectations.
- Actual ROM audit symbols: _start0x8000000c, stack0xa0207ff0. Do not claim _start0x8000012c or stack0xa028fff0. Derive formatted addresses/lengths from input fields.
- gpu_memory manifest is [start,size], not [start,end]: 0x00800000 +0x05800000=0x06000000. Compute range accurately; loader>range.
- rootfs hashes accessible entries[bin/prodock-autostart], entries[init], entries[etc/console-autostart]. All claims must match source lines, avoid arbitrary booleans/json casts.
- Defaults/fat/menu path checks must really check source: remove trailing orTrue in path_ok. Do not claim gcc unavailable unless actually observed (no recompilation needed for audit).
- Evidence must derive values rather than hardcoded math: e.g. scratchend=base+size and postroute mismatchfields exact. No prose drafting artifacts 'wait,...'.
- Findings: R3 known mismatch is blocked; R4 postroute remains pending as captured. Report source checks separately from these unresolved qualification checks. Original input_manifest SHA remain unchanged.

For a protected semantic test expose validate_header(h:bytes,file_size:int,kind:int)->bool matching exact image.c header contract. It must returnFalse for malformed or truncated header, wrongfixedentry/load/ABI/kind, inconsistent length, zero/overflow capacity. No payload validation in this function. Put audit execution in main/if__name__ so importing validator doesn't produce output or run audit. Use readable functions/comments; <=1000lines. New test_header.py protects this behavior with real three valid files and corrupted headers re-signedCRC.
