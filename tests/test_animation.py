"""Unit tests for animation.py: the character's run to the cannon and back (M3.4-C).

animation.py uses only the standard library, so these tests run without Pygame. How main.py
uses it (input lock, firing exactly once, drawing) is tested in tests/test_main.py.
"""
import os
import re
import subprocess
import sys
import unittest

from animation import (FIRE, FIRE_FRAMES, IDLE, RETURN_FRAMES, RETURN_TO_SLOT, RUN_FRAMES, RUN_TO_CANNON,
                       CannonRun, PendingShot, firing_x, fires_the_cannon)
from battle import CANNON_PIVOT, CHARACTER_WIDTH, SLOT_X
from castle import BLOCK_SIZE, COLUMN_X
from characters import ARCHETYPES, Archer, Engineer, Knight

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def started(side="left", index=0, action="attack"):
    """A CannonRun that has just sent the character in slot `index` of `side` to the cannon."""
    run = CannonRun()
    run.start(PendingShot(side, index, action, 45, 50), SLOT_X[side][index])
    return run


def play_out(run):
    """Step a run until it is idle again. Returns [(state before the step, step's answer), ...]."""
    frames = []
    for _ in range(RUN_FRAMES + FIRE_FRAMES + RETURN_FRAMES + 10):
        if not run.is_busy():
            return frames
        state = run.state
        frames.append((state, run.step()))
    raise AssertionError("the run never ended")


class StatesTest(unittest.TestCase):
    def test_a_new_run_is_idle_and_holds_no_shot(self):
        run = CannonRun()
        self.assertEqual(run.state, IDLE)
        self.assertFalse(run.is_busy())
        self.assertIsNone(run.shot)
        self.assertFalse(run.step())                       # an idle run never asks to fire

    def test_starting_keeps_the_shot_and_begins_the_run_to_the_cannon(self):
        shot = PendingShot("right", 2, "special", 60, 88)
        run = CannonRun()
        run.start(shot, SLOT_X["right"][2])
        self.assertEqual(run.state, RUN_TO_CANNON)
        self.assertTrue(run.is_busy())
        self.assertIs(run.shot, shot)
        self.assertEqual((shot.side, shot.actor_index, shot.action, shot.angle, shot.power, shot.plan),
                         ("right", 2, "special", 60, 88, None))

    def test_the_states_follow_each_other_for_a_fixed_number_of_frames(self):
        states = [state for state, _ in play_out(started())]
        expected = [RUN_TO_CANNON] * RUN_FRAMES + [FIRE] * FIRE_FRAMES + [RETURN_TO_SLOT] * RETURN_FRAMES
        self.assertEqual(states, expected)

    def test_step_asks_to_fire_exactly_once_on_the_frame_the_cannon_is_reached(self):
        frames = play_out(started())
        fire_frames = [number for number, (_, fire) in enumerate(frames, start=1) if fire]
        self.assertEqual(fire_frames, [RUN_FRAMES])

    def test_the_timing_suits_60_fps(self):
        # The brief: 15-24 frames each way, and a short firing pose.
        self.assertTrue(15 <= RUN_FRAMES <= 24 and 15 <= RETURN_FRAMES <= 24)
        self.assertTrue(1 <= FIRE_FRAMES <= 20)

    def test_cancel_stops_at_once_and_nothing_is_fired_afterwards(self):
        for frames_before_cancel in (0, 5, RUN_FRAMES + 3, RUN_FRAMES + FIRE_FRAMES + 4):
            with self.subTest(frames=frames_before_cancel):
                run = started()
                for _ in range(frames_before_cancel):
                    run.step()
                run.cancel()
                self.assertEqual((run.state, run.shot), (IDLE, None))
                self.assertFalse(any(run.step() for _ in range(RUN_FRAMES * 3)))

    def test_a_second_run_cannot_start_while_one_is_going(self):
        run = started()
        with self.assertRaises(RuntimeError):
            run.start(PendingShot("left", 1, "attack", 45, 50), SLOT_X["left"][1])
        self.assertEqual(run.shot.actor_index, 0)

    def test_moves_names_only_the_running_character(self):
        run = started("right", 1)
        self.assertTrue(run.moves("right", 1))
        self.assertFalse(run.moves("right", 0))
        self.assertFalse(run.moves("left", 1))
        run.cancel()
        self.assertFalse(run.moves("right", 1))


