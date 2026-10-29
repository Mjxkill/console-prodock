#!/usr/bin/env python3
"""Freeze a locally validated living valley and its complete RAM-only trial."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
TOOLS=REPO/'games/luma3d/tools'
sys.path.insert(0,str(TOOLS))
from build_delta import compress,delta
from prodock_valley_benchmark import fields

R3=REPO/'games/luma3d/build/frozen_20261024_r3_v2'
R3_SHA='131ff6d7ca404e0188bb7e0ff68c25bd2db29b52ae27c561e019f6c53dfcc270'


def digest(p):
    b=p.read_bytes()
    return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    p.add_argument('--tag',required=True)
    a=p.parse_args();build=a.build.resolve();out=a.out.resolve()
    import re
    assert re.fullmatch(r'vl[0-9]+',a.tag)
    frozen=json.loads((build/'manifest.json').read_text())
    validation=json.loads((build/'validation/result.json').read_text())
    assert validation['passed'] and validation['runtime']==frozen['riscv'] and not validation['hardware']
    for path,info in frozen['files'].items():
        actual=digest(build/'source'/path)
        assert actual['bytes']==info['bytes'] and actual['sha256']==info['sha256'],path
    assert digest(build/'luma3d-riscv')==frozen['riscv']
    baseline=digest(R3/'luma3d-riscv');assert baseline['sha256']==R3_SHA
    out.mkdir(parents=True,exist_ok=False)
    for name in ('prodock_valley_ab.py','prodock_valley_trial.py','prodock_valley_benchmark.py','prodock_transport.py','build_delta.py'):
        shutil.copy2(TOOLS/name,out/name)
    for name in ('check_linux.py','check_gpu_reloads.py'):
        shutil.copy2(REPO/'tools'/name,out/name)
    for name in ('prodock_living.py','prepare_hardware.py'):
        shutil.copy2(HERE/name,out/name)
    for name in ('runtime_inspect.c','test_runtime_inspect.py','test_hardware.py'):
        shutil.copy2(HERE/'tests'/name,out/name)
    shutil.copy2(build/'manifest.json',out/'game_manifest.json')
    shutil.copy2(build/'validation/result.json',out/'local_validation.json')
    source=build/'source';driver=source/'linux/drivers'
    shutil.copy2(driver/'prodock-uapi.h',out/'prodock-uapi.h')
    helper=a.tag+'-helper'
    flags=['-std=c11','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I'+str(out)]
    compile_commands=[]
    for cc,name,extra in [('cc','helper-host',[]),(str(REPO/'linux/build/userbin/riscv32-prodock-linux-gcc'),helper,['-static'])]:
        command=[cc,*flags,*extra,str(out/'runtime_inspect.c'),'-o',str(out/name)]
        subprocess.run(command,check=True);compile_commands.append(command)
    m=dict(candidate=True,hardware_tested=False,program='luma3d-'+a.tag,tag=a.tag,helper=helper,
           game=frozen['riscv'],baseline=baseline,validation=validation,scenes=[],
           compile_commands=compile_commands,transfer_files=[helper],
           scope='Six new fixed scenes plus comparable R3 initial scene; actual120s adventure, no same-content speedup or long-campaign claim')
    def reference(raw,name):
        ref=out/(name+'.raw');ref.write_bytes(raw);info=digest(ref);ref.unlink()
        file=name+'.lz4';(out/file).write_bytes(compress(raw))
        subprocess.run([str(out/'helper-host'),'verify',str(out/file),'unused',str(info['bytes']),info['crc32']],check=True,stdout=subprocess.DEVNULL)
        m['transfer_files'].append(file)
        return dict(file=file,**info)
    captures=out/'capture_work';captures.mkdir()
    # The missing initial-pose capture is made from the exact frozen executable.
    initial=captures/'arrival'
    subprocess.run([str(build/'luma3d-host'),'--host','--frames','1','--capture',str(initial)],check=True,stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable,str(HERE/'render_preview.py'),str(initial)],check=True,stdout=subprocess.DEVNULL)
    plans=[('r3',0,R3/'captures/frame_0')]+[('new',pose,prefix) for pose,prefix in [
        (0,initial),(90,build/'captures/maelle'),(1450,build/'captures/silo'),
        (2330,build/'captures/relay'),(3200,build/'captures/iria'),(3800,build/'captures/completion')]]
    for i,(variant,pose,prefix) in enumerate(plans):
        oracle=json.loads(prefix.with_suffix('.reference.json').read_text())
        ref=reference(prefix.with_suffix('.rgb565').read_bytes(),a.tag+'-p'+str(i))
        assert ref['bytes']==192000 and ref['sha256']==oracle['image_sha256']
        scene=dict(variant=variant,pose=pose,pixels=ref,oracle=oracle)
        if variant=='new':
            overlay=json.loads(prefix.with_suffix('.overlay.json').read_text())
            data=prefix.with_suffix('.memory').read_bytes();base=20<<20
            end=max(l[0]-0x800000+l[5]*(l[1]>>16) for l in overlay['layers'] if l[6]&1)
            assert base<end<=base+240000 and (end-base)%800==0
            scene['hud']=reference(data[base:end],a.tag+'-h'+str(i))
            run=subprocess.run([str(build/'luma3d-host'),'--host','--benchmark','--frames','30','--warmup','3','--advance',str(pose)],check=True,capture_output=True)
            (out/(a.tag+'-host-'+str(pose)+'.log')).write_bytes(run.stdout+run.stderr)
            scene['host_benchmark']=fields(run.stdout,'LUMA3D_RESULT')
            if pose==3800:m['completion_hud']=reference(data[base:base+800*44],a.tag+'-complete')
        m['scenes'].append(scene)
    old=(R3/'luma3d-riscv').read_bytes();new=(build/'luma3d-riscv').read_bytes();patch=delta(old,new)
    assert len(patch)<16<<20
    file=a.tag+'.delta.lz4';(out/file).write_bytes(compress(patch));m['transfer_files'].insert(1,file)
    m['delta']=dict(file=file,old_sha256=R3_SHA,new_sha256=frozen['riscv']['sha256'],new_bytes=len(new),
                    new_crc32=frozen['riscv']['crc32'],patch_bytes=len(patch),patch_crc32=f'{zlib.crc32(patch):08x}')
    with tempfile.TemporaryDirectory(prefix='luma-living-') as temp:
        # Helper explicitly permits only one /tmp filename, not subdirectories.
        rebuilt=Path('/tmp/'+Path(temp).name+'.elf')
        try:
            run=subprocess.run([str(out/'helper-host'),'patch',str(out/file),str(rebuilt),str(len(patch)),m['delta']['patch_crc32'],str(R3/'luma3d-riscv')],check=True,capture_output=True)
            assert digest(rebuilt)==m['game'];(out/'reconstruction.log').write_bytes(run.stdout+run.stderr)
        finally:
            if rebuilt.exists():rebuilt.unlink()
    assert digest(R3/'luma3d-riscv')==baseline
    # Keep original review captures in the game build; transport only references.
    shutil.rmtree(captures)
    m['files']={f.name:digest(f) for f in sorted(out.iterdir()) if f.is_file()}
    m['transport_bytes']=sum(m['files'][n]['bytes'] for n in m['transfer_files'])
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print(json.dumps(dict(game=m['game'],transport_bytes=m['transport_bytes'],manifest=digest(out/'manifest.json')),indent=2))


if __name__=='__main__':main()
