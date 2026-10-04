#!/usr/bin/env python3
"""Exercise G0/G1/G2/G3/G4/G5 diagnostic firmware over the MegaPro USB CDC port."""
import argparse
import re
import struct
import time

import serial
from serial.tools import list_ports


def response(dev, prefix, timeout=15):
    deadline = time.monotonic() + timeout
    pending = bytearray()
    while time.monotonic() < deadline:
        pending.extend(dev.read_until(b'\n\r'))
        if b'TRAP' in pending:
            raise SystemExit(f'CPU exception: {pending!r}')
        # read_until can return a fragment when the serial timeout expires.
        # Keep it until the complete BSP LF/CR terminator has arrived.
        if not pending.endswith(b'\n\r'):
            continue
        line = bytes(pending).strip()
        pending.clear()
        print(line.decode('ascii', errors='replace'), flush=True)
        if b'FAIL' in line or b'TRAP' in line:
            raise SystemExit('GPU diagnostic failed')
        if line.startswith(prefix):
            return line
    raise SystemExit(f'Timeout waiting for {prefix!r}')


def test_gpu(dev):
    dev.write(b'V')
    line = response(dev, b'GPU READY')
    sums = [int(v, 16) for v in re.findall(rb'sum[01]=([0-9a-fA-F]+)', line)]
    if len(sums) != 2:
        raise SystemExit('Invalid checksum response')
    previous_frames = None
    for page in (0, 1, 0, 1, 0):
        if previous_frames is not None:
            dev.write(b'F')
            if response(dev, b'GPU FLIP') != f'GPU FLIP page={page}'.encode():
                raise SystemExit('Wrong page acknowledgement')
        time.sleep(.12)  # let the new page traverse two complete frames
        dev.write(b'M')  # CPU reads/writes a separate 1 MiB region while GPU scans
        if response(dev, b'SHARED END', timeout=90) != b'SHARED END errors=0':
            raise SystemExit('Concurrent CPU DDR test failed')
        dev.write(b'S')
        line = response(dev, b'GPU base=')
        fields = dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)', line))
        expected_base = 0x800000 if page == 0 else 0x900000
        if (int(fields[b'base'], 16) != expected_base or fields[b'enable'] != b'1'
                or fields[b'busy'] != b'0' or fields[b'underflows'] != b'0'
                or int(fields[b'sum'], 16) != sums[page]):
            raise SystemExit('Framebuffer status/checksum mismatch')
        frames = int(fields[b'frames'])
        if previous_frames is not None and frames <= previous_frames:
            raise SystemExit('LCD frame counter stopped')
        previous_frames = frames
    print('G1 PASS: DDR framebuffer, palette, 4 page flips, concurrent CPU DDR, zero underflows', flush=True)


def test_blitter(dev):
    previous_frames = None
    for run in range(3):
        dev.write(b'B')
        line = response(dev, b'BLIT END', timeout=60)
        fields = dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)', line))
        if fields.get(b'errors') != b'0' or int(fields.get(b'commands', b'0')) < 50:
            raise SystemExit('Hardware blitter pixel comparison failed')
        expected_sum = int(fields[b'sum'], 16)
        time.sleep(.12)
        dev.write(b'M')
        if response(dev, b'SHARED END', timeout=90) != b'SHARED END errors=0':
            raise SystemExit('Concurrent DDR test failed after blit')
        dev.write(b'S')
        line = response(dev, b'GPU base=')
        status = dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)', line))
        frames = int(status[b'frames'])
        if (int(status[b'base'], 16) != 0x900000 or status[b'enable'] != b'1'
                or status[b'busy'] != b'0' or status[b'underflows'] != b'0'
                or int(status[b'sum'], 16) != expected_sum
                or (previous_frames is not None and frames <= previous_frames)):
            raise SystemExit('Blitter framebuffer scanout mismatch')
        previous_frames = frames
        print(f'G2 pass {run+1}: CPU pixel comparison, guard bytes and LCD checksum exact', flush=True)
    print('G2 PASS: shapes, gradients, overlapping copies, text x1/x2, programmable font', flush=True)


