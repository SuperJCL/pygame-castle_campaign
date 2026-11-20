"""Unit tests for battle.py: Projectile, Cannon, collision along the flight path, and
the flight of shots on the M3.4 battlefield.

Run from the project root:  python -m unittest discover tests
Expected numbers are worked out by hand, or come from an independent simulation
script (its own physics and its own collision check, sampling each step's path
finely), not from battle.py itself. Team combat rules are in test_combat.py.
"""
import copy
import os
import subprocess
import sys
import unittest

from battle import (Battle, Cannon, Projectile, MAX_STEPS, segment_entry)
from castle import DEFAULT_LAYOUT, GROUND_Y, slot_position
from characters import Archer, Engineer, Knight

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIO = [Knight, Archer, Engineer]
OPEN = {"left": (), "right": ()}            # no cover blocks at all


def team_battle(layouts=None, roster=TRIO):
    """3 v 3 with the same roles on both sides; the default cover unless `layouts` is given."""
    return Battle(roster={"left": list(roster), "right": list(roster)}, layouts=layouts)


def play_shot(battle, angle, power):
    """Aim the active cannon, Attack with the first living character, and fly until the
    shot ends. Returns the events produced by this shot."""
    cannon = battle.cannons[battle.active_side]
    cannon.adjust_angle(angle - cannon.angle)
    cannon.adjust_power(power - cannon.power)
    battle.take_events()                       # throw away older events
    team = battle.teams[battle.active_side]
    index = next(i for i, c in enumerate(team.characters) if c.is_alive())
    if not battle.perform_action(index, "attack"):
        raise AssertionError("the attack was refused")
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
        for side, pivot, vx in (("left", (340, 544), 242.487), ("right", (940, 544), -242.487)):
            with self.subTest(side=side):
                cannon = Cannon(side)
                cannon.adjust_angle(30 - cannon.angle)
                cannon.adjust_power(40 - cannon.power)
                shot = cannon.fire()
                self.assertEqual((shot.x, shot.y), pivot)
                self.assertAlmostEqual(shot.vx, vx, places=3)
                self.assertAlmostEqual(shot.vy, -140.0, places=3)

    def test_each_cannon_stands_on_the_ground_in_front_of_its_cover(self):
        battle = team_battle()
        for side, ahead in (("left", 1), ("right", -1)):
            with self.subTest(side=side):
                cannon = battle.cannons[side]
                self.assertTrue(GROUND_Y - 20 <= cannon.y < GROUND_Y)       # near the ground
                for slot in range(8):                                       # past every cover slot ...
                    x, _ = slot_position(side, slot)
                    nearest_edge = x + 32 if side == "left" else x
                    self.assertGreater((cannon.x - nearest_edge) * ahead, 14)
                for index in range(3):                                      # ... and every character
                    left, _, width, _ = battle.teams[side].character_rect(index)
                    self.assertGreater((cannon.x - (left + width / 2)) * ahead, 150)


class SegmentEntryTest(unittest.TestCase):
    """segment_entry(): where a straight move first touches a rectangle (0 = start, 1 = end)."""

    def test_a_move_straight_through_a_rectangle(self):
        self.assertAlmostEqual(segment_entry(0, 10, 100, 10, (40, 0, 20, 20)), 0.4)

    def test_a_move_that_passes_beside_or_stops_short_misses(self):
        self.assertIsNone(segment_entry(0, -5, 100, -5, (40, 0, 20, 20)))     # above it
        self.assertIsNone(segment_entry(0, 10, 39, 10, (40, 0, 20, 20)))      # stops short
        self.assertIsNone(segment_entry(50, 30, 50, 60, (40, 0, 20, 20)))     # straight down, below it

    def test_a_step_longer_than_the_target_is_still_caught(self):
        # Both ends are outside the 20 px rectangle, so checking only where each step ends
        # would miss it. The move enters through the left side at x = 40 (y = 17).
        self.assertAlmostEqual(segment_entry(30, 14, 70, 26, (40, 0, 20, 20)), 0.25)

    def test_vertical_and_corner_moves(self):
        self.assertAlmostEqual(segment_entry(50, -10, 50, 30, (40, 0, 20, 20)), 0.25)
        self.assertAlmostEqual(segment_entry(30, -10, 50, 10, (40, 0, 20, 20)), 0.5)   # through the corner


