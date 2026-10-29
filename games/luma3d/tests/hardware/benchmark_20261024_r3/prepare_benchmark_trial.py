#!/usr/bin/env python3
"""Freeze the reviewed R2/R3 trial and prove native helper reconstruction locally."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid
import zlib

from build_delta import compress, delta
from prodock_valley_benchmark import EXPECTED, LIVE_SHA, POSES

GAME = Path(__file__).resolve().parents[1]
REPO = GAME.parents[1]


def digest(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), crc32=f'{zlib.crc32(raw):08x}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve(); out.mkdir(parents=True, exist_ok=False)
    previous = GAME/'tests/hardware/valley_20261024_r2'
    old_path = GAME/'build/frozen_20261024_r2/luma3d-riscv'
    assert digest(old_path)['sha256'] == LIVE_SHA
    old = old_path.read_bytes()
    for name in ('prodock_valley_benchmark.py', 'prodock_valley_ab.py', 'prodock_valley_trial.py',
                 'prodock_transport.py', 'build_delta.py', 'prepare_benchmark_trial.py'):
        shutil.copy2(GAME/'tools'/name, out/name)
    for name in ('runtime-helper-r2', 'runtime_helper.c'):
        shutil.copy2(previous/name, out/name)
    for name in ('check_linux.py', 'check_gpu_reloads.py'):
        shutil.copy2(REPO/'tools'/name, out/name)
    for name in ('test_valley_benchmark.py', 'test_render_contract.py'):
        shutil.copy2(GAME/'tests'/name, out/name)
    helper = out/'runtime-helper-host'
    subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
                    '-I'+str(REPO/'linux/drivers'), str(out/'runtime_helper.c'), '-o', str(helper)], check=True)
    manifest = dict(candidate=True, hardware_tested=False, live_sha256=LIVE_SHA,
                    helper=digest(out/'runtime-helper-r2'), programs={},
                    shared_tools={name:digest(out/name)['sha256'] for name in ('check_linux.py', 'check_gpu_reloads.py')},
                    scope='R2/R3 four fixed poses, 30 measured frames +3 warmup; 75s automatic endurance; leave R3 visible or restore exact R2')
    assert manifest['helper']['sha256'] == '579d5a85fb798950f2f249299299c1084ce873c288d769c4b87fa539842563c9'
    for key, folder in (('r2', args.baseline.resolve()), ('r3', args.candidate.resolve())):
        frozen = json.loads((folder/'manifest.json').read_text())
        for name, record in frozen['files'].items():
            info = digest(folder/'source'/name)
            assert info['sha256'] == record['sha256'] and info['bytes'] == record['bytes'], name
        info = digest(folder/'luma3d-riscv')
        assert info == frozen['riscv'] and info['sha256'] == EXPECTED[key]
        shutil.copy2(folder/'manifest.json', out/(key+'_game_manifest.json'))
        new = (folder/'luma3d-riscv').read_bytes()
        raw = delta(old, new)
        assert len(raw) <= 16 << 20
        delta_name = f'l3v2-{key}.delta.lz4'
        (out/delta_name).write_bytes(compress(raw))
        patch = dict(file=delta_name, old_sha256=LIVE_SHA, new_sha256=info['sha256'],
                     new_bytes=info['bytes'], new_crc32=info['crc32'],
                     patch_bytes=len(raw), patch_crc32=f'{zlib.crc32(raw):08x}', transport_bytes=(out/delta_name).stat().st_size)
        rebuilt = Path('/tmp/l3-benchmark-rebuilt-'+uuid.uuid4().hex)
        try:
            result = subprocess.run([str(helper), 'patch', str(out/delta_name), str(rebuilt),
                str(len(raw)), patch['patch_crc32'], str(old_path)], check=True, capture_output=True)
            assert digest(rebuilt) == info and digest(old_path)['sha256'] == LIVE_SHA
            (out/(key+'_reconstruction.log')).write_bytes(result.stdout+result.stderr)
        finally:
            if rebuilt.exists(): rebuilt.unlink()
        references = {}
        for pose in POSES:
            image = folder/'captures'/f'frame_{pose}.rgb565'
            reference = digest(image)
            assert reference['bytes'] == 192000
            assert reference['sha256'] == frozen['captures'][f'frame_{pose}']['image_sha256']
            name = f'l3v2-{key}-p{pose}.lz4'
            (out/name).write_bytes(compress(image.read_bytes()))
            subprocess.run([str(helper), 'verify', str(out/name), 'unused', '192000', reference['crc32']],
                           check=True, stdout=subprocess.DEVNULL)
            references[str(pose)] = dict(file=name, **reference)
        manifest['programs'][key] = dict(name='luma3d-b2v2' if key == 'r2' else 'luma3d-b3v2',
                                        **info, delta=patch, references=references)
        print(key, 'ELF', info['sha256'], 'delta bytes', patch['transport_bytes'], flush=True)
    manifest['files'] = {p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()}
    manifest['local_reconstruction_and_references'] = True
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('Bundle', out, 'manifest', digest(out/'manifest.json')['sha256'])


if __name__ == '__main__':
    main()
