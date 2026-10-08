#!/usr/bin/env python3
"""Vérifie refus des CBW malformés et reprise BOT sur le disque DDR uniquement.

Exige USBDISK R4, USB HS et 65536 secteurs DDR. N'écrit jamais une carte SD.
Le secteur DDR 32768 est réservé aux essais. La console CDC reste ouverte.
"""
import argparse
import errno
import json
from pathlib import Path
import re
import struct
import time

import serial
from serial.tools import list_ports
import usb.core
import usb.util
from check_gpu_reloads import console_snapshot
from check_usb_disk import Disk, Fail, command, VID, PID

def state(port):
    return dict(re.findall(r'(\w+)=(\w+)',command(port,'s','USBDISK MEDIA=')))

def require_ddr(port,disk):
    current=state(port)
    if current.get('MEDIA')!='DDR' or current.get('SERVING')!='1':
        raise Fail('Essai refusé : le firmware ne sert pas la DDR')
    for _ in range(3):
        if disk.transfer(bytes(6))[0]==0:break
        disk.sense()
    else:raise Fail('DDR non prête')
    status,residue,data=disk.transfer(bytes([0x25])+bytes(9),8)
    if status or residue or data!=struct.pack('>II',65535,512):
        raise Fail('Essai refusé : capacité différente de la DDR 32 Mio')

def expect_stall(action):
    try:action()
    except usb.core.USBError as error:
        if error.errno==errno.EPIPE:return
        raise Fail(f'Erreur USB autre que STALL : {error}') from error
    raise Fail('STALL attendu, transfert accepté')

def halted(dev,endpoint):
    value=bytes(dev.ctrl_transfer(0x82,0,0,endpoint,2,timeout=2000))
    if len(value)!=2:raise Fail('GET_STATUS incomplet')
    return struct.unpack('<H',value)[0]&1

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    report=dict(passed=False,physical_sd_writes=0,cases=[],cleanup_errors=[])
    dev=None;detached=claimed=False;recover_needed=False
    try:
        snap=console_snapshot();report['usb']=snap
        if not snap or snap['speed_mbps']!=480:raise Fail('Console 11252024 HS absente')
        dev=usb.core.find(idVendor=VID,idProduct=PID,bus=snap['bus'],address=snap['address'])
        if dev is None:raise Fail('Console absente')
        ports=[p.device for p in list_ports.comports() if (p.vid,p.pid,p.serial_number)==(VID,PID,'11252024')]
        if len(ports)!=1:raise Fail('Port CDC ambigu')
        if dev.is_kernel_driver_active(2):dev.detach_kernel_driver(2);detached=True
        usb.util.claim_interface(dev,2);claimed=True
        with serial.Serial(ports[0],115200,timeout=.05,exclusive=True) as port:
            identity=command(port,'?','USBDISK R')
            if 'R4 ' not in identity or 'BOT_GUARD=1' not in identity:raise Fail('Firmware corrigé R4 requis')
            command(port,'d','USBDISK MEDIA=DDR')
            disk=Disk(dev);require_ddr(port,disk)
            payload=bytes((i*73+17)&255 for i in range(512))
            if disk.write(32768,payload)!=(0,0):raise Fail('Écriture DDR témoin refusée')
            initial=state(port);report['initial']=initial
            cdb=struct.pack('>BBIBHB',0x2a,0,32768,0,1,0)
            cbw=struct.pack('<IIIBBB',0x43425355,0x20261008,512,0,0,10)+cdb.ljust(16,b'\0')
            cases=[('signature',bytes(4)+cbw[4:]),('court',cbw[:-1]),('long',cbw+b'\0'),('vide',b''),
                   ('cdb_court',cbw[:14]+b'\x01'+cbw[15:]),('flags_reserves',cbw[:12]+b'\x01'+cbw[13:]),
                   ('longueur_reservee',cbw[:14]+b'\xea'+cbw[15:]),('lun',cbw[:13]+b'\x01'+cbw[14:]),
                   ('donnees_courtes',cbw)]
            for name,bad in cases:
                require_ddr(port,disk);before=state(port);recover_needed=True
                dev.write(0x01,bad,timeout=2000)
                if name=='donnees_courtes':dev.write(0x01,bytes(16),timeout=2000)
                deadline=time.monotonic()+2
                while True:
                    during=state(port)
                    if int(during['PORT'],16)&0x400:break
                    if time.monotonic()>=deadline:raise Fail(f'{name} : verrou BOT absent')
                expect_stall(lambda:dev.read(0x81,512,timeout=2000))
                if not halted(dev,0x81) or not halted(dev,0x01):raise Fail('GET_STATUS sans HALT')
                dev.clear_halt(0x81);dev.clear_halt(0x01)
                expect_stall(lambda:dev.read(0x81,512,timeout=2000))
                expect_stall(lambda:dev.write(0x01,cbw,timeout=2000))
                if state(port)['WRITTEN']!=before['WRITTEN']:raise Fail('Écriture malgré CBW refusé')
                dev.ctrl_transfer(0x21,0xff,0,2,None,timeout=2000)
                dev.clear_halt(0x81);dev.clear_halt(0x01)
                deadline=time.monotonic()+3
                while True:
                    after=state(port)
                    if int(after['RESETS'])>int(before['RESETS']) and not (int(after['PORT'],16)&0x400):break
                    if time.monotonic()>=deadline:raise Fail('Reset BOT non traité')
                recover_needed=False
                if halted(dev,0x81) or halted(dev,0x01):raise Fail('HALT persistant après reset')
                status,residue,data=disk.read(32768,1)
                if status or residue or data!=payload:raise Fail('DDR altérée après commande malformée')
                row=dict(name=name,passed=True,cdc_during_error=during,after_reset=after)
                report['cases'].append(row);print('PASS',name,flush=True)
            report['final']=state(port)
            for key in ('TIMEOUTS','LOSSES','WRITTEN'):
                if report['final'][key]!=initial[key]:raise Fail(f'Compteur inattendu : {key}')
            report['passed']=True
    except Exception as error:
        report['error']=str(error);raise
    finally:
        actions=[]
        if recover_needed and dev is not None:
            actions += [lambda:dev.ctrl_transfer(0x21,0xff,0,2,None,timeout=2000),lambda:dev.clear_halt(0x81),lambda:dev.clear_halt(0x01)]
        if claimed:actions.append(lambda:usb.util.release_interface(dev,2))
        if detached:actions.append(lambda:dev.attach_kernel_driver(2))
        if dev is not None:actions.append(lambda:usb.util.dispose_resources(dev))
        for action in actions:
            try:action()
            except Exception as error:report['cleanup_errors'].append(str(error));report['passed']=False
        (args.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    if not report['passed']:raise Fail('Nettoyage incomplet')

if __name__=='__main__':main()
