"""Tests for ai.py: the computer opponent (M3.1).

Run from the project root:  python -m unittest discover tests
Every AIController here gets a seed, so its "random" choices are the same on
every run and the tests are reproducible.
"""
import copy
import os
import re
import time
import unittest

from ai import DIFFICULTY_SETTINGS, AIController, Plan, find_routes, imagine, scan_aims, shot_value
from battle import MAX_ANGLE, MAX_POWER, MAX_STEPS, MIN_ANGLE, MIN_POWER, ROUND_LIMIT, Battle
from castle import DEFAULT_LAYOUT, MAX_BLOCKS, layout_problem
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
        state.append([block.hp for block in battle.castles[side].blocks])
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


class LayoutChoiceTest(unittest.TestCase):
    """M3.4-B: the computer places its own cover, under the same rules as a player."""

    def test_the_ai_cover_is_legal_and_uses_at_most_the_budget(self):
        for difficulty in DIFFICULTY_SETTINGS:
            for seed in range(30):
                layout = AIController("right", difficulty, seed=seed).choose_layout()
                self.assertIsNone(layout_problem(layout), layout)
                self.assertLessEqual(len(layout), MAX_BLOCKS)
                self.assertEqual(layout, tuple(sorted(layout)))
                battle = combat([Knight], [Archer], layouts={"left": (), "right": layout})
                self.assertEqual(battle.castles["right"].total_hp(), 100 * len(layout))

    def test_the_ai_always_builds_the_tower_next_to_its_characters(self):
        for seed in range(30):
            layout = AIController("right", "normal", seed=seed).choose_layout()
            self.assertEqual(len(layout), MAX_BLOCKS)          # the whole budget, never more
            self.assertIn(0, layout)
            self.assertIn(4, layout)

    def test_the_same_seed_gives_the_same_cover(self):
        for seed in range(10):
            self.assertEqual(AIController("right", "hard", seed=seed).choose_layout(),
                             AIController("right", "hard", seed=seed).choose_layout())

    def test_different_seeds_give_different_covers(self):
        layouts = {AIController("right", "easy", seed=seed).choose_layout() for seed in range(40)}
        self.assertEqual(len(layouts), 6)                      # every possible tower layout appears


