#!/usr/bin/env python3
"""Execution adapter over the shared dispatcher, not a second queue engine.

Reuses locks, durable claims, dependencies, concurrency and orphan policy from
dispatch_queue. Only task validation and the worker CLI differ from reviews.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent
if not (HERE / 'dispatch_queue.py').is_file():
    # Candidate source tree only; the published pack uses sibling modules.
    sys.path.insert(0, str(HERE.parent / 'release_02' / 'pack'))
import dispatch_queue as common
from workflow_common import atomic_json, need, prepared_text, process_start_ticks, safe_path, utc_now


def validate(document, project):
    common.validate_queue(document, project, execution_mode='execution')
    for job in document['jobs']:
        source, text = prepared_text(project, job['packet'], suffixes=('.json',))
        spec = json.loads(text)
        need(type(spec) is dict and spec.get('execution_mode') == 'execution',
             'Each implementation task.json must declare execution_mode=execution')
        need(spec.get('task_id') == job['task_id'], 'Task identity differs from queue job')
        for field in ('domain', 'task_type', 'acceptance_criteria'):
            need(spec.get(field) == job[field], 'Task metadata differs: ' + field)
        need(spec.get('difficulty', 'unspecified') == job.get('difficulty', 'unspecified'),
             'Task difficulty differs')
        need(type(spec.get('inputs')) is list and type(spec.get('owned')) is list
             and type(spec.get('tests')) is list, 'Missing owned-copy task contract')
    return document


def command(job, project, output, runner, credential_file=None, registry=None, queued_at=None):
    """Always explicit execution; review metadata cannot silently change mode."""
    argv = [sys.executable, str(runner), '--mode', 'execution',
            '--project', str(project), '--spec', str(project / job['packet']),
            '--out', str(output), '--model', job['model'], '--run-id', job['run_id'],
            '--max-output-tokens', str(job.get('max_output_tokens', 65536))]
    if credential_file:
        argv += ['--credential-file', str(credential_file)]
    if registry:
        argv += ['--registry', str(registry)]
    if queued_at:
        argv += ['--queued-at', queued_at]
    return argv


def start_job(state, row, project, session, runner, runner_sha, credential_file=None, registry=None):
    """Persist claim before spawning; exact source/worker SHA checked again."""
    job = row['spec']
    output = safe_path(session / 'runs' / job['run_id'], exists=False)
    log_path = safe_path(session / 'logs' / (job['run_id'] + '.log'), exists=False)
    log = None
    try:
        need(not output.exists(), 'Output already exists')
        need(common.file_sha(runner) == runner_sha, 'Worker changed before launch')
        packet, unused = prepared_text(project, job['packet'], suffixes=('.json',))
        need(common.file_sha(packet) == job['packet_sha256'], 'Task changed before launch')
        row.update(status='CLAIMED', claim=dict(claimed_at=utc_now(), pid=None, start_ticks=None))
        atomic_json(session / 'state.json', state)
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        log = os.fdopen(fd, 'wb')
        child = subprocess.Popen(command(job, project, output, runner, credential_file, registry, row['queued_at']),
                                 cwd=project, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        row.update(status='RUNNING')
        row['claim'].update(pid=child.pid, start_ticks=process_start_ticks(child.pid))
        atomic_json(session / 'state.json', state)
        return child
    except (OSError, ValueError) as error:
        row.update(status='NEEDS_REVIEW', error_type=type(error).__name__)
        atomic_json(session / 'state.json', state)
        return None
    finally:
        if log is not None:
            log.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('project', 'session', 'queue', 'runner-sha256'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--runner', default=str(HERE / 'agent_runner.py'))
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--credential-file', type=Path)
    parser.add_argument('--registry', type=Path,
                        default=Path.home() / '.codex/model-workflow/data/metrics.sqlite')
    args = parser.parse_args(argv)
    project, session = safe_path(args.project), safe_path(args.session, exists=False)
    runner = safe_path(args.runner)
    need(project.is_dir() and common.file_sha(runner) == args.runner_sha256, 'Wrong project/worker')
    document = validate(json.loads(safe_path(args.queue).read_text()), project)
    if not args.run:
        state = common.reconcile(document, common.load_state(session) if session.exists() else None, project, session)
        common.settle(state)
        print(json.dumps(dict(prepared=True, execution_mode='execution', summary=common.summary(state))))
        return 0
    session.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(session / 'queue.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    need(stat.S_ISREG(os.fstat(descriptor).st_mode), 'Lock is not regular')
    previous = {}
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for name in ('runs', 'logs'):
            safe_path(session / name, exists=False).mkdir(mode=0o700, exist_ok=True)
        def interrupted(number, frame):
            raise InterruptedError('Execution queue interrupted')
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[number] = signal.signal(number, interrupted)
        result = common.run_session(document, project, session, runner, args.runner_sha256,
                                    args.credential_file, args.registry, start_job_fn=start_job)
        atomic_json(session / 'summary.json', result)
        print(json.dumps(result))
        return result['exit_code']
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
        os.close(descriptor)


if __name__ == '__main__':
    raise SystemExit(main())
