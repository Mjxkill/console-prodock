#!/usr/bin/env python3
"""Volatile R17 -> G3D1 Linux transition on Pro Dock 11252024 only.

Keep LUMA running until all files/recovery inputs are checked. No FPGA or
physical SD/flash writes. A successful boot leaves a simple GPU test visible;
game deployment is a separate, identified step. On failure restore R17 and
the previously tested LUMA2D exterior, never silently substitute NEBULA.
"""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

import serial
from prodock_transport import Transport, RECEIVER_SHA

FPGA_SHA='fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f'
MANIFEST_SHA='2b6c8b61a920ea45fcc189a44c5af7f4d6941b87c5d9a814af87021f478c091f'
RELEASE='6.12.112-prodock-luma3d-g3d1-r1'
SETUP_SHA='909ec0f10dbb03becab161c8d2480a052d24f7859bad4ab243591331ee7edc78'
WARM_SHA='95b37af2dd390dc57333aba16318b95b11fcf7ccf9e8e36e2c726049e0c6c044'
PORT='/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00'
ROLLBACK={'luma-riscv':'23f096f081d81d958a81f911a9b30441d51f27f0e377f10682f0bd7024ad7218',
          'luma.lz4':'11309f1676757c64c907304fe16c69b47b790f58ecbef05dc9a1e170c0852c1b',
          'world_02.lz4':'6ca43179b7f8310bea57179648e61d04fd470a3eb112fe91fca3964972f764d3',
          'uart-receiver':RECEIVER_SHA}


def meta(path):
    data=path.read_bytes()
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def package(pack):
    manifest=json.loads((pack/'manifest.json').read_text())
    assert manifest['board']=='Tang Mega 138K Pro Dock' and manifest['abi']==1
    assert manifest['load']==manifest['entry']==0x07c00000 and manifest['kernel']==0x08000000
    records={}
    for name in ['opensbi/platform/generic/firmware/fw_payload.bin','payload.rle.bin']:
        records[name]=meta(pack/name)
        assert records[name]==manifest['files'][name] and 0<records[name]['bytes']<=0x2000000
    lm=manifest['launcher_packed']; records['launch_packed.bin']=meta(pack/'launch_packed.bin')
    assert lm['entry']==0xa000000c and lm['load']==0xa0000000 and lm['stage']==0x10000000
    assert records['launch_packed.bin']=={k:lm[k] for k in ['bytes','sha256']}
    assert 12<lm['bytes']<0xf000, 'Launcher would overlap warm parking page'
    records['manifest.json']=meta(pack/'manifest.json')
    return records


def display(data):
    lines=re.findall(rb'^DISPLAY [^\r\n]+',data,re.M)
    assert len(lines)==1,repr(data[-1500:])
    values={k.decode():int(v) for k,v in re.findall(rb'\b(errors|uf|invalid|sprites|fault)=(\d+)\b',lines[0])}
    assert set(values)=={'errors','uf','invalid','sprites','fault'} and not any(values.values()),values
    return values


def identities(a):
    files={'controller':meta(Path(__file__)),
           'transport':meta(Path(__file__).with_name('prodock_transport.py')),
           'warm':meta(a.warm_bin),'setup':meta(a.setup),
           'kernel':package(a.pack),'rollback_kernel':package(a.rollback_pack),
           'rollback_files':{n:meta(a.rollback_bundle/n) for n in ROLLBACK},
           'loader':{n:meta(a.root/'tools'/n) for n in ['load_linux.py','load_ilm.py','check_linux.py','check_gpu_reloads.py']}}
    assert files['kernel']['manifest.json']['sha256']==MANIFEST_SHA
    assert files['rollback_kernel']['manifest.json']['sha256']=='d9a4df8df1cb3fe8c7ef6d76e98d17d8e78913a25c8a48e7c4e63451c49fce0a'
    assert files['rollback_kernel']['opensbi/platform/generic/firmware/fw_payload.bin']['sha256']=='7d8cb19e0cb032cc73bc271172dae67e50354746e4ce27f529b5e00a08b41f4c'
    assert files['warm']['sha256']==WARM_SHA and files['warm']['bytes']==446
    assert files['setup']['sha256']==SETUP_SHA
    assert all(files['rollback_files'][n]['sha256']==digest for n,digest in ROLLBACK.items())
    assert meta(a.root/'tang/impl/gpu_geometry_g22r0/impl/pnr/console_gpu_geometry_g22r0.fs')['sha256']==FPGA_SHA
    return files


