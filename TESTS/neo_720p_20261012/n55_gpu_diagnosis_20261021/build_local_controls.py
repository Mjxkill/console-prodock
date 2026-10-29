#!/usr/bin/env python3
"""Prepare/build one N56 routing experiment: exactly three LOCAL_CLOCK lines.

No synthesis, RTL, SDC, DDR, placement-constraint, pin or frequency change.
Placement and routing are recomputed by Gowin from the same synthesized netlist.
--prepare-only archives the reviewed candidate and never invokes Gowin.
No hardware access in either mode.
"""
import argparse,difflib,hashlib,json,re,shutil,subprocess,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from board_contract import before_build,record_build
from gowin_toolchain import IDE,environment
from check_ddr_profile import audit as audit_ddr

PARENT=ROOT/'tang/impl/console_neo_n56_observe'
NETS=('u_accel/u_v1/n56220_6','u_gpu_debug/n2835_5','u_gpu_debug/mem_up[1]')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
norm=lambda s:re.sub(r'\s+','',s).removeprefix('\\')


def cells(text):
    return {norm(name):dict(kind=kind,pins={pin:norm(net) for pin,net in
        re.findall(r'\.(\w+)\s*\(([^()]*)\)',body)})
        for kind,name,body in re.findall(r'^\s*(\w+)\s+(\\\S+|\w+)\s*\(([^;]*?)\);',text,re.M|re.S)
        if kind!='module'}