def test_layers(dev):
    dev.write(b'L')
    line=response(dev,b'LAYERS READY',timeout=180)
    fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',line))
    if fields.get(b'poses')!=b'3' or fields.get(b'underflows')!=b'0':
        raise SystemExit('16-layer initialization failed')
    previous_frames=None
    for pose in (1,2,0,1,2,0):
        dev.write(b'P')
        line=response(dev,b'LAYERS POSE',timeout=90)
        fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',line))
        expected_hash=int(fields[b'hash'],16)
        if response(dev,b'LAYERS MOVED')!=f'LAYERS MOVED pose={pose}'.encode():
            raise SystemExit('Layer pose acknowledgement mismatch')
        dev.write(b'M')
        if response(dev,b'SHARED END',timeout=90)!=b'SHARED END errors=0':
            raise SystemExit('CPU DDR corruption with 16 layers active')
        dev.write(b'S')
        line=response(dev,b'GPU base=')
        status=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',line))
        frames=int(status[b'frames'])
        if (status[b'enable']!=b'1' or status[b'busy']!=b'0' or status[b'underflows']!=b'0'
                or status.get(b'layers')!=b'1' or status.get(b'invalid')!=b'0'
                or int(status[b'sum'],16)!=expected_hash
                or (previous_frames is not None and frames<=previous_frames)):
            raise SystemExit('16-layer frame hash/status mismatch')
        previous_frames=frames
    print('G3 PASS: 16 full surfaces, 3 poses, positions/scroll/priority, 6 atomic swaps, concurrent CPU DDR, zero underflows',flush=True)


def test_sprites(dev):
    dev.write(b'O')
    line=response(dev,b'SPRITES READY',timeout=180)
    fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',line))
    if fields.get(b'count')!=b'64' or fields.get(b'poses')!=b'3' or fields.get(b'underflows')!=b'0':
        raise SystemExit('64-sprite initialization failed')
    previous_frames=None
    for pose in (1,2,0,1,2,0):
        dev.write(b'N')
        line=response(dev,b'SPRITES POSE',timeout=90)
        fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',line))
        expected_hash=int(fields[b'hash'],16)
        if response(dev,b'SPRITES MOVED')!=f'SPRITES MOVED pose={pose}'.encode():
            raise SystemExit('Sprite pose acknowledgement mismatch')
        dev.write(b'M')
        if response(dev,b'SHARED END',timeout=90)!=b'SHARED END errors=0':
            raise SystemExit('CPU DDR corruption with sprites active')
        dev.write(b'S')
        line=response(dev,b'GPU base=')
        status=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',line))
        frames=int(status[b'frames'])
        if (status[b'enable']!=b'1' or status[b'busy']!=b'0' or status[b'underflows']!=b'0'
                or status.get(b'sprites')!=b'1' or status.get(b'invalid_sprites')!=b'0'
                or status.get(b'max_sprites')!=b'64' or int(status[b'sum'],16)!=expected_hash
                or (previous_frames is not None and frames<=previous_frames)):
            raise SystemExit('Sprite frame hash/status mismatch')
        previous_frames=frames
    print('G4 PASS: 64 cached DDR sprites, size 8/16/32, flip XY, transparency, layer priorities, image animation, 6 atomic swaps, CPU DDR, zero underflows',flush=True)


