"""Tests for ai.py: the computer opponent (M3.1).

Run from the project root:  python -m unittest discover tests
Every AIController here gets a seed, so its "random" choices are the same on
every run and the tests are reproducible.
"""
import copy
import os
import re
import unittest

from ai import DIFFICULTY_SETTINGS, AIController, Plan
from battle import MAX_ANGLE, MAX_POWER, MAX_STEPS, MIN_ANGLE, MIN_POWER, Battle
from characters import ARCHETYPES, Archer, Engineer, Knight

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARMLESS = (80, 10)          # comes down beside the shooter's own cannon: no damage (see test_combat.py)


OPEN = {"left": (), "right": ()}   # no cover blocks


def combat(left, right, **options):
    return Battle(roster={"left": left, "right": right}, **options)


def fly(battle):
    """Run the shot in flight (if any) until it lands. Returns the events since the last call."""
    for _ in range(MAX_STEPS + 1):
        if battle.projectile is None:
            break
        battle.update()
    return battle.take_events()


def pass_turn(battle):
    """The active side fires a harmless shot, so the turn moves on with no damage."""
    cannon = battle.cannons[battle.active_side]
    cannon.adjust_angle(HARMLESS[0] - cannon.angle)
    cannon.adjust_power(HARMLESS[1] - cannon.power)
    team = battle.teams[battle.active_side]
    index = next(i for i, c in enumerate(team.characters) if c.is_alive())
    assert battle.perform_action(index, "attack")
    fly(battle)


def right_to_move(left, right, **options):
    """A battle in which the left team has just passed, so it is the right team's turn."""
    battle = combat(left, right, **options)
    pass_turn(battle)
    return battle


def snapshot(battle):
    """Everything an action could change (to check that choosing changes nothing)."""
    state = [battle.active_side, battle.round_number, battle.projectile, battle.winner]
    for side in ("left", "right"):
        state.append(battle.castles[side].total_hp())
        state.append((battle.cannons[side].angle, battle.cannons[side].power))
        for c in battle.teams[side].characters:
            state.append((c.hp, c.exp, c.level, c.is_defending, c.special_cooldown))
    return state


def check_plan_is_legal(test, battle, plan):
    """The plan names a living character of the active team, an allowed action and a legal aim."""
    test.assertIsNotNone(plan)
    test.assertNotIn("safety net", plan.reason)          # the AI's own choice was legal
    team = battle.teams[battle.active_side]
    test.assertTrue(team.characters[plan.actor_index].is_alive())
    test.assertIsNone(battle.why_not_allowed(plan.actor_index, plan.action))
    if plan.fires_a_shot():
        test.assertTrue(MIN_ANGLE <= plan.angle <= MAX_ANGLE, plan.angle)
        test.assertTrue(MIN_POWER <= plan.power <= MAX_POWER, plan.power)


def play(test, battle, controllers, max_rounds):
    """Play until the game ends or max_rounds have passed. Returns the number of AI turns.

    controllers maps a side to its AIController; a side without one passes every turn.
    Each AI turn must be accepted by the Battle: exactly one "action" event by that
    side, no "invalid" event, and a legal aim.
    """
    ai_turns = 0
    battle.take_events()
    while not battle.is_over() and battle.round_number <= max_rounds:
        side = battle.active_side
        if side not in controllers:
            pass_turn(battle)
            continue
        plan = controllers[side].take_turn(battle)
        test.assertIsNotNone(plan)
        test.assertNotIn("safety net", plan.reason)       # the AI's own choice was legal
        if plan.fires_a_shot():
            test.assertTrue(MIN_ANGLE <= plan.angle <= MAX_ANGLE and MIN_POWER <= plan.power <= MAX_POWER)
        events = fly(battle)
        test.assertEqual([e for e in events if e["type"] == "invalid"], [])
        test.assertEqual([e["side"] for e in events if e["type"] == "action"], [side])
        ai_turns += 1
    return ai_turns


