#!/usr/bin/env python3
"""Reproduce a pre-write consistency gap with a deterministic file-mutation hook.

No hardware. The native raw-route check succeeds on real bytes, then the hook
changes one preserved-tail byte before the plan captures its image digest.
The fake runner records that wrong image was submitted. Full readback detects
it later: this is NOT a false final integrity PASS.
"""
from pathlib import Path
import json
import sys
import tempfile
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
WRITER = BASE.parent / 'prepared'
sys.path.insert(0, str(WRITER))
import flash_write as writer
from fixture_factory import Fixture, sha, BACKUP


def reproduce():
    with tempfile.TemporaryDirectory() as tmp:
        f = Fixture(tmp, WRITER)
        out = f.tests / 'prepared'
        original = writer.proofs.check_raw_route
        def route_then_mutate(bitstream, image):
            record = original(bitstream, image)
            data = bytearray(image.read_bytes())
            data[65535] ^= 0x80
            image.write_bytes(data)
            return record
        with patch.object(writer.proofs, 'check_raw_route', side_effect=route_then_mutate):
            plan = writer.prepare(f.request, sha(f.request), out, root=f.root)
        image = Path(plan['image']['path']).read_bytes()
        offline = json.loads(Path(plan['offline_report']['path']).read_text())
        f.after = image + BACKUP[len(image):]
        result = writer.execute(out/'plan.json', sha(out/'plan.json'), f.tests/'run',
            root=f.root, runner=f.runner, guard_factory=lambda root:f.guard())
        return dict(hardware_access=False,
            source_sha256=sha(WRITER/'flash_write.py'),
            scope='Mutation after successful native route check, before plan image SHA.',
            plan_image_sha256=plan['image']['sha256'],
            offline_program_sha256=offline['program_sha256'],
            hashes_differ=plan['image']['sha256'] != offline['program_sha256'],
            program_attempted=result['program_attempted'],
            full_readback_matches=result['full_readback_matches'],
            status=result['status'], runner_calls=len(f.calls), result_error=result.get('error'))


if __name__ == '__main__':
    result = reproduce()
    print(json.dumps(result, indent=2))
    assert result['hashes_differ']
    assert result['program_attempted'] and result['runner_calls'] == 2
    assert result['status'] == 'failed' and result['full_readback_matches'] is False
