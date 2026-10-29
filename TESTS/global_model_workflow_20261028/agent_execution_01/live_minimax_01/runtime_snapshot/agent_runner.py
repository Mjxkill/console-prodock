#!/usr/bin/env python3
"""Execute a bounded OpenCode implementation on an isolated copy.

Execution is the default here; --mode review explicitly delegates to the
separate review runner. Nothing is merged into the original project.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time
import uuid

from agent_backend import Backend, dependencies
from agent_core import atomic, execute
from agent_events import parse

MODELS = ('deepseek-v4.1-flash', 'glm-5.3-flash', 'minimax-m3.1-flash', 'beam')


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def credential(path):
    key = os.environ.get('OLLAMA_API_KEY')
    if not key and path:
        path = Path(path).expanduser().absolute()
        if any(p.is_symlink() for p in [path, *path.parents]) or path.stat().st_size > 65536:
            raise ValueError('invalid credential path')
        for line in path.read_text().splitlines():
            match = re.fullmatch(r'\s*(?:export\s+)?OLLAMA_API_KEY\s*=\s*(.+)', line)
            if match:
                values = shlex.split(match[1], comments=True)
                if len(values) != 1 or '$' in values[0]:
                    raise ValueError('unsupported credential assignment')
                key = values[0]
                break
    if not key or '\n' in key or '\r' in key:
        raise ValueError('provider credential unavailable')
    return key


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('execution', 'review'), default='execution')
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--model', choices=MODELS, required=True)
    parser.add_argument('--run-id', default=None)
    parser.add_argument('--registry', type=Path,
                        default=Path.home() / '.codex/model-workflow/data/metrics.sqlite')
    parser.add_argument('--credential-file', type=Path)
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--max-steps', type=int, default=16)
    parser.add_argument('--max-requests', type=int, default=48)
    parser.add_argument('--max-output-tokens', type=int, default=65536)
    parser.add_argument('--opencode-bin', default='opencode')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(argv)
    for value, low, high in ((args.timeout, 1, 3600), (args.max_steps, 1, 32),
                             (args.max_requests, 1, 96), (args.max_output_tokens, 512, 131072)):
        if not low <= value <= high:
            parser.error('execution bound outside policy')
    for path in (args.project, args.spec, args.out, args.registry):
        if '..' in path.parts:
            parser.error('parent traversal refused')
        if any(p.is_symlink() for p in [path.absolute(), *path.absolute().parents]):
            parser.error('symlink path refused')
    args.project = args.project.absolute()
    args.spec = args.spec.absolute()
    args.out = args.out.absolute()
    if not args.project.is_dir() or not args.spec.is_file() or args.spec.stat().st_size > 1 << 20:
        parser.error('invalid project/spec')
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error('output must be fresh with existing parent')
    return args


def test_counts(backend):
    """Independent tests counted here; MCP test audit is integrated separately."""
    runs, failures = 0, 0
    for entry in backend.tests:
        outcomes = entry.get('test_results')
        if isinstance(outcomes, list):
            runs += len(outcomes)
            failures += sum(item.get('returncode') != 0 for item in outcomes)
        elif type(entry.get('test_runs')) is int and type(entry.get('test_failures')) is int:
            runs += entry['test_runs']
            failures += entry['test_failures']
        else:
            return None, None
    return runs, failures


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    mode_parser = argparse.ArgumentParser(add_help=False)
    mode_parser.add_argument('--mode', default='execution')
    early, unused = mode_parser.parse_known_args(raw)
    if early.mode == 'review':
        sibling = Path(__file__).resolve().with_name('runner.py')
        if not sibling.is_file():
            raise SystemExit('Review delegation requires the release02 flat pack')
        return subprocess.call([sys.executable, str(sibling), *raw])
    args = arguments(raw)
    spec = json.loads(args.spec.read_text())
    if type(spec) is not dict or spec.get('execution_mode') != 'execution':
        raise ValueError('task spec must explicitly declare execution_mode=execution')
    if not isinstance(spec.get('prompt'), str) or not 1 <= len(spec['prompt']) <= 64000:
        raise ValueError('bounded task prompt required')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', spec.get('task_id', '')):
        raise ValueError('invalid task_id')
    spec['project'] = str(args.project)
    spec['run_id'] = args.run_id or uuid.uuid4().hex
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', spec['run_id']):
        raise ValueError('invalid run_id')
    if args.prepare_only:
        print(json.dumps(dict(prepared=True, execution_mode='execution',
                              isolation_verified=False, network_access=False)))
        return 0
    key = credential(args.credential_file)
    if key in json.dumps(spec):
        raise ValueError('task contains credential')
    started_at, started = utc(), time.monotonic()
    backend = Backend(args, spec, args.out, key)
    previous = {}
    def interrupted(number, frame):
        raise InterruptedError('signal')
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous[number] = signal.signal(number, interrupted)
    try:
        state = execute(backend, spec, args.out, parse)
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
    # Final metrics deliberately describe one task, not one API call.
    all_events = '\n'.join((args.out / f'events_{i}.jsonl').read_text()
                            for i in range(len(state['attempts'])))
    dependencies()
    from event_parser import parse_events
    decoded = parse_events(all_events, 'ollama-cloud')
    answer = decoded['answer']
    (args.out / 'answer.txt').write_text(answer)
    test_runs, test_failures = test_counts(backend)
    success = state['status'] == 'REVIEW_PENDING'
    record = dict(schema=1, event='finished', run_id=spec['run_id'], task_id=spec['task_id'],
                  parent_task_id=spec.get('parent_task_id'), project=str(args.project),
                  provider='ollama-cloud', model=args.model, execution_mode='execution',
                  domain=spec.get('domain', 'implementation'),
                  task_type=spec.get('task_type', 'implementation'),
                  difficulty=spec.get('difficulty', 'unspecified'),
                  dataset=spec.get('dataset'), task_family=spec.get('task_family'),
                  acceptance_criteria=spec.get('acceptance_criteria', 'Independent fixed tests pass'),
                  model_config=dict(version='2026-10-28.agent.1', execution_mode='execution',
                                    requested_output_cap=args.max_output_tokens, max_steps=args.max_steps,
                                    max_requests=args.max_requests),
                  queued_at=None, started_at=started_at, finished_at=utc(),
                  elapsed_seconds=time.monotonic()-started, queue_delay_seconds=None,
                  status='COMPLETED_REVIEW_PENDING_VALIDATION' if success else
                         'INCOMPLETE_LENGTH' if decoded['truncated'] else
                         'INTERRUPTED' if state['status'] == 'INTERRUPTED' else 'FAILED',
                  exit_code=0 if success else 1, truncated=decoded['truncated'],
                  tokens=decoded['tokens'], cost=None,
                  input_sha256=sha(args.spec.read_bytes()), prompt_sha256=sha(spec['prompt'].encode()),
                  output_sha256=sha(answer.encode()), answer_chars=len(answer),
                  quality_status='pending_independent_evaluation', automatic_quality_score=None,
                  model_requests=len(backend.gateway_records),
                  model_steps=state['model_steps_observed'],
                  tool_calls=state['tool_invocations_observed'], test_runs=test_runs, test_failures=test_failures,
                  lifecycle_status=state['status'], session_id=state['session_id'],
                  source_integrated=False, hardware_access=False)
    atomic(args.out / 'metrics.json', record)
    atomic(args.out / 'status.json', record)
    (args.out / 'task_events.jsonl').write_text(json.dumps(record) + '\n')
    imported = False
    try:
        from metrics import import_run
        args.registry.parent.mkdir(parents=True, exist_ok=True)
        import_run(args.registry, args.out / 'metrics.json')
        imported = True
        receipt = dict(passed=True, registry=str(args.registry),
                       metrics_sha256=sha((args.out / 'metrics.json').read_bytes()))
    except Exception as error:
        receipt = dict(passed=False, error_type=type(error).__name__)
    atomic(args.out / 'registry_import.json', receipt)
    print(json.dumps(dict(run_id=spec['run_id'], status=record['status'],
                          model_requests=record['model_requests'], tool_calls=record['tool_calls'],
                          registry_imported=imported)))
    return 0 if success and imported else 1


if __name__ == '__main__':
    raise SystemExit(main())
