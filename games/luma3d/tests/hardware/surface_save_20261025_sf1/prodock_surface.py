#!/usr/bin/env python3
"""Bounded canonical-surface/save trial; art3 fallback, RAM only."""
import argparse,fcntl,hashlib,json,math,re,signal,struct,time,zlib
from pathlib import Path
import serial
from prodock_transport import Transport,RECEIVER_SHA
from prodock_valley_ab import process,stop,launch,progress,PORT,RELEASE
from prodock_valley_trial import sha,display,game_counters
from prodock_valley_benchmark import readback,supervisor,wait_exit,fields
from prodock_order import identity,parse,verify_pixels,verify_hud,abort_receiver,recover,BASE,LIVE
NEW_SHA='ad74b613145bf410c55ac3501962ecea9089f448d84a40e3056bff8671f09d8d'
BASE_SHA='7fa1062373664d977c26bf6df2a4a5075d64061b967fc3d6d9b831a841302882'
def preflight(bundle):
 m=json.loads((bundle/'manifest.json').read_text())
 assert m['candidate'] and m['game']['sha256']==NEW_SHA and m['baseline']['sha256']==BASE_SHA
 assert re.fullmatch(r'sf[0-9]+',m['tag']) and m['program']=='luma3d-'+m['tag'] and m['helper']==m['tag']+'-helper'
 for name,r in m['files'].items():
  assert re.fullmatch(r'[A-Za-z0-9_.-]+',name)
  p=bundle/name;assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],name
 for name in ('prodock_surface.py','prodock_order.py','prodock_transport.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','check_linux.py','check_gpu_reloads.py'):
  assert sha(Path(__file__).with_name(name))==m['files'][name]['sha256']
 assert json.loads((bundle/'game_manifest.json').read_text())['riscv']==m['game']
 assert m['validation']['passed'] and not m['validation']['hardware'] and m['validation']['runtime']==m['game']
 d=m['delta'];assert d['old_sha256']==BASE_SHA and d['new_sha256']==NEW_SHA and d['new_bytes']==m['game']['bytes'] and d['new_crc32']==m['game']['crc32']
 assert [(s['variant'],s['pose']) for s in m['scenes']]==[('art3',0),('new',0),('new',1450),('new',3800),('art3',0)]
 for s in m['scenes']:
  assert s['pixels']['bytes']==192000 and s['pixels']['sha256']==s['oracle']['image_sha256']
  assert 0<s['hud']['bytes']<=240000 and not s['hud']['bytes']%800
  for ref in (s['pixels'],s['hud']):assert ref['file'] in m['files']
 assert m['acceptance']==dict(max_arrival_slowdown=.10,max_witness_drift=.05)
 assert m['transfer_files']==[m['helper'],d['file'],*m['new_references']]
 return m
def saved_bytes(tx,label,path):
 raw=tx.run(label,'od -b -v '+path);data=bytearray()
 for line in raw.replace(b'\r',b'').splitlines():
  if re.fullmatch(rb'[0-7]{7,} (?:[0-7]{3} ?){1,16}',line.strip()):data.extend(int(x,8) for x in line.split()[1:])
 assert len(data)==136 and data[:8]==b'L3PROG1\0'
 size,campaign,version,checksum=struct.unpack_from('<4I',data,8)
 assert size==136 and campaign==0x56414c31 and version==1 and zlib.crc32(data[24:])==checksum
 w=struct.unpack_from('<20I',data,24);records=[struct.unpack_from('<2I',data,104+i*8) for i in range(4)]
 assert w[0]==4 and w[1]==4 and w[2]==3 and w[3]==1 and w[5]==0 and w[6]==0 and w[7]<15 and w[8] in (0,2) and w[18:]==(0,0)
 assert records==[(0x4c455431+i,1) for i in range(4)]
 floats=struct.unpack_from('<8f',data,24+40);assert all(math.isfinite(x) for x in floats)
 assert 0<=floats[0]<=160 and 0<=floats[2]<=160 and 0<=floats[6] and 0<=floats[7]
 return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),words=list(w),records=records,float_fields=list(floats),hex=data.hex())
def once(program,tag,arguments):
 return (f'( /tmp/{program} {arguments} < /dev/null > /tmp/{tag}.log 2>&1 & p=$!; echo "$p" > /tmp/{tag}.pid;'
         f' wait "$p"; rc=$?; echo "$rc" > /tmp/{tag}.exit; printf "\\nL3_EXIT_{tag}:%s\\n" "$rc" ) < /dev/null & echo SURFACE_LAUNCHED')
