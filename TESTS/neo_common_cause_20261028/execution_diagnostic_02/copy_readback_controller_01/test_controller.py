#!/usr/bin/env python3
"""Exercise real Tcl generation/guards and decoder binding with no hardware.

Tcl memory, PC and loader commands are inert stubs. Production paths perform
prepare-only; hardware interfaces are never invoked by this test program.
"""
import contextlib
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import re
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
CONTROL=HERE.parents[1]/'root_microdma_01.py'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


ctl=module('copy_controller',CONTROL)
old=module('previous_controller',HERE/'controller_before.py')
old.HERE=ctl.HERE;old.ROOT=ctl.ROOT
parser=argparse.ArgumentParser()
parser.add_argument('--out-name',default='tests_02')
args=parser.parse_args()
assert re.fullmatch(r'[a-zA-Z0-9_-]+',args.out_name)
OUT=HERE/args.out_name
OUT.mkdir(exist_ok=False)


def prepare(mod,name,revision,readback=False,capture=False):
    path=OUT/name
    args=['controller','--out',str(path),'--firmware-revision',str(revision)]
    if readback:args.append('--cpu-readback')
    if capture:args.append('--capture-gpu')
    with patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):
        mod.main()
    return path


def tcl_case(name,prior=None,pc_before='0x80000000',pc_after='0x80000004',
             cleared=0,short_zero=False,short_prior=False,fail_verify=False):
    words=[0]*30
    for index,value in {0:0x4d443132,1:1,2:8,3:0xfffffffb,28:32,29:32}.items():words[index]=value
    for index,value in (prior or {}).items():words[index]=value
    if short_prior:words.pop()
    zeros=[0]*(63 if short_zero else 64);zeros[0]=cleared
    script=f'''
set oldjournal {{{' '.join(map(str,words))}}}
set clearedjournal {{{' '.join(map(str,zeros))}}}
set pcs {{{pc_before} {pc_after} {pc_after}}}
set pcindex 0
proc read_memory {{address bits count}} {{
    global oldjournal clearedjournal
    puts "READ $address $bits $count"
    if {{$address == 0xa0006000}} {{return $oldjournal}}
    if {{$address == 0xa0006400}} {{return $clearedjournal}}
    error "Forbidden memory read $address"
}}
proc reg {{name}} {{global pcs pcindex; set v [lindex $pcs $pcindex];incr pcindex; return [list pc 32 $v]}}
proc mww {{address value count}} {{
    if {{$address != 0xa0006400 || $value != 0 || $count != 64}} {{error "Forbidden write"}}
    puts "ZERO $address $value $count"
}}
proc load_image {{path address kind}} {{
    if {{$address != 0xa0005000 || $kind ne "bin"}} {{error "Wrong code write"}}
    puts LOADED
}}
proc verify_image {{args}} {{{'error "Injected verify failure"' if fail_verify else 'puts VERIFIED'}}}
proc resume {{address}} {{if {{$address != 0xa0005000}} {{error "Wrong resume"}};puts RESUMED}}
proc sleep {{args}} {{}}
proc halt {{args}} {{}}
proc dump_image {{path address count}} {{
    if {{$address != 0xa0006400 || $count != 256}} {{error "Wrong dump"}}
    puts DUMPED
}}
proc microdma_capture_r19 {{label}} {{puts "SNAP $label"}}
proc echo {{args}} {{puts [join $args]}}
set status [catch {{
{ctl.readback_stage(Path('/fixture/readback.bin'),Path('/fixture/out'))}
}} message]
puts "CAUGHT $status $message"
'''
    (OUT/(name+'.tcl')).write_text(script)
    result=subprocess.run(['/usr/bin/tclsh'],input=script,text=True,capture_output=True,timeout=3)
    (OUT/(name+'.log')).write_text(result.stdout+result.stderr)
    assert result.returncode==0 and not result.stderr,(result.stdout,result.stderr)
    return result.stdout


