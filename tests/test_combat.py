"""Unit tests for team combat in battle.py: teams, actions, specials, EXP, cover,
Cover Guard, elimination victory and the round limit.

Run from the project root:  python -m unittest discover tests
Damage numbers are worked out by hand from the stats in docs/M0_design.md §3.2.
The aiming values below were found with an independent simulation script (its own
physics and collision check, not battle.py): which block or character each shot
touches first, and what is within the 50 px blast. They are given for LEFT firing;
the field is a mirror image, so RIGHT firing with the same aim does the same to LEFT.
"""
import itertools
import unittest

from battle import Battle, Team, MAX_STEPS, ROUND_LIMIT
from castle import Castle, DEFAULT_LAYOUT, SLOT_COUNT, layout_problem, slot_position
from characters import Archer, Engineer, Knight

OPEN = {"left": (), "right": ()}   # no cover blocks: shots reach the characters directly
HARMLESS = (80, 10)          # comes down beside the shooter's own cannon: no damage
# Open field:
FRONT_CHARACTER = (45, 81)   # hits the enemy in slot 0 only (slot 1 is 59 px from the explosion)
SLOTS_0_AND_1 = (45, 84)     # hits slot 1; the blast also reaches slot 0 (37 px), not slot 2 (62 px)
SLOT_1 = (45, 85)            # hits slot 1 on top
# Default cover (slots 0-5):
COVER_WALL = (45, 76)        # comes down on the slot-2 block; 4 blocks in the blast (slots 1, 2, 3, 5)
OVER_THE_COVER = {0: (60, 88), 1: (60, 90), 2: (60, 93)}   # a steep shot onto slot 0, 1 or 2 from above
FRONT_AND_COVER = (60, 87)   # hits the slot-0 character's front; blocks 0 and 4 are also in the blast
# Cover of one block in slot 0:
ON_THE_FRONT_BLOCK = (45, 80)  # lands on top of that block, 40 px from the slot-0 character


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


def defend_turns(battle, count):
    """`count` turns in a row, whoever is to move: the first living character Defends
    (instant, no shot, no damage). Since M4.2-B a team can't Defend two turns in a row, so on
    the turn after its own Defend a team passes with a harmless shot instead. Returns the
    events of the last turn."""
    events = []
    for _ in range(count):
        team = battle.teams[battle.active_side]
        index = next(i for i, c in enumerate(team.characters) if c.is_alive())
        if battle.why_not_allowed(index, "defend") is None:
            accepted, events = act(battle, index, "defend")
        else:
            accepted, events = act(battle, index, "attack", HARMLESS)
        assert accepted, events
    return events


def events_of(events, event_type):
    return [event for event in events if event["type"] == event_type]


def explosion_of(events):
    return events_of(events, "explosion")[0]


def snapshot(battle):
    """Everything an action could change, to check that a refused action changed nothing."""
    state = [battle.active_side, battle.round_number, battle.projectile, battle.winner]
    for side in ("left", "right"):
        state.append(battle.castles[side].total_hp())
        for c in battle.teams[side].characters:
            state.append((c.hp, c.exp, c.level, c.is_defending, c.special_cooldown))
    return state


def other(side):
    return "right" if side == "left" else "left"


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

    def test_a_team_loses_only_when_every_character_is_defeated(self):
        knight, archer = Knight("K", "left"), Archer("A", "left")
        team = Team("left", [knight, archer], Castle("left"))
        for block in team.castle.blocks:
            block.take_damage(100)                  # all cover gone: that alone never loses
        archer.take_damage(90)
        self.assertFalse(team.has_lost())
        knight.take_damage(140)
        self.assertTrue(team.has_lost())

    def test_character_rect_is_the_28_by_44_box_standing_on_its_slot(self):
        right = Team("right", [Knight("K", "right"), Archer("A", "right")], Castle("right"))
        # Slot 0 centre (1140, 538): left edge 1140 - 14, top 560 - 44.
        self.assertEqual(right.character_rect(0), (1126, 516, 28, 44))
        self.assertEqual(right.character_rect(1), (1171, 516, 28, 44))

    def test_slots_are_mirror_images_with_slot_0_at_the_front(self):
        left = Team("left", [Knight("K", "left"), Archer("A", "left"), Engineer("E", "left")], Castle("left"))
        right = Team("right", [Knight("K", "right"), Archer("A", "right"), Engineer("E", "right")], Castle("right"))
        self.assertEqual([left.slot_center(i) for i in range(3)], [(140, 538), (95, 538), (50, 538)])
        self.assertEqual([right.slot_center(i) for i in range(3)], [(1140, 538), (1185, 538), (1230, 538)])

    def test_no_cover_slot_overlaps_a_character(self):
        for side in ("left", "right"):
            team = Team(side, [Knight("K", side), Archer("A", side), Engineer("E", side)],
                        Castle(side, ()))
            for slot in range(SLOT_COUNT):
                x, y = slot_position(side, slot)
                for left, top, width, height in (team.character_rect(i) for i in range(3)):
                    self.assertTrue(x >= left + width or x + 32 <= left        # side by side ...
                                    or y >= top + height or y + 32 <= top)     # ... or one above the other

    def test_is_covered_looks_for_a_standing_block_on_the_line_to_the_character(self):
        team = Team("left", [Knight("K", "left")], Castle("left", (0,)))   # block x 172..204, y 528..560
        self.assertTrue(team.is_covered(0, 195, 528))       # on top of the block: the block is in between
        self.assertFalse(team.is_covered(0, 160, 560))      # between the block and the character
        self.assertFalse(team.is_covered(0, 300, 400))      # high above: the line passes over the block
        team.castle.blocks[0].take_damage(100)
        self.assertFalse(team.is_covered(0, 195, 528))      # a destroyed block covers nothing