class CoverAwarenessTest(unittest.TestCase):
    """M3.4-B: the computer breaks cover only when the cover stands between it and a
    living enemy, and prefers hitting a character when it can."""

    def lone_knight(self, layout, attacker=Knight):
        """LEFT (the AI) attacks a lone RIGHT Knight hiding behind `layout`; LEFT moves first."""
        return combat([attacker], [Knight], layouts={"left": (), "right": layout})

    def test_routes_list_the_blocks_between_the_cannon_and_a_character(self):
        battle = self.lone_knight(DEFAULT_LAYOUT)
        routes = find_routes(battle, "left", scan_aims(battle, 0))
        self.assertTrue(routes)
        layout = battle.castles["right"].layout
        for target, blockers, value in routes:
            self.assertEqual(target, 0)                           # the Knight, the only enemy
            self.assertTrue(blockers)
            self.assertGreater(value, 0)
            self.assertNotIn(3, [layout[i] for i in blockers])    # the far column is never in the way

    def test_a_shot_that_only_hits_cover_in_nobodys_way_is_worth_nothing(self):
        battle = self.lone_knight((3, 7))                         # a tower by the enemy cannon
        scan = scan_aims(battle, 0)
        routes = find_routes(battle, "left", scan)
        cover_only = [(angle, power) for angle, power, trial, events in scan
                      if any(e["type"] == "explosion" and e["blocks_hit"] and not e["characters_hit"]
                             for e in events)]
        self.assertTrue(cover_only)
        for angle, power, trial, events in scan:
            if (angle, power) in cover_only:
                self.assertEqual(shot_value(battle, trial, "left", routes), 0, (angle, power))

    def test_with_an_open_shot_the_ai_attacks_the_character(self):
        battle = self.lone_knight((3, 7))                         # the Knight stands in the open
        for difficulty in DIFFICULTY_SETTINGS:
            for seed in range(3):
                plan = AIController("left", difficulty, seed=seed).choose(battle)
                if plan.fires_a_shot():
                    self.assertEqual(plan.goal, "damage", plan.reason)
                    self.assertIn("RIGHT Knight", plan.reason)

    def test_when_the_character_is_protected_the_ai_breaks_the_cover_in_front_of_it(self):
        battle = self.lone_knight(DEFAULT_LAYOUT)
        plan = AIController("left", "hard", seed=1).choose(battle)
        self.assertEqual(plan.goal, "cover", plan.reason)
        self.assertIn("cover in front of the RIGHT Knight", plan.reason)
        # Carried out without aiming error, the planned shot damages a block that is in the way.
        routes = find_routes(battle, "left", scan_aims(battle, 0))
        in_the_way = {i for _, blockers, _ in routes for i in blockers}
        trial, _ = imagine(battle, plan.actor_index, plan.action, plan.angle, plan.power)
        damaged = {i for i, block in enumerate(trial.castles["right"].blocks)
                   if block.hp < battle.castles["right"].blocks[i].hp}
        self.assertTrue(damaged & in_the_way, (damaged, in_the_way))

    def test_once_the_cover_is_broken_the_ai_goes_for_the_character(self):
        battle = self.lone_knight(DEFAULT_LAYOUT)
        for block in battle.castles["right"].blocks:
            block.take_damage(100)                                # every block destroyed
        plan = AIController("left", "hard", seed=1).choose(battle)
        self.assertEqual(plan.goal, "damage", plan.reason)

    def test_the_ai_reaches_and_defeats_a_protected_character_in_time(self):
        # LEFT (the AI) against a lone Knight behind the full default cover that never shoots back.
        # Easy too since M3.4-B.1 (it won in all 20 seeds tried, in 12-27 rounds).
        for difficulty in DIFFICULTY_SETTINGS:
            with self.subTest(difficulty=difficulty):
                battle = combat([Knight], [Knight], layouts={"left": (), "right": DEFAULT_LAYOUT})
                ai = AIController("left", difficulty, seed=11)
                plans = []
                while not battle.is_over():
                    if battle.active_side == "left":
                        plans.append(ai.take_turn(battle))
                        fly(battle)
                    else:
                        pass_turn(battle)
                self.assertEqual(battle.winner, "left")
                self.assertLess(battle.round_number, ROUND_LIMIT)
                # Never a turn spent on nothing: every shot aimed at a character or at cover in its way.
                for plan in plans:
                    if plan.fires_a_shot():
                        self.assertIn(plan.goal, ("damage", "cover"), plan.reason)
                        self.assertGreater(plan.score, 0, plan.reason)

    def test_every_team_size_and_cover_gives_a_legal_plan(self):
        for size in (1, 2, 3):
            for layout in ((), DEFAULT_LAYOUT, (0, 1, 2, 4, 5, 6)):
                with self.subTest(size=size, layout=layout):
                    battle = right_to_move([Knight, Archer, Engineer][:size], [Archer, Engineer, Knight][:size],
                                           layouts={"left": layout, "right": layout})
                    for difficulty in DIFFICULTY_SETTINGS:
                        plan = AIController("right", difficulty, seed=size).choose(battle)
                        check_plan_is_legal(self, battle, plan)