class ShotTest(unittest.TestCase):
    def test_the_default_aim_lands_in_the_middle_of_the_field(self):
        battle = team_battle()
        explosion = only_event(play_shot(battle, 45, 50), "explosion")
        self.assertEqual((explosion["kind"], explosion["y"]), ("ground", GROUND_Y))
        self.assertTrue(650 <= explosion["x"] <= 665, explosion)          # independent sim: 657.6
        self.assertEqual((explosion["blocks_hit"], explosion["characters_hit"]), (0, []))

    def test_a_shot_explodes_where_it_first_touches_a_block(self):
        # Independent sim: 45 deg, power 76 comes down on the top of the right slot-2 block
        # at about (1024.8, 528). Block centres within 50 px: slots 1, 2, 3 and 5.
        battle = team_battle()
        explosion = only_event(play_shot(battle, 45, 76), "explosion")
        self.assertEqual(explosion["kind"], "block")
        self.assertAlmostEqual(explosion["y"], 528, places=6)             # on the surface, not inside
        self.assertTrue(1020 <= explosion["x"] <= 1030, explosion)
        self.assertEqual((explosion["blocks_hit"], explosion["damage"]), (4, 200))
        damaged = sorted(slot for slot, block in zip(DEFAULT_LAYOUT, battle.castles["right"].blocks)
                         if block.hp < 100)
        self.assertEqual(damaged, [1, 2, 3, 5])

    def test_a_shot_explodes_on_the_surface_of_a_character(self):
        # Independent sim: 45 deg, power 81 reaches the front of the right slot-0 character.
        battle = team_battle(OPEN)
        explosion = only_event(play_shot(battle, 45, 81), "explosion")
        self.assertEqual((explosion["kind"], explosion["target"]), ("character", "Knight"))
        self.assertAlmostEqual(explosion["x"], 1126, places=6)            # the character's front edge
        self.assertTrue(516 <= explosion["y"] <= 560, explosion)

    def test_a_destroyed_block_no_longer_stops_shots(self):
        battle = team_battle()
        block = battle.castles["right"].block_at(1024, 530)              # the slot-2 block 45/76 hits
        block.take_damage(100)
        explosion = only_event(play_shot(battle, 45, 76), "explosion")
        self.assertFalse(block.contains(explosion["x"], explosion["y"]))
        self.assertEqual(explosion["kind"], "block")
        self.assertAlmostEqual(explosion["x"], 1044, places=6)            # it flew on, to the next block

    def test_a_shot_never_hits_its_own_side(self):
        # 80 deg, power 10 goes almost straight up and comes down beside the own cannon.
        battle = team_battle()
        explosion = only_event(play_shot(battle, 80, 10), "explosion")
        self.assertEqual(explosion["kind"], "ground")
        self.assertTrue(340 <= explosion["x"] <= 352, explosion)          # independent sim: 346.0
        self.assertEqual((explosion["blocks_hit"], explosion["characters_hit"]), (0, []))
        for side in ("left", "right"):
            self.assertEqual(battle.castles[side].total_hp(), 600)

    def test_a_shot_that_leaves_the_screen_is_a_miss(self):
        battle = team_battle()
        events = play_shot(battle, 45, 100)                               # passes high over everyone
        miss = only_event(events, "miss")
        self.assertEqual(miss["reason"], "offscreen")
        self.assertFalse([e for e in events if e["type"] == "explosion"])

    def test_every_legal_shot_ends_before_the_timeout(self):
        # The step limit always ends a shot, so the real check is that no legal
        # shot needs it: each one must hit something or leave the screen.
        for angle in range(5, 81, 5):
            for power in range(10, 101, 10):
                with self.subTest(angle=angle, power=power):
                    result = shot_result(play_shot(team_battle(), angle, power))
                    self.assertNotEqual(result.get("reason"), "timeout")

    def test_left_and_right_shots_are_mirror_images(self):
        for layouts in (None, OPEN, {"left": (0, 4, 2), "right": (0, 4, 2)}):
            for angle, power in ((45, 50), (45, 76), (45, 81), (60, 88), (80, 10), (45, 100)):
                with self.subTest(layouts=layouts, angle=angle, power=power):
                    battle = team_battle(layouts)
                    left = shot_result(play_shot(battle, angle, power))     # left's turn
                    right = shot_result(play_shot(battle, angle, power))    # then right's
                    self.assertEqual(left["type"], right["type"])
                    self.assertAlmostEqual(right["x"], 1280 - left["x"], places=6)
                    self.assertAlmostEqual(right["y"], left["y"], places=6)
                    for key in ("kind", "target", "blocks_hit", "damage", "characters_hit", "covered"):
                        self.assertEqual(left.get(key), right.get(key), key)

    def test_same_shot_always_gives_the_same_result(self):
        first = shot_result(play_shot(team_battle(), 60, 88))
        second = shot_result(play_shot(team_battle(), 60, 88))
        self.assertEqual(first, second)


