"""Castle Siege - the Pygame interface (the only module that uses Pygame).

Screens (Game.state):
  "select"  team selection: mode (Player vs AI or two players), AI level, team size
            (1v1, 2v2 or 3v3) and the characters
  "cover"   cover placement (M3.4-B): one team at a time clicks its 8 cover slots to
            place up to 6 blocks (Game.placing says which team)
  "battle"  the battlefield: pick a character, aim the cannon, pick an action
  "result"  the battlefield with the winner (or DRAW), plus Rematch / Change teams buttons
Each team has its cover blocks in front of its characters and one cannon in front of
the cover.

Setup flow:  Player vs AI:  select -> LEFT cover -> battle (the computer places RIGHT's cover)
             Two players:   select -> LEFT cover -> RIGHT cover -> battle
Back on a cover screen returns to the previous step; nothing chosen is lost.

Player vs AI: the human plays LEFT and the computer (ai.py) picks, places and plays RIGHT.
Two players: both teams play on this computer and take turns ("hot seat").
All game rules live in battle.py, castle.py and characters.py: this file reads
the mouse and keyboard, calls Battle methods and draws what the Battle reports.

An attack (ATTACK or Power Shot, by a person or the computer) is not fired at once (M3.4-C):
the character first runs to its team's cannon (animation.py), the shot is fired with
Battle.perform_action() when it gets there, and it runs back while the shot flies. Combat
input and the computer wait until it is back. Defend, Rally and Repair still happen at once.

Sound (M4.2-A, sound.py): effects made in code play for Battle events (a shot, an explosion,
cover hit or destroyed, a level-up, the result). M turns the sound off and on; without an audio
device the game is silent and works the same.

Run from the project folder:   python main.py
"""
import math

import pygame

from ai import DIFFICULTY_SETTINGS, AIController, aim_cannon
from animation import FIRE, FIRE_FRAMES, RUN_TO_CANNON, CannonRun, PendingShot, fires_the_cannon
from battle import (BLAST_RADIUS, CHARACTER_HEIGHT, FIELD_WIDTH, MAX_POWER, MAX_TEAM_SIZE, MIN_POWER,
                    ROUND_LIMIT, SLOT_X, Battle, Cannon, direction, other_side)
from castle import (BLOCK_SIZE, COLUMN_X, DEFAULT_LAYOUT, GROUND_Y, MAX_BLOCKS, SLOT_COUNT,
                    layout_problem, place_block, remove_block, slot_position)
from characters import ARCHETYPES, MAX_LEVEL, Archer
from drawing import (ACTIVE_RING_COLOR, AIM_COLOR, BUTTON_OFF, CANNON_COLOR, CLOSED_SLOT_COLOR,
                     COOLDOWN_COLOR, DAMAGE_COLOR, DEFEATED_COLOR, DEFEND_COLOR, DIM_TEXT, DRAW_COLOR,
                     FLASH_COLOR, FLASH_EDGE, GROUND_COLOR, GUARD_COLOR, LABEL_COLORS, LIGHT_TEXT,
                     MENU_COLOR, OPEN_SLOT_COLOR, PANEL_COLOR, POWER_SHOT_COLOR, READY_COLOR, SHOT_COLOR,
                     SKY_COLOR, TEAM_COLORS, TEXT_COLOR, TRAIL_COLOR, WOOD, Button, block_color, draw_block,
                     draw_figure, draw_firing_figure, draw_outlined_text, draw_rubble_outline,
                     draw_running_figure, draw_text, hp_bar_color, hp_bar_width, wrap_text)
from drawing import EMBLEM_COLOR, EMBLEM_Y, draw_badge, draw_emblem, draw_plate, make_background   # M4.2-A
from sound import BUFFER, SAMPLE_RATE, SoundBoard

WINDOW_WIDTH = FIELD_WIDTH        # 1280
WINDOW_HEIGHT = 720
FPS = 60
AI_DELAY_FRAMES = 40              # the computer waits this long (2/3 s) before it acts
EXPLOSION_FRAMES = 20             # how long an explosion stays on screen
EXPLOSION_ALPHA = 160             # explosions are see-through (0-255), so the target stays visible
FLOAT_FRAMES = 60                 # a floating damage number stays 1 s, rising slowly
TRAIL_LENGTH = 12                 # dots behind a flying shot
LOG_LINES = 6                     # combat-log lines shown at once
PANEL_TOP = 580                   # the control panel fills the bottom of the window
COVER_HELP_TOP = 122              # the placement screen's instructions start at this y ...
COVER_HELP_STEP = 26              # ... one line every 26 px


# ----- small helpers -------------------------------------------------------------

def slot_rect(side, slot):
    """The clickable square of cover slot `slot` (0-7) of `side`: exactly where its block stands."""
    return pygame.Rect(slot_position(side, slot), (BLOCK_SIZE, BLOCK_SIZE))


def guard_badge_rect(side):
    """Where the GUARDED badge of `side`'s cover is drawn: just above the higher cover row,
    centred over the four slot columns, clear of the characters and their HP bars, the
    cannon and the HUD. The two sides are mirror images."""
    center_x = COLUMN_X["left"][0] + 2 * BLOCK_SIZE                 # 236: the middle of the columns
    if side == "right":
        center_x = WINDOW_WIDTH - center_x                          # 1044
    badge = pygame.Rect(0, 0, 84, 20)
    badge.center = (center_x, GROUND_Y - 2 * BLOCK_SIZE - 20)       # y 476: above the raised row
    return badge


def result_banner_rect():
    """The coloured title band of the result overlay: the winner's colour, or DRAW_COLOR."""
    return pygame.Rect(310, 120, 660, 90)


def muzzle_point(cannon):
    """Centre of the muzzle flash: just past the tip of the 24 px barrel, along its angle."""
    radians = math.radians(cannon.angle)
    return (round(cannon.x + direction(cannon.side) * 30 * math.cos(radians)),
            round(cannon.y - 30 * math.sin(radians)))


def describe_event(event):
    """Turn one battle event into combat-log lines (an empty list if it isn't worth logging)."""
    kind = event["type"]
    if kind == "action" and event["action"] != "special":
        verb = "attacks" if event["action"] == "attack" else "defends"
        return [f"{event['side'].upper()} {event['name']} {verb}."]
    if kind == "special":
        return [f"{event['side'].upper()} {event['message']}"]
    if kind == "explosion":
        lines = []
        if event["blocks_hit"]:
            plural = "s" if event["blocks_hit"] != 1 else ""
            lines.append(f"Explosion: {event['blocks_hit']} cover block{plural}, "
                         f"{event['damage']} damage.")
            if event.get("guarded"):
                lines.append("Cover Guard halved the damage to the blocks.")
        target_side = other_side(event["side"]).upper()
        for name in event["covered"]:
            lines.append(f"{target_side} {name} was shielded by cover.")
        for hit in event["characters_hit"]:
            ending = " and is defeated!" if hit["defeated"] else "."
            lines.append(f"{target_side} {hit['name']} takes {hit['damage']} damage{ending}")
        return lines or ["Explosion: nothing was close enough."]
    if kind == "miss":
        return ["The shot flew off the battlefield."]
    if kind == "exp":
        if event["levels"] == 0:
            return [f"{event['name']} gains {event['amount']} EXP."]
        return [f"{event['name']} gains {event['amount']} EXP and levels up!"]
    if kind == "round":
        return [f"--- Round {event['number']} ---"]
    if kind == "invalid":
        return [f"Not allowed: {event['reason']}."]
    if kind == "game_over":
        lines = []
        if event["reason"] == "timeout":
            lines.append("Round limit reached: no team was eliminated.")
        if event["winner"] == "draw":
            return lines + ["It's a draw!"]
        return lines + [f"{event['winner'].upper()} wins!"]
    return []    # "fire" and "turn" are shown by the HUD instead


