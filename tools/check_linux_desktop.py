#!/usr/bin/env python3
"""Exercise native hardware text, layout changes and concurrent game/terminal.

No SD writes or FPGA programming. Run against Linux already booted on ax15.
"""
import argparse
import json
from pathlib import Path
import re
import time
import serial
from check_gpu_reloads import wait_console
from check_linux import command


def display(data):
    line=re.search(rb'^DISPLAY mode=.*$',data.replace(b'\r',b''),re.M)
    if not line:raise RuntimeError('Missing display telemetry: '+repr(data[-1200:]))
    fields=dict(re.findall(rb'(\w+)=([0-9a-f]+)',line[0]))
    return {k.decode():int(v,16 if k in (b'usb',b'crc') else 10) for k,v in fields.items()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    port,usb=wait_console()
    if usb['speed_mbps']!=480:raise RuntimeError(usb)
    report={'passed':False,'usb':usb,'physical_sd_writes':0,'commands':[]}
    background_started=False
    with serial.Serial(port,115200,timeout=.15,exclusive=True) as uart:
        def run(name,cmd,timeout=40):
            status,data=command(uart,cmd,timeout)
            (a.out/(name+'.log')).write_bytes(data)
            print(data.decode(errors='replace'),flush=True)
            report['commands'].append({'name':name,'exit':status})
            if status:raise RuntimeError(f'{name}: exit {status}')
            return data
        try:
            uart.write(b'\n');time.sleep(.3);(a.out/'initial.log').write_bytes(uart.read(16000))
            before=display(run('before','prodockctl display'))
            run('system','uname -a; ls /dev/prodock-display /dev/prodock-gpu /dev/tty1')
            run('fb0_guard','if dd if=/dev/fb0 of=/tmp/fb-probe bs=1 count=1 2>/tmp/fb-error; then false; else grep -i "not supported" /tmp/fb-error; fi')
            # Test output itself is mirrored to tty1 by the PTY daemon.
            # Hold it in a file until all reference frames were sampled.
            text=run('text_pixels','prodock-text-test > /tmp/text-test.log; rc=$?; cat /tmp/text-test.log; test "$rc" = 0')
            if b'PRODOCK_TEXT_PIXELS_OK poses=4 pixels=1536000' not in text:raise RuntimeError('Text pixel proof absent')
            if b'TEXT_SPARSE_OK trials=8' not in text:raise RuntimeError('Sparse text bank reuse proof absent')
            game=run('game','prodock-game --demo --frames 180',60)
            rate=re.search(rb'PRODOCK_GAME_RATE frames=180 seconds=([0-9.]+) fps=([0-9.]+)',game)
            if not rate:raise RuntimeError('Missing game frame-rate measurement')
            report['game_fps']=float(rate[2])
            after=display(run('after_game','prodockctl display'))
            report['after_game']=after
            if report['game_fps']<45:raise RuntimeError('Game below 45 FPS')
            if (after['presents']-before['presents'])&0xffffffff!=180:raise RuntimeError('Missing game frames')
            background_started=True
            run('background','prodock-game --demo --frames 3000 > /tmp/game.log & echo $! > /tmp/game.pid')
            for mode,number,dims in [('game',1,(50,15)),('console',2,(100,30)),('split',0,(50,15))]*2:
                index=len(report['commands'])
                run(f'layout_{index}',f'prodockctl layout {mode}')
                info=display(run(f'display_{index}','prodockctl display'))
                if info['mode']!=number or (info['cols'],info['rows'])!=dims:raise RuntimeError('Layout not applied')
            run('shell_live','printf "LINUX_SHELL_WHILE_GPU_RUNNING\\n"')
            run('stop_game','kill -TERM `cat /tmp/game.pid`; sleep 1; cat /tmp/game.log')
            background_started=False
            final=display(run('final','prodockctl display'))
            if final['errors'] or final['fault'] or final['invalid'] or final['sprites'] or final['uf']!=before['uf']:
                raise RuntimeError(f'Display errors: {before} -> {final}')
            if final['line']>=2556:raise RuntimeError('LCD line budget exceeded')
            if final['text']<=before['text'] or final['presents']<=after['presents']:raise RuntimeError('Terminal/game did not progress')
            submitted=((final['sent']-before['sent']) & 0xffffffff)
            if (final['done']-before['done'])&65535 != submitted&65535:
                raise RuntimeError('Completed command counter disagrees with submissions')
            if final['usb']&0x60!=0x60 or final['usb']&0x80:raise RuntimeError('USB state degraded')
            report.update(passed=True,before=before,final=final,text_pixels=1536000,submitted=submitted)
        except Exception as e:
            report['error']=str(e)
            if hasattr(e,'data'):(a.out/'timeout.log').write_bytes(e.data)
            raise
        finally:
            if background_started:
                try:
                    status,data=command(uart,'p=`cat /tmp/game.pid`; if test "`cat /proc/$p/comm`" = prodock-game; then kill -TERM "$p"; fi',10)
                    (a.out/'cleanup.log').write_bytes(data)
                    report['cleanup_exit']=status
                except Exception as e:report['cleanup_error']=str(e)
            (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
