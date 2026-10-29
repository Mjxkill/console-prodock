#!/usr/bin/env python3
"""Bounded eight-activity trial; exact OP2 fallback, temporary RAM only."""
import argparse,fcntl,hashlib,json,re,signal,struct,time,zlib
from pathlib import Path
import serial
from prodock_transport import Transport,RECEIVER_SHA
from prodock_valley_ab import process,progress,PORT,RELEASE,UnpublishedPID
from prodock_valley_trial import sha,display,game_counters
from prodock_valley_benchmark import readback,supervisor,wait_exit,fields
from prodock_order import parse,verify_pixels,abort_receiver
BASE='luma3d-op2';BASE_SAVE='/tmp/op2-live.save';LIVE='/tmp/luma3d-live.pid'
BASE_SHA='8f7500184ccf9977502243e5ddfbfb3b27f4b5b224dde46c606d8bdcf8f18981'
NEW_SHA='3ae9c784195280d9653c08117d56b48611c4a209f8c622bf68c2921a3b2a2659'
DEPENDENCIES=('prodock_arcade.py','prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','check_linux.py','check_gpu_reloads.py')

def preflight(bundle):
 m=json.loads((bundle/'manifest.json').read_text())
 assert m['candidate'] and m['game']['sha256']==NEW_SHA and m['baseline']['sha256']==BASE_SHA
 assert re.fullmatch(r'ar[0-9]+',m['tag'])
 assert m['program']=='luma3d-'+m['tag'] and m['helper']==m['tag']+'-helper' and m['probe']==m['tag']+'-probe'
 for name,r in m['files'].items():
  assert re.fullmatch(r'[A-Za-z0-9_.-]+',name)
  p=bundle/name;assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],name
 for name in DEPENDENCIES:assert sha(Path(__file__).with_name(name))==m['files'][name]['sha256'],name
 assert json.loads((bundle/'game_manifest.json').read_text())['riscv']==m['game']
 assert json.loads((bundle/'baseline_manifest.json').read_text())['riscv']==m['baseline']
 assert m['validation']['passed'] and not m['validation']['hardware_tested'] and m['validation']['elf']==m['game']
 assert sha(bundle/'game_manifest.json')==m['validation']['manifest_sha256']
 assert m['rv32_validation']['passed'] and not m['rv32_validation']['hardware']
 assert len(m['rv32_validation']['records'])==16
 for record in m['rv32_validation']['records']:
  assert record['passed'] and record['elf_sha256']==NEW_SHA and record['memory_changed_bytes']==0 and record['command_bytes_identical'] and record['overlay_identical']
 assert m['probe_validation']['passed'] and not m['probe_validation']['hardware']
 assert m['probe_validation']['build_manifest_sha256']==sha(bundle/'game_manifest.json')
 pv=m['probe_rv32_validation'];assert pv['passed'] and not pv['hardware'] and pv['probe_manifest_sha256']==sha(bundle/'probe_validation.json')
 assert len(pv['records'])==7
 for record in pv['records']:
  assert record['passed'] and record['probe_sha256']==m['probe_binary']['sha256']
  if record['name']=='replay':assert record['replay_identical']
  else:assert record['memory_changed_bytes']==0 and record['commands_identical'] and record['overlay_identical']
 for key in ('bytes','sha256'):
  assert m['probe_binary'][key]==m['probe_validation']['files']['probe-riscv'][key]
  assert m['files'][m['helper']][key]==m['probe_validation']['files']['helper-riscv'][key]
 for name,r in m['oracle_files'].items():
  assert re.fullmatch(r'oracle/[A-Za-z0-9_.-]+',name)
  assert (bundle/name).stat().st_size==r['bytes'] and sha(bundle/name)==r['sha256']
 for d,old,new in ((m['delta'],m['baseline'],m['game']),(m['probe_delta'],m['game'],m['probe_binary'])):
  assert d['old_sha256']==old['sha256'] and d['new_sha256']==new['sha256'] and d['new_bytes']==new['bytes'] and d['new_crc32']==new['crc32']
 assert [s['variant'] for s in m['benchmarks']]==['op2','new','op2']
 for s in m['benchmarks']:
  assert s['pose']==0 and s['pixels']['bytes']==192000 and s['pixels']['sha256']==s['oracle']['image_sha256']
 assert [s['name'] for s in m['fixtures']]==['activity_5_flash','activity_5_mid','activity_6','activity_6_boss','activity_7','activity_7_mid']
 for s in m['fixtures']:
  assert 360<=s['state']['bytes']<=7480 and s['fixture_name']==m['tag']+'-'+s['name']+'.save'
  assert s['host_scene']['frames']==3 and s['host_scene']['fixed_fixture']==1
  assert (s['pixels'] is None)==s['name'].startswith('activity_6')
  assert len(s['regions'])==(4 if s['name'].startswith('activity_6') else 2)
  for ref in s['regions']:
   o,n=ref['offset'],ref['bytes'];assert not(o%4 or n%4) and n>0
   assert (20<<20<=o and o+n<=24<<20) or (28<<20<=o and o+n<=31<<20)
  assert [r['offset'] for r in s['regions'][:2]]==[22<<20,23<<20]
  if s['name'].startswith('activity_6'):assert [(r['offset'],r['bytes']) for r in s['regions'][2:]]==[(28<<20,491520),(30<<20,65536)]
 assert m['acceptance']==dict(max_arrival_slowdown=.10,max_witness_drift=.05)
 assert m['transfer_files']==[m['helper'],m['delta']['file'],m['probe_delta']['file'],*m['reference_files'],*m['fixture_files']]
 assert len(set(m['transfer_files']))==len(m['transfer_files'])
 return m

