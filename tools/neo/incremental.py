"""Freeze same-netlist incremental placement/routing with strict provenance.

A completed route can be a reference even when timing fails: this is an
optimization input, never a qualification. Pins, clocks, timing constraints
and synthesized logic must match; only physical cell locations may change.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def statements(path, placement=False):
    text='\n'.join(line.split('//',1)[0] for line in Path(path).read_text().splitlines())
    if placement:
        return [' '.join(s.split()) for s in text.split(';')
                if s.strip() and not s.strip().startswith('INS_LOC ')]
    return [' '.join(line.split()) for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def freeze(reference, build, mode='pnr'):
    if mode not in ('place','pnr'):raise ValueError('Unknown incremental mode')
    reference=Path(reference).resolve(strict=True);build=Path(build).resolve(strict=True)
    log=(reference/'build.log').read_text()
    if 'Bitstream generation completed' not in log or re.search(r'^ERROR',log,re.M):
        raise ValueError('Incomplete incremental reference')
    command=(reference/'impl/pnr/cmd.do').read_text()
    if not re.search(r'^-pn GW5AST-LV138PG484AC1/I0\s*$',command,re.M):
        raise ValueError('Incremental reference targets another FPGA')
    manifest=json.loads((reference/'sources.json').read_text())
    for rel,want in manifest.items():
        if digest(reference/'source'/rel)!=want:raise ValueError('Changed reference source '+rel)
    net=reference/'console_neo.vg'
    if not net.is_file():net=reference/'impl/gwsynthesis/console_neo.vg'
    if digest(net)!=digest(build/'console_neo.vg'):raise ValueError('Incremental netlist differs')
    board=Path('source/tang/boards/neo')
    for name,placement in (('neo.cst',True),('neo.sdc',False)):
        if statements(reference/board/name,placement)!=statements(build/board/name,placement):
            raise ValueError('Incremental pins/clocks/timing differ: '+name)
    suffix='p' if mode=='place' else 'pr'
    original=reference/f'impl/pnr/console_neo.{suffix}'
    if not original.is_file() or original.stat().st_size==0:raise ValueError('Missing incremental cache')
    target=build/f'incremental_reference.{suffix}'
    if target.exists():raise ValueError('Incremental cache already frozen')
    record=dict(mode=mode,reference=str(reference),cache=target.name,cache_sha256=digest(original),
                netlist_sha256=digest(net),reference_bitstream_sha256=digest(reference/'impl/pnr/console_neo.fs'),
                reference_manifest_sha256=digest(reference/'sources.json'),
                reference_command_sha256=digest(reference/'impl/pnr/cmd.do'),
                reference_sdc_sha256=digest(reference/board/'neo.sdc'),
                reference_cst_sha256=digest(reference/board/'neo.cst'))
    shutil.copy2(original,target)
    if digest(target)!=record['cache_sha256']:raise ValueError('Incremental cache copy changed')
    return record


def audit(build,record):
    build=Path(build);errors=[]
    mode=record.get('mode');suffix={'place':'p','pnr':'pr'}.get(mode)
    expected='incremental_reference.'+str(suffix)
    if suffix is None or record.get('cache')!=expected:
        return dict(passed=False,errors=['Unknown incremental input'])
    cache=build/expected
    if not cache.is_file() or digest(cache)!=record.get('cache_sha256'):
        errors.append('Changed incremental cache')
    if digest(build/'console_neo.vg')!=record.get('netlist_sha256'):
        errors.append('Changed incremental netlist')
    command=(build/'impl/pnr/cmd.do').read_text()
    options=re.findall(r'^-inc_(place|pnr)\s+(.+?)\s*$',command,re.M)
    if options!=[(mode,str(cache.resolve()))]:errors.append('Incremental option not applied')
    return dict(passed=not errors,errors=errors,mode=mode,cache_sha256=record.get('cache_sha256'))