def jlink(a,out,script):
    commands=['exec InhibitConnectRetries = 1','exec DisableFlashDL','exec DisableFlashBPs',
              'exec SetAllowFlashCache = 0','connect','h','speed 1000',
              'w4 0xa0207e00 0','w4 0xa0207e04 0',
              f'loadfile {a.warm_bin.resolve()} 0xa000f000 noreset',
              f'verifybin {a.warm_bin.resolve()} 0xa000f000',
              'SetPC 0xa000f000','g','sleep 500','h','mem32 0xa0207e00 2','g','q']
    script.write_text('\n'.join(commands)+'\n')
    with (out/'jlink.log').open('x') as log:
        proc=subprocess.run(['JLinkExe','-SelectEmuBySN','506005083','-Device','A25',
             '-If','JTAG','-Speed','100','-JTAGConf','-1,-1','-NoGui','1','-ExitOnError','1',
             '-JLinkScriptFile',str(a.setup.resolve()),'-CommanderScript',str(script.resolve())],
             stdout=log,stderr=subprocess.STDOUT,timeout=90)
    content=(out/'jlink.log').read_text()
    assert proc.returncode==0 and 'Verify successful.' in content and 'LUMA_WARM_CSR_READY' in content,content[-2500:]
    assert not re.search(r'Error:|Script error|Cannot connect',content),content[-2500:]
    assert re.search(r'A0207E00\s*=\s*5741524D\s+00000000',content,re.I), 'No fresh DLM ready status'


def warm_and_boot(a,pack,out):
    out.mkdir()
    with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
        uart.reset_input_buffer()
        jlink(a,out,out/'warm.jlink')
        until=time.monotonic()+10; data=bytearray()
        while time.monotonic()<until:
            data.extend(uart.read(4096))
            if b'PRODOCK WARM PARK M=3 SATP=0 CACHE=OFF READY\r\n' in data:
                break
        (out/'warm_uart.log').write_bytes(data)
        assert b'PRODOCK WARM PARK M=3 SATP=0 CACHE=OFF READY\r\n' in data
        assert b'WARM PARK FAIL' not in data
    # The historical loader now sees a known M-mode parking program, not Linux.
    with (out/'loader.log').open('x') as log:
        proc=subprocess.run([sys.executable,str(a.root/'tools/load_linux.py'),
            '--pack',str(pack.resolve()),'--packed','--jtag-speed','4000',
            '--out',str((out/'boot').resolve()),'--seconds','180'],
            cwd=a.root,stdout=log,stderr=subprocess.STDOUT,timeout=1500)
    assert proc.returncode==0 and json.loads((out/'boot/result.json').read_text())['passed']


def luma_state(tx,name):
    data=tx.run(name,'p=`cat /tmp/luma-live.pid`; if test -d /proc/$p; then cat /proc/$p/comm; cat /proc/$p/status; else echo STOPPED; fi')
    if re.search(rb'^STOPPED\r?$',data,re.M):
        return 'absent'
    assert re.search(rb'^luma-riscv\r?$',data,re.M), 'PID now belongs to another process'
    state=re.search(rb'^State:\s+([A-Z])\s',data,re.M)
    assert state,'Missing process state'
    return 'dead' if state[1] in (b'Z',b'X') else 'alive'


def live_luma(tx,prefix):
    assert luma_state(tx,prefix+'_process')=='alive', 'LUMA process exited or became a zombie'
    first=tx.run(prefix+'_first','prodockctl display')
    display(first)
    time.sleep(3)
    assert luma_state(tx,prefix+'_process_again')=='alive'
    second=tx.run(prefix+'_second','prodockctl display')
    counts=display(second)
    presents=lambda data:int(re.search(rb'^DISPLAY .*?\bpresents=(\d+)\b',data,re.M)[1])
    assert (presents(second)-presents(first))&0xffffffff, 'LUMA is not presenting new frames'
    return counts


