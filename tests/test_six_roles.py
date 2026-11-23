"""Tests for M6.3: six roles (Gunner, Bombardier and Medic join Knight, Archer and Engineer).

Run from the project root:  python -m unittest discover tests

The rules tests (characters, battle, animation, ai) use only the standard library. The aims
below were found with the real engine (Battle.path_contacts and the real step()) in an open field
(no cover), with the RIGHT team Knight, Archer, Engineer in slots 0, 1, 2:

    VOLLEY_ON_FRONT    57 deg / 85: all three Triple Volley shells hit the front character directly
    AIRBURST_ON_FRONT  20 deg / 100: after the split, shells 3-5 hit the front character directly and
                       shells 1-2 land on the ground in front of it

A splitting shell can't reach anything of the enemy before the top of its arc in a real match: the
farthest top is x 959 from the LEFT cannon and the RIGHT cover starts at x 980. So the tests for a
shell that hits something before it splits move the shell there by hand.
"""
import math
import unittest
import unittest.mock

import test_main
from test_playability import PlayabilityTestCase, frames, key
from ai import AIController, heal_value, team_hp
from animation import fires_the_cannon
from battle import (DT, EXP_FOR_DEFEAT, EXP_FOR_HIT, EXP_FOR_SUPPORT_SPECIAL, GRAVITY, MAX_ANGLE, MAX_POWER,
                    MAX_STEPS, MIN_ANGLE, MIN_POWER, SPEED_PER_POWER, Battle, Projectile)
from castle import BLOCK_SIZE, COLUMN_X, DEFAULT_LAYOUT, slot_position
from characters import (ARCHETYPES, Archer, Bombardier, Character, Engineer, Gunner, Knight, Medic, ShotDamage,
                        calculate_damage)

pygame = test_main.pygame
if pygame is not None:
    import drawing
    import main

OPEN = {"left": (), "right": ()}
VOLLEY_ON_FRONT = (57, 85)
AIRBURST_ON_FRONT = (20, 100)
FRONT_THREE = [Knight, Archer, Engineer]


def combat(left, right, **options):
    return Battle(roster={"left": left, "right": right}, **options)


def aim(battle, side, angle, power):
    cannon = battle.cannons[side]
    cannon.adjust_angle(angle - cannon.angle)
    cannon.adjust_power(power - cannon.power)


def fly(battle):
    """Run every shell in flight until the attack is over. Returns the events since the last call."""
    for _ in range(2 * MAX_STEPS):
        if not battle.projectiles:
            break
        battle.update()
    return battle.take_events()


def launch_aim(shell):
    """(angle, power) a shell was launched with, read from its speed (gravity's change to the vertical
    speed in the steps it has already flown is taken back first)."""
    vy = shell.vy - GRAVITY * DT * shell.steps
    speed = math.hypot(shell.vx, vy)
    return round(math.degrees(math.atan2(-vy, abs(shell.vx)))), round(speed / SPEED_PER_POWER)


def of_type(events, kind):
    return [event for event in events if event["type"] == kind]


# ----- characters.py ---------------------------------------------------------------------

class NewRoleStatsTest(unittest.TestCase):
    def test_each_new_role_starts_with_the_design_numbers(self):
        # role, HP, ATK, DEF, block damage of a normal Attack, special, cooldown (docs/M6.3_six_role_design.md)
        table = [(Gunner, 115, 35, 7, 50, "Triple Volley", 3),
                 (Bombardier, 100, 32, 6, 50, "Airburst", 4),
                 (Medic, 105, 28, 6, 45, "Field Dressing", 4)]
        for role, hp, atk, defense, block, special, cooldown in table:
            with self.subTest(role=role.__name__):
                character = role(role.__name__, "left")
                self.assertIsInstance(character, Character)
                self.assertEqual((character.hp, character.max_hp, character.atk, character.defense),
                                 (hp, hp, atk, defense))
                self.assertEqual(character.attack_shot().block_damage, block)
                self.assertEqual((character.SPECIAL_NAME, character.SPECIAL_COOLDOWN), (special, cooldown))

    def test_there_are_six_roles_and_the_first_three_keep_their_order(self):
        self.assertEqual(ARCHETYPES, [Knight, Archer, Engineer, Gunner, Bombardier, Medic])

    def test_a_class_attribute_says_how_many_shells_each_special_fires(self):
        shells = {Knight: 0, Archer: 1, Engineer: 0, Gunner: 3, Bombardier: 5, Medic: 0}
        for role, count in shells.items():
            with self.subTest(role=role.__name__):
                self.assertEqual(role.SPECIAL_SHELLS, count)

    def test_every_role_has_a_short_special_description(self):
        for role in ARCHETYPES:
            with self.subTest(role=role.__name__):
                self.assertLessEqual(len(role.SPECIAL_DESCRIPTION), 66)


class TripleVolleyTest(unittest.TestCase):
    def test_the_special_is_three_light_shells_in_a_fixed_fan(self):
        message, shot = Gunner("Gunner", "left").use_special(None)
        self.assertIn("Triple Volley", message)
        self.assertEqual((shot.block_damage, shot.multiplier, shot.ignores_def, shot.blast_radius),
                         (18, 0.60, False, 32))
        self.assertEqual(shot.spread, ((-6, -4), (0, 0), (6, 4)))
        self.assertIsNone(shot.split)

    def test_one_shell_does_the_designed_damage(self):
        # 35 x 0.6 = 21, minus DEF: a Knight loses 9 per shell (27 for three), an Archer 17 (51).
        self.assertEqual(calculate_damage(35, Knight.BASE_DEF, False, Gunner.VOLLEY_MULTIPLIER), 9)
        self.assertEqual(calculate_damage(35, Archer.BASE_DEF, False, Gunner.VOLLEY_MULTIPLIER), 17)
        self.assertEqual(calculate_damage(35, Archer.BASE_DEF, True, Gunner.VOLLEY_MULTIPLIER), 8)


class AirburstTest(unittest.TestCase):
    def test_the_special_is_one_shell_that_splits_into_five(self):
        message, shot = Bombardier("Bombardier", "left").use_special(None)
        self.assertIn("Airburst", message)
        self.assertEqual((shot.block_damage, shot.multiplier, shot.ignores_def, shot.blast_radius),
                         (16, 0.45, False, 24))
        self.assertEqual(shot.spread, ((0, 0),))
        self.assertEqual(shot.split, (0.76, 0.88, 1.00, 1.12, 1.24))

    def test_one_small_shell_does_the_designed_damage(self):
        # 32 x 0.45 = 14 (rounded down), minus DEF: a Knight loses 2 per shell (10 for five), an Archer 10 (50).
        self.assertEqual(calculate_damage(32, Knight.BASE_DEF, False, Bombardier.AIRBURST_MULTIPLIER), 2)
        self.assertEqual(calculate_damage(32, Archer.BASE_DEF, False, Bombardier.AIRBURST_MULTIPLIER), 10)

    def test_a_normal_attack_is_still_one_plain_shell(self):
        shot = Bombardier("Bombardier", "left").attack_shot()
        self.assertEqual((shot.spread, shot.split, shot.blast_radius), (((0, 0),), None, None))


