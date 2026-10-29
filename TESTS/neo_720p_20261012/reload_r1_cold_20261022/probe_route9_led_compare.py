#!/usr/bin/env python3
"""Exact N56r8 -> R9 -> N56r8 LED experiment, with explicit user observations.

Prepare/review first. --check-only reads frozen files only. A real invocation
holds the Neo lock throughout, probes R9 DMI only AFTER its LED answer, never writes
framebuffer/GPU registers, starts Linux, resumes CPU, or writes SD/flash.
R9 remains configured until an explicit LED answer, EOF or interruption.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

import probe_scan_observer as p
import probe_route9_scan_reset_100k as prior

BUILD, BIT_SHA, TIMING_SHA = prior.BUILD, prior.BIT_SHA, prior.TIMING_SHA
REVIEW, REVIEW_SHA, TIMING = prior.REVIEW, prior.REVIEW_SHA, prior.TIMING
FALLBACK = p.ROOT/'tang/impl/console_neo_n56r8_hdmi_sg4'
ANCHOR = p.HERE/'r9_route9_rgb_trial_100k'
CONSUMED = ANCHOR/'led_compare_consumed.json'
ANCHOR_SHA = {
    'result.json': '3f4526d23d0792c2aea7d57d394ef7a19ef749caace8404dda660bf0f99bd692',
    'restored.log': 'ea5cc5fd845d4be6144b93bb05b792095befcf20a21c866e4d3a288a1e4dfe8a',
    'visual_confirmation_fallback.json': '8779625196d70a2e657d33cfd498b929cf60b2baa2e00edb48ad5aeac8911243'}
DEPENDENCIES = {
    p.HERE/'probe_scan_observer.py': '84acc1fa94d96958cbd1b83ea654bd7eae982b2c74db5c18ca8ccbfe7a1b5918',
    p.HERE/'probe_route9_scan_reset_100k.py': '845b727794d3f02e70556ac9def6fff5dfe33dcaafd278d15f45809f7c3ea4fc',
    p.ROOT/'tools/neo/ae350_espprog.cfg': 'aa317f61c5093b8c230d96ba70b56cda65448f4b295a70b4e67cf09cd5ef9b67'}

GUARD = p.GUARD + '''
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Fallback bars state changed"}
echo R8_PARKING_CONFIRMED
shutdown
'''
RESTORED = p.GUARD + '''
sleep 100
echo "FALLBACK_0 [read_memory 0xe9000000 32 32]"
sleep 1000
echo "FALLBACK_1 [read_memory 0xe9000000 32 32]"
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Fallback differs"}
echo R8_BARS_RESTORED
shutdown
'''
DMI_AFTER_LED = '''init
halt
echo LED_DMI_CPU_HALTED
reg pc
echo LED_DMI_COMPLETE
shutdown
'''


def record(path):
    return json.loads(path.read_text())


def fallback_samples(log):
    matches = re.findall(r'^FALLBACK_([01]) (.+)$', log, re.M)
    p.require(len(matches) == 2 and {n for n, _ in matches} == {'0', '1'}, 'Missing/duplicate fallback samples')
    values = {n: [int(w, 0) for w in words.split()] for n, words in matches}
    p.require(all(len(v) == 32 and all(0 <= w <= 0xffffffff for w in v) for v in values.values()),
              'Incomplete fallback registers')
    delta = (values['1'][6]-values['0'][6]) & 0xffffffff
    p.require(delta > 0 and all(v[0] == 0x47505531 and v[2] == v[3] == 0 and
              v[24] == 0x1ff8f800 and v[28] == 0x02d00500 for v in values.values()) and
              re.search(r'^CPU_HALTED\r?$', log, re.M) and
              re.search(r'^R8_BARS_RESTORED\r?$', log, re.M), 'Fallback state/progress mismatch')
    return dict(registers=values, frame_delta=delta, cpu_left_halted=True)


def led_proof(build):
    top = build/'source/tang/boards/neo/console_neo.v'
    cst = build/'source/tang/boards/neo/neo.cst'
    vo = build/'impl/pnr/console_neo.vo'
    p.require(re.search(r'assign\s+led_n\s*=\s*~ddr_init\s*;', top.read_text()), 'LED RTL changed')
    p.require(re.findall(r'^IO_LOC "led_n" ([^;]+);', cst.read_text(), re.M) == ['V13'], 'LED pin changed')
    text = vo.read_text()
    for pattern in (
        r'^LUT1 led_n_d_s0\s*\(\s*\.I0\(ddr_init\),\s*\.F\(led_n_d_4\)\s*\);\s*defparam led_n_d_s0.INIT=2\x27h1;',
        r'^OBUF led_n_obuf\s*\(\s*\.I\(led_n_d_4\),\s*\.O\(led_n\)\s*\);',
        r'^DFFCE \\u_soc/g_ddr\.u_ddr/u_ip/gw3_top/u_ddr_phy_top/u_ddr_init/ddr_init_complete_d_3_s0\s+\([^;]*\.Q\(ddr_init\)\s*\);'):
        p.require(len(re.findall(pattern, text, re.M)) == 1, 'Routed LED/calibration function changed')
    return dict(function='led_n = !ddr_init', ball='V13', polarity='active-low user LED',
        observed_on_means_ddr_init=1, observed_off_means_ddr_init=0,
        input_sha256={str(f):p.sha(f) for f in (top, cst, vo)})


def preflight(bit_sha):
    # Same exact R9 failures/proofs as the reviewed 100 kHz experiment.
    p.require(bit_sha == BIT_SHA, 'Only the exact reviewed R9 SHA is allowed')
    for path, wanted in DEPENDENCIES.items():
        p.require(p.sha(path) == wanted, 'Reviewed dependency changed: '+str(path))
    q = record(BUILD/'qualification.json'); bit = BUILD/'impl/pnr/console_neo.fs'
    p.require(p.sha(bit) == q['bitstream_sha256'] == BIT_SHA, 'Bitstream changed')
    p.require(p.sha(BUILD/'impl/pnr/console_neo.tr') == q['timing_sha256'] == TIMING_SHA, 'Timing changed')
    p.require(q['status'] == 'FAIL' and q['timing_checks_ns'] == TIMING and
        q['violated_endpoints'] == dict(setup=64, hold=0) and q['minimum_pulse_slack_ns'] >= 0,
        'Different timing failure')
    audits = q['synthesis_audits']
    p.require({n for n, a in audits.items() if a.get('passed') is not True} == {'gpu_reset_tree'} and
        audits['gpu_reset_tree']['errors'] == ['Reset 4 still uses a global routing resource'], 'Different synthesis finding')
    p.require(audits['gpu_owner_replication']['netlist_sha256'] == p.sha(BUILD/'impl/pnr/console_neo.vo'), 'Owner proof changed')
    p.require(p.sha(BUILD/'console_neo.vg') == p.NETSHA, 'Synthesized logic changed')
    p.require(p.sha(BUILD/'sources.json') == q['sources_sha256'], 'Source manifest changed')
    p.require(record(BUILD/'sources.json') == {str(f.relative_to(BUILD/'source')):p.sha(f)
        for f in (BUILD/'source').rglob('*') if f.is_file()}, 'Frozen source changed')
    for name, digest in q['constraints_sha256'].items():
        p.require(p.sha(BUILD/'source/tang/boards/neo'/name) == digest, 'Constraint changed')
    p.require(q['ddr_profile']['passed'] and q['ddr_profile']['variant'] == 'neo-fifo-registers' and
        q['clock_mhz']['ddr3_mem_clk'] == 300.03 and q['clock_mhz']['core_clk'] == 800, 'DDR/core profile changed')
    p.require(p.sha(REVIEW) == REVIEW_SHA, 'Independent review changed')
    review = prior.fresh(REVIEW)
    p.require(review['passed'] and review['bitstream_sha256'] == BIT_SHA and
        review['qualification_status'] == 'FAIL' and review['reset_stages_unchanged'] and
        review['scope'] == 'Stopped-CPU scanout reset/RGB diagnostic only', 'Review scope differs')
    alias = prior.fresh(BUILD/'scan_observer_reset_alias_proof.json', 'sha256')
    strict = prior.fresh(BUILD/'scan_observer_audit.json', 'sha256')
    p.require(not strict['passed'] and strict['errors'] == [
        'Observer register function/clock/reset/init changed after synthesis'], 'Observer audit changed')
    p.require(alias['passed'] and alias['all_other_register_fields_identical'] and
        alias['reset_function'] == '!vid_hrstn' and alias['reset_alias_count'] == dict(CLEAR=2, RESET=372)
        and alias['controls'] == strict['controls'] and not alias['global_scanout_ce'], 'Observer alias differs')
    for name, wanted in ANCHOR_SHA.items():
        p.require(p.sha(ANCHOR/name) == wanted, 'Anchor changed: '+name)
    previous = record(ANCHOR/'result.json')
    p.require(previous['passed'] is False and previous['bitstream_sha256'] == BIT_SHA and
        previous['fallback_restored'] and previous['cpu_left_halted'] and previous['adapter_khz'] == 100 and
        previous['fallback_frame_delta'] > 0 and not previous['linux_started'] and not previous['sd_written'] and
        not previous['flash_written'] and previous['display_left'] == 'N56r8 internal bars, parked CPU', 'Invalid fallback anchor')
    samples = fallback_samples((ANCHOR/'restored.log').read_text())
    p.require(samples['registers'] == previous['fallback_registers'] and
        samples['frame_delta'] == previous['fallback_frame_delta'], 'Fallback evidence mismatch')
    visual = record(ANCHOR/'visual_confirmation_fallback.json')
    p.require(visual['bitstream_sha256'] == p.R8SHA and visual['user_confirmation'] == 'Oui, la mire est revenue' and
        visual['scope'] == 'N56r8 internal bars after failed R9 trial; not a framebuffer qualification', 'Visual anchor differs')
    p.require(not CONSUMED.exists(), 'Fallback anchor already consumed for LED comparison')
    _, fallback = p.check_fpga(FALLBACK, p.R8SHA)
    proof = dict(r9=led_proof(BUILD), n56r8=led_proof(FALLBACK))
    return dict(bit=bit, fallback=fallback, led_proof=proof)


def select_devices(devices):
    neo = [d for d in devices if d.get('serial') == '2025041420']
    esp = [d for d in devices if d.get('product') == 'Dual RS232-HS']
    p.require(len(neo) == 1 and len(esp) == 1 and neo[0]['path'] != esp[0]['path'], 'USB identities missing/ambiguous')
    for d in neo+esp:
        p.require(d.get('idVendor') == '0403' and d.get('idProduct') == '6010', 'Wrong Neo/ESP USB VID/PID')
        p.require(re.fullmatch(r'\d+', d.get('busnum', '')) and re.fullmatch(r'\d+', d.get('devnum', '')), 'Invalid USB address')
    return dict(neo=neo[0], esp=esp[0], programmer_busdev=neo[0]['busnum']+':'+neo[0]['devnum'])


def usb_identity():
    devices = []
    for d in Path('/sys/bus/usb/devices').iterdir():
        item = dict(path=str(d))
        for name in ('serial', 'product', 'idVendor', 'idProduct', 'busnum', 'devnum'):
            if (d/name).exists(): item[name] = (d/name).read_text().strip()
        devices.append(item)
    return select_devices(devices)


def run_child(command, logfile, timeout):
    # Kill and reap our own process group before a possible fallback command.
    with logfile.open('x') as log:
        child = subprocess.Popen(command, stdout=log, stderr=log, start_new_session=True)
        try:
            code = child.wait(timeout=timeout)
            if code: raise subprocess.CalledProcessError(code, command)
        except BaseException:
            old = {s:signal.signal(s, signal.SIG_IGN) for s in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
            try:
                try: os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                child.wait()
            finally:
                for s, handler in old.items(): signal.signal(s, handler)
            raise


class Hardware:
    def __init__(self, out, report): self.out, self.report = out, report
    def observe(self, name, code):
        self.report['usb_identity'] = usb_identity()
        p.require('write_memory' not in code and 'load_image' not in code and 'resume' not in code,
                  'Non-read-only debug script')
        script = self.out/(name+'.tcl'); script.write_text(code)
        log = self.out/(name+'.log')
        run_child(['/usr/local/bin/openocd', '-f', str(p.ROOT/'tools/neo/ae350_espprog.cfg'),
            '-c', 'adapter speed 100; gdb_port disabled; tcl_port disabled; telnet_port disabled',
            '-f', str(script)], log, 30)
        return log.read_text()
    def program(self, name, path, digest):
        p.require(p.sha(path) == digest, 'Programming payload changed')
        identity = usb_identity(); self.report['usb_identity'] = identity
        log = self.out/(name+'.log')
        run_child([str(Path.home()/'.local/bin/openFPGALoader'), '--busdev-num', identity['programmer_busdev'],
            '-b', 'tangconsole', '-m', '--verbose', '--freq', '6000000', str(path)], log, 120)
        self.report[name+'_status'] = p.check_program_status(log.read_text())
        time.sleep(2)
    def dmi_after_led(self):
        result = dict(attempted=True, timeout_seconds=30, cpu_halted=False, complete=False,
                      gpu_or_ddr_access=False)
        try:
            self.observe('r9_dmi', DMI_AFTER_LED)
        except Exception as error:
            # Transport failure is an observation, not a reason to discard LED
            # data. KeyboardInterrupt remains an abort and triggers fallback.
            result['error'] = repr(error)
            result['timed_out'] = isinstance(error, subprocess.TimeoutExpired)
        path = self.out/'r9_dmi.log'
        log = path.read_text() if path.exists() else ''
        result['cpu_halted'] = bool(re.search(r'^LED_DMI_CPU_HALTED\r?$', log, re.M))
        pc = re.search(r'^pc(?:\s+\([^)]*\))?:\s*(0x[0-9a-fA-F]+)\s*$', log, re.M)
        if pc: result['pc'] = int(pc[1], 16)
        result['complete'] = bool(not result.get('error') and result['cpu_halted'] and pc and
                                  re.search(r'^LED_DMI_COMPLETE\r?$', log, re.M))
        if path.exists(): result['log_sha256'] = p.sha(path)
        return result


def led_answer(phase):
    token = uuid.uuid4().hex
    print('LED_OBSERVATION_REQUIRED '+json.dumps(dict(phase=phase, token=token,
        values=['on', 'off', 'blinking', 'unclear'], observer='user', note='exact user observation')), flush=True)
    while True:
        line = sys.stdin.readline()
        if not line: raise EOFError('Observation cancelled: stdin closed')
        try:
            answer = json.loads(line)
            p.require(answer.get('phase') == phase and answer.get('token') == token and answer.get('observer') == 'user', 'Wrong observation phase/token/source')
            p.require(answer.get('value') in ('on', 'off', 'blinking', 'unclear'), 'Unknown LED value')
            p.require(isinstance(answer.get('note'), str) and 0 < len(answer['note'].strip()) <= 1000, 'Missing user observation')
        except (ValueError, RuntimeError, TypeError, AttributeError) as error:
            print('LED_OBSERVATION_REJECTED '+str(error), flush=True); continue
        # Keep the raw visual answer. Interpretation is allowed only after the
        # known-good LED has been identified as ON before AND after the trial.
        return dict(answer, recorded_at=time.time(), independent_of_cpu=True)


def conduct(hw, checked, report, consume, answer=led_answer, checkpoint=lambda: None):
    attempted = False
    report.update(protocol_passed=False, baseline_led_initial_valid=False,
                  baseline_led_valid=False, led_comparison_conclusive=False,
                  r9_ddr_init_from_led=None)
    try:
        guard = hw.observe('guard', GUARD)
        p.require(re.search(r'^CPU_HALTED\r?$', guard, re.M) and
                  re.search(r'^R8_PARKING_CONFIRMED\r?$', guard, re.M), 'Live parking guard absent')
        report['cpu_left_halted'] = True
        report['observations']['n56r8_before'] = answer('n56r8_before'); checkpoint()
        # The user may have interacted with the board during the visual wait.
        # Recheck the live anchor immediately before consumption/reprogramming.
        guard = hw.observe('guard_after_led', GUARD)
        p.require(re.search(r'^CPU_HALTED\r?$', guard, re.M) and
                  re.search(r'^R8_PARKING_CONFIRMED\r?$', guard, re.M), 'Live parking changed while waiting for LED')
        p.require(report['observations']['n56r8_before']['value'] == 'on',
                  'Initial V13 LED is not identified/stably on; stop without consuming anchor')
        report['baseline_led_initial_valid'] = True
        consume(); attempted = True; report['cpu_left_halted'] = False
        report['phase'] = 'programming_r9'; checkpoint()
        hw.program('program_r9', checked['bit'], BIT_SHA)
        report['phase'] = 'waiting_for_r9_led'; report['r9_programmed'] = True; checkpoint()
        # No R9 DMI probe until the user's LED observation has been persisted.
        report['observations']['r9'] = answer('r9'); checkpoint()
        report['phase'] = 'r9_dmi_after_led'; report['r9_dmi_access'] = True; checkpoint()
        report['r9_dmi'] = hw.dmi_after_led(); checkpoint()
        report['phase'] = 'restoring_n56r8'; checkpoint()
        hw.program('restore_n56r8', checked['fallback'], p.R8SHA)
        recovered = fallback_samples(hw.observe('restored', RESTORED))
        report.update(fallback_restored=True, cpu_left_halted=True, fallback=recovered,
                      phase='waiting_for_restored_led'); checkpoint()
        report['observations']['n56r8_after'] = answer('n56r8_after')
        baseline_valid = report['observations']['n56r8_after']['value'] == 'on'
        r9_value = report['observations']['r9']['value']
        conclusive = baseline_valid and r9_value in ('on', 'off')
        report.update(trial_completed=True, protocol_passed=True, passed=True, phase='complete',
                      baseline_led_valid=baseline_valid, led_comparison_conclusive=conclusive,
                      r9_ddr_init_from_led=(1 if r9_value == 'on' else 0) if conclusive else None)
    except BaseException as error:
        report['error'] = repr(error); report['phase'] = 'aborted'
        try: checkpoint()
        except BaseException as save_error: report['checkpoint_error'] = repr(save_error)
        if attempted and not report.get('fallback_restored'):
            try:
                hw.program('error_restore_n56r8', checked['fallback'], p.R8SHA)
                recovered = fallback_samples(hw.observe('error_restored', RESTORED))
                report.update(fallback_restored=True, cpu_left_halted=True, fallback=recovered)
            except BaseException as cleanup:
                report['cleanup_error'] = repr(cleanup)
        return False
    finally:
        checkpoint()
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bitstream-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    checked = preflight(args.bitstream_sha256)
    if args.check_only:
        print(json.dumps(dict(passed=True, hardware_access=False, bitstream_sha256=BIT_SHA,
            qualification_status='FAIL', timing_checks_ns=TIMING, led_proof=checked['led_proof'],
            anchor_sha256=ANCHOR_SHA, consumed=False, script_sha256=p.sha(Path(__file__)),
            scope='Explicit LED observations with post-observation DMI, no functional qualification'), indent=2)); return 0
    out = args.out.resolve()
    p.require(out.is_relative_to(p.HERE) and not any(c in str(out) for c in '{}\\\n\r'), 'Bad output path')
    out.mkdir(exist_ok=False)
    report = dict(passed=False, trial_completed=False, functional_qualification=False,
        scope='Explicit LED observations with post-observation DMI, no functional qualification',
        phase='preflight', bitstream_sha256=BIT_SHA, qualification_status='FAIL', timing_checks_ns=TIMING,
        reset4_LW_finding_preserved=True, cpu_left_halted=False, framebuffer_written=False,
        gpu_commands_sent=False, linux_started=False, sd_written=False, flash_written=False,
        cpu_resume_requested=False, r9_dmi_access=False, observations={},
        script_sha256=p.sha(Path(__file__)), anchor_sha256=ANCHOR_SHA,
        led_proof=checked['led_proof'], limits=[
            'LED is user observation of V13, not a CPU/FPGA register measurement.',
            'DONE is programming status, not SRAM readback or startup success.',
            'All setup/recovery/reset4-LW failures remain; no Linux/GPU qualification.'])
    def checkpoint():
        temp = out/'result.tmp'; temp.write_text(json.dumps(report, indent=2)+'\n'); temp.replace(out/'result.json')
    def consume():
        with CONSUMED.open('x') as marker:
            json.dump(dict(out=str(out), bitstream_sha256=BIT_SHA, anchor_sha256=ANCHOR_SHA,
                           script_sha256=report['script_sha256'], time=time.time()), marker)
    def interrupted(signum, frame): raise KeyboardInterrupt('Signal '+str(signum))
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(signum, interrupted)
    try:
        with (p.ROOT/'TESTS/neo_board.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            checked = preflight(BIT_SHA)
            report['usb_identity'] = usb_identity(); checkpoint()
            conduct(Hardware(out, report), checked, report, consume, checkpoint=checkpoint)
    except BaseException as error:
        report.setdefault('error', repr(error))
    finally:
        checkpoint(); print(json.dumps(report, indent=2), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