class BattleLayoutTest(unittest.TestCase):
    def test_both_teams_get_the_default_cover_unless_told_otherwise(self):
        battle = combat([Knight], [Archer])
        self.assertEqual(battle.layouts, {"left": DEFAULT_LAYOUT, "right": DEFAULT_LAYOUT})
        self.assertEqual((battle.castles["left"].layout, battle.castles["right"].layout),
                         (DEFAULT_LAYOUT, DEFAULT_LAYOUT))

    def test_each_team_has_its_own_cover(self):
        battle = combat([Knight], [Archer], layouts={"left": (3, 7), "right": ()})
        self.assertEqual(battle.castles["left"].layout, (3, 7))
        self.assertEqual(battle.castles["right"].blocks, ())
        self.assertIs(battle.teams["left"].castle, battle.castles["left"])

    def test_an_illegal_cover_is_refused(self):
        with self.assertRaises(ValueError):
            combat([Knight], [Archer], layouts={"left": (0, 1, 2, 3, 4, 5, 6), "right": ()})
        with self.assertRaises(ValueError):
            combat([Knight], [Archer], layouts={"left": (), "right": (6,)})     # floating block


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


class AttackTest(unittest.TestCase):
    def test_block_damage_depends_on_the_attacker(self):
        # 4 blocks in the blast: Knight/Archer 4 x 50, Engineer 4 x 60.
        for role, expected in ((Knight, 200), (Archer, 200), (Engineer, 240)):
            with self.subTest(role=role.__name__):
                battle = combat([role], [Knight])
                explosion = explosion_of(act(battle, 0, "attack", COVER_WALL)[1])
                self.assertEqual((explosion["blocks_hit"], explosion["damage"]), (4, expected))
                self.assertEqual(battle.castles["right"].total_hp(), 600 - expected)
                self.assertEqual(battle.teams["right"].characters[0].hp, 140)   # the Knight is far away

    def test_attack_damages_the_character_it_hits(self):
        battle = combat([Knight], [Archer], layouts=OPEN)
        explosion = explosion_of(act(battle, 0, "attack", FRONT_CHARACTER)[1])
        self.assertEqual((explosion["kind"], explosion["target"]), ("character", "Archer"))
        # Knight ATK 30 - Archer DEF 4 = 26.
        self.assertEqual(explosion["characters_hit"], [{"name": "Archer", "damage": 26, "defeated": False}])
        self.assertEqual(battle.teams["right"].characters[0].hp, 90 - 26)

    def test_one_explosion_hurts_every_enemy_in_range_and_no_one_else(self):
        battle = combat([Archer], [Knight, Archer, Engineer], layouts=OPEN)
        act(battle, 0, "attack", SLOTS_0_AND_1)
        knight, archer, engineer = battle.teams["right"].characters
        # Archer ATK 40: 40-12 = 28 and 40-4 = 36; the Engineer in slot 2 is out of range.
        self.assertEqual((knight.hp, archer.hp, engineer.hp), (140 - 28, 90 - 36, 110))

    def test_one_explosion_can_hurt_a_character_and_blocks(self):
        battle = combat([Knight], [Archer])                      # default cover
        explosion = explosion_of(act(battle, 0, "attack", FRONT_AND_COVER)[1])
        self.assertEqual(explosion["target"], "Archer")
        self.assertEqual(explosion["characters_hit"], [{"name": "Archer", "damage": 26, "defeated": False}])
        self.assertEqual((explosion["blocks_hit"], explosion["damage"]), (2, 100))   # blocks 0 and 4

    def test_a_defeated_character_no_longer_stops_shots(self):
        battle = combat([Knight], [Archer, Engineer], layouts=OPEN)
        archer = battle.teams["right"].characters[0]
        archer.take_damage(90)
        explosion = explosion_of(act(battle, 0, "attack", FRONT_CHARACTER)[1])
        self.assertEqual(explosion["kind"], "ground")             # it fell past the defeated Archer
        self.assertNotIn("Archer", [hit["name"] for hit in explosion["characters_hit"]])
        self.assertEqual(archer.hp, 0)


