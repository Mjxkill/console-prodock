# FPGA downloads

Use **Pro Dock R6** for the current Tang Mega Pro Dock console. The selected
image, its frozen build inputs and checksums are in the
[R6 release package](../releases/fpga/prodock_r6/README.md).

The [release guide](../docs/RELEASES.md) explains what works, which software
belongs with it, how to rebuild it, and the difference between loading SRAM
and programming flash. The [game catalogue](../docs/GAMES.md) covers LUMA,
ORBITAL, ASTRILLA, NEBULA and LUMA3D / MAZE.

| Board | Selected image | Status |
|---|---|---|
| Tang Mega Pro Dock 138K, 800×480 LCD | **R6** | Working Linux/graphics platform. SD boot through Linux and game startup has been observed; SD loading remains slow. |
| Tang Neo / Console 138K, 1280×720 HDMI | [REJECT R1 diagnostic](../releases/fpga/neo_reject_r1/README.md) | Diagnostic image with a working test-pattern path; the game/GPU port is incomplete. Not a console-game release. |

The board images are not interchangeable. The G22r0 / NEBULA R17 pair remains
a protected historical reference, with its original timing and USB limitations.
It is not a second current download recommendation.

Older names such as `console_gpu_g*`, `console_gpu_l*`, `console_gpu_v1_800`
and `usb_sipeed_*` describe development milestones or standalone USB tests.
They are not alternatives to the selected console image. Their historical
reports, checksums and source evidence remain useful for regression analysis;
the old binaries are retained locally rather than offered as a release list.

No timing qualification is implied by selecting a working image. R6 has
documented timing violations, and the Neo diagnostic is explicitly experimental.
