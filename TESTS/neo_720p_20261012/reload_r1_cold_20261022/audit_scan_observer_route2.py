#!/usr/bin/env python3
"""Run the unchanged strict observer audit against N56r9_route2 only."""
import argparse
import json
from pathlib import Path
import time

import audit_scan_observer as observer
from route_scan_observer_placement import OUT, NETSHA, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wait', action='store_true')
    args = parser.parse_args()
    if args.wait:
        end = time.monotonic()+7200
        while not (OUT/'automatic_checks.json').exists():
            result = OUT/'route_result.json'
            if result.exists() and json.loads(result.read_text())['status'] == 'ROUTING_FAILED':
                raise SystemExit('Routing failed; observer audit not possible')
            if time.monotonic() >= end:
                raise SystemExit('Timeout waiting for route2 qualification')
            time.sleep(15)
    assert OUT.name == 'console_neo_n56r9_route2'
    assert sha(OUT/'console_neo.vg') == NETSHA
    observer.OUT = OUT
    report = observer.audit()
    report['sha256'][str(Path(__file__).resolve())] = sha(Path(__file__))
    report['build'] = str(OUT)
    with (OUT/'scan_observer_audit.json').open('x') as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({k: report[k] for k in ('passed', 'errors', 'register_counts', 'hardware_access')}, indent=2), flush=True)
    if not report['passed']:
        raise SystemExit('Observer audit failed; review required, no automatic waiver')


if __name__ == '__main__':
    main()
