#!/usr/bin/env python3
"""Explicit bus slices for Gowin's mapped-netlist parser; same logical design."""
import argparse,json,re,shutil
from pathlib import Path
import build_capture as b
SRC=b.OUT
DEST=b.ROOT/'tang/impl/console_neo_n56r18r1_local_capture'

def prepare():
    b.preflight();contract=b.before_build('neo',candidate=True)
    failed=json.loads((SRC/'route_result.json').read_text());assert failed['returncode']==1
    log=(SRC/'build.log').read_text();assert 'PA2060' in log and 'Running placement' not in log
    original=(SRC/'console_neo.vg').read_text();modified=original
    changes={'.write_addr(bus_addr)':'.write_addr(bus_addr[7:0])',
             '.legacy_data(trace_legacy_data)':'.legacy_data(trace_legacy_data[31:0])',
             '.hrdata(debug_hrdata)':'.hrdata(debug_hrdata[31:0])',
             '.held(trace_held)':'.held(trace_held[63:0])',
             '.trace_held(trace_held)':'.trace_held(trace_held[63:0])'}
    counts={}
    for old,new in changes.items():
        counts[old]=modified.count(old);assert counts[old]>0
        assert new not in modified;modified=modified.replace(old,new)
    restored=modified
    for old,new in changes.items():restored=restored.replace(new,old)
    assert restored==original
    # Explicit full ranges equal the declarations, so no bit selection changes.
    for name,width in [('bus_addr',8),('trace_legacy_data',32),('debug_hrdata',32),('trace_held',64)]:
        scope=original if name=='trace_held' else b.block(original,'neo_gpu_debug_0')
        declarations=re.findall(r'^(?:input|output|wire) \[(\d+):0\] '+name+r';',scope,re.M)
        assert declarations and all(int(v)+1==width for v in declarations)
    DEST.mkdir(exist_ok=False)
    for folder in ('source','capture_ip'):shutil.copytree(SRC/folder,DEST/folder)
    for n in ('parent.vg','sources.json','preparation.json','assembly.json','font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex'):
        (DEST/n).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SRC/n,DEST/n)
    (DEST/'console_neo.vg').write_text(modified)
    (DEST/'build.tcl').write_text((SRC/'build.tcl').read_text().replace(str(SRC),str(DEST)))
    a=json.loads((DEST/'assembly.json').read_text())
    a['inputs'].update({n:b.sha(DEST/n) for n in ('console_neo.vg','build.tcl')})
    a['format_correction']=dict(parent=str(SRC),counts=counts,exact_reverse=True,logic_changed=False,
        failed_route_sha256=b.sha(SRC/'route_result.json'),formatter_sha256=b.sha(Path(__file__)))
    b.save(DEST/'assembly.json',a);b.record_build(DEST,contract)
    shutil.copy2(Path(__file__),DEST/'format_retry.py')
    print(json.dumps(dict(prepared=str(DEST),counts=counts,logic_changed=False)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--route',action='store_true');p.add_argument('--proof',type=Path);a=p.parse_args()
    if a.route:
        assert a.proof
        r=json.loads((DEST/'assembly.json').read_text())
        assert r['format_correction']['formatter_sha256']==b.sha(Path(__file__))
        b.OUT=DEST;b.route(a.proof)
    else:prepare()
