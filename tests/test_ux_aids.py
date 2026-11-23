"""Tests for M6.4, the five items of docs/M6.4_ux_research.md as the M6.4 request ordered them:

  1 each team's last shot: its aim and result in the panel, a faint mark where its center shell landed
  2 a marker under the HUD for shells above the top of the window
  3 R during a match asks first (Continue / Restart) and pauses the match meanwhile
  4 the computer thinks ahead during its pause, and imagines each shot of a decision once
  5 the practice range (Practice on the selection screen)

Run from the project root:  python -m unittest discover tests
The rules and AI tests use only the standard library; the screen tests need Pygame (skipped
without it), use SDL's "dummy" drivers and send input to the same Game methods the main loop uses.
"""
import copy
import unittest
import unittest.mock

import test_main
import test_playability
from test_main import (FRONT_CHARACTER, HARMLESS, aim, end_match_now, finish_shot, pass_turn,
                       run_to_cannon)
from test_playability import OUT_OF_FIELD, PlayabilityTestCase, frames, key
from test_six_roles import AIRBURST_ON_FRONT, OPEN, VOLLEY_ON_FRONT, combat, fly, of_type, press, release, until
import ai
from ai import AIController
from battle import MAX_STEPS, Battle
from castle import GROUND_Y
from characters import Archer, Bombardier, Engineer, Gunner, Knight, Medic

pygame = test_main.pygame
if pygame is not None:
    import drawing
    import main


FRONT_THREE = [Knight, Archer, Engineer]


def landings(events):
    """The "explosion" and "miss" events of an attack's shells, in the order they landed."""
    return [event for event in events if event["type"] in ("explosion", "miss")]


def fire(battle, action, angle, power):
    """The active team's slot 0 fires `action` with this aim; returns the events of the attack."""
    cannon = battle.cannons[battle.active_side]
    cannon.adjust_angle(angle - cannon.angle)
    cannon.adjust_power(power - cannon.power)
    battle.take_events()
    battle.perform_action(0, action)
    return fly(battle)


# ----- 1. the last shot: which shell is the center shell (battle.py) ---------------------------

class CenterShellTest(unittest.TestCase):
    """Each landing event says whether its shell is the center shell: the shell fired with the aim
    the player set (M6.4), so the game can mark where that aim really landed."""

    def test_a_single_shell_is_its_own_center_shell(self):
        events = landings(fire(combat([Knight], [Knight]), "attack", *FRONT_CHARACTER))
        self.assertEqual([event["center"] for event in events], [True])

    def test_a_shell_that_flies_off_the_side_says_so_too(self):
        events = landings(fire(combat([Knight], [Knight]), "attack", *OUT_OF_FIELD))
        self.assertEqual([(event["type"], event["center"]) for event in events], [("miss", True)])

    def plain_landing(self, role, aim_at):
        """Where one plain shell with this aim lands (an Attack by the same role, same field)."""
        event = landings(fire(combat([role], FRONT_THREE, layouts=OPEN), "attack", *aim_at))[0]
        return round(event["x"], 6), round(event["y"], 6)

    def test_only_the_unchanged_volley_shell_is_the_center_shell(self):
        events = landings(fire(combat([Gunner], FRONT_THREE, layouts=OPEN), "special", *VOLLEY_ON_FRONT))
        centers = [event for event in events if event["center"]]
        self.assertEqual((len(events), len(centers)), (3, 1))
        # It flew exactly as one plain shell with the same aim does.
        self.assertEqual((round(centers[0]["x"], 6), round(centers[0]["y"], 6)),
                         self.plain_landing(Gunner, VOLLEY_ON_FRONT))

    def test_only_the_airburst_shell_that_keeps_its_speed_is_the_center_shell(self):
        events = landings(fire(combat([Bombardier], FRONT_THREE, layouts=OPEN), "special", *AIRBURST_ON_FRONT))
        centers = [event for event in events if event["center"]]
        self.assertEqual((len(events), len(centers)), (5, 1))
        self.assertEqual((round(centers[0]["x"], 6), round(centers[0]["y"], 6)),
                         self.plain_landing(Bombardier, AIRBURST_ON_FRONT))

    def test_an_airburst_shell_before_its_split_is_the_center_shell(self):
        battle = combat([Bombardier], FRONT_THREE, layouts=OPEN)
        battle.perform_action(0, "special")
        self.assertEqual([(shell.center, shell.split is not None) for shell in battle.projectiles],
                         [(True, True)])

    def test_nothing_else_about_the_shot_changes(self):
        """The flag is only read by the screen: damage, EXP and the turn are as before."""
        battle = combat([Gunner], FRONT_THREE, layouts=OPEN)
        events = fire(battle, "special", *VOLLEY_ON_FRONT)
        self.assertEqual(sum(1 for event in events if event["type"] == "exp"), 1)
        self.assertEqual(battle.active_side, "right")


