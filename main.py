"""Castle Siege - the Pygame interface (the only module that uses Pygame).

Screens (Game.state):
  "select"  team selection: mode (Player vs AI or two players), AI level, team size
            (1v1, 2v2 or 3v3) and the characters
  "battle"  the battlefield: pick a character, aim the cannon, pick an action
  "result"  the battlefield with the winner, plus Rematch / Change teams buttons
The selection screen can also start the classic cannon duel (the M1 prototype,
with no characters).

Player vs AI: the human plays LEFT and the computer (ai.py) picks and plays RIGHT.
Two players: both teams play on this computer and take turns ("hot seat").
All game rules live in battle.py, castle.py and characters.py: this file reads
the mouse and keyboard, calls Battle methods and draws what the Battle reports.

Run from the project folder:   python main.py
"""
import math

import pygame

from ai import DIFFICULTY_SETTINGS, AIController
from battle import BLAST_RADIUS, FIELD_WIDTH, MAX_TEAM_SIZE, Battle, direction, other_side
from castle import GROUND_Y
from characters import ARCHETYPES, MAX_LEVEL, Archer, Knight

WINDOW_WIDTH = FIELD_WIDTH        # 1280
WINDOW_HEIGHT = 720
FPS = 60
AI_DELAY_FRAMES = 40              # the computer waits this long (2/3 s) before it acts
EXPLOSION_FRAMES = 20             # how long an explosion stays on screen
LOG_LINES = 6                     # combat-log lines shown at once
PANEL_TOP = 580                   # the control panel fills the bottom of the window

SKY_COLOR = (160, 205, 235)
GROUND_COLOR = (96, 140, 72)
MENU_COLOR = (225, 232, 240)
PANEL_COLOR = (38, 46, 58)
TEXT_COLOR = (25, 25, 35)
LIGHT_TEXT = (235, 238, 242)
DIM_TEXT = (160, 166, 176)
HINT_COLOR = (235, 240, 225)
CANNON_COLOR = (55, 55, 60)
ACTIVE_RING_COLOR = (255, 215, 0)
AIM_COLOR = (230, 110, 20)
SHOT_COLOR = (20, 20, 20)
TEAM_COLORS = {"left": (60, 100, 200), "right": (200, 70, 60)}
STONE_COLORS = {"left": (150, 162, 195), "right": (196, 156, 142)}   # an undamaged block
SKIN = (240, 205, 170)
STEEL = (175, 180, 190)
WOOD = (130, 85, 45)
HARD_HAT = (240, 200, 40)
HOOD = (60, 130, 60)
DEFEATED_COLOR = (120, 120, 120)
DEFEND_COLOR = (90, 170, 255)
COOLDOWN_COLOR = (255, 225, 120)  # these two are drawn on the green ground strip
READY_COLOR = (235, 240, 235)
BUTTON_COLOR = (70, 95, 130)
BUTTON_CHOSEN = (225, 170, 40)
BUTTON_OFF = (95, 98, 105)


# ----- small helpers -------------------------------------------------------------

def block_color(side, hp, max_hp):
    """A block gets darker as it loses HP, so every hit is visible.

    Full health keeps 100 % of the colour; a block with almost no HP left keeps 40 %.
    """
    shade = 0.4 + 0.6 * hp / max_hp
    return tuple(int(channel * shade) for channel in STONE_COLORS[side])


def hp_bar_width(character, full_width):
    """Length of a character's HP bar: full when unhurt, 0 when defeated."""
    return int(full_width * character.hp / character.max_hp)


def draw_text(screen, text, font, color, **position):
    """Draw text placed by one keyword, e.g. center=(x, y) or topleft=(x, y)."""
    image = font.render(text, True, color)
    screen.blit(image, image.get_rect(**position))


def wrap_text(text, font, max_width):
    """Split text into lines that each fit in max_width pixels."""
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and font.size(candidate)[0] > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    return lines + [line] if line else lines


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
            lines.append(f"Explosion: {event['blocks_hit']} castle block{plural}, "
                         f"{event['damage']} damage.")
        target_side = other_side(event["side"]).upper()
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
        if event["winner"] == "draw":
            return ["It's a draw!"]
        return [f"{event['winner'].upper()} wins!"]
    return []    # "fire" and "turn" are shown by the HUD instead