class MovementTest(unittest.TestCase):
    def test_the_runner_goes_from_its_slot_to_the_cannon_and_back_in_a_straight_line(self):
        for side in ("left", "right"):
            for index in range(3):
                with self.subTest(side=side, index=index):
                    run = started(side, index)
                    slot, cannon = SLOT_X[side][index], firing_x(side)
                    self.assertEqual(run.actor_x(), slot)
                    for _ in range(RUN_FRAMES // 2):
                        run.step()
                    self.assertAlmostEqual(run.actor_x(), (slot + cannon) / 2)      # halfway there
                    for _ in range(RUN_FRAMES - RUN_FRAMES // 2):
                        run.step()
                    self.assertEqual((run.state, run.actor_x()), (FIRE, cannon))   # beside the cannon
                    for _ in range(FIRE_FRAMES + RETURN_FRAMES // 2):
                        run.step()
                    self.assertAlmostEqual(run.actor_x(), (slot + cannon) / 2)      # halfway back
                    for _ in range(RETURN_FRAMES - RETURN_FRAMES // 2):
                        run.step()
                    self.assertFalse(run.is_busy())                                # back in its slot

    def test_every_step_moves_toward_the_cannon_then_back(self):
        run = started("left", 2)
        xs = [run.actor_x()]
        while run.is_busy():
            run.step()
            if run.is_busy():
                xs.append(run.actor_x())
        there = xs[:RUN_FRAMES + 1]
        back = xs[RUN_FRAMES + FIRE_FRAMES:]
        self.assertEqual(there, sorted(there))                     # left team: toward larger x
        self.assertEqual(back, sorted(back, reverse=True))

    def test_the_runner_faces_the_cannon_then_faces_home(self):
        for side, toward_cannon in (("left", 1), ("right", -1)):
            with self.subTest(side=side):
                run = started(side)
                seen = {}
                while run.is_busy():
                    seen.setdefault(run.state, set()).add(run.facing())
                    run.step()
                self.assertEqual(seen, {RUN_TO_CANNON: {toward_cannon}, FIRE: {toward_cannon},
                                        RETURN_TO_SLOT: {-toward_cannon}})

    def test_the_firing_spot_is_between_the_cover_and_the_cannon_on_both_sides(self):
        for side in ("left", "right"):
            with self.subTest(side=side):
                x = firing_x(side)
                body = (x - CHARACTER_WIDTH / 2, x + CHARACTER_WIDTH / 2)
                cover = (min(COLUMN_X[side]), max(COLUMN_X[side]) + BLOCK_SIZE)
                wheel = (CANNON_PIVOT[side][0] - 8, CANNON_PIVOT[side][0] + 8)   # main.draw_cannon
                self.assertTrue(body[1] < cover[0] or body[0] > cover[1], (body, cover))
                self.assertTrue(body[1] < wheel[0] or body[0] > wheel[1], (body, wheel))
                # Between the two: the cover on one side, the cannon on the other.
                self.assertLess(abs(x - CANNON_PIVOT[side][0]), abs(SLOT_X[side][0] - CANNON_PIVOT[side][0]))
        self.assertEqual(firing_x("left") + firing_x("right"), 1280)              # mirror images


class FiresTheCannonTest(unittest.TestCase):
    def test_attack_and_power_shot_fire_and_nothing_else_does(self):
        self.assertTrue(fires_the_cannon(Knight("K", "left"), "attack"))
        self.assertTrue(fires_the_cannon(Archer("A", "left"), "special"))
        for character in (Knight("K", "left"), Engineer("E", "left"), Archer("A", "left")):
            self.assertFalse(fires_the_cannon(character, "defend"))
        self.assertFalse(fires_the_cannon(Knight("K", "left"), "special"))       # Rally
        self.assertFalse(fires_the_cannon(Engineer("E", "left"), "special"))     # Repair

    def test_it_agrees_with_what_each_special_really_does(self):
        # use_special returns a shot exactly when the Battle fires the cannon for it.
        from battle import Battle
        for role in ARCHETYPES:
            with self.subTest(role=role.__name__):
                battle = Battle(roster={"left": [role], "right": [Knight]})
                battle.castles["left"].blocks[0].take_damage(10)     # so Repair has work to do
                character = battle.teams["left"].characters[0]
                _, shot = character.use_special(battle.teams["left"])
                self.assertEqual(fires_the_cannon(character, "special"), shot is not None)


class SeparationTest(unittest.TestCase):
    def test_animation_does_not_import_pygame(self):
        # A fresh interpreter, so other tests can't have loaded pygame already.
        result = subprocess.run([sys.executable, "-c", "import sys, animation; print('pygame' in sys.modules)"],
                                cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")

    def test_the_rule_modules_do_not_use_the_animation(self):
        # The Battle (and the AI) decide everything without it; only main.py uses it.
        for name in ("battle.py", "castle.py", "characters.py", "ai.py"):
            with open(os.path.join(PROJECT_ROOT, name), encoding="utf-8") as f:
                self.assertIsNone(re.search(r"^\s*(import|from)\s+animation\b", f.read(), re.MULTILINE), name)


if __name__ == "__main__":
    unittest.main()