def restart_luma(tx):
    tx.run('luma_launch','/tmp/luma-riscv --demo --no-save --world 2 > /tmp/luma-live.log 2>&1 & echo $! > /tmp/luma-live.pid; echo 2 > /tmp/luma-live.world')
    for i in range(8):
        time.sleep(5)
        data=tx.run('luma_start_'+str(i),'p=`cat /tmp/luma-live.pid`; test "`cat /proc/$p/comm`" = luma-riscv && cat /tmp/luma-live.log')
        if b'LUMA_START worlds=36 mode=benchmark board=800x480 ' in data:
            break
    else:
        raise RuntimeError('Restored LUMA did not start')
    return live_luma(tx,'luma_live')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--pack',type=Path,required=True)
    p.add_argument('--rollback-pack',type=Path,required=True)
    p.add_argument('--rollback-bundle',type=Path,required=True)
    p.add_argument('--warm-bin',type=Path,required=True)
    p.add_argument('--setup',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--check-only',action='store_true')
    p.add_argument('--prepared',type=Path)
    a=p.parse_args(); files=identities(a)
    a.out.mkdir(parents=True,exist_ok=False)
    if a.check_only:
        (a.out/'prepared.json').write_text(json.dumps(files,indent=2)+'\n')
        print('Identities and recovery files PASS; no hardware access')
        return
    assert a.prepared and json.loads(a.prepared.read_text())==files, 'Prepared identities changed'
    lock=open('/tmp/prodock-diagnostic.lock','a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def interrupted(signum,frame):
        raise KeyboardInterrupt('Signal '+str(signum))
    signal.signal(signal.SIGTERM,interrupted)
    signal.signal(signal.SIGHUP,interrupted)
    sys.path.insert(0,str(a.root/'tools'));from check_linux import command
    report={'passed':False,'identities':files,'fpga_sha256':FPGA_SHA,
            'runtime_fpga_identity':'Continuity from G22r0 restoration; no hardware hash register',
            'fpga_writes':0,'physical_sd_writes':0,'flash_writes':0,'kernel_ram_reload':True,
            'user_final_preference':'Leave LUMA visible after successful deployment; no NEBULA restoration'}
    stopped=False; transition=False
    try:
        with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
            tx=Transport(uart,command,a.out)
            uart.write(b'\n');time.sleep(.2);uart.read(16000)
            before=tx.run('before','uname -r; prodockctl display; ps; cat /proc/mounts; cat /tmp/luma-live.pid; cat /tmp/luma-live.world')
            assert re.search(rb'^6\.12\.112-prodock\r?$',before,re.M)
            assert b'tmpfs /tmp tmpfs ' in before and not re.search(rb'^/dev/mmc\S* ',before,re.M)
            report['initial_display']=display(before)
            tx.run('identify_game','p=`cat /tmp/luma-live.pid`; test "$p" = 1343 && test "`cat /proc/$p/comm`" = luma-riscv && test "`cat /tmp/luma-live.world`" = 2')
            stopped=True
            tx.run('stop_game','p=`cat /tmp/luma-live.pid`; test "`cat /proc/$p/comm`" = luma-riscv && kill -TERM "$p" && sleep 1 && test ! -d /proc/$p')
            info=tx.run('gpu_released','prodockctl info; prodockctl display')
            assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in info
            report['released_display']=display(info)
        transition=True
        print('WARM transition: Linux stopped; entering verified M-mode park',flush=True)
        warm_and_boot(a,a.pack,a.out/'candidate')
        with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
            tx=Transport(uart,command,a.out)
            uart.write(b'\n');time.sleep(.3);uart.read(16000)
            state=tx.run('candidate_system','uname -r; prodockctl info; prodockctl display; cat /proc/mounts')
            assert re.search(rb'^'+RELEASE.encode()+rb'\r?$',state,re.M)
            assert b'tmpfs /tmp tmpfs ' in state and not re.search(rb'^/dev/mmc\S* ',state,re.M)
            report['candidate_display']=display(state)
            # Existing reference raster oracle, BEFORE the new geometry scene.
            raster=tx.run('raster_oracle','prodockctl demo',90)
            assert b'PRODOCK_GPU_PIXELS_OK pixels=384000' in raster
            report['after_raster_display']=display(tx.run('raster_display','prodockctl display'))
        report['passed']=True
        report['left_running']='G3D1 candidate Linux; reference raster test visible; 3D deployment next'
    except BaseException as error:
        report['error']=repr(error)
        if stopped:
            try:
                recovery=a.out/'recovery';recovery.mkdir()
                if transition:
                    warm_and_boot(a,a.rollback_pack,recovery/'r17')
                with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
                    tx=Transport(uart,command,recovery)
                    uart.write(b'\n');time.sleep(.3);uart.read(16000)
                    if transition:
                        state=tx.run('r17_system','uname -r; prodockctl info; cat /proc/mounts')
                        assert re.search(rb'^6\.12\.112-prodock\r?$',state,re.M)
                        tx.bootstrap(a.rollback_bundle/'uart-receiver')
                        report['restored_files']=[tx.transfer(a.rollback_bundle/n,n) for n in ['luma-riscv','luma.lz4','world_02.lz4']]
                    else:
                        # TERM may have succeeded before its acknowledgement was lost.
                        state=luma_state(tx,'old_process_state')
                        for i in range(5):
                            if state!='dead':
                                break
                            time.sleep(1)
                            state=luma_state(tx,'old_process_reap_'+str(i))
                        assert state!='dead', 'Stopped process not reaped; do not claim live restoration'
                        if state=='alive':
                            report['recovery_display']=live_luma(tx,'old_live')
                            report['restored_luma']=True
                    if not report.get('restored_luma'):
                        report['recovery_display']=restart_luma(tx)
                        report['restored_luma']=True
            except BaseException as recovery_error:
                report['recovery_error']=repr(recovery_error)
        raise
    finally:
        lock.close()
        (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='identities'},indent=2),flush=True)


if __name__=='__main__':
    main()