class ShotRecordTest(unittest.TestCase):
    """main.ShotRecord on its own: the aim, the result words and the mark."""

    @unittest.skipIf(pygame is None, "Pygame is not installed")
    def test_the_line_names_the_aim_and_where_one_shell_landed(self):
        record = main.ShotRecord("left", 45, 83)
        record.landings.append({"type": "explosion", "kind": "block", "x": 990.0, "y": 520.0,
                                "center": True})
        self.assertEqual(record.text(), "Last shot · 45° / 83 · COVER HIT")
        self.assertEqual(record.mark(), (990.0, 520.0))

    @unittest.skipIf(pygame is None, "Pygame is not installed")
    def test_a_shot_off_the_side_has_words_but_no_mark(self):
        record = main.ShotRecord("right", 40, 88)
        record.landings.append({"type": "miss", "reason": "offscreen", "x": 0.0, "y": 300.0, "center": True})
        self.assertEqual(record.text(), "Last shot · 40° / 88 · OUT OF FIELD")
        self.assertIsNone(record.mark())

    @unittest.skipIf(pygame is None, "Pygame is not installed")
    def test_several_shells_give_the_totals_and_the_center_shells_mark(self):
        record = main.ShotRecord("left", 57, 85)
        for kind, x, center in (("character", 1140.0, False), ("character", 1150.0, True), ("ground", 1200.0, False)):
            record.landings.append({"type": "explosion", "kind": kind, "x": x, "y": 540.0, "center": center})
        self.assertEqual(record.text(), "Last shot · 57° / 85 · 2 direct, 1 ground")
        self.assertEqual(record.mark(), (1150.0, 540.0))

    @unittest.skipIf(pygame is None, "Pygame is not installed")
    def test_without_a_known_center_shell_only_the_totals_are_shown(self):
        record = main.ShotRecord("left", 50, 86)
        for kind in ("character", "ground", "ground", "block", "ground"):
            record.landings.append({"type": "explosion", "kind": kind, "x": 1000.0, "y": 560.0})
        self.assertEqual(record.text(), "Last shot · 50° / 86 · 1 direct, 1 cover, 3 ground")
        self.assertIsNone(record.mark())


@unittest.skipIf(pygame is None, "Pygame is not installed")
class LastShotTest(PlayabilityTestCase):
    def shoot(self, angle, power, action="attack"):
        aim(self.game, angle, power)
        self.game.do_action(action)
        finish_shot(self.game)

    def actor_texts(self):
        return [text for group, text, *_ in self.game.panel_items() if group == "actor"]

    def test_each_team_sees_only_its_own_last_shot_on_its_own_turn(self):
        self.start([Knight], [Archer])
        self.assertIsNone(self.game.last_shot_line())              # nothing fired yet
        self.shoot(*FRONT_CHARACTER)                                # LEFT: 45 / 83, a direct hit
        self.assertEqual(self.game.battle.active_side, "right")
        self.assertIsNone(self.game.last_shot_line())              # RIGHT has not fired yet
        self.shoot(*HARMLESS)                                       # RIGHT: 80 / 10, beside its own cannon
        self.assertEqual(self.game.last_shot_line(), "Last shot · 45° / 83 · DIRECT HIT")
        self.assertIn("Last shot · 45° / 83 · DIRECT HIT", self.actor_texts())
        self.game.do_action("defend")
        self.game.update()
        self.assertEqual(self.game.last_shot_line(), "Last shot · 80° / 10 · GROUND IMPACT")

    def test_the_mark_is_where_the_shot_really_landed(self):
        self.start([Knight], [Archer])
        seen, show = [], self.game.show_event
        self.game.show_event = lambda event: (seen.append(event), show(event))
        self.shoot(*FRONT_CHARACTER)
        landing = landings(seen)[0]
        self.game.do_action("defend")                                  # RIGHT
        self.game.update()
        self.assertEqual(self.game.battle.active_side, "left")
        self.assertEqual(self.game.last_shot_mark(), (landing["x"], landing["y"]))

    def test_it_is_shown_only_while_that_team_may_aim(self):
        self.start([Knight], [Archer])
        self.shoot(*FRONT_CHARACTER)
        self.game.do_action("defend")
        self.game.update()
        self.assertIsNotNone(self.game.last_shot_line())
        aim(self.game, *HARMLESS)
        self.game.do_action("attack")                                  # the run starts: controls locked
        self.assertIsNone(self.game.last_shot_line())
        self.assertIsNone(self.game.last_shot_mark())

    def test_a_new_shot_replaces_the_record_and_a_defend_keeps_it(self):
        self.start([Knight], [Archer])
        self.shoot(*FRONT_CHARACTER)
        pass_turn(self.game)                                           # RIGHT defends
        pass_turn(self.game)                                           # LEFT defends: no new shot
        pass_turn(self.game)                                           # RIGHT (a harmless shot)
        self.assertEqual(self.game.last_shot_line(), "Last shot · 45° / 83 · DIRECT HIT")
        self.shoot(*HARMLESS)                                          # LEFT fires again
        pass_turn(self.game)
        self.assertEqual(self.game.last_shot_line(), "Last shot · 80° / 10 · GROUND IMPACT")

    def test_a_shot_off_the_side_is_words_only(self):
        self.start([Knight], [Archer])
        self.shoot(*OUT_OF_FIELD)
        self.game.do_action("defend")
        self.game.update()
        self.assertEqual(self.game.last_shot_line(), "Last shot · 40° / 88 · OUT OF FIELD")
        self.assertIsNone(self.game.last_shot_mark())

    def test_a_volley_marks_its_center_shell_and_counts_the_rest(self):
        self.start([Gunner], [Knight])
        seen, show = [], self.game.show_event
        self.game.show_event = lambda event: (seen.append(event), show(event))
        self.shoot(*FRONT_CHARACTER, action="special")
        center = [event for event in landings(seen) if event["center"]]
        self.game.do_action("defend")
        self.game.update()
        line = self.game.last_shot_line()
        self.assertTrue(line.startswith("Last shot · 45° / 83 · "), line)
        words = line.split(" · ")[-1]
        self.assertEqual(sum(int(part.split()[0]) for part in words.split(", ")), 3)    # all three shells
        self.assertEqual(self.game.last_shot_mark(), (center[0]["x"], center[0]["y"]))

    def test_the_record_is_only_read_never_used_to_aim(self):
        self.start([Knight], [Archer])
        self.shoot(*FRONT_CHARACTER)
        self.game.do_action("defend")
        self.game.update()
        cannon = self.game.battle.cannons["left"]
        self.assertEqual((cannon.angle, cannon.power), FRONT_CHARACTER)    # kept by the cannon, as before
        aim(self.game, 30, 60)
        self.game.update()
        self.assertEqual((cannon.angle, cannon.power), (30, 60))
        self.assertEqual(self.game.last_shot_line(), "Last shot · 45° / 83 · DIRECT HIT")

    def test_a_rematch_forgets_both_records(self):
        self.start([Knight], [Archer])
        self.shoot(*FRONT_CHARACTER)
        self.shoot(*HARMLESS)
        end_match_now(self)
        self.click(self.game.rematch_button.rect)
        self.assertEqual(self.game.last_shots, {"left": None, "right": None})
        self.assertIsNone(self.game.last_shot_line())

    def test_the_computer_has_a_record_but_it_is_never_shown(self):
        self.game = main.Game(self.screen, ai_seed=4)
        self.click(self.game.difficulty_buttons["hard"].rect)        # Hard never defends when unhurt
        self.start_vs_ai([Knight])
        self.shoot(*FRONT_CHARACTER)                                   # LEFT has a record now
        until(self.game, lambda: self.game.cannon_run.is_busy(), 200)  # the computer runs to fire
        self.assertIsNone(self.game.last_shot_line())                  # nothing shown on its turn
        until(self.game, lambda: self.game.battle.active_side == "left" and not self.game.controls_locked(), 1500)
        self.assertIsNotNone(self.game.last_shots["right"])            # it was recorded ...
        self.assertEqual(self.game.last_shot_line(), "Last shot · 45° / 83 · DIRECT HIT")   # ... LEFT sees its own

    def test_the_line_and_the_mark_are_drawn(self):
        self.start([Knight], [Archer])
        self.shoot(*FRONT_CHARACTER)
        self.game.do_action("defend")
        self.game.update()
        x, y = self.game.last_shot_mark()
        with self.hover((2000, 2000)):
            self.game.draw()
        before = self.screen.copy()
        self.game.last_shots["left"] = None
        with self.hover((2000, 2000)):
            self.game.draw()
        self.assertNotEqual(before.get_at((round(x) + main.LAST_MARK_RADIUS - 1, round(y))),
                            self.screen.get_at((round(x) + main.LAST_MARK_RADIUS - 1, round(y))))

    def test_the_line_fits_in_the_actor_group_for_every_role(self):
        group = main.PANEL_GROUPS["actor"]
        longest = "Last shot · 75° / 100 · 2 direct, 2 cover, 1 ground"
        for role in (Knight, Archer, Engineer, Gunner, Bombardier, Medic):
            for cooling in (False, True):
                with self.subTest(role=role.__name__, cooling=cooling):
                    self.game = main.Game(self.screen)
                    self.start([role], [Knight])
                    self.game.last_shot_line = lambda: longest
                    if cooling:                                        # "ready in 3" instead of "ready"
                        self.game.battle.teams["left"].characters[0].start_cooldown()
                    for rect in self.game.panel_text_rects()["actor"]:
                        self.assertTrue(group.contains(rect), (role.__name__, rect))
                    self.assertIn(longest, self.actor_texts())


