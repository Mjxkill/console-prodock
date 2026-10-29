#!/usr/bin/env python3
"""Exact-SHA Neo reset diagnosis. SRAM only; no software/DDR/SD writes."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COLD = HERE.parent / 'reload_r1_cold_20261022'
sys.path.insert(0, str(COLD))
import probe_route9_led_compare as hw

BUILD = ROOT / 'tang/impl/console_neo_n56r15_reset50ms'
PARENT = ROOT / 'tang/impl/console_neo_n56r10_gao_startup'
BIT_SHA = '8b005988433a70fdef654f5e2e7f93b3ba484764c1be44bb356bd1418931227b'
OLD_SHA = '7ca33ea0a54a4ba557319489239e330f6fbfca69840982894ca447a705b05f28'
AUDIT_SHA = '48f5c4a42891353f2f93691e3b2d223da241ad3d4bfddf71377e543c3e8d77a7'
TIMING = dict(setup=-3.844, hold=-0.305, recovery=-4.972, removal=0.269)

TRANSPORT = '''adapter driver ftdi
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
irscan neo.cpu 0x01
set ident [drscan neo.cpu 32 0]
if {$ident ne "1000563d"} {error "Unexpected AE350 IDCODE: $ident"}
echo "TRANSPORT_ID $ident"
irscan neo.cpu 0x10
set dtmcs [drscan neo.cpu 32 0]
echo "DTMCS_BEFORE $dtmcs"
if {$dtmcs ne "00007071"} {error "Unexpected initial DTMCS: $dtmcs"}
irscan neo.cpu 0x11
echo "DMCONTROL_REQUEST [drscan neo.cpu 41 0x4000000001]"
foreach idle_cycles {1000 10000 100000} {
    runtest $idle_cycles
    echo "DMCONTROL_RESPONSE cycles=$idle_cycles raw=[drscan neo.cpu 41 0]"
}
irscan neo.cpu 0x10
echo "DTMCS_AFTER [drscan neo.cpu 32 0]"
shutdown
'''


def preflight():
    audit = HERE / 'postroute/result.json'
    assert hw.p.sha(audit) == AUDIT_SHA
    r = json.loads(audit.read_text())
    assert r['qualification_status'] == 'FAIL' and r['timing'] == TIMING
    assert r['bitstream_sha256'] == BIT_SHA and not r['missing_primary']
    assert r['timing_summary']['violated_endpoints'] == dict(setup=31, hold=7)
    assert all(v['passed'] for k,v in r['synthesis_audits'].items() if k != 'ddr_profile')
    assert r['synthesis_audits']['ddr_profile']['changed'] == ['tang/rtl/board/ae350_soc.v']
    assert set(r['only_original_application_cell_change']) == {'u_soc/init_sync_0_s0'}
    for path,digest in r['input_sha256'].items():
        assert hw.p.sha(Path(path)) == digest, path
    assert hw.p.sha(BUILD/'impl/pnr/ao_0.fs') == BIT_SHA
    assert hw.p.sha(PARENT/'impl/pnr/ao_0.fs') == OLD_SHA
    manifest = json.loads((BUILD/'sources.json').read_text())
    assert manifest == {str(p.relative_to(BUILD/'source')):hw.p.sha(p)
                        for p in (BUILD/'source').rglob('*') if p.is_file()}
    old = json.loads((COLD/'r10_gao_load_trial/result.json').read_text())
    assert old['configured'] and old['bitstream_sha256'] == OLD_SHA and not old['fallback_restored']
    return r


def transport(out, name):
    cfg = out / (name + '.tcl')
    cfg.write_text(TRANSPORT)
    log = out / (name + '.log')
    hw.run_child(['/usr/local/bin/openocd', '-f', str(cfg)], log, 15)
    text = log.read_text()
    values = re.findall(r'^DMCONTROL_RESPONSE cycles=(\d+) raw=([0-9a-fA-F]+)\r?$', text, re.M)
    assert len(values) == 3
    return dict(responses=[dict(cycles=int(c), raw=v, status=int(v,16)&3,
        data_valid=(int(v,16)&3)==0) for c,v in values], log_sha256=hw.p.sha(log),
        cpu_target_created=False, cpu_halt_requested=False, cpu_reset_requested=False,
        DMI_write_requested=False, transport_TAP_initialized=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    preflight()
    if args.check_only:
        print(json.dumps(dict(preflight_passed=True, hardware=False,
            qualification='FAIL', bitstream_sha256=BIT_SHA, timing=TIMING)))
        return
    out = HERE / 'cold_trial_01'
    assert not out.exists()
    import subprocess
    report = dict(bitstream_sha256=BIT_SHA, qualification='FAIL', timing=TIMING,
        authorization='User continued Neo reset diagnosis and selected a 50 ms margin',
        scope='Cold FPGA configuration, camera and raw DMI read; no warm comparison yet',
        script_sha256=hw.p.sha(Path(__file__)), programming_attempted=False,
        configured=False, previous_restored=False, software_started_by_script=False,
        ddr_written_by_script=False, sd_written_by_script=False, flash_written=False)
    def save():
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def interrupted(signum, frame):
        raise KeyboardInterrupt('Interrupted: '+str(signum))
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, interrupted)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
            '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode == 1 and not active.stdout.strip(), active.stdout
        identity = hw.usb_identity()
        assert identity['neo']['path'].endswith('/3-4.4.1')
        assert identity['esp']['path'].endswith('/3-4.4.2')
        out.mkdir()
        report['identity'] = identity
        report['started_unix'] = time.time()
        save()
        board = hw.Hardware(out, report)
        try:
            report['before'] = transport(out,'before_dmi')
            assert all(v['status'] == 3 for v in report['before']['responses']), 'Previous blocked state changed: do not reconfigure'
            save()
            report['programming_attempted'] = True
            save()
            board.program('program_r15',BUILD/'impl/pnr/ao_0.fs',BIT_SHA)
            report['configured'] = True
            save()
            print('R15_CONFIGURED '+BIT_SHA,flush=True)
            try:
                hw.run_child(['/usr/bin/ffmpeg','-hide_banner','-loglevel','warning',
                    '-f','v4l2','-input_format','mjpeg','-video_size','1920x1080',
                    '-i','/dev/video0','-vf','select=gte(n\\,15)','-frames:v','1',
                    '-update','1','-n',str(out/'camera_before_dmi.jpg')],out/'camera.log',15)
                report['camera_sha256'] = hw.p.sha(out/'camera_before_dmi.jpg')
            except Exception as exc:
                report['camera_error'] = repr(exc)
            try:
                report['after'] = transport(out,'after_dmi')
            except Exception as exc:
                report['after_observation_error'] = repr(exc)
            report['complete'] = True
            report['left_configured'] = 'R15 reset diagnosis, not qualified'
            save()
            print(json.dumps(report),flush=True)
        except BaseException as exc:
            report['error'] = repr(exc)
            save()
            if report['programming_attempted']:
                for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP): signal.signal(sig,signal.SIG_IGN)
                try:
                    board.program('restore_r10',PARENT/'impl/pnr/ao_0.fs',OLD_SHA)
                    report['previous_restored'] = True
                except Exception as restore:
                    report['restore_error'] = repr(restore)
                save()
            raise


if __name__ == '__main__':
    main()
