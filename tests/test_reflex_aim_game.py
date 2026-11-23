"""Tests for Reflex Aim in the game (M6.1, experimental): the Aim choice on the selection screen,
which cannons swing, capturing the angle, the input lock, the computer, rematches and Classic Aim.

These tests need Pygame (they are skipped if it isn't installed) and use the same setup as
tests/test_main.py: SDL's "dummy" drivers, and clicks and key presses passed to the real
Game.handle_click() / handle_key(), one Game.update() per frame like the main loop.
"""
import math
import unittest

import test_main
from test_main import FRONT_CHARACTER, battle_key, finish_shot, restart_with_r, run_to_cannon

pygame = test_main.pygame
if pygame is not None:
    import main
    from animation import RUN_TO_CANNON
    from battle import CANNON_PIVOT, Projectile
    from characters import Archer, Engineer, Knight
    from reflex_aim import AimSwing


def frames(game, count):
    for _ in range(count):
        game.update()


def expected_angle(frame):
    """The angle of the default swing on `frame` (worked out by a separate AimSwing)."""
    swing = AimSwing()
    for _ in range(frame % swing.period):
        swing.step()
    return swing.angle()


def record_events(game):
    """From now on, keep every Battle event the game shows (it still shows them)."""
    seen, show = [], game.show_event

    def record(event):
        seen.append(event)
        show(event)
    game.show_event = record
    return seen


def record_launches(cannon):
    """From now on, keep the velocity (vx, vy) of every shot this cannon fires, as it leaves the
    barrel (the Projectile itself moves on afterwards)."""
    fired, fire = [], cannon.fire

    def spy(*change):                  # M6.3: Cannon.fire may change the aim (volley shells)
        shot = fire(*change)
        fired.append((shot.vx, shot.vy))
        return shot
    cannon.fire = spy
    return fired


def swing_to(game, angle):
    """Run frames until the active cannon shows `angle` on the way up. Returns the frames run."""
    side = game.battle.active_side
    for count in range(2 * game.swings[side].period):
        swing = game.swings[side]
        if game.battle.cannons[side].angle == angle and swing.frame < swing.period // 2:
            return count
        game.update()
    raise AssertionError(f"the barrel never showed {angle} degrees")


def set_power(game, power):
    cannon = game.battle.cannons[game.battle.active_side]
    while cannon.power != power:
        game.handle_key(battle_key(game, "more" if cannon.power < power else "less"), 0)


def wait_for_left(game):
    """Run frames until it is LEFT's turn again and LEFT may act (or the match is over)."""
    for _ in range(3000):
        if game.state == "result" or (game.battle.active_side == "left" and not game.controls_locked()):
            return
        game.update()
    raise AssertionError("LEFT's turn never came back")


@unittest.skipIf(pygame is None, "Pygame is not installed")
class ReflexAimTestCase(test_main.MainTestCase):
    def start(self, left, right, aim="reflex"):
        """Two players with the chosen Aim mode and the default cover on both sides."""
        self.pick_teams(left, right)
        self.click(self.game.aim_buttons[aim].rect)
        self.click(self.game.start_button.rect)
        self.click(self.game.confirm_button.rect)
        self.click(self.game.confirm_button.rect)
        self.assertEqual((self.game.state, self.game.aim_mode), ("battle", aim))

    def start_vs_ai(self, left, aim="reflex"):
        self.click(self.game.size_buttons[len(left) - 1].rect)
        for role in left:
            self.click(self.game.card_rects[("left", role)])
        self.click(self.game.aim_buttons[aim].rect)
        self.click(self.game.start_button.rect)
        self.click(self.game.confirm_button.rect)
        self.assertEqual((self.game.state, self.game.aim_mode), ("battle", aim))

    def left_cannon(self):
        return self.game.battle.cannons["left"]