def draw_figure(screen, role, center_x, top, facing, body_color):
    """A simple figure for a character role, standing in the 28 x 44 box whose top is `top`.

    `facing` is +1 (looking right) or -1 (looking left); the shield, bow or hammer
    is held on that side.
    """
    pygame.draw.rect(screen, body_color, (center_x - 9, top + 15, 18, 29), border_radius=4)
    pygame.draw.circle(screen, SKIN, (center_x, top + 8), 7)
    front = center_x + facing * 11
    if role is Knight:
        pygame.draw.rect(screen, STEEL, (center_x - 7, top, 14, 7),
                         border_top_left_radius=6, border_top_right_radius=6)           # helmet
        pygame.draw.rect(screen, STEEL, (front - 5, top + 18, 10, 16), border_radius=3)  # shield
        pygame.draw.rect(screen, TEXT_COLOR, (front - 5, top + 18, 10, 16), 1, border_radius=3)
    elif role is Archer:
        pygame.draw.polygon(screen, HOOD, [(center_x - 8, top + 8), (center_x + 8, top + 8),
                                           (center_x, top - 3)])                        # hood
        bow = pygame.Rect(front - 6, top + 12, 12, 26)
        if facing > 0:
            pygame.draw.arc(screen, WOOD, bow, -math.pi / 2, math.pi / 2, 3)
        else:
            pygame.draw.arc(screen, WOOD, bow, math.pi / 2, 3 * math.pi / 2, 3)
        pygame.draw.line(screen, LIGHT_TEXT, (front, top + 12), (front, top + 38), 1)    # string
    else:                                                                               # Engineer
        pygame.draw.rect(screen, HARD_HAT, (center_x - 8, top, 16, 6),
                         border_top_left_radius=7, border_top_right_radius=7)           # hard hat
        pygame.draw.line(screen, WOOD, (front, top + 20), (front, top + 40), 3)          # hammer
        pygame.draw.rect(screen, STEEL, (front - 5, top + 16, 10, 6))


class Button:
    """A clickable rectangle with a label. A disabled button is greyed out and ignores clicks."""

    def __init__(self, x, y, width, height, label):
        self.rect = pygame.Rect(x, y, width, height)
        self.label = label
        self.enabled = True
        self.chosen = False         # drawn highlighted (e.g. the chosen team size)

    def is_clicked(self, pos):
        return self.enabled and self.rect.collidepoint(pos)

    def draw(self, screen, font):
        if not self.enabled:
            fill, text_color = BUTTON_OFF, DIM_TEXT
        elif self.chosen:
            fill, text_color = BUTTON_CHOSEN, TEXT_COLOR
        else:
            fill, text_color = BUTTON_COLOR, LIGHT_TEXT
        pygame.draw.rect(screen, fill, self.rect, border_radius=6)
        pygame.draw.rect(screen, TEXT_COLOR, self.rect, 2, border_radius=6)
        draw_text(screen, self.label, font, text_color, center=self.rect.center)


