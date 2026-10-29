#!/usr/bin/env python3
"""Bounded register-only CAMERA discrimination; never issue DMA commands."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys

path = Path(__file__).resolve().parent.parent / 'n55_gpu_diagnosis_20261021/probe_config.py'
spec = importlib.util.spec_from_file_location('config_probe', path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

def camera_cases():
    suite = []
    for w, h, focal in ((160, 100, 80), (1, 1, 1), (32, 32, 32), (160, 100, 160)):
        label = f'{w}x{h}_f{focal}'
        suite.append(dict(name='target_'+label, accepted=True,
            words=[0x16000000, 0x00800000, 0x00900000, w<<16|h, 384<<16|384, 0, 0, 0]))
        for center in (0, 1):
            for repeat in range(2):
                suite.append(dict(name=f'camera_{label}_center{center}_repeat{repeat}', accepted=True,
                    words=[0x20000000, 0x4000, 0x500000, focal<<16, focal<<16,
                           ((w//2)<<16|(h//2)) if center else 0, w<<16|h, 0]))
    bad = suite[-1]['words'].copy()
    bad[1] = 0
    suite.append(dict(name='camera_invalid_near_zero', accepted=False, words=bad))
    if any(c['words'][0]>>24 not in (22, 32) or len(c['words']) != 8 for c in suite):
        raise ValueError('Not register-only camera diagnostics')
    return suite

probe.cases = camera_cases
probe.main()
# The original capture helper exits nonzero only for an incomplete capture.
# Keep its observations, but make this CAMERA test fail on wrong acceptance.
args = sys.argv[1:]
out = Path(args[args.index('--out')+1])
report_path = out / 'result.json'
report = json.loads(report_path.read_text())
report['camera_probe_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
report['camera_cases_sha256'] = hashlib.sha256(
    json.dumps(camera_cases(), sort_keys=True).encode()).hexdigest()
report_path.write_text(json.dumps(report, indent=2)+'\n')
if not report['all_expectations_match']:
    raise SystemExit('CAMERA acceptance differs from expectations; evidence retained')
