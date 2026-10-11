#!/usr/bin/env python3
"""Check the existing game's command stream against the actual Linux validators."""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from render_orbital import Scene, POSES, Info
class Present(ctypes.Structure):
    _fields_ = [('base', ctypes.c_uint), ('stride', ctypes.c_uint), ('format', ctypes.c_uint),
                ('layers_enabled', ctypes.c_uint), ('sprites_enabled', ctypes.c_uint),
                ('reserved', ctypes.c_uint * 3), ('layers', (ctypes.c_uint * 8) * 16),
                ('sprites', (ctypes.c_uint * 4) * 64)]
with tempfile.TemporaryDirectory(prefix='prodock_linux_api_') as tmp:
    work = Path(tmp)
    (work / 'validate.c').write_text('#include "prodock-validate.h"\n'
        'int command(const __u32 *p){return prodock_command(p);}\n'
        'int present(const struct prodock_scene *s){return prodock_scene_valid(s);}\n')
    subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                    '-I', str(ROOT / 'linux/drivers'), str(work / 'validate.c'),
                    '-o', str(work / 'validate.so')], check=True)
    lib = ctypes.CDLL(str(work / 'validate.so'))
    game = Scene(); count = 0
    for pose in POSES:
        commands = game.commands(pose)
        for c in commands:
            words = (ctypes.c_uint * 8)(*c)
            if lib.command(words): raise RuntimeError(f'rejected game command: pose={pose} words={list(c)}')
            count += 1
        s = Present(base=0x800000, stride=800, format=7, layers_enabled=1, sprites_enabled=1)
        info = Info()
        game.lib.layers(pose, 4, s.layers, s.sprites, ctypes.byref(info))
        result = lib.present(ctypes.byref(s))
        if result: raise RuntimeError(f'rejected game scene: pose={pose} errno={result}')
    print(json.dumps({'passed': True, 'poses': len(POSES), 'commands': count,
                       'note': 'Actual scene data and kernel validator; no physical GPU test'}))
