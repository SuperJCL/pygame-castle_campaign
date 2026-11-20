"""Tests for main.py: screens, buttons, keyboard and mouse handling, and window setup.

These tests need Pygame (they are skipped if it isn't installed). They use SDL's
"dummy" video driver, so no window appears. Clicks and key presses are passed to
the same Game.handle_click() / handle_key() methods that real mouse and keyboard
events reach, and the results are checked in the real Battle.
"""
import ctypes
import glob
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
try:
    import pygame
    import main
    from ai import AIController
    from battle import ROUND_LIMIT
    from castle import DEFAULT_LAYOUT, layout_problem, slot_position
    from characters import Archer, Engineer, Knight
except ImportError:          # Pygame is not installed: the tests below are skipped
    pygame = None

SHIFT = pygame.KMOD_SHIFT if pygame else 0
# Both teams have the default cover in these matches (see tests/test_combat.py for how the
# aims were found; they work the same from either side).
COVER_WALL = (45, 76)        # comes down on the enemy cover: 4 blocks in the blast
FRONT_CHARACTER = (45, 83)   # over the cover onto the enemy in slot 0 (the blast also reaches slot 1)
HARMLESS = (80, 10)          # comes down beside the shooter's own cannon: no damage


def load_sdl():
    """Pygame's own copy of the SDL library (Windows, macOS or Linux wheels), or None."""
    folder = os.path.dirname(pygame.__file__)
    for pattern in ("SDL2.dll", os.path.join(".dylibs", "libSDL2*"),
                    os.path.join("..", "pygame.libs", "libSDL2*")):
        for path in glob.glob(os.path.join(folder, pattern)):
            return ctypes.CDLL(path)
    return None


def finish_shot(game):
    """Run frames until the shot in flight has landed."""
    for _ in range(1000):
        if game.battle.projectile is None:
            return
        game.update()
    raise AssertionError("the shot never landed")


def aim(game, angle, power):
    cannon = game.battle.cannons[game.battle.active_side]
    cannon.adjust_angle(angle - cannon.angle)
    cannon.adjust_power(power - cannon.power)


@unittest.skipIf(pygame is None, "Pygame is not installed")
class MainTestCase(unittest.TestCase):
    def setUp(self):
        self.screen = main.open_window()
        self.game = main.Game(self.screen)

    def tearDown(self):
        pygame.quit()

    def click(self, rect):
        """Click the centre of `rect`, then run one frame (as the real main loop does:
        input first, then update(), which reads the battle's events)."""
        self.game.handle_click(pygame.Rect(rect).center)
        self.game.update()

    def start(self, left, right):
        """Two-player (hot seat) match: choose "Two players", pick both teams by clicking,
        press PLACE COVER, and confirm both teams' cover (the default layout, unchanged)."""
        self.pick_teams(left, right)
        self.click(self.game.start_button.rect)
        self.assertEqual((self.game.state, self.game.placing), ("cover", "left"))
        self.click(self.game.confirm_button.rect)
        self.assertEqual((self.game.state, self.game.placing), ("cover", "right"))
        self.click(self.game.confirm_button.rect)
        self.assertEqual(self.game.state, "battle")

    def pick_teams(self, left, right):
        """Two players: choose the mode and team size, and click both teams' characters."""
        self.click(self.game.mode_buttons["pvp"].rect)
        self.click(self.game.size_buttons[len(left) - 1].rect)
        for side, roles in (("left", left), ("right", right)):
            for role in roles:
                self.click(self.game.card_rects[(side, role)])

    def start_vs_ai(self, left):
        """Player vs AI: pick the LEFT team, press PLACE COVER and confirm the LEFT cover."""
        self.click(self.game.size_buttons[len(left) - 1].rect)
        for role in left:
            self.click(self.game.card_rects[("left", role)])
        self.click(self.game.start_button.rect)
        self.assertEqual((self.game.state, self.game.placing), ("cover", "left"))
        self.click(self.game.confirm_button.rect)
        self.assertEqual(self.game.state, "battle")

    def click_slot(self, side, slot):
        self.click(main.slot_rect(side, slot))

    def character_rect(self, side, index):
        return self.game.battle.teams[side].character_rect(index)


class WindowSetupTest(MainTestCase):
    def test_text_input_is_off_so_an_input_method_cannot_capture_keys(self):
        # M1.1 regression: with text input on (Pygame's default), a Chinese input
        # method captured R, then the arrow keys and SPACE, so aiming and restart failed.
        sdl = load_sdl()
        if sdl is None:
            self.skipTest("could not find Pygame's SDL library")
        self.assertEqual(sdl.SDL_IsTextInputActive(), 0)


class DrawingHelpersTest(MainTestCase):
    def test_damaged_blocks_are_drawn_darker(self):
        healthy = main.block_color("left", 100, 100)
        half = main.block_color("left", 50, 100)
        nearly_gone = main.block_color("left", 1, 100)
        self.assertTrue(all(h > d for h, d in zip(healthy, half)), (healthy, half))
        self.assertTrue(all(d > n for d, n in zip(half, nearly_gone)), (half, nearly_gone))

    def test_hp_bar_length_follows_the_hp(self):
        archer = Archer("A", "left")
        self.assertEqual(main.hp_bar_width(archer, 40), 40)
        archer.take_damage(26)                           # 64 / 90 of 40 px = 28.4
        self.assertEqual(main.hp_bar_width(archer, 40), 28)
        archer.take_damage(100)
        self.assertEqual(main.hp_bar_width(archer, 40), 0)

    def test_the_log_says_which_characters_cover_shielded(self):
        event = {"type": "explosion", "side": "left", "kind": "block", "x": 1100.9, "y": 528,
                 "target": None, "blocks_hit": 1, "damage": 50, "guarded": False,
                 "characters_hit": [], "covered": ["Knight"]}
        self.assertEqual(main.describe_event(event),
                         ["Explosion: 1 cover block, 50 damage.", "RIGHT Knight was shielded by cover."])

    def test_the_hud_counts_standing_characters_and_blocks(self):
        self.start([Knight, Archer], [Engineer, Knight])
        battle = self.game.battle
        self.assertEqual(self.game.hud_team_line("left"), "LEFT  2/2 standing   cover 6/6")
        battle.teams["right"].characters[1].take_damage(500)
        battle.castles["right"].blocks[0].take_damage(100)
        self.assertEqual(self.game.hud_team_line("right"), "RIGHT  1/2 standing   cover 5/6")


