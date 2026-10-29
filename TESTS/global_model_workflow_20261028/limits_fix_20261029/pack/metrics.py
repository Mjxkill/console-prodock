#!/usr/bin/env python3
"""Portable SQLite run registry, independent assessments and observed statistics.

No model routing or code integration is performed. All durations are seconds;
unknown measurements stay NULL. Run imports bind exact metrics bytes and output
bytes. Evaluations are append-only and bind evidence plus the original output.
"""
import argparse
import csv
import hashlib
import html
import io
import json
import math
import re
import sqlite3
import statistics
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
SUCCESS = 'COMPLETED_REVIEW_PENDING_VALIDATION'
TERMINAL = {SUCCESS, 'FAILED', 'INCOMPLETE_LENGTH', 'INTERRUPTED', 'TIMEOUT'}
WEIGHTS = {'correctness': 40, 'relevance': 25, 'completeness': 20, 'actionability': 15}
EXECUTION_COUNTS = ('model_requests', 'tool_calls', 'test_runs', 'test_failures')
RUBRIC = '1'
HEX = re.compile(r'[a-f0-9]{64}\Z')


def require(value, message):
    """Validation must also run under python -O."""
    if not value:
        raise ValueError(message)


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_path(path, must_exist=True):
    """Reject symlink components, including the SQLite DB and adjacent files."""
    p = Path(path).expanduser().absolute()
    for item in [p, *p.parents]:
        require(not item.is_symlink(), 'Symlink path refused: ' + str(item))
    if must_exist:
        require(p.is_file(), 'Missing regular file: ' + str(p))
    return p


def strict_json(text):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'Duplicate JSON key: ' + key)
            out[key] = value
        return out
    def constant(value):
        raise ValueError('Nonfinite JSON value: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def load_document(path):
    p = safe_path(path)
    require(p.stat().st_size <= 2_000_000, 'JSON document too large')
    raw = p.read_bytes()
    data = strict_json(raw.decode('utf-8'))
    require(type(data) is dict, 'Expected JSON object')
    return p, data, hashlib.sha256(raw).hexdigest()


def string(value, name, nullable=False):
    if nullable and value is None:
        return None
    require(type(value) is str and 0 < len(value) <= 4096 and '\x00' not in value, 'Invalid ' + name)
    return value


def number(value, name, nullable=True, maximum=None):
    if nullable and value is None:
        return None
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, 'Invalid ' + name)
    require(maximum is None or value <= maximum, 'Out of range ' + name)
    return value


def integer(value, name, nullable=True):
    if nullable and value is None:
        return None
    require(type(value) is int and value >= 0, 'Invalid ' + name)
    return value


def digest(value, name, nullable=False):
    if nullable and value is None:
        return None
    require(type(value) is str and HEX.fullmatch(value), 'Invalid SHA256 ' + name)
    return value


def timestamp(value, name):
    if value is None:
        return None
    string(value, name)
    try:
        t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid timestamp ' + name) from exc
    require(t.utcoffset() is not None, 'Timestamp lacks timezone: ' + name)
    return t


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


