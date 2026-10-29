#!/usr/bin/env python3
"""Generate offline vendor SVF only, recording opened paths; never program."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent/'programmer_comparison_02'
VENDOR=Path('/home/michael/gowin/Programmer/bin/programmer_cli')
BUILDS=[('r19','console_neo_n56r19_capture_ce_local','1056917bf942ea2eaf9541b9abbb3997a8ad45eb78fc09e9432f73f3e209917c'),
        ('r21','console_neo_n56r21r1_capture_memory','2fd6f3b01bee26a835aefcef3c34712de649f0af4e1fa24ff5bb4983430200d7')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=False)
    help_result=subprocess.run([str(VENDOR),'--help'],capture_output=True,text=True,timeout=10)
    (OUT/'official_help.txt').write_text(help_result.stdout+help_result.stderr)
    assert help_result.returncode==0 and 'Create SVF file only.' in help_result.stdout
    report={'hardware_requested':False,'mode':'official offline SVF only','programmer_sha256':sha(VENDOR),'script_sha256':sha(Path(__file__)),'runs':[]}
    for name,build,digest in BUILDS:
        fs=ROOT/'tang/impl'/build/'impl/pnr/console_neo.fs';assert sha(fs)==digest
        svf=OUT/(name+'.svf');trace=OUT/(name+'_syscalls.log')
        cmd=['/usr/bin/strace','-f','-e','trace=openat,ioctl,connect','-o',str(trace),str(VENDOR),
             '--device','GW5AST-138C','--operation_index','2','--svfcreate','--svf_frequency','6',
             '--fsFile',str(fs),'--output',str(svf)]
        assert '--svfcreate' in cmd and not any(x in cmd for x in ['--scan','--scan-cables','--location','--uid'])
        run=subprocess.run(cmd,capture_output=True,text=True,cwd=OUT,timeout=60)
        (OUT/(name+'_conversion.log')).write_text(run.stdout+run.stderr)
        forbidden=[l for l in trace.read_text().splitlines() if '/dev/bus/usb/' in l or '/dev/ttyUSB' in l]
        entry={'name':name,'command':cmd,'exit_code':run.returncode,'fs_sha256':digest,
               'svf_exists':svf.exists(),'svf_bytes':svf.stat().st_size if svf.exists() else None,
               'svf_sha256':sha(svf) if svf.exists() else None,'usb_device_open_lines':forbidden}
        report['runs'].append(entry)
        (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(entry),flush=True)
        assert run.returncode==0 and svf.exists() and not forbidden
    report['files']={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='result.json'}
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
