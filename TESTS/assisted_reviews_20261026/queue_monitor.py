#!/usr/bin/env python3
"""Dispatch explicitly queued review packets; never edit sources or access boards."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODELS = {'minimax-m3.1-flash', 'deepseek-v4.1-flash', 'beam', 'fable'}
SUCCESS = 'COMPLETED_REVIEW_PENDING_VALIDATION'

def read_status(name):
    p = HERE / name / 'status.json'
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {'status': 'STATUS_WRITE_IN_PROGRESS'}

def validate(queue):
    names = set()
    assert type(queue['max_active']) is int and 1 <= queue['max_active'] <= 8
    for job in queue['jobs']:
        assert re.fullmatch('[a-z0-9_]+', job['name']) and job['name'] not in names
        names.add(job['name'])
        assert job['model'] in MODELS
        p = (ROOT / job['packet']).resolve()
        assert p.is_relative_to(ROOT) and p.suffix == '.txt' and p.is_file()
        assert hashlib.sha256(p.read_bytes()).hexdigest() == job['packet_sha256']
        assert isinstance(job['focus'], str) and 1 <= len(job['focus']) <= 2000
    for name in queue.get('watch', []):
        assert re.fullmatch('[a-z0-9_]+', name)
    known = names | set(queue.get('watch', []))
    done = set(queue.get('watch', []))
    for job in queue['jobs']:
        assert all(n in known and n != job['name'] for n in job.get('after', []))
    while done != known:
        next_done = done | {j['name'] for j in queue['jobs'] if set(j.get('after', [])) <= done}
        assert next_done != done, 'Cyclic dependencies'
        done = next_done
    return queue

def snapshot(queue):
    names = set(queue.get('watch', [])) | {j['name'] for j in queue['jobs']}
    states = {name: read_status(name) for name in sorted(names)}
    active = sum(v is not None and v['status'] in ('RUNNING', 'STARTING', 'STATUS_WRITE_IN_PROGRESS') for v in states.values())
    ready = [j for j in queue['jobs'] if states[j['name']] is None and not (HERE / j['name']).exists()
             and all(states[n] is not None and states[n]['status'] == SUCCESS for n in j.get('after', []))]
    return states, active, ready

def main():
    if sys.flags.optimize:
        raise SystemExit('Assertions required')
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--queue', type=Path, required=True)
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--idle-exit-seconds', type=int, default=3600)
    args = ap.parse_args()
    path = args.queue.resolve()
    assert path.is_relative_to(ROOT) and 1 <= args.idle_exit_seconds <= 43200
    queue = validate(json.loads(path.read_text()))
    if not args.run:
        states, active, ready = snapshot(queue)
        print(json.dumps({'active': active, 'ready': [j['name'] for j in ready], 'hardware_access': False}))
        return
    work = path.parent
    children = {}
    idle_since = None
    with (work / 'monitor.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            queue = validate(json.loads(path.read_text()))
            for name, (child, log) in list(children.items()):
                if child.poll() is not None:
                    log.close()
                    del children[name]
            states, active, ready = snapshot(queue)
            active = len({n for n, v in states.items() if v is not None and v['status'] in
                          ('RUNNING', 'STARTING', 'STATUS_WRITE_IN_PROGRESS')} | set(children))
            for job in ready[:max(0, queue['max_active'] - active)]:
                # Durable exclusive claim prevents duplicate billing on restart.
                claim = work / (job['name'] + '.claim')
                try:
                    with claim.open('x') as f:
                        json.dump({'claimed_unix': time.time(), 'job': job}, f)
                except FileExistsError:
                    continue
                log = (work / (job['name'] + '.log')).open('xb')
                command = [sys.executable, '-u', str(HERE / 'run_review.py'), '--model', job['model'],
                           '--packet', str(ROOT / job['packet']), '--name', job['name'], '--focus', job['focus']]
                child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                children[job['name']] = child, log
                print(json.dumps({'event': 'LAUNCHED', 'name': job['name'], 'model': job['model'], 'wrapper_pid': child.pid}), flush=True)
            states, active, ready = snapshot(queue)
            status = {'updated_unix': time.time(), 'monitor_pid': os.getpid(), 'active': active,
                      'ready': [j['name'] for j in ready], 'states': states,
                      'hardware_access': False, 'automatic_code_integration': False}
            tmp = work / 'monitor_status.tmp'
            tmp.write_text(json.dumps(status, indent=2) + '\n')
            tmp.replace(work / 'monitor_status.json')
            if not children and active == 0 and not ready:
                idle_since = idle_since or time.monotonic()
                if time.monotonic() - idle_since >= args.idle_exit_seconds:
                    print('QUEUE_IDLE: no prepared task remains', flush=True)
                    break
            else:
                idle_since = None
            time.sleep(2)

if __name__ == '__main__':
    main()