class DecisionTimeTest(unittest.TestCase):
    def test_a_decision_takes_well_under_two_seconds(self):
        # A generous bound so slow machines pass too; typical times are in the M3.4-B report.
        battle = right_to_move([Knight, Archer, Engineer], [Archer, Engineer, Knight])
        for difficulty in DIFFICULTY_SETTINGS:
            start = time.perf_counter()
            AIController("right", difficulty, seed=0).choose(battle)
            self.assertLess(time.perf_counter() - start, 2.0, difficulty)


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

    def test_each_level_hits_more_often_than_the_one_below(self):
        # M3.4-B.1 made Easy more accurate; it must still clearly miss more than Normal.
        easy, normal, hard = (self.hit_rate(d, trials=40) for d in ("easy", "normal", "hard"))
        self.assertGreater(normal, easy + 0.05, (easy, normal, hard))
        self.assertGreater(hard, normal + 0.05, (easy, normal, hard))
        self.assertGreater(hard, easy + 0.25, (easy, normal, hard))
        self.assertLess(hard, 1.0, (easy, normal, hard))            # not perfectly accurate

    def test_only_targets_worth_something_are_listed(self):
        # A target is a hit on a character or on cover in front of one (M3.4-B); nothing else.
        battle = right_to_move([Knight], [Archer])
        targets = AIController("right", "easy", seed=0).find_targets(battle, 0)
        self.assertTrue(targets)
        self.assertTrue(all(score > 0 for score, _, _, _, _ in targets))
        self.assertTrue(all("LEFT Knight" in description for _, _, _, description, _ in targets))
        self.assertEqual(targets, sorted(targets, key=lambda target: target[0], reverse=True))

    def test_hard_still_has_some_aiming_error(self):
        battle = right_to_move([Knight], [Archer], layouts=OPEN)
        aims = {(p.angle, p.power) for p in
                (AIController("right", "hard", seed=s).choose(battle) for s in range(8))}
        self.assertGreater(len(aims), 1)


def play_easy_mirror(seed, first):
    """One seeded Easy-vs-Easy 3 v 3 match in which each AI picks its team and places its cover.

    Returns a record: how it ended, the rounds played, every plan, the longest run of
    consecutive shots by one side that damaged nothing at all (no character, no block),
    the slowest turn in seconds, and any turn the Battle refused or that broke a rule.
    """
    ais = {side: AIController(side, "easy", seed=100 * seed + (side == "right")) for side in ("left", "right")}
    battle = combat(ais["left"].pick_team(3), ais["right"].pick_team(3),
                    layouts={side: ai.choose_layout() for side, ai in ais.items()}, first_side=first)
    record = {"plans": [], "longest_harmless_run": 0, "slowest": 0.0, "problems": []}
    runs = {"left": 0, "right": 0}
    battle.take_events()
    while not battle.is_over():
        side = battle.active_side
        enemy = "right" if side == "left" else "left"
        before = ([c.hp for c in battle.teams[enemy].characters], [b.hp for b in battle.castles[enemy].blocks])
        start = time.perf_counter()
        plan = ais[side].take_turn(battle)
        record["slowest"] = max(record["slowest"], time.perf_counter() - start)
        events = fly(battle)
        if (plan is None or "safety net" in plan.reason or any(e["type"] == "invalid" for e in events)
                or [e["side"] for e in events if e["type"] == "action"] != [side]):
            record["problems"].append((battle.round_number, side, plan and plan.reason))
            break
        record["plans"].append((side, plan.actor_index, plan.action, plan.angle, plan.power))
        if plan.fires_a_shot():
            after = ([c.hp for c in battle.teams[enemy].characters], [b.hp for b in battle.castles[enemy].blocks])
            runs[side] = runs[side] + 1 if after == before else 0
            record["longest_harmless_run"] = max(record["longest_harmless_run"], runs[side])
    record["end"], record["rounds"] = battle.end_reason, battle.round_number
    return record


