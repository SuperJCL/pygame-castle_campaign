"""Tests for the M6.2 playability and presentation changes, one class per item of
docs/M6.2_playability_brief.md:

  1 Reflex Aim: the mode on the selection and cover screens, the swing gauge and the lock
  2 Classic Aim: the short path preview (Battle.preview_path) and the V key
  3 action buttons: the real special's name, a note, and one line of help
  4 cover presets (Inner Wall / Outer Wall), the step and next-step texts, the hover preview
  5 the result of a shot: DIRECT HIT, COVER HIT, GROUND IMPACT, OUT OF FIELD, impact marks
  6 the studio intro and the role cards
  7 the battlefield: same positions, depth shade, ground line, block shapes, shadows
  8 the panel groups, the HUD lines and the result panel

Like tests/test_main.py these need Pygame (they are skipped without it), use SDL's "dummy"
drivers and send input to the same Game methods the main loop uses (handle_event for the
intro). The Battle tests of preview_path need no window.
"""
import math
import unittest
import unittest.mock

import test_main
from test_main import (COVER_WALL, FRONT_CHARACTER, HARMLESS, aim, end_match_now, finish_shot,
                       restart_with_r, run_to_cannon)
from battle import ACTIONS, CANNON_PIVOT, Battle              # the rule modules need no Pygame
from battle_feedback import impact_summary
from castle import DEFAULT_LAYOUT, GROUND_Y, layout_problem, slot_position
from characters import Archer, Engineer, Knight

pygame = test_main.pygame
if pygame is not None:
    import drawing
    import main
    from ai import AIController

OUT_OF_FIELD = (40, 88)       # from LEFT over everything and off the right edge (1v1, default cover)
# RIGHT on Outer Wall with every block down to 5 HP: the shot lands on the cover, destroys two
# blocks, and the Archer behind them is still shielded (a block shields even as it breaks).
BREAKS_COVER_SHIELDS_ARCHER = (45, 80)
DESIGN_EXAMPLE = (30, 88)     # brief, item 4: Inner Wall stops it, Outer Wall lets it reach the Knight


def frames(game, count):
    for _ in range(count):
        game.update()


def record_launches(cannon):
    """From now on, keep the (vx, vy) of every shot this cannon fires as it leaves the barrel."""
    fired, fire = [], cannon.fire

    def spy(*change):                  # M6.3: Cannon.fire may change the aim (volley shells)
        shot = fire(*change)
        fired.append((shot.vx, shot.vy))
        return shot
    cannon.fire = spy
    return fired


def launch_angle(velocity, side):
    vx, vy = velocity
    return round(math.degrees(math.atan2(-vy, vx if side == "left" else -vx)), 9)


def key(game, key_code, release=True):
    """A key press through the real event path, then (by default) its release."""
    game.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key_code, mod=0))
    if release:
        game.handle_event(pygame.event.Event(pygame.KEYUP, key=key_code, mod=0))


def battle_state(battle):
    """Everything a read-only call must leave alone."""
    return ([(c.angle, c.power) for c in battle.cannons.values()],
            [(ch.hp, ch.exp, ch.level, ch.special_cooldown, ch.is_defending)
             for team in battle.teams.values() for ch in team.characters],
            [b.hp for castle in battle.castles.values() for b in castle.blocks],
            dict(battle.layouts), battle.active_side, battle.round_number, battle.projectile,
            list(battle._events))


@unittest.skipIf(pygame is None, "Pygame is not installed")
class PlayabilityTestCase(test_main.MainTestCase):
    def start(self, left, right, aim_mode="classic", right_preset=None):
        """Two players with the chosen Aim mode; RIGHT may choose a cover preset."""
        self.pick_teams(left, right)
        self.click(self.game.aim_buttons[aim_mode].rect)
        self.click(self.game.start_button.rect)
        self.click(self.game.confirm_button.rect)
        if right_preset is not None:
            self.click(self.game.preset_buttons[right_preset].rect)
        self.click(self.game.confirm_button.rect)
        self.assertEqual((self.game.state, self.game.aim_mode), ("battle", aim_mode))

    def start_vs_ai(self, left, aim_mode="classic"):
        self.click(self.game.size_buttons[len(left) - 1].rect)
        for role in left:
            self.click(self.game.card_rects[("left", role)])
        self.click(self.game.aim_buttons[aim_mode].rect)
        self.click(self.game.start_button.rect)
        self.click(self.game.confirm_button.rect)
        self.assertEqual(self.game.state, "battle")

    def press_space(self):
        """A fresh press of the fire key of the team to move (SPACE against the computer; with two
        players F or Enter, since the M6.2 rework)."""
        fire = test_main.battle_key(self.game, "fire")
        self.game.handle_event(pygame.event.Event(pygame.KEYUP, key=fire, mod=0))
        self.game.handle_key(fire, 0)

    def hover(self, pos):
        return unittest.mock.patch("pygame.mouse.get_pos", return_value=pos)

    def colours_near(self, point):
        """The colours on screen within 1 px of `point` (a thin line may round either way)."""
        x, y = round(point[0]), round(point[1])
        return {tuple(self.screen.get_at((x + dx, y + dy)))[:3] for dx in (-1, 0, 1) for dy in (-1, 0, 1)}


# ----- 1. Reflex Aim: entry, swing and lock -------------------------------------------------

