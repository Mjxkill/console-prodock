"""Add RJC1 payload bits to an existing NGDB transport, without new addresses."""
import re


def once(text, old, new):
    assert text.count(old) == 1, old[:100]
    return text.replace(old, new, 1)


def port(text, declarations):
    """Append ports without altering old declarations or names."""
    end = re.search(r'\n\)\s*;', text)
    assert end
    names = [name for _, name in declarations]
    head = text[:end.start()] + ',\n  ' + ',\n  '.join(names)
    decl = ''.join(direction + ' ' + name + ';\n' for direction, name in declarations)
    return head + text[end.start():end.end()] + '\n' + decl + text[end.end():]


def wires(text, declarations):
    point = re.search(r'^wire ', text, re.M).start()
    return text[:point] + declarations + '\n' + text[point:]


def instance_ports(text, name, entries):
    match = re.search(r'^\s*\w+ ' + re.escape(name) + r' \(\n', text, re.M)
    assert match
    inserted = ''.join('    .' + key + '(' + value + '),\n' for key, value in entries)
    return text[:match.end()] + inserted + text[match.end():]


def tail(text, code):
    return once(text, 'endmodule', code + '\nendmodule')


def cell_text(text, name):
    matches = list(re.finditer(r'^\s*\w+ ' + re.escape(name) +
                              r' \(.*?\n\);', text, re.M | re.S))
    assert len(matches) == 1, name
    return matches[0].group(0)


def escaped(net):
    return net + ' ' if net.startswith('\\') else net


def transform(text, parsed, gpu):
    """Only old held-D and hrdata-D pins change; add missing held/snapshot FFs."""
    new = port(text, [('input [319:0]', 'rjc_payload')])
    if gpu:
        new = port(new, [('output', 'rjc_snapshot_request')])
    new = wires(new, 'wire [31:0] rjc_legacy_input,rjc_merged;')
    # SCAN's constant high bits were removed from both the FFs and bus width.
    for stage in ('held', 'snapshot'):
        matches = list(re.finditer(r'^wire \[(\d+):0\] ' + stage + ';', new, re.M))
        assert len(matches) == 1 and int(matches[0].group(1)) <= 319
        new = once(new, matches[0].group(0), f'wire [319:0] {stage};')
    added, allowed = [], {}
    clocks = {'held': 'gpu_clk', 'snapshot': 'vid_hclk'}
    reset = {'held': 'n237_5', 'snapshot': 'n6_6'}
    held_ce = 'n2835_5' if gpu else 'n2835_3'
    ce = {'held': held_ce, 'snapshot': 'n4022_5'}
    for stage in ('held', 'snapshot'):
        found = {int(m.group(1)): (n, c) for n, c in parsed.items()
                 if c['kind'] == 'DFFRE'
                 and (m := re.fullmatch(stage + r'\[(\d+)\]', c['ports'].get('Q', '')))}
        for bit in range(320):
            data = f'rjc_payload[{bit}]' if stage == 'held' else f'held[{bit}]'
            if bit in found:
                name, cell = found[bit]
                assert cell['ports']['CLK'] == clocks[stage]
                assert cell['ports']['RESET'] == reset[stage]
                # R19 absorbs the hold mux of GPU held[103] into its D cone,
                # leaving CE=VCC. Restore a data mux, never make it free-running.
                if gpu and stage == 'held' and bit == 103:
                    assert cell['ports']['CE'] == 'VCC'
                    new = wires(new, 'wire rjc_held103_D;')
                    added.append('LUT3 rjc_hold103(.I0(held[103]),.I1(rjc_payload[103]),'
                                 '.I2(n2835_5),.F(rjc_held103_D));\n'
                                 "defparam rjc_hold103.INIT=8'hca;")
                    data = 'rjc_held103_D'
                else:
                    assert cell['ports']['CE'] == ce[stage]
                # Snapshot input bits may also alias another original held bit
                # after constant/common-value folding (e.g. SCAN70<-held67).
                # Arbitrary RJC1 data requires the original bit index again.
                if stage == 'held' or cell['ports']['D'] != data:
                    old = cell_text(new, name)
                    changed = re.sub(r'\.D\([^)]*\)', '.D(' + data + ')', old, count=1)
                    new = once(new, old, changed)
                    allowed[name] = {'D': data}
            else:
                name = f'rjc_{stage}_{bit}'
                added.append(f'DFFRE {name}(.Q({stage}[{bit}]),.D({data}),'
                             f'.CLK({clocks[stage]}),.RESET({reset[stage]}),.CE({ce[stage]}));\n'
                             f"defparam {name}.INIT=1'b0;")
    qname = 'trace_legacy_data' if gpu else 'scan_debug_hrdata'
    for bit in range(32):
        name = f'hrdata_{bit}_s0'
        cell = parsed[name]
        assert cell['ports']['Q'] == f'{qname}[{bit}]'
        assert cell['ports']['CLK'] == 'vid_hclk' and cell['ports']['CE'] == 'VCC'
        old = cell_text(new, name)
        new = once(new, old, re.sub(r'\.D\([^)]*\)', f'.D(rjc_merged[{bit}])', old, count=1))
        # Preserve whitespace that terminates an escaped vector identifier;
        # removing it changes `\\name [0]` into a different scalar `\\name[0]`.
        raw_data = re.search(r'\.D\(([^)]*)\)', old).group(1)
        added.append(f'assign rjc_legacy_input[{bit}]={raw_data};')
        allowed[name] = {'D': f'rjc_merged[{bit}]'}
    added.append('neo_rjc_readback rjc_read(.legacy(rjc_legacy_input),.select(read_select),'
                 '.snapshot(snapshot),.merged(rjc_merged));')
    if gpu:
        added.append('LUT2 rjc_req(.I0(req_s[1]),.I1(ack),.F(rjc_snapshot_request));\n'
                     "defparam rjc_req.INIT=4'h6;")
    return tail(new, '\n'.join(added)), allowed