def test_tiles(dev):
    dev.write(b'U')
    line=response(dev,b'TILES READY',timeout=180)
    fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',line))
    if fields.get(b'poses')!=b'4' or fields.get(b'underflows')!=b'0':
        raise SystemExit('Tile map initialization failed')
    previous_frames=None
    for pose in (1,2,3,0,1,2,3,0):
        dev.write(b'Y')
        fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'TILES POSE',timeout=90)))
        expected_hash=int(fields[b'hash'],16)
        if int(fields[b'max_cycles'])>=2556:
            raise SystemExit('Tile map scene exceeds the line budget')
        if response(dev,b'TILES MOVED')!=f'TILES MOVED pose={pose}'.encode():
            raise SystemExit('Tile pose acknowledgement mismatch')
        dev.write(b'M')
        if response(dev,b'SHARED END',timeout=90)!=b'SHARED END errors=0':
            raise SystemExit('CPU DDR corruption with tile maps active')
        dev.write(b'S')
        status=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'GPU base=')))
        frames=int(status[b'frames'])
        if (status[b'enable']!=b'1' or status[b'busy']!=b'0' or status[b'underflows']!=b'0'
                or status.get(b'layers')!=b'1' or status.get(b'sprites')!=b'1'
                or status.get(b'invalid')!=b'0' or status.get(b'invalid_sprites')!=b'0'
                or int(status[b'sum'],16)!=expected_hash
                or (previous_frames is not None and frames<=previous_frames)):
            raise SystemExit('Tile map frame hash/status mismatch')
        previous_frames=frames
    # Scrolling: one descriptor update per LCD frame, no drawing command.
    dev.write(b'W')
    response(dev,b'TILES SCROLL')
    for _ in range(2):
        fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'TILES BENCH',timeout=30)))
        if (fields[b'frames']!=b'240' or fields[b'underflows']!=b'0' or fields[b'invalid']!=b'0'
                or fields[b'gpu_commands']!=b'0'):
            raise SystemExit('Tile map scrolling status mismatch')
        assert int(fields[b'fps_x100'])>5400, 'Scrolling does not follow the panel refresh rate'
        assert int(fields[b'max_cycles'])<2556, 'Scrolling exceeds the line budget'
    dev.write(b'M')  # CPU DDR traffic while the scene keeps scrolling
    if response(dev,b'SHARED END',timeout=90)!=b'SHARED END errors=0':
        raise SystemExit('CPU DDR corruption while scrolling tile maps')
    response(dev,b'TILES BENCH',timeout=30)
    dev.write(b'S')
    status=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'GPU base=')))
    if status[b'underflows']!=b'0' or status.get(b'invalid')!=b'0':
        raise SystemExit('Missing lines while scrolling under CPU DDR traffic')
    print('L11 PASS: tile maps 8/16/32, flips, wrap, map end, surface and sprites, 4 exact poses x2, scrolling at the panel rate without drawing, concurrent CPU DDR, zero underflows',flush=True)


def test_3d(dev):
    dev.write(b'T')
    line=response(dev,b'THREED READY',timeout=180)
    fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',line))
    if fields.get(b'poses')!=b'4' or fields.get(b'underflows')!=b'0':
        raise SystemExit('3D initialization failed')
    for pose in (1,2,3,0):
        dev.write(b'J')
        fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'THREED POSE',timeout=90)))
        if (int(fields.get(b'triangles',b'0'))==0 or fields.get(b'underflows')!=b'0'
                or (pose==3 and int(fields.get(b'clipped',b'0'))==0)):
            raise SystemExit('3D triangle/clipping coverage missing')
        if response(dev,b'THREED MOVED')!=f'THREED MOVED pose={pose}'.encode():
            raise SystemExit('Wrong 3D pose acknowledgement')
        dev.write(b'M')
        if response(dev,b'SHARED END',timeout=90)!=b'SHARED END errors=0':
            raise SystemExit('CPU DDR corruption with 3D active')
        dev.write(b'S')
        status=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'GPU base=')))
        if (status.get(b'layers')!=b'1' or status.get(b'sprites')!=b'0'
                or status.get(b'underflows')!=b'0' or status.get(b'busy')!=b'0'
                or status.get(b'invalid')!=b'0' or status.get(b'sum')!=fields[b'hash']):
            raise SystemExit('3D composed frame mismatch')
    dev.write(b'A')
    response(dev,b'THREED ANIMATION started')
    dev.write(b'M')
    if response(dev,b'SHARED END',timeout=90)!=b'SHARED END errors=0':
        raise SystemExit('CPU DDR corruption during 3D demo')
    fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'THREED BENCH',timeout=90)))
    if (fields.get(b'frames')!=b'120' or fields.get(b'underflows')!=b'0'
            or any(int(fields.get(k,b'0'))==0 for k in (b'cpu_avg',b'gpu_avg',b'frame_avg',b'fps_x100'))):
        raise SystemExit('3D animation benchmark failed')
    dev.write(b'X')
    response(dev,b'THREED PAUSED')
    time.sleep(.12)  # Let the last committed page finish scanning before hashing.
    dev.write(b'S')
    a=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'GPU base=')))
    time.sleep(.15)
    dev.write(b'S')
    b=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'GPU base=')))
    if a[b'sum']!=b[b'sum'] or int(b[b'frames'])<=int(a[b'frames']) or b[b'underflows']!=b'0':
        raise SystemExit('3D pause/display continuity failed')
    print('G5 PASS: triangle pixels+guards, 4 reference poses, near clipping, 2 composed layers, atomic double buffering, 120 animated frames, CPU/GPU timing, USB pause, zero underflows',flush=True)
    dev.write(b'A')  # Leave both cubes rotating for the visual check.
    response(dev,b'THREED ANIMATION started')


