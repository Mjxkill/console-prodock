# SOFT-USB: console, loading and updates

## Product contract

**SOFT-USB is the intended PC connection for using and loading the console.**
Users should boot from SD and transfer applications, assets and updates over
USB. They should not need a J-Link to install or launch a game.

The CDC console and experimental checked transfer mechanisms exist. A complete
reliable loading/update workflow remains under qualification. Routine CPU JTAG
loading is no longer a substitute for completing this workflow.

## Connections and responsibilities

| Connection | Role | Intended user requirement |
|---|---|---|
| FPGA programmer USB | Initial FPGA configuration, developer SRAM loads and persistent configuration programming | Initial provisioning; not the Linux terminal |
| **SOFT-USB device port** | **USB2 HS console and software transfers between FPGA and PC** | **Normal PC connection** |
| CPU JTAG / J-Link | AE350 halt, registers, memory inspection, exceptional recovery | Explicit diagnostic use only |
| Neo USB-A host ports | Two host ports for controllers | Game input; not the upstream PC connection |

USB3 is **not** part of the console plan. SOFT-USB and the Neo host ports
are separate functions, even though both use the USB2 family of protocols.

The SOFT-USB PHY uses FPGA logic and the board's passive network. Clocking,
reset, constraints and the physical connection all matter. A test must identify
which changed; replacing a cable does not demonstrate a logic fix.

## Link rate and useful throughput

- **High-Speed (HS): 480 Mbit/s.** Required operating mode.
- **Full-Speed (FS): 12 Mbit/s.** Not an accepted substitute for HS here.
- Terminal **115200 baud** describes the CPU serial console/line coding,
  not the USB bus speed.
- `480M` in `lsusb -t` proves a negotiated link mode, not application goodput.
  UART bridging, small messages, host pacing and acknowledgements can dominate.

Inspect a Linux host without changing the board:

```sh
lsusb
lsusb -t
python3 -m serial.tools.list_ports -v
ls -l /dev/serial/by-path/
```

The project device uses VID:PID **359f:2011**. Lab boards can advertise the same
USB serial string (`11252024`). Select a board by its verified physical USB
path rather than assuming that string uniquely identifies it. Close the other
terminal/transfer program before opening the selected device.

## CDC terminal

CDC uses interfaces 0/1, data endpoint 2 and notification endpoint 3. The
FPGA/firmware console path connects the CPU UART to USB. Board Linux uses
`/dev/ttyS0`; the PC normally sees `/dev/ttyACM*`.

See [Linux operation](LINUX_CONSOLE.md). Opening a terminal does not install
Linux, configure a blank FPGA or copy a game. A game already installed under
Linux is launched from the shell.

The MSC data path crosses nominally 80 MHz AHB and 60 MHz USB domains using
asynchronous FIFOs. The Pro Dock CDC bridge instead uses `uart2_to_ep2` in the
60 MHz PHY domain, with its UART and local FIFO; it is not a direct AHB-to-CDC
bulk data path. Reconnect, reset and stale-data replay belong to the contracts.
Historical CDC duplicates and enumeration failures remain in dated reports;
a new version number does not invalidate those observations.

## Existing transfer mechanisms

### Framed application transfer

Development transfers use length/integrity checks, acknowledgements and readback.
Their speed depends on the receiver and host implementation. One recent
conservative upload, with 16-byte chunks and host pacing, achieved approximately
1 KB/s. This is a particular software-path result, not USB2 HS capacity.

There is not yet a supported public `console upload` command covering every boot
state and payload type. A lab script expecting a particular firmware, prompt
and board identity must not be presented as a universal installer.

### Firmware mass storage and DDR staging

The [SD/USB design](../ARCHI/SD_USB_DISQUE.md) adds optional SCSI transparent
Bulk-Only Transport alongside CDC:

| Item | Implementation contract |
|---|---|
| MSC | Interface 2, endpoint 1 IN/OUT; 512-byte HS packets |
| MMIO | `0xe9003000`, identity `UMSC` |
| Firmware | USBDISK R4 / compatible BOT-guard-aware variants |
| Medium | Physical SD or explicitly selected 32 MiB DDR window |
| Medium unavailable | Report no medium rather than leave host requests pending |

This is a firmware storage service. It is **not** proof that Linux exports
its mounted SD as a USB disk. Firmware, host and Linux must not write the same
filesystem concurrently without explicit ownership transfer.

`tools/stage_linux.py` implements an experimental DDR staging path. It requires
the matching firmware, HS enumeration, expected DDR medium size and serving
state; it performs writes and readback through MSC. DDR mode does not write the
SD. A bootstrap/launch step remains necessary. Large-transfer failures are part
of the qualification history; this is not an endorsed complete end-user loader.

The design document describes the register/BOT contract, not universal validation
of every host, disconnect sequence and payload size.

## Bootstrapping

An unconfigured FPGA cannot enumerate a USB device implemented by its own logic.
The intended dependency chain is:

```text
initial board provisioning
        ↓
persistent FPGA image + resident boot/USB support
        ↓
power on → SD boot → Linux console → game executable
                           ↑
                    SOFT-USB updates
```

Initial FPGA provisioning and Linux/application updates are separate operations.
A future FPGA update over SOFT-USB needs a persistent configuration writer and
a recoverable boot image. Copying a `.fs` file into DDR does not provide that.

The second-board tests reached U-Boot/Linux from SD. Persistent cold boot through
all stages and subsequent USB-only deployment still need repeatable qualification.
No routine J-Link step is included in the normal-user procedure.

## Completion criteria

| Stage | Required behavior | Acceptance evidence |
|---|---|---|
| Identify | Board, firmware, ABI and payload capabilities | Reject wrong-board/version requests before writes |
| Transfer | Bounded sizes, destination checks, chunk integrity | Boundary sizes, FIFO wrap, sustained traffic, no replay |
| Verify | Explicit full-payload integrity result | Independent readback/hash; timeout never reported as success |
| Install | Exclusive SD/filesystem ownership, explicit finalization | Interrupted transfers preserve a usable installation |
| Execute | Start the requested application or payload | Console response and observed startup identity |
| Reconnect | Recover after unplug and FPGA reconfiguration | Repeated cycles, including cable already connected at load |
| Performance | Useful bytes per second, not just link mode | Host, transport and storage timing boundaries |
| Recovery | Deterministic partial-state handling | Disconnect, reset, cancellation, corrupt or invalid image |

CRC detects accidental corruption; it is not an authenticity signature. Existing
boot packages do not implement secure boot. Authenticated updates would require
a separate trust/key-management design.

## Diagnose without bypassing the normal path

1. Identify the board, physical USB path and negotiated HS mode.
2. Separate absent USB, enumerated-but-silent CDC, and a running shell with a
   failing transfer command.
3. Record the running images, command, byte count, result and elapsed time.
4. Inspect transport/receiver errors before changing the implementation.
5. Keep transfer, SD installation and program launch results separate.

Do not automatically reload through CPU JTAG on failure. Preserve evidence
and repair the normal path. CPU inspection, if necessary, is a separately
agreed diagnostic operation.
