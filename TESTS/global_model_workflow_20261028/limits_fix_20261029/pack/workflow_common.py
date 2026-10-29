"""Small shared invariants for the portable text-only model workflow.

No network or process launch occurs here. Paths never follow symlinks. JSON
replacement is atomic and flushed before the parent directory is flushed.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


def need(condition, message):
    """Runtime guard, deliberately independent of Python assertion settings."""
    if not condition:
        raise ValueError(message)


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def parse_utc(value):
    need(isinstance(value, str) and value.endswith('Z'), 'UTC timestamp must end in Z')
    parsed = dt.datetime.fromisoformat(value[:-1] + '+00:00')
    need(parsed.utcoffset() == dt.timedelta(0), 'Timestamp is not UTC')
    return parsed


def identifier(value):
    need(isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_][a-zA-Z0-9_.-]{0,127}', value), 'Invalid identifier')
    return value


def safe_path(value, *, exists=True):
    """Return an absolute path after checking every existing component."""
    path = Path(value).expanduser()
    need('..' not in path.parts, 'Parent traversal is forbidden')
    path = path.absolute()
    for item in (path, *path.parents):
        need(not item.is_symlink(), 'Symlink path is forbidden')
    if exists:
        need(path.exists(), 'Required path is absent')
    return path


def prepared_text(project, value, *, maximum=200_000, suffixes=('.txt',)):
    """Read bounded prepared input; callers explicitly select text or task JSON."""
    candidate = Path(value)
    path = safe_path(candidate if candidate.is_absolute() else project / candidate)
    need(path.is_relative_to(project) and path.suffix in suffixes and path.is_file(),
         'Packet must be a project file with an explicitly allowed suffix')
    raw = path.read_bytes()
    need(0 < len(raw) <= maximum, 'Prepared text is empty or too large')
    return path, raw.decode('utf-8')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, value):
    """Commit a JSON object without exposing a partially written state."""
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def process_start_ticks(pid):
    """Linux process identity, or None when it has already exited."""
    try:
        raw = Path('/proc', str(pid), 'stat').read_text()
        return int(raw[raw.rfind(')') + 2:].split()[19])
    except (FileNotFoundError, ProcessLookupError, ValueError, IndexError):
        return None
