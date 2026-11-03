#!/usr/bin/env python3
"""D128: synthesize only diagnostic helpers, then assemble frozen application.

No PNR or hardware operation exists here. Production RTL is never synthesized.
Every phase checks the reviewed input delivery and current board regression
guard. One stage, one launch, two sequential helper jobs; failures stay visible.
"""
import argparse
import fcntl
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = HERE.parent / 'instrumentation'
DELIVERY_SHA = 'f01a2a63c9c5e4154ef31222b365fb8c8b6e8fa5d33812ec287c316f054b1827'
RECIPE = ROOT / 'TESTS/neo_common_cause_20261028/copy_result_analysis_01/s400_20261031_01/build_recipe_01/recipe.py'
RECIPE_SHA = '2687209ee76af0606acb2904a86d7b206b6d9ac55eaf462e116c8e7012cf7dc8'
sys.path.insert(0, str(ROOT / 'tools'))
from board_contract import before_build, reference_check
from gowin_toolchain import IDE, PRIMITIVES, environment

JOBS = {
    'observer': ('neo_copy_dma_taps', ['neo_copy_dma_taps.v','neo_copy_dma_observe.v']),
    'bus': ('neo_capture_bus', ['neo_capture_bus.v']),
}
SOURCE_FILES = {
    'neo_copy_dma_taps.v': 'neo_copy_dma_taps.v',
    'neo_copy_dma_observe.v': 'candidate_01/neo_copy_dma_observe.v',
    'neo_capture_bus.v': 'prepared_06/neo_capture_bus.v',
}
TAP_PORTS = {k:('input',w) for k,w in dict(clk=1,resetn=1,arm_req=1,snap_req=1,gpu=22,memory=26).items()}
TAP_PORTS.update({k:('output',w) for k,w in dict(arm_ack=1,snap_ack=1,ready=1,heartbeat=1,held=64).items()})

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def need(condition, message):
    if not condition:
        raise ValueError(message)

def save(path, value):
    path.write_text(json.dumps(value,indent=2)+'\n')