def test_racer(dev):
    dev.write(b'XG')
    line=response(dev,b'RACE VERIFIED',timeout=180)
    if b'poses=4 underflows=0' not in line:raise SystemExit('Racer pixel comparison failed')
    dev.write(b'R');response(dev,b'RACE READY')
    def controls(mask,seconds):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            dev.write(bytes([0x80|mask]));time.sleep(.04)
    def status():
        dev.write(b'H')
        fields=dict(re.findall(rb'(\w+)=(-?\d+)',response(dev,b'RACE STATUS')))
        assert fields[b'underflows']==b'0'
        return {k.decode():int(v) for k,v in fields.items()}
    controls(16|4,.12);controls(4,2)
    a=status();assert a['phase']==1 and a['speed']>100 and a['distance']>0
    controls(4|2,.4);b=status();assert b['x']>a['x']
    controls(4|1,.6);c=status();assert c['x']<b['x']
    controls(8,.4);d=status();assert d['speed']<c['speed']
    controls(4,.2);time.sleep(.55)
    e=status();assert e['keys']==0, 'Input watchdog failed'
    dev.write(b'M')
    assert response(dev,b'SHARED END',timeout=90)==b'SHARED END errors=0'
    fields=dict(re.findall(rb'(\w+)=(\d+)',response(dev,b'RACE BENCH',timeout=30)))
    assert fields[b'underflows']==b'0' and int(fields[b'fps_x100'])>0
    controls(16,.12);controls(0,.1)
    a=status();assert a['phase']==1 and a['distance']==0 and a['speed']==0 and a['hits']==0
    dev.write(b'XR');response(dev,b'RACE READY')
    print('G6 PASS: 4 exact images+guards, zoom, USB driving, steering, brake, watchdog, restart, concurrent DDR, benchmark, zero underflows',flush=True)


def test_racer_perf(dev):
    dev.write(b'K')
    for mode in (b'original',b'cached'):
        line=response(dev,b'RACE PERF',timeout=60)
        fields=dict(re.findall(rb'(\w+)=([\w]+)',line))
        assert fields[b'mode']==mode and fields[b'frames']==b'240' and fields[b'underflows']==b'0'
        assert int(fields[b'fps_x100'])>5300, 'Scene does not sustain the panel refresh rate'
        assert int(fields[b'gpu_max'])<14000000, 'Insufficient GPU margin for 18.17 ms LCD frame'
    response(dev,b'RACE READY')
    print('FAST PASS: original and cached renderers, 240 deterministic frames each, >53 fps, GPU max <17.5 ms, zero underflows',flush=True)