class ReflexVisibilityTest(PlayabilityTestCase):
    def test_the_selection_screen_always_explains_the_chosen_aim_style(self):
        self.assertEqual(self.game.aim_description(), "Up/Down set the angle. Press Space to fire.")
        self.click(self.game.aim_buttons["reflex"].rect)
        self.assertEqual(self.game.aim_description(), "The cannon swings. Press Space to lock and fire.")
        rect = self.game.aim_description_rect()
        self.assertTrue(pygame.Rect(0, 0, main.WINDOW_WIDTH, main.WINDOW_HEIGHT).contains(rect))
        others = ([b.rect for b in self.game.mode_buttons.values()] + [b.rect for b in self.game.size_buttons]
                  + [b.rect for b in self.game.difficulty_buttons.values()]
                  + [b.rect for b in self.game.aim_buttons.values()] + list(self.game.card_rects.values())
                  + [self.game.start_button.rect, self.game.team_title_rect("right")])
        self.assertEqual(rect.collidelist(others), -1, rect)
        self.game.draw()

    def test_the_cover_screen_names_the_chosen_aim_style(self):
        self.pick_teams([Knight], [Archer])
        self.click(self.game.aim_buttons["reflex"].rect)
        self.click(self.game.start_button.rect)
        self.assertEqual(self.game.cover_aim_text(), "Aim: Reflex")
        self.click(self.game.back_button.rect)
        self.click(self.game.aim_buttons["classic"].rect)
        self.click(self.game.start_button.rect)
        self.assertEqual(self.game.cover_aim_text(), "Aim: Classic")
        self.game.draw()

    def test_the_status_says_swinging_then_locked_at_the_angle_that_is_fired(self):
        self.start([Knight], [Archer], aim_mode="reflex")
        fired = record_launches(self.game.battle.cannons["left"])
        self.assertEqual(self.game.aim_status(), "REFLEX · SWINGING")
        frames(self.game, 37)
        shown = self.game.battle.cannons["left"].angle
        self.assertEqual(self.game.aim_values()[0], f"{shown}°")
        self.press_space()
        locked = f"REFLEX · LOCKED {shown}°"
        self.assertEqual(self.game.aim_status(), locked)
        while self.game.battle.projectile is None:
            self.assertEqual(self.game.aim_status(), locked)   # all the way to the cannon ...
            self.game.update()
        self.assertEqual(launch_angle(fired[0], "left"), shown)
        while self.game.battle.projectile is not None:
            self.assertEqual(self.game.swing_gauge(), ("left", shown, True))   # ... and while it flies
            self.game.update()
        finish_shot(self.game)
        self.assertEqual(self.game.battle.active_side, "right")
        self.assertEqual(self.game.aim_status(), "REFLEX · SWINGING")      # RIGHT is a person too
        self.assertEqual(self.game.swing_gauge()[0], "right")

    def test_space_attack_and_power_shot_lock_and_fire_the_angle_on_screen(self):
        for how in ("space", "attack", "power shot"):
            for wait in (12, 61, 97):
                with self.subTest(how=how, wait=wait):
                    self.game = main.Game(self.screen)
                    self.start([Archer], [Knight], aim_mode="reflex")
                    cannon = self.game.battle.cannons["left"]
                    fired = record_launches(cannon)
                    frames(self.game, wait)
                    self.game.draw()                             # what the player sees ...
                    shown = cannon.angle
                    self.assertEqual(self.game.swing_gauge(), ("left", shown, False))
                    if how == "space":
                        self.press_space()
                    else:
                        action = "attack" if how == "attack" else "special"
                        self.game.handle_click(self.game.action_buttons[action].rect.center)
                    self.assertEqual(self.game.aim_status(), f"REFLEX · LOCKED {shown}°")   # ... is locked
                    self.assertIn(f"Angle locked at {shown}°", self.game.message)
                    run_to_cannon(self.game)
                    self.assertEqual(len(fired), 1)
                    self.assertEqual(launch_angle(fired[0], "left"), shown)   # ... and fired
                    self.assertEqual(self.game.shot_style, "power" if how == "power shot" else "attack")

    def test_the_lock_stays_on_the_shooters_cannon_while_it_runs_back(self):
        # A soft shot lands while the LEFT shooter is still running back: the turn is RIGHT's,
        # but the lock mark stays on LEFT's cannon (PendingShot.side), never on RIGHT's.
        self.start([Knight], [Archer], aim_mode="reflex")
        test_main.aim(self.game, 45, 10)                       # only the power: the swing sets the angle
        frames(self.game, 3)
        shown = self.game.battle.cannons["left"].angle
        self.press_space()
        run_to_cannon(self.game)
        seen_waiting = False
        while self.game.cannon_run.is_busy():
            self.game.update()
            if self.game.battle.active_side == "right" and self.game.cannon_run.is_busy():
                seen_waiting = True
                self.assertEqual(self.game.swing_gauge(), ("left", shown, True))
                self.assertEqual(self.game.aim_status(), "REFLEX · WAITING")
                self.assertEqual(self.game.phase_text(), "waiting")
                self.assertEqual(self.game.swings["right"].frame, 0)
        self.assertTrue(seen_waiting, "the shot should land while the shooter runs back")
        self.assertIsNone(self.game.locked_shot)
        self.assertEqual(self.game.swing_gauge()[0], "right")

    def test_the_computers_turn_says_thinking_and_its_cannon_has_no_gauge(self):
        self.game = main.Game(self.screen, ai_seed=4)
        self.start_vs_ai([Knight], aim_mode="reflex")
        self.assertEqual(self.game.swing_gauge()[0], "left")
        self.click(self.game.action_buttons["defend"].rect)
        right = self.game.battle.cannons["right"]
        angle = right.angle
        for _ in range(main.AI_DELAY_FRAMES - 2):
            self.assertEqual(self.game.aim_status(), "THINKING")
            self.assertIsNone(self.game.swing_gauge())
            self.game.update()
            self.assertEqual(right.angle, angle)

    def test_classic_draws_no_gauge(self):
        self.start([Knight], [Archer])
        self.assertIsNone(self.game.swing_gauge())
        self.assertEqual(self.game.aim_status(), "PATH ON · V")

    def test_a_rematch_forgets_the_lock_keeps_the_mode_and_starts_at_20(self):
        self.start([Knight], [Archer], aim_mode="reflex")
        frames(self.game, 40)
        self.press_space()
        self.assertIsNotNone(self.game.locked_shot)
        restart_with_r(self.game)
        self.assertIsNone(self.game.locked_shot)
        self.assertEqual(self.game.aim_mode, "reflex")
        self.assertEqual(self.game.swing_gauge(), ("right", 20, False))   # RIGHT moves first now

    def test_the_gauge_is_drawn_with_ticks_and_a_pointer(self):
        self.start([Knight], [Archer], aim_mode="reflex")
        frames(self.game, 45)
        self.game.draw()
        pivot, angle = CANNON_PIVOT["left"], self.game.battle.cannons["left"].angle
        pointer = drawing.arc_point(pivot, 1, angle, main.SWING_MARK_RADIUS + 2)
        self.assertEqual(tuple(self.screen.get_at((round(pointer[0]), round(pointer[1]))))[:3], main.LIGHT_TEXT)
        for end in (20, 75):                                     # a light tick at each end
            tick = drawing.arc_point(pivot, 1, end, main.SWING_MARK_RADIUS + 5)
            self.assertIn(main.LIGHT_TEXT, self.colours_near(tick), end)
        self.press_space()
        self.game.draw()
        self.assertEqual(tuple(self.screen.get_at((round(pointer[0]), round(pointer[1]))))[:3], main.BRASS)