def recipe_parser():
    """Reuse proven S400 netlist/port parsing only; none of its actions run."""
    need(sha(RECIPE)==RECIPE_SHA,'Historical parser dependency changed')
    spec=importlib.util.spec_from_file_location('frozen_s400_helper_recipe',RECIPE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def source_guard():
    path=SOURCE/'DELIVERY.json'
    need(sha(path)==DELIVERY_SHA,'Reviewed D128 delivery changed')
    delivery=json.loads(path.read_text())
    need(delivery['status']=='READY_FOR_SEPARATE_HELPER_SYNTHESIS_NOT_ROUTED','Delivery not ready for helpers')
    for name,digest in delivery['files'].items():
        need(sha(SOURCE/name)==digest,'Delivery input changed: '+name)
    for name,digest in delivery['constraints'].items():
        need(sha(ROOT/name)==digest,'Constraint changed: '+name)
    proof=json.loads((SOURCE/'prepared_06/result.json').read_text())
    need(proof['passed'] and proof['inverse_exact'],'Passive preparation not proven')
    need(proof['application_cells_preserved']==34916,'Unexpected application cell proof')
    return delivery,recipe_parser()

def current_guard():
    delivery,parser=source_guard()
    return delivery,parser,before_build('neo',candidate=True)

def prepare(stage):
    delivery,parser,guard=current_guard()
    need(not stage.exists(),'Refusing an existing stage')
    # Validate the entire passive archive before making a stage directory.
    application=gzip.decompress((SOURCE/delivery['passive_application']).read_bytes()).decode()
    need(hashlib.sha256(application.encode()).hexdigest()==delivery['application_uncompressed_sha256'],
         'Prepared netlist differs from reviewed archive')
    blocks=parser.modules(application)
    need(len(blocks)==delivery['application_modules'],'Passive module count changed')
    need(not {'neo_copy_dma_taps','neo_copy_dma_observe','neo_capture_bus'} & blocks.keys(),
         'Helpers already present in application')
    stage.mkdir();(stage/'sources').mkdir()
    for dest,src in SOURCE_FILES.items():
        data=(SOURCE/src).read_bytes()
        need(len(data.splitlines())<=1000,'Owned helper exceeds1000 lines: '+src)
        (stage/'sources'/dest).write_bytes(data)
    (stage/'application.vg.gz').write_bytes((SOURCE/delivery['passive_application']).read_bytes())
    for key,(top,files) in JOBS.items():
        job=stage/key;job.mkdir()
        project=ET.Element('Project');ET.SubElement(project,'Version').text='beta'
        ET.SubElement(project,'Device',id='GW5AST-138C',package='PBGA484A',speed='1',partNumber='GW5AST-LV138PG484AC1/I0')
        filelist=ET.SubElement(project,'FileList')
        for name in files:
            ET.SubElement(filelist,'File',path=str(stage/'sources'/name),type='verilog')
        options=ET.SubElement(project,'OptionList')
        for key,value in [('disable_insert_pad','1'),('enable_dsrm','0'),('output_file',top+'.vg'),
                          ('top_module',top),('vcc','0.9'),('vccx','1.8'),('verilog_language','sysv-2017')]:
            ET.SubElement(options,'Option',type=key,value=value)
        ET.indent(project);ET.ElementTree(project).write(job/'helper.prj',encoding='utf-8',xml_declaration=True)
    save(stage/'board_contract.json',guard)
    save(stage/'stage.json',dict(status='HELPERS_PREPARED_NOT_SYNTHESIZED',PNR=False,hardware=False,
        delivery_sha256=DELIVERY_SHA,builder_sha256=sha(Path(__file__)),parser_sha256=RECIPE_SHA,
        tool=str(IDE/'bin/GowinSynthesis'),tool_sha256=sha(IDE/'bin/GowinSynthesis'),
        primitive_library_sha256=sha(PRIMITIVES),application_sha256=delivery['application_uncompressed_sha256'],
        preserved_modules=len(blocks),constraints=delivery['constraints'],
        files={str(p.relative_to(stage)):sha(p) for p in stage.rglob('*') if p.is_file()}))
    print('Prepared diagnostic helpers only:',stage,flush=True)

def check(stage):
    delivery,parser,guard=current_guard()
    record=json.loads((stage/'stage.json').read_text())
    need(record['delivery_sha256']==DELIVERY_SHA,'Unreviewed source delivery')
    need(record['builder_sha256']==sha(Path(__file__)),'Builder changed after preparation')
    need(record['tool_sha256']==sha(IDE/'bin/GowinSynthesis'),'Gowin executable changed')
    need(record['primitive_library_sha256']==sha(PRIMITIVES),'Simulation library changed')
    for name,digest in record['files'].items():need(sha(stage/name)==digest,'Staged input changed: '+name)
    return record,parser,guard

def process_inventory():
    """Observe other jobs; never signal a process discovered by this inventory."""
    data=subprocess.check_output(['ps','-eo','pid,etimes,comm,args'],text=True)
    return [line.strip() for line in data.splitlines() if any(
        word in line for word in ('/GowinSynthesis','/gw_sh','/gw_pnr'))]

def synthesize(stage):
    record,_,guard=check(stage)
    with (stage/'synthesis.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        need(not (stage/'launch.json').exists(),'Duplicate launch refused')
        save(stage/'launch.json',dict(started_unix=time.time(),stage_sha256=sha(stage/'stage.json'),
            current_regressions=guard['local_regressions'],other_gowin_processes=process_inventory(),PNR=False))
        for key,(top,_) in JOBS.items():
            job=stage/key;start=time.monotonic();child=None
            result=dict(job=key,top=top,PNR=False,hardware=False,stage_sha256=sha(stage/'stage.json'),
                tool_sha256=record['tool_sha256'],project_sha256=sha(job/'helper.prj'))
            with (job/'synthesis.log').open('x') as log:
                try:
                    old=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGTERM,signal.SIGHUP,signal.SIGINT})
                    try:
                        child=subprocess.Popen([record['tool'],'-prj',str(job/'helper.prj')],cwd=job,
                            env=environment(),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                        result['pid']=child.pid
                        save(job/'process.json',dict(pid=child.pid,started_unix=time.time(),owned=True))
                    finally:signal.pthread_sigmask(signal.SIG_SETMASK,old)
                    print('Helper synthesis',key,'PID',child.pid,flush=True)
                    result['returncode']=child.wait(timeout=600)
                except BaseException as error:
                    result['error']=repr(error)
                    if child is not None and child.poll() is None:
                        os.killpg(child.pid,signal.SIGTERM)
                        try:child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
            netlist=job/(top+'.vg');text=(job/'synthesis.log').read_text(errors='replace')
            result.update(elapsed_seconds=time.monotonic()-start,log_sha256=sha(job/'synthesis.log'),
                          netlist_sha256=sha(netlist) if netlist.exists() else None)
            result['passed']=result.get('returncode')==0 and netlist.is_file() and \
                'GowinSynthesis finish' in text and not re.search(r'^ERROR',text,re.M)
            save(job/'result.json',result)
            need(result['passed'],'Helper synthesis failed: '+key+'; no retry')
    reference_check()

def assemble(stage,out):
    record,parser,_=check(stage)
    application=gzip.decompress((stage/'application.vg.gz').read_bytes()).decode()
    need(hashlib.sha256(application.encode()).hexdigest()==record['application_sha256'],'Application archive changed')
    original=parser.modules(application);helpers={};proof={}
    known=set(re.findall(r'^module\s+(\w+)\b',PRIMITIVES.read_text(),re.M))
    for key,(top,_) in JOBS.items():
        job=stage/key;r=json.loads((job/'result.json').read_text());netlist=job/(top+'.vg')
        need(r['passed'] and r['stage_sha256']==sha(stage/'stage.json'),'Unqualified helper: '+key)
        for field,path in [('project_sha256',job/'helper.prj'),('log_sha256',job/'synthesis.log'),
                           ('netlist_sha256',netlist)]:need(r[field]==sha(path),'Changed helper evidence: '+field)
        need(r['tool_sha256']==record['tool_sha256'],'Helper tool differs')
        blocks=parser.modules(netlist.read_text())
        need(top in blocks,'Missing helper top')
        need(parser.ports(blocks[top])==(TAP_PORTS if key=='observer' else parser.BUS_PORTS),'Helper port contract mismatch')
        need(not blocks.keys() & (original.keys()|helpers.keys()),'Duplicate module in assembly')
        for block in blocks.values():
            for cell in parser.INV.cells(block).values():
                need(cell['kind'] in known or cell['kind'] in blocks,'Unknown mapped helper cell '+cell['kind'])
        helpers.update(blocks);proof[key]=dict(modules=sorted(blocks),netlist_sha256=sha(netlist),
            result_sha256=sha(job/'result.json'))
    merged=application+'\n\n'+'\n\n'.join(helpers.values())+'\n'
    all_modules=parser.modules(merged)
    need(all(all_modules[n]==b for n,b in original.items()),'Application module changed during assembly')
    need(merged[:len(application)]==application,'Application byte prefix differs')
    need(not out.exists(),'Assembly output already exists');out.mkdir()
    (out/'console_neo.vg.gz').write_bytes(gzip.compress(merged.encode(),mtime=0))
    save(out/'assembly.json',dict(status='ASSEMBLED_PENDING_MAPPED_REVIEW',passed=True,PNR=False,hardware=False,
        stage_sha256=sha(stage/'stage.json'),application_sha256=record['application_sha256'],
        preserved_modules=len(original),netlist_sha256=hashlib.sha256(merged.encode()).hexdigest(),
        archive_sha256=sha(out/'console_neo.vg.gz'),helpers=proof,constraints=record['constraints'],
        limits=['128-bit photo mapping, held/shadow transport simulation and root review still required.',
                'VG alias grammar has not been checked by the PNR frontend.',
                'No timing, physical mapping or hardware qualification.']))
    print('Assembled for mapped review only:',out,flush=True)

def owned(path):
    path=path.resolve();need(path.is_relative_to(HERE),'Output outside owned build folder');return path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','check','synth','assemble'))
    parser.add_argument('--stage',type=Path,required=True)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--execute-reviewed',action='store_true')
    args=parser.parse_args();stage=owned(args.stage)
    if args.action=='prepare':prepare(stage)
    elif args.action=='check':check(stage);print('STAGE_GUARDS_PASS')
    elif args.action=='assemble':
        need(args.out is not None,'Assembly output required');assemble(stage,owned(args.out))
    else:
        need(args.execute_reviewed,'Explicit root-reviewed synthesis flag required')
        def interrupted(number,frame):raise InterruptedError('Signal '+str(number))
        old={n:signal.signal(n,interrupted) for n in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT)}
        try:synthesize(stage)
        finally:
            for n,handler in old.items():signal.signal(n,handler)

if __name__=='__main__':main()
