#!/usr/bin/env python3
"""Test SG4 after the confirmed explicit-PG0 CPU-free HDMI probe."""
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools/neo'))
from load_linux import check_program_status
prior=json.loads((HERE/'hdmi_pg0_trial/result.json').read_text())
assert prior['programmed'] and not prior['cpu_present_in_probe'] and not prior['linux_running']
assert prior['visual_confirmation']=='user: Oui, la mire est visible'
assert prior['bitstream_sha256']=='fb7027560c5f4e9551e9d2697cf1c4e6890b98210ddc4d7c07fb10470c31d386'
build=HERE/'hdmi_bars_dce_sg4';parent=HERE/'hdmi_bars_dce'
record=json.loads((build/'result.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert record['complete']
assert sha(build/'probe.vg')==sha(parent/'impl/gwsynthesis/probe.vg')
assert (build/'probe.cst').read_text()==(parent/'probe.cst').read_text()+'INS_LOC "u_video_fast" SG[4];\n'
for n,h in record['source_sha256'].items():assert sha(build/n)==h
for n in ['impl/pnr/probe.fs','impl/pnr/probe.tr','impl/pnr/probe.rpt.txt']:
    assert sha(build/n)==record[n+'_sha256']
report=(build/'impl/pnr/probe.tr').read_text();margins={}
for i,k in enumerate(['Setup','Hold','Recovery','Removal'],1):
    table=re.search(r'^3\.1\.'+str(i)+' '+k+r' Paths Table.*?(?=^3\.|\Z)',report,re.M|re.S)[0]
    values=[float(x) for x in re.findall(r'^\s+\d+\s+(-?\d+\.\d+)\s+',table,re.M)]
    assert values and min(values)>0
    margins[k]=min(values)
assert '<Numbers of Setup Violated Endpoints>:0' in report and '<Numbers of Hold Violated Endpoints>:0' in report
devices=[d for d in Path('/sys/bus/usb/devices').iterdir() if (d/'serial').exists() and (d/'serial').read_text().strip()=='2025041420']
assert len(devices)==1;d=devices[0]
assert (d/'idVendor').read_text().strip()=='0403' and (d/'idProduct').read_text().strip()=='6010'
busdev=':'.join((d/n).read_text().strip() for n in ['busnum','devnum'])
out=HERE/'hdmi_sg4_trial';out.mkdir(exist_ok=False)
with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with (out/'program.log').open('w') as log:
        subprocess.run([str(Path.home()/'.local/bin/openFPGALoader'),'--busdev-num',busdev,
            '-b','tangconsole','-m','--verbose','--freq','6000000',str(build/'impl/pnr/probe.fs')],
            stdout=log,stderr=log,timeout=120,check=True)
result=dict(programmed=True,program_status=check_program_status((out/'program.log').read_text()),
    bitstream_sha256=sha(build/'impl/pnr/probe.fs'),timing_minima_ns=margins,
    previous_bitstream=prior['bitstream_sha256'],visual_confirmation='pending',
    linux_running=False,cpu_present_in_probe=False,ddr_used=False,sd_written=False,flash_written=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
