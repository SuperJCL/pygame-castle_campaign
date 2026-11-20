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
import unittest.mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
try:
    import pygame
    import drawing
    import main
    from ai import AIController, Plan
    from animation import FIRE, FIRE_FRAMES, RETURN_FRAMES, RETURN_TO_SLOT, RUN_FRAMES, RUN_TO_CANNON, firing_x
    from battle import CANNON_PIVOT, ROUND_LIMIT, SLOT_X, Battle
    from castle import DEFAULT_LAYOUT, GROUND_Y, layout_problem, slot_position
    from characters import Archer, Engineer, Knight
except ImportError:          # Pygame is not installed: the tests below are skipped
    pygame = None

SHIFT = pygame.KMOD_SHIFT if pygame else 0
# Both teams have the default cover in these matches (see tests/test_combat.py for how the
# aims were found; they work the same from either side).
COVER_WALL = (45, 76)        # comes down on the enemy cover: 4 blocks in the blast
FRONT_CHARACTER = (45, 83)   # over the cover onto the enemy in slot 0 (the blast also reaches slot 1)
HARMLESS = (80, 10)          # comes down beside the shooter's own cannon: no damage
LOW_AND_SOFT = (5, 10)       # also harmless, and quicker: it lands about 18 frames after launch,
                             # while the shooter is still walking back from the cannon


def load_sdl():
    """Pygame's own copy of the SDL library (Windows, macOS or Linux wheels), or None."""
    folder = os.path.dirname(pygame.__file__)
    for pattern in ("SDL2.dll", os.path.join(".dylibs", "libSDL2*"),
                    os.path.join("..", "pygame.libs", "libSDL2*")):
        for path in glob.glob(os.path.join(folder, pattern)):
            return ctypes.CDLL(path)
    return None


def finish_shot(game):
    """Run frames until the attack is over (M3.4-C): the character has run to the cannon and
    fired, the shot has landed and the character is back in its slot."""
    for _ in range(1000):
        if game.battle.projectile is None and not game.cannon_run.is_busy():
            return
        game.update()
    raise AssertionError("the attack never finished")


def run_to_cannon(game):
    """Run frames until the running character reaches the cannon and the shot is launched.
    Returns how many frames that took."""
    for frame in range(1, RUN_FRAMES + 2):
        game.update()
        if game.battle.projectile is not None:
            return frame
    raise AssertionError("no shot was launched")


def aim(game, angle, power):
    cannon = game.battle.cannons[game.battle.active_side]
    cannon.adjust_angle(angle - cannon.angle)
    cannon.adjust_power(power - cannon.power)


def pass_turn(game):
    """The team to move passes without hurting anyone: DEFEND if it may, otherwise a harmless
    shot (since M4.2-B a team can't Defend two turns in a row), waiting until it has landed."""
    if game.battle.why_not_allowed(game.selected_index(), "defend") is None:
        game.handle_click(game.action_buttons["defend"].rect.center)
        game.update()
    else:
        aim(game, *HARMLESS)
        game.handle_click(game.action_buttons["attack"].rect.center)
        game.update()
        finish_shot(game)


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

    def background_at(self, x, y):
        """What the empty battlefield shows at (x, y): sky, scenery or ground. (Until M4.2-A the
        sky was one flat colour, so these tests compared with SKY_COLOR.)"""
        return tuple(self.game.background.get_at((round(x), round(y))))[:3]


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
        run_to_cannon(self.game)                                       # M3.4-C: fired at the cannon
        self.assertIsNotNone(self.game.battle.projectile)
        finish_shot(self.game)
        self.assertEqual(self.game.battle.castles["right"].total_hp(), 600 - 200)  # Knight: 4 x 50
        self.assertEqual(self.game.battle.active_side, "right")

    def test_space_is_the_attack_shortcut(self):
        self.start([Knight], [Engineer])
        self.game.handle_key(pygame.K_SPACE, 0)
        self.assertEqual(self.game.cannon_run.shot.action, "attack")
        run_to_cannon(self.game)
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
        run_to_cannon(self.game)
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
        run_to_cannon(self.game)
        for _ in range(FIRE_FRAMES + RETURN_FRAMES):                  # the Knight is back; the shot flies on
            self.game.update()
        self.assertIsNotNone(self.game.battle.projectile)
        self.assertFalse(self.game.cannon_run.is_busy())
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
        run_to_cannon(self.game)
        self.game.handle_key(pygame.K_UP, 0)
        self.game.handle_key(pygame.K_RIGHT, 0)
        cannon = self.game.battle.cannons["left"]
        self.assertEqual((cannon.angle, cannon.power), (45, 50))

    def test_r_during_a_flight_cancels_the_shot(self):
        self.game.handle_key(pygame.K_SPACE, 0)
        run_to_cannon(self.game)
        for _ in range(FIRE_FRAMES + RETURN_FRAMES + 10):              # the Knight is back by now
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

    def drawn_above_head(self, side, index):
        """True if something is drawn 8 px above a character's head (otherwise only the
        background shows there)."""
        self.game.draw()
        left, top, width, _ = self.character_rect(side, index)
        x, y = left + width // 2, top - 8
        return tuple(self.screen.get_at((x, y)))[:3] != self.background_at(x, y)

    def test_rally_halves_the_next_enemy_hit_on_every_living_ally(self):
        self.start([Knight, Archer, Engineer], [Archer, Engineer, Knight])
        self.assertFalse(self.drawn_above_head("left", 1))
        self.act("special")                                    # the left Knight (chosen first): Rally
        self.assertEqual(self.game.battle.active_side, "right")
        for index in range(3):                                 # every ally shows the defend bubble
            self.assertTrue(self.drawn_above_head("left", index))
        self.act("attack", FRONT_CHARACTER)                    # right Archer hits slots 0 and 1
        left = self.game.battle.teams["left"].characters
        # Without Rally: 40-12 = 28 and 40-4 = 36. Rally halves each one; slot 2 is out of range.
        self.assertEqual([c.hp for c in left], [140 - 14, 90 - 18, 110])
        log = " ".join(self.game.log)
        self.assertIn("Rally: 3 allies are defending", log)
        self.assertIn("LEFT Archer takes 18 damage", log)
        for _ in range(main.EXPLOSION_FRAMES):                 # let the explosion fade
            self.game.update()
        self.assertFalse(self.drawn_above_head("left", 1))                 # Rally is over

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
        pass_turn(self.game)                                   # right; round 2 starts
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
            pass_turn(self.game)                               # left (DEFEND, or a harmless shot)
            self.assertEqual(archer.special_cooldown, 3 - (round_number - 1))   # no tick mid-round
            pass_turn(self.game)                               # right; the next round starts
        self.assertEqual((self.game.battle.round_number, archer.special_cooldown), (4, 0))
        self.assertTrue(self.game.action_buttons["special"].enabled)
        self.click(self.game.action_buttons["special"].rect)
        run_to_cannon(self.game)
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
    """Both teams pass every turn until the match ends (two-player mode): DEFEND, or a harmless
    shot on a turn right after the team's own Defend (M4.2-B)."""
    for _ in range(2 * ROUND_LIMIT + 2):
        if test.game.state == "result":
            return
        pass_turn(test.game)
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
    """The result screen shows the winner (or DRAW), the reason and the final round."""

    def test_an_elimination_shows_its_reason_and_the_rounds(self):
        self.start([Knight], [Archer])
        end_match_now(self)
        self.assertEqual(self.game.result_title(), "LEFT TEAM WINS!")
        self.assertEqual(self.game.result_reason(), "Every RIGHT character was defeated.")
        self.assertEqual(self.game.result_rounds(), f"Final round: 1 / {ROUND_LIMIT}")
        self.game.handle_key(pygame.K_r, 0)                    # RIGHT moves first now
        end_match_now(self)
        self.assertEqual(self.game.result_title(), "RIGHT TEAM WINS!")
        self.assertEqual(self.game.result_reason(), "Every LEFT character was defeated.")
        self.assertEqual(self.game.result_rounds(), f"Final round: 1 / {ROUND_LIMIT}")

    def test_the_round_limit_is_a_draw_even_when_one_team_is_ahead(self):
        self.start([Knight], [Knight])
        self.game.battle.teams["right"].characters[0].take_damage(100)
        defend_until_the_end(self)
        self.assertEqual(self.game.result_title(), "DRAW!")
        self.assertEqual(self.game.result_reason(), f"Round limit: {ROUND_LIMIT} rounds and no team was eliminated.")
        self.assertEqual(self.game.result_rounds(), f"Final round: {ROUND_LIMIT} / {ROUND_LIMIT}")
        self.assertIn("Round limit reached: no team was eliminated.", self.game.log)
        self.assertIn("It's a draw!", self.game.log)

    def test_a_timeout_draw_with_right_moving_first(self):
        self.start([Knight, Archer], [Knight, Archer])
        self.game.handle_key(pygame.K_r, 0)                    # RIGHT first: the limit still holds
        defend_until_the_end(self)
        self.assertEqual(self.game.battle.round_number, ROUND_LIMIT)
        self.assertEqual(self.game.result_title(), "DRAW!")
        self.assertEqual(self.game.result_rounds(), f"Final round: {ROUND_LIMIT} / {ROUND_LIMIT}")

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
        self.assertIn("AI (Normal):", " ".join(self.game.log))     # the computer explains its choice
        finish_shot(self.game)                                    # (an attack is fired at the cannon)
        self.assertRegex(" ".join(self.game.log), r"RIGHT \w+ (attacks|defends|uses)")  # its action is logged
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

    def test_the_computers_turn_never_gets_stuck_when_its_plan_is_refused(self):
        # M4.2-B.1: right after its own Defend, the computer's final safety net must not be a
        # Defend (the anti-stall rule refuses it); it attacks, and the turn moves on.
        battle = self.game.battle
        self.game.handle_key(pygame.K_r, 0)                       # RIGHT (the computer) moves first
        battle.perform_action(0, "defend")                        # RIGHT defends (by hand) ...
        self.game.update()
        self.click(self.game.action_buttons["defend"].rect)       # ... LEFT passes: RIGHT again
        self.assertIsNotNone(battle.why_not_allowed(0, "defend"))
        illegal = Plan(5, "attack", 45, 70, reason="a slot that doesn't exist")
        self.game.ai.attack_plan = lambda *args: illegal
        self.game.ai.defensive_plan = lambda *args: illegal
        for _ in range(main.AI_DELAY_FRAMES + 900):               # its pause, the run and the shot
            if battle.active_side == "left" or self.game.state == "result":
                break
            self.game.update()
        self.assertEqual(battle.active_side, "left")
        log = " ".join(self.game.log)
        self.assertIn("safety net", log)
        self.assertNotIn("Not allowed", log)

    def test_a_whole_match_against_the_computer_ends_on_the_result_screen(self):
        for _ in range(20000):                                    # the human only passes
            if self.game.state == "result":
                break
            if (self.game.battle.active_side == "left" and self.game.battle.can_fire()
                    and not self.game.cannon_run.is_busy()):
                pass_turn(self.game)
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


