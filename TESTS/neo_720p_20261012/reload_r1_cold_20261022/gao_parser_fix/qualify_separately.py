#!/usr/bin/env python3
"""Run the unchanged complete qualifier, redirecting only its result write.

All real candidate reads and audits execute normally. The existing candidate
qualification is read-only, and both its contents and the qualifier are hashed.
No gate, path, report text, return code or audit result is substituted.
"""
import contextlib
import hashlib
import json
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BUILD = ROOT/'tang/impl/console_neo_n56r10_gao_startup'
SCRIPT = ROOT/'tools/check_neo_timing.py'
ORIGINAL = BUILD/'qualification.json'
OUTPUT = HERE/'qualification_after_parser.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not OUTPUT.exists()
    before = sha(ORIGINAL)
    script_hash = sha(SCRIPT)
    write_count = 0
    def result_write(path, data, *args, **kwargs):
        nonlocal write_count
        assert path.resolve() == ORIGINAL and write_count == 0, 'Unexpected qualifier write'
        assert not args and not kwargs, 'Unexpected output encoding/options'
        with OUTPUT.open('x') as output:
            written = output.write(data)
        write_count += 1
        return written
    sys.path.insert(0, str(ROOT/'tools'))
    sys.argv = [str(SCRIPT), str(BUILD)]
    with (HERE/'qualification_after_parser.log').open('x') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log), \
                patch.object(Path, 'write_text', result_write):
            try:
                runpy.run_path(str(SCRIPT), run_name='__main__')
                code = 0
            except SystemExit as exc:
                code = exc.code
                print('QUALIFIER_EXIT', repr(code))
    assert sha(ORIGINAL) == before and sha(SCRIPT) == script_hash
    assert write_count == 1
    result = json.loads(OUTPUT.read_text())
    record = dict(qualifier_sha256=script_hash, original_qualification_sha256=before,
        original_qualification_unchanged=True, output_sha256=sha(OUTPUT),
        exit_code=code, qualification_status=result['status'],
        only_redirected_write=str(ORIGINAL), destination=str(OUTPUT),
        wrapper_sha256=sha(Path(__file__)), hardware_access=False)
    with (HERE/'qualification_run.json').open('x') as out:
        json.dump(record, out, indent=2); out.write('\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
