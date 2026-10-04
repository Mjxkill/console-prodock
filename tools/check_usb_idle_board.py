#!/usr/bin/env python3
"""Poll empty USB IN endpoints and recover the passive trace through J-Link.

Only console 359f:2011/11252024, HS480, and J-Link 506005083 are used.
Temporarily detach/rebind cdc_acm; no OUT, private EP0, clear-halt, reset,
configuration change or bitstream load. J-Link briefly halts/resumes the CPU
for diagnostic MMIO, without resetting or loading firmware.
"""
import argparse
import ctypes
import errno
import fcntl
import json
from pathlib import Path
import re
import signal
import struct
import subprocess
import threading
import time

from check_gpu_reloads import console_snapshot
from check_usb_bulk import DriverIoctl


class Urb(ctypes.Structure):
    _fields_ = [('type', ctypes.c_ubyte), ('endpoint', ctypes.c_ubyte),
                ('status', ctypes.c_int), ('flags', ctypes.c_uint),
                ('buffer', ctypes.c_void_p), ('buffer_length', ctypes.c_int),
                ('actual_length', ctypes.c_int), ('start_frame', ctypes.c_int),
                ('number_of_packets', ctypes.c_int), ('error_count', ctypes.c_int),
                ('signr', ctypes.c_uint), ('usercontext', ctypes.c_void_p)]


LIBC = ctypes.CDLL(None, use_errno=True)
LIBC.ioctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p]
LIBC.ioctl.restype = ctypes.c_int


def ioctl(fd, request, data):
    if LIBC.ioctl(fd, request, ctypes.byref(data)) < 0:
        code = ctypes.get_errno()
        raise OSError(code, errno.errorcode.get(code, str(code)))


def jlink(out, name, command=None):
    script = ['connect', 'h']
    if command is not None:
        script += [f'w4 0xE900200C, 0x{command:08X}', 'sleep 10']
    script += ['mem32 0xE9002000, 3', 'mem32 0xE9002040, 32', 'g', 'q']
    path = out/(name+'.jlink')
    path.write_text('\n'.join(script)+'\n')
    base = ['JLinkExe', '-SelectEmuBySN', '506005083',
        '-Device', 'A25', '-If', 'JTAG', '-Speed', '1000', '-JTAGConf', '-1,-1',
        '-NoGui', '1', '-ExitOnError', '1', '-CommanderScript']
    def resume_after_error():
        recovery = out/(name+'_resume.jlink')
        recovery.write_text('connect\ng\nq\n')
        resumed = subprocess.run(base+[str(recovery)], capture_output=True, text=True, timeout=30)
        (out/(name+'_resume.log')).write_text(resumed.stdout+resumed.stderr)
        if resumed.returncode:
            raise RuntimeError('J-Link CPU resume failed; see '+str(out/(name+'_resume.log')))
    try:
        result = subprocess.run(base+[str(path)], capture_output=True, text=True, timeout=45)
    except BaseException as error:
        if isinstance(error, subprocess.TimeoutExpired):
            (out/(name+'.log')).write_bytes((error.stdout or b'')+(error.stderr or b''))
        resume_after_error()
        raise
    log = result.stdout+result.stderr
    (out/(name+'.log')).write_text(log)
    words = {}
    for line in log.splitlines():
        match = re.match(r'^([0-9A-Fa-f]{8})\s*=\s*((?:[0-9A-Fa-f]{8}(?:\s+|$))+)', line)
        if match:
            addr = int(match[1], 16)
            for offset, word in enumerate(match[2].split()):
                words[addr+4*offset] = int(word, 16)
    if result.returncode or words.get(0xe9002000) != 0x55544e41:
        resume_after_error()
        raise RuntimeError('J-Link read failed or loaded build has no UTNA observer: '+str(out/(name+'.log')))
    if words.get(0xe9002004) != 0:
        raise RuntimeError('Trace command busy/rejected: '+str(words))
    bank = [words[0xe9002040+4*i] for i in range(32)]
    return dict(sequence=words[0xe9002008], words=bank)