class CannonRunTest(MainTestCase):
    """M3.4-C: an attacking character runs to its team's cannon, the shot is fired once when it
    gets there, and it runs back. The Battle still owns positions, damage and turns."""

    def setUp(self):
        super().setUp()
        self.start([Knight, Archer], [Knight, Engineer])          # two players, default cover

    def record_events(self):
        """From now on, keep every Battle event the game shows (it still shows them)."""
        seen, show = [], self.game.show_event

        def record(event):
            seen.append(event)
            show(event)
        self.game.show_event = record
        return seen

    def pixel(self, x, y):
        self.game.draw()
        return tuple(self.screen.get_at((round(x), y)))[:3]

    def body_pixel(self, x):
        """The colour 20 px above the ground at x: a figure's body when one is drawn there."""
        return self.pixel(x, GROUND_Y - 20)

    def press_everything(self):
        """Every combat input a player could try: all three buttons, SPACE, aiming and 1-3."""
        for button in self.game.action_buttons.values():
            self.game.handle_click(button.rect.center)
        for key in (pygame.K_SPACE, pygame.K_UP, pygame.K_RIGHT, pygame.K_2):
            self.game.handle_key(key, 0)
        self.game.handle_click(pygame.Rect(self.character_rect(self.game.battle.active_side, 1)).center)

    def test_attack_starts_the_run_and_fires_only_when_the_cannon_is_reached(self):
        events = self.record_events()
        aim(self.game, *COVER_WALL)
        self.click(self.game.action_buttons["attack"].rect)                # the click, then 1 frame
        run = self.game.cannon_run
        self.assertEqual((run.state, run.shot.side, run.shot.actor_index, run.shot.action),
                         (RUN_TO_CANNON, "left", 0, "attack"))
        self.assertEqual((run.shot.angle, run.shot.power), COVER_WALL)    # the aim when ATTACK was clicked
        panel = " ".join(self.game.selected_info_lines() + self.game.action_hint_lines())
        self.assertNotIn("choose who acts", panel)                         # the panel doesn't invite input
        self.assertIn("LEFT Knight runs to the cannon", panel)
        for _ in range(RUN_FRAMES - 2):
            self.game.update()
            self.assertIsNone(self.game.battle.projectile)
        self.assertEqual([e for e in events if e["type"] in ("action", "fire")], [])   # the Battle waits
        self.game.update()                                                # frame RUN_FRAMES: at the cannon
        self.assertIsNotNone(self.game.battle.projectile)
        self.assertEqual(run.state, FIRE)
        self.assertEqual([e["type"] for e in events if e["type"] in ("action", "fire")], ["action", "fire"])
        finish_shot(self.game)
        self.assertEqual(sum(e["type"] == "fire" for e in events), 1)
        self.assertEqual(self.game.battle.castles["right"].total_hp(), 600 - 200)     # Knight: 4 x 50

    def test_clicks_and_keys_during_the_run_add_nothing(self):
        events = self.record_events()
        aim(self.game, *COVER_WALL)
        cannon = self.game.battle.cannons["left"]
        self.click(self.game.action_buttons["attack"].rect)
        self.game.handle_key(pygame.K_SPACE, 0)                           # the same frame as the click
        frames = 0
        while self.game.cannon_run.is_busy():                             # run, fire pose and return
            self.press_everything()
            self.assertFalse(any(button.enabled for button in self.game.action_buttons.values()))
            self.game.update()
            frames += 1
        self.assertGreaterEqual(frames, FIRE_FRAMES + RETURN_FRAMES)
        self.assertEqual((cannon.angle, cannon.power), COVER_WALL)
        self.assertEqual(self.game.selected["left"], 0)                   # still the Knight's turn
        finish_shot(self.game)
        self.assertEqual([(e["name"], e["action"]) for e in events if e["type"] == "action"],
                         [("Knight", "attack")])
        self.assertEqual(sum(e["type"] == "fire" for e in events), 1)
        self.assertEqual([e for e in events if e["type"] == "invalid"], [])
        self.assertFalse(self.game.battle.teams["left"].characters[0].is_defending)
        self.assertEqual(self.game.battle.active_side, "right")

    def test_the_shot_uses_the_chosen_characters_stats(self):
        self.click(self.character_rect("left", 1))                       # the Archer
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["attack"].rect)
        run = self.game.cannon_run
        self.assertTrue(run.moves("left", 1))
        self.assertEqual(run.slot_x, SLOT_X["left"][1])                  # it starts from its own slot (x 95)
        self.assertLess(abs(run.actor_x() - SLOT_X["left"][1]), 15)      # one frame into the run
        finish_shot(self.game)
        # The Archer: 40 - 12 = 28 to the RIGHT Knight (the LEFT Knight would have done 18).
        self.assertEqual(self.game.battle.teams["right"].characters[0].hp, 140 - 28)
        self.assertEqual(self.game.battle.teams["left"].characters[1].exp, 10)
        self.assertIn("LEFT Archer attacks.", self.game.log)

    def test_power_shot_takes_the_same_run_and_keeps_its_special_damage(self):
        archer = self.game.battle.teams["left"].characters[1]
        self.click(self.character_rect("left", 1))
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["special"].rect)
        run = self.game.cannon_run
        self.assertEqual((run.state, run.shot.action), (RUN_TO_CANNON, "special"))
        self.assertEqual(archer.special_cooldown, 0)                      # nothing is used before the shot
        self.assertEqual(run_to_cannon(self.game), RUN_FRAMES - 1)
        self.assertEqual(archer.special_cooldown, 3)
        finish_shot(self.game)
        self.assertEqual(self.game.battle.teams["right"].characters[0].hp, 140 - 60)   # 1.5 x 40, no DEF
        self.assertIn("LEFT Archer uses Power Shot!", self.game.log)

    def test_the_runner_is_drawn_once_where_it_runs_and_battle_positions_never_move(self):
        battle = self.game.battle
        teams = battle.teams.values()
        rects = [team.character_rect(i) for team in teams for i in range(len(team.characters))]
        centres = [team.slot_center(i) for team in teams for i in range(len(team.characters))]
        slot, cannon = SLOT_X["left"][0], firing_x("left")
        knight_colour = main.TEAM_COLORS["left"]
        self.assertEqual(self.body_pixel(slot), knight_colour)
        aim(self.game, *COVER_WALL)
        self.click(self.game.action_buttons["attack"].rect)
        run, seen = self.game.cannon_run, {}
        while run.is_busy():
            self.assertEqual([team.character_rect(i) for team in teams for i in range(len(team.characters))], rects)
            self.assertEqual([team.slot_center(i) for team in teams for i in range(len(team.characters))], centres)
            moment = (run.state, run.frame)
            if moment in ((RUN_TO_CANNON, RUN_FRAMES // 2), (FIRE, 1), (RETURN_TO_SLOT, RETURN_FRAMES // 2)):
                seen[run.state] = run.actor_x()
                self.assertEqual(self.body_pixel(run.actor_x()), knight_colour, moment)   # drawn here ...
                self.assertEqual(self.body_pixel(slot), self.background_at(slot, GROUND_Y - 20), moment)  # not at home
            self.game.update()
        halfway = (slot + cannon) / 2
        self.assertEqual(seen, {RUN_TO_CANNON: halfway, FIRE: cannon, RETURN_TO_SLOT: halfway})
        self.assertEqual(self.body_pixel(slot), knight_colour)            # back in its slot
        self.assertEqual(self.body_pixel(cannon), self.background_at(cannon, GROUND_Y - 20))

    def test_the_flight_is_the_same_as_a_shot_fired_straight_from_the_battle(self):
        aim(self.game, *COVER_WALL)
        self.click(self.game.action_buttons["attack"].rect)
        run_to_cannon(self.game)              # the launch frame also moved the shot its first step
        shot, path = self.game.battle.projectile, []
        while self.game.battle.projectile is not None:
            path.append((shot.x, shot.y))
            self.game.update()
        twin = Battle(roster={side: [type(c) for c in team.characters]
                              for side, team in self.game.battle.teams.items()},
                      layouts=self.game.battle.layouts)
        aim_twin = twin.cannons["left"]
        aim_twin.adjust_angle(COVER_WALL[0] - aim_twin.angle)
        aim_twin.adjust_power(COVER_WALL[1] - aim_twin.power)
        twin.perform_action(0, "attack")
        twin_path = []
        while twin.projectile is not None:
            twin.update()
            if twin.projectile is not None:
                twin_path.append((twin.projectile.x, twin.projectile.y))
        explosion = next(e for e in twin.take_events() if e["type"] == "explosion")
        self.assertGreater(len(path), 60)
        self.assertEqual(path, twin_path)                                 # every step, exactly
        self.assertEqual(self.game.explosions[0][:2], [explosion["x"], explosion["y"]])
        self.assertEqual([b.hp for b in self.game.battle.castles["right"].blocks],
                         [b.hp for b in twin.castles["right"].blocks])

    def test_the_turn_passes_only_when_the_shot_has_landed(self):
        aim(self.game, *COVER_WALL)
        self.click(self.game.action_buttons["attack"].rect)
        while self.game.battle.projectile is None:                        # the run
            self.assertEqual(self.game.battle.active_side, "left")
            self.game.update()
        while self.game.battle.projectile is not None:                    # the flight
            self.assertEqual(self.game.battle.active_side, "left")
            self.game.update()
        self.assertEqual(self.game.battle.active_side, "right")

    def test_the_next_team_waits_until_the_runner_is_back_in_its_slot(self):
        aim(self.game, *LOW_AND_SOFT)
        self.click(self.game.action_buttons["attack"].rect)
        run_to_cannon(self.game)
        while self.game.battle.projectile is not None:
            self.game.update()
        run = self.game.cannon_run
        self.assertEqual(self.game.battle.active_side, "right")           # the Battle passed the turn ...
        self.assertTrue(run.is_busy())                                     # ... the LEFT Knight walks back
        cannon = self.game.battle.cannons["right"]
        aim_before = (cannon.angle, cannon.power)
        while run.is_busy():
            self.press_everything()
            self.game.update()
        self.assertEqual((cannon.angle, cannon.power), aim_before)
        self.assertIsNone(self.game.battle.projectile)
        self.assertEqual(self.game.selected["right"], 0)
        self.assertFalse(any(c.is_defending for c in self.game.battle.teams["right"].characters))
        self.assertEqual(self.game.battle.active_side, "right")
        self.game.update()
        self.assertTrue(self.game.action_buttons["attack"].enabled)       # now RIGHT may act
        self.game.handle_key(pygame.K_SPACE, 0)
        self.assertEqual(self.game.cannon_run.shot.side, "right")

    def test_two_players_each_run_to_their_own_cannon(self):
        events = self.record_events()
        for side in ("left", "right"):
            aim(self.game, *HARMLESS)
            self.click(self.game.action_buttons["attack"].rect)
            run = self.game.cannon_run
            self.assertEqual((run.shot.side, run.slot_x), (side, SLOT_X[side][0]))
            run_to_cannon(self.game)
            self.assertEqual((run.actor_x(), self.game.battle.projectile.side), (firing_x(side), side))
            finish_shot(self.game)
        self.assertEqual([e["side"] for e in events if e["type"] == "fire"], ["left", "right"])
        self.assertEqual((self.game.battle.active_side, self.game.battle.round_number), ("left", 2))

    def test_after_a_rematch_right_moves_first_and_runs_to_its_own_cannon(self):
        self.game.handle_key(pygame.K_r, 0)
        self.assertEqual(self.game.battle.active_side, "right")
        aim(self.game, *HARMLESS)
        self.click(self.game.action_buttons["attack"].rect)
        run = self.game.cannon_run
        self.assertEqual(run.shot.side, "right")
        self.assertTrue(firing_x("right") < run.actor_x() < SLOT_X["right"][0])   # running left, to x 964
        self.assertEqual(run.facing(), -1)
        run_to_cannon(self.game)
        self.assertEqual(self.game.battle.projectile.side, "right")
        self.assertEqual(run.actor_x(), CANNON_PIVOT["right"][0] + 24)
        finish_shot(self.game)
        self.assertEqual((self.game.battle.active_side, self.game.battle.round_number), ("left", 1))

    def test_r_during_the_run_cancels_it_and_nothing_is_fired_later(self):
        events = self.record_events()
        self.click(self.game.action_buttons["attack"].rect)
        for _ in range(5):
            self.game.update()
        self.game.handle_key(pygame.K_r, 0)
        battle = self.game.battle
        self.assertFalse(self.game.cannon_run.is_busy())
        self.assertEqual((self.game.state, battle.round_number, battle.active_side), ("battle", 1, "right"))
        for _ in range(3 * RUN_FRAMES):
            self.game.update()
        self.assertIsNone(battle.projectile)
        self.assertEqual([e for e in events if e["type"] in ("action", "fire")], [])
        self.assertTrue(self.game.action_buttons["attack"].enabled)       # RIGHT can play the new match

    def test_r_after_the_shot_left_the_cannon_also_restarts_cleanly(self):
        for frames_after_launch in (2, FIRE_FRAMES + 5):                  # firing pose, then walking back
            with self.subTest(frames=frames_after_launch):
                self.click(self.game.action_buttons["attack"].rect)
                run_to_cannon(self.game)
                for _ in range(frames_after_launch):
                    self.game.update()
                self.assertTrue(self.game.cannon_run.is_busy())
                self.game.handle_key(pygame.K_r, 0)
                self.assertFalse(self.game.cannon_run.is_busy())
                self.assertIsNone(self.game.battle.projectile)
                self.assertEqual(self.game.battle.round_number, 1)
                self.game.handle_key(pygame.K_r, 0)                       # LEFT first again for the next pass

    def test_defend_rally_and_repair_happen_at_once_without_a_run(self):
        battle = self.game.battle
        self.click(self.game.action_buttons["defend"].rect)              # LEFT Knight: Defend
        self.assertFalse(self.game.cannon_run.is_busy())
        self.assertEqual(battle.active_side, "right")
        battle.castles["right"].blocks[0].take_damage(30)
        self.click(self.character_rect("right", 1))                       # RIGHT Engineer: Repair
        self.click(self.game.action_buttons["special"].rect)
        self.assertFalse(self.game.cannon_run.is_busy())
        self.assertEqual(battle.castles["right"].total_hp(), 600)
        self.assertEqual(battle.active_side, "left")
        self.click(self.game.action_buttons["special"].rect)              # LEFT Knight: Rally
        self.assertFalse(self.game.cannon_run.is_busy())
        self.assertTrue(all(c.is_defending for c in battle.teams["left"].characters))
        self.assertEqual(battle.active_side, "right")

    def reach_the_last_turn(self):
        """Both teams pass until it is RIGHT's turn in round 30, the match's last turn."""
        battle = self.game.battle
        while not (battle.round_number == ROUND_LIMIT and battle.active_side == "right"):
            pass_turn(self.game)

    def end_while_walking_back(self):
        """RIGHT's last turn is a quick harmless shot: the round limit ends the match while the
        RIGHT Knight is still walking back from the cannon."""
        self.reach_the_last_turn()
        aim(self.game, *LOW_AND_SOFT)
        self.click(self.game.action_buttons["attack"].rect)
        run_to_cannon(self.game)
        while self.game.battle.projectile is not None:
            self.game.update()
        self.assertEqual((self.game.state, self.game.battle.winner), ("result", "draw"))
        self.assertTrue(self.game.cannon_run.is_busy())

    def test_a_match_that_ends_while_the_runner_walks_back_lets_it_finish(self):
        self.end_while_walking_back()
        frames = 0
        while self.game.cannon_run.is_busy():
            self.game.update()
            frames += 1
        self.assertLessEqual(frames, FIRE_FRAMES + RETURN_FRAMES)
        self.assertEqual(self.body_pixel(SLOT_X["right"][0]), main.TEAM_COLORS["right"])
        self.click(self.game.rematch_button.rect)
        self.assertEqual(self.game.state, "battle")
        self.assertFalse(self.game.cannon_run.is_busy())

    def test_rematch_and_quitting_stop_a_run(self):
        self.end_while_walking_back()
        self.click(self.game.rematch_button.rect)                         # Rematch on the result screen
        self.assertFalse(self.game.cannon_run.is_busy())
        self.assertEqual(self.game.battle.active_side, "right")           # it alternates as before
        self.click(self.game.action_buttons["attack"].rect)
        self.assertTrue(self.game.cannon_run.is_busy())
        self.game.handle_key(pygame.K_ESCAPE, 0)                          # closing the game mid-run
        self.assertFalse(self.game.running)
        self.assertFalse(self.game.cannon_run.is_busy())
        self.assertIsNone(self.game.battle.projectile)

    def test_change_teams_stops_a_run(self):
        self.end_while_walking_back()
        self.click(self.game.change_teams_button.rect)
        self.assertEqual(self.game.state, "select")
        self.assertFalse(self.game.cannon_run.is_busy())
        self.click(self.game.start_button.rect)                           # the next match starts idle
        self.click(self.game.confirm_button.rect)
        self.click(self.game.confirm_button.rect)
        self.assertEqual(self.game.state, "battle")
        self.assertFalse(self.game.cannon_run.is_busy())

    def test_a_runner_defeated_meanwhile_leaves_no_figure_behind(self):
        # Not possible in play (no friendly fire, and the enemy waits), so forced from outside.
        events = self.record_events()
        self.click(self.game.action_buttons["attack"].rect)
        for _ in range(RUN_FRAMES // 2):
            self.game.update()
        runner_x = self.game.cannon_run.actor_x()
        self.game.battle.teams["left"].characters[0].take_damage(500)
        self.game.update()
        self.assertFalse(self.game.cannon_run.is_busy())
        self.assertNotEqual(self.body_pixel(runner_x), main.TEAM_COLORS["left"])
        self.assertEqual(self.pixel(SLOT_X["left"][0], GROUND_Y - 4), main.DEFEATED_COLOR)
        self.assertEqual([e for e in events if e["type"] in ("action", "fire")], [])

    def test_the_muzzle_flash_starts_on_the_frame_the_shot_is_launched(self):
        aim(self.game, *COVER_WALL)
        point = main.muzzle_point(self.game.battle.cannons["left"])
        self.click(self.game.action_buttons["attack"].rect)
        while self.game.battle.projectile is None:
            self.assertNotEqual(self.pixel(*point), main.FLASH_COLOR)
            self.game.update()
        self.assertEqual(self.pixel(*point), main.FLASH_COLOR)            # the launch frame
        while self.game.cannon_run.state == FIRE:
            self.game.update()
        self.assertNotEqual(self.pixel(*point), main.FLASH_COLOR)         # gone after the firing pose


class ComputerCannonRunTest(MainTestCase):
    """M3.4-C: the computer's attacks take the same run: it decides first (AIController.choose)
    and the shot is carried out (AIController.carry_out) when its character reaches the cannon."""

    def setUp(self):
        super().setUp()
        self.game = main.Game(self.screen, ai_seed=4)
        self.click(self.game.difficulty_buttons["hard"].rect)    # Hard never defends when unhurt
        self.start_vs_ai([Knight])

    def wait_for_the_computer(self):
        for _ in range(main.AI_DELAY_FRAMES + 1):
            if self.game.cannon_run.is_busy() or self.game.battle.active_side == "left":
                return
            self.game.update()

    def test_the_computer_runs_to_its_cannon_before_its_shot_is_fired(self):
        seen, show = [], self.game.show_event
        self.game.show_event = lambda event: (seen.append(event), show(event))
        self.click(self.game.action_buttons["defend"].rect)              # the human passes
        self.wait_for_the_computer()
        run, battle = self.game.cannon_run, self.game.battle
        self.assertEqual((run.state, run.shot.side), (RUN_TO_CANNON, "right"))
        plan = run.shot.plan
        self.assertIsNotNone(plan)
        self.assertIn(f"AI (Hard): {plan.reason}.", self.game.log)         # it explains its choice at once
        self.assertEqual((battle.cannons["right"].angle, battle.cannons["right"].power), (plan.angle, plan.power))
        self.assertIsNone(battle.projectile)                                # ... but has not fired
        self.assertEqual([e for e in seen if e["type"] in ("action", "fire") and e["side"] == "right"], [])
        self.assertEqual(run_to_cannon(self.game), RUN_FRAMES)
        self.assertEqual(battle.projectile.side, "right")
        self.assertEqual(run.actor_x(), firing_x("right"))
        finish_shot(self.game)
        self.assertEqual([e["side"] for e in seen if e["type"] == "fire"], ["right"])
        self.assertEqual((battle.active_side, battle.round_number), ("left", 2))
        self.assertFalse(self.game.ai.defended_last_turn)

    def test_the_computer_waits_until_the_human_runner_is_back(self):
        aim(self.game, *LOW_AND_SOFT)
        self.click(self.game.action_buttons["attack"].rect)
        run_to_cannon(self.game)
        while self.game.battle.projectile is not None:
            self.game.update()
        self.assertEqual(self.game.battle.active_side, "right")
        self.assertTrue(self.game.cannon_run.is_busy())                    # the LEFT Knight walks back
        log_length = len(self.game.log)
        while self.game.cannon_run.is_busy():
            self.assertEqual(self.game.ai_wait, 0)                          # the computer has not started
            self.game.update()
        self.assertFalse(any("AI (Hard)" in line for line in self.game.log[log_length:]))
        self.wait_for_the_computer()
        self.assertEqual(self.game.cannon_run.shot.side, "right")


class SoundEventsTest(MainTestCase):
    """M4.2-A: the game plays a sound for the right Battle events, once each, and never needs one."""

    def record_sounds(self):
        """From now on, keep the names of the sounds the game plays (instead of playing them)."""
        played = []
        self.game.sounds.play = played.append
        return played

    def test_an_attack_on_cover_plays_fire_explosion_and_cover_hit_once_each(self):
        self.start([Knight], [Engineer])
        played = self.record_sounds()
        aim(self.game, *COVER_WALL)
        self.click(self.game.action_buttons["attack"].rect)
        self.assertEqual(played, [])                              # nothing while running to the cannon
        run_to_cannon(self.game)
        self.assertEqual(played, ["fire"])                        # on the launch frame
        finish_shot(self.game)
        self.assertEqual(played, ["fire", "explosion", "cover_hit"])

    def test_destroying_cover_plays_the_destruction_sound_instead(self):
        self.start([Knight], [Engineer])
        for block in self.game.battle.castles["right"].blocks:
            block.take_damage(50)
        played = self.record_sounds()
        aim(self.game, *COVER_WALL)
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)
        self.assertEqual(played, ["fire", "explosion", "cover_destroyed"])

    def test_defend_specials_and_refused_actions_make_no_sound(self):
        self.start([Engineer], [Knight])
        played = self.record_sounds()
        self.click(self.game.action_buttons["special"].rect)      # refused: nothing to repair
        self.click(self.game.action_buttons["defend"].rect)       # LEFT defends
        self.click(self.game.action_buttons["special"].rect)      # RIGHT Knight: Rally
        self.assertEqual(played, [])

    def test_a_winning_shot_plays_its_sounds_then_one_victory_tune(self):
        self.start([Knight], [Archer])
        self.game.battle.teams["right"].characters[0].take_damage(64)
        played = self.record_sounds()
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)
        for _ in range(120):                                      # the result screen stays quiet
            self.game.update()
        self.assertEqual(played, ["fire", "explosion", "level_up", "victory"])

    def test_against_the_computer_its_win_is_a_defeat_and_a_timeout_a_draw(self):
        self.start_vs_ai([Knight])
        played = self.record_sounds()
        battle = self.game.battle
        self.click(self.game.action_buttons["defend"].rect)       # LEFT passes ...
        battle.teams["left"].characters[0].take_damage(500)       # ... and falls: the computer's turn ends it
        for _ in range(main.AI_DELAY_FRAMES + 800):              # its pause, run and shot (up to 600 steps)
            if self.game.state == "result":
                break
            self.game.update()
        self.assertEqual(battle.winner, "right")
        self.assertEqual(played[-1], "defeat")
        self.assertEqual(played.count("defeat"), 1)
        self.game.handle_key(pygame.K_r, 0)
        for _ in range(2 * ROUND_LIMIT * 200):                    # both sides only pass, to the limit
            if self.game.state == "result":
                break
            if battle.active_side == "left":
                pass_turn(self.game)
            elif battle.why_not_allowed(0, "defend") is None:     # the computer's side, by hand:
                battle.perform_action(0, "defend")                # Defend, or a harmless shot
                self.game.update()
            else:
                aim(self.game, *HARMLESS)
                battle.perform_action(0, "attack")
                finish_shot(self.game)
        self.assertEqual(battle.end_reason, "timeout")
        self.assertEqual(played[-1], "draw")

    def test_a_rematch_stops_every_sound_and_none_comes_back(self):
        self.start([Knight], [Engineer])
        played = self.record_sounds()
        stopped = []
        self.game.sounds.stop = lambda: stopped.append(True)
        aim(self.game, *COVER_WALL)
        self.click(self.game.action_buttons["attack"].rect)
        run_to_cannon(self.game)
        self.game.handle_key(pygame.K_r, 0)                       # the shot is cancelled mid-flight
        self.assertTrue(stopped)
        for _ in range(300):
            self.game.update()
        self.assertEqual(played, ["fire"])

    def test_m_turns_the_sound_off_and_on(self):
        self.start([Knight], [Engineer])
        self.game.handle_key(pygame.K_m, 0)
        self.assertTrue(self.game.sounds.muted)
        self.assertIn("Sound off", self.game.message)
        self.game.handle_key(pygame.K_m, 0)
        self.assertFalse(self.game.sounds.muted)
        self.assertIn("Sound on", self.game.message)
        self.game.state = "select"                                # it works on every screen
        self.game.handle_key(pygame.K_m, 0)
        self.assertTrue(self.game.sounds.muted)

    def test_the_whole_game_works_without_an_audio_device(self):
        pygame.mixer.quit()
        with unittest.mock.patch("pygame.mixer.init", side_effect=pygame.error("no audio device")), \
                unittest.mock.patch("pygame.mixer.get_init", return_value=None):
            self.game = main.Game(self.screen)
        self.assertFalse(self.game.sounds.available)
        self.start([Knight], [Archer])
        self.game.battle.teams["right"].characters[0].take_damage(64)
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)
        self.assertEqual(self.game.state, "result")
        self.game.handle_key(pygame.K_m, 0)
        self.game.handle_key(pygame.K_r, 0)
        self.game.draw()
        self.assertEqual(self.game.state, "battle")