# ----- 2. shells above the top of the window ----------------------------------------------------

@unittest.skipIf(pygame is None, "Pygame is not installed")
class AboveViewMarkerTest(PlayabilityTestCase):
    def fire_high(self, angle, power, action="attack"):
        """The team to move fires; returns, for every frame of the flight, (marker, x of each shell
        above the window, shells in the air)."""
        aim(self.game, angle, power)
        self.game.do_action(action)
        run_to_cannon(self.game)
        seen = []
        while self.game.battle.projectiles:
            above = [shell.x for shell in self.game.battle.projectiles if shell.y < 0]
            seen.append((self.game.above_marker(), above, len(self.game.battle.projectiles)))
            self.game.update()
        seen.append((self.game.above_marker(), [], 0))        # after the last shell has landed
        return seen

    def test_75_and_80_degrees_at_power_100_are_followed_for_39_and_57_frames(self):
        for angle, frames_above in ((75, 39), (80, 57)):
            with self.subTest(angle=angle):
                self.game = main.Game(self.screen)
                self.start([Knight], [Knight])
                seen = self.fire_high(angle, 100)
                self.assertEqual(sum(1 for marker, _, _ in seen if marker is not None), frames_above)
                for marker, above, _ in seen:
                    self.assertEqual(marker is not None, bool(above))           # only while one is up there
                    if above:
                        self.assertEqual(marker, (round(above[0]), "Shell above view"))

    def test_the_right_cannons_marker_is_the_mirror_image(self):
        self.start([Knight], [Knight])
        left = [marker[0] for marker, _, _ in self.fire_high(75, 100) if marker]
        until(self.game, lambda: self.game.battle.active_side == "right" and not self.game.controls_locked(), 50)
        right = [marker[0] for marker, _, _ in self.fire_high(75, 100) if marker]
        self.assertEqual(len(left), 39)
        self.assertEqual([main.WINDOW_WIDTH - x for x in right], left)

    def test_several_shells_above_share_one_marker_with_their_number(self):
        self.start([Gunner], [Knight])
        seen = self.fire_high(75, 100, action="special")       # the 69° shell stays in view, 75° and 81° go up
        self.assertEqual({len(above) for _, above, _ in seen}, {0, 1, 2})
        for marker, above, flying in seen:
            if len(above) == 2:
                self.assertEqual(marker, (round(sum(above) / 2), "2 shells above"))
                self.assertEqual(flying, 3)                                   # the third one is in view

    def test_an_airburst_split_above_the_window_counts_its_small_shells(self):
        self.start([Bombardier], [Knight])
        texts = {marker[1] for marker, _, _ in self.fire_high(80, 100, action="special") if marker}
        self.assertEqual(texts, {"Shell above view", "5 shells above"})

    def test_a_shell_that_leaves_by_the_side_is_never_shown_as_still_flying(self):
        self.start([Knight], [Knight])
        aim(self.game, 75, 100)
        self.game.do_action("attack")
        run_to_cannon(self.game)
        shell = self.game.battle.projectile
        shell.x, shell.y, shell.vx = main.WINDOW_WIDTH - 1, -40.0, 600.0    # above the top, at the edge
        self.assertIsNotNone(self.game.above_marker())
        self.game.update()                                                  # it crosses the edge: a miss
        self.assertEqual(self.game.battle.projectiles, [])
        self.assertIsNone(self.game.above_marker())

    def test_the_marker_stays_under_the_hud_and_inside_the_window(self):
        self.start([Knight], [Knight])
        for x in (0, 300, 640, 1280):
            with self.subTest(x=x):
                self.game.above_marker = lambda: (min(max(x, 0), main.WINDOW_WIDTH), "3 shells above")
                rect = self.game.above_marker_rect()
                self.assertFalse(rect.colliderect(self.game.hud_banner_rect()))
                self.assertGreater(rect.top, 62 + self.game.small_font.get_height() // 2)   # under the message
                self.assertTrue(pygame.Rect(0, 0, main.WINDOW_WIDTH, main.PANEL_TOP).contains(rect))

    def test_the_marker_is_drawn(self):
        self.start([Knight], [Knight])
        aim(self.game, 80, 100)
        self.game.do_action("attack")
        run_to_cannon(self.game)
        until(self.game, lambda: self.game.above_marker() is not None, 200)
        x = self.game.above_marker()[0]
        with self.hover((2000, 2000)):
            self.game.draw()
        self.assertIn(main.ABOVE_COLOR, self.colours_near((x, main.ABOVE_Y + 6)))


# ----- 3. R during a match asks first, and the match waits -----------------------------------

def frozen_state(game):
    """What must not change while the match waits: the battle, every shell, the run, the swing,
    the computer's pause and the effects on screen."""
    battle = game.battle
    rules = test_playability.battle_state(battle)
    return (rules[:6] + rules[7:],                       # all but the shell object (compared by its numbers)
            [(shell.x, shell.y, shell.vx, shell.vy, shell.steps) for shell in battle.projectiles],
            (game.cannon_run.state, game.cannon_run.frame), game.ai_wait,
            [(side, swing.angle()) for side, swing in game.swings.items()],
            [list(e) for e in game.explosions], [list(f) for f in game.floaters], len(game.log))


@unittest.skipIf(pygame is None, "Pygame is not installed")
class RestartQuestionTest(PlayabilityTestCase):
    def test_escape_opens_the_menu_and_holding_it_does_not_close_it(self):
        self.start([Knight], [Archer])
        before = frozen_state(self.game)
        for _ in range(3):
            press(self.game, pygame.K_ESCAPE)
            self.game.update()
        self.assertTrue(self.game.match_paused)
        self.assertTrue(self.game.running)
        self.assertEqual(frozen_state(self.game), before)
        release(self.game, pygame.K_ESCAPE)
        key(self.game, pygame.K_ESCAPE)
        self.assertFalse(self.game.match_paused)

    def test_main_menu_abandons_the_shot_but_preserves_setup(self):
        self.start([Gunner], [Archer], aim_mode="reflex")
        selection = self.game.selection.roster()
        layouts = dict(self.game.setup.layouts)
        self.click(self.game.action_buttons["attack"].rect)
        run_to_cannon(self.game)
        self.assertTrue(self.game.battle.projectiles)
        key(self.game, pygame.K_ESCAPE)
        self.click(self.game.main_menu_button.rect)
        self.assertEqual(self.game.state, "select")
        self.assertIsNone(self.game.battle)
        self.assertIsNone(self.game.locked_shot)
        self.assertIsNone(self.game.ai_thoughts)
        self.assertFalse(self.game.cannon_run.is_busy())
        self.assertFalse(self.game.match_paused)
        self.assertTrue(self.game.running)
        self.assertEqual(self.game.selection.roster(), selection)
        self.assertEqual(self.game.selection.aim_mode, "reflex")
        self.assertEqual(self.game.setup.layouts, layouts)
        self.click(self.game.start_button.rect)
        self.assertEqual((self.game.state, self.game.placing), ("cover", "left"))

    def test_r_in_a_match_asks_and_continue_is_the_default(self):
        self.start([Knight], [Archer])
        key(self.game, pygame.K_r)
        self.assertTrue(self.game.match_paused)
        self.assertTrue(self.game.continue_button.primary)                 # the default, in gold
        self.assertFalse(self.game.restart_button.primary)
        before = frozen_state(self.game)
        key(self.game, pygame.K_RETURN)                                    # Enter takes the default
        self.assertFalse(self.game.match_paused)
        self.assertEqual(frozen_state(self.game), before)

    def test_everything_waits_and_continues_from_the_same_frame(self):
        """Two games get the same input; one waits 45 frames at the question in the middle of the
        run. Afterwards both are in exactly the same state, frame for frame."""
        games = []
        for _ in range(2):
            self.game = main.Game(self.screen)
            self.start([Gunner], [Knight])
            aim(self.game, 75, 100)
            self.game.do_action("special")
            frames(self.game, 12)                                          # running to the cannon
            games.append(self.game)
        paused, twin = games
        key(paused, pygame.K_r)
        before = frozen_state(paused)
        frames(paused, 45)
        self.assertEqual(frozen_state(paused), before)
        key(paused, pygame.K_ESCAPE)                                       # Esc also means Continue
        self.assertTrue(paused.running)
        for _ in range(140):                                              # the run, the launch, the flight
            paused.update()
            twin.update()
            self.assertEqual(frozen_state(paused), frozen_state(twin))

    def test_a_flying_shell_and_the_reflex_swing_wait(self):
        self.start([Knight], [Archer], aim_mode="reflex")
        frames(self.game, 7)
        swing = self.game.swings["left"].angle()
        key(self.game, pygame.K_r)
        frames(self.game, 30)
        self.assertEqual(self.game.swings["left"].angle(), swing)
        key(self.game, pygame.K_RETURN)
        self.press_space()                                                 # lock and fire
        run_to_cannon(self.game)
        frames(self.game, 5)
        shell = self.game.battle.projectile
        where = (shell.x, shell.y)
        key(self.game, pygame.K_r)
        frames(self.game, 30)
        self.assertEqual((shell.x, shell.y), where)

    def test_the_computers_turn_waits(self):
        self.start_vs_ai([Knight])
        self.click(self.game.action_buttons["defend"].rect)
        frames(self.game, 10)
        wait, log = self.game.ai_wait, list(self.game.log)
        key(self.game, pygame.K_r)
        frames(self.game, main.AI_DELAY_FRAMES + 20)
        self.assertEqual((self.game.ai_wait, self.game.log), (wait, log))   # it has not chosen
        key(self.game, pygame.K_RETURN)
        frames(self.game, main.AI_DELAY_FRAMES - wait)
        self.assertIn("AI (Normal):", " ".join(self.game.log[len(log):]))

    def test_restart_needs_its_own_press_so_holding_r_never_restarts(self):
        self.start([Knight], [Archer])
        self.game.battle.teams["right"].characters[0].take_damage(30)
        first = self.game.battle.first_side
        for _ in range(20):                                                # R held down: key repeat
            press(self.game, pygame.K_r)
            self.game.update()
        self.assertTrue(self.game.match_paused)
        self.assertEqual(self.game.battle.teams["right"].characters[0].hp, 60)      # nothing restarted
        release(self.game, pygame.K_r)
        press(self.game, pygame.K_r)                                       # a new press: Restart
        self.assertFalse(self.game.match_paused)
        self.assertEqual(self.game.battle.teams["right"].characters[0].hp, 90)
        self.assertNotEqual(self.game.battle.first_side, first)           # a rematch, as R always was
        for _ in range(20):                                                # still held: no new question
            press(self.game, pygame.K_r)
            self.game.update()
        self.assertFalse(self.game.match_paused)

    def test_the_restart_button_restarts_and_clears_the_match(self):
        self.start([Knight], [Archer])
        aim(self.game, *FRONT_CHARACTER)
        self.game.do_action("attack")
        run_to_cannon(self.game)
        key(self.game, pygame.K_r)
        self.click(self.game.restart_button.rect)
        battle = self.game.battle
        self.assertFalse(self.game.match_paused)
        self.assertEqual((battle.projectiles, battle.round_number, self.game.cannon_run.is_busy()), ([], 1, False))
        self.assertEqual([c.hp for t in battle.teams.values() for c in t.characters], [140, 90])

    def test_while_it_asks_only_its_two_buttons_answer(self):
        self.start([Knight], [Archer])
        key(self.game, pygame.K_r)
        self.click(self.game.action_buttons["defend"].rect)
        self.game.handle_key(test_main.battle_key(self.game, "up"), 0)
        self.assertEqual((self.game.battle.active_side, self.game.battle.cannons["left"].angle), ("left", 45))
        self.click(self.game.continue_button.rect)
        self.assertFalse(self.game.match_paused)
        self.click(self.game.action_buttons["defend"].rect)              # now it works again
        self.assertEqual(self.game.battle.active_side, "right")

    def test_after_the_match_r_still_rematches_at_once(self):
        self.start([Knight], [Archer])
        end_match_now(self)
        key(self.game, pygame.K_r)
        self.assertEqual((self.game.state, self.game.match_paused), ("battle", False))

    def test_the_question_is_drawn_over_the_match(self):
        self.start([Knight], [Archer])
        key(self.game, pygame.K_r)
        with self.hover((2000, 2000)):
            self.game.draw()
        center = self.game.continue_button.rect.center
        self.assertEqual(tuple(self.screen.get_at(center))[:3], drawing.PRIMARY_COLOR)
        self.assertIn("paused", self.game.hud_turn_text())


# ----- 4. the computer: each shot of a decision imagined once, and thought out ahead --------------

SPREAD_TEAM = [Gunner, Bombardier, Medic]


def decision_states(count=4):
    """(difficulty, seed, battle, controller) at the computer's (RIGHT's) first `count` decisions
    of AI-vs-AI 3v3 matches: RIGHT Gunner, Bombardier, Medic (both spread specials and a heal),
    LEFT Knight, Archer, Engineer; every AI places its own cover. Copies, so each test may use them."""
    states = []
    for difficulty in ("easy", "normal", "hard"):
        for seed in (0, 1):
            ais = {"left": AIController("left", difficulty, seed=100 + seed),
                   "right": AIController("right", difficulty, seed=seed)}
            battle = Battle({"left": FRONT_THREE, "right": SPREAD_TEAM},
                            layouts={side: c.choose_layout() for side, c in ais.items()}, first_side="right")
            battle.take_events()
            while not battle.is_over() and sum(1 for s in states if s[:2] == (difficulty, seed)) < count:
                if battle.active_side == "right":
                    states.append((difficulty, seed, copy.deepcopy(battle), copy.deepcopy(ais["right"])))
                    ais["right"].take_turn(battle)
                else:
                    ais["left"].take_turn(battle)
                fly(battle)
    return states


class CountedImagine:
    """Counts the shots really imagined (calls of ai.imagine) while it is in use."""

    def __enter__(self):
        self.keys, real = [], ai.imagine

        def counting(battle, actor_index, action, angle=None, power=None):
            self.keys.append((actor_index, action, angle, power))
            return real(battle, actor_index, action, angle, power)
        self.patch = unittest.mock.patch.object(ai, "imagine", counting)
        self.patch.start()
        return self

    def __exit__(self, *problem):
        self.patch.stop()


def plan_of(plan):
    return plan.actor_index, plan.action, plan.angle, plan.power, plan.goal, plan.reason


class AIMemoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.states = decision_states()

    def test_one_decision_imagines_each_shot_once(self):
        for difficulty, seed, battle, controller in self.states:
            with self.subTest(difficulty=difficulty, seed=seed, round=battle.round_number):
                with CountedImagine() as counted:
                    copy.deepcopy(controller).choose(copy.deepcopy(battle))
                self.assertEqual(len(counted.keys), len(set(counted.keys)))

    def test_thinking_ahead_never_changes_the_decision(self):
        for difficulty, seed, battle, controller in self.states:
            with self.subTest(difficulty=difficulty, seed=seed, round=battle.round_number):
                cold, warm = copy.deepcopy(controller), copy.deepcopy(controller)
                cold_plan = cold.choose(copy.deepcopy(battle))
                warm_battle = copy.deepcopy(battle)
                for _ in warm.thinking_ahead(warm_battle):
                    pass
                self.assertEqual(plan_of(warm.choose(warm_battle)), plan_of(cold_plan))
                self.assertEqual(warm.rng.getstate(), cold.rng.getstate())      # the dice were not touched

    def test_after_thinking_ahead_the_decision_imagines_nothing_new(self):
        for difficulty, seed, battle, controller in self.states:
            with self.subTest(difficulty=difficulty, seed=seed, round=battle.round_number):
                warm, warm_battle = copy.deepcopy(controller), copy.deepcopy(battle)
                for _ in warm.thinking_ahead(warm_battle):
                    pass
                with CountedImagine() as counted:
                    warm.choose(warm_battle)
                self.assertEqual(counted.keys, [])

    def test_each_step_of_thinking_ahead_imagines_at_most_one_shot(self):
        difficulty, seed, battle, controller = self.states[-1]
        steps = []
        thoughts = controller.thinking_ahead(battle)
        while True:
            with CountedImagine() as counted:
                if next(thoughts, "done") == "done":
                    break
            steps.append(len(counted.keys))
        self.assertLessEqual(max(steps), 1)
        self.assertGreater(len(steps), 50)                       # the work really is split up

    def test_the_memory_lasts_one_decision(self):
        difficulty, seed, battle, controller = copy.deepcopy(self.states[0])
        for _ in controller.thinking_ahead(battle):
            pass
        self.assertGreater(len(controller.memory), 0)
        controller.choose(battle)
        self.assertEqual(controller.memory, {})                  # forgotten after the decision
        for _ in controller.thinking_ahead(battle):
            pass
        controller.new_match()
        self.assertEqual(controller.memory, {})                  # and when a match starts again

    def test_shots_imagined_on_another_battle_are_never_used(self):
        difficulty, seed, battle, controller = copy.deepcopy(self.states[1])
        cold = copy.deepcopy(controller)
        for _ in controller.thinking_ahead(copy.deepcopy(battle)):        # a different Battle object
            pass
        with CountedImagine() as counted:
            plan = controller.choose(battle)
        self.assertGreater(len(counted.keys), 0)                 # it imagined its own shots again
        self.assertEqual(plan_of(plan), plan_of(cold.choose(copy.deepcopy(battle))))


@unittest.skipIf(pygame is None, "Pygame is not installed")
class AIThinkingInGameTest(PlayabilityTestCase):
    def start_against(self, difficulty="hard"):
        self.game = main.Game(self.screen, ai_seed=3)
        self.click(self.game.difficulty_buttons[difficulty].rect)
        self.click(self.game.size_buttons[2].rect)
        for role in FRONT_THREE:
            self.click(self.game.card_rects[("left", role)])
        with unittest.mock.patch.object(AIController, "pick_team", return_value=list(SPREAD_TEAM)):
            self.click(self.game.start_button.rect)
            self.click(self.game.confirm_button.rect)

    def test_it_thinks_during_its_pause_and_decides_on_the_same_frame_as_before(self):
        self.start_against()
        self.click(self.game.action_buttons["defend"].rect)
        cold = copy.deepcopy(self.game.ai)
        cold_plan = cold.choose(copy.deepcopy(self.game.battle))
        frames(self.game, main.AI_DELAY_FRAMES - 2)             # (the click ran the turn's first frame)
        self.assertGreater(len(self.game.ai.memory), 0)          # it has been thinking ahead
        self.assertFalse(any(line.startswith("AI (Hard):") for line in self.game.log))   # not decided yet
        with CountedImagine() as counted:
            self.game.update()                                   # frame 40: the decision
        self.assertIn(f"AI (Hard): {cold_plan.reason}.", self.game.log)
        self.assertLess(len(counted.keys), 20)                   # (a cold decision imagines about 100)

    def test_a_restart_while_it_thinks_drops_the_old_thoughts(self):
        self.start_against("normal")
        self.click(self.game.action_buttons["defend"].rect)
        frames(self.game, 10)
        self.assertIsNotNone(self.game.ai_thoughts)
        test_main.restart_with_r(self.game)
        self.assertIsNone(self.game.ai_thoughts)
        self.assertEqual(self.game.ai.memory, {})


# ----- 5. the practice range ---------------------------------------------------------------------

@unittest.skipIf(pygame is None, "Pygame is not installed")
class PracticeRangeTest(PlayabilityTestCase):
    def enter(self):
        self.click(self.game.practice_button.rect)
        self.assertEqual((self.game.state, self.game.practice), ("battle", True))

    def selection_now(self):
        selection = self.game.selection
        return (selection.vs_ai, selection.difficulty, selection.team_size, selection.aim_mode,
                {side: list(picks) for side, picks in selection.picks.items()}, dict(self.game.setup.layouts))

    def test_practice_starts_from_the_selection_screen_without_choosing_teams(self):
        self.assertTrue(self.game.practice_button.enabled)
        self.enter()
        battle = self.game.battle
        self.assertEqual([type(c) for c in battle.teams["left"].characters], [Archer, Gunner, Bombardier])
        self.assertEqual([type(c) for c in battle.teams["right"].characters], [Knight, Archer, Engineer])
        self.assertIsNone(self.game.ai)
        self.assertEqual((battle.active_side, self.game.aim_mode), ("left", "classic"))
        self.assertTrue(self.game.hud_turn_text().startswith("PRACTICE RANGE"))

    def test_after_each_shot_the_targets_and_the_special_are_back_and_the_aim_stays(self):
        self.enter()
        key(self.game, pygame.K_2)                                            # the Gunner
        aim(self.game, *FRONT_CHARACTER)
        self.game.do_action("special")
        finish_shot(self.game)
        self.assertIn("TRIPLE VOLLEY", self.game.last_result)                 # it did hit something ...
        battle = self.game.battle
        self.assertEqual([c.hp for c in battle.teams["right"].characters], [140, 90, 110])   # ... and all is back
        self.assertEqual([b.hp for b in battle.castles["right"].blocks],
                         [b.max_hp for b in battle.castles["right"].blocks])
        self.assertIsNone(battle.why_not_allowed(1, "special"))               # Triple Volley ready again
        self.assertEqual((battle.active_side, battle.round_number), ("left", 1))
        cannon = battle.cannons["left"]
        self.assertEqual((cannon.angle, cannon.power), FRONT_CHARACTER)       # the aim to compare with
        self.assertEqual(self.game.last_shot_line()[:22], "Last shot · 45° / 83 ·")
        self.assertEqual(self.game.selected["left"], 1)                       # still the Gunner

    def test_practice_shots_follow_the_real_rules(self):
        """The same shot in the practice range and in a plain Battle with the same teams and cover
        does exactly the same damage."""
        self.enter()
        key(self.game, pygame.K_3)                                            # the Bombardier
        aim(self.game, 50, 86)
        seen, show = [], self.game.show_event
        self.game.show_event = lambda event: (seen.append(event), show(event))
        self.game.do_action("special")
        finish_shot(self.game)
        battle = Battle(main.PRACTICE_ROSTER, layouts=main.PRACTICE_LAYOUTS)
        battle.cannons["left"].adjust_angle(50 - 45)
        battle.cannons["left"].adjust_power(86 - 50)
        battle.perform_action(2, "special")
        expected = [(e["kind"], e["characters_hit"], e["blocks_hit"], e["damage"])
                    for e in landings(fly(battle)) if e["type"] == "explosion"]
        self.assertEqual([(e["kind"], e["characters_hit"], e["blocks_hit"], e["damage"])
                          for e in landings(seen) if e["type"] == "explosion"], expected)

    def test_one_practice_shot_can_never_defeat_a_target(self):
        """So the practice range never ends: the strongest hit of any practice shooter on one
        target is less than the HP of the weakest target."""
        targets = [role("t", "right") for role in main.PRACTICE_ROSTER["right"]]
        strongest = 0
        for role in main.PRACTICE_ROSTER["left"]:
            shooter = role("s", "left")
            for shot in (shooter.attack_shot(), shooter.use_special(None)[1]):
                for target in targets:
                    hit = target.defense
                    damage = max(1, int(shooter.atk * shot.multiplier) - (0 if shot.ignores_def else hit))
                    shells = len(shot.split) if shot.split else len(shot.spread)
                    strongest = max(strongest, damage * shells)
        self.assertLess(strongest, min(target.max_hp for target in targets))

    def test_classic_and_reflex_switch_here_and_the_selection_keeps_its_own(self):
        self.enter()
        self.click(self.game.practice_buttons["reflex"].rect)
        self.assertEqual((self.game.aim_mode, self.game.selection.aim_mode), ("reflex", "classic"))
        before = self.game.battle.cannons["left"].angle
        frames(self.game, 10)
        self.assertNotEqual(self.game.battle.cannons["left"].angle, before)   # it swings
        self.click(self.game.practice_buttons["classic"].rect)
        self.assertEqual(self.game.aim_mode, "classic")
        angle = self.game.battle.cannons["left"].angle
        frames(self.game, 10)
        self.assertEqual(self.game.battle.cannons["left"].angle, angle)       # it stays

    def test_back_returns_to_the_selection_exactly_as_it_was(self):
        self.click(self.game.mode_buttons["pvp"].rect)
        self.click(self.game.size_buttons[1].rect)
        self.click(self.game.aim_buttons["reflex"].rect)
        for side, role in (("left", Medic), ("left", Gunner), ("right", Knight)):
            self.click(self.game.card_rects[(side, role)])
        self.game.setup.apply_preset("left", "Outer Wall")
        before = self.selection_now()
        self.enter()
        self.assertEqual(self.game.aim_mode, "reflex")                         # starts with the chosen style
        self.click(self.game.practice_buttons["classic"].rect)
        self.press_space()
        finish_shot(self.game)
        self.click(self.game.practice_buttons["back"].rect)
        self.assertEqual((self.game.state, self.game.practice, self.game.battle), ("select", False, None))
        self.assertEqual(self.selection_now(), before)
        self.enter()
        key(self.game, pygame.K_BACKSPACE)                                     # the key does the same
        self.assertEqual(self.game.state, "select")
        self.assertEqual(self.selection_now(), before)

    def test_the_keys_are_those_of_the_chosen_mode(self):
        self.enter()                                                           # Player vs AI: SPACE
        self.assertEqual(self.game.battle_keys()["fire"], (pygame.K_SPACE,))
        key(self.game, pygame.K_BACKSPACE)
        self.click(self.game.mode_buttons["pvp"].rect)
        self.enter()                                                           # two players: LEFT's F
        self.assertEqual(self.game.battle_keys()["fire"], (pygame.K_f,))
        self.press_space()
        self.assertTrue(self.game.cannon_run.is_busy())

    def test_r_resets_the_range_at_once(self):
        self.enter()
        aim(self.game, *FRONT_CHARACTER)
        self.game.do_action("attack")
        run_to_cannon(self.game)
        frames(self.game, 60)
        key(self.game, pygame.K_r)
        battle = self.game.battle
        self.assertFalse(self.game.match_paused)                               # nothing to lose here
        self.assertEqual((battle.projectiles, self.game.cannon_run.is_busy()), ([], False))
        self.assertEqual([c.hp for c in battle.teams["right"].characters], [140, 90, 110])

    def test_the_practice_panel_fits_and_its_buttons_are_drawn(self):
        self.enter()
        group = main.PANEL_GROUPS["log"]
        for button in self.game.practice_buttons.values():
            self.assertTrue(group.contains(button.rect))
        for name, rects in self.game.panel_text_rects().items():
            for rect in rects:
                self.assertTrue(main.PANEL_GROUPS[name].contains(rect), (name, rect))
                if name == "log":
                    for button in self.game.practice_buttons.values():
                        self.assertFalse(rect.colliderect(button.rect))
        self.assertIn("Backspace", self.game.log_header())
        with self.hover((2000, 2000)):
            self.game.draw()
        back = self.game.practice_buttons["back"].rect
        self.assertNotEqual(tuple(self.screen.get_at(back.center))[:3], main.GROUP_COLOR)

    def test_defend_is_greyed_out_in_the_practice_range(self):
        self.enter()
        defend = self.game.action_buttons["defend"]
        self.assertEqual((defend.enabled, defend.note), (False, "shots only"))
        self.game.do_action("defend")
        self.assertEqual((self.game.battle.active_side, self.game.message), ("left", main.PRACTICE_NO_DEFEND))
        self.assertEqual(self.game.action_help("defend"), main.PRACTICE_NO_DEFEND)

    def test_the_practice_button_has_its_own_place_on_the_selection_screen(self):
        button = self.game.practice_button.rect
        self.assertFalse(button.colliderect(self.game.start_button.rect))
        self.assertFalse(button.colliderect(self.game.selection_message_rect()))
        self.assertLess(button.bottom, 648 - 10)                               # above the footer lines
        with self.hover((2000, 2000)):
            self.game.draw()
        self.assertNotEqual(self.screen.get_at(button.center), self.game.menu_background.get_at(button.center))

