#!/usr/bin/env python3
"""Bounded amber/save V3 trial; ws1 fallback, RAM only."""
import argparse,fcntl,hashlib,json,math,re,signal,struct,time,zlib
from pathlib import Path
import serial
from prodock_transport import Transport,RECEIVER_SHA
from prodock_valley_ab import process,stop,launch,progress,PORT,RELEASE
from prodock_valley_trial import sha,display,game_counters
from prodock_valley_benchmark import readback,supervisor,wait_exit,fields
from prodock_order import parse,verify_pixels,verify_hud,abort_receiver
BASE="luma3d-ws1"
BASE_SAVE="/tmp/ws1-live.save"
LIVE="/tmp/luma3d-live.pid"
NEW_SHA='62a9178dab260dc5e60be8b9bcea90b35f370357691fb157e5d7fd45a90616ee'
BASE_SHA='78afc779447e76f221b509f7b3e4c9a2abb347f98ab405f23001c9567a75050c'
def identity(tx,label):
 assert process(tx,label+'_alive',BASE,LIVE)
 raw=tx.run(label+'_identity','p=`cat '+LIVE+'`; cat /proc/$p/stat; cat /proc/$p/cmdline; echo')
 line=re.search(rb'^(\d+) \('+BASE.encode()+rb'\) ([^\r\n]+)',raw,re.M);assert line
 rest=line[2].split();assert rest[0] not in (b'Z',b'X') and len(rest)>=20
 assert re.search(rb'^/tmp/'+BASE.encode()+rb'(?:\x00|\r?$)',raw,re.M)
 assert b'--save\x00/tmp/ws1-live.save' in raw or b'--save\x00/tmp/am' in raw
 return dict(pid=int(line[1]),start_ticks=int(rest[19]))
def recover(tx,m,current,ever):
 if current:stop(tx,current[0],'cleanup_current',current[1])
 if not ever and process(tx,'ws1_still_alive',BASE,LIVE):
  one=display(tx.run('preserved_display1','prodockctl display'));time.sleep(3)
  two=display(tx.run('preserved_display2','prodockctl display'));assert (two['presents']-one['presents'])&0xffffffff;return two
 tag=m['tag']+'_restore';pidfile='/tmp/'+tag+'.pid';save='/tmp/'+m['tag']+'-ws1-recovery.save'
 tx.run('copy_ws1_recovery','cp '+BASE_SAVE+' '+save)
 tx.run('restore_ws1',f'/tmp/{BASE} --save {save} < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {pidfile}')
 result=progress(tx,BASE,tag+'.log','restored_ws1',pidfile);tx.run('publish_restored_pid','cp '+pidfile+' '+LIVE);return result
def preflight(bundle):
 m=json.loads((bundle/'manifest.json').read_text())
 assert m['initial_guard']==dict(pid=1331,start_ticks=8373701)
 assert m['candidate'] and m['game']['sha256']==NEW_SHA and m['baseline']['sha256']==BASE_SHA
 assert re.fullmatch(r'am[0-9]+',m['tag']) and m['program']=='luma3d-'+m['tag'] and m['helper']==m['tag']+'-helper'
 for name,r in m['files'].items():
  assert re.fullmatch(r'[A-Za-z0-9_.-]+',name)
  p=bundle/name;assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],name
 for name in ('prodock_amber.py','prodock_order.py','prodock_transport.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','check_linux.py','check_gpu_reloads.py'):
  assert sha(Path(__file__).with_name(name))==m['files'][name]['sha256']
 assert json.loads((bundle/'game_manifest.json').read_text())['riscv']==m['game']
 assert m['validation']['passed'] and not m['validation']['hardware'] and m['validation']['binaries']['riscv']==m['game']
 d=m['delta'];assert d['old_sha256']==BASE_SHA and d['new_sha256']==NEW_SHA and d['new_bytes']==m['game']['bytes'] and d['new_crc32']==m['game']['crc32']
 assert [(s['variant'],s['pose']) for s in m['scenes']]==[('ws1',0),('new',0),('new',10730),('new',11990),('new',12500),('new',14720),('ws1',0)]
 for s in m['scenes']:
  assert s['pixels']['bytes']==192000 and s['pixels']['sha256']==s['oracle']['image_sha256']
  assert 0<s['hud']['bytes']<=240000 and not s['hud']['bytes']%800
  for ref in (s['pixels'],s['hud']):assert ref['file'] in m['files']
 assert m['acceptance']==dict(max_arrival_slowdown=.10,max_witness_drift=.05)
 assert m['transfer_files']==[m['helper'],d['file'],*m['new_references']]
 return m
