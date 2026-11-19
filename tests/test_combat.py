"""Unit tests for team combat in battle.py (M2.2): teams, actions, specials, EXP, victory.

Run from the project root:  python -m unittest discover tests
Damage numbers are worked out by hand from the stats in docs/M0_design.md §3.2.
The aiming values below were found with the independent simulation script from
M0 (not with battle.py): which character each shot hits, and which characters
are within the 50 px blast.
"""
import unittest

from battle import Battle, Team, MAX_STEPS
from castle import Castle
from characters import Archer, Engineer, Knight

HARMLESS = (80, 10)        # goes almost straight up and falls on the shooter's own castle
TOWER = (45, 64)           # hits the enemy tower: 4 blocks in the blast
FRONT_CHARACTER = (45, 73)  # hits the enemy in slot 0 only (the next slot is 54 px away)
SLOTS_0_AND_1 = (45, 76)   # hits slot 1; the blast also reaches slot 0, not slot 2
ALL_THREE = (63, 88)       # hits slot 1; the blast reaches slots 0, 1 and 2
SLOT_1 = (45, 77)          # hits slot 1 (the blast would also reach slot 2)


def combat(left, right, **options):
    """A battle with teams. `left` and `right` are lists of character classes."""
    return Battle(roster={"left": left, "right": right}, **options)


def aim(battle, angle, power):
    cannon = battle.cannons[battle.active_side]
    cannon.adjust_angle(angle - cannon.angle)
    cannon.adjust_power(power - cannon.power)


def act(battle, index, action, aim_at=None):
    """Aim (optional), perform the action and fly any shot to the end.

    Returns (accepted, events produced by this action).
    """
    if aim_at is not None:
        aim(battle, *aim_at)
    battle.take_events()                      # throw away older events
    accepted = battle.perform_action(index, action)
    for _ in range(MAX_STEPS + 1):
        if battle.projectile is None:
            break
        battle.update()
    return accepted, battle.take_events()


def pass_turn(battle):
    """The active side fires a harmless shot, so the turn moves on with no damage."""
    team = battle.teams[battle.active_side]
    index = next(i for i, c in enumerate(team.characters) if c.is_alive())
    accepted, events = act(battle, index, "attack", HARMLESS)
    assert accepted, events
    return events


def events_of(events, event_type):
    return [event for event in events if event["type"] == event_type]


def snapshot(battle):
    """Everything an action could change, to check that a refused action changed nothing."""
    state = [battle.active_side, battle.round_number, battle.projectile, battle.winner]
    for side in ("left", "right"):
        state.append(battle.castles[side].total_hp())
        for c in battle.teams[side].characters:
            state.append((c.hp, c.exp, c.level, c.is_defending, c.special_cooldown))
    return state


class TeamTest(unittest.TestCase):
    def test_a_team_has_1_to_3_characters(self):
        self.assertEqual(len(Team("left", [Knight("K", "left")], Castle("left")).characters), 1)
        trio = [Knight("K", "left"), Archer("A", "left"), Engineer("E", "left")]
        self.assertEqual(len(Team("left", trio, Castle("left")).characters), 3)
        with self.assertRaises(ValueError):
            Team("left", [], Castle("left"))
        with self.assertRaises(ValueError):
            Team("left", trio + [Knight("K2", "left")], Castle("left"))

    def test_duplicate_roles_are_rejected(self):
        with self.assertRaises(ValueError):
            Team("left", [Knight("K1", "left"), Knight("K2", "left")], Castle("left"))
        with self.assertRaises(ValueError):
            combat([Archer, Archer], [Knight])

    def test_characters_must_belong_to_the_team_side(self):
        with self.assertRaises(ValueError):
            Team("left", [Knight("K", "right")], Castle("left"))

    def test_team_loses_when_every_character_is_defeated(self):
        knight, archer = Knight("K", "left"), Archer("A", "left")
        team = Team("left", [knight, archer], Castle("left"))
        archer.take_damage(90)
        self.assertFalse(team.has_lost())
        knight.take_damage(140)
        self.assertTrue(team.has_lost())

    def test_team_loses_when_its_castle_falls_unless_that_rule_is_off(self):
        team = Team("left", [Knight("K", "left")], Castle("left"))
        for block in team.castle.blocks[:9]:
            block.take_damage(100)                  # 900 / 1500 = 60 %
        self.assertTrue(team.has_lost())
        self.assertFalse(team.has_lost(castle_loss_enabled=False))

    def test_character_rect_is_the_28_by_44_box_standing_on_its_slot(self):
        right = Team("right", [Knight("K", "right"), Archer("A", "right")], Castle("right"))
        # Slot 0 centre (1140, 538): left edge 1140 - 14, top 560 - 44.
        self.assertEqual(right.character_rect(0), (1126, 516, 28, 44))
        self.assertEqual(right.character_rect(1), (1171, 516, 28, 44))

    def test_slots_are_mirror_images_with_slot_0_nearest_the_castle(self):
        left = Team("left", [Knight("K", "left"), Archer("A", "left"), Engineer("E", "left")], Castle("left"))
        right = Team("right", [Knight("K", "right"), Archer("A", "right"), Engineer("E", "right")], Castle("right"))
        self.assertEqual([left.slot_center(i) for i in range(3)], [(140, 538), (95, 538), (50, 538)])
        self.assertEqual([right.slot_center(i) for i in range(3)], [(1140, 538), (1185, 538), (1230, 538)])


