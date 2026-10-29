#!/usr/bin/env python3
"""Wait for the existing route3 and archive its review, never touch hardware.

Does not start, restart, stop, or change any compiler. Does not mark timing
or an observer audit PASS. The resulting evidence still needs human review.
"""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = ROOT / 'tang/impl/console_neo_n56r9_route3_scan_reset'
OUT = HERE / 'route3_followup'


def main():
    OUT.mkdir(exist_ok=False)
    report = dict(complete=False, hardware_access=False, compilation_started=False,
                  build=str(BUILD), commands=[], started=time.time())
    try:
        deadline = time.monotonic() + 3 * 3600
        while not (BUILD / 'automatic_checks.json').exists():
            if (BUILD / 'route_result.json').exists():
                route = json.loads((BUILD / 'route_result.json').read_text())
                if route['status'] == 'ROUTING_FAILED':
                    raise RuntimeError('Existing route3 failed; no candidate review possible')
            if time.monotonic() >= deadline:
                raise TimeoutError('Existing route3 has not completed its checks within three hours')
            time.sleep(15)
        commands = [
            ('reset_comparison', [sys.executable, str(HERE / 'audit_route3_scan_reset.py')]),
            ('workbench', [sys.executable, str(ROOT / 'optimizer/optimize.py'), 'report',
                           '--out', str(OUT / 'workbench'),
                           str(ROOT / 'tang/impl/console_neo_n56r9_route1'),
                           str(ROOT / 'tang/impl/console_neo_n56r9_route2'), str(BUILD),
                           '--board-results', str(HERE / 'r9_route2_rgb_observer/result.json')]),
        ]
        for name, command in commands:
            with (OUT / (name + '.log')).open('x') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=log, timeout=600)
            report['commands'].append(dict(name=name, returncode=result.returncode))
        q = json.loads((BUILD / 'qualification.json').read_text())
        report['qualification_status'] = q['status']
        report['timing_checks_ns'] = q['timing_checks_ns']
        report['bitstream_sha256'] = q['bitstream_sha256']
        report['automatic_checks'] = json.loads((BUILD / 'automatic_checks.json').read_text())
        report['complete'] = True
        report['review_required'] = True
    except Exception as error:
        report['error'] = str(error)
    finally:
        report['finished'] = time.time()
        (OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2), flush=True)
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
