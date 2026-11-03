#!/usr/bin/env python3
"""Read-only publication audit. Never persists credential values.

Scans tracked worktree/index plus all blobs/commit/tag messages reachable from
all Git refs. Patterns are heuristic, not a substitute for a secret-scanning
product; compressed/nested file content is not decoded by this pass.
"""
import collections,hashlib,json,os,re,shutil,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PATTERNS=[
 ('private_key',rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),
 ('github_token',rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})'),
 ('openai_anthropic_style_token',rb'\bsk-(?:proj-|ant-api[0-9]+-)?[A-Za-z0-9_-]{24,}'),
 ('aws_access_id',rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
 ('google_api_key',rb'\bAIza[A-Za-z0-9_-]{35}\b'),
 ('slack_token',rb'\bxox[baprs]-[A-Za-z0-9-]{20,}'),
 ('gitlab_token',rb'\bglpat-[A-Za-z0-9_-]{20,}'),
 ('literal_credential',rb'(?i)(?:api[_-]?key|access[_-]?token|auth[_-]?token|secret[_-]?key|password|passwd|passphrase|ollama_api_key)["\x27]?\s*[:=]\s*["\x27]([A-Za-z0-9_.+/=-]{12,})["\x27]'),
 ('bearer_literal',rb'(?i)Bearer\s+([A-Za-z0-9_.+/=-]{20,})'),
 ('url_user_password',rb'(?i)https?://[^\s:/@]{1,100}:([^\s/@]{5,})@'),
]
PATTERNS=[(n,re.compile(p)) for n,p in PATTERNS]
PLACEHOLDER=re.compile(rb'(?i)(example|dummy|synthetic|redacted|placeholder|fake|not.?a.?real|changeme|test.?token|test.?key|x{8}|0{12})')
RUNTIME=re.compile(r'(?i)(?:^|/)(?:controller/(?:data|cache)|opencode\.db(?:-shm|-wal)?|auth\.json|secrets?\.env|\.env(?:\.|$)|id_rsa|id_ed25519|credentials(?:\.json)?$)|\.sqlite(?:3)?$')

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

def scan_bytes(data,scope,path,oid=None):
 findings=[]
 for kind,pattern in PATTERNS:
  for m in pattern.finditer(data):
   value=m.group(m.lastindex or 0)
   line=data.count(b'\n',0,m.start())+1
   a=data.rfind(b'\n',0,m.start())+1;b=data.find(b'\n',m.end());b=len(data) if b<0 else b
   context=data[a:b]
   findings.append({'scope':scope,'path':path,'object':oid,'line':line,'type':kind,
                    'matched_length':len(value),'placeholder_indicator':bool(PLACEHOLDER.search(value)),
                    'synthetic_context_indicator':bool(re.search(rb'(?i)(synthetic|test.fixture|fake.?secret|placeholder|dummy)',context)),
                    'evidence':'[VALUE REDACTED]'})
 return findings

def main():
 start=time.monotonic()
 head=git('rev-parse','HEAD').decode().strip()
 files=[os.fsdecode(x) for x in git('ls-files','-z').split(b'\0') if x]
 index={}
 for item in git('ls-files','--stage','-z').split(b'\0'):
  if item:
   meta,path=item.split(b'\t',1);index.setdefault(meta.split()[1].decode(),os.fsdecode(path))
 reachable={}
 for line in git('rev-list','--objects','--all').splitlines():
  oid,_,path=line.partition(b' ');reachable.setdefault(oid.decode(),os.fsdecode(path) or '[commit/tag]')
 reachable.update({oid:reachable.get(oid,path) for oid,path in index.items()})
 ids=list(reachable)
 proc=subprocess.Popen(['git','cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
 raw,_=proc.communicate(('\n'.join(ids)+'\n').encode());assert proc.returncode==0
 objects=[]
 for line in raw.splitlines():
  oid,kind,size=line.decode().split();objects.append((oid,kind,int(size)))
 findings=[];counts=collections.Counter();skipped=[];bytes_scanned=0
 for path in files:
  p=ROOT/path
  if p.is_symlink():
   findings+=scan_bytes(os.fsencode(os.readlink(p)),'tracked_symlink',path);continue
  if not p.exists():skipped.append({'scope':'tracked_worktree','path':path,'reason':'absent'});continue
  data=p.read_bytes();bytes_scanned+=len(data);counts['tracked_worktree_files']+=1
  findings+=scan_bytes(data,'tracked_worktree',path)
 print(json.dumps({'phase':'worktree_done','files':counts['tracked_worktree_files'],'candidate_count':len(findings)}),flush=True)
 batch=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
 for i,(oid,kind,size) in enumerate(objects):
  counts['reachable_'+kind]+=1
  if kind not in ['blob','commit','tag']:continue
  batch.stdin.write((oid+'\n').encode());batch.stdin.flush()
  header=batch.stdout.readline().split();assert header[0].decode()==oid and int(header[2])==size
  data=batch.stdout.read(size);assert len(data)==size and batch.stdout.read(1)==b'\n'
  bytes_scanned+=size
  findings+=scan_bytes(data,'git_'+kind,reachable[oid],oid)
  if i%1000==0:print(json.dumps({'phase':'history','objects_visited':i,'candidate_count':len(findings)}),flush=True)
 batch.stdin.close();batch.wait();assert batch.returncode==0
 cfg=subprocess.run(['git','config','--get-regexp',r'^remote\..*\.url$'],cwd=ROOT,capture_output=True)
 findings+=scan_bytes(cfg.stdout,'local_git_remote_configuration','[remote URL configuration]')
 runtime_current=[p for p in files if RUNTIME.search(p)]
 runtime_history=[{'path':p,'object':o} for o,p in reachable.items() if RUNTIME.search(p)]
 report={'schema':1,'head_start':head,'head_end':git('rev-parse','HEAD').decode().strip(),'shallow':git('rev-parse','--is-shallow-repository').decode().strip(),
  'scanners':{x:shutil.which(x) for x in ['gitleaks','trufflehog']},'tool':'local redacted heuristic scanner scan.py',
  'counts':dict(counts),'bytes_scanned_including_duplicate_worktree_versions':bytes_scanned,'seconds':time.monotonic()-start,
  'findings':findings,'runtime_paths_current':runtime_current,'runtime_paths_reachable':runtime_history,'skipped':skipped,
  'limitations':['No gitleaks/trufflehog installed','Regex heuristics can miss arbitrary/high-entropy secrets or produce false positives','Compressed archives and encoded credentials not decoded','Git --all reachable refs plus current index only; no reflog-only/dangling objects','Untracked/ignored files excluded from this pass; a final staged snapshot requires rescan','No credential validity or network authentication attempted']}
 (HERE/'SCAN.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'finished':True,'counts':dict(counts),'findings':len(findings),'runtime_current':len(runtime_current),'runtime_history':len(runtime_history),'seconds':report['seconds']}))

if __name__=='__main__':main()