# ----- 2. Classic Aim: the short path preview -----------------------------------------------

STEPS, EVERY = 24, 4          # main.PATH_STEPS and main.PATH_EVERY (PathPreviewTest checks them)


class PreviewPathRulesTest(unittest.TestCase):
    """Battle.preview_path against real shots. Only the rule modules: no Pygame needed."""
    AIMS = ((45, 50), (20, 100), (80, 100), (5, 10), (80, 10), (5, 100), (60, 75))

    def real_points(self, angle, power, side):
        """Fire for real (Battle.perform_action) and note where the shot is after steps 4, 8, ...
        24, as long as it is still flying."""
        battle = Battle(roster={"left": [Knight], "right": [Archer]}, first_side=side)
        cannon = battle.cannons[side]
        cannon.adjust_angle(angle - cannon.angle)
        cannon.adjust_power(power - cannon.power)
        battle.perform_action(0, "attack")
        points = []
        for step in range(1, STEPS + 1):
            battle.update()
            if battle.projectile is None:
                break
            if step % EVERY == 0:
                points.append((battle.projectile.x, battle.projectile.y))
        return points

    def preview(self, angle, power, side):
        battle = Battle(roster={"left": [Knight], "right": [Archer]}, first_side=side)
        cannon = battle.cannons[side]
        cannon.adjust_angle(angle - cannon.angle)
        cannon.adjust_power(power - cannon.power)
        return battle.preview_path(side, STEPS, EVERY)

    def test_the_dots_are_where_a_real_shot_goes(self):
        for side in ("left", "right"):
            for angle, power in self.AIMS:
                with self.subTest(side=side, angle=angle, power=power):
                    self.assertEqual(self.preview(angle, power, side), self.real_points(angle, power, side))

    def test_at_most_six_dots_and_none_past_the_first_contact(self):
        self.assertEqual(len(self.preview(45, 50, "left")), 6)
        low = self.preview(5, 10, "left")                       # it hits the ground almost at once
        self.assertLess(len(low), 6)
        self.assertTrue(all(y < GROUND_Y for _, y in low))
        for angle, power in self.AIMS:
            self.assertLessEqual(len(self.preview(angle, power, "left")), 6)

    def test_left_and_right_are_mirror_images(self):
        for angle, power in self.AIMS:
            left, right = self.preview(angle, power, "left"), self.preview(angle, power, "right")
            self.assertEqual(len(left), len(right))
            for (lx, ly), (rx, ry) in zip(left, right):
                self.assertAlmostEqual(lx + rx, 1280, places=6)     # the field is 1280 px wide
                self.assertAlmostEqual(ly, ry, places=6)

    def test_a_near_target_cuts_the_preview(self):
        battle = Battle(roster={"left": [Knight], "right": [Archer]}, layouts={"left": DEFAULT_LAYOUT, "right": ()})
        archer = battle.teams["right"].characters[0]
        battle.teams["right"].slot_center = lambda index: (420, GROUND_Y - 22)   # pretend it stands close
        battle.teams["right"].character_rect = lambda index: (406, GROUND_Y - 44, 28, 44)
        self.assertTrue(archer.is_alive())
        cannon = battle.cannons["left"]
        cannon.adjust_angle(10 - cannon.angle)
        cannon.adjust_power(100 - cannon.power)
        points = battle.preview_path("left", STEPS, EVERY)
        self.assertLess(len(points), 6)
        self.assertTrue(all(x < 406 for x, _ in points))

    def test_the_preview_changes_nothing(self):
        battle = Battle(roster={"left": [Knight, Archer], "right": [Engineer]})
        battle.teams["left"].characters[1].start_cooldown()
        battle.castles["right"].blocks[0].take_damage(30)
        before = battle_state(battle)
        for side in ("left", "right"):
            battle.preview_path(side, STEPS, EVERY)
        self.assertEqual(battle_state(battle), before)
        self.assertEqual(battle.take_events(), [])


class PathPreviewTest(PlayabilityTestCase):
    def test_the_game_uses_24_steps_and_a_dot_every_4(self):
        self.assertEqual((main.PATH_STEPS, main.PATH_EVERY), (STEPS, EVERY))

    def test_classic_shows_the_dots_and_v_hides_them(self):
        self.start([Knight], [Archer])
        points = self.game.path_points()
        self.assertEqual(len(points), 6)
        self.game.handle_key(test_main.battle_key(self.game, "up"), 0)
        self.assertNotEqual(self.game.path_points(), points)    # redrawn for the new aim
        self.game.handle_key(pygame.K_v, 0)
        self.assertEqual(self.game.path_points(), [])
        self.assertEqual(self.game.aim_status(), "PATH OFF · V")
        self.game.handle_key(pygame.K_v, 0)
        self.assertEqual(len(self.game.path_points()), 6)
        self.game.draw()

    def test_the_dots_hide_while_firing_on_the_computers_turn_in_reflex_and_after_the_game(self):
        self.start([Knight], [Archer])
        self.click(self.game.action_buttons["attack"].rect)
        self.assertEqual(self.game.path_points(), [])           # the run, then the flight
        finish_shot(self.game)
        self.assertEqual(len(self.game.path_points()), 6)        # RIGHT's turn (a person)
        end_match_now(self)
        self.assertEqual(self.game.path_points(), [])
        self.game = main.Game(self.screen, ai_seed=2)
        self.start_vs_ai([Knight])
        self.click(self.game.action_buttons["defend"].rect)
        self.assertTrue(self.game.is_ai_turn())
        self.assertEqual(self.game.path_points(), [])
        self.game = main.Game(self.screen)
        self.start([Knight], [Archer], aim_mode="reflex")
        self.assertEqual(self.game.path_points(), [])

    def test_aim_arrow_length_tracks_power_and_mirrors_to_the_right(self):
        for mode in ("classic", "reflex"):
            with self.subTest(mode=mode):
                self.game = main.Game(self.screen)
                self.start([Knight], [Archer], aim_mode=mode)
                self.game.show_path = False  # a white trajectory dot can sit on the gold arrow
                for side, facing in (("left", 1), ("right", -1)):
                    cannon = self.game.battle.cannons[side]
                    cannon.adjust_angle(45 - cannon.angle)
                    pivot = CANNON_PIVOT[side]
                    near = drawing.arc_point(pivot, facing, 45, 34)
                    middle = drawing.arc_point(pivot, facing, 45, 48)  # inside the Reflex dial
                    far = drawing.arc_point(pivot, facing, 45, 83)
                    for power, reaches_middle, reaches_far in ((10, False, False),
                                                               (55, True, False),
                                                               (100, True, True)):
                        cannon.adjust_power(power - cannon.power)
                        self.game.draw()
                        self.assertIn(main.AIM_COLOR, self.colours_near(near))
                        self.assertEqual(main.AIM_COLOR in self.colours_near(middle), reaches_middle)
                        self.assertEqual(main.AIM_COLOR in self.colours_near(far), reaches_far)
                    if side == "left":
                        self.click(self.game.action_buttons["defend"].rect)


