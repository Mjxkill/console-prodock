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


class Flight(ctypes.Structure):
    _fields_ = [(k, ctypes.c_float) for k in ('x', 'y', 'dx', 'dy', 'size', 'heading', 'pitch', 'bank')]


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
        cls.scene.lib.flight_probe.argtypes = [ctypes.c_float, ctypes.c_uint, ctypes.POINTER(Flight)]
        cls.scene.lib.pursuit_probe.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.POINTER(Flight)]
        cls.scene.lib.basis_probe.argtypes = [ctypes.c_float]*3+[ctypes.POINTER(ctypes.c_float)]
        cls.scene.lib.straight_bank.argtypes = [ctypes.c_float]
        cls.scene.lib.straight_bank.restype = ctypes.c_float

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

    def basis(self, heading, pitch, bank):
        basis = (ctypes.c_float*9)()
        self.scene.lib.basis_probe(heading, pitch, bank, basis)
        return [tuple(basis[i:i+3]) for i in (0, 3, 6)]

    def test_wings_are_level_in_the_world_without_bank(self):
        for heading in range(-128, 129, 8):
            for pitch in (-48, -24, 0, 24, 48):
                forward, wings, up = self.basis(heading, pitch, 0)
                self.assertAlmostEqual(wings[1], 0, delta=1e-6)
                self.assertLessEqual(up[1], .0001)
                for bank in (-48, -24, 24, 48):
                    axes = self.basis(heading, pitch, bank)
                    for i in range(3):
                        for j in range(3):
                            self.assertAlmostEqual(sum(a*b for a, b in zip(axes[i], axes[j])), i == j, delta=1e-6)
                    f, w, u = axes
                    cross = (f[1]*w[2]-f[2]*w[1], f[2]*w[0]-f[0]*w[2], f[0]*w[1]-f[1]*w[0])
                    self.assertGreater(sum(a*b for a, b in zip(cross, u)), .99999)

    def test_straight_flight_has_no_free_running_roll(self):
        for i in range(-50, 151):
            self.assertAlmostEqual(self.scene.lib.straight_bank(i/100), 0, delta=1e-7)

    def test_combat_and_chase_have_bounded_angular_speed_and_inertia(self):
        # All passes, including entrances/exits; omit only cuts or hidden laps.
        for combat in (True, False):
            for ship in range(9) if combat else range(2):
                previous = None
                previous_roll_rate = None
                for t in range(1650) if combat else range(8800, 13750):
                    f = Flight()
                    cadence = .88 if combat and ship == 8 else 1
                    if combat:
                        self.scene.lib.flight_probe(t/55*cadence, ship, ctypes.byref(f))
                    else:
                        self.scene.lib.pursuit_probe(t, ship, ctypes.byref(f))
                    axes = self.basis(f.heading, f.pitch, f.bank)
                    minimum_speed = (200 if ship == 8 else 230) if combat else 190
                    self.assertGreater(math.hypot(f.dx, f.dy)*cadence, minimum_speed)
                    self.assertLess(abs(f.bank)*360/256, 30)
                    continuous = previous and abs(f.x-previous[0].x) < 50 and (combat or (t-8800) % 165)
                    if continuous:
                        old, old_axes = previous
                        for axis, old_axis in zip(axes, old_axes):
                            dot = max(-1, min(1, sum(a*b for a, b in zip(axis, old_axis))))
                            self.assertLess(math.degrees(math.acos(dot))*55, 55, (combat, ship, t))
                        # Per-axis roll rate and acceleration bound the inertia,
                        # independently of whether the object is currently visible.
                        roll_rate = (f.bank-old.bank)*360/256*55
                        self.assertLess(abs(roll_rate), 40)
                        if previous_roll_rate is not None:
                            self.assertLess(abs(roll_rate-previous_roll_rate)*55, 50)
                        previous_roll_rate = roll_rate
                        # The nose follows the derivative of the *3D* translation,
                        # not just a screen-space heading with an arbitrary pitch.
                        def center(p):
                            z = 520/p.size
                            return ((p.x-200)*z/200, (p.y-120)*z/200, z)
                        delta = [a-b for a, b in zip(center(f), center(old))]
                        norm = math.sqrt(sum(a*a for a in delta))
                        self.assertGreater(sum(a*b for a, b in zip(axes[0], delta))/norm, .9999)
                    else:
                        previous_roll_rate = None
                        if previous and combat:
                            for pose in (f, previous[0]):
                                self.assertTrue(pose.x+pose.size*1.4 < 0 or pose.x-pose.size*1.4 > 400)
                    previous = (f, axes)

    def test_flight_pose_is_independent_of_query_order(self):
        first = Flight()
        self.scene.lib.flight_probe(13.7, 8, ctypes.byref(first))
        for seconds in (29.5, 0, 6.21, -1, 31.7):
            unused = Flight()
            self.scene.lib.flight_probe(seconds, 2, ctypes.byref(unused))
        again = Flight()
        self.scene.lib.flight_probe(13.7, 8, ctypes.byref(again))
        self.assertEqual(bytes(first), bytes(again))

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
