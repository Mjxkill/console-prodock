#!/usr/bin/env python3
"""Offline insertion into the SHA-pinned R19 netlist; never invokes Gowin/P&R.

Every original primitive port/parameter is compared after transformation.
Only held-D/read-D diagnostic pins and new hierarchy ports may differ.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import patch_transport as pt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
import inspect_decision as inv


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def require_mapping(mapping):
    result = json.loads((mapping/'result.json').read_text())
    assert result['passed'] and not result['routing']
    for name, digest in result['inputs'].items():
        assert sha(HERE/name) == digest, ('mapping input changed', name)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    a = parser.parse_args()
    mapping, out = a.mapping.resolve(), a.out.resolve()
    assert mapping.parent == HERE and out.parent == HERE
    require_mapping(mapping)
    parent = inv.BUILD/'console_neo.vg'
    assert sha(parent) == inv.EXPECTED
    original = parent.read_text()
    assert 'rjc_' not in original
    names = set(re.findall(r'^module (\w+)', original, re.M))
    touched = {'gpu_copy565','gpu_v1','gpu_geometry','gpu_accel','console_neo',
               'neo_gpu_debug_0','neo_gpu_debug'}
    old = {n: inv.module(original, n) for n in touched}
    new = dict(old)
    allow = {n: {} for n in touched}

    new['gpu_copy565'] = pt.port(new['gpu_copy565'], [('output [303:0]', 'rjc_copy_taps')])
    new['gpu_copy565'] = pt.tail(new['gpu_copy565'],
        'assign rjc_copy_taps={n577_9,n4731_54,n7630_6,n5984_12,descriptor_bad,'
        'n2436_5,n2382_7,n2373_7,state_0,src_end,packet_0};')
    for n, instance in [('gpu_v1','u_copy'),('gpu_geometry','u_pixels'),('gpu_accel','u_v1')]:
        new[n] = pt.port(new[n], [('output [639:0]','rjc_record'),
                                 ('input','rjc_snapshot_request')])
        if n == 'gpu_v1':
            new[n] = pt.wires(new[n], 'wire [303:0] rjc_copy_taps;\nwire rjc_reset;')
            ports = [('rjc_copy_taps', 'rjc_copy_taps')]
        else:
            ports = [('rjc_record','rjc_record'),('rjc_snapshot_request','rjc_snapshot_request')]
        new[n] = pt.instance_ports(new[n], instance, ports)
        allow[n][instance] = dict(ports)
    parent_packet = '{packet[255:32],gpu_observe_packet_words[63:32]}'
    helper = f'''LUT1 rjc_reset_inv(.I0(trace_ready),.F(rjc_reset));
defparam rjc_reset_inv.INIT=2'h1;
neo_reject_witness rjc_observer(
 .clk(gpu_clk),.reset(rjc_reset),.arm_ack_toggle(trace_arm_ack),
 .snapshot_request(rjc_snapshot_request),
 .parent_reset(n1617_5),.child_reset(rjc_copy_taps[303]),
 .parent_capture(n37565_3),.copy_capture(rjc_copy_taps[301]),.check_ce(rjc_copy_taps[300]),
 .parent_packet({parent_packet}),.copy_packet(rjc_copy_taps[255:0]),
 .parent_state(state),.child_state(rjc_copy_taps[293:289]),
 .parent_bad_d(n22771_33),.parent_bad_q(state[1]),
 .child_bad_d(rjc_copy_taps[302]),.child_bad_q(copy_bad),.child_done(copy_done),
 .bad_header(bad_header),.target_valid(shader_target_valid),
 .descriptor_d(rjc_copy_taps[296:294]),.descriptor_q(rjc_copy_taps[299:297]),
 .target_base({{2'b00,color_base}}),.target_stride(color_stride),
 .target_width(width),.target_height(height),
 .src_end(rjc_copy_taps[288:256]),.dst_end(color_end),
 .live({{2'b00,rjc_copy_taps[303],n1617_5,copy_done,copy_bad,copy_valid,state[41],
 n6248_4,native_valid_13,native_write,native_valid}}),.record(rjc_record));'''
    new['gpu_v1'] = pt.tail(new['gpu_v1'], helper)
    new['console_neo'] = pt.wires(new['console_neo'],
        'wire [639:0] rjc_record;\nwire rjc_snapshot_request;')
    entries = {
        'u_accel': [('rjc_record','rjc_record'),('rjc_snapshot_request','rjc_snapshot_request')],
        'u_gpu_debug': [('rjc_payload','rjc_record[319:0]'),('rjc_snapshot_request','rjc_snapshot_request')],
        'u_scan_debug': [('rjc_payload','rjc_record[639:320]')],
    }
    for instance, ports in entries.items():
        new['console_neo'] = pt.instance_ports(new['console_neo'], instance, ports)
        allow['console_neo'][instance] = dict(ports)
    for n in ('neo_gpu_debug_0','neo_gpu_debug'):
        new[n], allow[n] = pt.transform(old[n], inv.cells(old[n]), n.endswith('_0'))

    audit, merged = {}, original
    for n in sorted(touched):
        before, after = inv.cells(old[n]), inv.cells(new[n])
        assert set(before) <= set(after)
        changes = {}
        for cell, b in before.items():
            a = after[cell]
            assert a['kind'] == b['kind'] and a['parameters'] == b['parameters'], (n, cell)
            permitted = allow[n].get(cell, {})
            assert a['ports'] == {**b['ports'], **permitted}, (n, cell, 'pin mismatch')
            if a['ports'] != b['ports']:
                changes[cell] = permitted
        audit[n] = {'original_cells':len(before),'original_parameters_unchanged':True,
                    'changed_or_added_pins':changes,'added_cells':sorted(set(after)-set(before))}
        merged = pt.once(merged, old[n], new[n])
    for n in names-touched:
        assert inv.module(merged,n) == inv.module(original,n), n
    # Undo every modified module, not a lossy normalized diff.
    undo = merged
    for n in touched:
        undo = pt.once(undo,new[n],old[n])
    assert undo == original
    for top in ('neo_reject_witness','neo_rjc_readback'):
        text = (mapping/(top+'_mapped.v')).read_text()
        merged += '\n' + inv.module(text,top) + '\n'
    out.mkdir(exist_ok=False)
    (out/'console_neo.vg').write_text(merged)
    (out/'changed_modules.v').write_text('\n\n'.join(new[n] for n in sorted(touched))+'\n')
    result = {'passed':True,'candidate_only':True,'hardware':False,'routing':False,
              'parent_vg_sha256':inv.EXPECTED,'candidate_vg_sha256':sha(out/'console_neo.vg'),
              'original_recovered_byte_identical':True,'modules':audit,
              'untouched_module_count':len(names-touched),
              'transport_added_FF':298,'observer_added_FF':653,'total_added_FF':951,
              'pending':['Independent audit of assignment/port semantics.',
                         'Full two-bank AHB/CDC simulation.',
                         'No Gowin parser, P&R, timing or board test.'],
              'inputs':{str(p.relative_to(HERE)):sha(p) for p in
                        (Path(__file__),HERE/'patch_transport.py',mapping/'result.json')}}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'candidate_vg_sha256':result['candidate_vg_sha256'],
                      'total_added_FF':951,'routing':False}))


if __name__ == '__main__':
    main()