class AimChoiceTest(ReflexAimTestCase):
    def test_classic_aim_is_the_default_and_the_aim_buttons_switch_modes(self):
        self.assertEqual(main.TeamSelection().aim_mode, "classic")
        self.assertTrue(self.game.aim_buttons["classic"].chosen)
        self.click(self.game.aim_buttons["reflex"].rect)
        self.assertEqual(self.game.selection.aim_mode, "reflex")
        self.assertEqual([b.chosen for b in self.game.aim_buttons.values()], [False, True])
        self.assertIn("swings", self.game.message)
        self.assertIn("ATTACK or SPACE", self.game.message)
        self.click(self.game.aim_buttons["classic"].rect)
        self.assertEqual(self.game.selection.aim_mode, "classic")
        self.assertIn("arrow keys", self.game.message)
        with self.assertRaises(ValueError):
            self.game.selection.set_aim_mode("lucky")

    def test_the_aim_buttons_fit_on_the_selection_screen_without_overlapping(self):
        screen = pygame.Rect(0, 0, main.WINDOW_WIDTH, main.WINDOW_HEIGHT)
        others = ([b.rect for b in self.game.mode_buttons.values()]
                  + [b.rect for b in self.game.difficulty_buttons.values()]
                  + [b.rect for b in self.game.size_buttons] + [self.game.start_button.rect]
                  + list(self.game.card_rects.values()))
        for button in self.game.aim_buttons.values():
            self.assertTrue(screen.contains(button.rect))
            self.assertEqual(button.rect.collidelist(others), -1, button.label)
            self.assertLess(button.rect.bottom, 180)            # above the team titles
        self.game.draw()                                        # the screen draws with them

    def test_the_mode_is_kept_for_a_rematch_and_can_be_switched_after_change_teams(self):
        self.start([Knight], [Archer])
        restart_with_r(self.game)
        self.assertEqual(self.game.aim_mode, "reflex")
        test_main.end_match_now(self)
        self.click(self.game.rematch_button.rect)
        self.assertEqual(self.game.aim_mode, "reflex")
        test_main.end_match_now(self)
        self.click(self.game.change_teams_button.rect)
        self.assertEqual((self.game.state, self.game.selection.aim_mode), ("select", "reflex"))
        self.click(self.game.aim_buttons["classic"].rect)        # switch, and play on with the same teams
        self.click(self.game.start_button.rect)
        self.click(self.game.confirm_button.rect)
        self.click(self.game.confirm_button.rect)
        self.assertEqual((self.game.state, self.game.aim_mode), ("battle", "classic"))
        before = self.left_cannon().angle
        frames(self.game, 100)
        self.assertEqual(self.left_cannon().angle, before)      # Classic again: nothing swings


class SwingInBattleTest(ReflexAimTestCase):
    def test_the_active_cannon_swings_20_to_75_and_back_every_180_frames(self):
        self.start([Knight], [Archer])
        swing, cannon = self.game.swings["left"], self.left_cannon()
        first = swing.frame
        seen = []
        for _ in range(180):
            self.assertEqual(cannon.angle, expected_angle(swing.frame))   # the barrel shows the swing
            seen.append(cannon.angle)
            self.game.update()
        self.assertEqual((min(seen), max(seen)), (20, 75))
        self.assertEqual(swing.frame, first)                    # one full period later: the same place
        self.assertLessEqual(max(abs(b - a) for a, b in zip(seen, seen[1:])), 1)   # no jumps
        self.assertTrue(self.game.aim_swings())

    def test_a_new_match_starts_the_swing_at_the_low_limit(self):
        self.pick_teams([Knight], [Archer])
        self.click(self.game.aim_buttons["reflex"].rect)
        self.click(self.game.start_button.rect)
        self.click(self.game.confirm_button.rect)
        self.game.handle_click(self.game.confirm_button.rect.center)     # the battle starts ...
        self.assertEqual(self.left_cannon().angle, 20)                  # ... at the bottom of the swing
        self.assertEqual(self.game.battle.cannons["right"].angle, 20)   # both people's cannons
        self.game.update()
        self.assertEqual((self.game.swings["left"].frame, self.game.swings["right"].frame), (1, 0))

    def test_only_the_team_whose_turn_it_is_swings(self):
        self.start([Knight], [Archer])
        right = self.game.battle.cannons["right"]
        frames(self.game, 50)
        self.assertEqual((right.angle, self.game.swings["right"].frame), (20, 0))


