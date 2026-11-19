"""Unit tests for characters.py (Character, Knight, Archer, Engineer, calculate_damage).

Run from the project root:  python -m unittest discover tests
Expected values are worked out by hand from docs/M0_design.md §3 and the M2.1 brief.
"""
import os
import subprocess
import sys
import unittest

from characters import Archer, Character, Engineer, Knight, calculate_damage

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class InitialAttributesTest(unittest.TestCase):
    def test_each_role_starts_with_its_own_stats(self):
        # role, HP, ATK, DEF, special name, cooldown length
        table = [
            (Knight, 140, 30, 12, "Rally", 4),
            (Archer, 90, 40, 4, "Power Shot", 3),
            (Engineer, 110, 34, 8, "Repair", 4),
        ]
        for role, hp, atk, defense, special, cooldown in table:
            with self.subTest(role=role.__name__):
                character = role("Test", "left")
                self.assertEqual((character.hp, character.max_hp), (hp, hp))
                self.assertEqual((character.atk, character.defense), (atk, defense))
                self.assertEqual(character.SPECIAL_NAME, special)
                self.assertEqual(character.SPECIAL_COOLDOWN, cooldown)

    def test_every_character_starts_fresh(self):
        for role in (Knight, Archer, Engineer):
            with self.subTest(role=role.__name__):
                character = role("Ada", "right")
                self.assertEqual((character.name, character.side), ("Ada", "right"))
                self.assertEqual((character.level, character.exp), (1, 0))
                self.assertFalse(character.is_defending)
                self.assertEqual(character.special_cooldown, 0)
                self.assertTrue(character.special_ready())
                self.assertTrue(character.is_alive())

    def test_important_state_is_read_only(self):
        knight = Knight("K", "left")
        for attribute in ("hp", "max_hp", "atk", "defense", "level", "exp",
                          "is_defending", "special_cooldown"):
            with self.subTest(attribute=attribute):
                with self.assertRaises(AttributeError):
                    setattr(knight, attribute, 999)


class InheritanceTest(unittest.TestCase):
    def test_all_roles_are_characters(self):
        for role in (Knight, Archer, Engineer):
            with self.subTest(role=role.__name__):
                self.assertTrue(issubclass(role, Character))
                self.assertIsInstance(role("X", "left"), Character)

    def test_shared_rules_are_inherited_not_copied(self):
        # The subclasses reuse the base class's methods instead of defining their own.
        for role in (Knight, Archer, Engineer):
            for method in ("take_damage", "take_hit", "gain_exp", "defend", "tick_cooldown"):
                with self.subTest(role=role.__name__, method=method):
                    self.assertIs(getattr(role, method), getattr(Character, method))


class DamageTest(unittest.TestCase):
    def test_hp_never_goes_below_zero(self):
        archer = Archer("A", "left")                  # 90 HP
        self.assertEqual(archer.take_damage(100), 90)  # only 90 HP could be lost
        self.assertEqual(archer.hp, 0)
        self.assertFalse(archer.is_alive())
        self.assertEqual(archer.take_damage(5), 0)     # already defeated: nothing more happens
        self.assertEqual(archer.hp, 0)

    def test_negative_damage_is_rejected(self):
        knight = Knight("K", "left")
        with self.assertRaises(ValueError):
            knight.take_damage(-10)
        self.assertEqual(knight.hp, 140)

    def test_defense_reduces_damage(self):
        # Archer ATK 40 - Knight DEF 12 = 28; Knight ATK 30 - Archer DEF 4 = 26.
        archer, knight = Archer("A", "left"), Knight("K", "right")
        self.assertEqual(knight.take_hit(archer), 28)
        self.assertEqual(knight.hp, 140 - 28)
        self.assertEqual(archer.take_hit(knight), 26)
        self.assertEqual(archer.hp, 90 - 26)

    def test_a_hit_always_does_at_least_1_damage(self):
        self.assertEqual(calculate_damage(5, 12, defending=False), 1)    # 5 - 12 is negative
        self.assertEqual(calculate_damage(12, 12, defending=False), 1)   # 12 - 12 is zero

    def test_defending_halves_the_damage(self):
        archer, knight = Archer("A", "left"), Knight("K", "right")
        knight.defend()
        self.assertTrue(knight.is_defending)
        self.assertEqual(knight.take_hit(archer), 14)                    # 28 halved
        self.assertEqual(knight.hp, 140 - 14)

    def test_halving_rounds_down_and_still_does_at_least_1(self):
        self.assertEqual(calculate_damage(33, 12, defending=True), 10)   # 21 / 2 = 10.5 -> 10
        self.assertEqual(calculate_damage(5, 12, defending=True), 1)     # 1 / 2 would be 0

    def test_defend_status_can_be_cleared(self):
        archer, knight = Archer("A", "left"), Knight("K", "right")
        knight.defend()
        knight.clear_defend()
        self.assertFalse(knight.is_defending)
        self.assertEqual(knight.take_hit(archer), 28)                    # full damage again


