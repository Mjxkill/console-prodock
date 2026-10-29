# Derived from reviewed PP2 guards; exact complete argv, PID/starttime and idempotent fallback.
import re,time
from prodock_valley_ab import process,progress
from prodock_valley_trial import display
from prodock_arcade import stop
BASE='luma3d-gm1';BASE_SAVE='/tmp/op2-live.save';LIVE='/tmp/luma3d-live.pid'
BASE_SHA='df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b'
SAVE_SHA='2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6'
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
 assert identity(tx,'baseline_stop_identity')==expected, 'Baseline identity changed before stop'
 pid=expected['pid'];ticks=expected['start_ticks'];assert pid>1 and ticks>0
 command=(f'test "`cat {LIVE}`" = {pid} && test "`cat /proc/{pid}/comm`" = {BASE}'
          f' && set -- `cat /proc/{pid}/stat` && test "$1" = {pid} && test "$2" = "({BASE})"'
          f' && test "$3" != Z && test "$3" != X && shift 21 && test "$1" = {ticks}'
          f' && kill -TERM {pid} && sleep 1')
 tx.run('stop_baseline_term_guarded',command)
 for i in range(8):
  raw=tx.run('stop_baseline_confirm_'+str(i),f'if test -d /proc/{pid}; then cat /proc/{pid}/stat; else echo STOPPED; fi')
  if re.search(rb'^STOPPED\r?$',raw,re.M):return
  match=re.search(rb'^(\d+) \('+BASE.encode()+rb'\) ([^\r\n]+)',raw,re.M);assert match
  rest=match[2].split();assert len(rest)>=20 and int(match[1])==pid and int(rest[19])==ticks, 'PID reused; refuse further GPU launch'
  if rest[0] in (b'Z',b'X'):return
  time.sleep(1)
 raise RuntimeError('Original baseline did not stop')


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
 if not ever and process(tx,'baseline_still_alive',BASE,LIVE):
  assert identity(tx,'preserved_baseline_identity')==recovery['baseline_identity'], 'Changed baseline cannot be adopted during recovery'
  one=display(tx.run('preserved_display1','prodockctl display'));time.sleep(3)
  two=display(tx.run('preserved_display2','prodockctl display'))
  # TERM may have succeeded just before the controller lost its reply. Do
  # not call a few final presents a live recovery after that process exits.
  if process(tx,'preserved_baseline_still_alive',BASE,LIVE):
   assert identity(tx,'preserved_baseline_final_identity')==recovery['baseline_identity']
   assert (two['presents']-one['presents'])&0xffffffff
   recovery['identity']=recovery['baseline_identity'];return two
 tag=m['tag']+'_restore';pidfile='/tmp/'+tag+'.pid'
 recovery.update(attempted=True,pidfile=pidfile,log=tag+'.log')
 tx.run('restore_baseline',f'/tmp/{BASE} --showcase < /dev/null > /tmp/{tag}.log 2>&1 & echo $! > {pidfile}')
 anchor=identity(tx,'restore_identity',pidfile);recovery['identity']=anchor
 result=progress(tx,BASE,tag+'.log','restored_baseline',pidfile)
 assert identity(tx,'restore_after_progress',pidfile)==anchor
 tx.run('publish_restored_pid','cp '+pidfile+' '+LIVE)
 assert identity(tx,'restore_after_publish')==anchor;return result