class ValidationTest(unittest.TestCase):
    def test_only_living_characters_can_act(self):
        battle = combat([Knight, Archer], [Engineer])
        battle.teams["left"].characters[1].take_damage(90)      # the Archer is defeated
        accepted, events = act(battle, 1, "defend")
        self.assertFalse(accepted)
        self.assertEqual(len(events_of(events, "invalid")), 1)
        self.assertEqual(battle.active_side, "left")
        accepted, _ = act(battle, 0, "defend")                   # the Knight can still act
        self.assertTrue(accepted)

    def test_refused_actions_change_nothing(self):
        battle = combat([Knight, Archer, Engineer], [Archer])
        battle.teams["left"].characters[1].start_cooldown()      # Archer's special is cooling down
        before = snapshot(battle)
        for index, action in ((3, "attack"),                      # no fourth character
                              (-1, "attack"),                     # no negative positions
                              (0, "dance"),                       # not an action
                              (1, "special"),                     # still cooling down
                              (2, "special")):                    # Repair with nothing to repair
            with self.subTest(index=index, action=action):
                accepted, events = act(battle, index, action)
                self.assertFalse(accepted)
                self.assertEqual([e["type"] for e in events], ["invalid"])
                self.assertEqual(snapshot(battle), before)

    def test_no_action_while_a_shot_is_flying(self):
        battle = combat([Knight, Archer], [Engineer])
        self.assertTrue(battle.perform_action(0, "attack"))
        shot = battle.projectile
        self.assertFalse(battle.perform_action(1, "defend"))
        self.assertIs(battle.projectile, shot)
        self.assertFalse(battle.teams["left"].characters[1].is_defending)

    def test_why_not_allowed_answers_without_doing_anything(self):
        battle = combat([Archer, Engineer], [Knight])
        archer = battle.teams["left"].characters[0]
        self.assertIsNone(battle.why_not_allowed(0, "attack"))
        self.assertIsNone(battle.why_not_allowed(0, "special"))
        archer.start_cooldown()
        self.assertEqual(battle.why_not_allowed(0, "special"),
                         "Power Shot is recharging: ready in 3 rounds")
        self.assertIn("nothing to repair", battle.why_not_allowed(1, "special"))
        self.assertEqual(battle.take_events(), [])                # asking records nothing
        self.assertEqual(battle.active_side, "left")

    def test_each_mode_keeps_its_own_way_of_acting(self):
        self.assertFalse(Battle().perform_action(0, "attack"))  # the M1 duel has no characters
        self.assertFalse(combat([Knight], [Archer]).fire())      # combat needs perform_action


