#!/usr/bin/env python3
"""One explicitly authorized experimental G22r0 SRAM load; no timing qualification."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import serial

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
from check_gpu_reloads import console_snapshot, target_busdev, wait_console, run
from load_ilm import identify_console, quiesce_console


def main():
    pack = ROOT/'TESTS/gpu_geometry_20261011/g22r0_trial_pack'
    record = json.loads((pack/'experiment.json').read_text())
    if record['stage'] != 'gpu_geometry_g22r0' or not record['experimental'] or record['timing_qualified']:
        raise RuntimeError('Wrong experiment record')
    stage = ROOT/'tang/impl'/record['stage']
    for name, digest in record['stage_files'].items():
        if hashlib.sha256((stage/name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Transported stage file mismatch: '+name)
    fs = stage/'impl/pnr/console_gpu_geometry_g22r0.fs'
    if hashlib.sha256(fs.read_bytes()).hexdigest() != record['bitstream_sha256']:
        raise RuntimeError('Bitstream mismatch')
    out = pack.parent/'board_g22r0_trial'
    out.mkdir(exist_ok=False)
    result = dict(status='running', scope='experimental_usb_and_gpu', timing_qualified=False,
                  experiment=record, sha256=record['bitstream_sha256'], runs=[])
    try:
        # Refuse mounted media and detach only this console's MSC interface.
        run(['python3', str(pack.parent/'detach_msc.py'), '--out', str(out/'msc_before.json')],
            out/'msc_before.log', 20)
        port, before = wait_console()
        with serial.Serial(port, 115200, timeout=.1, exclusive=True) as uart:
            identity, pause = identify_console(uart)
            (out/'identity_before.txt').write_bytes(identity)
            (out/'paused_before.txt').write_bytes(quiesce_console(uart, pause))
        attempt = dict(load=1, busdev=target_busdev(), target_serial='2023112818', usb_before=before,
                       load_started_unix=time.time(), status='loading')
        result['runs'].append(attempt)
        print('EXPERIMENTAL SRAM LOAD', attempt['busdev'], 'timing=-0.564 ns / 9 setup', flush=True)
        run([str(ROOT/'bin/openFPGALoader'), '--busdev-num', attempt['busdev'], '-b',
             'tangmega138k', '-m', str(fs)], out/'loader.log', 120)
        if not re.search(r'^DONE\s*$', (out/'loader.log').read_text(), re.M):
            raise RuntimeError('No FPGA DONE')
        port, after = wait_console(before)
        attempt.update(usb_after=after, fresh_enumeration=True, usb_speed_mbps=after['speed_mbps'],
                       port=port, load_completed_unix=time.time())
        if after['speed_mbps'] != 480:
            raise RuntimeError('Expected USB HS 480')
        print('Fresh USB HS enumeration:', after, flush=True)
        run(['python3', 'tools/check_usb_stress.py', '--rounds', '100', '--out', str(out/'usb')],
            out/'usb.log', 1530)
        attempt.update(status='pass', usb='pass', usb_rounds=100)
        print('USB 100 rounds PASS', flush=True)
        run(['python3', 'tools/check_gpu_console.py', '--wait', '20'], out/'gpu.log', 900)
        result['status'] = 'pass'
        print('Experimental functional USB/GPU PASS; timing remains FAIL', flush=True)
    except BaseException as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
