"""Reuse frozen UART.read on one strictly pinned new-board descriptor.

Only host termios is set. No write(), flush(), DTR/RTS ioctl, shell command,
JTAG or device probing is exposed. The global diagnostic lock spans capture.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import importlib.util
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import termios
import time
import tty

HOST='michael-AX15'
PROGRAMMER='2025071717'
PORT=Path('/dev/serial/by-path/pci-0000:00:14.0-usb-0:7.1:1.0')
USB=Path('/sys/bus/usb/devices/3-7.1')
LOCK=Path('/tmp/prodock-diagnostic.lock')
SUPPORT=Path('/tmp/festival_persistent_20261028_prepared_r1/support.py')
SUPPORT_SHA='45cf2c8cddcbe8a903f6bf73dca552512052883d88670ffa889815133127c29b'
PACKAGE_SHA='10b0ee5d77919f492bef371427d5849010ead80e9be7ded10089772d55b05b43'
KERNEL_MANIFEST_SHA='29b0d686d114fa6f41973b4686b1903875e96f97b690f68c17da6205e8cb0a71'
GAME_SHA='a8485ce6d5e34ed46617a2b663278f14333fd20ee47396198d4296e087b76ebd'


def need(ok,message):
    if not ok:raise RuntimeError(message)


def validate_review(review,manifest_sha,host,now):
    """An explicit root attestation binds topology/package; it is not UART proof."""
    need(host==HOST and review.get('host')==HOST,'Wrong execution host')
    expected={'target_programmer':PROGRAMMER,'port':str(PORT),'usb_topology':'3-7.1','manifest_sha256':manifest_sha,'package_manifest_sha256':PACKAGE_SHA,'kernel_manifest_sha256':KERNEL_MANIFEST_SHA,'game_sha256':GAME_SHA}
    for k,v in expected.items():need(review.get(k)==v,'Review mismatch: '+k)
    for k in ('new_console_binding_confirmed','passive_capture_authorized','old_board_untouched','no_other_console_session','bitstream_validation_reviewed'):
        need(review.get(k) is True,'Missing root attestation: '+k)
    stamp=review.get('reviewed_unix')
    need(type(stamp) in (int,float) and 0<=now-stamp<=1800,'Review expired or future')
    return {'source':'root_attestation_not_measured_by_collector','powercycle_claim':review.get('powercycle_claim',None)}


def verify_program_result(review):
    """Pin prior root programming result; SRAM success is not a cold-boot proof."""
    path=Path(review['program_result_path'])
    need(not path.is_symlink() and path.is_file() and path.stat().st_size<=1048576,'Invalid programming proof file')
    raw=path.read_bytes()
    need(hashlib.sha256(raw).hexdigest()==review.get('program_result_sha256'),'Programming proof changed')
    result=json.loads(raw)
    need(result.get('target_serial')==PROGRAMMER and result.get('configuration_completed') is True,'New-board programming not confirmed')
    expected=review.get('bitstream_sha256','')
    need(isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected) and result.get('bitstream_sha256')==expected,'Bitstream identity differs')
    writes=result.get('flash_writes')
    need(type(writes) is int and writes>=0,'Missing programming mode evidence')
    return {'path':str(path),'sha256':review['program_result_sha256'],'bitstream_sha256':expected,'flash_writes':writes,'scope':'root programming result; no independent FPGA readback by collector'}


def validate_identity(identity):
    need(identity['usb_path']==str(USB),'Wrong USB topology (old7.3 forbidden)')
    need(identity['port']==str(PORT),'Wrong console path')
    need((identity['idVendor'],identity['idProduct'],identity['serial'])==('359f','2011','11252024'),'Wrong USB descriptor')
    need(identity['speed']=='480','USB HS required')
    need(identity['tty_usb_parent']==str(USB.resolve()),'TTY maps outside new USB7.1')
    need(re.fullmatch(r'ttyACM[0-9]+',identity['tty']) is not None,'Unexpected TTY type')
    return identity


def snapshot():
    """Prove the by-path alias resolves to a TTY belonging to USB7.1 itself."""
    node=PORT.resolve(strict=True)
    need(stat.S_ISCHR(node.stat().st_mode),'Port is not a character device')
    device=(Path('/sys/class/tty')/node.name/'device').resolve(strict=True)
    usb=USB.resolve(strict=True)
    need(usb in device.parents,'TTY mapping is not new-board7.1')
    data={k:(USB/k).read_text().strip() for k in ('idVendor','idProduct','serial','speed','busnum','devnum')}
    data.update(port=str(PORT),usb_path=str(USB),tty=node.name,tty_usb_parent=str(usb),rdev=node.stat().st_rdev)
    return validate_identity(data)


def quiet_owner(result):
    need(result.returncode==1 and not result.stdout.strip() and not result.stderr.strip(),'UART busy or fuser failed')


@contextmanager
def diagnostic_lock():
    fd=os.open(LOCK,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(fd)
        need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.getuid(),'Unsafe diagnostic lock')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(fd)


class PassiveUART:
    """Read-only file descriptor; reuse UART.read/close, never its constructor/write."""
    def __init__(self):
        need(socket.gethostname().split('.')[0]==HOST,'Wrong execution host')
        need(not SUPPORT.is_symlink() and hashlib.sha256(SUPPORT.read_bytes()).hexdigest()==SUPPORT_SHA,'Frozen UART support changed')
        spec=importlib.util.spec_from_file_location('frozen_passive_support',SUPPORT)
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        self.base=mod.UART;self.fd=None;self.identity=None;self.termios_before=None

    def open(self,timeout=5):
        before=snapshot()
        quiet_owner(subprocess.run(['fuser',str(PORT)],capture_output=True,timeout=timeout))
        fd=os.open(PORT,os.O_RDONLY|os.O_NOCTTY|os.O_NONBLOCK)
        try:
            fcntl.ioctl(fd,termios.TIOCEXCL)
            need(os.fstat(fd).st_rdev==before['rdev'],'TTY switched while opening')
            need(snapshot()==before,'USB identity changed during opening')
            self.termios_before=repr(termios.tcgetattr(fd))
            tty.setraw(fd,termios.TCSANOW)
            attrs=termios.tcgetattr(fd)
            attrs[2]&=~(termios.PARENB|termios.CSTOPB|termios.CSIZE|termios.CRTSCTS|termios.HUPCL)
            attrs[2]|=termios.CS8|termios.CLOCAL|termios.CREAD
            attrs[4]=attrs[5]=termios.B115200
            termios.tcsetattr(fd,termios.TCSANOW,attrs)
            need(termios.tcgetattr(fd)[4:6]==[termios.B115200]*2,'115200 setup failed')
            self.fd=fd;self.identity=before
            return before
        except BaseException:os.close(fd);raise

    def connected(self):
        try:return snapshot()==self.identity
        except FileNotFoundError:return False

    def read(self,size,timeout):
        return self.base.read(self,size,timeout)

    def write(self,*args):
        raise RuntimeError('Passive collector forbids every UART transmission')

    def close(self):
        if self.fd is not None:
            fd=self.fd;self.fd=None
            os.close(fd)
