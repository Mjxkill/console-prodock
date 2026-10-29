#!/usr/bin/env python3
"""MO1: same-scene HUD cost measurement; always restore the exact live R6."""
import argparse,fcntl,hashlib,json,math,re,signal,time,zlib
from pathlib import Path
import serial
from prodock_transport import Transport,RECEIVER_SHA
from prodock_valley_ab import PORT,RELEASE
from prodock_valley_trial import sha,display,game_counters
from prodock_valley_benchmark import readback,wait_exit
from prodock_order import verify_pixels,abort_receiver
from prodock_arcade import saved_bytes,verify_regions,raw_verify,once
import trial_guards as guard

DEPENDENCIES=('prodock_motion.py','trial_guards.py','prodock_arcade.py','prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','check_linux.py','check_gpu_reloads.py')
WINDOWS=[dict(variant='baseline',kind=4,frames=360),dict(variant='candidate',kind=4,frames=360),dict(variant='candidate',kind=6,frames=600),dict(variant='baseline',kind=6,frames=600)]

def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')

def preflight(bundle):
 m=json.loads((bundle/'manifest.json').read_text())
 assert m['candidate'] and not m['hardware_tested'] and m['baseline']['sha256']==guard.BASE_SHA
 assert re.fullmatch(r'mo[0-9]+',m['tag']) and m['helper']==m['tag']+'-helper'
 assert m['expected_identity']==dict(pid=2472,start_ticks=21513398)
 for name,r in m['files'].items():
  assert re.fullmatch(r'[A-Za-z0-9_.-]+',name) and digest(bundle/name)==r,name
 for name in DEPENDENCIES:assert digest(Path(__file__).with_name(name))==m['files'][name],name
 assert json.loads((bundle/'baseline_manifest.json').read_text())['riscv']==m['baseline']
 pv=json.loads((bundle/'probe_validation.json').read_text())
 assert pv['passed'] and not pv['hardware'] and pv['game_manifest_sha256']==sha(bundle/'game_manifest.json')
 rv=json.loads((bundle/'probe_rv32_validation.json').read_text())
 assert rv['passed'] and not rv['hardware'] and rv['probe_manifest_sha256']==sha(bundle/'probe_validation.json')
 assert len(rv['records'])==4 and len(pv['records'])==8
 for r in rv['records']:
  v=r['name'].split('_')[0];assert r['passed'] and r['memory_changed_bytes']==0 and r['commands_identical'] and r['overlay_identical']
  assert r['elf_sha256']==m['probes'][v]['binary']['sha256']
 for variant in ('baseline','candidate'):
  q=m['probes'][variant];assert q['program']==m['tag']+'-'+variant and q['binary']==pv['files'][variant+'-riscv']
  old=m['baseline'] if variant=='baseline' else m['probes']['baseline']['binary'];d=q['delta']
  assert d['old_sha256']==old['sha256'] and d['new_sha256']==q['binary']['sha256'] and d['new_bytes']==q['binary']['bytes'] and d['new_crc32']==q['binary']['crc32']
 assert m['windows']==WINDOWS and m['wall']==dict(kind=4,seconds=20) and m['deadlines']==dict(fixture=180,window=600,wall=120)
 assert [f['kind'] for f in m['fixtures']]==[4,6]
 refs=[]
 for f in m['fixtures']:
  assert f['region']['offset']==22<<20 and f['region']['bytes']==384000
  if f['kind']==4:assert f['pixels']['bytes']==192000 and f['pixels']['sha256']==f['oracle']['image_sha256'];refs.append(f['pixels'])
  else:assert f['pixels'] is None
  refs.append(f['region'])
 assert refs==m['references']
 assert m['transfer_files']==[m['helper'],*[m['probes'][v]['delta']['file'] for v in ('baseline','candidate')],*[r['file'] for r in refs]]
 assert len(set(m['transfer_files']))==len(m['transfer_files'])
 local=json.loads((bundle/'fixed_windows.json').read_text());assert local['passed'] and not local['hardware'] and local['windows']==WINDOWS
 for r in local['records']:assert r['elf_sha256']==pv['files'][r['variant']+'-host']['sha256']
 prior=json.loads((bundle/'prior_result.json').read_text())
 assert prior['passed'] and prior['live_identity']==m['expected_identity'] and prior['game']==m['baseline']
 return m

