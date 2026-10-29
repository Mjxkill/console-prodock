"""Replicate the existing Neo bus reset register without another clock stage.

Only frozen Neo sources are edited. Each branch has the original D, clock,
enable, reset polarity and initial value. This is fanout reduction, not a
new reset synchronizer. Post-synthesis mapping must retain distinct drivers.
"""
import hashlib
import json
import re
from pathlib import Path

PROFILE=Path('tang/boards/neo/system_reset.json')
BRANCHES=('scanout','accel','gamepads','scan_queue','usb_trace','usb_msc')
ORIGINAL="    reg vid_hrstn_r = 1'b0; always @(posedge exts_hclk) vid_hrstn_r <= exts_hrstn;"


def registers():
    names=('vid_hrstn_r',)+tuple('vid_hrstn_'+name for name in BRANCHES)
    text='\n'.join("    reg "+name+" /* synthesis syn_preserve=1 syn_keep=1 */ = 1'b0;\n"
                   "    always @(posedge exts_hclk) "+name+" <= exts_hrstn;" for name in names)
    text+='\n'+''.join(f'    assign vid_reset_branches[{i}] = vid_hrstn_{name};\n'
                         for i,name in enumerate(BRANCHES))
    return text


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Missing/ambiguous system reset anchor: '+old)
    return text.replace(old,new,1)


def freeze(source):
    source=Path(source)
    if (source/PROFILE).exists():raise ValueError('System reset profile already applied')
    soc_path=Path('tang/rtl/board/ae350_soc.v')
    top_path=Path('tang/boards/neo/console_neo.v')
    usb_path=Path('tang/boards/neo/soft_usb.vh')
    cst_path=Path('tang/boards/neo/neo.cst')
    before={p:(source/p).read_text() for p in (soc_path,top_path,usb_path,cst_path)}
    soc=once(before[soc_path],'    output wire        vid_hrstn,',
             '    output wire        vid_hrstn,\n    output wire [5:0]  vid_reset_branches,')
    soc=once(soc,"    assign vid_hclk = 1'b0; assign vid_hrstn = 1'b0;",
             "    assign vid_reset_branches = 6'd0;\n    assign vid_hclk = 1'b0; assign vid_hrstn = 1'b0;")
    soc=once(soc,ORIGINAL,registers())
    top=once(before[top_path],'    wire vid_hclk,vid_hrstn,vid_hsel,vid_hwrite,vid_hready;',
             '    wire [5:0] vid_reset_branches;\n    wire vid_hclk,vid_hrstn,vid_hsel,vid_hwrite,vid_hready;')
    top=once(top,'.vid_hclk(vid_hclk), .vid_hrstn(vid_hrstn),',
             '.vid_reset_branches(vid_reset_branches), .vid_hclk(vid_hclk), .vid_hrstn(vid_hrstn),')
    for old,new in (
        ('.hresetn(vid_hrstn),.hsel(bus_hsel && bus_haddr[14:12]==0)',
         '.hresetn(vid_reset_branches[0]),.hsel(bus_hsel && bus_haddr[14:12]==0)'),
        ('gpu_accel u_accel(.hclk(vid_hclk),.hresetn(vid_hrstn),',
         'gpu_accel u_accel(.hclk(vid_hclk),.hresetn(vid_reset_branches[1]),'),
        ('neo_gamepads u_gamepads(.clk(vid_hclk),.resetn(vid_hrstn),',
         'neo_gamepads u_gamepads(.clk(vid_hclk),.resetn(vid_reset_branches[2]),'),
        ('neo_scan_queue u_scan_queue(.clk(gpu_clk),.resetn(vid_hrstn),',
         'neo_scan_queue u_scan_queue(.clk(gpu_clk),.resetn(vid_reset_branches[3]),')):
        top=once(top,old,new)
    usb=before[usb_path]
    for index,module in ((4,'usb_idle_trace'),(5,'usb_msc_port')):
        old=module+' u_'+module+' (\n        .clk(phy_clk),.reset_n(vid_hrstn && !rst_usb)'
        usb=once(usb,old,old.replace('vid_hrstn &&',f'vid_reset_branches[{index}] &&'))
    # syn_keep gives the driver's internal Q precedence over its port alias.
    cst=once(before[cst_path],'CLOCK_LOC "vid_hrstn" LOCAL_CLOCK;',
             'CLOCK_LOC "u_soc/vid_hrstn_r" LOCAL_CLOCK;')
    cst+='\n// Neo same-cycle reset branches; final routing must be measured.\n'
    cst+=''.join(f'CLOCK_LOC "u_soc/vid_hrstn_{name}" LOCAL_CLOCK;\n' for name in BRANCHES)
    after={soc_path:soc,top_path:top,usb_path:usb,cst_path:cst}
    record=dict(profile='neo-system-reset-seven-drivers',branches=list(BRANCHES),
                added_clock_stages=0,changed={str(p):dict(before=hashlib.sha256(before[p].encode()).hexdigest(),
                after=hashlib.sha256(text.encode()).hexdigest()) for p,text in after.items()})
    for p,text in after.items():(source/p).write_text(text)
    (source/PROFILE).write_text(json.dumps(record,indent=2)+'\n')
    return record