class TeamSelectionTest(MainTestCase):
    def test_each_team_size_needs_that_many_characters(self):
        for size in (1, 2, 3):
            with self.subTest(size=size):
                selection = main.TeamSelection()
                selection.set_mode(vs_ai=False)
                selection.set_team_size(size)
                for role in (Knight, Archer, Engineer)[:size]:
                    selection.toggle("left", role)
                    self.assertFalse(selection.is_complete())
                for role in (Engineer, Archer, Knight)[:size]:
                    selection.toggle("right", role)
                self.assertTrue(selection.is_complete())
                self.assertEqual(len(selection.roster()["right"]), size)

    def test_against_the_computer_only_the_left_team_is_picked(self):
        selection = main.TeamSelection()                   # Player vs AI is the default
        selection.set_team_size(2)
        self.assertIn("computer", selection.toggle("right", Knight))
        self.assertEqual(selection.picks["right"], [])
        selection.toggle("left", Knight)
        self.assertFalse(selection.is_complete())
        selection.toggle("left", Engineer)
        self.assertTrue(selection.is_complete())

    def test_picking_a_role_twice_removes_it(self):
        selection = main.TeamSelection()
        selection.toggle("left", Knight)
        selection.toggle("left", Knight)
        self.assertEqual(selection.picks["left"], [])

    def test_a_full_team_refuses_another_pick(self):
        selection = main.TeamSelection()                   # team size 1
        self.assertIsNone(selection.toggle("left", Knight))
        refusal = selection.toggle("left", Archer)
        self.assertIn("already has 1", refusal)
        self.assertEqual(selection.picks["left"], [Knight])

    def test_a_smaller_team_size_keeps_the_first_picks(self):
        selection = main.TeamSelection()
        selection.set_team_size(3)
        for role in (Archer, Knight, Engineer):
            selection.toggle("left", role)
        selection.set_team_size(2)
        self.assertEqual(selection.picks["left"], [Archer, Knight])

    def test_team_size_must_be_1_to_3(self):
        with self.assertRaises(ValueError):
            main.TeamSelection().set_team_size(4)


class SelectionScreenTest(MainTestCase):
    def test_the_game_opens_on_team_selection(self):
        self.assertEqual(self.game.state, "select")
        self.assertIsNone(self.game.battle)

    def test_start_is_refused_until_both_teams_are_complete(self):
        self.click(self.game.mode_buttons["pvp"].rect)
        self.click(self.game.card_rects[("left", Knight)])
        self.assertFalse(self.game.start_button.enabled)
        self.click(self.game.start_button.rect)
        self.assertEqual(self.game.state, "select")
        self.click(self.game.card_rects[("right", Archer)])
        self.assertTrue(self.game.start_button.enabled)

    def test_every_team_size_starts_a_match_with_the_chosen_roles(self):
        for size in (1, 2, 3):
            with self.subTest(size=size):
                self.game = main.Game(self.screen)
                left = [Knight, Archer, Engineer][:size]
                right = [Engineer, Knight, Archer][:size]
                self.start(left, right)
                for side, roles in (("left", left), ("right", right)):
                    team = self.game.battle.teams[side]
                    self.assertEqual([type(c) for c in team.characters], roles)

    def test_only_elimination_battles_are_offered(self):
        # M3.4: the M1 cannon duel (won by 60 % castle destruction) is no longer in the game.
        self.assertFalse(hasattr(self.game, "duel_button"))
        with self.assertRaises(TypeError):
            main.Battle()                                  # every battle needs two teams
        self.game.draw()                                   # the selection screen states the rule


