# USB-A2 gamepad host

`usb_ls_engine.v`, the ROM and its assembler derive from
[nand2mario/usb_hid_host](https://github.com/nand2mario/usb_hid_host),
commit `678b0137bd32d1ca99fb2d48865f4eb1df712c4e`, Apache-2.0 (see `LICENSE`).
Upstream credits hi631 and the original UKP authors. The generic upstream
keyboard/mouse/gamepad decoder is not used.

LA16 modifications (2026-10-01):

- Extract UKP as `la16_usb_ls_engine`; add synchronous enable to it and ROM.
- Run on clk100 with 3/25 enables (12 MHz average), no generated clock.
  Tick intervals are 80/90 ns; eight-tick USB bits are 660/670 ns.
- Synchronize D+/D−, initialize receiver/state on reset, release both pins
  during reset. Restore the existing device-descriptor request and save VID/PID.
- Pipeline D+/D− and output enable together by one clk100 cycle (10 ns),
  keeping the instruction decoder out of the output-register path. Expose a
  registered snapshot of engine PC, state, instruction and line levels over AHB.
- G13: complete device/configuration control reads with OUT/DATA1 status,
  wait at least 2 ms after SET_ADDRESS, distinguish ACK from NAK using the
  complete PID, and return a negative result after 1 ms waiting for a response.
  Diagnostics now expose PC and return PC (10 bits each), state and line levels.
- G57: hold root-port reset for at least 50 ms, including the partial first
  millisecond tick. Bound enumeration to 2 s after detecting D− high; retries
  cannot indefinitely refresh that deadline. Either watchdog resets the whole
  engine and descriptor/report state together, instead of changing PC alone.
  Register the restart request before distribution. Reset the output enable,
  while the two IOB data registers continuously track the reset engine; this
  avoids routing the high-fanout reset to distant IOB data reset pins.
- New wrappers accept only 8-byte reports from HID `081f:e401`, using its
  captured descriptor: X/Y bytes 0/1, ten buttons in bits 44–53.
- Release momentary inputs after disconnect or 500 ms without a valid report.
  Require neutral controls on attachment; toggle settings only on press edges.

Regenerate ROM with `cd tang/rtl/usbhost/firmware && python3 asukp.py`.
The patched assembler preserves the clock-enable and ROM filename parameter.
`ukp.lst` is generated and is not source.

Board: Sipeed Console 32001C schematic, USB-A2/J16: D+ = H13, D− = G13,
bank 3, 3.3 V. R115/R117 provide 15 kΩ pulldowns; U12 supplies VBUS.
The USB3 acquisition device stays on USB-A1/Q0 lane 2.

Scope: direct low-speed device, configuration 1, interface 0, EP1 IN,
8-byte maximum packet, 10 ms polling. No hub/full-speed support or generic
HID descriptor parser. The inherited engine does not validate received USB
CRC16/data toggles; report length and identity filtering are not a substitute.
Physical validation is recorded in `TESTS/TESTS_USB_ANALYSE_2026-09-29.md`.

Control-read status and address recovery follow USB 2.0 sections 8.5.3 and
9.2.6.3 ([specification, archival copy](https://bitsavers.trailing-edge.com/components/usb/USB_2.0_2000.pdf)).
Completing a descriptor read before the next SETUP is a compatibility choice;
a new SETUP can also abort an unfinished control transfer under the specification.

## Console Neo, 2026-10-13

Imported from the local analyser, with original paths/hashes in import.json.
The console uses two independent instances on bus80 and a 3/20 enable.
The engine now validates received DATA CRC16 and does not ACK bad data;
reports are published only after validation and repeated DATA PIDs are
suppressed. This supersedes the inherited no-CRC limitation above.
The original analyser sources were not modified. The Linux driver exposes
raw axes/buttons rather than the analyser's acquisition-control mapping.

N14 adds a fabric register after the enabled ROM, clocked on every bus80
edge. The wire-level bench asserts that the pipelined and original ROM
values are identical at each 3/20 consumer enable, including resets.
This removes the ROM/decoder critical path without changing USB bit timing;
the previous ROM-to-interpreter 6/5 multicycle constraints are removed.
All instruction paths are now checked at the ordinary 80 MHz period.
