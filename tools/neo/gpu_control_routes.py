"""Catalog wide GPU controls from a frozen Gowin netlist for a routing A/B.

Only locally driven CE/reset nets are constrained. Clocks, pins, DDR and USB
are untouched. This is a physical experiment, not a waiver of timing checks.
"""
import hashlib
import re
from collections import Counter
from pathlib import Path


def catalog(text, threshold=64):
    modules = dict(re.findall(r'^module (\w+)\b(.*?)^endmodule', text, re.M | re.S))
    if 'console_neo' not in modules:
        raise ValueError('Missing console_neo netlist')
    cache = {}

    def cells(module):
        if module not in cache:
            cache[module] = [(kind, name, dict(re.findall(r'\.(\w+)\(([^()]*)\)', body)))
                for kind, name, body in re.findall(
                    r'^\s*(\w+)\s+(\\\S+\s|\S+)\s*\((.*?)\);', modules[module], re.M | re.S)]
        return cache[module]

    def canonical(name):
        name = name.strip().removeprefix('\\')
        if not re.fullmatch(r'[A-Za-z0-9_$/\.\[\]-]+', name):
            raise ValueError('Unsupported control net name '+repr(name))
        return name

    entries = []
    skipped = []

    def visit(module, hierarchy, stack):
        if module in stack:
            raise ValueError('Recursive netlist module')
        local = cells(module)
        clocks = set()
        loads = Counter()
        enable_loads = Counter()
        drivers = {}
        for kind, cell, ports in local:
            clocks.update(net for port, net in ports.items()
                          if port.upper() in ('CLK','CLKA','CLKB','CLKIN','WCLK','RCLK'))
            if kind in modules:
                continue
            if kind.startswith(('DFF','MULT','SDP','DPB','SP')):
                loads.update(net for port, net in ports.items()
                             if port in ('CE','CEA','CEB','RESET','CLEAR','PRESET','SET'))
                enable_loads.update(net for port, net in ports.items() if port in ('CE','CEA','CEB'))
            for port in ('F','Q','O'):
                if port in ports:
                    drivers.setdefault(ports[port], []).append((kind, cell, port))
        for net, count in loads.items():
            if count < threshold or net in ('GND','VCC') or net in clocks:
                continue
            found = drivers.get(net, [])
            if not found:
                # Parent-owned resets are already constrained in the frozen
                # profile. Do not guess an alias for a module input here.
                skipped.append(dict(module=module, hierarchy=hierarchy,
                                    net=net.strip(), loads=count))
                continue
            if len(found) != 1:
                raise ValueError('Ambiguous control driver '+hierarchy+'/'+net)
            kind, cell, port = found[0]
            alias = None
            if kind == 'INV' and not enable_loads[net]:
                # Gowin folds reset polarity into the receiving FF. A CST
                # on this inverter output can alias an existing reset CST.
                # Constrain a local source FF once; parent-owned sources
                # remain covered by the existing reset-tree constraints.
                source = next(p['I'] for k,c,p in local if k==kind and c==cell)
                parent = drivers.get(source, [])
                if not parent:
                    skipped.append(dict(module=module,hierarchy=hierarchy,
                                        net=source.strip(),loads=count,inverted_reset=net.strip()))
                    continue
                if len(parent)!=1 or source in clocks:
                    raise ValueError('Ambiguous/clock reset alias '+hierarchy+'/'+net)
                alias=canonical(net);net=source;kind,cell,port=parent[0]
            entries.append(dict(net=hierarchy+'/'+canonical(net), module=module,
                                loads=count, driver=canonical(cell), primitive=kind, port=port,
                                inverted_reset_alias=alias))
        for kind, cell, ports in local:
            if kind in modules:
                visit(kind, hierarchy+'/'+canonical(cell), stack+(module,))

    roots = {name.strip(): kind for kind, name, ports in cells('console_neo')
             if name.strip() in ('u_accel','u_gpu')}
    if roots != {'u_accel':'gpu_accel','u_gpu':'gpu_scanout'}:
        raise ValueError('Unexpected GPU hierarchy')
    for name, module in roots.items():
        visit(module, name, ())
    if not entries:
        raise ValueError('No wide GPU controls found')
    return dict(netlist_sha256=hashlib.sha256(text.encode()).hexdigest(),
                threshold=threshold, entries=sorted(entries,key=lambda e:e['net']),
                parent_owned=sorted(skipped,key=lambda e:(e['hierarchy'],e['net'])))


def constrain(cst, netlist):
    record = catalog(netlist)
    lines = []
    for entry in record['entries']:
        net = entry['net']
        prior = re.findall(r'CLOCK_LOC\s+"'+re.escape(net)+r'"\s+([^;]+);', cst)
        if prior and prior != ['LOCAL_CLOCK']:
            raise ValueError('Conflicting control constraint '+net)
        if not prior:
            lines.append(f'CLOCK_LOC "{net}" LOCAL_CLOCK;')
    return cst+'\n// Frozen-netlist experiment: wide GPU controls on local wiring.\n'+'\n'.join(lines)+'\n', record


def audit(netlist, resource_report, record):
    nettext=Path(netlist).read_text()
    current = catalog(nettext)
    errors = []
    if current != record:
        errors.append('Wide-control catalog differs from the frozen netlist')
    text = Path(resource_report).read_text()
    table = re.search(r'^\s*6\. Global Clock Signals\s*$(.*?)^\s*7\. ', text, re.M | re.S)
    routes = {}
    if not table:
        errors.append('Missing global routing table')
    else:
        requested = {e['net'] for e in record['entries']}
        # Gowin may expose an internal GPU control as a top-level alias,
        # e.g. v1_pending or gpu_debug_state[48], losing the u_accel prefix.
        modules=dict(re.findall(r'^module (\w+)\b(.*?)^endmodule',nettext,re.M|re.S))
        aliases=set()
        for module,instance in (('gpu_accel','u_accel'),('gpu_scanout','u_gpu')):
            outputs=re.findall(r'^output\s+(?:\[[^\]]+\]\s+)?(\w+)\s*;',modules[module],re.M)
            body=re.findall(r'^\s*'+module+' '+instance+r'\s*\((.*?)\);',modules['console_neo'],re.M|re.S)
            if len(body)!=1:
                errors.append('Missing GPU output aliases '+instance)
                continue
            ports=dict(re.findall(r'\.(\w+)\(([^()]*)\)',body[0]))
            for output in outputs:
                net=ports.get(output,'').strip().removeprefix('\\')
                if net:
                    vector=re.fullmatch(r'([\w.$/]+)\[(\d+):(\d+)\]',net)
                    if vector:
                        high,low=int(vector[2]),int(vector[3])
                        if not 0<=high-low<1024:raise ValueError('Unsupported GPU output range')
                        aliases.update(f'{vector[1]}[{i}]' for i in range(low,high+1))
                    else:aliases.add(net)
        for line in table[1].splitlines():
            fields = [v.strip() for v in line.split('|')]
            if len(fields) >= 2 and (fields[0] in requested or fields[0] in aliases or fields[0].startswith(('u_accel/','u_gpu/'))):
                routes[fields[0]] = fields[1]
                if fields[1] == 'LW':
                    errors.append(fields[0]+' still uses LW')
    return dict(passed=not errors,errors=errors,controls=len(record['entries']),
                global_routes=routes,netlist_sha256=current['netlist_sha256'])
