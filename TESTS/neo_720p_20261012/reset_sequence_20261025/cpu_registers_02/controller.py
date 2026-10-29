#!/usr/bin/env python3
"""Halt the identified R15 CPU and read GPU registers only; no DDR writes."""
import fcntl
import json
from pathlib import Path
import re
import subprocess

from load_r15 import HERE, ROOT, BUILD, BIT_SHA, preflight, hw

CODE = '''init
halt
echo R15_CPU_HALTED
echo "PC_VALUE [dict get [get_reg -force {pc}] pc]"
echo "GPU_0 [read_memory 0xe9000000 32 32]"
sleep 1000
echo "GPU_1 [read_memory 0xe9000000 32 32]"
echo R15_REGISTER_READ_COMPLETE
shutdown
'''


def main():
    preflight()
    loaded = json.loads((HERE/'cold_trial_01/result.json').read_text())
    assert loaded['configured'] and loaded['bitstream_sha256'] == BIT_SHA and not loaded['previous_restored']
    out = HERE/'cpu_registers_02'
    assert not out.exists()
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
            '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode == 1 and not active.stdout.strip(),active.stdout
        identity=hw.usb_identity()
        assert identity['neo']['path'].endswith('/3-4.4.1') and identity['esp']['path'].endswith('/3-4.4.2')
        out.mkdir()
        report=dict(bitstream_sha256=BIT_SHA,qualification='FAIL',identity=identity,
            cpu_halt_requested=True,cpu_reset_requested=False,fpga_reloaded=False,
            memory_writes=False,ddr_access=False,linux_started=False,
            loaded_identity_basis='Recorded exact SRAM load plus matching GAO configuration',
            script_sha256=hw.p.sha(Path(__file__)))
        board=hw.Hardware(out,report)
        try:
            text=board.observe('registers',CODE)
            report['cpu_halted']=bool(re.search(r'^R15_CPU_HALTED\r?$',text,re.M))
            pc=re.search(r'^PC_VALUE\s+(0x[0-9a-fA-F]+)\s*$',text,re.M)
            if pc: report['pc']=int(pc[1],16)
            raw=re.findall(r'^GPU_([01]) (.+)$',text,re.M)
            assert len(raw)==2
            values={n:[int(w,0) for w in words.split()] for n,words in raw}
            assert all(len(v)==32 for v in values.values())
            report['gpu']=values
            report['frame_delta']=(values['1'][6]-values['0'][6])&0xffffffff
            report['complete']=bool(report['cpu_halted'] and pc and 'R15_REGISTER_READ_COMPLETE' in text)
        except Exception as exc:
            report['error']=repr(exc)
            report['complete']=False
        log=out/'registers.log'
        if log.exists(): report['log_sha256']=hw.p.sha(log)
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)
        if not report['complete']: raise SystemExit(1)


if __name__=='__main__': main()
