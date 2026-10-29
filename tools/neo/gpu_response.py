"""Insert a response stage in a frozen Neo top, leaving the DDR arbiter intact."""
import hashlib
import json
import re
from pathlib import Path
from .gpu_debug import replace_once

RTL = 'tang/boards/neo/neo_gpu_response.v'
PROFILE = 'tang/boards/neo/gpu_response.json'


def freeze(source):
    source = Path(source)
    path = source/'tang/boards/neo/console_neo.v'
    original = path.read_text()
    if (source/PROFILE).exists():
        raise ValueError('GPU response stage already applied')
    reset = re.findall(r'gpu_accel u_accel\(.hclk\(vid_hclk\),.hresetn\(([^)]+)\)', original)
    if len(reset) != 1 or reset[0] not in ('vid_hrstn', 'vid_reset_branches[1]'):
        raise ValueError('Unknown GPU reset connection')
    text = replace_once(original, '    gpu_accel u_accel(', '''    wire gpu_response_valid;
    wire [255:0] gpu_response_data;
    neo_gpu_response u_gpu_response(.clk(gpu_clk),.resetn('''+reset[0]+'''),
        .in_valid(blit_rd_valid),.in_data(blit_rd_data),
        .out_valid(gpu_response_valid),.out_data(gpu_response_data));
    gpu_accel u_accel(''')
    text = replace_once(text, '.rd_data(blit_rd_data),.rd_valid(blit_rd_valid)',
                        '.rd_data(gpu_response_data),.rd_valid(gpu_response_valid)')
    record = dict(profile='neo-gpu-response-one-ui-cycle', latency_cycles=1,
                  throughput_beats_per_cycle=1, reset=reset[0],
                  before=hashlib.sha256(original.encode()).hexdigest(),
                  after=hashlib.sha256(text.encode()).hexdigest(),
                  rtl_sha256=hashlib.sha256((source/RTL).read_bytes()).hexdigest())
    path.write_text(text)
    (source/PROFILE).write_text(json.dumps(record, indent=2)+'\n')
    return record


def audit_mapped(netlist):
    """Require the 256 always-clocked payload FFs and the reset guard chain.

    Structural check only: RTL simulations check ownership/data sequencing;
    the full routed timing report remains mandatory.
    """
    raw=Path(netlist).read_bytes()
    found=re.findall(r'^module neo_gpu_response\b.*?^endmodule', raw.decode(), re.M|re.S)
    if len(found)!=1:return dict(passed=False,errors=['Missing response-stage module'])
    body=found[0];errors=[]
    cells={name:(kind,dict(re.findall(r'\.(\w+)\(([^()]*)\)',ports)))
           for kind,name,ports in re.findall(r'^\s*(DFF\w+)\s+(\w+)\s*\((.*?)\);',body,re.M|re.S)}
    expected_names={f'out_data_{i}_s0' for i in range(256)}|{'released_0_s0','released_1_s0','out_valid_s0'}
    if set(cells)!=expected_names:errors.append('Response-stage FF count or names changed')
    for i in range(256):
        wanted=dict(Q=f'gpu_response_data[{i}]',D=f'blit_rd_data[{i}]',CLK='gpu_clk',CLEAR='GND',CE='VCC')
        if cells.get(f'out_data_{i}_s0')!=('DFFCE',wanted):
            errors.append('Changed response payload FF '+str(i))
    clears=[]
    for name,q,d in [('released_0_s0','released[0]','VCC'),
                     ('released_1_s0','released[1]','released[0]'),
                     ('out_valid_s0','gpu_response_valid',None)]:
        kind,ports=cells.get(name,('',{}))
        if (kind!='DFFCE' or ports.get('Q')!=q or ports.get('CLK')!='gpu_clk'
                or ports.get('CE')!='VCC' or (d is not None and ports.get('D')!=d)
                or not re.search(r'defparam '+name+r"\.INIT=1'b0;",body)):
            errors.append('Changed response validity/reset FF '+name)
        clears.append(ports.get('CLEAR'))
    if len(set(clears))!=1 or clears[0] in (None,'GND','VCC'):
        errors.append('Response validity/reset FFs do not share asynchronous assertion')
    else:
        inverters=re.findall(r'\bINV\s+\w+\s*\(\s*\.O\('+re.escape(clears[0])+r'\),\s*\.I\(([^)]+)\)',body)
        if inverters!=['vid_hrstn_accel']:errors.append('Response reset does not come from the GPU reset branch')
    return dict(passed=not errors,errors=errors,payload_registers=256,control_registers=3,
                netlist_sha256=hashlib.sha256(raw).hexdigest(),
                scope='Structure only; functional and full timing checks remain required')
