# Buffered RX2 — preparation only

Root alone may run this after the current transfer has ended and the ordinary
shell is confirmed. It never stops or launches a game. New executable:
`/tmp/luma-rx2-buffer1`; new probe paths `/tmp/rx2-buffer1-*`.
Historical RX and RX2-probe3 remain untouched. Same identity/FPGA/save, host,
port and exclusive lock guards as the previously tested RX2 probe bundle.

Bootstrap uses verified BusyBox printf, od -b -v and chmod only. The whole
13,132-byte ELF is read back and SHA-verified before any execution. This is
slow but small and independent of the unknown transfer state.

After bootstrap: clean0/513/16384 bytes, a deliberate CRC NACK, STOP at512
and resume to1024. Full payload readback is checked. Transfer, sender and
reply-wait intervals are separate from this readback cost. These six probes
require only1MiB free /tmp; the32MiB reservation was for a large game stage.

Default invocation of trial.py is check-only. --run requires exact manifest,
fresh root review, ordinary-shell attestation and new output directory.
If RETURN is unknown, cleanup stays passive and no shell query is sent.
Results do not imply game/GPU validation or a measured FPS improvement.