def decision(scenes,limits):
 assert len(scenes)==5
 first,after=scenes[0]['result'],scenes[-1]['result'];new=scenes[1]['result']
 slowdown=new['elapsed']/first['elapsed']-1;drift=first['elapsed']/after['elapsed']-1
 return dict(accepted=slowdown<=limits['max_arrival_slowdown'] and abs(drift)<=limits['max_witness_drift'],arrival_slowdown=slowdown,witness_drift=drift,limits=limits,
  scope='30 frames +3 warmup at arrival, with terminal witness. World collision/anchors intentionally differ; not an identical-pixel optimization test or percentile claim.')
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
    r['before']=display(before);r['initial_identity']=identity(tx,'initial_art3')
    tags=[m['tag']+'_'+str(i) for i in range(5)]+[m['tag']+'_'+s for s in ('endurance','resume','live','restore')]
    save='/tmp/'+m['tag']+'-progress.save';live_save='/tmp/'+m['tag']+'-live.save'
    names=[t+'.pid' for t in tags]+[m['program'],Path(save).name,Path(live_save).name]+m['transfer_files']
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
    assert identity(tx,'art3_before_switch')==r['initial_identity']
    print('SURFACE_READY: transfer verified; art3 baseline first, candidate announcement follows',flush=True)
    stopped=True;stop(tx,BASE,'stop_art3');raw=tx.run('released','prodockctl info; prodockctl display')
    assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in raw;r['released']=display(raw)
    for i,s in enumerate(m['scenes']):
     program=BASE if s['variant']=='art3' else m['program'];tag=tags[i]
     if i==1:print('SURFACE_FIRST_APPEARANCE_IN_10_SECONDS',flush=True);time.sleep(10)
     current=(program,'/tmp/'+tag+'.pid');ever=True
     initial=tx.run(tag+'_launch',supervisor(program,tag,s['pose']));assert wait_exit(uart,a.out,tag,initial=initial)==0
     log=tx.run(tag+'_log','cat /tmp/'+tag+'.log');current=None;record=parse(log,s);record.update(variant=s['variant'],pose=s['pose'])
     verify_pixels(tx,helper,tag,s['pixels']);verify_hud(tx,helper,tag,s['hud']);record['display']=display(tx.run(tag+'_display','prodockctl display'));r['scenes'].append(record)
     print(f'{tag} pose={s["pose"]}: pixels/HUD PASS, {record["result"]["fps"]} FPS',flush=True)
    r['comparison']=decision(r['scenes'],m['acceptance'])
    if not r['comparison']['accepted']:
     tag=m['tag']+'_restore';current=(BASE,'/tmp/'+tag+'.pid')
     launch(tx,BASE,tag+'.log','restore_art3',current[1]);r['restored_display']=progress(tx,BASE,tag+'.log','restored_art3',current[1]);tx.run('publish_restored_pid','cp '+current[1]+' '+LIVE)
     r['restored_art3']=True;r['passed']=True;r['left_running']=BASE+' automatic; surface not promoted'
     r['live_identity']=tx.run('restored_identity','p=`cat '+LIVE+'`; cat /proc/$p/stat').decode(errors='replace');return
    tag=m['tag']+'_endurance';current=(m['program'],'/tmp/'+tag+'.pid')
    tx.run('endurance_launch',f'/tmp/{m["program"]} --save {save} < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {current[1]}')
    r['warm_display']=progress(tx,m['program'],tag+'.log','warm',current[1]);begin=time.monotonic();print('SURFACE_ENDURANCE: 120 seconds with /tmp autosave, no UART writes',flush=True)
    while time.monotonic()-begin<120:time.sleep(min(5,max(0,120-(time.monotonic()-begin))))
    assert process(tx,'endurance_alive',m['program'],current[1]);stop(tx,m['program'],'endurance_stop',current[1]);current=None
    log=tx.run('endurance_log','cat /tmp/'+tag+'.log');r['endurance']=fields(log,'LUMA3D_RESULT');r['story']=fields(log,'LUMA3D_STORY');r['endurance_counters']=game_counters(log)
    assert r['endurance']['elapsed']>=120 and r['endurance']['frames']>1 and r['story']['sim']>=61.8
    assert all(r['story'][k]==v for k,v in dict(phase=4,relay=3,discovered=1,collected=4,complete=1,auto=1).items())
    r['after_endurance']=display(tx.run('after_endurance','prodockctl display'));r['save_before_resume']=saved_bytes(tx,'save_before_resume',save)
    tag=m['tag']+'_resume';current=(m['program'],'/tmp/'+tag+'.pid')
    initial=tx.run('resume_launch',once(m['program'],tag,'--manual --frames 1 --save '+save));assert wait_exit(uart,a.out,tag,initial=initial)==0
    log=tx.run('resume_log','cat /tmp/'+tag+'.log');current=None;r['resume_story']=fields(log,'LUMA3D_STORY');r['resume_counters']=game_counters(log)
    assert r['resume_counters']['frames']==1 and r['resume_story']['auto']==0
    for k in ('phase','relay','discovered','collected','complete'):assert r['resume_story'][k]==r['story'][k]
    r['save_after_resume']=saved_bytes(tx,'save_after_resume',save)
    assert r['save_before_resume']['words'][:10]==r['save_after_resume']['words'][:10]
    assert r['save_before_resume']['records']==r['save_after_resume']['records']
    r['after_resume']=display(tx.run('after_resume','prodockctl display'))
    tag=m['tag']+'_live';current=(m['program'],'/tmp/'+tag+'.pid')
    tx.run('live_launch',f'/tmp/{m["program"]} --save {live_save} < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {current[1]}')
    r['live_display']=progress(tx,m['program'],tag+'.log','live',current[1]);tx.run('publish_live_pid','cp '+current[1]+' '+LIVE)
    r['live_identity']=tx.run('live_identity','p=`cat '+LIVE+'`; cat /proc/$p/stat').decode(errors='replace')
    r['passed']=True;r['left_running']=m['program']+' automatic fresh visit, save '+live_save+' (volatile RAM); art3 preserved'
   except BaseException as e:
    r['error']=repr(e)
    try:abort_receiver(tx,uart,a.out)
    except BaseException as e:r['receiver_abort_error']=repr(e)
    if stopped:
     try:
      uart.write(b'\x03');uart.flush();time.sleep(.3);uart.read(16000);r['restored_display']=recover(tx,m,current,ever);r['restored_art3']=True
     except BaseException as e:r['cleanup_error']=repr(e)
    raise
   finally:(a.out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
if __name__=='__main__':main()
