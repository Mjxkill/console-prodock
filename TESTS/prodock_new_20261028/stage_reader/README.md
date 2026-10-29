# FM4A recovery stage reader — preparation only

No hardware was accessed by this task. The current CPU/FPGA physical binding
must be established by the root coordinator before any preload or boot.
Old FM4A PID/starttick anchors are invalid after the reported J-Link incident;
this helper neither checks nor authorizes that binding.

The exact existing FM4A R4 ELF is staged as a raw LZ4 envelope, copied unchanged
from the previous verified transfer preparation. Preload `fm4a.full.lz4` at
physical address `0x04000000` before Linux boot. Its 5,805,324 bytes end at
`0x0458950c`; the read mapping is rounded to 5,808,128 bytes. The frozen G3D1
GPU ABI maps base `0x00800000` plus offset `0x03800000`, within its 0x05600000
byte region. `/dev/mem` is not used.

After the exact G3D1 Linux is running, no game owns `/dev/prodock-gpu`, and the
13,032-byte reader has been transferred and its identity checked, run:

```sh
/tmp/stage_reader /tmp/luma3d-fm4a
```

Success prints `STAGE_FM4A_OK bytes=16640496 crc=fa358bf4` and returns zero.
The output is created with mode0700 and O_EXCL/O_NOFOLLOW only after the
compressed CRC, bounded LZ4 decode, full output size and ELF CRC all pass.
It never executes the ELF. A new root decision starts the game. SHA256 of the
ELF is pinned in the local manifest; the on-board helper checks CRC32, not SHA.
CRC detects accidental corruption and is not a cryptographic authenticity proof.

The source includes the exact existing bounded raw-LZ4 decoder extracted from
`games/luma3d/tests/runtime_helper.c` by `build.py`; the original is not modified.
No independently maintained decoder fork is introduced. Both CRCs are compiled
constants, and filenames are limited to a flat `/tmp` name. Existing outputs
and symlinks are refused. Write failure removes only the freshly created file.
A failure reporting the final success line can leave a valid output; do not
blindly retry or unlink it. Inspect the exit status and output identity.

The helper opens the GPU read-only, uses PROT_READ/MAP_SHARED and issues no
ioctls or GPU commands. The historical driver's close path calls fb_restore,
which may restore the console display: read-only mapping does not remove that
existing driver side effect. This is a boot-only helper, not an operation
alongside a running game. The mapping assumes staged data remains untouched
until completion. Kernel hangs, changed physical DDR, and hardware ownership
are outside these local tests.

`host_tests.json` records ASan/UBSan, full output comparison, bad compressed CRC,
short input, nested path, existing file and symlink tests. `qemu_r1/result.json`
records execution of the exact RV32 ELF on the frozen Linux kernel, using a
sparse regular-file fixture for the GPU mmap window; it does not simulate
physical GPU DDR or prove real board operation.