class HealTest(unittest.TestCase):
    def test_heal_never_goes_above_max_hp_and_says_how_much(self):
        archer = Archer("Archer", "left")
        archer.take_damage(10)
        self.assertEqual(archer.heal(32), 10)
        self.assertEqual(archer.hp, archer.max_hp)
        self.assertEqual(archer.heal(5), 0)

    def test_heal_never_revives(self):
        archer = Archer("Archer", "left")
        archer.take_damage(archer.hp)
        self.assertEqual(archer.heal(32), 0)
        self.assertFalse(archer.is_alive())

    def test_negative_heal_is_rejected(self):
        with self.assertRaises(ValueError):
            Archer("Archer", "left").heal(-1)


class FieldDressingTest(unittest.TestCase):
    def team(self, *roles):
        battle = combat(list(roles), [Knight])
        return battle.teams["left"]

    def medic_of(self, team):
        return next(c for c in team.characters if isinstance(c, Medic))

    def test_an_ally_gains_up_to_32_and_the_medic_itself_up_to_24(self):
        team = self.team(Medic, Knight)
        medic, knight = team.characters
        knight.take_damage(80)
        self.assertEqual(medic.heal_target(team), (knight, 32))
        medic.take_damage(50)
        knight.heal(80)
        self.assertEqual(medic.heal_target(team), (medic, 24))

    def test_it_picks_the_character_that_really_gains_most(self):
        team = self.team(Medic, Knight, Archer)
        medic, knight, archer = team.characters
        knight.take_damage(80)               # could gain 32
        archer.take_damage(20)               # could gain only 20
        medic.take_damage(60)                # could gain only 24 (itself)
        self.assertEqual(medic.heal_target(team), (knight, 32))

    def test_a_tie_goes_to_another_ally_then_to_slot_order(self):
        team = self.team(Medic, Knight, Archer)
        medic, knight, archer = team.characters
        medic.take_damage(24)
        archer.take_damage(24)               # both gain 24: the ally, not the Medic
        self.assertEqual(medic.heal_target(team), (archer, 24))
        knight.take_damage(24)               # two allies gain 24: the earlier slot
        self.assertEqual(medic.heal_target(team), (knight, 24))

    def test_a_defeated_ally_is_never_a_target(self):
        team = self.team(Medic, Archer)
        medic, archer = team.characters
        archer.take_damage(archer.hp)
        self.assertIsNone(medic.heal_target(team))
        self.assertIn("nothing to heal", medic.special_blocked_reason(team))

    def test_with_everyone_at_full_hp_it_is_blocked_and_says_why(self):
        team = self.team(Medic, Knight)
        medic = team.characters[0]
        self.assertIsNone(medic.heal_target(team))
        self.assertFalse(medic.can_use_special(team))
        self.assertIn("full HP", medic.special_blocked_reason(team))

    def test_the_heal_is_exactly_the_preview(self):
        team = self.team(Archer, Medic)
        archer, medic = team.characters
        archer.take_damage(26)
        target, amount = medic.heal_target(team)
        message, shot = medic.use_special(team)
        self.assertIsNone(shot)
        self.assertEqual((target, amount, archer.hp), (archer, 26, archer.max_hp))
        self.assertIn(f"{archer.name} +26 HP", message)

    def test_the_cooldown_still_blocks_first(self):
        team = self.team(Medic, Knight)
        medic, knight = team.characters
        knight.take_damage(50)
        medic.start_cooldown()
        self.assertIn("recharging", medic.special_blocked_reason(team))


# ----- battle.py: one attack, several shells -----------------------------------------------

class VolleyLaunchTest(unittest.TestCase):
    def test_a_normal_attack_still_fires_one_shell(self):
        battle = combat([Gunner], [Knight], layouts=OPEN)
        battle.perform_action(0, "attack")
        self.assertEqual(len(battle.projectiles), 1)
        self.assertIs(battle.projectile, battle.projectiles[0])     # the old name still reads the shell

    def test_three_shells_leave_together_around_the_aim(self):
        battle = combat([Gunner], [Knight], layouts=OPEN)
        aim(battle, "left", 50, 70)
        battle.perform_action(0, "special")
        self.assertEqual([launch_aim(shell) for shell in battle.projectiles], [(44, 66), (50, 70), (56, 74)])
        self.assertEqual(len({(shell.x, shell.y) for shell in battle.projectiles}), 1)   # all from the muzzle

    def test_each_shell_stays_inside_the_legal_aim(self):
        battle = combat([Gunner], [Knight], layouts=OPEN)
        aim(battle, "left", MAX_ANGLE, MAX_POWER)
        battle.perform_action(0, "special")
        self.assertEqual([launch_aim(shell) for shell in battle.projectiles],
                         [(MAX_ANGLE - 6, MAX_POWER - 4), (MAX_ANGLE, MAX_POWER), (MAX_ANGLE, MAX_POWER)])
        battle = combat([Gunner], [Knight], layouts=OPEN)
        aim(battle, "left", MIN_ANGLE, MIN_POWER)
        battle.perform_action(0, "special")
        self.assertEqual([launch_aim(shell) for shell in battle.projectiles],
                         [(MIN_ANGLE, MIN_POWER), (MIN_ANGLE, MIN_POWER), (MIN_ANGLE + 6, MIN_POWER + 4)])

    def test_the_right_team_fires_the_mirror_image(self):
        left = combat([Gunner], [Gunner], layouts=OPEN)
        right = combat([Gunner], [Gunner], layouts=OPEN, first_side="right")
        for battle, side in ((left, "left"), (right, "right")):
            aim(battle, side, 50, 70)
            battle.perform_action(0, "special")
        for a, b in zip(left.projectiles, right.projectiles):
            self.assertEqual((round(a.vx, 6), round(a.vy, 6)), (round(-b.vx, 6), round(b.vy, 6)))
            self.assertEqual(a.x, 1280 - b.x)