def decode(capture):
    w = capture['words']
    if w[:2] != [0x55544e41, 1]:
        raise RuntimeError('Invalid or incomplete snapshot')
    names = ['ticks', 'in2', 'in3', 'nak2', 'nak3', 'data2', 'data3',
             'missing2', 'missing3', 'bad_response', 'rx_error_cycles',
             'bad_in_tokens', 'bus_resets', 'sofs', 'tx_stall_cycles',
             'last_token', 'last_response']
    d = dict(zip(names, w[3:20]))
    d.update(sequence=capture['sequence'], command=w[2],
             max_nak_offer_cycles=w[20] & 255, max_nak_accept_cycles=(w[20]>>8) & 255,
             armed=bool(w[31] & (1<<10)), pending=bool(w[31] & (1<<9)), address=w[31]&127)
    def event(lo, hi):
        return dict(valid=bool(lo & (1<<31)), missing=bool(lo & (1<<30)),
                    malformed=bool(lo & (1<<29)), cork=bool(lo & (1<<28)),
                    endpoint=(lo>>24)&15, pid=f'{(lo>>16)&255:02x}',
                    accept_cycles=(lo>>8)&255, accepted_bytes=lo&255, token_tick=hi)
    d['history_newest_first'] = [event(w[21+2*i], w[22+2*i]) for i in range(4)]
    d['first_fault'] = event(w[29], w[30])
    return d


def poll(fd, endpoints, seconds, *, repeat=False, stop=None):
    buffers = {ep: ctypes.create_string_buffer(512 if ep==2 else 16) for ep in endpoints}
    urbs = {ep: Urb(type=3 if ep==2 else 1, endpoint=ep|0x80,
                    buffer=ctypes.addressof(buf), buffer_length=len(buf)) for ep,buf in buffers.items()}
    by_address = {ctypes.addressof(urb): ep for ep,urb in urbs.items()}
    pending = set()
    result = dict(status='polling', endpoints=endpoints, completions=[], cancellations=[], discards=[],
                  started_monotonic_ns=time.monotonic_ns())
    def reap(cancel=False):
        pointer = ctypes.c_void_p()
        try:
            ioctl(fd, 0x4000550d | (ctypes.sizeof(pointer)<<16), pointer)
        except OSError as error:
            if error.errno == errno.EAGAIN:
                return False
            raise
        if pointer.value not in by_address:
            raise RuntimeError('Unknown reaped URB')
        ep = by_address[pointer.value]
        pending.remove(ep)
        urb = urbs[ep]
        record = dict(endpoint=ep, status=urb.status, actual=urb.actual_length,
                      monotonic_ns=time.monotonic_ns(), data=buffers[ep].raw[:urb.actual_length].hex())
        record['during_cleanup']=cancel
        cancelled=cancel and urb.status in (-errno.ENOENT,-errno.ECONNRESET) and urb.actual_length==0
        result['cancellations' if cancelled else 'completions'].append(record)
        if cancel and not cancelled:
            result['status']='completion_during_cleanup'
        return True
    try:
        for ep,urb in urbs.items():
            ioctl(fd, 0x8000550a | (ctypes.sizeof(Urb)<<16), urb)
            pending.add(ep)
        end = time.monotonic()+seconds
        while time.monotonic()<end and (stop is None or not stop.is_set()):
            if reap():
                result['status'] = 'unexpected_completion'
                if not repeat:
                    break # empty IN must remain pending under NAK
                for ep,urb in urbs.items():
                    if ep not in pending:
                        urb.status=0;urb.actual_length=0;urb.error_count=0
                        ioctl(fd, 0x8000550a | (ctypes.sizeof(Urb)<<16), urb)
                        pending.add(ep)
            time.sleep(.001)
        else:
            result['status'] = ('repeating_poll_finished' if repeat
                                else 'no_completion_during_window')
    finally:
        for ep in list(pending):
            try:
                ioctl(fd, 0x550b, urbs[ep])
                result['discards'].append(dict(endpoint=ep, errno=0))
            except OSError as error:
                result['discards'].append(dict(endpoint=ep, errno=error.errno))
                if error.errno != errno.EINVAL:
                    raise
        end = time.monotonic()+2
        while pending and time.monotonic()<end:
            if not reap(cancel=True):
                time.sleep(.001)
        if pending:
            raise RuntimeError('Cancelled URBs not reaped')
        result['ended_monotonic_ns'] = time.monotonic_ns()
    return result


