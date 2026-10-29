#!/usr/bin/env python3
"""Prepared Festival R9 trial. Check-only by default; no board access on import.

The explicit --run path requires a separate root review bound to the complete
manifest. All board actions occur on ax15, under the Pro Dock lock and exclusive
UART. Only temporary RAM payloads are installed. GM1 is always restored.
"""
import argparse,contextlib,fcntl,hashlib,importlib,json,math,re,signal,socket,sys,time,zlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
SSH_HOST='ax15'
LOCAL_HOSTNAME='michael-AX15'
PORT='/dev/serial/by-id/usb-Electrosens_MegaPro_Console_11252024-if00'
LOCK='/tmp/prodock-diagnostic.lock'
MIN_TMP_KIB=32768
ANCHOR={'pid':3158,'start_ticks':27508908}
BASE_SHA='df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b'
SAVE_SHA='2138ac0ad21a4707aad2dc0613381e3bde131acfa783dbb29a43f4d6a4c08cc6'
RELEASE='6.12.112-prodock-luma3d-g3d1-r1'
FPGA_SHA='fbbea9c357d0c4d5b33c3c4a7e54f9ed0ff8e31cc3fad1ac9dc1771f8e8cba5f'
DEPS=('prodock_transport.py','prodock_valley_ab.py','prodock_valley_trial.py',
      'prodock_valley_benchmark.py','prodock_order.py','prodock_arcade.py',
      'trial_guards.py','check_linux.py','check_gpu_reloads.py','guarded_transport.py')

def require(test,message):
    if not test:raise RuntimeError(message)
def digest(path):
    b=Path(path).read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def schedule():
    rows=[dict(name=['othello','solitaire','chroma','hangman','garden'][k],kind=k,
               frames=120,manual=True,timeout=240) for k in range(5)]
    return rows+[dict(name='automatic_tour',kind=4,frames=450,manual=False,timeout=600)]
def arguments(row):
    return '--festival'+(f' --festival-game {row["kind"]}' if row['kind']<4 else '')+(' --manual' if row['manual'] else '')+f' --frames {row["frames"]}'

def launch_command(program,tag,args):
    require(re.fullmatch(r'[A-Za-z0-9_.-]+',program) and re.fullmatch(r'[A-Za-z0-9_.-]+',tag),'Unsafe launch identifier')
    # Only the child supervisor can acknowledge the completed atomic rename.
    # ARCADE_LAUNCHED merely says the parent shell started that supervisor.
    return (f'( /tmp/{program} {args} < /dev/null > /tmp/{tag}.log 2>&1 & p=$!;'
            f' printf "%s\\n" "$p" > /tmp/{tag}.pid.tmp && mv /tmp/{tag}.pid.tmp /tmp/{tag}.pid'
            f' && printf "\\nF9_PID_{tag}:%s\\n" "$p";'
            f' wait "$p"; rc=$?; echo "$rc" > /tmp/{tag}.exit; printf "\\nL3_EXIT_{tag}:%s\\n" "$rc" ) < /dev/null & echo ARCADE_LAUNCHED')

class LaunchState:
    def __init__(self,program,tag):
        self.program,self.tag=program,tag;self.pidfile='/tmp/'+tag+'.pid'
        self.state='not_sent';self.pid=None;self.exit_code=None
    @property
    def attempted(self):return self.state!='not_sent'
    def begin_write(self):
        require(self.state=='not_sent','Duplicate initial launch write')
        self.state='sending_unknown'
    def observe(self,data):
        pids=re.findall(rb'^F9_PID_'+self.tag.encode()+rb':(\d+)\r?\n',data,re.M)
        if pids:
            require(self.attempted and len(set(pids))==1,'Unexpected launch publication')
            pid=int(pids[0]);require(pid>1 and (self.pid is None or self.pid==pid),'Candidate PID changed')
            self.pid=pid
            if self.state!='completed':self.state='published'
        exits=re.findall(rb'^L3_EXIT_'+self.tag.encode()+rb':(\d+)\r?\n',data,re.M)
        if exits:
            require(self.attempted and len(set(exits))==1,'Unexpected completion marker')
            code=int(exits[0]);require(code<=255 and (self.exit_code is None or self.exit_code==code),'Completion changed')
            self.exit_code=code;self.state='completed'
    def cleanup_target(self):
        # Unpublished after any write remains uncertain and must fail closed.
        return None if self.state in ('not_sent','completed') else (self.program,self.pidfile)
    def record(self):return dict(program=self.program,pidfile=self.pidfile,state=self.state,pid=self.pid,exit_code=self.exit_code)