class CooldownTest(unittest.TestCase):
    def test_archer_special_is_ready_again_after_3_round_starts(self):
        # Used in round 2 -> ticks at the starts of rounds 3, 4, 5 -> ready in round 5 (2 + 3).
        archer = Archer("A", "left")
        archer.start_cooldown()
        self.assertEqual(archer.special_cooldown, 3)
        self.assertFalse(archer.special_ready())
        archer.tick_cooldown()                         # round 3
        archer.tick_cooldown()                         # round 4
        self.assertFalse(archer.special_ready())
        archer.tick_cooldown()                         # round 5
        self.assertTrue(archer.special_ready())

    def test_knight_and_engineer_wait_4_round_starts(self):
        for role in (Knight, Engineer):
            with self.subTest(role=role.__name__):
                character = role("X", "left")
                character.start_cooldown()
                for _ in range(3):
                    character.tick_cooldown()
                self.assertFalse(character.special_ready())
                character.tick_cooldown()
                self.assertTrue(character.special_ready())

    def test_cooldown_never_goes_below_zero(self):
        knight = Knight("K", "left")
        knight.tick_cooldown()
        self.assertEqual(knight.special_cooldown, 0)


class ExperienceTest(unittest.TestCase):
    def test_level_2_needs_30_exp(self):
        knight = Knight("K", "left")
        self.assertEqual(knight.gain_exp(29), 0)
        self.assertEqual((knight.level, knight.exp), (1, 29))
        self.assertEqual(knight.gain_exp(1), 1)
        self.assertEqual((knight.level, knight.exp), (2, 0))

    def test_level_up_improves_stats(self):
        # Knight 140/30/12 -> +10 max HP, +10 HP, +3 ATK, +1 DEF.
        knight = Knight("K", "left")
        knight.take_damage(40)                         # 100 / 140 HP
        knight.gain_exp(30)
        self.assertEqual((knight.hp, knight.max_hp), (110, 150))
        self.assertEqual((knight.atk, knight.defense), (33, 13))

    def test_level_3_needs_60_more_exp(self):
        knight = Knight("K", "left")
        knight.gain_exp(30)                            # level 2
        self.assertEqual(knight.gain_exp(59), 0)
        self.assertEqual(knight.level, 2)
        self.assertEqual(knight.gain_exp(1), 1)
        self.assertEqual((knight.level, knight.exp), (3, 0))

    def test_one_award_can_give_several_levels(self):
        # 99 EXP at level 1: 30 for level 2, then 60 for level 3, 9 left over.
        archer = Archer("A", "left")                   # 90 / 40 / 4
        self.assertEqual(archer.gain_exp(99), 2)
        self.assertEqual((archer.level, archer.exp), (3, 9))
        self.assertEqual((archer.max_hp, archer.atk, archer.defense), (110, 46, 6))

    def test_level_5_is_the_maximum(self):
        # 30 + 60 + 90 + 120 = 300 EXP takes level 1 to level 5.
        knight = Knight("K", "left")
        self.assertEqual(knight.gain_exp(1000), 4)     # stops at level 5
        self.assertEqual((knight.level, knight.exp), (5, 0))
        self.assertEqual((knight.max_hp, knight.atk, knight.defense), (180, 42, 16))
        self.assertEqual(knight.gain_exp(50), 0)       # nothing left to earn
        self.assertEqual((knight.level, knight.exp), (5, 0))

    def test_defeated_character_gains_no_exp_and_is_not_revived(self):
        archer = Archer("A", "left")
        archer.take_damage(90)
        self.assertEqual(archer.gain_exp(100), 0)
        self.assertEqual((archer.level, archer.exp, archer.hp, archer.max_hp), (1, 0, 0, 90))
        self.assertFalse(archer.is_alive())

    def test_negative_exp_is_rejected(self):
        with self.assertRaises(ValueError):
            Knight("K", "left").gain_exp(-5)

    def test_a_new_match_starts_from_level_1(self):
        # EXP lasts one match: new characters are created for every match, and
        # levelling up one character must not change the role's starting stats.
        veteran = Knight("K", "left")
        veteran.gain_exp(90)                           # level 3
        rookie = Knight("K", "left")
        self.assertEqual((rookie.level, rookie.exp), (1, 0))
        self.assertEqual((rookie.max_hp, rookie.atk, rookie.defense), (140, 30, 12))


class SpecialAbilityTest(unittest.TestCase):
    def test_each_role_has_its_own_special(self):
        # The same call works on any character; each class answers in its own way.
        party = [Knight("K", "left"), Archer("A", "left"), Engineer("E", "left")]
        messages = [character.use_special() for character in party]
        for message, name in zip(messages, ("Rally", "Power Shot", "Repair")):
            self.assertIn(name, message)
        self.assertEqual(len(set(messages)), 3)

    def test_every_role_overrides_use_special(self):
        for role in (Knight, Archer, Engineer):
            with self.subTest(role=role.__name__):
                self.assertIsNot(role.use_special, Character.use_special)

    def test_a_role_without_its_own_special_raises(self):
        class Recruit(Character):                      # forgets to define use_special
            BASE_HP, BASE_ATK, BASE_DEF = 50, 10, 2
        with self.assertRaises(NotImplementedError):
            Recruit("R", "left").use_special()


class PygameIndependenceTest(unittest.TestCase):
    def test_characters_module_does_not_import_pygame(self):
        result = subprocess.run(
            [sys.executable, "-c", "import sys, characters; print('pygame' in sys.modules)"],
            cwd=PROJECT_ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