class CaptureTest(ReflexAimTestCase):
    def test_space_locks_the_angle_shown_on_the_frame_it_is_pressed(self):
        for wait in (0, 1, 17, 44, 45, 88, 89, 90, 91, 133, 178, 179, 250):
            with self.subTest(wait=wait):
                self.game = main.Game(self.screen)
                self.start([Knight], [Archer])
                frames(self.game, wait)
                self.game.draw()                                 # what the player sees ...
                shown = self.left_cannon().angle
                self.assertEqual(self.game.aim_values()[0], f"{shown}°")    # M6.2: was aim_text()
                frame = self.game.swings["left"].frame
                self.game.handle_key(battle_key(self.game, "fire"), 0)          # ... is what SPACE locks
                shot = self.game.cannon_run.shot
                self.assertEqual((shot.angle, shot.power), (shown, 50))
                self.assertEqual(shown, expected_angle(frame))
                if expected_angle(frame + 1) != shown:          # not the angle of the next frame
                    self.assertNotEqual(shot.angle, expected_angle(frame + 1))

    def test_the_attack_button_locks_the_angle_the_same_way(self):
        self.start([Knight], [Archer])
        frames(self.game, 30)
        shown = self.left_cannon().angle
        self.game.handle_click(self.game.action_buttons["attack"].rect.center)
        self.assertEqual((self.game.cannon_run.state, self.game.cannon_run.shot.angle), (RUN_TO_CANNON, shown))

    def test_the_shot_leaves_the_cannon_once_at_the_locked_angle(self):
        self.start([Knight], [Archer])
        events = record_events(self.game)
        fired = record_launches(self.left_cannon())
        frames(self.game, 61)
        locked = self.left_cannon().angle
        self.game.handle_key(battle_key(self.game, "fire"), 0)
        frame = self.game.swings["left"].frame
        run_to_cannon(self.game)                                 # 20 frames later it is fired ...
        self.assertEqual(len(fired), 1)
        x, y = CANNON_PIVOT["left"]
        same = Projectile(x, y, locked, 50, "left")
        self.assertEqual(fired[0], (same.vx, same.vy))   # ... with the locked angle exactly
        self.assertEqual(round(math.degrees(math.atan2(-fired[0][1], fired[0][0])), 9), locked)
        finish_shot(self.game)
        self.assertEqual(len(fired), 1)                          # once
        self.assertEqual(sum(e["type"] == "fire" for e in events), 1)
        self.assertEqual((self.left_cannon().angle, self.game.swings["left"].frame), (locked, frame))

    def test_the_locked_angle_is_shown_in_the_message_and_the_log(self):
        self.start([Knight], [Archer])
        set_power(self.game, 60)
        frames(self.game, 40)
        locked = self.left_cannon().angle
        self.game.handle_key(battle_key(self.game, "fire"), 0)
        self.assertIn(f"Angle locked at {locked}°", self.game.message)
        self.assertIn(f"LEFT locked the angle at {locked}° (power 60).", self.game.log)
        self.game.update()
        self.assertEqual(self.game.cannon_label(self.left_cannon()), f"{locked}° / 60")   # still under the cannon
        run_to_cannon(self.game)
        self.assertEqual(self.game.aim_values()[0], f"{locked}°")   # the panel keeps it while the shot flies
        self.assertEqual(self.game.aim_status(), f"REFLEX · LOCKED {locked}°")   # M6.2

    def test_power_shot_also_locks_the_swinging_angle(self):
        self.start([Archer], [Knight])
        frames(self.game, 25)
        shown = self.left_cannon().angle
        self.game.handle_click(self.game.action_buttons["special"].rect.center)
        self.assertEqual((self.game.cannon_run.shot.action, self.game.cannon_run.shot.angle), ("special", shown))


class PowerAndKeysTest(ReflexAimTestCase):
    def test_power_is_still_set_with_the_arrow_keys_while_the_barrel_swings(self):
        self.start([Knight], [Archer])
        cannon, shift = self.left_cannon(), test_main.SHIFT
        angles = []
        for name, mods in (("more", 0), ("more", shift), ("less", 0), ("more", 0)):   # the team's power keys
            self.game.handle_key(battle_key(self.game, name), mods)
            angles.append(cannon.angle)
            frames(self.game, 10)
        self.assertEqual(cannon.power, 50 + 1 + 5 - 1 + 1)
        self.assertEqual(len(set(angles)), 4)                    # the swing went on meanwhile
        self.game.handle_key(battle_key(self.game, "fire"), 0)
        self.assertEqual(self.game.cannon_run.shot.power, 56)

    def test_up_and_down_do_not_move_the_swinging_barrel_and_say_why(self):
        self.start([Knight], [Archer])
        frames(self.game, 20)
        angle = self.left_cannon().angle
        for name, mods in (("up", 0), ("down", test_main.SHIFT)):     # the team's angle keys
            self.game.handle_key(battle_key(self.game, name), mods)
            self.assertEqual(self.left_cannon().angle, angle)
        self.assertIn("swings by itself", self.game.message)


