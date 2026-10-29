#!/usr/bin/env python3
"""Actual Tcl execution with synthetic MMIO; strict parser and bounded host IO tests."""
import ast,ctypes,importlib.util,json,re,subprocess,sys,tempfile
from pathlib import Path
import controller as c
HERE=Path(__file__).resolve().parent
host=c.module('test_host_usb',HERE/'host_usb.py')
original=ast.parse((c.PARENT/'test_collector.py').read_text())
HARNESS=next(ast.literal_eval(n.value) for n in original.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='HARNESS' for x in n.targets))
HARNESS=HARNESS.split('source [lindex $argv 1]')[0]
EXTRA=r'''
set gpuwords 0
set gpudone 0
array set snap {0xe9005000 0 0xe9006000 0}
set frames 1
rename sleep parent_sleep
proc sleep {n} {if {$n ni {1 2 100 200 1000}} {error "unbounded wait"}}
rename read_memory parent_read
rename write_memory parent_write
rename word parent_word
proc word {a} {
 global fault gpuwords gpudone
 if {$a in {0xe9000014 0xe9000034 0xe9000044}} {return 0}
 if {$a==0xe9001008} {return $gpudone}
 if {$a==0xe900100c} {return 0}
 return [parent_word $a]
}
proc write_memory {a bits values} {
 global snap gpuwords gpudone fault
 if {$bits!=32} {error "bad write width"}
 if {$a==0xe900200c} {return [parent_write $a $bits $values]}
 if {$a in {0xe9005004 0xe9006004}} {
  if {$values ne "1"} {error "forbidden snapshot"}
  set base [format 0x%x [expr {$a-4}]];incr snap($base);return
 }
 if {$a==0xe9001010} {
  if {$gpuwords>=8 || $values!=[lindex {0x1f000000 0 65536 0 0 0 0 0} $gpuwords]} {error "forbidden GPU command"}
  incr gpuwords
  if {$gpuwords==8 && $fault ne "gpu_timeout"} {incr gpudone}
  return
 }
 error "forbidden write $a"
}
proc read_memory {a bits count} {
 global snap gpuwords gpudone frames fault
 if {$bits!=32} {error "bad read width"}
 if {$a==0xe9000000 && $count==30} {
  set v [lrepeat 30 0];lset v 0 0x47505531;lset v 6 $frames;lset v 24 0x1ff8f800;lset v 28 0x02d00500
  if {$fault ne "video_stopped"} {incr frames};return $v
 }
 if {$a==0xe9001000 && $count==26} {set v [lrepeat 26 0];lset v 0 0x424c5432;lset v 2 $gpudone;return $v}
 foreach base {0xe9005000 0xe9006000} {
  if {$a==$base && $count==17} {
   set v [lrepeat 17 0];lset v 0 0x4e474442;lset v 1 6;lset v 2 $gpuwords;lset v 3 $snap($base);lset v 4 $gpuwords;lset v 8 $gpudone;lset v 9 0x00fff000;return $v
  }
  if {$count==1 && $a>=$base && $a<=$base+16} {
   switch [expr {$a-$base}] {
    0 {return 0x4e474442}
    4 {return [expr {$fault eq "source_stopped"?0:($snap($base)>0 && $fault ne "snapshot_timeout"?6:4)}]}
    8 {return $gpuwords}
    12 {return $snap($base)}
    16 {return [expr {$fault eq "gpu_lost" && $gpuwords?7:$gpuwords}]}
   }
  }
 }
 if {$count==1 && $a in {0xe9000014 0xe9000034 0xe9000044 0xe9001008 0xe900100c}} {return [word $a]}
 return [parent_read $a $bits $count]
}
source [lindex $argv 1]
echo {COMBINED_HOST {"devices":[],"usb_io_attempted":false,"hs_present":false,"diag_status":"NO_DEVICE"}}
source [lindex $argv 2]
if {$writes!=4} {error "wrong observer write count"}
if {$fault ni {source_stopped snapshot_timeout} && $gpuwords!=8} {error "not eight GPU words"}
'''