class TeamSelection:
    """The choices made on the team-selection screen. (No drawing happens here.)

    Each team picks `team_size` different roles. The order of the picks is the
    slot order: the first pick stands nearest the team's castle. Against the
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


class Game:
    """Connects the mouse, keyboard and screen to the team selection and one Battle."""

    def __init__(self, screen):
        self.screen = screen
        # Font(None, size) uses Pygame's built-in font. (SysFont scans the system's
        # installed fonts, and on some Windows machines that scan crashes.)
        self.big_font = pygame.font.Font(None, 80)
        self.font = pygame.font.Font(None, 30)
        self.small_font = pygame.font.Font(None, 24)
        self.tiny_font = pygame.font.Font(None, 19)
        self.running = True
        self.space_released = True    # fire only once per SPACE press (see handle_key)
        self.state = "select"
        self.selection = TeamSelection()
        self.battle = None
        self.ai = None                # the AIController playing RIGHT, or None (two players)
        self.ai_wait = 0              # frames the computer has waited on this turn
        self.selected = {"left": 0, "right": 0}   # slot of the character chosen to act
        self.explosions = []          # each one is [x, y, age in frames]
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
        self.start_button = Button(515, 515, 250, 56, "START BATTLE")
        self.duel_button = Button(20, 660, 300, 40, "Classic cannon duel (M1)")
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

    def start_battle(self, roster, ai=None):
        """Start a match. `roster` is None for the classic cannon duel; `ai` is the
        AIController playing RIGHT, or None if two people play."""
        self.battle = Battle(roster=roster)
        self.ai = ai
        self.begin_match()

    def rematch(self):
        """Play again with the same teams (also the R key)."""
        self.battle.reset()
        if self.ai is not None:
            self.ai.new_match()
        self.begin_match()

    def begin_match(self):
        self.state = "battle"
        self.selected = {"left": 0, "right": 0}
        self.ai_wait = 0
        self.explosions = []
        if self.battle.teams is None:
            self.log = []
            self.message = "LEFT cannon: aim, then press SPACE to fire."
        else:
            self.log = ["--- Round 1 ---"]
            self.message = "Choose a character, aim, then choose an action."
        self.refresh_buttons()

    def try_start(self):
        if not self.selection.is_complete():
            size = self.selection.team_size
            self.message = f"Each team needs exactly {size} character{'s' if size > 1 else ''}."
        elif self.selection.vs_ai:
            ai = AIController("right", self.selection.difficulty)
            roster = {"left": list(self.selection.picks["left"]),
                      "right": ai.pick_team(self.selection.team_size)}
            self.start_battle(roster, ai)
        else:
            self.start_battle(self.selection.roster())

    def is_ai_turn(self):
        """True while it is the computer's turn to act (it acts by itself in update())."""
        return (self.state == "battle" and self.ai is not None
                and self.battle.active_side == self.ai.side and self.battle.can_fire())

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
        if self.battle is None or self.battle.teams is None:
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
        """Ask the Battle to carry out an action for the chosen character."""
        if self.battle.teams is None:            # classic duel: only firing exists
            if action == "attack":
                self.battle.fire()
            return
        index = self.selected_index()
        reason = self.battle.why_not_allowed(index, action)
        if reason is not None:
            self.message = reason
            return
        self.battle.perform_action(index, action)

    # ----- input -------------------------------------------------------------------

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self.space_released = True
        elif event.type == pygame.KEYDOWN:
            self.handle_key(event.key, event.mod)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.handle_click(event.pos)

    def handle_key(self, key, mods):
        if key == pygame.K_ESCAPE:
            self.running = False
        elif self.state == "select":
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.try_start()
        elif key == pygame.K_r:
            self.rematch()
        elif self.state == "battle" and self.battle.can_fire() and not self.is_ai_turn():
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
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3) and self.battle.teams is not None:
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
        elif self.state == "battle":
            self.click_battle(pos)
        elif self.rematch_button.is_clicked(pos):
            self.rematch()
        elif self.change_teams_button.is_clicked(pos):
            self.state = "select"
            self.message = "Change the teams, then press START BATTLE."
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
        elif self.duel_button.is_clicked(pos):
            self.start_battle(None)

    def click_battle(self, pos):
        if self.battle.teams is None:
            return                                 # the classic duel uses only the keyboard
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
        if self.battle is not None and self.battle.teams is not None:
            index = self.selected_index()
            for action, button in self.action_buttons.items():
                button.enabled = (self.state == "battle" and not self.is_ai_turn()
                                  and self.battle.why_not_allowed(index, action) is None)

    # ----- update ------------------------------------------------------------------

    def update(self):
        if self.is_ai_turn():
            self.update_ai()
        if self.battle is not None and self.state != "select":
            self.battle.update()
            for event in self.battle.take_events():
                self.show_event(event)
            for explosion in self.explosions:
                explosion[2] += 1
            self.explosions = [e for e in self.explosions if e[2] < EXPLOSION_FRAMES]
        self.refresh_buttons()

    def update_ai(self):
        """On the computer's turn: wait AI_DELAY_FRAMES (so the player can see the turn
        change), then let the AIController act. Its action goes through the same
        Battle.perform_action() as the buttons, and its events are shown as usual."""
        self.ai_wait += 1
        if self.ai_wait < AI_DELAY_FRAMES:
            return
        self.ai_wait = 0
        plan = self.ai.take_turn(self.battle)
        if plan is not None:
            self.selected[self.ai.side] = plan.actor_index         # the panel shows who acted
            self.log = (self.log + [f"AI ({self.ai.difficulty.capitalize()}): {plan.reason}."])[-50:]

    def show_event(self, event):
        """React to one battle event: effects, the log, and the end of the game."""
        if event["type"] == "explosion":
            self.explosions.append([event["x"], event["y"], 0])
        elif event["type"] == "game_over":
            self.state = "result"
        lines = describe_event(event)
        if lines:
            self.log = (self.log + lines)[-50:]
            self.message = lines[-1]

    # ----- text shown on the battle screen --------------------------------------------

    def selected_info_lines(self):
        """The panel text about the character chosen to act."""
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
        if character.is_defending:
            status = "Defending until your next turn."
        elif self.ai is not None and self.battle.active_side == self.ai.side:
            status = "Played by the computer."
        else:
            status = "Click a character or press 1-3 to choose who acts."
        stats = (f"HP {character.hp}/{character.max_hp}   ATK {character.atk}   "
                 f"DEF {character.defense}   {exp_text}")
        return [f"{self.battle.active_side.upper()} TEAM: {character.name}   Level {character.level}",
                stats, special_text, status]

    def action_hint_lines(self):
        """The panel text under the action buttons: the aim and what SPECIAL would do."""
        cannon = self.battle.cannons[self.battle.active_side]
        character = self.selected_character()
        if self.battle.is_over():
            return ["The game is over: choose Rematch or Change teams."]
        if self.is_ai_turn():
            return [f"The computer ({self.ai.difficulty.capitalize()}) is choosing the RIGHT team's move..."]
        lines = [f"Aim: angle {cannon.angle}°, power {cannon.power}  (arrow keys, Shift = 5)"]
        if self.battle.projectile is not None:
            lines.append("The shot is in the air...")
            return lines
        reason = self.battle.why_not_allowed(self.selected_index(), "special")
        if reason is None:
            lines.append(f"SPECIAL = {character.SPECIAL_NAME}: {character.SPECIAL_DESCRIPTION}")
        else:
            lines.append(f"SPECIAL unavailable: {reason}.")
        if isinstance(character, Archer):
            lines.append("ATTACK and Power Shot fire with this aim. SPACE = ATTACK.")
        else:
            lines.append("ATTACK fires with this aim. SPACE = ATTACK.")
        return lines

    def result_title(self):
        if self.battle.winner == "draw":
            return "DRAW!"
        if self.battle.teams is None:
            return f"{self.battle.winner.upper()} WINS!"
        return f"{self.battle.winner.upper()} TEAM WINS!"

    def result_reason(self):
        if self.battle.winner == "draw":
            return "Both sides lost at the same time."
        loser = other_side(self.battle.winner)
        if self.battle.teams is not None and not self.battle.teams[loser].alive_characters():
            return f"Every {loser.upper()} character was defeated."
        return f"The {loser.upper()} castle reached 60% destruction."

    # ----- drawing: team selection ---------------------------------------------------------

    def draw(self):
        if self.state == "select":
            self.draw_selection()
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
            right_title = f"RIGHT TEAM   the computer picks {size} at START"
        else:
            right_title = f"RIGHT TEAM   {len(self.selection.picks['right'])}/{size} chosen"
        draw_text(self.screen, right_title, self.font, TEAM_COLORS["right"], topleft=(660, 180))
        for (side, role), rect in self.card_rects.items():
            self.draw_card(side, role, rect)
        draw_text(self.screen, self.message, self.small_font, TEXT_COLOR, center=(WINDOW_WIDTH // 2, 495))
        self.start_button.draw(self.screen, self.font)
        draw_text(self.screen, "Slot 1 stands nearest the castle. Both teams have the same size. "
                  "Enter = start, Esc = quit.", self.small_font, TEXT_COLOR,
                  center=(WINDOW_WIDTH // 2, 600))
        self.duel_button.draw(self.screen, self.small_font)

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
        draw_figure(self.screen, role, rect.centerx, rect.top + 38, direction(side), TEAM_COLORS[side])
        lines = [f"HP {role.BASE_HP}  ATK {role.BASE_ATK}  DEF {role.BASE_DEF}",
                 f"Castle damage: {role.BLOCK_DAMAGE}",
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

    # ----- drawing: the battlefield --------------------------------------------------

    def draw_battlefield(self):
        self.screen.fill(SKY_COLOR)
        pygame.draw.rect(self.screen, GROUND_COLOR, (0, GROUND_Y, WINDOW_WIDTH, PANEL_TOP - GROUND_Y))
        for side, castle in self.battle.castles.items():
            for block in castle.alive_blocks():
                rect = (block.x, block.y, block.size, block.size)
                pygame.draw.rect(self.screen, block_color(side, block.hp, block.max_hp), rect)
                pygame.draw.rect(self.screen, TEXT_COLOR, rect, 1)
        if self.battle.teams is not None:
            self.draw_characters()
        for side, cannon in self.battle.cannons.items():
            self.draw_cannon(cannon, is_active=(side == self.battle.active_side))
        if self.battle.can_fire():
            self.draw_aim_arrow(self.battle.cannons[self.battle.active_side])
        if self.battle.projectile is not None:
            shot = self.battle.projectile
            pygame.draw.circle(self.screen, SHOT_COLOR, (round(shot.x), round(shot.y)), 5)
        # An explosion is a circle that grows to the blast radius while fading from yellow to red.
        for x, y, age in self.explosions:
            progress = age / EXPLOSION_FRAMES
            radius = int(8 + (BLAST_RADIUS - 8) * progress)
            color = (255, int(220 - 150 * progress), int(80 - 60 * progress))
            pygame.draw.circle(self.screen, color, (round(x), round(y)), radius,
                               0 if progress < 0.5 else 4)

    def draw_characters(self):
        """Each character at its Team slot, with its name, HP bar and special cooldown."""
        acting_side = self.battle.active_side
        chosen = self.selected_index() if self.state == "battle" else None
        for side, team in self.battle.teams.items():
            for index, character in enumerate(team.characters):
                rect = pygame.Rect(team.character_rect(index))
                # Neighbours stand 45 px apart, so the middle slot's label sits higher.
                label_y = rect.top - 30 - (24 if index == 1 else 0)
                if character.is_alive():
                    if character.is_defending:
                        bubble = pygame.Surface((64, 64), pygame.SRCALPHA)
                        pygame.draw.circle(bubble, DEFEND_COLOR + (90,), (32, 32), 31)
                        pygame.draw.circle(bubble, DEFEND_COLOR + (220,), (32, 32), 31, 2)
                        self.screen.blit(bubble, bubble.get_rect(center=rect.center))
                    draw_figure(self.screen, type(character), rect.centerx, rect.top,
                                direction(side), TEAM_COLORS[side])
                    name_color = TEAM_COLORS[side]
                else:
                    # Defeated: a grey shape lying on the ground.
                    pygame.draw.rect(self.screen, DEFEATED_COLOR, (rect.left - 4, rect.bottom - 9, rect.width + 8, 9),
                                     border_radius=4)
                    name_color = DEFEATED_COLOR
                draw_text(self.screen, character.name, self.tiny_font, name_color,
                          center=(rect.centerx, label_y))
                bar = pygame.Rect(rect.centerx - 20, label_y + 8, 40, 6)
                pygame.draw.rect(self.screen, (60, 60, 60), bar)
                fill = (60, 190, 70) if character.hp * 2 > character.max_hp else (220, 120, 40)
                pygame.draw.rect(self.screen, fill, (bar.left, bar.top, hp_bar_width(character, bar.width), bar.height))
                if character.is_alive():                        # special cooldown, under the feet
                    if character.special_cooldown > 0:
                        draw_text(self.screen, f"wait {character.special_cooldown}", self.tiny_font,
                                  COOLDOWN_COLOR, center=(rect.centerx, GROUND_Y + 10))
                    else:
                        draw_text(self.screen, "ready", self.tiny_font, READY_COLOR,
                                  center=(rect.centerx, GROUND_Y + 10))
                if side == acting_side and index == chosen and character.is_alive():
                    pygame.draw.rect(self.screen, ACTIVE_RING_COLOR, rect.inflate(8, 8), 2)
                    tip_y = label_y - 10
                    pygame.draw.polygon(self.screen, ACTIVE_RING_COLOR,
                                        [(rect.centerx - 7, tip_y - 10), (rect.centerx + 7, tip_y - 10),
                                         (rect.centerx, tip_y)])

    def draw_cannon(self, cannon, is_active):
        # The barrel points along the cannon's angle, toward the enemy.
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

    def draw_hud(self):
        for side, position in (("left", {"topleft": (20, 15)}),
                               ("right", {"topright": (WINDOW_WIDTH - 20, 15)})):
            percent = int(self.battle.castles[side].destruction_percent())  # whole percent, rounded down
            draw_text(self.screen, f"{side.upper()} CASTLE  {percent}% destroyed",
                      self.font, TEXT_COLOR, **position)
        side = self.battle.active_side
        if self.battle.teams is None:                  # the classic duel's status line
            cannon = self.battle.cannons[side]
            if self.battle.is_over():
                status = "Game over"
            elif self.battle.projectile is not None:
                status = "Shot in flight..."
            else:
                status = f"Turn: {side.upper()}    Angle {cannon.angle}°    Power {cannon.power}"
            draw_text(self.screen, status, self.font, TEXT_COLOR, center=(WINDOW_WIDTH // 2, 27))
        elif self.battle.is_over():
            draw_text(self.screen, f"Round {self.battle.round_number}   -   GAME OVER",
                      self.font, TEXT_COLOR, center=(WINDOW_WIDTH // 2, 27))
        else:
            player = ""
            if self.ai is not None:
                player = "  (computer)" if side == self.ai.side else "  (you)"
            draw_text(self.screen, f"Round {self.battle.round_number}   -   {side.upper()} TEAM'S TURN{player}",
                      self.font, TEAM_COLORS[side], center=(WINDOW_WIDTH // 2, 27))
        draw_text(self.screen, self.message, self.small_font, TEXT_COLOR, center=(WINDOW_WIDTH // 2, 58))

    def draw_panel(self):
        pygame.draw.rect(self.screen, PANEL_COLOR, (0, PANEL_TOP, WINDOW_WIDTH, WINDOW_HEIGHT - PANEL_TOP))
        if self.battle.teams is None:
            lines = [("UP / DOWN: angle     LEFT / RIGHT: power     SHIFT: change by 5     "
                      "SPACE: fire     R: restart     ESC: quit"),
                     "Players take turns. A castle that reaches 60% destruction loses."]
            for i, line in enumerate(lines):
                draw_text(self.screen, line, self.small_font, HINT_COLOR,
                          center=(WINDOW_WIDTH // 2, PANEL_TOP + 45 + i * 30))
            return
        # Left: the character chosen to act.
        for i, line in enumerate(self.selected_info_lines()):
            color = TEAM_COLORS[self.battle.active_side] if i == 0 else LIGHT_TEXT
            if i == 0:
                color = tuple(min(255, c + 70) for c in color)      # brighter on the dark panel
            draw_text(self.screen, line, self.small_font, color, topleft=(20, PANEL_TOP + 12 + i * 30))
        # Middle: the three action buttons and what they will do.
        for button in self.action_buttons.values():
            button.draw(self.screen, self.font)
        y = PANEL_TOP + 62
        for line in self.action_hint_lines():
            for part in wrap_text(line, self.tiny_font, 390):
                draw_text(self.screen, part, self.tiny_font, LIGHT_TEXT, topleft=(450, y))
                y += 18
        # Right: the combat log.
        draw_text(self.screen, "Combat log   (R: restart, Esc: quit)", self.tiny_font, DIM_TEXT,
                  topleft=(860, PANEL_TOP + 8))
        for i, line in enumerate(self.log[-LOG_LINES:]):
            draw_text(self.screen, line, self.tiny_font, LIGHT_TEXT, topleft=(860, PANEL_TOP + 28 + i * 19))

    def draw_result(self):
        panel = pygame.Surface((660, 240), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 180))                                 # semi-transparent black
        self.screen.blit(panel, panel.get_rect(center=(WINDOW_WIDTH // 2, 250)))
        draw_text(self.screen, self.result_title(), self.big_font, (255, 255, 255),
                  center=(WINDOW_WIDTH // 2, 190))
        draw_text(self.screen, self.result_reason(), self.font, (230, 230, 230),
                  center=(WINDOW_WIDTH // 2, 250))
        self.rematch_button.draw(self.screen, self.font)
        self.change_teams_button.draw(self.screen, self.font)
        draw_text(self.screen, "R = rematch     Esc = quit", self.small_font, (220, 220, 220),
                  center=(WINDOW_WIDTH // 2, 362))


def open_window():
    """Start Pygame, open the game window and set up the keyboard. Returns the screen."""
    pygame.init()
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
