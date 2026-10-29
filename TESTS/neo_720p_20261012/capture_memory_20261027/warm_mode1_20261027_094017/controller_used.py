#!/usr/bin/env python3
"""Prepare/run one reviewed Neo UART mode1 trial. Default: filesystem checks only."""
import argparse
import fcntl
import json
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
import board_trial_r21 as t
import serial
HERE,ROOT,hw=t.HERE,t.ROOT,t.hw
ANCHOR=HERE/'startup_100k_20261027_090320/result.json'
ANCHOR_SHA='94ac7c893b75a60e8e0f3408013afaf24568db8654e4b7bc72267e2ad9a31b8f'
PHOTO=ANCHOR.parent/'r19_after_check.jpg'
PHOTO_SHA='5c9c34a42b7d8f8232c30c77a11aef605625f2f366489334957ea9704e1c4502'
REVIEW=HERE/'root_route_review_01.json'
UART=Path('/dev/serial/by-id/usb-SIPEED_USB_Debugger_2025041420-if01-port0')
FRAME=bytes.fromhex('a55a52313501fe0d')


def check_code(count):
    assert count in (0,2)
    return t.BASE_GUARD+f'''
echo "NCP_RAW_BEFORE_ASSERT [read_memory 0xe9005080 32 7]"
foreach {{addr expected}} {{
  0xe9005080 0x4e435031 0xe9005088 {count} 0xe900508c {count}
  0xe9001004 0 0xe9001008 0 0xe9001034 0
}} {{
  if {{[lindex [read_memory $addr 32 1] 0]!=$expected}} {{error "Unexpected idle GPU/NCP counters"}}
}}
echo "NCP_COUNTERS [read_memory 0xe9005088 32 2]"
echo "WARM_CHECK_{count}"
'''


def seed_code():
    # No GPU command or DDR transaction: two observer ARM/SNAP handshakes.
    code=check_code(0)
    for i in range(2):code+=t.ARM+t.CAPTURE
    code+='''if {[word 0xe9005088]!=2 || [word 0xe900508c]!=2 || [word 0xe9001004]!=0 || [word 0xe9001008]!=0} {error "NCP witness not established"}
echo NCP_WITNESS_2_2
'''
    assert set(re.findall(r'write_memory\s+(0x[0-9a-f]+)',code))=={'0xe9005084','0xe9005088'}
    assert not any(s in code for s in ['load_image','dump_image','resume','reset halt','reset run','0xe9001010'])
    return code


def local_plan():
    assert t.sha(ANCHOR)==ANCHOR_SHA and t.sha(PHOTO)==PHOTO_SHA
    a=json.loads(ANCHOR.read_text())
    assert a['left_startup_verified'] and a['last_programmed_sha256']==t.R19_SHA
    assert a['left_state']=='R19 CPU halted; fresh GPU state; internal bars selected'
    for name,digest in a['files'].items():assert t.sha(ANCHOR.parent/name)==digest,name
    review,bit=t.route_review(REVIEW)
    assert t.sha(t.R19/'impl/pnr/console_neo.fs')==t.R19_SHA
    assert FRAME==bytes([0xa5,0x5a,0x52,0x31,0x35,1,0xfe,0x0d])
    seed_code()
    return dict(anchor_sha256=ANCHOR_SHA,anchor_photo_sha256=PHOTO_SHA,
        route_review_sha256=t.sha(REVIEW),candidate_sha256=review['bitstream_sha256'],
        r19_sha256=t.R19_SHA,controller_sha256=t.sha(Path(__file__)),
        jtag_khz=100,frame_hex=FRAME.hex(),delay_mode=1,DDR_commands=False,
        USB_relay_CLI=False,mode0=False,program_flash=False),bit


