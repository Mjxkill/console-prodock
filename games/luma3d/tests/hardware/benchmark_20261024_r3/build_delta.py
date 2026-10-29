#!/usr/bin/env python3
"""Small COPY/LITERAL transport delta; both exact ELF identities remain external."""
import argparse,ctypes,ctypes.util,hashlib,json,struct,zlib
from pathlib import Path

def compress(data):
    lib=ctypes.CDLL(ctypes.util.find_library('lz4'))
    lib.LZ4_compressBound.argtypes=[ctypes.c_int]
    lib.LZ4_compress_HC.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int]
    buf=ctypes.create_string_buffer(lib.LZ4_compressBound(len(data)))
    size=lib.LZ4_compress_HC(data,buf,len(data),len(buf),12);assert size>0
    return struct.pack('<4I',0x4c345a4c,len(data),size,zlib.crc32(data))+buf.raw[:size]

def delta(old,new):
    assert 0<len(old)<=16<<20 and 0<len(new)<=16<<20
    table={}
    for offset in range(0,len(old)-31,32):
        key=zlib.crc32(old[offset:offset+32]);bucket=table.setdefault(key,[])
        if len(bucket)<8:bucket.append(offset)
        else:bucket[-1]=offset
    ops=[];position=literal=0
    while position+32<=len(new):
        best=0;source=0;key=zlib.crc32(new[position:position+32])
        for offset in table.get(key,[]):
            if old[offset:offset+32]!=new[position:position+32]:continue
            lo=32;hi=min(len(old)-offset,len(new)-position)
            while lo<hi:
                mid=(lo+hi+1)//2
                if old[offset:offset+mid]==new[position:position+mid]:lo=mid
                else:hi=mid-1
            if lo>best:best=lo;source=offset
        if best>=64:
            if position>literal:ops.append((0xffffffff,new[literal:position]))
            ops.append((source,best));position+=best;literal=position
        else:position+=1
    if literal<len(new):ops.append((0xffffffff,new[literal:]))
    result=bytearray(struct.pack('<6I',0x3150334c,len(old),zlib.crc32(old),len(new),zlib.crc32(new),len(ops)))
    for offset,payload in ops:
        if offset==0xffffffff:result.extend(struct.pack('<2I',offset,len(payload))+payload)
        else:result.extend(struct.pack('<2I',offset,payload))
    return bytes(result)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('old',type=Path);p.add_argument('new',type=Path);p.add_argument('out',type=Path);a=p.parse_args()
    old=a.old.read_bytes();new=a.new.read_bytes();raw=delta(old,new);packed=compress(raw);a.out.write_bytes(packed)
    metadata={'old_sha256':hashlib.sha256(old).hexdigest(),'new_sha256':hashlib.sha256(new).hexdigest(),
              'old_bytes':len(old),'new_bytes':len(new),'new_crc32':'%08x'%zlib.crc32(new),
              'patch_bytes':len(raw),'patch_crc32':'%08x'%zlib.crc32(raw),'transport_bytes':len(packed),'transport_sha256':hashlib.sha256(packed).hexdigest()}
    a.out.with_suffix('.json').write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps(metadata))
if __name__=='__main__':main()