class CommandUART:
    """Track the first attempted write, not the intent to call Transport.run."""
    def __init__(self,uart,signals):self.uart,self.signals,self.launch=uart,signals,None
    @property
    def timeout(self):return self.uart.timeout
    @timeout.setter
    def timeout(self,value):self.uart.timeout=value
    def write(self,data):
        if self.launch is not None and self.launch.state=='not_sent':
            self.signals.checkpoint();self.launch.begin_write()
        return self.uart.write(data)
    def __getattr__(self,name):return getattr(self.uart,name)

def preflight(bundle,expected=None):
    require(__debug__,'Python -O would disable guards in frozen dependencies')
    bundle=Path(bundle).resolve();manifest=bundle/'manifest.json'
    if expected:require(digest(manifest)['sha256']==expected,'Manifest changed')
    m=json.loads(manifest.read_text())
    require(m['schema']==1 and m.get('controller_revision')==4 and m['candidate'] and m['hardware_tested'] is False,'Not a prepared v4 candidate')
    require(m['board']=='prodock' and m['host']==SSH_HOST and m.get('local_hostname')==LOCAL_HOSTNAME and m['port']==PORT and m['lock']==LOCK,'Wrong board or transport')
    require(m['expected_identity']==ANCHOR and m['baseline']['sha256']==BASE_SHA,'Stale baseline anchor')
    require(m['save_sha256']==SAVE_SHA and m['kernel']==RELEASE and m['fpga_sha256']==FPGA_SHA,'Wrong retained reference')
    require(m['program']=='luma3d-f9d' and m['tag']=='festivalr9d' and m['helper']=='f9d-helper','Unexpected program names')
    require(m['windows']==schedule() and m['normal_exit']=='restore_gm1','Unreviewed schedule or cleanup')
    require(m['transfer_files']==['f9d-helper','festival-r9d.delta.lz4'],'Unreviewed transfer')
    require(m.get('storage_guard')==dict(mount='/tmp',minimum_available_kib=MIN_TMP_KIB,check='before_each_transfer_and_reconstruction'),'Missing or weakened tmpfs capacity guard')
    require(set(DEPS).issubset(m['files']) and 'festival_trial.py' in m['files'],'Missing imported sources')
    for name,expected_file in m['files'].items():
        require(re.fullmatch(r'[A-Za-z0-9_.-]+',name) is not None,'Unsafe local path')
        p=bundle/name;require(p.is_file() and not p.is_symlink(),'Missing/linked input '+name)
        require(digest(p)==expected_file,'Changed input '+name)
    require(all(p.name in m['files'] for p in bundle.glob('*.py')),'Unhashed Python source in bundle')
    require(digest(HERE/'festival_trial.py')==m['files']['festival_trial.py'],'Executing another controller')
    gm=json.loads((bundle/'game_manifest.json').read_text());bm=json.loads((bundle/'baseline_manifest.json').read_text())
    require(gm['riscv']==m['game'] and bm['riscv']==m['baseline'],'ELF provenance mismatch')
    require(m['game_manifest_sha256']==digest(bundle/'game_manifest.json')['sha256'],'Wrong R9 manifest')
    d=m['delta'];require(d['old_sha256']==BASE_SHA and d['new_sha256']==m['game']['sha256'] and d['new_bytes']==m['game']['bytes'] and d['new_crc32']==m['game']['crc32'],'Delta identity mismatch')
    require(d['file']=='festival-r9d.delta.lz4','Wrong delta')
    reconstruction=json.loads((bundle/'reconstruction.json').read_text());require(reconstruction['passed'] and reconstruction['game']==m['game'],'No exact reconstruction')
    prior=json.loads((bundle/'prior_result.json').read_text());require(prior['passed'] and prior['final_identity']==ANCHOR and prior['save_final']['sha256']==SAVE_SHA,'Anchor is not the restored MC1 process')
    guarded=json.loads((bundle/'guard_tests.json').read_text());require(guarded['passed'] and guarded['hardware'] is False and guarded['files']['guarded_transport.py']==m['files']['guarded_transport.py']['sha256'],'Guarded transport tests are stale')
    receiver=json.loads((bundle/'receiver_exact.json').read_text());require(receiver['passed'] and receiver['hardware'] is False,'Exact receiver counterexample missing')
    require(receiver['inputs'].get('games/luma_adventure/tests/hardware/trial_20261024_r9b/uart-receiver')=='5964389b8244dc73b58bf916a7856da3cc3aba2c2efa58779d1f755bb8410ae4','Receiver proof covers another ELF')
    require(receiver['artifacts']['initrd.cpio.gz']==digest(bundle/'receiver-test-initrd.cpio.gz')['sha256'],'Receiver test initrd changed')
    for name in ('logic_r9','logic_r9_sanitize','temporal_r9','temporal_r9_sanitize','cli_r9'):
        proof=json.loads((bundle/(name+'.json')).read_text());require(proof['passed'] and proof['hardware'] is False,'Missing local proof '+name)
        if 'manifest_sha256' in proof:require(proof['manifest_sha256']==m['game_manifest_sha256'],'Stale local proof')
        if 'executable_sha256' in proof:require(proof['executable_sha256']==gm['host']['sha256'],'Wrong host proof')
    return m

