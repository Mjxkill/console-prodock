#!/usr/bin/env python3
"""Inspect the exact N56r8 command echo cone; no synthesis or hardware access."""
from itertools import product
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'TESTS/neo_720p_20261012/n55_gpu_diagnosis_20261021'))
from audit_geometry_controls import indexed_netlist

BUILD = ROOT/'tang/impl/console_neo_n56r8_hdmi_sg4'
PREFIX = 'u_usb_idle_trace/'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    vo = BUILD/'impl/pnr/console_neo.vo'
    assert sha(vo) == '33c919d5c8ab6e90ec6b68f44849ff9d6f2c5682a40192d12c55298494afccc9'
    cc, pp, drivers, loads = indexed_netlist(vo)
    selected, terminal, proven = set(), set(), []

    def evaluate(net, known, memo):
        if net in known: return {known[net]}
        if net in ('VCC', 'GND'): return {int(net == 'VCC')}
        if net in memo: return memo[net]
        assert len(drivers[net]) == 1, (net, drivers[net])
        name, kind, pin = drivers[net][0]
        selected.add(name)
        if kind.startswith('LUT'):
            width = int(kind[3:]); assert pin == 'F'
            init = int(pp[name]['INIT'].split("'h")[1], 16)
            inputs = [evaluate(cc[name]['pins'][f'I{i}'], known, memo) for i in range(width)]
            result = {(init >> sum(v << i for i, v in enumerate(values))) & 1
                      for values in product(*inputs)}
        elif kind.startswith('MUX2'):
            pins = cc[name]['pins']
            choose = evaluate(pins['S0'], known, memo)
            result = set().union(*(evaluate(pins['I'+str(i)], known, memo) for i in choose))
        else:
            terminal.add(net)
            result = {0, 1}
        memo[net] = result
        return result

    for bit, output in ((0, 'n181_37'), (2, 'n179_37')):
        for value in (0, 1):
            known = {PREFIX+f'send_index[{i}]': (2 >> i)&1 for i in range(5)}
            known[PREFIX+f'snapshot[{64+bit}]'] = value
            actual = evaluate(PREFIX+output, known, {})
            assert actual == {value}, (bit, value, actual)
            proven.append(dict(send_index=2, snapshot_bit=64+bit, snapshot_value=value,
                               reply_ram_DI_bit=bit, possible_output_values=sorted(actual),
                               all_other_sequential_terminal_values='unconstrained'))

    for name in ('snapshot_64_s0','snapshot_66_s0','n1170_s0','n5310_s1','armed_s1',
                 'u_commands/head_0_s0','u_commands/head_2_s0',
                 'u_replies/g_inferred_storage.mem_g_inferred_storage.mem_0_0_s',
                 'bank_bank_0_0_s','bank_bank_1_0_s'):
        selected.add(PREFIX+name)
    # Preserve the exact RESET/CE drivers rather than merely their names.
    for name in ('snapshot_64_s0','snapshot_66_s0','armed_s1'):
        for pin in ('RESET','CE','D'):
            net = cc[PREFIX+name]['pins'][pin]
            if net not in ('VCC','GND'):
                selected.update(n for n, _, _ in drivers[net])
    a, b = cc[PREFIX+'snapshot_64_s0'], cc[PREFIX+'snapshot_66_s0']
    assert a['kind'] == b['kind'] == 'DFFRE'
    assert all(a['pins'][p] == b['pins'][p] for p in ('CLK','CE','RESET'))
    assert a['pins']['D'] == PREFIX+'command[0]' and b['pins']['D'] == PREFIX+'command[2]'
    assert pp[PREFIX+'snapshot_64_s0'] == pp[PREFIX+'snapshot_66_s0'] == dict(INIT="1'b0")
    paths = {}
    for net in (PREFIX+'command[0]',PREFIX+'command[2]',PREFIX+'snapshot[64]',
                PREFIX+'snapshot[66]',PREFIX+'n181_37',PREFIX+'n179_37',
                PREFIX+'reply[0]',PREFIX+'reply[2]'):
        paths[net] = dict(drivers=drivers[net], loads=loads[net])
    # Record exact named interconnect delays only. These are not slack or
    # a sensitized path sum; both transitions and min/typ/max are retained.
    sdf = BUILD/'impl/pnr/console_neo.sdf'
    routes = []
    with sdf.open() as source:
        for line_number, line in enumerate(source, 1):
            clean = re.sub(r'\\(.)', r'\1', line.strip())
            m = re.fullmatch(r'\(INTERCONNECT (\S+) (\S+) (.+)\)', clean)
            if m and m[1].rsplit('/', 1)[0] in selected and m[2].rsplit('/', 1)[0] in selected:
                delays = [[float(x) for x in part.split(':')] for part in re.findall(r'\(([-\d.:]+)\)', m[3])]
                assert len(delays) in (1, 2) and all(len(d) == 3 for d in delays)
                routes.append(dict(source=m[1], destination=m[2], line=line_number,
                                   rise_ns=delays[0], fall_ns=delays[-1]))
    result = dict(passed=True, hardware_access=False, synthesis=False, timing_qualification=False,
        bitstream_sha256=sha(BUILD/'impl/pnr/console_neo.fs'),
        source_sha256={str(p):sha(p) for p in (Path(__file__),vo,sdf,
            BUILD/'source/tang/rtl/usb/usb_idle_trace.v', BUILD/'source/tang/rtl/board/ddr_dcfifo.v')},
        combinational_mux_proof=proven, selected_primitives={n:dict(cell=cc[n], parameters=pp.get(n,{})) for n in sorted(selected)},
        boundary_connections=paths, selected_interconnects=routes,
        limitations=['Zero-delay LUT logic only; hardware timing, RAM contents and dynamic register state not measured.',
            'A successful mux proof does not prove that snapshot[64] was captured as one on hardware.',
            'RAM primitive interfaces are recorded; no unsupported RAM behavior is assumed.'])
    destination = HERE/'command_echo_cone.json'
    with destination.open('x') as out: json.dump(result, out, indent=2); out.write('\n')
    print(json.dumps(dict(passed=True, selected_primitives=len(selected), interconnects=len(routes),
                         mux_cases=len(proven), output_sha256=sha(destination))))


if __name__ == '__main__': main()
