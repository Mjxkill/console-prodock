#!/usr/bin/env python3
"""Freeze existing phase2 inputs locally; never access hardware."""
import json
from pathlib import Path
import festival_trial as legacy
HERE=Path(__file__).resolve().parent
def main():
 stage=json.loads((HERE/'stage_plan.json').read_text())
 m=dict(schema=1,prepared_only=True,hardware_tested=False,board='prodock',host=legacy.LOCAL_HOSTNAME,ssh_host='ax15',port=legacy.PORT,lock=legacy.LOCK,expected_identity=legacy.ANCHOR,kernel=legacy.RELEASE,fpga_sha256=legacy.FPGA_SHA,save_sha256=legacy.SAVE_SHA,baseline=stage['base'],game=stage['target'],helper_record=stage['helper'],helper='mc1-helper',program='luma3d-fm4a',tag='fm4measurec',windows=stage['windows'],normal_exit='restore_gm1_showcase',minimum_tmp_kib=1024,stage_plan_sha256=legacy.digest(HERE/'stage_plan.json')['sha256'],runtime_integrity='full-file CRC32, local exact SHA and QEMU reconstruction provenance; no measured hardware SHA claim')
 names=sorted(p.name for p in HERE.iterdir() if p.is_file() and (p.suffix=='.py' or p.name in ('README.md','prior_result.json','stage_plan.json','fpga_reference.json')))
 m['files']={name:legacy.digest(HERE/name) for name in names}
 (HERE/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 print(json.dumps(dict(manifest_sha256=legacy.digest(HERE/'manifest.json')['sha256'],hardware_access=False)))
if __name__=='__main__':main()