# ----- 3. action buttons: the real special, its cost, why not ----------------------------------

class ActionButtonTextTest(PlayabilityTestCase):
    def test_the_special_button_names_the_chosen_characters_skill(self):
        self.start([Knight, Archer, Engineer], [Knight, Archer, Engineer])
        for index, label in enumerate(("RALLY", "POWER SHOT", "REPAIR")):
            self.click(self.character_rect("left", index))
            button = self.game.action_buttons["special"]
            self.assertEqual(button.label, label)
            self.assertLess(self.game.font.size(label)[0], button.rect.width - 8)
            self.game.draw()

    def test_the_help_line_shows_the_skill_unless_a_button_is_under_the_mouse(self):
        self.start([Knight, Archer, Engineer], [Knight, Archer, Engineer])
        with self.hover((5, 5)):
            self.assertIn(Knight.SPECIAL_DESCRIPTION, self.game.action_hint_lines()[0])
        with self.hover(self.game.action_buttons["attack"].rect.center):
            self.assertIn("current angle and power", self.game.action_hint_lines()[0])
            self.assertIn("ends your turn", self.game.action_hint_lines()[0].lower())
        with self.hover(self.game.action_buttons["defend"].rect.center):
            self.assertIn("Guarded Strike", self.game.action_hint_lines()[0])
        self.click(self.character_rect("left", 1))
        self.assertIn("current aim", self.game.action_help("special"))
        self.click(self.character_rect("left", 2))
        self.assertIn("standing", self.game.action_help("special"))

    def test_a_button_that_cannot_be_used_says_why_and_a_click_changes_nothing(self):
        self.start([Engineer, Knight], [Knight, Archer])
        special = self.game.action_buttons["special"]
        self.assertFalse(special.enabled)                         # nothing to repair yet
        self.assertEqual(special.note, "nothing to repair")
        self.assertIn("nothing to repair", self.game.action_help("special"))
        cooldowns = [c.special_cooldown for c in self.game.battle.teams["left"].characters]
        self.click(special.rect)
        self.assertIn("nothing to repair", self.game.message)
        self.assertEqual(self.game.battle.active_side, "left")
        self.assertEqual([c.special_cooldown for c in self.game.battle.teams["left"].characters], cooldowns)
        self.click(self.character_rect("left", 1))                # the Knight: Rally is ready
        self.assertTrue(special.enabled)
        self.click(special.rect)                                  # Rally: the turn passes
        self.assertEqual(self.game.battle.active_side, "right")
        self.click(self.game.action_buttons["defend"].rect)       # RIGHT defends; LEFT again
        self.click(self.character_rect("left", 1))
        self.assertFalse(special.enabled)
        self.assertEqual(special.note, f"ready in {Knight.SPECIAL_COOLDOWN - 1}")
        self.assertIn("recharging", self.game.action_help("special"))

    def test_defend_after_a_defend_and_a_locked_reflex_shot_have_notes(self):
        self.start([Knight], [Knight], aim_mode="reflex")
        self.click(self.game.action_buttons["defend"].rect)
        self.click(self.game.action_buttons["defend"].rect)       # RIGHT; LEFT may not defend again
        self.assertEqual(self.game.action_buttons["defend"].note, "not twice")
        self.assertIn("two turns in a row", self.game.action_help("defend"))
        self.assertEqual(self.game.action_buttons["attack"].note, "+25% ATK")   # its Guarded Strike
        frames(self.game, 20)
        angle = self.game.battle.cannons["left"].angle
        self.press_space()
        self.assertEqual(self.game.action_buttons["attack"].note, f"locked {angle}°")
        self.assertEqual(self.game.action_buttons["defend"].note, "wait")

    def test_the_help_fits_two_lines_for_every_role_state_and_mode(self):
        for aim_mode in ("classic", "reflex"):
            self.game = main.Game(self.screen)
            self.start([Knight, Archer, Engineer], [Knight, Archer, Engineer], aim_mode=aim_mode)
            for index in range(3):
                for blocked in (False, True):
                    character = self.game.battle.teams["left"].characters[index]
                    if blocked:
                        character.start_cooldown()
                    self.game.select_actor(index)
                    for action in ACTIONS:
                        with self.subTest(aim=aim_mode, index=index, blocked=blocked, action=action):
                            lines = main.wrap_text(self.game.action_help(action), self.game.tiny_font, main.HINT_WIDTH)
                            self.assertLessEqual(len(lines), 2, lines)

    def test_the_computers_turn_has_its_own_hint(self):
        self.game = main.Game(self.screen, ai_seed=1)
        self.start_vs_ai([Knight])
        self.click(self.game.action_buttons["defend"].rect)
        self.assertIn("computer", self.game.action_hint_lines()[0])
        self.assertEqual(self.game.action_buttons["special"].label, "SPECIAL")   # nobody chosen yet
        self.game.draw()


# ----- 4. cover presets ------------------------------------------------------------------------