def parse_result(raw,kind,frames=0,wall=0,hardware=1):
 assert b'LUMA3D_SAVE ' not in raw
 markers=re.findall(rb'^MOTION_PROBE ([^\r\n]+)',raw,re.M);assert len(markers)==1
 marker=dict((k.decode(),v.decode()) for k,v in re.findall(rb'(\w+)=(\S+)',markers[0]))
 assert marker['kind']==str(kind) and marker['fixed_frames']==str(frames) and marker['wall_seconds']==str(wall)
 assert marker['hardware']==str(hardware) and marker['replay_without_render']=='1' and marker['saves']=='disabled' and int(marker['replay_steps'])>0
 lines=re.findall(rb'^MOTION_RESULT ([^\r\n]+)',raw,re.M);assert len(lines)==1
 values=dict((k.decode(),v.decode()) for k,v in re.findall(rb'(\w+)=(\S+)',lines[0]))
 assert re.fullmatch(r'[0-9a-f]{8}',values['state_crc32'])
 d={k:(v if k=='state_crc32' else float(v)) for k,v in values.items()}
 assert all(math.isfinite(v) and v>=0 for k,v in d.items() if k!='state_crc32')
 assert d['kind']==kind and d['hardware']==hardware and d['ok']==1 and d['frames']>0 and d['wall']>0
 assert d['queue_overflows']==0 and d['max_frame']<=d['frame_sum']+.00001
 assert abs(d['frame_sum']-d['wall'])<=.1 and d['frame_sum']>0
 costs=sum(d[k] for k in ('simulation','preparation','submit','present'))
 assert costs<=d['frame_sum']+.002 and d['ui_raster']+d['ui_publish']<=d['preparation']+.002
 assert d['overflow']<=d['frames']
 for p in ('p95_upper_ms','p99_upper_ms'):
  assert d[p]==0 or (4<=d[p]<=1020 and d[p]%4==0)
  if d[p]==0:assert d['overflow']>0
 if d['p95_upper_ms'] and d['p99_upper_ms']:assert d['p95_upper_ms']<=d['p99_upper_ms']
 completion=re.findall(rb'^MOTION_COMPLETION activity_exit=(\d+) showcase_status=(\d+) active=(\d+)\r?$',raw,re.M);assert len(completion)==1
 exited,status,active=map(int,completion[0]);assert status==1 and exited in (0,1)
 if frames:assert not exited and active==kind+1 and d['frames']==frames and abs(d['simulated']-frames/60)<.00001
 else:
  assert 1<=d['wall']<=30 and 0<d['simulated']<=d['wall']+.001 and d['moves']>0
  assert (exited and active==0) or (not exited and active==kind+1 and d['wall']>=19.9)
 d['activity_exit']=exited
 counters=game_counters(raw) if hardware else None
 if hardware:assert counters['frames']==d['frames']
 if kind==6:
  assert d['commands']==d['batches']==0
  if hardware:assert counters['vertices']==counters['triangles']==0
 d['fps']=d['frames']/d['wall'];d['preparation_ms_per_frame']=1000*d['preparation']/d['frames']
 return dict(result=d,counters=counters,scope='Cold-entry interval; fixed-frame comparison has one simulation tick per image, wall window uses 60Hz accumulator; histogram bounds are 4ms')

