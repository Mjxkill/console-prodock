#!/usr/bin/env python3
"""Transport patch round trips, immutability, and malformed-record rejection."""
import hashlib,random,struct,subprocess,sys,tempfile,uuid,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from build_delta import compress,delta
helper=Path(__file__).parents[1]/'build/runtime-helper-host'
with tempfile.TemporaryDirectory() as folder:
    p=Path(folder);rng=random.Random(31);old=rng.randbytes(32768)+b'ABCD'*32768+rng.randbytes(16384)
    base=p/'base';base.write_bytes(old)
    cases=[old,old[:512]+b'new instructions'*111+old[900:],old[1234:]+old[:1234],rng.randbytes(8192)]
    for i,new in enumerate(cases):
        raw=delta(old,new);packed=p/'delta.lz4';packed.write_bytes(compress(raw))
        out=Path('/tmp/luma3d-delta-test-'+uuid.uuid4().hex)
        args=[str(helper),'patch',str(packed),str(out),str(len(raw)),'%08x'%zlib.crc32(raw),str(base)]
        try:
            subprocess.run(args,check=True,capture_output=True);assert out.read_bytes()==new and base.read_bytes()==old
            assert subprocess.run(args,capture_output=True).returncode and out.read_bytes()==new
            out.unlink()
            corrupt=bytearray(old);corrupt[0]^=1;base.write_bytes(corrupt)
            assert subprocess.run(args,capture_output=True).returncode and not out.exists();base.write_bytes(old)
        finally:
            if out.exists():out.unlink()
    header=struct.pack('<6I',0x3150334c,len(old),zlib.crc32(old),64,zlib.crc32(old[:64]),1)
    malformed=[header+struct.pack('<2I',len(old)+1,64),header+struct.pack('<2I',len(old)-1,64),
               header+struct.pack('<2I',0,65),header+struct.pack('<2I',0,0),header+struct.pack('<2I',0,63),
               header+struct.pack('<2I',0xffffffff,64)+b'x',header+struct.pack('<2I',0,64)+b'trailing',header[:20]]
    for raw in malformed:
        packed=p/'bad.lz4';packed.write_bytes(compress(raw));out=Path('/tmp/luma3d-delta-test-'+uuid.uuid4().hex)
        result=subprocess.run([str(helper),'patch',str(packed),str(out),str(len(raw)),'%08x'%zlib.crc32(raw),str(base)],capture_output=True)
        assert result.returncode and not out.exists(),raw.hex()
print('Delta PASS: 4 round trips, base/overwrite protection, 8 malformed records rejected before output')