class CoverTest(unittest.TestCase):
    """M3.4: a standing block between an explosion and a character takes the whole blast."""

    def test_intact_cover_shields_a_character_from_the_blast(self):
        battle = combat([Knight], [Knight], layouts={"left": (), "right": (0,)})
        explosion = explosion_of(act(battle, 0, "attack", ON_THE_FRONT_BLOCK)[1])
        self.assertEqual((explosion["kind"], explosion["target"]), ("block", None))
        self.assertAlmostEqual(explosion["y"], 528, places=6)             # on top of the block
        self.assertEqual(explosion["covered"], ["Knight"])                # 40 px away, but shielded
        self.assertEqual(explosion["characters_hit"], [])
        self.assertEqual(battle.teams["right"].characters[0].hp, 140)
        self.assertEqual((explosion["blocks_hit"], explosion["damage"]), (1, 50))

    def test_destroyed_cover_no_longer_protects(self):
        battle = combat([Knight], [Knight], layouts={"left": (), "right": (0,)})
        battle.castles["right"].blocks[0].take_damage(100)
        explosion = explosion_of(act(battle, 0, "attack", ON_THE_FRONT_BLOCK)[1])
        self.assertEqual((explosion["kind"], explosion["target"]), ("character", "Knight"))
        self.assertEqual(explosion["covered"], [])
        self.assertEqual(battle.teams["right"].characters[0].hp, 140 - 18)   # 30 - 12

    def test_a_block_destroyed_by_the_same_explosion_still_shields_against_it(self):
        # Cover is read once, at the moment of impact, before anything is damaged.
        battle = combat([Knight], [Knight], layouts={"left": (), "right": (0,)})
        block = battle.castles["right"].blocks[0]
        knight = battle.teams["right"].characters[0]
        block.take_damage(90)                                             # 10 HP left
        explosion = explosion_of(act(battle, 0, "attack", ON_THE_FRONT_BLOCK)[1])
        self.assertTrue(block.is_destroyed())
        self.assertEqual((explosion["blocks_hit"], explosion["damage"]), (1, 10))
        self.assertEqual((explosion["covered"], knight.hp), (["Knight"], 140))
        pass_turn(battle)
        explosion = explosion_of(act(battle, 0, "attack", ON_THE_FRONT_BLOCK)[1])
        self.assertEqual((explosion["target"], knight.hp), ("Knight", 140 - 18))   # exposed now

    def test_characters_behind_cover_can_still_be_hit_from_above(self):
        battle = combat([Knight], [Knight, Archer, Engineer])          # default cover
        for slot, name, damage in ((0, "Knight", 18), (1, "Archer", 26), (2, "Engineer", 22)):
            with self.subTest(slot=slot):
                explosion = explosion_of(act(battle, 0, "attack", OVER_THE_COVER[slot])[1])
                self.assertEqual(explosion["target"], name)
                hit = [h for h in explosion["characters_hit"] if h["name"] == name]
                self.assertEqual(hit[0]["damage"], damage)
                pass_turn(battle)

    def test_an_exposed_neighbour_is_hurt_even_with_cover_in_front(self):
        # The block stands in front of the Knight, not between the Knight and this explosion.
        battle = combat([Knight], [Knight, Archer], layouts={"left": (), "right": (0,)})
        explosion = explosion_of(act(battle, 0, "attack", SLOTS_0_AND_1)[1])
        self.assertEqual((explosion["target"], explosion["covered"]), ("Archer", []))
        knight, archer = battle.teams["right"].characters
        self.assertEqual((knight.hp, archer.hp), (140 - 18, 90 - 26))

    def test_every_legal_cover_leaves_every_character_reachable(self):
        # For each of the 76 legal layouts, a steep shot still reaches each character.
        layouts = [subset for size in range(SLOT_COUNT + 1)
                   for subset in itertools.combinations(range(SLOT_COUNT), size)
                   if layout_problem(subset) is None]
        self.assertEqual(len(layouts), 76)
        for layout in layouts:
            for slot, name in enumerate(("Knight", "Archer", "Engineer")):
                with self.subTest(layout=layout, slot=slot):
                    battle = combat([Knight], [Knight, Archer, Engineer],
                                    layouts={"left": (), "right": layout})
                    explosion = explosion_of(act(battle, 0, "attack", OVER_THE_COVER[slot])[1])
                    self.assertEqual(explosion["target"], name)

    def test_mirrored_cover_shields_the_same_way_on_both_sides(self):
        battle = combat([Knight], [Knight], layouts={"left": (0,), "right": (0,)})
        left_shot = explosion_of(act(battle, 0, "attack", ON_THE_FRONT_BLOCK)[1])
        right_shot = explosion_of(act(battle, 0, "attack", ON_THE_FRONT_BLOCK)[1])
        self.assertAlmostEqual(right_shot["x"], 1280 - left_shot["x"], places=6)
        for explosion in (left_shot, right_shot):
            self.assertEqual((explosion["covered"], explosion["blocks_hit"]), (["Knight"], 1))
        self.assertEqual([t.characters[0].hp for t in battle.teams.values()], [140, 140])


class DefendTest(unittest.TestCase):
    def test_defend_halves_damage_until_the_team_next_turn_starts(self):
        battle = combat([Knight], [Archer], layouts=OPEN)
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


