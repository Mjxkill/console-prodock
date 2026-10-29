# RX2 same-receiver retry test, preparation only

The failed buffered probe remains immutable. This controller reuses exactly
`/tmp/luma-rx2-buffer1`, SHA c28b795a17922708a0f990eff4c0ef05dfd8aa2f7a20f036f4fbab51b67ad466.
It reads the entire 13132-byte ELF with the existing octal/SHA path before
execution. It never bootstraps, rewrites or chmods the receiver. Root alone
may execute under the existing host, port, lock, GM1 and save identity guards.

All six probes run again, with new `/tmp/rx2-buffer3-*` files: clean0/513/16384,
one intentional bad DATA CRC, STOP, resume. The injected corruption still
expects exactly one actual retransmission and one NACK. Count deviations
are recorded as link_stability_passed=false, while all six tests continue
through complete independent payload readback. The global passed flag remains
false on instability. integrity_passed covers only six completed, CRC/nonce/
offset-checked probes, exact readbacks and valid STOP/resume. A true integrity,
deadline or terminal error still stops immediately. The root may separately
authorize staging on a verified but unstable reference link; this never labels
USB stable. Full payload readback remains mandatory. A recovery does not establish why extra NACKs
were present in the earlier physical capture.

Only the host retry policy changes. It consumes already received replies
before retrying and, after the fourth transmission, reads for a valid ACK or
terminal result within the existing deadline. It never adds a fifth DATA
frame. Invalid CRC/nonce/offset, terminal replies and timeouts remain errors.
Queued X/RETURN prevents a subsequent write. There is no claim that a finite
drain proves an asynchronous receiver cannot exit immediately afterward;
frames remain inert Base64/NUL, and shell commands require fresh RETURN.

`sender_base.py` is the pinned historical dependency, not a second maintained
implementation. The candidate override is separately tested. The original
receiver ELF is unchanged; no RTL, kernel, FPGA or game changes occur here.

Run `python3 -B trial.py --prepare-only` for local validation only. Actual
execution additionally requires `--run --expected-manifest SHA --review JSON
--out NEW`. The fresh root review includes the previous hardware result SHA
and `same_receiver_since_prior_probe:true`; no agent may attest continuity on
root's behalf. Successful probes alone do not qualify the game or graphics.