class TeamSelection:
    """The choices made on the team-selection screen. (No drawing happens here.)

    Each team picks `team_size` different roles. The order of the picks is the
    slot order: the first pick stands at the front, behind the team's cover. Against the
    computer (vs_ai) only the LEFT team is picked here; the AI builds its own.
    """

    def __init__(self):
        self.vs_ai = True               # Player vs AI is the main mode
        self.difficulty = "normal"
        self.team_size = 1
        self.picks = {"left": [], "right": []}

    def set_mode(self, vs_ai):
        self.vs_ai = vs_ai

    def set_team_size(self, size):
        if not 1 <= size <= MAX_TEAM_SIZE:
            raise ValueError(f"team size must be 1 to {MAX_TEAM_SIZE}")
        self.team_size = size
        for picks in self.picks.values():
            del picks[size:]                    # a smaller team keeps its first picks

    def toggle(self, side, role):
        """Add `role` to the team, or remove it if it is already there.

        Returns None, or a message if the pick is refused (the team is full, or it
        is the computer's team). A role can't be picked twice, so there are never duplicates.
        """
        if side == "right" and self.vs_ai:
            return "The computer picks the RIGHT team when the battle starts."
        picks = self.picks[side]
        if role in picks:
            picks.remove(role)
            return None
        if len(picks) >= self.team_size:
            return (f"{side.upper()} team already has {self.team_size} - "
                    f"click a chosen character to remove it first.")
        picks.append(role)
        return None

    def is_complete(self):
        """True when every team picked here has exactly team_size characters."""
        sides = ["left"] if self.vs_ai else ["left", "right"]
        return all(len(self.picks[side]) == self.team_size for side in sides)

    def roster(self):
        """The picks in the form Battle(roster=...) expects."""
        return {side: list(picks) for side, picks in self.picks.items()}


class CoverSetup:
    """The cover layouts chosen on the placement screens (no drawing happens here).

    Each side keeps its own layout: a tuple of slot numbers, so the two sides can never
    share one list. Both start as DEFAULT_LAYOUT. Clicks go through castle.place_block()
    and castle.remove_block(), which check with castle.layout_problem(), so a layout
    stays legal and no rule is repeated here. Cover slots never depend on the team size
    or roles (no character stands on one), so the layouts are kept when teams change.
    """

    def __init__(self):
        self.layouts = {"left": DEFAULT_LAYOUT, "right": DEFAULT_LAYOUT}

    def click_slot(self, side, slot):
        """A click on cover slot `slot` of `side`: place a block on an empty slot, or remove
        the block on an occupied one. Returns a short message for the status line."""
        layout = self.layouts[side]
        if slot in layout:
            self.layouts[side], removed = remove_block(layout, slot)
            if len(removed) > 1:
                return ("Block removed, and the raised block on top of it too "
                        "(a raised block needs a block under it).")
            return "Block removed."
        self.layouts[side], problem = place_block(layout, slot)
        if problem is not None:
            return f"No block there: {problem}."
        return "Block placed."


