#!/usr/bin/env python3
"""Bounded Neo AE350 transport diagnosis; no target examination or CPU reset."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
FS = ROOT / 'tang/impl/console_neo_n56r10_gao_startup/impl/pnr/ao_0.fs'
SHA = '7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument('--dmstatus', action='store_true',
        help='Also send one read-only DMI request to DMSTATUS; no DMI write or reset')
    choice.add_argument('--dmcontrol', action='store_true',
        help='Instead read DMCONTROL; no DMCONTROL write is ever issued')
    parser.add_argument('--clear-sticky', action='store_true',
        help='After DMSTATUS, clear DTM sticky error only; never cancel the outstanding request')
    args = parser.parse_args()
    read_dm = args.dmstatus or args.dmcontrol
    if args.clear_sticky and not read_dm:
        parser.error('--clear-sticky requires --dmstatus or --dmcontrol')
    out = HERE / ('dmcontrol_01' if args.dmcontrol else
        'clear_sticky_01' if args.clear_sticky else 'dmstatus_01' if args.dmstatus else 'read_01')
    assert not out.exists(), 'Never overwrite a hardware observation'
    assert hashlib.sha256(FS.read_bytes()).hexdigest() == SHA
    with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = subprocess.run(['ps', '-C', 'openocd', '-C', 'openFPGALoader',
            '-C', 'gao_sh', '-C', 'gao_analyzer', '-C', 'jtagserver',
            '-o', 'pid=,comm='], capture_output=True, text=True)
        assert active.returncode == 1 and not active.stdout.strip(), active.stdout
        devices = []
        for p in Path('/sys/bus/usb/devices').iterdir():
            if not (p / 'idVendor').exists():
                continue
            item = {'path': str(p.resolve())}
            for key in ['idVendor', 'idProduct', 'product', 'serial', 'busnum', 'devnum', 'speed']:
                item[key] = (p / key).read_text().strip() if (p / key).exists() else None
            devices.append(item)
        esp = [d for d in devices if (d['idVendor'], d['idProduct'], d['product']) ==
               ('0403', '6010', 'Dual RS232-HS')]
        neo = [d for d in devices if (d['idVendor'], d['idProduct'], d['serial']) ==
               ('0403', '6010', '2025041420')]
        assert len(esp) == len(neo) == 1, (esp, neo)
        assert esp[0]['path'].endswith('/3-4.4.2'), esp
        assert neo[0]['path'].endswith('/3-4.4.1'), neo
        out.mkdir()
        report = {'expected_loaded_fs_sha256': SHA,
            'identity_basis': 'Recorded R10 programming, not SRAM readback',
            'usb': devices, 'cpu_halt_requested': False, 'cpu_reset_requested': False,
            'fpga_programmed': False, 'dmi_request_sent': read_dm,
            'dmi_address': 0x10 if args.dmcontrol else 0x11 if args.dmstatus else None,
            'dmi_operation': 'READ' if read_dm else None,
            'transport_tap_initialized': True, 'dtmcs_write_values': [0, 0x10000] if args.clear_sticky else [0],
            'dtmhardreset_requested': False,
            'started_unix': time.time()}
        cfg = '''adapter driver ftdi
ftdi vid_pid 0x0403 0x6010
ftdi channel 0
ftdi layout_init 0x0008 0xf00b
ftdi device_desc "Dual RS232-HS"
transport select jtag
adapter speed 100
gdb_port disabled
tcl_port disabled
telnet_port disabled
jtag newtap neo cpu -irlen 5 -expected-id 0x1000563d
init
foreach speed {100 1000 100} {
    adapter speed $speed
    irscan neo.cpu 0x01
    set ident [drscan neo.cpu 32 0]
    if {$ident ne "1000563d"} {error "Unexpected AE350 IDCODE: $ident"}
    echo "TRANSPORT_ID speed_khz=$speed raw=$ident"
    irscan neo.cpu 0x10
    for {set i 0} {$i < 4} {incr i} {
        runtest 1000
        set raw [drscan neo.cpu 32 0]
        echo "TRANSPORT_DTMCS speed_khz=$speed index=$i raw=$raw"
    }
}
'''
        if read_dm:
            cfg += '''
adapter speed 100
irscan neo.cpu 0x10
set ready [drscan neo.cpu 32 0]
if {$ready ne "00007071"} {error "DTM state differs from reviewed first read: $ready"}
# DMI address 0x11 (DMSTATUS), 32 zero data bits, op=1 (READ).
# 41 bits = 7 address + 32 data + 2 operation. No op=2 writes.
irscan neo.cpu 0x11
echo "DMSTATUS_REQUEST [drscan neo.cpu 41 0x4400000001]"
foreach idle_cycles {1000 10000 100000} {
    runtest $idle_cycles
    echo "DMSTATUS_RESPONSE idle_cycles=$idle_cycles raw=[drscan neo.cpu 41 0]"
}
irscan neo.cpu 0x10
echo "DTMCS_AFTER_READ [drscan neo.cpu 32 0]"
'''
        if args.clear_sticky:
            cfg += '''
# DMIRESET only clears sticky status; unlike DTMHARDRESET it does not
# cancel an outstanding DMI request. No DMCONTROL write is performed.
for {set i 0} {$i < 2} {incr i} {
    runtest 100000
    irscan neo.cpu 0x10
    echo "STICKY_CLEAR_BEFORE index=$i raw=[drscan neo.cpu 32 0x10000]"
    runtest 1000
    echo "STICKY_CLEAR_AFTER index=$i raw=[drscan neo.cpu 32 0]"
    irscan neo.cpu 0x11
    runtest 1000
    echo "DMSTATUS_AFTER_CLEAR index=$i raw=[drscan neo.cpu 41 0]"
    irscan neo.cpu 0x10
    echo "DTMCS_AFTER_NOP index=$i raw=[drscan neo.cpu 32 0]"
}
'''
        if args.dmcontrol:
            cfg = cfg.replace('DMSTATUS', 'DMCONTROL').replace('0x4400000001', '0x4000000001')
            cfg = cfg.replace('address 0x11 (DMCONTROL)', 'address 0x10 (DMCONTROL)')
        cfg += 'shutdown\n'
        path = out / 'read.tcl'
        path.write_text(cfg)
        with (out / 'openocd.log').open('w') as log:
            child = subprocess.Popen(['/usr/local/bin/openocd', '-f', str(path)],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                report['returncode'] = child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                report['timed_out'] = True
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                report['returncode'] = child.returncode
        report['finished_unix'] = time.time()
        report['script_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        report['log_sha256'] = hashlib.sha256((out / 'openocd.log').read_bytes()).hexdigest()
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print((out / 'openocd.log').read_text())
        if report['returncode']:
            raise SystemExit(report['returncode'])


if __name__ == '__main__':
    main()
