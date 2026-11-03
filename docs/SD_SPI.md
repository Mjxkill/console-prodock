# SD, SPI and boot performance

## Actual controller path

The maintained SD path uses the **native Andes ATCSPI200 SPI controller inside
the AE350 integration**, not a newly instantiated FPGA SD engine.
The controller base is `0xf0f00000`; GPIO chip select uses the platform adapter.
A separate FPGA SD-controller example exists in the vendor ecosystem, but its
behavior must not be used to explain this driver's measurements.

| Layer | Source / responsibility |
|---|---|
| Shared PIO engine | [`prodock-spi-pio.c`](../linux/drivers/prodock-spi-pio.c): controller configuration, synchronous FIFO exchange and explicit recovery |
| Declaration-only header | [`prodock-spi-pio.h`](../linux/drivers/prodock-spi-pio.h) |
| Linux adapter | [`prodock-spi.c`](../linux/drivers/prodock-spi.c): SPI framework, GPIO CS and platform integration |
| U-Boot adapter | [`prodock_spi.c`](../linux/uboot/overlay/drivers/spi/prodock_spi.c) |
| Bare-metal adapter | [`sd_ae350.c`](../fw_console/sd_ae350.c) |
| SD command protocol | Linux `mmc_spi`, U-Boot MMC SPI, or project [`sd.c`](../fw_console/sd.c), depending on boot stage |
| Filesystem/application | FAT/ext filesystem behavior and game resource loading, outside the SPI exchange loop |

The source core is shared rather than copied into three independently maintained
drivers. Its test register seam is a model interface, not MMIO executed on the
board. Passing that model does not measure bus latency.

## Transfer contract and FIFO algorithm

`SPI_Master_send_receive(spi, tx, rx, count)` is synchronous. TX NULL sends `0xff`;
RX NULL still drains received data. Zero length performs no MMIO. Exact in-place
TX/RX is supported; arbitrary partial buffer overlaps are not.

The implementation splits longer requests into chunks of at most 512 bytes:

1. Configuration is established separately by init or explicit speed selection.
2. A chunk programs its length and primes up to four bytes in TX before start.
3. Each received byte is drained; if more TX bytes remain, the next byte is
   supplied, maintaining the outstanding-byte pipeline.
4. Requests shorter than four bytes are primed only to their actual length.
5. Completion requires all RX consumed and the controller no longer busy.
6. A failure returns a negative error; partial RX is invalid and recovery is
   required before another exchange. Recovery never replays the failed data.

Chip select belongs to the adapter and stays unchanged between internal chunks.
The function does not print progress or redraw the display in its data loop.
It does not silently lower frequency to make repeated failures look successful.
The header contains declarations and contracts, not function implementations.

## Clock policy and uncertainty

SD identification starts at a low clock (nominally 400 kHz), then normal data
operation targets **20 MHz**. This protocol transition is different from changing
speed opportunistically after errors. The shared engine has an explicit speed
function; the adapter/framework's requests must be checked against its policy.

With an effective 80 MHz SPI source and ordinary divider mode:

```text
SCK = source / [2 × (DIV + 1)]
20 MHz → DIV = 1
```

`DIV` is the low byte of TIMING at offset `0x40`; other bits may make the complete
register value different from `1`. The `0xff` bypass behavior is a separate case.
The nominal 80 MHz follows the integration/clock setup; **SCK has not been measured
at the SD pins in the latest diagnosis**. Those pins are inaccessible to the
available instruments. A register readback is not an independent clock measurement.

The known upstream U-Boot issue of restoring an old TIMING value was investigated.
It should not be asserted as the cause here merely because a similar controller
has that historical bug. The current shared driver and actual running binary
must be inspected separately.

## Measurement boundaries

| Scope | Includes | Does not automatically establish |
|---|---|---|
| FIFO PIO loop | STATUS/DATA MMIO service during payload movement | Physical SCK or SD command response latency |
| Complete controller chunk | Preparation, PIO, completion | Complete MMC command or application read |
| MMC request | Commands, tokens, payload, CRC/busy and driver scheduling | Filesystem metadata and every application overhead |
| `pread` | Time inside the application's read call | Game decoding/upload/render time |
| Game startup | Resources, decode, uploads, initialization | SPI-only throughput |

The latest reported 411 internal **512-byte** chunks confirmed exactly 512 bytes
sent and received each. Their approximate results were:

| Population | Mean | Minimum | Maximum |
|---|---:|---:|---:|
| PIO loop, 411 chunks | 7.106 ms | See per-chunk retained report | See per-chunk retained report |
| Complete chunk, same 411 chunks | 7.394 ms | 6.194 ms | 8.795 ms |
| Application `pread(512)`, separate three samples | 20.576 ms | 19.148 ms | 22.985 ms |

The last row is **not the same population or interval** as the first two.
An older approximately 26 ms observation must not be relabeled as the current
PIO time. Subtracting unrelated means does not locate an overhead.
Cycle-based conversions assume the stated 800 MHz core clock; retain raw cycles
and conversion assumptions alongside milliseconds. Linux, U-Boot and bare-metal
timeout clocks use different facilities; their cost is not interchangeable.

## What the observations suggest, and what they do not prove

At a continuous 20 MHz clock, 512 payload bytes alone occupy 204.8 microseconds.
A much larger software interval needs to be located, not explained by quoting
the theoretical link speed.

The measured payload loop had no observed RX-empty wait. That is consistent
with the CPU/MMIO path servicing the FIFO more slowly than SPI can fill it,
but is not proof of which instruction, bridge or interruption causes the cost.
Generated code includes ordered MMIO/fences. There is no explicit cache flush
for every payload byte in the source loop. A fence is not itself a cache flush;
its observed cost depends on the system's outstanding transactions.

The following remain distinct hypotheses: MMIO/ordering latency, scheduling or
interrupt interference, source clock configuration, controller gaps, MMC token
waiting and higher-layer transactions. Logging every byte would change the
measurement and cannot be used as neutral evidence.

## DMA work

The native DMAC at `0xf0c00000` has been identified by register reads. A candidate
provider was compiled, and failure/teardown tests exposed real lifetime/error
handling problems. This does **not** mean SPI DMA is operational.

Production integration still needs validated request routing, buffer/cache
ownership, transfer completion, cancellation, timeout propagation and resource
release. A provider that reports success after an abort failure would violate
the project contract. No DMA performance gain is claimed until measured on the
board with the actual driver and buffers.

## Tests and next discriminating checks

The publication regression runs four separate local suites:

```sh
python3 linux/tests/test_spi_pio.py --out /tmp/spi_pio.json
python3 linux/tests/test_spi_linux.py --out /tmp/spi_linux.json
python3 linux/tests/test_spi_uboot.py --out /tmp/spi_uboot.json
python3 linux/tests/test_mmc_spi_init.py --out /tmp/mmc_spi_init.json
```

These model FIFO ordering, boundaries, errors, adapter behavior and initialization.
They are not SD throughput tests. Hardware work should retain raw intervals,
lengths, min/max and the exact running image, then isolate one variable at a time.
Measurements are stored in RAM and printed after transfers. Full-screen game
mode suppresses dashboard redraw/SD collection, but other system traffic must
still be accounted for.

The objective is a fast, correct normal SD/USB startup path. Reloading a different
image through JTAG without explaining the measured change is not a fix for it.
