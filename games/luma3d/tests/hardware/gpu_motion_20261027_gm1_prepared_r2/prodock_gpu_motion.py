#!/usr/bin/env python3
"""GM1 userspace-only trial. Reviewed bundle required; no implicit hardware run."""
import argparse,fcntl,hashlib,json,re,signal,time,zlib
from pathlib import Path
import serial
from prodock_transport import Transport,RECEIVER_SHA
from prodock_valley_ab import PORT,RELEASE,progress
from prodock_valley_trial import sha,display,game_counters
from prodock_valley_benchmark import readback,wait_exit
from prodock_order import abort_receiver
from prodock_arcade import saved_bytes,verify_regions,raw_verify,once
from probe_metrics import parse
import trial_guards as guard
WINDOWS=[('baseline',1),('candidate',1),('candidate',3),('baseline',3),('baseline',5),('candidate',5),('candidate',4),('baseline',4),('baseline',6),('candidate',6)]
FIXTURES=[(1,1),(3,1),(4,1),(5,1),(6,1),(1,31),(3,31),(5,51)]
EXACT=('frames','commands','batches','ui_bytes','rasters','static_bytes','dynamic_bytes','moves','teleports','queue_overflows','contacts','contact_fallbacks','state_crc32')
DEPS=('prodock_gpu_motion.py','probe_metrics.py','trial_guards.py','prodock_arcade.py','prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','check_linux.py','check_gpu_reloads.py')
PERFORMANCE=dict(max_mean_ratio=1.10,max_p99_ratio=1.25,p99_slack_ms=4,max_frame_ratio=1.50,max_frame_slack_ms=20)
def compare(rows):
 out=[]
 for kind in (1,3,4,5,6):
  pair={r['variant']:r['result'] for r in rows if r['kind']==kind};assert len(pair)==2
  for a,b in zip(pair['baseline']['phases'],pair['candidate']['phases']):assert a['state_crc32']==b['state_crc32']
  a=pair['baseline']['phases'][2];b=pair['candidate']['phases'][2]
  mean_ratio=(b['wall']/b['frames'])/(a['wall']/a['frames'])
  checks=dict(mean=mean_ratio<=PERFORMANCE['max_mean_ratio'],p99=bool(a['p99_upper_ms'] and b['p99_upper_ms']) and b['p99_upper_ms']<=a['p99_upper_ms']*PERFORMANCE['max_p99_ratio']+PERFORMANCE['p99_slack_ms'],maximum=b['max_frame']<=a['max_frame']*PERFORMANCE['max_frame_ratio']+PERFORMANCE['max_frame_slack_ms']/1000)
  out.append(dict(kind=kind,mean_frame_ratio=mean_ratio,baseline_fps=a['fps'],candidate_fps=b['fps'],baseline_p99_upper_ms=a['p99_upper_ms'],candidate_p99_upper_ms=b['p99_upper_ms'],baseline_max_ms=a['max_frame']*1000,candidate_max_ms=b['max_frame']*1000,checks=checks,accepted=all(checks.values())))
 return out