class PathContactsTest(unittest.TestCase):
    """M3.4-B: path_contacts() lists what a shot's path crosses, for the computer's planning.
    It uses the same flight and collision code as real shots, and changes nothing."""

    AIMS = [(angle, power) for angle in (30, 45, 60) for power in range(60, 101, 4)]

    def test_the_first_contact_is_exactly_what_a_real_shot_hits(self):
        for layouts in (None, OPEN, {"left": (0, 4, 2), "right": (0, 4, 2)}):
            for angle, power in self.AIMS:
                with self.subTest(layouts=layouts, angle=angle, power=power):
                    battle = team_battle(layouts)
                    kind, ref, x, y = battle.path_contacts("left", angle, power)[0]
                    result = shot_result(play_shot(battle, angle, power))
                    if result["type"] == "miss":
                        self.assertEqual(kind, "offscreen")
                    else:
                        self.assertEqual(kind, result["kind"])
                        if kind == "character":
                            self.assertEqual(battle.teams["right"].characters[ref].name, result["target"])
                    self.assertAlmostEqual(x, result["x"], places=6)
                    self.assertAlmostEqual(y, result["y"], places=6)

    def test_the_path_goes_on_behind_the_first_block(self):
        battle = team_battle()
        contacts = battle.path_contacts("left", 45, 76)        # comes down on the slot-2 block
        kinds = [kind for kind, _, _, _ in contacts]
        self.assertEqual(kinds[0], "block")
        self.assertIn(kinds[-1], ("ground", "offscreen"))
        self.assertGreaterEqual(len(contacts), 3)
        refs = [(kind, ref) for kind, ref, _, _ in contacts]
        self.assertEqual(len(refs), len(set(refs)))              # each thing is listed once
        # With the first block destroyed, a real shot hits what the path listed next.
        battle.castles["right"].blocks[contacts[0][1]].take_damage(100)
        _, _, next_x, next_y = contacts[1]
        result = shot_result(play_shot(battle, 45, 76))
        self.assertAlmostEqual(result["x"], next_x, places=6)
        self.assertAlmostEqual(result["y"], next_y, places=6)

    def test_destroyed_blocks_and_defeated_characters_are_not_listed(self):
        battle = team_battle(OPEN)
        first = battle.path_contacts("left", 45, 81)[0]          # the right Knight
        self.assertEqual(first[:2], ("character", 0))
        battle.teams["right"].characters[0].take_damage(500)
        self.assertNotIn(("character", 0), [c[:2] for c in battle.path_contacts("left", 45, 81)])

    def test_the_right_side_path_is_the_mirror_image(self):
        battle = team_battle()
        for angle, power in self.AIMS:
            left = battle.path_contacts("left", angle, power)
            right = battle.path_contacts("right", angle, power)
            self.assertEqual([c[:2] for c in left], [c[:2] for c in right])
            for (_, _, lx, ly), (_, _, rx, ry) in zip(left, right):
                self.assertAlmostEqual(rx, 1280 - lx, places=6)
                self.assertAlmostEqual(ry, ly, places=6)

    def test_tracing_a_path_changes_nothing(self):
        battle = team_battle()
        battle.cannons["left"].adjust_angle(7)
        twin = copy.deepcopy(battle)
        for angle, power in self.AIMS:
            battle.path_contacts("left", angle, power)
            battle.path_contacts("right", angle, power)
        for side in ("left", "right"):
            self.assertEqual([b.hp for b in battle.castles[side].blocks],
                             [b.hp for b in twin.castles[side].blocks])
            self.assertEqual([c.hp for c in battle.teams[side].characters],
                             [c.hp for c in twin.teams[side].characters])
            self.assertEqual((battle.cannons[side].angle, battle.cannons[side].power),
                             (twin.cannons[side].angle, twin.cannons[side].power))
        self.assertEqual((battle.active_side, battle.projectile, battle.round_number),
                         (twin.active_side, twin.projectile, twin.round_number))
        self.assertEqual(battle.take_events(), twin.take_events())


