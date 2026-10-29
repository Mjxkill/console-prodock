# Persistent Festival — root execution only

Purpose: after the six real GPU windows succeed, leave the new game on the
LCD instead of returning immediately to GM1. This launches the already staged
`/tmp/luma3d-fm4a`, never a different ELF or a new bitstream.

Exact arguments: `--festival --festival-save /tmp/fm4live1.festival.save
--memory-save /tmp/fm4live1.memory.save`. Automatic mode is the default. Without
`--frames` the hardware loop is unbounded. `--showcase` must not be combined
with `--festival` in this executable: the CLI explicitly rejects that mixture.
The Festival tour walks in its 3D garden, enters Othello, solitaire, Chroma,
Pendu and Memory, then continues through the other garden ambience. The host
60000-frame run visited all four classic tables and Memory, verified through
the independent save codec; its throughput is not a hardware FPS measurement.

The baseline PID/starttime comes from `recovery.identity` in the exact passing
measurement result, not from historical PID3158. Before switching, the launcher
checks that process's complete argv and executable, the protected save, kernel,
tmpfs, free memory, GPU status and full-file CRCs of helper/game/fallback. It
requires only1MiB free tmpfs for small private saves/metadata, not another large
transfer reserve. Files for this persistent launch must be new.

TERM is bound to a fixed PID and starttime, rechecked in the shell immediately
before signalling. The candidate PID is published atomically. After four live
identity/GPU observations spanning at least9 seconds and a protected-save
check, success deliberately leaves Festival running. Its stdout/stderr go to
`/dev/null`: unattended performance logs cannot fill tmpfs. Only private saves,
a PID and eventual exit-code file remain. The saved campaign is not passed to
the new process.

An error or handled interruption after switching begins restores GM1 only
after the candidate's stopped/dead identity is established. An unpublished
ambiguous launch fails closed and reports manual review, rather than risking
two GPU owners. An initial failed guard never starts or stops a game. The
successful handoff is not a permanent watchdog: later faults, host SIGKILL,
kernel crashes and power loss are outside this controller's recovery scope.

Local command: `python3 -B persistent.py` validates only. Root's launch uses
`--run --expected-manifest SHA --measure-result EXACT_RESULT --review REVIEW
--out NEW_DIRECTORY`. Review expiry is30minutes. The review binds manifest,
measurement result, actual restored identity and G22r0/helper/ELF continuity,
and explicitly authorizes leaving the demo running. UART access holds the
common diagnostic lock and requires no other console owner. No transfer,
receiver, SD, JTAG, FPGA or kernel command exists in this controller.

The imported channel/transport helpers are pinned archival dependencies.
`policy.py` and `persistent.py` are the maintained implementation of this
isolated candidate. Unit fixtures, the host tour and the owned-child TERM test
are local evidence only; root performs and records all board qualification.