class AttackTest(unittest.TestCase):
    def test_castle_damage_depends_on_the_attacker(self):
        # 4 tower blocks in the blast: Knight/Archer 4 x 50, Engineer 4 x 60.
        for role, expected in ((Knight, 200), (Archer, 200), (Engineer, 240)):
            with self.subTest(role=role.__name__):
                battle = combat([role], [Knight])
                _, events = act(battle, 0, "attack", TOWER)
                explosion = events_of(events, "explosion")[0]
                self.assertEqual((explosion["blocks_hit"], explosion["damage"]), (4, expected))
                self.assertEqual(battle.castles["right"].total_hp(), 1500 - expected)

    def test_attack_damages_the_character_it_hits(self):
        battle = combat([Knight], [Archer])
        _, events = act(battle, 0, "attack", FRONT_CHARACTER)
        explosion = events_of(events, "explosion")[0]
        self.assertEqual(explosion["kind"], "character")
        # Knight ATK 30 - Archer DEF 4 = 26.
        self.assertEqual(explosion["characters_hit"], [{"name": "Archer", "damage": 26, "defeated": False}])
        self.assertEqual(battle.teams["right"].characters[0].hp, 90 - 26)

    def test_one_explosion_hits_every_enemy_in_range(self):
        battle = combat([Archer], [Knight, Archer, Engineer])
        act(battle, 0, "attack", ALL_THREE)
        knight, archer, engineer = battle.teams["right"].characters
        # Archer ATK 40 minus each DEF: 40-12 = 28, 40-4 = 36, 40-8 = 32.
        self.assertEqual((knight.hp, archer.hp, engineer.hp), (140 - 28, 90 - 36, 110 - 32))

    def test_characters_outside_the_blast_are_not_hurt(self):
        battle = combat([Knight], [Knight, Archer, Engineer])
        act(battle, 0, "attack", SLOTS_0_AND_1)
        knight, archer, engineer = battle.teams["right"].characters
        # Knight ATK 30: 30-12 = 18 and 30-4 = 26; the Engineer in slot 2 is out of range.
        self.assertEqual((knight.hp, archer.hp, engineer.hp), (140 - 18, 90 - 26, 110))

    def test_a_defeated_character_no_longer_stops_shots(self):
        battle = combat([Knight], [Archer, Engineer])
        archer = battle.teams["right"].characters[0]
        archer.take_damage(90)
        _, events = act(battle, 0, "attack", FRONT_CHARACTER)
        explosion = events_of(events, "explosion")[0]
        self.assertEqual(explosion["kind"], "ground")             # it fell past the defeated Archer
        self.assertNotIn("Archer", [hit["name"] for hit in explosion["characters_hit"]])
        self.assertEqual(archer.hp, 0)


class DefendTest(unittest.TestCase):
    def test_defend_halves_damage_until_the_team_next_turn_starts(self):
        battle = combat([Knight], [Archer])
        knight = battle.teams["left"].characters[0]
        accepted, events = act(battle, 0, "defend")
        self.assertTrue(accepted)
        self.assertTrue(knight.is_defending)
        self.assertFalse(events_of(events, "fire"))               # Defend fires nothing
        act(battle, 0, "attack", FRONT_CHARACTER)                 # right's Archer: 40-12 = 28, halved 14
        self.assertEqual(knight.hp, 140 - 14)
        self.assertEqual(battle.active_side, "left")              # left's next turn has started...
        self.assertFalse(knight.is_defending)                     # ...so the Defend is over
        pass_turn(battle)
        act(battle, 0, "attack", FRONT_CHARACTER)                 # full 28 now
        self.assertEqual(knight.hp, 140 - 14 - 28)


