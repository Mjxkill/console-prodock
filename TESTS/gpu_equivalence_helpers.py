"""Shared cycle monitor for the open DDR arbiter; references stay frozen."""
from pathlib import Path
import re


def arbiter_equivalence(root, reference_root, out, bench_path):
    source = root/'tang/rtl/board/ddr_gpu_arb.v'
    reference = reference_root/'tang/rtl/board/ddr_gpu_arb.v'
    old = reference.read_text()
    (out/'arb_reference.v').write_text(old.replace('module ddr_gpu_arb (', 'module ddr_gpu_arb_reference (', 1))
    header = source.read_text().split('    reg [1:0] tags')[0]
    inputs, outputs = [], {}
    for direction, width, names in re.findall(r'(input|output) wire\s*(\[[^]]+\])?\s*([^;\n]+)', header):
        for name in names.rstrip(',').split(','):
            name = name.strip()
            if direction == 'input':
                inputs.append(name)
            else:
                outputs[name] = width or ''
    body = ''.join(f'    wire {width} ref_{name};\n' for name, width in outputs.items())
    for typ, prefix in [('ddr_gpu_arb', ''), ('ddr_gpu_arb_reference', 'ref_')]:
        ports = [f'.{n}({n})' for n in inputs] + [f'.{n}({prefix}{n})' for n in outputs]
        body += f'    {typ} u_{typ} ('+', '.join(ports)+');\n'
    body += '    integer compared_cycles=0;\n    always @(posedge clk) if(rst_n)begin\n        compared_cycles<=compared_cycles+1;\n'
    # Empty buffers may sample the next payload early. Compare every control
    # cycle and all strobed DDR payloads; idle address/data have no protocol
    # meaning and are never consumed by the memory controller.
    qualifier = {'m_cmd':'m_en', 'm_addr':'m_en',
                 'm_wr_data':'m_wr_en', 'm_wr_mask':'m_wr_en'}
    for name in outputs:
        guard = qualifier.get(name, "1'b1")
        body += f'        if({guard} && {name} !== ref_{name}) $fatal(1,"Arbiter {name} mismatch at %0d",compared_cycles);\n'
    for name in ['wp', 'rp', 'full']:
        body += f'        if(u_ddr_gpu_arb.{name} !== u_ddr_gpu_arb_reference.{name}) $fatal(1,"Arbiter {name} mismatch at %0d",compared_cycles);\n'
    body += '    end\n    final $display("ARBITER EQUIVALENCE: %0d cycles compared",compared_cycles);\nendmodule\n'
    (out/'arb_wrapper.sv').write_text(header.replace('module ddr_gpu_arb (', 'module ddr_gpu_arb_equiv (', 1)+body)
    bench = bench_path.read_text()
    assert 'ddr_gpu_arb arb (' in bench
    (out/'bench.sv').write_text(bench.replace('ddr_gpu_arb arb (', 'ddr_gpu_arb_equiv arb (', 1))
    return [out/'arb_reference.v', out/'arb_wrapper.sv', out/'bench.sv'], [source, reference]
