"""Unit tests for battle.py (Projectile, Cannon, Battle).

Run from the project root:  python -m unittest discover tests
Expected numbers are worked out by hand or come from an independent simulation
script written during M0 (docs/M0_design.md §14), not from battle.py itself.
"""
import math
import os
import subprocess
import sys
import unittest

from battle import (Battle, Cannon, Projectile, CANNON_PIVOT, DT, GRAVITY,
                    MAX_POWER, MAX_STEPS, SPEED_PER_POWER)
from castle import GROUND_Y

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def play_shot(battle, angle, power):
    """Aim the active cannon, fire, and fly until the shot ends.

    Returns the list of events produced by this shot. Uses only the public
    methods a player's key presses would use.
    """
    cannon = battle.cannons[battle.active_side]
    cannon.adjust_angle(angle - cannon.angle)
    cannon.adjust_power(power - cannon.power)
    battle.take_events()                       # throw away older events
    if not battle.fire():
        raise AssertionError("the active cannon refused to fire")
    for _ in range(MAX_STEPS + 1):
        if battle.projectile is None:
            break
        battle.update()
    return battle.take_events()


def only_event(events, event_type):
    """The single event of this type (fails if there is not exactly one)."""
    matches = [event for event in events if event["type"] == event_type]
    if len(matches) != 1:
        raise AssertionError(f"expected one {event_type!r} event, got {events}")
    return matches[0]


def shot_result(events):
    """The explosion or miss event of a shot."""
    results = [e for e in events if e["type"] in ("explosion", "miss")]
    if len(results) != 1:
        raise AssertionError(f"expected one explosion or miss, got {events}")
    return results[0]


class ProjectileTest(unittest.TestCase):
    # Power 10 -> speed 70 px/s. At 45 deg: vx = 70 cos 45 = 49.4975, vy = -49.4975.
    # Each step: vy += 400/60, then y += vy/60. After 60 steps (one second):
    #   vy = -49.4975 + 400 = 350.5025
    #   x  = 60 * 49.4975 / 60 = 49.4975
    #   y  = (60 * vy0 + (400/60) * (1 + 2 + ... + 60)) / 60
    #      = -49.4975 + 400 * 1830 / 3600 = 153.8358
    def test_gravity_changes_only_the_vertical_speed(self):
        shot = Projectile(0, 0, 45, 10, "left")
        for _ in range(60):
            shot.step()
        self.assertAlmostEqual(shot.vx, 49.4975, places=3)
        self.assertAlmostEqual(shot.vy, 350.5025, places=3)
        self.assertAlmostEqual(shot.x, 49.4975, places=3)
        self.assertAlmostEqual(shot.y, 153.8358, places=3)
        self.assertEqual(shot.steps, 60)

    def test_right_side_projectile_travels_left(self):
        shot = Projectile(1000, 0, 45, 10, "right")
        for _ in range(60):
            shot.step()
        self.assertAlmostEqual(shot.x, 1000 - 49.4975, places=3)
        self.assertAlmostEqual(shot.y, 153.8358, places=3)


class CannonTest(unittest.TestCase):
    def test_angle_is_kept_between_5_and_80(self):
        cannon = Cannon("left")                    # starts at 45 deg
        cannon.adjust_angle(5)
        self.assertEqual(cannon.angle, 50)
        cannon.adjust_angle(100)
        self.assertEqual(cannon.angle, 80)
        cannon.adjust_angle(-200)
        self.assertEqual(cannon.angle, 5)

    def test_power_is_kept_between_10_and_100(self):
        cannon = Cannon("right")                   # starts at power 50
        cannon.adjust_power(1)
        self.assertEqual(cannon.power, 51)
        cannon.adjust_power(500)
        self.assertEqual(cannon.power, 100)
        cannon.adjust_power(-500)
        self.assertEqual(cannon.power, 10)

    def test_fire_launches_from_the_pivot_with_the_current_aim(self):
        # Power 40 -> 280 px/s. At 30 deg: vx = 280 cos 30 = 242.487, vy = -280 sin 30 = -140.
        for side, pivot, vx in (("left", (360, 390), 242.487), ("right", (920, 390), -242.487)):
            with self.subTest(side=side):
                cannon = Cannon(side)
                cannon.adjust_angle(30 - cannon.angle)
                cannon.adjust_power(40 - cannon.power)
                shot = cannon.fire()
                self.assertEqual((shot.x, shot.y), pivot)
                self.assertAlmostEqual(shot.vx, vx, places=3)
                self.assertAlmostEqual(shot.vy, -140.0, places=3)