@contextmanager
def database(path):
    """WAL plus BEGIN IMMEDIATE serialize competing writers; all SQL is bound."""
    p = safe_path(path, must_exist=False)
    require(p.parent.is_dir(), 'Database parent must already exist')
    for suffix in ('-wal', '-shm', '-journal'):
        safe_path(str(p) + suffix, must_exist=False)
    con = sqlite3.connect(str(p), timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.execute('PRAGMA busy_timeout=30000')
        con.execute('PRAGMA foreign_keys=ON')
        # Initial WAL creation may return SQLITE_BUSY immediately despite the
        # connection busy handler. Retry only this setup statement, never an
        # arbitrary transaction, with a monotonic deadline.
        deadline = time.monotonic() + 30
        while True:
            try:
                con.execute('PRAGMA journal_mode=WAL')
                break
            except sqlite3.OperationalError as exc:
                code = getattr(exc, 'sqlite_errorcode', 0) & 255
                if code not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) or time.monotonic() >= deadline:
                    raise
                time.sleep(.01)
        con.execute('BEGIN IMMEDIATE')
        version = con.execute('PRAGMA user_version').fetchone()[0]
        require(version in (0, SCHEMA), 'Unsupported registry schema')
        if version == 0:
            con.execute('''CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL,
                task_id TEXT NOT NULL, project TEXT NOT NULL, provider TEXT NOT NULL,
                model TEXT NOT NULL, domain TEXT NOT NULL, task_type TEXT NOT NULL,
                difficulty TEXT, dataset TEXT, task_family TEXT, model_config TEXT NOT NULL,
                status TEXT NOT NULL, truncated INTEGER NOT NULL,
                queued_at TEXT, started_at TEXT, finished_at TEXT,
                elapsed_seconds REAL, queue_seconds REAL, tokens TEXT NOT NULL, cost TEXT,
                output_sha256 TEXT, output_path TEXT, source_path TEXT NOT NULL,
                raw_json TEXT NOT NULL, imported_at TEXT NOT NULL)''')
            con.execute('''CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, evaluation_id TEXT UNIQUE NOT NULL,
                run_id TEXT NOT NULL REFERENCES runs(run_id), source_sha256 TEXT NOT NULL,
                evaluator_type TEXT NOT NULL, evaluator_id TEXT NOT NULL,
                evaluator_model TEXT, rubric_version TEXT NOT NULL,
                verdict TEXT NOT NULL, tests TEXT NOT NULL, scores TEXT, score REAL,
                review_seconds REAL, rework_seconds REAL,
                evidence_path TEXT NOT NULL, evidence_sha256 TEXT NOT NULL,
                output_sha256 TEXT, evaluated_at TEXT,
                recorded_at TEXT NOT NULL, raw_json TEXT NOT NULL)''')
            con.execute('CREATE INDEX IF NOT EXISTS evaluation_runs ON evaluations(run_id,id)')
            con.execute('PRAGMA user_version=1')
        yield con
        con.execute('COMMIT')
    except BaseException:
        if con.in_transaction:
            con.execute('ROLLBACK')
        raise
    finally:
        con.close()


def validate_run(data, source):
    require(type(data.get('schema')) is int and data['schema'] == 1 and data.get('event') == 'finished', 'Only final runner schema1 metrics accepted')
    for name in ('run_id', 'task_id', 'project', 'provider', 'model', 'domain', 'task_type'):
        string(data.get(name), name)
    for name in ('difficulty', 'dataset', 'task_family', 'parent_task_id'):
        string(data.get(name), name, True)
    require(data.get('status') in TERMINAL, 'Run is not in a terminal state')
    require(type(data.get('truncated')) is bool, 'truncated must be explicit boolean')
    require(data['status'] != 'INCOMPLETE_LENGTH' or data['truncated'], 'Truncated state without flag')
    config = data.get('model_config', {})
    require(type(config) is dict, 'model_config must be an object')
    mode = data.get('execution_mode', config.get('execution_mode', 'legacy_unspecified'))
    require(mode in ('review', 'execution', 'legacy_unspecified'), 'Unknown execution mode')
    require(config.get('execution_mode', mode) == mode, 'Conflicting execution modes')
    for key in EXECUTION_COUNTS:
        integer(data.get(key), key)
    require(data.get('test_failures') is None or data.get('test_runs') is None or
            data['test_failures'] <= data['test_runs'], 'More failed tests than test executions')
    json_text(config)  # rejects nested NaN/Infinity too
    times = [timestamp(data.get(k), k) for k in ('queued_at', 'started_at', 'finished_at')]
    for a, b in ((times[0], times[1]), (times[1], times[2])):
        require(a is None or b is None or a <= b, 'Timestamps out of order')
    number(data.get('elapsed_seconds'), 'elapsed_seconds')
    number(data.get('queue_delay_seconds'), 'queue_delay_seconds')
    tokens = data.get('tokens')
    tokens = {} if tokens is None else tokens
    require(type(tokens) is dict, 'tokens must be an object')
    for key, value in tokens.items():
        string(key, 'token kind'); integer(value, 'tokens.' + key)
    cost = data.get('cost')
    if cost is not None:
        require(type(cost) is dict, 'cost must be observed object or null')
        number(cost.get('value'), 'cost.value', False)
        string(cost.get('currency'), 'cost.currency')
        string(cost.get('source'), 'cost.source')
    number(data.get('cost_observed'), 'cost_observed')
    if data.get('cost_observed') is not None:
        string(data.get('cost_source'), 'cost_source')
    require(data.get('automatic_quality_score') is None, 'Automatic quality score refused')
    for key in ('input_sha256', 'prompt_sha256'):
        digest(data.get(key), key, True)
    output_hash = digest(data.get('output_sha256'), 'output_sha256', True)
    output = None
    if output_hash is not None:
        given = data.get('output_path', 'answer.txt')
        string(given, 'output_path')
        output = Path(given)
        if not output.is_absolute():
            output = source.parent / output
        output = safe_path(output)
        require(sha256(output) == output_hash, 'Output bytes do not match metrics SHA')
    if data['status'] == SUCCESS and not data['truncated']:
        require(output_hash is not None, 'Successful output must be hash-bound')
    return output


