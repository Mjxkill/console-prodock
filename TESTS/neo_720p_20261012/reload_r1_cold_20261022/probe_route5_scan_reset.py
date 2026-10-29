#!/usr/bin/env python3
"""Neo-only SRAM trial of the reviewed route5 reset experiment.

Consumes the stopped route2 reset-reload anchor once. Never starts Linux,
writes SD/flash, or accesses Pro Dock. Negative recovery/removal/hold timing
is rejected by the normal loader checks; this script has no reset waiver.
"""
import argparse
import fcntl
import json
from pathlib import Path
import re
import struct
import subprocess
import time

import probe_scan_observer as probe

BUILD = probe.ROOT / 'tang/impl/console_neo_n56r9_route5_c155'
ANCHOR = probe.HERE / 'r9_route2_reset_reloads'
CONSUMED = ANCHOR / 'route5_consumed.json'


def fresh(path):
    record = json.loads(path.read_text())
    for name, expected in record.get('sha256', {}).items():
        probe.require(probe.sha(Path(name)) == expected, 'Stale proof: ' + name)
    return record


def preflight(bit_sha):
    probe.require(bool(re.fullmatch('[a-f0-9]{64}', bit_sha)), 'Exact bitstream SHA required')
    probe.require(bit_sha == 'b85a1a41e22e1b9a0b24be45a5c18cdce9d84a996305238c4ceb933415a854ea',
                  'Only the reviewed route5 diagnostic is allowed')
    q = json.loads((BUILD / 'qualification.json').read_text())
    probe.require(q['bitstream_sha256'] == bit_sha, 'Wrong candidate SHA')
    q, bit = probe.check_fpga(BUILD, bit_sha if q['status'] == 'FAIL' else None)
    comparison = fresh(BUILD / 'scan_reset_route_comparison.json')
    probe.require(comparison['passed'] is True and comparison['bitstream_sha256'] == bit_sha,
                  'Reset distribution comparison has unresolved changes')
    probe.require(comparison['scope'] == 'Structural review permitting only stopped-CPU reset/RGB observation'
                  and comparison['qualification_status'] == 'FAIL'
                  and comparison['reset_stages_unchanged'] is True,
                  'Not the reviewed route5 diagnostic scope')
    strict = fresh(BUILD / 'scan_observer_audit.json')
    if not strict['passed']:
        proof = fresh(BUILD / 'scan_observer_reset_alias_proof.json')
        probe.require(strict['errors'] == ['Observer register function/clock/reset/init changed after synthesis']
                      and proof['passed'] is True and proof['all_other_register_fields_identical'] is True
                      and proof['reset_function'] == '!vid_hrstn'
                      and proof['reset_alias_count'] == dict(CLEAR=2, RESET=372)
                      and proof['original_fail_preserved'] == str(BUILD / 'scan_observer_audit.json')
                      and proof['controls'] == strict['controls'] and not proof['global_scanout_ce'],
                      'Observer reset alias proof requires independent review')
    probe.require(probe.sha(BUILD / 'console_neo.vg') == probe.NETSHA, 'Changed netlist')
    actual = {str(p.relative_to(BUILD / 'source')): probe.sha(p)
              for p in (BUILD / 'source').rglob('*') if p.is_file()}
    probe.require(actual == json.loads((BUILD / 'sources.json').read_text()), 'Changed frozen sources')
    prior = json.loads((ANCHOR / 'result.json').read_text())
    probe.require(prior['complete'] and prior['cpu_left_halted'] and not prior['sd_written']
                  and not prior['flash_written'] and prior['bitstream_sha256'] == probe.ROUTE2SHA
                  and len(prior['rounds']) == 2 and not CONSUMED.exists(),
                  'Stopped route2 anchor missing or consumed')
    probe.require(probe.sha(probe.HERE / 'repeat_route2_reset.py') == prior['script_sha256'],
                  'Anchor script changed')
    for entry in prior['rounds']:
        probe.require(entry['internal_bars_selected'] and entry['program_status']['done']
                      and not entry['program_status']['error_flags'], 'Incomplete previous reload')
        for sample in entry['snapshots'].values():
            probe.require(sample['raw_words'] == [1, 0, 79, 0, 0, 0, 0, 0x53434e15],
                          'Previous reset state differs')
    frame = probe.HERE / 'r8_rgb_only/framebuffer.bin'
    probe.require(probe.sha(frame) == probe.FRAMESHA and frame.stat().st_size == 1843200,
                  'Reference framebuffer changed')
    expected = sum(struct.unpack('<460800I', frame.read_bytes())) & 0xffffffff
    return q, bit, frame, expected