class IO:
    def __init__(self,out,report,save):self.out,self.r,self.save=out,report,save
    def observe(self,name,code,marker):
        script=self.out/(name+'.tcl');log=self.out/(name+'.log')
        assert not script.exists() and not log.exists()
        script.write_text(code+'\nshutdown\n')
        hw.run_child(['/usr/local/bin/openocd','-f',str(ROOT/'tools/neo/ae350_espprog.cfg'),
          '-c','adapter speed 100; gdb_port disabled; tcl_port disabled; telnet_port disabled',
          '-f',str(script)],log,30)
        text=log.read_text();assert re.search(r'^'+re.escape(marker)+r'\r?$',text,re.M),marker
        return text
    def program(self,name,path,digest):
        assert t.sha(path)==digest
        log=self.out/(name+'.log');assert not log.exists()
        self.r['programming_attempted_sha256']=digest
        self.r['last_programmed_sha256']=None;self.r['left_startup_verified']=False;self.save()
        ident=hw.usb_identity();self.r['usb_identity']=ident
        assert ident['neo']['serial']=='2025041420' and ident['neo']['path'].endswith('/3-4.4.1')
        hw.run_child([str(Path.home()/'.local/bin/openFPGALoader'),'--busdev-num',ident['programmer_busdev'],
          '-b','tangconsole','-m','--verbose','--freq','6000000',str(path)],log,120)
        self.r[name+'_status']=hw.p.check_program_status(log.read_text())
        # Persist immediately after valid DONE, before delay, photo or CPU guard.
        self.r['last_programmed_sha256']=digest;self.save()
        time.sleep(2)
    def camera(self,name):
        jpg=self.out/(name+'.jpg');log=self.out/(name+'_camera.log')
        assert not jpg.exists() and not log.exists()
        try:
            hw.run_child(['/usr/bin/ffmpeg','-hide_banner','-loglevel','warning','-f','v4l2',
              '-input_format','mjpeg','-video_size','1920x1080','-i','/dev/video0',
              '-vf','select=gte(n\\,15)','-frames:v','1','-update','1','-n',str(jpg)],log,15)
        except Exception as e:self.r[name+'_camera_error']=repr(e)
        self.save()
    def send(self,name,before_frame=None,after_frame=None):
        # Preserve the current relay; entering BL616 CLI previously broke it.
        real=UART.resolve(strict=True)
        dev=(Path('/sys/class/tty')/real.name/'device').resolve(strict=True)
        parents=[dev]+list(dev.parents)
        interfaces=[p for p in parents if (p/'bInterfaceNumber').is_file()]
        boards=[p for p in parents if (p/'serial').is_file()]
        assert len(interfaces)==1 and (interfaces[0]/'bInterfaceNumber').read_text().strip()=='01'
        assert any((p/'serial').read_text().strip()=='2025041420' for p in boards)
        owners=subprocess.run(['fuser',str(real)],capture_output=True,text=True,timeout=5)
        assert owners.returncode==1 and not owners.stdout.strip(),'UART already in use'
        entry=dict(frame_hex=FRAME.hex(),bytes_written=0,receipt='unknown',UART=str(UART),resolved=str(real),started_unix=time.time())
        self.r[name]=entry;self.save()
        with serial.Serial(str(UART),2000000,timeout=.05,write_timeout=1,
                           exclusive=True,xonxoff=False,rtscts=False,dsrdtr=False) as link:
            # R19 checks remain inside the same open handle: neither opening
            # nor closing modem control lines may explain its witness reset.
            if before_frame is not None:before_frame()
            entry['bytes_written']=link.write(FRAME);self.save()
            assert entry['bytes_written']==len(FRAME),'Partial reset frame'
            deadline=time.monotonic()+2
            while link.out_waiting:
                if time.monotonic()>deadline:raise TimeoutError('UART transmit queue did not drain')
                time.sleep(.005)
            time.sleep(.25)
            # Bounded RX evidence only. No flush, CLI entry, line cancellation or retry.
            data=link.read(4096)
            (self.out/(name+'_rx.bin')).write_bytes(data)
            if after_frame is not None:after_frame()
        entry['finished_unix']=time.time();self.save()


