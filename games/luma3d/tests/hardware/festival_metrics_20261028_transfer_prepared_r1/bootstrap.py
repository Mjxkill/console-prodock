"""Prepare-only shell bootstrap; never opens a UART or invokes the receiver.

Each line must be ACKed by a verified shell before sending the next one. The
caller must read back the entire file with `od`, verify SHA256 locally, THEN
chmod/execute. CRC replies from an unverified receiver are not bootstrap proof.
"""
import argparse,hashlib,json,re
from pathlib import Path

def plan(elf,path):
    if not re.fullmatch('/tmp/luma-rx2-[a-z0-9_-]+',path):raise ValueError('distinct temporary receiver path required')
    data=Path(elf).read_bytes()
    if not data.startswith(b'\x7fELF') or len(data)>32768:raise ValueError('unexpected bootstrap ELF')
    lines=[f"(set -C; umask 077; : > {path}) && printf '\\nRX2_BOOT_CREATED\\n'\n"]
    for seq,at in enumerate(range(0,len(data),96)):
        octal=''.join('\\%03o'%x for x in data[at:at+96])
        lines.append(f"printf '{octal}' >> {path} && printf '\\nRX2_BOOT_{seq:04d}\\n'\n")
    # No chmod/run command included. The pre-existing shell's od reads bytes.
    lines.append(f"printf '\\nRX2_BOOT_READ_BEGIN\\n'; od -b -v {path}; printf '\\nRX2_BOOT_READ_END\\n'\n")
    return dict(path=path,elf_bytes=len(data),elf_sha256=hashlib.sha256(data).hexdigest(),commands=lines,wire_bytes=sum(len(x.encode()) for x in lines),shell_max_line=max(map(len,lines)),verified=False)

def validate_readback(plan,text):
    m=re.search(rb'\r?\nRX2_BOOT_READ_BEGIN\r?\n(.*?)\r?\nRX2_BOOT_READ_END\r?\n',text,re.S)
    if not m:raise ValueError('missing complete od boundaries')
    raw=bytearray();ended=False
    for line in m[1].replace(b'\r',b'').splitlines():
        if not line.strip():continue
        fields=line.split()
        if ended or not fields or any(not re.fullmatch(rb'[0-7]+',f) for f in fields):raise ValueError('unexpected od output')
        if int(fields[0],8)!=len(raw):raise ValueError('noncontiguous od offset')
        if len(fields)==1:ended=True;continue
        if len(fields)>17 or any(len(f)!=3 or int(f,8)>255 for f in fields[1:]):raise ValueError('bad octal byte')
        raw.extend(int(f,8) for f in fields[1:])
    if not ended:raise ValueError('missing final od offset')
    raw=bytes(raw)
    if len(raw)!=plan['elf_bytes'] or hashlib.sha256(raw).hexdigest()!=plan['elf_sha256']:raise ValueError('bootstrap bytes mismatch')
    return raw

def storage_required(new_elf_bytes,delta_bytes,reconstructed_bytes,headroom=2*1024*1024):
    if any(type(n)!=int or n<0 for n in [new_elf_bytes,delta_bytes,reconstructed_bytes,headroom]):raise ValueError('sizes')
    return new_elf_bytes+delta_bytes+reconstructed_bytes+headroom

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--elf',type=Path,required=True);p.add_argument('--path',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=plan(a.elf,a.path)
    with a.out.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in r.items() if k!='commands'},indent=2))
