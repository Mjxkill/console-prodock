# Festival metrics R4 — six sequences, separate phase 2

Prepare-only bundle. Root alone may execute on michael-AX15, through alias ax15.
It contains no ELF transfer or receiver invocation. Phase 1 stays frozen.

Prerequisite: exact successful hardware result for phase1 plan
`d2d7bcc3d9b4bf4dccdeec20742323576ce944be0980caaaf291b98e5ddf4331`.
Runtime ELF `/tmp/luma3d-fm4a`: 16,640,496 bytes, CRC32 fa358bf4.
Expected source SHA256 is recorded in the manifest. Hardware integrity is a
complete file CRC32 plus pinned helper/delta and exact QEMU reconstruction;
this is not a claim that SHA256 was recomputed on the board.

Six windows execute only after baseline identity, save hash, GPU progression,
kernel, mounted tmpfs, helper and both ELF CRCs are checked. Four tables run four
legal actions each; Memory runs its bounded 24-action round; the garden runs
120 frames. Each window has a 180-second outer bound, exact argv in manifest,
no save path, and fresh PID/log names. Each candidate exits before the next
begins. The inherited launch state distinguishes never sent, unknown after
first byte, child PID published, and completed. Unknown PID never licenses a
second game or blind kill. The original GM1 is restored on success, failure,
or handled interruption; result remains FAIL if that cannot be confirmed.

GPU errors/underflows/faults/geometry errors must stay zero. The exact R4
metrics parser distinguishes asset/cache entry from actual action frames and
requires final stable poses and both pages. The garden statistic measures a
stationary camera/render window, not an animated game FPS. No host throughput
is reported as physical FPS. No framebuffer readback is claimed by this suite.

The stage used a large temporary-space reserve. Phase2 only needs **1 MiB**
free for its small logs; ~15 MiB after installation is sufficient. No other
file is deleted. No FPGA, kernel, SD, JTAG, receiver or save is changed.

Check locally with `python3 -B measure.py`. Execution requires `--run`, an
exact `--expected-manifest`, `--stage-result`, `--review` and a fresh `--out`.
The review schema is implemented by `review_check`: host, port, manifest and
stage-result SHA, baseline PID/starttime, FPGA/save/target SHA and root's six
explicit continuity/authorization booleans. Its timestamp expires in 30 min.
UART is opened only under the diagnostic lock, fuser and TIOCEXCL, without
changing DTR or the host termios. Recovery holds this same lock.

Local tests use a simulated /proc/command transport around the actual launch,
cleanup, PID and restore functions. They prove controller behavior under the
listed transcript cases; they do not qualify Linux, GPU timing or serial
hardware, and cannot promise cleanup after SIGKILL, a crashed host or kernel.
