#!/usr/bin/env python3
"""Reload the exact parked route2 twice, observing reset release in bars mode.

Consumes the stopped failed followup once. SRAM only, no DDR payload or SD.
"""
import fcntl
import json
from pathlib import Path
import re
import subprocess
import time
import probe_scan_observer as probe


def main():
    prior_dir = probe.HERE/'r9_route2_followup'
    prior = json.loads((prior_dir/'result.json').read_text())
    assert prior['bitstream_sha256'] == probe.ROUTE2SHA and prior['cpu_left_halted']
    assert not prior['sd_written'] and not prior['flash_written'] and not prior['fpga_reloaded']
    previous_log = (prior_dir/'observe.log').read_text()
    assert 'SNAP_BARS1 0x1 0x0 0x4f 0x0 0x0 0x0 0x0 0x53434e15' in previous_log
    assert 'Error: Fallback bars not applied' in previous_log
    assert not (prior_dir/'reload_consumed.json').exists()
    q, bit = probe.check_fpga(probe.BUILD, probe.ROUTE2SHA,
        diagnostic_recovery_min_ns=-1.418, preflight_only=True)
    out = probe.HERE/'r9_route2_reset_reloads'
    out.mkdir(exist_ok=False)
    report = dict(complete=False, cpu_left_halted=False, bitstream_sha256=probe.ROUTE2SHA,
        sd_written=False, flash_written=False, ddr_payload_written=False, rounds=[],
        qualification_status=q['status'], script_sha256=probe.sha(Path(__file__)),
        anchor_sha256=probe.sha(prior_dir/'result.json'), anchor_log_sha256=probe.sha(prior_dir/'observe.log'))

    def observe(name, code):
        script = out/(name+'.tcl'); script.write_text(code)
        with (out/(name+'.log')).open('w') as log:
            subprocess.run(['/usr/local/bin/openocd','-f',str(probe.ROOT/'tools/neo/ae350_espprog.cfg'),
                '-c','gdb_port disabled; tcl_port disabled; telnet_port disabled','-f',str(script)],
                stdout=log,stderr=log,check=True,timeout=30)
        text = (out/(name+'.log')).read_text()
        report['cpu_left_halted'] = 'CPU_HALTED' in text
        return text

    try:
        devices=[d for d in Path('/sys/bus/usb/devices').iterdir()
            if (d/'serial').exists() and (d/'serial').read_text().strip()=='2025041420']
        assert len(devices)==1
        device=devices[0]
        assert (device/'idVendor').read_text().strip()=='0403' and (device/'idProduct').read_text().strip()=='6010'
        busdev=':'.join((device/n).read_text().strip() for n in ('busnum','devnum'))
        report['programmer_busdev']=busdev
        with (probe.ROOT/'TESTS/neo_board.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            observe('guard',probe.GUARD+'''
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=1 || [lindex [read_memory 0xe9000004 32 1] 0]!=0x01700000} {error "Not the stopped pending-bars trial"}
'''+probe.SNAPSHOT+'snapshot GUARD\nshutdown\n')
            with (prior_dir/'reload_consumed.json').open('x') as marker:
                json.dump(dict(out=str(out),bitstream_sha256=probe.ROUTE2SHA,time=time.time()),marker)
            for index in range(2):
                name=f'reload_{index}'
                report['cpu_left_halted']=False
                with (out/(name+'_program.log')).open('w') as log:
                    subprocess.run([str(Path.home()/'.local/bin/openFPGALoader'),'--busdev-num',busdev,
                        '-b','tangconsole','-m','--verbose','--freq','6000000',str(bit)],
                        stdout=log,stderr=log,timeout=120,check=True)
                status=probe.check_program_status((out/(name+'_program.log')).read_text())
                text=observe(name,probe.GUARD+probe.SNAPSHOT+'''
sleep 100
snapshot START
sleep 1000
snapshot LATER
if {[lindex [read_memory 0xe9000008 32 1] 0]!=0 || [lindex [read_memory 0xe900000c 32 1] 0]!=0 || [lindex [read_memory 0xe9000060 32 1] 0]!=0x1ff8f800} {error "Internal bars not active after reload"}
echo RESET_RELOAD_COMPLETE
shutdown
''')
                snaps={n:probe.decode([int(w,0) for w in words.split()])
                    for n,words in re.findall(r'^SNAP_(\w+) (.+)$',text,re.M)}
                report['rounds'].append(dict(index=index,program_status=status,snapshots=snaps,
                    internal_bars_selected='RESET_RELOAD_COMPLETE' in text))
            report['complete']=len(report['rounds'])==2 and all(r['internal_bars_selected'] for r in report['rounds'])
    except Exception as error: report['error']=str(error)
    finally:
        report['limits']='Repeated SRAM reload observations with known setup/recovery FAIL, no visual confirmation or framebuffer qualification.'
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
    return 0 if report['complete'] else 1


if __name__=='__main__':raise SystemExit(main())