def proof():
    vg=PARENT/'impl/gwsynthesis/console_neo.vg';vo=PARENT/'impl/pnr/console_neo.vo'
    text=vg.read_text();routed=vo.read_text()
    modules={m[1]:m[0] for m in re.finditer(r'^module (\w+)\b.*?^endmodule',text,re.M|re.S)}
    top=cells(modules['console_neo']);accel=cells(modules[top['u_accel']['kind']])
    if top['u_gpu_debug']['kind']!='neo_gpu_debug' or accel['u_v1']['kind']!='gpu_geometry':
        raise ValueError('Unexpected mapped hierarchy')
    routes=(PARENT/'impl/pnr/console_neo.rpt.txt').read_text()
    result=[]
    for net,module,hierarchy,driver,kind,init,ce_count in (
        (NETS[0],'gpu_geometry','u_accel/u_v1','n56220_s2','LUT4',"16'h8000",312),
        (NETS[1],'neo_gpu_debug','u_gpu_debug','n2835_s1','LUT2',"4'h6",283),
        (NETS[2],'neo_gpu_debug','u_gpu_debug','mem_up_1_s0','DFFCE',"1'b0",None)):
        local=net.removeprefix(hierarchy+'/');stages={}
        for stage,body,prefix in [('synthesis',modules[module],''),('routed',routed,hierarchy+'/')]:
            cc=cells(body);target=prefix+local;name=prefix+driver
            found=[n for n,c in cc.items() if any(c['pins'].get(p)==target for p in ('Q','F','O'))]
            if found!=[name] or cc[name]['kind']!=kind:raise ValueError('Driver differs: '+net+' '+stage)
            params={norm(n):v.lower() for n,v in re.findall(r'^\s*defparam\s+(\\\S+|\w+)\s*\.INIT\s*=\s*([^;]+);',body,re.M)}
            if params.get(name)!=init:raise ValueError('Driver INIT differs: '+net)
            loads=[dict(instance=n,primitive=c['kind'],pin=p) for n,c in cc.items() for p,v in c['pins'].items()
                if v==target and p not in ('Q','F','O')]
            if any(x['pin'] in ('CLK','CLKA','CLKB','CLKIN') for x in loads):raise ValueError('A proposed control is a clock')
            if ce_count is not None and sum(x['pin']=='CE' for x in loads)!=ce_count:
                raise ValueError('Unexpected CE fanout '+net+' '+stage)
            if net==NETS[0] and sum(x['pin']=='CE' and '/captured_command_' in '/'+x['instance'] for x in loads)!=256:
                raise ValueError('Captured-command cone differs')
            if net==NETS[1] and sum(x['pin']=='CE' and '/held_' in '/'+x['instance'] for x in loads)!=282:
                raise ValueError('Snapshot held cone differs')
            if net==NETS[2]:
                pins=cc[name]['pins']
                if pins['D']!=prefix+'mem_up[0]' or pins['CE']!='VCC' or pins['CLK']!='gpu_clk':
                    raise ValueError('mem_up pipeline differs')
            stages[stage]=dict(driver=name,primitive=kind,init=init,pins=cc[name]['pins'],loads=loads)
        if not re.search(r'^\s*'+re.escape(net)+r'\s*\|\s*LW\s*\|',routes,re.M):
            raise ValueError('Expected observed LW control absent: '+net)
        result.append(dict(net=net,original_route='LW',stages=stages))
    return dict(controls=result,sha256={str(p):sha(p) for p in (vg,vo,PARENT/'impl/pnr/console_neo.rpt.txt')})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--name',default='console_neo_n56r1',choices=['console_neo_n56r1'])
    p.add_argument('--prepare-only',action='store_true')
    a=p.parse_args()
    manifest=json.loads((PARENT/'sources.json').read_text())
    actual={str(f.relative_to(PARENT/'source')):sha(f) for f in (PARENT/'source').rglob('*') if f.is_file()}
    if actual!=manifest:raise ValueError('Changed parent source tree')
    ddr=audit_ddr(PARENT/'source',variant='neo-fifo-registers')
    if not ddr['passed']:raise ValueError('DDR profile changed')
    q=json.loads((PARENT/'qualification.json').read_text())
    if q['bitstream_sha256']!='ecef1e120d9940bab6b28bac12557e87f0790e8610cf6788326220bd38db0f3a':
        raise ValueError('Different N56 parent')
    cst=PARENT/'source/tang/boards/neo/neo.cst';original=cst.read_text()
    if any(re.search(r'CLOCK_LOC\s+"'+re.escape(net)+'"',original) for net in NETS):
        raise ValueError('Refusing to override an existing control constraint')
    addition='\n'+''.join(f'CLOCK_LOC "{net}" LOCAL_CLOCK;\n' for net in NETS)
    candidate=original+addition
    audit=proof()
    contract=before_build('neo',candidate=True)
    prepared=HERE/'n56r1_local_controls';prepared.mkdir(exist_ok=True)
    (prepared/'neo.cst').write_text(candidate)
    (prepared/'constraints.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),candidate.splitlines(True),fromfile='N56/neo.cst',tofile='N56r1/neo.cst')))
    (prepared/'control_proof.json').write_text(json.dumps(audit,indent=2)+'\n')
    record=dict(parent=str(PARENT),name=a.name,hardware_access=False,synthesis=False,
        netlist_sha256=sha(PARENT/'impl/gwsynthesis/console_neo.vg'),
        source_manifest_sha256=sha(PARENT/'sources.json'),
        sdc_sha256=sha(PARENT/'source/tang/boards/neo/neo.sdc'),
        original_cst_sha256=sha(cst),candidate_cst_sha256=sha(prepared/'neo.cst'),
        exact_added_lines=addition.strip().splitlines(),changed_source_files=['tang/boards/neo/neo.cst'],
        control_proof_sha256=sha(prepared/'control_proof.json'),script_sha256=sha(Path(__file__)),ddr_profile=ddr)
    (prepared/'manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    if a.prepare_only:
        print(json.dumps(record,indent=2));return
    out=ROOT/'tang/impl'/a.name;out.mkdir(exist_ok=False)
    record_build(out,contract);shutil.copytree(PARENT/'source',out/'source')
    (out/'source/tang/boards/neo/neo.cst').write_text(candidate)
    shutil.copy2(PARENT/'impl/gwsynthesis/console_neo.vg',out/'console_neo.vg')
    for relative in ('font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex'):
        target=out/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/relative,target)
    updated={str(f.relative_to(out/'source')):sha(f) for f in (out/'source').rglob('*') if f.is_file()}
    if set(updated)!=set(manifest) or [k for k in updated if updated[k]!=manifest[k]]!=['tang/boards/neo/neo.cst']:
        raise ValueError('Unexpected source changes')
    (out/'sources.json').write_text(json.dumps(updated,indent=2)+'\n')
    observer=json.loads((PARENT/'observer_build.json').read_text())
    observer.update(source_manifest_sha256=sha(out/'sources.json'),routing_parent=str(PARENT),
        routing_parent_observer_manifest_sha256=sha(PARENT/'observer_build.json'))
    (out/'observer_build.json').write_text(json.dumps(observer,indent=2)+'\n')
    (out/'route.json').write_text(json.dumps(dict(parent=str(PARENT),netlist_sha256=record['netlist_sha256'],
        local_controls_experiment=record),indent=2)+'\n')
    settings=[line.replace(str(PARENT),str(out)) for line in (PARENT/'build.tcl').read_text().splitlines()
              if line.startswith(('set_device ','set_option '))]
    tcl='\n'.join(settings+[f'add_file {{{out/"console_neo.vg"}}}',
        f'add_file {{{out/"source/tang/boards/neo/neo.cst"}}}',
        f'add_file {{{out/"source/tang/boards/neo/neo.sdc"}}}','run pnr',''])
    (out/'build.tcl').write_text(tcl)
    shutil.copy2(prepared/'control_proof.json',out/'local_controls_proof.json')
    with (out/'build.log').open('w') as log:
        done=subprocess.run([str(IDE/'bin/gw_sh'),'build.tcl'],cwd=out,env=environment(),stdout=log,stderr=subprocess.STDOUT)
    if done.returncode or re.search(r'^ERROR',(out/'build.log').read_text(),re.M):raise SystemExit('Routing failed')
    print(out)


if __name__=='__main__':main()