class ShotTest(unittest.TestCase):
    def test_default_shot_lands_short_of_the_enemy_castle(self):
        battle = Battle()
        cannon = battle.cannons["left"]
        events = play_shot(battle, cannon.angle, cannon.power)   # default aim
        explosion = only_event(events, "explosion")
        self.assertEqual(explosion["kind"], "ground")
        self.assertTrue(770 <= explosion["x"] <= 800, explosion)  # about 785
        self.assertEqual(explosion["blocks_hit"], 0)
        self.assertEqual(battle.castles["right"].total_hp(), 1500)

    def test_shot_into_the_tower_damages_the_blocks_around_the_impact(self):
        # Independent simulation: 45 deg, power 64 hits the tower near (893, 429).
        # Block centres within 50 px of that point: (904,416), (936,416), (904,448), (936,448).
        # 4 blocks x 50 damage = 200.
        battle = Battle()
        explosion = only_event(play_shot(battle, 45, 64), "explosion")
        self.assertEqual(explosion["kind"], "block")
        self.assertTrue(885 <= explosion["x"] <= 900 and 420 <= explosion["y"] <= 440, explosion)
        self.assertEqual((explosion["blocks_hit"], explosion["damage"]), (4, 200))
        self.assertEqual(battle.castles["right"].total_hp(), 1500 - 200)
        self.assertEqual(battle.castles["left"].total_hp(), 1500)

    def test_two_direct_hits_destroy_the_blocks_they_cover(self):
        # Each 45/64 shot hits the same 4 tower blocks for 50: 100 -> 50 -> 0 HP.
        battle = Battle()
        play_shot(battle, 45, 64)                 # left: the 4 blocks drop to 50 HP
        play_shot(battle, 80, 10)                 # right: lands on its own castle, harmless
        play_shot(battle, 45, 64)                 # left again: the 4 blocks are destroyed
        castle = battle.castles["right"]
        alive = {(b.x, b.y) for b in castle.alive_blocks()}
        for gone in ((888, 400), (920, 400), (888, 432), (920, 432)):
            self.assertNotIn(gone, alive)
        self.assertEqual(len(alive), 11)
        self.assertAlmostEqual(castle.destruction_percent(), 400 / 1500 * 100)

    def test_ground_explosion_next_to_the_castle_damages_the_front_block(self):
        # Power 56 lands on the ground at x ~ 868: 39 px from the front block's centre (904, 544).
        battle = Battle()
        explosion = only_event(play_shot(battle, 45, 56), "explosion")
        self.assertEqual(explosion["kind"], "ground")
        self.assertEqual(explosion["y"], GROUND_Y)
        self.assertEqual((explosion["blocks_hit"], explosion["damage"]), (1, 50))
        damaged = [(b.x, b.y) for b in battle.castles["right"].blocks if b.hp < 100]
        self.assertEqual(damaged, [(888, 528)])

    def test_ground_explosion_just_out_of_range_damages_nothing(self):
        # Power 55 lands at x ~ 855: 52 px from the nearest block centre.
        battle = Battle()
        explosion = only_event(play_shot(battle, 45, 55), "explosion")
        self.assertEqual(explosion["blocks_hit"], 0)
        self.assertEqual(battle.castles["right"].total_hp(), 1500)

    def test_shot_passes_through_its_own_castle_without_damaging_it(self):
        # 80 deg, power 10 goes almost straight up and falls back through the
        # left castle's own tower, landing at x ~ 373.6 inside the castle's footprint.
        battle = Battle()
        explosion = only_event(play_shot(battle, 80, 10), "explosion")
        self.assertEqual(explosion["kind"], "ground")
        self.assertTrue(365 <= explosion["x"] <= 382, explosion)
        self.assertEqual(battle.castles["left"].total_hp(), 1500)
        self.assertEqual(battle.castles["right"].total_hp(), 1500)

    def test_destroyed_block_no_longer_stops_shots(self):
        battle = Battle()
        block = battle.castles["right"].block_at(893, 429)   # the block the 45/64 shot hits
        block.take_damage(100)
        explosion = only_event(play_shot(battle, 45, 64), "explosion")
        self.assertFalse(block.contains(explosion["x"], explosion["y"]))
        self.assertGreaterEqual(explosion["y"], 432)          # it flew on, into the block below

    def test_shot_that_leaves_the_screen_is_a_miss(self):
        battle = Battle()
        events = play_shot(battle, 45, 100)                   # would land near x = 1284
        miss = only_event(events, "miss")
        self.assertEqual(miss["reason"], "offscreen")
        self.assertFalse([e for e in events if e["type"] == "explosion"])
        self.assertEqual(battle.castles["right"].total_hp(), 1500)

    def test_every_legal_shot_ends_before_the_timeout(self):
        # The step limit always ends a shot, so the real check is that no legal
        # shot needs it: each one must hit something or leave the screen.
        for angle in range(5, 81, 5):
            for power in range(10, 101, 10):
                with self.subTest(angle=angle, power=power):
                    result = shot_result(play_shot(Battle(), angle, power))
                    self.assertNotEqual(result.get("reason"), "timeout")

    def test_left_and_right_shots_are_mirror_images(self):
        for angle, power in ((45, 50), (45, 64), (30, 60), (70, 85), (80, 10), (45, 100)):
            with self.subTest(angle=angle, power=power):
                battle = Battle()
                left = shot_result(play_shot(battle, angle, power))    # left's turn
                right = shot_result(play_shot(battle, angle, power))   # then right's
                self.assertEqual(left["type"], right["type"])
                self.assertEqual(left.get("blocks_hit"), right.get("blocks_hit"))
                self.assertAlmostEqual(right["x"], 1280 - left["x"], places=6)
                self.assertAlmostEqual(right["y"], left["y"], places=6)

    def test_same_shot_always_gives_the_same_result(self):
        first = shot_result(play_shot(Battle(), 30, 60))
        second = shot_result(play_shot(Battle(), 30, 60))
        self.assertEqual(first, second)

    def test_fastest_shot_cannot_jump_over_a_target(self):
        # Energy conservation: the fastest a shot can ever move is at ground level
        # with maximum power. Its move per step must stay below the smallest
        # target (28 px: the character width planned for M2; blocks are 32 px).
        launch_speed = SPEED_PER_POWER * MAX_POWER
        drop = GROUND_Y - min(y for _, y in CANNON_PIVOT.values())
        fastest = math.sqrt(launch_speed ** 2 + 2 * GRAVITY * drop)
        self.assertLess(fastest * DT, 28)