def check_review(review,m,manifest_sha,host):
    require(host==LOCAL_HOSTNAME and m.get('local_hostname')==LOCAL_HOSTNAME,'Hardware execution is restricted to '+LOCAL_HOSTNAME)
    require(review.get('approved') is True and review.get('reviewer')=='root','Independent root review missing')
    require(review.get('ssh_host')==SSH_HOST and review.get('local_hostname')==LOCAL_HOSTNAME,'Review host identity mismatch')
    require(review.get('manifest_sha256')==manifest_sha and review.get('controller_sha256')==m['files']['festival_trial.py']['sha256'],'Review does not cover these exact bytes')
    require(review.get('board')=='prodock' and review.get('expected_identity')==ANCHOR,'Review anchor mismatch')
    require(review.get('fpga')=='G22r0' and review.get('fpga_sha256')==FPGA_SHA and review.get('continuity_confirmed') is True,'G22r0 continuity not attested')
    require(review.get('kernel')==RELEASE and review.get('save_sha256')==SAVE_SHA,'Review reference mismatch')

def dependencies(bundle,m):
    # Hash every transitive local import before executing any of them.
    bundle=Path(bundle).resolve()
    for name in DEPS:
        require(digest(bundle/name)==m['files'][name],'Dependency changed '+name)
        existing=sys.modules.get(Path(name).stem)
        if existing:require(Path(existing.__file__).resolve()==bundle/name,'Foreign cached import '+name)
    sys.path.insert(0,str(bundle))
    modules={Path(name).stem:importlib.import_module(Path(name).stem) for name in DEPS}
    for name,module in modules.items():require(Path(module.__file__).resolve()==bundle/(name+'.py'),'Import escaped bundle')
    return modules

def fields(raw,prefix):
    lines=re.findall(rb'^'+prefix.encode()+rb' ([^\r\n]+)',raw,re.M)
    require(len(lines)==1,'Missing/duplicate '+prefix)
    result={}
    for key,value in re.findall(rb'(\w+)=(\S+)',lines[0]):
        name=key.decode();require(name not in result,'Duplicate metric')
        if name in ('visited','won'):result[name]=int(value,16)
        else:
            v=float(value);require(math.isfinite(v) and v>=0,'Invalid metric');result[name]=v
    return result

def parse_window(raw,row):
    require(b'LUMA3D_SAVE ' not in raw and b'LUMA3D_SHOWCASE_RESULT ' not in raw,'Unexpected campaign mutation')
    r=fields(raw,'LUMA3D_RESULT');f=fields(raw,'LUMA3D_FESTIVAL');g=fields(raw,'LUMA3D_COUNTERS')
    require(r['hardware']==f['hardware']==1 and r['benchmark']==0 and r['warmup']==0,'Not real-time hardware measurement')
    require(r['frames']==row['frames'] and r['elapsed']>0 and r['fps']>0 and f['active']==1,'Incomplete window')
    require(abs(r['fps']-r['frames']/r['elapsed'])<=.05,'Inconsistent FPS')
    require(all(g[k]==0 for k in ('errors','underflows','fault','geometry_errors')),'GPU/display error')
    require(g['frames']==row['frames'],'Present count mismatch')
    require(f['mode'] in range(5) and f['visited']<=15 and f['won']<=15 and not(int(f['won'])&~int(f['visited'])),'Invalid Festival state')
    if row['manual']:require(f['mode']==row['kind'],'Window changed scene')
    perf=re.findall(rb'^LUMA3D_PERF [^\r\n]+',raw,re.M)
    counters=re.findall(rb'^LUMA3D_WINDOW [^\r\n]+',raw,re.M)
    require(len(perf)==len(counters),'Incomplete periodic metrics')
    return dict(result=r,festival=f,counters=g,periodic_windows=len(perf),scope='Static table/garden average including entry; no animated per-table FPS claim' if row['manual'] else 'Global automatic Festival average; scene mix depends on real frame rate')