def main():
 out=HERE/'tests_local_04';out.mkdir(exist_ok=False);cases=[]
 begin,finish=c.parts();(out/'begin.tcl').write_text(begin);(out/'finish.tcl').write_text(finish);(out/'harness.tcl').write_text(HARNESS+EXTRA)
 for fault,passed in [('good',True),('source_stopped',False),('snapshot_timeout',False),('gpu_timeout',False),('gpu_lost',False),('video_stopped',False),('version0',False),('raw0',False)]:
  proc=subprocess.run(['tclsh',str(out/'harness.tcl'),fault,str(out/'begin.tcl'),str(out/'finish.tcl')],capture_output=True,text=True,timeout=10)
  (out/(fault+'.log')).write_text(proc.stdout+proc.stderr);c.need(proc.returncode==0,'Tcl fault '+fault+' '+proc.stderr)
  result=c.parse(proc.stdout,'a'*64,origin='synthetic');c.need(result['protocol_passed']==passed,'parse '+fault+' '+str(result.get('combined_errors')))
  c.need(result['qualification_status']=='FAIL' and not result['hardware_qualified'],'unqualified observation promoted')
  cases.append(dict(name=fault,passed=True,protocol_passed=result['protocol_passed'],errors=result['combined_errors']))
 good=(out/'good.log').read_text()
 for name,bad in [('no_host',re.sub(r'^COMBINED_HOST .*\n','',good,flags=re.M)),('wrong_continuity',re.sub(r'^UTW1_CONTROL HOST_RETURN .+$','UTW1_CONTROL HOST_RETURN 0x55544e41 0 0',good,flags=re.M)),('missing_complete',good.replace('COMBINED_DONE',''))]:
  try:c.parse(bad,'a'*64,origin='synthetic')
  except (RuntimeError,ValueError):cases.append(dict(name=name,passed=True))
  else:raise AssertionError('bad log accepted '+name)
 # Host behavior tested with no real sysfs access or USB device opens.
 saved=host.inventory;calls=[]
 def open_stub(path,flags):calls.append(('open',path));return 42
 def close_stub(fd):calls.append(('close',fd))
 def ioctl_stub(fd,request,arg):
  req=host.Control.from_buffer(arg);c.need((req.request_type,req.request,req.value,req.index,req.length,req.timeout)==(0xa0,0x21,0xd1a6,0,32,1000),'wrong diagnostic request')
  ctypes.memset(req.data,0,32);calls.append(('ioctl',fd));return 32
 dev=dict(path='/sys/bus/usb/devices/3-4.4.3',idVendor='359f',idProduct='2011',serial='11252024',speed='480',busnum='3',devnum='18')
 try:
  for name,devices,allowed,status,io in [('absent',[],None,'NO_DEVICE',False),('ambiguous',[dev,dev],dev['path'],'AMBIGUOUS',False),('FS',[dict(dev,speed='12')],dev['path'],'NON_HS_REFUSED',False),('no_path',[dev],None,'PATH_NOT_AUTHORIZED',False),('wrong_path',[dev],'/sys/bus/usb/devices/3-2','PATH_NOT_AUTHORIZED',False),('HS_bound',[dev],dev['path'],'READ_32_BYTES',True)]:
   host.inventory=lambda root:devices;calls.clear();r=host.sample(allowed,opener=open_stub,ioctl=ioctl_stub,closer=close_stub)
   c.need(r['diag_status']==status and r['usb_io_attempted']==io,'host '+name);c.need(bool(calls)==io,'host opened unexpected USB')
   if io:c.need(len(calls)==3,'multiple USB operations')
   cases.append(dict(name='host_'+name,passed=True,io_stub_used=io))
 finally:host.inventory=saved
 # The tested restoration implementation is an exact source copy, not a rewrite.
 orig=c.inspect.getsource(c.parent.execute);new=c.inspect.getsource(c.execute);c.need(orig==new,'rollback implementation changed')
 cases.append(dict(name='execute identical to frozen 52-signal collector function',passed=True))
 inputs={str(p):c.sha(p) for p in [Path(__file__),HERE/'controller.py',HERE/'gpu_video.tcl',HERE/'host_usb.py',c.PARENT/'test_collector.py']}
 report=dict(passed=True,hardware_access=False,controller_sha256=c.sha(HERE/'controller.py'),cases=cases,inputs=inputs)
 (HERE/'tests_result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,cases=len(cases))))
if __name__=='__main__':main()
