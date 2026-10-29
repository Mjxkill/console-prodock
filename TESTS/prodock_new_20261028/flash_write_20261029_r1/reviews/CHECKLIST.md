# Independent review scope — pending implementation

- All input evidence is closed by actual bytes/SHA, including referenced logs and two separate reads. An attestation remains a root statement, not a hardware sensor.
- Refuse changed FS, plan, preserved tail, backup, acceptance, references and serial before program boundary.
- CLI prepare/default program never opens a device, acquires hardware lock or invokes programmer.
- Guard owns lock for program and full readback; one program invocation only. Exceptions retain evidence and never trigger a retry/restore.
- Full-capacity verification detects corruption outside both payload and rounded programmed sector.
- Failure/interruption before process ownership is covered by reused frozen process_guard; kernel-uninterruptible cleanup remains explicitly inconclusive.
- Integrity verification does not claim a successful autonomous cold boot or working GPU.
- Reference modules and archived failures stay unchanged. No board source, kernel or RTL input changes in this task.
