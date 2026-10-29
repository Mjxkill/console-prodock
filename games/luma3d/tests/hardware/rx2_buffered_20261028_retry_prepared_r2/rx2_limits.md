# RX2 buffered input candidate

This independent candidate changes only the receiver input buffering. No old
receiver, running transfer, board process, or reference file is replaced.

A 1024-byte nonblocking read buffer and cursor replace read(1)/poll per byte.
Buffered octets after a frame delimiter remain available to the next parser
iteration. Signals are checked for each byte. Absolute idle/total deadlines
are checked before refilling and before decoding each completed frame. The
CRC, nonce, bounds, acknowledgements, writes, fdatasync, STOP/resume and fresh
shell return protocol are unchanged. A suffix already read after FIN/STOP
is discarded on exit: the protocol uses stop-and-wait; this suffix can contain
only inert Base64/NUL, not a shell command. No suffix is ever re-emitted.

The ELF remains 13,132 bytes. Thirty-two exact RV32/Linux/QEMU cases pass,
including corruption, drops, duplicate frames, truncation, lost ACK, finite
idle wait, ENOSPC rollback/resume, symlink/hardlink refusal, and blocked output.
A separate test writes DATA/duplicate DATA/DATA/FIN together and verifies
all checkpoints and final bytes. The existing 20 sender tests pass.

Executable call counting on 2048 data bytes plus FIN, at 16-byte/2ms pacing:
3046→192 read calls, 3046→192 input poll calls, 6110→407 clock_gettime calls.
These are libc function counts, not an assertion that every clock call enters
the kernel on every platform. Both variants still do four file writes and
four fdatasync calls. The counting harness is not part of the delivered ELF.

One QEMU boot comparing exact old/new ELF on 32 KiB gives about 5.28 kB/s
for both with production pacing. Without artificial sleeps: 53.3→159.6 kB/s.
These local timings do not establish a gain on the Pro Dock and do not
reproduce its observed ~500–600 B/s. The prepared board probe separately
records sender time, reply wait time and complete transfer time, excluding
payload readback, to discriminate the remaining cost.

Receiver deadlines bound userspace poll/read processing on a healthy kernel.
They cannot guarantee completion across a kernel hang or blocked regular-file
I/O. Production targets remain flat /tmp/rx2-* regular files on verified tmpfs.
The copied sender emits only Base64/NUL until an exact fresh RETURN, then
clears the harmless line and verifies the shell. No unknown-state retry is
allowed; only an explicit coherent NACK permits a bounded retransmission.
