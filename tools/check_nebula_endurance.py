#!/usr/bin/env python3
"""Finite 10,000-frame game endurance, with GPU checks inside NEBULA every 0.2s.

CDC carries short completion probes instead of continuous long telemetry.
All malformed/timeout replies are preserved; only read-only probes are retried.
Leaves a new autoplay running after validating the finished game's output.
"""
import argparse,json,re,time
from pathlib import Path
import serial
from check_linux import command,CommandTimeout
from check_gpu_reloads import wait_console
from check_nebula import display


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    port,usb=wait_console();assert usb['speed_mbps']==480
    report={'passed':False,'usb':usb,'rejected_reads':[],'physical_sd_writes':0}
    started=False
    with serial.Serial(port,115200,timeout=.1,exclusive=True) as uart:
        def run(name,text,timeout=20):
            try:status,data=command(uart,text,timeout)
            except CommandTimeout as error:
                (a.out/(name+'.log')).write_bytes(error.data);raise
            (a.out/(name+'.log')).write_bytes(data);return status,data
        def read(name,text,parser):
            for i in range(12):
                try:
                    status,data=run(name+f'_{i}',text);assert status==0,status
                    return parser(data)
                except (ValueError,CommandTimeout) as error:
                    report['rejected_reads'].append({'name':name,'attempt':i,'error':str(error)})
            raise RuntimeError('Cannot read '+name)
        def healthy(s):
            assert not(s['errors'] or s['fault'] or s['uf'] or s['invalid'] or s['sprites']),s
            assert s['line']<2556 and s['usb']&0x60==0x60 and not s['usb']&0x480,s
        try:
            before=read('before','prodockctl display',display);healthy(before);report['before']=before
            status,_=run('start','nebula --demo --frames 10000 > /tmp/nebula-endurance.log & echo $! > /tmp/nebula-endurance.pid')
            assert status==0;started=True;start=time.monotonic()
            for attempt in range(20):
                time.sleep(20)
                try:status,_=run(f'probe{attempt}','grep -q "^NEBULA_RESULT" /tmp/nebula-endurance.log',15)
                except CommandTimeout as error:
                    report['rejected_reads'].append({'name':'probe','attempt':attempt,'error':str(error)});continue
                print('NEBULA_ENDURANCE_RUNNING',round(time.monotonic()-start,1),'seconds',flush=True)
                assert status in (0,1),status
                if status==0:break
            else:raise RuntimeError('Game did not finish within the endurance deadline')
            def rate(data):
                m=re.search(rb'^NEBULA_RATE frames=10000 seconds=([0-9.]+) fps=([0-9.]+) commands=(\d+) max_sprites=(\d+) max_layers=(\d+) cosmetic_dropped=(\d+)\r?$',data,re.M)
                end=re.search(rb'^NEBULA_RESULT score=(\d+) kills=(\d+) sector=(\d+) boss_hp=(-?\d+) health=(\d+) victory=([01]) spawned=(\d+) shots=(\d+) damage=(\d+) novas=(\d+) status=([01])\r?$',data,re.M)
                if not m or not end:raise ValueError('Malformed game result')
                result=dict(seconds=float(m[1]),fps=float(m[2]),commands=int(m[3]),sprites=int(m[4]),layers=int(m[5]),cosmetic_dropped=int(m[6]),status=int(end[11]))
                if not 0<result['fps']<=56 or abs(10000/result['seconds']-result['fps'])>.02 or result['sprites']>64 or result['layers']>12:
                    raise ValueError('Inconsistent game result '+str(result))
                return result
            result=read('game_result','cat /tmp/nebula-endurance.log',rate);report['game']=result
            assert result['fps']>=38 and result['status']==0,result
            after=read('after','prodockctl display',display);healthy(after);report['after']=after
            assert after['presents']-before['presents']==10000,(before,after)
            assert after['sent']-before['sent']==result['commands'],(before,after,result)
            assert (after['done']-before['done'])&65535==result['commands']&65535,(before,after,result)
            started=False
            status,_=run('autoplay','nebula --demo > /tmp/nebula.log & echo $! > /tmp/nebula.pid')
            assert status==0
            time.sleep(8)
            live=read('autoplay_state','prodockctl display',display);healthy(live)
            assert live['mode']==1 and live['presents']>after['presents'],live
            report.update(passed=True,autoplay=live,serial_clean=not report['rejected_reads'])
        except Exception as error:
            report['error']=str(error);raise
        finally:
            if started:
                try:run('cleanup','p=`cat /tmp/nebula-endurance.pid`; if test "`cat /proc/$p/comm`" = nebula; then kill -TERM "$p"; fi')
                except Exception as error:report['cleanup_error']=str(error)
            (a.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
