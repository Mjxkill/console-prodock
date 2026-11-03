"""Read-only worker inventory, grounded in live /proc identities.

A status file saying RUNNING is never sufficient. PID plus kernel start ticks
are checked twice, and an OpenCode child is associated through actual PPIDs.
Only allowlisted metadata is returned; argv, prompts, credentials and model
answers are never published. No process is started, signalled or modified.
Test/failure numbers are cumulative command results, including the deliberately
failing initial baseline. They do not describe the current code's test status.
Run this collector in the intended host PID namespace; it cannot inspect jobs
hidden in a different PID namespace or manufacture visibility across one.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import hashlib
import math
import os
from pathlib import Path
import re
import sqlite3

MODELS = ('deepseek-v4.1-flash', 'glm-5.3-flash', 'minimax-m3.1-flash', 'beam')
MAX_FILE = 2 * 1024 * 1024
ACTIVE_LABELS = {'PREPARING', 'BASELINE_TESTED', 'RUNNING', 'VALIDATING'}
TERMINAL_LABELS = {
    'COMPLETED_REVIEW_PENDING_VALIDATION': 'REVIEW_PENDING',
    'REVIEW_PENDING': 'REVIEW_PENDING', 'FAILED': 'FAILED',
    'POLICY_FAILED': 'FAILED', 'TEST_INFRASTRUCTURE_FAILED': 'FAILED',
    'MODEL_INCOMPLETE': 'INCOMPLETE', 'INCOMPLETE_LENGTH': 'INCOMPLETE',
    'INTERRUPTED': 'INTERRUPTED',
}


def _number(value):
    try:
        return value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None
    except OverflowError:
        return None


def _count(value):
    return value if type(value) is int and 0 <= value <= 2**63 - 1 else None


def _identifier(value):
    # Do not publish arbitrary text from a task prompt/error or an argv value.
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', value) else None


def _inside(path, root):
    try:
        resolved = Path(path).resolve()
        return resolved if resolved.is_relative_to(root) else None
    except (OSError, TypeError, ValueError, RuntimeError):
        return None


def _utc(epoch):
    if _number(epoch) is None:
        return None
    try:
        return datetime.fromtimestamp(epoch, timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def _epoch(stamp):
    if not isinstance(stamp, str):
        return None
    try:
        date = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        return date.timestamp() if date.tzinfo else None
    except (ValueError, OverflowError, OSError):
        return None


def _read(path, boundary, limit=MAX_FILE):
    """Bounded file read within a run directory; never follow an escaping link."""
    safe = _inside(path, boundary)
    if safe is None:
        return None, 'outside_boundary'
    try:
        with safe.open('rb') as stream:
            raw = stream.read(limit + 1)
        return (raw, None) if len(raw) <= limit else (None, 'file_too_large')
    except FileNotFoundError:
        return None, 'missing'
    except (PermissionError, OSError):
        return None, 'unreadable'


def _json(path, boundary):
    raw, issue = _read(path, boundary)
    if issue:
        return None, issue
    try:
        value = json.loads(raw)
        return value, None
    except (ValueError, UnicodeError):
        return None, 'json_incomplete'


def _stat(pid, proc_root):
    """Parse /proc/PID/stat including command names containing spaces or ')'."""
    try:
        raw = (proc_root / str(pid) / 'stat').read_text()
        fields = raw[raw.rindex(')') + 2:].split()
        return {'pid': int(raw.split(' ', 1)[0]), 'ppid': int(fields[1]),
                'start_ticks': int(fields[19]), 'kernel_state': fields[0]}, None
    except FileNotFoundError:
        return None, 'ABSENT'
    except (PermissionError, OSError, ValueError, IndexError):
        return None, 'UNKNOWN'


def process_state(pid, start_ticks, *, proc_root=Path('/proc')):
    """Public PID identity check for other dashboard collectors.

