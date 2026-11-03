"""Reusable data/qualification adapter for the frozen D128 routing machinery.

The parent builder owns all prepare/check/run operations. This module adds only
reviewed candidate data and proof guards, preserving historical variants.
"""
import argparse,importlib.util,json
from pathlib import Path
import build
HERE=Path(__file__).resolve().parent;ROOT=build.ROOT
BASE=HERE/'route_d128.py';BASE_SHA='0f6713985db84091ec85d99d696d2cbd01f95f905f35a991bab0674739e29ca7'

def configured(entry,data,out,net_sha,delivery_sha):
    build.need(build.sha(BASE)==BASE_SHA,'Frozen builder changed')
    spec=importlib.util.spec_from_file_location('frozen_route_variant_base',BASE)
    base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
    original=(base.HERE,base.NET_SHA,base.DELIVERY_SHA)
    parent_guard,parent_check=base.guards,base.check
    def guards():
        selected=(base.HERE,base.NET_SHA,base.DELIVERY_SHA)
        base.HERE,base.NET_SHA,base.DELIVERY_SHA=original
        try:contract=parent_guard()
        finally:base.HERE,base.NET_SHA,base.DELIVERY_SHA=selected
        path=data/'MAPPED_DELIVERY.json';build.need(build.sha(path)==delivery_sha,'Variant delivery changed')
        d=json.loads(path.read_text());build.need(d['netlist_sha256']==net_sha,'Wrong candidate')
        for name,digest in d['files'].items():
            p=ROOT/name;build.need(p.resolve().is_relative_to(ROOT)and not p.is_symlink(),'Unsafe proof')
            build.need(build.sha(p)==digest,'Changed variant input '+name)
        q=json.loads((ROOT/d['qualification']).read_text())
        build.need(q['passed']and q['netlist_sha256']==net_sha,'Independent qualification missing')
        return contract
    def check():
        contract=parent_check();r=json.loads((out/'preparation.json').read_text())
        build.need(r['variant_entry_sha256']==build.sha(entry),'Variant entry changed')
        build.need(r['variant_runner_sha256']==build.sha(Path(__file__)),'Variant runner changed')
        return contract
    base.HERE,base.NET_SHA,base.DELIVERY_SHA,base.OUT=data,net_sha,delivery_sha,out
    base.guards,base.check=guards,check
    return base

def main(entry,data,out,net_sha,delivery_sha):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','check','run'))
    p.add_argument('--root-reviewed-single-pnr',action='store_true');a=p.parse_args()
    base=configured(entry,data,out,net_sha,delivery_sha)
    if a.action=='prepare':
        base.prepare();r=json.loads((out/'preparation.json').read_text())
        r.update(variant_entry_sha256=build.sha(entry),variant_runner_sha256=build.sha(Path(__file__)),application_proof='Independent qualified candidate delta; historical incomplete34916proof superseded')
        build.save(out/'preparation.json',r)
    elif a.action=='check':base.check();print('D128_VARIANT_GUARDS_PASS')
    else:
        build.need(a.root_reviewed_single_pnr,'Explicit root review required');base.run()
