#!/usr/bin/env python3
"""User-requested, exact-SHA N56r10 SRAM observation; qualification stays FAIL.

Do not boot Linux, touch DDR/GPU data, SD or flash. Photograph before probing
the hard CPU. A CPU timeout is an observation and leaves the requested R10
configured. A programming error/interruption restores the checked R8 fallback.
"""
import argparse
import fcntl
import json
from pathlib import Path
import re
import signal
import subprocess
import time

import probe_route9_led_compare as old

p = old.p
HERE, ROOT = p.HERE, p.ROOT
BUILD = ROOT / 'tang/impl/console_neo_n56r10_gao_startup'
BIT_SHA = '7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28'
QUAL = HERE / 'gao_parser_fix/qualification_after_parser.json'
QUAL_SHA = '5e35d051311d3605729327b484a15636755af3c024e59a170de17070e7711dc3'
TIMING = dict(setup=-0.849, hold=-0.384, recovery=-0.364, removal=0.196)


def preflight():
    p.require(p.sha(QUAL) == QUAL_SHA, 'Reviewed qualification changed')
    q = json.loads(QUAL.read_text())
    bit = BUILD / 'impl/pnr/ao_0.fs'
    p.require(p.sha(bit) == q['bitstream_sha256'] == BIT_SHA, 'R10 payload changed')
    p.require(q['status'] == 'FAIL' and q['timing_checks_ns'] == TIMING and
              q['violated_endpoints'] == dict(setup=64, hold=13) and
              q['minimum_pulse_slack_ns'] == 1.375, 'Different diagnostic timing')
    p.require(p.sha(BUILD / 'impl/pnr/console_neo.tr') == q['timing_sha256'], 'Timing report changed')
    p.require(p.sha(BUILD / 'sources.json') == q['sources_sha256'], 'Source manifest changed')
    sources = json.loads((BUILD / 'sources.json').read_text())
    p.require(sources == {str(f.relative_to(BUILD / 'source')): p.sha(f)
                         for f in (BUILD / 'source').rglob('*') if f.is_file()}, 'Frozen source changed')
    for name, digest in q['constraints_sha256'].items():
        p.require(p.sha(BUILD / 'source/tang/boards/neo' / name) == digest, 'Constraint changed')
    p.require(p.sha(BUILD / 'console_neo.vg') == p.NETSHA, 'Application netlist changed')
    audits = q['synthesis_audits']
    p.require({n for n, a in audits.items() if a.get('passed') is not True} == {'gpu_reset_tree'} and
              audits['gpu_reset_tree']['errors'] == ['Reset 4 still uses a global routing resource'],
              'Different structural failure')
    p.require(audits['gpu_owner_replication']['netlist_sha256'] == p.sha(BUILD / 'impl/pnr/console_neo.vo'),
              'Routed netlist changed')
    p.require(q['ddr_profile']['passed'] and q['ddr_profile']['variant'] == 'neo-fifo-registers' and
              q['clock_mhz']['ddr3_mem_clk'] == 300.03 and q['clock_mhz']['core_clk'] == 800,
              'Different DDR/core profile')
    _, fallback = p.check_fpga(old.FALLBACK, p.R8SHA)
    return bit, fallback, q, old.led_proof(BUILD)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    bit, fallback, q, led = preflight()
    out = args.out.resolve()
    p.require(out.is_relative_to(HERE) and not out.exists(), 'Use a new local evidence directory')
    if args.check_only:
        print(json.dumps(dict(passed=True, hardware_access=False, bitstream_sha256=BIT_SHA,
                              qualification_status=q['status'], timing=TIMING)))
        return
    out.mkdir()
    report = dict(bitstream_sha256=BIT_SHA, build=str(BUILD), qualification_status='FAIL',
                  timing=TIMING, qualification_sha256=QUAL_SHA, led_proof=led,
                  authorization='User: alors charge la N56r10',
                  script_sha256=p.sha(Path(__file__)), linux_started=False,
                  sd_written=False, flash_written=False, ddr_written=False,
                  gao_capture_attempted=False, programming_attempted=False,
                  fallback_restored=False, complete=False)
    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Interrupted: ' + str(signum))
    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(signum, interrupted)
    with (ROOT / 'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = subprocess.run(['ps', '-C', 'jtagserver', '-C', 'gao_analyzer', '-C', 'gao_sh',
            '-C', 'openocd', '-C', 'openFPGALoader', '-o', 'pid=,args='], capture_output=True, text=True)
        p.require(active.returncode == 1 and not active.stdout.strip(), 'Existing Neo hardware operator')
        report['usb_identity'] = old.usb_identity()
        hw = old.Hardware(out, report)
        save()
        try:
            guard = hw.observe('guard_r8', old.GUARD)
            p.require('CPU_HALTED' in guard and 'R8_PARKING_CONFIRMED' in guard,
                      'Live R8 parking guard absent')
            report['programming_attempted'] = True; save()
            hw.program('program_r10', bit, BIT_SHA)
            report['configured'] = True; save()
            print('N56R10_CONFIGURED ' + BIT_SHA, flush=True)
            try:
                old.run_child(['/usr/bin/ffmpeg', '-hide_banner', '-loglevel', 'warning',
                    '-f', 'v4l2', '-input_format', 'mjpeg', '-video_size', '1920x1080',
                    '-i', '/dev/video0', '-vf', 'select=gte(n\\,15)', '-frames:v', '1',
                    '-update', '1', '-n', str(out / 'camera_before_dmi.jpg')], out / 'camera.log', 15)
                report['camera_before_dmi_sha256'] = p.sha(out / 'camera_before_dmi.jpg')
            except Exception as error:
                report['camera_error'] = repr(error)
            save()
            result = dict(attempted=True, timeout_seconds=30, gpu_or_ddr_access=False)
            try:
                log = hw.observe('r10_dmi', old.DMI_AFTER_LED)
            except Exception as error:
                result['error'] = repr(error)
                result['timed_out'] = isinstance(error, subprocess.TimeoutExpired)
            path = out / 'r10_dmi.log'
            log = path.read_text() if path.exists() else ''
            result['cpu_halted'] = bool(re.search(r'^LED_DMI_CPU_HALTED\r?$', log, re.M))
            pc = re.search(r'^pc(?:\s+\([^)]*\))?:\s*(0x[0-9a-fA-F]+)\s*$', log, re.M)
            if pc: result['pc'] = int(pc[1], 16)
            result['complete'] = bool(not result.get('error') and result['cpu_halted'] and pc and
                                      re.search(r'^LED_DMI_COMPLETE\r?$', log, re.M))
            if path.exists(): result['log_sha256'] = p.sha(path)
            report.update(dmi=result, complete=True,
                          left_configured='N56r10 requested diagnostic; not qualified')
            save()
            print(json.dumps(report), flush=True)
        except BaseException as error:
            report['error'] = repr(error); save()
            if report['programming_attempted']:
                for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                    signal.signal(signum, signal.SIG_IGN)
                try:
                    hw.program('restore_r8', fallback, p.R8SHA)
                    samples = old.fallback_samples(hw.observe('restored', old.RESTORED))
                    report.update(fallback_restored=True, fallback=samples,
                                  left_configured='N56r8 internal bars; CPU halted')
                except Exception as restore_error:
                    report['restore_error'] = repr(restore_error)
                save()
            raise


if __name__ == '__main__':
    main()
