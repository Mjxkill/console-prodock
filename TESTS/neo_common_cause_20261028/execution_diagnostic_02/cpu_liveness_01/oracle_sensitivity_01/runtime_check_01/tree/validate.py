#!/usr/bin/env python3
"""Protected checks of records; supervisor separately inspects implementation."""
import hashlib
import json
from pathlib import Path
from mutation_runner import run_suite

HERE=Path(__file__).resolve().parent
EXPECTED={'baseline':None,'return_low':'CPU_DATA index0',
          'return_upper':'CPU_DATA index4','return_missing':'CPU progress timeout',
          'write_mask':'ENDPOINT unexpected CLEAR footprint',
          'write_address':'ENDPOINT address outside scratch128B'}

def main():
    refs=json.loads((HERE/'REFERENCE_HASHES.json').read_text())
    check=lambda:all(hashlib.sha256((HERE/k).read_bytes()).hexdigest()==v for k,v in refs.items())
    assert check(),'Protected input changed before tests'
    rows=run_suite()
    assert check(),'Protected input changed during tests'
    assert type(rows) is list and len(rows)==len(EXPECTED),'Need6real trials'
    assert {x['name'] for x in rows}==set(EXPECTED),'Wrong/missing trial set'
    for row in rows:
        assert row['compile_returncode']==0,'Compile failure not sensitivity'
        assert row['timeout'] is False,'External timeout not sensitivity'
        assert row['executed_binary'] is True,'Need actual compiled executable'
        expected=EXPECTED[row['name']]
        if expected is None:
            assert row['returncode']==0,'Baseline must succeed'
            final=[json.loads(x[4:]) for x in row['log'].splitlines() if x.startswith('OBS ') and '"final"' in x]
            assert len(final)==1 and final[0]['cpu']==32 and final[0]['gpu_done']==2
        else:
            assert row['returncode']!=0 and expected in row['log'],f'No specific detection:{row["name"]}'
    print(json.dumps({'passed':True,'trials':rows},indent=2))

if __name__=='__main__':main()