def contrast(colour_a, colour_b):
    """The WCAG contrast ratio of two RGB colours (4.5 or more is easy to read for small text)."""
    def luminance(colour):
        channels = []
        for value in colour:
            value /= 255
            channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
    light, dark = sorted((luminance(colour_a), luminance(colour_b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


class InterfacePolishTest(MainTestCase):
    """M4.1: cosmetic changes only. What the screen says and shows; no rule is involved."""

    def pixel(self, x, y):
        self.game.draw()
        return tuple(self.screen.get_at((round(x), round(y))))[:3]

    def computer_moves_first(self):
        self.start_vs_ai([Knight, Archer])                     # Normal
        end_match_now(self)
        self.click(self.game.rematch_button.rect)               # RIGHT (the computer) moves first now
        self.assertTrue(self.game.is_ai_turn())

    # ----- status text --------------------------------------------------------------

    def test_when_the_computer_moves_first_nothing_asks_the_player_to_act(self):
        self.computer_moves_first()
        shown = " ".join([self.game.message, self.game.hud_turn_text()] + self.game.selected_info_lines()
                         + self.game.action_hint_lines())
        self.assertNotIn("Choose a character", shown)
        self.assertNotIn("choose who acts", shown)
        self.assertIn("The computer (RIGHT) moves first.", self.game.message)
        self.assertIn("thinking", self.game.hud_turn_text())
        self.assertIn("RIGHT TEAM'S TURN (computer)", self.game.hud_turn_text())
        self.assertEqual(self.game.log[:2], ["--- Round 1 ---", "RIGHT team moves first."])

    def test_while_the_computer_thinks_no_character_is_marked_as_chosen(self):
        self.computer_moves_first()
        self.assertIn("thinking", " ".join(self.game.selected_info_lines()))
        left, top, width, height = self.character_rect("right", self.game.selected["right"])
        ring = pygame.Rect(left, top, width, height).inflate(8, 8)
        self.assertNotEqual(self.pixel(ring.left + 1, ring.centery), main.ACTIVE_RING_COLOR)

    def test_the_hud_message_keeps_the_result_of_a_shot(self):
        self.start([Knight], [Archer])
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)
        self.assertEqual(self.game.message, "RIGHT Archer takes 26 damage.")     # not "Knight gains 10 EXP."
        self.assertIn("Knight gains 10 EXP.", self.game.log)                    # still in the log

    def test_the_turn_banner_says_what_is_happening(self):
        self.start([Knight], [Archer])
        self.assertEqual(self.game.hud_turn_text(), f"Round 1 / {ROUND_LIMIT}   LEFT TEAM'S TURN: aim and act")
        aim(self.game, *COVER_WALL)
        self.click(self.game.action_buttons["attack"].rect)
        self.assertTrue(self.game.hud_turn_text().endswith("running to the cannon"))
        run_to_cannon(self.game)
        self.assertTrue(self.game.hud_turn_text().endswith("shot in the air"))
        finish_shot(self.game)
        self.assertEqual(self.game.hud_turn_text(), f"Round 1 / {ROUND_LIMIT}   RIGHT TEAM'S TURN: aim and act")
        end_match_now(self)
        self.assertEqual(self.game.hud_turn_text(), f"Round 1 / {ROUND_LIMIT}   GAME OVER")

    def test_after_the_game_the_panel_does_not_invite_input_and_no_cannon_is_active(self):
        self.start([Knight], [Archer])
        end_match_now(self)
        lines = " ".join(self.game.selected_info_lines())
        self.assertNotIn("choose who acts", lines)
        self.assertIn("The game is over.", lines)
        for cannon in self.game.battle.cannons.values():           # no yellow ring around either cannon
            self.assertNotEqual(self.pixel(cannon.x + 13, cannon.y), main.ACTIVE_RING_COLOR)

    def test_the_aim_is_shown_in_the_panel_and_under_the_active_cannon(self):
        self.start([Knight], [Archer])
        for _ in range(5):
            self.game.handle_key(pygame.K_UP, 0)
        self.game.handle_key(pygame.K_RIGHT, SHIFT)
        self.assertEqual(self.game.aim_text(), "Angle 50°   Power 55")
        self.assertEqual(self.game.cannon_label(self.game.battle.cannons["left"]), "50° / 55")
        self.game.draw()

    def test_the_panel_hints_fit_under_the_buttons_for_every_role(self):
        self.start([Knight, Archer, Engineer], [Knight, Archer, Engineer])
        for index in range(3):
            for blocked in (False, True):
                with self.subTest(index=index, blocked=blocked):
                    character = self.game.battle.teams["left"].characters[index]
                    if blocked:
                        character.start_cooldown()
                    self.game.select_actor(index)
                    hints = []
                    for line in self.game.action_hint_lines():
                        hints.extend(main.wrap_text(line, self.game.tiny_font, 390))
                    self.assertLessEqual(main.PANEL_TOP + 84 + 18 * len(hints), main.WINDOW_HEIGHT, hints)

    # ----- feedback on the battlefield ------------------------------------------------

    def test_a_hit_shows_a_floating_damage_number_for_a_second(self):
        self.start([Knight], [Archer])
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["attack"].rect)
        run_to_cannon(self.game)
        while self.game.battle.projectile is not None:
            self.game.update()
        texts = [(text, x) for x, _, text, _, _ in self.game.floaters]
        self.assertEqual(texts, [("-26", SLOT_X["right"][0])])
        for _ in range(main.FLOAT_FRAMES):
            self.game.update()
        self.assertEqual(self.game.floaters, [])

    def test_shielded_and_defeated_characters_get_their_own_words(self):
        self.start([Knight], [Archer])
        event = {"type": "explosion", "side": "left", "kind": "block", "x": 1100, "y": 528, "target": None,
                 "blocks_hit": 1, "damage": 50, "guarded": False, "covered": ["Archer"], "characters_hit": []}
        self.game.show_event(event)
        self.assertEqual([text for _, _, text, _, _ in self.game.floaters], ["shielded"])
        event.update(covered=[], characters_hit=[{"name": "Archer", "damage": 26, "defeated": True}])
        self.game.show_event(event)
        self.assertEqual([text for _, _, text, _, _ in self.game.floaters], ["shielded", "-26", "DEFEATED"])
        self.game.handle_key(pygame.K_r, 0)                     # a rematch clears them
        self.assertEqual(self.game.floaters, [])

    def test_an_explosion_no_longer_hides_the_character_it_hits(self):
        self.start([Knight], [Archer])
        x, y = self.game.battle.teams["right"].slot_center(0)
        self.game.explosions = [[x, y, 0]]                      # a fresh explosion right on the Archer
        body = self.pixel(x, main.GROUND_Y - 20)
        self.assertNotEqual(body, (255, 220, 80))                # not covered by the solid yellow
        self.assertNotEqual(body, main.TEAM_COLORS["right"])     # but the explosion is still visible

    def test_a_power_shot_looks_different_and_every_shot_leaves_a_short_trail(self):
        self.start([Archer], [Knight])
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["special"].rect)
        run_to_cannon(self.game)
        self.assertEqual(self.game.shot_style, "power")
        for _ in range(main.TRAIL_LENGTH + 5):
            self.game.update()
        shot = self.game.battle.projectile
        self.assertEqual(len(self.game.trail), main.TRAIL_LENGTH)
        self.assertEqual(self.pixel(shot.x, shot.y), main.POWER_SHOT_COLOR)
        finish_shot(self.game)
        self.assertEqual(self.game.trail, [])
        aim(self.game, *HARMLESS)                               # RIGHT's Knight: a plain attack
        self.click(self.game.action_buttons["attack"].rect)
        run_to_cannon(self.game)
        self.assertEqual(self.game.shot_style, "attack")
        shot = self.game.battle.projectile
        self.assertEqual(self.pixel(shot.x, shot.y), main.SHOT_COLOR)

    def test_damaged_blocks_show_cracks_and_destroyed_blocks_leave_an_outline(self):
        self.assertEqual([drawing.block_cracks(hp, 100) for hp in (100, 80, 79, 40, 39, 1)], [0, 0, 1, 1, 2, 2])
        self.start([Knight], [Archer])
        blocks = self.game.battle.castles["right"].blocks
        standing = self.pixel(blocks[0].x + 1, blocks[0].y + 16)
        self.assertNotEqual(standing, self.background_at(blocks[0].x + 1, blocks[0].y + 16))   # a standing block
        blocks[0].take_damage(100)                                 # destroyed: no longer stops shots ...
        self.assertTrue(blocks[0].is_destroyed())
        self.assertEqual(self.pixel(blocks[0].x, blocks[0].y + 4), drawing.RUBBLE_COLOR)   # ... but its place shows
        self.assertEqual(self.pixel(blocks[0].x + 16, blocks[0].y + 16),
                         self.background_at(blocks[0].x + 16, blocks[0].y + 16))

    def test_hp_bars_turn_red_below_a_quarter(self):
        archer = Archer("A", "left")
        colours = []
        for damage in (0, 45, 22, 1):                              # 90, 45, 23 and 22 HP (a quarter: 22.5)
            archer.take_damage(damage)
            colours.append(drawing.hp_bar_color(archer))
        self.assertEqual(colours, [drawing.HP_GOOD, drawing.HP_HURT, drawing.HP_HURT, drawing.HP_LOW])

    def test_names_on_the_battlefield_are_easy_to_read(self):
        # Since M4.2-A every name sits on a light plate (the sky and scenery behind vary).
        self.start([Knight, Archer, Engineer], [Engineer, Knight, Archer])
        self.game.draw()
        for side, team in self.game.battle.teams.items():
            for index in range(3):
                plate = self.game.label_plate_rect(side, index)
                behind = tuple(self.screen.get_at((plate.left + 2, plate.centery)))[:3]
                self.assertGreaterEqual(contrast(main.LABEL_COLORS[side], behind), 4.5, (side, index, behind))

    # ----- buttons, selection and placement ---------------------------------------------

    def test_an_enabled_button_lights_up_under_the_mouse(self):
        button = main.Button(10, 10, 100, 40, "OK")
        inside = (25, 30)

        def colour(hover_at):
            with unittest.mock.patch("pygame.mouse.get_pos", return_value=hover_at):
                button.draw(self.screen, self.game.font)
            return tuple(self.screen.get_at(inside))[:3]
        self.assertNotEqual(colour((50, 30)), colour((500, 500)))
        button.enabled = False
        self.assertEqual(colour((50, 30)), colour((500, 500)))       # a disabled button doesn't react

    def test_the_computers_cards_are_clearly_not_clickable(self):
        rect = self.game.card_rects[("right", Knight)]
        band = (rect.left + 8, rect.bottom - 18)                    # a grey band: "THE COMPUTER PICKS"
        self.assertEqual(self.pixel(*band), main.BUTTON_OFF)        # Player vs AI (the default)
        self.click(self.game.mode_buttons["pvp"].rect)
        self.assertNotEqual(self.pixel(*band), main.BUTTON_OFF)

    def test_the_cover_screen_shows_the_budget_and_marks_slots_that_cannot_take_a_block(self):
        self.pick_teams([Knight], [Archer])
        self.click(self.game.start_button.rect)
        self.click_slot("left", 3)                                 # 5 blocks; slot 7 can't take one
        pips = self.game.budget_pip_rects()
        self.assertEqual(len(pips), 6)
        filled = [self.pixel(*pip.center) == main.block_color("left", 1, 1) for pip in pips]
        self.assertEqual(filled, [True] * 5 + [False])
        unsupported = main.slot_rect("left", 7)
        self.assertEqual(self.pixel(*unsupported.center), main.CLOSED_SLOT_COLOR)   # the "x"
        for pip in pips:                                           # the pips stay clear of the text
            self.assertFalse(pip.colliderect(pygame.Rect(0, 100, main.WINDOW_WIDTH, 120)))

    def test_win_and_draw_banners_look_different(self):
        self.start([Knight], [Knight])
        end_match_now(self)
        banner = main.result_banner_rect()
        win = self.pixel(banner.left + 4, banner.top + 4)
        self.assertEqual(win, main.TEAM_COLORS["left"])
        self.game.handle_key(pygame.K_r, 0)
        defend_until_the_end(self)
        self.assertEqual(self.pixel(banner.left + 4, banner.top + 4), main.DRAW_COLOR)
        self.assertIn("time limit", self.game.result_subtitle().lower())