class SetupTest(unittest.TestCase):
    def test_there_are_easy_normal_and_hard_with_the_same_settings(self):
        self.assertEqual(list(DIFFICULTY_SETTINGS), ["easy", "normal", "hard"])
        keys = [set(settings) for settings in DIFFICULTY_SETTINGS.values()]
        self.assertTrue(all(k == keys[0] for k in keys))

    def test_harder_levels_aim_better_and_choose_more_carefully(self):
        easy, normal, hard = (DIFFICULTY_SETTINGS[d] for d in ("easy", "normal", "hard"))
        for key in ("angle_error", "power_error", "top_choices"):
            self.assertGreater(easy[key], normal[key])
            self.assertGreater(normal[key], hard[key])
        self.assertGreater(hard["power_error"], 0)            # Hard is not perfectly accurate
        self.assertLess(easy["special_chance"], normal["special_chance"])
        self.assertLessEqual(normal["special_chance"], hard["special_chance"])

    def test_an_unknown_difficulty_is_rejected(self):
        with self.assertRaises(ValueError):
            AIController("right", "impossible")

    def test_the_ai_builds_a_legal_team_of_the_requested_size(self):
        for size in (1, 2, 3):
            for seed in range(8):
                team = AIController("right", "normal", seed=seed).pick_team(size)
                self.assertEqual(len(team), size)
                self.assertEqual(len(set(team)), size)               # no duplicate roles
                self.assertTrue(all(role in ARCHETYPES for role in team))
                combat([Knight, Archer, Engineer][:size], team)      # Battle accepts it

    def test_the_ai_module_does_not_import_pygame(self):
        with open(os.path.join(PROJECT_ROOT, "ai.py"), encoding="utf-8") as f:
            self.assertNotIn("import pygame", f.read())

    def test_the_ai_changes_the_battle_only_through_actions_and_aiming(self):
        # HP and cover blocks change only inside Battle.perform_action(), never from ai.py.
        with open(os.path.join(PROJECT_ROOT, "ai.py"), encoding="utf-8") as f:
            source = f.read()
        forbidden = [r"take_damage", r"take_hit", r"restore\(", r"\.repair\(", r"apply_blast",
                     r"\._hp", r"gain_exp", r"\.winner\s*=(?!=)", r"active_side\s*=(?!=)"]
        for pattern in forbidden:
            match = re.search(pattern, source)
            self.assertIsNone(match, f"ai.py contains {match.group(0) if match else ''!r}")


class TurnRulesTest(unittest.TestCase):
    def test_the_ai_only_acts_on_its_own_turn(self):
        battle = combat([Knight], [Archer])                      # left's turn
        ai = AIController("right", "hard", seed=1)
        before = snapshot(battle)
        self.assertIsNone(ai.choose(battle))
        self.assertIsNone(ai.take_turn(battle))
        self.assertEqual(snapshot(battle), before)

    def test_the_ai_waits_while_its_shot_flies(self):
        battle = right_to_move([Knight], [Archer])
        ai = AIController("right", "hard", seed=1)
        self.assertTrue(ai.take_turn(battle).fires_a_shot())     # Hard never defends when unhurt
        self.assertIsNotNone(battle.projectile)
        self.assertIsNone(ai.take_turn(battle))                  # the shot is still in the air
        self.assertIsNone(ai.choose(battle))

    def test_the_ai_does_nothing_after_the_game_has_ended(self):
        battle = right_to_move([Knight], [Archer])
        battle.teams["left"].characters[0].take_damage(140)
        battle.check_winner()                                    # right has won
        before = snapshot(battle)
        self.assertIsNone(AIController("right", "hard", seed=1).take_turn(battle))
        self.assertEqual(snapshot(battle), before)

    def test_choosing_changes_nothing_in_the_real_battle(self):
        battle = combat([Knight, Archer], [Archer, Engineer])
        battle.cannons["left"].adjust_angle(HARMLESS[0] - 45)
        battle.cannons["left"].adjust_power(HARMLESS[1] - 50)
        battle.perform_action(1, "attack")                       # left passes ...
        while battle.projectile is not None:
            battle.update()                                      # ... and its events stay unread
        battle.cannons["right"].adjust_angle(-7)
        twin = copy.deepcopy(battle)
        before = snapshot(battle)
        AIController("right", "normal", seed=3).choose(battle)
        self.assertEqual(snapshot(battle), before)
        self.assertEqual(battle.take_events(), twin.take_events())

    def test_take_turn_carries_out_the_plan_with_perform_action(self):
        battle = right_to_move([Knight], [Archer, Engineer])
        battle.take_events()
        plan = AIController("right", "hard", seed=2).take_turn(battle)
        events = fly(battle)
        action = [e for e in events if e["type"] == "action"]
        self.assertEqual(len(action), 1)
        self.assertEqual(action[0]["side"], "right")
        actor = battle.teams["right"].characters[plan.actor_index]
        self.assertEqual((action[0]["name"], action[0]["action"]), (actor.name, plan.action))
        if plan.fires_a_shot():                                   # the real cannon used the plan's aim
            cannon = battle.cannons["right"]
            self.assertEqual((cannon.angle, cannon.power), (plan.angle, plan.power))
        self.assertEqual(battle.active_side, "left")              # exactly one action, then left's turn


