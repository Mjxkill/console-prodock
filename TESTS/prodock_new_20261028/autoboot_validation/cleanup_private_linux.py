#!/usr/bin/env python3
"""Remove only inventoried private duplicate trees; keep all evidence artefacts.

Root explicitly authorised this task cleanup. No protected reference, hardware,
SD, other project's process or final build is touched. Revalidate identities
before deletion; refuse unrecognised private source changes.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil

HERE=Path(__file__).resolve().parent
ROOT=next(p for p in HERE.parents if (p/'ARCHI/COMPATIBILITE_CARTES.md').is_file())
C=ROOT/'games/luma3d/candidates/autoboot_linux_20261028_r1'
BASE=ROOT/'games/luma3d/build-kernel/prodock_g3d1_20261024_r1'


def meta(p):
    d=p.read_bytes();return {'bytes':len(d),'sha256':hashlib.sha256(d).hexdigest()}


def inventory(path):
    result={}
    for root,dirs,files in os.walk(path,followlinks=False):
        for name in files+list(dirs):
            p=Path(root)/name;n=str(p.relative_to(path))
            if p.is_symlink():result[n]={'symlink':os.readlink(p)}
            elif p.is_file():result[n]=meta(p)
    return result


def delivered():
    for root in [C,ROOT/'games/luma3d/candidates/sd_install_20261028_r1']:
        m=json.loads((root/'DELIVERY.json').read_text())
        for n,v in m['files'].items():assert meta(root/n)==v,n
    # Final build files and protected historical files are never cleanup targets.
    for root in (C/'build_r3',BASE):
        m=json.loads((root/'manifest.json').read_text())
        for n,v in m['files'].items():assert meta(root/n)==v,n


def main():
    report=HERE/'cleanup_linux_result.json';assert not report.exists()
    delivered()
    frozen=json.loads((BASE/'provenance/kernel_source_files.json').read_text())
    final_small={n:inventory(C/'build_r3'/n) for n in ('busybox-source','launcher-source')}
    plans=[]
    for build in ('build_r1','build_r2'):
        root=C/build
        for sub,reference in [('source',frozen),*final_small.items()]:
            path=root/sub
            assert path.is_dir() and not path.is_symlink() and path.resolve().is_relative_to(C)
            actual=inventory(path);assert actual==reference,(build,sub,'unexpected private edit')
            plans.append((path,actual))
    # Retain exact historical failing Image/config/release/BusyBox in place.
    keep={'kernel':{'arch/riscv/boot/Image','.config','include/config/kernel.release'},'busybox':{'busybox','.config'}}
    kept={}
    for build in ('build_r1','build_r2'):
        for sub,names in keep.items():
            for n in names:kept[str((C/build/sub/n).relative_to(C))]=meta(C/build/sub/n)
    rows=[]
    for path,files in plans:
        rows.append({'path':str(path.relative_to(C)),'removed_entries':len(files),'removed_apparent_bytes':sum(v.get('bytes',0) for v in files.values()),'duplicate_source_verified':True})
        shutil.rmtree(path)
    for build in ('build_r1','build_r2'):
        for sub,names in keep.items():
            path=C/build/sub;count=total=0
            for root,dirs,files in os.walk(path,topdown=False,followlinks=False):
                for name in files:
                    p=Path(root)/name
                    if str(p.relative_to(path)) in names:continue
                    if not p.is_symlink():total+=p.stat().st_size
                    p.unlink();count+=1
                for name in dirs:
                    p=Path(root)/name
                    if p.is_symlink():p.unlink();count+=1
                    elif not any(p.iterdir()):p.rmdir()
            rows.append({'path':str(path.relative_to(C)),'removed_entries':count,'removed_apparent_bytes':total,'kept':sorted(names)})
    for n,v in kept.items():assert meta(C/n)==v,n
    delivered()
    result={'passed':True,'hardware':False,'scope':'own failed private LinuxR1/R2 only','rows':rows,'removed_apparent_bytes':sum(r['removed_apparent_bytes'] for r in rows),'retained':kept,'deliveries_and_frozen_reference_verified_after':True,'notes':['Apparent file bytes, not claimed physical free-space recovery (reflinks and concurrent host workloads).','All failed Image/rootfs/config/log/proof files stay; final build_r3 and historical source remain intact.','Original cleanup_inventory.json is unchanged historical intent; this result records actual removal.']}
    report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'removed_apparent_bytes':result['removed_apparent_bytes'],'entries':sum(r['removed_entries'] for r in rows)}))

if __name__=='__main__':main()
