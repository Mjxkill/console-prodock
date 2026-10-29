#!/usr/bin/env python3
"""MC1 userspace-only comparison; always restore GM1. Reviewed bundle required; no implicit hardware run."""
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
WINDOWS=[(v,k) for k in (4,8) for v in ('baseline','candidate','candidate','baseline')]
FIXTURES=[(8,1,0,0),(4,1,0,0),(4,31,0,0),(4,31,16,0),(4,32,16,31),(7,1,0,0),(7,31,0,0),(7,32,16,31)]
EXACT=('frames','commands','batches','ui_bytes','rasters','static_bytes','dynamic_bytes','moves','teleports','queue_overflows','contacts','contact_fallbacks','state_crc32')
COPY_EXACT=('name','requested','published','compared','allocated')
DEPS=('prodock_mesh_cache.py','probe_metrics.py','trial_guards.py','prodock_arcade.py','prodock_order.py','prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','check_linux.py','check_gpu_reloads.py')
PERFORMANCE=dict(max_mean_ratio=1.10,max_p99_ratio=1.25,p99_slack_ms=4,max_frame_ratio=1.50,max_frame_slack_ms=20)
def compare(rows):
 assert [(r['variant'],r['kind']) for r in rows]==WINDOWS
 out=[]
 for j,kind in enumerate((4,8)):
  group=rows[j*4:j*4+4]
  for i in (1,2,3):
   for a,b in zip(group[0]['result']['phases'],group[i]['result']['phases']):
    assert all(a[k]==b[k] for k in EXACT)
   for a,b in zip(group[0]['result']['counters'],group[i]['result']['counters']):
    assert all(a[k]==b[k] for k in ('presents','vertices','triangles','culled','slivers'))
  pairs=[]
  for ai,bi in ((0,1),(3,2)):
   a=group[ai]['result']['phases'][2];b=group[bi]['result']['phases'][2]
   ratio=(b['wall']/b['frames'])/(a['wall']/a['frames'])
   checks=dict(mean=ratio<=PERFORMANCE['max_mean_ratio'],p99=bool(a['p99_upper_ms'] and b['p99_upper_ms']) and b['p99_upper_ms']<=a['p99_upper_ms']*PERFORMANCE['max_p99_ratio']+PERFORMANCE['p99_slack_ms'],maximum=b['max_frame']<=a['max_frame']*PERFORMANCE['max_frame_ratio']+PERFORMANCE['max_frame_slack_ms']/1000)
   pairs.append(dict(order='AB' if ai==0 else 'BA',mean_frame_ratio=ratio,baseline_fps=a['fps'],candidate_fps=b['fps'],baseline_p99_upper_ms=a['p99_upper_ms'],candidate_p99_upper_ms=b['p99_upper_ms'],baseline_max_ms=a['max_frame']*1000,candidate_max_ms=b['max_frame']*1000,checks=checks,accepted=all(checks.values())))
  drift=group[3]['result']['phases'][2]['wall']/group[0]['result']['phases'][2]['wall']
  out.append(dict(kind=kind,pairs=pairs,baseline_wall_ratio_last_first=drift,accepted=all(p['accepted'] for p in pairs)))
 return out