class TwoPlayerReflexTest(ReflexAimTestCase):
    def test_left_and_right_each_swing_and_lock_their_own_cannon(self):
        self.start([Knight], [Archer])
        battle = self.game.battle
        fired = {side: record_launches(battle.cannons[side]) for side in ("left", "right")}
        frames(self.game, 33)
        left_locked = self.left_cannon().angle
        left_frame = self.game.swings["left"].frame
        self.game.handle_key(battle_key(self.game, "fire"), 0)
        self.game.handle_event(pygame.event.Event(pygame.KEYUP, key=battle_key(self.game, "fire")))   # let go of SPACE
        finish_shot(self.game)
        self.assertEqual(battle.active_side, "right")
        right_angles = []
        for _ in range(70):                              # RIGHT's turn: its barrel swings, LEFT's waits
            self.game.update()
            right_angles.append(battle.cannons["right"].angle)
            self.assertEqual(self.left_cannon().angle, left_locked)
        self.assertEqual(right_angles[0], expected_angle(1))
        self.assertGreater(len(set(right_angles)), 30)
        right_locked = battle.cannons["right"].angle
        self.game.handle_key(battle_key(self.game, "fire"), 0)
        self.assertEqual(self.game.cannon_run.shot.side, "right")
        run_to_cannon(self.game)
        vx, vy = fired["right"][0]
        self.assertLess(vx, 0)                           # RIGHT fires toward LEFT ...
        self.assertEqual(round(math.degrees(math.atan2(-vy, -vx)), 9),
                         right_locked)                   # ... at its own locked angle
        finish_shot(self.game)
        self.assertEqual(battle.active_side, "left")
        self.assertEqual(self.game.swings["left"].frame, left_frame)   # LEFT goes on from where it stopped
        self.game.update()
        self.assertLessEqual(abs(self.left_cannon().angle - left_locked), 1)    # no jump
        self.assertEqual([len(fired["left"]), len(fired["right"])], [1, 1])

    def test_a_whole_two_player_match_plays_to_the_result(self):
        self.start([Knight], [Archer])
        for _ in range(40):
            if self.game.state == "result":
                break
            set_power(self.game, FRONT_CHARACTER[1])
            swing_to(self.game, FRONT_CHARACTER[0])
            self.game.handle_event(pygame.event.Event(pygame.KEYUP, key=battle_key(self.game, "fire")))
            self.game.handle_key(battle_key(self.game, "fire"), 0)
            finish_shot(self.game)
        self.assertEqual((self.game.state, self.game.battle.winner), ("result", "left"))


class LockTest(ReflexAimTestCase):
    def test_the_swing_stops_while_the_controls_are_locked(self):
        self.start([Knight], [Archer])
        frames(self.game, 52)
        self.game.handle_key(battle_key(self.game, "fire"), 0)
        cannon, swing = self.left_cannon(), self.game.swings["left"]
        locked = (cannon.angle, swing.frame)
        phases = set()
        while self.game.cannon_run.is_busy() or self.game.battle.projectile is not None:
            self.assertTrue(self.game.controls_locked())
            self.assertFalse(self.game.aim_swings())
            phases.add(self.game.phase_text())
            self.game.update()
            self.assertEqual((cannon.angle, swing.frame), locked)
            self.assertEqual(self.game.swings["right"].frame, 0)      # RIGHT waits for the runner too
        self.assertTrue({"running to the cannon", "shot in the air"} <= phases)
        self.assertEqual((cannon.angle, swing.frame), locked)

    def test_nothing_swings_after_the_game_is_over(self):
        self.start([Knight], [Archer])
        frames(self.game, 10)
        test_main.end_match_now(self)
        angles = {side: c.angle for side, c in self.game.battle.cannons.items()}
        frames(self.game, 60)
        self.assertEqual({side: c.angle for side, c in self.game.battle.cannons.items()}, angles)
        self.game.draw()


