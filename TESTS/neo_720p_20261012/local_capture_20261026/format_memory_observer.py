#!/usr/bin/env python3
"""R20r1: scalar alias syntax accepted by Gowin's mapped-netlist parser."""
import argparse
import json
import shutil
from pathlib import Path
import prepare_memory_observer as b

PARENT=b.OUT
DEST=b.ROOT/'tang/impl/console_neo_n56r20r1_memory_observer'

def prepare():
    b.preflight();contract=b.before_build('neo',candidate=True)
    failure=json.loads((PARENT/'route_result.json').read_text())
    assert failure['returncode']!=0
    log=(PARENT/'build.log').read_text()
    assert 'PA2097' in log and "Not support bus wire('diag_pixels') in assign expression" in log
    r=json.loads((PARENT/'observation.json').read_text())
    for name,h in r['inputs'].items():assert b.sha(PARENT/name)==h,name
    before=(PARENT/'console_neo.vg').read_text()
    signals=[f'state[{i}]' for i in range(58)]+['native_issue','native_valid_8','n1617_5','clear_flags[0]','clear_flags[1]','bad_clear']
    transforms=[]
    for net,expr,bits in [('diag_pixels',b.PIXEL_EXPR,signals),('diag_handshake','{'+','.join(reversed(b.HANDSHAKES))+'}',b.HANDSHAKES)]:
        old='assign '+net+'='+expr+';'
        new='\n'.join(f'assign {net}[{i}] = {v};' for i,v in enumerate(bits))
        transforms.append((old,new));assert before.count(old)==1
    after=before
    for old,new in transforms:after=b.once(after,old,new)
    undone=after
    for old,new in transforms:undone=b.once(undone,new,old)
    assert undone==before
    DEST.mkdir(exist_ok=False);shutil.copytree(PARENT/'source',DEST/'source')
    for name in ('font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex','sources.json','prepare_memory_observer.py'):
        (DEST/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/name,DEST/name)
    (DEST/'console_neo.vg').write_text(after)
    (DEST/'build.tcl').write_text((PARENT/'build.tcl').read_text().replace(str(PARENT),str(DEST)))
    r.update(format_parent=str(PARENT),format_builder_sha256=b.sha(Path(__file__)),
        formatting_change='Two vector alias assignments expanded into 80 scalar assignments; unchanged bit order and drivers',
        format_undo_recovers_parent=True,scalar_pixel_signals_lsb_first=signals)
    r['inputs']={name:b.sha(DEST/name) for name in r['inputs']}
    b.save(DEST/'observation.json',r);shutil.copy2(Path(__file__),DEST/'format_memory_observer.py')
    b.record_build(DEST,contract);print('R20r1 scalar aliases prepared; R20 failure retained',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--route',type=Path);a=p.parse_args()
    if a.route:
        r=json.loads((DEST/'observation.json').read_text());assert r['format_builder_sha256']==b.sha(Path(__file__))
        b.OUT=DEST;b.route(a.route.resolve())
    else:prepare()
