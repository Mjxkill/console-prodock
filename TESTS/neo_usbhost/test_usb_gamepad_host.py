"""Wire-level low-speed USB device: enumerate captured descriptors and send HID."""
from pathlib import Path
import os
import shutil
import cocotb
from cocotb.triggers import RisingEdge, FallingEdge, Timer, with_timeout
from cocotb.utils import get_sim_time
from cocotb.runner import get_runner, get_results

HERE = Path(__file__).resolve().parent
RTL = HERE.parents[1] / "tang/boards/neo/usbhost"
BIT_NS = 666.667
DEVICE_BIT_NS = float(os.environ.get("GAMEPAD_DEVICE_BIT_NS", str(BIT_NS)))
DEVICE = bytes.fromhex("12010001000000081f0801e4060100020001")
CONFIG = bytes.fromhex("0902220001010080fa0904000001030000000921100121012262000705810308000a")


def crc16(data):
    crc = 0xffff
    for byte in data:
        for bit in range(8):
            mix = (crc ^ (byte >> bit)) & 1
            crc >>= 1
            if mix:
                crc ^= 0xa001
    return (crc ^ 0xffff).to_bytes(2, "little")


async def send(d, packet):
    # Host releases after EOP; 2 USB bit times turnaround before response.
    if int(d.host_oe.value):
        await FallingEdge(d.host_oe)
    await Timer(round(2 * DEVICE_BIT_NS, 3), units="ns")
    level, ones = 1, 0
    d.dev_drive.value = 1
    for byte in b"\x80" + packet:
        for bit in range(8):
            value = (byte >> bit) & 1
            if not value:
                level ^= 1
            d.dev_dp.value = 1 - level
            d.dev_dm.value = level
            await Timer(DEVICE_BIT_NS, units="ns")
            ones = ones + 1 if value else 0
            if ones == 6:
                level ^= 1
                d.dev_dp.value = 1 - level
                d.dev_dm.value = level
                await Timer(DEVICE_BIT_NS, units="ns")
                ones = 0
    d.dev_dp.value = 0; d.dev_dm.value = 0
    await Timer(round(2 * DEVICE_BIT_NS, 3), units="ns")
    d.dev_dm.value = 1
    await Timer(DEVICE_BIT_NS, units="ns")
    d.dev_drive.value = 0


async def receive(d):
    while True:
        await RisingEdge(d.dp)
        if int(d.host_oe.value):
            break
    await Timer(round(BIT_NS / 2, 3), units="ns")
    bits, last, ones = [], 1, 0
    for _ in range(256):
        dp, dm = int(d.dp.value), int(d.dm.value)
        if dp == dm == 0:
            assert len(bits) % 8 == 0, bits
            data = bytes(sum(bits[i+j] << j for j in range(8)) for i in range(0, len(bits), 8))
            assert data[0] == 0x80, data.hex()
            return data[1:]
        assert dp != dm, (dp, dm)
        bit = int(dm == last)
        last = dm
        if ones == 6:
            assert bit == 0, "missing stuffed bit"
            ones = 0
        else:
            bits.append(bit)
            ones = ones + 1 if bit else 0
        await Timer(BIT_NS, units="ns")
    raise AssertionError("unterminated host packet")


