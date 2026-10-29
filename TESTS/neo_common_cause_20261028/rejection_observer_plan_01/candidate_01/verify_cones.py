#!/usr/bin/env python3
"""Independent exact-LUT proof, with RESET deliberately separate from CE.

The model run's green evaluator added a nonexistent reset qualifier. This
reviewer implementation does not reuse it. Raw CE is not an effective write.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def evaluate(graph, output, leaves):
    drivers = {c['ports']['F']: c for c in graph['cells'].values()}
    active, memo = set(), {}

    def visit(net):
        if net in memo:
            return memo[net]
        if net in leaves:
            assert leaves[net] in (0, 1)
            return leaves[net]
        assert net not in active, 'cycle'
        c = drivers[net]
        assert c['kind'] in ('LUT1', 'LUT2', 'LUT3', 'LUT4')
        active.add(net)
        n = int(c['kind'][3:])
        index = sum(visit(c['ports']['I' + str(i)]) << i for i in range(n))
        width, value = c['parameters']['INIT'].split("'h")
        assert int(width) == 2 ** n
        answer = (int(value, 16) >> index) & 1
        active.remove(net)
        memo[net] = answer
        return answer

    return visit(output)


def main():
    path = HERE / 'stateproof_task/graph.json'
    graph = json.loads(path.read_text())
    count = 0
    for state in range(32):
        for old_bad in (0, 1):
            for start in (0, 1):
                for release in (0, 1):
                    for bad in range(8):
                        x = {f'state_0[{i}]': (state >> i) & 1 for i in range(5)}
                        x.update({f'descriptor_bad[{i}]': (bad >> i) & 1 for i in range(3)})
                        x.update({'copy_bad': old_bad, 'state[41]': start,
                                  'gpu_debug_state[50]': release})
                        expect = 1 if state >= 19 or (state == 17 and bad) else (
                            0 if state == 0 and start else old_bad)
                        assert evaluate(graph, 'n4731_54', x) == expect
                        assert evaluate(graph, 'n5984_12', x) == int(state == 1)
                        assert evaluate(graph, 'n7630_6', x) == int(state == 0 and start and release)
                        count += 1
    result = {'passed': True, 'combinations': count, 'cones': 3,
              'proof': 'combinational INIT evaluation; no clocked or physical claim',
              'CHECK_CE': 'state_0 == 1; RESET is separate FF pin, not part of CE',
              'copy_capture_CE': 'state_0 == 0 && state[41] && gpu_debug_state[50]',
              'descriptor_reject_state': 17, 'default_bad_states': list(range(19, 32)),
              'model_disposition': 'REJECTED: extra reset qualification invented to satisfy wrong test',
              'preparation_error': 'v1 protected test incorrectly required reset in raw CHECK CE',
              'inputs': {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (path, Path(__file__))}}
    (HERE / 'state_cone_review.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
