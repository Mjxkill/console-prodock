# Connecting to Linux and operating the console

These instructions assume a compatible FPGA and Linux package are already
running. Installing or recovering that package is a separate step described in
[installation](INSTALLATION.md) and [SOFT-USB](USB_TRANSPORT.md).

## PC connection

Use the board's **SOFT-USB** device port, not its FPGA programmer connector.
On the Linux PC:

```sh
python3 -m serial.tools.list_ports -v
ls -l /dev/serial/by-path/
lsusb -t
```

Choose the path corresponding to the intended board, then run:

```sh
python3 -m serial.tools.miniterm /dev/serial/by-path/YOUR_BOARD_PORT 115200
```

`YOUR_BOARD_PORT` is a placeholder, not a literal device. A stable physical
path is preferable when two boards advertise the same USB serial string.
The `ttyACM` number can change after FPGA loading or reconnecting.

Use **Ctrl+]** to leave miniterm. Closing the PC terminal does not by itself
stop an application running on the console. Do not open a second diagnostic
reader on the same port; two readers can consume each other's responses.

If access is denied, use your distribution's serial-device group/udev policy.
Do not grant universal write access to every USB device. The host's USB speed
should show 480M for the intended HS connection; the terminal baud setting is
not that bus speed.

There is no qualified Ethernet/Wi-Fi login service in the current console
package. SSH to `ax15` in historical reports means SSH to the **host PC**, not
to the board. It is unnecessary when the board is directly attached to your PC.

## Boot stages and prompts

| Observation | Meaning |
|---|---|
| FPGA test pattern | Display timing/scanout active; not proof Linux booted |
| `PRODOCK SD BOOT READY` | Resident SD bootstrap running |
| `PRODOCK =>` | U-Boot prompt |
| Kernel log and `PRODOCK_LINUX_READY` | Linux startup reached its userspace init path |
| `prodock#` | Project shell prompt, depending on package |
| Game graphics without a prompt | Application may own the foreground terminal |

The rootfs starts devtmpfs/proc/sysfs/tmpfs, then init. SD mounting is not
implied by `PRODOCK_LINUX_READY`; the base init message explicitly says it is
not mounted. Inspect rather than assume:

```sh
uname -a
cat /proc/cmdline
cat /proc/mounts
cat /proc/partitions
ls -l /dev/prodock* /dev/mmcblk*
```

A `can't lookup blockdev` message indicates the requested block device did not
exist at mount time. It is not evidence of a fragmented filesystem or slow
GPU. Check driver enumeration and the exact device node before retrying.

## Shared and full-screen layouts

The Pro Dock physical output is 800 × 480. In split mode the game viewport is
400 × 240 at the upper left, the terminal is upper right, and diagnostic tables
occupy the lower half. Full-screen game mode scales the game view; it does not
automatically turn a 400 × 240 render target into native 800 × 480 3D rendering.

```sh
prodockctl layout split
prodockctl layout game
prodockctl layout console
prodockctl display
```

The terminal bridge implements interactive layout switching; the explicit
commands above also avoid ambiguity when using another serial client.
Layers 12–15 and palette entries 240–255 are reserved by the Linux display
contract. Applications should not overwrite them directly.

The dashboard presents GPU/USB/SD status and counters. Full-screen game mode
suppresses periodic dashboard rendering/SD collection in the current terminal
code; a lightweight display-state check remains so it can detect a return to
split view. This is not a claim that all system activity stops during gameplay.

## Useful project commands

| Command | Purpose / caveat |
|---|---|
| `prodockctl display` | Inspect display/layout state through the display interface |
| `prodockctl geometry` | Query exposed geometry capability/status |
| `prodockctl info` | GPU information; may require the exclusive GPU lease |
| `prodockctl selftest` | Userspace ABI/structure checks; not a rendered-image hardware test |
| `prodockctl demo` | Render a test sequence and compare pixels; requires GPU ownership |
| `nebula --demo` | Automatic space shooter, when included in that package |
| `luma3d-maze --festival` | Latest packaged MAZE automatic festival, when installed |

Only one rendering application should own `/dev/prodock-gpu`. An `EBUSY` result
while a game is running is not automatically a broken GPU. Exit the game before
launching another renderer or a destructive self-test. The independent display
interface permits layout/terminal management without stealing rendering ownership.

## MAZE controls and packages

The latest run reported these controls:

| Key | Action |
|---|---|
| W/A/S/D | Move |
| I/U/K/L | Camera |
| Space | Jump |
| E | Interact |
| J | Journal |
| T | Automatic mode |
| N | New garden |
| Q | Quit from the world; context-sensitive inside activities |

In Hangman, Q can be a letter input. Return from a festival activity with its
normal return key before quitting. Individual activities can have their own controls; see the game's startup/help
and [game guide](GAMES.md). `--festival` runs automatically for demonstration.
Do not confuse this executable with the older `games/luma3d` default binary.

To run an application already present on a mounted SD, first establish the
actual mount and filename. For example, after installing it there:

```sh
cd /mnt/sd
./luma3d-maze --festival
```

This is an execution example, not a claim that every shipped SD contains that
file. FAT mount options may control executable permissions. Do not blindly
change mount options or replace the root filesystem to work around an error.

## Persistent versus temporary changes

An executable placed in `/tmp` or a RAM initramfs can disappear after power-off.
A running game after a debugger recovery does not prove that the SD installation
contains it. Record the executable hash and package identity when comparing runs:

```sh
sha256sum /bin/luma3d-maze
uname -r
```

Only use a command if the corresponding file exists in the selected package.
Changing autostart configuration is package-specific; the latest recovery package
set its SD autostart off and launched the embedded game explicitly. It does not
represent the final autonomous-boot policy.

## If the console is silent or the game freezes

1. Check whether USB is enumerated and at the expected physical path.
2. Ensure no other process owns the port and that the terminal is configured.
3. Distinguish a running foreground game from a shell that should answer.
4. Preserve startup logs and the exact kernel/FPGA/game identities.
5. Check the display and GPU status only through commands that do not steal the
   active application's lease.

Do not automatically reload Linux via J-Link. Normal operation must be repaired
through its SD/USB path; CPU inspection is a separate agreed diagnostic step.
A new FPGA SRAM load also changes the running system and may destroy evidence.
