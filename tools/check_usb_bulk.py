#!/usr/bin/env python3
"""Diagnostic d'échos EP2 sans le pilote série cdc_acm (Linux usbfs).

Sélectionne 359f:2011 / 11252024, détache temporairement cdc_acm puis le
rattache en sortie. Aucun reset USB, changement de configuration ou bitstream.
Le firmware doit être au repos et aucun lecteur série ne doit être actif.
Les lectures IN restent actives pendant l'envoi OUT et le délai de grâce.
Ce diagnostic change le rythme des IN ; il ne remplace pas l'endurance CDC.
"""
import argparse
import ctypes
import errno
import fcntl
import io
import contextlib
import json
from pathlib import Path
import struct
import subprocess
import threading
import time

from usb_control_probe import control


# ABI de /usr/include/linux/usbdevice_fs.h ; tailles natives, pointeurs inclus.
class Bulk(ctypes.Structure):
    _fields_ = [('ep', ctypes.c_uint), ('length', ctypes.c_uint),
                ('timeout', ctypes.c_uint), ('data', ctypes.c_void_p)]


class DriverIoctl(ctypes.Structure):
    _fields_ = [('interface', ctypes.c_int), ('code', ctypes.c_int),
                ('data', ctypes.c_void_p)]


def bulk(fd, endpoint, payload=None):
    buf = ctypes.create_string_buffer(512 if payload is None else payload)
    length = 512 if payload is None else len(payload)
    req = Bulk(endpoint, length, 20 if payload is None else 1000,
               ctypes.addressof(buf))
    n = fcntl.ioctl(fd, 0xc0005502 | (ctypes.sizeof(Bulk) << 16),
                    bytearray(bytes(req)))
    return buf.raw[:n] if payload is None else n


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rounds', type=int, default=1024)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 10000:
        parser.error('rounds doit être entre 1 et 10000')
    devices = []
    for path in Path('/sys/bus/usb/devices').glob('*'):
        try:
            identity = tuple((path / name).read_text().strip()
                             for name in ('idVendor', 'idProduct', 'serial'))
            if identity == ('359f', '2011', '11252024'):
                devices.append(path)
        except OSError:
            pass
    if len(devices) != 1:
        raise SystemExit('Expected exactly one Pro Dock console 359f:2011 / 11252024')
    path = devices[0]
    ports = list((path / (path.name + ':1.0')).glob('tty/ttyACM*'))
    if len(ports) != 1:
        raise SystemExit('Expected the bound CDC control interface and one ttyACM port')
    port = '/dev/' + ports[0].name
    owner = subprocess.run(['fuser', port], capture_output=True, text=True)
    if owner.returncode != 1 or owner.stdout.strip() or owner.stderr.strip():
        raise SystemExit(f'Cannot establish an idle serial port: {owner.stdout} {owner.stderr}')
    node = '/dev/bus/usb/%03d/%03d' % (int((path/'busnum').read_text()),
                                      int((path/'devnum').read_text()))
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(status='running', topology=path.name, serial='11252024',
                  samples=[], zero_length=0, timeouts=0, packets=[], reader_errors=[])
    stop = threading.Event()
    condition = threading.Condition()
    received = bytearray()

    def reader(fd):
        while not stop.is_set():
            try:
                data = bulk(fd, 0x82)
            except OSError as error:
                if error.errno == errno.ETIMEDOUT:
                    result['timeouts'] += 1
                    continue
                result['reader_errors'].append(dict(time=time.monotonic(), errno=error.errno,
                                                    error=str(error)))
                with condition:
                    condition.notify_all()
                return
            with condition:
                if data:
                    result['packets'].append(dict(time=time.monotonic(), data=data.hex()))
                    received.extend(data)
                else:
                    result['zero_length'] += 1
                condition.notify_all()

    thread = None
    claimed = []
    detached = False
    try:
        with open(node, 'r+b', buffering=0) as fd:
            try:
                # Atomically detach only cdc_acm and claim its control interface.
                claim = struct.pack('II256s', 0, 1, b'cdc_acm')
                fcntl.ioctl(fd, 0x8000551b | (len(claim) << 16), claim)
                detached = True
                claimed.append(0)
                fcntl.ioctl(fd, 0x8004550f, struct.pack('I', 1))
                claimed.append(1)
                thread = threading.Thread(target=reader, args=(fd,))
                thread.start()
                time.sleep(.1)
                with condition:
                    if received or result['reader_errors']:
                        raise RuntimeError('Unexpected initial data or bulk read error')
                for i in range(args.rounds):
                    expected = bytes([(i*73+17) & 255])
                    start = time.monotonic()
                    command = b'E\x01\x00' + expected
                    if bulk(fd, 0x02, command) != len(command):
                        raise RuntimeError('Short bulk OUT transfer')
                    with condition:
                        while not received and not result['reader_errors'] and time.monotonic()-start < 1:
                            condition.wait(timeout=max(.001, 1-(time.monotonic()-start)))
                    time.sleep(.01)
                    with condition:
                        got = bytes(received)
                        received.clear()
                    sample = dict(index=i, expected=expected.hex(), received=got.hex())
                    result['samples'].append(sample)
                    if got != expected or result['reader_errors']:
                        # Same descriptor, reader and endpoint remain active.
                        time.sleep(1)
                        with condition:
                            got += bytes(received)
                            received.clear()
                        sample.update(received_after_grace=got.hex(), elapsed=time.monotonic()-start)
                        result['status'] = ('usb_error' if result['reader_errors'] else
                                            'late' if got == expected else 'mismatch')
                        stop.set()
                        thread.join()
                        trace = io.StringIO()
                        try:
                            with contextlib.redirect_stdout(trace):
                                control(fd, True, True)
                                control(fd, True, False)
                        except Exception as error:
                            result['diagnostic_error'] = str(error)
                        (args.out/'diagnostic.txt').write_text(trace.getvalue())
                        print(json.dumps(sample), flush=True)
                        print(trace.getvalue(), end='', flush=True)
                        break
                else:
                    result['status'] = 'pass'
                    print(f'PASS: {args.rounds} direct bulk bytes exact (diagnostic only)', flush=True)
            finally:
                stop.set()
                if thread is not None:
                    thread.join()
                cleanup_errors = []
                for interface in reversed(claimed):
                    try:
                        fcntl.ioctl(fd, 0x80045510, struct.pack('I', interface))
                    except OSError as error:
                        cleanup_errors.append(str(error))
                if detached:
                    try:
                        request = DriverIoctl(0, 0x5517, None)  # USBDEVFS_CONNECT
                        fcntl.ioctl(fd, 0xc0005512 | (ctypes.sizeof(request) << 16),
                                    bytearray(bytes(request)))
                    except OSError as error:
                        cleanup_errors.append(str(error))
                result['cleanup_errors'] = cleanup_errors
                driver = path / (path.name+':1.0') / 'driver'
                result['cdc_rebound'] = driver.is_symlink() and driver.resolve().name == 'cdc_acm'
                if result['reader_errors'] and result['status'] == 'pass':
                    result['status'] = 'usb_error'
    except Exception as error:
        result.update(status='error', error=str(error))
        raise
    finally:
        (args.out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print('CDC restored:', result.get('cdc_rebound'), flush=True)
    return int(result['status'] != 'pass' or bool(result.get('cleanup_errors'))
               or not result.get('cdc_rebound'))


if __name__ == '__main__':
    raise SystemExit(main())
