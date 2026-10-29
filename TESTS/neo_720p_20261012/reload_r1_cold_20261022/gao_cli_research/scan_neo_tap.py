#!/usr/bin/env python3
"""Read the FPGA TAP identity through the vendor libusb cable selection."""
import ctypes
import fcntl
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
from probe_route9_led_compare import run_child, usb_identity

out = HERE / 'ft2ch_neo_location12737'
assert not out.exists()
with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    active = subprocess.run(['ps', '-C', 'jtagserver', '-C', 'gao_analyzer', '-C', 'gao_sh',
        '-C', 'openocd', '-C', 'openFPGALoader', '-o', 'pid=,args='], capture_output=True, text=True)
    assert active.returncode == 1 and not active.stdout.strip()
    identity = usb_identity()
    assert identity['neo']['path'].endswith('/3-4.4.1')
    assert identity['esp']['path'].endswith('/3-4.4.2')
    out.mkdir()
    (out / 'identity.json').write_text(json.dumps(dict(usb=identity,
        candidate_location=12737, candidate_cable_index=1,
        selection_not_confirmed_until_fpga_id=True, fpga_programmed=False,
        instruction='Vendor --scan only: no operation or bitstream'), indent=2) + '\n')
    library = ctypes.CDLL('/home/michael/gowin/Programmer/bin/libftd2xx.so')
    count = ctypes.c_ulong(0)
    create = library.FT_CreateDeviceInfoList
    create.argtypes = [ctypes.POINTER(ctypes.c_ulong)]; create.restype = ctypes.c_uint
    detail = library.FT_GetDeviceInfoDetail
    detail.argtypes = [ctypes.c_ulong] + [ctypes.POINTER(ctypes.c_ulong)] * 4 + [ctypes.c_void_p] * 3
    detail.restype = ctypes.c_uint
    status = create(ctypes.byref(count))
    assert status == 0 and count.value < 20, (status, count.value)
    result = []
    for index in range(count.value):
        flags, kind, ident, location = [ctypes.c_ulong(0) for _ in range(4)]
        serial, description = ctypes.create_string_buffer(128), ctypes.create_string_buffer(128)
        handle = ctypes.c_void_p()
        status = detail(index, ctypes.byref(flags), ctypes.byref(kind), ctypes.byref(ident),
                        ctypes.byref(location), serial, description, ctypes.byref(handle))
        result.append(dict(index=index, status=status, flags=flags.value, kind=kind.value,
            vid_pid=hex(ident.value), location=location.value, location_hex=hex(location.value),
            serial=serial.value.decode(errors='replace'), description=description.value.decode(errors='replace')))
    (out / 'details.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

    matches = [d for d in result if d['serial'] == '2025041420A']
    assert len(matches) == 1 and matches[0]['location'] == 12737 and matches[0]['description'] == 'USB Debugger A'
    command = ['/home/michael/gowin/Programmer/bin/programmer_cli', '--scan', '--cable-index', '1', '--location', '12737', '--frequency', '2.5MHz']
    try:
        run_child(command, out / 'scan.log', 20)
    finally:
        print((out / 'scan.log').read_text())