def original_soc(source):
    """Reconstruct the byte-identical baseline; never exempt arbitrary SoC edits."""
    source=Path(source);record=json.loads((source/PROFILE).read_text())
    if (record.get('profile')!='neo-system-reset-seven-drivers' or
        record.get('branches')!=list(BRANCHES) or record.get('added_clock_stages')!=0):
        raise ValueError('Unknown system reset transformation')
    rel='tang/rtl/board/ae350_soc.v';text=(source/rel).read_text()
    if hashlib.sha256(text.encode()).hexdigest()!=record['changed'][rel]['after']:
        raise ValueError('Changed system reset SoC')
    text=once(text,'    output wire        vid_hrstn,\n    output wire [5:0]  vid_reset_branches,',
              '    output wire        vid_hrstn,')
    text=once(text,"    assign vid_reset_branches = 6'd0;\n    assign vid_hclk = 1'b0; assign vid_hrstn = 1'b0;",
              "    assign vid_hclk = 1'b0; assign vid_hrstn = 1'b0;")
    text=once(text,registers(),ORIGINAL)
    if hashlib.sha256(text.encode()).hexdigest()!=record['changed'][rel]['before']:
        raise ValueError('System reset inversion did not reproduce its original SoC')
    return text.encode()


def audit(netlist):
    """Reject merged copies or changed D/clock/enable/reset/initial values."""
    text=Path(netlist).read_text();errors=[];drivers=[]
    modules=re.findall(r'^module ae350_soc\b.*?^endmodule',text,re.M|re.S)
    if len(modules)!=1:return dict(passed=False,errors=['Missing/ambiguous ae350_soc'])
    module=modules[0]
    for name in ('vid_hrstn_r',)+tuple('vid_hrstn_'+b for b in BRANCHES):
        found=re.findall(r'^\s*DFFCE ('+name+r'_s[01])\s*\((.*?)\);',module,re.M|re.S)
        if len(found)!=1:
            errors.append('Missing distinct reset driver '+name);continue
        cell,body=found[0]
        ports=dict(re.findall(r'\.(\w+)\(([^()]*)\)',body));drivers.append(dict(cell=cell,ports=ports))
        wanted=dict(D='exts_hrstn',CLK='vid_hclk',CLEAR='GND',CE='VCC')
        if {k:v for k,v in ports.items() if k!='Q'}!=wanted:errors.append('Changed reset function '+cell)
        if not re.search(r'defparam '+cell+r"\.INIT=1'b0;",module):errors.append('Changed reset initial value '+cell)
    outputs=[d['ports'].get('Q') for d in drivers]
    if len(outputs)!=7 or len(set(outputs))!=7 or None in outputs:errors.append('Reset branches merged or incomplete')
    return dict(passed=not errors,errors=errors,drivers=drivers,
                netlist_sha256=hashlib.sha256(Path(netlist).read_bytes()).hexdigest())


def constrain(source,netlist):
    """Bind old port aliases to preserved, audited driver Q nets in a route copy."""
    mapped=audit(netlist)
    if not mapped['passed']:raise ValueError('Unverified system reset mapping')
    cst=Path(source)/'tang/boards/neo/neo.cst';text=cst.read_text()
    aliases=('vid_hrstn',)+tuple(f'vid_reset_branches[{i}]' for i in range(len(BRANCHES)))
    for alias,driver in zip(aliases,mapped['drivers']):
        old=f'CLOCK_LOC "{alias}" LOCAL_CLOCK;'
        new=f'CLOCK_LOC "u_soc/{driver["ports"]["Q"]}" LOCAL_CLOCK;'
        if old in text:text=once(text,old,new)
        elif text.count(new)!=1:raise ValueError('Missing system reset constraint '+new)
    cst.write_text(text)
    return mapped


def audit_routed(netlist):
    """Repeat the driver-function check on Gowin's flattened post-PnR netlist."""
    path=Path(netlist)
    if not path.is_file():return dict(passed=False,errors=['Missing post-PnR netlist'])
    text=path.read_text();errors=[];drivers=[]
    for name in ('vid_hrstn_r',)+tuple('vid_hrstn_'+b for b in BRANCHES):
        found=re.findall(r'^DFFCE (\\u_soc/'+name+r'_s[01])\s+\((.*?)\);',text,re.M|re.S)
        if len(found)!=1:
            errors.append('Missing routed driver '+name);continue
        cell,body=found[0]
        ports={k:v.strip().lstrip('\\') for k,v in re.findall(r'\.(\w+)\(([^()]*)\)',body)}
        drivers.append(dict(cell=cell,ports=ports))
        if {k:v for k,v in ports.items() if k!='Q'}!=dict(D='u_soc/exts_hrstn',CLK='vid_hclk',CLEAR='GND',CE='VCC'):
            errors.append('Changed routed reset function '+cell)
        if not re.search(r'defparam '+re.escape(cell)+r"\s+\.INIT=1'b0;",text):
            errors.append('Changed routed reset initial value '+cell)
    outputs=[d['ports'].get('Q') for d in drivers]
    if len(outputs)!=7 or len(set(outputs))!=7 or None in outputs:errors.append('Routed reset branches merged or incomplete')
    return dict(passed=not errors,errors=errors,drivers=drivers,
                netlist_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
