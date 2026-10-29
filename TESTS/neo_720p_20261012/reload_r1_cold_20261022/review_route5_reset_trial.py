#!/usr/bin/env python3
"""Review exact R5 for a stopped-CPU reset/RGB diagnostic, not qualification.

Retain the failed STA and strict observer reports. Additional global control
routes are accounted for explicitly, including all their driver/load cells.
No source or routing transformation and no hardware access.
"""
from collections import Counter
import json
from pathlib import Path

from route_observed_scan_reset import ROOT, HERE, NETSHA, SDC, sha
from audit_geometry_controls import indexed_netlist
from audit_gpu_control_inventory import global_nets, CLOCK, pin_base
import prove_route2_observer_reset_alias as alias
from reports import parse_timing

PARENT = ROOT / 'tang/impl/console_neo_n56r9_route2'
BUILD = ROOT / 'tang/impl/console_neo_n56r9_route5_c155'
BIT = 'b85a1a41e22e1b9a0b24be45a5c18cdce9d84a996305238c4ceb933415a854ea'
ADDED = {'v1_pending': 8, 'u_accel/u_v1/u_pixels/n37565_3': 256,
         'u_accel/u_v1/u_pixels/u_copy/n7630_6': 256}
REMOVED = {'scan_debug_live_178[1]', 'u_accel/u_v1/n60439_3', 'u_accel/u_v1/n59467_5'}


def main():
    q = json.loads((BUILD / 'qualification.json').read_text())
    assert q['status'] == 'FAIL' and q['bitstream_sha256'] == BIT
    assert sha(BUILD / 'impl/pnr/console_neo.fs') == BIT
    assert q['timing_checks_ns'] == dict(setup=-5.840, hold=.124, recovery=.310, removal=.095)
    assert all(a['passed'] for a in q['synthesis_audits'].values())
    assert sha(BUILD / 'console_neo.vg') == sha(PARENT / 'console_neo.vg') == NETSHA
    assert sha(BUILD / 'source/tang/boards/neo/neo.sdc') == SDC
    old = json.loads((PARENT / 'sources.json').read_text())
    new = json.loads((BUILD / 'sources.json').read_text())
    assert new == {str(p.relative_to(BUILD / 'source')): sha(p)
                   for p in (BUILD / 'source').rglob('*') if p.is_file()}
    assert old.keys() == new.keys()
    assert sorted(k for k in old if old[k] != new[k]) == [
        'tang/boards/neo/neo.cst', 'tang/boards/neo/timing_closure.json']
    pc, pp, pd, pl = indexed_netlist(PARENT / 'impl/pnr/console_neo.vo')
    cc, cp, cd, cl = indexed_netlist(BUILD / 'impl/pnr/console_neo.vo')
    pg, cg = global_nets(PARENT), global_nets(BUILD)
    assert {n for n, r in cg.items() if pg.get(n) != r} == set(ADDED)
    assert set(pg) - set(cg) == REMOVED
    records = []
    for net in sorted(set(ADDED) | REMOVED | {'scan_debug_live_178[0]'}):
        assert pd[net] == cd[net] and sorted(pl[net]) == sorted(cl[net]), net
        affected = {n for n, _, _ in cd[net] + cl[net]}
        assert all(pc[n] == cc[n] and pp.get(n) == cp.get(n) for n in affected), net
        assert not any(CLOCK.fullmatch(pin_base(pin)) for _, _, pin in cl[net]), net
        if net in ADDED:
            assert cg[net] == 'LW' and len(cl[net]) == ADDED[net]
        records.append(dict(net=net, before=pg.get(net, 'local'), after=cg.get(net, 'local'),
                            drivers=cd[net], loads=cl[net],
                            load_pins=dict(Counter(pin_base(p) for _, _, p in cl[net])),
                            cells_and_parameters_unchanged=True))
    assert 'scan_debug_live_178[1]' not in cg
    assert cg['gpu_clk'] == 'PRIMARY'
    assert len(cl['scan_debug_live_178[0]']) == 2 and len(cl['scan_debug_live_178[1]']) == 21

    # Reuse the strict Boolean proof with an explicit output binding. Its own
    # input hashes and original FAIL are retained; timing is not excused.
    alias.OUT = BUILD
    alias.main()
    timing = parse_timing((BUILD / 'impl/pnr/console_neo.tr').read_text())
    assert timing['complete'] and not timing['timing_clean']
    negative = [p for p in timing['paths'] if p['slack_ns'] < 0]
    observed = [p for p in negative if 'u_scan_observe/' in p['source'] + p['destination']]
    assert not observed, 'Observer has a reported failing timing endpoint'
    paths = [Path(__file__), Path(alias.__file__), BUILD / 'scan_observer_reset_alias_proof.json',
             BUILD / 'scan_observer_audit.json', BUILD / 'automatic_checks.json',
             BUILD / 'qualification.json', BUILD / 'sources.json', PARENT / 'sources.json']
    paths += [b / f for b in (PARENT, BUILD) for f in (
        'console_neo.vg', 'impl/pnr/console_neo.vo', 'impl/pnr/console_neo.rpt.txt',
        'impl/pnr/console_neo.tr', 'source/tang/boards/neo/neo.cst',
        'source/tang/boards/neo/neo.sdc', 'source/tang/boards/neo/timing_closure.json')]
    result = dict(passed=True, bitstream_sha256=BIT, hardware_access=False,
        qualification_status='FAIL', timing_checks_ns=q['timing_checks_ns'],
        scope='Structural review permitting only stopped-CPU reset/RGB observation',
        reset_stages_unchanged=True, global_route_changes=records,
        reported_negative_observer_paths=observed,
        reported_negative_paths=[{k: p[k] for k in ('analysis', 'slack_ns', 'source', 'destination')}
                                 for p in negative],
        sha256={str(p): sha(p) for p in paths},
        limits=['Same synthesized logic, different placement/routing; no isolation of a single physical cause.',
                'New LW routes feed pixel packet CEs and pending data logic, not clocks; no silicon guarantee.',
                'Global setup violations remain; no Linux/full GPU qualification or promotion.',
                'No reported observer violation does not establish complete point-to-point STA coverage.'])
    with (BUILD / 'scan_reset_route_comparison.json').open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(review_passed=True, qualification_status='FAIL',
                         bitstream_sha256=BIT, global_route_changes=len(records),
                         setup_violations=len(negative), hardware_access=False)))


if __name__ == '__main__':
    main()
