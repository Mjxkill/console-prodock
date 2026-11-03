#!/usr/bin/env python3
"""Prepare one D128 diagnostic PNR, preserving S400 application and settings.

Only root may authorize run after review. There is no synthesis here and no
board access. Frozen generic launch/collection machinery is reused from RJC1;
its historical printed label does not identify the netlist being routed.
"""
import argparse,gzip,hashlib,importlib.util,json,re,shutil,sys
from pathlib import Path
import build
HERE=Path(__file__).resolve().parent;ROOT=build.ROOT
PARENT=ROOT/'tang/impl/console_neo_s400_20261031_r1'
OUT=ROOT/'tang/impl/console_neo_d128_20261102_r1'
NET_SHA='3f61cb977702e66e28210403de44c814ed473fe087b6347f62ca9bc1b82ceb48'
DELIVERY_SHA='d69ad597d73e3acfc07e9c5c4729a36239a55055ab19b739a449225af6d2d7ae'
ENGINE=ROOT/'TESTS/neo_common_cause_20261028/rejection_observer_plan_01/route_rjc1.py'
ENGINE_SHA='a0b231edf322de1080e2a379b7b3daca26233d166cc07426bc435331cfb713f8'
from board_contract import before_build,record_build
from gowin_toolchain import IDE
sha,need,save=build.sha,build.need,build.save

def guards():
    build.source_guard()
    need(sha(HERE/'MAPPED_DELIVERY.json')==DELIVERY_SHA,'Mapped delivery changed')
    d=json.loads((HERE/'MAPPED_DELIVERY.json').read_text())
    need(d['netlist_sha256']==NET_SHA,'Wrong assembly')
    for name,digest in d['files'].items():
        path=ROOT/name
        need(path.resolve().is_relative_to(ROOT) and not path.is_symlink(),'Unsafe proof')
        need(sha(path)==digest,'Mapped evidence changed: '+name)
    need(sha(ENGINE)==ENGINE_SHA,'Historical single-run engine changed')
    need(json.loads((HERE/'mapped_review_01/run_01/result.json').read_text())['passed'],'Mapped CDC failed')
    return before_build('neo',candidate=True)

def script():
    original=(PARENT/'build.tcl').read_text()
    need(original.count('run pnr')==1 and original.rstrip().endswith('run pnr'),'Parent flow changed')
    need(not re.search(r'\binc_(pnr|place)\b|run\s+syn',original),'Incremental/synthesis forbidden')
    text=original
    for name in ('console_neo.vg','neo.cst','neo.sdc'):
        old='add_file {'+str(PARENT/name)+'}'
        need(text.count(old)==1,'Missing unique input '+name)
        text=text.replace(old,'add_file {'+str(OUT/name)+'}')
    return text

def prepare():
    guard=guards();need(not OUT.exists(),'Candidate exists; no overwrite')
    net=gzip.decompress((HERE/'assembly_01/console_neo.vg.gz').read_bytes())
    need(hashlib.sha256(net).hexdigest()==NET_SHA,'Decompressed netlist differs')
    tcl=script();OUT.mkdir()
    (OUT/'console_neo.vg').write_bytes(net)
    for name in ('neo.cst','neo.sdc','font8x16.hex','rtl/video/font8x16.hex','rtl/usbhost/usb_hid_host_rom.hex'):
        target=OUT/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(PARENT/name,target)
    (OUT/'build.tcl').write_text(tcl);record_build(OUT,guard)
    save(OUT/'preparation.json',dict(candidate=True,board='neo',experiment='D128_COPY_DMA',
        hardware_access=False,netlist_sha256=NET_SHA,delivery_sha256=DELIVERY_SHA,
        script_sha256=sha(Path(__file__)),engine_sha256=ENGINE_SHA,tool_sha256=sha(IDE/'bin/gw_sh'),
        local_regressions=guard['local_regressions'],incremental=False,constraints_byte_identical=True,
        application_resynthesized=False,DDR_reset_frequency_changed=False,
        files={str(p.relative_to(OUT)):sha(p)for p in OUT.rglob('*')if p.is_file()},
        limits=['PNR frontend grammar pending single run.','Diagnostic, not a correction or hardware qualification.']))
    print('D128_PREPARED_NOT_ROUTED '+str(OUT),flush=True)

def check():
    guard=guards();record=json.loads((OUT/'preparation.json').read_text())
    for key,path in [('script_sha256',Path(__file__)),('engine_sha256',ENGINE),('tool_sha256',IDE/'bin/gw_sh')]:
        need(record[key]==sha(path),'Changed '+key)
    for name,digest in record['files'].items():need(sha(OUT/name)==digest,'Changed prepared input '+name)
    need((OUT/'build.tcl').read_text()==script(),'PNR settings changed')
    return guard

def run():
    check()
    spec=importlib.util.spec_from_file_location('frozen_single_route_engine',ENGINE)
    engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
    engine.OUT,engine.NET_SHA,engine.check=OUT,NET_SHA,check
    engine.run()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','check','run'))
    p.add_argument('--root-reviewed-single-pnr',action='store_true')
    a=p.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='check':check();print('D128_GUARDS_PASS')
    else:
        need(a.root_reviewed_single_pnr,'Explicit root review required; no automatic route')
        run()