async def device(d, observed, drop_configuration=False):
    payload, offset, setup, toggle = b"", 0, False, 0x4b
    control_read, status_out, completed_reads = False, False, 0
    response_dropped = False
    bad_crc_sent = duplicate_sent = False
    corrupt_after = duplicate_after = False
    previous_pid = None
    nak_sent, after_nak = False, False
    configuration_dropped, configuration_missing = False, False
    for _ in range(5000):
        packet = await with_timeout(receive(d), 400, "ms")
        observed.append(packet.hex())
        pid = packet[0]
        if corrupt_after:
            assert pid != 0xd2, "host must not ACK bad CRC16"
            assert int(d.report_count.value) == 0, "bad CRC leaked a report"
            corrupt_after = False
        if duplicate_after:
            assert int(d.report_count.value) == 1, "duplicate PID replayed a report"
            duplicate_after = False
        if after_nak:
            assert pid != 0xd2, "host must not ACK a NAK"
            after_nak = False
        if pid == 0x2d:
            assert not control_read, "descriptor read must finish with its OUT status stage"
            setup = True
        elif pid == 0xc3 and setup:
            request = packet[1:-2]
            assert len(request) == 8 and crc16(request) == packet[-2:]
            if request[1] == 9 and drop_configuration and not configuration_dropped:
                # A lost SET_CONFIGURATION cannot be repaired by indefinitely
                # repeating only its IN status stage. Require a fresh SETUP.
                configuration_dropped = configuration_missing = True
                setup = False
                continue
            configuration_missing = False
            if request[1] == 6:
                payload = (DEVICE if request[3] == 1 else CONFIG)[:int.from_bytes(request[6:8], "little")]
                control_read = True
            else:
                assert request[1] in (5, 9), request.hex()
                payload = b""
            offset, toggle, setup = 0, 0x4b, False
            await send(d, b"\xd2")
        elif pid == 0xe1:
            assert control_read and offset == len(payload), (offset, payload.hex())
            assert packet == bytes.fromhex("e10010"), packet.hex()
            status_out = True
        elif pid == 0x4b and status_out:
            assert packet == bytes.fromhex("4b0000"), packet.hex()
            await send(d, b"\xd2")
            control_read, status_out = False, False
            completed_reads += 1
        elif pid == 0x69:
            token = int.from_bytes(packet[1:3], "little")
            address, endpoint = token & 127, (token >> 7) & 15
            if endpoint == 1:
                assert address == 1
                assert completed_reads >= 2 and completed_reads % 2 == 0, completed_reads
                if not response_dropped:
                    # One deliberately silent transaction must not wedge START.
                    response_dropped = True
                    continue
                if not nak_sent:
                    await send(d, b"\x5a")
                    nak_sent, after_nak = True, True
                    continue
                report_number = int(d.report_count.value)
                # Neutral, START pressed, released, left, neutral, source toggle.
                payloads = [bytes.fromhex(s) for s in (
                    "8080000000000000", "8080000000002000", "8080000000000000",
                    "0080000000000000", "8080000000000000", "8080000000100000")]
                data = payloads[min(report_number, len(payloads)-1)]
                if not bad_crc_sent:
                    bad = bytearray(crc16(data)); bad[0] ^= 0x01
                    await send(d, bytes([toggle]) + data + bytes(bad))
                    bad_crc_sent = corrupt_after = True
                    continue
                if report_number == 1 and not duplicate_sent:
                    await send(d, bytes([previous_pid]) + data + crc16(data))
                    duplicate_sent = duplicate_after = True
                    continue
            else:
                assert endpoint == 0
                if configuration_missing:
                    continue
                data = payload[offset:offset+8]
                offset += len(data)
            await send(d, bytes([toggle]) + data + crc16(data))
            previous_pid = toggle
            toggle = 0xc3 if toggle == 0x4b else 0x4b
        else:
            assert pid == 0xd2, packet.hex()
        if int(d.report_count.value) >= 7:
            assert response_dropped and nak_sent and completed_reads >= 2
            assert not drop_configuration or configuration_dropped
            return
    raise AssertionError(f"no reports: {observed}")


@cocotb.test()
async def enumerate_and_poll(d):
    d.rst.value = 1; d.dev_drive.value = 0; d.dev_dp.value = 0; d.dev_dm.value = 1
    await Timer(200, units="ns")
    assert int(d.host_oe.value) == 0
    d.rst.value = 0
    observed = []
    task = cocotb.start_soon(device(d, observed))
    await with_timeout(task, 900, "ms")
    await Timer(1000, units="ns")
    assert int(d.identity.value) == 0xe401081f, (hex(int(d.identity.value)), observed)
    assert int(d.status.value) & 0xb == 0xb
    assert int(d.buttons.value) == 0x80, hex(int(d.buttons.value))
    # At idle the diagnostic must expose the attached low-speed line (D-=1).
    await Timer(50, units="us")
    status = int(d.status.value)
    assert (status >> 6) & 3 == 1, hex(status)
    assert not status & 0x20, hex(status)
    rom_size = len((RTL / "usb_hid_host_rom.hex").read_text().splitlines())
    assert 0 < status >> 22 < rom_size, hex(status)
    assert (status >> 12) & 1023 < rom_size, hex(status)
    d._log.info("Enumerated 081f:e401, completed control reads, recovered silent/NAK EP1 transactions and received reports")


