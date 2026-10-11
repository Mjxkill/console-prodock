#!/usr/bin/env python3
"""Charge une application téléchargeable en ILM sur la Pro Dock (FTDI 2023112818, J-Link 506005083).

À lancer sur ax15, dans l'arbre de validation. Tout est volatile : --fs charge d'abord un bitstream
en SRAM (la flash n'est pas modifiée), puis J-Link écrit le programme à 0xa0000000 et le lance,
sans reset : la DDR et l'USB restent initialisés. Le texte attendu est guetté sur le port série.
"""
import argparse,hashlib,json,re,subprocess,time
from pathlib import Path
import serial
from check_gpu_reloads import target_busdev,wait_console,console_snapshot
ROOT=Path(__file__).resolve().parents[1]

def require(condition,detail):
    if not condition:raise RuntimeError(str(detail))

def identify_console(uart):
    """Read through queued animation logs before deciding how to stop firmware."""
    uart.reset_input_buffer()
    uart.write(b'?');uart.flush()
    response=bytearray();deadline=time.monotonic()+8
    while time.monotonic()<deadline and len(response)<262144:
        response.extend(uart.read(4096))
        for line in bytes(response).split(b'\n')[:-1]:
            if b'USBDISK R' in line:return bytes(response),b'q'
            if b'MegaPro GPU' in line:return bytes(response),b'c'
            if b'LUMA R' in line or b'ORBITAL R' in line or b'ASTRA R' in line or b'ASTRILLA R' in line:return bytes(response),b'P'
    raise RuntimeError(f'Identité console absente ; aucun chargement effectué : {bytes(response[-2000:])!r}')

def quiesce_console(uart, pause, timeout=8):
    """Require the firmware's acknowledgement before halting the CPU.

    USBDISK reports actual hardware ownership through SERVING, including
    when it was already released. GPU command c stops all animation modes.
    No J-Link action may follow a timeout or an incomplete acknowledgement.
    """
    markers={b'P': (b'LUMA PAUSED', b'ORBITAL PAUSED', b'ASTRA PAUSED', b'ASTRILLA PAUSED'), b'c': (b'RASTER PAUSED',)}
    if pause not in (*markers,b'q'):
        raise RuntimeError(f'Commande de pause inconnue : {pause!r}')
    uart.reset_input_buffer();uart.write(pause);uart.flush()
    answer=bytearray();deadline=time.monotonic()+timeout;next_query=time.monotonic()+(.5 if pause!=b'q' else 0)
    while time.monotonic()<deadline and len(answer)<262144:
        # Pause/release are idempotent. Retrying tolerates a dropped CDC OUT
        # around a host USB reset, but never bypasses the exact ACK below.
        if pause!=b'q' and time.monotonic()>=next_query:
            uart.write(pause);uart.flush();next_query=time.monotonic()+.5
        if pause==b'q' and time.monotonic()>=next_query:
            uart.write(b's');uart.flush();next_query=time.monotonic()+.2
        answer.extend(uart.read(4096))
        for line in bytes(answer).split(b'\n')[:-1]:
            # Some AE350 printf paths append CR after LF as well as before it.
            # Normalize only CR framing, still require a complete exact line.
            line=line.strip(b'\r')
            if pause==b'q':
                if line.startswith(b'USBDISK MEDIA=') and re.search(rb'\bSERVING=0\b',line):
                    return bytes(answer)
            elif any(line.rstrip(b'\r')==marker for marker in markers[pause]):
                return bytes(answer)
    raise RuntimeError(f'Arrêt non acquitté ; aucun chargement effectué : {bytes(answer[-2000:])!r}')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bin',type=Path,required=True);p.add_argument('--entry',type=lambda v:int(v,0),required=True)
    p.add_argument('--fs',type=Path,help='bitstream à charger en SRAM avant le programme');p.add_argument('--expect',default='READY');p.add_argument('--seconds',type=float,default=30)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);program=a.bin.read_bytes()
    require(0xa0000000<=a.entry<0xa0000000+len(program)<=0xa0010000, 'Programme ou entrée hors ILM')
    print('Target Pro Dock',target_busdev(),flush=True)
    if a.fs:
        before=console_snapshot()
        with (out/'fpga.log').open('w') as log:
            subprocess.run([str(ROOT/'bin/openFPGALoader'),'--busdev-num',target_busdev(),'-b','tangmega138k','-m',str(a.fs)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        port,snap=wait_console(before)
    else:port,snap=wait_console()
    require(snap['speed_mbps']==480,snap)
    uart=serial.Serial(port,115200,timeout=.3,exclusive=True)
    identity,pause=identify_console(uart)
    (out/'before.txt').write_bytes(identity)
    # Le programme en place est mis en pause ; s'il sert le disque USB, il le rend d'abord au matériel
    # (q), sinon une commande du PC resterait sans réponse quand J-Link arrête le processeur.
    try:
        (out/'paused.txt').write_bytes(quiesce_console(uart,pause))
    except Exception:
        uart.close();raise
    commands=['exec InhibitConnectRetries = 1','exec DisableFlashDL','exec DisableFlashBPs','exec SetAllowFlashCache = 0','connect','h','speed 1000',
              f'loadfile {a.bin.resolve()} 0xa0000000 noreset',f'verifybin {a.bin.resolve()} 0xa0000000',f'SetPC 0x{a.entry:08x}','g','q']
    (out/'load.jlink').write_text('\n'.join(commands)+'\n')
    with (out/'jlink.log').open('w') as log:
        result=subprocess.run(['JLinkExe','-SelectEmuBySN','506005083','-Device','A25','-If','JTAG','-Speed','100','-JTAGConf','-1,-1','-NoGui','1','-ExitOnError','1','-CommanderScript',str(out/'load.jlink')],stdout=log,stderr=subprocess.STDOUT,timeout=300)
    content=(out/'jlink.log').read_text();require(result.returncode==0 and 'Verify successful.' in content and 'Error:' not in content,content[-2000:])
    answer=bytearray();deadline=time.monotonic()+a.seconds
    while time.monotonic()<deadline:
        answer.extend(uart.read(4000))
        # The AE350 printf stream can end each LF with an additional CR.
        # Match a completed line instead of waiting out the whole timeout.
        if any(a.expect.encode() in line for line in bytes(answer).replace(b'\r',b'').split(b'\n')[:-1]):
            time.sleep(.5);answer.extend(uart.read(4000));break
    uart.close();(out/'console.txt').write_bytes(answer);print(answer.decode(errors='replace'),flush=True)
    require(a.expect.encode() in answer,'texte attendu absent')
    (out/'result.json').write_text(json.dumps(dict(status='started',usb=snap,sha256=hashlib.sha256(program).hexdigest(),fs=str(a.fs) if a.fs else None),indent=2)+'\n')
if __name__=='__main__':main()
