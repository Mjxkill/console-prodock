"""Frozen Neo reset profile isolation and observation-bit compatibility."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from neo.gpu_reset import split_resets, constrain_local, audit_reset_tree, queue_reset_local, register_shader_phase
from neo.gpu_debug import instrument
from neo.gpu_reset import control_local_constraints,audit_control_routing,local_geometry_payloads,audit_local_payloads
from neo.gpu_reset import prefetch_payload,stream_native_payload,audit_stream_payload,register_transform_check,audit_transform_check
from neo.gpu_reset import prefetch_bounds_ratio,audit_bounds_prefetch,prefetch_shader_inputs,audit_shader_inputs


class ResetProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        self.paths = ['tang/rtl/video/'+n+'.v' for n in
                      ('gpu_accel', 'gpu_geometry', 'gpu_v1', 'gpu_raster', 'blitter')]
        self.paths += ['tang/boards/neo/console_neo.v', 'tang/boards/neo/neo.cst']
        for rel in self.paths:
            target = self.source/rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT/rel, target)

    def test_profile_changes_only_copy_and_keeps_flag_positions(self):
        before = {p:(ROOT/p).read_bytes() for p in self.paths}
        split_resets(self.source)
        instrument(self.source)
        nets = constrain_local(self.source)
        self.assertEqual(nets, [f'gpu_debug_state[{i}]' for i in range(44, 56)])
        self.assertIn("8'd0,engine_resetn,mrst", (self.source/self.paths[0]).read_text())
        for rel, data in before.items():
            self.assertEqual((ROOT/rel).read_bytes(), data)
        with self.assertRaises(ValueError):constrain_local(self.source)

    def test_unknown_child_refused_without_partial_changes(self):
        p = self.source/'tang/rtl/video/gpu_v1.v'
        p.write_text(p.read_text().replace('gpu_copy565 u_copy(', 'gpu_copy565 changed('))
        before = {p:(self.source/p).read_bytes() for p in self.paths}
        with self.assertRaises(ValueError):split_resets(self.source)
        for rel, data in before.items():self.assertEqual((self.source/rel).read_bytes(), data)

    def test_no_constraints_without_observation(self):
        split_resets(self.source)
        with self.assertRaises(ValueError):constrain_local(self.source)

    def test_shader_phase_profile_is_isolated_and_rejects_source_drift(self):
        original=(ROOT/'tang/rtl/video/gpu_geometry.v').read_bytes()
        register_shader_phase(self.source)
        self.assertEqual((ROOT/'tang/rtl/video/gpu_geometry.v').read_bytes(),original)
        changed=(self.source/'tang/rtl/video/gpu_geometry.v').read_bytes()
        with self.assertRaises(ValueError):register_shader_phase(self.source)
        self.assertEqual((self.source/'tang/rtl/video/gpu_geometry.v').read_bytes(),changed)

    def test_shader_phase_missing_decode_fails_without_partial_edit(self):
        path=self.source/'tang/rtl/video/gpu_geometry.v'
        path.write_text(path.read_text().replace('rd_valid&&(state[PASS]', 'rd_valid&&(state[OTHER]'))
        before=path.read_bytes()
        with self.assertRaises(ValueError):register_shader_phase(self.source)
        self.assertEqual(path.read_bytes(),before)
        self.assertFalse((self.source/'tang/boards/neo/gpu_shader_phase.json').exists())

    def test_local_payloads_isolated_and_fail_closed(self):
        before={p:(ROOT/p).read_bytes() for p in self.paths}
        local_geometry_payloads(self.source)
        changed={p:(self.source/p).read_bytes() for p in self.paths}
        for path,data in before.items():self.assertEqual((ROOT/path).read_bytes(),data)
        with self.assertRaises(ValueError):local_geometry_payloads(self.source)
        for path,data in changed.items():self.assertEqual((self.source/path).read_bytes(),data)

    def test_local_payloads_reject_partial_pixel_change_atomically(self):
        pixels=self.source/'tang/rtl/video/gpu_v1.v'
        pixels.write_text(pixels.read_text().replace('color_buf<=0;z_buf<=0;', 'color_buf<=1;z_buf<=0;',1))
        before={p:(self.source/p).read_bytes() for p in self.paths}
        with self.assertRaises(ValueError):local_geometry_payloads(self.source)
        for path,data in before.items():self.assertEqual((self.source/path).read_bytes(),data)
        self.assertFalse((self.source/'tang/boards/neo/gpu_local_payloads.json').exists())

    def test_stream_payload_is_isolated_and_rejects_unknown_source(self):
        path=self.source/'tang/rtl/video/gpu_accel.v'
        before=path.read_bytes()
        with self.assertRaises(ValueError):stream_native_payload(self.source)
        self.assertEqual(path.read_bytes(),before)
        prefetch_payload(self.source)
        stream_native_payload(self.source)
        changed=path.read_bytes()
        with self.assertRaises(ValueError):stream_native_payload(self.source)
        self.assertEqual(path.read_bytes(),changed)
        self.assertEqual((ROOT/'tang/rtl/video/gpu_accel.v').read_bytes(),before)

    def test_transform_check_isolated_and_fails_before_partial_edit(self):
        path=self.source/'tang/rtl/video/gpu_geometry.v';before=path.read_bytes()
        register_transform_check(self.source);changed=path.read_bytes()
        self.assertEqual((ROOT/'tang/rtl/video/gpu_geometry.v').read_bytes(),before)
        with self.assertRaises(ValueError):register_transform_check(self.source)
        self.assertEqual(path.read_bytes(),changed)
        path.write_bytes(before.replace(b'if(sum64>2147483647',b'if(sum64>2147483646'))
        drift=path.read_bytes()
        with self.assertRaises(ValueError):register_transform_check(self.source)
        self.assertEqual(path.read_bytes(),drift)

    def test_transform_check_mapping_requires_fabric_register_and_clock(self):
        path=self.source/'transform.v';good='module gpu_geometry ();\nDFFRE transform_overflow_s0 (.Q(q),.D(d),.CLK(gpu_clk),.RESET(GND),.CE(e));\nendmodule\n'
        path.write_text(good);self.assertTrue(audit_transform_check(path)['passed'])
        for bad in (good.replace('gpu_clk','wrong_clk'),good.replace('DFFRE','MULT27X36'),good.replace('RESET(GND)','RESET(reset)')):
            path.write_text(bad);self.assertFalse(audit_transform_check(path)['passed'])

    def test_bounds_prefetch_isolated_and_rejects_drift(self):
        path=self.source/'tang/rtl/video/gpu_geometry.v';before=path.read_bytes()
        prefetch_bounds_ratio(self.source);changed=path.read_bytes()
        self.assertEqual((ROOT/'tang/rtl/video/gpu_geometry.v').read_bytes(),before)
        with self.assertRaises(ValueError):prefetch_bounds_ratio(self.source)
        self.assertEqual(path.read_bytes(),changed)
        path.write_bytes(before.replace(b'bounds_y ? ratio[3]',b'bounds_y ? ratio[2]'))
        bad=path.read_bytes()
        with self.assertRaises(ValueError):prefetch_bounds_ratio(self.source)
        self.assertEqual(path.read_bytes(),bad)

    def test_bounds_prefetch_mapping_rejects_lost_or_gated_register(self):
        path=self.source/'bounds.v'
        good='module gpu_geometry ();\n'+''.join(
            f'DFFCE bounds_ratio{v}_{i}_s0 (.Q(q_{v}_{i}),.D(d_{v}_{i}),.CLK(gpu_clk),.CLEAR(GND),.CE(VCC));\n'
            for v in (0,1) for i in range(32))+'endmodule\n'
        path.write_text(good);self.assertTrue(audit_bounds_prefetch(path)['passed'])
        for bad in (good.replace('gpu_clk','wrong_clk',1),good.replace('CE(VCC)','CE(state)',1),
                    good.replace('bounds_ratio0_0_s0','missing_register',1)):
            path.write_text(bad);self.assertFalse(audit_bounds_prefetch(path)['passed'])

    def test_shader_inputs_isolated_and_atomic(self):
        path=self.source/'tang/rtl/video/gpu_v1.v';before=path.read_bytes()
        prefetch_shader_inputs(self.source);changed=path.read_bytes()
        self.assertEqual((ROOT/'tang/rtl/video/gpu_v1.v').read_bytes(),before)
        with self.assertRaises(ValueError):prefetch_shader_inputs(self.source)
        self.assertEqual(path.read_bytes(),changed)
        path.write_bytes(before.replace(b'alpha_product[16:8]==0 ? PIX_NEXT',b'alpha_product[16:8]==1 ? PIX_NEXT'))
        drift=path.read_bytes()
        with self.assertRaises(ValueError):prefetch_shader_inputs(self.source)
        self.assertEqual(path.read_bytes(),drift)

    def test_shader_mapping_rejects_wrong_pipeline_or_enable(self):
        path=self.source/'shader.v'
        registers=''.join(f'DFFCE tex_{axis}_{i}_s0 (.Q(tex_{axis}[{i}]),.D(addressed_{axis}[{i}]),.CLK(gpu_clk),.CE(VCC),.CLEAR(GND));\n'
                          for axis in ('u','v') for i in range(9))
        params={'MULT_RESET_MODE':'SYNC','OREG_CLK':'CLK0','OREG_CE':'CE0','OREG_RESET':'RESET0',
                'AREG_CLK':'BYPASS','BREG_CLK':'BYPASS','PREG_CLK':'BYPASS'}
        good='module gpu_v1 ();\n'+registers+'MULT12X12 product (.DOUT(alpha_product[16:7]),.CLK({GND,gpu_clk}),.CE({VCC,state[21]}));\n'
        good+=''.join(f'defparam product.{k}="{v}";\n' for k,v in params.items())+'endmodule\n'
        path.write_text(good);self.assertTrue(audit_shader_inputs(path)['passed'])
        for old,new in [('OREG_CLK="CLK0"','OREG_CLK="BYPASS"'),('state[21]','state[22]'),
                        ('CE(VCC)','CE(valid)'),('tex_u_0_s0','missing_coordinate')]:
            path.write_text(good.replace(old,new,1));self.assertFalse(audit_shader_inputs(path)['passed'])

    def test_mapping_audit_rejects_wrong_clock_and_global_reset(self):
        net = self.source/'mapped.v'
        good = 'module gpu_accel ();\n'+''.join(
            f'DFFCE engine_resetn_{i}_s0 (.Q(gpu_debug_state_{44+i}),.D(gpu_debug_state_42),'
            '.CLK(gpu_clk),.CE(VCC),.CLEAR(common_clear));\n' for i in range(12))+'endmodule\n'
        rpt = self.source/'resource.rpt'
        rpt.write_text('6. Global Clock Signals\n clk | PRIMARY | BUFG[0]\n7. IO\n')
        net.write_text(good)
        self.assertTrue(audit_reset_tree(net, rpt)['passed'])
        net.write_text(good.replace('.CLK(gpu_clk)', '.CLK(other_clk)', 1))
        self.assertFalse(audit_reset_tree(net, rpt)['passed'])
        net.write_text(good)
        rpt.write_text('6. Global Clock Signals\n gpu_debug_state[51] | LW | TLW1\n7. IO\n')
        self.assertFalse(audit_reset_tree(net, rpt)['passed'])
        gao='7. Global Clock Signals\n gpu_debug_state[48] | LW | -\n8. IO\n'
        rpt.write_text(gao)
        self.assertEqual(audit_reset_tree(net,rpt)['errors'],
                         ['Reset 4 still uses a global routing resource'])
        for bad in ('',gao.replace('8. IO',''),gao.replace(' | LW | -',' | LW'),
                    gao+gao,gao.replace('gpu_debug_state[48] | LW | -','')):
            rpt.write_text(bad)
            self.assertFalse(audit_reset_tree(net,rpt)['passed'])

    def test_queue_reset_constraint_is_narrow_and_refuses_unknown_driver(self):
        net = 'module gpu_accel ();\nDFFCE mrst_1_s0 (.Q(gpu_debug_state_43),.D(gpu_debug_state_42),.CLK(gpu_clk),.CLEAR(n1205_6),.CE(VCC));\nendmodule\n'
        cst='CLOCK_LOC "gpu_clk" BUFG[5] = CLK;\n'
        changed,nets=queue_reset_local(cst,net)
        self.assertTrue(changed.startswith(cst))
        self.assertEqual(nets,['gpu_debug_state[43]'])
        with self.assertRaises(ValueError):queue_reset_local(changed,net)
        with self.assertRaises(ValueError):queue_reset_local(cst,net.replace('.D(gpu_debug_state_42)','.D(VCC)'))

    def test_control_routing_checks_functions_and_rejects_lw(self):
        net='''module gpu_geometry ();
LUT2 n60343_s0 (.F(n60343_3),.I0(gpu_debug_state_46),.I1(state[61]));
defparam n60343_s0.INIT=4'h8;
endmodule
module gpu_v1 ();
LUT2 n34374_s1 (.F(n34374_4),.I0(state[13]),.I1(gpu_debug_state_48));
defparam n34374_s1.INIT=4'hB;
LUT2 n38025_s0 (.F(n38025_3),.I0(shader_start),.I1(state[0]));
defparam n38025_s0.INIT=4'h8;
endmodule
module gpu_scanout ();
DFFCE mrst_1_s0 (.Q(mrst[1]),.D(mrst[0]),.CLK(gpu_clk),.CLEAR(n3390_6),.CE(VCC));
endmodule
'''
        cst,nets=control_local_constraints('original\n',net)
        self.assertTrue(cst.startswith('original\n'))
        self.assertEqual(len(nets),4)
        with self.assertRaises(ValueError):control_local_constraints(cst,net)
        with self.assertRaises(ValueError):control_local_constraints('',net.replace("4'hB","4'h8"))
        with self.assertRaises(ValueError):control_local_constraints('',net.replace('.I1(state[61])','.I1(state[60])'))
        report=self.source/'control.rpt'
        report.write_text(f'6. Global Clock Signals\n {nets[0]} | LW | -\n7. IO\n')
        self.assertFalse(audit_control_routing(report,nets)['passed'])
        report.write_text(f'6. Global Clock Signals\n {nets[0]} | PRIMARY | PTR1\n7. IO\n')
        actual=audit_control_routing(report,nets)
        self.assertTrue(actual['passed'])
        self.assertEqual(actual['global_routes'][nets[0]],'PRIMARY')
        self.assertFalse(audit_control_routing(report,nets,primary=True)['passed'])
        primary_cst,primary_nets=control_local_constraints('',net,primary=True)
        self.assertEqual(primary_nets,nets)
        self.assertEqual(primary_cst.count('BUFG = CE|SR|LOGIC;'),4)
        report.write_text('6. Global Clock Signals\n'+''.join(f'{n} | PRIMARY | PTR1\n' for n in nets)+'7. IO\n')
        self.assertTrue(audit_control_routing(report,nets,primary=True)['passed'])
        gao=report.read_text().replace('6. Global','7. Global').replace('7. IO','8. IO')
        report.write_text(gao)
        self.assertTrue(audit_control_routing(report,nets,primary=True)['passed'])
        for bad in ('',gao.replace('8. IO',''),gao.replace('| PRIMARY | PTR1','| PRIMARY',1),
                    gao+gao,gao.replace('| PRIMARY | PTR1','| UNKNOWN | PTR1',1)):
            report.write_text(bad)
            self.assertFalse(audit_control_routing(report,nets)['passed'])
            self.assertFalse(audit_control_routing(report,nets,primary=True)['passed'])
        # Multiple resource kinds must not hide a forbidden LW assignment.
        report.write_text(gao.replace('8. IO',f'{nets[0]} | LW | -\n8. IO'))
        self.assertFalse(audit_control_routing(report,nets)['passed'])
        self.assertFalse(audit_control_routing(report,nets,primary=True)['passed'])

    def test_payload_mapping_rejects_wide_controls_and_mask_lw(self):
        geometry='module gpu_geometry ();\n'
        for name,width in [('edge_a',160),('edge_b',160),('clip_side0',33),('clip_side1',33)]:
            geometry+=''.join(f'DFFCE {name}_{i}_s0 (.Q(q),.D(d),.CLK(gpu_clk),.CLEAR(GND),.CE(VCC));\n' for i in range(width))
        geometry+='endmodule\nmodule gpu_v1 ();\n'
        for name in ('color_buf','z_buf'):
            geometry+=''.join(f'DFFRE {name}_{i}_s0 (.Q(q),.D(d),.CLK(gpu_clk),.RESET(GND),.CE(enable_{i//16}));\n' for i in range(256))
        geometry+=''.join(f'DFFSE pixel_mask_{i}_s0 (.Q(q),.D(d),.CLK(gpu_clk),.SET(mask_reset),.CE(e));\n' for i in range(16))
        geometry+='DFFRE chunk_dirty_s0 (.Q(q),.D(d),.CLK(gpu_clk),.RESET(mask_reset),.CE(e));\nendmodule\n'
        net=self.source/'payload.v';rpt=self.source/'payload.rpt'
        net.write_text(geometry);rpt.write_text('6. Global Clock Signals\n clk | PRIMARY | PTR0\n7. IO\n')
        self.assertTrue(audit_local_payloads(net,rpt)['passed'])
        for bad in (geometry.replace('.CE(VCC)','.CE(wide_enable)',1),
                    geometry.replace('.RESET(GND)','.RESET(wide_reset)',1),
                    geometry.replace('DFFCE edge_a_0_s0','DFFCE missing_0_s0',1)):
            net.write_text(bad);self.assertFalse(audit_local_payloads(net,rpt)['passed'])
        net.write_text(geometry)
        rpt.write_text('6. Global Clock Signals\n u_accel/u_v1/u_pixels/mask_reset | LW | -\n7. IO\n')
        self.assertFalse(audit_local_payloads(net,rpt)['passed'])

    def test_stream_mapping_rejects_pending_enable_and_lw(self):
        net=self.source/'stream.v';rpt=self.source/'stream.rpt'
        good='module gpu_accel ();\n'+''.join(
            f'DFFCE {name}_{i}_s0 (.Q(q),.D(d),.CLK(gpu_clk),.CLEAR(GND),.CE(VCC));\n'
            for name,width in [('v1_tx_addr',28),('v1_tx_data',256),('v1_tx_mask',32),('v1_tx_write',1)]
            for i in range(width))+'endmodule\n'
        net.write_text(good);rpt.write_text('6. Global Clock Signals\n clk | PRIMARY | PTR0\n7. IO\n')
        self.assertTrue(audit_stream_payload(net,rpt)['passed'])
        net.write_text(good.replace('.CE(VCC)','.CE(v1_pending)',1))
        self.assertFalse(audit_stream_payload(net,rpt)['passed'])
        net.write_text(good)
        rpt.write_text('6. Global Clock Signals\n v1_pending | LW | -\n7. IO\n')
        self.assertFalse(audit_stream_payload(net,rpt)['passed'])


if __name__ == '__main__':unittest.main()
