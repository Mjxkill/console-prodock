#!/usr/bin/env python3
"""Polished showcase trial. Exact SC1 fallback; never open a game save."""
import argparse,fcntl,json,math,re,signal,time
from pathlib import Path
import serial
from prodock_transport import Transport,RECEIVER_SHA
from prodock_valley_ab import process,progress,PORT,RELEASE
from prodock_valley_trial import sha,display,game_counters
from prodock_valley_benchmark import readback,wait_exit,fields
from prodock_order import verify_pixels,abort_receiver
from prodock_arcade import stop,saved_bytes,verify_overlay,verify_regions,raw_verify,once
from prodock_showcase import tour_result as original_tour_result
BASE='luma3d-sc1';BASE_SAVE='/tmp/op2-live.save';LIVE='/tmp/luma3d-live.pid'
BASE_SHA='b88685f36fe18d8fbdab53652a0683d8ff666c1aae8e3f8b245154fabec88ff6'
SAVE_SHA='2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6'
DEPENDENCIES=('prodock_polish.py','prodock_showcase.py','prodock_arcade.py','prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','check_linux.py','check_gpu_reloads.py')

def preflight(bundle):
 m=json.loads((bundle/'manifest.json').read_text())
 assert m['candidate'] and not m['hardware_tested'] and m['baseline']['sha256']==BASE_SHA
 assert re.fullmatch(r'pp[0-9]+',m['tag']) and m['program']=='luma3d-pp1' and m['probe']=='pp1-probe' and m['helper']==m['tag']+'-helper'
 for name,record in m['files'].items():
  assert re.fullmatch(r'[A-Za-z0-9_.-]+',name)
  p=bundle/name;assert p.stat().st_size==record['bytes'] and sha(p)==record['sha256'],name
 for name in DEPENDENCIES:assert sha(Path(__file__).with_name(name))==m['files'][name]['sha256'],name
 for name,key in [('game_manifest.json','game'),('baseline_manifest.json','baseline')]:assert json.loads((bundle/name).read_text())['riscv']==m[key]
 validation=json.loads((bundle/'local_validation.json').read_text())
 assert validation['passed'] and not validation['hardware_tested'] and validation['elf']==m['game'] and validation['manifest_sha256']==sha(bundle/'game_manifest.json')
 common=json.loads((bundle/'common_regression_status.json').read_text());assert common['passed'] and common['tests']==11 and not common['changed']
 probe=json.loads((bundle/'probe_validation.json').read_text())
 assert probe['passed'] and not probe['hardware'] and probe['files']['luma3d-riscv']==m['probe_binary'] and probe['game_manifest_sha256']==sha(bundle/'game_manifest.json')
 for name,count,binary in [('rv32_validation.json',16,m['game']),('probe_rv32_validation.json',8,m['probe_binary'])]:
  rv=json.loads((bundle/name).read_text());assert rv['passed'] and not rv['hardware'] and rv['manifest_sha256']==sha(bundle/'game_manifest.json') and len(rv['records'])==count
  for r in rv['records']:assert r['passed'] and r['elf_sha256']==binary['sha256'] and r['memory_changed_bytes']==0 and r['commands_identical'] and r['overlay_identical']
 for delta,old,new in [(m['delta'],m['baseline'],m['game']),(m['probe_delta'],m['game'],m['probe_binary'])]:
  assert delta['old_sha256']==old['sha256'] and delta['new_sha256']==new['sha256'] and delta['new_bytes']==new['bytes'] and delta['new_crc32']==new['crc32']
 assert m['first']['pixels']['bytes']==192000 and m['first']['pixels']['sha256']==m['first']['oracle']['image_sha256']
 assert m['first']['hud']['bank']==20 and 0<m['first']['hud']['bytes']<=240000
 assert [f['name'] for f in m['fixtures']]==['entry_0','entry_1','entry_2','entry_3','entry_4','crystal','boss','checkpoint']
 assert [f['active'] for f in m['fixtures']]==list(range(1,9))
 for f in m['fixtures']:
  assert 0<f['advance']<100000 and f['regions'][0]['offset']==22<<20 and f['regions'][0]['bytes']==384000
  assert bool(f['pixels'])==(f['active'] in (5,6,8))
  if f['pixels']:assert f['pixels']['bytes']==192000 and f['pixels']['sha256']==f['oracle']['image_sha256']
  for r in f['regions']:
   x,n=r['offset'],r['bytes'];assert x%4==n%4==0 and n>0 and ((20<<20<=x and x+n<=24<<20) or (28<<20<=x and x+n<=32<<20))
  assert len(f['regions'])==(2 if f['active']==7 else 1)
 references=[m['first']['pixels'],m['first']['hud']]
 for f in m['fixtures']:
  if f['pixels']:references.append(f['pixels'])
  references.extend(f['regions'])
 assert m['references']==references
 assert m['transfer_files']==[m['helper']]
 assert len(set(m['transfer_files']))==len(m['transfer_files']) and m['deadline_seconds']==3700
 assert m['tour_args']=='--showcase-once' and m['live_args']=='--showcase'
 assert sha(bundle/'prior_result.json')==m['resume_result_sha256']
 prior=json.loads((bundle/'prior_result.json').read_text())
 assert not prior['passed'] and prior['restored_sc1'] and prior['game']==m['game']
 assert prior['recovery']['identity']==m['expected_identity']==dict(pid=2376,start_ticks=21307354)
 assert [f['name'] for f in prior['fixtures']]==['entry_0','entry_1','entry_2','entry_3','entry_4','crystal']
 assert [(q['gpu_offset'],q['source_offset'],q['bytes']) for q in m['publication_ranges']]==[(28<<20,0,835584),(31<<20,3<<20,961152)]
 publication=json.loads((bundle/'publication_validation.json').read_text())
 assert publication['passed'] and not publication['hardware'] and publication['game_sha256']==m['game']['sha256']
 assert len(publication['records'])==2 and all(x['passed'] for x in publication['records'])
 for expected,actual in zip(m['publication_ranges'],publication['records'][0]['ranges']):
  assert expected['gpu_offset']==actual['offset'] and all(expected[k]==actual[k] for k in ('bytes','sha256','crc32'))
 return m