class RematchTest(ReflexAimTestCase):
    def test_r_restarts_both_swings_and_right_moves_first(self):
        self.start([Knight], [Archer])
        frames(self.game, 70)
        restart_with_r(self.game)
        battle = self.game.battle
        self.assertEqual((battle.first_side, battle.active_side), ("right", "right"))
        self.assertEqual([self.game.swings[s].frame for s in ("left", "right")], [0, 0])
        self.assertEqual([battle.cannons[s].angle for s in ("left", "right")], [20, 20])
        frames(self.game, 30)
        self.assertEqual(battle.cannons["right"].angle, expected_angle(30))   # RIGHT swings first now
        self.assertEqual(self.left_cannon().angle, 20)

    def test_r_during_the_run_fires_nothing_later(self):
        self.start([Knight], [Archer])
        events = record_events(self.game)
        frames(self.game, 40)
        self.game.handle_key(battle_key(self.game, "fire"), 0)
        frames(self.game, 5)
        restart_with_r(self.game)
        frames(self.game, 60)
        self.assertFalse(any(e["type"] in ("action", "fire") for e in events))
        self.assertTrue(self.game.aim_swings())                  # the new match swings again


class ComputerTest(ReflexAimTestCase):
    def play_three_turns(self, aim):
        """Player vs the computer (seed 4): the LEFT Knight defends, rallies and defends; returns the
        computer's three plans and LEFT's swing frames during the computer's turns."""
        self.game = main.Game(self.screen, ai_seed=4)
        self.start_vs_ai([Knight], aim=aim)
        plans, choose = [], self.game.ai.choose

        def spy(battle):
            plan = choose(battle)
            plans.append(None if plan is None else (plan.actor_index, plan.action, plan.angle, plan.power))
            return plan
        self.game.ai.choose = spy
        right = self.game.battle.cannons["right"]
        for action in ("defend", "special", "defend"):
            frames(self.game, 23)
            self.game.handle_click(self.game.action_buttons[action].rect.center)
            self.assertEqual(self.game.battle.active_side, "right")
            left_angle = self.left_cannon().angle
            aimed = None
            while self.game.battle.active_side == "right" and self.game.state == "battle":
                self.assertFalse(self.game.aim_swings())
                self.assertEqual(self.left_cannon().angle, left_angle)   # LEFT waits
                self.game.update()
                if self.game.cannon_run.is_busy() and aimed is None:
                    aimed = (right.angle, right.power)
                if aimed is not None and self.game.battle.active_side == "right":
                    self.assertEqual((right.angle, right.power), aimed)   # its own aim, never swung
            wait_for_left(self.game)
        self.assertEqual(self.game.swings["right"].frame, 0)
        return plans

    def test_the_computer_plays_exactly_as_in_classic_aim(self):
        classic = self.play_three_turns("classic")
        reflex = self.play_three_turns("reflex")
        self.assertEqual(len(reflex), 3)
        self.assertEqual(reflex, classic)                        # the same choices and the same aims

    def test_only_the_person_s_cannon_swings_against_the_computer(self):
        self.game = main.Game(self.screen, ai_seed=4)
        self.start_vs_ai([Knight])
        right = self.game.battle.cannons["right"]
        self.assertEqual(right.angle, 45)                        # the computer's cannon is left alone
        frames(self.game, 40)
        self.assertEqual((right.angle, self.game.swings["right"].frame), (45, 0))
        self.assertNotEqual(self.left_cannon().angle, 20)
        self.click(self.game.action_buttons["defend"].rect)     # now the computer's turn ...
        for _ in range(main.AI_DELAY_FRAMES - 2):                # ... and while it thinks
            self.assertTrue(self.game.ai_thinking())
            self.assertFalse(self.game.aim_swings())
            self.game.update()
            self.assertEqual((right.angle, self.game.swings["right"].frame), (45, 0))


class ClassicAimRegressionTest(ReflexAimTestCase):
    def test_classic_aim_never_moves_the_barrel_by_itself(self):
        self.start([Knight], [Archer], aim="classic")
        cannon = self.left_cannon()
        frames(self.game, 200)
        self.assertEqual((cannon.angle, cannon.power), (45, 50))
        self.assertEqual([self.game.swings[s].frame for s in ("left", "right")], [0, 0])
        self.assertFalse(self.game.aim_swings())
        self.game.handle_key(battle_key(self.game, "up"), 0)
        self.game.handle_key(battle_key(self.game, "down"), test_main.SHIFT)
        self.assertEqual(cannon.angle, 41)

    def test_classic_texts_are_unchanged(self):
        self.start([Knight], [Archer], aim="classic")
        self.assertEqual(self.game.message, "LEFT team moves first. Choose a character, aim, then choose an action.")
        self.assertIn("drag", self.game.aim_labels()[1])          # M6.2: the power label names the slider
        self.assertEqual(self.game.aim_labels()[0], "ANGLE · W/S")     # two players: LEFT's keys (M6.2 rework)
        self.assertTrue(self.game.hud_turn_text().endswith("aim and act"))
        test_main.aim(self.game, 50, 60)
        self.game.handle_key(battle_key(self.game, "fire"), 0)
        self.assertEqual(self.game.message, "LEFT Knight runs to the cannon...")
        self.assertFalse(any("locked" in line for line in self.game.log))
        self.assertEqual((self.game.cannon_run.shot.angle, self.game.cannon_run.shot.power), (50, 60))


