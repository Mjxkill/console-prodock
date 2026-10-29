#!/usr/bin/env python3
"""Compare whole synthesized geometry modules after four explicit renames.

Read-only build access, no FPGA access. This is textual structural identity,
not a timing assertion or a proof about the changed USB modules.
"""
import difflib
import hashlib
import json
from pathlib import Path
import re

import resolve_n57_controls as r

RENAMES = {
    'bounds_product1_57_6': 'bounds_product1_57_108',
    'bounds_product1_57_s1': 'bounds_product1_57_s103',
    'bounds_product1_61_108': 'bounds_product1_61_6',
    'bounds_product1_61_s103': 'bounds_product1_61_s1',
}


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def main():
    output = r.OUT / 'geometry_rename_proof.json'
    diff_path = r.OUT / 'geometry_renames.diff'
    if output.exists() or diff_path.exists():
        raise ValueError('Existing evidence must not be overwritten')
    old_path = r.PARENT / 'console_neo.vg'
    new_path = r.CANDIDATE / 'impl/gwsynthesis/console_neo.vg'
    evidence = json.loads((r.OUT / 'resolution.json').read_text())
    for path in (old_path, new_path):
        if evidence['sha256'][str(path)] != r.sha(path):
            raise ValueError('Netlist changed after control resolution')
    old = r.modules_for(old_path)[1]['geometry']
    new = r.modules_for(new_path)[1]['geometry']
    token = re.compile(r'\b(' + '|'.join(map(re.escape, RENAMES)) + r')\b')
    counts = {name: len(re.findall(r'\b' + name + r'\b', old)) for name in RENAMES}
    if sorted(counts.values()) != [2, 2, 3, 3]:
        raise ValueError('Unexpected rename occurrence count')
    if any(re.search(r'\b' + re.escape(name) + r'\b', old) for name in RENAMES.values()):
        raise ValueError('Rename collides with an existing parent identifier')
    normalized = token.sub(lambda match: RENAMES[match[0]], old)
    passed = normalized == new
    diff_path.write_text(''.join(difflib.unified_diff(
        old.splitlines(True), new.splitlines(True),
        fromfile=str(old_path) + ':gpu_geometry',
        tofile=str(new_path) + ':gpu_geometry')))
    constraint_paths = [r.CANDIDATE / 'source/tang/boards/neo/neo.cst',
                        r.CANDIDATE / 'source/tang/boards/neo/neo.sdc',
                        r.OUT / 'proposed_controls.cst']
    constraint_refs = {
        str(path): [name for name in list(RENAMES) + list(RENAMES.values())
                    if name in path.read_text()]
        for path in constraint_paths
    }
    passed = passed and not any(constraint_refs.values())
    result = dict(
        passed=passed,
        scope=__doc__,
        renames=RENAMES, parent_occurrences=counts,
        old_module_sha256=digest(old), new_module_sha256=digest(new),
        normalized_old_sha256=digest(normalized),
        whole_module_equal_after_only_these_renames=normalized == new,
        references_in_constraints=constraint_refs,
        sha256={str(path): r.sha(path) for path in
                [Path(__file__), Path(r.__file__), old_path, new_path,
                 r.OUT / 'resolution.json', diff_path] + constraint_paths},
        hardware_access=False, route_launched=False)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(dict(passed=passed, output=str(output)), indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