class CoverPresetTest(PlayabilityTestCase):
    def go_to_cover(self, vs_ai=False):
        if vs_ai:
            self.click(self.game.card_rects[("left", Knight)])
        else:
            self.pick_teams([Knight], [Knight])
        self.click(self.game.start_button.rect)

    def test_both_presets_are_legal_six_blocks_and_mirrored(self):
        self.assertEqual(main.COVER_PRESETS, {"Inner Wall": (0, 1, 2, 3, 4, 5), "Outer Wall": (0, 1, 2, 3, 6, 7)})
        for layout in main.COVER_PRESETS.values():
            self.assertIsNone(layout_problem(layout))
            self.assertEqual(len(layout), 6)
            for slot in layout:
                (lx, ly), (rx, ry) = slot_position("left", slot), slot_position("right", slot)
                self.assertEqual((rx, ry), (main.WINDOW_WIDTH - lx - 32, ly))
        self.assertEqual(main.COVER_PRESETS["Inner Wall"], DEFAULT_LAYOUT)

    def test_a_preset_fills_only_the_team_placing_and_stays_editable(self):
        self.go_to_cover()
        self.click(self.game.preset_buttons["Outer Wall"].rect)
        self.assertEqual(self.game.setup.layouts, {"left": (0, 1, 2, 3, 6, 7), "right": DEFAULT_LAYOUT})
        self.assertIn("High wall near the cannon", self.game.message)
        self.assertTrue(self.game.preset_buttons["Outer Wall"].chosen)
        self.click_slot("left", 7)                                # still editable: remove a raised block
        self.assertEqual(self.game.setup.layouts["left"], (0, 1, 2, 3, 6))
        self.assertFalse(self.game.preset_buttons["Outer Wall"].chosen)
        for slot in (0, 1, 2, 3):
            self.click_slot("left", slot)
        self.assertEqual(self.game.setup.layouts["left"], ())     # down to zero blocks
        self.click(self.game.preset_buttons["Inner Wall"].rect)
        self.click(self.game.confirm_button.rect)                 # RIGHT's turn to place
        self.click(self.game.preset_buttons["Outer Wall"].rect)
        self.assertEqual(self.game.setup.layouts, {"left": DEFAULT_LAYOUT, "right": (0, 1, 2, 3, 6, 7)})
        self.click(self.game.back_button.rect)                    # Back keeps both
        self.assertEqual(self.game.setup.layouts, {"left": DEFAULT_LAYOUT, "right": (0, 1, 2, 3, 6, 7)})

    def test_the_step_and_the_next_button_say_where_you_are(self):
        self.go_to_cover()
        self.assertEqual(self.game.cover_step_text(), "1/2 · Left cover")
        self.assertEqual(self.game.confirm_button.label, "Next: Right Cover")
        self.click(self.game.confirm_button.rect)
        self.assertEqual(self.game.cover_step_text(), "2/2 · Right cover")
        self.assertEqual(self.game.confirm_button.label, "Start Battle")
        self.game.draw()
        self.game = main.Game(self.screen)
        self.go_to_cover(vs_ai=True)
        self.assertEqual(self.game.cover_step_text(), "1/1 · Left cover")
        self.assertEqual(self.game.confirm_button.label, "Start Battle")

    def test_hovering_a_supporting_block_marks_the_block_on_top_and_changes_nothing(self):
        self.go_to_cover()
        layout = self.game.setup.layouts["left"]
        self.assertEqual(self.game.removal_preview(main.slot_rect("left", 0).center), (0, 4))
        self.assertEqual(self.game.removal_preview(main.slot_rect("left", 2).center), (2,))   # nothing on top
        self.assertEqual(self.game.removal_preview((5, 5)), ())
        self.assertIsNotNone(self.game.cover_hover_text(main.slot_rect("left", 1).center))
        self.assertIsNone(self.game.cover_hover_text(main.slot_rect("left", 3).center))
        self.assertEqual(self.game.setup.layouts["left"], layout)
        with self.hover(main.slot_rect("left", 0).center):
            self.game.draw()
        top = main.slot_rect("left", 4)
        self.assertEqual(tuple(self.screen.get_at((top.left + 1, top.centery)))[:3], main.REMOVE_COLOR)
        self.click_slot("left", 0)                                # the click removes exactly those
        self.assertEqual(self.game.setup.layouts["left"], (1, 2, 3, 5))

    def test_the_other_teams_cover_stays_hidden(self):
        self.go_to_cover()
        self.click(self.game.preset_buttons["Outer Wall"].rect)
        self.click(self.game.confirm_button.rect)                 # RIGHT's screen
        self.game.draw()
        for slot in (0, 6):
            x, y = main.slot_rect("left", slot).center
            self.assertEqual(tuple(self.screen.get_at((x, y)))[:3], self.background_at(x, y))

    def test_the_computers_cover_and_rematches_are_unchanged(self):
        self.game = main.Game(self.screen, ai_seed=3)
        self.go_to_cover(vs_ai=True)
        self.click(self.game.preset_buttons["Outer Wall"].rect)
        self.click(self.game.confirm_button.rect)
        twin = AIController("right", "normal", seed=3)
        twin.pick_team(1)
        self.assertEqual(self.game.battle.layouts, {"left": (0, 1, 2, 3, 6, 7),
                                                    "right": tuple(sorted(twin.choose_layout()))})
        layouts = dict(self.game.battle.layouts)
        end_match_now(self)
        self.click(self.game.rematch_button.rect)
        self.assertEqual(self.game.battle.layouts, layouts)

    def test_the_design_example_inner_wall_stops_the_shot_outer_wall_lets_it_through(self):
        kinds = {}
        for preset in ("Inner Wall", "Outer Wall"):
            self.game = main.Game(self.screen)
            self.start([Knight], [Knight], right_preset=preset)
            battle = self.game.battle
            first = battle.path_contacts("left", *DESIGN_EXAMPLE)[0][0]
            aim(self.game, *DESIGN_EXAMPLE)
            self.click(self.game.action_buttons["attack"].rect)
            seen = []
            show = self.game.show_event
            self.game.show_event = lambda event: (seen.append(event), show(event))
            finish_shot(self.game)
            explosion = next(e for e in seen if e["type"] == "explosion")
            kinds[preset] = (first, explosion["kind"], [h["name"] for h in explosion["characters_hit"]])
        self.assertEqual(kinds["Inner Wall"], ("block", "block", []))
        self.assertEqual(kinds["Outer Wall"], ("character", "character", ["Knight"]))


# ----- 5. the result of a shot -------------------------------------------------------------------