class SameRulesTest(ReflexAimTestCase):
    def play_one_shot(self, aim):
        """LEFT Knight fires at 45 degrees, power 83 (over the cover onto the RIGHT Archer)."""
        self.game = main.Game(self.screen)
        self.start([Knight, Engineer], [Archer, Knight], aim=aim)
        set_power(self.game, 83)
        if aim == "reflex":
            swing_to(self.game, 45)
        else:
            test_main.aim(self.game, 45, 83)
        events = record_events(self.game)
        self.game.handle_key(battle_key(self.game, "fire"), 0)
        finish_shot(self.game)
        battle = self.game.battle
        state = {
            "hp": {s: [c.hp for c in battle.teams[s].characters] for s in ("left", "right")},
            "exp": {s: [c.exp for c in battle.teams[s].characters] for s in ("left", "right")},
            "blocks": {s: [b.hp for b in battle.castles[s].blocks] for s in ("left", "right")},
            "turn": (battle.active_side, battle.round_number),
        }
        return events, state

    def test_damage_hp_collision_and_turn_order_are_the_same_as_classic(self):
        classic_events, classic_state = self.play_one_shot("classic")
        reflex_events, reflex_state = self.play_one_shot("reflex")
        self.assertEqual(reflex_events, classic_events)          # the same hit, explosion and EXP
        self.assertEqual(reflex_state, classic_state)
        self.assertEqual(reflex_state["turn"], ("right", 1))
        self.assertLess(reflex_state["hp"]["right"][0], Archer.BASE_HP)   # it really hit the Archer


class ReflexInterfaceTest(ReflexAimTestCase):
    def test_the_panel_and_banner_explain_the_timing(self):
        self.start([Knight], [Archer])
        self.assertIn("ATTACK or F", self.game.message)               # two players: LEFT fires with F
        self.assertIn("lock", self.game.message)
        self.assertIn("locks the swinging angle", self.game.action_help("attack"))   # M6.2: ATTACK's help
        self.assertTrue(self.game.hud_turn_text().endswith("time your shot"))

    def test_the_hints_fit_the_panel_for_every_role(self):
        # M6.2: every action's one help line fits two rows of HINT_WIDTH.
        self.start([Knight, Archer, Engineer], [Knight, Archer, Engineer])
        for index in range(3):
            for blocked in (False, True):
                with self.subTest(index=index, blocked=blocked):
                    character = self.game.battle.teams["left"].characters[index]
                    if blocked:
                        character.start_cooldown()
                    self.game.select_actor(index)
                    for action in ("attack", "defend", "special"):
                        hints = main.wrap_text(self.game.action_help(action), self.game.tiny_font, main.HINT_WIDTH)
                        self.assertLessEqual(len(hints), 2, hints)

    def test_the_swing_range_is_drawn_only_in_reflex_aim(self):
        x, y = CANNON_PIVOT["left"]
        far = (round(x + main.SWING_MARK_RADIUS * math.cos(math.radians(70))),
               round(y - main.SWING_MARK_RADIUS * math.sin(math.radians(70))))
        for aim, marked in (("reflex", True), ("classic", False)):
            with self.subTest(aim=aim):
                self.game = main.Game(self.screen)
                self.start([Knight], [Archer], aim=aim)
                restart_with_r(self.game)
                restart_with_r(self.game)              # LEFT first again, barrel at 20 (or 45)
                self.game.draw()
                pixel = tuple(self.screen.get_at(far))[:3]
                self.assertEqual(pixel == main.AIM_COLOR, marked)

    def test_every_phase_draws_in_reflex_aim(self):
        self.start([Knight], [Archer])
        frames(self.game, 15)
        self.game.draw()
        self.game.handle_key(battle_key(self.game, "fire"), 0)
        for _ in range(400):
            self.game.update()
            self.game.draw()
            if self.game.battle.active_side == "right" and not self.game.controls_locked():
                break
        test_main.end_match_now(self)
        self.game.draw()


if __name__ == "__main__":
    unittest.main()