class TurnTest(unittest.TestCase):
    def test_turns_alternate_left_right_left(self):
        battle = team_battle()
        self.assertEqual(battle.active_side, "left")
        events = play_shot(battle, 45, 50)
        self.assertEqual(only_event(events, "turn")["side"], "right")
        self.assertEqual(battle.active_side, "right")
        play_shot(battle, 45, 50)
        self.assertEqual(battle.active_side, "left")

    def test_turn_also_passes_after_a_miss(self):
        battle = team_battle()
        play_shot(battle, 45, 100)                            # off the screen
        self.assertEqual(battle.active_side, "right")

    def test_each_side_keeps_its_own_aim(self):
        battle = team_battle()
        play_shot(battle, 30, 40)                             # left aims and fires
        self.assertEqual((battle.cannons["right"].angle, battle.cannons["right"].power), (45, 50))
        play_shot(battle, 60, 70)                             # right aims and fires
        self.assertEqual((battle.cannons["left"].angle, battle.cannons["left"].power), (30, 40))


class RestartTest(unittest.TestCase):
    def test_reset_starts_a_fresh_match_with_the_same_cover(self):
        layouts = {"left": (0, 1, 4), "right": (2, 3, 6, 7)}
        battle = team_battle(layouts)
        for block in battle.castles["right"].blocks:
            block.take_damage(100)                            # all right cover destroyed
        battle.teams["right"].characters[0].take_damage(50)
        play_shot(battle, 30, 40)
        battle.cannons["right"].adjust_angle(10)

        battle.reset()

        self.assertIsNone(battle.winner)
        self.assertIsNone(battle.projectile)
        self.assertEqual(battle.active_side, "left")
        self.assertEqual(battle.take_events(), [])
        for side in ("left", "right"):
            castle = battle.castles[side]
            self.assertEqual(castle.layout, layouts[side])     # the same cover, rebuilt
            self.assertTrue(all(block.hp == 100 for block in castle.blocks))
            self.assertEqual((battle.cannons[side].angle, battle.cannons[side].power), (45, 50))
            self.assertTrue(all(c.hp == c.max_hp for c in battle.teams[side].characters))
            self.assertIs(battle.teams[side].castle, castle)

    def test_reset_while_a_shot_is_flying_cancels_it(self):
        battle = team_battle()
        battle.perform_action(0, "attack")
        for _ in range(10):
            battle.update()
        battle.reset()
        self.assertIsNone(battle.projectile)
        self.assertEqual(battle.active_side, "left")
        self.assertEqual(battle.take_events(), [])
        battle.update()                                       # nothing left to move or explode
        self.assertEqual(battle.take_events(), [])
        self.assertTrue(battle.perform_action(0, "attack"))


class EventTest(unittest.TestCase):
    def test_take_events_hands_each_event_over_once(self):
        battle = team_battle()
        battle.perform_action(0, "attack")
        self.assertEqual([e["type"] for e in battle.take_events()], ["action", "fire"])
        self.assertEqual(battle.take_events(), [])

    def test_events_wait_until_they_are_taken(self):
        battle = team_battle()
        battle.perform_action(0, "attack")
        while battle.projectile is not None:
            battle.update()
        types = [event["type"] for event in battle.take_events()]
        self.assertEqual(types, ["action", "fire", "explosion", "turn"])


class PygameIndependenceTest(unittest.TestCase):
    def test_logic_modules_do_not_import_pygame(self):
        # A fresh interpreter, so other tests can't have loaded pygame already.
        result = subprocess.run(
            [sys.executable, "-c", "import sys, castle, battle, characters, ai; print('pygame' in sys.modules)"],
            cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
