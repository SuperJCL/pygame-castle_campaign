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
    from characters import Archer, Engineer, Knight
except ImportError:          # Pygame is not installed: the tests below are skipped
    pygame = None

SHIFT = pygame.KMOD_SHIFT if pygame else 0
TOWER = (45, 64)             # hits the enemy tower (4 blocks); see tests/test_combat.py
FRONT_CHARACTER = (45, 73)   # hits the enemy in slot 0 only


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
        """Pick the teams on the selection screen (by clicking) and press START."""
        self.click(self.game.size_buttons[len(left) - 1].rect)
        for side, roles in (("left", left), ("right", right)):
            for role in roles:
                self.click(self.game.card_rects[(side, role)])
        self.click(self.game.start_button.rect)
        self.assertEqual(self.game.state, "battle")

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


class TeamSelectionTest(MainTestCase):
    def test_each_team_size_needs_that_many_characters(self):
        for size in (1, 2, 3):
            with self.subTest(size=size):
                selection = main.TeamSelection()
                selection.set_team_size(size)
                for role in (Knight, Archer, Engineer)[:size]:
                    selection.toggle("left", role)
                    self.assertFalse(selection.is_complete())
                for role in (Engineer, Archer, Knight)[:size]:
                    selection.toggle("right", role)
                self.assertTrue(selection.is_complete())
                self.assertEqual(len(selection.roster()["right"]), size)

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

    def test_classic_cannon_duel_is_still_available(self):
        self.click(self.game.duel_button.rect)
        self.assertEqual(self.game.state, "battle")
        self.assertIsNone(self.game.battle.teams)


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
        aim(self.game, *TOWER)
        self.click(self.game.action_buttons["attack"].rect)
        self.assertIsNotNone(self.game.battle.projectile)
        finish_shot(self.game)
        self.assertEqual(self.game.battle.castles["right"].total_hp(), 1500 - 200)  # Knight: 4 x 50
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
        self.assertEqual(castle.total_hp(), 1500 - 80 + 75)
        self.assertEqual(self.game.battle.active_side, "right")
        self.assertIn("regains 75 HP", " ".join(self.game.log))

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

    def test_destroying_the_castle_shows_the_result(self):
        self.start([Knight], [Archer])
        for block in self.game.battle.castles["right"].blocks:
            block.take_damage(58)
        aim(self.game, *TOWER)
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)
        self.assertEqual(self.game.state, "result")
        self.assertIn("castle", self.game.result_reason())

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
        self.assertEqual((self.game.battle.round_number, self.game.battle.active_side), (1, "left"))

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


class ClassicDuelTest(MainTestCase):
    """The M1 cannon duel, still reachable from the selection screen."""

    def setUp(self):
        super().setUp()
        self.click(self.game.duel_button.rect)

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
        self.game.handle_key(pygame.K_SPACE, 0)            # left fires
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
        self.assertEqual(self.game.battle.active_side, "left")
        self.assertTrue(self.game.battle.can_fire())

    def test_r_clears_explosion_effects(self):
        self.game.handle_key(pygame.K_SPACE, 0)
        finish_shot(self.game)                              # the default shot explodes on the ground
        self.assertEqual(len(self.game.explosions), 1)
        self.game.handle_key(pygame.K_r, 0)
        self.assertEqual(self.game.explosions, [])

    def test_r_after_a_victory_starts_a_fresh_match(self):
        battle = self.game.battle
        for block in battle.castles["right"].blocks:
            block.take_damage(58)                           # 58 %: one more hit wins
        aim(self.game, *TOWER)
        self.game.handle_key(pygame.K_SPACE, 0)
        finish_shot(self.game)
        self.assertEqual(battle.winner, "left")
        self.assertEqual(self.game.state, "result")
        self.game.handle_key(pygame.K_r, 0)
        self.assertIsNone(battle.winner)
        self.assertEqual(self.game.state, "battle")
        for side in ("left", "right"):
            self.assertEqual(battle.castles[side].total_hp(), 1500)
            self.assertEqual((battle.cannons[side].angle, battle.cannons[side].power), (45, 50))


if __name__ == "__main__":
    unittest.main()
