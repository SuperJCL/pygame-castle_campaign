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

Reflex Aim (M6.1, an experimental prototype, reflex_aim.py): chosen with "Aim" on the selection
screen (Classic is the default and works exactly as before). In Reflex Aim the active person's
barrel swings between 20 and 75 degrees by itself, and ATTACK or SPACE locks the angle shown at
that moment; power is set with the arrow keys or power slider. The swing stops while the controls are
locked. The computer opponent keeps its own aim search and never swings.

M6.2 (playability and presentation; no rule changed): a 2.5 s studio intro at launch (a click,
SPACE or Enter skips it); "Aim style" explained on the selection screen and named on the cover
screen; Reflex Aim's swing gauge with a lock mark that stays on the shooter's cannon; Classic
Aim's short path dots (V hides them, Battle.preview_path); action buttons named after the real
special, with a note and one line of help; Inner Wall / Outer Wall cover presets and a hover
preview of what a click removes; a short result for every shot (DIRECT HIT, COVER HIT, GROUND
IMPACT, OUT OF FIELD) with a mark where it landed; role portraits; a darker, clearer battlefield
floor; the panel in three groups; and a solid result panel.

Local two players (M6.2 rework, after a playtest): each team has its own keys, so nobody has to
reach across: LEFT aims with W/S, sets the power with D (more) / A (less) and fires with F; RIGHT
uses Up/Down, Left (more) / Right (less) and Enter. The power keys add power toward the middle of the
field. Against the computer the person keeps the arrow keys and SPACE. A fire key that is held down
fires once: it must be let go before it fires again (also across a turn, or from the cover screen).

M6.3 (six roles): Gunner, Bombardier and Medic join Knight, Archer and Engineer; each team still picks
1-3 different roles, now from six compact cards (3 x 2), with the specials explained in the roster
box under them. A Triple Volley or an Airburst is one run to the cannon and one attack: its shells fly
together (an Airburst shell splits at the top of its arc, with a flash), each one explodes on its
own, and the top line sums the whole attack up. Field Dressing names its target and the HP before it
is used. Classic Aim's dots show the path of the center shell.

M6.4 (five aids, no rule changed): on its turn each team sees its own last shot that has landed
("Last shot · 45° / 83 · COVER HIT", ShotRecord) and a faint ring where its center shell landed; a
gold marker under the HUD follows shells above the top of the window; R during a match pauses it
and asks Restart / Continue (the whole match waits; holding R never restarts); the computer thinks
ahead during its 40-frame pause (AIController.thinking_ahead), so its decision frame is short; and
Practice on the selection screen opens a practice range (Archer, Gunner, Bombardier against fixed
targets that reset after every shot; Back returns to the selection as it was).

Sound (M4.2-A, sound.py): effects made in code play for Battle events (a shot, an explosion,
cover hit or destroyed, a Defend or Rally (M5.2-A), a level-up, the result). M turns the sound off and on; without an audio
device the game is silent and works the same.

Run from the project folder:   python main.py
"""

import math
import time

import pygame

from ai import DIFFICULTY_SETTINGS, AIController, aim_cannon
from animation import (
    FIRE,
    FIRE_FRAMES,
    RUN_TO_CANNON,
    CannonRun,
    PendingShot,
    fires_the_cannon,
)
from battle import (
    CHARACTER_HEIGHT,
    FIELD_WIDTH,
    MAX_POWER,
    MAX_TEAM_SIZE,
    MIN_POWER,
    ROUND_LIMIT,
    SLOT_X,
    Battle,
    Cannon,
    direction,
    other_side,
)
from battle_feedback import ShotRecord, attack_summary, describe_event
from castle import (
    BLOCK_SIZE,
    COLUMN_X,
    DEFAULT_LAYOUT,
    GROUND_Y,
    MAX_BLOCKS,
    SLOT_COUNT,
    layout_problem,
    place_block,
    remove_block,
    slot_position,
)
from characters import (
    ARCHETYPES,
    MAX_LEVEL,
    Archer,
    Bombardier,
    Engineer,
    Gunner,
    Knight,
    Medic,
)
from drawing import (
    ACTIVE_RING_COLOR,
    AIM_COLOR,
    BUTTON_OFF,
    CANNON_COLOR,
    CLOSED_SLOT_COLOR,
    COOLDOWN_COLOR,
    DAMAGE_COLOR,
    DEFEATED_COLOR,
    DEFEND_COLOR,
    DIM_TEXT,
    DRAW_COLOR,
    FLASH_COLOR,
    FLASH_EDGE,
    GROUND_COLOR,
    GUARD_COLOR,
    LABEL_COLORS,
    LIGHT_TEXT,
    OPEN_SLOT_COLOR,
    PANEL_COLOR,
    POWER_SHOT_COLOR,
    READY_COLOR,
    SHOT_COLOR,
    SKY_COLOR,
    TEAM_COLORS,
    TEXT_COLOR,
    TRAIL_COLOR,
    WOOD,
    Button,
    block_color,
    draw_block,
    draw_figure,
    draw_firing_figure,
    draw_outlined_text,
    draw_rubble_outline,
    draw_running_figure,
    draw_text,
    hp_bar_color,
    hp_bar_width,
    wrap_text,
)
from drawing import (
    EMBLEM_COLOR,
    EMBLEM_Y,
    draw_badge,
    draw_emblem,
    draw_plate,
    make_background,
)  # M4.2-A
from drawing import EXPIRED_COLOR, GUARD_STRIKE_COLOR, draw_guard_mark  # M4.2-B
from drawing import BRASS, PANEL_EDGE, load_valley_art, make_menu_background
from drawing import (
    INTRO_COLOR,
    OUTLINE,
    PORTRAIT_BACK,
    arc_point,
    chip_rect,  # M6.2
    draw_chip,
    draw_contact_shadow,
    draw_path_dots,
    draw_six_seal,
    draw_swing_gauge,
)
from drawing import (
    CARD_PORTRAIT_SIZE,
    HEAL_COLOR,
    card_portrait,
    draw_marked_shell,  # M6.3
    draw_split_flash,
    draw_spread_icon,
)
from setup_choices import COVER_PRESETS, PRESET_NOTES, CoverSetup, TeamSelection
from sound import BUFFER, SAMPLE_RATE, SoundBoard
from reflex_aim import SWING_HIGH, SWING_LOW, AimSwing  # M6.1 (experimental)

WINDOW_WIDTH = FIELD_WIDTH  # 1280
WINDOW_HEIGHT = 720
FPS = 60
AI_DELAY_FRAMES = 40  # the computer waits this long (2/3 s) before it acts
# M6.4: during that pause the computer thinks ahead (AIController.thinking_ahead), at most this long
# in one frame, so a frame still fits in 1/60 s with the drawing.
AI_THINK_SECONDS = 0.010
EXPLOSION_FRAMES = 20  # how long an explosion stays on screen
EXPLOSION_ALPHA = 160  # explosions are see-through (0-255), so the target stays visible
FLOAT_FRAMES = 60  # a floating damage number stays 1 s, rising slowly
TRAIL_LENGTH = 12  # dots behind a flying shot
LOG_LINES = 5  # combat-log lines shown at most (fewer if the last result wraps)
PANEL_TOP = 580  # the control panel fills the bottom of the window
COVER_HELP_TOP = 122  # the placement screen's instructions start at this y ...
COVER_HELP_STEP = 26  # ... one line every 26 px
AIM_DESCRIPTIONS = {
    "classic": "Up/Down set the angle. Press Space to fire.",  # M6.2: always shown
    "reflex": "The cannon swings. Press Space to lock and fire.",
}  # under "Aim style"
TWO_PLAYER_AIM_DESCRIPTIONS = {
    "classic": "Each team aims with its own keys. F (left) or Enter (right) fires.",
    "reflex": "The cannon swings. F (left) or Enter (right) locks and fires.",
}
SWING_MARK_RADIUS = (
    58  # Reflex Aim (M6.2): the swing gauge's arc, this far from the pivot
)
AIM_ARROW_MIN, AIM_ARROW_MAX = (
    40,
    96,
)  # tip distance from the pivot at minimum and maximum power
PATH_STEPS, PATH_EVERY = (
    24,
    4,
)  # Classic Aim's path dots: one every 4 physics steps, for 24 steps

# M6.2: the studio intro, once when the game starts: fade in, stay, fade out (2.5 s at 60 FPS:
# 0.5 s, 1.5 s, 0.5 s; first 1.2 s, lengthened after a playtest request).
STUDIO_NAME = "DOUBLE SIX STUDIO"
INTRO_FADE_IN, INTRO_HOLD, INTRO_FADE_OUT = 30, 90, 30
INTRO_FRAMES = INTRO_FADE_IN + INTRO_HOLD + INTRO_FADE_OUT
INTRO_SKIP_KEYS = (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER)
SEAL_SIZE = 76
SEAL_CENTERS = ((588, 300), (692, 300))

REMOVE_COLOR = (235, 70, 55)  # the outline of the blocks a click would remove

IMPACT_COLORS = {
    "character": (235, 70, 55),
    "block": (120, 190, 255),
    "ground": (240, 200, 120),
}
SHOT_RIM = (
    245,
    245,
    240,
)  # a light ring round a plain shot, so it shows on dark scenery

# M6.2: the panel in three groups (who acts, what to do, what happened), with gaps between them.
PANEL_GROUPS = {
    "actor": pygame.Rect(12, PANEL_TOP + 8, 368, 128),
    "controls": pygame.Rect(392, PANEL_TOP + 8, 496, 128),
    "log": pygame.Rect(900, PANEL_TOP + 8, 368, 128),
}
GROUP_COLOR = (31, 43, 56)
CONTROL_X = 404  # the middle group: buttons, then ANGLE / POWER, then one help line
POWER_X = 672
AIM_LABEL_Y = PANEL_TOP + 58
AIM_VALUE_Y = PANEL_TOP + 70
HINT_Y = PANEL_TOP + 104
HINT_WIDTH = 472
RESULT_BADGE_RADIUS = 22

# M6.2 rework (local two players): each team has its own keys, and the power keys add power toward
# the middle of the field. Against the computer the person keeps the arrow keys and SPACE.
PVP_KEYS = {
    "left": {
        "up": pygame.K_w,
        "down": pygame.K_s,
        "more": pygame.K_d,
        "less": pygame.K_a,
        "fire": (pygame.K_f,),
    },
    "right": {
        "up": pygame.K_UP,
        "down": pygame.K_DOWN,
        "more": pygame.K_LEFT,
        "less": pygame.K_RIGHT,
        "fire": (pygame.K_RETURN, pygame.K_KP_ENTER),
    },
}
PVAI_KEYS = {
    "up": pygame.K_UP,
    "down": pygame.K_DOWN,
    "more": pygame.K_RIGHT,
    "less": pygame.K_LEFT,
    "fire": (pygame.K_SPACE,),
}
# What the panel calls those keys: (angle, power, fire). Pygame's built-in font has no arrow signs.
KEY_NAMES = {
    "computer": ("Up/Down", "Left/Right", "SPACE"),
    "left": ("W/S", "D+ / A−", "F"),
    "right": ("Up/Down", "Left+ / Right−", "Enter"),
}
FIRE_KEYS = (pygame.K_SPACE, pygame.K_f, pygame.K_RETURN, pygame.K_KP_ENTER)
# Keys that act once per press: they are remembered as held until they are let go (handle_key).
# M6.4: R too, so holding R can't answer the Restart question it has just opened.
ONCE_KEYS = FIRE_KEYS + (pygame.K_r, pygame.K_ESCAPE)
CONTINUE_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_ESCAPE)

# M6.3: six roles, so each team's cards are 3 columns x 2 rows of compact cards. A card names the
# special; the team's roster box under the cards explains it.
CARD_SIZE = (180, 128)
CARD_STEP = (190, 136)  # from one card to the next, across and down
CARD_GRID = {
    "left": (50, 222),
    "right": (670, 222),
}  # the top-left corner of each team's first card
ROSTER_BOX_TOP, ROSTER_BOX_HEIGHT = 494, 52
SELECT_MESSAGE_Y = 560
SPLIT_FLASH_FRAMES = 18  # how long an Airburst's split flash stays on screen
SHOT_STYLES = {
    Archer: "power",
    Gunner: "volley",
    Bombardier: "airburst",
}  # how a special's shells look
SHELL_SIZES = {"attack": 5, "volley": 4, "airburst": 3}  # radius of a plain shell
# M6.4: the faint ring where a team's last center shell landed (shown on that team's turn).
LAST_MARK_RADIUS = 9
LAST_MARK_ALPHA = 190  # 0-255: see-through, so it is never mistaken for a real impact
# M6.4: the practice range (Practice on the selection screen). The three roles whose shots differ
# most shoot at a fixed target team behind the default cover; after every shot the targets, the
# cover and the specials are new again. One shot can never defeat a target (strongest hit 60, the
# weakest target has 90 HP), so a practice never ends by itself.
PRACTICE_SIDE = "left"
PRACTICE_ROSTER = {"left": [Archer, Gunner, Bombardier], "right": [Knight, Archer, Engineer]}
PRACTICE_LAYOUTS = {"left": DEFAULT_LAYOUT, "right": DEFAULT_LAYOUT}
PRACTICE_NO_DEFEND = "Practice range: shots only. DEFEND is for matches."
# M6.4: a shell above the top of the window is still flying (it falls back). A small gold
# triangle under the HUD follows it from side to side, with "Shell above view" under it.
ABOVE_Y = 80  # the tip of the triangle: under the turn banner and the message line
ABOVE_COLOR = BRASS
# ----- small helpers -------------------------------------------------------------


def slot_rect(side, slot):
    """The clickable square of cover slot `slot` (0-7) of `side`: exactly where its block stands."""
    return pygame.Rect(slot_position(side, slot), (BLOCK_SIZE, BLOCK_SIZE))


def guard_badge_rect(side):
    """Where the GUARDED badge of `side`'s cover is drawn: just above the higher cover row,
    centred over the four slot columns, clear of the characters and their HP bars, the
    cannon and the HUD. The two sides are mirror images."""
    center_x = COLUMN_X["left"][0] + 2 * BLOCK_SIZE  # 236: the middle of the columns
    if side == "right":
        center_x = WINDOW_WIDTH - center_x  # 1044
    badge = pygame.Rect(0, 0, 84, 20)
    badge.center = (
        center_x,
        GROUND_Y - 2 * BLOCK_SIZE - 20,
    )  # y 476: above the raised row
    return badge


def keep_off_cover(side, plate):
    """Move a name plate toward the edge of the screen if it would reach over its team's cover
    columns (M6.3: "Bombardier", the longest name, stands in the front slot right next to them)."""
    if side == "left":
        plate.right = min(plate.right, min(COLUMN_X["left"]))
    else:
        plate.left = max(plate.left, max(COLUMN_X["right"]) + BLOCK_SIZE)
    return plate


def result_banner_rect():
    """The coloured title band of the result overlay: the winner's colour, or DRAW_COLOR."""
    return pygame.Rect(310, 120, 660, 90)


def pause_panel_rect():
    """The pause menu over the current match."""
    return pygame.Rect(320, 200, 640, 196)