class CoverPlacementScreenTest(MainTestCase):
    """M3.4-B: the cover placement screen, after team selection and before the battle."""

    def setUp(self):
        super().setUp()
        self.pick_teams([Knight, Archer], [Engineer, Knight])
        self.click(self.game.start_button.rect)                 # PLACE COVER

    def layout(self, side="left"):
        return self.game.setup.layouts[side]

    def test_the_left_team_places_its_cover_first_starting_from_the_default(self):
        self.assertEqual((self.game.state, self.game.placing), ("cover", "left"))
        self.assertEqual(self.layout(), DEFAULT_LAYOUT)
        self.assertEqual(self.game.cover_count_text(), "Blocks: 6 / 6")
        self.assertIn("LEFT", self.game.cover_title())
        self.game.draw()                                         # the screen draws without errors

    def test_clicking_an_occupied_slot_removes_its_block(self):
        self.click_slot("left", 3)
        self.assertEqual(self.layout(), (0, 1, 2, 4, 5))
        self.assertEqual(self.game.cover_count_text(), "Blocks: 5 / 6")
        self.assertIn("removed", self.game.message)

    def test_clicking_an_empty_slot_places_a_block(self):
        self.click_slot("left", 3)
        self.click_slot("left", 6)                               # on top of slot 2
        self.assertEqual(self.layout(), (0, 1, 2, 4, 5, 6))
        self.assertIn("placed", self.game.message)

    def test_a_raised_block_needs_a_block_under_it_and_the_screen_says_so(self):
        self.click_slot("left", 3)
        self.click_slot("left", 7)                               # slot 3 under it is empty now
        self.assertEqual(self.layout(), (0, 1, 2, 4, 5))
        self.assertIn("needs a block under it", self.game.message)

    def test_removing_a_supporting_block_also_removes_the_block_on_top(self):
        self.click_slot("left", 0)                               # slot 4 stood on slot 0
        self.assertEqual(self.layout(), (1, 2, 3, 5))
        self.assertIn("block on top", self.game.message)

    def test_a_seventh_block_is_refused(self):
        self.click_slot("left", 6)
        self.assertEqual(self.layout(), DEFAULT_LAYOUT)
        self.assertIn("at most 6", self.game.message)

    def test_a_cover_of_zero_blocks_can_be_confirmed(self):
        for slot in (0, 1, 2, 3):                                # the raised blocks go with them
            self.click_slot("left", slot)
        self.assertEqual(self.layout(), ())
        self.assertEqual(self.game.cover_count_text(), "Blocks: 0 / 6")
        self.click(self.game.confirm_button.rect)
        self.click(self.game.confirm_button.rect)                # RIGHT keeps the default
        self.assertEqual(self.game.state, "battle")
        self.assertEqual(self.game.battle.castles["left"].blocks, ())
        self.assertEqual(self.game.battle.castles["right"].layout, DEFAULT_LAYOUT)

    def test_the_right_team_uses_the_mirrored_slots(self):
        for slot in range(8):
            left, right = main.slot_rect("left", slot), main.slot_rect("right", slot)
            self.assertEqual((right.x, right.y, right.size), (1280 - left.x - 32, left.y, left.size))
        self.click(self.game.confirm_button.rect)
        self.assertEqual(self.game.placing, "right")
        self.click_slot("left", 3)                               # LEFT's slots don't react now
        self.assertEqual(self.layout("left"), DEFAULT_LAYOUT)
        self.click_slot("right", 3)                              # x 980: next to the RIGHT cannon
        self.assertEqual(self.layout("right"), (0, 1, 2, 4, 5))
        self.assertEqual(self.layout("left"), DEFAULT_LAYOUT)

    def test_an_illegal_layout_never_reaches_the_battle(self):
        self.game.setup.layouts["left"] = (5,)                   # forced from outside: floats
        self.click(self.game.confirm_button.rect)
        self.assertEqual((self.game.state, self.game.placing), ("cover", "left"))
        self.assertIn("needs a block under it", self.game.message)
        self.assertIsNone(self.game.battle)

    def test_empty_and_occupied_slots_look_different(self):
        self.click_slot("left", 3)                               # slot 3 empty; slot 7 can't take a block
        self.game.draw()

        def colour(slot):                                        # inside the outline, beside the "+"
            rect = main.slot_rect("left", slot)
            return tuple(self.screen.get_at((rect.left + 5, rect.top + 5)))[:3]
        occupied, empty, unsupported = colour(0), colour(3), colour(7)
        self.assertEqual(occupied, main.block_color("left", 100, 100))
        self.assertEqual(empty, main.OPEN_SLOT_COLOR)
        self.assertEqual(len({occupied, empty, unsupported}), 3)

    def test_slots_stay_clear_of_characters_cannons_and_text(self):
        self.click(self.game.confirm_button.rect)                # check the RIGHT screen too
        half_width = max(16, self.game.tiny_font.size("Engineer")[0] // 2 + 1)   # the widest name
        for side in ("left", "right"):
            text_bottom = self.game.cover_text_bottom()
            cannon = main.Cannon(side)
            for slot in range(8):
                rect = main.slot_rect(side, slot)
                self.assertGreater(rect.top, text_bottom + 40)
                self.assertLessEqual(rect.bottom, main.GROUND_Y)
                self.assertFalse(rect.colliderect((cannon.x - 30, cannon.y - 30, 60, 60)))
                for index in range(3):
                    x = main.SLOT_X[side][index]
                    figure = pygame.Rect(x - half_width, main.GROUND_Y - 44 - 40, 2 * half_width, 84)
                    self.assertFalse(rect.colliderect(figure), (side, slot, index))

    def test_the_instructions_explain_placing_removing_and_support(self):
        text = " ".join(self.game.cover_help_lines())
        for words in ("empty slot", "remove", "under it", "6 blocks", "only defeating every enemy"):
            self.assertIn(words, text)
        for line in self.game.cover_help_lines():
            self.assertLess(self.game.small_font.size(line)[0], main.WINDOW_WIDTH - 40, line)

    def test_enter_confirms_and_backspace_goes_back(self):
        self.game.handle_key(pygame.K_RETURN, 0)
        self.assertEqual(self.game.placing, "right")
        self.game.handle_key(pygame.K_BACKSPACE, 0)
        self.assertEqual(self.game.placing, "left")
        self.game.handle_key(pygame.K_BACKSPACE, 0)
        self.assertEqual(self.game.state, "select")


class SetupFlowTest(MainTestCase):
    """M3.4-B: selection -> LEFT cover -> (RIGHT cover in two-player mode) -> battle."""

    def test_against_the_computer_only_the_left_cover_is_placed_by_hand(self):
        self.game = main.Game(self.screen, ai_seed=3)
        self.click(self.game.card_rects[("left", Knight)])
        self.click(self.game.start_button.rect)
        self.click_slot("left", 3)
        self.click(self.game.confirm_button.rect)
        self.assertEqual(self.game.state, "battle")
        battle = self.game.battle
        twin = AIController("right", "normal", seed=3)           # the same seed chooses the same
        twin.pick_team(1)
        self.assertEqual(battle.layouts, {"left": (0, 1, 2, 4, 5), "right": twin.choose_layout()})
        self.assertIsNone(layout_problem(battle.layouts["right"]))
        self.assertLessEqual(len(battle.castles["right"].blocks), 6)
        self.assertIn("AI (Normal) placed 6 cover blocks.", self.game.log)

    def test_two_players_each_place_their_own_cover(self):
        self.pick_teams([Knight], [Archer])
        self.click(self.game.start_button.rect)
        self.click_slot("left", 3)
        self.click(self.game.confirm_button.rect)
        self.assertEqual(self.game.placing, "right")
        self.assertIn("RIGHT", self.game.cover_title())
        self.click_slot("right", 0)
        self.click(self.game.confirm_button.rect)
        self.assertEqual(self.game.battle.layouts, {"left": (0, 1, 2, 4, 5), "right": (1, 2, 3, 5)})

    def test_back_from_the_right_cover_keeps_both_covers(self):
        self.pick_teams([Knight], [Archer])
        self.click(self.game.start_button.rect)
        self.click_slot("left", 3)
        self.click(self.game.confirm_button.rect)
        self.click_slot("right", 0)
        self.click(self.game.back_button.rect)
        self.assertEqual((self.game.state, self.game.placing), ("cover", "left"))
        self.assertEqual(self.game.setup.layouts, {"left": (0, 1, 2, 4, 5), "right": (1, 2, 3, 5)})
        self.click(self.game.confirm_button.rect)
        self.click(self.game.confirm_button.rect)
        self.assertEqual(self.game.battle.layouts, {"left": (0, 1, 2, 4, 5), "right": (1, 2, 3, 5)})

    def test_back_from_the_left_cover_returns_to_selection_with_everything_kept(self):
        self.pick_teams([Knight, Archer], [Engineer, Knight])
        self.click(self.game.start_button.rect)
        self.click_slot("left", 2)
        self.click(self.game.back_button.rect)
        self.assertEqual(self.game.state, "select")
        self.assertEqual(self.game.selection.picks, {"left": [Knight, Archer], "right": [Engineer, Knight]})
        self.assertFalse(self.game.selection.vs_ai)
        self.click(self.game.start_button.rect)
        self.assertEqual(self.game.setup.layouts["left"], (0, 1, 3, 4, 5))

    def test_changing_the_teams_keeps_the_cover_choices(self):
        # Cover slots never depend on the team size or roles, so the choices stay valid.
        self.pick_teams([Knight, Archer], [Engineer, Knight])
        self.click(self.game.start_button.rect)
        self.click_slot("left", 0)
        self.click(self.game.confirm_button.rect)
        self.click_slot("right", 3)
        self.click(self.game.back_button.rect)
        self.click(self.game.back_button.rect)
        self.click(self.game.size_buttons[0].rect)               # 1 v 1 now: the first picks stay
        self.click(self.game.card_rects[("left", Knight)])       # swap the LEFT role
        self.click(self.game.card_rects[("left", Archer)])
        self.click(self.game.start_button.rect)
        self.click(self.game.confirm_button.rect)
        self.click(self.game.confirm_button.rect)
        battle = self.game.battle
        self.assertEqual([type(c) for c in battle.teams["left"].characters], [Archer])
        self.assertEqual(battle.layouts, {"left": (1, 2, 3, 5), "right": (0, 1, 2, 4, 5)})

    def test_the_two_teams_never_share_one_layout(self):
        self.pick_teams([Knight], [Archer])
        self.click(self.game.start_button.rect)
        self.click_slot("left", 3)
        self.assertEqual(self.game.setup.layouts["right"], DEFAULT_LAYOUT)
        for layout in self.game.setup.layouts.values():
            self.assertIsInstance(layout, tuple)                 # can't be changed in place

    def test_a_rematch_keeps_both_covers_and_the_computer_layout(self):
        self.game = main.Game(self.screen, ai_seed=8)
        self.click(self.game.size_buttons[1].rect)
        for role in (Knight, Archer):
            self.click(self.game.card_rects[("left", role)])
        self.click(self.game.start_button.rect)
        self.click_slot("left", 1)
        self.click(self.game.confirm_button.rect)
        battle = self.game.battle
        layouts = dict(battle.layouts)
        for side in ("left", "right"):
            for block in battle.castles[side].blocks:
                block.take_damage(60)
            for character in battle.teams[side].characters:
                character.take_damage(30)
                character.defend()
        battle.castles["right"].blocks[0].take_damage(100)
        self.game.handle_key(pygame.K_r, 0)
        self.assertEqual(battle.layouts, layouts)
        self.assertEqual(battle.layouts["left"], (0, 2, 3, 4))
        for side in ("left", "right"):
            self.assertEqual(battle.castles[side].layout, layouts[side])
            self.assertTrue(all(block.hp == 100 for block in battle.castles[side].blocks))
            for character in battle.teams[side].characters:
                self.assertEqual((character.hp, character.is_defending), (character.max_hp, False))


class ActorSelectionTest(MainTestCase):
    def setUp(self):
        super().setUp()
        self.start([Knight, Archer], [Engineer, Knight])

    def test_the_first_living_character_is_selected_at_the_start(self):
        self.assertIsInstance(self.game.selected_character(), Knight)

    def test_clicking_a_character_selects_it_and_shows_its_stats(self):
        self.click(self.character_rect("left", 1))
        self.assertIsInstance(self.game.selected_character(), Archer)
        info = " | ".join(self.game.selected_info_lines())
        for text in ("Archer", "Level 1", "HP 90/90", "ATK 40", "DEF 4", "EXP 0/30", "Power Shot: ready"):
            self.assertIn(text, info)

    def test_number_keys_also_select(self):
        self.game.handle_key(pygame.K_2, 0)
        self.assertIsInstance(self.game.selected_character(), Archer)

    def test_defeated_characters_cannot_be_selected(self):
        self.game.battle.teams["left"].characters[1].take_damage(90)
        self.click(self.character_rect("left", 1))
        self.assertIsInstance(self.game.selected_character(), Knight)
        self.assertIn("defeated", self.game.message)

    def test_enemy_characters_cannot_be_selected(self):
        self.click(self.character_rect("right", 0))
        self.assertIsInstance(self.game.selected_character(), Knight)
        self.assertEqual(self.game.battle.active_side, "left")


class ActionButtonTest(MainTestCase):
    def test_attack_button_fires_the_cannon_for_the_selected_character(self):
        self.start([Knight], [Engineer])
        aim(self.game, *COVER_WALL)
        self.click(self.game.action_buttons["attack"].rect)
        self.assertIsNotNone(self.game.battle.projectile)
        finish_shot(self.game)
        self.assertEqual(self.game.battle.castles["right"].total_hp(), 600 - 200)  # Knight: 4 x 50
        self.assertEqual(self.game.battle.active_side, "right")

    def test_space_is_the_attack_shortcut(self):
        self.start([Knight], [Engineer])
        self.game.handle_key(pygame.K_SPACE, 0)
        self.assertIsNotNone(self.game.battle.projectile)

    def test_arrow_keys_aim_the_active_cannon(self):
        self.start([Knight], [Engineer])
        self.game.handle_key(pygame.K_UP, SHIFT)
        self.game.handle_key(pygame.K_RIGHT, 0)
        cannon = self.game.battle.cannons["left"]
        self.assertEqual((cannon.angle, cannon.power), (50, 51))

    def test_defend_button_ends_the_turn_at_once(self):
        self.start([Knight], [Engineer])
        self.click(self.game.action_buttons["defend"].rect)
        self.assertTrue(self.game.battle.teams["left"].characters[0].is_defending)
        self.assertIsNone(self.game.battle.projectile)
        self.assertEqual(self.game.battle.active_side, "right")

    def test_rally_button_makes_the_whole_team_defend(self):
        self.start([Knight, Archer], [Engineer, Archer])
        self.click(self.game.action_buttons["special"].rect)
        self.assertTrue(all(c.is_defending for c in self.game.battle.teams["left"].characters))
        self.assertEqual(self.game.battle.active_side, "right")
        self.assertIn("Rally", " ".join(self.game.log))

    def test_repair_button_repairs_at_once(self):
        self.start([Engineer], [Knight])
        castle = self.game.battle.castles["left"]
        castle.blocks[0].take_damage(80)
        self.click(self.game.action_buttons["special"].rect)
        self.assertEqual(castle.total_hp(), 600)                       # only 80 HP were missing
        self.assertEqual(self.game.battle.active_side, "right")
        self.assertIn("regains 80 HP", " ".join(self.game.log))

    def test_power_shot_button_launches_a_shot(self):
        self.start([Archer], [Knight])
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["special"].rect)
        self.assertIsNotNone(self.game.battle.projectile)
        finish_shot(self.game)
        self.assertEqual(self.game.battle.teams["right"].characters[0].hp, 140 - 60)
        self.assertIn("Knight takes 60 damage", " ".join(self.game.log))

    def test_an_unavailable_special_is_disabled_and_explained(self):
        self.start([Engineer], [Knight])                    # nothing to repair yet
        self.game.update()
        button = self.game.action_buttons["special"]
        self.assertFalse(button.enabled)
        self.click(button.rect)
        self.assertEqual(self.game.battle.active_side, "left")   # nothing happened
        self.assertIn("nothing to repair", " ".join(self.game.action_hint_lines()))

    def test_the_panel_shows_the_cooldown_counting_down(self):
        self.start([Knight], [Engineer])
        self.click(self.game.action_buttons["special"].rect)     # Rally: cooldown 4
        self.click(self.game.action_buttons["defend"].rect)      # right's turn; round 2 starts
        info = " | ".join(self.game.selected_info_lines())
        self.assertIn("Rally is recharging: ready in 3 rounds", info)
        self.game.update()
        self.assertFalse(self.game.action_buttons["special"].enabled)

    def test_buttons_do_nothing_while_a_shot_flies(self):
        self.start([Knight], [Engineer])
        self.click(self.game.action_buttons["attack"].rect)
        self.game.update()
        self.assertFalse(self.game.action_buttons["defend"].enabled)
        self.click(self.game.action_buttons["defend"].rect)
        self.assertFalse(self.game.battle.teams["left"].characters[0].is_defending)

    def test_the_log_and_hp_follow_character_damage(self):
        self.start([Knight], [Archer])
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)
        archer = self.game.battle.teams["right"].characters[0]
        self.assertEqual(archer.hp, 90 - 26)
        self.assertIn("Archer takes 26 damage", " ".join(self.game.log))
        self.assertIn("HP 64/90", " ".join(self.game.selected_info_lines()))   # right's turn: Archer selected


