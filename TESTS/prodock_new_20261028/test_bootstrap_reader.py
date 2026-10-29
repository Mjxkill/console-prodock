#!/usr/bin/env python3
"""Transcript checks only: full readback, no ambiguous append retry/early exec."""
import hashlib,importlib.util,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('reader_boot',HERE/'bootstrap_reader.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ROOT=next(p for p in HERE.parents if (p/'ARCHI/COMPATIBILITE_CARTES.md').is_file());m.TRANSPORT=ROOT/'games/luma3d/tests/hardware/festival_persistent_20261028_prepared_r1'
data=(HERE/'stage_reader/stage_reader').read_bytes();lines=m.commands(data)
assembled=b''.join(bytes(int(x,8) for x in re.findall(r'\\([0-7]{3})',line)) for line in lines[1:-1]);assert assembled==data
for line in lines:assert '\n' not in line and not any(ord(c)<32 for c in line)
def dump(blob):
    rows=[('%07o'%i)+' '+ ' '.join('%03o'%b for b in blob[i:i+16]) for i in range(0,len(blob),16)];rows.append('%07o'%len(blob));return ('\r\nRX2_BOOT_READ_BEGIN\r\n'+'\r\n'.join(rows)+'\r\nRX2_BOOT_READ_END\r\n').encode()
class Fake:
    def __init__(self,fault=None):self.fault=fault;self.calls=[]
    def initial_shell(self):pass
    def run(self,name,command,timeout=90):
        self.calls.append((name,command))
        if name=='kernel':return (m.KERNEL+'\n'+'tmpfs /tmp tmpfs rw 0 0\n').encode()
        if name=='space':return b'tmpfs 100000 1000 99000 1% /tmp\n'
        if self.fault=='timeout' and name=='bootstrap_003':raise TimeoutError('ambiguous append')
        if name.startswith('bootstrap_'):
            index=int(name.split('_')[1])
            if index==len(lines)-1:return dump(data[:-1] if self.fault=='truncated' else data)
            marker='RX2_BOOT_CREATED' if index==0 else f'RX2_BOOT_{index-1:04d}'
            return ('\r\n'+marker+'\r\n').encode()
        if name=='extract_fm4a':return b'\r\nSTAGE_FM4A_OK bytes=16640496 crc=fa358bf4\r\n'
        return b''
f=Fake();r=m.execute(f,data);assert r['reader_full_readback_sha256']==m.READER_SHA and not r['game_launched']
for fault in ['timeout','truncated']:
    f=Fake(fault)
    try:m.execute(f,data)
    except (TimeoutError,ValueError):pass
    else:raise AssertionError('accepted '+fault)
    assert not any(n in ['chmod_verified','extract_fm4a'] for n,c in f.calls)
    if fault=='timeout':assert sum(n=='bootstrap_003' for n,c in f.calls)==1
result={'passed':True,'hardware':False,'script_sha256':hashlib.sha256((HERE/'bootstrap_reader.py').read_bytes()).hexdigest(),'cases':['136 exact octal chunks','Full readback before chmod/execute','Ambiguous append aborts without retry or execute','Truncated readback aborts before chmod/execute','No game launch'],'limits':['Transcript/command generation test only, no UART/kernel/hardware test']}
(HERE/'bootstrap_reader_tests.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