class CoverGuardTest(unittest.TestCase):
    """M3.2 Castle Guard, called Cover Guard since M3.4: while one of a team's characters is
    defending (Defend or Rally), enemy shots do half damage to that team's blocks, rounded
    down. It ends with the Defend. (The code still calls it castle_guarded.)"""

    def test_defend_guards_the_cover_until_the_team_next_turn_starts(self):
        battle = combat([Knight, Archer], [Knight])
        act(battle, 1, "defend")                                  # one defender is enough: the Archer
        self.assertTrue(battle.castle_guarded("left"))
        explosion = explosion_of(act(battle, 0, "attack", COVER_WALL)[1])   # right: 4 x 50, halved
        self.assertEqual((explosion["blocks_hit"], explosion["damage"], explosion["guarded"]),
                         (4, 100, True))
        self.assertEqual(battle.castles["left"].total_hp(), 600 - 100)
        self.assertFalse(battle.castle_guarded("left"))           # left's turn has started: guard over
        pass_turn(battle)
        explosion = explosion_of(act(battle, 0, "attack", COVER_WALL)[1])   # the same 4 blocks, full 50
        self.assertEqual((explosion["damage"], explosion["guarded"]), (200, False))
        self.assertEqual(battle.castles["left"].total_hp(), 600 - 300)

    def test_only_the_defending_team_cover_is_guarded(self):
        battle = combat([Knight], [Knight])
        pass_turn(battle)                                         # left
        act(battle, 0, "defend")                                  # right defends
        self.assertEqual((battle.castle_guarded("left"), battle.castle_guarded("right")), (False, True))
        self.assertEqual(explosion_of(act(battle, 0, "attack", COVER_WALL)[1])["damage"], 100)
        self.assertEqual(explosion_of(act(battle, 0, "attack", COVER_WALL)[1])["damage"], 200)

    def test_rally_guards_the_cover_like_defend_and_also_ends_at_the_next_turn(self):
        battle = combat([Knight, Archer], [Archer])
        act(battle, 0, "special")                                 # Rally: the whole team defends
        self.assertEqual(explosion_of(act(battle, 0, "attack", COVER_WALL)[1])["damage"], 100)
        pass_turn(battle)                                         # left (the Rally is over)
        self.assertEqual(explosion_of(act(battle, 0, "attack", COVER_WALL)[1])["damage"], 200)

    def test_several_defenders_do_not_stack_the_guard(self):
        battle = combat([Knight, Archer, Engineer], [Knight])
        act(battle, 0, "special")                                 # Rally: all three defend
        self.assertEqual(sum(c.is_defending for c in battle.teams["left"].characters), 3)
        explosion = explosion_of(act(battle, 0, "attack", COVER_WALL)[1])
        self.assertEqual(explosion["damage"], 4 * 25)             # halved once, not 3 times

    def test_guard_lasts_the_whole_enemy_turn_and_ends_as_the_defender_turn_starts(self):
        for defender in ("left", "right"):
            with self.subTest(defender=defender):
                battle = combat([Knight], [Knight])
                if defender == "right":
                    pass_turn(battle)                             # left moves first
                act(battle, 0, "defend")
                attacker = battle.active_side
                self.assertNotEqual(attacker, defender)
                aim(battle, *COVER_WALL)
                battle.perform_action(0, "attack")
                while battle.projectile is not None:              # every frame of the enemy shot
                    self.assertEqual(battle.active_side, attacker)
                    self.assertTrue(battle.castle_guarded(defender))
                    battle.update()
                self.assertEqual(explosion_of(battle.take_events())["damage"], 100)
                self.assertEqual(battle.active_side, defender)    # the defender's next turn has begun...
                self.assertFalse(battle.castle_guarded(defender))  # ...so the guard is already over

    def test_guarded_block_damage_is_halved_and_rounded_down(self):
        # 4 blocks: Knight 50 -> 25, Engineer 60 -> 30, Power Shot 75 -> 37 (37.5 rounded down).
        cases = ((Knight, "attack", 4 * 25), (Engineer, "attack", 4 * 30), (Archer, "special", 4 * 37))
        for role, action, expected in cases:
            with self.subTest(role=role.__name__, action=action):
                battle = combat([Knight], [role])
                act(battle, 0, "defend")
                self.assertEqual(explosion_of(act(battle, 0, action, COVER_WALL)[1])["damage"], expected)

    def test_cover_guard_can_keep_a_block_standing(self):
        # The slot-2 block has 30 HP: a full Knight hit (50) destroys it, a guarded one (25) doesn't.
        for defends, destroyed in ((False, True), (True, False)):
            with self.subTest(defends=defends):
                battle = combat([Knight], [Knight])
                block = battle.castles["left"].blocks[2]
                block.take_damage(70)
                if defends:
                    act(battle, 0, "defend")
                else:
                    pass_turn(battle)
                act(battle, 0, "attack", COVER_WALL)
                self.assertEqual(block.is_destroyed(), destroyed)

    def test_the_guard_also_covers_the_shot_that_defeats_the_defender(self):
        battle = combat([Archer], [Knight])
        archer = battle.teams["left"].characters[0]
        archer.take_damage(89)                                    # 1 HP left
        act(battle, 0, "defend")
        explosion = explosion_of(act(battle, 0, "attack", FRONT_AND_COVER)[1])   # (30-4)//2 = 13
        self.assertEqual(explosion["characters_hit"], [{"name": "Archer", "damage": 1, "defeated": True}])
        self.assertEqual((explosion["blocks_hit"], explosion["damage"], explosion["guarded"]), (2, 50, True))
        self.assertEqual(battle.winner, "right")


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
        battle = combat([Archer], [Knight], layouts=OPEN)
        act(battle, 0, "special", FRONT_CHARACTER)
        self.assertEqual(battle.teams["right"].characters[0].hp, 140 - 60)   # 40 x 1.5, DEF ignored
        self.assertEqual(battle.teams["left"].characters[0].special_cooldown, 3)

    def test_power_shot_does_75_to_each_block(self):
        battle = combat([Archer], [Knight])
        explosion = explosion_of(act(battle, 0, "special", COVER_WALL)[1])
        self.assertEqual((explosion["blocks_hit"], explosion["damage"]), (4, 300))

    def test_power_shot_on_a_defending_target_is_halved(self):
        battle = combat([Archer], [Knight], layouts=OPEN)
        pass_turn(battle)                                         # left
        act(battle, 0, "defend")                                  # right's Knight defends
        act(battle, 0, "special", FRONT_CHARACTER)                # 60 halved = 30
        self.assertEqual(battle.teams["right"].characters[0].hp, 140 - 30)

    def test_repair_restores_at_most_150_hp_and_never_a_destroyed_block(self):
        battle = combat([Engineer], [Knight])
        castle = battle.castles["left"]
        lowest, low, mid, gone = castle.blocks[:4]
        lowest.take_damage(80)                                    # 20 HP
        low.take_damage(60)                                       # 40 HP
        mid.take_damage(30)                                       # 70 HP
        gone.take_damage(100)                                     # destroyed: 270 HP lost in total
        accepted, events = act(battle, 0, "special")
        self.assertTrue(accepted)
        # 150 HP, most damaged first: +80 (20 -> 100), +60 (40 -> 100), the last 10 to the 70-HP block.
        self.assertEqual(castle.total_hp(), 600 - 270 + 150)
        self.assertEqual((lowest.hp, low.hp, mid.hp, gone.hp), (100, 100, 80, 0))
        self.assertTrue(all(block.hp <= block.max_hp for block in castle.blocks))
        self.assertIsNone(battle.projectile)
        self.assertEqual(battle.teams["left"].characters[0].special_cooldown, 4)
        self.assertEqual(battle.active_side, "right")

    def test_repair_is_unavailable_without_a_damaged_standing_block(self):
        for layout, damage in (((), 0), ((0,), 0), ((0,), 100)):        # no blocks; unhurt; destroyed
            with self.subTest(layout=layout, damage=damage):
                battle = combat([Engineer], [Knight], layouts={"left": layout, "right": ()})
                for block in battle.castles["left"].blocks:
                    block.take_damage(damage)
                self.assertIn("nothing to repair", battle.why_not_allowed(0, "special"))
                self.assertFalse(act(battle, 0, "special")[0])

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
        aim(battle, *COVER_WALL)                                  # damaging blocks counts as a hit
        battle.perform_action(0, "attack")
        self.assertEqual(knight.exp, 0)                           # still flying
        while battle.projectile is not None:
            battle.update()
        self.assertEqual(knight.exp, 10)
        exp_event = events_of(battle.take_events(), "exp")[0]
        self.assertEqual((exp_event["name"], exp_event["amount"], exp_event["levels"]), ("Knight", 10, 0))

    def test_a_harmless_shot_and_a_defend_give_no_exp(self):
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
        battle = combat([Knight], [Archer, Engineer], layouts=OPEN)
        knight = battle.teams["left"].characters[0]
        archer, engineer = battle.teams["right"].characters
        archer.take_damage(64)                                    # 26 HP: one Knight hit (30-4) defeats it
        _, events = act(battle, 0, "attack", FRONT_CHARACTER)
        self.assertEqual(explosion_of(events)["characters_hit"],
                         [{"name": "Archer", "damage": 26, "defeated": True}])
        self.assertEqual((knight.level, knight.exp, knight.atk), (2, 0, 33))   # 10 + 20 = 30 EXP
        pass_turn(battle)
        act(battle, 0, "attack", SLOT_1)                          # Engineer: 33-8 = 25 (was 22)
        self.assertEqual(engineer.hp, 110 - 25)