class KeyboardTest(MainTestCase):
    """Aiming and R with the keyboard (these were checked in the M1 duel until M3.4)."""

    def setUp(self):
        super().setUp()
        self.start([Knight], [Archer])

    def test_arrow_keys_change_angle_and_power_by_1_or_5_with_shift(self):
        cannon = self.game.battle.cannons["left"]          # starts at 45 deg, power 50
        self.game.handle_key(pygame.K_UP, 0)
        self.game.handle_key(pygame.K_UP, SHIFT)
        self.game.handle_key(pygame.K_DOWN, 0)
        self.assertEqual(cannon.angle, 45 + 1 + 5 - 1)
        self.game.handle_key(pygame.K_RIGHT, SHIFT)
        self.game.handle_key(pygame.K_LEFT, 0)
        self.assertEqual(cannon.power, 50 + 5 - 1)

    def test_the_right_cannon_answers_the_same_keys_on_its_turn(self):
        self.game.handle_key(pygame.K_SPACE, 0)            # left attacks
        finish_shot(self.game)
        self.assertEqual(self.game.battle.active_side, "right")
        self.game.handle_key(pygame.K_UP, SHIFT)
        self.game.handle_key(pygame.K_LEFT, 0)
        right, left = self.game.battle.cannons["right"], self.game.battle.cannons["left"]
        self.assertEqual((right.angle, right.power), (50, 49))
        self.assertEqual((left.angle, left.power), (45, 50))

    def test_aiming_is_locked_while_a_shot_flies(self):
        self.game.handle_key(pygame.K_SPACE, 0)
        self.game.handle_key(pygame.K_UP, 0)
        self.game.handle_key(pygame.K_RIGHT, 0)
        cannon = self.game.battle.cannons["left"]
        self.assertEqual((cannon.angle, cannon.power), (45, 50))

    def test_r_during_a_flight_cancels_the_shot(self):
        self.game.handle_key(pygame.K_SPACE, 0)
        for _ in range(10):
            self.game.update()
        self.assertIsNotNone(self.game.battle.projectile)
        self.game.handle_key(pygame.K_r, 0)
        self.assertIsNone(self.game.battle.projectile)
        self.assertTrue(self.game.battle.can_fire())

    def test_r_clears_explosion_effects(self):
        self.game.handle_key(pygame.K_SPACE, 0)
        finish_shot(self.game)                              # the default aim explodes on the ground
        self.assertEqual(len(self.game.explosions), 1)
        self.game.handle_key(pygame.K_r, 0)
        self.assertEqual(self.game.explosions, [])