class Game:
    """Connects the mouse, keyboard and screen to the team selection, the cover placement
    and one Battle.

    ai_seed: a number makes the computer's choices (team, cover, moves) repeatable; the
    tests use it. None (the real game) gives a different computer opponent every time.
    """

    def __init__(self, screen, ai_seed=None):
        self.screen = screen
        self.ai_seed = ai_seed
        # Font(None, size) uses Pygame's built-in font. (SysFont scans the system's
        # installed fonts, and on some Windows machines that scan crashes.)
        self.big_font = pygame.font.Font(None, 80)
        self.title_font = pygame.font.Font(None, 54)
        self.font = pygame.font.Font(None, 30)
        self.small_font = pygame.font.Font(None, 24)
        self.tiny_font = pygame.font.Font(None, 19)
        self.banner_font = pygame.font.Font(None, 24)
        self.banner_font.set_bold(True)           # the turn banner stands out from the other HUD text
        self.background = make_background(WINDOW_WIDTH, PANEL_TOP, GROUND_Y)   # M4.2-A: drawn once
        self.running = True
        self.space_released = True    # fire only once per SPACE press (see handle_key)
        self.state = "select"
        self.selection = TeamSelection()
        self.setup = CoverSetup()
        self.placing = "left"         # the team whose cover is being placed (state "cover")
        self.battle = None
        self.ai = None                # the AIController playing RIGHT, or None (two players)
        self.ai_wait = 0              # frames the computer has waited on this turn
        self.cannon_run = CannonRun()  # an attacking character's run to the cannon and back (M3.4-C)
        self.sounds = SoundBoard()     # sound effects (M4.2-A); silent if there is no audio device
        self.standing_blocks = {}      # standing blocks per side, to hear when one is destroyed
        self.selected = {"left": 0, "right": 0}   # slot of the character chosen to act
        self.explosions = []          # each one is [x, y, age in frames]
        self.floaters = []            # floating damage numbers: [x, y, text, colour, age in frames]
        self.trail = []               # the last positions of the flying shot (drawn as dots)
        self.shot_style = "attack"    # "power" while a Power Shot flies (drawn bigger and orange)
        self.log = []                 # combat-log lines, newest last
        self.message = "Click characters to add them to a team (click again to remove)."
        self.make_buttons()
        self.refresh_buttons()

    def make_buttons(self):
        # Team selection screen.
        self.mode_buttons = {"ai": Button(290, 72, 180, 38, "Player vs AI"),
                             "pvp": Button(480, 72, 180, 38, "Two players")}
        self.difficulty_buttons = {level: Button(800 + i * 110, 72, 100, 38, level.capitalize())
                                   for i, level in enumerate(DIFFICULTY_SETTINGS)}
        self.size_buttons = [Button(470 + i * 120, 120, 105, 40, f"{n} v {n}")
                             for i, n in enumerate(range(1, MAX_TEAM_SIZE + 1))]
        self.card_rects = {}
        for side, first_x in (("left", 60), ("right", 660)):
            for i, role in enumerate(ARCHETYPES):
                self.card_rects[(side, role)] = pygame.Rect(first_x + i * 190, 210, 170, 265)
        self.start_button = Button(515, 515, 250, 56, "PLACE COVER")
        # Cover placement screen.
        self.back_button = Button(430, PANEL_TOP + 42, 190, 46, "Back")
        self.confirm_button = Button(660, PANEL_TOP + 42, 190, 46, "Confirm")
        # Battle screen.
        self.action_buttons = {
            "attack": Button(450, PANEL_TOP + 12, 120, 42, "ATTACK"),
            "defend": Button(580, PANEL_TOP + 12, 120, 42, "DEFEND"),
            "special": Button(710, PANEL_TOP + 12, 120, 42, "SPECIAL"),
        }
        # Result overlay.
        self.rematch_button = Button(430, 300, 200, 46, "Rematch")
        self.change_teams_button = Button(650, 300, 200, 46, "Change teams")

    # ----- starting matches ------------------------------------------------------

    def start_battle(self, roster, layouts, ai=None):
        """Start a match. `ai` is the AIController playing RIGHT, or None if two people play."""
        self.battle = Battle(roster=roster, layouts=layouts)
        self.ai = ai
        self.begin_match()
        if ai is not None:
            self.log.append(f"AI ({ai.difficulty.capitalize()}) placed {len(layouts['right'])} cover blocks.")

    def rematch(self):
        """Play again with the same teams and cover (the Rematch button or R). The side that
        moves first swaps every time: LEFT, then RIGHT, then LEFT... A new choice of teams
        starts with LEFT again."""
        self.battle.reset(first_side=other_side(self.battle.first_side))
        if self.ai is not None:
            self.ai.new_match()
        self.begin_match()

    def begin_match(self):
        self.state = "battle"
        self.cannon_run.cancel()          # a rematch (R) mid-run: nothing is fired later
        self.sounds.stop()                # nothing from the last match keeps playing
        self.standing_blocks = {side: len(castle.alive_blocks()) for side, castle in self.battle.castles.items()}
        self.selected = {"left": 0, "right": 0}
        self.ai_wait = 0
        self.explosions = []
        self.floaters = []
        self.trail = []
        first = f"{self.battle.first_side.upper()} team moves first."
        self.log = ["--- Round 1 ---", first]
        if self.ai is not None and self.battle.first_side == self.ai.side:
            self.message = f"The computer ({self.ai.side.upper()}) moves first."   # nothing to do yet
        else:
            self.message = first + " Choose a character, aim, then choose an action."
        self.refresh_buttons()

    def try_start(self):
        """PLACE COVER (or Enter) on the selection screen: go on to the LEFT cover screen."""
        if not self.selection.is_complete():
            size = self.selection.team_size
            self.message = f"Each team needs exactly {size} character{'s' if size > 1 else ''}."
        else:
            self.begin_cover("left")

    # ----- cover placement -----------------------------------------------------------

    def begin_cover(self, side):
        self.state = "cover"
        self.placing = side
        self.message = f"{side.upper()} team: click the slots to place or remove blocks, then press Confirm."

    def click_cover(self, pos):
        for slot in range(SLOT_COUNT):
            if slot_rect(self.placing, slot).collidepoint(pos):
                self.message = self.setup.click_slot(self.placing, slot)
                return
        if self.back_button.is_clicked(pos):
            self.back_from_cover()
        elif self.confirm_button.is_clicked(pos):
            self.confirm_cover()

    def back_from_cover(self):
        """Back: RIGHT's cover screen returns to LEFT's, LEFT's to team selection. Nothing is lost."""
        if self.placing == "right":
            self.begin_cover("left")
        else:
            self.state = "select"
            self.message = "Change the teams, then press PLACE COVER."

    def confirm_cover(self):
        """Confirm: RIGHT places its cover next (two players), or the battle starts."""
        layout = self.setup.layouts[self.placing]
        problem = layout_problem(layout)
        if problem is not None:        # clicks always keep the layout legal; this is a safety net
            self.message = f"This cover can't be used: {problem}."
            return
        if self.placing == "left" and not self.selection.vs_ai:
            self.begin_cover("right")
        elif self.selection.vs_ai:
            ai = AIController("right", self.selection.difficulty, seed=self.ai_seed)
            roster = {"left": list(self.selection.picks["left"]),
                      "right": ai.pick_team(self.selection.team_size)}
            self.start_battle(roster, {"left": layout, "right": ai.choose_layout()}, ai)
        else:
            self.start_battle(self.selection.roster(), dict(self.setup.layouts))

    def is_ai_turn(self):
        """True while it is the computer's turn to act (it acts by itself in update())."""
        return (self.state == "battle" and self.ai is not None
                and self.battle.active_side == self.ai.side and self.battle.can_fire())

    def controls_locked(self):
        """True while nobody may aim or act in the battle: a character is running to or from
        the cannon (M3.4-C), a shot is flying, the game is over, or it is the computer's turn."""
        return (self.state != "battle" or self.cannon_run.is_busy() or not self.battle.can_fire()
                or self.is_ai_turn())

    # ----- the character who acts --------------------------------------------------

    def selected_index(self):
        """Slot of the active team's chosen character (moved to a living one if needed)."""
        side = self.battle.active_side
        team = self.battle.teams[side]
        if not team.characters[self.selected[side]].is_alive():
            for index, character in enumerate(team.characters):
                if character.is_alive():
                    self.selected[side] = index
                    break
        return self.selected[side]

    def selected_character(self):
        if self.battle is None:
            return None
        return self.battle.teams[self.battle.active_side].characters[self.selected_index()]

    def select_actor(self, index):
        """Choose who acts. Only living characters of the team whose turn it is can be chosen."""
        team = self.battle.teams[self.battle.active_side]
        if not 0 <= index < len(team.characters):
            return
        character = team.characters[index]
        if not character.is_alive():
            self.message = f"{character.name} has been defeated and can't act."
            return
        self.selected[self.battle.active_side] = index
        self.message = f"{character.name} is ready. Aim, then choose an action."

    def do_action(self, action):
        """Ask the Battle to carry out an action for the chosen character.

        ATTACK and Power Shot first send the character to the cannon (start_cannon_run): the
        shot is fired when it gets there. Defend, Rally and Repair happen at once."""
        if self.cannon_run.is_busy():
            return                        # one action per turn: a character is already on its way
        index = self.selected_index()
        reason = self.battle.why_not_allowed(index, action)
        if reason is not None:
            self.message = reason
            return
        side = self.battle.active_side
        if fires_the_cannon(self.battle.teams[side].characters[index], action):
            cannon = self.battle.cannons[side]
            self.start_cannon_run(PendingShot(side, index, action, cannon.angle, cannon.power))
        else:
            self.battle.perform_action(index, action)

    # ----- the run to the cannon (M3.4-C) -------------------------------------------

    def start_cannon_run(self, shot):
        """Send the character of `shot` (a PendingShot) from its slot to the cannon. The
        controls stay locked until it is back; nothing is fired yet."""
        team = self.battle.teams[shot.side]
        self.cannon_run.start(shot, team.slot_center(shot.actor_index)[0])
        self.message = f"{shot.side.upper()} {team.characters[shot.actor_index].name} runs to the cannon..."

    def update_cannon_run(self):
        """One frame of the run. On the frame the character reaches the cannon, the one real
        shot of this attack is fired (fire_pending_shot)."""
        shot = self.cannon_run.shot
        if not self.battle.teams[shot.side].characters[shot.actor_index].is_alive():
            self.cannon_run.cancel()      # not possible in play, but never leave a ghost runner
            return
        if self.cannon_run.step():
            self.fire_pending_shot(shot)

    def fire_pending_shot(self, shot):
        """Fire the shot the character carried to the cannon, through the Battle like every
        action. The computer's plan is carried out by its AIController (it aims, then calls
        Battle.perform_action); a person's shot uses the aim it had when the action was chosen."""
        if shot.plan is not None:
            fired = self.ai.carry_out(self.battle, shot.plan) is not None
        else:
            aim_cannon(self.battle.cannons[shot.side], shot.angle, shot.power)
            fired = self.battle.perform_action(shot.actor_index, shot.action)
        if not fired:
            self.cannon_run.cancel()      # not possible in play; the log says why it was refused
        self.shot_style = "power" if shot.action == "special" else "attack"   # only how it is drawn

    # ----- input -------------------------------------------------------------------

    def quit(self):
        """Esc or closing the window: stop the main loop, and any run with it."""
        self.cannon_run.cancel()
        self.sounds.stop()
        self.running = False

    def toggle_sound(self):
        """M (on every screen): sound off, or back on."""
        if not self.sounds.available:
            self.message = "No sound: the audio device could not be opened."
            return
        self.sounds.toggle_mute()
        self.message = "Sound off. Press M to turn it back on." if self.sounds.muted else "Sound on."

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.quit()
        elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self.space_released = True
        elif event.type == pygame.KEYDOWN:
            self.handle_key(event.key, event.mod)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.handle_click(event.pos)

    def handle_key(self, key, mods):
        if key == pygame.K_ESCAPE:
            self.quit()
        elif key == pygame.K_m:
            self.toggle_sound()
        elif self.state == "select":
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.try_start()
        elif self.state == "cover":
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm_cover()
            elif key == pygame.K_BACKSPACE:
                self.back_from_cover()
        elif key == pygame.K_r:
            self.rematch()                # also cancels a run (begin_match)
        elif not self.controls_locked():
            self.handle_battle_key(key, mods)
        self.refresh_buttons()

    def handle_battle_key(self, key, mods):
        """Keys during a turn: aim, choose a character (1-3) and SPACE to attack."""
        step = 5 if mods & pygame.KMOD_SHIFT else 1
        cannon = self.battle.cannons[self.battle.active_side]
        if key == pygame.K_UP:
            cannon.adjust_angle(step)
        elif key == pygame.K_DOWN:
            cannon.adjust_angle(-step)
        elif key == pygame.K_RIGHT:
            cannon.adjust_power(step)
        elif key == pygame.K_LEFT:
            cannon.adjust_power(-step)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.select_actor(key - pygame.K_1)
        elif key == pygame.K_SPACE and self.space_released:
            # Holding SPACE produces repeated key presses (key repeat is on for the
            # arrow keys). Requiring a release stops a held SPACE from also acting
            # for the next team as soon as its turn starts.
            self.space_released = False
            self.do_action("attack")

    def handle_click(self, pos):
        self.refresh_buttons()                     # decide using the situation right now
        if self.state == "select":
            self.click_selection(pos)
        elif self.state == "cover":
            self.click_cover(pos)
        elif self.state == "battle":
            self.click_battle(pos)
        elif self.rematch_button.is_clicked(pos):
            self.rematch()
        elif self.change_teams_button.is_clicked(pos):
            self.cannon_run.cancel()      # a character may still be walking back
            self.sounds.stop()
            self.state = "select"
            self.message = "Change the teams, then press PLACE COVER."
        self.refresh_buttons()

    def click_selection(self, pos):
        for mode, button in self.mode_buttons.items():
            if button.is_clicked(pos):
                self.selection.set_mode(vs_ai=(mode == "ai"))
                self.message = ("You play LEFT; the computer picks and plays RIGHT." if mode == "ai"
                                else "Two players: pick both teams, then take turns.")
        for level, button in self.difficulty_buttons.items():
            if button.is_clicked(pos):
                self.selection.difficulty = level
                self.message = f"Computer level: {level.capitalize()}."
        for size, button in enumerate(self.size_buttons, start=1):
            if button.is_clicked(pos):
                self.selection.set_team_size(size)
                self.message = f"{size} v {size}: each team picks {size} different character(s)."
        for (side, role), rect in self.card_rects.items():
            if rect.collidepoint(pos):
                refusal = self.selection.toggle(side, role)
                if refusal:
                    self.message = refusal
        if self.start_button.rect.collidepoint(pos):
            self.try_start()                       # explains what is missing if incomplete

    def click_battle(self, pos):
        if self.cannon_run.is_busy():
            return                                 # wait until the character is back in its slot
        if self.is_ai_turn():
            self.message = "The computer is playing the RIGHT team's turn."
            return
        for action, button in self.action_buttons.items():
            if button.is_clicked(pos):
                self.do_action(action)
                return
        if not self.battle.can_fire():
            return                                 # can't change who acts while a shot flies
        active = self.battle.active_side
        for side, team in self.battle.teams.items():
            for index in range(len(team.characters)):
                if pygame.Rect(team.character_rect(index)).collidepoint(pos):
                    if side == active:
                        self.select_actor(index)
                    else:
                        self.message = f"It is the {active.upper()} team's turn."
                    return

    def refresh_buttons(self):
        """Enable or disable buttons to match the current situation."""
        for mode, button in self.mode_buttons.items():
            button.chosen = (mode == "ai") == self.selection.vs_ai
        for level, button in self.difficulty_buttons.items():
            button.chosen = (level == self.selection.difficulty)
            button.enabled = self.selection.vs_ai
        for size, button in enumerate(self.size_buttons, start=1):
            button.chosen = (size == self.selection.team_size)
        self.start_button.enabled = self.selection.is_complete()
        if self.battle is not None:
            index = self.selected_index()
            for action, button in self.action_buttons.items():
                button.enabled = (not self.controls_locked()
                                  and self.battle.why_not_allowed(index, action) is None)

    # ----- update ------------------------------------------------------------------

    def update(self):
        if self.cannon_run.is_busy():
            self.update_cannon_run()      # the controls and the computer wait for it
        elif self.is_ai_turn():
            self.update_ai()
        if self.battle is not None and self.state in ("battle", "result"):
            self.battle.update()
            for event in self.battle.take_events():
                self.show_event(event)
            for explosion in self.explosions:
                explosion[2] += 1
            self.explosions = [e for e in self.explosions if e[2] < EXPLOSION_FRAMES]
            for floater in self.floaters:             # rise slowly, then disappear
                floater[1] -= 0.5
                floater[4] += 1
            self.floaters = [f for f in self.floaters if f[4] < FLOAT_FRAMES]
            shot = self.battle.projectile
            self.trail = (self.trail + [(shot.x, shot.y)])[-TRAIL_LENGTH:] if shot is not None else []
        self.refresh_buttons()

    def update_ai(self):
        """On the computer's turn: wait AI_DELAY_FRAMES (so the player can see the turn
        change), then let the AIController choose. Defend, Rally and Repair are carried out
        at once. An attack or Power Shot takes the same run to the cannon as a person's and is
        carried out (AIController.carry_out -> Battle.perform_action) when the character gets
        there. Its events are shown as usual."""
        self.ai_wait += 1
        if self.ai_wait < AI_DELAY_FRAMES:
            return
        self.ai_wait = 0
        plan = self.ai.choose(self.battle)
        if plan is None:
            return
        self.selected[self.ai.side] = plan.actor_index             # the panel shows who acts
        self.log = (self.log + [f"AI ({self.ai.difficulty.capitalize()}): {plan.reason}."])[-50:]
        if plan.fires_a_shot():
            # The barrel turns to the aim now, while the character runs; the shot waits for it.
            aim_cannon(self.battle.cannons[self.ai.side], plan.angle, plan.power)
            self.start_cannon_run(PendingShot(self.ai.side, plan.actor_index, plan.action,
                                              plan.angle, plan.power, plan))
        else:
            self.ai.carry_out(self.battle, plan)

    def show_event(self, event):
        """React to one battle event: effects, sounds, the log, and the end of the game."""
        self.play_event_sound(event)
        if event["type"] == "explosion":
            self.explosions.append([event["x"], event["y"], 0])
            target = other_side(event["side"])
            for name in event["covered"]:
                self.add_floater(target, name, "shielded", GUARD_COLOR)
            for hit in event["characters_hit"]:
                self.add_floater(target, hit["name"], f"-{hit['damage']}", DAMAGE_COLOR)
                if hit["defeated"]:
                    self.add_floater(target, hit["name"], "DEFEATED", DAMAGE_COLOR, below=True)
        elif event["type"] == "game_over":
            self.state = "result"
        lines = describe_event(event)
        if lines:
            self.log = (self.log + lines)[-50:]
            # The HUD keeps the outcome of the action: a new round or EXP is only in the log.
            if event["type"] not in ("round", "exp"):
                self.message = lines[-1]

    def play_event_sound(self, event):
        """The sound for one battle event (M4.2-A). Each event is read once, so each sound plays
        once; a refused action, Defend and Rally make no sound."""
        kind = event["type"]
        if kind == "fire":
            self.sounds.play("fire")
        elif kind == "explosion":
            self.sounds.play("explosion")
            target = other_side(event["side"])
            standing = len(self.battle.castles[target].alive_blocks())
            if standing < self.standing_blocks.get(target, standing):
                self.sounds.play("cover_destroyed")
            elif event["blocks_hit"]:
                self.sounds.play("cover_hit")
            self.standing_blocks[target] = standing
        elif kind == "exp" and event["levels"] > 0:
            self.sounds.play("level_up")
        elif kind == "game_over":
            self.sounds.stop()
            if event["winner"] == "draw":
                self.sounds.play("draw")
            elif self.ai is not None and event["winner"] == self.ai.side:
                self.sounds.play("defeat")     # against the computer, its win is your defeat
            else:
                self.sounds.play("victory")

    def add_floater(self, side, name, text, color, below=False):
        """A word or number floating up from above a character (M4.1): "-28", "DEFEATED", "shielded"."""
        team = self.battle.teams[side]
        index = next(i for i, character in enumerate(team.characters) if character.name == name)
        rect = pygame.Rect(team.character_rect(index))
        top = rect.top - 48 - (24 if index == 1 else 0)            # above its name and HP bar
        floater = [rect.centerx, top + (18 if below else 0), text, color, 0]
        # M4.2-A: move it up until it overlaps no other floating word (quick hits on one character).
        for _ in range(8):
            if not any(self.floater_rect(floater).colliderect(self.floater_rect(other)) for other in self.floaters):
                break
            floater[1] -= 16
        self.floaters.append(floater)

    def floater_font(self, text):
        return self.small_font if text.startswith("-") else self.tiny_font

    def floater_rect(self, floater):
        """The area a floating word covers (its text plus the 1 px outline)."""
        x, y, text = floater[0], floater[1], floater[2]
        width, height = self.floater_font(text).size(text)
        rect = pygame.Rect(0, 0, width + 2, height + 2)
        rect.center = (x, round(y))
        return rect

    # ----- text shown on the battle screen --------------------------------------------

    def ai_thinking(self):
        """True while it is the computer's turn and it has not chosen yet (its 2/3 s pause)."""
        return self.is_ai_turn() and not self.cannon_run.is_busy()

    def selected_info_lines(self):
        """The panel text about the character chosen to act."""
        if self.ai_thinking():                   # nobody is chosen yet: don't show a character
            return [f"{self.battle.active_side.upper()} TEAM: the computer ({self.ai.difficulty.capitalize()})",
                    "The computer is thinking about its move.", "", ""]
        character = self.selected_character()
        team = self.battle.teams[self.battle.active_side]
        if character.level == MAX_LEVEL:
            exp_text = "EXP max"
        else:
            exp_text = f"EXP {character.exp}/{character.exp_to_next_level()}"
        if character.special_ready():
            special_text = f"{character.SPECIAL_NAME}: ready"
        else:
            special_text = character.special_blocked_reason(team)
        if self.battle.is_over():
            status = "The game is over."
        elif character.is_defending:
            status = "Defending until your next turn."
        elif self.ai is not None and self.battle.active_side == self.ai.side:
            status = "Played by the computer."
        elif self.cannon_run.is_busy():
            status = self.cannon_run_text()      # the controls wait for the runner
        else:
            status = "Click a character or press 1-3 to choose who acts."
        stats = (f"HP {character.hp}/{character.max_hp}   ATK {character.atk}   "
                 f"DEF {character.defense}   {exp_text}")
        return [f"{self.battle.active_side.upper()} TEAM: {character.name}   Level {character.level}",
                stats, special_text, status]

    def action_hint_lines(self):
        """The panel text under the aim line: what SPECIAL would do, or what is happening.
        (The aim itself is shown by aim_text, in a bigger font, with a power bar.)"""
        character = self.selected_character()
        if self.battle.is_over():
            return ["The game is over: choose Rematch or Change teams."]
        if self.cannon_run.is_busy() and self.battle.projectile is None:
            return [self.cannon_run_text()]
        if self.is_ai_turn():
            return [f"The computer ({self.ai.difficulty.capitalize()}) is choosing the RIGHT team's move..."]
        if self.battle.projectile is not None:
            return ["The shot is in the air..."]
        reason = self.battle.why_not_allowed(self.selected_index(), "special")
        if reason is None:
            lines = [f"SPECIAL = {character.SPECIAL_NAME}: {character.SPECIAL_DESCRIPTION}"]
        else:
            lines = [f"SPECIAL unavailable: {reason}."]
        if isinstance(character, Archer):
            lines.append("ATTACK, SPACE and Power Shot use this aim. Arrows aim.")
        else:
            lines.append("ATTACK (or SPACE) fires with this aim. Arrows aim.")
        return lines

    def aim_text(self):
        """The active cannon's aim, shown large in the panel."""
        cannon = self.battle.cannons[self.battle.active_side]
        return f"Angle {cannon.angle}°   Power {cannon.power}"

    @staticmethod
    def cannon_label(cannon):
        """The short aim label drawn under the active cannon."""
        return f"{cannon.angle}° / {cannon.power}"

    def phase_text(self):
        """What is happening in this turn, for the turn banner."""
        if self.battle.is_over():
            return "game over"
        if self.battle.projectile is not None:
            return "shot in the air"
        if self.cannon_run.is_busy():
            if self.cannon_run.shot.side != self.battle.active_side:
                return "waiting"                    # the last shooter is still running back
            return "running to the cannon" if self.cannon_run.state == RUN_TO_CANNON else "running back"
        if self.is_ai_turn():
            return "thinking..."
        return "aim and act"

    def hud_turn_text(self):
        """The turn banner: the round, whose turn it is (and who plays it) and the phase."""
        heading = f"Round {self.battle.round_number} / {ROUND_LIMIT}   "
        if self.battle.is_over():
            return heading + "GAME OVER"
        side = self.battle.active_side
        player = ""
        if self.ai is not None:
            player = " (computer)" if side == self.ai.side else " (you)"
        return f"{heading}{side.upper()} TEAM'S TURN{player}: {self.phase_text()}"

    def cannon_run_text(self):
        """The panel line while a character runs to the cannon or back to its slot."""
        shot = self.cannon_run.shot
        name = f"{shot.side.upper()} {self.battle.teams[shot.side].characters[shot.actor_index].name}"
        if self.cannon_run.state == RUN_TO_CANNON:
            return f"{name} runs to the cannon to fire..."
        return f"{name} runs back to its place..."

    def log_header(self):
        """The combat log's heading, with the keys that work at any time."""
        if not self.sounds.available:
            sound = "no sound"
        else:
            sound = "M: sound off" if self.sounds.muted else "M: sound"
        return f"Combat log   (R: rematch, {sound}, Esc: quit)"

    def result_title(self):
        if self.battle.winner == "draw":
            return "DRAW!"
        return f"{self.battle.winner.upper()} TEAM WINS!"

    def result_reason(self):
        """One line: why the match ended (from Battle.end_reason)."""
        reason = self.battle.end_reason
        if reason == "timeout":
            return f"Round limit: {ROUND_LIMIT} rounds and no team was eliminated."
        if reason == "both_lost":
            return "Both teams were defeated at the same time."
        loser = other_side(self.battle.winner).upper()
        return f"Every {loser} character was defeated."

    def result_rounds(self):
        """The round in which the match ended (it can end in the middle of a round)."""
        return f"Final round: {self.battle.round_number} / {ROUND_LIMIT}"

    def result_subtitle(self):
        """A few words under the result title, so a win and a draw read differently."""
        if self.battle.end_reason == "timeout":
            return "Time limit reached"
        if self.battle.end_reason == "both_lost":
            return "Both teams fell together"
        return "Victory by elimination"

    # ----- drawing: team selection ---------------------------------------------------------

    def draw(self):
        if self.state == "select":
            self.draw_selection()
            return
        if self.state == "cover":
            self.draw_cover_screen()
            return
        self.draw_battlefield()
        self.draw_hud()
        self.draw_panel()
        if self.state == "result":
            self.draw_result()

    def draw_selection(self):
        self.screen.fill(MENU_COLOR)
        draw_text(self.screen, "CASTLE SIEGE", self.big_font, TEXT_COLOR, center=(WINDOW_WIDTH // 2, 36))
        draw_text(self.screen, "Mode:", self.font, TEXT_COLOR, midright=(280, 91))
        for button in self.mode_buttons.values():
            button.draw(self.screen, self.font)
        draw_text(self.screen, "Computer:", self.font, TEXT_COLOR, midright=(790, 91))
        for button in self.difficulty_buttons.values():
            button.draw(self.screen, self.font)
        draw_text(self.screen, "Team size:", self.font, TEXT_COLOR, midright=(455, 140))
        for button in self.size_buttons:
            button.draw(self.screen, self.font)
        size = self.selection.team_size
        draw_text(self.screen, f"LEFT TEAM   {len(self.selection.picks['left'])}/{size} chosen"
                  + ("   (you)" if self.selection.vs_ai else ""),
                  self.font, TEAM_COLORS["left"], topleft=(60, 180))
        if self.selection.vs_ai:
            right_title = f"RIGHT TEAM   the computer picks {size} and its cover"
        else:
            right_title = f"RIGHT TEAM   {len(self.selection.picks['right'])}/{size} chosen"
        draw_text(self.screen, right_title, self.font, TEAM_COLORS["right"], topleft=(660, 180))
        for (side, role), rect in self.card_rects.items():
            self.draw_card(side, role, rect)
        draw_text(self.screen, self.message, self.small_font, TEXT_COLOR, center=(WINDOW_WIDTH // 2, 495))
        self.start_button.draw(self.screen, self.font)
        draw_text(self.screen, "Slot 1 stands at the front, behind the cover. Both teams have the same size. "
                  "Enter = next, M = sound, Esc = quit.", self.small_font, TEXT_COLOR,
                  center=(WINDOW_WIDTH // 2, 600))
        draw_text(self.screen, "Win by defeating every enemy character. Cover blocks only protect: "
                  "destroying them does not win.", self.small_font, TEXT_COLOR,
                  center=(WINDOW_WIDTH // 2, 630))

    def draw_card(self, side, role, rect):
        """One character card on the selection screen, with its stats."""
        picks = self.selection.picks[side]
        computer_team = side == "right" and self.selection.vs_ai
        chosen = role in picks and not computer_team
        background = (236, 238, 242) if computer_team else (250, 250, 252)   # greyed: not clickable
        pygame.draw.rect(self.screen, background, rect, border_radius=8)
        border = TEAM_COLORS[side] if chosen else DIM_TEXT
        pygame.draw.rect(self.screen, border, rect, 5 if chosen else 2, border_radius=8)
        draw_text(self.screen, role.__name__, self.font, TEXT_COLOR, center=(rect.centerx, rect.top + 20))
        draw_figure(self.screen, role, rect.centerx, rect.top + 38, direction(side), TEAM_COLORS[side], side)
        lines = [f"HP {role.BASE_HP}  ATK {role.BASE_ATK}  DEF {role.BASE_DEF}",
                 f"Block damage: {role.BLOCK_DAMAGE}",
                 f"Special: {role.SPECIAL_NAME}",
                 f"Cooldown: {role.SPECIAL_COOLDOWN} rounds",
                 role.SPECIAL_DESCRIPTION]
        y = rect.top + 94
        for line in lines:
            for part in wrap_text(line, self.tiny_font, rect.width - 14):   # never wider than the card
                draw_text(self.screen, part, self.tiny_font, TEXT_COLOR, center=(rect.centerx, y))
                y += 19
        if chosen:
            slot = picks.index(role) + 1
            label = f"Slot {slot}" + (" (front)" if slot == 1 else "")
            draw_text(self.screen, label, self.small_font, TEAM_COLORS[side],
                      center=(rect.centerx, rect.bottom - 18))
        elif computer_team:                       # M4.1: say plainly that these cards can't be clicked
            band = pygame.Rect(rect.left + 6, rect.bottom - 32, rect.width - 12, 26)
            pygame.draw.rect(self.screen, BUTTON_OFF, band, border_radius=4)
            draw_text(self.screen, "THE COMPUTER PICKS", self.tiny_font, LIGHT_TEXT, center=band.center)

    # ----- drawing: cover placement ------------------------------------------------

    def cover_title(self):
        return f"{self.placing.upper()} TEAM: PLACE YOUR COVER"

    def cover_title_color(self):
        return LABEL_COLORS[self.placing]

    def cover_text_plate_rect(self):
        """The light plate behind the placement screen's title, instructions and legend."""
        return pygame.Rect(140, 12, WINDOW_WIDTH - 280, self.cover_text_bottom() + 10 - 12)

    def cover_count_text(self):
        return f"Blocks: {len(self.setup.layouts[self.placing])} / {MAX_BLOCKS}"

    def budget_pip_rects(self):
        """MAX_BLOCKS small squares right of "Blocks: n / 6", one per block of the budget (M4.1)."""
        first_x = WINDOW_WIDTH // 2 + self.font.size(self.cover_count_text())[0] // 2 + 14
        return [pygame.Rect(first_x + i * 19, 79, 14, 14) for i in range(MAX_BLOCKS)]

    def cover_help_lines(self):
        return ["Click an empty slot to place a block (100 HP). Click a block to remove it.",
                f"Up to {MAX_BLOCKS} blocks. A raised block needs a block under it: "
                "removing that block also removes the one on top.",
                "Blocks stop enemy shots and shield the characters behind them.",
                "Destroying cover never wins: only defeating every enemy character does."]

    def cover_legend_y(self):
        """y of the middle of the legend row, just under the instructions."""
        return COVER_HELP_TOP + COVER_HELP_STEP * len(self.cover_help_lines()) + 14

    def cover_text_bottom(self):
        """The lowest y the placement screen's title, instructions and legend reach."""
        return self.cover_legend_y() + 12

    def cover_next_step(self):
        if self.placing == "right":
            return "Confirm: the battle starts."
        if self.selection.vs_ai:
            return "Confirm: the battle starts (the computer places its own cover)."
        return "Confirm: RIGHT places its cover next."

    def draw_cover_screen(self):
        """One team's side of the battlefield: its characters, its cannon and its 8 cover
        slots, drawn exactly where they stand in the battle. The other team's cover stays hidden."""
        side = self.placing
        self.screen.blit(self.background, (0, 0))   # sky, scenery and ground (M4.2-A)
        draw_plate(self.screen, self.cover_text_plate_rect())   # the text stays readable on the sky
        draw_text(self.screen, self.cover_title(), self.title_font, self.cover_title_color(),
                  center=(WINDOW_WIDTH // 2, 42))
        draw_text(self.screen, self.cover_count_text(), self.font, TEXT_COLOR, center=(WINDOW_WIDTH // 2, 86))
        used = len(self.setup.layouts[side])
        for i, pip in enumerate(self.budget_pip_rects()):
            if i < used:
                pygame.draw.rect(self.screen, block_color(side, 1, 1), pip)
            pygame.draw.rect(self.screen, TEXT_COLOR if i < used else DIM_TEXT, pip, 1)
        for i, line in enumerate(self.cover_help_lines()):
            draw_text(self.screen, line, self.small_font, TEXT_COLOR,
                      center=(WINDOW_WIDTH // 2, COVER_HELP_TOP + i * COVER_HELP_STEP))
        self.draw_cover_legend(side)
        for index, role in enumerate(self.selection.picks[side]):
            center_x, top = SLOT_X[side][index], GROUND_Y - CHARACTER_HEIGHT
            draw_figure(self.screen, role, center_x, top, direction(side), TEAM_COLORS[side], side)
            label = pygame.Rect(0, 0, self.tiny_font.size(role.__name__)[0] + 10, 18)
            label.center = (center_x, top - 14 - (18 if index == 1 else 0))
            draw_plate(self.screen, label)
            draw_text(self.screen, role.__name__, self.tiny_font, LABEL_COLORS[side], center=label.center)
        self.draw_cannon(Cannon(side), is_active=False)
        # A frame around the 8 slots, so the small area to click stands out on the big screen.
        frame = pygame.Rect(min(COLUMN_X[side]) - 5, GROUND_Y - 2 * BLOCK_SIZE - 6, 4 * BLOCK_SIZE + 10,
                            2 * BLOCK_SIZE + 6)
        pygame.draw.rect(self.screen, LABEL_COLORS[side], frame, 2, border_radius=6)
        for slot in range(SLOT_COUNT):
            self.draw_slot(side, slot, self.setup.layouts[side])
        draw_text(self.screen, "COVER SLOTS", self.tiny_font, LABEL_COLORS[side],
                  center=(frame.centerx, frame.top - 9))
        other = other_side(side)
        if side == "right":
            note = "LEFT's cover stays hidden until the battle starts."
        elif self.selection.vs_ai:
            note = "The computer places the RIGHT cover when the battle starts."
        else:
            note = "RIGHT places its own cover next, without seeing LEFT's."
        draw_text(self.screen, note, self.small_font, LABEL_COLORS[other],
                  center=(WINDOW_WIDTH // 4 * (3 if other == "right" else 1), 420))
        pygame.draw.rect(self.screen, PANEL_COLOR, (0, PANEL_TOP, WINDOW_WIDTH, WINDOW_HEIGHT - PANEL_TOP))
        draw_text(self.screen, self.message, self.small_font, LIGHT_TEXT, center=(WINDOW_WIDTH // 2, PANEL_TOP + 22))
        self.back_button.draw(self.screen, self.font)
        self.confirm_button.draw(self.screen, self.font)
        draw_text(self.screen, f"{self.cover_next_step()}   Enter = Confirm, Backspace = Back, Esc = quit.",
                  self.tiny_font, DIM_TEXT, center=(WINDOW_WIDTH // 2, PANEL_TOP + 114))

    def draw_cover_legend(self, side):
        """One row under the instructions: what the three kinds of slot look like."""
        items = [("block", "Block: click to remove"), ("open", "Empty slot: click to place"),
                 ("closed", "No block allowed here now")]
        widths = [30 + self.small_font.size(text)[0] for _, text in items]
        x = (WINDOW_WIDTH - sum(widths) - 50 * (len(items) - 1)) // 2
        y = self.cover_legend_y()
        for (kind, text), width in zip(items, widths):
            sample = pygame.Rect(x, y - 11, 22, 22)
            if kind == "block":
                pygame.draw.rect(self.screen, block_color(side, 1, 1), sample)
                pygame.draw.rect(self.screen, TEXT_COLOR, sample, 1)
            elif kind == "open":
                pygame.draw.rect(self.screen, OPEN_SLOT_COLOR, sample)
                pygame.draw.rect(self.screen, TEAM_COLORS[side], sample, 2)
            else:
                self.draw_closed_slot(sample)
            draw_text(self.screen, text, self.small_font, TEXT_COLOR, midleft=(x + 30, y))
            x += width + 50

    def draw_slot(self, side, slot, layout):
        """An occupied slot shows its block; a slot that can take a block is light with a "+";
        a slot that can't take one right now (castle.place_block says why) is only outlined."""
        rect = slot_rect(side, slot)
        if slot in layout:
            pygame.draw.rect(self.screen, block_color(side, 1, 1), rect)
            pygame.draw.rect(self.screen, TEXT_COLOR, rect, 1)
        elif place_block(layout, slot)[1] is None:
            pygame.draw.rect(self.screen, OPEN_SLOT_COLOR, rect)
            pygame.draw.rect(self.screen, TEAM_COLORS[side], rect, 2)
            draw_text(self.screen, "+", self.font, TEAM_COLORS[side], center=rect.center)
        else:
            self.draw_closed_slot(rect)

    def draw_closed_slot(self, rect):
        """A slot that can't take a block right now: an outline with an "x" (M4.1: it was
        only a faint outline)."""
        pygame.draw.rect(self.screen, DIM_TEXT, rect, 1)
        inset = rect.width // 4
        pygame.draw.line(self.screen, CLOSED_SLOT_COLOR, (rect.left + inset, rect.top + inset),
                         (rect.right - 1 - inset, rect.bottom - 1 - inset), 2)
        pygame.draw.line(self.screen, CLOSED_SLOT_COLOR, (rect.right - 1 - inset, rect.top + inset),
                         (rect.left + inset, rect.bottom - 1 - inset), 2)

    # ----- drawing: the battlefield --------------------------------------------------

    def draw_battlefield(self):
        self.screen.blit(self.background, (0, 0))   # sky, scenery and ground (M4.2-A)
        for side, castle in self.battle.castles.items():
            for block in castle.blocks:
                if block.is_destroyed():              # M4.1: show where cover used to be
                    draw_rubble_outline(self.screen, block.x, block.y, block.size)
                else:
                    draw_block(self.screen, side, block.x, block.y, block.size, block.hp, block.max_hp)
            # Asked from the Battle on every frame, so it can never be out of date.
            if self.battle.castle_guarded(side):
                self.draw_castle_guard(side, castle)
        self.draw_characters()
        for side, cannon in self.battle.cannons.items():
            self.draw_cannon(cannon, is_active=(side == self.battle.active_side and not self.battle.is_over()))
        if self.cannon_run.state == FIRE:            # starts on the frame the shot is launched
            self.draw_muzzle_flash(self.battle.cannons[self.cannon_run.shot.side])
        if self.battle.can_fire():
            cannon = self.battle.cannons[self.battle.active_side]
            self.draw_aim_arrow(cannon)
            draw_text(self.screen, self.cannon_label(cannon), self.tiny_font, READY_COLOR,
                      center=(cannon.x, GROUND_Y + 10))
        for x, y in self.trail[:-1]:                 # dots where the shot has just been
            pygame.draw.circle(self.screen, TRAIL_COLOR, (round(x), round(y)), 2)
        if self.battle.projectile is not None:
            shot = (round(self.battle.projectile.x), round(self.battle.projectile.y))
            if self.shot_style == "power":           # a Power Shot: bigger and orange
                pygame.draw.circle(self.screen, FLASH_COLOR, shot, 9)
                pygame.draw.circle(self.screen, POWER_SHOT_COLOR, shot, 7)
            else:
                pygame.draw.circle(self.screen, SHOT_COLOR, shot, 5)
        # An explosion is a circle that grows to the blast radius while fading from yellow to red.
        # It is see-through (M4.1), so the character it hits can still be seen.
        for x, y, age in self.explosions:
            progress = age / EXPLOSION_FRAMES
            radius = int(8 + (BLAST_RADIUS - 8) * progress)
            color = (255, int(220 - 150 * progress), int(80 - 60 * progress))
            alpha = int(EXPLOSION_ALPHA * (1 - 0.5 * progress))
            circle = pygame.Surface((2 * radius + 2, 2 * radius + 2), pygame.SRCALPHA)
            pygame.draw.circle(circle, color + (alpha,), (radius + 1, radius + 1), radius,
                               0 if progress < 0.5 else 4)
            self.screen.blit(circle, (round(x) - radius - 1, round(y) - radius - 1))
        for x, y, text, color, _ in self.floaters:   # "-28", "DEFEATED", "shielded"
            draw_outlined_text(self.screen, text, self.floater_font(text), color, (255, 255, 255),
                               center=(x, round(y)))

    def draw_castle_guard(self, side, castle):
        """Cover Guard is on: a blue outline on every standing block, and a GUARDED badge."""
        for block in castle.alive_blocks():
            pygame.draw.rect(self.screen, GUARD_COLOR, (block.x, block.y, block.size, block.size), 3)
        badge = guard_badge_rect(side)
        pygame.draw.rect(self.screen, GUARD_COLOR, badge, border_radius=5)
        draw_text(self.screen, "GUARDED", self.tiny_font, (255, 255, 255), center=badge.center)

    def draw_characters(self):
        """Each character at its Team slot, with its name, HP bar and special cooldown. A
        character running to or from the cannon is drawn where it runs instead (draw_runner)."""
        acting_side = self.battle.active_side
        chosen = self.selected_index() if self.state == "battle" else None
        for side, team in self.battle.teams.items():
            for index, character in enumerate(team.characters):
                rect = pygame.Rect(team.character_rect(index))
                # Neighbours stand 45 px apart, so the middle slot's label sits higher.
                label_y = rect.top - 30 - (24 if index == 1 else 0)
                running = character.is_alive() and self.cannon_run.moves(side, index)
                if character.is_alive():
                    if character.is_defending:
                        bubble = pygame.Surface((64, 64), pygame.SRCALPHA)
                        pygame.draw.circle(bubble, DEFEND_COLOR + (90,), (32, 32), 31)
                        pygame.draw.circle(bubble, DEFEND_COLOR + (220,), (32, 32), 31, 2)
                        self.screen.blit(bubble, bubble.get_rect(center=rect.center))
                    if running:
                        self.draw_runner(type(character), side, rect.top)
                    else:
                        draw_figure(self.screen, type(character), rect.centerx, rect.top,
                                    direction(side), TEAM_COLORS[side], side)
                    name_color = LABEL_COLORS[side]
                else:
                    # Defeated: a grey shape lying on the ground.
                    pygame.draw.rect(self.screen, DEFEATED_COLOR, (rect.left - 4, rect.bottom - 9, rect.width + 8, 9),
                                     border_radius=4)
                    name_color = DEFEATED_COLOR
                draw_plate(self.screen, self.label_plate_rect(side, index))   # M4.2-A: readable on any scenery
                draw_text(self.screen, character.name, self.tiny_font, name_color,
                          center=(rect.centerx, label_y))
                bar = pygame.Rect(rect.centerx - 20, label_y + 8, 40, 6)
                pygame.draw.rect(self.screen, (60, 60, 60), bar)
                pygame.draw.rect(self.screen, hp_bar_color(character),
                                 (bar.left, bar.top, hp_bar_width(character, bar.width), bar.height))
                pygame.draw.rect(self.screen, TEXT_COLOR, bar.inflate(2, 2), 1)      # outline
                if character.is_alive():                        # special cooldown, under the feet
                    if character.special_cooldown > 0:
                        draw_text(self.screen, f"wait {character.special_cooldown}", self.tiny_font,
                                  COOLDOWN_COLOR, center=(rect.centerx, GROUND_Y + 10))
                    else:
                        draw_text(self.screen, "ready", self.tiny_font, READY_COLOR,
                                  center=(rect.centerx, GROUND_Y + 10))
                if (side == acting_side and index == chosen and character.is_alive() and not running
                        and not self.ai_thinking()):     # the computer hasn't chosen anyone yet
                    pygame.draw.rect(self.screen, ACTIVE_RING_COLOR, rect.inflate(8, 8), 3)
                    tip_y = label_y - 10
                    pygame.draw.polygon(self.screen, ACTIVE_RING_COLOR,
                                        [(rect.centerx - 7, tip_y - 10), (rect.centerx + 7, tip_y - 10),
                                         (rect.centerx, tip_y)])

    def draw_runner(self, role, side, top):
        """The attacking character on its way to the cannon, firing it, or on its way back.
        Only the figure moves: its name, HP bar and cooldown stay over its slot, where the
        Battle keeps the character (and where a shot could hit it)."""
        run = self.cannon_run
        x = round(run.actor_x())
        if run.state == FIRE:
            draw_firing_figure(self.screen, role, x, top, run.facing(), TEAM_COLORS[side], side)
        else:
            draw_running_figure(self.screen, role, x, top, run.facing(), TEAM_COLORS[side], run.frame, side)

    def label_plate_rect(self, side, index):
        """The light plate behind a character's name and HP bar (M4.2-A)."""
        team = self.battle.teams[side]
        rect = pygame.Rect(team.character_rect(index))
        label_y = rect.top - 30 - (24 if index == 1 else 0)
        plate = pygame.Rect(0, 0, max(52, self.tiny_font.size(team.characters[index].name)[0] + 12), 24)
        plate.midtop = (rect.centerx, label_y - 8)
        return plate

    def draw_muzzle_flash(self, cannon):
        """A short flash at the barrel's tip while the shot leaves it, shrinking over FIRE_FRAMES.
        The cannon itself never moves."""
        radius = round(12 - 7 * self.cannon_run.frame / FIRE_FRAMES)
        if self.shot_style == "power":
            radius = round(radius * 1.5)          # M4.1: a Power Shot gets a bigger flash
        center = muzzle_point(cannon)
        pygame.draw.circle(self.screen, FLASH_EDGE, center, radius)
        pygame.draw.circle(self.screen, FLASH_COLOR, center, max(2, radius // 2))

    def draw_cannon(self, cannon, is_active):
        # A wheel on the ground under the pivot; the barrel points along the cannon's angle.
        pygame.draw.circle(self.screen, WOOD, (cannon.x, GROUND_Y - 8), 8)
        radians = math.radians(cannon.angle)
        tip = (cannon.x + direction(cannon.side) * 24 * math.cos(radians),
               cannon.y - 24 * math.sin(radians))       # minus: up is smaller y
        pygame.draw.line(self.screen, CANNON_COLOR, (cannon.x, cannon.y), tip, 8)
        pygame.draw.circle(self.screen, CANNON_COLOR, (cannon.x, cannon.y), 9)
        if is_active:
            pygame.draw.circle(self.screen, ACTIVE_RING_COLOR, (cannon.x, cannon.y), 14, 3)

    def draw_aim_arrow(self, cannon):
        """An arrow in the aiming direction; a longer arrow means more power."""
        length = 30 + cannon.power * 1.2
        radians = math.radians(cannon.angle)
        dx = direction(cannon.side) * math.cos(radians)
        dy = -math.sin(radians)
        end = (cannon.x + dx * length, cannon.y + dy * length)
        pygame.draw.line(self.screen, AIM_COLOR, (cannon.x, cannon.y), end, 3)
        back = math.atan2(-dy, -dx)                       # arrowhead: two short lines
        for offset in (-0.5, 0.5):
            wing = (end[0] + 12 * math.cos(back + offset), end[1] + 12 * math.sin(back + offset))
            pygame.draw.line(self.screen, AIM_COLOR, end, wing, 3)

    def hud_team_line(self, side):
        """'LEFT  2/3 standing   cover 5/6': living characters, and standing / placed blocks."""
        team, castle = self.battle.teams[side], self.battle.castles[side]
        return (f"{side.upper()}  {len(team.alive_characters())}/{len(team.characters)} standing"
                f"   cover {len(castle.alive_blocks())}/{len(castle.blocks)}")

    def draw_hud(self):
        # Each team's line, after its badge (M4.2-A: the emblem tells the teams apart by shape).
        for side, centre in self.hud_emblem_centres().items():
            draw_badge(self.screen, side, centre, 11)
            draw_text(self.screen, self.hud_team_line(side), self.small_font, TEXT_COLOR,
                      **self.hud_side_position(side))
        # The turn banner (M4.1): white text on the colour of the team whose turn it is, saying
        # what is happening ("aim and act", "shot in the air", "thinking..."); grey once it's over.
        banner = self.hud_banner_rect()
        if self.battle.is_over():
            pygame.draw.rect(self.screen, (70, 74, 82), banner, border_radius=12)
        else:
            pygame.draw.rect(self.screen, TEAM_COLORS[self.battle.active_side], banner, border_radius=12)
            draw_emblem(self.screen, self.battle.active_side, (banner.left + 16, banner.centery), 5)
        draw_text(self.screen, self.hud_turn_text(), self.banner_font, (255, 255, 255),
                  center=(banner.centerx + 9, banner.centery))
        draw_text(self.screen, self.message, self.small_font, TEXT_COLOR, center=(WINDOW_WIDTH // 2, 62))

    def hud_banner_rect(self):
        """Where the turn banner is drawn: centred at the top, sized to its text and emblem."""
        width, height = self.banner_font.size(self.hud_turn_text())
        banner = pygame.Rect(0, 0, width + 46, height + 14)
        banner.center = (WINDOW_WIDTH // 2, 27)
        return banner

    @staticmethod
    def hud_emblem_centres():
        """Where each team's badge is drawn in the HUD, before its line."""
        return {"left": (30, 27), "right": (WINDOW_WIDTH - 30, 27)}

    @staticmethod
    def hud_side_position(side):
        return {"midleft": (48, 27)} if side == "left" else {"midright": (WINDOW_WIDTH - 48, 27)}

    def hud_side_rects(self):
        """The area of each team's HUD line, badge included (the banner must stay clear of it)."""
        rects = {}
        for side, (x, y) in self.hud_emblem_centres().items():
            text = self.small_font.render(self.hud_team_line(side), True, TEXT_COLOR)
            rects[side] = text.get_rect(**self.hud_side_position(side)).union(pygame.Rect(x - 11, y - 11, 22, 22))
        return rects

    def draw_panel(self):
        pygame.draw.rect(self.screen, PANEL_COLOR, (0, PANEL_TOP, WINDOW_WIDTH, WINDOW_HEIGHT - PANEL_TOP))
        # Left: the character chosen to act.
        for i, line in enumerate(self.selected_info_lines()):
            color = TEAM_COLORS[self.battle.active_side] if i == 0 else LIGHT_TEXT
            if i == 0:
                color = tuple(min(255, c + 70) for c in color)      # brighter on the dark panel
            draw_text(self.screen, line, self.small_font, color, topleft=(20, PANEL_TOP + 12 + i * 30))
        # Middle: the three action buttons, the aim (M4.1: large, with a power bar) and what
        # the buttons will do.
        for button in self.action_buttons.values():
            button.draw(self.screen, self.font)
        if not self.battle.is_over():
            draw_text(self.screen, self.aim_text(), self.small_font, LIGHT_TEXT, topleft=(450, PANEL_TOP + 60))
            power = self.battle.cannons[self.battle.active_side].power
            bar = pygame.Rect(660, PANEL_TOP + 64, 170, 10)
            pygame.draw.rect(self.screen, (60, 66, 78), bar)
            filled = round(bar.width * (power - MIN_POWER) / (MAX_POWER - MIN_POWER))
            pygame.draw.rect(self.screen, AIM_COLOR, (bar.left, bar.top, filled, bar.height))
            pygame.draw.rect(self.screen, DIM_TEXT, bar, 1)
        y = PANEL_TOP + 84
        for line in self.action_hint_lines():
            for part in wrap_text(line, self.tiny_font, 390):
                draw_text(self.screen, part, self.tiny_font, LIGHT_TEXT, topleft=(450, y))
                y += 18
        # Right: the combat log.
        draw_text(self.screen, self.log_header(), self.tiny_font, DIM_TEXT,
                  topleft=(860, PANEL_TOP + 8))
        lines = []                                 # long lines (the AI's reasons) are wrapped
        for line in self.log[-LOG_LINES:]:
            lines.extend(wrap_text(line, self.tiny_font, WINDOW_WIDTH - 870))
        for i, line in enumerate(lines[-LOG_LINES:]):
            draw_text(self.screen, line, self.tiny_font, LIGHT_TEXT, topleft=(860, PANEL_TOP + 28 + i * 19))

    def draw_result(self):
        banner = result_banner_rect()
        panel = pygame.Surface((banner.width, 270), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 190))                                 # semi-transparent black
        self.screen.blit(panel, banner.topleft)
        # M4.1: the title band has the winner's colour, or DRAW_COLOR, so a win and a draw
        # can't be mistaken for each other.
        fill = DRAW_COLOR if self.battle.winner == "draw" else TEAM_COLORS[self.battle.winner]
        pygame.draw.rect(self.screen, fill, banner)
        draw_text(self.screen, self.result_title(), self.big_font, (255, 255, 255),
                  center=(WINDOW_WIDTH // 2, banner.top + 36))
        draw_text(self.screen, self.result_subtitle(), self.small_font, (245, 245, 245),
                  center=(WINDOW_WIDTH // 2, banner.bottom - 14))
        draw_text(self.screen, self.result_reason(), self.font, (230, 230, 230),
                  center=(WINDOW_WIDTH // 2, 236))
        draw_text(self.screen, self.result_rounds(), self.small_font, (200, 200, 200),
                  center=(WINDOW_WIDTH // 2, 266))
        self.rematch_button.draw(self.screen, self.font)
        self.change_teams_button.draw(self.screen, self.font)
        draw_text(self.screen, "R = rematch     M = sound     Esc = quit", self.small_font, (220, 220, 220),
                  center=(WINDOW_WIDTH // 2, 368))


def open_window():
    """Start Pygame, open the game window and set up the keyboard. Returns the screen."""
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, BUFFER)   # small buffer: sounds start without delay
    pygame.init()                     # a missing audio device is not an error here (see sound.py)
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Castle Siege")
    pygame.key.set_repeat(250, 40)    # holding an arrow key keeps changing the aim
    # Pygame starts in "text input" mode, which sends key presses through the
    # operating system's input method. With a Chinese input method active, R was
    # captured to type Chinese, and while it was waiting for more letters it also
    # captured the arrow keys and SPACE. The game only needs plain key presses,
    # so text input is switched off.
    pygame.key.stop_text_input()
    return screen


def main():
    screen = open_window()
    clock = pygame.time.Clock()
    game = Game(screen)
    while game.running:
        for event in pygame.event.get():
            game.handle_event(event)
        game.update()
        game.draw()
        pygame.display.flip()
        clock.tick(FPS)
    pygame.quit()


if __name__ == "__main__":
    main()