class CharacterChoiceTest(unittest.TestCase):
    def test_the_ai_only_chooses_living_characters(self):
        battle = right_to_move([Knight], [Archer, Engineer, Knight])
        archer, engineer, knight = battle.teams["right"].characters
        archer.take_damage(90)
        knight.take_damage(140)
        for difficulty in ("easy", "hard"):
            for seed in range(4):
                plan = AIController("right", difficulty, seed=seed).choose(battle)
                check_plan_is_legal(self, battle, plan)
                self.assertEqual(plan.actor_index, 1)             # the Engineer, the only survivor
                if difficulty == "hard":                          # unhurt Hard always attacks (so this
                    self.assertEqual(plan.action, "attack")       # is not the safety net's Defend)

    def test_an_impossible_plan_is_replaced_by_defend(self):
        battle = right_to_move([Knight], [Archer, Engineer])
        battle.teams["right"].characters[0].take_damage(90)        # the Archer is defeated
        ai = AIController("right", "hard", seed=0)
        ai.attack_plan = lambda battle, use_specials: Plan(0, "attack", 45, 70)   # a broken plan
        plan = ai.choose(battle)
        self.assertEqual((plan.actor_index, plan.action), (1, "defend"))
        self.assertIsNone(battle.why_not_allowed(plan.actor_index, plan.action))
        self.assertIn("safety net", plan.reason)

    def test_the_ai_respects_special_cooldowns(self):
        battle = right_to_move([Knight], [Archer])
        ai = AIController("right", "hard", seed=4)
        actions = []
        for _ in range(4):                                       # right's turns in rounds 1-4
            plan = ai.take_turn(battle)
            actions.append(plan.action)
            fly(battle)
            if battle.is_over():
                break
            pass_turn(battle)                                    # left
        self.assertEqual(actions[0], "special")                  # Power Shot: better than Attack
        self.assertEqual(actions[1:3], ["attack", "attack"])     # rounds 2 and 3: recharging
        self.assertEqual(actions[3], "special")                  # round 4 = 1 + 3: ready again

    def test_hard_repairs_badly_damaged_cover(self):
        battle = right_to_move([Knight], [Engineer])
        for block in battle.castles["right"].blocks:
            block.take_damage(50)                                # half of every block's HP is gone
        plan = AIController("right", "hard", seed=5).choose(battle)
        self.assertEqual((plan.actor_index, plan.action), (0, "special"))
        self.assertIn("Repair", plan.reason)

    def test_the_ai_never_tries_repair_when_nothing_is_damaged(self):
        battle = right_to_move([Knight], [Engineer])
        for seed in range(5):
            plan = AIController("right", "hard", seed=seed).choose(battle)
            self.assertNotEqual(plan.action, "special")


class DefensiveBehaviourTest(unittest.TestCase):
    """Course requirement: a character below 50 % HP makes the AI more likely to Defend."""

    def defend_rate(self, difficulty, hurt):
        battle = right_to_move([Knight], [Archer, Engineer])
        if hurt:
            battle.teams["right"].characters[1].take_damage(60)   # Engineer 50/110: below half
        team = battle.teams["right"]
        trials = 400
        defends = sum(AIController("right", difficulty, seed=seed).wants_to_defend(team)
                      for seed in range(trials))
        return defends / trials

    def test_a_character_below_half_hp_makes_defending_more_likely(self):
        for difficulty in DIFFICULTY_SETTINGS:
            healthy = self.defend_rate(difficulty, hurt=False)
            hurt = self.defend_rate(difficulty, hurt=True)
            self.assertGreater(hurt, healthy + 0.2, difficulty)
            settings = DIFFICULTY_SETTINGS[difficulty]
            self.assertAlmostEqual(healthy, settings["defend_chance"], delta=0.05)
            self.assertAlmostEqual(hurt, settings["hurt_defend_chance"], delta=0.07)

    def test_exactly_half_hp_is_not_below_half(self):
        battle = right_to_move([Knight], [Engineer])
        battle.teams["right"].characters[0].take_damage(55)      # 55 / 110 = exactly half
        team = battle.teams["right"]
        rate = sum(AIController("right", "hard", seed=s).wants_to_defend(team) for s in range(200)) / 200
        self.assertEqual(rate, DIFFICULTY_SETTINGS["hard"]["defend_chance"])

    def test_the_hurt_character_is_the_one_that_defends(self):
        battle = right_to_move([Knight], [Archer, Engineer])
        battle.teams["right"].characters[1].take_damage(70)       # the Engineer is hurt
        plans = [AIController("right", "normal", seed=s).choose(battle) for s in range(12)]
        defends = [p for p in plans if p.action == "defend"]
        self.assertTrue(defends)                                  # some seeds defend ...
        self.assertTrue(all(p.actor_index == 1 for p in defends))  # ... always with the Engineer
        self.assertTrue(all("below half" in p.reason for p in defends))

    def test_rally_protects_the_team_when_the_knight_can_use_it(self):
        battle = right_to_move([Archer], [Knight, Archer])
        battle.teams["right"].characters[1].take_damage(60)       # the Archer is hurt
        for seed in range(30):                                    # find a seed that plays defensively
            plan = AIController("right", "hard", seed=seed).choose(battle)
            if plan.defensive:
                break
        self.assertEqual((plan.actor_index, plan.action), (0, "special"))   # Knight's Rally
        self.assertIn("Rally", plan.reason)

    def test_the_ai_never_defends_two_turns_in_a_row(self):
        battle = right_to_move([Knight], [Archer, Engineer])
        battle.teams["right"].characters[0].take_damage(70)       # hurt all game long
        ai = AIController("right", "hard", seed=6)
        defensive = []
        for _ in range(8):
            plan = ai.take_turn(battle)
            defensive.append(plan.action == "defend" or "Rally" in plan.reason)
            fly(battle)
            if battle.is_over():
                break
            pass_turn(battle)
        self.assertIn(True, defensive)                            # it did defend sometimes
        for first, second in zip(defensive, defensive[1:]):
            self.assertFalse(first and second, defensive)


