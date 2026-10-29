#!/usr/bin/env python3
"""Run exact RV32 reader bytes against independently prepared memory images.

The interpreter is reused, unchanged. There is no AHB/DDR/physical timing model.
Metadata rejection and address footprints are checked separately from content.
"""
import hashlib
import json
from pathlib import Path
import struct
import time

from readback_model import Reader, JOURNAL, OLD, SCRATCH, rv
from decode import decode, decode_bound, COPY_STAGE_SHA256, READER_SHA256

HERE = Path(__file__).resolve().parent
SEED = [(SCRATCH+i*4)^0xa5396c17 for i in range(32)]
COPY = SEED[:8]+SEED[:8]+SEED[16:]


class ControlledReader(Reader):
    """Expose host-selected read-only registers without changing instruction logic."""
    def __init__(self, *args, overrides=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.overrides = overrides or {}

    def access(self, address, write=False, value=0):
        if address in self.overrides and not write:
            self.accesses.append((False,address,value))
            return self.overrides[address]
        return super().access(address,write,value)


class TransitionReader(ControlledReader):
    """Counter/status transition during CPU traffic must remain separately visible."""
    def access(self, address, write=False, value=0):
        if not write and len(self.ddr_reads) >= 16:
            self.overrides.update({rv.GPU+4:0,rv.GPU+8:2,rv.GPU+52:1})
        return super().access(address,write,value)


def check(cpu, binary, expected):
    raw = cpu.run(limit=10000)
    data = struct.pack('<64I', *raw[:64])
    result = decode_bound(data, stage_sha256=COPY_STAGE_SHA256, reader_sha256=READER_SHA256)
    assert result['classification'] == expected, result
    assert not cpu.commands and not cpu.gpu_writes
    assert all(JOURNAL <= address < JOURNAL+256 for write,address,_ in cpu.accesses if write)
    assert cpu.original_old == [cpu.word(OLD+i*4) for i in range(128)]
    assert cpu.csr[0x305] == 0x80000000
    assert not result['gpu_passed']
    if expected != 'unobserved':
        assert result['readback_valid']
        assert cpu.ddr_reads == list(range(SCRATCH,SCRATCH+128,4))
        assert result['header']['words_read'] == 32
        if expected == 'copy_exact_canaries_intact':
            assert result['image'] == COPY
            assert result['header']['error_count'] == 0
        elif expected == 'seed_unchanged':
            assert result['image'] == SEED and result['header']['error_count'] == 8
    elif result['header']['result'] == -7:
        assert len(cpu.ddr_reads)==7 and result['header']['mtval']==SCRATCH+28
    else:
        assert result['header']['result']==-1 and not cpu.ddr_reads
    return data, result, {'instructions':cpu.steps,'reads':len(cpu.ddr_reads),
                          'classification':expected,'result':result['header']['result']}


def main():
    started=time.monotonic()
    binary=(HERE/'build_01/readback.bin').read_bytes()
    old=(HERE.parent/'readback_r1/build_01/readback.bin').read_bytes()
    assert hashlib.sha256(binary).hexdigest()==READER_SHA256
    assert len(binary)==len(old)==588
    changed=[i for i in range(0,len(old),4) if old[i:i+4]!=binary[i:i+4]]
    # Decode the changed instructions, rather than merely expecting two offsets.
    assert len(changed)==2 and changed[1]==changed[0]+4
    a,b=struct.unpack_from('<2I',binary,changed[0])
    assert a&127==0x13 and (a>>12)&7==0 and (a>>7)&31==28
    assert (a>>15)&31==5 and rv.signed(a>>20,12)==-32
    assert b&127==0x33 and (b>>12)&7==4 and b>>25==0
    assert (b>>7)&31==28 and (b>>15)&31==28 and (b>>20)&31==7
    cases=[]
    valid=None
    for scenario,expected in [('copied','copy_exact_canaries_intact'),
                              ('unchanged','seed_unchanged'),
                              ('partial','other_or_partial_change'),
                              ('canary','other_or_partial_change'),('trap','unobserved')]:
        cpu=ControlledReader(binary,scenario)
        data,result,row=check(cpu,binary,expected)
        cases.append(dict(name=scenario,**row))
        if scenario=='copied':valid=data
    # Firmware guards must refuse before any DDR read.
    for name,ctor,csrs,prior,overrides in [
        ('cache',{'cache':1},{},{},{}),('milmb',{'milmb':0xa0010001},{},{},{}),
        ('satp',{}, {0x180:1},{},{}),('mie',{}, {0x304:8},{},{}),
        ('mstatus_mie',{}, {0x300:0x1808},{},{}),
        ('prior_magic',{}, {},{0:0},{}),('prior_version',{}, {},{4:2},{}),
        ('prior_phase',{}, {},{8:10},{}),('prior_result',{}, {},{12:1},{}),
        ('prior_seed_count',{}, {},{112:31},{}),('prior_target_count',{}, {},{116:31},{}),
        ('fb_shadow',{}, {},{},{rv.VIDEO+8:1}),
        ('fb_commit',{}, {},{},{rv.VIDEO+12:1}),
        ('fb_active',{}, {},{},{rv.VIDEO+20:1}),
        ('gpu_identity',{}, {},{},{rv.GPU:0})]:
        cpu=ControlledReader(binary,'copied',overrides=overrides,**ctor)
        cpu.csr.update(csrs)
        for offset,value in prior.items():cpu.put(OLD+offset,value)
        cpu.original_old=[cpu.word(OLD+i*4) for i in range(128)]
        _,_,row=check(cpu,binary,'unobserved')
        cases.append(dict(name=name,**row))
    # A completed/rejected GPU may be present after the first firmware failed.
    cpu=ControlledReader(binary,'unchanged',overrides={rv.GPU+4:0,rv.GPU+8:2,rv.GPU+52:1})
    _,result,row=check(cpu,binary,'seed_unchanged')
    assert [result['header'][x] for x in ('done_before','done_after','status_before',
            'status_after','rejected_before','rejected_after')]==[2,2,0,0,1,1]
    cases.append(dict(name='completed_rejected_gpu',**row))
    cpu=TransitionReader(binary,'unchanged')
    _,result,row=check(cpu,binary,'seed_unchanged')
    assert [result['header'][x] for x in ('done_before','done_after','status_before',
            'status_after','rejected_before','rejected_after')]==[1,2,1,0,0,1]
    cases.append(dict(name='gpu_transitions_during_cpu_reads',**row))
    # A genuine old CLEAR image must not classify as a successful COPY.
    cpu=ControlledReader(binary,'unchanged')
    for i in range(8,16):cpu.put(SCRATCH+4*i,0x6b4d6b4d)
    _,_,row=check(cpu,binary,'other_or_partial_change')
    cases.append(dict(name='old_clear_image',**row))
    decoder_cases=[]
    for name,index,value in [('incomplete_count',29,31),('incomplete_phase',2,2),
                             ('wrong_errors',16,1),('first_bad',13,SCRATCH),
                             ('wrong_extent',28,SCRATCH+128),('reserved',31,1),
                             ('trap_recorded',10,5),('cache_metadata',5,1)]:
        data=bytearray(valid);struct.pack_into('<I',data,index*4,value)
        r=decode(data);assert not r['readback_valid'] and r['classification']=='unobserved'
        decoder_cases.append(name)
    for stage,reader in [('0'*64,READER_SHA256),(COPY_STAGE_SHA256,'0'*64)]:
        try:decode_bound(valid,stage_sha256=stage,reader_sha256=reader)
        except ValueError:decoder_cases.append('wrong_provenance')
        else:raise AssertionError('Provenance accepted')
    for data in [valid[:-1],valid+b'\x00',b'\x00'*256]:
        try:decode(data)
        except ValueError:decoder_cases.append('malformed_journal')
        else:raise AssertionError('Bad journal accepted')
    report={'passed':True,'hardware_access':False,'binary_sha256':READER_SHA256,
            'parent_binary_sha256':hashlib.sha256(old).hexdigest(),
            'changed_instruction_offsets':changed,'cases':cases,'decoder_cases':decoder_cases,
            'elapsed_seconds':time.monotonic()-started,
            'limits':'RV32 control-flow/footprint, not physical CPU/DDR timing or atomic snapshot'}
    (HERE/'tests_01.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'rv32_cases':len(cases),'decoder_cases':len(decoder_cases),
                      'changed_instruction_offsets':changed}))


if __name__=='__main__':main()