async def reset_pulses(d, durations):
    """Measure actual driven SE0 on the pins, including free-running tick phase."""
    while True:
        await RisingEdge(d.host_oe)
        if int(d.dp.value) or int(d.dm.value):
            continue
        start = get_sim_time(units="ns")
        await FallingEdge(d.host_oe)
        duration = get_sim_time(units="ns") - start
        if duration > 1_000_000:
            durations.append(duration)


@cocotb.test()
async def root_port_reset_duration(d):
    d.rst.value = 1; d.dev_drive.value = 0; d.dev_dp.value = 0; d.dev_dm.value = 1
    await Timer(217, units="ns")
    durations = []
    monitor = cocotb.start_soon(reset_pulses(d, durations))
    d.rst.value = 0
    observed = []
    await with_timeout(device(d, observed), 1100, "ms")
    monitor.kill()
    d._log.info("Root-port reset durations (ms): %s", [t / 1e6 for t in durations])
    assert len(durations) == 2, durations
    # USB 2.0 section 7.1.7.5: root-port reset >= 50 ms, continuous here.
    assert all(t >= 50_000_000 for t in durations), durations


@cocotb.test()
async def missing_configuration_restarts_enumeration(d):
    d.rst.value = 1; d.dev_drive.value = 0; d.dev_dp.value = 0; d.dev_dm.value = 1
    await Timer(193, units="ns")
    d.rst.value = 0
    observed = []
    await with_timeout(device(d, observed, drop_configuration=True), 3100, "ms")
    await Timer(1000, units="ns")
    assert int(d.identity.value) == 0xe401081f
    assert int(d.status.value) & 0xb == 0xb
    d._log.info("Recovered a lost SET_CONFIGURATION by reinitializing and enumerating again")


@cocotb.test()
async def reset_after_reports(d):
    d.rst.value = 1; d.dev_drive.value = 0; d.dev_dp.value = 0; d.dev_dm.value = 1
    await Timer(173, units="ns")
    for cycle in range(2):
        d.rst.value = 0
        await with_timeout(device(d, []), 900, "ms")
        await Timer(1000, units="ns")
        assert int(d.report_count.value) == 7
        assert int(d.report_data.value) != 0
        d.rst.value = 1
        await Timer(200, units="ns")
        assert int(d.host_oe.value) == 0
        assert not int(d.status.value) & 9
        assert int(d.identity.value) == 0
        assert int(d.report_count.value) == 0
        assert int(d.report_data.value) == 0
    d._log.info("PASS two enumerations separated by reset, no old report or identity replay")


if __name__ == "__main__":
    build = Path(os.environ.get("GAMEPAD_BUILD", str(HERE / "sim_build_usb_gamepad_host"))).resolve()
    build.mkdir(exist_ok=True)
    shutil.copyfile(RTL / "usb_hid_host_rom.hex", build / "usb_hid_host_rom.hex")
    runner = get_runner("verilator")
    runner.build(sources=[HERE / "usb_gamepad_host_tb.v", *sorted(RTL.glob("*.v"))],
                 hdl_toplevel="usb_gamepad_host_tb", build_dir=build,
                 build_args=["-Wno-fatal", "--timing", "--timescale", "1ns/1ps"])
    result = runner.test(hdl_toplevel="usb_gamepad_host_tb", test_module="test_usb_gamepad_host",
                         testcase=os.environ.get("GAMEPAD_TESTCASE"))
    count, failures = get_results(result)
    expected = 1 if os.environ.get("GAMEPAD_TESTCASE") else 4
    if count != expected or failures:
        raise SystemExit(f"USB host: {failures} failures / {count} tests")