class VictoryTest(unittest.TestCase):
    """M3.4: the only way to win is to defeat every enemy character."""

    def test_defeating_every_enemy_wins(self):
        battle = combat([Knight], [Archer], layouts=OPEN)
        battle.teams["right"].characters[0].take_damage(64)       # one hit left
        _, events = act(battle, 0, "attack", FRONT_CHARACTER)
        self.assertEqual((battle.winner, battle.end_reason), ("left", "elimination"))
        self.assertEqual(events_of(events, "game_over"),
                         [{"type": "game_over", "winner": "left", "reason": "elimination"}])
        self.assertFalse(events_of(events, "turn"))
        self.assertFalse(battle.perform_action(0, "attack"))      # nobody acts after the end

    def test_destroying_every_block_does_not_win(self):
        battle = combat([Knight], [Knight])
        for block in battle.castles["right"].blocks[1:]:
            block.take_damage(100)
        battle.castles["right"].blocks[0].take_damage(90)
        act(battle, 0, "attack", ON_THE_FRONT_BLOCK)              # finishes off the last block
        self.assertEqual(battle.castles["right"].alive_blocks(), [])
        self.assertIsNone(battle.winner)                          # cover is not a victory condition
        self.assertEqual(battle.active_side, "right")

    def test_both_teams_defeated_together_is_a_draw(self):
        # No shot hurts its own team, so this can't happen in play, but the rule holds.
        battle = combat([Knight], [Archer])
        battle.teams["left"].characters[0].take_damage(140)
        battle.teams["right"].characters[0].take_damage(90)
        self.assertEqual((battle.check_winner(), battle.end_reason), ("draw", "both_lost"))

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


