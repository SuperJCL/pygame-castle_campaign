"""Tests for sound.py: the sound effects made in code (M4.2-A) and the silent fallback.

They need Pygame (skipped if it isn't installed) and use SDL's "dummy" audio driver, so
nothing is heard. How the game triggers the sounds is tested in tests/test_main.py.
"""
import os
import unittest
import unittest.mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
try:
    import pygame
except ImportError:          # Pygame is not installed: the tests below are skipped
    pygame = None
if pygame is not None:
    import sound             # outside the try: a broken sound.py must fail, not be skipped


@unittest.skipIf(pygame is None, "Pygame is not installed")
class SynthesisTest(unittest.TestCase):
    def test_every_sound_is_short_audible_and_within_range(self):
        for name in sound.SOUND_NAMES:
            with self.subTest(name=name):
                samples = sound.synthesize(name, 22050)
                self.assertTrue(0.05 <= len(samples) / 22050 <= 1.0, len(samples))
                self.assertLessEqual(max(abs(s) for s in samples), 1.0)
                self.assertGreaterEqual(max(abs(s) for s in samples), 0.2)      # not silent
                self.assertLess(abs(samples[-1]), 0.05)                         # fades out: no click

    def test_the_sounds_differ_from_each_other(self):
        made = {name: sound.synthesize(name, 22050) for name in sound.SOUND_NAMES}
        names = list(made)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                self.assertNotEqual(made[a], made[b], (a, b))

    def test_the_same_sound_is_made_the_same_way_every_time(self):
        self.assertEqual(sound.synthesize("explosion", 22050), sound.synthesize("explosion", 22050))

    def test_samples_become_mixer_bytes_in_the_mixer_format(self):
        samples = [0.0, 1.0, -1.0]
        self.assertEqual(len(sound.to_bytes(samples, -16, 1)), 3 * 2)
        self.assertEqual(len(sound.to_bytes(samples, -16, 2)), 3 * 2 * 2)    # stereo: each sample twice
        self.assertEqual(len(sound.to_bytes(samples, 32, 1)), 3 * 4)
        with self.assertRaises(ValueError):
            sound.to_bytes(samples, 8, 1)                                      # not supported: no sound


@unittest.skipIf(pygame is None, "Pygame is not installed")
class SoundBoardTest(unittest.TestCase):
    def setUp(self):
        pygame.init()

    def tearDown(self):
        pygame.quit()

    def test_with_a_mixer_every_sound_is_ready(self):
        board = sound.SoundBoard()
        self.assertTrue(board.available)
        self.assertEqual(set(board.sounds), set(sound.SOUND_NAMES))

    def test_play_plays_the_named_sound_once_and_mute_silences_it(self):
        board = sound.SoundBoard()
        board.sounds["fire"] = effect = unittest.mock.Mock()   # stands in for the real Sound
        board.play("fire")
        self.assertEqual(effect.play.call_count, 1)
        board.toggle_mute()
        board.play("fire")
        self.assertEqual(effect.play.call_count, 1)
        board.toggle_mute()
        board.play("fire")
        self.assertEqual(effect.play.call_count, 2)

    def test_no_audio_device_means_a_silent_board_and_no_error(self):
        pygame.mixer.quit()
        with unittest.mock.patch("pygame.mixer.init", side_effect=pygame.error("no audio device")), \
                unittest.mock.patch("pygame.mixer.get_init", return_value=None):
            board = sound.SoundBoard()
        self.assertFalse(board.available)
        self.assertEqual(board.sounds, {})
        for name in sound.SOUND_NAMES:
            board.play(name)                     # does nothing, raises nothing
        board.stop()
        board.toggle_mute()

    def test_an_unsupported_mixer_format_also_falls_back_to_silence(self):
        with unittest.mock.patch("pygame.mixer.get_init", return_value=(22050, 8, 1)):
            board = sound.SoundBoard()
        self.assertFalse(board.available)


if __name__ == "__main__":
    unittest.main()
