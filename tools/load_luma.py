#!/usr/bin/env python3
"""Load the autonomous adventure on Pro Dock FTDI 2023112818/J-Link 506005083.

Run on ax15 in the console validation tree. SRAM/ILM/DDR only. --reload
first restores the archived R31 FPGA. No reset is issued through J-Link:
DDR/USB stay initialized. Never loadfile ITCM, treated as flash by A25.
"""
import argparse,hashlib,json,subprocess,time
from pathlib import Path
import serial
from check_gpu_reloads import target_busdev,wait_console,console_snapshot
ROOT=Path(__file__).resolve().parents[1]
R31='60806fa2e988641e5b67ddcc5b13873c5b39c87621d5f1a23bbcf5e80b6d6aee'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reload',action='store_true');p.add_argument('--firmware-only',action='store_true');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.reload and a.firmware_only:p.error('--reload requires asset loading')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    pack=ROOT/'assets/luma/packed';meta=json.loads((pack/'firmware.json').read_text());assets=pack/'luma.bin';fw=pack/'luma_fw.bin';fpga=ROOT/'bitstreams/console_gpu_v1_800.fs'
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    assert meta['fpga_sha256']==R31==sha(fpga)
    assert meta['sha256']==sha(fw) and meta['assets_sha256']==sha(assets)
    assert meta['load']==0xa0000000 and meta['load']<=meta['entry']<meta['load']+len(fw.read_bytes())<=0xa0010000
    print('Target Pro Dock',target_busdev(),flush=True)
    if a.reload:
        before=console_snapshot()
        loader=ROOT/'bin/openFPGALoader'
        with (out/'fpga.log').open('w') as log:
            subprocess.run([str(loader),'--busdev-num',target_busdev(),'-b','tangmega138k','-m',str(fpga)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        port,snap=wait_console(before)
    else:port,snap=wait_console()
    assert snap['speed_mbps']==480
    (out/'usb.json').write_text(json.dumps(snap,indent=2)+'\n')
    uart=serial.Serial(port,115200,timeout=.3,exclusive=True)
    uart.reset_input_buffer();uart.write(b'?');uart.flush();time.sleep(.2);identity=uart.read(1000)
    (out/'before.txt').write_bytes(identity)
    assert b'MegaPro GPU' in identity or b'LUMA R' in identity,identity
    uart.write(b'c' if b'MegaPro GPU' in identity else b'P');uart.flush();time.sleep(.2);uart.reset_input_buffer()
    commands=['exec InhibitConnectRetries = 1','exec DisableFlashDL','exec DisableFlashBPs','exec SetAllowFlashCache = 0','connect','h','speed 1000']
    if not a.firmware_only:commands += [f'loadfile {assets} 0x04000000 noreset',f'verifybin {assets} 0x04000000']
    commands += [f'loadfile {fw} 0xa0000000 noreset',f'verifybin {fw} 0xa0000000',f'SetPC 0x{meta["entry"]:08x}','g','q']
    script=out/'load.jlink';script.write_text('\n'.join(commands)+'\n')
    start=time.monotonic();print('Downloading Luma into RAM…',flush=True)
    with (out/'jlink.log').open('w') as log:
        result=subprocess.run(['JLinkExe','-SelectEmuBySN','506005083','-Device','A25','-If','JTAG','-Speed','100','-JTAGConf','-1,-1','-NoGui','1','-ExitOnError','1','-CommanderScript',str(script)],stdout=log,stderr=subprocess.STDOUT,timeout=1200)
    content=(out/'jlink.log').read_text();assert result.returncode==0 and 'Verify successful.' in content and 'Error:' not in content,content[-3000:]
    print('Download complete',round(time.monotonic()-start,1),'seconds',flush=True)
    responses=bytearray();deadline=time.monotonic()+12
    while time.monotonic()<deadline:
        uart.write(b'?S');uart.flush();responses.extend(uart.read(4000))
        if b'LUMA R' in responses and b'errors=0' in responses:break
    (out/'startup.txt').write_bytes(responses);print(responses.decode(errors='replace'),flush=True)
    uart.close();assert b'LUMA R' in responses and b'errors=0' in responses,'Firmware did not start; inspect J-Link/USB logs, restore R31 if necessary'
    (out/'result.json').write_text(json.dumps(dict(status='started',seconds=time.monotonic()-start,firmware=meta,usb=snap),indent=2)+'\n')
if __name__=='__main__':main()
