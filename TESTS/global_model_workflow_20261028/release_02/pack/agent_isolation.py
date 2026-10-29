"""Prepare explicit task copies and launch their tools with Bubblewrap isolation.

No provider credentials are used here. OpenCode is the separate trusted model
client; only its taskbox MCP tools receive access to this copied filesystem.
"""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
MODULES=('agent_box.py','agent_mcp.py')
HOST_MODULES=('agent_isolation.py','agent_mcp_launcher.py')
DENIED={'.git','.ssh','.aws','.codex','.claude','.env','secrets.env'}


def need(ok,message):
    if not ok:raise ValueError(message)


def safe(path):
    path=Path(path)
    need('..' not in path.parts,'Parent path refused')
    path=path.absolute()
    for item in (path,*path.parents):need(not item.is_symlink(),'Symlink refused: '+str(item))
    return path


def relative(value):
    need(isinstance(value,str) and value and '\\' not in value and '\0' not in value,'Invalid relative path')
    parts=value.split('/')
    need(all(p not in ('','.','..') and p not in DENIED for p in parts),'Unsafe or secret path')
    return value


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(spec,out):
    """Copy regular explicit inputs; each owned file is a separate writable bind.

    Parent directories stay read-only. Owned new files are provisioned empty,
    so tools may truncate/write but cannot replace bind targets with symlinks.
    Build temporaries belong in the isolated /tmp, not beside protected tests.
    """
    need(spec.get('schema')==1,'Unknown spec schema')
    project=safe(spec['project']);out=safe(out)
    need(project.is_dir() and not out.exists(),'Project absent or output exists')
    inputs=[relative(x) for x in spec['inputs']];owned=[relative(x) for x in spec['owned']]
    require_changes=spec.get('require_changes',True)
    need(type(require_changes)is bool,'require_changes must be boolean')
    need(inputs and (owned or not require_changes) and len(inputs)==len(set(inputs))
         and len(owned)==len(set(owned)),'Empty or duplicate paths')
    need(len(set(inputs+owned))<=512,'Too many task files')
    tests=spec['tests'];need(type(tests)is list and 0<len(tests)<=32,'No bounded test commands')
    for command in tests:validate_argv(command)
    timeout=spec.get('timeout_seconds',30)
    need(type(timeout)is int and 1<=timeout<=60,'Timeout outside1..60seconds')
    paths={}
    for name in sorted(set(inputs+owned)):
        source=safe(project/name)
        need(source.is_relative_to(project),'Path escapes project')
        if source.exists():
            need(source.is_file() and source.stat().st_size<=1048576,'Nonregular or oversized input')
            paths[name]=dict(existed=True,sha256=digest(source),bytes=source.stat().st_size)
        else:
            need(name in owned and name not in inputs,'Missing context file')
            paths[name]=dict(existed=False,sha256=None,bytes=0)
    out.mkdir(parents=True,mode=0o700);tree=out/'tree';tree.mkdir()
    for name,record in paths.items():
        dest=tree/name;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes((project/name).read_bytes() if record['existed'] else b'')
        if record['existed']:need(digest(dest)==record['sha256'],'Input changed during copy')
        dest.chmod(0o600 if name in owned else 0o400)
    policy=dict(schema=1,readable=sorted(paths),owned=owned,tests=tests,timeout_seconds=timeout)
    (out/'policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    manifest=dict(schema=1,project=str(project),directory=str(out),tree=str(tree),paths=paths,
                  owned=owned,policy_sha256=digest(out/'policy.json'),
                  modules={name:digest(HERE/name) for name in MODULES},
                  host_modules={name:digest(HERE/name) for name in HOST_MODULES},
                  manifest_path=str(out/'manifest.json'),journal_path=str(out/'audit.jsonl'))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def load(path):
    path=safe(path);manifest=json.loads(path.read_text())
    need(manifest.get('schema')==1 and manifest['manifest_path']==str(path),'Manifest identity')
    root=safe(manifest['directory']);need(root==path.parent,'Manifest directory mismatch')
    need(digest(root/'policy.json')==manifest['policy_sha256'],'Policy changed')
    for name,expected in manifest['modules'].items():
        need(name in MODULES and digest(HERE/name)==expected,'Sandbox module changed')
    need(set(manifest['modules'])==set(MODULES),'Sandbox module missing')
    need(set(manifest['host_modules'])==set(HOST_MODULES),'Launcher module missing')
    for name,expected in manifest['host_modules'].items():
        need(digest(HERE/name)==expected,'Trusted launcher changed')
    return manifest


def validate_argv(argv):
    need(type(argv)is list and 0<len(argv)<=128,'Invalid argv')
    need(all(type(a)is str and a and '\0' not in a and len(a)<=16384 for a in argv),'Invalid argv value')