An expected start tick is mandatory. A reused PID or zombie is never reported
as a running job. The return value contains only kernel identity fields.
"""
    if type(pid) is not int or pid <= 0 or type(start_ticks) is not int or start_ticks < 0:
        return {'state': 'UNKNOWN', 'reason': 'invalid_identity'}
    record, issue = _stat(pid, Path(proc_root))
    if issue:
        return {'state': issue, 'pid': pid}
    if record['pid'] != pid or record['start_ticks'] != start_ticks:
        return {'state': 'REUSED', 'pid': pid}
    if record['kernel_state'] in ('Z', 'X', 'x'):
        return {'state': 'ABSENT', 'pid': pid, 'reason': 'exited_process'}
    return {'state': 'RUNNING', **record}


def _options(argv):
    allowed = {'--project', '--out', '--model', '--run-id', '--spec'}
    result = {}
    for index, word in enumerate(argv):
        key, equal, value = word.partition('=')
        if key not in allowed:
            continue
        if key in result:
            return {}  # Ambiguous CLI is not an identity proof.
        if not equal:
            value = argv[index + 1] if index + 1 < len(argv) else ''
        result[key] = value
    return result


def _scan(proc_root):
    records, denied = {}, False
    try:
        entries = list(proc_root.iterdir())
    except (PermissionError, OSError):
        return records, True
    for entry in entries:
        if not entry.name.isdecimal():
            continue
        pid = int(entry.name)
        record, issue = _stat(pid, proc_root)
        if issue:
            denied |= issue == 'UNKNOWN'
            continue
        try:
            raw = (entry / 'cmdline').read_bytes()
            if len(raw) > 65536:
                denied = True
                continue
            argv = [part.decode('utf-8', 'replace') for part in raw.split(b'\0') if part]
        except FileNotFoundError:
            continue  # Normal process exit during scan.
        except (PermissionError, OSError):
            denied = True
            continue
        confirmed = process_state(pid, record['start_ticks'], proc_root=proc_root)
        if confirmed['state'] != 'RUNNING':
            denied |= confirmed['state'] in ('UNKNOWN', 'REUSED')
            continue
        record['argv'] = argv  # Private, never placed in a public row.
        records[pid] = record
    return records, denied


def _clock(proc_root):
    try:
        uptime = float((proc_root / 'uptime').read_text().split()[0])
        boot = next(int(line.split()[1]) for line in (proc_root / 'stat').read_text().splitlines()
                    if line.startswith('btime '))
        hz = os.sysconf('SC_CLK_TCK')
        return uptime, boot, hz
    except (OSError, ValueError, StopIteration, IndexError):
        return None, None, None


def _is_descendant(pid, ancestor, records):
    visited = set()
    for _ in range(64):
        if pid == ancestor:
            return True
        if pid in visited or pid not in records:
            return False
        visited.add(pid)
        pid = records[pid]['ppid']
    return False


def _opencode_children(runner, records, model, proc_root):
    children, conflict = [], False
    for pid, record in records.items():
        argv = record['argv']
        executable = any(Path(arg).name in ('opencode', 'opencode.exe') for arg in argv[:2])
        if (pid != runner['pid'] and executable and 'run' in argv and
                record['start_ticks'] >= runner['start_ticks'] and
                _is_descendant(pid, runner['pid'], records)):
            observed_model = _options(argv).get('--model')
            if observed_model not in (model, 'task-provider/' + model):
                conflict = True
            elif process_state(pid, record['start_ticks'], proc_root=proc_root)['state'] == 'RUNNING':
                children.append(pid)
    return sorted(children), conflict


def _metadata(out):
    notes = []
    for name in ('metrics.json', 'status.json', 'state.json'):
        value, issue = _json(out / name, out)
        if isinstance(value, dict):
            return value, name, notes
        if issue != 'missing':
            notes.append(name + ':' + (issue or 'invalid_schema'))
    return {}, None, notes


def _progress(out, metadata):
    """Use final counters, or completed audit events while a runner is alive."""
    result = {'requests': _count(metadata.get('model_requests')),
              'tool_calls': _count(metadata.get('tool_calls')),
              'tests': _count(metadata.get('test_runs')),
              'failures': _count(metadata.get('test_failures'))}
    if all(value is not None for value in result.values()):
        return result
    raw, _ = _read(out / 'isolation/audit.jsonl', out)
    events = []
    if raw is not None:
        for line in raw.splitlines():
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    events.append(event)
            except (ValueError, UnicodeError):
                pass  # An incomplete final append is not a complete event.
        result['tool_calls'] = sum(e.get('event') == 'tool_finish' for e in events)
        finished = [e for e in events if e.get('event') == 'test_finish']
        tests, failures = len(finished), sum(e.get('returncode') != 0 for e in finished)
        for path in [out / 'baseline.json', *sorted(out.glob('validation_tests_*.json'))[:8]]:
            document, _ = _json(path, out)
            if isinstance(document, dict):
                n, f = _count(document.get('test_runs')), _count(document.get('test_failures'))
                if n is not None and f is not None:
                    tests += n
                    failures += f
        result['tests'], result['failures'] = tests, failures
    if result['requests'] is None:
        # The gateway records actual HTTP requests. A model 'step' in the CLI
        # log is deliberately not converted into an unproven request count.
        counts = []
        for path in sorted(out.glob('gateway_*.json'))[:16]:
            value, _ = _json(path, out)
            if isinstance(value, list):
                counts.append(len(value))
        result['requests'] = max(counts) if counts else None
    return result


def _last_activity(out):
    times = []
    for relative in ('metrics.json', 'status.json', 'state.json',
                     'isolation/audit.jsonl', 'controller/data/opencode/log/opencode.log'):
        safe = _inside(out / relative, out)
        if safe:
            try:
                times.append(safe.stat().st_mtime)
            except OSError:
                pass
    return _utc(max(times)) if times else None


def _recent(root, registry):
    """Merge attempts by their registered start instant, across all registries.

    Per-database SQL ordering is insufficient: an older database can be scanned
    first. Filesystem mtimes describe edits, not attempt chronology. Unknown
    dates sort last; stable path order only breaks ties, never proves recency.
    All actual metadata reads remain bounded under the project root.
    """
    if registry is None:
        paths = list((root / 'TESTS').glob('model_*/metrics.sqlite'))[:16]
    else:
        paths = [Path(registry)]
    selected = []
    for path in paths:
        safe = _inside(path, root)
        if safe is None or not safe.is_file():
            continue
        try:
            with sqlite3.connect(safe.as_uri() + '?mode=ro', uri=True, timeout=0.1) as connection:
                rows = connection.execute(
                    'SELECT model,project,source_path,started_at FROM runs ORDER BY started_at DESC LIMIT 64').fetchall()
            for model, project, source, started_at in rows:
                if model not in MODELS or _inside(project, root) is None:
                    continue
                source = _inside(source, root)
                if source is not None and source.name == 'metrics.json':
                    stamp = _epoch(started_at)
                    selected.append((stamp if stamp is not None else float('-inf'), model, source.parent))
        except (sqlite3.Error, OSError, ValueError):
            continue
    selected.sort(key=lambda item: (item[0], str(item[2]), item[1]), reverse=True)
    return [(model, out) for _, model, out in selected]


def _review(root, registry, row):
    """Read the latest independent verdict without mutating runner metrics.

    A verdict applies to one attempt and its exact answer, never a task family.
    Proof bytes must still match. Do not expose evaluator free text or prompts.
    """
    run_id = row.get('run_id')
    if not _identifier(run_id):
        return None
    paths = ([Path(registry)] if registry is not None else
             list((root / 'TESTS').glob('model_*/metrics.sqlite'))[:16])
    records = []
    for path in paths:
        safe = _inside(path, root)
        if safe is None or not safe.is_file():
            continue
        try:
            with sqlite3.connect(safe.as_uri() + '?mode=ro', uri=True, timeout=0.1) as db:
                db.row_factory = sqlite3.Row
                found = db.execute(
                    'SELECT e.*,r.source_path,r.output_sha256 AS run_output_sha '
                    'FROM evaluations e JOIN runs r ON e.run_id=r.run_id '
                    'WHERE e.run_id=? ORDER BY e.recorded_at DESC,e.id DESC LIMIT 1',
                    (run_id,)).fetchone()
                if found is not None:
                    records.append(dict(found))
        except (sqlite3.Error, OSError, ValueError):
            continue
    if not records:
        return None
    e = max(records, key=lambda x: (_epoch(x.get('recorded_at')) or 0, x['id']))
    verdicts = {'accepted': 'ACCEPTED', 'edited': 'ACCEPTED_AFTER_CHANGES',
                'rejected': 'REJECTED', 'inconclusive': 'REVIEW_INCONCLUSIVE'}
    out = {'state': 'REVIEW_UNKNOWN', 'evaluation_id': _identifier(e.get('evaluation_id'))}
    source = _inside(e.get('source_path'), root)
    expected = _inside(root / row['evidence']['out'] / 'metrics.json', root)
    if source is None or source != expected:
        return out
    meta, issue = _json(source, root)
    if issue or not isinstance(meta, dict):
        return out
    digest = e.get('output_sha256')
    if (not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or
            digest != e.get('run_output_sha') or digest != meta.get('output_sha256') or
            meta.get('run_id') != run_id):
        return out
    evaluator = e.get('evaluator_id')
    independent = (e.get('evaluator_type') == 'human' or
                   (e.get('evaluator_type') == 'model' and
                    isinstance(evaluator, str) and evaluator.startswith('Codex')))
    if not independent or e.get('verdict') not in verdicts:
        return out
    proof = _inside(e.get('evidence_path'), root)
    raw, issue = _read(proof, root) if proof is not None else (None, 'outside')
    if issue or hashlib.sha256(raw).hexdigest() != e.get('evidence_sha256'):
        return out
    score = _number(e.get('score'))
    out.update(state=verdicts[e['verdict']], verdict=e['verdict'],
               score=score if score is not None and score <= 100 else None,
               evaluator_type=e['evaluator_type'],
               evaluated_at=_utc(_epoch(e.get('evaluated_at'))),
               evidence=str(proof.relative_to(root)))
    return out


def collect_workers(root: Path, *, proc_root=Path('/proc'), registry=None) -> list[dict]:
    """Collect active tasks, plus the last recorded result for inactive models.