def tour_result(raw):
 result=original_tour_result(raw);cost=[]
 for row in re.findall(rb'^LUMA3D_ACTIVITY_COST ([^\r\n]+)',raw,re.M):
  d={k.decode():float(v) for k,v in re.findall(rb'(\w+)=([^\s]+)',row)}
  assert all(math.isfinite(v) and v>=0 for v in d.values()) and d['hardware']==1 and d['frames']>=1
  for key in ('p95','p99'):
   assert d[key+'_overflow'] in (0,1)
   assert (d[key+'_upper_ms']==0)==bool(d[key+'_overflow'])
   if not d[key+'_overflow']:assert 4<=d[key+'_upper_ms']<=1020 and d[key+'_upper_ms']%4==0
  assert d['adviser']<=d['simulation']+.001 and d['max_sprites']<=64 and d['max_layers']<=12
  assert d['max_frame']<=d['frame_sum']+.001 and d['over_33ms']<=d['frames'] and d['over_1020ms']<=d['frames']
  cost.append(d)
 assert [r['mode'] for r in cost]==list(range(9)) and sum(r['frames'] for r in cost)==result['counters']['frames']
 for mode in (1,2,3,4,7):
  assert cost[mode]['commands']==cost[mode]['batches']==cost[mode]['triangles']==0
 assert cost[7]['max_sprites']>0 and cost[7]['max_layers']==4
 result['activity_cost']=cost
 result['timing_scope']='Per-activity completion intervals, 4 ms histogram bounds and exact maximum; no controlled A/B or preset FPS claim'
 return result

