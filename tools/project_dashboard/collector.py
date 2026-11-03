"""Local, bounded evidence collection for the three project workstreams.

data.json is an explicit inventory, not a crawler. Missing, malformed, changed
or oversized evidence becomes UNKNOWN. This module never connects to a board,
network, model provider or shell, and never returns process command lines.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

MAX_BYTES = 262144
ALLOWED_PREFIXES = ('TESTS/', 'games/luma3d/candidates/', 'tang/impl/', 'ARCHI/')
ALLOWED_DOCUMENTS = {
    'games/luma3d/README.md', 'games/luma3d/CONTENT_STATUS.md',
    'games/luma3d/DESIGN.md',
}
ALLOWED_SUFFIXES = {'.json', '.md', '.txt'}
BENCHMARK_REPORTS = {'benchmark_cm1_a.log','benchmark_candidate.log','benchmark_cm1_b.log'}


def _iso(value):
    if type(value) in (int, float):
        try:return datetime.fromtimestamp(value, timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError):return None
    if isinstance(value, str):
        try:return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat()
        except ValueError:return None
    return None


def _field(value, dotted):
    for piece in dotted.split('.') if dotted else []:
        if isinstance(value, list) and piece.isdigit():value = value[int(piece)]
        elif isinstance(value, dict):value = value[piece]
        else:raise KeyError(piece)
    return value


def evidence(root, name):
    """Return only allowlisted small reports; never arbitrary paths or logs."""
    if (not isinstance(name, str) or
            (not name.startswith(ALLOWED_PREFIXES) and name not in ALLOWED_DOCUMENTS) or
            Path(name).is_absolute() or '..' in Path(name).parts or
            any(part.startswith('.') or any(s in part.lower() for s in ('secret','credential'))
                for part in Path(name).parts) or
            (Path(name).suffix.lower() not in ALLOWED_SUFFIXES and Path(name).name not in BENCHMARK_REPORTS)):
        return None, 'Chemin de preuve refusé'
    path = root/name
    try:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            return None, 'Lien de preuve refusé'
        with path.open('rb') as stream:raw = stream.read(MAX_BYTES+1)
        if len(raw) > MAX_BYTES:return None, 'Preuve trop volumineuse'
        text = raw.decode('utf-8')
        value = json.loads(text) if path.suffix == '.json' else text
        return dict(value=value, text=text, sha256=hashlib.sha256(raw).hexdigest(),
                    time=_iso(path.stat().st_mtime)), None
    except (OSError, UnicodeError, ValueError):
        return None, 'Preuve absente ou illisible'


def _check(root, spec):
    """A successful read alone is not a PASS: declared assertions must match."""
    report, error = evidence(root, spec.get('evidence'))
    out = dict(level=spec.get('level','unknown'), status='UNKNOWN',
               detail=spec.get('detail',''), evidence=spec.get('evidence'))
    if error:
        out['detail'] += ' — '+error
        return out
    if spec.get('sha256') and report['sha256'] != spec['sha256']:
        out['detail'] += ' — Empreinte différente de la preuve revue'
        return out
    conditions = spec.get('conditions', [])
    if not conditions and not spec.get('contains') and not spec.get('sha256'):
        out['detail'] += ' — Aucune assertion de résultat déclarée'
        return out
    try:
        for condition in conditions:
            actual = _field(report['value'], condition['field'])
            expected = condition['equals']
            if type(actual) is not type(expected) or actual != expected:
                out['status'] = spec.get('on_mismatch','UNKNOWN')
                out['detail'] += ' — Résultat différent de l’attente enregistrée'
                return out
        if spec.get('contains') and spec['contains'] not in report['text']:
            out['detail'] += ' — Marqueur attendu absent'
            return out
    except (KeyError, IndexError, TypeError):
        out['detail'] += ' — Champ de preuve manquant'
        return out
    out['status'] = spec.get('status','UNKNOWN')
    return out


def _workers(root):
    try:
        if __package__:
            from .workers import collect_workers
        else:
            from workers import collect_workers
        return collect_workers(root)
    except (ImportError, OSError, ValueError, TypeError):
        return []


def _label_workers(rows, labels):
    """Decorate observed tasks with maintained titles; keep identity/state intact.

    Labels are descriptions, never process-liveness evidence. No task prompts
    or command lines are read to infer a title.
    """
    if not isinstance(labels, dict):return rows
    result=[]
    for row in rows:
        out=dict(row)
        label=labels.get(row.get('task'))
        if isinstance(label, dict):
            for field in ('title','detail'):
                value=label.get(field)
                if isinstance(value,str) and len(value)<=300:out[field]=value
        result.append(out)
    return result


def _build(root, spec):
    """Never use a stale 'running' file as a process-liveness proof."""
    out = dict(name=spec['name'], state='UNKNOWN', detail=spec.get('detail',''),
               evidence=spec.get('result') or spec.get('started'))
    final, _ = evidence(root, spec.get('qualification',''))
    if final is not None:
        passed = final['value'].get('passed') if isinstance(final['value'],dict) else None
        if type(passed) is bool:
            out.update(state='TIMING_PASS' if passed else 'FAIL', evidence=spec['qualification'])
            out['detail'] += ' — Rapport final local ; qualification carte distincte'
            return out
    result, _ = evidence(root, spec.get('result',''))
    if result is not None and isinstance(result['value'],dict) and type(result['value'].get('returncode')) is int:
        out['state'] = 'ROUTED' if result['value']['returncode'] == 0 else 'FAIL'
        out['detail'] += ' — Routage terminé ; timing/carte à qualifier séparément'
        return out
    started, error = evidence(root, spec.get('started',''))
    out['evidence'] = spec.get('started')
    if error:
        out['detail'] += ' — Démarrage non documenté';return out
    state = started['value']
    if not isinstance(state, dict):return out
    pid = state.get('pid')
    tick = state.get('start_ticks', state.get('process_start_ticks', spec.get('start_ticks')))
    try:
        if __package__:
            from .workers import process_state
        else:
            from workers import process_state
        current = process_state(pid, tick)
        if current['state'] == 'RUNNING':out['state'] = 'RUNNING'
        elif current['state'] in ('ABSENT','REUSED'):
            out['state'] = 'STOPPED_NO_RESULT'
        else:out['state'] = 'UNKNOWN'
    except (ImportError, OSError, ValueError, TypeError, KeyError):pass
    out['detail'] += ' — Aucune qualification finale ; PID seul ne prouve pas une tâche active'
    return out


def collect(root: Path) -> dict:
    """Collect a current local snapshot; hardware/load labels remain historical."""
    root = Path(root).resolve()
    registry_path = root/'tools/project_dashboard/data.json'
    try:
        raw = registry_path.read_bytes()
        if len(raw) > MAX_BYTES:raise ValueError('Registry too large')
        registry = json.loads(raw)
    except (OSError, ValueError):
        registry = dict(topics=[], builds=[], events=[])
    topics=[]
    for item in registry.get('topics',[]):
        features=[]
        for feature in item.get('features',[]):
            tests=[_check(root, x) for x in feature.get('tests',[])]
            state=feature.get('state','UNKNOWN')
            if not tests and state in ('TODO','PLANNED','PENDING'):
                tests=[dict(level='planned',status='NOT_TESTED',detail='Fonction prévue ; aucune preuve de validation.',evidence=None)]
            elif not tests or all(t['status']=='UNKNOWN' for t in tests):state='UNKNOWN'
            elif any(t['status']=='UNKNOWN' for t in tests):state='PARTIAL'
            features.append(dict(name=feature['name'],state=state,tests=tests))
        known=any(t['status']!='UNKNOWN' for f in features for t in f['tests'])
        loaded_check=_check(root,item.get('loaded_check',{}))
        loaded=item.get('loaded','INCONNU') if loaded_check['status']!='UNKNOWN' else 'INCONNU — dernière charge non prouvée'
        done=[]
        for entry in item.get('done',[]):
            if _check(root,entry)['status'] in ('PASS','OBSERVED'):done.append(entry['detail'])
        topics.append(dict(id=item['id'],title=item['title'],status=item.get('status','PARTIAL') if known else 'UNKNOWN',
            summary=item.get('summary',''),loaded=loaded,done=done,next=item.get('next',[]),features=features))
    events=[]
    for item in registry.get('events',[]):
        report, error=evidence(root,item.get('evidence'))
        if error:continue
        try:stamp=_iso(_field(report['value'],item.get('time_field',''))) if item.get('time_field') else None
        except (KeyError,TypeError,IndexError):stamp=None
        events.append(dict(time=stamp or report['time'],topic=item['topic'],title=item['title'],
                           detail=item['detail'],evidence=item['evidence']))
    events.sort(key=lambda x:x['time'] or '',reverse=True)
    return dict(generated_at=datetime.now(timezone.utc).isoformat(),topics=topics,
                workers=_label_workers(_workers(root),registry.get('worker_labels',{})),
                builds=[_build(root,x) for x in registry.get('builds',[])],events=events[:30])