class OneAttackOneSettlementTest(unittest.TestCase):
    def volley(self, *, defending=False):
        battle = combat([Gunner], FRONT_THREE, layouts=OPEN)
        if defending:
            battle.teams["right"].characters[0].defend()
        battle.take_events()
        aim(battle, "left", *VOLLEY_ON_FRONT)
        battle.perform_action(0, "special")
        return battle

    def test_the_turn_waits_for_the_last_shell(self):
        battle = self.volley()
        explosions = 0
        while battle.projectiles:
            self.assertFalse(battle.can_fire())
            self.assertEqual(battle.active_side, "left")
            battle.update()
            explosions += len(of_type(battle._events, "explosion"))
            if battle.projectiles:
                self.assertEqual(of_type(battle._events, "turn"), [])
        events = battle.take_events()
        self.assertEqual(len(of_type(events, "explosion")), 3)
        self.assertEqual(battle.active_side, "right")
        self.assertTrue(battle.can_fire())

    def test_one_action_one_fire_one_exp_one_turn(self):
        battle = self.volley()
        events = battle.take_events() + fly(battle)
        counts = {kind: len(of_type(events, kind)) for kind in ("action", "special", "fire", "exp", "turn")}
        self.assertEqual(counts, {"action": 1, "special": 1, "fire": 1, "exp": 1, "turn": 1})
        self.assertEqual(of_type(events, "exp")[0]["amount"], EXP_FOR_HIT)          # three hits, one award
        self.assertEqual(battle.teams["left"].characters[0].special_cooldown, Gunner.SPECIAL_COOLDOWN)

    def test_three_direct_hits_on_one_knight_do_27(self):
        battle = self.volley()
        events = fly(battle)
        explosions = of_type(events, "explosion")
        self.assertEqual([e["kind"] for e in explosions], ["character"] * 3)
        self.assertEqual([e["radius"] for e in explosions], [32] * 3)
        self.assertEqual([[hit["damage"] for hit in e["characters_hit"]] for e in explosions], [[9]] * 3)
        knight = battle.teams["right"].characters[0]
        self.assertEqual(knight.hp, knight.max_hp - 27)
        self.assertEqual([c.hp for c in battle.teams["right"].characters[1:]], [Archer.BASE_HP, Engineer.BASE_HP])

    def test_defend_halves_every_shell(self):
        battle = self.volley(defending=True)
        fly(battle)
        knight = battle.teams["right"].characters[0]
        self.assertEqual(knight.hp, knight.max_hp - 3 * 4)          # 9 // 2 = 4 per shell

    def test_cover_guard_halves_each_shells_block_damage(self):
        battle = combat([Gunner], [Knight], layouts={"left": (), "right": DEFAULT_LAYOUT})
        battle.teams["right"].characters[0].defend()                 # Cover Guard on the RIGHT cover
        aim(battle, "left", 45, 83)                                  # the first shell hits the cover
        battle.perform_action(0, "special")
        block_hits = [e for e in of_type(fly(battle), "explosion") if e["blocks_hit"]]
        self.assertTrue(block_hits)
        for event in block_hits:
            self.assertTrue(event["guarded"])
            self.assertEqual(event["damage"], 9 * event["blocks_hit"])

    def test_a_defeat_counts_once_and_the_game_ends_after_the_last_shell(self):
        battle = combat([Bombardier], [Archer], layouts=OPEN)
        archer = battle.teams["right"].characters[0]
        archer.take_damage(archer.hp - 5)                            # one small shell (10) defeats it
        aim(battle, "left", *AIRBURST_ON_FRONT)
        battle.perform_action(0, "special")
        battle.take_events()
        defeated_while_flying = False
        while battle.projectiles:
            battle.update()
            if not archer.is_alive() and battle.projectiles:
                defeated_while_flying = True
                self.assertIsNone(battle.winner)                    # not before the last shell
        events = battle.take_events()
        self.assertTrue(defeated_while_flying)
        defeats = [hit for e in of_type(events, "explosion") for hit in e["characters_hit"] if hit["defeated"]]
        self.assertEqual(len(defeats), 1)
        self.assertEqual(of_type(events, "exp")[0]["amount"], EXP_FOR_HIT + EXP_FOR_DEFEAT)
        self.assertEqual(len(of_type(events, "game_over")), 1)
        self.assertEqual(battle.winner, "left")

    def test_a_later_shell_flies_through_a_block_an_earlier_one_destroyed_this_frame(self):
        battle = combat([Gunner], [Knight], layouts={"left": (), "right": DEFAULT_LAYOUT})
        battle.perform_action(0, "special")
        battle.take_events()
        raised = next(b for b in battle.castles["right"].blocks if (b.x, b.y) == slot_position("right", 4))
        raised.take_damage(raised.hp - 10)                           # one 18-damage shell destroys it
        first, second, _ = battle.projectiles
        for shell in (first, second):                                # just above it, falling straight down
            shell.x, shell.y, shell.vx, shell.vy = raised.x + 16, raised.y - 0.5, 0.0, 60.0
        battle.update()
        explosions = of_type(battle.take_events(), "explosion")
        self.assertEqual(len(explosions), 1)                         # only the first shell exploded
        self.assertTrue(raised.is_destroyed())
        self.assertNotIn(first, battle.projectiles)
        self.assertIn(second, battle.projectiles)                    # still falling, through the gap

    def test_a_rematch_forgets_every_shell(self):
        battle = self.volley()
        battle.update()
        battle.reset()
        self.assertEqual(battle.projectiles, [])
        self.assertIsNone(battle.projectile)
        self.assertTrue(battle.can_fire())


class AirburstFlightTest(unittest.TestCase):
    def launch(self, right=FRONT_THREE, layouts=OPEN, angle_power=AIRBURST_ON_FRONT):
        battle = combat([Bombardier], right, layouts=layouts)
        aim(battle, "left", *angle_power)
        battle.perform_action(0, "special")
        battle.take_events()
        return battle

    def test_one_marked_shell_leaves_the_cannon(self):
        battle = self.launch()
        self.assertEqual(len(battle.projectiles), 1)
        self.assertEqual(battle.projectiles[0].split, Bombardier.AIRBURST_SPLIT)

    def test_it_splits_into_five_when_it_starts_to_come_down(self):
        battle = self.launch()
        mother = battle.projectiles[0]
        while battle.projectiles == [mother]:
            rising = mother.vy < 0
            battle.update()
            if battle.projectiles == [mother]:
                self.assertTrue(rising or mother.vy < 0)
        splits = of_type(battle.take_events(), "split")
        self.assertEqual(len(splits), 1)
        self.assertEqual((splits[0]["x"], splits[0]["y"], splits[0]["shells"]), (mother.x, mother.y, 5))
        shells = battle.projectiles
        self.assertNotIn(mother, shells)                              # the marked shell is gone
        self.assertEqual(len(shells), 5)
        self.assertGreaterEqual(mother.vy, 0)
        for shell, factor in zip(shells, Bombardier.AIRBURST_SPLIT):
            self.assertEqual((shell.x, shell.y, shell.vy), (mother.x, mother.y, mother.vy))
            self.assertAlmostEqual(shell.vx, mother.vx * factor)
            self.assertIsNone(shell.split)                            # small shells never split again

    def test_three_small_shells_on_the_front_knight_do_6_and_the_exp_comes_once(self):
        battle = self.launch()
        events = fly(battle)
        explosions = of_type(events, "explosion")
        self.assertEqual([e["kind"] for e in explosions].count("character"), 3)
        self.assertEqual(len(explosions), 5)
        self.assertEqual({e["radius"] for e in explosions}, {24})
        knight = battle.teams["right"].characters[0]
        self.assertEqual(knight.hp, knight.max_hp - 3 * 2)
        self.assertEqual([e["amount"] for e in of_type(events, "exp")], [EXP_FOR_HIT])
        self.assertEqual(len(of_type(events, "turn")), 1)

    def test_a_hit_before_the_split_counts_as_one_small_shell(self):
        battle = self.launch(right=[Knight], layouts={"left": (), "right": DEFAULT_LAYOUT})
        mother = battle.projectiles[0]
        block = next(b for b in battle.castles["right"].blocks if (b.x, b.y) == slot_position("right", 3))
        mother.x, mother.y, mother.vx, mother.vy = block.x - 2, block.y + 12, 300.0, -60.0   # rising into its side
        events = fly(battle)
        explosions = of_type(events, "explosion")
        self.assertEqual(of_type(events, "split"), [])
        self.assertEqual(len(explosions), 1)
        self.assertEqual((explosions[0]["kind"], explosions[0]["radius"], explosions[0]["damage"]), ("block", 24, 16))
        self.assertEqual(block.hp, block.max_hp - 16)
        self.assertEqual([e["amount"] for e in of_type(events, "exp")], [EXP_FOR_HIT])
        self.assertEqual(battle.active_side, "right")

    def test_leaving_the_field_before_the_split_is_a_miss(self):
        battle = self.launch(right=[Knight])
        mother = battle.projectiles[0]
        mother.x, mother.y, mother.vx, mother.vy = 1278.0, 300.0, 300.0, -200.0
        events = fly(battle)
        self.assertEqual([e["type"] for e in events if e["type"] in ("split", "explosion", "miss")], ["miss"])
        self.assertEqual(of_type(events, "exp"), [])
        self.assertEqual(battle.active_side, "right")

    def test_the_path_dots_still_follow_one_shell(self):
        # Classic Aim's dots are the centre shell's path, whoever fires (main.py labels them so).
        battle = combat([Bombardier], [Knight], layouts=OPEN)
        aim(battle, "left", 50, 70)
        cannon = battle.cannons["left"]
        shell = Projectile(cannon.x, cannon.y, 50, 70, "left")
        for _ in range(4):
            shell.step()
        self.assertEqual(battle.preview_path("left", 24, 4)[0], (shell.x, shell.y))


