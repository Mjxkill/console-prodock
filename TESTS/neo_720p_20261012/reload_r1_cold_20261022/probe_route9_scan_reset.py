#!/usr/bin/env python3
"""User-requested trial of one exact R9 SHA, parked CPU and scanout only.

This isolated case retains the negative setup/recovery and reset4-LW findings.
It does not alter the normal loader, its mutually exclusive diagnostics, or
any qualification. No accelerator commands, CPU resume, Linux, SD or flash.
On failure after programming starts, restore the already visible N56r8 bars.
"""
import argparse
import fcntl
import json
from pathlib import Path
import re
import signal
import struct
import subprocess
import time

import probe_scan_observer as p

BUILD = p.ROOT/'tang/impl/console_neo_n56r9_route9_dma_c150'
BIT_SHA = '1593a2aaf7d84e5d099520d96b5d60852340601fd861d2c21108bace846e2fde'
TIMING_SHA = '8615fb10bf487512a859e2bfa0566d636644d5ce3b40025f46df5bb52af92b72'
ANCHOR = p.HERE/'r8_restored_after_route5'
CONSUMED = ANCHOR/'route9_consumed.json'
REVIEW = BUILD/'scan_reset_route9_trial_review.json'
REVIEW_SHA = '095335436255b2bd9f808bb0e891f59afe723f248c644a97ca45949d8ee7a47c'
TIMING = dict(setup=-.849, hold=.124, recovery=-.360, removal=.196)


def fresh(path, field='input_sha256'):
    record = json.loads(path.read_text())
    p.require(bool(record.get(field)), 'Missing proof inputs: '+str(path))
    for name, digest in record[field].items():
        p.require(p.sha(Path(name)) == digest, 'Changed proof input: '+name)
    return record


def preflight(bit_sha):
    p.require(bit_sha == BIT_SHA, 'Only the user-requested R9 SHA is allowed')
    q = json.loads((BUILD/'qualification.json').read_text())
    bit = BUILD/'impl/pnr/console_neo.fs'
    p.require(p.sha(bit) == q['bitstream_sha256'] == BIT_SHA, 'Bitstream changed')
    p.require(p.sha(BUILD/'impl/pnr/console_neo.tr') == q['timing_sha256'] == TIMING_SHA, 'Timing changed')
    p.require(q['status'] == 'FAIL' and q['timing_checks_ns'] == TIMING and
              q['violated_endpoints'] == dict(setup=64, hold=0) and
              q['minimum_pulse_slack_ns'] >= 0, 'Different timing failure')
    audits = q['synthesis_audits']
    p.require(set(n for n, a in audits.items() if a.get('passed') is not True) == {'gpu_reset_tree'},
              'Unreviewed synthesis finding')
    p.require(audits['gpu_reset_tree']['errors'] == ['Reset 4 still uses a global routing resource'],
              'Different reset-route finding')
    p.require(audits['gpu_owner_replication']['netlist_sha256'] == p.sha(BUILD/'impl/pnr/console_neo.vo'),
              'Post-route owner proof changed')
    p.require(p.sha(BUILD/'console_neo.vg') == p.NETSHA, 'Changed synthesized logic')
    p.require(p.sha(BUILD/'sources.json') == q['sources_sha256'], 'Source manifest changed')
    p.require(json.loads((BUILD/'sources.json').read_text()) ==
              {str(f.relative_to(BUILD/'source')):p.sha(f) for f in (BUILD/'source').rglob('*') if f.is_file()},
              'Frozen source changed')
    for name, digest in q['constraints_sha256'].items():
        p.require(p.sha(BUILD/'source/tang/boards/neo'/name) == digest, 'Constraint changed')
    p.require(q['ddr_profile']['passed'] and q['ddr_profile']['variant'] == 'neo-fifo-registers' and
              q['clock_mhz']['ddr3_mem_clk'] == 300.03 and q['clock_mhz']['core_clk'] == 800,
              'DDR or core profile changed')
    p.require(p.sha(REVIEW) == REVIEW_SHA, 'Independent review changed')
    review = fresh(REVIEW)
    p.require(review['passed'] and review['bitstream_sha256'] == BIT_SHA and
              review['qualification_status'] == 'FAIL' and review['reset_stages_unchanged'] and
              review['scope'] == 'Stopped-CPU scanout reset/RGB diagnostic only', 'Review scope differs')
    alias = fresh(BUILD/'scan_observer_reset_alias_proof.json', 'sha256')
    strict = fresh(BUILD/'scan_observer_audit.json', 'sha256')
    p.require(not strict['passed'] and
              strict['errors'] == ['Observer register function/clock/reset/init changed after synthesis'],
              'Observer audit changed')
    p.require(alias['passed'] and alias['all_other_register_fields_identical'] and
              alias['reset_function'] == '!vid_hrstn' and alias['reset_alias_count'] == dict(CLEAR=2, RESET=372)
              and alias['controls'] == strict['controls'] and not alias['global_scanout_ce'],
              'Observer alias differs')
    previous = json.loads((ANCHOR/'result.json').read_text())
    p.require(previous['passed'] and previous['complete'] and previous['bitstream_sha256'] == p.R8SHA and
              previous['cpu_left_halted'] and not previous['linux_running'] and
              not previous['sd_written'] and not previous['flash_written'], 'Missing stopped fallback anchor')
    p.require('R8_BARS_RESTORED' in (ANCHOR/'after.log').read_text(), 'Incomplete fallback evidence')
    p.require(not CONSUMED.exists(), 'Fallback anchor already consumed')
    fallback_q, fallback = p.check_fpga(p.ROOT/'tang/impl/console_neo_n56r8_hdmi_sg4', p.R8SHA)
    frame = p.HERE/'r8_rgb_only/framebuffer.bin'
    p.require(p.sha(frame) == p.FRAMESHA and frame.stat().st_size == 1843200, 'Frame changed')
    expected = sum(struct.unpack('<460800I', frame.read_bytes())) & 0xffffffff
    return q, bit, fallback, frame, expected