def identity(tx,label):
 assert process(tx,label+'_alive',BASE,LIVE)
 raw=tx.run(label+'_identity','p=`cat '+LIVE+'`; cat /proc/$p/stat; cat /proc/$p/cmdline; echo')
 line=re.search(rb'^(\d+) \('+BASE.encode()+rb'\) ([^\r\n]+)',raw,re.M);assert line
 rest=line[2].split();assert len(rest)>=20 and rest[0] not in (b'Z',b'X')
 args=re.search(rb'^/tmp/'+BASE.encode()+rb'\x00[^\r\n]*',raw,re.M);assert args
 argv=args[0].split(b'\x00');assert argv[-1]==b'';argv.pop()
 assert argv.count(b'--save')==1, 'Missing or duplicate baseline --save'
 at=argv.index(b'--save');assert at+1<len(argv) and argv[at+1]==BASE_SAVE.encode(), 'Unexpected baseline save path; fresh plan required'
 return dict(pid=int(line[1]),start_ticks=int(rest[19]))

def stop_baseline(tx,expected):
 # Tie TERM to the checked process, never to a later value read from LIVE.
 # The shell checks starttime immediately before signalling this fixed PID.
 assert identity(tx,'op2_stop_identity')==expected, 'Baseline identity changed before stop'
 pid=expected['pid'];ticks=expected['start_ticks'];assert pid>1 and ticks>0
 command=(f'test "`cat {LIVE}`" = {pid} && test "`cat /proc/{pid}/comm`" = {BASE}'
          f' && set -- `cat /proc/{pid}/stat` && test "$1" = {pid} && test "$2" = "({BASE})"'
          f' && test "$3" != Z && test "$3" != X && shift 21 && test "$1" = {ticks}'
          f' && kill -TERM {pid} && sleep 1')
 tx.run('stop_op2_term_guarded',command)
 for i in range(8):
  raw=tx.run('stop_op2_confirm_'+str(i),f'if test -d /proc/{pid}; then cat /proc/{pid}/stat; else echo STOPPED; fi')
  if re.search(rb'^STOPPED\r?$',raw,re.M):return
  match=re.search(rb'^(\d+) \('+BASE.encode()+rb'\) ([^\r\n]+)',raw,re.M);assert match
  rest=match[2].split();assert len(rest)>=20 and int(match[1])==pid and int(rest[19])==ticks, 'PID reused; refuse further GPU launch'
  if rest[0] in (b'Z',b'X'):return
  time.sleep(1)
 raise RuntimeError('Original op2 did not stop')

