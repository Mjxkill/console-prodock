#!/usr/bin/env python3
"""Offline copies only. Never opens a UART."""
import hashlib,json,shutil,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=next(p for p in P.parents if (p/'ARCHI/COMPATIBILITE_CARTES.md').is_file());RX=ROOT/'games/luma3d/candidates/uart_rx2_buffered_20261028_r1';HEALTH=P.parent/'festival_20261028_r6_health_resume_r3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 copies={'sender.py':RX/'sender.py','bootstrap.py':RX/'bootstrap.py','receiver':RX/'build_r1/receiver','receiver_build.json':RX/'build_r1/manifest.json','qemu_result.json':RX/'tests_r1/result.json','rx2_limits.md':RX/'README.md','health.json':HEALTH/'result.json','health_identity.log':HEALTH/'identity_after.log','health_save.log':HEALTH/'save_after.log','health_space.log':HEALTH/'space.log','fpga_reference.json':ROOT/'tang/boards/prodock/reference.json'}
 for n,p in copies.items():shutil.copy2(p,P/n)
 import bootstrap,trial as t
 (P/'bootstrap.json').write_text(json.dumps(bootstrap.plan(P/'receiver',t.EXECUTABLE),indent=2)+'\n')
 files=['trial.py','support.py','prepare.py','test_trial.py','README.md','bootstrap.json',*copies]
 m=dict(schema=1,prepare_only=True,hardware_tested=False,host=t.HOST,ssh_alias='ax15',port=t.PORT,lock=t.LOCK,anchor=t.ANCHOR,fpga_sha256=t.FPGA,save_sha256=t.SAVE,baseline_sha256=t.BASE,receiver_sha256=sha(P/'receiver'),health_sha256=sha(P/'health.json'),files={n:{'bytes':(P/n).stat().st_size,'sha256':sha(P/n)} for n in files})
 (P/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');h=sha(P/'manifest.json');r={k:m[k] for k in ['host','ssh_alias','port','anchor','fpga_sha256','save_sha256']};r.update(manifest_sha256=h,reviewed_unix=0)
 for k in ['root_authorized_probes','same_g22r0_since_health','same_gm1_since_health','ordinary_shell_confirmed','no_other_console_session']:r[k]=False
 (P/'review.example.json').write_text(json.dumps(r,indent=2)+'\n');t.preflight(P,h)
 q=subprocess.run(['python3','-B',str(P/'test_trial.py')],capture_output=True);(P/'tests.log').write_bytes(q.stdout+q.stderr);q.check_returncode();(P/'tests.json').write_text(json.dumps(dict(passed=True,hardware=False,manifest_sha256=h,controller_sha256=sha(P/'trial.py'),test_sha256=sha(P/'test_trial.py')),indent=2)+'\n');print(json.dumps(dict(prepared=True,hardware=False,manifest_sha256=h,controller_sha256=sha(P/'trial.py'))))
if __name__=='__main__':main()