def import_run(db_path, metrics_path):
    """Idempotent only for identical run_id AND original metrics bytes."""
    source, data, source_hash = load_document(metrics_path)
    output = validate_run(data, source)
    with database(db_path) as con:
        old = con.execute('SELECT source_sha256 FROM runs WHERE run_id=?', (data['run_id'],)).fetchone()
        if old:
            require(old['source_sha256'] == source_hash, 'run_id conflict: different metrics bytes')
            return 'duplicate'
        values = dict(run_id=data['run_id'], source_sha256=source_hash,
            **{k: data[k] for k in ('task_id', 'project', 'provider', 'model', 'domain', 'task_type', 'status')},
            **{k: data.get(k) for k in ('difficulty', 'dataset', 'task_family', 'queued_at', 'started_at', 'finished_at', 'elapsed_seconds', 'output_sha256')},
            truncated=int(data['truncated']), model_config=json_text(data.get('model_config', {})),
            queue_seconds=data.get('queue_delay_seconds'), tokens=json_text(data.get('tokens') or {}),
            cost=json_text(data['cost']) if data.get('cost') is not None else None,
            output_path=str(output) if output else None, source_path=str(source),
            raw_json=json_text(data), imported_at=utc_now())
        keys = list(values)
        con.execute('INSERT INTO runs (' + ','.join(keys) + ') VALUES (' + ','.join('?' for _ in keys) + ')', [values[k] for k in keys])
    return 'imported'


def weighted_score(scores):
    """Rubric1 puts 40% on correctness, then relevance25/completeness20/action15."""
    if scores is None:
        return None
    require(type(scores) is dict and set(scores) == set(WEIGHTS), 'Four score dimensions required')
    for key, value in scores.items():
        number(value, key, False, 5)
    return sum(scores[key] * weight / 5 for key, weight in WEIGHTS.items())


def model_identity(name):
    return name.strip().casefold().rsplit('/', 1)[-1]