class FieldDressingBattleTest(unittest.TestCase):
    def test_it_heals_at_once_reports_the_heal_and_ends_the_turn(self):
        battle = combat([Medic, Archer], [Knight], layouts=OPEN)
        archer = battle.teams["left"].characters[1]
        archer.take_damage(26)
        battle.take_events()
        self.assertTrue(battle.perform_action(0, "special"))
        events = battle.take_events()
        self.assertEqual(battle.projectiles, [])
        self.assertEqual(of_type(events, "heal"), [{"type": "heal", "side": "left", "name": archer.name,
                                                    "amount": 26}])
        self.assertEqual(of_type(events, "exp")[0]["amount"], EXP_FOR_SUPPORT_SPECIAL)
        self.assertEqual(battle.active_side, "right")
        self.assertEqual(archer.hp, archer.max_hp)

    def test_it_is_refused_when_nobody_needs_it(self):
        battle = combat([Medic, Archer], [Knight], layouts=OPEN)
        self.assertIn("nothing to heal", battle.why_not_allowed(0, "special"))
        self.assertFalse(battle.perform_action(0, "special"))


# ----- animation.py ------------------------------------------------------------------------

class FiresTheCannonTest(unittest.TestCase):
    def test_volley_and_airburst_go_to_the_cannon_field_dressing_does_not(self):
        self.assertTrue(fires_the_cannon(Gunner("G", "left"), "special"))
        self.assertTrue(fires_the_cannon(Bombardier("B", "left"), "special"))
        self.assertFalse(fires_the_cannon(Medic("M", "left"), "special"))
        for role in ARCHETYPES:
            self.assertTrue(fires_the_cannon(role("X", "left"), "attack"))
            self.assertFalse(fires_the_cannon(role("X", "left"), "defend"))


# ----- ai.py -------------------------------------------------------------------------------

def play_ai_match(difficulty, seed, left, right, first="left"):
    """A seeded AI-vs-AI match (the same loop as the M6.3 baseline). Returns the plans and the end."""
    battle = combat(left, right, first_side=first)
    ais = {side: AIController(side, difficulty, seed=seed + (side == "right")) for side in ("left", "right")}
    plans = []
    while not battle.is_over():
        plan = ais[battle.active_side].take_turn(battle)
        plans.append((plan.actor_index, plan.action, plan.angle, plan.power))
        fly(battle)
    hp = [c.hp for side in ("left", "right") for c in battle.teams[side].characters]
    return plans, battle.winner, battle.end_reason, battle.round_number, hp


class OriginalRolesDecideAsBeforeTest(unittest.TestCase):
    """Recorded with the code as it was before M6.3 (scratch script, same loop as play_ai_match):
    with only Knight, Archer and Engineer, every decision and the result must stay the same."""

    HARD = ([(1, 'special', 59, 86), (0, 'special', 61, 90), (0, 'special', None, None),
             (1, 'special', None, None), (1, 'attack', 61, 90), (0, 'attack', 60, 87), (1, 'special', 59, 86),
             (0, 'special', 61, 86), (1, 'attack', 59, 88), (0, 'attack', 59, 88), (1, 'attack', 61, 88),
             (1, 'attack', 60, 90)], "left", "elimination", 6, [0, 53, 0, 0])
    EASY_FIRST = [(0, 'attack', 59, 91), (0, 'attack', 56, 83), (0, 'attack', 59, 89), (0, 'attack', 56, 87),
                  (0, 'attack', 62, 85), (0, 'attack', 59, 92), (0, 'attack', 57, 85), (0, 'attack', 62, 88),
                  (0, 'attack', 56, 84), (0, 'defend', None, None), (0, 'attack', 30, 86), (0, 'attack', 27, 88)]
    NORMAL_FIRST = [(1, 'special', 57, 96), (2, 'special', 62, 84), (2, 'special', None, None),
                    (2, 'attack', 60, 88), (1, 'attack', 57, 92), (1, 'attack', 58, 92), (1, 'special', 62, 84),
                    (0, 'special', None, None), (1, 'attack', 61, 86), (0, 'attack', 57, 90),
                    (2, 'special', None, None), (0, 'attack', 63, 92)]

    def test_hard_two_v_two(self):
        self.assertEqual(play_ai_match("hard", 3, [Archer, Engineer], [Knight, Archer], "right"), self.HARD)

    def test_easy_one_v_one(self):
        plans, winner, reason, rounds, hp = play_ai_match("easy", 5, [Engineer], [Archer])
        self.assertEqual((plans[:12], len(plans), winner, reason, rounds, hp),
                         (self.EASY_FIRST, 17, "left", "elimination", 9, [96, 0]))

    def test_normal_three_v_three(self):
        plans, winner, reason, rounds, hp = play_ai_match("normal", 7, [Knight, Archer, Engineer],
                                                          [Engineer, Knight, Archer])
        self.assertEqual((plans[:12], len(plans), winner, reason, rounds, hp),
                         (self.NORMAL_FIRST, 59, "left", "elimination", 30, [55, 0, 0, 0, 0, 0]))


