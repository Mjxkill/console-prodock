#!/usr/bin/env python3
"""NEBULA board acceptance: reference frames, controls, layouts and endurance.

Requires Linux with NEBULA already loaded, a free CDC port and no running
game. Never programs FPGA/flash or writes SD. Leaves a demo running on pass.
"""
import argparse
import json
from pathlib import Path
import re
import time
import serial
from check_gpu_reloads import wait_console
from check_linux import command

FIELDS=('mode cols rows text presents sent frames done errors uf line invalid sprites usb fault crc '
        'feed_us wait_us cache_us present_us text_us').split()


def display(data):
    """Reject malformed transport; never repair or deduplicate received bytes."""
    pattern=b'DISPLAY '+b' '.join(k.encode()+b'='+
        (b'([0-9a-f]{8})' if k in ('usb','crc') else b'([0-9]+)') for k in FIELDS)
    lines=[line for line in data.replace(b'\r',b'').splitlines() if line.startswith(b'DISPLAY')]
    m=re.fullmatch(pattern,lines[0]) if len(lines)==1 else None
    if not m:raise ValueError('Malformed display telemetry: '+repr(data[-1200:]))
    return {k:int(v,16 if k in ('usb','crc') else 10) for k,v in zip(FIELDS,m.groups())}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=190)
    p.add_argument('--retry-reads',action='store_true',help='Retry malformed read-only telemetry; explicitly mark serial_clean=false')
    p.add_argument('--runtime-only',action='store_true',help='Resume controls/layout/endurance after reference frames and benchmarks already passed')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    port,usb=wait_console();assert usb['speed_mbps']==480,usb
    report={'passed':False,'serial_clean':True,'rejected_reads':[], 'usb':usb,'physical_sd_writes':0,'references':[],'benchmarks':[], 'interactive':[], 'samples':[]}
    report['scope']='runtime' if a.runtime_only else 'all'
    background=False;interactive_active=False
    with serial.Serial(port,115200,timeout=.1,exclusive=True) as uart:
        def run(name,text,timeout=90):
            status,data=command(uart,text,timeout);(a.out/(name+'.log')).write_bytes(data)
            if status:raise RuntimeError((name,status,data[-2000:]))
            return data
        def healthy(s):
            assert not(s['errors'] or s['fault'] or s['uf'] or s['invalid'] or s['sprites']),s
            assert s['line']<2556 and s['usb']&0x60==0x60 and not s['usb']&0x480,s
        def reading(name,cmd,parse):
            # Only read-only commands may be retried. Execution, input and GPU
            # operations are never replayed, and all rejected bytes stay logged.
            for attempt in range(8 if a.retry_reads else 1):
                data=run(name+f'_read{attempt}',cmd)
                try:return parse(data)
                except ValueError as error:
                    report['serial_clean']=False
                    report['rejected_reads'].append({'name':name,'attempt':attempt,'error':str(error)})
                    if not a.retry_reads:raise
            raise RuntimeError('Repeated malformed telemetry: '+name)
        def state(name):return reading(name,'prodockctl display',display)
        def ready(name):
            # CRC verification and atlas construction precede NEBULA_START.
            # A fixed two-second delay raced that initialization under Linux.
            run(name+'_ready','for i in 1 2 3 4 5 6 7 8 9 10; do grep -q "^NEBULA_START" /tmp/nebula-check.log && break; sleep 3; done; grep -q "^NEBULA_START" /tmp/nebula-check.log',45)
        def stop_game(name):
            return run(name,'kill -TERM `cat /tmp/nebula-check.pid`; sleep 1')
        try:
            initial=state('initial');healthy(initial);report['initial']=initial
            for name,options,crc,lcd in [
                ('wave700','--pose 700','7053a712','d6deb25f'),
                ('boss310','--boss --pose 310','7bf9f5b4','2a99c4db'),
                ('nova5740','--pose 5740','2a9e131f','1eab5d1f')][3 if a.runtime_only else 0:]:
                run(name+'_start',f'nebula --demo {options} --frames 10000 > /tmp/nebula-check.log & echo $! > /tmp/nebula-check.pid')
                background=True;ready(name);time.sleep(.3)
                sums=[]
                for i in range(3):
                    s=state(name+f'_lcd{i}');healthy(s)
                    assert s['mode']==1,s
                    sums.append(f"{s['crc']:08x}")
                stop_game(name+'_stop');background=False
                def parse_crc(data):
                    m=re.search(rb'^NEBULA_FRAME_CRC32 pose=\d+ crc=([0-9a-f]{8}) pixels=96000\r?$',data,re.M)
                    if not m:raise ValueError('Malformed frame CRC')
                    return m[1].decode()
                actual=reading(name+'_crc','cat /tmp/nebula-check.log',parse_crc)
                result={'scene':name,'frame_expected':crc,'frame_actual':actual,'lcd_expected':lcd,'lcd_samples':sums}
                report['references'].append(result);print(result,flush=True)
                assert actual==crc and sums==[lcd]*3,result
            for name,args in ([] if a.runtime_only else [('fullscreen',''),('split','--split')]):
                run(name,'nebula --demo '+args+' --frames 600 > /tmp/nebula-check.log',90)
                def parse_rate(data):
                    m=re.search(rb'^NEBULA_RATE frames=600 seconds=([0-9.]+) fps=([0-9.]+) commands=(\d+) max_sprites=(\d+) max_layers=(\d+) cosmetic_dropped=(\d+)\r?$',data,re.M)
                    if not m:raise ValueError('Malformed game rate')
                    row={'layout':name,'seconds':float(m[1]),'fps':float(m[2]),'commands':int(m[3]),'sprites':int(m[4]),'layers':int(m[5]),'cosmetic_dropped':int(m[6])}
                    if not 0<row['fps']<=56 or abs(600/row['seconds']-row['fps'])>.02 or row['sprites']>64 or row['layers']>12:
                        raise ValueError('Inconsistent game rate: '+str(row))
                    return row
                row=reading(name+'_rate','cat /tmp/nebula-check.log',parse_rate)
                report['benchmarks'].append(row);print(row,flush=True)
                assert row['fps']>=38,row
            for name,keys in [('keyboard',b'aD\x1b[C\x1b[Dws '),('sigint',b'\x03')]:
                uart.reset_input_buffer();data=bytearray()
                interactive_active=True
                # Preserve immutable game output on the target. An unsolicited
                # corrupted START line cannot be reread while the game owns
                # the terminal. The result below verifies that the game ran
                # and consumed the nova, before validating restored shell I/O.
                previous=uart.timeout;uart.timeout=.002
                try:
                    for ch in b'nebula > /tmp/nebula-play.log\n':
                        uart.write(bytes([ch]));uart.flush();time.sleep(.025);data.extend(uart.read(4096))
                finally:uart.timeout=previous
                time.sleep(8)
                for ch in keys:uart.write(bytes([ch]));time.sleep(.08);data.extend(uart.read(4096))
                if name=='keyboard':
                    for ch in b'pPfFq':uart.write(bytes([ch]));time.sleep(.35);data.extend(uart.read(4096))
                time.sleep(2);data.extend(uart.read(8192))
                (a.out/(name+'.log')).write_bytes(data)
                interactive_active=False
                def parse_result(data):
                    m=re.search(rb'^NEBULA_RESULT score=(\d+) kills=(\d+) sector=(\d+) boss_hp=(-?\d+) health=(\d+) victory=([01]) spawned=(\d+) shots=(\d+) damage=(\d+) novas=(\d+) status=([01])\r?$',data,re.M)
                    if not m:raise ValueError('Malformed interactive game result')
                    return dict(zip('score kills sector boss_hp health victory spawned shots damage novas status'.split(),map(int,m.groups())))
                outcome=reading(name+'_result','cat /tmp/nebula-play.log',parse_result)
                assert outcome['status']==0 and (name!='keyboard' or outcome['novas']==1),outcome
                run(name+'_shell','printf "NEBULA_SHELL_RESTORED\\n"')
                report['interactive'].append(dict(name=name,**outcome))
            run('autoplay_start','nebula --demo > /tmp/nebula-check.log & echo $! > /tmp/nebula-check.pid; cp /tmp/nebula-check.pid /tmp/nebula.pid')
            background=True;ready('autoplay');time.sleep(.3)
            for mode in ['split','console','game']:
                run('layout_'+mode,'prodockctl layout '+mode)
                s=state('layout_'+mode+'_state');healthy(s)
                assert s['mode']=={'split':0,'console':2,'game':1}[mode],s
            before=state('endurance_before');healthy(before)
            start=time.monotonic();print('NEBULA_AUTOPLAY_RUNNING',flush=True)
            for i in range((a.seconds+19)//20):
                time.sleep(20)
                s=state(f'sample_{i}');healthy(s)
                report['samples'].append(dict(seconds=time.monotonic()-start,**s))
                assert (s['done']-before['done'])&65535==(s['sent']-before['sent'])&65535,s
                assert s['presents']>before['presents'] and s['text']>before['text'],s
                assert s['presents']-before['presents']<=s['frames']-before['frames']+2,s
                print('NEBULA_ENDURANCE',report['samples'][-1],flush=True)
            elapsed=time.monotonic()-start
            report['endurance']={'seconds':elapsed,'frames':s['presents']-before['presents'],
                                 'approximate_fps':(s['presents']-before['presents'])/elapsed,
                                 'commands':s['sent']-before['sent'],'before':before,'after':s}
            assert report['endurance']['approximate_fps']>=38,report['endurance']
            # Refresh the final PID/file names used in the user's launch instructions.
            run('final_hint','printf "\\nNEBULA : kill `cat /tmp/nebula.pid` puis nebula\\n"')
            report['game_passed']=True
            report['passed']=report['serial_clean'];background=False
        except Exception as error:
            report['error']=str(error)
            if hasattr(error,'data'):(a.out/'timeout.log').write_bytes(error.data)
            raise
        finally:
            if interactive_active:
                uart.write(b'\x03');uart.flush();time.sleep(1)
                (a.out/'interactive_cleanup.log').write_bytes(uart.read(8192))
            if background:
                try:
                    status,data=command(uart,'p=`cat /tmp/nebula-check.pid`; if test "`cat /proc/$p/comm`" = nebula; then kill -TERM "$p"; fi',15)
                    (a.out/'cleanup.log').write_bytes(data);report['cleanup_exit']=status
                except Exception as error:report['cleanup_error']=str(error)
            (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
    if not report['passed']:raise SystemExit('Game passed; serial transport had rejected reads (see report)')


if __name__=='__main__':main()
