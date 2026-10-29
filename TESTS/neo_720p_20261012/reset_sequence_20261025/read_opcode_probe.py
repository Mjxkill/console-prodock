#!/usr/bin/env python3
"""Read the initial R17 TARGET capture, with no rearm or reconfiguration."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import uuid
from opcode_wrapper import HERE, ROOT, BUILD, sha, mapping, parse_csv, analyze, audit_wrapper, word
from read_gao_r15 import borrow_jtag_interface, select_neo, stop_owned_children, IDE, environment


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trial-sha', required=True)
    a=p.parse_args()
    assert re.fullmatch('[0-9a-f]{64}', a.trial_sha)
    trial=HERE/'opcode_probe_trial_01/result.json'
    assert sha(trial)==a.trial_sha
    loaded=json.loads(trial.read_text())
    assert loaded['configured'] and not loaded['restored_r15']
    assert loaded['first_command_terminated'] and loaded['mire_parked']
    assert loaded['bitstream_sha256']==sha(BUILD/'impl/pnr/ao_0.fs')
    for name, digest in loaded['files'].items(): assert sha(trial.parent/name)==digest
    wrapper=audit_wrapper()
    config=BUILD/'source/tang/boards/neo/opcode_capture.gao'
    assert sha(config)==json.loads((BUILD/'observation_preparation.json').read_text())['inputs']['source/tang/boards/neo/opcode_capture.gao']
    cli=IDE/'bin/gao_sh'
    assert sha(cli)=='4717a2afa56893861de161207bc2c4f094f53227099763ebfa2f0025ab72515b'
    out=HERE/'opcode_probe_read_01'
    assert not out.exists()
    r=dict(bitstream_sha256=loaded['bitstream_sha256'], trial_sha256=a.trial_sha,
        cli_sha256=sha(cli), gao_sha256=sha(config), wrapper=wrapper,
        programming_requested=False, rearm_requested=False, initial_read_requested=True,
        sample_period_ns=1000/75, raw_csv_us_is_sample_index=True,
        capture_read_complete=False, GPU_qualified=False, hardware_cause_established=False)
    token=uuid.uuid4().hex
    children, logs=[],[]
    def interrupt(sig, frame): raise KeyboardInterrupt('Signal '+str(sig))
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP): signal.signal(sig,interrupt)
    with (ROOT/'TESTS/neo_board.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.run(['ps','-C','openocd','-C','openFPGALoader','-C','gao_sh',
            '-C','gao_analyzer','-C','jtagserver','-o','pid=,comm='],capture_output=True,text=True)
        assert active.returncode==1 and not active.stdout.strip(),active.stdout
        out.mkdir()
        private_tmp=tempfile.mkdtemp(prefix='console-r17-gao-')
        r['runtime_dir']=private_tmp
        borrowed=None
        try:
            borrowed=borrow_jtag_interface(r)
            r['identity']=select_neo()
            env=environment()
            env['LD_PRELOAD']=str(Path('/lib/x86_64-linux-gnu/libz.so.1').resolve())+':'+env.get('LD_PRELOAD','')
            env.update(TMPDIR=private_tmp,CONSOLE_GAO_INSPECTION_TOKEN=token)
            server_env=dict(os.environ,TMPDIR=private_tmp,CONSOLE_GAO_INSPECTION_TOKEN=token)
            log=(out/'server.log').open('x');logs.append(log)
            server=subprocess.Popen(['/home/michael/gowin/Programmer/bin/jtagserver','-local'],
                cwd=out,env=server_env,stdout=log,stderr=log,start_new_session=True)
            children.append(server)
            time.sleep(.7)
            assert server.poll() is None
            command=[str(cli),'-gao',str(config),'-device','GW5AST-138C',
                '-cable','FT2CH','-location','12737','-out',str(out/'initial')]
            r['command']=command
            log=(out/'cli.log').open('x');logs.append(log)
            child=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=log,start_new_session=True)
            children.append(child)
            print('R17_GAO_INITIAL_READ_STARTED location=12737 serial=2025041420A',flush=True)
            r['returncode']=child.wait(timeout=45)
            assert r['returncode']==0
            captures=list(out.glob('initial*.csv'))
            assert len(captures)==1
            rows=parse_csv(captures[0].read_text(),mapping())
            assert len(rows)==512, 'Unexpected capture length'
            r['observation']=analyze(rows,mapping())
            m=mapping()
            r['shader_start_samples']=[i for i,row in enumerate(rows)
                if row[m['controls']['shader_start']]==1]
            r['target_geometry_samples']=[i for i,row in enumerate(rows)
                if word(row,m['geometry_header'])==0x16000000]
            r['target_window_identified']=bool(r['shader_start_samples'] and r['target_geometry_samples'])
            r['idle_host_pixel_headers']=[loaded['raw']['AFTER_'+str(i)][1] for i in range(3)]
            r['idle_host_pixel_opcodes']=[v & 0xff000000 for v in r['idle_host_pixel_headers']]
            r['gao_final_four_pixel_opcodes']=[word(row,m['pixel_Q']) for row in rows[-4:]]
            r['gao_tail_matches_idle_host']=all(value==r['idle_host_pixel_opcodes'][0] for value in
                r['gao_final_four_pixel_opcodes']+r['idle_host_pixel_opcodes'])
            r['capture_read_complete']=True
        except BaseException as error:
            r['error']=repr(error)
        finally:
            for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP): signal.signal(sig,signal.SIG_IGN)
            r['owned_detached_servers']=stop_owned_children(children,token)
            if borrowed:
                lib,ctx,handle,detached=borrowed
                if detached: r['kernel_driver']['reattach_status']=lib.libusb_attach_kernel_driver(handle,0)
                lib.libusb_close(handle);lib.libusb_exit(ctx)
            for log in logs:log.close()
            r['outputs']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in out.iterdir() if p.is_file()}
            r['script_sha256']=sha(Path(__file__))
            (out/'result.json').write_text(json.dumps(r,indent=2)+'\n')
            print(json.dumps({k:r[k] for k in ('capture_read_complete','error','returncode') if k in r}),flush=True)
    if not r['capture_read_complete'] or r.get('kernel_driver',{}).get('reattach_status',0)!=0:
        raise SystemExit(1)


if __name__=='__main__': main()