class DeferredSignals:
    def __init__(self):self.received=[];self.cleanup=False;self.previous={}
    def handler(self,number,frame):self.received.append(number)
    def checkpoint(self):
        if self.received and not self.cleanup:raise InterruptedError('Interrupted by signal '+str(self.received[0]))
    def __enter__(self):
        for number in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):self.previous[number]=signal.signal(number,self.handler)
        return self
    def __exit__(self,*unused):
        for number,old in self.previous.items():signal.signal(number,old)

class Session:
    """One experiment state machine; recovery remains inside the UART lock."""
    def __init__(self,backend,m,signals):
        self.b,self.m,self.signals=backend,m,signals;self.stopped=False;self.current=None;self.ever=False;self.recovery={};self.result=dict(passed=False,hardware=True,windows=[],fpga_writes=0,kernel_writes=0,sd_writes=0,flash_writes=0,save_writes=0,candidate_promoted=False)
    def run(self):
        try:
            self.signals.checkpoint();self.result['initial']=self.b.initial();self.recovery['baseline_identity']=ANCHOR.copy()
            self.signals.checkpoint();self.result['transfers']=self.b.prepare()
            self.signals.checkpoint();self.b.recheck()
            self.stopped=True;self.b.stop_baseline()
            for i,row in enumerate(self.m['windows']):
                self.signals.checkpoint();tag=self.m['tag']+'_'+str(i)
                self.current=LaunchState(self.m['program'],tag)
                value=self.b.window(row,tag,self.current);self.ever|=self.current.attempted
                self.current=None;self.result['windows'].append(value)
            self.result['functional_passed']=True
        except BaseException as error:self.result['error']=repr(error)
        finally:
            self.signals.cleanup=True
            receiver_resolved=True
            try:self.b.abort_transfer()
            except BaseException as error:
                self.result['receiver_abort_error']=repr(error);receiver_resolved=False
            if not receiver_resolved:
                self.result['cleanup_blocked']='Receiver return or confirmed-return resynchronization unresolved; subsequent preservation/recovery queries skipped'
                self.result['manual_recovery_required']=True
            elif self.stopped:
                try:
                    target=None
                    if self.current is not None:
                        self.result['interrupted_launch']=self.current.record();self.ever|=self.current.attempted
                        target=self.current.cleanup_target()
                    self.result['recovery']=self.b.recover(target,self.ever,self.recovery)
                    self.result['restored_gm1']=True
                except BaseException as error:self.result['cleanup_error']=repr(error)
            elif 'initial' in self.result:
                try:self.result['preserved_gm1']=self.b.preserved()
                except BaseException as error:self.result['cleanup_error']=repr(error)
            self.result['signals']=self.signals.received[:]
            self.result['receiver_resync_attempted']=bool(getattr(self.b,'receiver_resync_attempted',False))
            self.result['passed']=bool(self.result.get('functional_passed') and self.result.get('restored_gm1') and not any(k in self.result for k in ('error','cleanup_error','receiver_abort_error')) and not self.signals.received)
            self.result['outcome']='FESTIVAL_TESTED_GM1_RESTORED' if self.result['passed'] else 'FAILED_OR_INTERRUPTED'
        return self.result

def tmp_capacity(raw):
    # POSIX df -P -k: filesystem, 1024-blocks, used, available, capacity, mount.
    # Ignore shell framing, but never accept a row for a different mount.
    rows=[]
    for line in raw.splitlines():
        columns=line.split()
        if len(columns)==6 and columns[-1]==b'/tmp':
            require(all(re.fullmatch(rb'[0-9]+',x) for x in columns[1:4]) and re.fullmatch(rb'[0-9]+%',columns[4]),'Malformed /tmp capacity row')
            total,used,available=map(int,columns[1:4])
            require(total>0 and used<=total and available<=total and used+available<=total,'Inconsistent /tmp capacity row')
            rows.append(dict(total_kib=total,used_kib=used,available_kib=available))
    require(len(rows)==1,'Missing or duplicate /tmp capacity row')
    require(rows[0]['available_kib']>=MIN_TMP_KIB,'Insufficient /tmp space: need at least 32 MiB available; no payload sent at this checkpoint')
    return rows[0]

