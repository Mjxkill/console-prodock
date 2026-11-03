# Public layout and portable build verification — 4 November 2026

## Objective and scope

Publish selected board downloads, English user instructions and relocatable
build inputs; group application sources/resources under `games/`. Remove
personal assistant instructions and obsolete generated artifacts from the
published tree while retaining local diagnostic evidence and protected sources.
No board was programmed and no FPGA synthesis/routing was run in this work.

## Changes verified

- 106 application files relocated without changing their contents; common
  ASTRILLA/WORLD3D helpers have one source location.
- Pro Dock R6 source/IP snapshot and Neo REJECT R1 mapped-netlist snapshot:
  146 input files checked; both historical bitstream hashes verified.
- The supplied bootstrap installs 268 missing build/reference inputs into an
  independent checkout. Repeating it preserves identical inputs and a changed
  destination is rejected instead of overwritten.
- Bare-metal firmware no longer needs a sibling analyser repository. SDK,
  compiler and Gowin installation are configurable. Linux downloads use a
  configurable cache.
- Personal AGENTS/CLAUDE files, 20 old standalone bitstreams, legacy P&R outputs,
  and more than 22,000 worker/campaign artifacts removed from the current Git
  tree. Local evidence and Git history remain available.

## Environment and procedure

Linux x86-64, Python 3.12, GCC, Verilator, Icarus and the installed RV32 GMD
compiler. An independent directory was populated from the proposed Git index,
then bootstrap, release preparation, firmware compilation, and public links
were checked there. It had no sibling analyser checkout or previous build tree.
External SDK/compiler paths were supplied explicitly.

## Results

| Check | Result |
|---|---|
| Pro Dock + Neo regression | 15/15 groups PASS; input hashes unchanged |
| Preparation/path/unit tests in independent checkout | 39 PASS, one optional comparison against the external historical converter skipped |
| Firmware, LUMA, ORBITAL RV32 compilation after relocation | PASS |
| Independent-checkout firmware | PASS, 11,376-byte binary matching the original output |
| NEBULA, LUMA bloom, ASTRILLA HUD, ORBITAL validator, racer/controller and scene-model checks | PASS |
| Public guide and release links checked in independent checkout | 323 checked, zero missing |
| Protected reference integrity | PASS in working tree and independent checkout |

The first full regression recorded three LeakSanitizer environment failures
under the execution sandbox (text/dashboard/NEBULA). The full suite was rerun
outside that environment with sanitizers retained and all 15 groups passed.
The original failure record is retained locally, not converted into a PASS.

## Evidence and limits

[Full regression result](../dual_board/public_cleanup_20261104_host/result.json)
records commands, all input hashes, log hashes and each test outcome. Selected
release manifests pin their archives and bitstreams. The SD package contains
the files associated with the recorded successful ROM → U-Boot → Linux → game
boot, and is separate from the later MAZE executable package.

This work verifies packaging, relocation and software/simulation behavior.
Full Gowin rebuilding, new timing sign-off and flash power-cycle trials were
not performed. Neo remains a diagnostic build, not an operational game console.
