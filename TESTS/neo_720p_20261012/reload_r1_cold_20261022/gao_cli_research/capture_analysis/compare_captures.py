#!/usr/bin/env python3
"""Read the three archived GAO CSVs; never edit raw captures or access hardware."""
import csv
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
CONFIG = REPO/'tang/impl/console_neo_n56r10_gao_startup/source/tang/boards/neo/startup.gao'
CLOCKS = {'vid_hclk', 'gpu_clk'}


def main():
    expected = [n.text for n in ET.parse(CONFIG).findall('./AoCore/SignalList/Signal')]
    records = []; arrays = []; originals = {}
    for number in (1,2,3):
        path = HERE.parent/f'r10_initial_read_{number:02d}/initial_core0_window0.csv'
        raw = path.read_bytes(); originals[path] = raw
        parsed = list(csv.reader(raw.decode().splitlines()))
        header = [s.strip() for s in parsed[1] if s.strip()]
        rows = [[int(s.strip()) for s in row if s.strip()] for row in parsed[2:] if row and row[0].strip()]
        assert header[1:] == expected and len(rows) == 4096
        assert [r[0] for r in rows] == list(range(4096))
        assert all(len(r)==21 and all(v in (0,1) for v in r[1:]) for r in rows)
        signals = {}
        for column,name in enumerate(expected,1):
            values = [r[column] for r in rows]
            transitions = [i for i in range(1,4096) if values[i]!=values[i-1]]
            signals[name] = dict(first=values[0],last=values[-1],ones=sum(values),sample_changes=len(transitions))
            if name not in CLOCKS:
                signals[name]['transitions'] = [dict(index=i,time_ns_from_first_sample=i*20,
                    previous=values[i-1],value=values[i]) for i in transitions]
        records.append(dict(read=number,file=str(path.relative_to(REPO)),sha256=hashlib.sha256(raw).hexdigest(),
                            samples=4096,columns=20,signals=signals))
        arrays.append(rows)
    comparisons = []
    for a,b in ((0,1),(1,2),(0,2)):
        columns = {}
        for column,name in enumerate(expected,1):
            indices = [i for i in range(4096) if arrays[a][i][column]!=arrays[b][i][column]]
            columns[name] = dict(different_samples=len(indices))
            if name not in CLOCKS: columns[name]['indices'] = indices
        comparisons.append(dict(reads=[a+1,b+1],different_rows=sum(x!=y for x,y in zip(arrays[a],arrays[b])),
                                different_bits=sum(c['different_samples'] for c in columns.values()),columns=columns))
    report = dict(scope='Offline observations, not functional or timing qualification',hardware_access=False,
                  sample_period_ns=20,time_unit_correction='CLI labels 1us but design sampling clock is 50MHz; timestamps are relative, not time since configuration.',
                  clocks_frequency_measured=False,configuration_sha256=hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
                  reads=records,comparisons=comparisons,
                  conclusions=['The three exports are not byte-identical.',
                    'Read1 to read2 cannot be explained by a circular rotation alone: DDR/POR one-counts change.',
                    'Reads2 and3 both report DDR/init_sync/POR high and EXTS_HRSTN/vid_hrstn low at every sample.',
                    'Skipping software startTrigger does not prove the full read transaction has no acquisition side effect.',
                    'Capture update, initial-buffer consumption, JTAG session reset and readout integrity are not distinguished by these CSVs.',
                    'GAO hold timing FAIL remains a material limit.'])
    assert all(p.read_bytes()==raw for p,raw in originals.items())
    (HERE/'comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps([dict(reads=c['reads'],different_rows=c['different_rows'],different_bits=c['different_bits']) for c in comparisons]))


if __name__=='__main__':main()