def test_affine(dev):
    dev.write(b'I')
    fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'AFFINE READY',timeout=180)))
    assert fields.get(b'poses')==b'4' and fields.get(b'underflows')==b'0'
    dev.write(b'Z');response(dev,b'AFFINE ANIMATION started')
    for _ in range(2):
        fields=dict(re.findall(rb'(\w+)=(\d+)',response(dev,b'AFFINE BENCH',timeout=30)))
        assert fields[b'frames']==b'240' and fields[b'underflows']==b'0'
        assert int(fields[b'fps_x100'])>5300
        assert int(fields[b'gpu_max'])<14000000
    dev.write(b'M')
    assert response(dev,b'SHARED END',timeout=90)==b'SHARED END errors=0'
    response(dev,b'AFFINE BENCH',timeout=30)
    dev.write(b'Q');response(dev,b'AFFINE PAUSED')
    time.sleep(.12)
    dev.write(b'S')
    a=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'GPU base=')))
    time.sleep(.12)
    dev.write(b'S')
    b=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'GPU base=')))
    assert a[b'sum']==b[b'sum'] and int(b[b'frames'])>int(a[b'frames'])
    assert b[b'underflows']==b'0' and b[b'invalid']==b'0' and b[b'busy']==b'0'
    print('L12 PASS: 4 exact affine poses+guards, rotation, independent XY scale, shear, transparency, atomic double buffering, >53 fps, concurrent CPU DDR, USB pause, zero underflows',flush=True)
    dev.write(b'Z');response(dev,b'AFFINE ANIMATION started')