class TurnTest(unittest.TestCase):
    def test_turns_alternate_left_right_left(self):
        battle = Battle()
        self.assertEqual(battle.active_side, "left")
        events = play_shot(battle, 45, 50)
        self.assertEqual(only_event(events, "turn")["side"], "right")
        self.assertEqual(battle.active_side, "right")
        play_shot(battle, 45, 50)
        self.assertEqual(battle.active_side, "left")

    def test_turn_also_passes_after_a_miss(self):
        battle = Battle()
        play_shot(battle, 45, 100)                            # off the screen
        self.assertEqual(battle.active_side, "right")

    def test_cannot_fire_again_while_a_shot_is_flying(self):
        battle = Battle()
        self.assertTrue(battle.fire())
        first_shot = battle.projectile
        self.assertFalse(battle.fire())
        self.assertIs(battle.projectile, first_shot)
        self.assertEqual(battle.active_side, "left")

    def test_each_side_keeps_its_own_aim(self):
        battle = Battle()
        play_shot(battle, 30, 40)                             # left aims and fires
        self.assertEqual((battle.cannons["right"].angle, battle.cannons["right"].power), (45, 50))
        play_shot(battle, 60, 70)                             # right aims and fires
        self.assertEqual((battle.cannons["left"].angle, battle.cannons["left"].power), (30, 40))


