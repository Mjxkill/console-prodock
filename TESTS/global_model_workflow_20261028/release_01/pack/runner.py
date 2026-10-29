#!/usr/bin/env python3
"""Run one explicit text packet through OpenCode or opt-in Claude Code.

Outputs belong to one fresh --out directory. Model tools and project config
are disabled. No automatic retry, integration, quality score or hardware I/O.
The final metrics distinguish observed token counts from unknown fields.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
from process_io import capture

from workflow_common import (atomic_json, identifier, need, parse_utc,
                             prepared_text, process_start_ticks, safe_path,
                             sha256, utc_now)

FAVORITES = ('deepseek-v4.1-flash', 'glm-5.3-flash', 'minimax-m3.1-flash', 'beam')
CONFIG_VERSION = '2026-10-28.1'
SYSTEM = ('You are an implementation or review assistant. Work ONLY from the supplied '
          'text packet. Tools, filesystem access and execution are unavailable. '
          'Produce the requested concrete artifact. Separate evidence from hypotheses. '
          'Never claim tests were run. Results require independent review and validation. '
          'Keep code modular, documented, and below 1000 physical lines per file.')


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--model', choices=FAVORITES + ('claude',), required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--run-id', default=None)
    parser.add_argument('--parent-task-id')
    parser.add_argument('--domain', required=True)
    parser.add_argument('--task-type', required=True)
    parser.add_argument('--difficulty', choices=('low', 'medium', 'high', 'unspecified'), default='unspecified')
    parser.add_argument('--acceptance-criteria', required=True)
    parser.add_argument('--focus', default='')
    parser.add_argument('--queued-at')
    parser.add_argument('--dataset')
    parser.add_argument('--task-family')
    parser.add_argument('--max-output-tokens', type=int, default=65536)
    parser.add_argument('--reasoning-effort', choices=('low', 'medium', 'high', 'unspecified'), default='unspecified')
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--credential-file', type=Path)
    parser.add_argument('--registry', type=Path, default=Path.home() / '.codex/model-workflow/data/metrics.sqlite')
    parser.add_argument('--opencode-bin', default='opencode')
    parser.add_argument('--claude-bin', default='claude')
    parser.add_argument('--claude-model', default='fable')
    parser.add_argument('--allow-claude', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    return parser.parse_args(argv)


def validate(args):
    """Validate all prepared inputs before creating output or contacting a model."""
    project = safe_path(args.project)
    need(project.is_dir(), 'Project must be a directory')
    packet, source = prepared_text(project, args.packet)
    out = safe_path(args.out, exists=False)
    need(not out.exists() and out.parent.is_dir(), 'Output must be fresh with an existing parent')
    identifier(args.task_id)
    args.run_id = identifier(args.run_id or uuid.uuid4().hex)
    if args.parent_task_id:
        identifier(args.parent_task_id)
    for text, limit in ((args.domain, 200), (args.task_type, 200), (args.acceptance_criteria, 8000)):
        need(isinstance(text, str) and 0 < len(text) <= limit, 'Missing or oversized task metadata')
    need(len(args.focus) <= 4000, 'Focus too large')
    need(512 <= args.max_output_tokens <= 131072 and 1 <= args.timeout <= 3600, 'Output/time bound outside policy')
    if args.model == 'claude':
        need(args.allow_claude, 'Claude requires explicit opt-in')
        identifier(args.claude_model)
    need(args.reasoning_effort == 'unspecified' or args.model == 'deepseek-v4.1-flash', 'Reasoning option is only configured for the verified DeepSeek adapter')
    if args.queued_at:
        need(parse_utc(args.queued_at) <= parse_utc(utc_now()), 'Queue timestamp is in the future')
    return project, packet, source, out


def credential(args):
    """Read an environment key or one explicit env file, never evaluate a shell."""
    key = os.environ.get('OLLAMA_API_KEY')
    if not key and args.credential_file:
        path = safe_path(args.credential_file)
        need(path.is_file() and path.stat().st_size <= 65536, 'Invalid credential file')
        for line in path.read_text().splitlines():
            match = re.fullmatch(r'\s*(?:export\s+)?OLLAMA_API_KEY\s*=\s*(.+)', line)
            if match:
                words = shlex.split(match[1], comments=True)
                need(len(words) == 1 and '$' not in words[0], 'Unsupported credential assignment')
                key = words[0]
                break
    need(key and '\n' not in key and '\r' not in key, 'OLLAMA_API_KEY missing or invalid')
    return key


def executable(value):
    path = shutil.which(value)
    need(path is not None and os.access(path, os.X_OK), 'Requested CLI executable is unavailable')
    return str(Path(path).absolute())


def build_command(args, out, work, key):
    """Build an isolated child environment; configuration contains env references only."""
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'TERM', 'SSL_CERT_FILE', 'SSL_CERT_DIR')}
    if args.model == 'claude':
        command = [executable(args.claude_bin), '--safe-mode', '--model', args.claude_model,
                   '--tools', '', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                   '--no-session-persistence', '--output-format', 'json', '--print']
        return command, env
    env['OLLAMA_API_KEY'] = key
    for suffix in ('CONFIG', 'DATA', 'CACHE', 'STATE'):
        folder = work / ('xdg_' + suffix.lower())
        folder.mkdir()
        env['XDG_' + suffix + '_HOME'] = str(folder)
    model = dict(name=args.model, limit=dict(context=131072, output=args.max_output_tokens))
    if args.model == 'deepseek-v4.1-flash':
        model.update(reasoning=True, interleaved={'field': 'reasoning_content'})
        if args.reasoning_effort != 'unspecified':
            model['options'] = {'reasoningEffort': args.reasoning_effort}
    config = dict(enabled_providers=['explicit-ollama-cloud'], autoupdate=False,
                  snapshot=False, share='disabled', permission={'*': 'deny'},
                  agent={'worker': dict(mode='primary', description='Prepared text only', prompt=SYSTEM, permission={'*': 'deny'})},
                  provider={'explicit-ollama-cloud': dict(npm='@ai-sdk/openai-compatible', name='Explicit Ollama Cloud',
                       options=dict(baseURL='https://ollama.com/v1', apiKey='{env:OLLAMA_API_KEY}'), models={args.model: model})})
    atomic_json(out / 'opencode.json', config)
    env.update(OPENCODE_CONFIG=str(out / 'opencode.json'), OPENCODE_DISABLE_PROJECT_CONFIG='true',
               OPENCODE_DISABLE_CLAUDE_CODE='true', OPENCODE_EXPERIMENTAL_OUTPUT_TOKEN_MAX=str(args.max_output_tokens))
    command = [executable(args.opencode_bin), 'run', '--pure', '--model', 'explicit-ollama-cloud/' + args.model,
               '--agent', 'worker', '--format', 'json', '--title', args.task_id, '--dir', str(work)]
    return command, env


def append_event(path, record):
    with path.open('a') as stream:
        stream.write(json.dumps(record, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def redact_metadata(value, secret):
    """Sanitize caller metadata too, including a mistakenly supplied key."""
    if isinstance(value, str):
        return value.replace(secret, '[REDACTED]') if secret else value
    if isinstance(value, dict):
        return {key: redact_metadata(item, secret) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_metadata(item, secret) for item in value]
    return value


def main(argv=None):
    args = arguments(argv)
    project, packet, source, out = validate(args)
    if args.prepare_only:
        print(json.dumps(dict(prepared=True, network_access=False, model=args.model, run_id=args.run_id)))
        return 0
    # Imported after prepare-only validation: parser is a pure offline module.
    from event_parser import parse_events
    key = None
    credential_error = None
    try:
        key = credential(args) if args.model != 'claude' else None
    except Exception as error:
        # Retain a local availability failure as a task record, not a traceback
        # that escapes before accounting. Only its type is later persisted.
        credential_error = error
    prompt = SYSTEM + '\n\nTASK:\n' + args.focus + '\n\nACCEPTANCE:\n' + args.acceptance_criteria + '\n\nPACKET:\n' + source
    out.mkdir(mode=0o700)
    work = None
    started_at, start = utc_now(), time.perf_counter()
    record = dict(schema=1, event='started', run_id=args.run_id, task_id=args.task_id, parent_task_id=args.parent_task_id,
                  project=str(project), provider='claude-code' if args.model == 'claude' else 'ollama-cloud',
                  model=args.claude_model if args.model == 'claude' else args.model,
                  domain=args.domain, task_type=args.task_type, difficulty=args.difficulty,
                  acceptance_criteria=args.acceptance_criteria, dataset=args.dataset, task_family=args.task_family,
                  model_config=dict(version=CONFIG_VERSION, requested_output_cap=args.max_output_tokens,
                                    requested_context=131072, output_cap_applied=args.model != 'claude',
                                    reasoning_effort=args.reasoning_effort),
                  execution_timeout_seconds=args.timeout,
                  queued_at=args.queued_at, started_at=started_at, finished_at=None, elapsed_seconds=None,
                  queue_delay_seconds=(parse_utc(started_at)-parse_utc(args.queued_at)).total_seconds() if args.queued_at else None,
                  status='STARTING', exit_code=None, truncated=False,
                  tokens=dict.fromkeys(('input', 'output', 'reasoning', 'total', 'cache_read', 'cache_write')), cost=None,
                  input_sha256=sha256(source.encode()), prompt_sha256=sha256(prompt.encode()), output_sha256=None,
                  answer_chars=0, quality_status='pending_independent_evaluation', automatic_quality_score=None,
                  wrapper_pid=os.getpid(), wrapper_start_ticks=process_start_ticks(os.getpid()),
                  registry_path=str(args.registry.expanduser().absolute()), hardware_access=False)
    record = redact_metadata(record, key)
    atomic_json(out / 'status.json', record)
    append_event(out / 'task_events.jsonl', record)
    child = None
    previous = {}
    stdout = stderr = ''
    registry_ok = False
    def interrupted(number, frame):
        raise InterruptedError('Signal received')
    try:
        if credential_error is not None:
            raise credential_error
        need(not key or key not in prompt, 'Prepared packet contains credential')
        (out / 'prompt.txt').write_text(prompt)
        work = Path(tempfile.mkdtemp(prefix='codex-model-' + args.run_id + '-'))
        for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            previous[number] = signal.signal(number, interrupted)
        command, env = build_command(args, out, work, key)
        child = subprocess.Popen(command, cwd=work, env=env, stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        record.update(status='RUNNING', pid=child.pid, pid_start_ticks=process_start_ticks(child.pid))
        atomic_json(out / 'status.json', record)
        print(json.dumps(dict(run_id=args.run_id, model=record['model'], pid=child.pid, status='RUNNING')), flush=True)
        raw_stdout, raw_stderr = capture(child, prompt.encode(), args.timeout)
        stdout, stderr = raw_stdout.decode(errors='replace'), raw_stderr.decode(errors='replace')
        if key:
            stdout, stderr = stdout.replace(key, '[REDACTED]'), stderr.replace(key, '[REDACTED]')
        parsed = parse_events(stdout, record['provider'])
        answer = parsed['answer']
        (out / 'answer.txt').write_text(answer)
        record.update(exit_code=child.returncode, truncated=parsed['truncated'], tokens=parsed['tokens'],
                      cost=parsed.get('cost'), errors=parsed['errors'], finishes=parsed['finishes'],
                      cost_observed=parsed.get('cost_observed'), cost_source=parsed.get('cost_source'),
                      usage_observations=parsed.get('observations'),
                      answer_chars=len(answer), output_sha256=sha256(answer.encode()))
        record['status'] = ('INCOMPLETE_LENGTH' if parsed['truncated'] else
                            'COMPLETED_REVIEW_PENDING_VALIDATION' if child.returncode == 0 and answer and not parsed['errors'] else 'FAILED')
    except BaseException as error:
        record['status'] = 'TIMEOUT' if isinstance(error, subprocess.TimeoutExpired) else 'INTERRUPTED' if isinstance(error, (InterruptedError, KeyboardInterrupt)) else 'FAILED'
        record['error_type'] = type(error).__name__  # Never persist arbitrary exception text with credentials.
        stdout = getattr(error, 'captured_stdout', b'').decode(errors='replace')
        stderr = getattr(error, 'captured_stderr', b'').decode(errors='replace')
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if child is not None:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                record['reap_incomplete'] = True
            record['exit_code'] = child.returncode
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
        if key:
            stdout, stderr = stdout.replace(key, '[REDACTED]'), stderr.replace(key, '[REDACTED]')
        if child:
            for stream in (child.stdin, child.stdout, child.stderr):
                if not stream.closed:
                    stream.close()
        if work is not None:
            if child is None or child.poll() is not None:
                try:
                    shutil.rmtree(work)
                    record['work_cleanup'] = 'removed'
                except OSError:
                    record.update(work_cleanup='failed', work_retained=str(work))
            else:
                record.update(work_cleanup='retained_process_unreaped', work_retained=str(work))
        (out / 'events.jsonl').write_text(stdout)
        (out / 'stderr.txt').write_text(stderr)
        record.update(event='finished', finished_at=utc_now(), elapsed_seconds=time.perf_counter()-start)
        atomic_json(out / 'status.json', record)
        atomic_json(out / 'metrics.json', record)
        append_event(out / 'task_events.jsonl', record)
        try:
            from metrics import import_run
            registry = safe_path(args.registry, exists=False)
            registry.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            import_run(registry, out / 'metrics.json')
            registry_ok = True
            registration = dict(passed=True, registry=str(registry), metrics_sha256=sha256((out / 'metrics.json').read_bytes()))
        except Exception as error:
            registration = dict(passed=False, error_type=type(error).__name__, metrics_sha256=sha256((out / 'metrics.json').read_bytes()))
        atomic_json(out / 'registry_import.json', registration)
    print(json.dumps(dict(run_id=args.run_id, status=record['status'], registry_imported=registry_ok, answer_chars=record['answer_chars'])), flush=True)
    return 0 if record['status'] == 'COMPLETED_REVIEW_PENDING_VALIDATION' and registry_ok and record.get('work_cleanup') != 'failed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