def test_raster(dev,advanced=False):
    dev.write(b'd' if advanced else b'a')
    expected=([b'6121d64d',b'ff0e3a83',b'c54c5c04',b'fa3fafee'] if advanced else
              [b'5c621648',b'acabdcd1',b'56021377',b'25d5618a'])
    lcd_expected=[b'58ab9465',b'5d78b787',b'4c1385a9',b'5cc829f0']
    for pose,want in enumerate(expected):
        if advanced:
            overlay=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'RASTER OVERLAY',timeout=180)))
            assert overlay[b'sum']==lcd_expected[pose] and overlay[b'underflows']==b'0'
            assert 0<int(overlay[b'line_cycles'])<2500
        fields=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'RASTER POSE',timeout=180)))
        assert int(fields[b'angle'])==pose*37 and fields[b'sum']==want
        assert fields[b'underflows']==b'0'
    fields=dict(re.findall(rb'(\w+)=(\d+)',response(dev,b'RASTER READY')))
    assert all(fields.get(k)==b'1' for k in (b'rgb565',b'alpha',b'textures',b'depth'))
    assert fields.get(b'perspective',b'0')==(b'1' if advanced else b'0')
    assert fields.get(b'overlay',b'0')==(b'1' if advanced else b'0')
    assert fields[b'poses']==b'4' and fields[b'underflows']==b'0'
    dev.write(b'e' if advanced else b'b');response(dev,b'RASTER ANIMATION started')
    # Five windows including the one after M cover the complete 512-phase
    # rotation and its wrap, where the first demo had a discontinuity.
    for _ in range(4):
        fields=dict(re.findall(rb'(\w+)=(\d+)',response(dev,b'RASTER BENCH',timeout=30)))
        assert fields[b'frames']==b'120' and fields[b'underflows']==b'0'
        assert int(fields[b'fps_x100'])>5300, 'RGB/depth demo below panel cadence'
        assert int(fields[b'gpu_max'])<14000000, 'RGB/depth drawing exceeds frame budget'
    dev.write(b'M');assert response(dev,b'SHARED END',timeout=90)==b'SHARED END errors=0'
    response(dev,b'RASTER BENCH',timeout=30)
    dev.write(b'c');response(dev,b'RASTER PAUSED')
    # The last page was committed at vblank; its checksum is published only
    # after scanout finishes that frame, just as for the indexed/affine mode.
    time.sleep(.12)
    dev.write(b'S');a=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'GPU base=')))
    time.sleep(.12)
    dev.write(b'S');b=dict(re.findall(rb'(\w+)=([0-9a-fA-F]+)',response(dev,b'GPU base=')))
    assert a[b'sum']==b[b'sum'] and int(b[b'frames'])>int(a[b'frames'])
    assert b[b'underflows']==b'0' and b[b'layers']==(b'1' if advanced else b'0') and b[b'busy']==b'0'
    test_gpu(dev)  # Return to indexed palette mode and check every legacy hash.
    dev.write(b'e' if advanced else b'b');response(dev,b'RASTER ANIMATION started')
    print(('PERSPECTIVE + RGB565 OVERLAY PASS: exact rational textures, indexed HUD, sprites, tiles, LCD sums; ' if advanced else '')+'L13-L15 PASS: RGB565 alpha, affine textures, Z16, four exact color/depth images+guards, >53 fps, DDR concurrency, indexed return',flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait', type=float, default=15)
    args = parser.parse_args()
    deadline = time.monotonic() + args.wait
    while True:
        ports = [p for p in list_ports.comports() if (p.vid, p.pid) == (0x359f, 0x2011)]
        if len(ports) == 1:
            break
        if len(ports) > 1 or time.monotonic() > deadline:
            raise SystemExit(f'Expected one MegaPro USB CDC port, found {ports}')
        time.sleep(.2)
    with serial.Serial(ports[0].device, 115200, timeout=.2, write_timeout=2, exclusive=True) as dev:
        print(f'PORT {ports[0].device}', flush=True)
        time.sleep(.3)
        dev.reset_input_buffer()
        dev.write(b'X?')  # Stop a running G5 animation before destructive tests.
        identity = response(dev,b'MegaPro GPU')
        if b'MegaPro GPU G' not in identity or b'core=800MHz' not in identity:
            raise SystemExit('Wrong firmware or no response')
        for n in (1, 64, 256, 1024, 4096):
            data = bytes((i * 73 + 19) & 255 for i in range(n))
            dev.write(b'E' + struct.pack('<H', n) + data)
            received = bytearray()
            deadline = time.monotonic() + 5
            while len(received) < n and time.monotonic() < deadline:
                received.extend(dev.read(n - len(received)))
            if received != data:
                raise SystemExit(f'Echo mismatch: {len(received)}/{n} bytes')
            print(f'ECHO {n} PASS', flush=True)
        dev.write(b'D')
        deadline = time.monotonic() + 90
        pending = bytearray()
        failures = False
        while time.monotonic() < deadline:
            pending.extend(dev.read(256))
            while b'\n' in pending:
                line, _, pending = pending.partition(b'\n')
                line = line.strip(b'\r')
                print(line.decode('ascii', errors='replace'), flush=True)
                failures |= line.startswith(b'FAIL')
                if b'TRAP' in line or b'Unhandled Trap' in line:
                    raise SystemExit('CPU exception during DDR test')
                if line.startswith(b'DDR END '):
                    if line != b'DDR END errors=0' or failures:
                        raise SystemExit('DDR verification failed')
                    print('G0 PASS', flush=True)
                    if re.search(rb'GPU G[123456] ',identity):
                        test_gpu(dev)
                    if re.search(rb'GPU G[23456] ',identity):
                        test_blitter(dev)
                    if re.search(rb'GPU G[3456] ',identity):
                        test_layers(dev)
                    if re.search(rb'GPU G[456] ',identity):
                        test_sprites(dev)
                    if re.search(rb'GPU G[56] ',identity):
                        test_3d(dev)
                    if b' TILES ' in identity:
                        test_tiles(dev)
                    if b'GPU G6 ' in identity:
                        test_racer(dev)
                    if b' FAST ' in identity:
                        test_racer_perf(dev)
                    if b' AFFINE ' in identity:
                        test_affine(dev)
                    if b' RASTER ' in identity:
                        test_raster(dev)
                    if b' PERSPECTIVE ' in identity and b' OVERLAY ' in identity:
                        test_raster(dev,advanced=True)
                    return
        raise SystemExit(f'DDR timeout; pending={pending!r}')


if __name__ == '__main__':
    main()
