# Second Pro Dock game restoration — 3 November 2026

Objective: restore the demonstrated game on Pro Dock **2025071717** after the
owner's reboot, preserving the first Pro Dock **2023112818**.

This record describes a historical diagnostic JTAG restoration. The owner has
since required SD boot/SOFT-USB for normal loading and explicitly agreed J-Link
use only for diagnosis. This is not a public installation procedure.

## Inputs and procedure

Exact identities are in RESTORE_PLAN.json. The package retains the functional
`spi_clean` kernel objects, changes initramfs/link output, adds `/bin/luma3d-maze`
and disables SD autostart. The game is the existing MAZE executable, not a newly
improved version.

1. The old session did not answer shell probes; that failure remains recorded.
   No reset is presented as a fix for the SPI diagnosis.
2. After the owner's physical reboot, R6 was loaded into FPGA SRAM through
   programmer2025071717. DONE_FINAL and fresh USB enumeration were observed.
3. A known CPU parking/recovery procedure preceded the compact Linux/game JTAG
   load: 8,515,748 bytes in124.9 seconds, payload CRC correct, Linux READY.
4. Shell/context checked; SD unmounted; the ELF hash read back on the board.
5. `/bin/luma3d-maze --festival` launched and left active after four new telemetry
   windows. Host descriptors were closed.

## Observed result

PASS for this restoration/launch. Graphics ready at4.606784 seconds; FPS windows
5.55 /13.36 /32.91 /28.12 vary by scene. They are not a global average or a claim
of constant smoothness. GPU error/fault/underflow counters were zero before
launch; no end-of-run counter campaign was performed because the game remained
active. No new user visual confirmation accompanied this exact restoration.

FPGA R6 SHA-256:
`0a0ab081f12739767493bac8bac9247fe20d6a9cf83d54405f64d2a34015ed60`.
Game ELF SHA-256:
`2e552dd1cc9b73756b68040b75c4c0a8f9c62c6584dbadd4fcb38e7933c4b985`.

No flash or SD writes. This volatile load does not qualify autonomous SD boot.
The FPGA collector's overall boot result remains negative within its40-second
window although programming succeeded; the subsequent RAM boot has a separate
PASS result. Recovering a silent console by replacing software does not establish
why it was silent.

## Evidence

- `r6_reload_01/result.json`, `program.log`: FPGA load and new USB console.
- `warm_01/boot/jlink.log`, `console.log`, `result.json`: transfer, CRC, Linux.
- `game_01/elf_sha.log`, `uart_rx.bin`, `result.json`: game identity/progress.
- `shell_01`, `shell_02`: failed probes preserved locally.

Selected text evidence is published; binary captures and large build outputs
remain local. The package manifest and exact source/executable snapshot identify
the game separately from this hardware observation.
