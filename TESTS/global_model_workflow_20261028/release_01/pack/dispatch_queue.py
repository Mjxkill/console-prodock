#!/usr/bin/env python3
"""Session-local dispatcher; name deliberately avoids shadowing stdlib queue.

Based on a DeepSeek implementation proposal, with transaction, fresh-output,
cycle and restart defects corrected. Unknown claims require independent review;
on_terminal means a known completion, never an ambiguous live subprocess.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time

from workflow_common import atomic_json, identifier, need, parse_utc, prepared_text, process_start_ticks, safe_path, utc_now

MODELS = {'deepseek-v4.1-flash', 'glm-5.3-flash', 'minimax-m3.1-flash', 'beam'}
SUCCESS = 'COMPLETED_REVIEW_PENDING_VALIDATION'
FAILURES = {'FAILED', 'INCOMPLETE_LENGTH', 'TIMEOUT', 'INTERRUPTED'}
TERMINAL = FAILURES | {SUCCESS, 'BLOCKED_DEPENDENCY'}
ALL_STATES = TERMINAL | {'PENDING', 'CLAIMED', 'RUNNING', 'NEEDS_REVIEW', 'BLOCKED_UNRESOLVED'}
NAME = re.compile(r'[a-z0-9_]{1,80}')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_queue(document, project, allow_claude=False):
    """Reject ambiguous jobs, mutable packets, unknown dependencies and cycles."""
    need(isinstance(document, dict) and document.get('schema') == 1, 'Invalid queue schema')
    maximum = document.get('max_active')
    need(type(maximum) is int and 1 <= maximum <= 8, 'Invalid concurrency bound')
    jobs = document.get('jobs')
    need(isinstance(jobs, list) and len(jobs) <= 10000, 'Invalid job list')
    tasks, runs = set(), set()
    for job in jobs:
        need(isinstance(job, dict), 'Job must be an object')
        for name, known in (('task_id', tasks), ('run_id', runs)):
            value = job.get(name)
            need(isinstance(value, str) and NAME.fullmatch(value) and value not in known, 'Invalid/duplicate ' + name)
            known.add(value)
        model = job.get('model')
        if model == 'claude':
            need(allow_claude and document.get('allow_claude') is True, 'Claude needs explicit queue and CLI opt-in')
            need(isinstance(job.get('claude_model'), str) and NAME.fullmatch(job['claude_model']), 'Missing Claude model')
        else:
            need(model in MODELS, 'Unknown model')
        for key, limit in (('domain', 200), ('task_type', 200), ('acceptance_criteria', 8000)):
            need(isinstance(job.get(key), str) and 0 < len(job[key]) <= limit, 'Missing task metadata ' + key)
        need(job.get('difficulty', 'unspecified') in ('low', 'medium', 'high', 'unspecified'), 'Invalid difficulty')
        need(type(job.get('priority', 0)) is int, 'Invalid priority')
        relative = Path(job.get('packet', ''))
        need(not relative.is_absolute() and '..' not in relative.parts, 'Packet path escape')
        packet, unused = prepared_text(project, relative)
        need(file_sha(packet) == job.get('packet_sha256'), 'Packet SHA changed')
        need(isinstance(job.get('focus', ''), str) and len(job.get('focus', '')) <= 4000, 'Invalid focus')
        for optional in ('parent_task_id', 'dataset', 'task_family'):
            need(optional not in job or isinstance(job[optional], str), 'Invalid optional metadata')
        if job.get('parent_task_id'):
            identifier(job['parent_task_id'])
        if 'queued_at' in job:
            need(parse_utc(job['queued_at']) <= parse_utc(utc_now()), 'Future enqueue time')
        need(type(job.get('max_output_tokens', 65536)) is int and 512 <= job.get('max_output_tokens', 65536) <= 131072, 'Invalid output cap')
        need(job.get('reasoning_effort', 'unspecified') in ('low', 'medium', 'high', 'unspecified'), 'Invalid reasoning option')
        need(job.get('reasoning_effort', 'unspecified') == 'unspecified' or model == 'deepseek-v4.1-flash', 'Reasoning option unsupported for selected adapter')
        dependencies = job.get('after', [])
        need(isinstance(dependencies, list), 'Dependencies must be a list')
        for dependency in dependencies:
            need(isinstance(dependency, dict) and dependency.get('condition') in ('on_success', 'on_terminal'), 'Invalid dependency condition')
    graph = {}
    for job in jobs:
        graph[job['task_id']] = [item.get('task_id') for item in job.get('after', [])]
        need(all(name in tasks and name != job['task_id'] for name in graph[job['task_id']]), 'Unknown/self dependency')
    done = set()
    while len(done) != len(tasks):
        available = {name for name, dependencies in graph.items() if set(dependencies) <= done}
        need(available - done, 'Cyclic dependencies')
        done |= available
    return document


def load_state(session):
    path = safe_path(session / 'state.json', exists=False)
    return json.loads(path.read_text()) if path.exists() else None


def runner_status(session, job):
    """Bind the terminal record to this exact job; never adopt a foreign output."""
    path = safe_path(session / 'runs' / job['run_id'] / 'status.json', exists=False)
    if not path.exists():
        return None
    need(path.stat().st_size <= 2 << 20, 'Runner status too large')
    value = json.loads(path.read_text())
    need(isinstance(value, dict) and value.get('run_id') == job['run_id'] and value.get('task_id') == job['task_id'], 'Runner identity differs')
    expected_model = job.get('claude_model') if job['model'] == 'claude' else job['model']
    need(value.get('model') == expected_model and value.get('input_sha256') == job['packet_sha256'], 'Runner source/model differs')
    if value.get('status') == SUCCESS:
        # Model exit_code alone excludes the subsequent registry import. After
        # a monitor restart, adopt success only from its bound completion proof.
        proof_path = safe_path(path.parent / 'registry_import.json', exists=False)
        if not proof_path.exists():
            return dict(value, status='NEEDS_REVIEW')
        metrics_path = safe_path(path.parent / 'metrics.json')
        need(proof_path.stat().st_size <= 2 << 20 and metrics_path.stat().st_size <= 2 << 20, 'Runner completion proof too large')
        proof = json.loads(proof_path.read_text())
        need(type(proof.get('passed')) is bool and proof.get('metrics_sha256') == file_sha(metrics_path), 'Unbound registry completion')
        need(json.loads(metrics_path.read_text()) == value, 'Status and final metrics differ')
        if not proof['passed'] or value.get('work_cleanup') == 'failed':
            return dict(value, status='FAILED')
    return value


def completed_status(document, returncode):
    """Preserve explicit truncation/failure; a nonzero exit never means success."""
    status = document.get('status') if isinstance(document, dict) else None
    if status in FAILURES:
        return status
    if returncode != 0:
        return 'FAILED'
    if status == SUCCESS and document.get('exit_code') == 0 and not document.get('truncated'):
        return SUCCESS
    return 'NEEDS_REVIEW'


def reconcile(document, state, project, session):
    """Allow append-only queue changes; never automatically relaunch a claim."""
    if state is None:
        state = dict(schema=1, project=str(project), jobs={})
    need(isinstance(state, dict) and state.get('schema') == 1 and state.get('project') == str(project) and isinstance(state.get('jobs'), dict), 'Invalid session state')
    old = state['jobs']
    current_ids = {job['task_id'] for job in document['jobs']}
    need(set(old) <= current_ids, 'Removing historical jobs requires a new session')
    for job in document['jobs']:
        name = job['task_id']
        if name not in old:
            old[name] = dict(status='PENDING', spec=job.copy(), spec_sha256=digest(job), queued_at=job.get('queued_at', utc_now()))
            continue
        row = old[name]
        need(isinstance(row, dict) and row.get('spec_sha256') == digest(job), 'Historical job changed')
        if row.get('status') not in ALL_STATES:
            row.update(status='NEEDS_REVIEW', error='invalid_persisted_status')
        if row['status'] in ('CLAIMED', 'RUNNING'):
            try:
                observed = runner_status(session, job)
                if observed and observed.get('status') in FAILURES | {SUCCESS} and type(observed.get('exit_code')) is int:
                    row.update(status=completed_status(observed, observed['exit_code']), exit_code=observed['exit_code'])
                else:
                    row.update(status='NEEDS_REVIEW', error='unresolved_claim_no_relaunch')
            except (OSError, ValueError):
                row.update(status='NEEDS_REVIEW', error='unresolved_claim_invalid_status')
    state['queue_sha256'] = digest(document)
    return state


def settle(state):
    """Make failed/unknown dependencies explicit rather than idling forever."""
    changed = True
    while changed:
        changed = False
        for row in state['jobs'].values():
            if row['status'] != 'PENDING':
                continue
            for dependency in row['spec'].get('after', []):
                previous = state['jobs'][dependency['task_id']]['status']
                if previous in ('NEEDS_REVIEW', 'BLOCKED_UNRESOLVED'):
                    row.update(status='BLOCKED_UNRESOLVED', error='Dependency completion is unknown')
                elif previous in TERMINAL and dependency['condition'] == 'on_success' and previous != SUCCESS:
                    row.update(status='BLOCKED_DEPENDENCY', error='Dependency did not succeed')
                if row['status'] != 'PENDING':
                    changed = True
                    break


def ready(row, state):
    if row['status'] != 'PENDING':
        return False
    for dependency in row['spec'].get('after', []):
        previous = state['jobs'][dependency['task_id']]['status']
        if previous not in TERMINAL or (dependency['condition'] == 'on_success' and previous != SUCCESS):
            return False
    return True


def start_job(state, row, project, session, runner, runner_sha, credential_file=None, registry=None):
    """Persist a claim before Popen; output creation belongs solely to runner."""
    job = row['spec']
    output = safe_path(session / 'runs' / job['run_id'], exists=False)
    log_path = safe_path(session / 'logs' / (job['run_id'] + '.log'), exists=False)
    log = None
    child = None
    try:
        need(not output.exists(), 'Output already exists')
        need(file_sha(runner) == runner_sha, 'Runner changed before launch')
        # Packets are checked again immediately before launch, not only at start.
        path, unused = prepared_text(project, job['packet'])
        need(file_sha(path) == job['packet_sha256'], 'Packet changed before launch')
        row.update(status='CLAIMED', claim=dict(claimed_at=utc_now(), pid=None, start_ticks=None))
        atomic_json(session / 'state.json', state)
        descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        log = os.fdopen(descriptor, 'wb')
        command = [sys.executable, str(runner), '--project', str(project), '--out', str(output),
                   '--packet', job['packet'], '--model', job['model'], '--task-id', job['task_id'],
                   '--run-id', job['run_id'], '--domain', job['domain'], '--task-type', job['task_type'],
                   '--difficulty', job.get('difficulty', 'unspecified'), '--acceptance-criteria', job['acceptance_criteria'],
                   '--queued-at', row['queued_at'], '--max-output-tokens', str(job.get('max_output_tokens', 65536)),
                   '--reasoning-effort', job.get('reasoning_effort', 'unspecified')]
        for name in ('focus', 'parent_task_id', 'dataset', 'task_family'):
            if job.get(name):
                command += ['--' + name.replace('_', '-'), job[name]]
        if credential_file:
            command += ['--credential-file', str(credential_file)]
        if registry:
            command += ['--registry', str(registry)]
        if job['model'] == 'claude':
            command += ['--allow-claude', '--claude-model', job['claude_model']]
        child = subprocess.Popen(command, cwd=project, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        row.update(status='RUNNING')
        row['claim'].update(pid=child.pid, start_ticks=process_start_ticks(child.pid))
        atomic_json(session / 'state.json', state)
        return child
    except (OSError, ValueError):
        row.update(status='NEEDS_REVIEW' if child is not None else 'FAILED', error='local_launch_failure')
        atomic_json(session / 'state.json', state)
        return child
    finally:
        if log:
            log.close()


def summary(state):
    counts = {}
    for row in state['jobs'].values():
        counts[row['status']] = counts.get(row['status'], 0) + 1
    successful = all(row['status'] == SUCCESS for row in state['jobs'].values())
    return dict(counts=counts, status='COMPLETE' if successful else 'NEEDS_ATTENTION', exit_code=0 if successful else 1,
                automatic_code_integration=False, hardware_access=False)


def run_session(document, project, session, runner, runner_sha, credential_file=None, registry=None):
    """Dispatch only useful supplied jobs; interruption never kills an arbitrary PID."""
    state = reconcile(document, load_state(session), project, session)
    atomic_json(session / 'state.json', state)
    active = {}
    try:
        while True:
            for name, child in list(active.items()):
                code = child.poll()
                if code is None:
                    continue
                row = state['jobs'][name]
                try:
                    observed = runner_status(session, row['spec'])
                    row.update(status=completed_status(observed, code), exit_code=code)
                except (OSError, ValueError):
                    row.update(status='NEEDS_REVIEW', exit_code=code, error='invalid_runner_record')
                del active[name]
            settle(state)
            # Unknown existing children may still consume slots or money.
            # Exit for review instead of launching more around that uncertainty.
            unresolved = any(row['status'] == 'NEEDS_REVIEW' for row in state['jobs'].values())
            candidates = [] if unresolved else sorted((r for r in state['jobs'].values() if ready(r, state)),
                                                       key=lambda r: (-r['spec'].get('priority', 0), r['spec']['task_id']))
            for row in candidates[:max(0, document['max_active'] - len(active))]:
                child = start_job(state, row, project, session, runner, runner_sha, credential_file, registry)
                if child:
                    active[row['spec']['task_id']] = child
                if row['status'] == 'NEEDS_REVIEW':
                    break
            atomic_json(session / 'state.json', state)
            if not active:
                settle(state)
                if not any(ready(r, state) for r in state['jobs'].values()) or unresolved:
                    atomic_json(session / 'state.json', state)
                    return summary(state)
                continue
            time.sleep(0.1)
    except BaseException:
        for name in active:
            state['jobs'][name].update(status='NEEDS_REVIEW', error='monitor_interrupted_child_may_continue')
        atomic_json(session / 'state.json', state)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('project', 'session', 'queue', 'runner', 'runner-sha256'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--allow-claude', action='store_true')
    parser.add_argument('--credential-file', type=Path)
    parser.add_argument('--registry', type=Path, default=Path.home() / '.codex/model-workflow/data/metrics.sqlite')
    args = parser.parse_args(argv)
    project = safe_path(args.project)
    session = safe_path(args.session, exists=False)
    queue_path = safe_path(args.queue)
    runner = safe_path(args.runner)
    need(project.is_dir() and file_sha(runner) == args.runner_sha256, 'Wrong project/runner')
    document = validate_queue(json.loads(queue_path.read_text()), project, args.allow_claude)
    if not args.run:
        state = reconcile(document, load_state(session) if session.exists() else None, project, session)
        settle(state)
        print(json.dumps(dict(prepared=True, summary=summary(state), ready=[name for name, row in state['jobs'].items() if ready(row, state)])))
        return 0
    session.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(session / 'queue.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    need(stat.S_ISREG(os.fstat(descriptor).st_mode), 'Lock is not a regular file')
    previous = {}
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for name in ('runs', 'logs'):
            safe_path(session / name, exists=False).mkdir(mode=0o700, exist_ok=True)
        def interrupted(number, frame):
            raise InterruptedError('Monitor interrupted')
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[number] = signal.signal(number, interrupted)
        result = run_session(document, project, session, runner, args.runner_sha256, args.credential_file, args.registry)
        atomic_json(session / 'summary.json', result)
        print(json.dumps(result))
        return result['exit_code']
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
        os.close(descriptor)


if __name__ == '__main__':
    raise SystemExit(main())