def add_evaluation(db_path, evaluation_path):
    """Append a separately authored evidence-bound assessment; never overwrite."""
    source, data, source_hash = load_document(evaluation_path)
    for name in ('evaluation_id', 'run_id', 'evaluator_id', 'rubric_version', 'justification'):
        string(data.get(name), name)
    require(data.get('evaluator_type') in ('human', 'model'), 'Explicit evaluator type required')
    require(data.get('verdict') in ('accepted', 'edited', 'rejected', 'inconclusive'), 'Invalid verdict')
    require(data.get('tests') in ('pass', 'fail', 'unknown'), 'Explicit tests status required')
    require('scores' in data, 'Missing explicit scores (use null for unknown)')
    score = weighted_score(data['scores'])
    require(data['rubric_version'] == RUBRIC or score is None, 'Unknown scoring rubric version')
    require(data['verdict'] != 'inconclusive' or score is None, 'Inconclusive assessment cannot assign score')
    for field in ('review_seconds', 'rework_seconds'):
        number(data.get(field), field)
    timestamp(data.get('evaluated_at'), 'evaluated_at')
    require('output_sha256' in data, 'Explicit output SHA required (null if absent)')
    digest(data.get('output_sha256'), 'output_sha256', True)
    digest(data.get('evidence_sha256'), 'evidence_sha256')
    evidence = Path(string(data.get('evidence_path'), 'evidence_path'))
    if not evidence.is_absolute():
        evidence = source.parent / evidence
    evidence = safe_path(evidence)
    require(sha256(evidence) == data['evidence_sha256'], 'Evidence bytes do not match SHA')
    with database(db_path) as con:
        run = con.execute('SELECT * FROM runs WHERE run_id=?', (data['run_id'],)).fetchone()
        require(run is not None, 'Unknown run_id')
        require(run['output_sha256'] == data['output_sha256'], 'Assessment concerns a different output')
        if run['output_path']:
            require(sha256(safe_path(run['output_path'])) == data['output_sha256'], 'Output changed since import')
        else:
            require(data['output_sha256'] is None and score is None, 'Absent output cannot receive quality score')
        evaluator_model = data.get('evaluator_model')
        if data['evaluator_type'] == 'model':
            string(evaluator_model, 'evaluator_model')
            require(model_identity(evaluator_model) != model_identity(run['model']), 'Author model cannot assess itself')
        else:
            require(evaluator_model is None, 'Human evaluator must not claim model identity')
        require(model_identity(data['evaluator_id']) != model_identity(run['model']), 'Evaluator equals author model')
        eligible = run['status'] == SUCCESS and not run['truncated']
        require(eligible or (score is None and data['verdict'] == 'inconclusive'), 'Failed/truncated runs cannot receive quality verdict or score')
        old = con.execute('SELECT id,source_sha256 FROM evaluations WHERE evaluation_id=?', (data['evaluation_id'],)).fetchone()
        if old:
            require(old['source_sha256'] == source_hash, 'evaluation_id conflict')
            return old['id']
        values = dict(evaluation_id=data['evaluation_id'], run_id=data['run_id'], source_sha256=source_hash,
            **{k: data[k] for k in ('evaluator_type', 'evaluator_id', 'rubric_version', 'verdict', 'tests', 'evidence_sha256', 'output_sha256')},
            evaluator_model=evaluator_model, scores=json_text(data['scores']) if score is not None else None,
            score=score, review_seconds=data.get('review_seconds'), rework_seconds=data.get('rework_seconds'),
            evidence_path=str(evidence), evaluated_at=data.get('evaluated_at'), recorded_at=utc_now(), raw_json=json_text(data))
        keys = list(values)
        cur = con.execute('INSERT INTO evaluations (' + ','.join(keys) + ') VALUES (' + ','.join('?' for _ in keys) + ')', [values[k] for k in keys])
        return cur.lastrowid


def observed(values):
    """Nearest-rank p90; N and unknown count always accompany statistics."""
    values = list(values)
    clean = sorted(number(v, 'statistic value', False) for v in values if v is not None)
    return dict(n=len(clean), unknown=len(values)-len(clean), mean=statistics.mean(clean) if clean else None, median=statistics.median(clean) if clean else None,
                p90=clean[math.ceil(.9*len(clean))-1] if clean else None,
                total=sum(clean) if clean else None)