def stop(tx,program,label,pidfile):
 # Unique launch file, bounded publication wait, then PID AND start ticks
 # bound to TERM just as for the preserved baseline. Never chase LIVE here.
 for i in range(3):
  try:
   alive=process(tx,label+'_before_'+str(i),program,pidfile);break
  except UnpublishedPID:
   if i==2:raise
   time.sleep(1)
 if not alive:return
 raw=tx.run(label+'_stat',f'p=`cat {pidfile}`; if test -d /proc/$p; then cat /proc/$p/stat; else echo STOPPED; fi')
 if re.search(rb'^STOPPED\r?$',raw,re.M):return
 match=re.search(rb'^(\d+) \('+program.encode()+rb'\) ([^\r\n]+)',raw,re.M);assert match
 rest=match[2].split();assert len(rest)>=20
 if rest[0] in (b'Z',b'X'):return
 pid=int(match[1]);ticks=int(rest[19]);assert pid>1 and ticks>0
 cmd=(f'test "`cat {pidfile}`" = {pid} && set -- `cat /proc/{pid}/stat`'
      f' && test "$1" = {pid} && test "$2" = "({program})" && test "$3" != Z && test "$3" != X'
      f' && shift 21 && test "$1" = {ticks} && kill -TERM {pid} && sleep 1')
 tx.run(label+'_term_guarded',cmd)
 for i in range(8):
  raw=tx.run(label+'_after_'+str(i),f'if test -d /proc/{pid}; then cat /proc/{pid}/stat; else echo STOPPED; fi')
  if re.search(rb'^STOPPED\r?$',raw,re.M):return
  m=re.search(rb'^(\d+) \('+program.encode()+rb'\) ([^\r\n]+)',raw,re.M);assert m
  r=m[2].split();assert len(r)>=20 and int(m[1])==pid and int(r[19])==ticks,'PID reused; no second launch'
  if r[0] in (b'Z',b'X'):return
  time.sleep(1)
 raise RuntimeError('Candidate did not stop')

def saved_bytes(tx,label,path,version):
 raw=tx.run(label,'od -b -v '+path,90);data=bytearray()
 for line in raw.replace(b'\r',b'').splitlines():
  if re.fullmatch(rb'[0-7]{7,} (?:[0-7]{3} ?){1,16}',line.strip()):data.extend(int(v,8) for v in line.split()[1:])
 size=struct.unpack_from('<I',data,8)[0] if len(data)>=12 else 0
 assert (version==4 and size==5292) or (version==5 and 360<=size<=7480)
 assert len(data)==size and data[:8]==b'L3PROG1\0'
 assert struct.unpack_from('<3I',data,8)==(size,0x56414c31,version)
 assert struct.unpack_from('<I',data,20)[0]==zlib.crc32(data[24:])
 result=dict(bytes=size,sha256=hashlib.sha256(data).hexdigest(),hex=data.hex(),words=list(struct.unpack_from('<20I',data,24)))
 if version==4:
  ext=struct.unpack_from('<8I',data,136);assert ext[0]==0x34414354 and ext[1]==5
  assert ext[2]<=5 and ext[3]<32 and ext[4]<32 and not(ext[4]&~ext[3]) and ext[5]<=3 and ext[6]<1000 and ext[7]<=1
  result.update(active=ext[2],initialized=ext[3],won=ext[4])
 if version==5:
  ext=struct.unpack_from('<8I',data,136);assert ext[0]==0x35414354 and ext[1]==size-232 and ext[2:5]==(0,0,0) and ext[5] in (0,2) and ext[6]<1000 and ext[7]<=1
  arc=data[232:];h=struct.unpack_from('<8I',arc)
  assert h[:3]==(0x31435241,len(arc),1) and h[3]==zlib.crc32(arc[16:])
  assert h[4]<=8 and h[5]<256 and h[6]<256 and not(h[6]&~h[5]) and h[7]<=1
  assert not h[4] or h[5]&(1<<(h[4]-1))
  result.update(active=h[4],initialized=h[5],won=h[6])
 return result

def verify_regions(tx,helper,tag,refs):
 for i,ref in enumerate(refs):
  raw=tx.run(f'{tag}_memory_{i}',f'/tmp/{helper} memory /tmp/{ref["file"]} {ref["offset"]} {ref["bytes"]} {ref["crc32"]}',90)
  assert f'LUMA3D_MEMORY offset={ref["offset"]} bytes={ref["bytes"]} mismatch=0 actual_crc={ref["crc32"]} expected_crc={ref["crc32"]}'.encode() in raw

def once(program,tag,args):
 return (f'( /tmp/{program} {args} < /dev/null > /tmp/{tag}.log 2>&1 & p=$!; echo "$p" > /tmp/{tag}.pid;'
         f' wait "$p"; rc=$?; echo "$rc" > /tmp/{tag}.exit; printf "\\nL3_EXIT_{tag}:%s\\n" "$rc" ) < /dev/null & echo ARCADE_LAUNCHED')

