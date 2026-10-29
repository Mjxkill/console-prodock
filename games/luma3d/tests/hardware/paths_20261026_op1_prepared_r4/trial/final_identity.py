#!/usr/bin/env python3
"""One read-only cleanup identity/save check; never starts/stops a game."""
import fcntl,hashlib,json,re,sys,zlib
from pathlib import Path
import serial
bundle=Path(sys.argv[1]);out=Path(sys.argv[2]);sys.path.insert(0,str(bundle))
from check_linux import command
from prodock_transport import Transport
from prodock_valley_ab import PORT
from prodock_valley_trial import display
r=json.loads((out/'result.json').read_text());assert not r['passed'] and r['restored_am1']
blob=bytes.fromhex(r['baseline_save']['hex']);crc=f'{zlib.crc32(blob):08x}'
with open('/tmp/prodock-diagnostic.lock','a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 with serial.Serial(PORT,115200,timeout=.1,exclusive=True) as uart:
  tx=Transport(uart,command,out)
  raw=tx.run('final_identity','p=`cat /tmp/luma3d-live.pid`; cat /proc/$p/stat; cat /proc/$p/cmdline; echo; prodockctl display')
  match=re.search(rb'^(1754) \(luma3d-am1\) ([^\r\n]+)',raw,re.M);assert match
  stat=match[2].split();assert stat[0] not in (b'Z',b'X') and len(stat)>=20
  assert b'/tmp/luma3d-am1\x00--save\x00/tmp/op1-am1-recovery.save\x00' in raw
  state=dict(pid=1754,start_ticks=int(stat[19]),display=display(raw),program='/tmp/luma3d-am1',save='/tmp/op1-am1-recovery.save',no_new_gpu_test=True)
  checked=tx.run('baseline_v3_preserved',f'/tmp/op1-helper raw /tmp/am1-live.save unused 136 {crc}')
  assert f'LUMA3D_RAW_OK bytes=136 crc32={crc}'.encode() in checked
  state['original_v3_sha256']=hashlib.sha256(blob).hexdigest();state['original_v3_crc32_verified']=crc
(out/'final_identity.json').write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state))
