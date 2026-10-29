#!/usr/bin/env python3
"""Offline preparation only. Copies exact evidence and runs transcript tests."""
import hashlib,json,shutil,subprocess
from pathlib import Path
import recover as r
P=Path(__file__).resolve().parent
ROOT=next(p for p in P.parents if (p/'ARCHI/COMPATIBILITE_CARTES.md').is_file())
def main():
 r6=ROOT/'games/luma3d/tests/hardware/festival_20261028_r9_prepared_r6';incident=ROOT/'games/luma3d/tests/hardware/festival_20261028_r9_board_r6';proof=ROOT/'games/luma3d/candidates/receiver_nul_recovery_20261028_r1'
 assert r.sha(r6/'manifest.json')==r.R6_SHA
 copies={'r6_manifest.json':r6/'manifest.json','r6_result.json':incident/'result.json','r6_transport.json':incident/(r.NAME+'.transport.json'),'fpga_reference.json':ROOT/'tang/boards/prodock/reference.json','nul_qemu_result.json':proof/'run_r2/result.json','nul_proof_limits.md':proof/'README.md'}
 for name,src in copies.items():shutil.copy2(src,P/name)
 q=subprocess.run(['python3','-B',str(P/'test_recovery.py')],capture_output=True);(P/'tests.log').write_bytes(q.stdout+q.stderr);q.check_returncode()
 result={'passed':True,'hardware':False,'scope':'14 offline transcript/state tests plus exact prior RV32/Linux/ash PTY proof; no device open','test_sha256':r.sha(P/'test_recovery.py'),'controller_sha256':r.sha(P/'recover.py')};(P/'tests.json').write_text(json.dumps(result,indent=2)+'\n')
 files=['recover.py','prepare.py','test_recovery.py','README.md','tests.log','tests.json',*copies]
 m={'schema':1,'prepare_only':True,'hardware_tested':False,'host':r.HOST,'ssh_alias':r.SSH_ALIAS,'port':r.PORT,'lock':r.LOCK,'claim':r.CLAIM,'r6_manifest_sha256':r.R6_SHA,'r6_review_sha256':r.R6_REVIEW_SHA,'expected_identity':r.ANCHOR,'fpga_sha256':r.FPGA_SHA,'baseline_sha256':r.BASE_SHA,'save_sha256':r.SAVE_SHA,'recovery_hex':r.RECOVERY.hex(),'receiver_marker':r.MARKER.decode(),'failed_delta_reusable':False,'files':{n:{'bytes':(P/n).stat().st_size,'sha256':r.sha(P/n)} for n in files}}
 (P/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');digest=r.sha(P/'manifest.json')
 review={k:m[k] for k in ('host','ssh_alias','port','r6_manifest_sha256','r6_review_sha256','expected_identity','fpga_sha256','baseline_sha256','save_sha256')};review.update(manifest_sha256=digest,reviewed_unix=0)
 for key in ('root_authorized_one_shot','r6_state_unchanged_since_incident','no_other_console_session','receiver_or_ordinary_shell_only','not_in_quote_heredoc_or_other_program','no_reconfiguration_since_g22r0'):review[key]=False
 (P/'review.example.json').write_text(json.dumps(review,indent=2)+'\n');r.preflight(P,digest);print(json.dumps({'prepared':True,'hardware':False,'manifest_sha256':digest,'controller_sha256':r.sha(P/'recover.py')}))
if __name__=='__main__':main()
