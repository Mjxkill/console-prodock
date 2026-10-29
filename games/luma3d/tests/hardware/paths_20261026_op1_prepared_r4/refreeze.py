#!/usr/bin/env python3
"""Revise controller/tests only, preserving every runtime byte and oracle."""
import argparse,hashlib,json,shutil,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
def digest(p):
 b=p.read_bytes();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),crc32=f'{zlib.crc32(b):08x}')
def main():
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();base=a.base.resolve();out=a.out.resolve();m=json.loads((base/'manifest.json').read_text())
 for name,r in {**m['files'],**m['oracle_files']}.items():assert digest(base/name)==r,name
 shutil.copytree(base,out)
 updated=['prodock_paths.py','test_trial.py','TRIAL_PLAN.txt','refreeze.py']
 for name in updated:shutil.copy2(HERE/name,out/name);m['files'][name]=digest(out/name)
 m['controller_revision']=dict(previous_manifest=digest(base/'manifest.json'),changed_files=updated,runtime_bytes_unchanged=True)
 for name in m['transfer_files']:assert digest(out/name)==m['files'][name]
 (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(json.dumps(dict(manifest=digest(out/'manifest.json'),controller=digest(out/'prodock_paths.py'),transport_bytes=m['transport_bytes']),indent=2))
if __name__=='__main__':main()
