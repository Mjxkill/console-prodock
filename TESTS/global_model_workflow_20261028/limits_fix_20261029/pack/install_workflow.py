#!/usr/bin/env python3
"""Stage/check/install the explicit global workflow pack in a chosen CODEX_HOME.

Publication is atomic PER FILE, with the manifest committed last. This is not a
multi-file transaction. Existing data, settings and unrelated files are never
replaced. Source and installed hashes are checked before any publication.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import uuid

INSTALLABLE = ('runner.py', 'workflow_common.py', 'event_parser.py', 'process_io.py', 'dispatch_queue.py',
               'metrics.py', 'check_code_size.py', 'install_workflow.py',
               'GLOBAL_AGENTS.md', 'WORKFLOW.md', 'TEST_RECORD_TEMPLATE.md', 'QUICKSTART.md',
               'agent_runner.py', 'agent_backend.py', 'agent_core.py', 'agent_events.py',
               'agent_provider.py', 'agent_audit.py', 'agent_evidence.py', 'agent_queue.py',
               'agent_isolation.py', 'agent_box.py', 'agent_mcp.py', 'agent_mcp_launcher.py',
               'test_agent_isolation.py', 'AGENT_EXECUTION.md')
MANIFEST = 'install_manifest.json'
BEGIN = b'<!-- BEGIN MICHAEL MULTIMODEL WORKFLOW v1 -->'
END = b'<!-- END MICHAEL MULTIMODEL WORKFLOW v1 -->'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(value, exists=False):
    p = Path(value).expanduser()
    need('..' not in p.parts, 'Parent traversal refused')
    p = p.absolute()
    for item in (p, *p.parents):
        need(not item.is_symlink(), 'Symlink refused: ' + str(item))
    if exists:
        need(p.exists(), 'Missing path: ' + str(p))
    return p


def sha(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            need(k not in result, 'Duplicate manifest key')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def file_bytes(path):
    path = safe_path(path, True)
    need(path.is_file() and path.stat().st_size <= 2_000_000, 'Expected bounded regular file: ' + str(path))
    return path.read_bytes()


def manifest_data(source):
    files = {}
    for name in INSTALLABLE:
        raw = file_bytes(source / name)
        raw.decode('utf-8')
        if name.endswith('.py'):
            need(len(raw.splitlines()) <= 1000, 'Project code exceeds 1000 lines: ' + name)
        files[name] = dict(sha256=sha(raw), size=len(raw))
    return dict(schema=1, files=files)


def atomic_bytes(path, raw, mode=0o600):
    """Same-directory temp + fsync + replace, preserving permissions when set."""
    safe_path(path)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def make_manifest(source):
    source = safe_path(source, True)
    raw = (json.dumps(manifest_data(source), sort_keys=True, indent=2) + '\n').encode()
    target = safe_path(source / MANIFEST)
    if target.exists() and file_bytes(target) == raw:
        return dict(changed=False, manifest_sha256=sha(raw))
    atomic_bytes(target, raw)
    return dict(changed=True, manifest_sha256=sha(raw))


def verified_source(source):
    raw = file_bytes(source / MANIFEST)
    doc = strict_json(raw)
    need(doc == manifest_data(source), 'Source manifest mismatch: regenerate only after review')
    # Keep exact reviewed bytes in memory; later writes never recopy mutable files.
    content = {name:file_bytes(source/name) for name in INSTALLABLE}
    for name, data in content.items():
        need(sha(data) == doc['files'][name]['sha256'], 'Source changed during validation')
    return raw, doc, content


def merge_block(existing, block):
    """Replace only our markers, preserve every byte outside the managed block."""
    existing.decode('utf-8'); block.decode('utf-8')
    need(block.count(BEGIN) == block.count(END) == 1 and block.startswith(BEGIN), 'Invalid policy block')
    need(block.rstrip().endswith(END), 'Policy contains content outside markers')
    generic_begin = b'<!-- BEGIN MICHAEL MULTIMODEL WORKFLOW'
    generic_end = b'<!-- END MICHAEL MULTIMODEL WORKFLOW'
    if generic_begin in existing or generic_end in existing:
        need(existing.count(BEGIN) == existing.count(END) == 1, 'Unknown, duplicate or partial policy markers')
        need(existing.count(generic_begin) == existing.count(generic_end) == 1, 'Ambiguous policy blocks')
        start, end = existing.index(BEGIN), existing.index(END) + len(END)
        need(start < end, 'Policy marker order')
        # Include exactly one existing line ending to keep repeated installs stable.
        if existing[end:end+2] == b'\r\n':
            end += 2
        elif existing[end:end+1] == b'\n':
            end += 1
        return existing[:start] + block + existing[end:]
    separator = b'' if not existing else b'\n' if existing.endswith(b'\n') else b'\n\n'
    return existing + separator + block


def prepare(source, home):
    """Pure validation and plan: does not create CODEX_HOME or acquire a lock."""
    source, home = safe_path(source, True), safe_path(home)
    need(source.is_dir(), 'Source pack must be a directory')
    target = safe_path(home/'model-workflow')
    need(not target.exists() or target.is_dir(), 'Code destination is not a directory')
    raw, document, content = verified_source(source)
    old_manifest = safe_path(target/MANIFEST)
    previous = None
    if old_manifest.exists():
        previous = strict_json(file_bytes(old_manifest))
        need(type(previous) is dict and previous.get('schema') == 1 and type(previous.get('files')) is dict, 'Invalid installed manifest')
        need(set(previous['files']) <= set(INSTALLABLE), 'Installed manifest has unknown files')
        for name, item in previous['files'].items():
            need(type(item) is dict and set(item) == {'size','sha256'}, 'Invalid installed file metadata')
            current = file_bytes(target/name)
            need(sha(current) == item['sha256'] and len(current) == item['size'], 'Installed file changed locally: ' + name)
    updates = []
    for name, data in content.items():
        destination = safe_path(target/name)
        old = file_bytes(destination) if destination.exists() else None
        if old != data:
            need(old is None or (previous is not None and name in previous['files']), 'Unmanaged conflicting file: ' + name)
            updates.append((destination, old, data))
    agents = safe_path(home/'AGENTS.md')
    override = safe_path(home/'AGENTS.override.md')
    for destination in [agents] + ([override] if override.exists() else []):
        old = file_bytes(destination) if destination.exists() else None
        new = merge_block(old or b'', content['GLOBAL_AGENTS.md'])
        if old != new:
            updates.append((destination, old, new))
    old = file_bytes(old_manifest) if old_manifest.exists() else None
    if old != raw:
        updates.append((old_manifest, old, raw))  # Publish manifest LAST.
    return dict(source=str(source),home=str(home),target=str(target),manifest_sha256=sha(raw),
        override_present=override.exists(), override_notice='Existing override will retain its content and receive the same managed policy block.' if override.exists() else None,
        publication='atomic per file; manifest last; not a multi-file transaction',
        changed=bool(updates), files=[dict(path=str(p),before_sha256=sha(old) if old is not None else None,after_sha256=sha(new),backup_required=old is not None) for p,old,new in updates]), updates


@contextmanager
def install_lock(home):
    """One installer per CODEX_HOME. No compiler/model/hardware lock is touched."""
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = safe_path(home/'.model-workflow-install.lock')
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        need(stat.S_ISREG(os.fstat(fd).st_mode), 'Install lock is not regular')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def install(source, home):
    # Refuse all source/conflict problems before creating anything in the home.
    initial, unused = prepare(source, home)
    home = safe_path(home)
    with install_lock(home):
        plan, updates = prepare(source, home)
        target = Path(plan['target']);target.mkdir(mode=0o700,exist_ok=True)
        backups = []
        for destination, old, new in updates:
            # Detect another editor after preflight before replacing its file.
            current = file_bytes(destination) if destination.exists() else None
            need(current == old, 'Destination changed after validation: ' + str(destination))
            mode = stat.S_IMODE(destination.stat().st_mode) if old is not None else 0o600
            if old is not None:
                stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                backup = destination.with_name(destination.name+'.backup.'+stamp+'.'+uuid.uuid4().hex[:8])
                fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
                with os.fdopen(fd,'wb') as stream:
                    stream.write(old);stream.flush();os.fsync(stream.fileno())
                backups.append(str(backup))
            atomic_bytes(destination,new,mode)
        # Verify installed allowlist only; unrelated data and config stay intact.
        verified_source(target)
        plan['backups'] = backups
        plan['installed'] = True
        plan['config_toml_changed'] = False
        return plan


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--home',type=Path,help='Explicit CODEX_HOME, normally ~/.codex')
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--make-manifest',action='store_true')
    group.add_argument('--prepare-only',action='store_true')
    group.add_argument('--install',action='store_true')
    args=parser.parse_args()
    if args.make_manifest:
        result=make_manifest(args.source)
    else:
        need(args.home is not None,'--home CODEX_HOME required')
        result=install(args.source,args.home) if args.install else prepare(args.source,args.home)[0]
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
