#!/usr/bin/env python3
"""Inventory every nonconstant direct CE net feeding GPU/observer primitives.

This is a netlist/constraint audit, not an assertion about Gowin's undocumented
automatic-promotion threshold. Every CE net is retained; >=32 CE pins is only
the display threshold. Current and previously global GPU nets are also retained.
No compilation, hardware access, common source or constraint change.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from build_local_controls import cells
from build_timing_placement import HERE, ROOT, SHA_NET, sha, initial_values
from gowin_toolchain import PRIMITIVES

BUILD = ROOT / 'tang/impl/console_neo_n56r3'
OUT = HERE / 'n56r5_control_inventory'
PREFIXES = ('u_accel/', 'u_gpu/', 'u_gpu_debug/')
OUTPUTS = {'Q', 'F', 'O', 'OF'}
CE = re.compile(r'(?:CE(?:[AB]|\d+)?|OCE(?:[AB]|\d+)?|ADCE)\Z')
CLOCK = re.compile(r'(?:CLK\w*|\w*CLK|\w*CLOCK\w*)\Z')


def pin_base(pin):
    return pin.split('[', 1)[0]


def bit_expander(text):
    widths = {}
    for hi, lo, name in re.findall(r'^wire (?:\[(\d+):(\d+)\]\s*)?(\\\S+|\w+)\s*;', text, re.M):
        widths[name.removeprefix('\\')] = (int(hi), int(lo)) if hi else None

    def expand(expression):
        expression = re.sub(r'\s+', '', expression).replace('\\', '')
        if not expression:
            return []
        if expression.startswith('{'):
            if not expression.endswith('}') or '{' in expression[1:] or '}' in expression[:-1]:
                raise ValueError('Unsupported nested connection: ' + expression)
            return [b for atom in expression[1:-1].split(',') for b in expand(atom)]
        if expression in widths:
            span = widths[expression]
            return [expression] if span is None else [f'{expression}[{i}]' for i in range(span[0], span[1]-1, -1)]
        m = re.fullmatch(r'(.+)\[(\d+):(\d+)\]', expression)
        if m:
            return [f'{m[1]}[{i}]' for i in range(int(m[2]), int(m[3])-1, -1)]
        if re.fullmatch(r'[A-Za-z_][\w/.$\[\]-]*', expression):
            return [expression]
        raise ValueError('Unsupported net expression: ' + expression)

    return expand


def primitive_directions():
    directions = {}
    for m in re.finditer(r'^module (\w+)\b.*?^endmodule', PRIMITIVES.read_text(), re.M|re.S):
        body = re.sub(r'/\*.*?\*/|//[^\n]*', '', m[0], flags=re.S)
        pins = {}
        for direction, names in re.findall(r'\b(input|output|inout)\s+([^;]+);', body):
            names = re.sub(r'\[[^]]+\]', '', names)
            names = re.sub(r'\b(reg|wire|signed|unsigned)\b', '', names)
            pins.update({name.strip(): direction for name in names.split(',')})
        directions[m[1]] = pins
    return directions


def global_nets(build):
    path = build / 'impl/pnr/console_neo.rpt.txt'
    section = re.search(r'\n6\. Global Clock Signals\n(.*?)\n7\. Pinout by Port Name\n', path.read_text(), re.S)
    if not section:
        raise ValueError('Missing complete global-resource table: ' + str(build))
    return {net.strip(): kind for net, kind in
            re.findall(r'^\s*(\S+)\s*\|\s*(PRIMARY|LW|HCLK)\s*\|', section[1], re.M)}


def main():
    if sha(BUILD / 'console_neo.vg') != SHA_NET:
        raise ValueError('Unexpected netlist')
    routed = BUILD / 'impl/pnr/console_neo.vo'
    text = routed.read_text()
    cc, inits = cells(text), initial_values(text)
    expand, directions = bit_expander(text), primitive_directions()
    loads, drivers = defaultdict(list), defaultdict(list)
    ce_nets = set()
    for name, cell in cc.items():
        if name.startswith(PREFIXES) and cell['kind'] not in directions:
            raise ValueError('Unknown GPU primitive direction: ' + cell['kind'])
        for port, expression in cell['pins'].items():
            bits = expand(expression)
            vector = len(bits) > 1 or expression.startswith('{')
            direction = directions.get(cell['kind'], {}).get(port)
            output = direction == 'output' if direction else port in OUTPUTS
            for index, net in enumerate(bits):
                pin = f'{port}[{len(bits)-1-index}]' if vector else port
                entry = dict(instance=name, primitive=cell['kind'], pin=pin)
                if output:
                    drivers[net].append(entry)
                else:
                    loads[net].append(entry)
                    if name.startswith(PREFIXES) and CE.fullmatch(port) and net not in ('VCC', 'GND'):
                        ce_nets.add(net)
    builds = {name: ROOT / 'tang/impl' / name for name in
              ('console_neo_n56_observe', 'console_neo_n56r1', 'console_neo_n56r3', 'console_neo_n56r4')}
    history = {name: global_nets(build) for name, build in builds.items()}
    cst = (BUILD / 'source/tang/boards/neo/neo.cst').read_text()
    constraints = dict(re.findall(r'^CLOCK_LOC\s+"([^"]+)"\s+(\w+)\s*;', cst, re.M))
    historical = set().union(*(set(table) for table in history.values()))
    historical = {net for net in historical if
                  any(x['instance'].startswith(PREFIXES) for x in loads[net] + drivers[net])}
    all_nets = ce_nets | historical
    entries = []
    for net in sorted(all_nets):
        direct = loads[net]
        ce_loads = [x for x in direct if CE.fullmatch(pin_base(x['pin']))]
        clocks = [x for x in direct if CLOCK.fullmatch(pin_base(x['pin']))]
        dd = []
        for d in drivers[net]:
            name = d['instance']
            dd.append(dict(instance=name, primitive=cc[name]['kind'], pins=cc[name]['pins'], init=inits.get(name)))
        high = len(ce_loads) >= 32
        scalar = bool(re.fullmatch(r'[\w/.$\[\]-]+', net))
        entries.append(dict(net=net, ce_pins=len(ce_loads), all_pins=len(direct),
            display_high_fanout=high, clock_pins=clocks, driver=dd,
            load_pin_counts=dict(Counter(x['pin'] for x in direct)),
            ce_hierarchy_counts=dict(Counter('/'.join(x['instance'].split('/')[:-1]) for x in ce_loads)),
            all_loads=direct, existing_constraint=constraints.get(net),
            route_history={name: table.get(net, 'not_in_global_table') for name, table in history.items()},
            eligible_control_candidate=bool(scalar and len(dd) == 1 and not clocks and net not in ('VCC', 'GND')),
            unprotected_control=bool(scalar and len(dd) == 1 and not clocks and constraints.get(net) != 'LOCAL_CLOCK')))
    entries.sort(key=lambda e: (-e['ce_pins'], e['net']))
    shown = [e for e in entries if e['display_high_fanout'] or e['net'] in historical]
    unprotected = [e for e in shown if e['unprotected_control']]
    paths = [routed, BUILD/'console_neo.vg', BUILD/'source/tang/boards/neo/neo.cst', Path(__file__), PRIMITIVES]
    paths += [build/'impl/pnr/console_neo.rpt.txt' for build in builds.values()]
    result = dict(scope=__doc__, all_nonconstant_gpu_ce_nets=len(ce_nets),
        display_ce_threshold=32, retained_nets=len(entries), displayed_nets=len(shown),
        unprotected_displayed_controls=len(unprotected), entries=entries,
        sha256={str(p):sha(p) for p in paths}, hardware_access=False, compilation=False,
        limitations=[
            'The >=32 threshold is an audit display threshold, not a documented automatic LW promotion rule.',
            'Scalar and concatenated/vector CE/OCE/ADCE bits counted, including DSP and memory primitives; combinational descendants are not direct CE fanout.',
            'Historical global nets with GPU loads/drivers are included even if their direct CE count is zero.',
            'Eligibility means one scalar driver and no direct clock pins; it does not prove a need for LOCAL_CLOCK.',
            'A LOCAL_CLOCK constraint is not proof that the final router obeyed it: inspect the global table.',
            'Other high-fanout control pins such as reset/clear are not classified as CE pins.'])
    (OUT/'inventory.json').write_text(json.dumps(result,indent=2)+'\n')
    lines = ['# GPU/observateur : inventaire des contrôles CE', '',
        f'{len(ce_nets)} nets CE non constants inventoriés sans seuil ; affichage ci-dessous à partir de 32 charges CE, plus tous les nets GPU/observateur déjà globaux.', '',
        'Le seuil de 32 est un choix de présentation, pas un seuil Gowin établi. Les horloges sont explicitement exclues des propositions de contrôles locaux.', '',
        '| Net | CE directs | Autres pins | Contrainte R3 | Global R3 | Global R4 | Proposition admissible |',
        '| --- | ---: | ---: | --- | --- | --- | --- |']
    for e in shown:
        lines.append(f"| `{e['net']}` | {e['ce_pins']} | {e['all_pins']-e['ce_pins']} | {e['existing_constraint'] or 'aucune'} | {e['route_history']['console_neo_n56r3']} | {e['route_history']['console_neo_n56r4']} | {'contrôle à revoir' if e['unprotected_control'] else 'déjà local' if e['existing_constraint']=='LOCAL_CLOCK' else 'horloge / hors portée'} |")
    lines += ['', 'Les drivers, INIT, connexions et listes intégrales de charges sont conservés dans `inventory.json`. Aucun fichier CST ni aucune option de compilation ne sont modifiés par cet inventaire.', '']
    (OUT/'inventory.md').write_text('\n'.join(lines))
    print(json.dumps({k:result[k] for k in ('all_nonconstant_gpu_ce_nets','retained_nets','displayed_nets','unprotected_displayed_controls')},indent=2))
    for e in unprotected[:35]:
        print(e['ce_pins'],e['all_pins'],e['net'])


if __name__ == '__main__':
    main()
