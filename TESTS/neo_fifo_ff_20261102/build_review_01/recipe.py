#!/usr/bin/env python3
"""Replace two reviewed command memories only; no PNR/hardware action here.

Helper synthesis uses the frozen process/lock engine. All other modules,
connections, parameters and constraints are preserved; inversion is byte exact.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import signal
import sys
import time
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
BASE=ROOT/'tang/impl/console_neo_reject_20261102_r1'
NET_SHA='76d56bd49776d12919c8051f5460bb5e7cadf73fb388ac2bd2cddea63c63b255'
PINS={'console_neo.vg':NET_SHA,
 'neo.cst':'6330c9dd971b9151c08bddcf8b7b6a529983bc25f1c03ab4193b0b6a224aeac1',
 'neo.sdc':'c8da535e839157a361e78b06b2f65b2912891f8e9dc48b02d5b315ae9f953113'}
ENGINE=ROOT/'TESTS/neo_copy_dma_20261101/build/build.py'
ENGINE_SHA='bdfd7ed38d95b24629d07f1059879904150ab0c556f4263affc6cf646cf25d15'
AUDIT=ROOT/'TESTS/neo_copy_dma_20261101/escaped_port_review/audit.py'
AUDIT_SHA='c66738f5aae68afea7f34708c0de612f21e959bfb52172a653dec8baf383aaef'
TEMPLATE=ROOT/'TESTS/neo_copy_dma_20261101/reject_build_20261102/stage_04/child/helper.prj'
TOP='neo_command_ff128'
TARGETS={'ddr_dcfifo_3':r'\g_inferred_storage.mem_g_inferred_storage.mem_0_0_s',
         'blitter':'cmem_cmem_0_0_s'}
PARAMETERS={'BIT_WIDTH_0':'32','BIT_WIDTH_1':'32','READ_MODE':"1'b0",
            'RESET_MODE':'"SYNC"','BLK_SEL_0':"3'b000",'BLK_SEL_1':"3'b000"}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(text):return hashlib.sha256(text.encode()).hexdigest()
def need(ok,message):
    if not ok:raise ValueError(message)
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def load(path,expected,name):
    need(sha(path)==expected,'Dependency changed '+str(path))
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def modules_api():return load(AUDIT,AUDIT_SHA,'ff_frozen_mapped_parser')
def engine():
    sys.path.insert(0,str(ROOT/'tools'))
    return load(ENGINE,ENGINE_SHA,'ff_frozen_helper_process')

def guards():
    for name,h in PINS.items():need(sha(BASE/name)==h,'Base changed '+name)
    return engine().reference_check()


def replace_memories(text):
    """Two type substitutions and twelve defparam removals, nothing else."""
    a=modules_api();modules=a.modules(text);changed=text;rows=[]
    for module,instance in TARGETS.items():
        block=modules[module];cell=a.instances(block)[instance]
        need(cell['kind']=='SDPB','Target is not SDPB '+module)
        replacement=re.sub(r'^(\s*)SDPB\b',r'\1'+TOP,cell['raw'],count=1)
        need(replacement!=cell['raw'],'Missing unique cell type')
        new=block.replace(cell['raw'],replacement,1);removed=[]
        for key,value in PARAMETERS.items():
            pattern=r'^defparam\s+'+re.escape(instance)+r'\s*\.'+key+r'\s*=\s*'+re.escape(value)+r';\n'
            matches=list(re.finditer(pattern,new,re.M))
            need(len(matches)==1,'Parameter mismatch '+module+'/'+key)
            line=matches[0].group();removed.append(line);new=new.replace(line,'',1)
        # Restore each line at its original offset in the original module.
        inverse=new.replace(replacement,cell['raw'],1)
        for line in removed:
            before=block[:block.index(line)]
            offset=len(before)-sum(len(x) for x in removed if block.index(x)<block.index(line))
            # Insert lines in original order: earlier removals already restored.
            offset+=sum(len(x) for x in removed[:removed.index(line)])
            inverse=inverse[:offset]+line+inverse[offset:]
        need(inverse==block,'Inverse did not restore original module')
        need(changed.count(block)==1,'Nonunique target module')
        changed=changed.replace(block,new,1)
        rows.append(dict(module=module,instance=instance,old=cell['raw'],new=replacement,
                         removed_defparams=removed,original_module_sha256=digest(block),
                         transformed_module_sha256=digest(new)))
    after=a.modules(changed)
    need(set(after)==set(modules),'Module inventory changed')
    need(all(after[n]==b for n,b in modules.items() if n not in TARGETS),'Unrelated module changed')
    inverse_all=changed
    for name in TARGETS:inverse_all=inverse_all.replace(after[name],modules[name],1)
    need(inverse_all==text,'Full application inverse is not byte exact')
    # Connections including clocks, enables, resets and addresses are identical.
    for row in rows:
        old=a.instances(modules[row['module']]);new=a.instances(after[row['module']])
        need(old.keys()==new.keys(),'Cell added/removed outside helper')
        for name,c in old.items():
            need(c['ports']==new[name]['ports'],'Connection changed '+name)
            need(new[name]['kind']==(TOP if name==row['instance'] else c['kind']),'Unexpected type delta')
    return changed,rows


def project(stage):
    tree=ET.parse(TEMPLATE);root=tree.getroot();files=root.find('FileList');files.clear()
    ET.SubElement(files,'File',path=str(stage/'sources'/f'{TOP}.v'),type='verilog')
    for option in root.find('OptionList'):
        if option.attrib['type']=='top_module':option.set('value',TOP)
        if option.attrib['type']=='output_file':option.set('value',TOP+'.vg')
    ET.indent(tree);tree.write(stage/'helper/helper.prj',encoding='utf-8',xml_declaration=True)


def prepare(stage,source,source_sha):
    guards();need(not stage.exists(),'Stage already exists')
    need(source.is_file() and sha(source)==source_sha,'Helper source hash mismatch')
    need(len(source.read_bytes().splitlines())<=1000,'Helper source exceeds line limit')
    changed,rows=replace_memories((BASE/'console_neo.vg').read_text())
    stage.mkdir();(stage/'sources').mkdir();(stage/'helper').mkdir()
    (stage/'sources'/f'{TOP}.v').write_bytes(source.read_bytes());project(stage)
    (stage/'application.vg.gz').write_bytes(gzip.compress(changed.encode(),mtime=0))
    save(stage/'substitutions.json',rows)
    e=engine()
    save(stage/'stage.json',dict(status='PREPARED_ONLY',source=str(source),source_sha256=source_sha,
        base_sha256=NET_SHA,application_sha256=digest(changed),builder_sha256=sha(Path(__file__)),
        tool=str(e.IDE/'bin/GowinSynthesis'),tool_sha256=sha(e.IDE/'bin/GowinSynthesis'),
        primitive_library_sha256=sha(e.PRIMITIVES),template_sha256=sha(TEMPLATE),
        files={str(p.relative_to(stage)):sha(p) for p in stage.rglob('*') if p.is_file()},
        constraints={k:v for k,v in PINS.items() if k!='console_neo.vg'},PNR=False,hardware=False))


def check(stage,regressions=False):
    guards();r=json.loads((stage/'stage.json').read_text());e=engine()
    need(r['base_sha256']==NET_SHA and r['builder_sha256']==sha(Path(__file__)),'Builder/base changed')
    for name,h in r['files'].items():need(sha(stage/name)==h,'Stage input changed '+name)
    for key,path in [('tool_sha256',e.IDE/'bin/GowinSynthesis'),('primitive_library_sha256',e.PRIMITIVES),('template_sha256',TEMPLATE)]:
        need(sha(path)==r[key],'Changed '+key)
    return r,None,e.before_build('neo',candidate=True) if regressions else e.reference_check()


def synth(stage):
    e=engine();e.JOBS={'helper':(TOP,[TOP+'.v'])};e.check=lambda selected:check(selected,True)
    def interrupted(number,frame):raise InterruptedError('Signal '+str(number))
    old={n:signal.signal(n,interrupted) for n in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
    try:e.synthesize(stage)
    finally:
        for n,h in old.items():signal.signal(n,h)


def assemble(stage,out):
    r,_,_=check(stage);a=modules_api();e=engine();job=stage/'helper';receipt=json.loads((job/'result.json').read_text())
    need(receipt['passed'] and receipt['stage_sha256']==sha(stage/'stage.json'),'Helper synthesis not qualified')
    for key,path in [('netlist_sha256',job/(TOP+'.vg')),('project_sha256',job/'helper.prj'),('log_sha256',job/'synthesis.log')]:
        need(receipt[key]==sha(path),'Changed synthesis evidence '+key)
    helper=(job/(TOP+'.vg')).read_text();hm=a.modules(helper)
    need(TOP in hm,'Missing helper top')
    primitive_names=set(re.findall(r'^module\s+(\w+)\b',e.PRIMITIVES.read_text(),re.M))
    counts=Counter(cell['kind'] for b in hm.values() for cell in a.instances(b).values())
    need(all(k in primitive_names or k in hm for k in counts),'Unknown helper primitive')
    need(not any('RAM' in k.upper() or k in ('SDPB','SDPX9B','SP','SPX9','DP','DPX9B','ROM') for k in counts),'Helper inferred memory primitive')
    need(sum(v for k,v in counts.items() if k.startswith('DFF'))>=4096,'Expected FF storage absent')
    expected={'DO':('output','[','31',':','0',']'),'DI':('input','[','31',':','0',']')}
    expected.update({k:('input','[','2',':','0',']') for k in ('BLKSELA','BLKSELB')})
    expected.update({k:('input','[','13',':','0',']') for k in ('ADA','ADB')})
    expected.update({k:('input',) for k in ('CLKA','CLKB','CEA','CEB','OCE','RESET')})
    need(a.declarations(hm[TOP])==expected,'Mapped helper interface changed')
    base=(BASE/'console_neo.vg').read_text();changed,rows=replace_memories(base)
    need(digest(changed)==r['application_sha256'],'Prepared substitutions changed')
    need(gzip.decompress((stage/'application.vg.gz').read_bytes()).decode()==changed,'Application archive changed')
    need(not (set(a.modules(base))&set(hm)),'Helper module collision')
    merged=changed+'\n\n'+helper+'\n';mm=a.modules(merged)
    for module,instance in TARGETS.items():need(a.instances(mm[module])[instance]['kind']==TOP,'Target not replaced')
    need(not out.exists(),'Assembly output exists');out.mkdir()
    (out/'console_neo.vg.gz').write_bytes(gzip.compress(merged.encode(),mtime=0))
    before=Counter(c['kind'] for b in a.modules(base).values() for c in a.instances(b).values())
    save(out/'assembly.json',dict(passed=True,status='PENDING_INDEPENDENT_MAPPED_REVIEW',
        netlist_sha256=digest(merged),archive_sha256=sha(out/'console_neo.vg.gz'),base_sha256=NET_SHA,
        stage_sha256=sha(stage/'stage.json'),helper_sha256=sha(job/(TOP+'.vg')),
        application_inverse_exact=True,connection_changes=0,SDPB_removed=2,
        helper_primitive_counts_one_instance=dict(counts),helper_instance_count=2,
        defined_application_cell_counts_before=dict(before),constraints=r['constraints'],
        PNR=False,hardware=False,limitations=['Structural preservation is not behavioral/STA qualification.',
        'Resource counts here are mapped cells, not PNR occupancy; helper is instantiated twice.',
        'Independent mapped-memory equivalence and port/reset review required before root route.']))
    print('ASSEMBLED_PENDING_REVIEW',digest(merged),dict(counts),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('prepare','check','synth','assemble'))
    p.add_argument('--stage',type=Path,required=True);p.add_argument('--source',type=Path);p.add_argument('--source-sha')
    p.add_argument('--out',type=Path);p.add_argument('--root-reviewed-helper-synthesis',action='store_true')
    args=p.parse_args();stage=args.stage.resolve();need(stage.is_relative_to(HERE),'Stage outside ownership')
    if args.action=='prepare':need(args.source and args.source_sha,'Pinned helper required');prepare(stage,args.source.resolve(),args.source_sha)
    elif args.action=='check':check(stage);print('STAGE_GUARDS_PASS')
    elif args.action=='assemble':
        need(args.out and args.out.resolve().is_relative_to(HERE),'Owned assembly output required');assemble(stage,args.out.resolve())
    else:need(args.root_reviewed_helper_synthesis,'Explicit helper review required');synth(stage)

if __name__=='__main__':main()