def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def preflight(bundle):
 m=json.loads((bundle/'manifest.json').read_text());assert m['candidate'] and not m['hardware_tested'] and re.fullmatch(r'mc[0-9]+',m['tag'])
 assert m['expected_identity']==dict(pid=2925,start_ticks=26240721) and m['baseline']['sha256']==guard.BASE_SHA
 for name,value in m['files'].items():assert re.fullmatch(r'[A-Za-z0-9_.-]+',name) and digest(bundle/name)==value,name
 for name in DEPS:assert digest(Path(__file__).with_name(name))==m['files'][name]
 assert json.loads((bundle/'baseline_manifest.json').read_text())['riscv']==m['baseline']
 assert json.loads((bundle/'game_manifest.json').read_text())['riscv']==m['game']['binary']
 prior=json.loads((bundle/'prior_result.json').read_text());assert prior['passed'] and prior['live_identity']==m['expected_identity']
 assert prior['save_final']['sha256']==guard.SAVE_SHA
 assert m['windows']==[dict(variant=v,kind=k,frames=360) for v,k in WINDOWS]
 assert m['performance_policy']==PERFORMANCE and m['normal_exit']=='restore_gm1'
 assert [(x['kind'],x['frames'],x['restart_at'],x['back_at']) for x in m['fixtures']]==FIXTURES
 assert m['deadlines']==dict(fixture=240,window=600)
 before=m['baseline']
 for key in ('baseline','candidate'):
  q=m['programs'][key];d=q['delta'];assert q['binary']==m['probe_binaries'][key]
  assert q['program']==m['tag']+'-'+key
  assert d['old_sha256']==before['sha256'] and d['new_sha256']==q['binary']['sha256'] and d['new_bytes']==q['binary']['bytes'] and d['new_crc32']==q['binary']['crc32'];before=q['binary']
 assert m['helper']==m['tag']+'-helper'
 assert m['transfer_files']==[m['helper'],*[m['programs'][k]['delta']['file'] for k in ('baseline','candidate')],*[x['file'] for x in m['references']]]
 assert len(set(m['transfer_files']))==len(m['transfer_files'])
 tests=json.loads((bundle/'probe_validation.json').read_text());assert tests['passed'] and not tests['hardware'] and len(tests['records'])==8
 pm=json.loads((bundle/'probe_manifest.json').read_text());fp=json.loads((bundle/'fixtures_validation.json').read_text())
 assert tests['probe_manifest_sha256']==fp['probe_manifest_sha256']==sha(bundle/'probe_manifest.json')
 assert tests['parser_sha256']==sha(bundle/'probe_metrics.py') and fp['passed'] and not fp['hardware'] and len(fp['records'])==16
 assert fp['elf_sha256']==next(x['elf_sha256'] for x in pm['records'] if x['variant']=='candidate' and x['target']=='host')
 for key in ('baseline','candidate'):assert m['probe_binaries'][key]['sha256']==next(x['elf_sha256'] for x in pm['records'] if x['variant']==key and x['target']=='riscv')
 rv=json.loads((bundle/'probe_rv32.json').read_text());assert rv['passed'] and not rv['hardware'] and rv['probe_manifest_sha256']==sha(bundle/'probe_manifest.json')
 assert rv['fixtures_sha256']==sha(bundle/'fixtures_validation.json') and rv['windows_sha256']==sha(bundle/'probe_validation.json')
 assert len(rv['records'])==16 and {x['name'] for x in rv['records']}=={x['name'] for x in fp['records']}
 assert all(x['passed'] and x['memory_changed_bytes']==0 and x['commands_identical'] and x['overlay_identical'] and x['elf_sha256']==m['probe_binaries']['candidate']['sha256'] for x in rv['records'])
 assert len(rv['windows'])==4 and {(x['variant'],x['kind']) for x in rv['windows']}==set(WINDOWS) and all(x['passed'] for x in rv['windows'])
 assert m['expected_windows']==[[{k:p[k] for k in EXACT} for p in next(r['result']['phases'] for r in tests['records'] if r['variant']==v and r['kind']==kind and r['width']==800)] for v,kind in WINDOWS]
 assert m['expected_copies']==[[{k:p[k] for k in COPY_EXACT} for p in next(r['result']['copies'] for r in tests['records'] if r['variant']==v and r['kind']==kind and r['width']==800)] for v,kind in WINDOWS]
 proof=json.loads((bundle/'render_equivalence.json').read_text());assert proof['passed'] and not proof['hardware'] and proof['selected_frames']>=70
 assert proof['records'][0]['source_manifest_sha256']==sha(bundle/'baseline_manifest.json') and proof['records'][1]['source_manifest_sha256']==sha(bundle/'game_manifest.json')
 unit=json.loads((bundle/'cache_unit.json').read_text());assert unit['passed'] and not unit['hardware']
 for path,h in unit['inputs'].items():assert sha(bundle/('cache_'+path.replace('/','_')))==h
 assert json.loads((bundle/'game_manifest.json').read_text())['files']['games/luma3d/src/mesh_cache.c']['sha256']==unit['inputs']['src/mesh_cache.c']
 for f in m['fixtures']:
  source=next(x for x in fp['records'] if all(x[k]==f[k] for k in ('kind','frames','restart_at','back_at')) and x['width']==800)
  assert f['expected_phases']==[{k:p[k] for k in EXACT} for p in source['measurement']['phases']]
  assert f['expected_copies']==[{k:p[k] for k in COPY_EXACT} for p in source['measurement']['copies']]
  assert f['oracle']==source['oracle']==json.loads((bundle/(source['name']+'.reference.json')).read_text())
  assert len(f['ui'])==len(source['ui'])
  for q,original in [(f['rect'],source['rect']),*zip(f['ui'],source['ui'])]:
   assert all(q[k]==v for k,v in original.items() if k!='extension')
   ref=next(x for x in m['references'] if x['file']==q['file']);assert all(q[k]==v for k,v in ref.items())
  assert all(20<<20<=q['offset'] and q['offset']+q['bytes']<=24<<20 for q in f['ui'])
  rect=f['rect'];assert rect['pitch']==1600 and rect['width']==400 and rect['height']==240 and rect['bytes']==192000 and rect['offset']<(2<<20)
 return m
