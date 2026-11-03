#!/usr/bin/env python3
"""Rebuild a frozen FPGA selection into a new directory, never load a board.

Pro Dock R6: application synthesis with the exact pre-generated vendor IP.
Neo REJECT R1: reroute the exact diagnostic netlist, not an RTL reconstruction.
The development builders and their protected-reference guards are unchanged.
This entry point checks its own complete, immutable release-input manifest.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {'prodock': 'prodock_r6', 'neo': 'neo_reject_r1'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative_name(name):
    """Reject traversal, aliases and platform-specific separators in packages."""
    path = PurePosixPath(name)
    require(name and path.parts and not path.is_absolute() and path.as_posix() == name
            and all(part not in ('.', '..') for part in path.parts)
            and '\\' not in name, 'Unsafe package path: '+repr(name))
    return path


def load_package(board, packages=None):
    packages = ROOT/'releases/fpga' if packages is None else Path(packages)
    require(board in PACKAGES, 'Unsupported board: '+board)
    package = packages/PACKAGES[board]
    record = json.loads((package/'manifest.json').read_text())
    require(record['schema'] == 1 and record['board'] == board
            and record['release'] == PACKAGES[board], 'Wrong release identity')
    archive = package/relative_name(record['archive']['path'])
    require(archive.is_file() and not archive.is_symlink()
            and sha(archive) == record['archive']['sha256'], 'Changed input archive')
    for name, expected in record['scripts'].items():
        path = package/relative_name(name)
        require(path.is_file() and not path.is_symlink() and sha(path) == expected,
                'Changed release script: '+name)
        require('/home/' not in path.read_text(), 'Non-relocatable release script: '+name)
    for name in record['files']:
        relative_name(name)
    for name in record['outputs'].values():
        relative_name(name)
    return package, record, archive


def extract_inputs(archive, output, files):
    """Extract only listed regular files, verifying lengths and content hashes.

    No extractall: a malformed tar member must never follow a link or escape the
    fresh staging directory. A failed preparation is retained, never overwritten.
    """
    with tarfile.open(archive, 'r:gz') as bundle:
        members = bundle.getmembers()
        names = [member.name for member in members]
        require(len(names) == len(set(names)) and set(names) == set(files),
                'Archive member inventory differs from manifest')
        for member in members:
            relative_name(member.name)
            require(member.isfile() and not member.issym() and not member.islnk(),
                    'Non-regular archive member: '+member.name)
            require(member.size == files[member.name]['bytes'],
                    'Wrong archive member length: '+member.name)
        for member in members:
            path = output/member.name
            path.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256()
            with bundle.extractfile(member) as source, path.open('xb') as destination:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(block)
                    destination.write(block)
            require(digest.hexdigest() == files[member.name]['sha256'],
                    'Wrong archive member hash: '+member.name)


def validate_scripts(output, record):
    """Check every relative TCL input before allowing a vendor tool launch."""
    generated = record['outputs']['netlist'] if record['board'] == 'prodock' else None
    for name in record['scripts']:
        text = (output/name).read_text()
        for value in re.findall(r'^add_file \{([^\n}]+)\}$', text, re.M):
            relative_name(value)
            require(value in record['files'] or (name == 'route.tcl' and value == generated),
                    'Unlisted TCL input: '+value)
        require(re.search(r'^run (syn|pnr)$', text, re.M), 'Missing build phase: '+name)


def prepare(board, output, *, packages=None):
    """Validate and prepare without requiring a Gowin installation or a board."""
    package, record, archive = load_package(board, packages)
    require(not Path(output).is_symlink(), 'Output must not be a symbolic link')
    output = Path(output).resolve()
    require(not output.exists(), 'Output already exists; choose a new --out directory')
    output.mkdir(parents=True)
    try:
        extract_inputs(archive, output, record['files'])
        for name in record['scripts']:
            target = output/relative_name(name)
            require(not target.exists(), 'Script shadows an archived input: '+name)
            target.write_bytes((package/name).read_bytes())
        validate_scripts(output, record)
        evidence = {'prepared': True, 'board': board, 'release': record['release'],
                    'build_kind': record['build_kind'], 'manifest_sha256': sha(package/'manifest.json'),
                    'archive_sha256': sha(archive), 'file_count': len(record['files']),
                    'historical_bitstream_sha256': record['bitstream']['sha256'],
                    'candidate': True, 'Gowin_executed': False, 'hardware_access': False,
                    'timing_qualified': False, 'relocation': record['relocation']}
        (output/'PREPARATION.json').write_text(json.dumps(evidence, indent=2)+'\n')
    except Exception as error:
        (output/'PREPARATION_FAILED.json').write_text(json.dumps({'error': str(error)})+'\n')
        raise
    return output, record


def run_phase(output, script, ide, env):
    """One synchronous vendor invocation with an explicit recorded failure."""
    log = output/(script+'.log')
    start = time.monotonic()
    with log.open('w') as stream:
        result = subprocess.run([str(ide/'bin/gw_sh'), script], cwd=output,
                                env=env, stdout=stream, stderr=subprocess.STDOUT)
    errors = bool(re.search(r'^\s*(ERROR\b|unknown option:)', log.read_text(errors='replace'), re.M))
    phase = {'script': script, 'returncode': result.returncode, 'tool_errors': errors,
             'seconds': time.monotonic()-start, 'log_sha256': sha(log)}
    (output/(script+'.result.json')).write_text(json.dumps(phase, indent=2)+'\n')
    require(result.returncode == 0 and not errors, 'Gowin failed; see '+str(log))
    return phase


def build(output, record, stage):
    """Consume only prepared bytes; use the shared resolver after R6 synthesis."""
    require(stage in ('syn', 'all'), 'Unsupported build stage')
    require(record['board'] != 'neo' or stage == 'all',
            'Neo REJECT R1 is netlist-only: --stage syn is not available')
    for name, expected in record['files'].items():
        require(sha(output/name) == expected['sha256'], 'Prepared input changed: '+name)
    for name, expected in record['scripts'].items():
        require(sha(output/name) == expected, 'Prepared script changed: '+name)
    # Lazy import keeps --prepare-only usable on machines without Gowin installed.
    from gowin_toolchain import IDE, environment
    env = environment()
    result = {'candidate': True, 'board': record['board'], 'release': record['release'],
              'stage': stage, 'ide': str(IDE), 'gw_sh_sha256': sha(IDE/'bin/gw_sh'),
              'phases': [], 'hardware_access': False, 'timing_qualified': False}
    try:
        if record['board'] == 'prodock':
            require(sha(ROOT/'tools/build_gpu.py') == record['relocation']['resolver_source_sha256'],
                    'Shared constraint resolver changed; release requires an explicit reviewed update')
            from build_gpu import resolve_constraints
            result['phases'].append(run_phase(output, 'synth.tcl', IDE, env))
            netlist = output/record['outputs']['netlist']
            require(netlist.is_file(), 'Synthesis returned without the expected netlist')
            resolve_constraints(netlist, output/'source/tang/constr/gpu.cst',
                                output/'constraints_resolved.cst')
            result['resolved_constraints_sha256'] = sha(output/'constraints_resolved.cst')
        if stage == 'all':
            result['phases'].append(run_phase(output, 'route.tcl', IDE, env))
            bitstream = output/record['outputs']['bitstream']
            require(bitstream.is_file() and bitstream.stat().st_size > 0,
                    'Routing returned without the expected bitstream')
            result['bitstream_sha256'] = sha(bitstream)
            result['matches_historical_bitstream'] = result['bitstream_sha256'] == record['bitstream']['sha256']
        result['completed'] = True
    except (Exception, SystemExit) as error:
        result.update(completed=False, error=str(error))
        raise
    finally:
        (output/'RESULT.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', required=True, choices=PACKAGES)
    parser.add_argument('--out', required=True, type=Path, help='Fresh output directory')
    parser.add_argument('--prepare-only', action='store_true', help='Verify/extract only; never invoke Gowin')
    parser.add_argument('--stage', choices=('syn', 'all'), default='all')
    args = parser.parse_args()
    if args.board == 'neo' and args.stage == 'syn':
        parser.error('Neo selection is a netlist reroute; --stage syn is unavailable')
    output, record = prepare(args.board, args.out)
    if not args.prepare_only:
        build(output, record, args.stage)
    print(json.dumps({'prepared': str(output), 'release': record['release'],
                      'build_kind': record['build_kind'], 'Gowin_executed': not args.prepare_only,
                      'timing_qualified': False, 'hardware_access': False}, indent=2))


if __name__ == '__main__':
    main()
