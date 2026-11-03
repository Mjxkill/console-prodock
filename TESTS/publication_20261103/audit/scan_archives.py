#!/usr/bin/env python3
"""Read current tracked tar members without extracting paths or following links."""
import importlib.util,json,tarfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
LIMIT_MEMBER=128*1024*1024
LIMIT_TOTAL=1024*1024*1024

def main():
 spec=importlib.util.spec_from_file_location('redacted_scan',HERE/'scan.py')
 scan=importlib.util.module_from_spec(spec);spec.loader.exec_module(scan)
 files=json.loads((HERE/'ARCHIVE_PATHS.json').read_text())['not_decoded_by_regex_scan']
 start=time.monotonic();findings=[];skipped=[];members=0;total=0;archives=0
 for name in files:
  p=ROOT/name
  try:
   with tarfile.open(p,'r:*') as tar:
    archives+=1
    for m in tar:
     path=name+'::'+m.name
     if m.issym() or m.islnk():
      findings+=scan.scan_bytes(m.linkname.encode(),'archive_link',path);continue
     if not m.isfile():continue
     if m.size>LIMIT_MEMBER or total+m.size>LIMIT_TOTAL:
      skipped.append({'path':path,'bytes':m.size,'reason':'explicit size bound'});continue
     f=tar.extractfile(m);data=f.read();assert len(data)==m.size
     total+=len(data);members+=1
     findings+=scan.scan_bytes(data,'current_archive_member',path)
  except tarfile.TarError as e:skipped.append({'path':name,'reason':type(e).__name__})
 result={'archives_opened':archives,'members_scanned':members,'bytes_scanned':total,
  'findings':findings,'skipped':skipped,'seconds':time.monotonic()-start,
  'limitations':['Current tracked archives only; historical compressed variants and nested compressed members not decoded','Read-only tar member stream; no extraction or symlink following','Same regex limitations as SCAN.json']}
 (HERE/'ARCHIVE_SCAN.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ['findings','skipped']},indent=2))
 print('candidate_count',len(findings),'skipped',len(skipped))

if __name__=='__main__':main()
