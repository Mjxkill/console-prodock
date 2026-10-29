"""Generic RX2 staging only. No device opening, no process/game control.

Root supplies a previously reviewed Channel with the exclusive UART lock and
fresh hardware identities. On every exception, root invokes restore_shell on
channel.current: that routine waits RETURN passively and otherwise stays silent.
"""
import hashlib,json,math,os,zlib
from pathlib import Path
import sender
HERE=Path(__file__).resolve().parent
def require(value,text):
 if not value:raise ValueError(text)
def digest(data):return dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),crc32=f'{zlib.crc32(data):08x}')
def load_plan(bundle=HERE):
 m=json.loads((bundle/'plan.json').read_text())
 for name,d in m['files'].items():
  p=bundle/name;require(not p.is_symlink() and digest(p.read_bytes())==d,'Bundle changed '+name)
 require(m['base']['sha256']=='df529a3463d6f3138895eeefb6ac70d149d7a714f51be74fb79a73079054e29b','Wrong base')
 require(m['target']['sha256']=='6b8d3eeb273e03be38eb73a2ff6fee60dad16678316bfdacb52b4db308fec3f7','Wrong target')
 require(m['target']['bytes']<=16<<20 and m['delta']['raw_bytes']<=16<<20,'Historical helper bound exceeded')
 require(m['hardware_ready'] is False and m['hardware_access'] is False,'This is a preparation only')
 return m
def segment(channel,plan,bundle=HERE,*,resume=False,blocks=512,pause=.002,expected_offset=None):
 """A maximum256KiB per session; returned checkpoint decides next invocation.

 No automatic retry of a session or unknown launch. Payload is rechecked here.
 Protocol CRC prevents accidental damage. Offline SHA pins exact inputs and
 output; the retained helper verifies full-file CRC32 at runtime. No hardware
 SHA measurement of the16.64MB output is claimed by this staging controller.
 """
 require(type(blocks)==int and 1<=blocks<=512,'Segment bound')
 payload=(bundle/plan['payload_file']).read_bytes();require(digest(payload)==plan['files'][plan['payload_file']],'Payload changed')
 require(channel.shell and channel.current is None,'Shell not confirmed')
 s=sender.Session(channel,os.urandom(16).hex(),payload,idle_ms=5000,total_ms=900000,pause=pause)
 channel.current=s;channel.shell=False
 channel.text(s.command(plan['rx2_executable'],plan['remote_payload'],resume))
 ready=s.begin();require(expected_offset is not None and ready.offset==expected_offset,'READY differs from reviewed checkpoint');start=ready.offset;count=0
 while s.offset<len(payload) and count<blocks:s.block();count+=1
 complete=s.offset==len(payload);s.finish(stop=not complete);channel.restore_shell(s)
 return dict(complete=complete,start_offset=start,offset=s.offset,blocks=count,wire_frames=s.sent_frames,retries=s.retries,prefix_crc=s.prefixes[s.offset],returncode=s.returncode)
def storage_check(available_kib,plan,*,payload_exists=False):
 require(type(available_kib)==int and available_kib>=0,'Invalid free space')
 needed=plan['storage']['target_bytes']+plan['storage']['headroom_bytes']+(0 if payload_exists else plan['storage']['payload_bytes'])
 require(available_kib*1024>=needed,'Insufficient tmpfs capacity, no automatic deletion')
 return needed
if __name__=='__main__':
 p=load_plan();print(json.dumps({'prepared':True,'hardware_access':False,'payload':p['files'][p['payload_file']],'target':p['target'],'segments':p['transport']['planned_sessions']}))
