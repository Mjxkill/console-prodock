"""Hermetic process helpers for the pinned OSS CAD Suite (stdlib only)."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import signal

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
SUITE = ROOT / '.tools/oss-cad-suite'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def save(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


def tool_command(tool, args):
    # Upstream GUI wrappers unconditionally write to $HOME. Invoke the same
    # bundled ELF loader directly, keeping configuration within this project.
    binary = SUITE / 'libexec' / tool
    if tool in ('gowin_pack', 'gowin_pack_legacy'):
        binary = SUITE / 'libexec/python3.11'
        args = (['-m', 'apycula.gowin_pack'] if tool == 'gowin_pack_legacy' else [str(SUITE / 'libexec/gowin_pack')]) + list(args)
    if not binary.is_file():
        raise FileNotFoundError(f'{binary}: run python3 optimizer/bootstrap.py')
    return [str(SUITE / 'lib/ld-linux-x86-64.so.2'), '--inhibit-cache',
            '--inhibit-rpath', '', '--library-path', str(SUITE / 'lib'), str(binary), *map(str, args)]


def tool_env(tool=None):
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    if tool == 'gowin_pack_legacy':
        package = ROOT/'.tools/apicula-0.32'
        if not package.is_dir():
            raise FileNotFoundError('Run bootstrap.py --component legacy-pack first')
        env['PYTHONPATH'] = str(package)
    env.update(PYTHONHOME=str(SUITE), PYTHONNOUSERSITE='1',
               PATH=str(SUITE / 'bin') + os.pathsep + env.get('PATH', ''),
               QT_QPA_PLATFORM='offscreen', LC_ALL='C')
    # Never override HOME or modify the installed upstream wrappers.
    for key in ('CONFIG', 'CACHE', 'DATA'):
        path = ROOT / '.tools' / ('xdg-' + key.lower())
        path.mkdir(exist_ok=True)
        env['XDG_' + key + '_HOME'] = str(path)
    return env


def run_tool(tool, args, cwd, log, timeout=1800):
    cmd = tool_command(tool, args)
    start = time.monotonic()
    record = dict(tool=tool, argv=cmd, log=str(log), timeout_s=timeout)
    with Path(log).open('w') as output:
        try:
            process = subprocess.Popen(cmd, cwd=cwd, env=tool_env(tool), stdout=output,
                                       stderr=subprocess.STDOUT, start_new_session=True)
            record['returncode'] = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Only our own process group (e.g. Yosys + its ABC child).
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            record.update(returncode=None, error='timeout')
    record['elapsed_s'] = round(time.monotonic() - start, 3)
    save(Path(log).with_suffix('.command.json'), record)
    return record