def verify_overlay(tx,helper,tag,ref,both=True):
 for bank in range(ref['bank'],ref['bank']+(2 if both else 1)):
  raw=tx.run(f'{tag}_overlay_{bank}',f'/tmp/{helper} hud /tmp/{ref["file"]} bank{bank} {ref["bytes"]} {ref["crc32"]}',60)
  assert f'LUMA3D_HUD bank={bank} bytes={ref["bytes"]} mismatch=0 actual_crc={ref["crc32"]} expected_crc={ref["crc32"]}'.encode() in raw

def raw_verify(tx,helper,label,path,record):
 raw=tx.run(label,f'/tmp/{helper} raw {path} unused {record["bytes"]} {record["crc32"]}',60)
 assert f'LUMA3D_RAW_OK bytes={record["bytes"]} crc32={record["crc32"]}'.encode() in raw

def decision(scenes,limits):
 assert len(scenes)==3
 first,new,last=[s['result']['elapsed'] for s in scenes];assert min(first,new,last)>0
 slowdown=new/first-1;drift=first/last-1
 return dict(accepted=slowdown<=limits['max_arrival_slowdown'] and abs(drift)<=limits['max_witness_drift'],arrival_slowdown=slowdown,witness_drift=drift,
  scope='One 30-frame window +3 warmup per arrival; terminal witness; no gain or percentile claim',limits=limits)