def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def preflight(bundle):
 m=json.loads((bundle/'manifest.json').read_text());assert m['candidate'] and not m['hardware_tested'] and re.fullmatch(r'gm[0-9]+',m['tag'])
 assert m['expected_identity']==dict(pid=2680,start_ticks=25042521) and m['baseline']['sha256']==guard.BASE_SHA
 for name,value in m['files'].items():assert re.fullmatch(r'[A-Za-z0-9_.-]+',name) and digest(bundle/name)==value,name
 for name in DEPS:assert digest(Path(__file__).with_name(name))==m['files'][name]
 assert json.loads((bundle/'baseline_manifest.json').read_text())['riscv']==m['baseline']
 assert json.loads((bundle/'game_manifest.json').read_text())['riscv']==m['game']['binary']
 prior=json.loads((bundle/'prior_result.json').read_text());assert not prior['passed'] and prior['restored_r6'] and prior['final_identity']==m['expected_identity']
 assert prior['save_after_recovery']['sha256']==guard.SAVE_SHA
 assert m['windows']==[dict(variant=v,kind=k,frames=360) for v,k in WINDOWS]
 assert m['performance_policy']==PERFORMANCE and m['motion_counters_available']==dict(baseline=False,candidate=True)
 assert [(x['kind'],x['frames']) for x in m['fixtures']]==FIXTURES and m['deadlines']==dict(fixture=240,window=600,showcase=3700)
 before=m['baseline']
 for key in ('baseline','candidate','game'):
  q=m['programs'][key];d=q['delta'];assert q['binary']==(m['game']['binary'] if key=='game' else m['probe_binaries'][key])
  assert q['program']==('luma3d-'+m['tag'] if key=='game' else m['tag']+'-'+key)
  assert d['old_sha256']==before['sha256'] and d['new_sha256']==q['binary']['sha256'] and d['new_bytes']==q['binary']['bytes'] and d['new_crc32']==q['binary']['crc32'];before=q['binary']
 assert m['helper']==m['tag']+'-helper'
 assert m['transfer_files']==[m['helper'],*[m['programs'][k]['delta']['file'] for k in ('baseline','candidate','game')],*[x['file'] for x in m['references']]]
 assert len(set(m['transfer_files']))==len(m['transfer_files'])
 tests=json.loads((bundle/'probe_validation.json').read_text());assert tests['passed'] and not tests['hardware'] and len(tests['records'])==20
 pm=json.loads((bundle/'probe_manifest.json').read_text());fp=json.loads((bundle/'fixtures_validation.json').read_text())
 assert tests['probe_manifest_sha256']==fp['probe_manifest_sha256']==sha(bundle/'probe_manifest.json')
 assert tests['parser_sha256']==sha(bundle/'probe_metrics.py') and fp['passed'] and not fp['hardware'] and len(fp['records'])==16
 assert fp['elf_sha256']==next(x['elf_sha256'] for x in pm['records'] if x['variant']=='candidate' and x['target']=='host')
 for key in ('baseline','candidate'):assert m['probe_binaries'][key]['sha256']==next(x['elf_sha256'] for x in pm['records'] if x['variant']==key and x['target']=='riscv')
 rv=json.loads((bundle/'probe_rv32.json').read_text());assert rv['passed'] and not rv['hardware'] and rv['probe_manifest_sha256']==sha(bundle/'probe_manifest.json')
 assert rv['fixtures_sha256']==sha(bundle/'fixtures_validation.json') and rv['windows_sha256']==sha(bundle/'probe_validation.json')
 assert len(rv['records'])==16 and {x['name'] for x in rv['records']}=={x['name'] for x in fp['records']}
 assert all(x['passed'] and x['memory_changed_bytes']==0 and x['commands_identical'] and x['overlay_identical'] and x['elf_sha256']==m['probe_binaries']['candidate']['sha256'] for x in rv['records'])
 assert len(rv['windows'])==10 and {(x['variant'],x['kind']) for x in rv['windows']}==set(WINDOWS) and all(x['passed'] for x in rv['windows'])
 assert m['expected_windows']==[[{k:p[k] for k in EXACT} for p in next(r['result']['phases'] for r in tests['records'] if r['variant']==v and r['kind']==kind and r['width']==800)] for v,kind in WINDOWS]
 for f in m['fixtures']:
  source=next(x for x in fp['records'] if x['kind']==f['kind'] and x['frames']==f['frames'] and x['width']==800)
  assert f['oracle']==source['oracle']==json.loads((bundle/(source['name']+'.reference.json')).read_text())
  for key in ('ui','rect'):
   if source[key] is None:assert f[key] is None;continue
   assert all(f[key][k]==v for k,v in source[key].items() if k not in ('x','y'))
   ref=next(x for x in m['references'] if x['file']==f[key]['file']);assert all(f[key][k]==v for k,v in ref.items())
  assert f['ui']['offset'] in (22<<20,23<<20) and f['ui']['bytes']==384000
  rect=f['rect']
  if f['kind']==6:assert rect is None
  else:assert rect['pitch']==1600 and 0<rect['width']<=800 and 0<rect['height']<=480 and rect['bytes']==rect['width']*rect['height']*2 and rect['offset']<(2<<20)
 for kind in (1,3,5):
  pair=[f for f in m['fixtures'] if f['kind']==kind];assert len(pair)==2 and pair[0]['rect']['sha256']!=pair[1]['rect']['sha256'], 'Motion/halo fixture must change published RGB pixels'
 return m