class EasyPacingTest(unittest.TestCase):
    """M3.4-B.1: Easy may miss a lot, but two Easy AIs behind their own cover must usually
    finish a 3 v 3 match by eliminating a team before the round limit, and never spend
    long runs of turns on shots that hit nothing.

    The 12 matches (seeds 0-5, each first mover) are played once, here. Single matches often
    end near round 30, so a handful can't tell "about 40 %" (Easy before M3.4-B.1) from
    "about 85 %" (now). With at least 8 of 12 required, this test fails by chance about 4 % of
    the time for the current Easy and passes by chance about 6 % of the time for the old one.
    The larger seeded benchmark behind the Easy settings is in docs/M0_design.md."""

    MATCHES = [(seed, first) for seed in range(6) for first in ("left", "right")]

    @classmethod
    def setUpClass(cls):
        cls.records = [play_easy_mirror(seed, first) for seed, first in cls.MATCHES]

    def test_every_easy_turn_is_legal_and_every_match_ends_by_the_round_limit(self):
        for record in self.records:
            self.assertEqual(record["problems"], [])
            self.assertIn(record["end"], ("elimination", "timeout", "both_lost"))
            self.assertLessEqual(record["rounds"], ROUND_LIMIT)

    def test_most_easy_mirror_matches_end_in_an_elimination(self):
        eliminations = [record["end"] == "elimination" for record in self.records]
        self.assertGreaterEqual(sum(eliminations), 8, [(r["end"], r["rounds"]) for r in self.records])

    def test_easy_never_fires_a_long_run_of_shots_that_hit_nothing(self):
        for record in self.records:
            self.assertLessEqual(record["longest_harmless_run"], 6)

    def test_the_same_seeds_replay_the_same_easy_match(self):
        seed, first = self.MATCHES[0]
        self.assertEqual(play_easy_mirror(seed, first)["plans"], self.records[0]["plans"])

    def test_every_easy_decision_is_quick(self):
        # A generous bound so slow machines pass too; measured times are in docs/M0_design.md.
        for record in self.records:
            self.assertLess(record["slowest"], 2.0)


class MatchTest(unittest.TestCase):
    """Whole matches: the AI must keep making progress until the game ends."""

    def test_ai_matches_finish_at_every_team_size_and_difficulty(self):
        for size, difficulty in ((1, "easy"), (2, "normal"), (3, "hard")):
            with self.subTest(size=size, difficulty=difficulty):
                battle = combat([Knight, Archer, Engineer][:size], [Archer, Engineer, Knight][:size])
                ai = AIController("right", difficulty, seed=size)
                play(self, battle, {"right": ai}, max_rounds=40)   # the left side only passes
                self.assertEqual(battle.winner, "right")

    def test_ai_matches_end_at_every_level_size_and_first_side_with_ai_placed_cover(self):
        # M3.4-B: each AI picks its team and places its own cover. Every match must end by the
        # round limit (an elimination or the timeout draw), with every AI turn legal (play()).
        for index, difficulty in enumerate(DIFFICULTY_SETTINGS):
            for size in (1, 2, 3):
                first = ("left", "right")[(size + index) % 2]      # every level moves first on both sides
                with self.subTest(difficulty=difficulty, size=size, first=first):
                    ais = {side: AIController(side, difficulty, seed=10 * size + index + (side == "right"))
                           for side in ("left", "right")}
                    battle = combat(ais["left"].pick_team(size), ais["right"].pick_team(size),
                                    layouts={side: ai.choose_layout() for side, ai in ais.items()},
                                    first_side=first)
                    play(self, battle, ais, max_rounds=ROUND_LIMIT + 1)
                    self.assertTrue(battle.is_over())
                    self.assertIn(battle.end_reason, ("elimination", "timeout", "both_lost"))
                    self.assertLessEqual(battle.round_number, ROUND_LIMIT)
                    if difficulty == "hard":
                        self.assertEqual(battle.end_reason, "elimination")

    def test_an_ai_match_that_reaches_the_round_limit_is_a_draw_and_the_ai_stops(self):
        battle = combat([Knight], [Knight])
        while battle.round_number < ROUND_LIMIT:                  # both sides defend until round 30
            battle.perform_action(0, "defend")
        ais = {side: AIController(side, "hard", seed=4) for side in ("left", "right")}
        play(self, battle, ais, max_rounds=ROUND_LIMIT)           # one round: nobody can fall in it
        self.assertEqual((battle.winner, battle.end_reason), ("draw", "timeout"))
        self.assertIsNone(ais[battle.active_side].take_turn(battle))

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