class VictoryTest(unittest.TestCase):
    def test_left_wins_when_the_right_castle_reaches_60_percent(self):
        battle = Battle()
        for block in battle.castles["right"].blocks:
            block.take_damage(58)                 # 870 damage = 58 %, no block destroyed
        events = play_shot(battle, 45, 64)        # 4 blocks x 42 HP left = +168 -> 1038 = 69 %
        self.assertEqual(only_event(events, "game_over")["winner"], "left")
        self.assertEqual(battle.winner, "left")
        self.assertTrue(battle.is_over())
        self.assertFalse(battle.fire())           # nobody can shoot after the game ends
        self.assertEqual(battle.active_side, "left")
        self.assertFalse([e for e in events if e["type"] == "turn"])

    def test_game_continues_below_60_percent(self):
        battle = Battle()
        for block in battle.castles["right"].blocks:
            block.take_damage(40)                 # 600 damage = 40 %
        events = play_shot(battle, 45, 64)        # 4 blocks x 50 = +200 -> 800 = 53 %
        self.assertIsNone(battle.winner)
        self.assertFalse([e for e in events if e["type"] == "game_over"])
        self.assertEqual(battle.active_side, "right")

    def test_right_wins_when_the_left_castle_falls(self):
        battle = Battle()
        for block in battle.castles["left"].blocks[:9]:
            block.take_damage(100)                # 900 damage = 60 %
        self.assertEqual(battle.check_winner(), "right")

    def test_draw_when_both_castles_fall_together(self):
        # A single M1 shot only damages one castle, so this can't happen in play yet,
        # but the rule (both lose = draw) must hold for later milestones.
        battle = Battle()
        for side in ("left", "right"):
            for block in battle.castles[side].blocks[:9]:
                block.take_damage(100)
        self.assertEqual(battle.check_winner(), "draw")
        self.assertTrue(battle.is_over())


class RestartTest(unittest.TestCase):
    def test_reset_starts_a_fresh_match(self):
        battle = Battle()
        for block in battle.castles["right"].blocks:
            block.take_damage(58)
        play_shot(battle, 45, 64)                 # left wins
        battle.cannons["right"].adjust_angle(10)
        self.assertTrue(battle.is_over())

        battle.reset()

        fresh = Battle()
        self.assertIsNone(battle.winner)
        self.assertFalse(battle.is_over())
        self.assertIsNone(battle.projectile)
        self.assertEqual(battle.active_side, "left")
        self.assertEqual(battle.take_events(), [])
        for side in ("left", "right"):
            self.assertEqual(battle.castles[side].total_hp(), 1500)
            self.assertEqual(battle.cannons[side].angle, fresh.cannons[side].angle)
            self.assertEqual(battle.cannons[side].power, fresh.cannons[side].power)
        self.assertTrue(battle.fire())

    def test_reset_while_a_shot_is_flying_cancels_it(self):
        battle = Battle()
        battle.fire()
        for _ in range(10):
            battle.update()
        battle.reset()
        self.assertIsNone(battle.projectile)
        self.assertEqual(battle.active_side, "left")
        self.assertEqual(battle.take_events(), [])
        battle.update()                           # nothing left to move or explode
        self.assertEqual(battle.castles["right"].total_hp(), 1500)
        self.assertTrue(battle.fire())


class EventTest(unittest.TestCase):
    def test_take_events_hands_each_event_over_once(self):
        battle = Battle()
        battle.fire()
        self.assertEqual(battle.take_events(), [{"type": "fire", "side": "left"}])
        self.assertEqual(battle.take_events(), [])

    def test_events_wait_until_they_are_taken(self):
        battle = Battle()
        battle.fire()
        while battle.projectile is not None:
            battle.update()
        types = [event["type"] for event in battle.take_events()]
        self.assertEqual(types, ["fire", "explosion", "turn"])


class PygameIndependenceTest(unittest.TestCase):
    def test_logic_modules_do_not_import_pygame(self):
        # A fresh interpreter, so other tests can't have loaded pygame already.
        result = subprocess.run(
            [sys.executable, "-c", "import sys, castle, battle; print('pygame' in sys.modules)"],
            cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
