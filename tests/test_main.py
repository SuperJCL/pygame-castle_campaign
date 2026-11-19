"""Tests for main.py: window setup, keyboard handling and restart.

These tests need Pygame (they are skipped if it isn't installed). They use SDL's
"dummy" video driver, so no window appears. Keys are passed to the same
Game.handle_key() method that the real keyboard events reach.
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
except ImportError:          # Pygame is not installed: the tests below are skipped
    pygame = None

SHIFT = pygame.KMOD_SHIFT if pygame else 0


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


@unittest.skipIf(pygame is None, "Pygame is not installed")
class MainTestCase(unittest.TestCase):
    def setUp(self):
        self.screen = main.open_window()
        self.game = main.Game(self.screen)

    def tearDown(self):
        pygame.quit()


class WindowSetupTest(MainTestCase):
    def test_text_input_is_off_so_an_input_method_cannot_capture_keys(self):
        # M1.1 regression: with text input on (Pygame's default), a Chinese input
        # method captured R, then the arrow keys and SPACE, so aiming and restart failed.
        sdl = load_sdl()
        if sdl is None:
            self.skipTest("could not find Pygame's SDL library")
        self.assertEqual(sdl.SDL_IsTextInputActive(), 0)


class BlockColorTest(MainTestCase):
    def test_damaged_blocks_are_drawn_darker(self):
        healthy = main.block_color("left", 100, 100)
        half = main.block_color("left", 50, 100)            # one hit at 50 damage
        nearly_gone = main.block_color("left", 1, 100)
        self.assertTrue(all(h > d for h, d in zip(healthy, half)), (healthy, half))
        self.assertTrue(all(d > n for d, n in zip(half, nearly_gone)), (half, nearly_gone))


class KeyboardTest(MainTestCase):
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


class RestartTest(MainTestCase):
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
        for key, mods in ((pygame.K_RIGHT, SHIFT), (pygame.K_RIGHT, SHIFT),
                          (pygame.K_RIGHT, 0), (pygame.K_RIGHT, 0),
                          (pygame.K_RIGHT, 0), (pygame.K_RIGHT, 0)):
            self.game.handle_key(key, mods)                 # power 50 -> 64 hits the tower
        self.game.handle_key(pygame.K_SPACE, 0)
        finish_shot(self.game)
        self.assertEqual(battle.winner, "left")

        self.game.handle_key(pygame.K_r, 0)

        self.assertIsNone(battle.winner)
        self.assertEqual(battle.active_side, "left")
        for side in ("left", "right"):
            self.assertEqual(battle.castles[side].total_hp(), 1500)
            self.assertEqual((battle.cannons[side].angle, battle.cannons[side].power), (45, 50))


if __name__ == "__main__":
    unittest.main()