def execute(io,report,save,bit):
    mutated=False
    def observe(name,count):return io.observe(name,check_code(count),'WARM_CHECK_'+str(count))
    def restored():
        assert not report.get('restore_attempted',False),'Restoration already attempted'
        report['restore_attempted']=True;save()
        for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,signal.SIG_IGN)
        io.program('restore_r19',t.R19/'impl/pnr/console_neo.fs',t.R19_SHA)
        observe('restored_r19_guard',0)
        report.update(left_startup_verified=True,left_state='R19 CPU halted; fresh GPU/NCP; internal bars')
        save();io.camera('restored_r19_view')
    try:
        observe('r19_initial_guard',0)
        mutated=True
        io.observe('r19_seed_ncp',seed_code(),'NCP_WITNESS_2_2')
        # Separate JTAG session proves reconnect/halt alone does not erase the witness.
        observe('r19_witness_before_uart',2)
        io.send('r19_mode1',
            before_frame=lambda:observe('r19_open_before_frame',2),
            after_frame=lambda:observe('r19_frame_before_close',0))
        observe('r19_after_mode1',0)
        report['r19_mode1']['receipt']='reset_observed_after_frame_with_open_control_epoch_unobserved'
        report['r19_reset_observed_after_frame']=True;save()
        io.camera('r19_warm_view')
        io.program('program_r21',bit,report['candidate_sha256'])
        io.camera('r21_before_initial_dmi')
        try:
            observe('r21_initial_dmi',0)
        except Exception as e:
            report['r21_initial_error']=repr(e);save()
            io.send('r21_mode1')
            io.camera('r21_after_uart_before_dmi')
            try:
                observe('r21_after_mode1_dmi',0)
            except Exception as second:
                report['r21_after_mode1_error']=repr(second)
                report['outcome']='R21_no_recovery_UART_receipt_unknown';save()
                restored();report['diagnostic_complete']=True;save();return
            report['outcome']='R21_recovered_after_mode1'
            # R21 had no readable pre-reset witness: recovery is not epoch proof.
            report['r21_mode1']['receipt']='recovery_after_frame_no_independent_epoch'
        else:report['outcome']='R21_started_without_UART_retry'
        report.update(r21_startup_verified=True,left_startup_verified=True,
                      left_state='R21r1 CPU halted; fresh GPU/NCP; internal bars',diagnostic_complete=True)
        save();io.camera('r21_final_view')
    except BaseException as e:
        report['error']=repr(e);save()
        if mutated:
            # Restore only after the original parked-state guard was valid.
            if report.get('restore_attempted',False):
                report['fallback_error']=repr(e);save()
            else:
                try:restored()
                except BaseException as fallback:report['fallback_error']=repr(fallback);save()
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--check-only',action='store_true')
    args=p.parse_args();assert not(args.run and args.check_only)
    plan,bit=local_plan()
    if not args.run:
        print(json.dumps(dict(local_plan_passed=True,hardware_access=False,**plan)));return
    out=HERE/('warm_mode1_'+time.strftime('%Y%m%d_%H%M%S'))
    report=dict(board='neo',candidate=True,qualification_status='FAIL',**plan,
      diagnostic_complete=False,r19_reset_observed_after_frame=False,r21_startup_verified=False,
      last_programmed_sha256=t.R19_SHA,left_startup_verified=False,
      DDR_written=False,SD_written=False,flash_written=False,Linux_loaded=False,
      CPU_resume_command=False,CPU_ROM_restart_possible=True)
    def save():(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    def interrupt(sig,frame):raise KeyboardInterrupt('Signal '+str(sig))
    for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,interrupt)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh','-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True,timeout=5)
        assert active.returncode==1 and not active.stdout.strip()
        ident=hw.usb_identity()
        assert ident['neo']['serial']=='2025041420' and ident['neo']['path'].endswith('/3-4.4.1') and ident['esp']['path'].endswith('/3-4.4.2')
        out.mkdir();(out/'controller_used.py').write_bytes(Path(__file__).read_bytes())
        report.update(identity=ident,started_unix=time.time());save()
        try:execute(IO(out,report,save),report,save,bit)
        finally:
            report['finished_unix']=time.time()
            report['files']={p.name:t.sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
            save();print(json.dumps(dict(output=str(out),**report)),flush=True)
if __name__=='__main__':main()
