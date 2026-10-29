#!/usr/bin/env python3
"""Read-only inventory/proposal. Never deletes, moves, programs or compiles."""
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

ROOT=Path('/home/michael/console')
HERE=Path(__file__).resolve().parent
BASE=ROOT/'tang/impl'
TEXT={'.py','.sh','.tcl','.do','.json','.md','.yaml','.yml','.toml','.ini','.cfg','.mk'}
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def save(name,obj):
    p=HERE/name
    if p.exists():raise ValueError('Refuse overwrite: '+str(p))
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def main():
    names={p.name for p in BASE.iterdir() if p.is_dir() and not p.is_symlink()}
    if any(re.fullmatch(r'[A-Za-z0-9_]+',n) is None for n in names):
        raise ValueError('A build name needs an explicit non-word reference parser')
    token=re.compile(r'[A-Za-z0-9_]+')
    tracked=set(subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines())
    references=collections.defaultdict(lambda:collections.defaultdict(set))
    sha_refs=collections.defaultdict(set)
    literal_paths=set();read_files=[];skipped=[];read_bytes=0;progress=time.monotonic()
    protected={n:['active Neo diagnosis N56/N57'] for n in names if n.startswith(('console_neo_n56','console_neo_n57'))}
    for n in ('gpu_geometry_g22r0','gpu_sdusb_c37','gpu_sdusb_c28','gpu_v1_r31'):
        protected.setdefault(n,[]).append('protected Pro Dock reference or retained release')
    for rel in tracked:
        bits=Path(rel).parts
        if bits[:2]==('tang','impl') and len(bits)>2:protected.setdefault(bits[2],[]).append('Git tracked build content')
    # Scan source/scripts, documentation, and JSON/Tcl records. Large generated
    # netlists and Linux/game caches are excluded; none is a deletion scope.
    for root,dirs,files in os.walk(ROOT,followlinks=False):
        relroot=Path(root).relative_to(ROOT)
        dirs[:]=[d for d in dirs if d not in {'.git','.venv','node_modules','__pycache__'} and not (Path(root)/d).is_symlink()]
        if relroot==HERE.relative_to(ROOT):dirs[:]=[];continue
        if relroot.parts[:2] in {('linux','build'),('linux','build-neo')}:
            dirs[:]=[];continue
        # Frozen sources are retained verbatim; their generic build scripts are
        # historical copies, not active consumers of another build's outputs.
        if relroot.parts[:2]==('tang','impl') and 'source' in relroot.parts[3:]:
            dirs[:]=[];continue
        for name in files:
            p=Path(root)/name
            if p.suffix not in TEXT or p.is_symlink():continue
            if p.stat().st_size>128*1024*1024:skipped.append(str(p.relative_to(ROOT)));continue
            try:s=p.read_text(errors='strict')
            except (UnicodeError,OSError):continue
            rel=str(p.relative_to(ROOT));read_files.append(rel);read_bytes+=len(s)
            owner=Path(rel).parts[2] if Path(rel).parts[:2]==('tang','impl') else None
            found_names={m[0] for m in token.finditer(s) if m[0] in names}
            for found in found_names:
                if found==owner:continue
                kind='code' if p.suffix in {'.py','.sh','.tcl','.do','.mk'} else 'record_or_documentation'
                references[found][kind].add(rel)
            for value in re.findall(r'(?:/home/michael/console/)?tang/impl/[^\s\"\'{};,<>]+',s):
                literal_paths.add(value.removeprefix('/home/michael/console/').rstrip(').:'))
            if owner is None:
                for digest in set(re.findall(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])',s)):
                    sha_refs[digest].add(rel)
            if time.monotonic()-progress>15:
                print(json.dumps(dict(phase='references',files=len(read_files),read_bytes=read_bytes)),flush=True);progress=time.monotonic()
    for n,ref in references.items():
        if ref.get('code'):protected.setdefault(n,[]).append('referenced by static script/Tcl consumer')
    # Explicit source paths in any compiler invocation are retained, regardless
    # of whether their parent build has other removable private files.
    source_inputs={p for p in literal_paths if (ROOT/p).is_file()}
    inventory=[];candidates=[];bitstreams=[];review=[];extensions=collections.Counter()
    for name in sorted(names):
        build=BASE/name; files=[]; size=0; allocated=0
        for root,dirs,fnames in os.walk(build,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(root)/d).is_symlink()]
            for fname in fnames:
                p=Path(root)/fname
                if p.is_symlink():continue
                st=p.stat();size+=st.st_size;allocated+=st.st_blocks*512
                files.append((p,st));extensions[p.suffix or '<none>']+=st.st_size
        manifest=build/'sources.json'
        sm=None
        try:sm=json.loads(manifest.read_text())
        except (OSError,ValueError):pass
        category='neo' if name.startswith(('console_neo','neo_','hdmi_neo')) or isinstance(sm,dict) and any('boards/neo/' in k for k in sm) else 'prodock' if name.startswith(('gpu_','console_gpu','usb_','console_')) else 'historical_unclassified'
        complete=(build/'build.log').is_file() and 'Bitstream generation completed' in (build/'build.log').read_text(errors='replace')
        item=dict(name=name,category=category,bytes=size,allocated_bytes=allocated,files=len(files),sources_manifest=bool(sm),complete=complete,protection=sorted(set(protected.get(name,[]))),references={k:sorted(v) for k,v in references[name].items()})
        inventory.append(item)
        if not sm or not complete:review.append(dict(build=name,reason='No complete build log and/or frozen sources manifest; retain pending manual classification',bytes=size))
        for p,st in files:
            rel=str(p.relative_to(ROOT));suffix=p.suffix
            if suffix=='.fs':bitstreams.append(dict(path=rel,size=st.st_size,build=name,category=category,protected=name in protected,has_references=bool(references[name]),digest=None))
            if name in protected or not sm or not complete or rel in tracked or rel in source_inputs:continue
            # Never alter source snapshots or runtime initialization copies.
            if p.parent!=build/'impl/pnr':continue
            reason=None
            if suffix in {'.pr','.p','.db'}:
                reason='Private PnR work cache; sources/netlist/bitstream/reports retained. Incremental reuse of this build would require full reroute.'
            elif suffix in {'.bin','.binx'} and p.with_suffix('.fs').is_file():
                reason='Alternate generated bitstream encoding; canonical .fs retained, no literal input dependency found.'
            elif suffix=='.html' and (p.with_suffix('.txt').is_file() or p.with_suffix('').is_file()):
                reason='HTML rendering of retained plain-text report; no literal input dependency found.'
            if reason:
                candidates.append(dict(path=rel,size=st.st_size,allocated=st.st_blocks*512,mtime_ns=st.st_mtime_ns,inode=st.st_ino,links=st.st_nlink,build=name,category=category,reason=reason))
    # Hash actual bitstreams; this identifies exact duplicate payloads without
    # assuming that two reroutes or an identical source tree are interchangeable.
    groups=collections.defaultdict(list)
    print(json.dumps(dict(phase='bitstream_hashes',files=len(bitstreams),references_files=len(read_files))),flush=True)
    for b in bitstreams:
        b['digest']=sha(ROOT/b['path']);b['sha_references']=sorted(sha_refs.get(b['digest'],()))
        groups[b['digest']].append(b)
    duplicate_groups=[]
    for digest,bs in groups.items():
        if len(bs)<2:continue
        kept=sorted(bs,key=lambda b:(not b['protected'],not b['has_references'],b['path']))[0]
        duplicate_groups.append(dict(sha256=digest,retained=kept['path'],paths=[b['path'] for b in bs]))
        for b in bs:
            if b is kept or b['protected'] or b['has_references'] or b['sha_references'] or b['path'] in source_inputs or b['path'] in tracked:continue
            p=ROOT/b['path'];st=p.stat()
            candidates.append(dict(path=b['path'],size=st.st_size,allocated=st.st_blocks*512,mtime_ns=st.st_mtime_ns,inode=st.st_ino,links=st.st_nlink,build=b['build'],category=b['category'],sha256=digest,retained_duplicate=kept['path'],reason='Exact duplicate bitstream; canonical same-SHA payload retained, no static build/path/hash reference found.'))
    # Unreferenced unique bitstreams require an explicit review, not automatic
    # removal merely because they are old or failed timing.
    unique_review=[b for b in bitstreams if not b['protected'] and not b['has_references'] and not b['sha_references'] and len(groups[b['digest']])==1]
    summary=dict(builds=len(inventory),logical_bytes=sum(x['bytes'] for x in inventory),allocated_bytes=sum(x['allocated_bytes'] for x in inventory),candidate_files=len(candidates),candidate_bytes=sum(x['size'] for x in candidates),candidate_allocated_bytes=sum(x['allocated'] for x in candidates if x['links']==1),candidate_by_category={k:sum(x['size'] for x in candidates if x['category']==k) for k in ('neo','prodock','historical_unclassified')},bitstreams=len(bitstreams),duplicate_groups=len(duplicate_groups),unique_unreferenced_bitstreams_for_review=len(unique_review),scanned_text_files=len(read_files))
    save('build_inventory.json',inventory)
    save('dependencies.json',dict(by_build={n:{k:sorted(v) for k,v in ref.items()} for n,ref in references.items()},literal_existing_files=sorted(source_inputs),scanned_text_files=read_files,skipped_text_files=skipped))
    save('bitstreams.json',dict(files=bitstreams,duplicates=duplicate_groups,unique_unreferenced_review=unique_review))
    save('manual_review.json',review)
    save('deletion_candidates.json',dict(schema=1,status='PROPOSAL_ONLY_NO_DELETION',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='tang/impl files only',summary=summary,protected_builds={n:sorted(set(v)) for n,v in protected.items()},files=candidates,limitations=['Static references are conservative; dynamically assembled external paths cannot be exhaustively resolved.','No deletion or reorganization performed. No unique bitstream is in this allowlist.','All source snapshots, .vg/.vo/.sdf/.tr, reports, scripts and proof directories retained.','References by code protect the complete build. N56/N57 diagnosis and Pro Dock releases are wholly retained.','Revalidate complete allowlist, source manifests, reference hashes, processes and file identity immediately before any deletion.'],input_sha256={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'AGENTS.md',ROOT/'ARCHI/COMPATIBILITE_CARTES.md',ROOT/'tang/boards/ownership.json',ROOT/'tang/boards/prodock/reference.json',Path(__file__))}))
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
