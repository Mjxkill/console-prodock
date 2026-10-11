#!/usr/bin/env python3
"""World anchoring, camera continuity and trajectory headings in the real scene."""
import ctypes
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from render_astrilla import Camera, Scene


class Landing(ctypes.Structure):
    _fields_ = [(k, ctypes.c_float) for k in ('x', 'y', 'size', 'gx', 'gy', 'scale', 'altitude')]


class Motion(ctypes.Structure):
    _fields_ = [(k, ctypes.c_float) for k in ('x', 'y', 'dx', 'dy')]


class CinematicMotion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scene = Scene()
        cls.scene.lib.heading.argtypes = [ctypes.c_float, ctypes.c_float]
        cls.scene.lib.heading.restype = ctypes.c_float
        cls.scene.lib.flagship.argtypes = [ctypes.c_float, ctypes.POINTER(Motion)]
        cls.scene.lib.dogfight.argtypes = [ctypes.c_float, ctypes.c_uint, ctypes.POINTER(Motion)]
        cls.scene.lib.pursuit.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.POINTER(Motion)]
        cls.scene.lib.mesh_probe.argtypes = [ctypes.c_float]*3

    def camera(self, t):
        camera = Camera()
        self.scene.lib.camera(t, ctypes.byref(camera))
        return camera

    def landing(self, t):
        pose = Landing()
        self.scene.lib.landing(t, ctypes.byref(pose))
        return pose

    def test_heading_follows_velocity_in_every_quadrant(self):
        for i in range(1440):
            angle = i * math.tau / 1440
            x, y = math.cos(angle), math.sin(angle)
            heading = self.scene.lib.heading(x, y) * math.tau / 256
            # The visible nose must point forward, never toward a side or tail.
            error = math.atan2(math.sin(heading-angle), math.cos(heading-angle))
            self.assertLess(abs(error), math.radians(.3), i)

    def test_capital_has_continuous_forward_motion(self):
        previous = None
        for t in range(1650):
            pose = Motion()
            self.scene.lib.flagship(t/55, ctypes.byref(pose))
            if previous:
                self.assertLess(pose.x, previous.x)
                self.assertAlmostEqual((pose.x-previous.x)*55, pose.dx, delta=.003)
                self.assertAlmostEqual((pose.y-previous.y)*55, pose.dy, delta=.08)
            previous = pose

    def test_landing_and_zoom_share_world_anchor(self):
        for t in range(15290, 16500):  # touchdown at 278 s, through final zoom
            c, p = self.camera(t), self.landing(t)
            self.assertEqual(p.altitude, 0)
            wx = (c.u+c.ux*p.gx+c.uy*p.gy)/65536
            wy = (c.v+c.vx*p.gx+c.vy*p.gy)/65536
            self.assertAlmostEqual(wx, 440, delta=.0001)
            self.assertAlmostEqual(wy, 270, delta=.0001)
            self.assertAlmostEqual(p.size*c.ux/65536, 64, delta=.0001)
            self.assertAlmostEqual(p.y+p.size*.18, p.gy, delta=.0001)

    def test_no_cut_between_touchdown_and_final_dolly(self):
        self.assertEqual(bytes(self.camera(15674))[:44], bytes(self.camera(15675))[:44])
        self.assertEqual(bytes(self.landing(15674)), bytes(self.landing(15675)))
        previous = self.landing(15675)
        for t in range(15676, 15950):
            pose = self.landing(t)
            self.assertGreaterEqual(pose.size, previous.size)
            self.assertLess(abs(pose.x-previous.x), .6)
            self.assertLess(abs(pose.y-previous.y), .6)
            previous = pose
        for t in range(15950, 16500):
            self.assertEqual(bytes(self.landing(t)), bytes(previous))

    def test_black_hole_is_non_affine_monotonic_and_never_banks(self):
        previous = 0
        for t in range(3850, 4510):
            c = self.camera(t)
            self.assertGreaterEqual(c.lens, previous)
            self.assertEqual(c.vx, 0)
            self.assertEqual(c.uy, 0)
            self.assertEqual(c.roll, 0)
            self.assertEqual(c.ux, c.vy)
            previous = c.lens
        # The field collapses completely before the interior is revealed.
        self.assertEqual(self.scene.background(4509, check=True), self.scene.background(4619, check=True))
        self.assertLess(self.camera(4510).lens, 0)

    def test_terrestrial_story_never_returns_to_space(self):
        assets = self.scene.manifest['regions']
        allowed = {assets[n]['address'] for n in ('valley', 'canyon', 'forest', 'clearing')}
        for t in range(8800, 16500):
            self.assertIn(self.camera(t).base, allowed)

    def test_enemy_is_destroyed_and_does_not_respawn(self):
        def bound(t):
            self.scene.commands(t)
            return self.scene.lib.enemy_triangles() > 0
        for t in (9340, 10800, 12700, 13474):
            self.assertTrue(bound(t), t)
        for t in (13475, 13480, 13640, 13750, 14200, 15000, 16000):
            self.assertFalse(bound(t), t)

    def test_dogfights_have_speed_and_large_heading_changes(self):
        for ship in range(7):
            speeds, headings = [], []
            for step in range(1,100):
                m=Motion();self.scene.lib.dogfight(step*.02,ship,ctypes.byref(m))
                if 0<m.x<400 and 0<m.y<240:
                    speeds.append(math.hypot(m.dx,m.dy))
                    headings.append(math.atan2(m.dy,m.dx))
            self.assertTrue(speeds)
            self.assertGreater(max(speeds),200,ship)
            changes=[abs(math.atan2(math.sin(a-b),math.cos(a-b))) for a in headings for b in headings]
            self.assertGreater(max(changes),math.radians(45),ship)

    def test_ship_meshes_use_depth_and_perspective_in_three_axes(self):
        words=[]
        for yaw,pitch,bank in [(0,0,0),(30,0,0),(0,30,0),(0,0,40),(95,-20,-35)]:
            self.assertTrue(self.scene.lib.mesh_probe(yaw,pitch,bank))
            n=self.scene.lib.command_count();p=self.scene.lib.command_words()
            commands=[tuple(p[i*8+j] for j in range(8)) for i in range(n)]
            materials=[q[1] for q in commands if q[0]>>24==25]
            self.assertTrue(materials)
            self.assertTrue(all(flags&23==23 for flags in materials))
            self.assertGreater(sum(q[0]>>24==27 for q in commands),15)
            words.append(tuple(commands))
        self.assertEqual(len(set(words)),5)

    def test_other_world_reveals_before_horizon_crossing(self):
        previous = 0
        for t in range(3850, 4510):
            portal = self.camera(t).portal
            self.assertGreaterEqual(portal, previous)
            previous = portal
        self.assertGreater(self.camera(4300).portal, 0)
        self.assertGreaterEqual(self.camera(4509).portal, 240*16)
        self.assertEqual(self.scene.background(4509), self.scene.background(4619))

    def test_opening_uses_nine_distinct_camera_setups(self):
        transforms = set()
        for shot in range(9):
            c = self.camera(shot*220+100)
            transforms.add((c.ux, c.vx, c.uy, c.vy))
        self.assertEqual(len(transforms), 9)

    def test_descent_has_no_vertical_bobbing(self):
        previous = self.landing(14300)
        for t in range(14301, 15675):
            pose = self.landing(t)
            self.assertLessEqual(pose.altitude, previous.altitude)
            previous = pose
        self.assertEqual(previous.altitude, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