class SpecialTest(unittest.TestCase):
    def test_rally_makes_every_living_ally_defend_and_fires_nothing(self):
        battle = combat([Knight, Archer, Engineer], [Archer])
        knight, archer, engineer = battle.teams["left"].characters
        archer.take_damage(90)
        accepted, events = act(battle, 0, "special")
        self.assertTrue(accepted)
        self.assertTrue(knight.is_defending and engineer.is_defending)
        self.assertFalse(archer.is_defending)
        self.assertIsNone(battle.projectile)
        self.assertFalse(events_of(events, "fire"))
        self.assertEqual(knight.special_cooldown, 4)
        self.assertEqual(battle.active_side, "right")

    def test_power_shot_ignores_def(self):
        battle = combat([Archer], [Knight])
        act(battle, 0, "special", FRONT_CHARACTER)
        self.assertEqual(battle.teams["right"].characters[0].hp, 140 - 60)   # 40 x 1.5, DEF ignored
        self.assertEqual(battle.teams["left"].characters[0].special_cooldown, 3)

    def test_power_shot_does_75_to_each_block(self):
        battle = combat([Archer], [Knight])
        _, events = act(battle, 0, "special", TOWER)
        explosion = events_of(events, "explosion")[0]
        self.assertEqual((explosion["blocks_hit"], explosion["damage"]), (4, 300))

    def test_power_shot_on_a_defending_target_is_halved(self):
        battle = combat([Archer], [Knight])
        pass_turn(battle)                                         # left
        act(battle, 0, "defend")                                  # right's Knight defends
        act(battle, 0, "special", FRONT_CHARACTER)                # 60 halved = 30
        self.assertEqual(battle.teams["right"].characters[0].hp, 140 - 30)

    def test_repair_restores_at_most_75_hp_and_never_a_destroyed_block(self):
        battle = combat([Engineer], [Knight])
        castle = battle.castles["left"]
        low, mid, gone = castle.blocks[1], castle.blocks[2], castle.blocks[3]
        low.take_damage(60)                                       # 40 HP
        mid.take_damage(30)                                       # 70 HP
        gone.take_damage(100)                                     # destroyed: 190 HP lost in total
        accepted, events = act(battle, 0, "special")
        self.assertTrue(accepted)
        self.assertEqual(castle.total_hp(), 1500 - 190 + 75)
        self.assertEqual((low.hp, mid.hp, gone.hp), (100, 85, 0))
        self.assertIsNone(battle.projectile)
        self.assertEqual(battle.teams["left"].characters[0].special_cooldown, 4)
        self.assertEqual(battle.active_side, "right")

    def test_special_used_in_round_r_is_ready_again_in_round_r_plus_cooldown(self):
        battle = combat([Archer], [Knight])
        self.assertTrue(act(battle, 0, "special", HARMLESS)[0])  # round 1, cooldown 3
        pass_turn(battle)                                         # right; round 2 starts
        for round_number in (2, 3):
            self.assertEqual(battle.round_number, round_number)
            self.assertFalse(act(battle, 0, "special", HARMLESS)[0])
            pass_turn(battle)                                     # left
            pass_turn(battle)                                     # right
        self.assertEqual(battle.round_number, 4)                  # 1 + 3
        self.assertTrue(act(battle, 0, "special", HARMLESS)[0])


class TurnTest(unittest.TestCase):
    def test_a_shot_ends_the_turn_when_it_lands_and_instant_actions_end_it_at_once(self):
        battle = combat([Knight], [Knight])
        self.assertTrue(battle.perform_action(0, "attack"))
        self.assertEqual(battle.active_side, "left")              # the shot is still flying
        while battle.projectile is not None:
            battle.update()
        self.assertEqual(battle.active_side, "right")
        self.assertTrue(battle.perform_action(0, "defend"))
        self.assertEqual(battle.active_side, "left")              # Defend is instant

    def test_cooldowns_tick_once_per_round_not_once_per_action(self):
        battle = combat([Archer], [Knight])
        archer = battle.teams["left"].characters[0]
        act(battle, 0, "special", HARMLESS)                       # round 1: cooldown 3
        pass_turn(battle)                                         # right acts, round 2 starts
        self.assertEqual((battle.round_number, archer.special_cooldown), (2, 2))
        pass_turn(battle)                                         # left acts, still round 2
        self.assertEqual(archer.special_cooldown, 2)

    def test_the_same_character_may_act_in_consecutive_rounds(self):
        battle = combat([Knight, Archer], [Knight])
        self.assertTrue(act(battle, 0, "attack", HARMLESS)[0])
        pass_turn(battle)
        self.assertTrue(act(battle, 0, "attack", HARMLESS)[0])