def compare(records):
 assert len(records)==4
 out=[]
 for kind in (4,6):
  b=next(r['measurement']['result'] for r in records if r['variant']=='baseline' and r['kind']==kind)
  c=next(r['measurement']['result'] for r in records if r['variant']=='candidate' and r['kind']==kind)
  for key in ('kind','frames','simulated','state_crc32','commands','batches','ui_bytes','moves','teleports','queue_overflows'):assert b[key]==c[key],(kind,key,b[key],c[key])
  out.append(dict(kind=kind,frames=b['frames'],state_crc32=b['state_crc32'],baseline_fps=b['fps'],candidate_fps=c['fps'],preparation_ratio=c['preparation']/b['preparation'],frame_time_ratio=c['wall']/b['wall'],scope='Single predetermined pair, no automatic promotion and no statistical confidence claim'))
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--expected-manifest',required=True);a=p.parse_args()
 assert sha(a.bundle/'manifest.json')==a.expected_manifest;m=preflight(a.bundle);a.out.mkdir(parents=True,exist_ok=False)
 from check_linux import command
 r=dict(passed=False,hardware=True,manifest_sha256=a.expected_manifest,baseline=m['baseline'],probes=m['probes'],transfers=[],fpga='G22r0 continuity from PP2, renderer checks G3D1',kernel=RELEASE.decode(),fpga_writes=0,kernel_writes=0,sd_writes=0,flash_writes=0)
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
    r['before']=display(before);r['initial_identity']=guard.identity(tx,'initial_r6');assert r['initial_identity']==m['expected_identity']
    recovery['baseline_identity']=r['initial_identity'];r['save_initial']=saved_bytes(tx,'save_initial',guard.BASE_SAVE,4);assert r['save_initial']['sha256']==guard.SAVE_SHA
    time.sleep(3);r['progress_before']=display(tx.run('progress_before','prodockctl display'));assert (r['progress_before']['presents']-r['before']['presents'])&0xffffffff
    tags=[m['tag']+'_'+x for x in ('fixture4','fixture6','window0','window1','window2','window3','wall','restore')]
    names=[*m['transfer_files'],*[q['program'] for q in m['probes'].values()],*[t+'.'+s for t in tags for s in ('pid','log','exit')]]
    tx.run('fresh_names',' && '.join('test ! -f /tmp/'+n for n in names))
    readback(tx,'receiver_readback','/tmp/luma-rx',1464,RECEIVER_SHA)
    for name in m['transfer_files']:
     tx.receiver_active=True;r['transfers'].append(tx.transfer(a.bundle/name,name))
    helper=m['helper'];tx.run('helper_mode','chmod 700 /tmp/'+helper)
    raw_verify(tx,helper,'baseline_file','/tmp/'+guard.BASE,m['baseline']);raw_verify(tx,helper,'baseline_running_image','/proc/'+str(r['initial_identity']['pid'])+'/exe',m['baseline'])
    for variant in ('baseline','candidate'):
     q=m['probes'][variant];d=q['delta'];old=guard.BASE if variant=='baseline' else m['probes']['baseline']['program']
     raw=tx.run('install_'+variant,f'/tmp/{helper} patch /tmp/{d["file"]} /tmp/{q["program"]} {d["patch_bytes"]} {d["patch_crc32"]} /tmp/{old}',90)
     assert f'LUMA3D_UNPACK_OK bytes={q["binary"]["bytes"]} crc32={q["binary"]["crc32"]}'.encode() in raw
     tx.run('mode_'+variant,'chmod 700 /tmp/'+q['program']);raw_verify(tx,helper,'verify_'+variant,'/tmp/'+q['program'],q['binary'])
    for ref in m['references']:
     raw=tx.run('verify_'+ref['file'],f'/tmp/{helper} verify /tmp/{ref["file"]} unused {ref["bytes"]} {ref["crc32"]}')
     assert f'LUMA3D_VERIFY_OK bytes={ref["bytes"]} crc32={ref["crc32"]}'.encode() in raw
    assert guard.identity(tx,'before_switch')==r['initial_identity']
    print('MOTION_READY_IN_10_SECONDS: R6 still visible; same-scene diagnostic measurements start next',flush=True);time.sleep(10)
    stopped=True;guard.stop_baseline(tx,r['initial_identity'])
    released=tx.run('released','prodockctl info; prodockctl display');assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in released;r['released']=display(released)
    def run(variant,tag,kind,frames=0,wall=0,deadline=600):
     nonlocal current,ever
     program=m['probes'][variant]['program'];current=(program,'/tmp/'+tag+'.pid');ever=True
     args=f'--kind {kind} '+(f'--frames {frames}' if frames else f'--wall {wall}')
     initial=tx.run(tag+'_launch',once(program,tag,args));assert wait_exit(uart,a.out,tag,timeout=deadline,initial=initial)==0
     raw=tx.run(tag+'_log','cat /tmp/'+tag+'.log',90);current=None
     record=parse_result(raw,kind,frames,wall);record['display']=display(tx.run(tag+'_display','prodockctl display'));return record
    r['fixtures']=[]
    for f in m['fixtures']:
     tag=m['tag']+'_fixture'+str(f['kind']);record=run('candidate',tag,f['kind'],frames=1,deadline=m['deadlines']['fixture'])
     for key in ('vertices','triangles','slivers'):assert record['counters'][key]==f['oracle'][key]
     if f['pixels']:verify_pixels(tx,helper,tag,f['pixels'])
     verify_regions(tx,helper,tag,[f['region']]);r['fixtures'].append(record)
    print('MOTION_ORACLES_PASS: two exact fixtures; four fixed-state measurement windows',flush=True)
    r['windows']=[]
    for i,w in enumerate(m['windows']):
     measurement=run(w['variant'],m['tag']+'_window'+str(i),w['kind'],frames=w['frames'],deadline=m['deadlines']['window'])
     r['windows'].append(dict(**w,measurement=measurement));print(json.dumps(r['windows'][-1]),flush=True)
    r['comparison']=compare(r['windows'])
    r['wall']=run('candidate',m['tag']+'_wall',m['wall']['kind'],wall=m['wall']['seconds'],deadline=m['deadlines']['wall'])
    r['restored_display']=guard.recover(tx,m,current,ever,recovery);r['restored_r6']=True
    r['save_final']=saved_bytes(tx,'save_final',guard.BASE_SAVE,4);assert r['save_final']['sha256']==r['save_initial']['sha256']
    r['final_identity']=guard.identity(tx,'final_after_save');assert r['final_identity']==recovery['identity']
    r['passed']=True;r['left_running']='/tmp/'+guard.BASE+' --showcase; autonomous background loop, stdin /dev/null'
   except BaseException as e:
    r['error']=repr(e)
    try:abort_receiver(tx,uart,a.out)
    except BaseException as e:r['receiver_abort_error']=repr(e)
    if stopped:
     try:
      uart.write(b'\x03');uart.flush();time.sleep(.3);uart.read(16000)
      r['restored_display']=guard.recover(tx,m,current,ever,recovery);r['restored_r6']=True
      r['save_after_recovery']=saved_bytes(tx,'save_after_recovery',guard.BASE_SAVE,4);assert r['save_after_recovery']['sha256']==guard.SAVE_SHA
      r['final_identity']=guard.identity(tx,'recovery_final_after_save');assert r['final_identity']==recovery['identity']
     except BaseException as e:r['cleanup_error']=repr(e)
    raise
   finally:
    (a.out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
if __name__=='__main__':main()
