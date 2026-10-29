"""Apply and verify the explicit DDR startup sequence in an isolated Neo copy."""
import hashlib
import json
import re
from pathlib import Path

SOC = 'tang/rtl/board/ae350_soc.v'
RTL = 'tang/boards/neo/neo_ddr_startup.v'
PROFILE = 'tang/boards/neo/ddr_startup.json'
OLD = '''    reg  [1:0] init_sync = 2'b00;
    always @(posedge ahb_clk or negedge rst_key_n)
        if (!rst_key_n) init_sync <= 2'b00;
        else init_sync <= {init_sync[0], ddr3_init_completed};
    wire ae350_rstn = init_sync[1];'''
NEW = '''    wire ddr_controller_resetn, ae350_rstn;
    neo_ddr_startup u_ddr_startup (
        .ref_clk(ddr3_clk_in), .resetn(rst_key_n), .cpu_clk(ahb_clk),
        .pll_locked(ddr3_lock), .calib_complete(ddr3_init_completed),
        .ip_resetn(ddr_controller_resetn), .cpu_resetn(ae350_rstn)
    );'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Missing/ambiguous DDR startup anchor: '+old)
    return text.replace(old, new, 1)


def reset_ports(text, old, new):
    # Normal controller and mutually exclusive RAM_PROBE diagnostic branch.
    if text.count(old) != 2:
        raise ValueError('Missing/ambiguous DDR reset ports')
    return text.replace(old, new)


def freeze(source):
    source = Path(source)
    if (source/PROFILE).exists():
        raise ValueError('DDR startup profile already applied')
    path = source/SOC
    before = path.read_bytes()
    text = replace_once(before.decode(), OLD, NEW)
    text = reset_ports(text, ".DDR3_RSTN(1'b1)", '.DDR3_RSTN(ddr_controller_resetn)')
    # The only asynchronous reset endpoints are the two synchronizer chains.
    # The counter, IP reset release and all downstream paths remain timed.
    sdc = source/'tang/boards/neo/neo.sdc'
    constraints = ''.join('set_false_path -to [get_pins {u_soc/u_ddr_startup/'+name+'*/CLEAR}]\n'
                          for name in ('start_sync_', 'cpu_sync_'))
    record = dict(profile='neo-ddr-startup-ref50-v1', hold_cycles=1024,
                  before_sha256=digest(before), after_sha256=digest(text.encode()),
                  rtl_sha256=digest((source/RTL).read_bytes()), constraints=constraints)
    path.write_text(text)
    sdc.write_text(sdc.read_text()+'\n// DDR startup: asynchronous assertion, synchronized release.\n'+constraints)
    (source/PROFILE).write_text(json.dumps(record, indent=2)+'\n')
    return record


def original_soc(source, data=None):
    """Undo only the declared startup edit, optionally after reset-tree undo."""
    source = Path(source)
    record = json.loads((source/PROFILE).read_text())
    if record.get('profile') != 'neo-ddr-startup-ref50-v1' or record.get('hold_cycles') != 1024:
        raise ValueError('Unknown DDR startup transformation')
    data = (source/SOC).read_bytes() if data is None else data
    if digest(data) != record['after_sha256']:
        raise ValueError('DDR startup SoC changed')
    if digest((source/RTL).read_bytes()) != record['rtl_sha256']:
        raise ValueError('DDR startup sequencer changed')
    text = replace_once(data.decode(), NEW, OLD)
    text = reset_ports(text, '.DDR3_RSTN(ddr_controller_resetn)', ".DDR3_RSTN(1'b1)")
    if digest(text.encode()) != record['before_sha256']:
        raise ValueError('DDR startup inversion did not reproduce the baseline')
    return text.encode()


def audit_mapped(netlist):
    """Require the two distinct synchronization stages and the reference clock."""
    text=Path(netlist).read_text()
    found=re.findall(r'^module neo_ddr_startup\b.*?^endmodule',text,re.M|re.S)
    if len(found)!=1:return dict(passed=False,errors=['Missing startup module'])
    text=found[0];errors=[];chains={}
    for name,clock in (('start_sync','clk_d'),('cpu_sync','vid_hclk')):
        cells=[]
        for i in (0,1):
            cell=f'{name}_{i}_s0'
            body=re.findall(r'\bDFFCE '+cell+r'\s*\((.*?)\);',text,re.S)
            if len(body)!=1:
                errors.append('Missing distinct startup FF '+cell);continue
            ports=dict(re.findall(r'\.(\w+)\(([^()]*)\)',body[0]));cells.append(ports)
            if (ports.get('CLK')!=clock or ports.get('CE')!='VCC' or
                    ports.get('D')!=('VCC' if i==0 else name+'[0]') or
                    not re.search(r'defparam '+cell+r"\.INIT=1'b0;",text)):
                errors.append('Changed startup synchronizer '+cell)
        if len(cells)==2 and (cells[0]['CLEAR']!=cells[1]['CLEAR'] or cells[0]['Q']==cells[1]['Q']):
            errors.append('Merged or independently reset synchronizer '+name)
        chains[name]=cells
    ip=re.findall(r'\bDFFCE ip_resetn_s0\s*\((.*?)\);',text,re.S)
    if len(ip)!=1 or '.CLK(clk_d)' not in ip[0] or "defparam ip_resetn_s0.INIT=1'b0;" not in text:
        errors.append('IP reset is not initialized low on the reference clock')
    return dict(passed=not errors,errors=errors,chains=chains,
                netlist_sha256=digest(Path(netlist).read_bytes()))