def discover_address(fd, endpoints, out):
    """Discover wire address passively: xHCI devaddr is NOT sysfs devnum.

    Only the selected IN endpoints are polled. Changing observer filters
    neither sends SET_ADDRESS nor accesses any other USB device.
    """
    script=['connect','h']
    for address in range(1,128):
        script += [f'w4 0xE900200C, 0x{(address<<8)|1:08X}', 'sleep 4',
                   f'w4 0xE900200C, 0x{(address<<8)|6:08X}', 'sleep 2',
                   'mem32 0xE9002048, 4']
    script += ['g','q']
    path=out/'address_scan.jlink';path.write_text('\n'.join(script)+'\n')
    stop=threading.Event();traffic={}
    def worker():
        try:traffic.update(poll(fd,endpoints,30,repeat=True,stop=stop))
        except BaseException as error:traffic['error']=str(error)
    thread=threading.Thread(target=worker)
    thread.start()
    try:
        process=subprocess.run(['JLinkExe','-SelectEmuBySN','506005083','-Device','A25',
            '-If','JTAG','-Speed','1000','-JTAGConf','-1,-1','-NoGui','1',
            '-CommanderScript',str(path)],capture_output=True,text=True,timeout=30)
        log=process.stdout+process.stderr
        (out/'address_scan.log').write_text(log)
        if process.returncode:
            raise RuntimeError('J-Link address scan failed')
    finally:
        stop.set();thread.join(timeout=4)
        if thread.is_alive():
            raise RuntimeError('Address scan USB worker still active')
        # This command always resumes the CPU, even after an interrupted scan.
        jlink(out,'address_scan_cleanup',6)
        (out/'address_scan_usb.json').write_text(json.dumps(traffic,indent=2)+'\n')
    rows=[]
    for match in re.finditer(r'^E9002048 = ([0-9A-F]{8}) ([0-9A-F]{8}) ([0-9A-F]{8}) ([0-9A-F]{8})',log,re.M):
        command,ticks,in2,in3=(int(v,16) for v in match.groups())
        if command&255==6:rows.append(dict(address=(command>>8)&127,ticks=ticks,in2=in2,in3=in3))
    matches=[row for row in rows if row['in2']+row['in3']]
    result=dict(rows=rows,matches=matches,poll=traffic)
    (out/'address_scan.json').write_text(json.dumps(result,indent=2)+'\n')
    if len(rows)!=127 or len(matches)!=1 or 'error' in traffic:
        raise RuntimeError('No unique observed wire address: '+str(matches))
    return matches[0]['address']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--endpoints', required=True, type=int, nargs='+', choices=[2,3])
    parser.add_argument('--seconds', type=float, default=1)
    parser.add_argument('--wire-address',type=int,help='actual on-wire USB address; otherwise discover by passive filtering')
    args = parser.parse_args()
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt('termination requested')
    signal.signal(signal.SIGTERM, interrupted)
    if not 1 <= args.seconds <= 10 or len(set(args.endpoints)) != len(args.endpoints):
        parser.error('seconds 1..10; no duplicate endpoints')
    if args.wire_address is not None and not 1<=args.wire_address<=127:
        parser.error('wire-address must be 1..127')
    device = console_snapshot()
    if not device or device['speed_mbps'] != 480 or device['configuration'] != '1':
        raise RuntimeError('Expected the configured HS480 console')
    path = Path('/sys/bus/usb/devices')/device['topology']
    ports = list((path/(path.name+':1.0')).glob('tty/ttyACM*'))
    if len(ports) != 1:
        raise RuntimeError('Expected one bound CDC port')
    owner = subprocess.run(['fuser', '/dev/'+ports[0].name], capture_output=True, text=True)
    if owner.returncode != 1 or owner.stdout.strip() or owner.stderr.strip():
        raise RuntimeError('CDC port may be in use: '+owner.stdout+owner.stderr)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = dict(device=device, status='started', cleanup_errors=[])
    claimed=[]
    detached=False
    try:
        # Verify the observer ID BEFORE any write to its MMIO page.
        result['probe'] = jlink(out, 'probe')
        node = '/dev/bus/usb/%03d/%03d' % (device['bus'], device['address'])
        with open(node, 'r+b', buffering=0) as fd:
            try:
                claim=struct.pack('II256s', 0, 1, b'cdc_acm')
                fcntl.ioctl(fd, 0x8000551b | (len(claim)<<16), claim)
                detached=True;claimed.append(0)
                fcntl.ioctl(fd, 0x8004550f, struct.pack('I', 1));claimed.append(1)
                wire_address=args.wire_address
                if wire_address is None:
                    wire_address=discover_address(fd.fileno(),args.endpoints,out)
                    result['probe']=jlink(out,'after_discovery')
                result['wire_address']=wire_address
                arm_command=(wire_address<<8)|1
                result['arm'] = jlink(out, 'arm', arm_command)
                if (result['arm']['sequence'] != (result['probe']['sequence']+1)&0xffffffff
                        or result['arm']['words'][2] != arm_command):
                    raise RuntimeError('Arm command not acknowledged exactly once')
                try:
                    result['poll'] = poll(fd.fileno(), args.endpoints, args.seconds)
                except Exception as error:
                    result['poll_error'] = str(error)
                # Retrieve the independent observation even if usbfs itself
                # failed. Stop the observer after capturing its pre-stop bank.
                result['snapshot'] = jlink(out, 'snapshot', 6)
                result['trace'] = decode(result['snapshot'])
                if (result['snapshot']['sequence'] != (result['arm']['sequence']+1)&0xffffffff
                        or result['snapshot']['words'][2] != 6
                        or not result['trace']['armed']
                        or result['trace']['address'] != wire_address):
                    raise RuntimeError('Snapshot command not acknowledged exactly once')
                if not result['trace']['in2'] and not result['trace']['in3']:
                    raise RuntimeError('No selected IN token observed; result is inconclusive')
                if console_snapshot() != device:
                    raise RuntimeError('Console identity/configuration changed during observation')
                result['status'] = 'captured_after_poll_error' if 'poll_error' in result else 'captured'
            finally:
                for interface in reversed(claimed):
                    try:fcntl.ioctl(fd, 0x80045510, struct.pack('I', interface))
                    except OSError as error:result['cleanup_errors'].append(str(error))
                driver=path/(path.name+':1.0')/'driver'
                # DISCONNECT_CLAIM can detach successfully, then fail to
                # claim. Restore the original driver in that case too.
                if detached or not driver.exists():
                    try:
                        request=DriverIoctl(0, 0x5517, None)
                        fcntl.ioctl(fd, 0xc0005512 | (ctypes.sizeof(request)<<16), bytearray(bytes(request)))
                    except OSError as error:result['cleanup_errors'].append(str(error))
                result['driver_after_cleanup']=driver.resolve().name if driver.exists() else None
                if result['driver_after_cleanup']!='cdc_acm':
                    result['cleanup_errors'].append('cdc_acm not rebound')
    except BaseException as error:
        result.update(status='error', error=str(error))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k in ('status','error','trace','poll','poll_error','cleanup_errors')},indent=2))
    return 0 if not result['cleanup_errors'] and 'poll_error' not in result else 1


if __name__ == '__main__':
    raise SystemExit(main())