The four exact preferred models remain visible even without a known task.
Counter absence is None, not a fabricated zero. Finished results never become
RUNNING merely because a status file or a stale PID claims they are active.
"""
    root, proc_root = Path(root).resolve(), Path(proc_root)
    records, denied = _scan(proc_root)
    uptime, boot, hz = _clock(proc_root)
    active, rows, active_models = set(), [], set()
    for pid, record in records.items():
        argv = record['argv']
        if not any(Path(arg).name == 'agent_runner.py' for arg in argv[:3]):
            continue
        options = _options(argv)
        model = options.get('--model')
        if model not in MODELS:
            continue
        project, out = options.get('--project'), options.get('--out')
        if not project or not out or not Path(project).is_absolute() or not Path(out).is_absolute():
            continue
        project, out = _inside(project, root), _inside(out, root)
        if project is None or out is None:
            continue
        meta, source, notes = _metadata(out)
        children, child_conflict = _opencode_children(record, records, model, proc_root)
        state = 'RUNNING' if children else 'STARTING'
        process_epoch = boot + record['start_ticks'] / hz if hz and boot is not None else None
        metadata_epoch = _epoch(meta.get('started_at'))
        if child_conflict:
            state = 'UNKNOWN'
            notes.append('opencode_model_conflict')
        elif metadata_epoch is not None and process_epoch is not None and abs(metadata_epoch - process_epoch) > 10:
            state = 'UNKNOWN'
            notes.append('run_time_does_not_match_process')
        elif meta.get('model', model) != model:
            state = 'UNKNOWN'
            notes.append('model_metadata_conflict')
        elif isinstance(meta.get('status'), str) and meta['status'] in TERMINAL_LABELS:
            state = 'FINALIZING'
        check = process_state(pid, record['start_ticks'], proc_root=proc_root)
        if check['state'] != 'RUNNING':
            state = 'STOPPED' if check['state'] == 'ABSENT' else 'UNKNOWN'
            notes.append('process_identity_changed_during_collection')
        elapsed = max(0.0, uptime - record['start_ticks'] / hz) if uptime is not None and hz else None
        task = _identifier(meta.get('task_id')) or _identifier(options.get('--run-id')) or 'task-unknown'
        evidence = {'source': 'proc+' + (source or 'no-metadata'), 'pid': pid,
                    'start_ticks': record['start_ticks'], 'opencode_pids': children,
                    'out': str(out.relative_to(root)), 'notes': notes,
                    'counter_scope': 'cumulative; includes initial baseline; not current failure state'}
        rows.append(dict(model=model, task=task,
                         run_id=_identifier(meta.get('run_id', options.get('--run-id'))),
                         state=state, runner_status=meta.get('status') if meta.get('status') in ACTIVE_LABELS | set(TERMINAL_LABELS) else None, elapsed_s=elapsed,
                         last_activity=_last_activity(out), **_progress(out, meta), evidence=evidence))
        active.add(out)
        active_models.add(model)
    recent_models = set()
    for model, out in _recent(root, registry):
        if model in active_models or model in recent_models or out in active:
            continue
        meta, source, notes = _metadata(out)
        if meta.get('model', model) != model:
            continue
        label = meta.get('status') if isinstance(meta.get('status'), str) else None
        state = TERMINAL_LABELS.get(label, 'UNKNOWN')
        if label in ACTIVE_LABELS:
            state = 'UNKNOWN' if denied else 'STOPPED'
            notes.append('no_matching_live_runner')
        rows.append(dict(model=model, task=_identifier(meta.get('task_id')) or 'task-unknown',
            run_id=_identifier(meta.get('run_id')),
            state=state, runner_status=label if label in ACTIVE_LABELS | set(TERMINAL_LABELS) else None, elapsed_s=_number(meta.get('elapsed_seconds')),
            last_activity=_last_activity(out), **_progress(out, meta),
            evidence={'source': source or 'registry-path-only', 'out': str(out.relative_to(root)),
                      'notes': notes, 'process_scan_incomplete': denied,
                      'counter_scope': 'cumulative; includes initial baseline; not current failure state'}))
        recent_models.add(model)
    for model in MODELS:
        if model not in active_models | recent_models:
            rows.append(dict(model=model, task=None, run_id=None, state='UNKNOWN' if denied else 'NO_ACTIVE',
                elapsed_s=None, last_activity=None, requests=None, tool_calls=None,
                tests=None, failures=None,
                evidence={'source': 'proc', 'notes': ['process_scan_incomplete'] if denied else []}))
    for row in rows:
        # Keep process-derived state for live workers and failure state for
        # failed runs. Only a completed pending review is replaced for display.
        review = _review(root, registry, row)
        row['review'] = review
        if row['state'] == 'REVIEW_PENDING' and review is not None:
            row['state'] = review['state']
    order = {model: index for index, model in enumerate(MODELS)}
    return sorted(rows, key=lambda row: (order[row['model']], row['task'] or ''))
