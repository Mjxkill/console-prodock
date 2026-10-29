#!/usr/bin/env python3
"""Validate the frozen pack, temporary installs and an explicit-file archive."""
from pathlib import Path
import datetime,gzip,hashlib,importlib.util,io,json,subprocess,sys,tarfile,tempfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;PACK=HERE/'pack'
spec=importlib.util.spec_from_file_location('frozen_installer',PACK/'install_workflow.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest,doc,content=installer.verified_source(PACK)
assert manifest==(ROOT/installer.MANIFEST).read_bytes()
for name,digest in doc['files'].items():
    assert sha(ROOT/name)==digest['sha256'],name+' changed after staging'
commands=[]
for name in ['test_runner.py','test_queue.py','test_metrics.py','test_install_workflow.py','test_code_size.py']:
    command=[sys.executable,'-B',str(ROOT/name)]
    p=subprocess.run(command,capture_output=True,text=True,timeout=60)
    (HERE/(name+'.log')).write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(name+' '+p.stderr)
    commands.append(dict(command=command,exit_code=0))
command=[sys.executable,'-B',str(ROOT/'metrics_checks_01/test_deepseek_adapted.py')]
p=subprocess.run(command,capture_output=True,text=True,timeout=60)
(HERE/'deepseek_tests.log').write_text(p.stdout+p.stderr)
if p.returncode:raise RuntimeError(p.stderr)
commands.append(dict(command=command,exit_code=0))
code_manifest=dict(version=1,files=[dict(path=name,ownership='project',generated=False) for name in installer.INSTALLABLE if name.endswith('.py')])
(HERE/'code_size_manifest.json').write_text(json.dumps(code_manifest,indent=2)+'\n')
command=[sys.executable,'-B',str(PACK/'check_code_size.py'),'--project',str(PACK),'--manifest',str(HERE/'code_size_manifest.json')]
p=subprocess.run(command,capture_output=True,text=True,timeout=10)
(HERE/'code_size.log').write_text(p.stdout+p.stderr)
if p.returncode:raise RuntimeError(p.stderr+p.stdout)
commands.append(dict(command=command,exit_code=0))
with tempfile.TemporaryDirectory(prefix='final-model-workflow-') as temp:
    home=Path(temp)/'codex'
    first=installer.install(PACK,home);second=installer.install(PACK,home)
    assert first['manifest_sha256']==hashlib.sha256(manifest).hexdigest()
    assert not second['changed'] and not second['backups']
    for name in ['runner.py','dispatch_queue.py','metrics.py','install_workflow.py','check_code_size.py']:
        command=[sys.executable,'-B',str(home/'model-workflow'/name),'--help']
        p=subprocess.run(command,capture_output=True,text=True,timeout=10)
        if p.returncode:raise RuntimeError(name+' '+p.stderr)
        commands.append(dict(command=['python3','-B','TEMP_CODEX/model-workflow/'+name,'--help'],exit_code=0))
for name,digest in doc['files'].items():
    assert sha(ROOT/name)==digest['sha256'],name+' changed during tests'
manifest_sha=hashlib.sha256(manifest).hexdigest()
archive=HERE/('model-workflow-'+manifest_sha[:12]+'.tar.gz')
with archive.open('wb') as stream:
    with gzip.GzipFile(fileobj=stream,mode='wb',mtime=0,filename='') as gz:
        with tarfile.open(fileobj=gz,mode='w') as tar:
            for name in sorted((*installer.INSTALLABLE,installer.MANIFEST)):
                data=(PACK/name).read_bytes();info=tarfile.TarInfo('pack/'+name)
                info.size=len(data);info.mode=0o600;info.mtime=0
                tar.addfile(info,io.BytesIO(data))
with tarfile.open(archive,'r:gz') as tar:
    assert set(tar.getnames())=={'pack/'+name for name in (*installer.INSTALLABLE,installer.MANIFEST)}
    assert all(member.isfile() and not member.issym() for member in tar.getmembers())
report=dict(passed=True,hardware_access=False,provider_access=False,real_global_install_performed=False,
    recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),python=sys.version.split()[0],
    manifest_sha256=manifest_sha,archive=archive.name,archive_sha256=sha(archive),
    installable_files={name:value['sha256'] for name,value in doc['files'].items()},
    commands=commands,logs={p.name:sha(p) for p in HERE.glob('*.log')},
    line_counts={name:len((PACK/name).read_bytes().splitlines()) for name in installer.INSTALLABLE if name.endswith('.py')})
(HERE/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,manifest_sha256=manifest_sha,archive=archive.name,archive_sha256=sha(archive))))
