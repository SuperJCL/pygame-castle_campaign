"""Unit tests for reflex_aim.py: the swinging cannon angle of Reflex Aim (M6.1, experimental).

reflex_aim.py uses only the standard library, so these tests run without Pygame. How main.py
uses it (which teams swing, the input lock, capturing the angle, Classic Aim) is tested in
tests/test_reflex_aim_game.py.
"""
import os
import re
import subprocess
import sys
import unittest

from battle import MAX_ANGLE, MIN_ANGLE
from reflex_aim import SWING_HIGH, SWING_LOW, SWING_PERIOD_FRAMES, AimSwing

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def one_period(swing, exact=False):
    """The angle on each frame of one full swing, starting from the swing's current frame."""
    angles = []
    for _ in range(swing.period):
        angles.append(swing.exact_angle() if exact else swing.angle())
        swing.step()
    return angles


class SwingSettingsTest(unittest.TestCase):
    def test_the_default_swing_is_20_to_75_degrees_every_3_seconds(self):
        self.assertEqual((SWING_LOW, SWING_HIGH), (20, 75))
        self.assertEqual(SWING_PERIOD_FRAMES, 180)          # 3 s at 60 frames per second
        swing = AimSwing()
        self.assertEqual((swing.low, swing.high, swing.period), (20, 75, 180))

    def test_the_limits_and_the_period_can_be_changed(self):
        swing = AimSwing(low=30, high=60, period=120)
        angles = one_period(swing)
        self.assertEqual((min(angles), max(angles)), (30, 60))
        self.assertEqual(len(angles), 120)

    def test_settings_that_cannot_work_are_refused(self):
        for low, high, period in ((50, 50, 180),          # no swing at all
                                  (60, 40, 180),          # upside down
                                  (MIN_ANGLE - 1, 75, 180), (20, MAX_ANGLE + 1, 180),   # beyond the cannon
                                  (20, 75, 0), (20, 75, 3), (20, 75, 91.5)):            # no exact top frame
            with self.subTest(low=low, high=high, period=period), self.assertRaises(ValueError):
                AimSwing(low=low, high=high, period=period)


class SwingMotionTest(unittest.TestCase):
    def test_it_starts_at_the_low_limit_and_reaches_the_high_limit_halfway(self):
        swing = AimSwing()
        self.assertEqual(swing.angle(), 20)
        for _ in range(90):
            swing.step()
        self.assertEqual(swing.angle(), 75)                  # 1.5 s: the top
        self.assertAlmostEqual(swing.exact_angle(), 75.0)

    def test_both_limits_are_reached_and_never_passed(self):
        exact = one_period(AimSwing(), exact=True)
        self.assertAlmostEqual(min(exact), 20.0)
        self.assertAlmostEqual(max(exact), 75.0)
        self.assertTrue(all(20.0 <= a <= 75.0 for a in exact))
        whole = one_period(AimSwing())
        self.assertEqual((min(whole), max(whole)), (20, 75))
        self.assertTrue(all(isinstance(a, int) for a in whole))   # whole degrees, like the arrow keys

    def test_it_rises_for_half_the_period_then_falls(self):
        exact = one_period(AimSwing(), exact=True)
        self.assertTrue(all(b > a for a, b in zip(exact[:90], exact[1:91])))   # frames 0 -> 90: up
        self.assertTrue(all(b < a for a, b in zip(exact[90:179], exact[91:180])))   # 90 -> 179: down

    def test_one_complete_period_brings_it_back_to_the_start(self):
        swing = AimSwing()
        first = one_period(swing)                    # 180 frames ...
        self.assertEqual((swing.frame, swing.angle()), (0, 20))   # ... and it is back where it began
        self.assertEqual(one_period(swing), first)   # the next swing is exactly the same

    def test_the_direction_reverses_smoothly_at_both_limits(self):
        exact = one_period(AimSwing(), exact=True) + [AimSwing().exact_angle()]   # frame 180 = frame 0
        speeds = [b - a for a, b in zip(exact, exact[1:])]                       # degrees per frame
        # It slows down into each limit and speeds up out of it: almost still at the turn ...
        for turn in (90, 180):
            self.assertLess(abs(speeds[turn - 1]), 0.05)
            self.assertLess(abs(speeds[turn % 180]), 0.05)
        # ... and the speed never changes suddenly. (A swing that bounced at full speed, about
        # 0.6 degrees a frame, would change its speed by about 1.2 degrees in one frame there.)
        changes = [b - a for a, b in zip(speeds, speeds[1:] + speeds[:1])]
        self.assertLess(max(abs(c) for c in changes), 0.05)

    def test_the_shown_angle_never_jumps_by_more_than_one_degree(self):
        swing = AimSwing()
        whole = one_period(swing) + [swing.angle()]          # including the wrap to the next swing
        self.assertLessEqual(max(abs(b - a) for a, b in zip(whole, whole[1:])), 1)
        self.assertEqual(sorted(set(whole)), list(range(20, 76)))   # every whole angle is on offer

    def test_reset_starts_the_swing_again_from_the_low_limit(self):
        swing = AimSwing()
        for _ in range(37):
            swing.step()
        swing.reset()
        self.assertEqual((swing.frame, swing.angle()), (0, 20))

    def test_the_motion_is_the_same_every_time(self):
        self.assertEqual(one_period(AimSwing(), exact=True), one_period(AimSwing(), exact=True))


class SwingModuleTest(unittest.TestCase):
    def test_reflex_aim_does_not_import_pygame(self):
        # A fresh interpreter, so other tests can't have loaded pygame already.
        result = subprocess.run([sys.executable, "-c", "import sys, reflex_aim; print('pygame' in sys.modules)"],
                                cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")

    def test_the_rule_modules_and_the_computer_do_not_use_it(self):
        # Reflex Aim is only a way for a person to aim: the Battle and the AI never see it.
        for name in ("battle.py", "castle.py", "characters.py", "ai.py", "animation.py"):
            with open(os.path.join(PROJECT_ROOT, name), encoding="utf-8") as f:
                self.assertIsNone(re.search(r"^\s*(import|from)\s+reflex_aim\b", f.read(), re.MULTILINE), name)


if __name__ == "__main__":
    unittest.main()
