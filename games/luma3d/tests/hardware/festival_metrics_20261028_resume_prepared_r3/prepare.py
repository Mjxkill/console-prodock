#!/usr/bin/env python3
"""Freeze this resume-only bundle. No device, process control or SSH."""
import json
from pathlib import Path
import stage
HERE=Path(__file__).resolve().parent
def main():
 m=json.loads((HERE/'plan.json').read_text());m['transport']['remaining_payload_bytes']=m['storage']['payload_bytes']-m['resume_checkpoint']['offset']
 names=[x.name for x in HERE.iterdir() if x.is_file() and x.name not in ('plan.json','review.example.json','tests.json','DELIVERY.json') and not x.name.endswith('.log')]
 m['files']={n:stage.digest((HERE/n).read_bytes()) for n in sorted(names)}
 (HERE/'plan.json').write_text(json.dumps(m,indent=2)+'\n');h=stage.digest((HERE/'plan.json').read_bytes())['sha256']
 r=json.loads((HERE/'review.example.json').read_text());r.update(plan_sha256=h,rx2_board_proof_sha256='ROOT_FILL_NEW_BUFFERED_PROBE_RESULT_SHA',failed_stage_sha256=m['failed_stage_sha256'],resume_existing_payload=True,reviewed_unix=0)
 for k in ['root_authorized_stage_only','same_gm1_since_rx2_probes','same_g22r0_since_rx2_probes','helper_unchanged_since_full_readback','ordinary_shell_confirmed','no_other_console_session']:r[k]=False
 (HERE/'review.example.json').write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps(dict(plan_sha256=h,hardware=False)))
if __name__=='__main__':main()
