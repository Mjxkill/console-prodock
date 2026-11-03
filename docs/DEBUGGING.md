# CPU debugger connections

The AE350 CPU JTAG interface is routed through expansion-header pins by the
FPGA design. It is a separate interface from the board's FPGA programmer USB
and SOFT-USB console. The tables below describe the checked-in console profiles;
a different FPGA image can assign different expansion pins.

## Tang Mega Pro Dock

Source: [gpu.cst](../tang/constr/gpu.cst), the `ae350_tms`, `ae350_tck`,
`ae350_tdo` and `ae350_tdi` constraints for the FPG676 profile.

| Signal | Direction at debugger | Pro Dock connector label | FPGA package pin |
|---|---|---|---|
| TMS | Output | PMOD1 / J7, IO1 | E25 |
| TCK | Output | PMOD1 / J7, IO0 | C24 |
| TDO | Input | PMOD1 / J7, IO3 | H14 |
| TDI | Output | PMOD1 / J7, IO6 | L18 |
| UART2 TX observation | Input to a serial receiver | PMOD1 / J7, IO7 | H15 |

The CST identifies Pro Dock **IO labels**, not numbered J7 connector positions.
It does not establish the connector's Vref/GND/reset positions; use the board
revision's connector markings or schematic for those connections. No physical
pin number is inferred from an IO label here. The four JTAG signals are
configured as LVCMOS33 in this profile. No separate TRST/SRST signal is listed
in these CPU JTAG constraints.

J-Link settings used by the checked-in [CPU loader](../tools/load_linux.py):

| Setting | Value |
|---|---|
| Target device | `A25` |
| Interface | `JTAG` |
| Initial connection speed | `100` kHz |
| JTAG chain configuration | `-1,-1` (automatic chain placement) |
| Probe selection | The serial number of the connected probe |

The loader also supports 1,000/2,000/4,000 kHz transfer settings. These are
software settings recorded in that tool, not a guaranteed maximum cable speed.

## Tang Mega Neo / Tang Console 138K

Source: [neo.cst](../tang/boards/neo/neo.cst), PG484 profile. Its connector
assignments differ from the Pro Dock:

| Signal | Direction at debugger | Neo connector position and IO label | FPGA package pin |
|---|---|---|---|
| TMS | Output | J7-6, IO7 | D21 |
| TCK | Output | J7-8, IO5 | D22 |
| TDO | Input | J7-10, IO3 | F20 |
| TDI | Output | J7-12, IO1 | W20 |
| UART TX observation | Input to serial receiver | J7-9, IO2 | F19 |

These numbered positions come directly from the Neo CST annotations. Vref,
ground and reset connector positions are not specified by those annotations.
The signal I/O standard is LVCMOS33.

The repository includes an [OpenOCD ESP-Prog configuration](../tools/neo/ae350_espprog.cfg):

| Setting | Value |
|---|---|
| Adapter | FT2232HL / ESP-Prog, FTDI channel 0 |
| USB VID:PID | `0403:6010` |
| Device-description selector | `Dual RS232-HS` |
| Transport | JTAG, 1,000 kHz |
| CPU target | `riscv`, target name `nds.cpu` |
| Instruction-register length | 5 bits |
| Expected CPU TAP IDCODE | `0x1000563D` |

The description selector distinguishes the ESP-Prog from a board programmer
that can advertise the same VID:PID. OpenOCD reads the board's AE350 CPU TAP;
the FPGA configuration TAP and CPU target are distinct.

Package preparation is described in [Installation](INSTALLATION.md), and serial
console access in [Linux console](LINUX_CONSOLE.md).