def build_report(db_path, min_evaluated=10, min_tasks=3):
    """Aggregate comparable configurations; failures remain visible but unscored.

    Latest assessment is used per run. Review/rework durations are incremental
    measurements for each assessment, never cumulative totals. Earlier records
    and time remain visible. Suggestions never mix rubrics or model options.
    """
    require(type(min_evaluated) is int and min_evaluated >= 10, 'Suggestion threshold must be >=10')
    require(type(min_tasks) is int and min_tasks >= 3, 'Distinct-task threshold must be >=3')
    with database(db_path) as con:
        runs = [dict(r) for r in con.execute('SELECT * FROM runs ORDER BY run_id')]
        evaluations = [dict(e) for e in con.execute('SELECT * FROM evaluations ORDER BY id')]
    latest, history = {}, {}
    for evaluation in evaluations:
        latest[evaluation['run_id']] = evaluation
        history.setdefault(evaluation['run_id'], []).append(evaluation)
    fields = ('project', 'provider', 'domain', 'task_type', 'difficulty', 'dataset', 'task_family', 'model', 'execution_mode', 'model_config')
    grouped = {}
    for run in runs:
        # Derive modes without rewriting immutable historical records. Older
        # runs remain explicitly unknown; never relabel a text review as work.
        raw = json.loads(run['raw_json'])
        run['execution_mode'] = raw.get('execution_mode', raw.get('model_config', {}).get('execution_mode', 'legacy_unspecified'))
        grouped.setdefault(tuple(run[k] for k in fields), []).append(run)
    cohorts = []
    for key, group in sorted(grouped.items(), key=lambda x: json_text(x[0])):
        selected = [latest[r['run_id']] for r in group if r['run_id'] in latest]
        scored = [e for e in selected if e['score'] is not None]
        eligible = [r for r in group if r['status'] == SUCCESS and not r['truncated']]
        attempts = [e for r in group for e in history.get(r['run_id'], [])]
        human = [e for e in attempts if e['evaluator_type'] == 'human']
        config = dict(zip(fields, key)); config['model_config'] = json.loads(config['model_config'])
        run_map = {r['run_id']:r for r in group}
        rubrics = []
        for rubric in sorted({e['rubric_version'] for e in selected}):
            ev = [e for e in selected if e['rubric_version'] == rubric and e['score'] is not None]
            tasks = {run_map[e['run_id']]['task_id'] for e in ev}
            sufficient = len(ev) >= min_evaluated and len(tasks) >= min_tasks
            rubrics.append(dict(rubric_version=rubric, n_evaluated=len(ev), n_distinct_tasks=len(tasks),
                score=observed(e['score'] for e in ev),
                accepted_without_edits=sum(e['verdict']=='accepted' for e in ev),
                accepted_after_edits=sum(e['verdict']=='edited' for e in ev),
                rejected=sum(e['verdict']=='rejected' for e in ev),
                acceptance_without_edits_rate=sum(e['verdict']=='accepted' for e in ev)/len(ev) if ev else None,
                acceptance_after_edits_rate=sum(e['verdict']=='edited' for e in ev)/len(ev) if ev else None,
                suggestion='Human comparison permitted; no automatic routing' if sufficient else 'Insufficient evidence',
                suggestion_eligible=sufficient))
        token_keys = sorted({'input','output','reasoning','total','cache_read','cache_write'} | {k for r in group for k in json.loads(r['tokens'])})
        token_stats = {k:observed(json.loads(r['tokens']).get(k) for r in group) for k in token_keys}
        costs = {}
        unitless_costs = {}
        for run in group:
            if run['cost']:
                cost = json.loads(run['cost'])
                costs.setdefault((cost['currency'], cost['source']), []).append(cost['value'])
            raw_run = json.loads(run['raw_json'])
            if raw_run.get('cost_observed') is not None:
                unitless_costs.setdefault(raw_run['cost_source'], []).append(raw_run['cost_observed'])
        cohorts.append(dict(cohort=config, cohort_id=hashlib.sha256(json_text(config).encode()).hexdigest()[:12], n_runs=len(group), n_tasks=len({r['task_id'] for r in group}),
            n_evaluated=len(scored), n_unevaluated=len(group)-len(scored), n_assessed=len(selected),
            n_successful=len(eligible), n_failed=sum(r['status'] not in (SUCCESS,'INCOMPLETE_LENGTH') for r in group),
            n_truncated=sum(bool(r['truncated']) for r in group),
            execution_status_counts={s:sum(r['status']==s for r in group) for s in sorted(TERMINAL)},
            n_unknown_quality=len(group)-len(scored),
            model_seconds=observed(r['elapsed_seconds'] for r in eligible),
            all_attempt_seconds=observed(r['elapsed_seconds'] for r in group),
            queue_seconds=observed(r['queue_seconds'] for r in group),
            human_review_seconds=observed(e['review_seconds'] for e in human),
            human_rework_seconds=observed(e['rework_seconds'] for e in human),
            all_review_seconds=observed(e['review_seconds'] for e in attempts),
            all_rework_seconds=observed(e['rework_seconds'] for e in attempts),
            latest_tests={k:sum(e['tests']==k for e in selected) for k in ('pass','fail','unknown')},
            execution_counts={k:observed(json.loads(r['raw_json']).get(k) for r in group) for k in EXECUTION_COUNTS},
            tokens_observed=token_stats, cost_observed=[dict(currency=k[0],source=k[1],**observed(v)) for k,v in sorted(costs.items())],
            cost_without_currency_observed=[dict(currency=None,source=k,**observed(v)) for k,v in sorted(unitless_costs.items())],
            cost_unknown=len(group)-sum(bool(r['cost']) for r in group), evaluations_by_rubric=rubrics))
    return dict(schema=SCHEMA, generated_at=utc_now(), hardware_access=False, automatic_routing=False,
        thresholds=dict(min_evaluated=min_evaluated,min_distinct_tasks=min_tasks),
        n_runs=len(runs), n_evaluations_history=len(evaluations), cohorts=cohorts,
        interpretation='Unknown is null, never zero. Quality excludes failed/truncated runs; reliability and all-attempt time include them. Cohort suggestions are not a causal model ranking.')