class ImpactFeedbackTest(PlayabilityTestCase):
    def event(self, **changes):
        event = {"type": "explosion", "side": "left", "kind": "ground", "x": 1150, "y": 560, "target": None,
                 "blocks_hit": 0, "damage": 50, "guarded": False, "covered": [], "characters_hit": []}
        event.update(changes)
        return event

    def test_each_kind_of_landing_has_its_own_words(self):
        summary = impact_summary
        archer = {"name": "Archer", "damage": 26, "defeated": False}
        self.assertEqual(summary(self.event(kind="character", target="Archer", characters_hit=[archer])),
                         "DIRECT HIT · Archer -26 HP")
        self.assertEqual(summary(self.event(kind="block", blocks_hit=4, damage=200)), "COVER HIT · 4 blocks, -200 HP")
        self.assertEqual(summary(self.event(kind="block", blocks_hit=1, covered=["Archer"])),
                         "COVER HIT · Archer shielded")
        self.assertEqual(summary(self.event(kind="block", blocks_hit=2, covered=["Archer"]), destroyed=2),
                         "COVER HIT · 2 blocks destroyed, Archer shielded")
        self.assertEqual(summary(self.event(characters_hit=[dict(archer, damage=18)])),
                         "GROUND IMPACT · Archer -18 HP")
        self.assertEqual(summary(self.event()), "GROUND IMPACT · no damage")
        two = [archer, {"name": "Knight", "damage": 18, "defeated": False}]
        self.assertEqual(summary(self.event(characters_hit=two)), "GROUND IMPACT · 2 hit, -44 HP")
        self.assertEqual(summary(self.event(kind="character", characters_hit=[dict(archer, defeated=True)])),
                         "DIRECT HIT · Archer -26 HP, defeated")
        self.assertEqual(summary({"type": "miss", "side": "left", "reason": "offscreen", "x": 1280, "y": 300}),
                         "OUT OF FIELD · no damage")

    def shoot(self, angle, power, preset=None, prepare=None):
        """A 1v1 two-player match (LEFT Knight, RIGHT Archer): LEFT fires once with this aim."""
        self.game = main.Game(self.screen)
        self.start([Knight], [Archer], right_preset=preset)
        if prepare is not None:
            prepare(self.game.battle)
        seen = []
        show = self.game.show_event
        self.game.show_event = lambda event: (seen.append(event), show(event))
        aim(self.game, angle, power)
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)
        return next(e for e in seen if e["type"] in ("explosion", "miss"))

    def test_real_shots_report_what_the_engine_says(self):
        event = self.shoot(*FRONT_CHARACTER)
        self.assertEqual(self.game.message, "DIRECT HIT · Archer -26 HP")
        self.assertEqual(self.game.last_result, self.game.message)
        self.assertEqual(self.game.battle.teams["right"].characters[0].hp, Archer.BASE_HP - 26)
        self.assertEqual(event["characters_hit"][0]["damage"], 26)
        event = self.shoot(*COVER_WALL)
        self.assertEqual(self.game.message, "COVER HIT · 4 blocks, -200 HP")   # 4 blocks x 50 (Knight)
        self.assertEqual((event["blocks_hit"], event["damage"]), (4, 200))
        self.shoot(*HARMLESS)
        self.assertEqual(self.game.message, "GROUND IMPACT · no damage")
        self.shoot(*OUT_OF_FIELD)
        self.assertEqual(self.game.message, "OUT OF FIELD · no damage")
        self.assertEqual(self.game.impacts, [])                   # out of the field: words only
        self.shoot(*BREAKS_COVER_SHIELDS_ARCHER, preset="Outer Wall",
                   prepare=lambda b: [block.take_damage(block.hp - 5) for block in b.castles["right"].blocks])
        self.assertEqual(self.game.message, "COVER HIT · 2 blocks destroyed, Archer shielded")
        self.assertEqual(self.game.battle.teams["right"].characters[0].hp, Archer.BASE_HP)

    def test_the_mark_is_drawn_where_the_engine_says_and_fades_with_the_numbers(self):
        event = self.shoot(*FRONT_CHARACTER)
        self.assertEqual([m[:3] for m in self.game.impacts], [[event["x"], event["y"], "character"]])
        self.game.draw()
        frames(self.game, main.FLOAT_FRAMES)
        self.assertEqual(self.game.impacts, [])

    def test_the_result_stays_on_top_until_the_next_action(self):
        self.shoot(*COVER_WALL)
        result = self.game.message
        self.assertEqual(self.game.battle.active_side, "right")   # EXP, the new turn: still the result
        self.click(self.character_rect("right", 0))               # choosing who acts keeps it too
        self.assertEqual(self.game.message, result)
        self.click(self.game.action_buttons["defend"].rect)       # the next action replaces it
        self.assertNotEqual(self.game.message, result)
        self.assertEqual(self.game.last_result, result)           # the panel still shows the last shot

    def test_a_rematch_and_new_teams_clear_the_old_result(self):
        self.shoot(*FRONT_CHARACTER)
        restart_with_r(self.game)
        self.assertEqual((self.game.impacts, self.game.last_result), ([], None))
        self.shoot(*FRONT_CHARACTER)
        end_match_now(self)
        self.click(self.game.change_teams_button.rect)
        self.click(self.game.start_button.rect)
        self.click(self.game.confirm_button.rect)
        self.click(self.game.confirm_button.rect)
        self.assertEqual((self.game.impacts, self.game.last_result), ([], None))

    def test_a_defeat_leads_to_the_result_screen_with_the_reason(self):
        self.start([Archer], [Archer])
        self.game.battle.teams["right"].characters[0].take_damage(Archer.BASE_HP - 5)
        aim(self.game, *FRONT_CHARACTER)
        self.click(self.game.action_buttons["attack"].rect)
        finish_shot(self.game)
        self.assertEqual(self.game.state, "result")
        self.assertIn("defeated", self.game.last_result)
        self.assertEqual(self.game.result_reason(), "Every RIGHT character was defeated.")
        self.game.draw()


# ----- 6. studio intro and role cards ---------------------------------------------------------