class NewRolesAITest(unittest.TestCase):
    def test_the_computer_picks_from_all_six_roles(self):
        seen = set()
        for seed in range(30):
            team = AIController("right", "normal", seed=seed).pick_team(3)
            self.assertEqual(len(set(team)), 3)
            seen.update(team)
        self.assertEqual(seen, set(ARCHETYPES))

    def test_heal_value_is_the_mirror_of_damage_progress(self):
        battle = combat([Knight], [Medic, Archer], layouts=OPEN)
        archer = battle.teams["right"].characters[1]
        archer.take_damage(60)
        self.assertAlmostEqual(heal_value(battle, "right", 32), 32 / (105 + 30))
        self.assertEqual(team_hp(battle.teams["right"]), 135)

    def test_heal_plan_names_the_target_or_is_none_at_full_hp(self):
        battle = combat([Knight], [Medic, Archer], layouts=OPEN, first_side="right")
        ai = AIController("right", "hard", seed=1)
        self.assertIsNone(ai.heal_plan(battle))
        archer = battle.teams["right"].characters[1]
        archer.take_damage(60)
        plan = ai.heal_plan(battle)
        self.assertEqual((plan.actor_index, plan.action, plan.goal, plan.angle), (0, "special", "heal", None))
        self.assertAlmostEqual(plan.score, 32 / 135)
        self.assertIn("Archer", plan.reason)

    def test_the_computer_heals_a_badly_hurt_ally_when_that_is_worth_more(self):
        healed = 0
        for seed in range(12):
            battle = combat([Knight], [Medic, Archer], first_side="right")
            battle.teams["right"].characters[1].take_damage(70)          # Archer 20 / 90
            plan = AIController("right", "hard", seed=seed).choose(battle)
            self.assertIsNone(battle.why_not_allowed(plan.actor_index, plan.action))
            healed += plan.goal == "heal"
        self.assertGreater(healed, 0)

    def test_hard_fires_a_triple_volley_over_the_default_cover(self):
        # Measured: behind the default cover, Hard rates the volley above an Attack for every seed,
        # because rated over its power error one of the three shells still hits.
        for seed in range(4):
            battle = combat([Knight, Archer], [Gunner, Engineer], first_side="right")
            plan = AIController("right", "hard", seed=seed).take_turn(battle)
            self.assertEqual((plan.actor_index, plan.action), (0, "special"))
            self.assertIn("Triple Volley", plan.reason)
            self.assertEqual(len(battle.projectiles), 3)

    def test_every_plan_with_a_volley_or_airburst_ready_is_legal(self):
        for role in (Gunner, Bombardier):
            for seed in range(6):
                battle = combat([Archer, Medic], [role, Engineer], first_side="right")
                plan = AIController("right", ("easy", "normal", "hard")[seed % 3], seed=seed).take_turn(battle)
                self.assertIsNotNone(plan)
                self.assertNotIn("safety net", plan.reason)
                self.assertEqual(of_type(fly(battle), "invalid"), [])

    def test_with_a_spread_ready_each_option_is_rated_over_the_power_error(self):
        battle = combat([Knight], [Gunner], first_side="right")
        ai = AIController("right", "normal", seed=0)            # power error 4: powers 66, 70 and 74
        exact = [ai.option_value(battle, [], 0, "special", 50, power, averaged=False) for power in (66, 70, 74)]
        self.assertAlmostEqual(ai.option_value(battle, [], 0, "special", 50, 70, averaged=True),
                               sum(exact) / len(exact))

    def test_matches_with_the_new_roles_end_legally_at_every_level(self):
        for index, difficulty in enumerate(("easy", "normal", "hard")):
            with self.subTest(difficulty=difficulty):
                left, right = [Gunner, Medic, Bombardier], [Bombardier, Knight, Medic]
                battle = combat(left, right, first_side=("left", "right")[index % 2])
                ais = {side: AIController(side, difficulty, seed=20 + index + (side == "right"))
                       for side in ("left", "right")}
                while not battle.is_over():
                    side = battle.active_side
                    battle.take_events()
                    plan = ais[side].take_turn(battle)
                    self.assertIsNotNone(plan)
                    self.assertNotIn("safety net", plan.reason)
                    events = fly(battle)
                    self.assertEqual(of_type(events, "invalid"), [])
                    if plan.action == "special" and isinstance(battle.teams[side].characters[plan.actor_index],
                                                               Medic):
                        self.assertTrue(of_type(events, "heal") or of_type(events, "game_over"))
                self.assertIn(battle.end_reason, ("elimination", "timeout", "both_lost"))


def until(game, condition, limit=900):
    """Run frames until condition() is true (at most `limit` frames, so a missing feature fails
    instead of hanging)."""
    for _ in range(limit):
        if condition():
            return
        game.update()
    raise AssertionError("it never happened")


# ----- main.py: local two-player keys (docs/M6.2_playability_brief.md, rework) -------------------

def press(game, key_code, mods=0):
    """A key press through the real event path, held down (no release)."""
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key_code, mod=mods))


def release(game, key_code):
    game.handle_event(pygame.event.Event(pygame.KEYUP, key=key_code, mod=0))