class AtmosphereTest(MainTestCase):
    """M4.2-A: a battlefield with depth and teams told apart by shape. Drawing only."""

    def pixel(self, x, y):
        self.game.draw()
        return tuple(self.screen.get_at((round(x), round(y))))[:3]

    def test_the_background_has_depth_and_is_made_only_once(self):
        background = self.game.background
        self.start([Knight], [Archer])
        self.game.draw()
        self.game.handle_key(pygame.K_r, 0)
        self.game.draw()
        self.assertIs(self.game.background, background)              # built once, then only copied
        top, horizon = self.background_at(640, 90), self.background_at(640, 440)
        self.assertLess(sum(top), sum(horizon))                       # the sky lightens toward the horizon
        scenery = {self.background_at(x, y) for x in range(0, main.WINDOW_WIDTH, 40) for y in (470, 500, 535)}
        self.assertGreaterEqual(len(scenery), 3)                      # sky, far and near hills: not flat
        self.assertEqual(self.background_at(640, main.GROUND_Y + 10), main.GROUND_COLOR)   # the ground is where it was
        self.assertNotEqual(self.background_at(640, main.GROUND_Y - 1), main.GROUND_COLOR)

    def test_drawing_the_scenery_changes_nothing_in_the_battle(self):
        self.start([Knight, Archer, Engineer], [Engineer, Knight, Archer])
        battle = self.game.battle

        def state():
            return ([t.character_rect(i) for t in battle.teams.values() for i in range(3)],
                    [b.rect() for c in battle.castles.values() for b in c.blocks],
                    [(c.x, c.y, c.angle, c.power) for c in battle.cannons.values()])
        before = state()
        for _ in range(3):
            self.game.draw()
        self.assertEqual(state(), before)

    def test_the_teams_differ_by_emblem_shape_as_well_as_colour(self):
        self.start([Knight], [Knight])
        for side, tip_is_white in (("left", False), ("right", True)):
            left, top, width, _ = self.character_rect(side, 0)
            x, y = left + width // 2, top + main.EMBLEM_Y
            self.assertEqual(self.pixel(x, y), main.EMBLEM_COLOR, side)              # a white emblem ...
            tip = self.pixel(x, y - 4)                                               # ... a diamond has a tip
            self.assertEqual(tip == main.EMBLEM_COLOR, tip_is_white, side)
        for side, (x, y) in self.game.hud_emblem_centres().items():                   # also in the HUD
            self.assertEqual(self.pixel(x, y), main.EMBLEM_COLOR, side)

    def test_floating_words_on_one_character_never_overlap(self):
        self.start([Knight], [Archer])
        hit = {"type": "explosion", "side": "left", "kind": "character", "x": 1140, "y": 520, "target": "Archer",
               "blocks_hit": 0, "damage": 0, "guarded": False, "covered": [],
               "characters_hit": [{"name": "Archer", "damage": 26, "defeated": False}]}
        for _ in range(3):                                            # three quick hits on the same Archer
            self.game.show_event(dict(hit))
        rects = [self.game.floater_rect(floater) for floater in self.game.floaters]
        self.assertEqual(len(rects), 3)
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                self.assertFalse(a.colliderect(b), (a, b))

    def test_the_turn_banner_never_runs_into_the_team_lines(self):
        self.start_vs_ai([Knight, Archer, Engineer])
        battle = self.game.battle
        battle.round_number = ROUND_LIMIT
        battle.active_side = "right"
        self.game.cannon_run.start(main.PendingShot("right", 0, "attack", 45, 50), SLOT_X["right"][0])
        self.assertTrue(self.game.hud_turn_text().endswith("(computer): running to the cannon"))   # the longest
        banner = self.game.hud_banner_rect()
        for side_line in self.game.hud_side_rects().values():
            self.assertFalse(banner.colliderect(side_line), (banner, side_line))
        self.game.cannon_run.cancel()

    def test_the_cover_screen_text_stays_readable_on_the_sky(self):
        self.pick_teams([Knight], [Archer])
        self.click(self.game.start_button.rect)
        for side in ("left", "right"):
            self.game.draw()
            plate = self.game.cover_text_plate_rect()
            self.assertLessEqual(plate.top, 30)
            self.assertGreaterEqual(plate.bottom, self.game.cover_text_bottom())    # title, help and legend
            behind = tuple(self.screen.get_at((plate.left + 3, plate.top + 30)))[:3]
            self.assertGreaterEqual(contrast(self.game.cover_title_color(), behind), 4.5, side)
            self.assertGreaterEqual(contrast(main.TEXT_COLOR, behind), 4.5, side)
            self.click(self.game.confirm_button.rect)                              # RIGHT's screen next

    def test_the_panel_says_how_to_turn_the_sound_off(self):
        self.start([Knight], [Archer])
        self.assertIn("M: sound", self.game.log_header())
        self.game.handle_key(pygame.K_m, 0)
        self.assertIn("sound off", self.game.log_header().lower())