class Hardware:
    def __init__(self,bundle,out,m,uart,signals,modules):
        self.bundle,self.out,self.m,self.uart,self.signals,self.mods=bundle,out,m,uart,signals,modules
        base=modules['guarded_transport'].guarded_class(modules['prodock_transport'].Transport)
        port=CommandUART(uart,signals)
        class CheckedTransport(base):
            def run(tx,*args,launch=None,**kw):
                signals.checkpoint();require(port.launch is None,'Nested command launch')
                port.launch=launch
                try:
                    data=super().run(*args,**kw)
                    if launch is not None:launch.observe(data)
                except BaseException as error:
                    if launch is not None and hasattr(error,'data'):launch.observe(error.data)
                    raise
                finally:port.launch=None
                signals.checkpoint();return data
        self.tx=CheckedTransport(port,modules['check_linux'].command,out);self.guard=modules['trial_guards'];self.arcade=modules['prodock_arcade'];self.display=modules['prodock_valley_trial'].display
        self.tx.rx_checkpoint=signals.checkpoint;self.receiver_resync_attempted=False
    def identity(self,label):
        got=self.guard.identity(self.tx,label);require(got==ANCHOR,'Live GM1 identity changed');return got
    def save(self,label):
        got=self.arcade.saved_bytes(self.tx,label,self.guard.BASE_SAVE,4);require(got['sha256']==SAVE_SHA,'Saved campaign changed');return dict(bytes=got['bytes'],sha256=got['sha256'])
    def initial(self):
        self.uart.write(b'\n');time.sleep(.2);self.uart.read(16000)
        raw=self.tx.run('before','uname -r; prodockctl display; cat /proc/mounts')
        require(re.search(rb'^'+RELEASE.encode()+rb'\r?$',raw,re.M) is not None,'Wrong kernel')
        require(b'tmpfs /tmp tmpfs ' in raw and not re.search(rb'^/dev/mmc\S* ',raw,re.M),'Unexpected filesystem/SD mount')
        first=self.display(raw);anchor=self.identity('initial_gm1');saved=self.save('save_initial');time.sleep(3)
        second=self.display(self.tx.run('progress_before','prodockctl display'));require((second['presents']-first['presents'])&0xffffffff,'GM1 not presenting')
        names=self.m['transfer_files']+[self.m['program']]+[self.m['tag']+'_'+str(i)+'.'+ext for i in range(len(self.m['windows'])) for ext in ('pid','pid.tmp','log','exit')]+[self.m['tag']+'_restore.'+ext for ext in ('pid','log')]
        self.tx.run('fresh_names',' && '.join('test ! -e /tmp/'+n for n in names))
        return dict(identity=anchor,save=saved,display=second,kernel=RELEASE,fpga='G22r0 continuity confirmed by external root review')
    def space(self,label):
        return tmp_capacity(self.tx.run('space_'+label,'LC_ALL=C df -Pk /tmp'))
    def prepare(self):
        bench=self.mods['prodock_valley_benchmark'];bench.readback(self.tx,'receiver_readback','/tmp/luma-rx',1464,self.mods['prodock_transport'].RECEIVER_SHA)
        transfers=[]
        for name in self.m['transfer_files']:
            self.signals.checkpoint();self.space('before_transfer_'+name)
            transfers.append(self.tx.transfer(self.bundle/name,name,expected=self.m['files'][name]))
        helper=self.m['helper'];self.tx.run('helper_mode','chmod 700 /tmp/'+helper)
        bench.readback(self.tx,'helper_readback','/tmp/'+helper,self.m['files'][helper]['bytes'],self.m['files'][helper]['sha256'])
        self.arcade.raw_verify(self.tx,helper,'baseline_file','/tmp/luma3d-gm1',self.m['baseline'])
        self.arcade.raw_verify(self.tx,helper,'baseline_running','/proc/3158/exe',self.m['baseline'])
        self.space('before_reconstruction')
        d=self.m['delta'];q=self.m['game'];raw=self.tx.run('install_candidate',f'/tmp/{helper} patch /tmp/{d["file"]} /tmp/{self.m["program"]} {d["patch_bytes"]} {d["patch_crc32"]} /tmp/luma3d-gm1',120)
        require(f'LUMA3D_UNPACK_OK bytes={q["bytes"]} crc32={q["crc32"]}'.encode() in raw,'Reconstruction failed')
        self.tx.run('candidate_mode','chmod 700 /tmp/'+self.m['program']);self.arcade.raw_verify(self.tx,helper,'candidate_file','/tmp/'+self.m['program'],q)
        return transfers
    def recheck(self):self.identity('before_switch');self.save('save_before_switch')
    def stop_baseline(self):
        self.guard.stop_baseline(self.tx,ANCHOR)
        raw=self.tx.run('released','prodockctl info; prodockctl display');require(b'GPU ABI=1 caps=000001ff DDR=00800000+90177536 ' in raw,'Wrong GPU ABI');self.display(raw)
    def window(self,row,tag,launch):
        raw=self.tx.run(tag+'_launch',launch_command(self.m['program'],tag,arguments(row)),launch=launch)
        data=bytearray(raw);deadline=time.monotonic()+row['timeout'];pattern=re.compile(rb'^L3_EXIT_'+tag.encode()+rb':(\d+)\r?\n',re.M)
        try:
            while True:
                launch.observe(data);self.signals.checkpoint();found=pattern.search(data)
                if found:require(int(found[1])==0,'Candidate exited with error');break
                require(time.monotonic()<deadline,'Window deadline expired');data.extend(self.uart.read(4096))
        finally:(self.out/(tag+'_wait.log')).write_bytes(data)
        value=parse_window(self.tx.run(tag+'_log','cat /tmp/'+tag+'.log',120),row)
        value['display']=self.display(self.tx.run(tag+'_display','prodockctl display'));return dict(window=row,measurement=value)
    def abort_transfer(self):
        self.tx.abort() # Unknown/receiving/received_D refuse before any write.
        if self.tx.receiver_state=='returned_error':
            # The receiver's numeric exit marker is confirmed, but a binary
            # fragment may still occupy the shell's current line.
            self.receiver_resync_attempted=True
            self.uart.write(b'\x03\x15\n');self.uart.flush();time.sleep(.2)
            raw=self.tx.run('receiver_confirmed_resync','printf "\\nLMA_CONFIRMED_RX_SHELL\\n"',10)
            require(re.search(rb'^LMA_CONFIRMED_RX_SHELL\r?\n',raw,re.M) is not None,'Shell resynchronization failed after confirmed receiver return')
            self.tx.set_state('idle')
    def preserved(self):self.identity('preserved_identity');return dict(identity=ANCHOR,save=self.save('preserved_save'))
    def recover(self,current,ever,recovery):
        # Cancel a possible partial foreground shell command; candidates have
        # their own /dev/null supervisor and are stopped by guarded PID below.
        self.uart.write(b'\x03');self.uart.flush();time.sleep(.3);self.uart.read(16000)
        self.arcade.raw_verify(self.tx,self.m['helper'],'recovery_baseline_file','/tmp/luma3d-gm1',self.m['baseline'])
        restored=self.guard.recover(self.tx,self.m,current,ever,recovery)
        saved=self.save('save_after_recovery');anchor=self.guard.identity(self.tx,'recovery_final_identity')
        require(anchor==recovery['identity'],'Recovery identity changed')
        self.arcade.raw_verify(self.tx,self.m['helper'],'recovery_running_file','/proc/'+str(anchor['pid'])+'/exe',self.m['baseline'])
        return dict(display=restored,identity=anchor,save=saved)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,default=HERE);p.add_argument('--run',action='store_true');p.add_argument('--review',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    bundle=a.bundle.resolve();m=preflight(bundle);sha=digest(bundle/'manifest.json')['sha256']
    if not a.run:print(json.dumps(dict(preflight_passed=True,hardware_access=False,root_review_required=True,manifest_sha256=sha)));return
    require(a.review is not None and a.out is not None,'--run requires --review and --out')
    review=json.loads(a.review.read_text());check_review(review,m,sha,socket.gethostname());mods=dependencies(bundle,m)
    import serial
    a.out.mkdir(parents=True,exist_ok=False)
    with DeferredSignals() as signals,open(LOCK,'a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
            session=Session(Hardware(bundle,a.out,m,uart,signals,mods),m,signals);result=session.run()
            result.update(manifest_sha256=sha,review_sha256=digest(a.review)['sha256'],reference_kernel=RELEASE)
            (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