def recover(tx,m,current,ever,recovery):
 if current:stop(tx,current[0],'cleanup_current',current[1])
 if recovery.get('attempted'):
  # A previous launch may have succeeded before its command/progress reply
  # failed. Never issue it twice. An unpublished or dead PID fails closed.
  assert process(tx,'recovery_existing_process',BASE,recovery['pidfile']), 'Recovery exited; no second automatic launch'
  result=progress(tx,BASE,recovery['log'],'recovery_existing',recovery['pidfile'])
  tx.run('publish_restored_pid','cp '+recovery['pidfile']+' '+LIVE);return result
 if not ever and process(tx,'op2_still_alive',BASE,LIVE):
  assert identity(tx,'preserved_op2_identity')==recovery['baseline_identity'], 'Changed baseline cannot be adopted during recovery'
  one=display(tx.run('preserved_display1','prodockctl display'));time.sleep(3)
  two=display(tx.run('preserved_display2','prodockctl display'))
  # TERM may have succeeded just before the controller lost its reply. Do
  # not call a few final presents a live recovery after that process exits.
  if process(tx,'preserved_op2_still_alive',BASE,LIVE):
   assert identity(tx,'preserved_op2_final_identity')==recovery['baseline_identity']
   assert (two['presents']-one['presents'])&0xffffffff;return two
 tag=m['tag']+'_restore';pidfile='/tmp/'+tag+'.pid';save='/tmp/'+m['tag']+'-op2-recovery.save'
 tx.run('copy_op2_recovery','cp '+BASE_SAVE+' '+save)
 recovery.update(attempted=True,pidfile=pidfile,log=tag+'.log')
 tx.run('restore_op2',f'/tmp/{BASE} --save {save} < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {pidfile}')
 result=progress(tx,BASE,tag+'.log','restored_op2',pidfile);tx.run('publish_restored_pid','cp '+pidfile+' '+LIVE);return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--expected-manifest',required=True);a=p.parse_args();assert sha(a.bundle/'manifest.json')==a.expected_manifest;m=preflight(a.bundle);a.out.mkdir(parents=True,exist_ok=False)
 from check_linux import command
 r=dict(passed=False,manifest_sha256=sha(a.bundle/'manifest.json'),game=m['game'],probe=m['probe_binary'],transfers=[],benchmarks=[],fixtures=[],kernel=RELEASE.decode(),
        fpga='G22r0 continuity, G3D1 signature checked by renderer; no JTAG/reset/write',fpga_writes=0,kernel_writes=0,sd_writes=0,flash_writes=0)
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
    tags=[m['tag']+'_bench'+str(i) for i in range(3)]+[m['tag']+'_'+s['name'] for s in m['fixtures']]+[m['tag']+'_'+x for x in ('replay','resume','live','restore')]
    replay_save='/tmp/'+m['tag']+'-replay.save';resume_save='/tmp/'+m['tag']+'-resume.save';live_save='/tmp/'+m['tag']+'-live.save'
    names=[x+'.pid' for x in tags]+[m['program'],m['probe'],Path(replay_save).name,Path(resume_save).name,Path(live_save).name,m['tag']+'-op2-recovery.save']+m['transfer_files']+[s['fixture_name'] for s in m['fixtures']]
    tx.run('fresh_names',' && '.join('test ! -f /tmp/'+n for n in names))
    readback(tx,'receiver_readback','/tmp/luma-rx',1464,RECEIVER_SHA)
    for name in m['transfer_files']:
     tx.receiver_active=True;r['transfers'].append(tx.transfer(a.bundle/name,name))
    helper=m['helper'];tx.run('helper_mode','chmod 700 /tmp/'+helper)
    raw_verify(tx,helper,'baseline_file','/tmp/'+BASE,m['baseline'])
    raw_verify(tx,helper,'baseline_running_image','/proc/'+str(r['initial_identity']['pid'])+'/exe',m['baseline'])
    for key,output,base in [('delta',m['program'],BASE),('probe_delta',m['probe'],m['program'])]:
     d=m[key];raw=tx.run('install_'+key,f'/tmp/{helper} patch /tmp/{d["file"]} /tmp/{output} {d["patch_bytes"]} {d["patch_crc32"]} /tmp/{base}',90)
     assert f'LUMA3D_UNPACK_OK bytes={d["new_bytes"]} crc32={d["new_crc32"]}'.encode() in raw
     tx.run('mode_'+key,'chmod 700 /tmp/'+output)
    seen=set()
    for s in [*m['benchmarks'],*m['fixtures']]:
     for ref in ([s['pixels'],s['hud']] if 'hud' in s else [s['pixels'],*s['regions']]):
      if not ref or ref['file'] in seen:continue
      seen.add(ref['file']);raw=tx.run('verify_'+ref['file'],f'/tmp/{helper} verify /tmp/{ref["file"]} unused {ref["bytes"]} {ref["crc32"]}')
      assert f'LUMA3D_VERIFY_OK bytes={ref["bytes"]} crc32={ref["crc32"]}'.encode() in raw
    for s in m['fixtures']:
     ref=s['state'];raw=tx.run('unpack_'+s['name'],f'/tmp/{helper} unpack /tmp/{ref["file"]} /tmp/{s["fixture_name"]} {ref["bytes"]} {ref["crc32"]}')
     assert f'LUMA3D_UNPACK_OK bytes={ref["bytes"]} crc32={ref["crc32"]}'.encode() in raw
    assert identity(tx,'op2_before_switch')==r['initial_identity']
    print('ARCADE_READY_SWITCH_IN_10_SECONDS: verified RAM files; op2 baseline, then candidate',flush=True);time.sleep(10)
    stopped=True;stop_baseline(tx,r['initial_identity']);r['baseline_save']=saved_bytes(tx,'baseline_v4_stopped',BASE_SAVE,4)
    released=tx.run('released','prodockctl info; prodockctl display');assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in released;r['released']=display(released)
    for i,s in enumerate(m['benchmarks']):
     program=BASE if s['variant']=='op2' else m['program'];tag=m['tag']+'_bench'+str(i)
     if i==1:print('ARCADE_FIRST_APPEARANCE_IN_10_SECONDS',flush=True);time.sleep(10)
     current=(program,'/tmp/'+tag+'.pid');ever=True
     initial=tx.run(tag+'_launch',supervisor(program,tag,0));assert wait_exit(uart,a.out,tag,initial=initial)==0
     log=tx.run(tag+'_log','cat /tmp/'+tag+'.log');current=None;record=parse(log,s);record['variant']=s['variant']
     verify_pixels(tx,helper,tag,s['pixels']);verify_overlay(tx,helper,tag,s['hud']);record['display']=display(tx.run(tag+'_display','prodockctl display'));r['benchmarks'].append(record)
     print(f'{tag}: pixels/layers PASS, {record["result"]["fps"]} FPS',flush=True)
    r['comparison']=decision(r['benchmarks'],m['acceptance'])
    if not r['comparison']['accepted']:
     r['restored_display']=recover(tx,m,current,ever,recovery);r['restored_op2']=True;r['left_running']=BASE+' automatic; candidate not promoted';r['functional_checks_completed']=False;return
    for s in m['fixtures']:
     tag=m['tag']+'_'+s['name'];current=(m['probe'],'/tmp/'+tag+'.pid')
     initial=tx.run(tag+'_launch',once(m['probe'],tag,'--scene /tmp/'+s['fixture_name']));assert wait_exit(uart,a.out,tag,initial=initial)==0
     log=tx.run(tag+'_log','cat /tmp/'+tag+'.log');current=None;actual=fields(log,'AR_SCENE');assert actual==s['host_scene'];assert fields(log,'AR_PRESENT')==s['host_present'];assert re.search(rb'^AR_PASS\r?$',log,re.M)
     c=game_counters(log);assert c['frames']==3
     for k in ('vertices','triangles','slivers'):assert c[k]==s['oracle'][k],(s['name'],k,c[k],s['oracle'][k])
     if s['pixels']:verify_pixels(tx,helper,tag,s['pixels'])
     verify_regions(tx,helper,tag,s['regions']);record=dict(name=s['name'],fixture=True,scene=actual,counters=c,render=fields(log,'AR_RENDER'),display=display(tx.run(tag+'_display','prodockctl display')));r['fixtures'].append(record)
     print(f'{tag}: 3-frame fixture pixels/indexed banks PASS',flush=True)
    tag=m['tag']+'_replay';current=(m['probe'],'/tmp/'+tag+'.pid')
    initial=tx.run('replay_launch',once(m['probe'],tag,'--replay '+replay_save));assert wait_exit(uart,a.out,tag,timeout=900,initial=initial)==0
    log=tx.run('replay_log','cat /tmp/'+tag+'.log',90);current=None;r['replay']=fields(log,'AR_COMPLETE');r['replay_render']=fields(log,'AR_RENDER');r['replay_counters']=game_counters(log)
    assert r['replay']==m['host_replay'];assert r['replay_counters']['frames']==r['replay']['rendered_frames'] and re.search(rb'^AR_PASS\r?$',log,re.M)
    assert len(re.findall(rb'^AR_RELOAD active=',log,re.M))==8
    r['replay_save']=saved_bytes(tx,'replay_save',replay_save,5);assert r['replay_save']['won']==255 and not r['replay_save']['active']
    checked=tx.run('replay_codec','/tmp/'+m['probe']+' --inspect-save '+replay_save);assert fields(checked,'AR_SAVE')['won']==255
    r['after_replay']=display(tx.run('after_replay','prodockctl display'))
    # Resume one active challenge in the exact user executable, not the probe.
    active=next(s for s in m['fixtures'] if s['name']=='activity_6_boss');tx.run('copy_resume','cp /tmp/'+active['fixture_name']+' '+resume_save)
    tag=m['tag']+'_resume';current=(m['program'],'/tmp/'+tag+'.pid')
    initial=tx.run('resume_launch',once(m['program'],tag,'--manual --frames 1 --save '+resume_save));assert wait_exit(uart,a.out,tag,initial=initial)==0
    log=tx.run('resume_log','cat /tmp/'+tag+'.log');current=None;assert b'LUMA3D_SAVE loaded' in log and b'LUMA3D_SAVE saved' in log
    r['resume_counters']=game_counters(log);assert r['resume_counters']['frames']==1
    r['resume_save']=saved_bytes(tx,'resume_save',resume_save,5);assert r['resume_save']['sha256']==m['resume_expected']['sha256']
    verify_regions(tx,helper,tag,[active['regions'][0],*active['regions'][2:]]);r['after_resume']=display(tx.run('after_resume','prodockctl display'))
    r['baseline_save_final']=saved_bytes(tx,'baseline_v4_final',BASE_SAVE,4);assert r['baseline_save_final']['sha256']==r['baseline_save']['sha256']
    tag=m['tag']+'_live';current=(m['program'],'/tmp/'+tag+'.pid')
    tx.run('copy_live_v5','cp '+BASE_SAVE+' '+live_save)
    tx.run('live_launch',f'/tmp/{m["program"]} --save {live_save} < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {current[1]}')
    r['live_display']=progress(tx,m['program'],tag+'.log','live',current[1]);tx.run('publish_live_pid','cp '+current[1]+' '+LIVE)
    r['live_identity']=tx.run('live_identity','p=`cat '+LIVE+'`; cat /proc/$p/stat').decode(errors='replace')
    r['baseline_save_after_live']=saved_bytes(tx,'baseline_v4_after_live',BASE_SAVE,4);assert r['baseline_save_after_live']['sha256']==r['baseline_save']['sha256']
    r['passed']=True;r['left_running']=m['program']+' main-mission automatic visit at Amber arrival; eight optional activities available in manual play, not an automatic activities tour; save '+live_save+' volatile RAM'
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