class FirstMoverTest(unittest.TestCase):
    """M3.3: either side can move first; a round is complete once both teams have acted."""

    def test_left_moves_first_unless_told_otherwise(self):
        battle = combat([Knight], [Knight])
        self.assertEqual((battle.first_side, battle.active_side, battle.round_number), ("left", "left", 1))
        battle = combat([Knight], [Knight], first_side="right")
        self.assertEqual((battle.first_side, battle.active_side, battle.round_number), ("right", "right", 1))
        with self.assertRaises(ValueError):
            combat([Knight], [Knight], first_side="middle")

    def test_reset_can_change_who_moves_first_and_starts_a_fresh_match(self):
        battle = combat([Archer], [Knight])
        act(battle, 0, "special", COVER_WALL)                     # Power Shot: block damage, EXP, cooldown
        battle.teams["right"].characters[0].take_damage(50)
        battle.reset(first_side="right")
        archer = battle.teams["left"].characters[0]
        knight = battle.teams["right"].characters[0]
        self.assertEqual((battle.first_side, battle.active_side, battle.round_number), ("right", "right", 1))
        self.assertEqual((archer.exp, archer.special_cooldown, knight.hp), (0, 0, 140))
        self.assertEqual(battle.castles["right"].total_hp(), 600)
        self.assertIsNone(battle.projectile)
        self.assertIsNone(battle.winner)
        self.assertIsNone(battle.end_reason)
        battle.reset()                                            # no argument: keeps the first side
        self.assertEqual(battle.active_side, "right")

    def test_with_right_first_a_round_starts_each_time_right_is_to_move(self):
        battle = combat([Knight], [Knight], first_side="right")
        events = defend_turns(battle, 1)                          # right, round 1
        self.assertEqual((battle.round_number, battle.active_side), (1, "left"))
        self.assertFalse(events_of(events, "round"))
        events = defend_turns(battle, 1)                          # left completes round 1
        self.assertEqual((battle.round_number, battle.active_side), (2, "right"))
        self.assertEqual(events_of(events, "round"), [{"type": "round", "number": 2}])

    def test_cooldowns_tick_once_per_round_with_right_first(self):
        battle = combat([Knight], [Archer], first_side="right")
        archer = battle.teams["right"].characters[0]
        self.assertTrue(act(battle, 0, "special", HARMLESS)[0])  # round 1: Power Shot, cooldown 3
        pass_turn(battle)                                         # left; round 2 starts
        self.assertEqual((battle.round_number, archer.special_cooldown), (2, 2))
        pass_turn(battle)                                         # right, still round 2: no tick
        self.assertEqual(archer.special_cooldown, 2)
        for round_number in (3, 4):
            pass_turn(battle)                                     # left; the next round starts
            self.assertEqual(battle.round_number, round_number)
            if round_number == 3:
                self.assertFalse(act(battle, 0, "special", HARMLESS)[0])   # still recharging
                pass_turn(battle)                                 # right
        self.assertEqual(archer.special_cooldown, 0)
        self.assertTrue(act(battle, 0, "special", HARMLESS)[0])  # round 4 = 1 + 3: ready again

    def test_defend_and_rally_end_at_the_defending_team_next_turn_with_right_first(self):
        battle = combat([Archer], [Knight], first_side="right", layouts=OPEN)
        knight = battle.teams["right"].characters[0]
        act(battle, 0, "defend")                                  # right, round 1
        act(battle, 0, "attack", FRONT_CHARACTER)                 # left: 40-12 = 28, halved 14
        self.assertEqual(knight.hp, 140 - 14)
        self.assertFalse(knight.is_defending)                     # right's turn (round 2) has started
        # Left defends as the second mover of round 2: it must last across the round start.
        archer = battle.teams["left"].characters[0]
        pass_turn(battle)                                         # right, round 2
        act(battle, 0, "defend")                                  # left, round 2
        self.assertEqual(battle.round_number, 3)
        self.assertTrue(archer.is_defending and battle.castle_guarded("left"))
        act(battle, 0, "attack", FRONT_CHARACTER)                 # right, round 3: 30-4 = 26, halved 13
        self.assertEqual(archer.hp, 90 - 13)
        self.assertFalse(archer.is_defending)                     # left's turn has started

        battle = combat([Archer], [Knight, Engineer], first_side="right")
        act(battle, 0, "special")                                 # right Knight: Rally
        self.assertTrue(battle.castle_guarded("right"))
        self.assertEqual(explosion_of(act(battle, 0, "attack", COVER_WALL)[1])["damage"], 100)
        self.assertFalse(battle.castle_guarded("right"))          # right's next turn: Rally over