def saved_bytes(tx,label,path,version=3):
 raw=tx.run(label,'od -b -v '+path);data=bytearray()
 for line in raw.replace(b'\r',b'').splitlines():
  if re.fullmatch(rb'[0-7]{7,} (?:[0-7]{3} ?){1,16}',line.strip()):data.extend(int(x,8) for x in line.split()[1:])
 assert len(data)==136 and data[:8]==b'L3PROG1\0'
 expected_version=version
 size,campaign,version,checksum=struct.unpack_from('<4I',data,8)
 assert size==136 and campaign==0x56414c31 and version==expected_version and zlib.crc32(data[24:])==checksum
 w=struct.unpack_from('<20I',data,24);records=[struct.unpack_from('<2I',data,104+i*8) for i in range(4)]
 assert w[0]==4 and w[1]==4 and w[2]==3 and w[3]==1 and w[5]==0 and w[6]==0 and w[7]<15 and w[8] in (0,2)
 if version==2:assert w[18]==(4|(3<<3)|(2<<5)|(5<<7)) and w[19]<30
 else:assert version==3 and w[18]==(4|(3<<3)|(2<<5)|(5<<7)|(5<<11)|(1<<14)|(2<<15)) and w[19]==0
 assert records==[(0x4c455431+i,1) for i in range(4)]
 floats=struct.unpack_from('<8f',data,24+40);assert all(math.isfinite(x) for x in floats)
 assert 0<=floats[0]<=160 and 0<=floats[2]<=160 and 0<=floats[6] and 0<=floats[7]
 return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),words=list(w),records=records,float_fields=list(floats),hex=data.hex())
def once(program,tag,arguments):
 return (f'( /tmp/{program} {arguments} < /dev/null > /tmp/{tag}.log 2>&1 & p=$!; echo "$p" > /tmp/{tag}.pid;'
         f' wait "$p"; rc=$?; echo "$rc" > /tmp/{tag}.exit; printf "\\nL3_EXIT_{tag}:%s\\n" "$rc" ) < /dev/null & echo SURFACE_LAUNCHED')
def decision(scenes,limits):
 assert len(scenes)==7
 first,after=scenes[0]['result'],scenes[-1]['result'];new=scenes[1]['result']
 slowdown=new['elapsed']/first['elapsed']-1;drift=first['elapsed']/after['elapsed']-1
 return dict(accepted=slowdown<=limits['max_arrival_slowdown'] and abs(drift)<=limits['max_witness_drift'],arrival_slowdown=slowdown,witness_drift=drift,limits=limits,
  scope='30 frames +3 warmup at arrival, with terminal witness. The valley passage intentionally differs; not an identical-pixel optimization test or percentile claim.')
