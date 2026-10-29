#!/usr/bin/env python3
"""One real paced showcase cycle, no user save, exact OP2 rollback."""
import argparse,fcntl,json,re,signal,time
from pathlib import Path
import serial
from prodock_transport import Transport,RECEIVER_SHA
from prodock_valley_ab import process,progress,PORT,RELEASE
from prodock_valley_trial import sha,display,game_counters
from prodock_valley_benchmark import readback,wait_exit,fields
from prodock_order import verify_pixels,abort_receiver
from prodock_arcade import BASE,BASE_SAVE,BASE_SHA,LIVE,identity,stop_baseline,stop,saved_bytes,verify_overlay,raw_verify,recover,once

DEPENDENCIES=('prodock_showcase.py','prodock_arcade.py','prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','check_linux.py','check_gpu_reloads.py')

def preflight(bundle):
 m=json.loads((bundle/'manifest.json').read_text())
 assert m['candidate'] and not m['hardware_tested'] and m['baseline']['sha256']==BASE_SHA
 assert re.fullmatch(r'sc[0-9]+',m['tag']) and m['program']=='luma3d-'+m['tag'] and m['helper']==m['tag']+'-helper'
 for name,r in m['files'].items():
  assert re.fullmatch(r'[A-Za-z0-9_.-]+',name)
  p=bundle/name;assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],name
 for name in DEPENDENCIES:assert sha(Path(__file__).with_name(name))==m['files'][name]['sha256'],name
 assert json.loads((bundle/'game_manifest.json').read_text())['riscv']==m['game']
 assert json.loads((bundle/'baseline_manifest.json').read_text())['riscv']==m['baseline']
 common=json.loads((bundle/'common_regression_status.json').read_text());assert common['passed'] and common['tests']==11 and not common['changed']
 v=json.loads((bundle/'local_validation.json').read_text());assert v['passed'] and not v['hardware_tested'] and v['elf']==m['game'] and v['manifest_sha256']==sha(bundle/'game_manifest.json')
 rv=json.loads((bundle/'rv32_validation.json').read_text());assert rv['passed'] and not rv['hardware'] and rv['manifest_sha256']==sha(bundle/'game_manifest.json') and len(rv['records'])==13
 for r in rv['records']:assert r['passed'] and r['elf_sha256']==m['game']['sha256'] and r['memory_changed_bytes']==0 and r['commands_identical'] and r['overlay_identical']
 d=m['delta'];assert d['old_sha256']==BASE_SHA and d['new_sha256']==m['game']['sha256'] and d['new_bytes']==m['game']['bytes'] and d['new_crc32']==m['game']['crc32']
 assert m['first']['pixels']['bytes']==192000 and m['first']['pixels']['sha256']==m['first']['oracle']['image_sha256']
 assert m['first']['hud']['bank']==20 and 0<m['first']['hud']['bytes']<=240000
 assert m['transfer_files']==[m['helper'],d['file'],m['first']['pixels']['file'],m['first']['hud']['file']]
 assert len(set(m['transfer_files']))==4 and m['deadline_seconds']==3700
 assert m['tour_args']=='--showcase-once' and m['live_args']=='--showcase'
 return m

