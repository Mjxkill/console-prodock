"""Trusted post-run evidence checks, separate from model text and tests.

The audit file is written by the host MCP relay and is not mounted in the box.
Test counters use the reviewed MiniMax implementation of the pure contract.
"""
import json
from pathlib import Path
from agent_audit import summarize


def process_ticks(pid):
    try:
        return int((Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None


def audit(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16 << 20:
        raise ValueError('missing or unsafe bounded MCP audit')
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    counts = summarize(rows)
    starts, exits, processes = {}, {}, []
    writes, test_failures, test_passes = [], [], []
    for index, row in enumerate(rows):
        event, launch = row['event'], row.get('launch_id')
        if event in ('sandbox_start', 'launcher_start', 'sandbox_exit', 'launcher_exit'):
            kind = event.rsplit('_', 1)[0]
            identity = (launch, kind)
            if type(row.get('pid')) is not int or type(row.get('start_ticks')) is not int:
                raise ValueError('process identity missing')
            (starts if event.endswith('_start') else exits)[identity] = row
        if event == 'tool_finish' and row.get('name') == 'write_file' and row.get('error') is False:
            writes.append(index)
        if event == 'test_finish':
            bad = row['returncode'] != 0 or row['timeout'] or row['output_limited']
            (test_failures if bad else test_passes).append(index)
    for identity, row in starts.items():
        end = exits.get(identity)
        same = process_ticks(row['pid']) == row['start_ticks']
        matched = end is not None and (end['pid'], end['start_ticks']) == (row['pid'], row['start_ticks'])
        processes.append(dict(kind=identity[1], launch_id=identity[0], pid=row['pid'],
                              start_ticks=row['start_ticks'], same_process_alive=same,
                              exit_record_matched=matched))
    all_exited = bool(starts) and starts.keys() == exits.keys() and all(
        not p['same_process_alive'] and p['exit_record_matched'] for p in processes)
    return dict(agent_test_runs=counts['test_runs'], agent_test_failures=counts['test_failures'],
                test_audit_complete=counts['complete'], test_calls=counts['test_calls'],
                processes=processes, all_recorded_processes_exited=all_exited,
                successful_write_calls=len(writes),
                failed_test_before_write=bool(writes and any(i < writes[0] for i in test_failures)),
                passed_test_after_write=bool(writes and any(i > writes[-1] for i in test_passes)),
                sequence_scope='explicit MCP write_file calls; arbitrary exec edits require separate review')