class IntroTest(PlayabilityTestCase):
    def setUp(self):
        super().setUp()
        self.game = main.Game(self.screen, intro=True)

    def test_the_intro_lasts_2_5_seconds_and_ends_by_itself(self):
        self.assertEqual(main.INTRO_FRAMES, round(2.5 * main.FPS))       # lengthened from 1.2 s on request
        self.assertEqual(main.INTRO_HOLD, round(1.5 * main.FPS))         # the seals stay 1.5 s at full colour
        self.assertEqual(main.STUDIO_NAME, "DOUBLE SIX STUDIO")
        self.assertTrue(self.game.intro_playing())
        frames(self.game, main.INTRO_FRAMES - 1)
        self.assertTrue(self.game.intro_playing())
        self.game.update()
        self.assertFalse(self.game.intro_playing())
        self.assertEqual(self.game.state, "select")

    def test_a_click_space_or_enter_only_skips_it(self):
        knight = self.game.card_rects[("left", Knight)].center
        for skip in ("click", "space", "enter"):
            with self.subTest(skip=skip):
                self.game = main.Game(self.screen, intro=True)
                self.game.selection.picks["left"] = [Knight]     # a full team: Enter would start
                frames(self.game, 10)
                if skip == "click":
                    self.game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=knight, button=1))
                else:
                    key(self.game, pygame.K_SPACE if skip == "space" else pygame.K_RETURN)
                self.assertFalse(self.game.intro_playing())
                self.assertEqual((self.game.state, self.game.selection.picks["left"]), ("select", [Knight]))
        self.game.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=knight, button=1))
        self.assertEqual(self.game.selection.picks["left"], [])   # after the intro, clicks work again

    def test_escape_still_quits(self):
        key(self.game, pygame.K_ESCAPE)
        self.assertFalse(self.game.running)

    def test_it_never_plays_again(self):
        key(self.game, pygame.K_SPACE)
        self.start([Knight], [Archer])
        restart_with_r(self.game)
        end_match_now(self)
        self.click(self.game.change_teams_button.rect)
        self.click(self.game.start_button.rect)
        self.click(self.game.back_button.rect)
        self.assertFalse(self.game.intro_playing())

    def test_the_intro_shows_the_two_seals_then_fades_into_the_selection_screen(self):
        frames(self.game, main.INTRO_FADE_IN + 5)
        self.game.draw()
        for center in main.SEAL_CENTERS:
            self.assertEqual(tuple(self.screen.get_at((center[0], center[1] - main.SEAL_SIZE // 2 + 6)))[:3],
                             main.BRASS)
        self.assertEqual(tuple(self.screen.get_at((20, 20)))[:3], main.INTRO_COLOR)
        frames(self.game, main.INTRO_FRAMES)
        self.game.draw()
        self.assertNotEqual(tuple(self.screen.get_at((20, 20)))[:3], main.INTRO_COLOR)

    def test_a_new_game_without_the_intro_starts_on_the_selection_screen(self):
        self.assertFalse(main.Game(self.screen).intro_playing())


class RoleCardTest(PlayabilityTestCase):
    def test_every_card_fits_its_text_above_the_state_band(self):
        for (side, role), rect in self.game.card_rects.items():
            with self.subTest(side=side, role=role.__name__):
                # M6.3: compact cards; the words end above the band at the bottom
                self.assertLessEqual(self.game.card_text_bottom(role, rect), self.game.card_band_rect(rect).top)
        self.game.draw()

    def test_chosen_open_and_computer_cards_say_different_things(self):
        self.click(self.game.card_rects[("left", Archer)])
        self.assertEqual(self.game.card_state_text("left", Archer), "Slot 1 · front")
        self.assertEqual(self.game.card_state_text("left", Knight), "Click to add")
        self.assertEqual(self.game.card_state_text("right", Knight), "THE COMPUTER PICKS")
        self.click(self.game.mode_buttons["pvp"].rect)
        self.assertEqual(self.game.card_state_text("right", Knight), "Click to add")

    def test_the_portraits_are_made_once_and_mirrored_for_the_right_team(self):
        left = drawing.portrait(Knight, 1)
        self.assertIs(drawing.portrait(Knight, 1), left)
        right = drawing.portrait(Knight, -1)
        width = left.get_width()
        for x, y in ((30, 70), (95, 75), (60, 30)):
            self.assertEqual(left.get_at((x, y)), right.get_at((width - 1 - x, y)))
        self.assertNotEqual(pygame.image.tostring(drawing.portrait(Archer, 1), "RGBA"),
                            pygame.image.tostring(drawing.portrait(Engineer, 1), "RGBA"))


# ----- 7. the battlefield ---------------------------------------------------------------------------

class BattlefieldLookTest(PlayabilityTestCase):
    def test_positions_and_hit_boxes_are_where_they_were(self):
        self.start([Knight, Archer, Engineer], [Engineer, Knight, Archer])
        battle = self.game.battle
        self.assertEqual({s: (c.x, c.y) for s, c in battle.cannons.items()}, CANNON_PIVOT)
        self.assertEqual(main.muzzle_point(battle.cannons["left"]), (361, 523))
        self.assertEqual(battle.teams["left"].character_rect(0), (126, GROUND_Y - 44, 28, 44))
        self.assertEqual(battle.castles["right"].blocks[0].rect(), (1076, 528, 32, 32))
        self.game.draw()

    def test_the_scenery_behind_the_units_is_darker_and_the_ground_line_is_marked(self):
        art = drawing.load_valley_art(main.WINDOW_WIDTH, main.WINDOW_HEIGHT)
        if art is None:
            self.skipTest("assets/siege-valley.jpg is missing")

        def brightness(surface, y):
            return sum(sum(surface.get_at((x, y))[:3]) for x in range(0, main.WINDOW_WIDTH, 16))
        self.assertLess(brightness(self.game.background, 550), 0.85 * brightness(art, 550))
        self.assertEqual(brightness(self.game.background, 380), brightness(art, 380))   # the sky is kept
        line = [tuple(self.game.background.get_at((x, GROUND_Y)))[:3] for x in range(0, 200)]
        self.assertIn(drawing.GRASS_EDGE, line)
        self.assertNotEqual(set(line), {drawing.GRASS_EDGE})       # a grass line with gaps

    def test_damaged_and_destroyed_blocks_have_their_own_shapes(self):
        surface = pygame.Surface((200, 60))
        corners = []
        for x, hp in ((10, 100), (60, 60), (110, 20)):
            surface.fill((255, 0, 255))
            drawing.draw_block(surface, "left", x, 10, 32, hp, 100)
            corners.append((tuple(surface.get_at((x + 30, 11)))[:3], tuple(surface.get_at((x + 1, 11)))[:3]))
        magenta = (255, 0, 255)
        self.assertNotIn(magenta, corners[0])                      # whole: both top corners are stone
        self.assertEqual((corners[1][0] == magenta, corners[1][1] == magenta), (True, False))   # one chipped
        self.assertEqual(corners[2], (magenta, magenta))           # two chipped
        surface.fill(magenta)
        drawing.draw_rubble_outline(surface, 10, 10, 32, on_ground=True)
        self.assertEqual(tuple(surface.get_at((26, 26)))[:3], magenta)       # see-through ...
        self.assertEqual(tuple(surface.get_at((28, 39)))[:3], drawing.RUBBLE_COLOR)   # ... with a heap

    def test_characters_stand_on_a_shadow_and_the_plain_shot_has_a_light_rim(self):
        self.start([Knight], [Archer])
        self.game.draw()
        x = main.SLOT_X["right"][0] - 12            # beside RIGHT's feet (LEFT's are inside the yellow ring)
        self.assertLess(sum(self.screen.get_at((x, GROUND_Y + 1))[:3]),
                        sum(self.background_at(x, GROUND_Y + 1)))
        aim(self.game, *COVER_WALL)
        self.click(self.game.action_buttons["attack"].rect)
        run_to_cannon(self.game)
        frames(self.game, 10)
        self.game.draw()
        shot = self.game.battle.projectile
        self.assertEqual(tuple(self.screen.get_at((round(shot.x), round(shot.y))))[:3], main.SHOT_COLOR)
        self.assertEqual(tuple(self.screen.get_at((round(shot.x) + 6, round(shot.y))))[:3], main.SHOT_RIM)


# ----- 8. panel, HUD and result -------------------------------------------------------------------

class PanelLayoutTest(PlayabilityTestCase):
    def test_the_three_groups_fit_the_panel_with_gaps(self):
        groups = list(main.PANEL_GROUPS.values())
        window = pygame.Rect(0, main.PANEL_TOP, main.WINDOW_WIDTH, main.WINDOW_HEIGHT - main.PANEL_TOP)
        for i, group in enumerate(groups):
            self.assertTrue(window.contains(group), group)
            for other in groups[i + 1:]:
                self.assertGreaterEqual(abs(other.left - group.right), 10)
        controls = main.PANEL_GROUPS["controls"]
        for button in self.game.action_buttons.values():
            self.assertTrue(controls.contains(button.rect))
        self.assertTrue(controls.contains(self.game.power_bar.inflate(14, 16)))
        buttons = [b.rect for b in self.game.action_buttons.values()]
        self.assertEqual(self.game.power_bar.inflate(14, 16).collidelist(buttons), -1)

    def test_texts_stay_inside_their_groups_in_every_situation(self):
        situations = []
        self.start([Knight, Archer, Engineer], [Engineer, Knight, Archer], aim_mode="reflex")
        situations.append("reflex, swinging")
        for index in range(3):
            self.game.select_actor(index)
            self.check_panel_fits(f"reflex, actor {index}")
        frames(self.game, 30)
        self.press_space()
        self.check_panel_fits("reflex, locked")
        self.game = main.Game(self.screen, ai_seed=5)
        self.start_vs_ai([Engineer, Archer, Knight])
        self.check_panel_fits("classic, person")
        self.click(self.game.action_buttons["defend"].rect)
        self.check_panel_fits("computer thinking")
        frames(self.game, main.AI_DELAY_FRAMES + 5)
        self.check_panel_fits("computer acting")

    def check_panel_fits(self, situation):
        with self.subTest(situation=situation):
            for name, rects in self.game.panel_text_rects().items():
                group = main.PANEL_GROUPS[name]
                for rect in rects:
                    self.assertTrue(group.contains(rect), (name, rect, group))
            aim_row = self.game.panel_text_rects()["controls"]
            for button in self.game.action_buttons.values():
                self.assertEqual(button.rect.collidelist(aim_row), -1)
            self.game.draw()

    def test_the_angle_and_power_are_the_biggest_numbers_in_the_panel(self):
        self.start([Knight], [Archer])
        self.assertEqual(self.game.aim_values(), ("45°", "50"))
        self.assertGreater(self.game.aim_font.get_height(), self.game.font.get_height())
        self.assertIn("drag", self.game.aim_labels()[1])

    def test_the_hud_shows_who_is_standing_large_and_the_cover_smaller(self):
        self.start([Knight, Archer], [Engineer, Knight])
        self.assertEqual(self.game.hud_team_line("left"), "LEFT  2/2")
        self.assertEqual(self.game.hud_detail_line("left"), "standing · cover 6/6")
        banner = self.game.hud_banner_rect()
        for side_rect in self.game.hud_side_rects().values():
            self.assertFalse(banner.colliderect(side_rect))

    def test_the_main_buttons_share_the_warm_gold_style(self):
        self.assertTrue(self.game.start_button.primary)
        self.assertTrue(self.game.rematch_button.primary)
        self.assertTrue(self.game.action_buttons["attack"].primary)
        self.assertFalse(self.game.action_buttons["defend"].primary)

    def test_the_result_panel_puts_the_winner_reason_and_next_step_in_order(self):
        for winner in ("left", "right"):
            self.game = main.Game(self.screen)
            self.start([Knight], [Archer])
            if winner == "right":
                self.click(self.game.action_buttons["defend"].rect)
            end_match_now(self)
            with self.subTest(winner=winner):
                self.game.draw()
                banner = main.result_banner_rect()
                self.assertEqual(tuple(self.screen.get_at((banner.left + 4, banner.top + 4)))[:3],
                                 main.TEAM_COLORS[winner])
                rows = self.game.result_rows()
                self.assertEqual([name for name, _ in rows], ["title", "reason", "rounds", "buttons"])
                tops = [top for _, top in rows]
                self.assertEqual(tops, sorted(tops))
        self.game = main.Game(self.screen)
        self.start([Knight], [Knight])
        test_main.defend_until_the_end(self)
        self.assertEqual(self.game.battle.winner, "draw")
        self.game.draw()
        x, y = self.game.result_badge_center()                     # a neutral badge: an equals sign
        self.assertEqual(tuple(self.screen.get_at((x, y)))[:3], main.DRAW_COLOR)
        bar = (x, y - main.RESULT_BADGE_RADIUS // 4)
        self.assertEqual(tuple(self.screen.get_at(bar))[:3], main.EMBLEM_COLOR)


if __name__ == "__main__":
    unittest.main()