def command(manifest_path,argv):
    """Fixed mount construction; never interpolate model text into host shell."""
    validate_argv(argv);m=load(manifest_path);tree=safe(m['tree'])
    need(tree==Path(m['directory'])/'tree','Copy identity changed')
    args=['/usr/bin/bwrap','--unshare-all','--unshare-user','--die-with-parent','--new-session',
          '--as-pid-1','--disable-userns','--cap-drop','ALL','--clearenv',
          '--setenv','PATH','/usr/bin:/bin','--setenv','LANG','C.UTF-8',
          '--setenv','HOME','/tmp','--setenv','PYTHONNOUSERSITE','1',
          '--setenv','PYTHONDONTWRITEBYTECODE','1',
          '--ro-bind','/usr','/usr','--symlink','usr/bin','/bin',
          '--proc','/proc','--dev','/dev','--tmpfs','/tmp',
          '--dir','/control','--dir','/isolation','--ro-bind',str(tree),'/work',
          '--ro-bind',str(Path(m['directory'])/'policy.json'),'/control/policy.json']
    for library in ('/lib','/lib64'):
        if Path(library).exists():args+=['--ro-bind',library,library]
    for name in MODULES:args+=['--ro-bind',str(HERE/name),'/isolation/'+name]
    for name in m['owned']:
        path=safe(tree/relative(name));need(path.is_file(),'Owned bind missing')
        args+=['--bind',str(path),'/work/'+name]
    return args+['--chdir','/work','--hostname','taskbox','--',*argv]


def mcp_config(manifest_path):
    load(manifest_path)
    return {'taskbox':dict(type='local',enabled=True,timeout=65000,
        command=['/usr/bin/env','-i','PATH=/usr/bin:/bin','LANG=C.UTF-8',
                 '/usr/bin/python3','-B',str(HERE/'agent_mcp_launcher.py'),str(safe(manifest_path))])}


def invoke(manifest_path,argv,timeout=65):
    """Secret-free host launcher; all task argv execute only inside Bubblewrap."""
    return subprocess.run(command(manifest_path,argv),capture_output=True,timeout=timeout,
                          env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})


def preflight(manifest_path):
    try:
        result=invoke(manifest_path,['/usr/bin/python3','-B','/isolation/agent_box.py','preflight'])
        data=json.loads(result.stdout) if result.returncode==0 else {}
        ok=result.returncode==0 and data.get('passed')is True
        return dict(isolation_verified=ok,infrastructure_ok=ok,backend='bubblewrap',
                    details=data,stderr=result.stderr.decode(errors='replace'))
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        return dict(isolation_verified=False,infrastructure_ok=False,backend='bubblewrap',error=str(error))


def collect_changes(manifest_path):
    m=load(manifest_path);project=Path(m['project']);tree=Path(m['tree'])
    changed=[];violations=[];diff=[];originals=True;context=True
    for name,record in m['paths'].items():
        source=safe(project/name);copy=tree/name
        if source.exists()!=record['existed'] or (record['existed'] and digest(source)!=record['sha256']):
            originals=False;violations.append('Original changed: '+name)
        if copy.is_symlink() or not copy.is_file() or copy.stat().st_size>1048576:
            violations.append('Invalid copied file: '+name);continue
        after=digest(copy);before=record['sha256']
        if (record['existed'] and after!=before) or (not record['existed'] and copy.stat().st_size):
            if name not in m['owned']:
                context=False;violations.append('Context changed: '+name);continue
            changed.append(dict(path=name,status='modified' if record['existed'] else 'added',
                                before_sha256=before,after_sha256=after))
            old=source.read_text(errors='replace').splitlines(True) if source.exists() else []
            diff.extend(difflib.unified_diff(old,copy.read_text(errors='replace').splitlines(True),
                                           fromfile='a/'+name,tofile='b/'+name))
    actual={str(p.relative_to(tree)) for p in tree.rglob('*') if p.is_file() or p.is_symlink()}
    if actual!=set(m['paths']):violations.append('Unexpected copied files')
    return dict(policy_ok=not violations,changed_files=[x['path'] for x in changed],changes=changed,
                diff=''.join(diff),originals_unchanged=originals,context_unchanged=context,violations=violations)


def run_tests(manifest_path):
    result=invoke(manifest_path,['/usr/bin/python3','-B','/isolation/agent_box.py','tests'],timeout=1950)
    try:data=json.loads(result.stdout)
    except ValueError:data={}
    infrastructure=result.returncode==0 and type(data.get('test_results'))is list
    checks=data.get('test_results',[]);failures=sum(r['returncode']!=0 for r in checks)
    limited=any(r.get('timeout') or r.get('output_limited') for r in checks)
    policy=collect_changes(manifest_path)['policy_ok'] and not limited
    ok=infrastructure and policy and not failures
    return dict(passed=ok,returncode=0 if ok else 1,
                tests_returncode=0 if ok else 1,policy_ok=policy,
                infrastructure_ok=infrastructure,test_runs=len(checks),test_failures=failures,
                tests_log=json.dumps(data,ensure_ascii=False)+'\n'+result.stderr.decode(errors='replace'))