def muzzle_point(cannon):
    """Centre of the muzzle flash: just past the tip of the 24 px barrel, along its angle."""
    radians = math.radians(cannon.angle)
    return (
        round(cannon.x + direction(cannon.side) * 30 * math.cos(radians)),
        round(cannon.y - 30 * math.sin(radians)),
    )


class Game:
    """Connects the mouse, keyboard and screen to the team selection, the cover placement
    and one Battle.

    ai_seed: a number makes the computer's choices (team, cover, moves) repeatable; the
    tests use it. None (the real game) gives a different computer opponent every time.
    intro: True plays the studio intro first (M6.2; main() asks for it, the tests mostly don't).
    """

    def __init__(self, screen, ai_seed=None, intro=False):
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
        self.banner_font.set_bold(
            True
        )  # the turn banner stands out from the other HUD text
        self.aim_font = pygame.font.Font(
            None, 40
        )  # M6.2: the angle and power, the biggest panel text
        art = load_valley_art(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.background = make_background(WINDOW_WIDTH, PANEL_TOP, GROUND_Y, art)
        self.menu_background = make_menu_background(
            WINDOW_WIDTH, WINDOW_HEIGHT, art, self.background
        )
        self.power_bar = pygame.Rect(POWER_X + 52, PANEL_TOP + 79, 150, 10)
        self.dragging_power = False
        self.running = True
        self.held_keys = (
            set()
        )  # fire keys held down now: a held key fires only once (handle_key)
        self.state = "select"
        self.selection = TeamSelection()
        self.setup = CoverSetup()
        self.placing = "left"  # the team whose cover is being placed (state "cover")
        self.battle = None
        self.ai = None  # the AIController playing RIGHT, or None (two players)
        self.ai_wait = 0  # frames the computer has waited on this turn
        self.ai_thoughts = None  # M6.4: its thinking ahead on this turn (a generator), or None
        self.cannon_run = (
            CannonRun()
        )  # an attacking character's run to the cannon and back (M3.4-C)
        self.aim_mode = (
            "classic"  # M6.1: the Aim mode of the current match (from the selection)
        )
        self.swings = {
            "left": AimSwing(),
            "right": AimSwing(),
        }  # Reflex Aim: each cannon's swing
        self.sounds = (
            SoundBoard()
        )  # sound effects (M4.2-A); silent if there is no audio device
        self.standing_blocks = {}  # standing blocks per side, to hear when one is destroyed
        self.selected = {"left": 0, "right": 0}  # slot of the character chosen to act
        self.explosions = []  # each one is [x, y, age in frames]
        self.floaters = []  # floating damage numbers: [x, y, text, colour, age in frames]
        self.trails = {}  # each flying shell's last positions (drawn as dots), by shell
        self.shot_style = "attack"  # how the flying shells look: "power", "volley", "airburst" (SHOT_STYLES)
        # M6.3
        self.shot_name = (
            None  # "TRIPLE VOLLEY" or "AIRBURST" while such an attack flies, else None
        )
        self.split_flashes = []  # where an Airburst shell split: [x, y, age in frames]
        self.attack_events = []  # the explosion and miss events of the attack in flight (its summary)
        self.attack_destroyed = 0  # blocks that attack has destroyed so far
        self.log = []  # combat-log lines, newest last
        # M6.2
        self.locked_shot = None  # Reflex Aim: the PendingShot whose angle was locked, until its attack is over
        self.show_path = True  # Classic Aim's path dots (V switches them)
        self.impacts = []  # where shots landed: [x, y, kind, age in frames]
        self.last_result = (
            None  # the last shot's result, e.g. "COVER HIT · Archer shielded"
        )
        # M6.4: each team's last shot that has landed (a ShotRecord), and the one in the air.
        self.last_shots = {"left": None, "right": None}
        self.flying_record = None
        self.match_paused = False  # the match waits for an answer from the pause menu
        self.practice = False  # M6.4: True in the practice range (state "battle")
        self.intro_frame = (
            0 if intro else INTRO_FRAMES
        )  # the studio intro plays once, at launch
        self.intro_card = self.make_intro_card() if intro else None
        self.message = "Click characters to add them to a team (click again to remove)."
        self.make_buttons()
        self.refresh_buttons()

    def make_buttons(self):
        # Team selection screen.
        self.mode_buttons = {
            "ai": Button(290, 72, 180, 38, "Player vs AI"),
            "pvp": Button(480, 72, 180, 38, "Two players"),
        }
        self.difficulty_buttons = {
            level: Button(800 + i * 110, 72, 100, 38, level.capitalize())
            for i, level in enumerate(DIFFICULTY_SETTINGS)
        }
        self.size_buttons = [
            Button(290 + i * 125, 120, 115, 38, f"{n} v {n}")
            for i, n in enumerate(range(1, MAX_TEAM_SIZE + 1))
        ]
        self.aim_buttons = {
            "classic": Button(800, 120, 155, 38, "Classic"),  # M6.1
            "reflex": Button(965, 120, 155, 38, "Reflex"),
        }
        self.card_rects = {}
        for side, (
            first_x,
            first_y,
        ) in CARD_GRID.items():  # M6.3: 3 columns x 2 rows per team
            for i, role in enumerate(ARCHETYPES):
                x, y = (
                    first_x + (i % 3) * CARD_STEP[0],
                    first_y + (i // 3) * CARD_STEP[1],
                )
                self.card_rects[(side, role)] = pygame.Rect((x, y), CARD_SIZE)
        self.start_button = Button(515, 576, 250, 46, "PLACE COVER", primary=True)
        self.practice_button = Button(785, 576, 150, 46, "Practice")  # M6.4
        # M6.4: in the practice range the right panel group holds its own three buttons.
        log = PANEL_GROUPS["log"]
        self.practice_buttons = {
            "classic": Button(log.left + 12, PANEL_TOP + 72, 108, 38, "Classic"),
            "reflex": Button(log.left + 128, PANEL_TOP + 72, 108, 38, "Reflex"),
            "back": Button(log.left + 244, PANEL_TOP + 72, 112, 38, "Back"),
        }
        # Cover placement screen (M6.2: two presets on the left, Back and the next step on the right).
        self.preset_buttons = {
            name: Button(40 + i * 174, PANEL_TOP + 36, 160, 42, name)
            for i, name in enumerate(COVER_PRESETS)
        }
        self.back_button = Button(744, PANEL_TOP + 36, 150, 44, "Back")
        self.confirm_button = Button(
            908, PANEL_TOP + 36, 250, 44, "Start Battle", primary=True
        )
        # Battle screen: the middle group of the panel (M6.2: SPECIAL is named after the real skill).
        self.action_buttons = {
            "attack": Button(
                CONTROL_X, PANEL_TOP + 16, 150, 38, "ATTACK", primary=True
            ),
            "defend": Button(CONTROL_X + 161, PANEL_TOP + 16, 150, 38, "DEFEND"),
            "special": Button(CONTROL_X + 322, PANEL_TOP + 16, 150, 38, "SPECIAL"),
        }
        # Result overlay.
        self.rematch_button = Button(430, 300, 200, 46, "Rematch", primary=True)
        self.change_teams_button = Button(650, 300, 200, 46, "Change teams")
        # Pause menu: Continue is the default, in gold.
        self.continue_button = Button(338, 296, 190, 46, "Continue", primary=True)
        self.restart_button = Button(545, 296, 190, 46, "Restart")
        self.main_menu_button = Button(752, 296, 190, 46, "Main Menu")

    # ----- starting matches ------------------------------------------------------

    def start_battle(self, roster, layouts, ai=None):
        """Start a match. `ai` is the AIController playing RIGHT, or None if two people play."""
        self.battle = Battle(roster=roster, layouts=layouts)
        self.ai = ai
        self.aim_mode = (
            self.selection.aim_mode
        )  # kept for every rematch with these teams
        self.begin_match()
        if ai is not None:
            self.log.append(
                f"AI ({ai.difficulty.capitalize()}) placed {len(layouts['right'])} cover blocks."
            )

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
        self.match_paused = False  # M6.4
        self.cannon_run.cancel()  # a rematch (R) mid-run: nothing is fired later
        self.sounds.stop()  # nothing from the last match keeps playing
        self.standing_blocks = {
            side: len(castle.alive_blocks())
            for side, castle in self.battle.castles.items()
        }
        self.selected = {"left": 0, "right": 0}
        self.ai_wait = 0
        self.ai_thoughts = None  # M6.4: no thinking from the last match goes on
        if self.ai is not None:
            self.ai.forget()
        self.explosions = []
        self.floaters = []
        self.trails = {}
        self.split_flashes = []  # M6.3: nor an Airburst's flash, nor the last attack's summary
        self.attack_events = []
        self.attack_destroyed = 0
        self.impacts = []  # M6.2: nothing from the last match stays on screen
        self.last_result = None
        self.last_shots = {"left": None, "right": None}  # M6.4: nor its last shots
        self.flying_record = None
        self.locked_shot = None
        for (
            side,
            swing,
        ) in self.swings.items():  # Reflex Aim: every swing starts again at its
            swing.reset()  # low limit, and each person's barrel with it
            if self.aim_mode == "reflex" and self.is_human_side(side):
                cannon = self.battle.cannons[side]
                aim_cannon(cannon, swing.angle(), cannon.power)
        first = f"{self.battle.first_side.upper()} team moves first."
        self.log = ["--- Round 1 ---", first]
        if self.ai is not None and self.battle.first_side == self.ai.side:
            self.message = f"The computer ({self.ai.side.upper()}) moves first."  # nothing to do yet
        elif self.aim_mode == "reflex":
            fire = self.key_names()[2]
            self.message = (
                first
                + f" Choose a character, then time your shot: ATTACK or {fire} locks the angle."
            )
        else:
            self.message = first + " Choose a character, aim, then choose an action."
        self.refresh_buttons()

    # ----- the practice range (M6.4) ----------------------------------------------------

    def start_practice(self):
        """Practice (selection screen): the battlefield and shooting of a match with PRACTICE_ROSTER
        and the default cover, no computer, and the aim style chosen on the selection screen. The
        selection's choices are not touched, so Back returns to them exactly."""
        self.practice = True
        self.battle = Battle(roster=PRACTICE_ROSTER, layouts=PRACTICE_LAYOUTS)
        self.ai = None
        self.aim_mode = self.selection.aim_mode
        self.begin_match()
        self.message = (
            "Practice: choose Archer, Gunner or Bombardier (1-3), aim and fire. "
            "Targets reset after every shot."
        )
        self.log = ["--- Practice range ---"]

    def reset_range(self):
        """After every practice shot (and on R): the targets, the cover and the shooters' specials
        are new again (Battle.reset) and LEFT is to move. The aim and the last shot stay, to
        compare the next shot with."""
        cannon = self.battle.cannons[PRACTICE_SIDE]
        angle, power = cannon.angle, cannon.power
        self.battle.reset(first_side=PRACTICE_SIDE)
        aim_cannon(self.battle.cannons[PRACTICE_SIDE], angle, power)
        self.standing_blocks = {
            side: len(castle.alive_blocks())
            for side, castle in self.battle.castles.items()
        }

    def set_practice_aim(self, aim_mode):
        """Classic or Reflex, for the practice range only (the selection keeps its own choice)."""
        self.aim_mode = aim_mode
        swing = self.swings[PRACTICE_SIDE]
        swing.reset()
        if aim_mode == "reflex":  # the barrel starts swinging from its low limit
            cannon = self.battle.cannons[PRACTICE_SIDE]
            aim_cannon(cannon, swing.angle(), cannon.power)
        self.message = f"Practice with {aim_mode.capitalize()} Aim."

    def leave_practice(self):
        """Back (or Backspace): to the selection screen, with every choice as it was left."""
        self.return_to_menu("Back from practice: the team choices are as you left them.")

    def return_to_menu(self, message="Back at the main menu. Your setup is kept for this session."):
        """End the active session and preserve the roster and cover choices."""
        self.match_paused = False
        self.practice = False
        self.cannon_run.cancel()
        self.sounds.stop()
        if self.ai is not None:
            self.ai.forget()
        self.ai_thoughts = None
        self.ai = None
        self.battle = None
        self.locked_shot = None
        self.flying_record = None
        self.trails.clear()
        self.dragging_power = False
        self.state = "select"
        self.message = message

    def try_start(self):
        """PLACE COVER (or Enter) on the selection screen: go on to the LEFT cover screen."""
        if not self.selection.is_complete():
            size = self.selection.team_size
            self.message = (
                f"Each team needs exactly {size} character{'s' if size > 1 else ''}."
            )
        else:
            self.begin_cover("left")

    # ----- cover placement -----------------------------------------------------------

    def begin_cover(self, side):
        self.state = "cover"
        self.placing = side
        # M6.2: the button says what comes next.
        two_steps = side == "left" and not self.selection.vs_ai
        self.confirm_button.label = "Next: Right Cover" if two_steps else "Start Battle"
        self.message = (
            f"{side.upper()} team: pick a preset or click the slots, then press "
            f"{self.confirm_button.label}."
        )

    def click_cover(self, pos):
        for slot in range(SLOT_COUNT):
            if slot_rect(self.placing, slot).collidepoint(pos):
                self.message = self.setup.click_slot(self.placing, slot)
                return
        for name, button in self.preset_buttons.items():  # M6.2
            if button.is_clicked(pos):
                self.message = self.setup.apply_preset(self.placing, name)
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
        if (
            problem is not None
        ):  # clicks always keep the layout legal; this is a safety net
            self.message = f"This cover can't be used: {problem}."
            return
        if self.placing == "left" and not self.selection.vs_ai:
            self.begin_cover("right")
        elif self.selection.vs_ai:
            ai = AIController("right", self.selection.difficulty, seed=self.ai_seed)
            roster = {
                "left": list(self.selection.picks["left"]),
                "right": ai.pick_team(self.selection.team_size),
            }
            self.start_battle(roster, {"left": layout, "right": ai.choose_layout()}, ai)
        else:
            self.start_battle(self.selection.roster(), dict(self.setup.layouts))

    def is_ai_turn(self):
        """True while it is the computer's turn to act (it acts by itself in update())."""
        return (
            self.state == "battle"
            and self.ai is not None
            and self.battle.active_side == self.ai.side
            and self.battle.can_fire()
        )

    def is_human_side(self, side):
        """True if a person plays `side` (both sides in two-player mode)."""
        return self.ai is None or side != self.ai.side

    def aim_swings(self):
        """Reflex Aim (M6.1): True while the active person's barrel swings, i.e. while that person
        may act. It stops whenever the controls are locked, so the computer's never swings."""
        return self.aim_mode == "reflex" and not self.controls_locked()

    def swing_aim(self):
        """One frame of Reflex Aim: the active team's swing moves on and its cannon turns with it."""
        side = self.battle.active_side
        swing, cannon = self.swings[side], self.battle.cannons[side]
        swing.step()
        aim_cannon(cannon, swing.angle(), cannon.power)

    def swing_gauge(self):
        """What Reflex Aim's gauge shows (M6.2): (side, angle, locked), or None for no gauge.

        A locked angle belongs to the shot, not to the turn: it is drawn on the cannon of
        locked_shot.side (the PendingShot) until that attack is over, even if the shot has landed
        and the turn has passed while the shooter runs back. Otherwise the gauge follows the
        swinging barrel, which only swings while a person may act (aim_swings), so the
        computer's cannon never gets one, and Classic Aim never draws one."""
        if self.aim_mode != "reflex" or self.state != "battle":
            return None
        if self.locked_shot is not None:
            return self.locked_shot.side, self.locked_shot.angle, True
        if self.aim_swings():
            side = self.battle.active_side
            return side, self.battle.cannons[side].angle, False
        return None

    def aim_status(self):
        """The short status beside the angle in the panel (M6.2), or "" for none:
        "REFLEX · SWINGING", "REFLEX · LOCKED 47°" (the real locked angle) or "REFLEX · WAITING"
        (the last shooter is still running back); "THINKING" while the computer chooses; in
        Classic Aim, whether the path dots are on (V switches them)."""
        if self.battle.is_over():
            return ""
        if self.ai_thinking():
            return "THINKING"
        side = self.battle.active_side
        if not self.is_human_side(side):
            return ""  # the computer's run and shot
        if self.aim_mode == "classic":
            if self.controls_locked():
                return ""
            return "PATH ON · V" if self.show_path else "PATH OFF · V"
        if self.locked_shot is not None and self.locked_shot.side == side:
            return f"REFLEX · LOCKED {self.locked_shot.angle}°"
        return "REFLEX · SWINGING" if self.aim_swings() else "REFLEX · WAITING"

    def path_points(self):
        """Classic Aim's path dots (M6.2): where the next shot would be after every PATH_EVERY
        physics steps of its first PATH_STEPS (Battle.preview_path: the real step and collision
        check, nothing fired). Only on a person's Classic turn while they may aim; V hides them.
        The far end and any damage are never shown: judging those is the player's job."""
        if self.aim_mode != "classic" or not self.show_path or self.controls_locked():
            return []
        return self.battle.preview_path(self.battle.active_side, PATH_STEPS, PATH_EVERY)

    def controls_locked(self):
        """True while nobody may aim or act in the battle: a character is running to or from
        the cannon (M3.4-C), a shot is flying, the game is over, or it is the computer's turn."""
        return (
            self.state != "battle"
            or self.match_paused
            or self.cannon_run.is_busy()
            or not self.battle.can_fire()
            or self.is_ai_turn()
        )

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
        return self.battle.teams[self.battle.active_side].characters[
            self.selected_index()
        ]

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
        if (
            self.message != self.last_result
        ):  # M6.2: the last shot's result stays on top
            self.message = f"{character.name} is ready. Aim, then choose an action."

    def do_action(self, action):
        """Ask the Battle to carry out an action for the chosen character.

        ATTACK and Power Shot first send the character to the cannon (start_cannon_run): the
        shot is fired when it gets there. Defend, Rally and Repair happen at once."""
        if self.cannon_run.is_busy():
            return  # one action per turn: a character is already on its way
        if self.practice and action == "defend":  # M6.4: the practice range is for shots
            self.message = PRACTICE_NO_DEFEND
            return
        index = self.selected_index()
        reason = self.battle.why_not_allowed(index, action)
        if reason is not None:
            self.message = reason
            return
        side = self.battle.active_side
        if fires_the_cannon(self.battle.teams[side].characters[index], action):
            cannon = self.battle.cannons[side]
            shot = PendingShot(side, index, action, cannon.angle, cannon.power)
            self.start_cannon_run(shot)
            if (
                self.aim_mode == "reflex"
            ):  # the angle shown now is the one that will be fired
                self.locked_shot = (
                    shot  # M6.2: its lock mark stays until this attack is over
                )
                self.message += f" Angle locked at {cannon.angle}°."
                self.log = (
                    self.log
                    + [
                        f"{side.upper()} locked the angle at {cannon.angle}° "
                        f"(power {cannon.power})."
                    ]
                )[-50:]
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
            self.cannon_run.cancel()  # not possible in play, but never leave a ghost runner
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
            self.cannon_run.cancel()  # not possible in play; the log says why it was refused
        character = self.battle.teams[shot.side].characters[shot.actor_index]
        special = shot.action == "special"
        self.shot_style = (
            SHOT_STYLES.get(type(character), "attack") if special else "attack"
        )  # only how it is drawn
        self.shot_name = (
            character.SPECIAL_NAME.upper()
            if special and character.SPECIAL_SHELLS > 1
            else None
        )

    # ----- the studio intro (M6.2) ------------------------------------------------------

    def intro_playing(self):
        """True during the studio intro (the first INTRO_FRAMES frames after a launch)."""
        return self.intro_frame < INTRO_FRAMES

    def skip_intro(self):
        self.intro_frame = INTRO_FRAMES

    def make_intro_card(self):
        """The intro's picture, made once: two gold six-pip seals and STUDIO_NAME. Returns the
        seals and name alone (to fade in on the blue) and the whole picture (to fade out)."""
        layer = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        for center in SEAL_CENTERS:
            draw_six_seal(layer, center, SEAL_SIZE)
        draw_text(
            layer, STUDIO_NAME, self.title_font, BRASS, center=(WINDOW_WIDTH // 2, 392)
        )
        card = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT))
        card.fill(INTRO_COLOR)
        card.blit(layer, (0, 0))
        return layer, card

    def draw_intro(self):
        """Drawn over the selection screen: the seals and name fade in on deep blue, stay, then
        the whole picture fades out, uncovering the selection screen and its CASTLE SIEGE title.
        Only the transparency changes from frame to frame; nothing waits or blocks."""
        layer, card = self.intro_card
        frame = self.intro_frame
        if frame < INTRO_FADE_IN + INTRO_HOLD:
            self.screen.fill(INTRO_COLOR)
            layer.set_alpha(min(255, round(255 * (frame + 1) / INTRO_FADE_IN)))
            self.screen.blit(layer, (0, 0))
        else:
            card.set_alpha(round(255 * (INTRO_FRAMES - frame) / INTRO_FADE_OUT))
            self.screen.blit(card, (0, 0))

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
        self.message = (
            "Sound off. Press M to turn it back on."
            if self.sounds.muted
            else "Sound on."
        )

    def handle_event(self, event):
        if self.intro_playing():  # M6.2: during the intro input only skips it ...
            if event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            ):
                self.quit()  # ... (Esc and closing the window still quit)
            elif event.type == pygame.MOUSEBUTTONDOWN or (
                event.type == pygame.KEYDOWN and event.key in INTRO_SKIP_KEYS
            ):
                self.skip_intro()
            return  # nothing reaches the selection screen under it
        if event.type == pygame.QUIT:
            self.quit()
        elif event.type == pygame.KEYUP:
            self.held_keys.discard(event.key)
        elif event.type == pygame.KEYDOWN:
            self.handle_key(event.key, event.mod)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.handle_click(event.pos)
        elif event.type == pygame.MOUSEMOTION and self.dragging_power:
            if self.controls_locked() or not event.buttons[0]:
                self.dragging_power = False
            else:
                self.set_power_from_mouse(event.pos[0])
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.dragging_power = False
            self.held_keys.clear()  # a key let go while the window was in the background sends no KEYUP
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging_power = False

    def set_power_from_mouse(self, x):
        """Map the power bar to the same range the arrow keys use."""
        fraction = max(0, min(1, (x - self.power_bar.left) / self.power_bar.width))
        power = MIN_POWER + round(fraction * (MAX_POWER - MIN_POWER))
        cannon = self.battle.cannons[self.battle.active_side]
        cannon.adjust_power(power - cannon.power)

    def handle_key(self, key, mods):
        self.dragging_power = False
        # Key repeat is on for aiming. Track fire keys until KEYUP so a held Enter cannot
        # confirm more than one setup screen or fire when the right team's turn starts.
        fresh = key not in self.held_keys
        if key in ONCE_KEYS:
            self.held_keys.add(key)
        if self.match_paused:
            self.handle_pause_key(key, fresh)
        elif key == pygame.K_ESCAPE:
            if fresh:
                if self.practice:
                    self.leave_practice()
                elif self.state == "battle":
                    self.open_pause_menu()
                elif self.state == "result":
                    self.return_to_menu()
                else:
                    self.quit()
        elif key == pygame.K_m:
            self.toggle_sound()
        elif self.state == "select":
            if fresh and key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.try_start()
        elif self.state == "cover":
            if fresh and key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm_cover()
            elif key == pygame.K_BACKSPACE:
                self.back_from_cover()
        elif self.practice and key == pygame.K_BACKSPACE:  # M6.4: out of the practice range
            self.leave_practice()
        elif key == pygame.K_r:
            if fresh:  # M6.4: a held R acts once
                self.press_r()
        elif not self.controls_locked():
            self.handle_battle_key(key, mods, fresh)
        self.refresh_buttons()

    # ----- R: rematch, or ask first during a match (M6.4) ---------------------------

    def press_r(self):
        """R: after the match, a rematch at once (as before). During a match a press could throw
        the match away by mistake, so the match pauses and asks first (open_pause_menu). In the practice
        range there is nothing to lose: R resets it at once, even during a run or a flight."""
        if self.practice:
            self.cannon_run.cancel()  # nothing is fired later
            self.locked_shot = None
            self.reset_range()
        elif self.state == "result":
            self.rematch()
        else:
            self.open_pause_menu()

    def open_pause_menu(self):
        """Open the pause menu. Continue resumes from exactly the same frame."""
        self.match_paused = True
        self.dragging_power = False

    def keep_playing(self):
        """Continue (the default): the question closes and the match goes on where it stopped."""
        self.match_paused = False

    def confirm_restart(self):
        """Restart: the same rematch R always started (new HP, cover and turn; the other side
        moves first). Also cancels a run and a shell in the air (begin_match)."""
        self.match_paused = False
        self.rematch()

    def handle_pause_key(self, key, fresh):
        """A key while the question is open. A key still held down from before (not fresh)
        answers nothing: holding R opens the question once and never restarts. R pressed again
        restarts; Enter, Space or Esc continue. Backspace returns to the menu."""
        if key == pygame.K_m:
            self.toggle_sound()
        elif not fresh:
            return
        elif key == pygame.K_r:
            self.confirm_restart()
        elif key == pygame.K_BACKSPACE:
            self.return_to_menu()
        elif key in CONTINUE_KEYS:
            self.keep_playing()

    def handle_battle_key(self, key, mods, fresh=True):
        """Keys during a turn: aim, choose a character (1-3) and fire. Only the keys of the team to
        move work (battle_keys): in two-player mode each team has its own. `fresh`: False for a fire
        key that is still held down from before (see handle_key), which never fires."""
        keys = self.battle_keys()
        step = 5 if mods & pygame.KMOD_SHIFT else 1
        cannon = self.battle.cannons[self.battle.active_side]
        if key in (keys["up"], keys["down"]) and self.aim_mode == "reflex":
            self.message = (
                f"Reflex Aim: the angle swings by itself. "
                f"Press ATTACK or {self.key_names()[2]} to lock it."
            )
        elif key == keys["up"]:
            cannon.adjust_angle(step)
        elif key == keys["down"]:
            cannon.adjust_angle(-step)
        elif key == keys["more"]:
            cannon.adjust_power(step)
        elif key == keys["less"]:
            cannon.adjust_power(-step)
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
            self.select_actor(key - pygame.K_1)
        elif key == pygame.K_v:  # M6.2: Classic Aim's path dots on / off
            self.show_path = not self.show_path
            self.message = (
                "Path dots on (V hides them)."
                if self.show_path
                else "Path dots off (V shows them)."
            )
        elif key in keys["fire"] and fresh:
            self.do_action("attack")

    def battle_keys(self):
        """The keys of the team to move (M6.2 rework): its own in two-player mode (PVP_KEYS); against
        the computer, the person's arrow keys and SPACE (PVAI_KEYS). M6.4: the practice range uses
        the keys of the mode chosen on the selection screen (LEFT's own keys for two players)."""
        if self.uses_person_keys():
            return PVAI_KEYS
        return PVP_KEYS[self.battle.active_side]

    def key_names(self):
        """(angle, power, fire): what the panel calls the keys of the team to move."""
        if self.uses_person_keys():
            return KEY_NAMES["computer"]
        return KEY_NAMES[self.battle.active_side]

    def uses_person_keys(self):
        """True for the arrow keys and SPACE: against the computer, and in the practice range when
        "Player vs AI" is chosen on the selection screen."""
        return self.ai is not None or (self.practice and self.selection.vs_ai)

    def handle_click(self, pos):
        self.dragging_power = False
        self.refresh_buttons()  # decide using the situation right now
        if self.match_paused:
            if self.continue_button.is_clicked(pos):
                self.keep_playing()
            elif self.restart_button.is_clicked(pos):
                self.confirm_restart()
            elif self.main_menu_button.is_clicked(pos):
                self.return_to_menu()
        elif self.state == "select":
            self.click_selection(pos)
        elif self.state == "cover":
            self.click_cover(pos)
        elif self.state == "battle":
            if not self.controls_locked() and self.power_bar.inflate(
                14, 16
            ).collidepoint(pos):
                self.dragging_power = True
                self.set_power_from_mouse(pos[0])
            else:
                self.click_battle(pos)
        elif self.rematch_button.is_clicked(pos):
            self.rematch()
        elif self.change_teams_button.is_clicked(pos):
            self.return_to_menu("Change the teams, then press PLACE COVER.")
        self.refresh_buttons()

    def click_selection(self, pos):
        for mode, button in self.mode_buttons.items():
            if button.is_clicked(pos):
                self.selection.set_mode(vs_ai=(mode == "ai"))
                self.message = (
                    "You play LEFT; the computer picks and plays RIGHT."
                    if mode == "ai"
                    else "Two players: pick both teams, then take turns."
                )
        for level, button in self.difficulty_buttons.items():
            if button.is_clicked(pos):
                self.selection.difficulty = level
                self.message = f"Computer level: {level.capitalize()}."
        for size, button in enumerate(self.size_buttons, start=1):
            if button.is_clicked(pos):
                self.selection.set_team_size(size)
                self.message = (
                    f"{size} v {size}: each team picks {size} different character(s)."
                )
        for aim_mode, button in self.aim_buttons.items():
            if button.is_clicked(pos):
                self.selection.set_aim_mode(aim_mode)
                if not self.selection.vs_ai:  # two players: each team has its own keys
                    self.message = (
                        f"Reflex Aim: the barrel swings between {SWING_LOW}° and {SWING_HIGH}°; "
                        "ATTACK, F (left) or Enter (right) locks the angle."
                        if aim_mode == "reflex"
                        else "Classic Aim: LEFT aims with W/S and D/A, RIGHT with the arrow keys."
                    )
                else:
                    self.message = (
                        f"Reflex Aim: the barrel swings between {SWING_LOW}° and {SWING_HIGH}°; "
                        "ATTACK or SPACE locks the angle. The arrow keys set the power."
                        if aim_mode == "reflex"
                        else "Classic Aim: the arrow keys set the angle and the power."
                    )
        for (side, role), rect in self.card_rects.items():
            if rect.collidepoint(pos):
                refusal = self.selection.toggle(side, role)
                if refusal:
                    self.message = refusal
        if self.start_button.rect.collidepoint(pos):
            self.try_start()  # explains what is missing if incomplete
        elif self.practice_button.is_clicked(pos):  # M6.4
            self.start_practice()

    def click_battle(self, pos):
        if self.practice:  # M6.4: the practice range's own buttons (Back works at any time)
            for name, button in self.practice_buttons.items():
                if button.is_clicked(pos):
                    if name == "back":
                        self.leave_practice()
                    else:
                        self.set_practice_aim(name)
                    return
        if self.cannon_run.is_busy():
            return  # wait until the character is back in its slot
        if self.is_ai_turn():
            self.message = "The computer is playing the RIGHT team's turn."
            return
        for action, button in self.action_buttons.items():
            if button.is_clicked(pos):
                self.do_action(action)
                return
            if button.rect.collidepoint(pos):  # greyed out: say why (M4.2-B)
                reason = self.battle.why_not_allowed(self.selected_index(), action)
                if reason is not None:
                    self.message = reason[0].upper() + reason[1:] + "."
                return
        if not self.battle.can_fire():
            return  # can't change who acts while a shot flies
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
            button.chosen = level == self.selection.difficulty
            button.enabled = self.selection.vs_ai
        for size, button in enumerate(self.size_buttons, start=1):
            button.chosen = size == self.selection.team_size
        for aim_mode, button in self.aim_buttons.items():
            button.chosen = aim_mode == self.selection.aim_mode
        self.start_button.enabled = self.selection.is_complete()
        for (
            name,
            button,
        ) in self.preset_buttons.items():  # M6.2: the preset now in place
            button.chosen = self.setup.layouts[self.placing] == COVER_PRESETS[name]
        if self.practice:  # M6.4: the aim style can change only while the shooter may aim
            for name, button in self.practice_buttons.items():
                button.chosen = name == self.aim_mode
                button.enabled = name == "back" or not self.controls_locked()
        if self.battle is not None:
            index = self.selected_index()
            special = (
                self.battle.teams[self.battle.active_side]
                .characters[index]
                .SPECIAL_NAME
            )
            self.action_buttons["special"].label = (
                "SPECIAL" if self.ai_thinking() else special.upper()
            )
            for action, button in self.action_buttons.items():
                button.enabled = (
                    not self.controls_locked()
                    and self.battle.why_not_allowed(index, action) is None
                    and not (self.practice and action == "defend")  # M6.4
                )
                button.note = self.action_note(action)

    # ----- update ------------------------------------------------------------------

    def update(self):
        if self.intro_playing():
            self.intro_frame += 1  # M6.2: the intro's clock (60 frames a second)
        if self.match_paused:  # M6.4: the whole match waits for the answer
            self.refresh_buttons()
            return
        if self.cannon_run.is_busy():
            self.update_cannon_run()  # the controls and the computer wait for it
        elif self.is_ai_turn():
            self.update_ai()
        elif self.aim_swings():
            self.swing_aim()  # Reflex Aim (M6.1): only while a person may act
        if self.battle is not None and self.state in ("battle", "result"):
            self.battle.update()
            for event in self.battle.take_events():
                self.show_event(event)
            if self.practice and self.battle.active_side != PRACTICE_SIDE:
                self.reset_range()  # M6.4: the shot has landed (the turn passed): all back
            for explosion in self.explosions:
                explosion[2] += 1
            self.explosions = [e for e in self.explosions if e[2] < EXPLOSION_FRAMES]
            for floater in self.floaters:  # rise slowly, then disappear
                floater[1] -= 0.5
                floater[4] += 1
            self.floaters = [f for f in self.floaters if f[4] < FLOAT_FRAMES]
            for mark in self.impacts:  # M6.2: impact marks last as long as the numbers
                mark[3] += 1
            self.impacts = [m for m in self.impacts if m[3] < FLOAT_FRAMES]
            for flash in self.split_flashes:  # M6.3
                flash[2] += 1
            self.split_flashes = [
                f for f in self.split_flashes if f[2] < SPLIT_FLASH_FRAMES
            ]
            # Each flying shell keeps its own short trail (a shell that landed or split loses its own).
            self.trails = {
                shell: (self.trails.get(shell, []) + [(shell.x, shell.y)])[
                    -TRAIL_LENGTH:
                ]
                for shell in self.battle.projectiles
            }
            if (
                self.locked_shot is not None
                and not self.cannon_run.is_busy()
                and not self.battle.projectiles
            ):
                self.locked_shot = (
                    None  # M6.2: that attack is over (landed, runner back)
                )
        self.refresh_buttons()

    def update_ai(self):
        """On the computer's turn: wait AI_DELAY_FRAMES (so the player can see the turn
        change), then let the AIController choose. Defend, Rally and Repair are carried out
        at once. An attack or Power Shot takes the same run to the cannon as a person's and is
        carried out (AIController.carry_out -> Battle.perform_action) when the character gets
        there. Its events are shown as usual.

        M6.4: in the frames of the pause it already thinks ahead, a little in each frame
        (think_a_little), so on frame AI_DELAY_FRAMES choose() finds most shots in its memory and
        the window does not stop. If the thinking is not finished by then (a slow computer),
        choose() imagines the rest itself: the decision is the same, only that frame is longer."""
        if self.ai_thoughts is None:  # the first frame of its turn
            self.ai_thoughts = self.ai.thinking_ahead(self.battle)
        self.think_a_little()
        self.ai_wait += 1
        if self.ai_wait < AI_DELAY_FRAMES:
            return
        self.ai_wait = 0
        self.ai_thoughts = None
        plan = self.ai.choose(self.battle)
        if plan is None:
            return
        self.selected[self.ai.side] = plan.actor_index  # the panel shows who acts
        self.log = (
            self.log + [f"AI ({self.ai.difficulty.capitalize()}): {plan.reason}."]
        )[-50:]
        if plan.fires_a_shot():
            # The barrel turns to the aim now, while the character runs; the shot waits for it.
            aim_cannon(self.battle.cannons[self.ai.side], plan.angle, plan.power)
            self.start_cannon_run(
                PendingShot(
                    self.ai.side,
                    plan.actor_index,
                    plan.action,
                    plan.angle,
                    plan.power,
                    plan,
                )
            )
        else:
            self.ai.carry_out(self.battle, plan)

    def think_a_little(self):
        """M6.4: let the computer think ahead for at most AI_THINK_SECONDS of this frame. Each step
        of its thinking imagines one shot; the loop stops at the time limit and goes on from there
        on the next frame. When there is nothing left to think about, the loop ends at once."""
        stop = time.perf_counter() + AI_THINK_SECONDS
        for _ in self.ai_thoughts:
            if time.perf_counter() >= stop:
                break

    def show_event(self, event):
        """React to one battle event: effects, sounds, the log, and the end of the game.
        M6.2: a shot's explosion or miss also gives the short result on top (impact_summary),
        kept until the next action, and an impact mark where the Battle says it landed."""
        destroyed = 0
        if event["type"] == "fire":  # M6.3: a new attack: its summary starts empty
            self.attack_events, self.attack_destroyed = [], 0
            cannon = self.battle.cannons[event["side"]]  # M6.4: the aim it was fired with
            self.flying_record = ShotRecord(event["side"], cannon.angle, cannon.power)
        if (
            event["type"] == "explosion"
        ):  # (before play_event_sound counts the blocks again)
            target = other_side(event["side"])
            standing = len(self.battle.castles[target].alive_blocks())
            destroyed = max(0, self.standing_blocks.get(target, standing) - standing)
        self.play_event_sound(event)
        if event["type"] == "explosion":
            self.explosions.append(
                [event["x"], event["y"], 0, event["radius"]]
            )  # M6.3: its own blast
            self.impacts.append([event["x"], event["y"], event["kind"], 0])
            target = other_side(event["side"])
            for name in event["covered"]:
                self.add_floater(target, name, "shielded", GUARD_COLOR)
            for hit in event["characters_hit"]:
                self.add_floater(target, hit["name"], f"-{hit['damage']}", DAMAGE_COLOR)
                if hit["defeated"]:
                    self.add_floater(
                        target, hit["name"], "DEFEATED", DAMAGE_COLOR, below=True
                    )
        elif event["type"] == "split":  # M6.3: where the Airburst shell split
            self.split_flashes.append([event["x"], event["y"], 0])
        elif event["type"] == "heal":  # M6.3: "+26" over the healed character
            self.add_floater(
                event["side"], event["name"], f"+{event['amount']}", HEAL_COLOR
            )
        elif event["type"] == "guard_used":  # M4.2-B: the bonus, where the player looks
            self.add_floater(event["side"], event["name"], "+25%", GUARD_STRIKE_COLOR)
        elif event["type"] == "guard_expired":
            self.add_floater(event["side"], event["name"], "expired", EXPIRED_COLOR)
        elif event["type"] == "game_over":
            self.state = "result"
        lines = describe_event(event)
        if lines:
            self.log = (self.log + lines)[-50:]
        if event["type"] in (
            "explosion",
            "miss",
        ):  # M6.3: the summary of every shell so far
            self.attack_events.append(event)
            self.attack_destroyed += destroyed
            self.last_result = self.message = attack_summary(
                self.attack_events, self.attack_destroyed, self.shot_name
            )
            self.note_landing(event)
        elif lines and event["type"] not in (
            "round",
            "exp",
            "guard_expired",
            "game_over",
        ):
            # The HUD keeps the outcome of the action: what happens after it in the same turn
            # (EXP, a new round, an unused Guarded Strike expiring, the end) is only in the log.
            self.message = lines[-1]

    def note_landing(self, event):
        """M6.4: one shell of the attack in the air has landed ("explosion" or "miss"). When no
        shell is left flying, the attack is settled and becomes its team's last shot."""
        record = self.flying_record
        if record is None:  # (a test may show an explosion that no "fire" came before)
            return
        record.landings.append(event)
        if not self.battle.projectiles:
            self.last_shots[record.side] = record

    def shown_record(self):
        """M6.4: the last shot of the team to move while a person of that team may aim, or None
        (no shot yet, the controls are locked, or it is the computer's turn)."""
        if self.state != "battle" or self.controls_locked():
            return None
        side = self.battle.active_side
        return self.last_shots[side] if self.is_human_side(side) else None

    def last_shot_line(self):
        """The panel's "Last shot · 45° / 83 · COVER HIT", or None (see shown_record)."""
        record = self.shown_record()
        return None if record is None else record.text()

    def last_shot_mark(self):
        """Where to draw the faint "last" ring, or None (see shown_record and ShotRecord.mark)."""
        record = self.shown_record()
        return None if record is None else record.mark()

    def above_marker(self):
        """M6.4: (x, words) for the shells above the top of the window, or None if there are none.
        x is the middle of those shells, so the marker moves with them; the words count them
        ("Shell above view", "3 shells above"). A shell that leaves by the side is no longer in
        Battle.projectiles (it is a miss), so it is never shown as still flying."""
        if self.battle is None:
            return None
        above = [shell.x for shell in self.battle.projectiles if shell.y < 0]
        if not above:
            return None
        words = "Shell above view" if len(above) == 1 else f"{len(above)} shells above"
        return round(sum(above) / len(above)), words

    def above_marker_rect(self):
        """Where the marker and its words are drawn: under the HUD at ABOVE_Y, moved in from the
        edges so the words stay inside the window."""
        x, words = self.above_marker()
        width, height = self.small_font.size(words)
        half = width // 2 + 2
        x = min(max(x, half), WINDOW_WIDTH - half)
        return pygame.Rect(x - half, ABOVE_Y, 2 * half, 16 + height)

    def play_event_sound(self, event):
        """The sound for one battle event (M4.2-A). Each event is read once, so each sound plays
        once. A Defend, and a Knight's Rally (the whole team defends), play the defend sound
        (M5.2-A). A refused action is an "invalid" event and makes no sound; nor does Repair."""
        kind = event["type"]
        if kind == "fire":
            self.sounds.play("fire")
        elif (kind == "action" and event["action"] == "defend") or (
            kind == "special" and self.is_rally(event)
        ):
            self.sounds.play("defend")
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
                self.sounds.play(
                    "defeat"
                )  # against the computer, its win is your defeat
            else:
                self.sounds.play("victory")

    def is_rally(self, event):
        """True if a "special" event is a Knight's Rally (characters are named after their role)."""
        return any(
            character.name == event["name"] and isinstance(character, Knight)
            for character in self.battle.teams[event["side"]].characters
        )

    def add_floater(self, side, name, text, color, below=False):
        """A word or number floating up from above a character (M4.1): "-28", "DEFEATED", "shielded"."""
        team = self.battle.teams[side]
        index = next(
            i for i, character in enumerate(team.characters) if character.name == name
        )
        rect = pygame.Rect(team.character_rect(index))
        top = rect.top - 48 - (24 if index == 1 else 0)  # above its name and HP bar
        floater = [rect.centerx, top + (18 if below else 0), text, color, 0]
        # M4.2-A: move it up until it overlaps no other floating word (quick hits on one character).
        for _ in range(8):
            if not any(
                self.floater_rect(floater).colliderect(self.floater_rect(other))
                for other in self.floaters
            ):
                break
            floater[1] -= 16
        self.floaters.append(floater)

    def floater_font(self, text):
        """Damage ("-28") and heal ("+26", M6.3) numbers are bigger than the words."""
        return (
            self.small_font
            if text.startswith("-") or text[1:].isdigit()
            else self.tiny_font
        )

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
        if self.ai_thinking():  # nobody is chosen yet: don't show a character
            return [
                f"{self.battle.active_side.upper()} TEAM: the computer ({self.ai.difficulty.capitalize()})",
                "The computer is thinking about its move.",
                "",
                "",
            ]
        character = self.selected_character()
        team = self.battle.teams[self.battle.active_side]
        if character.level == MAX_LEVEL:
            exp_text = "EXP max"
        else:
            exp_text = f"EXP {character.exp}/{character.exp_to_next_level()}"
        blocked = character.special_blocked_reason(
            team
        )  # M6.2: also "nothing to repair", as the button
        special_text = (
            f"{character.SPECIAL_NAME}: ready" if blocked is None else blocked
        )
        if self.battle.is_over():
            status = "The game is over."
        elif character.is_defending:
            status = "Defending until your next turn."
        elif self.ai is not None and self.battle.active_side == self.ai.side:
            status = "Played by the computer."
        elif self.cannon_run.is_busy():
            status = self.cannon_run_text()  # the controls wait for the runner
        elif character.guarded_strike_ready:
            status = "Guarded Strike ready: ATTACK +25% this turn."
        else:
            status = "Click a character or press 1-3 to choose who acts."
        stats = (
            f"HP {character.hp}/{character.max_hp}   ATK {character.atk}   "
            f"DEF {character.defense}   {exp_text}"
        )
        return [
            f"{self.battle.active_side.upper()} TEAM: {character.name}   Level {character.level}",
            stats,
            special_text,
            status,
        ]

    def action_hint_lines(self):
        """The one line of help under the aim (M6.2): what is happening, or else what the action
        button under the mouse would do (the chosen character's special if the mouse is elsewhere)."""
        if self.battle.is_over():
            return ["The game is over: choose Rematch or Change teams."]
        if self.cannon_run.is_busy() and self.battle.projectile is None:
            return [self.cannon_run_text()]
        if self.is_ai_turn():
            return [
                f"The computer ({self.ai.difficulty.capitalize()}) is choosing the RIGHT team's move..."
            ]
        if self.battle.projectile is not None:
            return ["The shot is in the air..."]
        return [self.action_help(self.focused_action(pygame.mouse.get_pos()))]

    def focused_action(self, pos):
        """The action whose button is at `pos`, or "special" (the default help: the skill)."""
        for action, button in self.action_buttons.items():
            if button.rect.collidepoint(pos):
                return action
        return "special"

    def action_help(self, action):
        """What `action` does for the chosen character and what it costs (M6.2), or why it can't
        be used now: Battle.why_not_allowed decides, exactly as it does for the buttons."""
        character = self.selected_character()
        reason = self.battle.why_not_allowed(self.selected_index(), action)
        if reason is not None:
            return reason[0].upper() + reason[1:] + "."
        reflex = self.aim_mode == "reflex"
        if action == "attack":
            fire = (
                "locks the swinging angle and fires"
                if reflex
                else "fires with the current angle and power"
            )
            bonus = (
                " Guarded Strike: ATK +25%." if character.guarded_strike_ready else ""
            )
            return f"ATTACK (or {self.key_names()[2]}) {fire}.{bonus} Ends your turn."
        if action == "defend":
            if self.practice:
                return PRACTICE_NO_DEFEND  # M6.4
            return (
                "DEFEND halves damage until your next turn; then your ATTACK gets +25% (Guarded Strike). "
                "Ends your turn; not two turns in a row."
            )
        name = character.SPECIAL_NAME.upper()
        if fires_the_cannon(character, action):  # Power Shot, Triple Volley, Airburst
            if reflex:
                aim = "It locks the swinging angle once"  # however many shells it fires
            elif character.SPECIAL_SHELLS > 1:
                aim = "The dots show the center shell"  # M6.3
            else:
                aim = "It uses the current aim"
            return f"{name}: {character.SPECIAL_DESCRIPTION} {aim}; ends your turn."
        if isinstance(character, Medic):  # M6.3: who and how much, before the click
            target, amount = character.heal_target(
                self.battle.teams[self.battle.active_side]
            )
            return f"Heal {self.battle.active_side.upper()} {target.name} · +{amount} HP · ends turn"
        if isinstance(character, Engineer):
            return (
                f"{name}: up to {character.REPAIR_POOL} HP back for damaged cover, standing blocks only. "
                "At once; ends your turn."
            )
        return f"{name}: {character.SPECIAL_DESCRIPTION} At once; ends your turn."

    def action_note(self, action):
        """A word or two under an action button (M6.2): why it can't be used now, or what it adds.
        Nothing on the computer's turn or after the game."""
        if self.battle.is_over() or not self.is_human_side(self.battle.active_side):
            return ""
        if self.practice and action == "defend":
            return "shots only"  # M6.4
        locked = self.locked_shot
        if (
            locked is not None
            and locked.side == self.battle.active_side
            and locked.action == action
        ):
            return f"locked {locked.angle}°"
        if self.controls_locked():
            return "wait"
        character = self.selected_character()
        if self.battle.why_not_allowed(self.selected_index(), action) is None:
            if (
                action == "attack"
            ):  # the bonus, or else the key that fires (M6.2 rework)
                return (
                    "+25% ATK"
                    if character.guarded_strike_ready
                    else f"key {self.key_names()[2]}"
                )
            if action == "special" and isinstance(
                character, Medic
            ):  # M6.3: who would gain what
                target, amount = character.heal_target(
                    self.battle.teams[self.battle.active_side]
                )
                return f"{target.name} +{amount}"
            return ""
        if action == "defend":
            return "not twice"
        if character.special_cooldown > 0:
            return f"ready in {character.special_cooldown}"
        if isinstance(character, Medic):
            return "all full HP"  # the Medic's other reason (M6.3)
        return "nothing to repair"  # the Engineer's other reason

    def aim_values(self):
        """The active cannon's angle and power, the two biggest numbers in the panel (M6.2)."""
        cannon = self.battle.cannons[self.battle.active_side]
        return f"{cannon.angle}°", f"{cannon.power}"

    def aim_labels(self):
        """The small words over the two numbers: the keys of the team to move that change them."""
        angle_keys, power_keys, _ = self.key_names()
        angle = "ANGLE" if self.aim_mode == "reflex" else f"ANGLE · {angle_keys}"
        return angle, f"POWER · drag or {power_keys}"

    def hint_icon(self):
        """3 or 5 when the help line explains a Triple Volley or an Airburst (M6.3): a small picture of
        its shells goes before the line. Otherwise 0."""
        if (
            self.controls_locked()
            or self.focused_action(pygame.mouse.get_pos()) != "special"
        ):
            return 0
        shells = self.selected_character().SPECIAL_SHELLS
        return shells if shells > 1 else 0

    def button_font(self, button):
        """The font for a panel button's label: the small one when a long name (FIELD DRESSING) would
        not fit in the button (M6.3)."""
        return (
            self.font
            if self.font.size(button.label)[0] <= button.rect.width - 10
            else self.small_font
        )

    def path_label(self):
        """ "center shell" beside Classic Aim's dots when the chosen character's special fires several
        shells (M6.3): the dots follow the middle one, the shot of the current aim. Otherwise None."""
        if not self.path_points() or self.selected_character().SPECIAL_SHELLS < 2:
            return None
        return "center shell"

    @staticmethod
    def cannon_label(cannon):
        """The short aim label drawn under the active cannon."""
        return f"{cannon.angle}° / {cannon.power}"

    def phase_text(self):
        """What is happening in this turn, for the turn banner."""
        if self.battle.is_over():
            return "game over"
        if self.match_paused:
            return "paused"  # M6.4
        if self.battle.projectile is not None:
            return "shot in the air"
        if self.cannon_run.is_busy():
            if self.cannon_run.shot.side != self.battle.active_side:
                return "waiting"  # the last shooter is still running back
            return (
                "running to the cannon"
                if self.cannon_run.state == RUN_TO_CANNON
                else "running back"
            )
        if self.is_ai_turn():
            return "thinking..."
        return "time your shot" if self.aim_mode == "reflex" else "aim and act"

    def hud_turn_text(self):
        """The turn banner: the round, whose turn it is (and who plays it) and the phase."""
        if self.practice:  # M6.4: no rounds and no turns in the practice range
            return f"PRACTICE RANGE: {self.phase_text()}"
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
        if self.practice:  # M6.4
            return f"Practice range   (Backspace: back, R: reset, {sound})"
        return f"Combat log   (Esc: menu, R: rematch, {sound})"

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
        elif self.state == "cover":
            self.draw_cover_screen()
        else:
            self.draw_battlefield()
            self.draw_hud()
            self.draw_panel()
            if self.state == "result":
                self.draw_result()
            if self.match_paused:  # M6.4
                self.draw_pause_menu()
        if self.intro_playing():  # M6.2: over everything, until it ends or is skipped
            self.draw_intro()

    def aim_description(self):
        """One sentence under "Aim style" (M6.2), always shown, for the mode chosen now (two players
        have their own keys: M6.2 rework)."""
        descriptions = (
            AIM_DESCRIPTIONS if self.selection.vs_ai else TWO_PLAYER_AIM_DESCRIPTIONS
        )
        return descriptions[self.selection.aim_mode]

    def aim_description_rect(self):
        rect = pygame.Rect((0, 0), self.small_font.size(self.aim_description()))
        rect.center = (
            self.aim_buttons["classic"].rect.left + 160,
            172,
        )  # under the two buttons
        return rect

    def team_title(self, side):
        size = self.selection.team_size
        if side == "left":
            return f"LEFT TEAM   {len(self.selection.picks['left'])}/{size} chosen" + (
                "   (you)" if self.selection.vs_ai else ""
            )
        if self.selection.vs_ai:
            return f"RIGHT TEAM   the computer picks {size} and its cover"
        return f"RIGHT TEAM   {len(self.selection.picks['right'])}/{size} chosen"

    def team_title_rect(self, side):
        return pygame.Rect(
            (88 if side == "left" else 688, 192), self.font.size(self.team_title(side))
        )

    def draw_selection(self):
        self.screen.blit(self.menu_background, (0, 0))
        draw_text(
            self.screen,
            "CASTLE SIEGE",
            self.big_font,
            BRASS,
            center=(WINDOW_WIDTH // 2, 36),
        )
        for text, position in (
            ("Mode:", (280, 91)),
            ("Computer:", (790, 91)),
            ("Team size:", (280, 139)),
            ("Aim style", (790, 139)),
        ):
            draw_text(self.screen, text, self.font, LIGHT_TEXT, midright=position)
        buttons = (
            list(self.mode_buttons.values())
            + list(self.difficulty_buttons.values())
            + self.size_buttons
            + list(self.aim_buttons.values())
        )
        for button in buttons:
            button.draw(self.screen, self.font)
        draw_text(
            self.screen,
            self.aim_description(),
            self.small_font,
            BRASS,
            center=self.aim_description_rect().center,
        )
        for side, badge in (("left", (71, 202)), ("right", (671, 202))):
            draw_badge(self.screen, side, badge, 9)
            draw_text(
                self.screen,
                self.team_title(side),
                self.font,
                LIGHT_TEXT,
                topleft=self.team_title_rect(side).topleft,
            )
        for (side, role), rect in self.card_rects.items():
            self.draw_card(side, role, rect)
        mouse = pygame.mouse.get_pos()
        for side in (
            "left",
            "right",
        ):  # M6.3: what the specials do, under each team's cards
            self.draw_roster_info(side, mouse)
        draw_text(
            self.screen,
            self.message,
            self.small_font,
            BRASS,
            center=self.selection_message_rect().center,
        )
        self.start_button.draw(self.screen, self.font)
        self.practice_button.draw(self.screen, self.font)  # M6.4
        draw_text(
            self.screen,
            "Slot 1 stands at the front, behind the cover. Both teams have the same size. "
            "Enter = next, M = sound, Esc = quit.",
            self.small_font,
            LIGHT_TEXT,
            center=(WINDOW_WIDTH // 2, 648),
        )
        draw_text(
            self.screen,
            "Win by defeating every enemy character. Cover blocks only protect: "
            "destroying them does not win.",
            self.small_font,
            LIGHT_TEXT,
            center=(WINDOW_WIDTH // 2, 674),
        )

    def selection_message_rect(self):
        rect = pygame.Rect((0, 0), self.small_font.size(self.message))
        rect.center = (WINDOW_WIDTH // 2, SELECT_MESSAGE_Y)
        return rect

    def roster_info_rect(self, side):
        """The roster box under a team's six cards (M6.3), as wide as the cards."""
        left, _ = CARD_GRID[side]
        return pygame.Rect(
            left, ROSTER_BOX_TOP, 2 * CARD_STEP[0] + CARD_SIZE[0], ROSTER_BOX_HEIGHT
        )

    def roster_info_lines(self, side, mouse):
        """The roster box (M6.3): what the card under the mouse does, or else the team's picks in slot
        order, each with its special explained (a card only names it)."""
        if side == "right" and self.selection.vs_ai:
            return [
                f"The computer picks {self.selection.team_size} of the six roles when the battle starts."
            ]
        for (card_side, role), rect in self.card_rects.items():
            if card_side == side and rect.collidepoint(mouse):
                return [
                    f"{role.__name__} · {role.SPECIAL_NAME}, cooldown {role.SPECIAL_COOLDOWN} rounds",
                    role.SPECIAL_DESCRIPTION,
                ]
        picks = self.selection.picks[side]
        if not picks:
            return [
                "Click cards to add roles; the order is the slot order.",
                "Point at a card to read what its special does.",
            ]
        return [
            f"{slot} {role.__name__} · {role.SPECIAL_NAME}: {role.SPECIAL_DESCRIPTION}"
            for slot, role in enumerate(picks, start=1)
        ]

    def roster_info_text_rects(self, side, mouse):
        box = self.roster_info_rect(side)
        return [
            pygame.Rect((box.left + 8, box.top + 4 + 15 * i), self.tiny_font.size(line))
            for i, line in enumerate(self.roster_info_lines(side, mouse))
        ]

    def draw_roster_info(self, side, mouse):
        box = self.roster_info_rect(side)
        pygame.draw.rect(self.screen, PANEL_COLOR, box, border_radius=6)
        pygame.draw.rect(self.screen, PANEL_EDGE, box, 1, border_radius=6)
        for line, rect in zip(
            self.roster_info_lines(side, mouse),
            self.roster_info_text_rects(side, mouse),
        ):
            draw_text(
                self.screen, line, self.tiny_font, LIGHT_TEXT, topleft=rect.topleft
            )

    def card_band_rect(self, rect):
        """The band at the bottom of a card that says chosen / open / the computer's."""
        return pygame.Rect(rect.left + 6, rect.bottom - 24, rect.width - 12, 20)

    def card_items(self, role, rect):
        """The words on a compact role card (M6.3), as (text, font, colour, topleft): the name on top,
        HP / ATK / DEF beside the portrait, the special's name and cooldown under it."""
        name = pygame.Rect((0, 0), self.font.size(role.__name__))
        name.center = (rect.centerx, rect.top + 15)
        items = [(role.__name__, self.font, TEXT_COLOR, name.topleft)]
        for i, stat in enumerate(
            (f"HP {role.BASE_HP}", f"ATK {role.BASE_ATK}", f"DEF {role.BASE_DEF}")
        ):
            items.append(
                (
                    stat,
                    self.tiny_font,
                    TEXT_COLOR,
                    (rect.left + 88, rect.top + 36 + 16 * i),
                )
            )
        skill = f"{role.SPECIAL_NAME} · cooldown {role.SPECIAL_COOLDOWN}"
        line = pygame.Rect((0, 0), self.tiny_font.size(skill))
        line.center = (rect.centerx, rect.top + 96)
        items.append(
            (skill, self.tiny_font, None, line.topleft)
        )  # None: the team's label colour
        return items

    def card_text_rects(self, role, rect):
        return [
            pygame.Rect(topleft, font.size(text))
            for text, font, _, topleft in self.card_items(role, rect)
        ]

    def card_text_bottom(self, role, rect):
        """The lowest y the card's words reach (they must stay above the state band)."""
        return max(text_rect.bottom for text_rect in self.card_text_rects(role, rect))

    def card_state_text(self, side, role):
        """The band at the bottom of a card: chosen (its slot), open, or the computer's."""
        if side == "right" and self.selection.vs_ai:
            return "THE COMPUTER PICKS"
        picks = self.selection.picks[side]
        if role in picks:
            slot = picks.index(role) + 1
            return f"Slot {slot}" + (" · front" if slot == 1 else "")
        return "Click to add"

    def draw_card(self, side, role, rect):
        """One role card on the selection screen (M6.2, made compact in M6.3): its name, a half-body
        portrait on navy, its stats, the special's name, and a band that says chosen / open / the
        computer's, by words and by shape (filled with the emblem, outlined, or grey)."""
        computer_team = side == "right" and self.selection.vs_ai
        chosen = role in self.selection.picks[side] and not computer_team
        hovered = not computer_team and rect.collidepoint(pygame.mouse.get_pos())
        background = (216, 222, 227) if computer_team else (246, 237, 218)
        if hovered:
            background = (255, 247, 226)
        pygame.draw.rect(self.screen, background, rect, border_radius=8)
        border = TEAM_COLORS[side] if chosen else BRASS if hovered else DIM_TEXT
        pygame.draw.rect(self.screen, border, rect, 4 if chosen else 2, border_radius=8)
        frame = pygame.Rect(
            rect.left + 8,
            rect.top + 30,
            CARD_PORTRAIT_SIZE[0] + 4,
            CARD_PORTRAIT_SIZE[1] + 4,
        )
        pygame.draw.rect(self.screen, PORTRAIT_BACK, frame, border_radius=5)
        self.screen.blit(
            card_portrait(role, direction(side)), (frame.left + 2, frame.top + 2)
        )
        items = self.card_items(role, rect)
        for text, font, color, topleft in items:
            draw_text(
                self.screen, text, font, color or LABEL_COLORS[side], topleft=topleft
            )
        if (
            role.SPECIAL_SHELLS > 1
        ):  # a Triple Volley or Airburst: a picture of its shells
            draw_spread_icon(
                self.screen,
                (rect.right - 22, rect.top + 52),
                role.SPECIAL_SHELLS,
                AIM_COLOR,
            )
        band = self.card_band_rect(rect)
        text = self.card_state_text(side, role)
        if computer_team:  # M4.1: say plainly that these cards can't be clicked
            pygame.draw.rect(self.screen, BUTTON_OFF, band, border_radius=4)
            draw_text(self.screen, text, self.tiny_font, LIGHT_TEXT, center=band.center)
        elif chosen:
            pygame.draw.rect(self.screen, TEAM_COLORS[side], band, border_radius=4)
            draw_emblem(self.screen, side, (band.left + 14, band.centery), 5)
            draw_text(
                self.screen,
                text,
                self.small_font,
                (255, 255, 255),
                center=(band.centerx + 8, band.centery),
            )
        else:
            pygame.draw.rect(self.screen, DIM_TEXT, band, 1, border_radius=4)
            draw_text(
                self.screen, text, self.tiny_font, (90, 96, 106), center=band.center
            )

    # ----- drawing: cover placement ------------------------------------------------

    def cover_title(self):
        return f"{self.placing.upper()} TEAM: PLACE YOUR COVER"

    def cover_title_color(self):
        return LABEL_COLORS[self.placing]

    def cover_text_plate_rect(self):
        """The light plate behind the placement screen's title, instructions and legend."""
        return pygame.Rect(
            140, 12, WINDOW_WIDTH - 280, self.cover_text_bottom() + 10 - 12
        )

    def cover_count_text(self):
        return f"Blocks: {len(self.setup.layouts[self.placing])} / {MAX_BLOCKS}"

    def budget_pip_rects(self):
        """MAX_BLOCKS small squares right of "Blocks: n / 6", one per block of the budget (M4.1)."""
        first_x = (
            WINDOW_WIDTH // 2 + self.font.size(self.cover_count_text())[0] // 2 + 14
        )
        return [pygame.Rect(first_x + i * 19, 79, 14, 14) for i in range(MAX_BLOCKS)]

    def cover_help_lines(self):
        return [
            "Click an empty slot to place a block (100 HP). Click a block to remove it.",
            f"Up to {MAX_BLOCKS} blocks. A raised block needs a block under it: "
            "removing that block also removes the one on top.",
            "Blocks stop enemy shots and shield the characters behind them.",
            "Destroying cover never wins: only defeating every enemy character does.",
        ]

    def cover_legend_y(self):
        """y of the middle of the legend row, just under the instructions."""
        return COVER_HELP_TOP + COVER_HELP_STEP * len(self.cover_help_lines()) + 14

    def cover_text_bottom(self):
        """The lowest y the placement screen's title, instructions and legend reach."""
        return self.cover_legend_y() + 12

    def cover_next_step(self):
        if self.placing == "right":
            return "Start Battle: the battle starts."
        if self.selection.vs_ai:
            return "Start Battle: the computer places its own cover, then the battle starts."
        return "Next: RIGHT places its cover, without seeing LEFT's."

    def cover_step_text(self):
        """Where the placing team is in the setup (M6.2): "1/2 · Left cover" in two-player mode,
        "1/1 · Left cover" against the computer (one step: the computer places its own)."""
        if self.selection.vs_ai:
            return f"1/1 · {self.placing.capitalize()} cover"
        return f"{1 if self.placing == 'left' else 2}/2 · {self.placing.capitalize()} cover"

    def cover_aim_text(self):
        return f"Aim: {self.selection.aim_mode.capitalize()}"

    def removal_preview(self, pos):
        """The slots a click at `pos` would empty (M6.2): the block there and any raised block on
        top of it. It only asks castle.remove_block() about a copy of the layout: nothing changes."""
        layout = self.setup.layouts[self.placing]
        for slot in layout:
            if slot_rect(self.placing, slot).collidepoint(pos):
                return remove_block(layout, slot)[1]
        return ()

    def cover_hover_text(self, pos):
        """A warning while the mouse is on a block that holds up another one, else None."""
        if len(self.removal_preview(pos)) > 1:
            return "Removing this block also removes the raised block on top."
        return None

    def draw_cover_screen(self):
        """One team's side of the battlefield: its characters, its cannon and its 8 cover
        slots, drawn exactly where they stand in the battle. The other team's cover stays hidden."""
        side = self.placing
        self.screen.blit(self.background, (0, 0))  # sky, scenery and ground (M4.2-A)
        plate = self.cover_text_plate_rect()
        draw_plate(self.screen, plate)  # the text stays readable on the sky
        draw_text(
            self.screen,
            self.cover_title(),
            self.title_font,
            self.cover_title_color(),
            center=(WINDOW_WIDTH // 2, 42),
        )
        # M6.2: the step in one corner, the chosen Aim style in the other.
        draw_text(
            self.screen,
            self.cover_step_text(),
            self.small_font,
            TEXT_COLOR,
            topleft=(plate.left + 16, plate.top + 12),
        )
        draw_text(
            self.screen,
            self.cover_aim_text(),
            self.small_font,
            TEXT_COLOR,
            topright=(plate.right - 16, plate.top + 12),
        )
        draw_text(
            self.screen,
            self.cover_count_text(),
            self.font,
            TEXT_COLOR,
            center=(WINDOW_WIDTH // 2, 86),
        )
        used = len(self.setup.layouts[side])
        for i, pip in enumerate(self.budget_pip_rects()):
            if i < used:
                pygame.draw.rect(self.screen, block_color(side, 1, 1), pip)
            pygame.draw.rect(self.screen, TEXT_COLOR if i < used else DIM_TEXT, pip, 1)
        for i, line in enumerate(self.cover_help_lines()):
            draw_text(
                self.screen,
                line,
                self.small_font,
                TEXT_COLOR,
                center=(WINDOW_WIDTH // 2, COVER_HELP_TOP + i * COVER_HELP_STEP),
            )
        self.draw_cover_legend(side)
        for index, role in enumerate(self.selection.picks[side]):
            center_x, top = SLOT_X[side][index], GROUND_Y - CHARACTER_HEIGHT
            draw_figure(
                self.screen,
                role,
                center_x,
                top,
                direction(side),
                TEAM_COLORS[side],
                side,
            )
            label = pygame.Rect(0, 0, self.tiny_font.size(role.__name__)[0] + 10, 18)
            label.center = (center_x, top - 14 - (18 if index == 1 else 0))
            keep_off_cover(side, label)  # M6.3: a long name stays clear of the slots
            draw_plate(self.screen, label)
            draw_text(
                self.screen,
                role.__name__,
                self.tiny_font,
                LABEL_COLORS[side],
                center=label.center,
            )
        self.draw_cannon(Cannon(side), is_active=False)
        # A frame around the 8 slots, so the small area to click stands out on the big screen.
        frame = pygame.Rect(
            min(COLUMN_X[side]) - 5,
            GROUND_Y - 2 * BLOCK_SIZE - 6,
            4 * BLOCK_SIZE + 10,
            2 * BLOCK_SIZE + 6,
        )
        pygame.draw.rect(self.screen, BRASS, frame, 2, border_radius=6)
        mouse = pygame.mouse.get_pos()
        preview = self.removal_preview(mouse)  # M6.2: what a click here would remove
        for slot in range(SLOT_COUNT):
            self.draw_slot(side, slot, self.setup.layouts[side], preview, mouse)
        draw_outlined_text(
            self.screen,
            "COVER SLOTS",
            self.tiny_font,
            LIGHT_TEXT,
            TEXT_COLOR,
            center=(frame.centerx, frame.top - 9),
        )
        warning = self.cover_hover_text(mouse)
        if warning is not None:
            draw_outlined_text(
                self.screen,
                warning,
                self.tiny_font,
                LIGHT_TEXT,
                TEXT_COLOR,
                center=(frame.centerx, frame.top - 30),
            )
        other = other_side(side)
        if side == "right":
            note = "LEFT's cover stays hidden until the battle starts."
        elif self.selection.vs_ai:
            note = "The computer places the RIGHT cover when the battle starts."
        else:
            note = "RIGHT places its own cover next, without seeing LEFT's."
        draw_outlined_text(
            self.screen,
            note,
            self.small_font,
            LIGHT_TEXT,
            TEXT_COLOR,
            center=(WINDOW_WIDTH // 4 * (3 if other == "right" else 1), 420),
        )
        pygame.draw.rect(
            self.screen,
            PANEL_COLOR,
            (0, PANEL_TOP, WINDOW_WIDTH, WINDOW_HEIGHT - PANEL_TOP),
        )
        draw_text(
            self.screen,
            self.message,
            self.small_font,
            LIGHT_TEXT,
            center=(WINDOW_WIDTH // 2, PANEL_TOP + 18),
        )
        for (
            name,
            button,
        ) in self.preset_buttons.items():  # M6.2: two layouts to start from
            button.draw(self.screen, self.font)
            draw_text(
                self.screen,
                PRESET_NOTES[name],
                self.tiny_font,
                DIM_TEXT,
                center=(button.rect.centerx, button.rect.bottom + 12),
            )
        self.back_button.draw(self.screen, self.font)
        self.confirm_button.draw(self.screen, self.font)
        draw_text(
            self.screen,
            f"{self.cover_next_step()}   Enter = {self.confirm_button.label}, "
            "Backspace = Back, Esc = quit.",
            self.tiny_font,
            DIM_TEXT,
            center=(WINDOW_WIDTH // 2, PANEL_TOP + 122),
        )

    def draw_cover_legend(self, side):
        """One row under the instructions: what the three kinds of slot look like."""
        items = [
            ("block", "Block: click to remove"),
            ("open", "Empty slot: click to place"),
            ("closed", "No block allowed here now"),
        ]
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
            draw_text(
                self.screen, text, self.small_font, TEXT_COLOR, midleft=(x + 30, y)
            )
            x += width + 50

    def draw_slot(self, side, slot, layout, preview=(), mouse=(-1, -1)):
        """An occupied slot shows its block; a slot that can take a block is light with a "+";
        a slot that can't take one right now (castle.place_block says why) is only outlined.
        M6.2: the blocks a click would remove (`preview`) all get the same red outline."""
        rect = slot_rect(side, slot)
        if slot in layout:
            draw_block(self.screen, side, rect.x, rect.y, rect.width, 1, 1)
        elif place_block(layout, slot)[1] is None:
            pygame.draw.rect(self.screen, OPEN_SLOT_COLOR, rect)
            pygame.draw.rect(self.screen, TEAM_COLORS[side], rect, 2)
            draw_text(
                self.screen, "+", self.font, TEAM_COLORS[side], center=rect.center
            )
        else:
            self.draw_closed_slot(rect)
            return
        if slot in preview:
            pygame.draw.rect(self.screen, REMOVE_COLOR, rect, 3)
        elif rect.collidepoint(mouse):
            pygame.draw.rect(self.screen, BRASS, rect, 3)

    def draw_closed_slot(self, rect):
        """A slot that can't take a block right now: an outline with an "x" (M4.1: it was
        only a faint outline)."""
        pygame.draw.rect(self.screen, DIM_TEXT, rect, 1)
        inset = rect.width // 4
        pygame.draw.line(
            self.screen,
            CLOSED_SLOT_COLOR,
            (rect.left + inset, rect.top + inset),
            (rect.right - 1 - inset, rect.bottom - 1 - inset),
            2,
        )
        pygame.draw.line(
            self.screen,
            CLOSED_SLOT_COLOR,
            (rect.right - 1 - inset, rect.top + inset),
            (rect.left + inset, rect.bottom - 1 - inset),
            2,
        )

    # ----- drawing: the battlefield --------------------------------------------------

    def draw_battlefield(self):
        self.screen.blit(self.background, (0, 0))  # sky, scenery and ground (M4.2-A)
        for side, castle in self.battle.castles.items():
            for block in castle.blocks:
                on_ground = block.y + block.size >= GROUND_Y
                if block.is_destroyed():  # M4.1: show where cover used to be
                    draw_rubble_outline(
                        self.screen, block.x, block.y, block.size, on_ground
                    )
                else:
                    if on_ground:  # M6.2: it stands on the ground
                        draw_contact_shadow(
                            self.screen,
                            block.x + block.size / 2,
                            GROUND_Y,
                            block.size + 6,
                        )
                    draw_block(
                        self.screen,
                        side,
                        block.x,
                        block.y,
                        block.size,
                        block.hp,
                        block.max_hp,
                    )
            # Asked from the Battle on every frame, so it can never be out of date.
            if self.battle.castle_guarded(side):
                self.draw_castle_guard(side, castle)
        self.draw_characters()
        for side, cannon in self.battle.cannons.items():
            self.draw_cannon(
                cannon,
                is_active=(
                    side == self.battle.active_side and not self.battle.is_over()
                ),
            )
        if self.cannon_run.state == FIRE:  # starts on the frame the shot is launched
            self.draw_muzzle_flash(self.battle.cannons[self.cannon_run.shot.side])
        if self.battle.can_fire():
            cannon = self.battle.cannons[self.battle.active_side]
            if not self.controls_locked():
                self.draw_aim_arrow(cannon)
            points = self.path_points()
            draw_path_dots(self.screen, points)  # M6.2: Classic Aim only
            label = self.path_label()  # M6.3: "center shell" for a spread
            if label is not None:
                x, y = points[-1]
                draw_outlined_text(
                    self.screen,
                    label,
                    self.tiny_font,
                    LIGHT_TEXT,
                    OUTLINE,
                    midbottom=(round(x), round(y) - 8),
                )
            draw_text(
                self.screen,
                self.cannon_label(cannon),
                self.tiny_font,
                READY_COLOR,
                center=(cannon.x, GROUND_Y + 10),
            )
        mark = self.last_shot_mark()  # M6.4: where this team's last center shell landed
        if mark is not None:
            self.draw_last_mark(mark)
        gauge = self.swing_gauge()  # M6.2: Reflex Aim's gauge (or the lock mark)
        if gauge is not None:
            side, angle, locked = gauge
            cannon = self.battle.cannons[side]
            draw_swing_gauge(
                self.screen,
                (cannon.x, cannon.y),
                direction(side),
                SWING_LOW,
                SWING_HIGH,
                angle,
                SWING_MARK_RADIUS,
                locked,
            )
            if locked:
                label = arc_point(
                    (cannon.x, cannon.y),
                    direction(side),
                    SWING_HIGH,
                    SWING_MARK_RADIUS + 22,
                )
                draw_outlined_text(
                    self.screen,
                    f"LOCKED {angle}°",
                    self.tiny_font,
                    BRASS,
                    OUTLINE,
                    center=(round(label[0]), round(label[1])),
                )
        for points in self.trails.values():  # dots where each shell has just been
            for x, y in points[:-1]:
                pygame.draw.circle(self.screen, TRAIL_COLOR, (round(x), round(y)), 2)
        for x, y, age in self.split_flashes:  # M6.3: where an Airburst shell split
            draw_split_flash(
                self.screen, (round(x), round(y)), age / SPLIT_FLASH_FRAMES
            )
        for shell in self.battle.projectiles:
            self.draw_shell(shell)
        # An explosion is a circle that grows to its blast radius while fading from yellow to red.
        # It is see-through (M4.1), so the character it hits can still be seen. M6.3: each shell's
        # own radius (the small shells of a Triple Volley or Airburst have smaller blasts).
        for x, y, age, blast in self.explosions:
            progress = age / EXPLOSION_FRAMES
            radius = int(8 + (blast - 8) * progress)
            color = (255, int(220 - 150 * progress), int(80 - 60 * progress))
            alpha = int(EXPLOSION_ALPHA * (1 - 0.5 * progress))
            circle = pygame.Surface((2 * radius + 2, 2 * radius + 2), pygame.SRCALPHA)
            pygame.draw.circle(
                circle,
                color + (alpha,),
                (radius + 1, radius + 1),
                radius,
                0 if progress < 0.5 else 4,
            )
            self.screen.blit(circle, (round(x) - radius - 1, round(y) - radius - 1))
        for x, y, kind, age in self.impacts:  # M6.2: where the last shot landed
            self.draw_impact_mark(x, y, kind, age)
        for x, y, text, color, _ in self.floaters:  # "-28", "DEFEATED", "shielded"
            draw_outlined_text(
                self.screen,
                text,
                self.floater_font(text),
                color,
                (255, 255, 255),
                center=(x, round(y)),
            )

    def draw_shell(self, shell):
        """One flying shell: an Airburst shell before it splits is marked (M6.3); a Power Shot is bigger
        and orange; any other shell is dark with a light rim (M6.2), smaller for a Triple Volley and
        smallest after an Airburst split."""
        center = (round(shell.x), round(shell.y))
        if shell.split is not None:
            draw_marked_shell(self.screen, center)
        elif self.shot_style == "power":
            pygame.draw.circle(self.screen, FLASH_COLOR, center, 9)
            pygame.draw.circle(self.screen, POWER_SHOT_COLOR, center, 7)
        else:
            size = SHELL_SIZES[self.shot_style]
            pygame.draw.circle(self.screen, SHOT_RIM, center, size + 2)
            pygame.draw.circle(self.screen, SHOT_COLOR, center, size)

    def draw_castle_guard(self, side, castle):
        """Cover Guard is on: a blue outline on every standing block, and a GUARDED badge."""
        for block in castle.alive_blocks():
            pygame.draw.rect(
                self.screen, GUARD_COLOR, (block.x, block.y, block.size, block.size), 3
            )
        badge = guard_badge_rect(side)
        pygame.draw.rect(self.screen, GUARD_COLOR, badge, border_radius=5)
        draw_text(
            self.screen, "GUARDED", self.tiny_font, (255, 255, 255), center=badge.center
        )

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
                    shadow_x = self.cannon_run.actor_x() if running else rect.centerx
                    draw_contact_shadow(self.screen, shadow_x, GROUND_Y, 30)  # M6.2
                    if character.is_defending:
                        bubble = pygame.Surface((64, 64), pygame.SRCALPHA)
                        pygame.draw.circle(bubble, DEFEND_COLOR + (90,), (32, 32), 31)
                        pygame.draw.circle(
                            bubble, DEFEND_COLOR + (220,), (32, 32), 31, 2
                        )
                        self.screen.blit(bubble, bubble.get_rect(center=rect.center))
                    if running:
                        self.draw_runner(type(character), side, rect.top)
                    else:
                        draw_figure(
                            self.screen,
                            type(character),
                            rect.centerx,
                            rect.top,
                            direction(side),
                            TEAM_COLORS[side],
                            side,
                        )
                    name_color = LABEL_COLORS[side]
                else:
                    # Defeated: a grey shape lying on the ground.
                    pygame.draw.rect(
                        self.screen,
                        DEFEATED_COLOR,
                        (rect.left - 4, rect.bottom - 9, rect.width + 8, 9),
                        border_radius=4,
                    )
                    name_color = DEFEATED_COLOR
                draw_plate(
                    self.screen, self.label_plate_rect(side, index)
                )  # M4.2-A: readable on any scenery
                if character.is_alive() and (
                    character.guarded_strike_pending or character.guarded_strike_ready
                ):
                    draw_guard_mark(
                        self.screen,
                        self.guard_mark_rect(side, index),
                        character.guarded_strike_ready,
                    )
                plate_x = self.label_plate_rect(
                    side, index
                ).centerx  # M6.3: off the cover
                draw_text(
                    self.screen,
                    character.name,
                    self.tiny_font,
                    name_color,
                    center=(plate_x, label_y),
                )
                bar = pygame.Rect(plate_x - 20, label_y + 8, 40, 6)
                pygame.draw.rect(self.screen, (60, 60, 60), bar)
                pygame.draw.rect(
                    self.screen,
                    hp_bar_color(character),
                    (bar.left, bar.top, hp_bar_width(character, bar.width), bar.height),
                )
                pygame.draw.rect(
                    self.screen, TEXT_COLOR, bar.inflate(2, 2), 1
                )  # outline
                if character.is_alive():  # special cooldown, under the feet
                    if character.special_cooldown > 0:
                        draw_text(
                            self.screen,
                            f"wait {character.special_cooldown}",
                            self.tiny_font,
                            COOLDOWN_COLOR,
                            center=(rect.centerx, GROUND_Y + 10),
                        )
                    else:
                        draw_text(
                            self.screen,
                            "ready",
                            self.tiny_font,
                            READY_COLOR,
                            center=(rect.centerx, GROUND_Y + 10),
                        )
                if (
                    side == acting_side
                    and index == chosen
                    and character.is_alive()
                    and not running
                    and not self.ai_thinking()
                ):  # the computer hasn't chosen anyone yet
                    pygame.draw.rect(
                        self.screen, ACTIVE_RING_COLOR, rect.inflate(8, 8), 3
                    )
                    tip_y = label_y - 10
                    pygame.draw.polygon(
                        self.screen,
                        ACTIVE_RING_COLOR,
                        [
                            (rect.centerx - 7, tip_y - 10),
                            (rect.centerx + 7, tip_y - 10),
                            (rect.centerx, tip_y),
                        ],
                    )

    def draw_runner(self, role, side, top):
        """The attacking character on its way to the cannon, firing it, or on its way back.
        Only the figure moves: its name, HP bar and cooldown stay over its slot, where the
        Battle keeps the character (and where a shot could hit it)."""
        run = self.cannon_run
        x = round(run.actor_x())
        if run.state == FIRE:
            draw_firing_figure(
                self.screen, role, x, top, run.facing(), TEAM_COLORS[side], side
            )
        else:
            draw_running_figure(
                self.screen,
                role,
                x,
                top,
                run.facing(),
                TEAM_COLORS[side],
                run.frame,
                side,
            )

    def guard_mark_rect(self, side, index):
        """Where a character's Guarded Strike mark goes (M4.2-B): beside its name plate, on the
        side toward the middle of the field."""
        plate = self.label_plate_rect(side, index)
        mark = pygame.Rect(0, 0, 13, 13)
        mark.centery = plate.centery
        if side == "left":
            mark.left = plate.right + 2
        else:
            mark.right = plate.left - 2
        return mark

    def label_plate_rect(self, side, index):
        """The light plate behind a character's name and HP bar (M4.2-A)."""
        team = self.battle.teams[side]
        rect = pygame.Rect(team.character_rect(index))
        label_y = rect.top - 30 - (24 if index == 1 else 0)
        plate = pygame.Rect(
            0, 0, max(52, self.tiny_font.size(team.characters[index].name)[0] + 12), 24
        )
        plate.midtop = (rect.centerx, label_y - 8)
        return keep_off_cover(side, plate)

    def draw_muzzle_flash(self, cannon):
        """A short flash at the barrel's tip while the shot leaves it, shrinking over FIRE_FRAMES.
        The cannon itself never moves."""
        radius = round(12 - 7 * self.cannon_run.frame / FIRE_FRAMES)
        if self.shot_style == "power":
            radius = round(radius * 1.5)  # M4.1: a Power Shot gets a bigger flash
        center = muzzle_point(cannon)
        pygame.draw.circle(self.screen, FLASH_EDGE, center, radius)
        pygame.draw.circle(self.screen, FLASH_COLOR, center, max(2, radius // 2))

    def draw_last_mark(self, point):
        """M6.4: a see-through hollow ring (light, with a thin dark edge so it shows on any
        background) where the team's last center shell landed, and "last" beside it on the
        shooter's side, clear of the name plates above the characters."""
        x, y = round(point[0]), round(point[1])
        size = 2 * LAST_MARK_RADIUS + 6
        ring = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size // 2, size // 2)
        pygame.draw.circle(ring, OUTLINE + (120,), center, LAST_MARK_RADIUS + 1, 4)
        pygame.draw.circle(ring, LIGHT_TEXT + (LAST_MARK_ALPHA,), center, LAST_MARK_RADIUS, 2)
        self.screen.blit(ring, (x - size // 2, y - size // 2))
        label = self.tiny_font.render("last", True, LIGHT_TEXT)
        label.set_alpha(LAST_MARK_ALPHA)
        gap = LAST_MARK_RADIUS + 4
        if self.battle.active_side == "left":  # LEFT shot from the left: the label on that side
            where = label.get_rect(midright=(x - gap, y))
        else:
            where = label.get_rect(midleft=(x + gap, y))
        self.screen.blit(label, where)

    def draw_impact_mark(self, x, y, kind, age):
        """M6.2: a ring that shrinks where a shot landed, in the colour of what it hit (a
        character, cover, the ground), with three bits of debris flying up. It fades with the
        floating numbers (FLOAT_FRAMES); only a picture."""
        progress = age / FLOAT_FRAMES
        radius = round(30 - 22 * progress)
        center = (round(x), round(y))
        pygame.draw.circle(self.screen, OUTLINE, center, radius, 4)
        pygame.draw.circle(self.screen, IMPACT_COLORS[kind], center, radius - 1, 2)
        for degrees in (60, 105, 150):  # debris, moving outward as the ring shrinks
            start = arc_point(center, 1, degrees, 12 + 24 * progress)
            end = arc_point(center, 1, degrees, 20 + 24 * progress)
            pygame.draw.line(self.screen, IMPACT_COLORS[kind], start, end, 2)

    def draw_cannon(self, cannon, is_active):
        # A wheel on the ground under the pivot; the barrel points along the cannon's angle.
        # M6.2: on a wooden carriage, with spokes; the pivot, barrel and muzzle are where they were.
        facing = direction(cannon.side)
        wheel = (cannon.x, GROUND_Y - 8)
        pygame.draw.ellipse(
            self.screen, TEXT_COLOR, (cannon.x - 16, GROUND_Y - 4, 32, 6)
        )
        carriage = [
            (cannon.x - facing * 17, GROUND_Y - 2),
            (cannon.x + facing * 6, GROUND_Y - 2),
            (cannon.x + facing * 3, cannon.y + 3),
            (cannon.x - facing * 7, cannon.y + 3),
        ]
        pygame.draw.polygon(self.screen, WOOD, carriage)
        pygame.draw.polygon(self.screen, OUTLINE, carriage, 2)
        pygame.draw.circle(self.screen, TEXT_COLOR, wheel, 9)
        pygame.draw.circle(self.screen, WOOD, wheel, 7)
        for degrees in (0, 60, 120):  # spokes
            a, b = (
                arc_point(wheel, 1, degrees, 6),
                arc_point(wheel, 1, degrees + 180, 6),
            )
            pygame.draw.line(self.screen, OUTLINE, a, b, 1)
        pygame.draw.circle(self.screen, BRASS, wheel, 2)
        radians = math.radians(cannon.angle)
        tip = (
            cannon.x + facing * 24 * math.cos(radians),
            cannon.y - 24 * math.sin(radians),
        )  # minus: up is smaller y
        pygame.draw.line(self.screen, TEXT_COLOR, (cannon.x, cannon.y), tip, 10)
        pygame.draw.line(self.screen, CANNON_COLOR, (cannon.x, cannon.y), tip, 7)
        pygame.draw.line(
            self.screen,
            (120, 124, 132),
            (cannon.x, cannon.y - 2),
            (tip[0], tip[1] - 2),
            1,
        )  # metal shine
        pygame.draw.circle(self.screen, BRASS, (round(tip[0]), round(tip[1])), 4, 2)
        pygame.draw.circle(self.screen, CANNON_COLOR, (cannon.x, cannon.y), 9)
        if is_active:
            pygame.draw.circle(
                self.screen, ACTIVE_RING_COLOR, (cannon.x, cannon.y), 14, 3
            )

    def draw_aim_arrow(self, cannon):
        """The current aim: angle sets direction and power sets arrow length."""
        pivot, facing = (cannon.x, cannon.y), direction(cannon.side)
        fraction = (cannon.power - MIN_POWER) / (MAX_POWER - MIN_POWER)
        length = AIM_ARROW_MIN + fraction * (AIM_ARROW_MAX - AIM_ARROW_MIN)
        start = arc_point(pivot, facing, cannon.angle, 26)
        tip = arc_point(pivot, facing, cannon.angle, length)
        head = (
            arc_point(tip, facing, cannon.angle - 145, 10),
            tip,
            arc_point(tip, facing, cannon.angle + 145, 10),
        )
        for color, width in ((OUTLINE, 5), (AIM_COLOR, 3)):
            pygame.draw.line(self.screen, color, start, tip, width)
            pygame.draw.lines(self.screen, color, False, head, width)

    def hud_team_line(self, side):
        """'LEFT  2/3': living characters / team size, read first (M6.2: the cover went below)."""
        team = self.battle.teams[side]
        name = "TARGETS" if self.practice and side != PRACTICE_SIDE else side.upper()  # M6.4
        return f"{name}  {len(team.alive_characters())}/{len(team.characters)}"

    def hud_detail_line(self, side):
        """The smaller line under it: 'standing · cover 5/6' (standing / placed blocks)."""
        castle = self.battle.castles[side]
        return f"standing · cover {len(castle.alive_blocks())}/{len(castle.blocks)}"

    def draw_hud(self):
        # Each team's line, after its badge (M4.2-A: the emblem tells the teams apart by shape).
        for side, centre in self.hud_emblem_centres().items():
            draw_badge(self.screen, side, centre, 11)
            draw_outlined_text(
                self.screen,
                self.hud_team_line(side),
                self.font,
                LIGHT_TEXT,
                TEXT_COLOR,
                **self.hud_side_position(side),
            )
            draw_outlined_text(
                self.screen,
                self.hud_detail_line(side),
                self.tiny_font,  # M6.2: smaller
                LIGHT_TEXT,
                TEXT_COLOR,
                **self.hud_side_position(side, 47),
            )
        # The turn banner (M4.1): white text on the colour of the team whose turn it is, saying
        # what is happening ("aim and act", "shot in the air", "thinking..."); grey once it's over.
        banner = self.hud_banner_rect()
        if self.battle.is_over():
            pygame.draw.rect(self.screen, (70, 74, 82), banner, border_radius=12)
        else:
            pygame.draw.rect(
                self.screen,
                TEAM_COLORS[self.battle.active_side],
                banner,
                border_radius=12,
            )
            draw_emblem(
                self.screen,
                self.battle.active_side,
                (banner.left + 16, banner.centery),
                5,
            )
        draw_text(
            self.screen,
            self.hud_turn_text(),
            self.banner_font,
            (255, 255, 255),
            center=(banner.centerx + 9, banner.centery),
        )
        draw_outlined_text(
            self.screen,
            self.message,
            self.small_font,
            LIGHT_TEXT,
            TEXT_COLOR,
            center=(WINDOW_WIDTH // 2, 62),
        )
        if self.above_marker() is not None:  # M6.4: shells above the window
            self.draw_above_marker()

    def draw_above_marker(self):
        """M6.4: a gold triangle pointing up, over the shells' x, and the words under it (a
        picture and words, so it reads the same with the sound off)."""
        rect = self.above_marker_rect()
        _, words = self.above_marker()
        x = rect.centerx
        triangle = [(x, ABOVE_Y), (x - 10, ABOVE_Y + 13), (x + 10, ABOVE_Y + 13)]
        pygame.draw.polygon(self.screen, ABOVE_COLOR, triangle)
        pygame.draw.polygon(self.screen, OUTLINE, triangle, 2)
        draw_outlined_text(
            self.screen,
            words,
            self.small_font,
            LIGHT_TEXT,
            TEXT_COLOR,
            midtop=(x, ABOVE_Y + 15),
        )

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
    def hud_side_position(side, y=27):
        return (
            {"midleft": (48, y)}
            if side == "left"
            else {"midright": (WINDOW_WIDTH - 48, y)}
        )

    def hud_side_rects(self):
        """The area of each team's HUD lines, badge included (the banner must stay clear of it)."""
        rects = {}
        for side, (x, y) in self.hud_emblem_centres().items():
            main_line = self.font.render(self.hud_team_line(side), True, TEXT_COLOR)
            detail = self.tiny_font.render(self.hud_detail_line(side), True, TEXT_COLOR)
            rects[side] = (
                main_line.get_rect(**self.hud_side_position(side))
                .union(detail.get_rect(**self.hud_side_position(side, 47)))
                .union(pygame.Rect(x - 11, y - 11, 22, 22))
            )
        return rects

    def panel_items(self):
        """Every text in the panel (M6.2), as (group, text, font, colour, topleft), so draw_panel
        and the layout test use the same list. The groups: who acts (left), what to do (middle:
        the buttons are drawn apart, then ANGLE and POWER in the biggest font, then one help
        line), and what happened (right: the last shot's result first, then the log)."""
        items = []
        actor = PANEL_GROUPS["actor"]
        x, width = actor.left + 12, actor.width - 24
        lines = self.selected_info_lines()
        title_font = (
            self.font if self.font.size(lines[0])[0] <= width else self.small_font
        )
        title_color = tuple(
            min(255, c + 70) for c in TEAM_COLORS[self.battle.active_side]
        )
        items.append(("actor", lines[0], title_font, title_color, (x, actor.top + 8)))
        items.append(
            ("actor", lines[1], self.small_font, LIGHT_TEXT, (x, actor.top + 48))
        )
        y = actor.top + 70
        for text, color in ((lines[2], LIGHT_TEXT), (lines[3], DIM_TEXT)):
            for part in wrap_text(text, self.tiny_font, width):
                items.append(("actor", part, self.tiny_font, color, (x, y)))
                y += 14
        last_shot = self.last_shot_line()  # M6.4: the team's last shot, in gold, last
        if last_shot is not None:
            items.append(("actor", last_shot, self.tiny_font, BRASS, (x, y)))
        if not self.battle.is_over():
            (angle_label, power_label), (angle, power) = (
                self.aim_labels(),
                self.aim_values(),
            )
            items += [
                (
                    "controls",
                    angle_label,
                    self.tiny_font,
                    DIM_TEXT,
                    (CONTROL_X, AIM_LABEL_Y),
                ),
                (
                    "controls",
                    angle,
                    self.aim_font,
                    LIGHT_TEXT,
                    (CONTROL_X, AIM_VALUE_Y),
                ),
                (
                    "controls",
                    power_label,
                    self.tiny_font,
                    DIM_TEXT,
                    (POWER_X, AIM_LABEL_Y),
                ),
                ("controls", power, self.aim_font, LIGHT_TEXT, (POWER_X, AIM_VALUE_Y)),
            ]
        y = HINT_Y
        x = CONTROL_X + (
            22 if self.hint_icon() else 0
        )  # M6.3: room for the picture of the shells
        for part in wrap_text(
            self.action_hint_lines()[0], self.tiny_font, HINT_WIDTH - (x - CONTROL_X)
        )[:2]:
            items.append(("controls", part, self.tiny_font, LIGHT_TEXT, (x, y)))
            y += 14
        log = PANEL_GROUPS["log"]
        x, width = log.left + 12, log.width - 24
        items.append(
            ("log", self.log_header(), self.tiny_font, DIM_TEXT, (x, log.top + 8))
        )
        y = log.top + 26
        result = self.last_result or "No shot has landed yet."
        for part in wrap_text(result, self.small_font, width)[:2]:
            items.append(
                (
                    "log",
                    part,
                    self.small_font,
                    BRASS if self.last_result else DIM_TEXT,
                    (x, y),
                )
            )
            y += 18
        if self.practice:  # M6.4: the practice buttons take the log's place
            return items
        lines = []  # long lines (the AI's reasons) are wrapped
        for line in self.log[-LOG_LINES:]:
            lines.extend(wrap_text(line, self.tiny_font, width))
        room = max(0, (log.bottom - 4 - (y + 4)) // 15)
        shown = lines[-room:] if room else []
        for i, line in enumerate(
            shown
        ):  # the newest line bright, the older ones dimmer
            color = LIGHT_TEXT if i == len(shown) - 1 else DIM_TEXT
            items.append(("log", line, self.tiny_font, color, (x, y + 4 + 15 * i)))
        return items

    def panel_chip(self):
        """The status chip beside the angle (aim_status), as (text, topleft, filled), or None."""
        status = self.aim_status()
        if not status:
            return None
        return status, (CONTROL_X + 60, AIM_VALUE_Y + 1), "LOCKED" in status

    def panel_text_rects(self):
        """Where each panel text lands, by group (for the layout test)."""
        rects = {name: [] for name in PANEL_GROUPS}
        for group, text, font, _, topleft in self.panel_items():
            rects[group].append(pygame.Rect(topleft, font.size(text)))
        chip = self.panel_chip()
        if chip is not None:
            rects["controls"].append(chip_rect(chip[0], self.small_font, chip[1]))
        return rects

    def draw_panel(self):
        pygame.draw.rect(
            self.screen,
            PANEL_COLOR,
            (0, PANEL_TOP, WINDOW_WIDTH, WINDOW_HEIGHT - PANEL_TOP),
        )
        pygame.draw.line(
            self.screen, PANEL_EDGE, (0, PANEL_TOP), (WINDOW_WIDTH, PANEL_TOP), 2
        )
        for (
            group
        ) in PANEL_GROUPS.values():  # M6.2: three groups, told apart by the gaps
            pygame.draw.rect(self.screen, GROUP_COLOR, group, border_radius=8)
        if not self.ai_thinking():  # the chosen character's HP, under its name
            character = self.selected_character()
            bar = pygame.Rect(
                PANEL_GROUPS["actor"].left + 12, PANEL_GROUPS["actor"].top + 34, 200, 8
            )
            pygame.draw.rect(self.screen, (60, 60, 60), bar)
            pygame.draw.rect(
                self.screen,
                hp_bar_color(character),
                (bar.left, bar.top, hp_bar_width(character, bar.width), bar.height),
            )
            pygame.draw.rect(self.screen, OUTLINE, bar.inflate(2, 2), 1)
        for button in self.action_buttons.values():
            button.draw(self.screen, self.button_font(button), self.tiny_font)
        if self.practice:  # M6.4
            for button in self.practice_buttons.values():
                button.draw(self.screen, self.small_font)
        icon = self.hint_icon()
        if icon:
            draw_spread_icon(self.screen, (CONTROL_X + 9, HINT_Y + 7), icon, AIM_COLOR)
        if not self.battle.is_over():
            power = self.battle.cannons[self.battle.active_side].power
            bar = self.power_bar
            pygame.draw.rect(self.screen, (55, 70, 82), bar, border_radius=5)
            filled = round(bar.width * (power - MIN_POWER) / (MAX_POWER - MIN_POWER))
            if filled:
                pygame.draw.rect(
                    self.screen,
                    AIM_COLOR,
                    (bar.left, bar.top, filled, bar.height),
                    border_radius=5,
                )
            hover = bar.inflate(14, 16).collidepoint(pygame.mouse.get_pos())
            if not self.controls_locked():
                color = BRASS if hover or self.dragging_power else LIGHT_TEXT
                pygame.draw.circle(
                    self.screen, color, (bar.left + filled, bar.centery), 6
                )
        chip = self.panel_chip()
        if chip is not None:
            draw_chip(self.screen, chip[0], self.small_font, chip[1], chip[2])
        for _, text, font, color, topleft in self.panel_items():
            draw_text(self.screen, text, font, color, topleft=topleft)

    def result_rows(self):
        """The result panel's rows from top to bottom (M6.2): who won, why, the round, what next."""
        banner = result_banner_rect()
        return [
            ("title", banner.top),
            ("reason", banner.bottom + 12),
            ("rounds", banner.bottom + 44),
            ("buttons", self.rematch_button.rect.top),
        ]

    def result_badge_center(self):
        """The winner's badge, left of the title (a neutral equals sign for a draw)."""
        banner = result_banner_rect()
        return banner.left + 50, banner.top + 38

    def draw_result(self):
        """M6.2: a solid panel over the battlefield. In order: the winner's badge and title on its
        colour (a draw gets its own word, colour and neutral badge), then the reason in gold,
        the round, and the next step (Rematch in the same warm gold as PLACE COVER)."""
        banner = result_banner_rect()
        panel = pygame.Rect(banner.left, banner.top, banner.width, 270)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_EDGE, panel, 2, border_radius=8)
        # M4.1: the title band has the winner's colour, or DRAW_COLOR, so a win and a draw
        # can't be mistaken for each other.
        winner = self.battle.winner
        fill = DRAW_COLOR if winner == "draw" else TEAM_COLORS[winner]
        pygame.draw.rect(
            self.screen,
            fill,
            banner,
            border_top_left_radius=8,
            border_top_right_radius=8,
        )
        draw_badge(self.screen, winner, self.result_badge_center(), RESULT_BADGE_RADIUS)
        pygame.draw.circle(
            self.screen,
            (255, 255, 255),
            self.result_badge_center(),
            RESULT_BADGE_RADIUS,
            2,
        )
        draw_text(
            self.screen,
            self.result_title(),
            self.big_font,
            (255, 255, 255),
            center=(WINDOW_WIDTH // 2 + 24, banner.top + 36),
        )
        draw_text(
            self.screen,
            self.result_subtitle(),
            self.small_font,
            (245, 245, 245),
            center=(WINDOW_WIDTH // 2, banner.bottom - 14),
        )
        rows = dict(self.result_rows())
        draw_text(
            self.screen,
            self.result_reason(),
            self.font,
            BRASS,
            center=(WINDOW_WIDTH // 2, rows["reason"] + 12),
        )
        draw_text(
            self.screen,
            self.result_rounds(),
            self.small_font,
            DIM_TEXT,
            center=(WINDOW_WIDTH // 2, rows["rounds"] + 10),
        )
        self.rematch_button.draw(self.screen, self.font)
        self.change_teams_button.draw(self.screen, self.font)
        draw_text(
            self.screen,
            "R = rematch     M = sound     Esc = main menu",
            self.small_font,
            (220, 220, 220),
            center=(WINDOW_WIDTH // 2, 368),
        )


    def draw_pause_menu(self):
        """Show the paused match under the three menu choices."""
        veil = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        veil.fill(PANEL_COLOR + (150,))
        self.screen.blit(veil, (0, 0))
        panel = pause_panel_rect()
        pygame.draw.rect(self.screen, PANEL_COLOR, panel, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_EDGE, panel, 2, border_radius=8)
        middle = panel.centerx
        draw_text(
            self.screen,
            "Match paused",
            self.title_font,
            LIGHT_TEXT,
            center=(middle, panel.top + 36),
        )
        draw_text(
            self.screen,
            "Restart or Main Menu ends this match.",
            self.font,
            BRASS,
            center=(middle, panel.top + 72),
        )
        self.continue_button.draw(self.screen, self.font)
        self.restart_button.draw(self.screen, self.font)
        self.main_menu_button.draw(self.screen, self.font)
        draw_text(
            self.screen,
            "Esc or Enter: Continue     R: Restart     Backspace: Main Menu",
            self.small_font,
            DIM_TEXT,
            center=(middle, panel.bottom - 22),
        )


def open_window():
    """Start Pygame, open the game window and set up the keyboard. Returns the screen."""
    pygame.mixer.pre_init(
        SAMPLE_RATE, -16, 1, BUFFER
    )  # small buffer: sounds start without delay
    pygame.init()  # a missing audio device is not an error here (see sound.py)
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Castle Siege")
    pygame.key.set_repeat(250, 40)  # holding an arrow key keeps changing the aim
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
    game = Game(screen, intro=True)  # M6.2: the studio intro, once per launch
    veil = pygame.Surface(screen.get_size())
    veil.fill(PANEL_COLOR)
    previous_screen = (game.state, game.placing)
    transition_start = -150
    while game.running:
        for event in pygame.event.get():
            game.handle_event(event)
        game.update()
        game.draw()
        # Fade the new screen in without carrying the other player's cover across.
        now = pygame.time.get_ticks()
        current_screen = (game.state, game.placing)
        if current_screen != previous_screen:
            previous_screen = current_screen
            transition_start = now
        remaining = max(0, 1 - (now - transition_start) / 150)
        if remaining:
            veil.set_alpha(round(115 * remaining**2))
            screen.blit(veil, (0, 0))
        pygame.display.flip()
        clock.tick(FPS)
    pygame.quit()


if __name__ == "__main__":
    main()
