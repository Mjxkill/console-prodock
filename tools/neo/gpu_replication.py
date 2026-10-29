"""Check routed GPU-owner copies against the original register function.

The N50r2 post-PnR model loses both input inversions on automatic copies of
v1_select. This audit covers that specific owner, not all replicated logic.
It is mandatory even for a parked-CPU diagnostic; timing cannot waive it.
"""
import hashlib
from pathlib import Path
import re


def canonical(value):
    return re.sub(r'\s+', '', value).removeprefix('\\')


def audit(netlist):
    raw=Path(netlist).read_bytes()
    text=raw.decode()
    cells={canonical(name):(kind,{pin:canonical(value) for pin,value in
        re.findall(r'\.(\w+)\(([^()]*)\)',ports)})
        for kind,name,ports in re.findall(r'^(\w+)\s+(\\[^\s]+|\w+)\s*\(([^;]*?)\);',text,re.M|re.S)
        if kind!='module'}
    init={canonical(name):value.lower() for name,value in
        re.findall(r'^defparam\s+(\\[^\s]+|\w+)\s*\.INIT\s*=\s*([^;]+);',text,re.M)}
    aliases={}
    for name,(kind,ports) in cells.items():
        if kind in ('INV','BUF') and set(ports)=={'I','O'}:
            aliases[ports['O']]=(ports['I'],int(kind=='INV'))
        elif kind=='LUT1' and set(ports)=={'I0','F'} and init.get(name) in ("2'h1","2'h2"):
            aliases[ports['F']]=(ports['I0'],int(init[name]=="2'h1"))
    def resolved(net):
        seen=set();inverted=0
        while net in aliases:
            if net in seen:raise ValueError('Cyclic buffer/inverter chain')
            seen.add(net);net,polarity=aliases[net];inverted^=polarity
        return (net,inverted)
    original='u_accel/v1_select_s0'
    copies={name:cell for name,cell in cells.items()
        if re.fullmatch(r'u_accel/gowin_replicate_reg_v1_select_\d+',name)}
    errors=[];differences=[]
    if original not in cells or cells[original][0]!='DFFRE':
        errors.append('Original GPU owner register is missing or unsupported')
    else:
        kind,ports=cells[original]
        if set(ports)!={'D','CLK','CE','RESET','Q'} or init.get(original) not in ("1'b0","1'b1"):
            errors.append('Original GPU owner pins/initialization are incomplete')
        else:
            for name,(copy_kind,copy_ports) in copies.items():
                mismatch={}
                if copy_kind!=kind or set(copy_ports)!=set(ports):
                    mismatch['primitive']={'original':kind,'copy':copy_kind}
                for pin in ('D','CLK','CE','RESET'):
                    if pin not in copy_ports or resolved(copy_ports[pin])!=resolved(ports[pin]):
                        mismatch[pin]={'original':resolved(ports[pin]),'copy':resolved(copy_ports[pin]) if pin in copy_ports else None}
                if init.get(name)!=init[original]:
                    mismatch['INIT']={'original':init[original],'copy':init.get(name)}
                if mismatch:
                    differences.append({'instance':name,'differences':mismatch})
                    errors.append('Replicated GPU owner differs from original: '+name)
    return dict(passed=not errors,errors=errors,checked_copies=len(copies),
        differences=differences,total_replica_cells=sum('gowin_replicate_reg_' in name for name in cells),
        netlist_sha256=hashlib.sha256(raw).hexdigest(),
        scope='Post-PnR v1_select type, D, CLK, CE, RESET and INIT equivalence only; not a general netlist equivalence proof')