def csv_report(report):
    stream = io.StringIO(newline='')
    fields = ['cohort_id','project','provider','domain','task_type','difficulty','dataset','task_family','model','execution_mode','model_config',
              'n_runs','n_tasks','n_evaluated','n_unevaluated','n_failed','n_truncated',
              'model_seconds_mean','model_seconds_median','model_seconds_p90','queue_seconds_median','all_review_seconds_total','all_rework_seconds_total','human_review_seconds_total','human_rework_seconds_total',
              'rubric_version','score_mean','score_median','accepted_without_edits','accepted_after_edits','suggestion']
    fields += [key + suffix for key in EXECUTION_COUNTS for suffix in ('_total', '_unknown')]
    writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
    def cell(value):
        # Export untrusted task labels safely to common spreadsheet programs.
        if isinstance(value,str) and value.startswith(('=','+','-','@','\t','\r')):
            return "'"+value
        return '' if value is None else value
    for c in report['cohorts']:
        for r in c['evaluations_by_rubric'] or [{}]:
            row=dict(c['cohort']);row['model_config']=json_text(row['model_config']);row['cohort_id']=c['cohort_id']
            for name, count in c['execution_counts'].items():
                row[name+'_total'], row[name+'_unknown'] = count['total'], count['unknown']
            row.update({k:c[k] for k in ['n_runs','n_tasks','n_evaluated','n_unevaluated','n_failed','n_truncated']})
            row.update(model_seconds_mean=c['model_seconds']['mean'],model_seconds_median=c['model_seconds']['median'],model_seconds_p90=c['model_seconds']['p90'],
                all_review_seconds_total=c['all_review_seconds']['total'],all_rework_seconds_total=c['all_rework_seconds']['total'],
                queue_seconds_median=c['queue_seconds']['median'],human_review_seconds_total=c['human_review_seconds']['total'],
                human_rework_seconds_total=c['human_rework_seconds']['total'],rubric_version=r.get('rubric_version'),
                score_mean=r.get('score',{}).get('mean'),score_median=r.get('score',{}).get('median'),accepted_without_edits=r.get('accepted_without_edits'),
                accepted_after_edits=r.get('accepted_after_edits'),suggestion=r.get('suggestion','Insufficient evidence'))
            writer.writerow({k:cell(v) for k,v in row.items()})
    return stream.getvalue()