def identity(tx,label,pidfile=LIVE,program=BASE):
 assert re.fullmatch(r'/tmp/[A-Za-z0-9_.-]+',pidfile) and re.fullmatch(r'[A-Za-z0-9_.-]+',program)
 assert process(tx,label+'_alive',program,pidfile)
 raw=tx.run(label+'_identity','p=`cat '+pidfile+'`; cat /proc/$p/stat; od -b -v /proc/$p/cmdline')
 line=re.search(rb'^(\d+) \('+program.encode()+rb'\) ([^\r\n]+)',raw,re.M);assert line
 rest=line[2].split();assert len(rest)>=20 and rest[0] not in (b'Z',b'X')
 args=bytearray();end=None
 for row in raw.replace(b'\r',b'').splitlines():
  if re.fullmatch(rb'[0-7]{7,} (?:[0-7]{3} ?){1,16}',row.strip()):
   fields=row.split();assert end is None and int(fields[0],8)==len(args)
   args.extend(int(v,8) for v in fields[1:]);assert len(args)<=512
  elif re.fullmatch(rb'[0-7]{7,}',row.strip()):
   assert end is None;end=int(row,8)
 assert end==len(args) and args==('/tmp/'+program+'\0--showcase\0').encode(), 'Unexpected full argv; fresh plan required'
 return dict(pid=int(line[1]),start_ticks=int(rest[19]))

def stop_baseline(tx,expected):
 # Tie TERM to the checked process, never to a later value read from LIVE.
 # The shell checks starttime immediately before signalling this fixed PID.
 assert identity(tx,'sc1_stop_identity')==expected, 'Baseline identity changed before stop'
 pid=expected['pid'];ticks=expected['start_ticks'];assert pid>1 and ticks>0
 command=(f'test "`cat {LIVE}`" = {pid} && test "`cat /proc/{pid}/comm`" = {BASE}'
          f' && set -- `cat /proc/{pid}/stat` && test "$1" = {pid} && test "$2" = "({BASE})"'
          f' && test "$3" != Z && test "$3" != X && shift 21 && test "$1" = {ticks}'
          f' && kill -TERM {pid} && sleep 1')
 tx.run('stop_sc1_term_guarded',command)
 for i in range(8):
  raw=tx.run('stop_sc1_confirm_'+str(i),f'if test -d /proc/{pid}; then cat /proc/{pid}/stat; else echo STOPPED; fi')
  if re.search(rb'^STOPPED\r?$',raw,re.M):return
  match=re.search(rb'^(\d+) \('+BASE.encode()+rb'\) ([^\r\n]+)',raw,re.M);assert match
  rest=match[2].split();assert len(rest)>=20 and int(match[1])==pid and int(rest[19])==ticks, 'PID reused; refuse further GPU launch'
  if rest[0] in (b'Z',b'X'):return
  time.sleep(1)
 raise RuntimeError('Original sc1 did not stop')


def recover(tx,m,current,ever,recovery):
 if current:stop(tx,current[0],'cleanup_current',current[1])
 if recovery.get('attempted'):
  # A previous launch may have succeeded before its command/progress reply
  # failed. Never issue it twice. An unpublished or dead PID fails closed.
  anchor=identity(tx,'recovery_existing_identity',recovery['pidfile'])
  if 'identity' in recovery:assert anchor==recovery['identity'], 'Recovery replaced; no second launch'
  else:recovery['identity']=anchor
  result=progress(tx,BASE,recovery['log'],'recovery_existing',recovery['pidfile'])
  assert identity(tx,'recovery_after_progress',recovery['pidfile'])==anchor
  tx.run('publish_restored_pid','cp '+recovery['pidfile']+' '+LIVE)
  assert identity(tx,'recovery_after_publish')==anchor;return result
 if not ever and process(tx,'sc1_still_alive',BASE,LIVE):
  assert identity(tx,'preserved_sc1_identity')==recovery['baseline_identity'], 'Changed baseline cannot be adopted during recovery'
  one=display(tx.run('preserved_display1','prodockctl display'));time.sleep(3)
  two=display(tx.run('preserved_display2','prodockctl display'))
  # TERM may have succeeded just before the controller lost its reply. Do
  # not call a few final presents a live recovery after that process exits.
  if process(tx,'preserved_sc1_still_alive',BASE,LIVE):
   assert identity(tx,'preserved_sc1_final_identity')==recovery['baseline_identity']
   assert (two['presents']-one['presents'])&0xffffffff;return two
 tag=m['tag']+'_restore';pidfile='/tmp/'+tag+'.pid'
 recovery.update(attempted=True,pidfile=pidfile,log=tag+'.log')
 tx.run('restore_sc1',f'/tmp/{BASE} --showcase < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {pidfile}')
 anchor=identity(tx,'restore_identity',pidfile);recovery['identity']=anchor
 result=progress(tx,BASE,tag+'.log','restored_sc1',pidfile)
 assert identity(tx,'restore_after_progress',pidfile)==anchor
 tx.run('publish_restored_pid','cp '+pidfile+' '+LIVE)
 assert identity(tx,'restore_after_publish')==anchor;return result


