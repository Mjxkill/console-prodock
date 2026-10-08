#!/usr/bin/env python3
"""Erreurs SD/MSC adversariales sous ASan/UBSan ; uniquement des supports simulés."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    report=dict(passed=False,cases=[])
    sources=['TESTS/host/sd_model.c','fw_console/sd.c']
    all_sources=sources+['TESTS/host/sd_fault_test.c','TESTS/host/usb_msc_fault_test.c',
                         'TESTS/host/usb_msc_test.c','fw_console/usb_msc.c','fw_console/sd.h','fw_console/usb_msc.h']
    report['sha256']={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in all_sources}
    try:
        with tempfile.TemporaryDirectory(prefix='console_storage_faults_') as tmp:
            for name,extra,defines,marker in [
                ('sd',['TESTS/host/sd_fault_test.c'],[],'SD FAULT PASS'),
                ('msc',['TESTS/host/usb_msc_fault_test.c','fw_console/usb_msc.c'],['-DUSB_MSC_HOST_MODEL'],'MSC FAULT PASS')]:
                exe=Path(tmp)/name
                command=['cc','-std=c11','-O1','-g','-Wall','-Wextra','-fsanitize=undefined,address',
                         '-fno-sanitize-recover=all',*defines,'-I',str(ROOT/'fw_console'),
                         *[str(ROOT/s) for s in sources+extra],'-o',str(exe)]
                subprocess.run(command,check=True)
                result=subprocess.run([str(exe)],capture_output=True,text=True,timeout=60)
                (args.out/(name+'.log')).write_text(result.stdout+result.stderr)
                passed=result.returncode==0 and marker in result.stdout
                report['cases'].append(dict(name=name,returncode=result.returncode,passed=passed))
                if not passed:raise RuntimeError(result.stdout+result.stderr)
                print(result.stdout,end='',flush=True)
        report['passed']=True
    finally:
        (args.out/'result.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
