#!/usr/bin/env python3
"""Freeze R3/R4 transport with exact source, ELF and image identities; no board."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid
import zlib
from build_delta import compress, delta
from prodock_valley_r4 import R3_SHA, R4_SHA, R3_PROGRAM, R4_PROGRAM, HELPER
from prodock_valley_benchmark import POSES

GAME = Path(__file__).resolve().parents[1]
REPO = GAME.parents[1]


def digest(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), crc32=f'{zlib.crc32(raw):08x}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); out = a.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    previous = GAME/'tests/hardware/valley_20261024_r2'
    for name in ('prodock_valley_r4.py', 'prodock_valley_benchmark.py', 'prodock_valley_ab.py',
                 'prodock_valley_trial.py', 'prodock_transport.py', 'build_delta.py', 'prepare_benchmark_r4.py'):
        shutil.copy2(GAME/'tools'/name, out/name)
    shutil.copy2(previous/'runtime-helper-r2', out/HELPER)
    shutil.copy2(previous/'runtime_helper.c', out/'runtime_helper.c')
    for name in ('check_linux.py', 'check_gpu_reloads.py'):
        shutil.copy2(REPO/'tools'/name, out/name)
    for name in ('test_valley_r4.py', 'test_render_contract.py'):
        shutil.copy2(GAME/'tests'/name, out/name)
    helper = out/'runtime-helper-host'
    subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
                    '-I'+str(REPO/'linux/drivers'), str(out/'runtime_helper.c'), '-o', str(helper)], check=True)
    assert digest(out/HELPER)['sha256'] == '579d5a85fb798950f2f249299299c1084ce873c288d769c4b87fa539842563c9'
    manifest = dict(candidate=True, hardware_tested=False, live_sha256=R3_SHA, programs={},
                    shared_tools={name:digest(out/name)['sha256'] for name in ('check_linux.py', 'check_gpu_reloads.py')},
                    scope='R3/R4 same four poses30+3; eight pixel comparisons;75s endurance; R4 only if significant gain, otherwise R3')
    for key, folder, expected, program in (('r3', a.baseline.resolve(), R3_SHA, R3_PROGRAM),
                                          ('r4', a.candidate.resolve(), R4_SHA, R4_PROGRAM)):
        frozen = json.loads((folder/'manifest.json').read_text())
        for name, record in frozen['files'].items():
            actual = digest(folder/'source'/name)
            assert actual['sha256'] == record['sha256'] and actual['bytes'] == record['bytes'], name
        info = digest(folder/'luma3d-riscv')
        assert info == frozen['riscv'] and info['sha256'] == expected
        shutil.copy2(folder/'manifest.json', out/(key+'_game_manifest.json'))
        references = {}
        for pose in POSES:
            image = folder/'captures'/f'frame_{pose}.rgb565'
            ref = digest(image)
            assert ref['bytes'] == 192000 and ref['sha256'] == frozen['captures'][f'frame_{pose}']['image_sha256']
            name = f'l3v2-r3-p{pose}.lz4' if key == 'r3' else f'l3r4-r4-p{pose}.lz4'
            (out/name).write_bytes(compress(image.read_bytes()))
            subprocess.run([str(helper), 'verify', str(out/name), 'unused', '192000', ref['crc32']],
                           check=True, stdout=subprocess.DEVNULL)
            references[str(pose)] = dict(file=name, reuse_remote=key == 'r3', **ref)
        manifest['programs'][key] = dict(name=program, **info, references=references)
    old_path = a.baseline.resolve()/'luma3d-riscv'
    old = old_path.read_bytes(); new = (a.candidate.resolve()/'luma3d-riscv').read_bytes()
    raw = delta(old, new); assert len(raw) <= 16 << 20
    name = 'l3r4.delta.lz4'; (out/name).write_bytes(compress(raw))
    info = manifest['programs']['r4']
    patch = dict(file=name, old_sha256=R3_SHA, new_sha256=R4_SHA, new_bytes=info['bytes'],
                 new_crc32=info['crc32'], patch_bytes=len(raw), patch_crc32=f'{zlib.crc32(raw):08x}',
                 transport_bytes=(out/name).stat().st_size)
    manifest['programs']['r4']['delta'] = patch
    rebuilt = Path('/tmp/l3-r4-rebuilt-'+uuid.uuid4().hex)
    try:
        result = subprocess.run([str(helper), 'patch', str(out/name), str(rebuilt), str(len(raw)),
            patch['patch_crc32'], str(old_path)], check=True, capture_output=True)
        assert digest(rebuilt)['sha256'] == R4_SHA and digest(old_path)['sha256'] == R3_SHA
        (out/'r4_reconstruction.log').write_bytes(result.stdout+result.stderr)
    finally:
        if rebuilt.exists(): rebuilt.unlink()
    manifest['local_reconstruction_and_references'] = True
    manifest['files'] = {f.name:digest(f) for f in sorted(out.iterdir()) if f.is_file()}
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('R4 delta bytes', patch['transport_bytes'])
    print('Manifest', digest(out/'manifest.json')['sha256'])


if __name__ == '__main__':
    main()