def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();m=preflight(a.bundle);a.out.mkdir(parents=True,exist_ok=False)
 from check_linux import command
 r=dict(passed=False,manifest_sha256=sha(a.bundle/'manifest.json'),game=m['game'],transfers=[],scenes=[],kernel=RELEASE.decode(),fpga='G22r0 continuity; unchanged FPGA, G3D signature at renderer open',fpga_writes=0,kernel_writes=0,sd_writes=0,flash_writes=0)
 def interrupted(n,frame):raise KeyboardInterrupt('Signal '+str(n))
 signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGHUP,interrupted)
 with open('/tmp/prodock-diagnostic.lock','a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
   tx=Transport(uart,command,a.out);stopped=False;current=None;ever=False
   try:
    uart.write(b'\n');time.sleep(.2);uart.read(16000)
    before=tx.run('before','uname -r; prodockctl display; cat /proc/mounts')
    assert re.search(rb'^'+RELEASE+rb'\r?$',before,re.M) and b'tmpfs /tmp tmpfs ' in before and not re.search(rb'^/dev/mmc\S* ',before,re.M)
    r['before']=display(before);r['initial_identity']=identity(tx,'initial_ws1');assert r['initial_identity']==m['initial_guard']
    tags=[m['tag']+'_'+str(i) for i in range(7)]+[m['tag']+'_'+s for s in ('endurance','resume','live','restore')]
    save='/tmp/'+m['tag']+'-progress.save';live_save='/tmp/'+m['tag']+'-live.save'
    names=[t+'.pid' for t in tags]+[m['program'],Path(save).name,Path(live_save).name,m['tag']+'-ws1-recovery.save']+m['transfer_files']
    tx.run('fresh_names',' && '.join('test ! -f /tmp/'+n for n in names))
    readback(tx,'receiver_readback','/tmp/luma-rx',1464,RECEIVER_SHA)
    for name in m['transfer_files']:
     tx.receiver_active=True;r['transfers'].append(tx.transfer(a.bundle/name,name))
    helper=m['helper'];tx.run('helper_mode','chmod 700 /tmp/'+helper);d=m['delta']
    raw=tx.run('install',f'/tmp/{helper} patch /tmp/{d["file"]} /tmp/{m["program"]} {d["patch_bytes"]} {d["patch_crc32"]} /tmp/{BASE}',90)
    assert f'LUMA3D_UNPACK_OK bytes={m["game"]["bytes"]} crc32={m["game"]["crc32"]}'.encode() in raw
    tx.run('candidate_mode','chmod 700 /tmp/'+m['program']);seen=set()
    for i,s in enumerate(m['scenes']):
     for kind in ('pixels','hud'):
      ref=s[kind]
      if ref['file'] in seen:continue
      seen.add(ref['file']);raw=tx.run(f'verify_{i}_{kind}',f'/tmp/{helper} verify /tmp/{ref["file"]} unused {ref["bytes"]} {ref["crc32"]}')
      assert f'LUMA3D_VERIFY_OK bytes={ref["bytes"]} crc32={ref["crc32"]}'.encode() in raw
    assert identity(tx,'ws1_before_switch')==r['initial_identity']
    print('AMBER_READY_SWITCH_IN_10_SECONDS: transfer verified; ws1 baseline first, candidate announcement follows',flush=True);time.sleep(10)
    stopped=True;stop(tx,BASE,'stop_ws1');r['baseline_v2']=saved_bytes(tx,'baseline_v2_stopped',BASE_SAVE,2);raw=tx.run('released','prodockctl info; prodockctl display')
    assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in raw;r['released']=display(raw)
    for i,s in enumerate(m['scenes']):
     program=BASE if s['variant']=='ws1' else m['program'];tag=tags[i]
     if i==1:print('AMBER_FIRST_APPEARANCE_IN_10_SECONDS',flush=True);time.sleep(10)
     current=(program,'/tmp/'+tag+'.pid');ever=True
     initial=tx.run(tag+'_launch',supervisor(program,tag,s['pose']));assert wait_exit(uart,a.out,tag,initial=initial)==0
     log=tx.run(tag+'_log','cat /tmp/'+tag+'.log');current=None;record=parse(log,s);record.update(variant=s['variant'],pose=s['pose'])
     verify_pixels(tx,helper,tag,s['pixels']);verify_hud(tx,helper,tag,s['hud']);record['display']=display(tx.run(tag+'_display','prodockctl display'));r['scenes'].append(record)
     print(f'{tag} pose={s["pose"]}: pixels/HUD PASS, {record["result"]["fps"]} FPS',flush=True)
    r['comparison']=decision(r['scenes'],m['acceptance'])
    if not r['comparison']['accepted']:
     r['restored_display']=recover(tx,m,current,ever);r['restored_ws1']=True;r['passed']=True;r['left_running']=BASE+' automatic; Amber candidate not promoted'
     r['live_identity']=tx.run('restored_identity','p=`cat '+LIVE+'`; cat /proc/$p/stat').decode(errors='replace');return
    tag=m['tag']+'_endurance';current=(m['program'],'/tmp/'+tag+'.pid')
    tx.run('endurance_launch',f'/tmp/{m["program"]} --save {save} < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {current[1]}')
    r['warm_display']=progress(tx,m['program'],tag+'.log','warm',current[1]);begin=time.monotonic();print('AMBER_ENDURANCE: 300 seconds with /tmp autosave, no UART writes',flush=True)
    while time.monotonic()-begin<300:time.sleep(min(5,max(0,300-(time.monotonic()-begin))))
    assert process(tx,'endurance_alive',m['program'],current[1]);stop(tx,m['program'],'endurance_stop',current[1]);current=None
    log=tx.run('endurance_log','cat /tmp/'+tag+'.log');r['endurance']=fields(log,'LUMA3D_RESULT');r['story']=fields(log,'LUMA3D_STORY');r['endurance_counters']=game_counters(log)
    assert r['endurance']['elapsed']>=300 and r['endurance']['frames']>1 and r['story']['sim']>=244.9
    assert all(r['story'][k]==v for k,v in dict(phase=4,relay=3,discovered=1,collected=4,complete=1,auto=1).items())
    r['workshop']=fields(log,'LUMA3D_WORKSHOP');assert all(r['workshop'][k]==v for k,v in dict(phase=4,mode=5,copper=3,blue=2).items())
    r['amber']=fields(log,'LUMA3D_AMBER');assert all(r['amber'][k]==v for k,v in dict(region=0,phase=5,point=0,intake=1,sluice=2).items())
    r['after_endurance']=display(tx.run('after_endurance','prodockctl display'));r['save_before_resume']=saved_bytes(tx,'save_before_resume',save)
    tag=m['tag']+'_resume';current=(m['program'],'/tmp/'+tag+'.pid')
    initial=tx.run('resume_launch',once(m['program'],tag,'--manual --frames 1 --save '+save));assert wait_exit(uart,a.out,tag,initial=initial)==0
    log=tx.run('resume_log','cat /tmp/'+tag+'.log');current=None;r['resume_story']=fields(log,'LUMA3D_STORY');r['resume_counters']=game_counters(log)
    assert r['resume_counters']['frames']==1 and r['resume_story']['auto']==0
    for k in ('phase','relay','discovered','collected','complete'):assert r['resume_story'][k]==r['story'][k]
    r['resume_workshop']=fields(log,'LUMA3D_WORKSHOP');assert r['resume_workshop']==r['workshop']
    r['resume_amber']=fields(log,'LUMA3D_AMBER');assert r['resume_amber']==r['amber']
    r['save_after_resume']=saved_bytes(tx,'save_after_resume',save)
    assert r['save_before_resume']['sha256']==r['save_after_resume']['sha256']
    assert r['save_before_resume']['words'][:10]==r['save_after_resume']['words'][:10]
    assert r['save_before_resume']['records']==r['save_after_resume']['records']
    assert r['save_before_resume']['words'][18:]==r['save_after_resume']['words'][18:]
    r['after_resume']=display(tx.run('after_resume','prodockctl display'))
    tag=m['tag']+'_live';current=(m['program'],'/tmp/'+tag+'.pid')
    tx.run('live_launch',f'/tmp/{m["program"]} --advance 10730 --save {live_save} < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {current[1]}')
    r['live_display']=progress(tx,m['program'],tag+'.log','live',current[1]);tx.run('publish_live_pid','cp '+current[1]+' '+LIVE)
    r['live_identity']=tx.run('live_identity','p=`cat '+LIVE+'`; cat /proc/$p/stat').decode(errors='replace')
    r['baseline_v2_final']=saved_bytes(tx,'baseline_v2_final',BASE_SAVE,2);assert r['baseline_v2_final']['sha256']==r['baseline_v2']['sha256']
    r['passed']=True;r['left_running']=m['program']+' automatic visit at Amber region arrival (--advance 10730 actual simulation), save '+live_save+' (volatile RAM); ws1 and V2 preserved'
   except BaseException as e:
    r['error']=repr(e)
    try:abort_receiver(tx,uart,a.out)
    except BaseException as e:r['receiver_abort_error']=repr(e)
    if stopped:
     try:
      uart.write(b'\x03');uart.flush();time.sleep(.3);uart.read(16000);r['restored_display']=recover(tx,m,current,ever);r['restored_ws1']=True
     except BaseException as e:r['cleanup_error']=repr(e)
    raise
   finally:(a.out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
if __name__=='__main__':main()