class AbilityPreflightTest(MainTestCase):
    """M3.1 preflight: each special played through the interface (clicks and frames),
    checked in the real Battle and on the drawn screen. Both teams are played by clicking."""

    def act(self, action, aim_at=None, actor=None):
        """The active team clicks a character (optional), aims (optional) and clicks an action;
        frames run until any shot has landed."""
        if actor is not None:
            self.click(self.character_rect(self.game.battle.active_side, actor))
        if aim_at is not None:
            aim(self.game, *aim_at)
        self.click(self.game.action_buttons[action].rect)
        finish_shot(self.game)

    def pixel_above_head(self, side, index):
        """A screen pixel 8 px above a character's head: plain sky unless something is drawn there."""
        self.game.draw()
        left, top, width, _ = self.character_rect(side, index)
        return tuple(self.screen.get_at((left + width // 2, top - 8)))[:3]

    def test_rally_halves_the_next_enemy_hit_on_every_living_ally(self):
        self.start([Knight, Archer, Engineer], [Archer, Engineer, Knight])
        self.assertEqual(self.pixel_above_head("left", 1), main.SKY_COLOR)
        self.act("special")                                    # the left Knight (chosen first): Rally
        self.assertEqual(self.game.battle.active_side, "right")
        for index in range(3):                                 # every ally shows the defend bubble
            self.assertNotEqual(self.pixel_above_head("left", index), main.SKY_COLOR)
        self.act("attack", FRONT_CHARACTER)                    # right Archer hits slots 0 and 1
        left = self.game.battle.teams["left"].characters
        # Without Rally: 40-12 = 28 and 40-4 = 36. Rally halves each one; slot 2 is out of range.
        self.assertEqual([c.hp for c in left], [140 - 14, 90 - 18, 110])
        log = " ".join(self.game.log)
        self.assertIn("Rally: 3 allies are defending", log)
        self.assertIn("LEFT Archer takes 18 damage", log)
        for _ in range(main.EXPLOSION_FRAMES):                 # let the explosion fade
            self.game.update()
        self.assertEqual(self.pixel_above_head("left", 1), main.SKY_COLOR)   # Rally is over

    def test_power_shot_does_more_damage_than_the_same_archer_attack(self):
        self.start([Archer], [Knight])
        knight = self.game.battle.teams["right"].characters[0]
        self.act("attack", FRONT_CHARACTER)                    # 40 - 12 = 28
        self.assertEqual(knight.hp, 140 - 28)
        self.act("attack", HARMLESS)                           # right passes
        self.act("special", FRONT_CHARACTER)                   # 40 x 1.5 = 60, DEF ignored
        self.assertEqual(knight.hp, 140 - 28 - 60)
        log = " ".join(self.game.log)
        self.assertIn("Knight takes 28 damage", log)
        self.assertIn("uses Power Shot", log)
        self.assertIn("Knight takes 60 damage", log)

    def test_repair_restores_hp_lost_to_a_real_hit_most_damaged_first(self):
        self.start([Knight], [Engineer])
        castle = self.game.battle.castles["right"]
        self.act("attack", COVER_WALL)                         # left: 4 blocks x 50
        self.assertEqual(castle.total_hp(), 600 - 200)
        self.assertTrue(self.game.action_buttons["special"].enabled)   # now there is damage to repair
        self.act("special")                                    # right Engineer: Repair
        self.assertEqual(castle.total_hp(), 600 - 200 + 150)
        self.assertEqual(sorted(b.hp for b in castle.blocks if b.hp < 100), [50])
        self.assertEqual(self.game.hud_team_line("right"), "RIGHT  1/1 standing   cover 6/6")
        self.assertIn("regains 150 HP", " ".join(self.game.log))
        self.assertEqual(self.game.battle.active_side, "left")

    def test_defend_also_guards_the_cover_and_the_log_says_so(self):
        self.start([Knight], [Knight])
        castle = self.game.battle.castles["left"]
        self.act("defend")                                     # left Knight defends
        self.act("attack", COVER_WALL)                         # right: 4 blocks, 50 halved to 25
        self.assertEqual(castle.total_hp(), 600 - 100)
        self.assertIn("Explosion: 4 cover blocks, 100 damage.", self.game.log)
        self.assertIn("Cover Guard halved the damage to the blocks.", self.game.log)
        for line in self.game.log:                             # the log panel doesn't wrap lines
            self.assertLessEqual(self.game.tiny_font.size(line)[0], main.WINDOW_WIDTH - 870)
        self.act("attack", HARMLESS)                           # left passes: its guard is over
        self.act("attack", COVER_WALL)                         # full 50 on each block now
        self.assertEqual(castle.total_hp(), 600 - 300)
        self.assertEqual(" ".join(self.game.log).count("Cover Guard"), 1)

    def test_cooldown_counts_down_at_round_starts_and_blocks_the_special_until_ready(self):
        self.start([Archer], [Knight])
        archer = self.game.battle.teams["left"].characters[0]
        self.act("special", HARMLESS)                          # round 1: Power Shot, cooldown 3
        self.assertEqual((self.game.battle.active_side, archer.special_cooldown), ("right", 3))
        self.act("defend")                                     # right; round 2 starts
        for round_number, waiting in ((2, "ready in 2 rounds"), (3, "ready in 1 round")):
            self.assertEqual(self.game.battle.round_number, round_number)
            self.assertFalse(self.game.action_buttons["special"].enabled)
            self.assertIn(waiting, " ".join(self.game.action_hint_lines()))
            before = (archer.special_cooldown, self.game.battle.active_side,
                      self.game.battle.teams["right"].characters[0].hp)
            self.click(self.game.action_buttons["special"].rect)            # refused: no change
            self.assertIsNone(self.game.battle.projectile)
            self.assertEqual((archer.special_cooldown, self.game.battle.active_side,
                              self.game.battle.teams["right"].characters[0].hp), before)
            self.act("defend")                                 # left
            self.assertEqual(archer.special_cooldown, 3 - (round_number - 1))   # no tick mid-round
            self.act("defend")                                 # right; the next round starts
        self.assertEqual((self.game.battle.round_number, archer.special_cooldown), (4, 0))
        self.assertTrue(self.game.action_buttons["special"].enabled)
        self.click(self.game.action_buttons["special"].rect)
        self.assertIsNotNone(self.game.battle.projectile)     # round 4 = 1 + 3: ready again


class ResultScreenTest(MainTestCase):
    def test_defeating_every_enemy_shows_the_result(self):
        self.start([Knight], [Archer])
        self.game.battle.teams["right"].characters[0].take_damage(64)   # one hit left
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)
        self.assertEqual(self.game.state, "result")
        self.assertEqual(self.game.result_title(), "LEFT TEAM WINS!")
        self.assertIn("defeated", self.game.result_reason())

    def test_destroying_cover_does_not_end_the_match(self):
        self.start([Knight], [Archer])
        for block in self.game.battle.castles["right"].blocks:
            block.take_damage(50)
        aim(self.game, *COVER_WALL)                            # destroys the 4 blocks in the blast
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)
        self.assertEqual(self.game.hud_team_line("right"), "RIGHT  1/1 standing   cover 2/6")
        self.assertEqual(self.game.state, "battle")
        self.assertIsNone(self.game.battle.winner)

    def win_quickly(self):
        self.start([Knight, Archer], [Engineer, Knight])
        for character in self.game.battle.teams["right"].characters:
            character.take_damage(200)                              # everyone defeated
        self.click(self.game.action_buttons["defend"].rect)          # the turn ends -> left wins
        self.assertEqual(self.game.state, "result")

    def test_rematch_starts_a_fresh_match_with_the_same_teams(self):
        self.win_quickly()
        self.click(self.game.rematch_button.rect)
        self.assertEqual(self.game.state, "battle")
        right = self.game.battle.teams["right"].characters
        self.assertEqual([type(c) for c in right], [Engineer, Knight])
        self.assertEqual([c.hp for c in right], [110, 140])
        # M3.3: the side that moves first alternates, so RIGHT starts the first rematch.
        self.assertEqual((self.game.battle.round_number, self.game.battle.active_side), (1, "right"))

    def test_change_teams_returns_to_selection_with_the_picks_kept(self):
        self.win_quickly()
        self.click(self.game.change_teams_button.rect)
        self.assertEqual(self.game.state, "select")
        self.assertEqual(self.game.selection.picks["left"], [Knight, Archer])

    def test_r_is_a_rematch_shortcut(self):
        self.win_quickly()
        self.game.handle_key(pygame.K_r, 0)
        self.assertEqual(self.game.state, "battle")
        self.assertIsNone(self.game.battle.winner)


def end_match_now(test):
    """The team to move wins at once: every enemy character is defeated, then it ends its turn."""
    battle = test.game.battle
    enemy = "right" if battle.active_side == "left" else "left"
    for character in battle.teams[enemy].characters:
        character.take_damage(500)
    test.click(test.game.action_buttons["defend"].rect)
    test.assertEqual(test.game.state, "result")


def defend_until_the_end(test):
    """Both teams click DEFEND every turn until the match ends (two-player mode)."""
    for _ in range(2 * ROUND_LIMIT + 2):
        if test.game.state == "result":
            return
        test.click(test.game.action_buttons["defend"].rect)
    test.assertEqual(test.game.state, "result")


class RematchAndFirstMoverTest(MainTestCase):
    """M3.3: the side that moves first alternates on every rematch (LEFT, RIGHT, LEFT, ...)."""

    def test_the_first_mover_alternates_on_every_rematch(self):
        self.start([Knight, Archer], [Engineer, Knight])
        firsts = [self.game.battle.active_side]
        for _ in range(3):
            end_match_now(self)
            self.click(self.game.rematch_button.rect)
            firsts.append(self.game.battle.active_side)
        self.game.handle_key(pygame.K_r, 0)                    # R is a rematch too
        firsts.append(self.game.battle.active_side)
        self.assertEqual(firsts, ["left", "right", "left", "right", "left"])
        self.game.handle_key(pygame.K_r, 0)
        self.assertEqual(self.game.battle.round_number, 1)     # a right-first match still shows Round 1
        self.assertEqual(self.game.log, ["--- Round 1 ---", "RIGHT team moves first."])

    def test_new_teams_start_with_left_again(self):
        self.start([Knight], [Archer])
        end_match_now(self)
        self.click(self.game.rematch_button.rect)              # RIGHT starts the rematch
        end_match_now(self)
        self.click(self.game.change_teams_button.rect)
        self.click(self.game.start_button.rect)                # same picks, a new series ...
        self.assertEqual(self.game.state, "cover")             # ... through the cover screens again
        self.click(self.game.confirm_button.rect)
        self.click(self.game.confirm_button.rect)
        self.assertEqual(self.game.battle.active_side, "left")

    def test_rematch_resets_the_match_and_keeps_teams_cover_and_difficulty(self):
        self.click(self.game.difficulty_buttons["hard"].rect)
        self.click(self.game.size_buttons[1].rect)
        for role in (Knight, Archer):
            self.click(self.game.card_rects[("left", role)])
        self.click(self.game.start_button.rect)
        self.click(self.game.confirm_button.rect)              # the LEFT cover: the default layout
        ai, battle = self.game.ai, self.game.battle
        layouts = dict(battle.layouts)
        right_roles = [type(c) for c in battle.teams["right"].characters]
        self.click(self.character_rect("left", 1))             # the Archer
        aim(self.game, *COVER_WALL)
        self.click(self.game.action_buttons["special"].rect)   # Power Shot: block damage, EXP, cooldown
        finish_shot(self.game)
        self.assertLess(battle.castles["right"].total_hp(), 600)   # the computer's own cover was hit
        self.game.handle_key(pygame.K_r, 0)                    # R restarts at any time
        self.assertIs(self.game.ai, ai)
        self.assertEqual(ai.difficulty, "hard")
        self.assertIsNone(battle.projectile)
        self.assertEqual([type(c) for c in battle.teams["left"].characters], [Knight, Archer])
        self.assertEqual([type(c) for c in battle.teams["right"].characters], right_roles)
        self.assertEqual(battle.layouts, layouts)
        for side in ("left", "right"):
            self.assertEqual(battle.castles[side].layout, layouts[side])
            self.assertEqual(battle.castles[side].total_hp(), 600)
            for character in battle.teams[side].characters:
                self.assertEqual((character.hp, character.exp, character.level, character.special_cooldown),
                                 (character.max_hp, 0, 1, 0))
        self.assertEqual((battle.round_number, battle.active_side, battle.winner), (1, "right", None))
        self.assertEqual(self.game.explosions, [])

    def test_the_computer_moves_first_by_itself_when_right_starts(self):
        self.start_vs_ai([Knight])                             # Player vs AI, Normal, 1 v 1
        end_match_now(self)
        self.click(self.game.rematch_button.rect)
        self.assertEqual(self.game.battle.active_side, "right")
        self.assertTrue(self.game.is_ai_turn())
        self.assertFalse(self.game.action_buttons["attack"].enabled)
        for _ in range(main.AI_DELAY_FRAMES):
            self.game.update()
        self.assertIn("AI (Normal):", " ".join(self.game.log))
        finish_shot(self.game)
        self.assertEqual((self.game.battle.active_side, self.game.battle.round_number), ("left", 1))
        self.click(self.game.action_buttons["defend"].rect)    # the human completes round 1
        self.assertEqual((self.game.battle.active_side, self.game.battle.round_number), ("right", 2))

    def test_two_players_can_play_with_right_first(self):
        self.start([Knight], [Archer])
        self.game.handle_key(pygame.K_r, 0)                    # RIGHT starts
        self.assertTrue(self.game.action_buttons["attack"].enabled)
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["attack"].rect)    # the RIGHT Archer: 40 - 12 = 28
        finish_shot(self.game)
        self.assertEqual(self.game.battle.teams["left"].characters[0].hp, 140 - 28)
        self.assertEqual((self.game.battle.active_side, self.game.battle.round_number), ("left", 1))
        self.click(self.game.action_buttons["defend"].rect)
        self.assertEqual((self.game.battle.active_side, self.game.battle.round_number), ("right", 2))


