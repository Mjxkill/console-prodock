#!/usr/bin/env python3
"""Verify the exact root-installed pack, optionally clean only its named staging.

No installation, model, hardware or configuration mutation. Deletion is limited
to the explicit root-created /tmp archive/staging after byte-for-byte checks.
"""
import argparse
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
import subprocess,sys,tarfile

MANIFEST_SHA='fc664faf94a39ea2e2b55a0ae2ddf0af9bab1f0b715ae2c2355e88146fc294b7'
AGENTS_SHA='6684c4f408f2401ecdec42317d7a80012d12c8e42eb028168d4e271c0582d1ae'
ARCHIVE_SHA='c858423405957cc4afcc1e44c887853e1be02f680d629692695379ead77fba6f'
STAGE=Path('/tmp/codex-model-workflow-fc664faf20261028')
ARCHIVE=STAGE.with_suffix('.tar')
NAMES={'runner.py','workflow_common.py','event_parser.py','process_io.py','dispatch_queue.py','metrics.py','check_code_size.py','install_workflow.py','GLOBAL_AGENTS.md','WORKFLOW.md','TEST_RECORD_TEMPLATE.md','QUICKSTART.md'}

def need(value,message):
    if not value:raise ValueError(message)

def safe(path):
    for p in [path,*path.parents]:need(not p.is_symlink(),'Symlink: '+str(p))
    return path

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--home',type=Path,required=True)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--cleanup-stage',action='store_true')
    ap.add_argument('--cleanup-archive',action='store_true')
    args=ap.parse_args()
    home=safe(args.home.absolute());target=safe(home/'model-workflow')
    raw=safe(target/'install_manifest.json').read_bytes()
    need(sha(raw)==MANIFEST_SHA,'Installed manifest differs')
    doc=json.loads(raw);need(set(doc['files'])==NAMES,'Wrong installed allowlist')
    hashes={}
    for name,entry in doc['files'].items():
        data=safe(target/name).read_bytes();hashes[name]=sha(data)
        need(hashes[name]==entry['sha256'] and len(data)==entry['size'],'Installed bytes differ: '+name)
    need(sha(safe(home/'AGENTS.md').read_bytes())==AGENTS_SHA,'Global instructions differ')
    need(not (home/'AGENTS.override.md').exists() and not (home/'AGENTS.override.md').is_symlink(),'Unexpected override')
    source=safe(args.source.absolute())
    check=subprocess.run([sys.executable,'-B',str(target/'install_workflow.py'),'--source',str(source),'--home',str(home),'--prepare-only'],capture_output=True,text=True,timeout=20)
    need(check.returncode==0,'Read-only installer check failed: '+check.stderr)
    plan=json.loads(check.stdout);need(not plan['changed'] and plan['manifest_sha256']==MANIFEST_SHA,'Install is not idempotent')
    expected=set(NAMES)|{'install_manifest.json'}
    # Validate ALL proposed deletions before deleting the first byte.
    if args.cleanup_stage:
        safe(STAGE);need(STAGE.is_dir(),'Staging absent or not directory')
        need({p.name for p in STAGE.iterdir()}==expected,'Staging contains unrelated files')
        for name in expected:
            data=safe(STAGE/name).read_bytes()
            need(sha(data)==(MANIFEST_SHA if name=='install_manifest.json' else hashes[name]),'Staging differs: '+name)
    if args.cleanup_archive:
        safe(ARCHIVE);need(sha(ARCHIVE.read_bytes())==ARCHIVE_SHA,'Archive SHA differs')
        with tarfile.open(ARCHIVE,'r') as tar:
            members=tar.getmembers()
            need(len(members)==len(expected) and {m.name for m in members}==expected,'Archive names differ')
            for member in members:
                need(member.isfile() and not member.issym(),'Archive not regular')
                data=tar.extractfile(member).read()
                need(sha(data)==(MANIFEST_SHA if member.name=='install_manifest.json' else hashes[member.name]),'Archive content differs')
    deleted=[]
    if args.cleanup_stage:
        for name in sorted(expected):(STAGE/name).unlink();deleted.append(str(STAGE/name))
        STAGE.rmdir();deleted.append(str(STAGE))
    if args.cleanup_archive:
        ARCHIVE.unlink();deleted.append(str(ARCHIVE))
    print(json.dumps(dict(passed=True,recorded_at=datetime.now(timezone.utc).isoformat(),home=str(home),
        manifest_sha256=MANIFEST_SHA,files_sha256=hashes,agents_sha256=AGENTS_SHA,override_absent=True,
        idempotent_readonly_check=True,global_mutation=False,temporary_paths_deleted=deleted,
        installed_extra_entries=sorted(p.name for p in target.iterdir() if p.name not in expected))))

if __name__=='__main__':main()
