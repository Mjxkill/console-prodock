#!/usr/bin/env python3
"""Predict one further N38 perspective draw before collecting it on the board."""
import hashlib
import itertools
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'TESTS'))
from test_gpu_v1 import Model, signed16
from test_gpu_accel import triangle_pixels

area = ROOT/'TESTS/neo_720p_20261012'
vectors = area/'n38_pixel_cases_validated_20261020'
captures = area/'n38_pixel_board_20261020'
history = ['solid', 'alpha', 'depth', 'textured', 'perspective']
mask, buffer, selector = set(), bytearray(32), 0
dividers = [None, None]
proofs = []
sha = lambda data: hashlib.sha256(data).hexdigest()
for index, name in enumerate(history+['perspective']):
    source = vectors/name
    words = [int(w,16) for w in (source/'commands.hex').read_text().split()]
    m = Model()
    m.memory[:] = bytes.fromhex((source/'initial.hex').read_text())
    expected = bytes.fromhex((source/'expected.hex').read_text())
    for start in range(0,len(words)-8,8):
        m.apply(words[start:start+8])
    if words[-8] != 27<<24 or m.base != 0x800000 or m.stride != 160:
        raise ValueError('Changed diagnostic')
    points = [(signed16(w>>16),signed16(w)) for w in words[-7:-4]]
    pixels = list(triangle_pixels(*sum(([x,y] for x,y in points),[]),width=m.width,height=m.height))
    initial_selector = selector
    for (y,chunk), group in itertools.groupby(pixels,lambda xy:(xy[1],xy[0]//16)):
        group = list(group)
        flags, alpha = m.mat[:2]
        offset = y*m.stride+chunk*32
        if alpha != 256 or flags&32 or (flags&1 and m.tex[4]):
            buffer[:] = m.memory[offset:offset+32]
        if flags&16:
            if (m.planes != {0:(0,65536,0),1:(0,0,65536),2:(65536,0,0)}
                    or flags != 17 or alpha != 256 or m.mat[3] != (256,256,256)
                    or m.tex[1:] != (16,16,32,False,1,1,0)):
                raise ValueError('Only the constant-Q, unit-tint wrapped RGB565 case is modeled')
            dividers[0] = group[0]
            if len(group)>1:
                dividers[1] = (group[0][0]+1,y)
        for pixel_index,(x,_) in enumerate(group):
            lane = x%16
            mask.add(lane)
            if flags&16:
                if dividers[selector] is None:
                    raise ValueError('Uninitialized stale divider outside model')
                sample_x,sample_y = dividers[selector]
                value = m.get(m.tex[0]+(sample_y%16)*32+(sample_x%16)*2)
                color = value.to_bytes(2,'little')
                if len(group)-pixel_index>2:
                    dividers[selector] = (x+2,y)
            else:
                at = y*m.stride+x*2
                color = expected[at:at+2]
            buffer[lane*2:lane*2+2] = color
            selector ^= 1
        for lane in mask:
            m.memory[offset+lane*2:offset+lane*2+2] = buffer[lane*2:lane*2+2]
    prediction = bytes(m.memory[:16384])
    if index<len(history):
        actual = (captures/name/'actual_0.bin').read_bytes()
        if prediction != actual:
            raise ValueError('Prior sequence no longer reproduced: '+name)
        proofs.append(dict(case=name,capture_sha256=sha(actual)))
    else:
        out = Path(__file__).parent/'next_perspective_prediction.bin'
        with out.open('xb') as stream:
            stream.write(prediction)
        record = dict(prepared_utc=datetime.now(timezone.utc).isoformat(),history=proofs,
            predicted_case=name,selector_at_start=initial_selector,bytes_predicted=len(prediction),
            predicted_sha256=sha(prediction),oracle_sha256=sha(expected[:16384]),
            predicted_bad_bytes=sum(a!=b for a,b in zip(prediction,expected)),
            differs_from_last_capture=prediction!=(captures/name/'actual_0.bin').read_bytes(),
            premise='Same N38 bitstream, no FPGA reset or intervening draw since captured history; missing shared CHUNK clear.',
            prediction_uses_future_capture=False,
            limitation='Observable fault model; physical cause unproven. Color prefix only.',
            script_sha256=sha(Path(__file__).read_bytes()))
        out.with_suffix('.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(record,indent=2))