def snapshots(log):
    return {name:p.decode([int(w, 0) for w in words.split()])
            for name, words in re.findall(r'^SNAP_(\w+) (.+)$', log, re.M)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bitstream-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    q, bit, fallback, frame, expected = preflight(args.bitstream_sha256)
    if args.check_only:
        print(json.dumps(dict(passed=True, hardware_access=False, bitstream_sha256=BIT_SHA,
                             qualification_status='FAIL', timing_checks_ns=TIMING,
                             reset4_LW_finding_preserved=True)))
        return 0
    out = args.out.resolve()
    p.require(out.is_relative_to(p.HERE) and not any(c in str(out) for c in '{}\\\n\r'), 'Bad output path')
    out.mkdir(exist_ok=False)
    report = dict(passed=False, trial_completed=False, functional_passed=False, cpu_left_halted=False,
                  bitstream_sha256=BIT_SHA, qualification_status='FAIL', timing_checks_ns=TIMING,
                  reset4_LW_finding_preserved=True, sd_written=False, flash_written=False, linux_started=False,
                  script_sha256=p.sha(Path(__file__)), review_sha256=p.sha(REVIEW),
                  helper_sha256=p.sha(Path(p.__file__)), anchor_sha256=p.sha(ANCHOR/'result.json'),
                  scope='Stopped-CPU scanout reset/RGB diagnostic only', build=str(BUILD))

    def observe(name, code, timeout=30):
        script = out/(name+'.tcl'); script.write_text(code)
        logfile = out/(name+'.log')
        try:
            with logfile.open('x') as log:
                subprocess.run(['/usr/local/bin/openocd', '-f', str(p.ROOT/'tools/neo/ae350_espprog.cfg'),
                    '-c', 'gdb_port disabled; tcl_port disabled; telnet_port disabled', '-f', str(script)],
                    stdout=log, stderr=log, check=True, timeout=timeout)
        finally:
            if logfile.exists(): report['cpu_left_halted'] = 'CPU_HALTED' in logfile.read_text()
        return logfile.read_text()

    def programmer():
        devices = [d for d in Path('/sys/bus/usb/devices').iterdir()
                   if (d/'serial').exists() and (d/'serial').read_text().strip() == '2025041420']
        p.require(len(devices) == 1, 'Neo programmer identity missing/ambiguous')
        d = devices[0]
        p.require((d/'idVendor').read_text().strip() == '0403' and
                  (d/'idProduct').read_text().strip() == '6010', 'Wrong programmer')
        probes = [d for d in Path('/sys/bus/usb/devices').iterdir()
                  if (d/'product').exists() and (d/'product').read_text().strip() == 'Dual RS232-HS']
        p.require(len(probes) == 1, 'CPU JTAG identity ambiguous')
        return ':'.join((d/n).read_text().strip() for n in ('busnum', 'devnum'))

    def program(name, path, digest):
        p.require(p.sha(path) == digest, 'Programming payload changed')
        busdev = programmer(); report['programmer_busdev'] = busdev
        with (out/(name+'.log')).open('x') as log:
            subprocess.run([str(Path.home()/'.local/bin/openFPGALoader'), '--busdev-num', busdev,
                '-b', 'tangconsole', '-m', '--verbose', '--freq', '6000000', str(path)],
                stdout=log, stderr=log, check=True, timeout=120)
        report[name+'_status'] = p.check_program_status((out/(name+'.log')).read_text())

    def interrupted(signum, frame): raise KeyboardInterrupt('Signal '+str(signum))
    signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGHUP, interrupted)
    try:
        programmer()
        with (p.ROOT/'TESTS/neo_board.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            preflight(BIT_SHA)
            attempted = False
            try:
                guard = observe('guard', p.GUARD+'''
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Fallback bars state changed"}
echo R8_PARKING_CONFIRMED
shutdown
''')
                p.require('R8_PARKING_CONFIRMED' in guard, 'Live anchor guard missing')
                with CONSUMED.open('x') as marker:
                    json.dump(dict(bitstream_sha256=BIT_SHA, out=str(out), time=time.time()), marker)
                attempted = True; report['cpu_left_halted'] = False
                print('Programming exact R9 on Neo SRAM', flush=True)
                program('program', bit, BIT_SHA)
                report['fpga_reloaded'] = True
                log = observe('reset', p.GUARD+p.SNAPSHOT+'''
sleep 100
snapshot START
sleep 1000
snapshot LATER
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0} {error "Display not reset"}
shutdown
''')
                report['reset_snapshots'] = snapshots(log)
                p.require(set(report['reset_snapshots']) == {'START', 'LATER'}, 'Missing reset samples')
                report['reset_released'] = all(s['flags']['mrst0'] and s['flags']['mrst1']
                                               for s in report['reset_snapshots'].values())
                p.require(report['reset_released'], 'Scanout reset remains asserted; no framebuffer write')
                code = 'riscv expose_csrs 1994,1996,2000\n'+p.GUARD+'''
reg mstatus 0
reg mie 0
reg csr1996 6
reg csr1994 0
'''+p.SNAPSHOT
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
echo R9_RGB_COMPLETE
shutdown
'''
                log = observe('rgb', code, 120)
                report['snapshots'] = snapshots(log)
                registers = {name:[int(w, 0) for w in words.split()]
                             for name, words in re.findall(r'^SCAN_(\w+) (.+)$', log, re.M)}
                first, last = registers['RGB0'], registers['RGB1']
                p.require(len(first) == len(last) == 32, 'Incomplete scanout registers')
                report['scanout_registers'] = registers
                for key, index in [('frame_delta', 6), ('fetch_frame_delta', 9), ('underflow_delta', 7)]:
                    report[key] = (last[index]-first[index]) & 0xffffffff
                before, after = (report['snapshots'][s] for s in ('RGB0', 'RGB1'))
                report['traffic_delta'] = {k:(after[k]-before[k]) & 0xffffffff
                    for k in ['accepted_by_queue', 'accepted_by_arbiter', 'returned']}
                report['trial_completed'] = 'R9_RGB_COMPLETE' in log and 'FRAME_VERIFIED' in log
                report['functional_passed'] = bool(report['trial_completed'] and report['frame_delta'] > 0 and
                    report['fetch_frame_delta'] > 0 and report['underflow_delta'] == 0 and
                    last[3] == 0 and last[5] == 1 and last[8] == expected)
                p.require(report['functional_passed'], 'RGB scanout check failed')
                report['passed'] = True; report['display_left'] = 'R9 RGB565, visual confirmation pending'
            except BaseException as error:
                report['error'] = repr(error)
                if attempted:
                    print('Diagnostic failed; restoring verified N56r8 bars', flush=True)
                    try:
                        program('restore', fallback, p.R8SHA)
                        log = observe('restored', p.GUARD+'''
sleep 100
echo "FALLBACK_0 [read_memory 0xe9000000 32 32]"
sleep 1000
echo "FALLBACK_1 [read_memory 0xe9000000 32 32]"
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Fallback differs"}
echo R8_BARS_RESTORED
shutdown
''')
                        values = {name:[int(w, 0) for w in words.split()]
                                  for name, words in re.findall(r'^FALLBACK_(\d) (.+)$', log, re.M)}
                        p.require(set(values) == {'0', '1'} and all(len(v) == 32 for v in values.values()),
                                  'Incomplete fallback samples')
                        report['fallback_frame_delta'] = (values['1'][6]-values['0'][6]) & 0xffffffff
                        p.require(report['fallback_frame_delta'] > 0 and
                                  all(v[2] == 0 and v[3] == 0 and v[24] == 0x1ff8f800 for v in values.values()) and
                                  'R8_BARS_RESTORED' in log, 'Fallback clock/configuration/checksum mismatch')
                        report['fallback_registers'] = values
                        report['fallback_restored'] = True
                        report['display_left'] = 'N56r8 internal bars, parked CPU'
                    except BaseException as cleanup: report['cleanup_error'] = repr(cleanup)
                raise
    except BaseException as error:
        report.setdefault('error', repr(error))
    finally:
        report['limits'] = ['STA and reset4-LW remain FAIL; no Linux or full GPU qualification.',
                            'Observer counters include reported setup violations; corroborate with scanout counters.',
                            'DONE is programmer status, not SRAM readback. No CPU resume was requested.']
        (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