@unittest.skipIf(pygame is None, "Pygame is not installed")
class TwoPlayerKeysTest(PlayabilityTestCase):
    def aim_of(self, side):
        cannon = self.game.battle.cannons[side]
        return cannon.angle, cannon.power

    def test_left_aims_with_w_s_d_a_and_fires_with_f(self):
        self.start([Knight], [Archer])
        for code, mods in ((pygame.K_w, 0), (pygame.K_w, pygame.KMOD_SHIFT), (pygame.K_s, 0),
                           (pygame.K_d, pygame.KMOD_SHIFT), (pygame.K_a, 0)):
            press(self.game, code, mods)                              # Shift: 5 at a time, as before
        self.assertEqual(self.aim_of("left"), (45 + 1 + 5 - 1, 50 + 5 - 1))
        for code in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_SPACE, pygame.K_RETURN):
            key(self.game, code)                                      # RIGHT's keys and SPACE do nothing
        self.assertEqual(self.aim_of("left"), (50, 54))
        self.assertFalse(self.game.cannon_run.is_busy())
        key(self.game, pygame.K_f)
        self.assertTrue(self.game.cannon_run.is_busy())

    def test_right_aims_with_the_arrows_left_adds_power_and_enter_fires(self):
        self.start([Knight], [Archer])
        self.click(self.game.action_buttons["defend"].rect)            # LEFT passes
        press(self.game, pygame.K_UP, pygame.KMOD_SHIFT)
        key(self.game, pygame.K_LEFT)                                  # toward the middle: more power
        key(self.game, pygame.K_LEFT)
        key(self.game, pygame.K_RIGHT)                                 # toward its own edge: less
        self.assertEqual(self.aim_of("right"), (50, 51))
        for code in (pygame.K_w, pygame.K_s, pygame.K_d, pygame.K_a, pygame.K_f, pygame.K_SPACE):
            key(self.game, code)
        self.assertEqual(self.aim_of("right"), (50, 51))
        self.assertEqual(self.aim_of("left"), (45, 50))
        self.assertFalse(self.game.cannon_run.is_busy())
        key(self.game, pygame.K_RETURN)
        self.assertTrue(self.game.cannon_run.is_busy())

    def test_the_same_power_still_gives_mirror_image_shots(self):
        self.start([Knight], [Archer])
        for _ in range(10):
            key(self.game, pygame.K_d)
        fired = []
        for fire_key, power_key in ((pygame.K_f, None), (pygame.K_RETURN, pygame.K_LEFT)):
            for _ in range(10 if power_key else 0):
                key(self.game, power_key)
            key(self.game, fire_key)
            until(self.game, lambda: self.game.battle.projectile is not None)
            shell = self.game.battle.projectile
            fired.append((round(shell.vx, 6), round(shell.vy, 6), shell.steps))
            test_main.finish_shot(self.game)
        (vx, vy, steps), (right_vx, right_vy, right_steps) = fired
        self.assertEqual((vx, vy, steps), (-right_vx, right_vy, right_steps))

    def test_held_enter_confirms_only_one_setup_screen(self):
        for enter in (pygame.K_RETURN, pygame.K_KP_ENTER):
            with self.subTest(enter=enter):
                self.game = main.Game(self.screen, ai_seed=1)
                self.pick_teams([Knight], [Archer])
                press(self.game, enter)
                self.assertEqual((self.game.state, self.game.placing), ("cover", "left"))
                press(self.game, enter)
                self.assertEqual((self.game.state, self.game.placing), ("cover", "left"))

                release(self.game, enter)
                press(self.game, enter)
                self.assertEqual((self.game.state, self.game.placing), ("cover", "right"))
                press(self.game, enter)
                self.assertEqual((self.game.state, self.game.placing), ("cover", "right"))
                self.assertIsNone(self.game.battle)

                release(self.game, enter)
                press(self.game, enter)
                self.assertEqual(self.game.state, "battle")
                self.click(self.game.action_buttons["defend"].rect)
                self.assertEqual(self.game.battle.active_side, "right")
                press(self.game, enter)
                self.assertFalse(self.game.cannon_run.is_busy())
                release(self.game, enter)
                press(self.game, enter)
                self.assertTrue(self.game.cannon_run.is_busy())

    def test_a_fire_key_held_from_the_last_turn_or_the_cover_screen_never_fires(self):
        self.pick_teams([Knight], [Archer])
        self.click(self.game.start_button.rect)
        self.click(self.game.confirm_button.rect)
        press(self.game, pygame.K_RETURN)                             # Enter confirms RIGHT's cover ...
        self.assertEqual(self.game.state, "battle")
        press(self.game, pygame.K_f)                                  # LEFT fires and keeps F down
        test_main.finish_shot(self.game)
        press(self.game, pygame.K_RETURN)                             # ... and is still held: no shot
        self.assertFalse(self.game.cannon_run.is_busy())
        release(self.game, pygame.K_RETURN)
        press(self.game, pygame.K_RETURN)                             # a new press fires
        self.assertTrue(self.game.cannon_run.is_busy())
        test_main.finish_shot(self.game)
        press(self.game, pygame.K_f)                                  # F was never let go
        self.assertFalse(self.game.cannon_run.is_busy())
        release(self.game, pygame.K_f)
        press(self.game, pygame.K_f)
        self.assertTrue(self.game.cannon_run.is_busy())

    def test_against_the_computer_the_arrow_keys_and_space_stay(self):
        self.start_vs_ai([Knight])
        key(self.game, pygame.K_UP)
        key(self.game, pygame.K_RIGHT)
        key(self.game, pygame.K_w)
        key(self.game, pygame.K_d)
        key(self.game, pygame.K_f)
        self.assertEqual(self.aim_of("left"), (46, 51))
        self.assertFalse(self.game.cannon_run.is_busy())
        key(self.game, pygame.K_SPACE)
        self.assertTrue(self.game.cannon_run.is_busy())

    def test_the_panel_names_the_keys_of_the_team_to_move(self):
        self.start([Knight], [Archer])
        self.assertEqual(self.game.aim_labels(), ("ANGLE · W/S", "POWER · drag or D+ / A−"))
        self.assertEqual(self.game.action_buttons["attack"].note, "key F")
        self.assertIn("ATTACK (or F)", self.game.action_help("attack"))
        self.click(self.game.action_buttons["defend"].rect)
        self.assertEqual(self.game.aim_labels(), ("ANGLE · Up/Down", "POWER · drag or Left+ / Right−"))
        self.assertEqual(self.game.action_buttons["attack"].note, "key Enter")
        self.check_panel_fits("right team keys")
        self.game = main.Game(self.screen, ai_seed=1)
        self.start_vs_ai([Knight])
        self.assertEqual(self.game.aim_labels(), ("ANGLE · Up/Down", "POWER · drag or Left/Right"))
        self.assertEqual(self.game.action_buttons["attack"].note, "key SPACE")

    def test_reflex_right_locks_its_swing_with_enter(self):
        self.start([Knight], [Archer], aim_mode="reflex")
        self.click(self.game.action_buttons["defend"].rect)
        frames(self.game, 25)
        angle = self.game.battle.cannons["right"].angle
        key(self.game, pygame.K_RETURN)
        self.assertEqual(self.game.locked_shot.angle, angle)
        self.assertEqual(self.game.aim_labels()[0], "ANGLE")

    def check_panel_fits(self, situation):
        with self.subTest(situation=situation):
            for name, rects in self.game.panel_text_rects().items():
                for rect in rects:
                    self.assertTrue(main.PANEL_GROUPS[name].contains(rect), (name, rect))
            self.game.draw()


# ----- main.py: six cards per team ---------------------------------------------------------------