class CoverGuardIndicatorTest(MainTestCase):
    """M3.3 (Castle Guard, called Cover Guard since M3.4): guarded cover gets a blue outline
    and a GUARDED badge, drawn straight from Battle.castle_guarded(side)."""

    def outline_pixel(self, side):
        """A pixel just inside the outer border of the slot-0 block (next to the characters)."""
        self.game.draw()
        x = 173 if side == "left" else 1106
        return tuple(self.screen.get_at((x, 544)))[:3]

    def badge_pixel(self, side):
        self.game.draw()
        badge = main.guard_badge_rect(side)
        return tuple(self.screen.get_at((badge.left + 2, badge.centery)))[:3]

    def test_the_indicator_appears_and_disappears_with_the_guard(self):
        self.start([Knight], [Knight])
        self.assertNotEqual(self.outline_pixel("left"), main.GUARD_COLOR)
        self.click(self.game.action_buttons["defend"].rect)    # LEFT defends
        self.assertEqual(self.outline_pixel("left"), main.GUARD_COLOR)
        self.assertEqual(self.badge_pixel("left"), main.GUARD_COLOR)
        self.assertNotEqual(self.outline_pixel("right"), main.GUARD_COLOR)
        self.assertNotEqual(self.badge_pixel("right"), main.GUARD_COLOR)
        aim(self.game, *HARMLESS)
        self.click(self.game.action_buttons["attack"].rect)    # RIGHT's turn passes...
        finish_shot(self.game)
        self.assertEqual(self.game.battle.active_side, "left")  # ...LEFT's turn ends the guard
        self.assertNotEqual(self.outline_pixel("left"), main.GUARD_COLOR)
        self.assertNotEqual(self.badge_pixel("left"), main.GUARD_COLOR)

    def test_the_indicator_reads_the_battle_state_directly(self):
        self.start([Knight], [Knight])
        knight = self.game.battle.teams["right"].characters[0]
        knight.defend()                                        # changed in the Battle only
        self.assertTrue(self.game.battle.castle_guarded("right"))
        self.assertEqual(self.outline_pixel("right"), main.GUARD_COLOR)
        knight.clear_defend()
        self.assertNotEqual(self.outline_pixel("right"), main.GUARD_COLOR)
        knight.defend()
        knight.take_damage(500)                                # a defeated defender guards nothing
        self.assertFalse(self.game.battle.castle_guarded("right"))
        self.assertNotEqual(self.outline_pixel("right"), main.GUARD_COLOR)

    def test_the_badge_does_not_cover_characters_bars_blocks_or_the_hud(self):
        self.start([Knight, Archer, Engineer], [Knight, Archer, Engineer])
        battle = self.game.battle
        for side in ("left", "right"):
            badge = main.guard_badge_rect(side)
            self.assertGreater(badge.top, 75)                  # below the HUD lines
            self.assertLessEqual(badge.bottom, main.GROUND_Y)
            for index in range(3):
                left, top, width, height = battle.teams[side].character_rect(index)
                # The figure plus its name and HP bar, which are drawn up to 66 px above it.
                area = pygame.Rect(left + width // 2 - 35, top - 66, 70, height + 66)
                self.assertFalse(badge.colliderect(area), (side, index))
            for slot in range(8):                              # every slot, used or not
                x, y = slot_position(side, slot)
                self.assertFalse(badge.colliderect((x, y, 32, 32)), (side, slot))
            pivot_x, pivot_y = battle.cannons[side].x, battle.cannons[side].y
            self.assertFalse(badge.colliderect((pivot_x - 30, pivot_y - 30, 60, 60)))


class ResultReasonTest(MainTestCase):
    """The result screen shows the winner (or DRAW), the reason and the rounds played."""

    def test_an_elimination_shows_its_reason_and_the_rounds(self):
        self.start([Knight], [Archer])
        end_match_now(self)
        self.assertEqual(self.game.result_title(), "LEFT TEAM WINS!")
        self.assertEqual(self.game.result_reason(), "Every RIGHT character was defeated.")
        self.assertEqual(self.game.result_rounds(), "Rounds played: 1")
        self.game.handle_key(pygame.K_r, 0)                    # RIGHT moves first now
        end_match_now(self)
        self.assertEqual(self.game.result_title(), "RIGHT TEAM WINS!")
        self.assertEqual(self.game.result_reason(), "Every LEFT character was defeated.")
        self.assertEqual(self.game.result_rounds(), "Rounds played: 1")

    def test_the_round_limit_is_a_draw_even_when_one_team_is_ahead(self):
        self.start([Knight], [Knight])
        self.game.battle.teams["right"].characters[0].take_damage(100)
        defend_until_the_end(self)
        self.assertEqual(self.game.result_title(), "DRAW!")
        self.assertEqual(self.game.result_reason(), f"Round limit: {ROUND_LIMIT} rounds and no team was eliminated.")
        self.assertEqual(self.game.result_rounds(), f"Rounds played: {ROUND_LIMIT}")
        self.assertIn("Round limit reached: no team was eliminated.", self.game.log)
        self.assertIn("It's a draw!", self.game.log)

    def test_a_timeout_draw_with_right_moving_first(self):
        self.start([Knight, Archer], [Knight, Archer])
        self.game.handle_key(pygame.K_r, 0)                    # RIGHT first: the limit still holds
        defend_until_the_end(self)
        self.assertEqual(self.game.battle.round_number, ROUND_LIMIT)
        self.assertEqual(self.game.result_title(), "DRAW!")
        self.assertEqual(self.game.result_rounds(), f"Rounds played: {ROUND_LIMIT}")

    def test_every_result_line_fits_the_result_panel(self):
        texts = ["Every RIGHT character was defeated.", "Both teams were defeated at the same time.",
                 f"Round limit: {ROUND_LIMIT} rounds and no team was eliminated."]
        for text in texts:
            self.assertLess(self.game.font.size(text)[0], 640, text)
        self.start([Knight], [Knight])
        defend_until_the_end(self)
        self.game.draw()                                       # the result overlay draws without errors


class PlayerVsAISelectionTest(MainTestCase):
    """M3.1: the selection screen in Player vs AI mode (the default)."""

    def test_the_game_opens_in_player_vs_ai_mode_at_normal_difficulty(self):
        self.assertTrue(self.game.selection.vs_ai)
        self.assertEqual(self.game.selection.difficulty, "normal")
        self.assertTrue(self.game.mode_buttons["ai"].chosen)
        self.assertTrue(self.game.difficulty_buttons["normal"].chosen)

    def test_the_computer_team_cannot_be_picked_by_hand(self):
        self.click(self.game.card_rects[("right", Archer)])
        self.assertEqual(self.game.selection.picks["right"], [])
        self.assertIn("computer", self.game.message)

    def test_start_needs_only_the_left_team_and_the_computer_builds_the_right_team(self):
        for size in (1, 2, 3):
            with self.subTest(size=size):
                self.game = main.Game(self.screen)
                self.click(self.game.size_buttons[size - 1].rect)
                left = [Archer, Engineer, Knight][:size]
                for role in left[:-1]:
                    self.click(self.game.card_rects[("left", role)])
                self.assertFalse(self.game.start_button.enabled)
                self.click(self.game.card_rects[("left", left[-1])])
                self.assertTrue(self.game.start_button.enabled)
                self.click(self.game.start_button.rect)
                self.assertEqual((self.game.state, self.game.placing), ("cover", "left"))
                self.click(self.game.confirm_button.rect)      # no RIGHT cover screen: the AI places it
                self.assertEqual(self.game.state, "battle")
                teams = self.game.battle.teams
                self.assertEqual([type(c) for c in teams["left"].characters], left)
                right_roles = [type(c) for c in teams["right"].characters]
                self.assertEqual(len(right_roles), size)
                self.assertEqual(len(set(right_roles)), size)          # a legal team
                self.assertEqual((self.game.ai.side, self.game.ai.difficulty), ("right", "normal"))

    def test_the_difficulty_buttons_choose_the_computer_level(self):
        self.click(self.game.difficulty_buttons["hard"].rect)
        self.assertEqual(self.game.selection.difficulty, "hard")
        self.assertTrue(self.game.difficulty_buttons["hard"].chosen)
        self.assertFalse(self.game.difficulty_buttons["normal"].chosen)
        self.start_vs_ai([Knight])
        self.assertEqual(self.game.ai.difficulty, "hard")

    def test_two_players_mode_has_no_computer(self):
        self.click(self.game.mode_buttons["pvp"].rect)
        self.assertFalse(self.game.selection.vs_ai)
        self.assertFalse(self.game.difficulty_buttons["easy"].enabled)
        self.start([Knight], [Archer])
        self.assertIsNone(self.game.ai)


class PlayerVsAIBattleTest(MainTestCase):
    """M3.1: the computer plays the RIGHT team by itself, through the same Battle methods."""

    def setUp(self):
        super().setUp()
        self.start_vs_ai([Knight])                               # 1 v 1, Normal

    def run_frames(self, count):
        for _ in range(count):
            self.game.update()

    def test_the_computer_plays_its_turn_after_a_short_pause(self):
        self.click(self.game.action_buttons["defend"].rect)       # the human ends LEFT's turn
        self.assertEqual(self.game.battle.active_side, "right")
        self.run_frames(main.AI_DELAY_FRAMES - 2)
        self.assertEqual(self.game.battle.active_side, "right")   # still thinking: nothing done yet
        self.assertIsNone(self.game.battle.projectile)
        self.run_frames(1)
        log = " ".join(self.game.log)
        self.assertIn("AI (Normal):", log)                        # the computer explains its choice
        self.assertRegex(log, r"RIGHT \w+ (attacks|defends|uses)")  # and its action is logged
        finish_shot(self.game)
        self.assertEqual(self.game.battle.active_side, "left")    # one action, then the human again
        self.assertEqual(self.game.battle.round_number, 2)

    def test_the_human_cannot_act_for_the_computer(self):
        self.click(self.game.action_buttons["defend"].rect)
        cannon = self.game.battle.cannons["right"]
        aim_before = (cannon.angle, cannon.power)
        for action in ("attack", "defend", "special"):
            self.assertFalse(self.game.action_buttons[action].enabled)
            self.click(self.game.action_buttons[action].rect)
        for key in (pygame.K_UP, pygame.K_RIGHT, pygame.K_SPACE, pygame.K_1):
            self.game.handle_key(key, 0)
        self.assertEqual((cannon.angle, cannon.power), aim_before)
        self.assertIsNone(self.game.battle.projectile)
        self.click(self.character_rect("right", 0))
        self.assertIn("computer", self.game.message)
        self.assertIn("computer", " ".join(self.game.action_hint_lines()))

    def test_a_whole_match_against_the_computer_ends_on_the_result_screen(self):
        for _ in range(20000):                                    # the human only defends
            if self.game.state == "result":
                break
            if self.game.battle.active_side == "left" and self.game.battle.can_fire():
                self.click(self.game.action_buttons["defend"].rect)
            else:
                self.game.update()
        self.assertEqual(self.game.state, "result")
        # The GUI's computer has no fixed seed, and since M3.4 only an elimination wins, so a
        # match against a human who only defends ends in a RIGHT win or, rarely, a timeout draw.
        self.assertIn(self.game.battle.winner, ("right", "draw"))
        self.click(self.game.rematch_button.rect)                 # rematch: same teams, same computer
        self.assertEqual(self.game.state, "battle")
        self.assertEqual(self.game.battle.round_number, 1)
        self.assertIsNotNone(self.game.ai)


if __name__ == "__main__":
    unittest.main()
