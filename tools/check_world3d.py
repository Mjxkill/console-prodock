#!/usr/bin/env python3
"""Qualify the G3D1 world with arbitrary live states, exact pixels and USB traffic."""
import argparse
import json
import re
import struct
import time
import zlib
from pathlib import Path
import serial
from check_gpu_reloads import wait_console


def require(condition, detail):
    if not condition:
        raise RuntimeError(str(detail))


def values(line):
    return {key: int(value, 16 if key in ('crc565', 'lcd') else 10)
            for key, value in re.findall(r'(\w+)=(\w+)', line)}


def packet(state):
    raw = struct.pack('<9f', *state)
    return b'V'+raw+struct.pack('<I', zlib.crc32(raw))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=125)
    parser.add_argument('--min-fps', type=float, default=50)
    args = parser.parse_args()
    require(args.seconds > 0 and args.min_fps > 0, 'Invalid measurement window')
    args.out.mkdir(parents=True, exist_ok=False)
    references = json.loads(args.expected.read_text())
    require(references, 'No reference poses')
    port, snapshot = wait_console()
    require(snapshot['speed_mbps'] == 480, snapshot)
    uart = serial.Serial(port, 115200, timeout=.1, exclusive=True)
    transcript = bytearray()
    result = dict(status='FAIL', usb=snapshot, poses=[], samples=[], invalid_tests=0)

    def command(data, marker, timeout=5):
        uart.write(data)
        uart.flush()
        response = bytearray()
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            response.extend(uart.read(4096))
            if marker in response and response.endswith((b'\r', b'\n')):
                break
        transcript.extend(response)
        require(marker in response, (data, response))
        return response.decode(errors='replace')

    def healthy(record, expected_slivers=None):
        require(all(record[k] == 0 for k in ('errors', 'rejected', 'uf')), record)
        require(record['line'] < 2556 and record['objects'] == 17 and record['sprites3d'] == 24, record)
        if expected_slivers is None:
            expected_slivers = int(record['auto'] == 1 and record['frame'] in (4099, 4101, 4102, 4104))
        require(record['vertices'] == 892 and record['slivers'] == expected_slivers and record['geom_cycles'] > 0, record)

    try:
        uart.reset_input_buffer()
        command(b'?', b'WORLD3D G3D1 hardware=1')
        command(b'L', b'WORLD3D LOADING')
        for reference in references:
            command(packet(reference['state']), b'WORLD3D VIEW OK')
            record = values(command(b'T'+struct.pack('<H', reference['frame']), b'WORLD3D frame='))
            healthy(record, reference['slivers'])
            require(record['auto'] == 0 and record['run'] == 0 and record['loading'] == 1, record)
            require(record['crc565'] == int(reference['crc565'], 16), (reference, record))
            for key in ('commands', 'objects', 'sprites3d', 'vertices', 'triangles', 'clipped', 'slivers'):
                require(record[key] == reference[key], (key, reference, record))
            result['poses'].append(record)
            print('POSE PASS', reference['name'], reference['crc565'], flush=True)
        baseline = result['poses'][-1]
        state = references[-1]['state']
        bad_crc = bytearray(packet(state))
        bad_crc[-1] ^= 1
        invalid_nan = list(state)
        invalid_nan[0] = float('nan')
        outside = list(state)
        outside[4] = 60
        for request, marker in [(bytes(bad_crc), b'VIEW INVALID'), (packet(invalid_nan), b'VIEW INVALID'),
                                (packet(outside), b'VIEW INVALID'), (b'V\x00\x00', b'VIEW TIMEOUT')]:
            command(request, marker)
            record = values(command(b'T'+struct.pack('<H', references[-1]['frame']), b'WORLD3D frame='))
            healthy(record)
            result['invalid_tests'] += 1
            require(record['invalid'] == baseline['invalid']+result['invalid_tests'], record)
            require(record['crc565'] == baseline['crc565'], ('Invalid packet changed live state', record, baseline))
        command(b'R', b'WORLD3D AUTO')
        start = time.monotonic()
        initial = values(command(b'S', b'WORLD3D frame='))
        echo_bytes = 0
        while time.monotonic()-start < args.seconds:
            time.sleep(5)
            payload = bytes((echo_bytes+i*73+31)&255 for i in range(32))
            uart.write(b'E'+struct.pack('<H', len(payload))+payload)
            uart.flush()
            received = bytearray()
            deadline = time.monotonic()+3
            while len(received) < len(payload) and time.monotonic() < deadline:
                received.extend(uart.read(len(payload)-len(received)))
            require(bytes(received) == payload, ('USB echo mismatch', received, payload))
            echo_bytes += len(payload)
            record = values(command(b'S', b'WORLD3D frame='))
            healthy(record)
            require(record['auto'] == 1 and record['run'] == 1 and record['invalid'] == baseline['invalid']+result['invalid_tests'], record)
            previous = result['samples'][-1] if result['samples'] else initial
            require(record['submitted'] > previous['submitted'] and record['total_lo'] > previous['total_lo'], record)
            result['samples'].append(record)
            print('AUTO', round(time.monotonic()-start, 1), record, flush=True)
        elapsed = time.monotonic()-start
        frames = result['samples'][-1]['submitted']-initial['submitted']
        require(frames/elapsed >= args.min_fps, ('Frame rate below requirement', frames/elapsed, args.min_fps))
        command(b'R', b'WORLD3D AUTO')
        result.update(status='PASS', seconds=elapsed, frames=frames, fps=frames/elapsed,
                      echo_bytes=echo_bytes, autoplay_restored=True)
    except Exception as error:
        result['error'] = str(error)
        raise
    finally:
        uart.close()
        (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        (args.out/'usb.txt').write_bytes(transcript)


if __name__ == '__main__':
    main()
