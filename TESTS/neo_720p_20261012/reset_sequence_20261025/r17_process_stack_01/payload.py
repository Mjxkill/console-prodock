"""GDB read-only payload: candidate X8 search frames, no inferior calls/writes."""
import gdb
import json
from pathlib import Path

inf=gdb.selected_inferior()
regions=[]
library=Path('/home/michael/gowin/IDE/lib/libgowin.so').resolve()
for line in Path('/proc/%d/maps'%inf.pid).read_text().splitlines():
    fields=line.split(maxsplit=5)
    lo,hi=[int(x,16) for x in fields[0].split('-')]
    regions.append((lo,hi,fields[1],int(fields[2],16),fields[5] if len(fields)>5 else ''))
bases={lo for lo,hi,perms,offset,path in regions
       if offset==0 and path.startswith('/') and Path(path).resolve()==library}
assert len(bases)==1,'Unexpected library mapping'
base=bases.pop()

def read(addr,n):
    assert 0<=n<=8192
    assert any(lo<=addr and addr+n<=hi and 'r' in perms for lo,hi,perms,off,path in regions)
    return bytes(inf.read_memory(addr,n))

def integer(addr,n=8,signed=False):return int.from_bytes(read(addr,n),'little',signed=signed)
def sym(addr):return gdb.execute('info symbol 0x%x'%addr,to_string=True).strip()

rsp=int(gdb.parse_and_eval('$rsp'));pc=int(gdb.parse_and_eval('$pc'))
top=next(hi for lo,hi,perms,off,path in regions if lo<=rsp<hi)
raw=read(rsp,min(8192,top-rsp))
r=dict(pc=hex(pc),symbol=sym(pc),rsp=hex(rsp),library_base=hex(base),
       candidates=[],x8_words=[],caveat='Stack words may be stale; only checked candidates are interpreted.')
for offset in range(0,len(raw)-7,8):
    value=int.from_bytes(raw[offset:offset+8],'little')
    slot=rsp+offset
    if base+0x1d8c110<=value<base+0x1d8f200:
        r['x8_words'].append(dict(slot=hex(slot),value=hex(value),symbol=sym(value)))
    if value-base not in (0x1d8c2b3,0x1d8c310):continue
    frame=slot+0xb8
    c=dict(slot=hex(slot),frame=hex(frame),return_address=hex(value),checked=False)
    try:
        assert rsp<=frame-0xb0<frame+24<=top
        assert read(value-5,1)==b'\xe8'
        node=integer(frame-0xb0)
        c.update(net_index=integer(frame-0xa4,4),node_net_index=integer(node+0x10,4),
            node=hex(node),row=integer(node+0x14,2),col=integer(node+0x16,2),
            iteration=integer(slot-24,4),limit=integer(frame-0x8c,4,signed=True),
            parent_return=hex(integer(frame+8)),parent_symbol=sym(integer(frame+8)))
        assert c['net_index']==c['node_net_index']
        assert 0<=c['iteration']<c['limit']<=1000000
        assert integer(frame-0x98)==frame-0x50
        assert integer(frame-0x88)==frame-0x78
        c['vectors']={}
        for name,address in [('source',integer(frame-0xa0)),('work',frame-0x70),('destination',frame-0x50)]:
            begin,end,cap=[integer(address+i*8) for i in range(3)]
            assert begin<=end<=cap and (end-begin)%8==0 and cap-begin<=8*1048576
            c['vectors'][name]=dict(count=(end-begin)//8,begin=hex(begin),end=hex(end))
        c['checked']=True
    except Exception as error:c['error']=repr(error)
    r['candidates'].append(c)
print('R17_STACK_JSON='+json.dumps(r,sort_keys=True))