@unittest.skipIf(pygame is None, "Pygame is not installed")
class SixCardSelectionTest(PlayabilityTestCase):
    def test_each_team_shows_six_cards_in_three_columns_and_two_rows(self):
        for side in ("left", "right"):
            rects = [self.game.card_rects[(side, role)] for role in ARCHETYPES]
            self.assertEqual(len({rect.left for rect in rects}), 3)
            self.assertEqual(len({rect.top for rect in rects}), 2)
            self.assertEqual([rect.topleft for rect in rects], sorted((r.topleft for r in rects),
                                                                       key=lambda p: (p[1], p[0])))
        groups = {side: [rect for (s, _), rect in self.game.card_rects.items() if s == side]
                  for side in ("left", "right")}
        left, right = (groups[side][0].unionall(groups[side]) for side in ("left", "right"))
        self.assertEqual((left.top, left.height, left.width), (right.top, right.height, right.width))
        self.assertEqual(left.left, main.WINDOW_WIDTH - right.right)            # the two groups mirror

    def test_nothing_on_the_selection_screen_overlaps_and_all_of_it_fits(self):
        for vs_ai in (True, False):
            self.click(self.game.mode_buttons["ai" if vs_ai else "pvp"].rect)
            for role in (Medic, Gunner, Knight):
                self.click(self.game.card_rects[("left", role)])
            with self.subTest(vs_ai=vs_ai):
                rects = (list(self.game.card_rects.values())
                         + [self.game.roster_info_rect(side) for side in ("left", "right")]
                         + [self.game.team_title_rect(side) for side in ("left", "right")]
                         + [self.game.aim_description_rect(), self.game.selection_message_rect(),
                            self.game.start_button.rect]
                         + [b.rect for b in self.game.size_buttons] + [b.rect for b in self.game.aim_buttons.values()])
                window = pygame.Rect(0, 0, main.WINDOW_WIDTH, main.WINDOW_HEIGHT)
                for i, rect in enumerate(rects):
                    self.assertTrue(window.contains(rect), rect)
                    self.assertEqual(rect.collidelist(rects[i + 1:]), -1, (rect, rects[i + 1:]))
                self.game.draw()

    def test_each_card_keeps_its_words_above_its_band(self):
        for (side, role), rect in self.game.card_rects.items():
            with self.subTest(side=side, role=role.__name__):
                band = self.game.card_band_rect(rect)
                self.assertTrue(rect.contains(band))
                self.assertLessEqual(self.game.card_text_bottom(role, rect), band.top)
                for text_rect in self.game.card_text_rects(role, rect):
                    self.assertTrue(rect.contains(text_rect), (text_rect, rect))

    def test_the_pick_order_is_the_slot_order(self):
        self.click(self.game.size_buttons[2].rect)
        for role in (Medic, Gunner, Knight):
            self.click(self.game.card_rects[("left", role)])
        self.assertEqual(self.game.selection.picks["left"], [Medic, Gunner, Knight])
        self.assertEqual([self.game.card_state_text("left", role) for role in (Medic, Gunner, Knight)],
                         ["Slot 1 · front", "Slot 2", "Slot 3"])
        self.assertIn("LEFT TEAM   3/3 chosen", self.game.team_title("left"))

    def test_the_roster_info_explains_the_picks_or_the_card_under_the_mouse(self):
        self.click(self.game.size_buttons[2].rect)
        for role in (Bombardier, Medic, Gunner):
            self.click(self.game.card_rects[("left", role)])
        lines = self.game.roster_info_lines("left", (0, 0))
        self.assertEqual(len(lines), 3)
        for slot, (line, role) in enumerate(zip(lines, (Bombardier, Medic, Gunner)), start=1):
            self.assertTrue(line.startswith(f"{slot} {role.__name__} · {role.SPECIAL_NAME}"), line)
            self.assertIn(role.SPECIAL_DESCRIPTION, line)
        hovered = self.game.roster_info_lines("left", self.game.card_rects[("left", Archer)].center)
        self.assertIn(Archer.SPECIAL_DESCRIPTION, " ".join(hovered))
        self.assertIn("computer", " ".join(self.game.roster_info_lines("right", (0, 0))))
        for side in ("left", "right"):
            box = self.game.roster_info_rect(side)
            for rect in self.game.roster_info_text_rects(side, (0, 0)):
                self.assertTrue(box.contains(rect), (rect, box))

    def test_the_six_portraits_and_figures_all_differ(self):
        portraits = {pygame.image.tostring(drawing.card_portrait(role, 1), "RGBA") for role in ARCHETYPES}
        self.assertEqual(len(portraits), 6)
        figures = set()
        for role in ARCHETYPES:
            surface = pygame.Surface((40, 50), pygame.SRCALPHA)
            drawing.draw_figure(surface, role, 20, 4, 1, drawing.TEAM_COLORS["left"], "left")
            figures.add(pygame.image.tostring(surface, "RGBA"))
        self.assertEqual(len(figures), 6)


# ----- main.py: the new specials in a match --------------------------------------------------------