def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--expected-manifest',required=True);a=p.parse_args()
 assert sha(a.bundle/'manifest.json')==a.expected_manifest;m=preflight(a.bundle);a.out.mkdir(parents=True,exist_ok=False)
 from check_linux import command
 r=dict(passed=False,hardware=True,manifest_sha256=a.expected_manifest,game=m['game'],transfers=[],resumed_from=m['resume_result_sha256'],fpga='G22r0 continuity; G3D1 checked by renderer',kernel=RELEASE.decode(),fpga_writes=0,kernel_writes=0,sd_writes=0,flash_writes=0)
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
    r['before']=display(before);r['initial_identity']=identity(tx,'initial_sc1');assert r['initial_identity']==m['expected_identity']
    r['baseline_save_initial']=saved_bytes(tx,'baseline_v4_initial',BASE_SAVE,4);assert r['baseline_save_initial']['sha256']==SAVE_SHA;recovery['baseline_identity']=r['initial_identity'];time.sleep(3)
    r['progress_before']=display(tx.run('progress_before','prodockctl display'));assert (r['progress_before']['presents']-r['before']['presents'])&0xffffffff
    tags=[m['tag']+'_'+x for x in ('boss','checkpoint','tour','live','restore')]
    tx.run('fresh_names',' && '.join('test ! -f /tmp/'+n for n in [m['helper'],*[x+'.pid' for x in tags]]))
    readback(tx,'receiver_readback','/tmp/luma-rx',1464,RECEIVER_SHA)
    tx.receiver_active=True;r['transfers'].append(tx.transfer(a.bundle/m['helper'],m['helper']))
    helper=m['helper'];tx.run('helper_mode','chmod 700 /tmp/'+helper)
    for label,path,record in [('baseline_file','/tmp/'+BASE,m['baseline']),('baseline_running_image','/proc/'+str(r['initial_identity']['pid'])+'/exe',m['baseline']),('staged_game','/tmp/'+m['program'],m['game']),('staged_probe','/tmp/'+m['probe'],m['probe_binary'])]:raw_verify(tx,helper,label,path,record)
    fixtures=[f for f in m['fixtures'] if f['name'] in ('boss','checkpoint')]
    for f in fixtures:
     for ref in [*f['regions'],*([f['pixels']] if f['pixels'] else [])]:
      raw=tx.run('verify_'+ref['file'],f'/tmp/{helper} verify /tmp/{ref["file"]} unused {ref["bytes"]} {ref["crc32"]}')
      assert f'LUMA3D_VERIFY_OK bytes={ref["bytes"]} crc32={ref["crc32"]}'.encode() in raw
    assert identity(tx,'sc1_before_switch')==r['initial_identity']
    print('POLISH_RESUME_IN_10_SECONDS: exact existing game/probe/references; SC1 still visible',flush=True);time.sleep(10)
    stopped=True;stop_baseline(tx,r['initial_identity']);r['baseline_save']=saved_bytes(tx,'baseline_v4_stopped',BASE_SAVE,4);assert r['baseline_save']['sha256']==SAVE_SHA
    released=tx.run('released','prodockctl info; prodockctl display');assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in released;r['released']=display(released)
    r['fixtures']=[]
    for fixture in fixtures:
     tag=m['tag']+'_'+fixture['name'];current=(m['probe'],'/tmp/'+tag+'.pid');ever=True
     initial=tx.run(tag+'_launch',once(m['probe'],tag,'--advance '+str(fixture['advance'])))
     assert wait_exit(uart,a.out,tag,timeout=240,initial=initial)==0
     log=tx.run(tag+'_log','cat /tmp/'+tag+'.log');current=None
     assert b'LUMA3D_SAVE ' not in log and f'LUMA3D_POLISH_PROBE advance={fixture["advance"]} replay_without_render=1 active={fixture["active"]} hardware=1 saves=disabled'.encode() in log
     record=dict(name=fixture['name'],counters=game_counters(log));assert record['counters']['frames']==1
     for key in ('vertices','triangles','slivers'):assert record['counters'][key]==fixture['oracle'][key],(fixture['name'],key)
     if fixture['pixels']:verify_pixels(tx,helper,tag,fixture['pixels'])
     verify_regions(tx,helper,tag,fixture['regions'][:1])
     if fixture['name']=='boss':
      ref=fixture['regions'][1];record['published_regions']=[]
      for q in m['publication_ranges']:
       raw=tx.run(tag+'_slice_'+str(q['source_offset']),f'/tmp/{helper} memory-slice /tmp/{ref["file"]} {q["gpu_offset"]} {ref["bytes"]} {ref["crc32"]} {q["source_offset"]} {q["bytes"]}',90)
       expected=f'LUMA3D_MEMORY offset={q["gpu_offset"]} bytes={q["bytes"]} mismatch=0 actual_crc={q["crc32"]} expected_crc={q["crc32"]}'
       assert expected.encode() in raw;record['published_regions'].append(q)
     record['display']=display(tx.run(tag+'_display','prodockctl display'));r['fixtures'].append(record)
    print('POLISH_RESUMED_ORACLES_PASS: exact published shooter regions and checkpoint; paced tour starts now',flush=True)
    tag=m['tag']+'_tour';current=(m['program'],'/tmp/'+tag+'.pid')
    initial=tx.run('tour_launch',once(m['program'],tag,m['tour_args']))
    assert wait_exit(uart,a.out,tag,timeout=m['deadline_seconds'],initial=initial)==0
    log=tx.run('tour_log','cat /tmp/'+tag+'.log',90);current=None;r['tour']=tour_result(log)
    r['after_tour']=display(tx.run('after_tour','prodockctl display'))
    r['baseline_save_final']=saved_bytes(tx,'baseline_v4_final',BASE_SAVE,4);assert r['baseline_save_final']['sha256']==r['baseline_save']['sha256']
    print('SHOWCASE_FULL_CYCLE_PASS: eight wins and real return; launching repeating tour',flush=True)
    tag=m['tag']+'_live';current=(m['program'],'/tmp/'+tag+'.pid')
    tx.run('live_launch',f'/tmp/{m["program"]} {m["live_args"]} < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {current[1]}')
    r['live_identity']=identity(tx,'live_started',current[1],m['program'])
    r['live_display']=progress(tx,m['program'],tag+'.log','live',current[1]);tx.run('publish_live_pid','cp '+current[1]+' '+LIVE)
    r['baseline_save_after_live']=saved_bytes(tx,'baseline_v4_after_live',BASE_SAVE,4);assert r['baseline_save_after_live']['sha256']==r['baseline_save']['sha256']
    assert identity(tx,'live_after_save',LIVE,m['program'])==r['live_identity']
    r['passed']=True;r['left_running']=m['program']+' --showcase; all eight activities in autonomous loop; no save file opened'
   except BaseException as e:
    r['error']=repr(e)
    try:abort_receiver(tx,uart,a.out)
    except BaseException as e:r['receiver_abort_error']=repr(e)
    if stopped:
     try:
      uart.write(b'\x03');uart.flush();time.sleep(.3);uart.read(16000);r['restored_display']=recover(tx,m,current,ever,recovery);r['restored_sc1']=True
     except BaseException as e:r['cleanup_error']=repr(e)
    raise
   finally:
    (a.out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
if __name__=='__main__':main()