def trial(bundle,out,expected):
 assert sha(bundle/'manifest.json')==expected;m=preflight(bundle);out.mkdir(parents=True,exist_ok=False)
 from check_linux import command
 r=dict(passed=False,hardware=True,manifest_sha256=expected,baseline=m['baseline'],game=m['game']['binary'],motion_counters_available=m['motion_counters_available'],transfers=[],fpga='G22r0 continuity from PP2/MO1; G3D1 checked',kernel=RELEASE.decode(),fpga_writes=0,kernel_writes=0,sd_writes=0,flash_writes=0)
 def interrupt(n,frame):raise KeyboardInterrupt('Signal '+str(n))
 signal.signal(signal.SIGTERM,interrupt);signal.signal(signal.SIGHUP,interrupt)
 with open('/tmp/prodock-diagnostic.lock','a+') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
   tx=Transport(uart,command,out);stopped=False;current=None;ever=False;recovery={};r['recovery']=recovery
   try:
    uart.write(b'\n');time.sleep(.2);uart.read(16000)
    raw=tx.run('before','uname -r; prodockctl display; cat /proc/mounts')
    assert re.search(rb'^'+RELEASE+rb'\r?$',raw,re.M) and b'tmpfs /tmp tmpfs ' in raw and not re.search(rb'^/dev/mmc\S* ',raw,re.M)
    r['before']=display(raw);r['initial_identity']=guard.identity(tx,'initial_r6');assert r['initial_identity']==m['expected_identity'];recovery['baseline_identity']=r['initial_identity']
    r['save_initial']=saved_bytes(tx,'save_initial',guard.BASE_SAVE,4);assert r['save_initial']['sha256']==guard.SAVE_SHA
    time.sleep(3);assert (display(tx.run('progress_before','prodockctl display'))['presents']-r['before']['presents'])&0xffffffff
    tags=[m['tag']+'_fixture'+str(i) for i in range(len(FIXTURES))]+[m['tag']+'_window'+str(i) for i in range(len(WINDOWS))]+[m['tag']+'_'+x for x in ('showcase','live','restore')]
    names=[*m['transfer_files'],*[x['program'] for x in m['programs'].values()],*[t+'.'+s for t in tags for s in ('pid','log','exit')]]
    tx.run('fresh_names',' && '.join('test ! -f /tmp/'+n for n in names));readback(tx,'receiver_readback','/tmp/luma-rx',1464,RECEIVER_SHA)
    for name in m['transfer_files']:tx.receiver_active=True;r['transfers'].append(tx.transfer(bundle/name,name))
    helper=m['helper'];tx.run('helper_mode','chmod 700 /tmp/'+helper)
    raw_verify(tx,helper,'baseline_file','/tmp/'+guard.BASE,m['baseline']);raw_verify(tx,helper,'baseline_running','/proc/'+str(r['initial_identity']['pid'])+'/exe',m['baseline'])
    old=guard.BASE
    for key in ('baseline','candidate','game'):
     q=m['programs'][key];d=q['delta'];raw=tx.run('install_'+key,f'/tmp/{helper} patch /tmp/{d["file"]} /tmp/{q["program"]} {d["patch_bytes"]} {d["patch_crc32"]} /tmp/{old}',120)
     assert f'LUMA3D_UNPACK_OK bytes={q["binary"]["bytes"]} crc32={q["binary"]["crc32"]}'.encode() in raw
     tx.run('mode_'+key,'chmod 700 /tmp/'+q['program']);raw_verify(tx,helper,'verify_'+key,'/tmp/'+q['program'],q['binary']);old=q['program']
    for ref in m['references']:
     raw=tx.run('verify_'+ref['file'],f'/tmp/{helper} verify /tmp/{ref["file"]} unused {ref["bytes"]} {ref["crc32"]}');assert f'LUMA3D_VERIFY_OK bytes={ref["bytes"]} crc32={ref["crc32"]}'.encode() in raw
    assert guard.identity(tx,'before_switch')==r['initial_identity'];print('GPU_MOTION_READY_IN_10_SECONDS: R6 visible, verified candidate will appear next',flush=True);time.sleep(10)
    stopped=True;guard.stop_baseline(tx,r['initial_identity']);raw=tx.run('released','prodockctl info; prodockctl display');assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in raw;r['released']=display(raw)
    def run(key,tag,kind,frames,fixture=False):
     nonlocal current,ever
     program=m['programs'][key]['program'];current=(program,'/tmp/'+tag+'.pid');ever=True
     raw=tx.run(tag+'_launch',once(program,tag,f'--kind {kind} --frames {frames}'+(' --fixture' if fixture else '')))
     assert wait_exit(uart,out,tag,timeout=m['deadlines']['fixture' if fixture else 'window'],initial=raw)==0
     raw=tx.run(tag+'_log','cat /tmp/'+tag+'.log',120);current=None;value=parse(raw,kind,frames,fixture,True)
     value['geometry']=game_counters(raw);value['display']=display(tx.run(tag+'_display','prodockctl display'));return value
    r['fixtures']=[]
    for i,f in enumerate(m['fixtures']):
     tag=m['tag']+'_fixture'+str(i);record=run('candidate',tag,f['kind'],f['frames'],True)
     for key in ('vertices','triangles','slivers'):assert record['geometry'][key]==f['oracle'][key]
     if f['rect']:
      q=f['rect'];raw=tx.run(tag+'_rect',f'/tmp/{helper} rect /tmp/{q["file"]} {q["offset"]} {q["bytes"]} {q["crc32"]} {q["pitch"]} {q["width"]} {q["height"]}',120)
      assert f'LUMA3D_RECT offset={q["offset"]} pitch={q["pitch"]} width={q["width"]} height={q["height"]} bytes={q["bytes"]} mismatch=0 actual_crc={q["crc32"]} expected_crc={q["crc32"]}'.encode() in raw
     verify_regions(tx,helper,tag,[f['ui']]);r['fixtures'].append(record);print('GPU_MOTION_FIXTURE_PASS '+str(i),flush=True)
    r['windows']=[]
    for i,w in enumerate(m['windows']):
     value=run(w['variant'],m['tag']+'_window'+str(i),w['kind'],w['frames'])
     assert [{k:p[k] for k in EXACT} for p in value['phases']]==m['expected_windows'][i]
     r['windows'].append(dict(**w,result=value));print(json.dumps(r['windows'][-1]),flush=True)
    r['comparison']=compare(r['windows']);r['performance_accepted']=all(x['accepted'] for x in r['comparison'])
    program=m['programs']['game']['program'];tag=m['tag']+'_showcase';current=(program,'/tmp/'+tag+'.pid');ever=True
    raw=tx.run('showcase_launch',once(program,tag,'--showcase-once'));print('GPU_MOTION_REAL_SHOWCASE: legal real-time loop, no UART commands until EXIT',flush=True)
    assert wait_exit(uart,out,tag,timeout=m['deadlines']['showcase'],initial=raw)==0
    raw=tx.run('showcase_log','cat /tmp/'+tag+'.log',180);current=None
    assert b'LUMA3D_SAVE ' not in raw
    match=re.findall(rb'^LUMA3D_SHOWCASE_RESULT ([^\r\n]+)',raw,re.M);assert len(match)==1
    result=dict((k.decode(),v.decode()) for k,v in re.findall(rb'(\w+)=(\S+)',match[0]));assert result['status']=='2' and result['visited']==result['won']=='ff' and result['stage']=='16' and result['hardware']=='1' and result['boss']==result['checkpoint']==result['crystals']=='1'
    assert result['loops']=='1' and int(result['commands'])>0 and 0<float(result['simulated'])<=float(result['wall'])+.5 and 0<float(result['wall'])<m['deadlines']['showcase']
    r['showcase']=result;r['showcase_geometry']=game_counters(raw);r['showcase_display']=display(tx.run('showcase_display','prodockctl display'));r['functional_passed']=True
    if not r['performance_accepted']:
     r['restored_display']=guard.recover(tx,m,current,ever,recovery);r['restored_r6']=True
     r['save_after_recovery']=saved_bytes(tx,'save_after_recovery',guard.BASE_SAVE,4);assert r['save_after_recovery']['sha256']==guard.SAVE_SHA
     r['final_identity']=guard.identity(tx,'final_recovery_after_save');assert r['final_identity']==recovery['identity']
     r['outcome']='FUNCTIONAL_PASS_PERFORMANCE_REJECTED';return
    tag=m['tag']+'_live';pidfile='/tmp/'+tag+'.pid';current=(program,pidfile);ever=True
    tx.run('launch_live',f'/tmp/{program} --showcase < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {pidfile}')
    anchor=guard.identity(tx,'live_initial',pidfile,program);r['live_display']=progress(tx,program,tag+'.log','live_progress',pidfile);assert guard.identity(tx,'live_after_progress',pidfile,program)==anchor
    r['save_final']=saved_bytes(tx,'save_final',guard.BASE_SAVE,4);assert r['save_final']['sha256']==guard.SAVE_SHA
    assert guard.identity(tx,'live_after_save',pidfile,program)==anchor;tx.run('publish_live','cp '+pidfile+' '+guard.LIVE);assert guard.identity(tx,'live_after_publish',guard.LIVE,program)==anchor
    r['live_identity']=anchor;r['left_running']=f'/tmp/{program} --showcase; autonomous background loop, stdin /dev/null';r['passed']=True
   except BaseException as e:
    r['error']=repr(e)
    try:abort_receiver(tx,uart,out)
    except BaseException as e:r['receiver_abort_error']=repr(e)
    if stopped:
     try:
      uart.write(b'\x03');uart.flush();time.sleep(.3);uart.read(16000)
      r['restored_display']=guard.recover(tx,m,current,ever,recovery);r['restored_r6']=True
      r['save_after_recovery']=saved_bytes(tx,'save_after_recovery',guard.BASE_SAVE,4);assert r['save_after_recovery']['sha256']==guard.SAVE_SHA
      r['final_identity']=guard.identity(tx,'final_recovery_after_save');assert r['final_identity']==recovery['identity']
     except BaseException as e:r['cleanup_error']=repr(e)
    raise
   finally:(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path);p.add_argument('--expected-manifest',required=True);p.add_argument('--check-only',action='store_true');a=p.parse_args()
 assert sha(a.bundle/'manifest.json')==a.expected_manifest
 if a.check_only:preflight(a.bundle);print('GM1_PREFLIGHT_PASS no_hardware=1');return
 assert a.out;trial(a.bundle,a.out,a.expected_manifest)
if __name__=='__main__':main()
