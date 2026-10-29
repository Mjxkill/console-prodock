# Resume Festival metricsR4 stage after protected NACK failure

Offline preparation only. Root owns every device access and launch.
This bundle never stops or executes a game. Previous phase1 remains immutable.

The saved trace proves a terminal checkpoint of **904192 bytes**, seq1766,
prefix CRC32 **1e4464ac**, terminal reason2/idle and exact matching RETURN2.
This exceeds the three completed segments (786432 bytes): two later ACKs
confirmed the last fourth-segment block. See checkpoint_proof.json, linked
to original RX/TX/result and exact payload hashes. Original stage failed;
GM1 PID3158/start27508908 and protected save remained intact, GPU errors zero.

New receiver `/tmp/luma-rx2-buffer1` must first pass root's separate six-probe
hardware trial. Execution requires that actual result via --receiver-proof,
its SHA in the fresh root review, and its exact receiver manifest/ELF SHA.
The old receiver board proof is refused. The whole new receiver is read back
again before execution. Helper/source CRC checks and baseline continuity stay
unchanged. The staged target is still /tmp/luma3d-fm4a.

Only --resume is accepted, against /tmp/rx2-fm4a.delta.lz4.part. The first READY
must reread that file and report exactly904192 with source-matching prefix CRC.
A different size or content refuses before any DATA transmission; cleanup
waits the finite receiver return. Subsequent sessions must start exactly at
the previous confirmed checkpoint. At most five sessions finish the remaining
1123449 bytes. A new failure is reported to root; no unknown retry or automatic
restart. STOP/RETURN/shell confirmation remain mandatory between segments.

The original conservative space reserve (whole delta + target +8MiB before
transfer) remains; after stage, only target+8MiB before reconstruction. No
deletion or source overwrite occurs. Final payload and target CRC32 are read
in full. Exact ELF SHA is local provenance plus tested reconstruction, not a
SHA measured on hardware. Memory/ELF limits of the retained helper remain.

Run transfer_trial.py without --run to validate only. The run path also needs
--expected-plan, --review, --receiver-proof, --resume and a fresh --out.
On success, the measurement phase must be rebound to this new stage plan;
the old measure_prepared_r1 intentionally accepts only the first plan.

R3 changes only the host retry sender and its required successful six-probe manifest. The RV32 receiver and saved904192-byte checkpoint are identical. R2 remains immutable. nack_events records all observed N separately from actual retransmissions.