class AccuracyTest(unittest.TestCase):
    def hit_rate(self, difficulty, trials=20):
        """How often the AI's shots damage an enemy character. Block damage doesn't count,
        so the AI always aims at the left Knight (the field has no cover here)."""
        hits = shots = 0
        for seed in range(trials):
            battle = right_to_move([Knight], [Archer], layouts=OPEN)
            plan = AIController("right", difficulty, seed=seed).take_turn(battle)
            if not plan.fires_a_shot():
                continue                                          # Easy sometimes defends at random
            shots += 1
            explosions = [e for e in fly(battle) if e["type"] == "explosion"]
            hits += bool(explosions and explosions[0]["characters_hit"])
        self.assertGreaterEqual(shots, trials * 3 // 4)
        return hits / shots

    def test_hard_hits_more_often_than_easy(self):
        easy, hard = self.hit_rate("easy"), self.hit_rate("hard")
        self.assertGreater(hard, easy + 0.25, (easy, hard))
        self.assertLess(hard, 1.0, (easy, hard))                    # not perfectly accurate

    def test_only_targets_worth_something_are_listed(self):
        # Hitting only blocks doesn't help win (M3.4-A), so it is never a target.
        battle = right_to_move([Knight], [Archer])
        targets = AIController("right", "easy", seed=0).find_targets(battle, 0)
        self.assertTrue(targets)
        self.assertTrue(all(score > 0 for score, _, _, _ in targets))
        self.assertTrue(all("Knight" in description for _, _, _, description in targets))

    def test_hard_still_has_some_aiming_error(self):
        battle = right_to_move([Knight], [Archer], layouts=OPEN)
        aims = {(p.angle, p.power) for p in
                (AIController("right", "hard", seed=s).choose(battle) for s in range(8))}
        self.assertGreater(len(aims), 1)


class MatchTest(unittest.TestCase):
    """Whole matches: the AI must keep making progress until the game ends."""

    def test_ai_matches_finish_at_every_team_size_and_difficulty(self):
        for size, difficulty in ((1, "easy"), (2, "normal"), (3, "hard")):
            with self.subTest(size=size, difficulty=difficulty):
                battle = combat([Knight, Archer, Engineer][:size], [Archer, Engineer, Knight][:size])
                ai = AIController("right", difficulty, seed=size)
                play(self, battle, {"right": ai}, max_rounds=40)   # the left side only passes
                self.assertEqual(battle.winner, "right")

    def test_two_ais_can_play_a_whole_3v3_match(self):
        battle = combat([Knight, Archer, Engineer], [Archer, Engineer, Knight])
        controllers = {"left": AIController("left", "normal", seed=7),
                       "right": AIController("right", "hard", seed=8)}
        play(self, battle, controllers, max_rounds=40)
        self.assertTrue(battle.is_over())

    def test_a_new_match_forgets_the_last_defend(self):
        for seed in range(50):                                    # find a seed that defends
            battle = right_to_move([Knight], [Archer])
            battle.teams["right"].characters[0].take_damage(60)  # 30 / 90: below half
            ai = AIController("right", "hard", seed=seed)
            if ai.take_turn(battle).action == "defend":
                break
        team = battle.teams["right"]
        self.assertFalse(any(ai.wants_to_defend(team) for _ in range(30)))   # not twice in a row
        ai.new_match()
        self.assertTrue(any(ai.wants_to_defend(team) for _ in range(30)))


if __name__ == "__main__":
    unittest.main()
