#!/usr/bin/env python3
"""Link the actual shared SPI .c with an independent register/FIFO model.

No .c is included, no function body lives in a header, and no hardware is
accessed. Tick-based timeouts are behavioral tests, not physical SPI timing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def structure(paths):
    for path in paths:
        text = path.read_text()
        if len(text.splitlines()) > 1000:
            raise ValueError('Source exceeds 1000 lines: ' + str(path))
        text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
        if re.search(r'^\s*#\s*include\s*["<][^">]*\.c[">]', text, re.M):
            raise ValueError('Forbidden .c include: ' + str(path))
        if path.suffix == '.h' and re.search(r'\)\s*\{', text):
            raise ValueError('Function body in header: ' + str(path))


def check(core, header):
    sources = [core, header, HERE/'spi_register_model.c',
               HERE/'spi_register_model.h', HERE/'spi_pio_model.c']
    report = dict(passed=False, hardware=False, physical_timing_measured=False,
                  inputs={str(p): digest(p) for p in sources + [Path(__file__)]},
                  commands=[])
    try:
        structure(sources)
        report['structure_passed'] = True
        with tempfile.TemporaryDirectory(prefix='console-spi-pio-') as td:
            temp = Path(td)
            # Byte-identical build copies make quoted header lookup explicit.
            mapping = {'prodock-spi-pio.c': core, 'prodock-spi-pio.h': header,
                       **{p.name: p for p in sources[2:]}}
            for name, path in mapping.items():
                shutil.copyfile(path, temp/name)
            flags = ['-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                     '-fsanitize=undefined', '-fno-sanitize-recover=all',
                     '-DPRODOCK_SPI_TEST', '-I'+str(temp)]
            commands = []
            objects = []
            for name in ('prodock-spi-pio', 'spi_register_model', 'spi_pio_model'):
                obj = temp/(name+'.o')
                objects.append(str(obj))
                commands.append(['gcc', *flags, '-c', str(temp/(name+'.c')), '-o', str(obj)])
            binary = temp/'test'
            commands.append(['gcc', '-fsanitize=undefined', *objects, '-o', str(binary)])
            commands.append([str(binary)])
            for command in commands:
                start = time.monotonic()
                result = subprocess.run(command, capture_output=True, text=True, timeout=30)
                report['commands'].append(dict(argv=command, returncode=result.returncode,
                    stdout=result.stdout, stderr=result.stderr,
                    elapsed_seconds=time.monotonic()-start))
                if result.returncode:
                    return report
            report['passed'] = report['commands'][-1]['stdout'].startswith('PASS:')
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        report['error'] = str(error)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--core', type=Path, default=ROOT/'linux/drivers/prodock-spi-pio.c')
    ap.add_argument('--header', type=Path, default=ROOT/'linux/drivers/prodock-spi-pio.h')
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    report = check(args.core.resolve(), args.header.resolve())
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2)+'\n')
    for command in report['commands']:
        print(command['stdout'], end='')
        print(command['stderr'], end='')
    print(json.dumps({k:v for k,v in report.items() if k != 'commands'}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
