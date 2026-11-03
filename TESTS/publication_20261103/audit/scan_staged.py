#!/usr/bin/env python3
"""Scan staged added/modified blobs; report metadata only, never secret values.

Run after final git add, before commit/push. This complements the frozen full
history scan; it neither edits the index nor treats regex absence as clearance.
"""
import hashlib,importlib.util,json,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

def main():
 spec=importlib.util.spec_from_file_location('redacted_scan',HERE/'scan.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 start=time.monotonic();index=git('ls-files','--stage','-z');mapping={}
 for item in index.split(b'\0'):
  if item:
   meta,path=item.split(b'\t',1);mapping[path.decode()]=meta.split()[1].decode()
 names=[x.decode() for x in git('diff','--cached','--name-only','--diff-filter=ACMR','-z').split(b'\0') if x]
 findings=[]
 for name in names:
  oid=mapping[name];findings+=m.scan_bytes(git('cat-file','blob',oid),'staged_blob',name,oid)
 result={'head':git('rev-parse','HEAD').decode().strip(),'index_sha256':hashlib.sha256(index).hexdigest(),
   'staged_changed_blobs_scanned':len(names),'files':names,'findings':findings,'seconds':time.monotonic()-start,
   'index_unchanged_during_scan':index==git('ls-files','--stage','-z'),'limitations':['Changed staged blobs only; baseline history scope in SCAN.json','Regex heuristics; no archive decoding in this short pass']}
 (HERE/'STAGED_SCAN.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'files':len(names),'candidate_occurrences':len(findings),'index_stable':result['index_unchanged_during_scan']},indent=2))

if __name__=='__main__':main()