class RoundLimitTest(unittest.TestCase):
    """M3.4: a team match that reaches the end of round 30 without an elimination is a
    draw (a timeout). HP and cover never pick a winner."""

    def play_to_the_limit(self, battle):
        """Defend through rounds 1-29 and the first turn of round 30; return the last turn's events."""
        defend_turns(battle, 2 * (ROUND_LIMIT - 1) + 1)
        self.assertEqual(battle.round_number, ROUND_LIMIT)
        self.assertIsNone(battle.winner)                          # one team has acted in round 30
        return defend_turns(battle, 1)                            # the other team completes it

    def test_the_limit_is_30_complete_rounds_with_either_side_first(self):
        self.assertEqual(ROUND_LIMIT, 30)
        for first in ("left", "right"):
            with self.subTest(first=first):
                battle = combat([Knight], [Knight], first_side=first)
                defend_turns(battle, 2 * (ROUND_LIMIT - 1))
                self.assertEqual((battle.round_number, battle.active_side), (30, first))
                defend_turns(battle, 1)                           # the first mover acts in round 30
                self.assertIsNone(battle.winner)                  # not over after half a round
                self.assertEqual((battle.round_number, battle.active_side), (30, other(first)))
                events = defend_turns(battle, 1)                  # round 30 is complete
                self.assertEqual((battle.winner, battle.end_reason), ("draw", "timeout"))
                self.assertEqual(battle.round_number, 30)
                self.assertFalse(events_of(events, "round"))      # no round 31
                self.assertEqual(events_of(events, "game_over"),
                                 [{"type": "game_over", "winner": "draw", "reason": "timeout"}])
                self.assertFalse(battle.perform_action(0, "defend"))

    def test_the_timeout_is_a_draw_even_when_one_team_is_far_ahead(self):
        battle = combat([Knight, Archer], [Knight, Archer])
        battle.teams["right"].characters[1].take_damage(90)       # right: one character left ...
        battle.teams["right"].characters[0].take_damage(130)      # ... with 10 HP
        for block in battle.castles["right"].blocks:
            block.take_damage(100)                                # and no cover
        self.play_to_the_limit(battle)
        self.assertEqual((battle.winner, battle.end_reason), ("draw", "timeout"))

    def test_an_elimination_on_the_last_turn_beats_the_timeout(self):
        battle = combat([Archer], [Knight], layouts=OPEN)
        battle.teams["left"].characters[0].take_damage(64)        # one Knight hit (30-4) left
        defend_turns(battle, 2 * (ROUND_LIMIT - 1))
        pass_turn(battle)                                         # left, round 30
        act(battle, 0, "attack", FRONT_CHARACTER)                 # right's last turn defeats the Archer
        self.assertEqual((battle.winner, battle.end_reason), ("right", "elimination"))


def guard_events(events):
    return [(e["type"], e["side"], e["name"]) for e in events if e["type"].startswith("guard_")]


class GuardedStrikeTest(unittest.TestCase):
    """M4.2-B: a basic Defend gives the defender ATK x 1.25 on a normal Attack during its team's
    next turn only. Defend itself still halves damage (course rule C5)."""

    def test_the_defender_attacks_25_percent_harder_on_its_team_next_turn(self):
        battle = combat([Knight], [Knight], layouts=OPEN)
        knight, enemy = battle.teams["left"].characters[0], battle.teams["right"].characters[0]
        _, events = act(battle, 0, "defend")
        self.assertTrue(knight.is_defending)                      # Defend still protects (C5)
        self.assertTrue(knight.guarded_strike_pending)
        self.assertEqual(guard_events(events), [("guard_granted", "left", "Knight")])
        pass_turn(battle)                                         # right
        self.assertTrue(knight.guarded_strike_ready)
        _, events = act(battle, 0, "attack", FRONT_CHARACTER)
        self.assertEqual(enemy.hp, 140 - 25)                      # int(30 x 1.25) - 12 = 25, not 18
        self.assertEqual(guard_events(events), [("guard_used", "left", "Knight")])
        self.assertEqual(knight.exp, 10)                          # EXP as for any hit
        self.assertFalse(knight.guarded_strike_ready)
        pass_turn(battle)
        act(battle, 0, "attack", FRONT_CHARACTER)
        self.assertEqual(enemy.hp, 140 - 25 - 18)                 # used up: a normal hit again

    def test_it_expires_if_another_character_acts_in_that_turn(self):
        battle = combat([Knight, Archer], [Knight], layouts=OPEN)
        knight, enemy = battle.teams["left"].characters[0], battle.teams["right"].characters[0]
        act(battle, 0, "defend")
        pass_turn(battle)
        _, events = act(battle, 1, "attack", FRONT_CHARACTER)     # the Archer attacks instead
        self.assertEqual(enemy.hp, 140 - 28)                      # the Archer's normal 40 - 12
        self.assertEqual(guard_events(events), [("guard_expired", "left", "Knight")])
        self.assertFalse(knight.guarded_strike_ready or knight.guarded_strike_pending)
        pass_turn(battle)
        act(battle, 0, "attack", FRONT_CHARACTER)
        self.assertEqual(enemy.hp, 140 - 28 - 18)                 # the Knight's bonus is gone

    def test_power_shot_neither_uses_nor_adds_it(self):
        battle = combat([Archer], [Knight], layouts=OPEN)
        enemy = battle.teams["right"].characters[0]
        act(battle, 0, "defend")
        pass_turn(battle)
        _, events = act(battle, 0, "special", FRONT_CHARACTER)    # Power Shot with a ready bonus
        self.assertEqual(enemy.hp, 140 - 60)                      # 40 x 1.5, DEF ignored: not x 1.25 more
        self.assertEqual(guard_events(events), [("guard_expired", "left", "Archer")])

    def test_rally_gives_no_guarded_strike(self):
        battle = combat([Knight, Archer], [Knight], layouts=OPEN)
        _, events = act(battle, 0, "special")                     # Rally: everyone defends
        self.assertTrue(all(c.is_defending for c in battle.teams["left"].characters))
        self.assertFalse(any(c.guarded_strike_pending for c in battle.teams["left"].characters))
        self.assertEqual(guard_events(events), [])

    def test_it_never_stacks(self):
        battle = combat([Knight], [Knight], layouts=OPEN, anti_stall=False)   # so Defend can repeat
        enemy = battle.teams["right"].characters[0]
        act(battle, 0, "defend")
        pass_turn(battle)
        act(battle, 0, "defend")                                  # again, while the first is ready
        pass_turn(battle)
        act(battle, 0, "attack", FRONT_CHARACTER)
        self.assertEqual(enemy.hp, 140 - 25)                      # x 1.25 once, never x 1.25 x 1.25

    def test_against_a_defender_the_bonus_hit_is_halved(self):
        battle = combat([Knight], [Knight], layouts=OPEN)
        enemy = battle.teams["right"].characters[0]
        act(battle, 0, "defend")
        act(battle, 0, "defend")                                  # right defends too
        act(battle, 0, "attack", FRONT_CHARACTER)
        self.assertEqual(enemy.hp, 140 - 12)                      # (37 - 12) // 2

    def test_block_damage_is_unchanged(self):
        battle = combat([Knight], [Knight])                       # default cover
        act(battle, 0, "defend")
        pass_turn(battle)
        act(battle, 0, "attack", COVER_WALL)
        self.assertEqual(battle.castles["right"].total_hp(), 600 - 200)   # 4 blocks x 50, as always

    def test_it_can_be_switched_off(self):
        battle = combat([Knight], [Knight], layouts=OPEN, guarded_strike=False)
        enemy = battle.teams["right"].characters[0]
        _, events = act(battle, 0, "defend")
        self.assertFalse(battle.teams["left"].characters[0].guarded_strike_pending)
        self.assertEqual(guard_events(events), [])
        pass_turn(battle)
        act(battle, 0, "attack", FRONT_CHARACTER)
        self.assertEqual(enemy.hp, 140 - 18)

    def test_a_defeated_defender_drops_it_quietly(self):
        battle = combat([Knight, Archer], [Knight], layouts=OPEN)
        act(battle, 1, "defend")                                  # the Archer
        battle.teams["left"].characters[1].take_damage(500)       # falls before its next turn
        pass_turn(battle)
        _, events = act(battle, 0, "attack", FRONT_CHARACTER)
        self.assertEqual(guard_events(events), [])
        self.assertEqual(battle.teams["right"].characters[0].hp, 140 - 18)

    def test_a_new_match_clears_it(self):
        battle = combat([Knight], [Knight], layouts=OPEN)
        act(battle, 0, "defend")
        battle.reset()
        self.assertFalse(battle.teams["left"].characters[0].guarded_strike_pending)

    def test_a_guarded_strike_can_win_on_the_last_turn_of_round_30(self):
        battle = combat([Archer], [Archer], layouts=OPEN)
        battle.teams["left"].characters[0].take_damage(50)        # 40 HP: a normal hit (36) won't do
        for _ in range(2 * (ROUND_LIMIT - 2) + 1):                # to round 29, right to move
            pass_turn(battle)
        act(battle, 0, "defend")                                  # right, round 29
        pass_turn(battle)                                         # left, round 30
        self.assertEqual(battle.round_number, ROUND_LIMIT)
        act(battle, 0, "attack", FRONT_CHARACTER)                 # right's last turn: 46 damage
        self.assertEqual((battle.winner, battle.end_reason), ("right", "elimination"))


