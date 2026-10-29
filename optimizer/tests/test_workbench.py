"""Failure-oriented tests for timing interpretation and placement isolation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard import export
from openflow import validate_project
from placement import propose, propose_grouped, path_groups
from reports import attach_board_results, clock_routing, comparison, diagnose_path, fixed_constraints, inspect_build, parse_timing, rank_key
from runtime import save, sha


def timing(slack='0.250', count=0, tns='0.000'):
    # Small fixture in Gowin 1.9.12 text format; tests exercise global
    # summaries independently of the deliberately limited detailed paths.
    return f'''<Numbers of Setup Violated Endpoints>:{count}
<Numbers of Hold Violated Endpoints>:0
2.2 Clock Summary
 1 ddr3_sys_clk Base 13.333 75.002MHz 0.000 6.667
2.4 Total Negative Slack Summary
 ddr3_sys_clk setup {tns} {count}
 ddr3_sys_clk hold 0.000 0
3.2 Minimum Pulse Width Table
 1 1.500 2.500 1.000 High Pulse Width ddr3_sys_clk ram
3.3.1 Setup Analysis Report
Path Summary:
Slack             : {slack}
From              : u_gpu/source
To                : u_gpu/destination
Launch Clk        : ddr3_sys_clk:[R]
Latch Clk         : ddr3_sys_clk:[R]
Data Arrival Path:
 0.000 0.000 tCL RR 99 LEFTSIDE[4] clock
 3.000 3.000 tNET RR 1 R80C150[0][A] u_gpu/source/CLK
 3.300 0.300 tC2Q RR 518 R80C150[0][A] u_gpu/source/Q
 9.000 5.700 tNET RR 1 R85C151[0][B] u_gpu/lut/I0
 9.500 0.500 tINS RR 1 R85C151[0][B] u_gpu/lut/F
 10.000 0.500 tNET RR 1 R90C152[1][A] u_gpu/destination/D
Data Required Path:
 14.000 3.000 tNET RR 1 R90C152[1][A] u_gpu/destination/CLK
Arrival Data Path Delay: (cell: 0.500 7.143%,
 route: 6.200 88.571%,
 tC2Q: 0.300 4.286%)
3.3.2 Hold Analysis Report
Path Summary:
Slack : 0.100
From : source
To : destination
3.3.3 Recovery Analysis Report
Path Summary:
Slack : 0.200
From : source
To : destination
3.3.4 Removal Analysis Report
Path Summary:
Slack : 0.300
From : source
To : destination
3.4 Minimum Pulse Width Report
3.8 Timing Constraints Report
 TC_CLOCK Actived create_clock -name ddr3_sys_clk -period 13.333 [get_ports clk]
 TC_REPORT_TIMING Actived report_timing -setup -max_paths 1000
'''


class BoardEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.report = {'builds': [dict(name='same_name', status='TIMING_PASS', bitstream_sha256='a'*64),
                                  dict(name='untested', status='TIMING_PASS', bitstream_sha256='b'*64)]}

    def record(self, name, passed, digest='a'*64):
        path = self.root/name
        path.write_text(json.dumps(dict(passed=passed, bitstream_sha256=digest)))
        return path

    def test_timing_pass_does_not_hide_board_failure(self):
        attach_board_results(self.report, [self.record('failed.json', False)])
        a, b = self.report['builds']
        self.assertEqual(a['status'], 'TIMING_PASS')
        self.assertEqual(a['board_tests']['state'], 'TESTS_FAILED')
        self.assertEqual(b['board_tests']['state'], 'NOT_TESTED')
        self.assertEqual(len(a['board_tests']['records'][0]['sha256']), 64)

    def test_new_pass_does_not_erase_earlier_failure(self):
        attach_board_results(self.report, [self.record('failed.json', False), self.record('passed.json', True)])
        self.assertEqual(self.report['builds'][0]['board_tests']['state'], 'MIXED_RESULTS')

    def test_same_name_with_different_bitstream_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'matches no reported bitstream'):
            attach_board_results(self.report, [self.record('same_name.json', True, 'c'*64)])

    def test_missing_or_non_boolean_verdict_is_not_evidence(self):
        for verdict in (None, 1, 'false'):
            with self.assertRaises(ValueError):
                attach_board_results(self.report, [self.record('invalid.json', verdict)])


class TimingTests(unittest.TestCase):
    def test_actual_clock_routes_keep_duplicate_resources_and_long_names(self):
        report='''6. Global Clock Signals
  Signal | Global Clock | Location
  clk5x_raw | PRIMARY | PBR3
  clk5x_raw | HCLK | BANK3_HCLK1
  u/very_long_name/reset[1]| LW | -
7. Pinout by Port Name
  unrelated | LW | ignored
'''
        log="WARN  (CT1018) : local clock not available\nWARN  (PR1014) : generic clock route\nWARN  (OTHER) : unrelated\n"
        routing=clock_routing(report,log)
        self.assertEqual(len(routing['entries']),3)
        self.assertEqual(routing['lw_nets'],['u/very_long_name/reset[1]'])
        self.assertEqual([r['resource'] for r in routing['entries']],['PRIMARY','HCLK','LW'])
        self.assertEqual(len(routing['warnings']),2)

    def test_absent_clock_routing_stays_unknown(self):
        routing=clock_routing('incomplete report','')
        self.assertEqual(routing['entries'],[])
        self.assertEqual(routing['lw_nets'],[])

    def test_complete_clean(self):
        r = parse_timing(timing())
        self.assertTrue(r['complete'])
        self.assertTrue(r['timing_clean'])

    def test_summary_violation_even_if_detail_omits_it(self):
        r = parse_timing(timing(count=2, tns='-0.393'))
        self.assertFalse(r['timing_clean'])
        self.assertEqual(r['tns_ns'], -.393)

    def test_negative_hold(self):
        self.assertFalse(parse_timing(timing().replace('Slack : 0.100', 'Slack : -0.010'))['timing_clean'])

    def test_negative_pulse(self):
        self.assertFalse(parse_timing(timing().replace('1 1.500 2.500', '1 -0.001 2.500'))['timing_clean'])

    def test_inactive_constraint(self):
        self.assertFalse(parse_timing(timing().replace('TC_CLOCK Actived', 'TC_CLOCK Inactived'))['timing_clean'])

    def test_truncated_report_never_passes(self):
        for marker in ('2.2 Clock Summary', '3.3.2 Hold', '3.8 Timing Constraints'):
            self.assertFalse(parse_timing(timing().split(marker)[0])['timing_clean'])

    def test_missing_hold_group(self):
        self.assertFalse(parse_timing(timing().replace(' ddr3_sys_clk hold 0.000 0', ''))['complete'])

    def test_empty_reset_sections_never_count_as_coverage(self):
        text=timing()
        for slack in ('0.200','0.300'):
            text=text.replace('Path Summary:\nSlack : '+slack+'\nFrom : source\nTo : destination',
                              'Nothing to report!')
        result=parse_timing(text)
        self.assertFalse(result['complete'])
        self.assertFalse(result['timing_clean'])
        self.assertEqual(result['missing_analysis'],['recovery','removal'])

    def test_arcs_exclude_clock_and_keep_route_delay(self):
        r = parse_timing(timing(slack='-0.249', count=1, tns='-0.249'))
        path = r['paths'][0]
        self.assertEqual(len(path['arcs']), 4)
        self.assertEqual(path['arcs'][0]['fanout'], 518)
        self.assertEqual(path['arcs'][1]['delay_ns'], 5.7)
        self.assertEqual(path['arcs'][1]['row'], 85)
        self.assertEqual(path['route_ns'], 6.2)

    def test_incomplete_is_not_ranked_as_best(self):
        self.assertLess(rank_key({'status':'TIMING_FAIL', 'wns_ns':-10}), rank_key({'status':'INCOMPLETE'}))

    def test_diagnosis_includes_clock_to_q_but_not_clock_route(self):
        p=parse_timing(timing(slack='-0.249',count=1,tns='-0.249'))['paths'][0]
        d=p['diagnosis']
        self.assertEqual(d['total_ns'],7.0)
        self.assertEqual(d['route_ns'],6.2)
        self.assertEqual(d['clock_to_q_ns'],.3)
        self.assertEqual(d['logic_ns'],.5)
        self.assertEqual(d['route_percent'],88.6)
        self.assertEqual(d['max_fanout'],518)
        self.assertEqual(d['largest_wires'][0]['delay_ns'],5.7)
        self.assertIn('Forte charge',d['hypothesis'])

    def test_diagnosis_does_not_invent_missing_arcs(self):
        self.assertIsNone(diagnose_path(dict(arcs=[])))

    def test_crossing_diagnosis_requires_cdc_review(self):
        p=parse_timing(timing(slack='-0.249',count=1,tns='-0.249'))['paths'][0]
        p['clock']='other_clock'
        self.assertIn('synchroniseurs',diagnose_path(p)['hypothesis'])

    def test_disjoint_paths_keep_separate_regions_and_bridge_merges(self):
        first = parse_timing(timing('-0.249',1,'-0.249'))['paths'][0]
        second = deepcopy(first)
        for arc in second['arcs']:
            arc['cell'] = arc['cell'].replace('u_gpu/', 'u_other/')
        self.assertEqual(len(path_groups([first,second])),2)
        bridge = deepcopy(first)
        bridge['arcs'] = [first['arcs'][0],second['arcs'][-1]]
        groups = path_groups([first,second,bridge])
        self.assertEqual(len(groups),1)
        self.assertEqual(set(groups[0]['paths']),{0,1,2})
        self.assertEqual(len(groups[0]['cells']),6)

    def test_automatic_groups_refuse_crossings(self):
        p=parse_timing(timing('-0.249',1,'-0.249'))['paths'][0]
        p['clock']='other'
        with self.assertRaisesRegex(ValueError,'clock crossings'):
            path_groups([p])

    def test_inline_pin_constraint_is_never_hidden(self):
        self.assertEqual(fixed_constraints('INS_LOC "u" R1C1[0][A]; IO_LOC "clk" V22;'), ['IO_LOC "clk" V22'])
        self.assertNotEqual(fixed_constraints('IO_LOC "clk" V22;'),
                            fixed_constraints('INS_LOC "u" R1C1[0][A]; IO_LOC "clk" V23;'))

    def test_open_ranking_uses_worst_clock_ratio(self):
        a=dict(backend='nextpnr',status='COMPILED',fmax={'a':dict(achieved=120,constraint=100), 'b':dict(achieved=52,constraint=50)})
        b=dict(backend='nextpnr',status='COMPILED',fmax={'a':dict(achieved=115,constraint=100), 'b':dict(achieved=60,constraint=50)})
        self.assertLess(rank_key(b), rank_key(a))


class FrozenBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.build = Path(self.temp.name)/'build'
        (self.build/'impl/pnr').mkdir(parents=True)
        (self.build/'source').mkdir()
        self.cst = self.build/'source/pins.cst'
        self.cst.write_text('IO_LOC "clk" V22;\nIO_PORT "clk" IO_TYPE=LVCMOS33;\nINS_LOC "u_gpu/source" R80C150[0][A];\n')
        self.sdc = self.build/'source/timing.sdc'
        self.sdc.write_text('create_clock -name ddr3_sys_clk -period 13.333 [get_ports clk]\nreport_timing -setup -max_paths 1000\n')
        self.net = self.build/'net.vg'
        self.net.write_text('module top; endmodule\n')
        save(self.build/'sources.json', {'pins.cst':sha(self.cst), 'timing.sdc':sha(self.sdc)})
        self.report = self.build/'impl/pnr/top.tr'
        self.report.write_text(f'<Part Number>: GW5AST-LV138PG484AC1/I0\n<Tool Version>: V1.9.12\n'
                               f'<Design File>: {self.net}\n<Physical Constraints File>: {self.cst}\n'
                               f'<Timing Constraints File>: {self.sdc}\n' + timing('-0.249', 1, '-0.249'))
        self.bit = self.report.with_suffix('.fs')
        self.bit.write_text('compile-only fixture\n')
        (self.build/'build.log').write_text(f'Bitstream generation completed\nGenerate file "{self.report}" completed\n')

    def test_complete_failing_build(self):
        self.assertEqual(inspect_build(self.build)['status'], 'TIMING_FAIL')

    def test_missing_completion(self):
        (self.build/'build.log').write_text('Running routing......\n')
        self.assertEqual(inspect_build(self.build)['status'], 'INCOMPLETE')

    def test_routing_failure_overrides_stale_report(self):
        with (self.build/'build.log').open('a') as output:
            output.write('ERROR (PR0004) : 124 unrouted nets\n')
        self.assertEqual(inspect_build(self.build)['status'], 'BUILD_FAILED')

    def test_changed_source(self):
        with self.cst.open('a') as output:
            output.write('// altered\n')
        self.assertEqual(inspect_build(self.build)['status'], 'UNVERIFIED')

    def test_sdc_mismatch(self):
        self.report.write_text(self.report.read_text().replace('-period 13.333', '-period 20.000'))
        self.assertEqual(inspect_build(self.build)['status'], 'UNVERIFIED')

    def test_stale_qualification(self):
        save(self.build/'qualification.json', {'status':'PASS','timing_sha256':'wrong','bitstream_sha256':sha(self.bit)})
        self.assertEqual(inspect_build(self.build)['qualification'], 'STALE')

    def test_failed_routed_logic_audit_is_visible_and_hash_bound(self):
        routed=self.report.with_suffix('.vo');routed.write_text('post-route fixture')
        qualification=dict(status='PASS',timing_sha256=sha(self.report),bitstream_sha256=sha(self.bit),
            synthesis_audits=dict(gpu_owner_replication=dict(passed=False,
                errors=['CE polarity differs'],netlist_sha256=sha(routed))))
        save(self.build/'qualification.json',qualification)
        result=inspect_build(self.build)
        self.assertEqual(result['status'],'TIMING_FAIL')
        self.assertEqual(result['qualification'],'FAIL')
        self.assertEqual(result['qualification_issues'],['gpu_owner_replication: CE polarity differs'])
        routed.write_text('modified')
        result=inspect_build(self.build)
        self.assertEqual(result['qualification'],'STALE')
        self.assertEqual(result['qualification_issues'],[])

    def test_region_preserves_all_pins_and_existing_anchors(self):
        out = Path(self.temp.name)/'proposal.cst'
        before = self.cst.read_text()
        r = propose(self.build, self.cst, out, 'R[80:100]C[146:160]')
        self.assertEqual(set(r['cells']), {'u_gpu/lut', 'u_gpu/destination'})
        self.assertEqual(fixed_constraints(out.read_text()), fixed_constraints(before))
        self.assertIn('INS_LOC "u_gpu/source" R80C150[0][A];', out.read_text())
        self.assertEqual(self.cst.read_text(), before)

    def test_region_rejects_code_and_overwrite(self):
        out = Path(self.temp.name)/'proposal.cst'
        with self.assertRaises(ValueError):
            propose(self.build, self.cst, out, 'R[80:90]C[1:2]; exec evil')
        out.write_text('preserve')
        with self.assertRaises(FileExistsError):
            propose(self.build, self.cst, out, 'R[80:90]C[1:2]')
        self.assertEqual(out.read_text(), 'preserve')

    def test_routing_replicas_are_not_constrained_in_a_new_placement(self):
        name='u_gpu/gowin_replicate_reg_st_0[21]_2'
        self.report.write_text(self.report.read_text().replace('u_gpu/destination', name))
        for index, action in enumerate((
                lambda out: propose(self.build,self.cst,out,'R[80:100]C[146:160]'),
                lambda out: propose_grouped(self.build,self.cst,out))):
            out=Path(self.temp.name)/f'no_replica_{index}.cst'
            result=action(out)
            self.assertEqual(set(result['cells']), {'u_gpu/lut'})
            self.assertEqual(result['skipped_route_created_cells'], [name])
            self.assertNotIn('gowin_replicate_reg_', out.read_text())
            self.assertEqual(fixed_constraints(out.read_text()),fixed_constraints(self.cst.read_text()))

    def test_anchor_after_another_statement_is_preserved(self):
        self.cst.write_text(self.cst.read_text().replace('\nINS_LOC', ' INS_LOC')+
                            'IO_LOC "extra" A1; INS_LOC "u_gpu/lut" R85C151[0][B];\n')
        save(self.build/'sources.json',{'pins.cst':sha(self.cst),'timing.sdc':sha(self.sdc)})
        for index,action in enumerate((
                lambda out:propose(self.build,self.cst,out,'R[80:100]C[146:160]'),
                lambda out:propose_grouped(self.build,self.cst,out))):
            out=Path(self.temp.name)/f'inline_{index}.cst'
            result=action(out)
            self.assertEqual(set(result['cells']),{'u_gpu/destination'})
            self.assertIn('INS_LOC "u_gpu/lut" R85C151[0][B];',out.read_text())

    def test_grouped_proposal_keeps_distant_paths_local_and_anchors_intact(self):
        result=inspect_build(self.build)
        second=deepcopy(result['paths'][0])
        for arc in second['arcs']:
            arc['cell']=arc['cell'].replace('u_gpu/','u_other/')
            arc['row']-=60;arc['col']-=100
            arc['loc']=f"R{arc['row']}C{arc['col']}[0][A]"
        result['paths']=[result['paths'][0],second]
        out=Path(self.temp.name)/'groups.cst'
        with patch('placement.inspect_build',return_value=result):
            proposed=propose_grouped(self.build,self.cst,out,factor=1)
            with self.assertRaises(FileExistsError):
                propose_grouped(self.build,self.cst,out,factor=1)
        self.assertEqual(len(proposed['regions']),2)
        self.assertNotEqual(proposed['cells']['u_gpu/lut']['region'],proposed['cells']['u_other/lut']['region'])
        self.assertEqual(len(proposed['cells']),5)
        self.assertNotIn('u_gpu/source',proposed['cells'])
        self.assertIn('INS_LOC "u_gpu/source" R80C150[0][A];',out.read_text())
        self.assertEqual(fixed_constraints(out.read_text()),fixed_constraints(self.cst.read_text()))

    def test_html_escapes_report_content(self):
        r = comparison([self.build])
        r['builds'][0]['name'] = '</script><script>alert(1)</script>'
        out = Path(self.temp.name)/'report.html'
        export(r, out)
        self.assertNotIn('</script><script>alert(1)', out.read_text())
        self.assertIn('\\u003c/script>', out.read_text())


class OpenProjectTests(unittest.TestCase):
    def test_reject_nonfinite_clock_or_yosys_injection(self):
        good = dict(top='top',frequency_mhz=50,synth_family='gw5a',sources=['top.v'])
        for change in [dict(top='top; shell bad'), dict(frequency_mhz=float('nan')), dict(frequency_mhz=-1)]:
            with self.assertRaises(ValueError):
                validate_project(dict(good, **change))


if __name__ == '__main__':
    unittest.main()