def trial(bundle,out,expected):
 assert sha(bundle/'manifest.json')==expected;m=preflight(bundle);out.mkdir(parents=True,exist_ok=False)
 from check_linux import command
 r=dict(passed=False,hardware=True,manifest_sha256=expected,baseline=m['baseline'],game=m['game']['binary'],transfers=[],fpga='G22r0 continuity from GM1; G3D1 checked',kernel=RELEASE.decode(),fpga_writes=0,kernel_writes=0,sd_writes=0,flash_writes=0)
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
    r['before']=display(raw);r['initial_identity']=guard.identity(tx,'initial_gm1');assert r['initial_identity']==m['expected_identity'];recovery['baseline_identity']=r['initial_identity']
    r['save_initial']=saved_bytes(tx,'save_initial',guard.BASE_SAVE,4);assert r['save_initial']['sha256']==guard.SAVE_SHA
    time.sleep(3);assert (display(tx.run('progress_before','prodockctl display'))['presents']-r['before']['presents'])&0xffffffff
    tags=[m['tag']+'_fixture'+str(i) for i in range(len(FIXTURES))]+[m['tag']+'_window'+str(i) for i in range(len(WINDOWS))]+[m['tag']+'_'+x for x in ('restore',)]
    names=[*m['transfer_files'],*[x['program'] for x in m['programs'].values()],*[t+'.'+s for t in tags for s in ('pid','log','exit')]]
    tx.run('fresh_names',' && '.join('test ! -f /tmp/'+n for n in names));readback(tx,'receiver_readback','/tmp/luma-rx',1464,RECEIVER_SHA)
    for name in m['transfer_files']:tx.receiver_active=True;r['transfers'].append(tx.transfer(bundle/name,name))
    helper=m['helper'];tx.run('helper_mode','chmod 700 /tmp/'+helper)
    raw_verify(tx,helper,'baseline_file','/tmp/'+guard.BASE,m['baseline']);raw_verify(tx,helper,'baseline_running','/proc/'+str(r['initial_identity']['pid'])+'/exe',m['baseline'])
    old=guard.BASE
    for key in ('baseline','candidate'):
     q=m['programs'][key];d=q['delta'];raw=tx.run('install_'+key,f'/tmp/{helper} patch /tmp/{d["file"]} /tmp/{q["program"]} {d["patch_bytes"]} {d["patch_crc32"]} /tmp/{old}',120)
     assert f'LUMA3D_UNPACK_OK bytes={q["binary"]["bytes"]} crc32={q["binary"]["crc32"]}'.encode() in raw
     tx.run('mode_'+key,'chmod 700 /tmp/'+q['program']);raw_verify(tx,helper,'verify_'+key,'/tmp/'+q['program'],q['binary']);old=q['program']
    for ref in m['references']:
     raw=tx.run('verify_'+ref['file'],f'/tmp/{helper} verify /tmp/{ref["file"]} unused {ref["bytes"]} {ref["crc32"]}');assert f'LUMA3D_VERIFY_OK bytes={ref["bytes"]} crc32={ref["crc32"]}'.encode() in raw
    assert guard.identity(tx,'before_switch')==r['initial_identity'];print('MESH_CACHE_READY_IN_10_SECONDS: GM1 visible, bounded comparison starts next',flush=True);time.sleep(10)
    stopped=True;guard.stop_baseline(tx,r['initial_identity']);raw=tx.run('released','prodockctl info; prodockctl display');assert b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in raw;r['released']=display(raw)
    def run(key,tag,kind,frames,fixture=False,restart_at=0,back_at=0):
     nonlocal current,ever
     program=m['programs'][key]['program'];current=(program,'/tmp/'+tag+'.pid');ever=True
     raw=tx.run(tag+'_launch',once(program,tag,f'--kind {kind} --frames {frames}'+(' --fixture' if fixture else '')+(f' --restart-at {restart_at}' if restart_at else '')+(f' --back-at {back_at}' if back_at else '')))
     assert wait_exit(uart,out,tag,timeout=m['deadlines']['fixture' if fixture else 'window'],initial=raw)==0
     raw=tx.run(tag+'_log','cat /tmp/'+tag+'.log',120);current=None;value=parse(raw,kind,frames,fixture,True,restart_at,back_at)
     value['geometry']=game_counters(raw);value['display']=display(tx.run(tag+'_display','prodockctl display'));return value
    r['fixtures']=[]
    for i,f in enumerate(m['fixtures']):
     tag=m['tag']+'_fixture'+str(i);record=run('candidate',tag,f['kind'],f['frames'],True,f['restart_at'],f['back_at'])
     assert [{k:p[k] for k in EXACT} for p in record['phases']]==f['expected_phases']
     assert [{k:p[k] for k in COPY_EXACT} for p in record['copies']]==f['expected_copies']
     for key in ('vertices','triangles','slivers'):assert record['last'][0][key]==f['oracle'][key]
     if f['rect']:
      q=f['rect'];raw=tx.run(tag+'_rect',f'/tmp/{helper} rect /tmp/{q["file"]} {q["offset"]} {q["bytes"]} {q["crc32"]} {q["pitch"]} {q["width"]} {q["height"]}',120)
      assert f'LUMA3D_RECT offset={q["offset"]} pitch={q["pitch"]} width={q["width"]} height={q["height"]} bytes={q["bytes"]} mismatch=0 actual_crc={q["crc32"]} expected_crc={q["crc32"]}'.encode() in raw
     verify_regions(tx,helper,tag,f['ui']);r['fixtures'].append(record);print('GPU_MOTION_FIXTURE_PASS '+str(i),flush=True)
    r['windows']=[]
    for i,w in enumerate(m['windows']):
     value=run(w['variant'],m['tag']+'_window'+str(i),w['kind'],w['frames'])
     assert [{k:p[k] for k in EXACT} for p in value['phases']]==m['expected_windows'][i]
     assert [{k:p[k] for k in COPY_EXACT} for p in value['copies']]==m['expected_copies'][i]
     r['windows'].append(dict(**w,result=value));print(json.dumps(r['windows'][-1]),flush=True)
    r['comparison']=compare(r['windows']);r['performance_accepted']=all(x['accepted'] for x in r['comparison'])
    r['functional_passed']=True
    r['restored_display']=guard.recover(tx,m,current,ever,recovery);r['restored_gm1']=True
    r['save_final']=saved_bytes(tx,'save_final',guard.BASE_SAVE,4);assert r['save_final']['sha256']==guard.SAVE_SHA
    r['final_identity']=guard.identity(tx,'final_recovery_after_save');assert r['final_identity']==recovery['identity']
    r['left_running']='/tmp/'+guard.BASE+' --showcase; autonomous background loop, stdin /dev/null'
    r['passed']=True;r['outcome']='COMPARISON_COMPLETE_GM1_RESTORED';r['candidate_promoted']=False
   except BaseException as e:
    r['error']=repr(e)
    try:abort_receiver(tx,uart,out)
    except BaseException as e:r['receiver_abort_error']=repr(e)
    if stopped:
     try:
      uart.write(b'\x03');uart.flush();time.sleep(.3);uart.read(16000)
      r['restored_display']=guard.recover(tx,m,current,ever,recovery);r['restored_gm1']=True
      r['save_after_recovery']=saved_bytes(tx,'save_after_recovery',guard.BASE_SAVE,4);assert r['save_after_recovery']['sha256']==guard.SAVE_SHA
      r['final_identity']=guard.identity(tx,'final_recovery_after_save');assert r['final_identity']==recovery['identity']
     except BaseException as e:r['cleanup_error']=repr(e)
    raise
   finally:(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--out',type=Path);p.add_argument('--expected-manifest',required=True);p.add_argument('--check-only',action='store_true');a=p.parse_args()
 assert sha(a.bundle/'manifest.json')==a.expected_manifest
 if a.check_only:preflight(a.bundle);print('MC1_PREFLIGHT_PASS no_hardware=1');return
 assert a.out;trial(a.bundle,a.out,a.expected_manifest)
if __name__=='__main__':main()