class ExperienceTest(unittest.TestCase):
    def test_a_hit_gives_10_exp_after_the_shot_lands(self):
        battle = combat([Knight], [Knight])
        knight = battle.teams["left"].characters[0]
        aim(battle, *TOWER)
        battle.perform_action(0, "attack")
        self.assertEqual(knight.exp, 0)                           # still flying
        while battle.projectile is not None:
            battle.update()
        self.assertEqual(knight.exp, 10)
        exp_event = events_of(battle.take_events(), "exp")[0]
        self.assertEqual((exp_event["name"], exp_event["amount"], exp_event["levels"]), ("Knight", 10, 0))

    def test_a_miss_and_a_defend_give_no_exp(self):
        battle = combat([Knight], [Knight])
        knight = battle.teams["left"].characters[0]
        act(battle, 0, "attack", HARMLESS)
        pass_turn(battle)
        act(battle, 0, "defend")
        self.assertEqual(knight.exp, 0)

    def test_rally_and_repair_give_5_exp(self):
        battle = combat([Knight, Engineer], [Archer])
        knight, engineer = battle.teams["left"].characters
        act(battle, 0, "special")                                 # Rally
        pass_turn(battle)
        battle.castles["left"].blocks[0].take_damage(20)
        act(battle, 1, "special")                                 # Repair
        self.assertEqual((knight.exp, engineer.exp), (5, 5))

    def test_a_defeat_gives_30_exp_and_the_new_atk_raises_later_damage(self):
        battle = combat([Knight], [Archer, Engineer])
        knight = battle.teams["left"].characters[0]
        archer, engineer = battle.teams["right"].characters
        archer.take_damage(64)                                    # 26 HP: one Knight hit (30-4) defeats it
        _, events = act(battle, 0, "attack", FRONT_CHARACTER)
        self.assertEqual(events_of(events, "explosion")[0]["characters_hit"],
                         [{"name": "Archer", "damage": 26, "defeated": True}])
        self.assertEqual((knight.level, knight.exp, knight.atk), (2, 0, 33))   # 10 + 20 = 30 EXP
        pass_turn(battle)
        act(battle, 0, "attack", SLOT_1)                          # Engineer: 33-8 = 25 (was 22)
        self.assertEqual(engineer.hp, 110 - 25)


class VictoryTest(unittest.TestCase):
    def test_defeating_every_enemy_wins(self):
        battle = combat([Knight], [Archer])
        battle.teams["right"].characters[0].take_damage(64)       # one hit left
        _, events = act(battle, 0, "attack", FRONT_CHARACTER)
        self.assertEqual(battle.winner, "left")
        self.assertEqual(events_of(events, "game_over")[0]["winner"], "left")
        self.assertFalse(events_of(events, "turn"))
        self.assertFalse(battle.perform_action(0, "attack"))      # nobody acts after the end

    def test_castle_destruction_still_wins(self):
        battle = combat([Knight], [Knight])
        for block in battle.castles["right"].blocks:
            block.take_damage(58)                                 # 58 %
        act(battle, 0, "attack", TOWER)                           # 4 blocks x 42 HP left = 168 -> 69 %
        self.assertEqual(battle.winner, "left")

    def test_castle_loss_can_be_switched_off(self):
        battle = combat([Knight], [Knight], castle_loss_enabled=False)
        for block in battle.castles["right"].blocks:
            block.take_damage(58)
        act(battle, 0, "attack", TOWER)
        self.assertTrue(battle.castles["right"].has_fallen())
        self.assertIsNone(battle.winner)                          # only elimination counts now
        self.assertEqual(battle.active_side, "right")

    def test_restart_brings_back_fresh_characters(self):
        battle = combat([Knight, Archer], [Engineer])
        knight = battle.teams["left"].characters[0]
        knight.gain_exp(30)
        knight.take_damage(50)
        act(battle, 0, "special")                                 # Rally: cooldown 4, defending
        battle.reset()
        fresh = battle.teams["left"].characters[0]
        self.assertIsNot(fresh, knight)
        self.assertEqual((fresh.level, fresh.hp, fresh.special_cooldown, fresh.is_defending),
                         (1, 140, 0, False))
        self.assertEqual((battle.round_number, battle.active_side), (1, "left"))
        self.assertIs(battle.teams["left"].castle, battle.castles["left"])


if __name__ == "__main__":
    unittest.main()
