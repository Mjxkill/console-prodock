#!/usr/bin/env python3
"""New review revision of unchanged runtime/transfers; no board, no overwrite."""
import argparse,hashlib,json,shutil,zlib
from pathlib import Path
C=Path(__file__).resolve().parent
def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def main():
 p=argparse.ArgumentParser();p.add_argument('--prior',type=Path,required=True);p.add_argument('--expected-prior',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 assert digest(a.prior/'manifest.json')['sha256']==a.expected_prior
 m=json.loads((a.prior/'manifest.json').read_text())
 for name,r in m['files'].items():assert digest(a.prior/name)==r,name
 a.out.mkdir(parents=True,exist_ok=False)
 for name in m['files']:shutil.copy2(a.prior/name,a.out/name)
 for name in ['prodock_polish.py','prepare_trial.py','revise_trial.py','test_trial.py','PLAN_MATERIEL.txt']:shutil.copy2(C/name,a.out/name)
 for name in m['transfer_files']:assert digest(a.out/name)==m['files'][name]
 m['previous_preparation_manifest_sha256']=a.expected_prior
 m['files']={p.name:digest(p) for p in sorted(a.out.iterdir()) if p.is_file()}
 (a.out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(dict(manifest=digest(a.out/'manifest.json'),transport_bytes=m['transport_bytes']),indent=2))
if __name__=='__main__':main()