class Preparation(unittest.TestCase):
    def test_legacy_nonreader_tcl_byte_identical(self):
        for revision in (1,2,3,4):
            before=prepare(old,f'old_{revision}',revision,capture=True)
            after=prepare(ctl,f'new_{revision}',revision,capture=True)
            a=(before/'prepared.tcl').read_text().replace(str(before),str(after))
            self.assertEqual(a,(after/'prepared.tcl').read_text())

    def test_both_reader_profiles_and_guards(self):
        for revision in (2,4):
            out=prepare(ctl,f'reader_{revision}',revision,True,True)
            code=(out/'prepared.tcl').read_text()
            self.assertIn('mww 0xa0006400 0 64',code)
            self.assertIn(ctl.READBACK_PROFILES[revision][0]+'/build_01/readback.bin',code)
            self.assertEqual(code.count('resume 0xa0005000'),1)
            report=json.loads((out/'result.json').read_text())
            self.assertFalse(report['hardware']);self.assertFalse(report['diagnostic_passed'])
            self.assertEqual(report['readback_sha256'],ctl.READBACK_PROFILES[revision][1])

    def test_disallowed_reader_modes(self):
        for revision,capture in ((1,True),(3,True),(2,False),(4,False)):
            with self.assertRaises(AssertionError):
                prepare(ctl,f'deny_{revision}_{capture}',revision,True,capture)


class TclGuards(unittest.TestCase):
    def test_valid_sequence(self):
        text=tcl_case('valid')
        self.assertIn('CAUGHT 0',text)
        steps=['ZERO 0xa0006400 0 64','READBACK_ZERO_VERIFIED','LOADED','VERIFIED','READBACK_START',
               'RESUMED','DUMPED','READBACK_RETURN_VERIFIED','SNAP READBACK_AFTER',
               'SNAP READBACK_AFTER100','READBACK_COLLECTED']
        lines=text.splitlines()
        self.assertEqual([lines.index(s) for s in steps],sorted(lines.index(s) for s in steps))

    def test_prior_guards_before_any_clear(self):
        for index,value in ((0,0),(1,2),(2,10),(3,1),(28,31),(29,31)):
            text=tcl_case('prior_'+str(index),prior={index:value})
            self.assertIn('CAUGHT 1',text);self.assertNotIn('ZERO ',text)
        text=tcl_case('prior_short',short_prior=True)
        self.assertIn('CAUGHT 1',text);self.assertNotIn('ZERO ',text)

    def test_clear_and_pc_refusals(self):
        for name,kwargs in [('bad_pre_pc',{'pc_before':'0xa0004000'}),
                            ('dirty_clear',{'cleared':1}),('short_clear',{'short_zero':True}),
                            ('verify_fail',{'fail_verify':True})]:
            text=tcl_case(name,**kwargs)
            self.assertIn('CAUGHT 1',text);self.assertNotIn('RESUMED',text)
        text=tcl_case('bad_return',pc_after='0xa0005190')
        self.assertIn('DUMPED',text);self.assertIn('CAUGHT 1',text)
        self.assertNotIn('READBACK_RETURN_VERIFIED',text)
        self.assertNotIn('READBACK_COLLECTED',text)


class DecoderBinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=ctl.HERE/'execution_diagnostic_02/copy_readback_r1'
        sys.path.insert(0,str(cls.path))
        reader=module('reader_controller_check',cls.path/'readback_model.py')
        cpu=reader.Reader((cls.path/'build_01/readback.bin').read_bytes(),'unchanged')
        cls.raw=struct.pack('<64I',*cpu.run()[:64])
        cls.markers=['READBACK_ZERO_VERIFIED','READBACK_START','READBACK_RETURN_VERIFIED',
                     'READBACK_COLLECTED']

    def decode(self,markers,sha=None):
        return ctl.decode_readback(self.raw,'\n'.join(markers)+'\n',4,
             sha or ctl.FIRMWARE_PROFILES[4][1],self.path)

    def test_current_valid_and_never_gpu_pass(self):
        result=self.decode(self.markers)
        self.assertTrue(result['readback_valid']);self.assertFalse(result['gpu_passed'])
        self.assertEqual(result['classification'],'seed_unchanged')

    def test_missing_duplicate_reordered_markers(self):
        cases=[self.markers[:i]+self.markers[i+1:] for i in range(4)]
        cases += [list(reversed(self.markers)),self.markers+self.markers,self.markers+['READBACK_START']]
        for markers in cases:
            result=self.decode(markers)
            self.assertFalse(result['readback_valid']);self.assertEqual(result['classification'],'unobserved')

    def test_wrong_parent_rejected(self):
        with self.assertRaises(ValueError):self.decode(self.markers,'0'*64)


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    record={'passed':result.wasSuccessful(),'tests':result.testsRun,'hardware_access':False,
            'controller_sha256':hashlib.sha256(CONTROL.read_bytes()).hexdigest(),
            'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'prepare-only actual CLI, real Tcl guards with inert memory/PC stubs, freshness decoder'}
    (OUT/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