def html_report(report):
    esc=lambda x:html.escape('inconnu' if x is None else str(x))
    rows=[]
    for c in report['cohorts']:
        label=c['cohort']; quality=c['evaluations_by_rubric']
        score=' ; '.join('rubrique '+r['rubric_version']+': moyenne '+esc(r['score']['mean'])+', médiane '+esc(r['score']['median'])+' /100 (N='+str(r['n_evaluated'])+')' for r in quality) or 'non évalué'
        suggestion='Comparaison humaine possible' if any(r['suggestion_eligible'] for r in quality) else 'Données insuffisantes'
        counts = [esc(c['execution_counts'][key]['total']) +
                  (' (' + str(c['execution_counts'][key]['unknown']) + ' inconnus)'
                   if c['execution_counts'][key]['unknown'] else '') for key in EXECUTION_COUNTS]
        cells=[label['model'],label['execution_mode'],*counts,label['domain']+'/'+label['task_type'],label['difficulty'],
               c['n_runs'],c['n_evaluated'],c['n_failed'],c['n_truncated'],
               c['model_seconds']['median'],c['model_seconds']['p90'],c['queue_seconds']['median'],
               c['all_review_seconds']['total'],c['all_rework_seconds']['total'],score,suggestion]
        detail='<td><details><summary>'+esc(c['cohort_id'])+'</summary><pre>'+esc(json.dumps(label,ensure_ascii=False,indent=2))+'</pre></details></td>'
        rows.append('<tr>'+detail+''.join('<td>'+esc(v)+'</td>' for v in cells)+'</tr>')
    headings=['Cohorte / détails','Modèle','Mode','Requêtes modèle','Appels outils','Tests lancés','Tests échoués','Domaine / tâche','Difficulté','Exécutions','Évaluées','Échecs','Tronquées','Médiane modèle (s)','p90 modèle (s)','Attente médiane (s)','Revue tous évaluateurs (s)','Reprise tous évaluateurs (s)','Note moyenne / médiane','Suggestion']
    return '<!doctype html><html lang="fr"><meta charset="utf-8"><title>Suivi des modèles</title><style>body{font:15px system-ui;margin:2rem;color:#163043}table{border-collapse:collapse;width:100%}th,td{padding:.55rem;border-bottom:1px solid #ccd6df;text-align:left}th{background:#e9f0f5}tr:nth-child(even){background:#f6f8fa}.wrap{overflow:auto}p{max-width:95ch}</style><h1>Suivi des modèles</h1><p>Généré '+esc(report['generated_at'])+'. '+str(report['n_runs'])+' exécutions ; '+str(report['n_evaluations_history'])+' évaluations conservées.</p><p>Les durées modèle concernent les réponses complètes. Les échecs et troncatures restent comptés. « inconnu » signifie non mesuré. Rubrique 1 : exactitude 40 %, pertinence 25 %, complétude 20 %, utilisabilité 15 %. Aucun routage automatique ; seuil '+str(report['thresholds']['min_evaluated'])+' sorties évaluées et '+str(report['thresholds']['min_distinct_tasks'])+' tâches distinctes par cohorte.</p><div class="wrap"><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in headings)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div><p>Les détails de chaque cohorte indiquent projet, fournisseur, jeu de données, famille et configuration exacte du modèle. Les durées de revue et reprise sont les incréments de chaque évaluation, pas des cumuls réimportés. Le JSON distingue aussi les évaluateurs humains. Une association statistique ne prouve pas qu’un modèle cause une meilleure qualité.</p></html>\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    imp=sub.add_parser('import');imp.add_argument('metrics',type=Path)
    ev=sub.add_parser('evaluate');ev.add_argument('assessment',type=Path)
    rep=sub.add_parser('report');rep.add_argument('--format',choices=['json','csv','html'],default='json');rep.add_argument('--out',type=Path)
    rep.add_argument('--min-evaluated',type=int,default=10);rep.add_argument('--min-tasks',type=int,default=3)
    args=parser.parse_args()
    if args.command=='import':print(json.dumps({'status':import_run(args.db,args.metrics)}));return
    if args.command=='evaluate':print(json.dumps({'evaluation_id':add_evaluation(args.db,args.assessment)}));return
    report=build_report(args.db,args.min_evaluated,args.min_tasks)
    result=json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n' if args.format=='json' else csv_report(report) if args.format=='csv' else html_report(report)
    if args.out:
        out=safe_path(args.out,must_exist=False)
        with out.open('x',encoding='utf-8',newline='') as stream:stream.write(result)
    else:print(result,end='')


if __name__=='__main__':
    main()