def samples(log):
    return {name: probe.decode([int(w, 0) for w in words.split()])
            for name, words in re.findall(r'^SNAP_(\w+) (.+)$', log, re.M)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bitstream-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    q, bit, frame, expected = preflight(args.bitstream_sha256)
    if args.check_only:
        print(json.dumps(dict(passed=True, hardware_access=False, qualification_status=q['status'],
                              timing_checks_ns=q['timing_checks_ns'], expected_fetch_sum=expected)))
        return 0
    out = args.out.resolve()
    probe.require(out.is_relative_to(probe.HERE) and not any(c in str(out) for c in '{}\\\n\r'),
                  'Invalid trial output path')
    out.mkdir(exist_ok=False)
    report = dict(passed=False, functional_passed=False, trial_completed=False, cpu_left_halted=False,
                  sd_written=False, flash_written=False, linux_started=False,
                  fpga_reloaded=False, bitstream_sha256=args.bitstream_sha256,
                  previous_bitstream_sha256=probe.ROUTE2SHA, qualification_status=q['status'],
                  timing_checks_ns=q['timing_checks_ns'], framebuffer_sha256=probe.FRAMESHA,
                  expected_fetch_sum=expected, script_sha256=probe.sha(Path(__file__)),
                  helpers_sha256=probe.sha(Path(probe.__file__)),
                  review_sha256=probe.sha(BUILD / 'scan_reset_route_comparison.json'),
                  build=str(BUILD),
                  anchor_sha256=probe.sha(ANCHOR / 'result.json'),
                  anchor_log_sha256=probe.sha(ANCHOR / 'reload_1.log'))

    def observe(name, code, timeout=120):
        script = out / (name + '.tcl')
        script.write_text(code)
        logfile = out / (name + '.log')
        try:
            with logfile.open('x') as log:
                subprocess.run(['/usr/local/bin/openocd', '-f',
                                str(probe.ROOT / 'tools/neo/ae350_espprog.cfg'),
                                '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled',
                                '-f', str(script)], stdout=log, stderr=log, check=True, timeout=timeout)
        finally:
            if logfile.exists():
                report['cpu_left_halted'] = 'CPU_HALTED' in logfile.read_text()
        return logfile.read_text()

    try:
        devices = [d for d in Path('/sys/bus/usb/devices').iterdir()
                   if (d / 'serial').exists() and (d / 'serial').read_text().strip() == '2025041420']
        probe.require(len(devices) == 1, 'Neo programmer not uniquely identified')
        device = devices[0]
        probe.require((device / 'idVendor').read_text().strip() == '0403'
                      and (device / 'idProduct').read_text().strip() == '6010', 'Wrong programmer')
        busdev = ':'.join((device / n).read_text().strip() for n in ('busnum', 'devnum'))
        report['programmer_busdev'] = busdev
        with (probe.ROOT / 'TESTS/neo_board.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # Check the one-shot marker again under the hardware lock.
            probe.require(not CONSUMED.exists(), 'Anchor consumed while preparing trial')
            guarded = observe('guard', probe.GUARD + probe.SNAPSHOT + '''
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Recorded route2 bars state changed"}
snapshot GUARD
shutdown
''', 30)
            prior_sample = samples(guarded)['GUARD']
            probe.require(prior_sample['raw_words'] == [1, 0, 79, 0, 0, 0, 0, 0x53434e15],
                          'Live route2 reset state changed')
            with CONSUMED.open('x') as marker:
                json.dump(dict(out=str(out), bitstream_sha256=args.bitstream_sha256,
                               time=time.time()), marker)
            report['cpu_left_halted'] = False
            with (out / 'program.log').open('x') as log:
                subprocess.run([str(Path.home() / '.local/bin/openFPGALoader'), '--busdev-num', busdev,
                                '-b', 'tangconsole', '-m', '--verbose', '--freq', '6000000', str(bit)],
                               stdout=log, stderr=log, timeout=120, check=True)
            report['program_status'] = probe.check_program_status((out / 'program.log').read_text())
            report['fpga_reloaded'] = True
            reset_log = observe('reset', probe.GUARD + probe.SNAPSHOT + '''
sleep 100
snapshot START
sleep 1000
snapshot LATER
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display not reset"}
echo ROUTE5_RESET_OBSERVED
shutdown
''', 30)
            report['reset_snapshots'] = samples(reset_log)
            report['reset_released'] = all(s['flags']['mrst0'] and s['flags']['mrst1']
                                           for s in report['reset_snapshots'].values())
            probe.require(set(report['reset_snapshots']) == {'START', 'LATER'}, 'Missing reset observations')
            if not report['reset_released']:
                report['trial_completed'] = True
                report['display_left'] = 'internal bars mode; no visual confirmation'
                raise RuntimeError('Scanout reset remains asserted; no framebuffer payload written')
            code = 'riscv expose_csrs 1994,1996,2000\n' + probe.GUARD + '''
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
''' + probe.SNAPSHOT
            code += f'load_image {{{frame}}} 0x01700000 bin\nverify_image {{{frame}}} 0x01700000 bin\necho FRAME_VERIFIED\n'
            code += '''write_memory 0xe9000004 32 {0x01700000}
write_memory 0xe900006c 32 {2560}
write_memory 0xe9000030 32 {0}
write_memory 0xe9000040 32 {0}
write_memory 0xe9000008 32 {3}
write_memory 0xe900000c 32 {1}
sleep 200
snapshot RGB0
sleep 1000
snapshot RGB1
echo ROUTE5_RGB_TRIAL_COMPLETE
shutdown
'''
            log = observe('rgb', code)
            report['snapshots'] = samples(log)
            before, after = (report['snapshots'][n] for n in ('RGB0', 'RGB1'))
            report['traffic_delta'] = {k: (after[k] - before[k]) & 0xffffffff
                                       for k in ('accepted_by_queue', 'accepted_by_arbiter', 'returned')}
            scan = {n: [int(w, 0) for w in words.split()]
                    for n, words in re.findall(r'^SCAN_(\w+) (.+)$', log, re.M)}
            first, last = scan['RGB0'], scan['RGB1']
            probe.require(len(first) == len(last) == 32, 'Incomplete scanout registers')
            report['scanout_registers'] = scan
            for key, index in (('frame_delta', 6), ('fetch_frame_delta', 9), ('underflow_delta', 7)):
                report[key] = (last[index] - first[index]) & 0xffffffff
            report['trial_completed'] = 'ROUTE5_RGB_TRIAL_COMPLETE' in log and 'FRAME_VERIFIED' in log
            report['functional_passed'] = bool(report['trial_completed'] and report['frame_delta'] > 0
                                              and report['fetch_frame_delta'] > 0
                                              and report['underflow_delta'] == 0 and last[3] == 0
                                              and last[5] == 1 and last[8] == expected)
            report['display_left'] = 'RGB565 diagnostic selected; visual confirmation pending'
    except Exception as error:
        report['error'] = str(error)
    finally:
        report['passed'] = report['functional_passed']
        report['scope'] = 'Stopped-CPU scanout reset/RGB test only; qualification_status remains separate.'
        report['limits'] = ('Stopped-CPU diagnostic, not Linux or a timing qualification. '
                            'Arbiter counter measures accepted enqueues, not native DDR commands. '
                            'Programmer DONE is not SRAM readback verification.')
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2), flush=True)
    return 0 if report['functional_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