class AntiStallTest(unittest.TestCase):
    """M4.2-B: a team can't Defend two turns in a row (on unless switched off). The computer
    has always played so; Rally is a special and doesn't count."""

    def test_after_a_defend_the_team_cannot_defend_on_its_next_turn(self):
        battle = combat([Knight, Archer], [Knight])
        act(battle, 0, "defend")
        pass_turn(battle)
        reason = battle.why_not_allowed(1, "defend")              # any character of the team
        self.assertIn("two turns in a row", reason)
        before = snapshot(battle)
        accepted, events = act(battle, 1, "defend")
        self.assertFalse(accepted)
        self.assertEqual(events_of(events, "invalid"), [{"type": "invalid", "reason": reason}])
        self.assertEqual(snapshot(battle), before)
        self.assertIsNone(battle.why_not_allowed(0, "attack"))
        pass_turn(battle)                                         # left attacks this turn
        pass_turn(battle)                                         # right
        self.assertIsNone(battle.why_not_allowed(0, "defend"))    # allowed again

    def test_each_team_is_counted_on_its_own(self):
        for first in ("left", "right"):
            with self.subTest(first=first):
                battle = combat([Knight], [Knight], first_side=first)
                act(battle, 0, "defend")                          # the first mover defends ...
                self.assertIsNone(battle.why_not_allowed(0, "defend"))   # ... the other team still may
                act(battle, 0, "defend")
                self.assertIsNotNone(battle.why_not_allowed(0, "defend"))

    def test_rally_is_not_blocked_and_does_not_count(self):
        battle = combat([Knight, Archer], [Knight])
        act(battle, 0, "defend")
        pass_turn(battle)
        accepted, _ = act(battle, 0, "special")                   # Rally right after a Defend: allowed
        self.assertTrue(accepted)
        pass_turn(battle)
        self.assertIsNone(battle.why_not_allowed(0, "defend"))    # and a Defend right after Rally too

    def test_it_can_be_switched_off(self):
        battle = combat([Knight], [Knight], anti_stall=False)
        for _ in range(6):
            accepted, _ = act(battle, 0, "defend")
            self.assertTrue(accepted)

    def test_it_is_on_by_default_and_a_new_match_forgets_the_last_defend(self):
        import battle as battle_module
        self.assertTrue(battle_module.ANTI_STALL and battle_module.GUARDED_STRIKE)
        battle = combat([Knight], [Knight])
        self.assertTrue(battle.anti_stall and battle.guarded_strike)
        act(battle, 0, "defend")
        battle.reset(first_side="left")
        self.assertIsNone(battle.why_not_allowed(0, "defend"))


if __name__ == "__main__":
    unittest.main()
