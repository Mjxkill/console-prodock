"""Bounded GDB memory reads; no inferior calls, writes or breakpoints.

Offsets apply only to the libgowin.so SHA checked by inspect_r17_progress.py.
Frame sizes and saved registers were read from its x86-64 disassembly.
The list is a work list, NOT a final count of unrouted nets.
"""
import gdb
import json
from pathlib import Path

inf = gdb.selected_inferior()
library = Path('/home/michael/gowin/IDE/lib/libgowin.so').resolve()
regions = []
for line in Path('/proc/%d/maps' % inf.pid).read_text().splitlines():
    f = line.split(maxsplit=5)
    lo, hi = (int(x, 16) for x in f[0].split('-'))
    regions.append((lo, hi, f[1], int(f[2], 16), f[5] if len(f) > 5 else ''))
bases = {lo for lo, hi, perms, off, path in regions
         if off == 0 and path.startswith('/') and Path(path).resolve() == library}
assert len(bases) == 1
base = bases.pop()
total = 0


def read(addr, n):
    global total
    assert 0 <= n <= 8192 and total + n <= 65536
    assert any(lo <= addr and addr+n <= hi and 'r' in perms
               for lo, hi, perms, off, path in regions), 'Unmapped read'
    total += n
    return bytes(inf.read_memory(addr, n))


def integer(addr, n=8):
    return int.from_bytes(read(addr, n), 'little')


def node(addr):
    assert addr and addr % 8 == 0
    return dict(address=hex(addr), net_index=integer(addr+0x10, 4),
                row=integer(addr+0x14, 2), col=integer(addr+0x16, 2))


def vector(addr):
    begin, end, cap = [integer(addr+8*i) for i in range(3)]
    assert begin <= end <= cap and (cap-begin) % 8 == 0
    assert cap-begin <= 8*1048576
    count = (end-begin)//8
    return dict(address=hex(addr), count=count,
                first=[node(integer(begin+8*i)) for i in range(min(count, 32))],
                truncated=count > 32)


rsp = int(gdb.parse_and_eval('$rsp'))
pc = int(gdb.parse_and_eval('$pc'))
top = next(hi for lo, hi, perms, off, path in regions if lo <= rsp < hi)
raw = read(rsp, min(8192, top-rsp))
r = dict(pc=hex(pc), symbol=gdb.execute('info symbol 0x%x' % pc, to_string=True).strip(),
         rsp=hex(rsp), library_base=hex(base), candidates=[],
         caveat='Checked frame layouts; work-list size is not an unrouted-net count; two samples do not prove convergence.')
for offset in range(0, len(raw)-7, 8):
    if int.from_bytes(raw[offset:offset+8], 'little') != base+0x1d8e6ba:
        continue
    f = rsp+offset  # routeAdjustment return after adjustByFreeSearch
    c = dict(frame=hex(f), checked=False)
    try:
        assert rsp <= f-0x130 and f+0xc0 <= top
        assert integer(f+0xb0) == base+0x1d8e8bf  # routeAdjustment -> autoAdjustment
        assert read(base+0x1d8e6b5, 5) == bytes.fromhex('e836ec67fe')
        assert read(base+0x1d8e8ba, 1) == b'\xe8'
        head = f+0x28
        assert integer(f-24) == head  # saved r13 from routeAdjustment
        budget = integer(f+0x14, 4)
        processed = integer(f-0xf8, 4)
        assert 0 <= processed <= budget <= 1000000
        assert integer(f-0xf4, 4) == budget
        info = integer(f-16)  # saved r14 (this)
        g = f-0x100  # adjustByFreeSearch -> its current child
        branch = integer(g)-base
        if branch == 0x1d8e221:  # conOneTypeDes pushes r15,r14,r13,r12,rbp,rbx
            target = integer(g-40)
            current = integer(g-48)
            assert integer(g-16) == head
            assert integer(g-32) == info
        elif branch == 0x1d8e38e:  # adjustIsolatedNode pushes rbp,r15,r14,r13,r12,rbx
            target = integer(g-8)
            current = integer(g-48)
            assert integer(g-24) == head
            assert integer(g-40) == info
            assert integer(g-0x90) == target  # local copy of input node
        else:
            raise AssertionError('Unsupported child return '+hex(branch))
        count = integer(head+16)
        assert 0 <= count <= 1048576
        cur = integer(head)
        prev = head
        seen = set()
        entries = []
        for i in range(min(count, 64)):
            assert cur not in seen and cur != head
            seen.add(cur)
            assert integer(cur+8) == prev
            entries.append(dict(link=hex(cur), node=node(integer(cur+16))))
            prev, cur = cur, integer(cur)
        if count <= 64:
            assert cur == head and integer(head+8) == prev
            assert current in seen
        net_count = integer(info+0x20, 4)
        target_data = node(target)
        assert target_data['net_index'] < net_count <= 10485760
        c.update(checked=True, branch_return=hex(branch), processed=processed,
                 budget=budget, work_list_count=count, work_list=entries,
                 list_truncated=count > 64, current_link=hex(current),
                 original=node(integer(current+16)), target=target_data,
                 source_vector=vector(integer(f-8)), net_table_count=net_count)
    except Exception as error:
        c['error'] = repr(error)
    r['candidates'].append(c)
r['bytes_read'] = total
print('R17_PROGRESS_JSON='+json.dumps(r, sort_keys=True))