@unittest.skipIf(pygame is None, "Pygame is not installed")
class NewSpecialsInGameTest(PlayabilityTestCase):
    def record_events(self):
        seen, show = [], self.game.show_event

        def spy(event):
            seen.append(event)
            show(event)
        self.game.show_event = spy
        return seen

    def test_the_special_buttons_are_named_after_the_skill_and_fit(self):
        self.start([Gunner, Bombardier, Medic], [Knight, Archer, Engineer])
        for index, name in enumerate(("TRIPLE VOLLEY", "AIRBURST", "FIELD DRESSING")):
            self.game.select_actor(index)
            self.game.refresh_buttons()
            button = self.game.action_buttons["special"]
            self.assertEqual(button.label, name)
            self.assertLessEqual(self.game.button_font(button).size(name)[0], button.rect.width - 10)
            self.game.draw()

    def test_field_dressing_shows_who_and_how_much_and_heals_exactly_that(self):
        self.start([Medic, Archer], [Knight, Engineer])
        archer = self.game.battle.teams["left"].characters[1]
        archer.take_damage(26)
        self.game.refresh_buttons()
        self.assertEqual(self.game.action_help("special"), "Heal LEFT Archer · +26 HP · ends turn")
        self.assertEqual(self.game.action_buttons["special"].note, "Archer +26")
        with self.hover(self.game.action_buttons["special"].rect.center):
            self.assertEqual(self.game.action_hint_lines(), ["Heal LEFT Archer · +26 HP · ends turn"])
        self.click(self.game.action_buttons["special"].rect)
        self.assertEqual(archer.hp, archer.max_hp)
        self.assertIn("+26", [floater[2] for floater in self.game.floaters])
        self.assertEqual(self.game.battle.active_side, "right")
        self.game.draw()

    def test_field_dressing_is_greyed_out_with_everyone_at_full_hp(self):
        self.start([Medic, Archer], [Knight, Engineer])
        self.game.refresh_buttons()
        button = self.game.action_buttons["special"]
        self.assertFalse(button.enabled)
        self.assertEqual(button.note, "all full HP")
        self.assertIn("nothing to heal", self.game.action_help("special"))

    def test_a_triple_volley_is_one_run_three_shells_and_one_turn(self):
        self.start([Gunner], [Knight])
        events = self.record_events()
        test_main.aim(self.game, 50, 70)
        self.click(self.game.action_buttons["special"].rect)
        until(self.game, lambda: self.game.battle.projectile is not None)
        self.assertEqual(len(self.game.battle.projectiles), 3)
        self.game.update()
        self.assertEqual(len(self.game.trails), 3)                           # one trail per shell
        self.game.draw()
        test_main.finish_shot(self.game)
        self.assertEqual([e["type"] for e in events].count("fire"), 1)
        self.assertEqual([e["type"] for e in events].count("turn"), 1)
        self.assertTrue(self.game.message.startswith("TRIPLE VOLLEY · "), self.game.message)
        self.assertEqual(self.game.last_result, self.game.message)

    def test_an_airburst_shows_a_marked_shell_a_flash_and_five_shells(self):
        self.start([Bombardier], [Knight])
        test_main.aim(self.game, 50, 70)
        self.click(self.game.action_buttons["special"].rect)
        until(self.game, lambda: self.game.battle.projectile is not None)
        self.assertIsNotNone(self.game.battle.projectile.split)               # the marked shell
        self.game.draw()
        until(self.game, lambda: len(self.game.battle.projectiles) != 1)
        self.assertEqual(len(self.game.battle.projectiles), 5)
        self.assertEqual(len(self.game.split_flashes), 1)
        self.assertIn("splits into 5", " ".join(self.game.log))
        self.game.draw()
        x, y, _ = self.game.split_flashes[0]
        self.assertIn(drawing.FLASH_COLOR, self.colours_near((x + 6, y)) | self.colours_near((x - 6, y)))
        test_main.finish_shot(self.game)
        self.assertTrue(self.game.message.startswith("AIRBURST · "), self.game.message)

    def test_each_explosion_grows_to_its_shells_own_blast(self):
        self.start([Gunner], [Knight])
        test_main.aim(self.game, 50, 70)
        self.click(self.game.action_buttons["special"].rect)
        until(self.game, lambda: self.game.explosions)
        self.assertEqual(self.game.explosions[0][3], Gunner.VOLLEY_BLAST_RADIUS)

    def test_a_rematch_during_a_volley_clears_every_shell_and_effect(self):
        self.start([Bombardier], [Knight])
        test_main.aim(self.game, 50, 70)
        self.click(self.game.action_buttons["special"].rect)
        until(self.game, lambda: len(self.game.battle.projectiles) >= 5)
        self.game.update()
        test_main.restart_with_r(self.game)        # M6.4: R asks first; R again restarts
        self.game.update()
        self.assertEqual((self.game.battle.projectiles, self.game.trails, self.game.split_flashes,
                          self.game.explosions, self.game.attack_events), ([], {}, [], [], []))
        self.assertTrue(self.game.battle.can_fire())

    def test_classic_dots_are_labelled_as_the_center_shell_for_a_spread(self):
        self.start([Gunner, Knight], [Knight, Archer])
        self.assertTrue(self.game.path_points())
        self.assertEqual(self.game.path_label(), "center shell")
        self.assertIn("The dots show the center shell", self.game.action_help("special"))
        self.game.draw()
        self.game.select_actor(1)
        self.assertIsNone(self.game.path_label())
        self.assertEqual(self.game.hint_icon(), 0)
        self.game.select_actor(0)
        self.assertEqual(self.game.hint_icon(), 3)

    def test_reflex_locks_the_volley_angle_once(self):
        self.start([Gunner], [Knight], aim_mode="reflex")
        frames(self.game, 40)
        self.assertIn("It locks the swinging angle once", self.game.action_help("special"))
        angle = self.game.battle.cannons["left"].angle
        self.click(self.game.action_buttons["special"].rect)
        self.assertEqual(self.game.locked_shot.angle, angle)
        until(self.game, lambda: self.game.battle.projectile is not None)
        aims = [launch_aim(shell)[0] for shell in self.game.battle.projectiles]
        self.assertEqual(aims, [max(5, angle - 6), angle, min(80, angle + 6)])
        self.assertEqual(self.game.locked_shot.angle, angle)                 # still the one lock

    def test_long_names_stay_clear_of_the_cover(self):
        # "Bombardier" is the longest name; in the front slot its plate moves outward, off the cover.
        self.start([Bombardier, Engineer, Medic], [Bombardier, Gunner, Knight])
        for side in ("left", "right"):
            for index in range(3):
                plate = self.game.label_plate_rect(side, index)
                if side == "left":
                    self.assertLessEqual(plate.right, min(COLUMN_X["left"]))
                else:
                    self.assertGreaterEqual(plate.left, max(COLUMN_X["right"]) + BLOCK_SIZE)
        self.game.draw()

    def test_the_computer_plays_the_new_roles_through_the_game_loop(self):
        self.game = main.Game(self.screen, ai_seed=3)
        self.click(self.game.difficulty_buttons["hard"].rect)
        with unittest.mock.patch.object(AIController, "pick_team", return_value=[Gunner, Medic]):
            self.start_vs_ai([Knight, Archer])
        events = self.record_events()
        for _ in range(6):                                       # six turns: LEFT defends, the computer acts
            if self.game.state != "battle":
                break
            if self.game.battle.active_side == "left" and self.game.battle.can_fire():
                test_main.pass_turn(self.game)
            for _ in range(800):
                if self.game.battle.active_side == "left" and not self.game.controls_locked():
                    break
                self.game.update()
            self.game.draw()
        fires = [e for e in events if e["type"] == "fire" and e["side"] == "right"]
        self.assertTrue(fires)
        self.assertEqual([e for e in events if e["type"] == "invalid"], [])
        self.assertTrue(any(line.startswith("AI (Hard): ") for line in self.game.log))


@unittest.skipIf(pygame is None, "Pygame is not installed")
class AttackSummaryTest(unittest.TestCase):
    def explosion(self, kind, hits=(), covered=(), blocks=0, damage=0):
        return {"type": "explosion", "kind": kind, "characters_hit": list(hits), "covered": list(covered),
                "blocks_hit": blocks, "damage": damage}

    def test_one_shell_reads_as_before(self):
        event = self.explosion("character", [{"name": "Archer", "damage": 26, "defeated": False}])
        self.assertEqual(main.attack_summary([event]), "DIRECT HIT · Archer -26 HP")

    def test_several_shells_are_added_up_under_the_special_name(self):
        events = [self.explosion("character", [{"name": "Knight", "damage": 9, "defeated": False}]),
                  self.explosion("character", [{"name": "Knight", "damage": 9, "defeated": False}]),
                  {"type": "miss"}]
        self.assertEqual(main.attack_summary(events, name="TRIPLE VOLLEY"),
                         "TRIPLE VOLLEY · 2 direct, 1 out · Knight -18 HP")

    def test_cover_only_and_shielded_and_destroyed(self):
        events = [self.explosion("block", covered=["Archer"], blocks=2, damage=32),
                  self.explosion("ground"), self.explosion("block", blocks=1, damage=16)]
        self.assertEqual(main.attack_summary(events, destroyed=1, name="AIRBURST"),
                         "AIRBURST · 2 cover, 1 ground · Archer shielded, 1 block destroyed")
        events = [self.explosion("block", blocks=2, damage=32), self.explosion("ground")]
        self.assertEqual(main.attack_summary(events, name="AIRBURST"), "AIRBURST · 1 cover, 1 ground · cover -32 HP")


if __name__ == "__main__":
    unittest.main()
