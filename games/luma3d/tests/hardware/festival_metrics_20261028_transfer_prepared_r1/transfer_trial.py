#!/usr/bin/env python3
"""Stage an exact delta and reconstruct an ELF; never signal or execute a game."""
import argparse,fcntl,hashlib,json,os,re,signal,socket,stat,subprocess,time
from pathlib import Path
import stage
import probe_channel as p
HERE=Path(__file__).resolve().parent
RX_SHA='9a5b401858d72b17be6ea5e6765e9994ba4173c8658f8169dd2de1f529e5810e'
RX_PROOF='e9a7712588e2ebcdfff3d04a15c1cc43526bf8fb3aa776d0a4f878df437156cb'
def preflight():
 m=stage.load_plan();proof=json.loads((HERE/'rx2_board_result.json').read_text());p.need(p.sha(HERE/'rx2_board_result.json')==RX_PROOF and proof['passed'] and proof['preserved'] and proof['after']['identity']==p.ANCHOR and proof['after']['save']['sha256']==p.SAVE,'Wrong RX2 board proof');p.need(proof['bootstrap_verified']==dict(bytes=13132,sha256=RX_SHA),'Wrong verified RX2')
 h=json.loads((HERE/'helper_qemu_result.json').read_text());p.need(h['passed'] and h['inputs_unchanged'],'No exact reconstruction proof')
 p.need((HERE/'mc1-helper').read_bytes()==(HERE/'helper_verified.bin').read_bytes(),'Retained helper differs from complete readback')
 return m,p.sha(HERE/'plan.json')
def review_check(r,h,host,now):
 p.need(host==p.HOST and r.get('host')==p.HOST and r.get('port')==p.PORT and r.get('plan_sha256')==h,'Wrong host/plan')
 p.need(r.get('anchor')==p.ANCHOR and r.get('fpga_sha256')==p.FPGA and r.get('save_sha256')==p.SAVE and r.get('rx2_board_proof_sha256')==RX_PROOF,'Wrong review anchors')
 for k in ['root_authorized_stage_only','same_gm1_since_rx2_probes','same_g22r0_since_rx2_probes','helper_unchanged_since_full_readback','ordinary_shell_confirmed','no_other_console_session']:p.need(r.get(k) is True,'Missing review '+k)
 p.need(type(r.get('reviewed_unix')) in (int,float) and 0<=now-r['reviewed_unix']<=1800,'Review expired')
def free_kib(raw):
 rows=[x.split() for x in raw.replace(b'\r',b'').splitlines() if x.split() and x.split()[-1]==b'/tmp'];p.need(len(rows)==1 and len(rows[0])==6 and rows[0][0]==b'tmpfs' and rows[0][3].isdigit(),'Unexpected df');return int(rows[0][3])
def memory(raw):
 values=re.findall(rb'^MemAvailable:\s+(\d+) kB\r?$',raw,re.M);p.need(len(values)==1 and int(values[0])*1024>=64<<20,'Insufficient MemAvailable for reconstruction');return int(values[0])
def health(c,label):
 ident=p.identity(c.run(label+'_identity','cat /tmp/luma3d-live.pid && cat /proc/3158/stat && od -b -v /proc/3158/cmdline && ls -l /proc/3158/exe'));saved=p.save(c.run(label+'_save','od -b -v /tmp/op2-live.save'));gpu=p.gpu(c.run(label+'_gpu','prodockctl display'));free=free_kib(c.run(label+'_space','LC_ALL=C df -Pk /tmp'))
 return dict(identity=ident,save=saved,gpu=gpu,tmp_available_kib=free)
def raw_check(c,label,path,record,m):
 b=c.run(label,f'{m["helper_remote"]} raw {path} unused {record["bytes"]} {record["crc32"]}',180);p.need(re.search(rb'^LUMA3D_RAW_OK bytes='+str(record['bytes']).encode()+rb' crc32='+record['crc32'].encode()+rb'\r?$',b,re.M),'Runtime file CRC mismatch');return record.copy()