def tour_result(raw):
 assert b'LUMA3D_SAVE ' not in raw and b'LUMA3D_SHOWCASE_FIXTURE' not in raw and b'LUMA3D_SHOWCASE_TIMEOUT' not in raw
 assert re.search(rb'^LUMA3D_SHOWCASE_START stage=0 simulated=0.000 once=1 saves=disabled\r?$',raw,re.M)
 matches=re.findall(rb'^LUMA3D_SHOWCASE stage=(\d+) status=(\d+) loops=(\d+) simulated=([0-9.]+) wall=([0-9.]+) visited=([0-9a-f]+) won=([0-9a-f]+) commands=(\d+) title=',raw,re.M)
 assert [(int(r[0]),int(r[1]),int(r[2])) for r in matches]==[(i,1,0) for i in range(1,17)]+[(16,2,1)]
 lines=re.findall(rb'^LUMA3D_SHOWCASE_RESULT ([^\r\n]+)',raw,re.M);assert len(lines)==1
 result={k.decode():v.decode() for k,v in re.findall(rb'(\w+)=([^\s]+)',lines[0])}
 for k,v in [('status','2'),('stage','16'),('loops','1'),('visited','ff'),('won','ff'),('boss','1'),('checkpoint','1'),('crystals','1'),('hardware','1')]:assert result[k]==v,(k,result[k])
 simulated=float(result['simulated']);wall=float(result['wall'])
 assert 0<simulated<=1201 and simulated-1<=wall<=3601 and int(result['commands'])>=8
 counters=game_counters(raw);assert counters['frames']>100
 return dict(completed=True,stages=17,visited=255,won=255,simulated_seconds=simulated,wall_seconds=wall,commands=int(result['commands']),counters=counters,result=fields(raw,'LUMA3D_RESULT'),scope='Actual positive-timestep paced demo with presentation gating; whole-tour FPS, not a fixed-scene benchmark')