class GuardedStrikeUITest(MainTestCase):
    """M4.2-B: Guarded Strike and the anti-stall rule are visible: a mark on the defender, the
    panel, the log, floating words, and DEFEND greyed out with its reason."""

    def setUp(self):
        super().setUp()
        self.start([Knight, Archer], [Knight, Engineer])          # two players, default cover

    def mark_pixel(self, side, index):
        self.game.draw()
        return tuple(self.screen.get_at(self.game.guard_mark_rect(side, index).center))[:3]

    def right_passes(self):
        aim(self.game, *HARMLESS)
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)

    def test_the_defender_gets_a_hollow_mark_then_a_filled_one_on_its_next_turn(self):
        self.assertNotEqual(self.mark_pixel("left", 0), main.GUARD_STRIKE_COLOR)
        self.click(self.game.action_buttons["defend"].rect)       # LEFT Knight defends
        self.assertIn("LEFT Knight: Guarded Strike next turn (+25% ATK).", self.game.log)
        self.assertNotEqual(self.mark_pixel("left", 0), main.GUARD_STRIKE_COLOR)   # hollow: waiting
        rect = self.game.guard_mark_rect("left", 0)
        self.game.draw()
        self.assertEqual(tuple(self.screen.get_at((rect.centerx, rect.top)))[:3], main.GUARD_STRIKE_COLOR)
        self.right_passes()
        self.assertEqual(self.mark_pixel("left", 0), main.GUARD_STRIKE_COLOR)      # filled: ready
        status = " ".join(self.game.selected_info_lines())
        self.assertIn("Guarded Strike ready", status)
        self.assertIn("+25%", status)

    def test_using_it_shows_the_bonus_and_the_bigger_hit(self):
        self.click(self.game.action_buttons["defend"].rect)
        self.right_passes()
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["attack"].rect)
        run_to_cannon(self.game)
        self.assertIn("LEFT Knight uses Guarded Strike: ATK x1.25.", self.game.log)
        self.assertIn("+25%", [text for _, _, text, _, _ in self.game.floaters])
        finish_shot(self.game)
        self.assertEqual(self.game.battle.teams["right"].characters[0].hp, 140 - 25)   # not 18
        self.assertNotEqual(self.mark_pixel("left", 0), main.GUARD_STRIKE_COLOR)       # used up

    def test_an_unused_one_expires_where_the_player_can_see_it(self):
        self.click(self.game.action_buttons["defend"].rect)
        self.right_passes()
        self.click(self.character_rect("left", 1))                # the Archer acts instead
        aim(self.game, *HARMLESS)
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)
        self.assertIn("LEFT Knight's Guarded Strike expired unused.", self.game.log)
        self.assertIn("expired", [text for _, _, text, _, _ in self.game.floaters])
        self.assertNotEqual(self.mark_pixel("left", 0), main.GUARD_STRIKE_COLOR)

    def test_defend_is_greyed_out_with_its_reason_the_turn_after_a_defend(self):
        self.click(self.game.action_buttons["defend"].rect)
        self.right_passes()
        self.assertFalse(self.game.action_buttons["defend"].enabled)
        self.assertTrue(self.game.action_buttons["attack"].enabled)
        self.assertIn("DEFEND unavailable", " ".join(self.game.action_hint_lines()))
        for index in range(2):                                    # the hints still fit the panel
            self.game.select_actor(index)
            hints = []
            for line in self.game.action_hint_lines():
                hints.extend(main.wrap_text(line, self.game.tiny_font, 390))
            self.assertLessEqual(main.PANEL_TOP + 84 + 18 * len(hints), main.WINDOW_HEIGHT, hints)
        self.game.select_actor(0)
        self.click(self.game.action_buttons["defend"].rect)       # clicking it explains, does nothing
        self.assertIn("two turns in a row", self.game.message)
        self.assertEqual(self.game.battle.active_side, "left")
        self.game.handle_key(pygame.K_r, 0)                       # a new match forgets it
        self.click(self.game.action_buttons["defend"].rect)       # RIGHT moves first now
        self.assertEqual(self.game.battle.active_side, "left")


if __name__ == "__main__":
    unittest.main()