def stage_files(c,m,resume,records):
 raw=c.run('kernel_tmp','uname -r && cat /proc/mounts');p.need(re.search(rb'^'+p.KERNEL.encode()+rb'\r?$',raw,re.M) and b'tmpfs /tmp tmpfs ' in raw,'Kernel/tmpfs changed')
 names=f'test ! -e {m["target_remote"]}'
 if not resume:names+=f' && test ! -e {m["remote_payload"]}'
 else:names+=f' && test -f {m["remote_payload"]} && test ! -L {m["remote_payload"]}'
 c.run('fresh_names',names)
 rx=p.octets(c.run('receiver_full_readback','od -b -v '+m['rx2_executable']),13132);p.need(len(rx)==13132 and hashlib.sha256(rx).hexdigest()==RX_SHA,'Receiver changed')
 c.run('helper_permissions',f'test -f {m["helper_remote"]} && test -x {m["helper_remote"]} && test ! -L {m["helper_remote"]}')
 raw_check(c,'helper_runtime',m['helper_remote'],m['helper'],m)
 raw_check(c,'baseline_file',m['base_remote'],m['base'],m);raw_check(c,'baseline_process','/proc/3158/exe',m['base'],m)
 # Conservative also on a partial resume: reserve the ENTIRE payload again.
 stage.storage_check(free_kib(c.run('space_transfer','LC_ALL=C df -Pk /tmp')),m,payload_exists=False)
 # Eight complete planned segments; bounded extra sessions only when root
 # explicitly restarts this controller with --resume after reviewing failure.
 for index in range(m['transport']['planned_sessions']+1):
  row=stage.segment(c,m,resume=resume or index>0);records.append(row);(c.out/'segments.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps({'segment':index,'offset':row['offset'],'complete':row['complete']}),flush=True)
  if row['complete']:break
 else:raise RuntimeError('Segment count exceeded')
 raw_check(c,'payload_runtime',m['remote_payload'],m['files'][m['payload_file']],m)
 stage.storage_check(free_kib(c.run('space_reconstruction','LC_ALL=C df -Pk /tmp')),m,payload_exists=True);memory(c.run('memory_reconstruction','cat /proc/meminfo'))
 d=m['delta'];b=c.run('reconstruction',f'{m["helper_remote"]} patch {m["remote_payload"]} {m["target_remote"]} {d["raw_bytes"]} {d["raw_crc32"]} {m["base_remote"]}',180)
 p.need(re.search(rb'^LUMA3D_UNPACK_OK bytes='+str(m['target']['bytes']).encode()+rb' crc32='+m['target']['crc32'].encode()+rb'\r?$',b,re.M),'Reconstruction failed')
 raw_check(c,'target_runtime',m['target_remote'],m['target'],m);c.run('target_mode','chmod 700 '+m['target_remote'])
 return dict(elf=m['target_remote'],expected_sha256=m['target']['sha256'],runtime_crc32=m['target']['crc32'],runtime_sha256_measured=False,identity_basis='Pinned exact delta/helper; QEMU byte comparison and runtime full-file CRC32',game_executed=False)
def main():
 a=argparse.ArgumentParser();a.add_argument('--run',action='store_true');a.add_argument('--resume',action='store_true');a.add_argument('--expected-plan');a.add_argument('--review',type=Path);a.add_argument('--out',type=Path);args=a.parse_args();m,h=preflight()
 if not args.run:print(json.dumps({'prepared':True,'hardware':False,'plan_sha256':h,'payload_bytes':m['files'][m['payload_file']]['bytes']}));return 0
 p.need(args.expected_plan==h and args.review and args.out,'Explicit plan/review/new output required');review=json.loads(args.review.read_text());review_check(review,h,socket.gethostname().split('.')[0],time.time());p.need(review.get('resume_existing_payload') is args.resume,'Resume mode not reviewed');args.out.mkdir(parents=True,exist_ok=False)
 result=dict(passed=False,hardware=True,plan_sha256=h,review_sha256=p.sha(args.review),stop_gm1=False,relaunch_gm1=False,game_executed=False,fpga_writes=0,sd_writes=0,save_writes=0,segments=[]);c=None;uart=None;cleanup=False
 def interrupted(sig,frame):
  if not cleanup:raise InterruptedError('Signal '+str(sig))
 previous={sig:signal.signal(sig,interrupted) for sig in [signal.SIGINT,signal.SIGTERM,signal.SIGHUP]}
 try:
  with open(p.LOCK,'a+') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);p.need(stat.S_ISCHR(os.stat(p.PORT).st_mode),'Port not character device');owner=subprocess.run(['fuser',p.PORT],capture_output=True);p.need(owner.returncode==1 and not owner.stdout.strip() and not owner.stderr.strip(),'Port busy')
   try:
    uart=p.UART(p.PORT);c=p.Channel(uart,args.out);c.initial_shell();result['before']=health(c,'before');result['staged']=stage_files(c,m,args.resume,result['segments']);result['passed']=True
   except BaseException as e:result['error']=repr(e)
   finally:
    cleanup=True
    if c:
     try:
      if c.current:c.restore_shell(c.current)
      if c.shell:
       result['after']=health(c,'after');delta=(result['after']['gpu']['presents']-result['before']['gpu']['presents'])&0xffffffff;p.need(0<delta<1000000,'GPU not progressing');result['presents_delta']=delta;result['preserved']=True
      else:result['passed']=False;result['manual_review_required']=True
     except BaseException as e:result['passed']=False;result['cleanup_error']=repr(e);result['manual_review_required']=True
     c.close()
    if uart:uart.close();uart=None
 except BaseException as e:result['passed']=False;result['error']=repr(e)
 finally:
  for sig,handler in previous.items():signal.signal(sig,handler)
  (args.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'passed':result['passed'],'output':str(args.out)}));return not result['passed']
if __name__=='__main__':raise SystemExit(main())