def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--expected-manifest',required=True);a=p.parse_args()
 assert sha(a.bundle/'manifest.json')==a.expected_manifest;m=preflight(a.bundle);a.out.mkdir(parents=True,exist_ok=False)
 from check_linux import command
 r=dict(passed=False,manifest_sha256=a.expected_manifest,game=m['game'],transfers=[],fpga='G22r0 continuity; G3D1 checked by renderer',kernel=RELEASE.decode(),fpga_writes=0,kernel_writes=0,sd_writes=0,flash_writes=0)
 def interrupted(n,frame):raise KeyboardInterrupt('Signal '+str(n))
 signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGHUP,interrupted)
 with open('/tmp/prodock-diagnostic.lock','a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
   tx=Transport(uart,command,a.out);stopped=False;current=None;ever=False;recovery={};r['recovery']=recovery
   try:
    uart.write(b'\n');time.sleep(.2);uart.read(16000)
    before=tx.run('before','uname -r; prodockctl display; cat /proc/mounts')
    assert re.search(rb'^'+RELEASE+rb'\r?$',before,re.M) and b'tmpfs /tmp tmpfs ' in before and not re.search(rb'^/dev/mmc\S* ',before,re.M)
    r['before']=display(before);r['initial_identity']=identity(tx,'initial_op2');recovery['baseline_identity']=r['initial_identity'];time.sleep(3)
    r['progress_before']=display(tx.run('progress_before','prodockctl display'));assert (r['progress_before']['presents']-r['before']['presents'])&0xffffffff
    tags=[m['tag']+'_'+x for x in ('first','tour','live','restore')]
    names=[x+'.pid' for x in tags]+[m['program'],m['tag']+'-op2-recovery.save']+m['transfer_files']
    tx.run('fresh_names',' && '.join('test ! -f /tmp/'+n for n in names))
    readback(tx,'receiver_readback','/tmp/luma-rx',1464,RECEIVER_SHA)
    for name in m['transfer_files']:
     tx.receiver_active=True;r['transfers'].append(tx.transfer(a.bundle/name,name))
    helper=m['helper'];tx.run('helper_mode','chmod 700 /tmp/'+helper)
    raw_verify(tx,helper,'baseline_file','/tmp/'+BASE,m['baseline']);raw_verify(tx,helper,'baseline_running_image','/proc/'+str(r['initial_identity']['pid'])+'/exe',m['baseline'])
    d=m['delta'];raw=tx.run('install_delta',f'/tmp/{helper} patch /tmp/{d["file"]} /tmp/{m["program"]} {d["patch_bytes"]} {d["patch_crc32"]} /tmp/{BASE}',90)
    assert f'LUMA3D_UNPACK_OK bytes={d["new_bytes"]} crc32={d["new_crc32"]}'.encode() in raw
    tx.run('game_mode','chmod 700 /tmp/'+m['program'])
    for ref in (m['first']['pixels'],m['first']['hud']):
     raw=tx.run('verify_'+ref['file'],f'/tmp/{helper} verify /tmp/{ref["file"]} unused {ref["bytes"]} {ref["crc32"]}')
     assert f'LUMA3D_VERIFY_OK bytes={ref["bytes"]} crc32={ref["crc32"]}'.encode() in raw
    assert identity(tx,'op2_before_switch')==r['initial_identity']
    print('SHOWCASE_FIRST_APPEARANCE_IN_10_SECONDS: verified RAM files; OP2 still visible',flush=True);time.sleep(10)
    stopped=True;stop_baseline(tx,r['initial_identity']);r['baseline_save']=saved_bytes(tx,'baseline_v4_stopped',BASE_SAVE,4)
    released=tx.run('released','prodockctl info; prodockctl display');assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in released;r['released']=display(released)
    tag=m['tag']+'_first';current=(m['program'],'/tmp/'+tag+'.pid');ever=True
    initial=tx.run('first_launch',once(m['program'],tag,'--showcase --frames 1'));assert wait_exit(uart,a.out,tag,initial=initial)==0
    log=tx.run('first_log','cat /tmp/'+tag+'.log');current=None;r['first_counters']=game_counters(log);assert r['first_counters']['frames']==1
    assert b'LUMA3D_SAVE ' not in log and b'LUMA3D_SHOWCASE_FIXTURE' not in log
    for key in ('vertices','triangles','slivers'):assert r['first_counters'][key]==m['first']['oracle'][key]
    verify_pixels(tx,helper,tag,m['first']['pixels']);verify_overlay(tx,helper,tag,m['first']['hud'],both=False)
    r['first_display']=display(tx.run('first_display','prodockctl display'));print('SHOWCASE_FIRST_IMAGE_PASS: exact pixels and native HUD bank',flush=True)
    tag=m['tag']+'_tour';current=(m['program'],'/tmp/'+tag+'.pid')
    initial=tx.run('tour_launch',once(m['program'],tag,m['tour_args']))
    assert wait_exit(uart,a.out,tag,timeout=m['deadline_seconds'],initial=initial)==0
    log=tx.run('tour_log','cat /tmp/'+tag+'.log',90);current=None;r['tour']=tour_result(log)
    r['after_tour']=display(tx.run('after_tour','prodockctl display'))
    r['baseline_save_final']=saved_bytes(tx,'baseline_v4_final',BASE_SAVE,4);assert r['baseline_save_final']['sha256']==r['baseline_save']['sha256']
    print('SHOWCASE_FULL_CYCLE_PASS: eight wins and real return; launching repeating tour',flush=True)
    tag=m['tag']+'_live';current=(m['program'],'/tmp/'+tag+'.pid')
    tx.run('live_launch',f'/tmp/{m["program"]} {m["live_args"]} < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {current[1]}')
    r['live_display']=progress(tx,m['program'],tag+'.log','live',current[1]);tx.run('publish_live_pid','cp '+current[1]+' '+LIVE)
    r['live_identity']=tx.run('live_identity','p=`cat '+LIVE+'`; cat /proc/$p/stat; cat /proc/$p/cmdline; echo').decode(errors='replace')
    assert '--showcase\x00' in r['live_identity'] and '--save' not in r['live_identity']
    r['baseline_save_after_live']=saved_bytes(tx,'baseline_v4_after_live',BASE_SAVE,4);assert r['baseline_save_after_live']['sha256']==r['baseline_save']['sha256']
    r['passed']=True;r['left_running']=m['program']+' --showcase; all eight activities in autonomous loop; no save file opened'
   except BaseException as e:
    r['error']=repr(e)
    try:abort_receiver(tx,uart,a.out)
    except BaseException as e:r['receiver_abort_error']=repr(e)
    if stopped:
     try:
      uart.write(b'\x03');uart.flush();time.sleep(.3);uart.read(16000);r['restored_display']=recover(tx,m,current,ever,recovery);r['restored_op2']=True
     except BaseException as e:r['cleanup_error']=repr(e)
    raise
   finally:
    (a.out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
if __name__=='__main__':main()
