"""Shared look of the Castle Siege screens: colours, text, character figures and buttons.

Moved out of main.py unchanged in M3.4-B, so main.py can stay focused on the screens and
their input. M3.4-C added the running and firing poses; M4.1 the cracked and destroyed
blocks, HP-bar colours, outlined text and button hover. M6.2 added the Reflex swing gauge, the
path dots, the studio seal, the role portraits, contact shadows, chipped blocks and button
notes. M6.3 added the Gunner, Bombardier and Medic figures and portraits, the small card
portraits, the three-line / five-line special icons, the marked Airburst shell and its split
flash. Everything here only draws: nothing changes a rule. Uses Pygame, so (like main.py) it is
not imported by the game-rule modules.
"""
import math
from pathlib import Path

import pygame

from characters import Archer, Bombardier, Engineer, Gunner, Knight, Medic

SKY_COLOR = (160, 205, 235)
GROUND_COLOR = (66, 58, 44)           # M6.2: dark soil under the grass line (was green)
MENU_COLOR = (225, 232, 240)
PANEL_COLOR = (21, 30, 39)
PANEL_EDGE = (67, 86, 99)
BRASS = (246, 202, 119)
TEXT_COLOR = (25, 25, 35)
LIGHT_TEXT = (235, 238, 242)
DIM_TEXT = (160, 166, 176)
CANNON_COLOR = (55, 55, 60)
ACTIVE_RING_COLOR = (255, 215, 0)
AIM_COLOR = (255, 192, 85)
SHOT_COLOR = (20, 20, 20)
SHOT_RIM_LIGHT = (245, 245, 240)   # a light ring round a shell, so it shows on dark scenery
TEAM_COLORS = {"left": (60, 100, 200), "right": (200, 70, 60)}
STONE_COLORS = {"left": (150, 162, 195), "right": (196, 156, 142)}   # an undamaged block
SKIN = (240, 205, 170)
STEEL = (175, 180, 190)
WOOD = (130, 85, 45)
HARD_HAT = (240, 200, 40)
HOOD = (60, 130, 60)
DEFEATED_COLOR = (120, 120, 120)
DEFEND_COLOR = (90, 170, 255)
GUARD_COLOR = (30, 110, 235)       # Cover Guard: outline on the blocks and the GUARDED badge
COOLDOWN_COLOR = (255, 225, 120)  # these two are drawn on the green ground strip
READY_COLOR = (235, 240, 235)
BUTTON_COLOR = (70, 95, 130)
BUTTON_CHOSEN = (225, 170, 40)
BUTTON_OFF = (95, 98, 105)
OPEN_SLOT_COLOR = (226, 240, 252)   # an empty cover slot that can take a block
FLASH_COLOR = (255, 236, 120)       # the muzzle flash (M3.4-C): a yellow centre ...
FLASH_EDGE = (255, 150, 40)         # ... with an orange edge
RUN_LIFT = 6                        # a running figure is drawn this much higher, so its legs show
# M4.1 (cosmetic only).
LABEL_COLORS = {"left": (30, 60, 150), "right": (150, 40, 30)}   # names on the sky: darker, easier to read
HP_GOOD, HP_HURT, HP_LOW = (60, 190, 70), (230, 150, 40), (215, 50, 40)   # HP bar: > 1/2, > 1/4, the rest
BUTTON_HOVER = (95, 125, 170)       # a button under the mouse is a little lighter
BUTTON_CHOSEN_HOVER = (240, 192, 80)
CRACK_COLOR = (45, 45, 50)          # cracks on a damaged block
RUBBLE_COLOR = (105, 112, 122)      # the dashed outline where a block was destroyed
CLOSED_SLOT_COLOR = (150, 156, 166)  # the "x" on a cover slot that can't take a block now
POWER_SHOT_COLOR = (225, 85, 20)    # a Power Shot is bigger and orange
TRAIL_COLOR = (120, 128, 140)       # the dots a shot leaves behind it
DAMAGE_COLOR = (200, 30, 30)        # floating damage numbers
DRAW_COLOR = (150, 120, 50)         # the result banner of a draw (a win uses the winner's colour)
# Crack lines inside a 32 px block: the first appears below 80 % HP, the second below 40 %.
CRACKS = (((8, 4), (15, 14), (11, 24)), ((24, 6), (19, 17), (26, 28)))
# M4.2-A (drawing only). The battlefield background: a sky that lightens toward the horizon,
# pale far hills with two distant castles, nearer green hills, the ground and each team's flag.
SKY_TOP, SKY_HORIZON = (112, 164, 218), (196, 225, 242)
CLOUD_COLOR = (255, 255, 255, 70)     # see-through
HILL_FAR, CASTLE_FAR = (172, 198, 216), (158, 184, 206)   # pale: far away, not part of the battle
HILL_NEAR = (118, 152, 112)
GRASS_EDGE = (128, 176, 92)           # the lighter top line of the ground
# Team emblems, so the teams differ by shape as well as colour: LEFT a circle, RIGHT a diamond.
EMBLEM_COLOR = (255, 255, 255)
EMBLEM_Y = 19                          # the emblem's centre, from the top of a figure's 28 x 44 box
PLATE_COLOR = (255, 255, 255, 224)    # the see-through plate behind each name and HP bar
VALLEY_ART = Path(__file__).resolve().parent / "assets" / "siege-valley.jpg"
GUARD_STRIKE_COLOR = (235, 170, 20)   # M4.2-B: the Guarded Strike mark and its "+25%"
EXPIRED_COLOR = (105, 112, 124)       # the "expired" word when an unused Guarded Strike is lost
# M6.2 (drawing only).
OUTLINE = TEXT_COLOR                  # the one dark outline every foreground object uses
STONE_LAYER = (98, 90, 74)            # the narrow stony band just under the ground line
DEPTH_SHADE = (16, 24, 34)            # darkens the scenery behind the characters and the cover
SHADOW = (0, 0, 0, 100)               # contact shadows on the ground
PRIMARY_COLOR, PRIMARY_HOVER = BRASS, (255, 222, 156)   # the main button of a screen (warm gold)
HATCH_COLOR = (80, 83, 90)            # stripes on a button that can't be used now
PORTRAIT_BACK = (30, 44, 62)          # navy behind a role portrait on its card
CLOTH = (86, 98, 116)                 # a portrait's neutral clothes (the team shows on the card)
SEAL_EDGE = (170, 124, 52)            # the darker rim of the studio's gold seal
INTRO_COLOR = (12, 22, 40)            # the studio intro's deep blue
PATH_DOT = (250, 250, 245)            # Classic Aim's path dots
# M6.3 (drawing only): the three new roles, the Airburst shell and the heal number.
GUNNER_CAP = (70, 78, 52)             # the Gunner's flat cap
LEATHER = (120, 78, 44)               # the Bombardier's leather cap
BOMB_COLOR = (44, 44, 52)             # the split bomb on the Bombardier's back (and the Airburst shell)
BANDAGE = (244, 240, 228)             # the Medic's cap, strap and bag
MEDIC_CROSS = (210, 40, 40)
HEAL_COLOR = (30, 150, 60)            # the floating "+26" of a heal
CARD_PORTRAIT_SIZE = (66, 55)         # the small portrait on a selection card


def block_color(side, hp, max_hp):
    """A block gets darker as it loses HP, so every hit is visible.

    Full health keeps 100 % of the colour; a block with almost no HP left keeps 40 %.
    """
    shade = 0.4 + 0.6 * hp / max_hp
    return tuple(int(channel * shade) for channel in STONE_COLORS[side])


def hp_bar_width(character, full_width):
    """Length of a character's HP bar: full when unhurt, 0 when defeated."""
    return int(full_width * character.hp / character.max_hp)


def hp_bar_color(character):
    """Green above half HP, orange above a quarter, red at a quarter or less."""
    if character.hp * 2 > character.max_hp:
        return HP_GOOD
    if character.hp * 4 > character.max_hp:
        return HP_HURT
    return HP_LOW


def block_cracks(hp, max_hp):
    """How many cracks a block shows: none from 80 % of its HP up, one from 40 %, two below."""
    if hp * 10 >= 8 * max_hp:
        return 0
    if hp * 10 >= 4 * max_hp:
        return 1
    return 2


def block_outline(x, y, size, cracks):
    """The corners of a block (M6.2): a square, with a corner chipped off for each crack, so a
    damaged block also has a different shape (it still reads in grey). Only the picture changes:
    the block's hit box is always the full square."""
    chip = size // 5
    top_left = [(x, y)] if cracks < 2 else [(x, y + chip), (x + chip, y)]
    top_right = [(x + size - 1, y)] if cracks < 1 else [(x + size - 1 - chip, y), (x + size - 1, y + chip)]
    return top_left + top_right + [(x + size - 1, y + size - 1), (x, y + size - 1)]


def draw_block(screen, side, x, y, size, hp, max_hp):
    """A standing cover block: darker as it loses HP (block_color), with stone joints, cracks
    (block_cracks) and, once damaged, chipped corners (block_outline)."""
    base = block_color(side, hp, max_hp)
    cracks = block_cracks(hp, max_hp)
    outline = block_outline(x, y, size, cracks)
    pygame.draw.polygon(screen, base, outline)
    highlight = tuple(min(255, c + 27) for c in base)
    mortar = tuple(round(c * 0.72) for c in base)
    for row, joint in ((1, 11), (2, 22)):
        seam_y = y + row * size // 3
        joint_x = x + joint * size // 32
        pygame.draw.line(screen, mortar, (x + 2, seam_y), (x + size - 3, seam_y))
        pygame.draw.line(screen, mortar, (joint_x, seam_y - size // 3 + 2), (joint_x, seam_y))
    inset = 2 + (size // 5 if cracks else 0)      # the light top edge stops before a chipped corner
    pygame.draw.line(screen, highlight, (x + inset, y + 2), (x + size - 1 - inset, y + 2))
    pygame.draw.polygon(screen, OUTLINE, outline, 1)
    for crack in CRACKS[:cracks]:
        points = [(x + px * size // 32, y + py * size // 32) for px, py in crack]
        pygame.draw.lines(screen, CRACK_COLOR, False, points, 2)


def draw_rubble_outline(screen, x, y, size, on_ground=False):
    """A dashed outline where a block was destroyed, and (M6.2) a low heap of broken stone if it
    stood on the ground. Only a picture: it stops no shot."""
    last = size - 1
    for start in range(0, size, 10):
        end = min(start + 6, last)
        for a, b in (((start, 0), (end, 0)), ((start, last), (end, last)),
                     ((0, start), (0, end)), ((last, start), (last, end))):
            pygame.draw.line(screen, RUBBLE_COLOR, (x + a[0], y + a[1]), (x + b[0], y + b[1]))
    if on_ground:                                   # three broken stones in the bottom third
        for left, width, height in ((3, 11, 7), (12, 10, 9), (20, 9, 6)):
            stone = [(x + left, y + last), (x + left + 2, y + last - height),
                     (x + left + width, y + last - height + 2), (x + left + width, y + last)]
            pygame.draw.polygon(screen, RUBBLE_COLOR, stone)
            pygame.draw.polygon(screen, OUTLINE, stone, 1)


def draw_text(screen, text, font, color, **position):
    """Draw text placed by one keyword, e.g. center=(x, y) or topleft=(x, y)."""
    image = font.render(text, True, color)
    screen.blit(image, image.get_rect(**position))


def draw_outlined_text(screen, text, font, color, outline, **position):
    """Like draw_text, with a 1 px outline all round, so it can be read on any background."""
    image = font.render(text, True, color)
    rect = image.get_rect(**position)
    edge = font.render(text, True, outline)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        screen.blit(edge, rect.move(dx, dy))
    screen.blit(image, rect)


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


def draw_emblem(screen, side, center, size):
    """The team emblem at `center`: a circle for LEFT, a diamond for RIGHT (M4.2-A), so a
    player who can't tell red from blue can still tell the teams apart."""
    x, y = center
    if side == "left":
        pygame.draw.circle(screen, EMBLEM_COLOR, center, size)
    else:
        reach = size + 1                   # a diamond looks smaller than a circle of the same size
        pygame.draw.polygon(screen, EMBLEM_COLOR, [(x, y - reach), (x + reach, y), (x, y + reach), (x - reach, y)])


def draw_guard_mark(screen, rect, ready):
    """The Guarded Strike mark (M4.2-B): a four-pointed star, hollow while it waits for the
    team's next turn, filled when this turn's Attack is stronger."""
    x, y = rect.center
    left, top, right, bottom = rect.left, rect.top, rect.right - 1, rect.bottom - 1
    points = [(x, top), (x + 2, y - 2), (right, y), (x + 2, y + 2), (x, bottom), (x - 2, y + 2), (left, y), (x - 2, y - 2)]
    pygame.draw.polygon(screen, GUARD_STRIKE_COLOR, points, 0 if ready else 1)


def draw_badge(screen, side, center, radius):
    """The team emblem on a disc of the team's colour, for light backgrounds (HUD, flags).
    side "draw" (M6.2, the result of a draw) gives a neutral disc with an equals sign."""
    if side == "draw":
        pygame.draw.circle(screen, DRAW_COLOR, center, radius)
        x, y = center
        for dy in (-radius // 4, radius // 4):
            pygame.draw.line(screen, EMBLEM_COLOR, (x - radius // 2, y + dy), (x + radius // 2, y + dy), 3)
        return
    pygame.draw.circle(screen, TEAM_COLORS[side], center, radius)
    draw_emblem(screen, side, center, radius // 2)


_plates = {}


def draw_plate(screen, rect):
    """A see-through light plate (behind a name and its HP bar), so they read on any scenery."""
    size = (rect.width, rect.height)
    if size not in _plates:               # made once per size, then only copied
        plate = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.rect(plate, PLATE_COLOR, plate.get_rect(), border_radius=5)
        _plates[size] = plate
    screen.blit(_plates[size], rect.topleft)


def make_background(width, height, ground_y, art=None):
    """The battlefield behind everything (M4.2-A), drawn once when the game starts: a sky
    gradient, a few clouds, far hills with two small castles, near hills, the ground and a
    flag for each team. Only a picture: nothing in it stops a shot or moves anything."""
    surface = pygame.Surface((width, height))
    for y in range(ground_y):
        t = y / (ground_y - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(SKY_TOP, SKY_HORIZON))
        pygame.draw.line(surface, color, (0, y), (width - 1, y))
    clouds = pygame.Surface((width, ground_y), pygame.SRCALPHA)
    for x, y, w, h in ((210, 150, 190, 40), (270, 134, 120, 34), (760, 112, 230, 46), (850, 96, 140, 34),
                       (1080, 190, 170, 34)):
        pygame.draw.ellipse(clouds, CLOUD_COLOR, (x - w // 2, y - h // 2, w, h))
    surface.blit(clouds, (0, 0))
    far = [(x, ground_y - 78 - 22 * math.sin(x / 160) - 12 * math.sin(x / 57 + 1.3)) for x in range(0, width + 8, 8)]
    pygame.draw.polygon(surface, HILL_FAR, [(0, ground_y)] + far + [(width, ground_y)])
    for center_x in (520, 770):           # two distant castles on the far hills, in the open middle
        base = ground_y - 70
        for dx, w, h in ((-22, 12, 34), (-10, 20, 24), (10, 12, 30)):
            pygame.draw.rect(surface, CASTLE_FAR, (center_x + dx, base - h, w, h + 40))
            for notch in range(0, w, 6):  # battlements
                pygame.draw.rect(surface, CASTLE_FAR, (center_x + dx + notch, base - h - 4, 3, 4))
    near = [(x, ground_y - 34 - 14 * math.sin(x / 110 + 2.0) - 6 * math.sin(x / 37)) for x in range(0, width + 8, 8)]
    pygame.draw.polygon(surface, HILL_NEAR, [(0, ground_y)] + near + [(width, ground_y)])
    if art is not None:
        surface.blit(art, (0, 0), (0, 0, width, ground_y))
    shade_depth(surface, width, ground_y)
    draw_ground(surface, width, height, ground_y)
    for side, pole_x in (("left", 14), ("right", width - 15)):     # a flag behind each team
        pygame.draw.line(surface, WOOD, (pole_x, ground_y - 164), (pole_x, ground_y), 3)
        reach = 32 if side == "left" else -32
        cloth = [(pole_x, ground_y - 162), (pole_x + reach, ground_y - 152), (pole_x, ground_y - 138)]
        pygame.draw.polygon(surface, TEAM_COLORS[side], cloth)
        draw_emblem(surface, side, (pole_x + reach // 3, ground_y - 151), 3)
    return surface


def shade_depth(surface, width, ground_y, top=440, strongest=150):
    """M6.2: darken the scenery from y `top` down to the ground, where the characters, cover and
    cannons stand, so the busy trees behind them fade back and the units stand out."""
    band = pygame.Surface((width, ground_y - top), pygame.SRCALPHA)
    for row in range(ground_y - top):
        alpha = round(strongest * (row / (ground_y - top - 1)) ** 1.4)
        pygame.draw.line(band, DEPTH_SHADE + (alpha,), (0, row), (width - 1, row))
    surface.blit(band, (0, top))


def draw_ground(surface, width, height, ground_y):
    """M6.2: the ground the shots hit (y = ground_y and below): a grass line with gaps, a narrow
    stony band under it, then dark soil. The line is exactly where the rules put the ground."""
    pygame.draw.rect(surface, GROUND_COLOR, (0, ground_y, width, height - ground_y))
    pygame.draw.rect(surface, STONE_LAYER, (0, ground_y + 2, width, 4))
    for x in range(5, width, 29):                  # pebbles along the stony band
        pygame.draw.ellipse(surface, GROUND_COLOR, (x, ground_y + 3, 7, 3))
    for x in range(0, width, 24):                  # grass in short pieces, with small gaps
        pygame.draw.line(surface, GRASS_EDGE, (x, ground_y), (x + 18, ground_y), 2)
    for x in range(11, width, 47):                 # a few stones lower down
        pygame.draw.ellipse(surface, STONE_LAYER, (x, height - 6, 9, 4))


_shadows = {}


def draw_contact_shadow(screen, center_x, ground_y, width):
    """M6.2: a short dark oval where something stands on the ground (a character, a block)."""
    if width not in _shadows:                      # made once per width, then only copied
        oval = pygame.Surface((width, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(oval, SHADOW, oval.get_rect())
        _shadows[width] = oval
    screen.blit(_shadows[width], (round(center_x - width / 2), ground_y - 3))


def load_valley_art(width, height):
    """Load the scenery once. The drawn landscape is also usable without the image."""
    try:
        art = pygame.image.load(VALLEY_ART.as_posix())
    except (FileNotFoundError, pygame.error):
        return None
    return pygame.transform.smoothscale(art, (width, height))


def make_menu_background(width, height, art, fallback):
    """Reuse the valley with a tint that keeps the setup labels readable."""
    surface = pygame.Surface((width, height))
    surface.blit(art if art is not None else pygame.transform.smoothscale(fallback, (width, height)), (0, 0))
    tint = pygame.Surface((width, height), pygame.SRCALPHA)
    tint.fill((9, 18, 27, 176))
    surface.blit(tint, (0, 0))
    return surface


def draw_figure(screen, role, center_x, top, facing, body_color, team=None):
    """A simple figure for a character role, standing in the 28 x 44 box whose top is `top`.

    `facing` is +1 (looking right) or -1 (looking left); the shield, bow or hammer
    is held on that side. `team` ("left" / "right") adds the team emblem on the chest.
    """
    front = center_x + facing * 11
    if role is Bombardier:                       # M6.3: the split bomb on its back, behind the body
        bomb = (center_x - facing * 10, top + 23)
        spark = (bomb[0] - facing * 3, top + 11)
        pygame.draw.line(screen, OUTLINE, (bomb[0], bomb[1] - 6), spark, 2)            # the fuse
        pygame.draw.circle(screen, FLASH_COLOR, spark, 2)
        pygame.draw.circle(screen, BOMB_COLOR, bomb, 7)
        pygame.draw.circle(screen, OUTLINE, bomb, 7, 1)
        pygame.draw.line(screen, STEEL, (bomb[0] - 5, bomb[1]), (bomb[0] + 5, bomb[1]), 1)   # split seams
        pygame.draw.line(screen, STEEL, (bomb[0], bomb[1] - 5), (bomb[0], bomb[1] + 5), 1)
    pygame.draw.rect(screen, body_color, (center_x - 9, top + 15, 18, 29), border_radius=4)
    pygame.draw.rect(screen, TEXT_COLOR, (center_x - 9, top + 15, 18, 29), 1, border_radius=4)
    pygame.draw.line(screen, TEXT_COLOR, (center_x - 7, top + 35), (center_x + 7, top + 35), 2)
    for dx in (-5, 5):
        pygame.draw.line(screen, TEXT_COLOR, (center_x + dx - 2, top + 43),
                         (center_x + dx + 2, top + 43), 3)
    pygame.draw.circle(screen, SKIN, (center_x, top + 8), 7)
    pygame.draw.circle(screen, OUTLINE, (center_x, top + 8), 7, 1)                      # M6.2: outlined
    if role is Knight:
        pygame.draw.rect(screen, STEEL, (center_x - 7, top, 14, 7),
                         border_top_left_radius=6, border_top_right_radius=6)           # helmet
        pygame.draw.line(screen, TEXT_COLOR, (center_x - 5, top + 6), (center_x + 5, top + 6), 2)
        pygame.draw.rect(screen, STEEL, (front - 5, top + 18, 10, 16), border_radius=3)  # shield
        pygame.draw.rect(screen, TEXT_COLOR, (front - 5, top + 18, 10, 16), 1, border_radius=3)
        pygame.draw.line(screen, BRASS, (front, top + 21), (front, top + 30), 2)
    elif role is Archer:
        pygame.draw.polygon(screen, HOOD, [(center_x - 8, top + 8), (center_x + 8, top + 8),
                                           (center_x, top - 3)])                        # hood
        bow = pygame.Rect(front - 6, top + 12, 12, 26)
        if facing > 0:
            pygame.draw.arc(screen, WOOD, bow, -math.pi / 2, math.pi / 2, 3)
        else:
            pygame.draw.arc(screen, WOOD, bow, math.pi / 2, 3 * math.pi / 2, 3)
        pygame.draw.line(screen, LIGHT_TEXT, (front, top + 12), (front, top + 38), 1)    # string
    elif role is Engineer:
        pygame.draw.rect(screen, HARD_HAT, (center_x - 8, top, 16, 6),
                         border_top_left_radius=7, border_top_right_radius=7)           # hard hat
        pygame.draw.line(screen, WOOD, (front, top + 20), (front, top + 40), 3)          # hammer
        pygame.draw.rect(screen, STEEL, (front - 5, top + 16, 10, 6))
        pygame.draw.line(screen, WOOD, (center_x - 8, top + 6), (center_x + 8, top + 6), 2)
    elif role is Gunner:                         # M6.3: flat cap, double shoulder guards, three-shell badge
        pygame.draw.rect(screen, GUNNER_CAP, (center_x - 7, top, 14, 5),
                         border_top_left_radius=4, border_top_right_radius=4)
        pygame.draw.line(screen, GUNNER_CAP, (center_x, top + 4), (center_x + facing * 10, top + 5), 2)   # brim
        for dx in (-12, 6):
            for dy in (14, 19):
                pygame.draw.rect(screen, STEEL, (center_x + dx, top + dy, 6, 5), border_radius=2)
                pygame.draw.rect(screen, OUTLINE, (center_x + dx, top + dy, 6, 5), 1, border_radius=2)
        for dx, dy in ((-4, 30), (0, 28), (4, 30)):
            pygame.draw.circle(screen, BOMB_COLOR, (center_x + dx, top + dy), 2)
    elif role is Bombardier:                     # leather cap and goggles (the bomb is behind the body)
        pygame.draw.rect(screen, LEATHER, (center_x - 7, top, 14, 6),
                         border_top_left_radius=6, border_top_right_radius=6)
        pygame.draw.circle(screen, BRASS, (center_x + facing * 3, top + 5), 2)
    elif role is Medic:                          # white cap with a cross, a strap across the body, a bag
        pygame.draw.rect(screen, BANDAGE, (center_x - 7, top, 14, 5),
                         border_top_left_radius=5, border_top_right_radius=5)
        pygame.draw.line(screen, MEDIC_CROSS, (center_x - 2, top + 2), (center_x + 2, top + 2), 1)
        pygame.draw.line(screen, MEDIC_CROSS, (center_x, top), (center_x, top + 4), 1)
        pygame.draw.line(screen, BANDAGE, (center_x - facing * 8, top + 16), (front - facing * 2, top + 31), 3)
        bag = pygame.Rect(front - 5, top + 29, 10, 9)
        pygame.draw.rect(screen, BANDAGE, bag, border_radius=2)
        pygame.draw.rect(screen, OUTLINE, bag, 1, border_radius=2)
        pygame.draw.line(screen, MEDIC_CROSS, (bag.centerx - 3, bag.centery), (bag.centerx + 3, bag.centery), 2)
        pygame.draw.line(screen, MEDIC_CROSS, (bag.centerx, bag.centery - 3), (bag.centerx, bag.centery + 3), 2)
    if team is not None:
        draw_emblem(screen, team, (center_x, top + EMBLEM_Y), 3)


def draw_running_figure(screen, role, center_x, top, facing, body_color, frame, team=None):
    """A figure running to or from the cannon (M3.4-C). `top` is where the standing figure's
    top would be. The body is lifted a little so two legs show under it; every 5 frames the
    legs swap and the body bobs up or down 2 px."""
    phase = (frame // 5) % 2
    stride = 5 if phase else -5
    ground = top + 44
    for hip_x, step in ((center_x - 3, stride), (center_x + 3, -stride)):
        pygame.draw.line(screen, TEXT_COLOR, (hip_x, ground - 12), (hip_x + step, ground - 1), 3)
    draw_figure(screen, role, center_x, top - RUN_LIFT - 2 * phase, facing, body_color, team)


def draw_firing_figure(screen, role, center_x, top, facing, body_color, team=None):
    """A figure firing the cannon (M3.4-C): standing, one arm stretched out to the cannon."""
    draw_figure(screen, role, center_x, top, facing, body_color, team)
    pygame.draw.line(screen, SKIN, (center_x + facing * 6, top + 19), (center_x + facing * 17, top + 26), 3)


# ----- M6.2: aiming aids, the studio seal and the role portraits ----------------------------

def arc_point(pivot, facing, degrees, radius):
    """The point `radius` px from `pivot` at `degrees` above the horizon, on the `facing` side."""
    radians = math.radians(degrees)
    return (pivot[0] + facing * radius * math.cos(radians), pivot[1] - radius * math.sin(radians))


def draw_swing_gauge(screen, pivot, facing, low, high, angle, radius, locked):
    """Reflex Aim's gauge around a cannon: an arc from the swing's low to its high limit with a
    short tick at each end, and a pointer at `angle`. Everything has a dark outline, so it reads
    on the sky and on the trees. A locked pointer is gold and sits in a notch across the arc."""
    arc = [arc_point(pivot, facing, a, radius) for a in range(low, high, 2)] + [arc_point(pivot, facing, high, radius)]
    pygame.draw.lines(screen, OUTLINE, False, arc, 7)
    pygame.draw.lines(screen, AIM_COLOR, False, arc, 3)
    for end in (low, high):
        pygame.draw.line(screen, OUTLINE, arc_point(pivot, facing, end, radius - 9),
                         arc_point(pivot, facing, end, radius + 9), 6)
        pygame.draw.line(screen, LIGHT_TEXT, arc_point(pivot, facing, end, radius - 8),
                         arc_point(pivot, facing, end, radius + 8), 2)
    tip = arc_point(pivot, facing, angle, radius + 2)
    if locked:
        pygame.draw.line(screen, OUTLINE, arc_point(pivot, facing, angle, radius - 12),
                         arc_point(pivot, facing, angle, radius + 12), 6)
        pygame.draw.line(screen, BRASS, arc_point(pivot, facing, angle, radius - 11),
                         arc_point(pivot, facing, angle, radius + 11), 2)
    pygame.draw.circle(screen, OUTLINE, (round(tip[0]), round(tip[1])), 8)
    pygame.draw.circle(screen, BRASS if locked else LIGHT_TEXT, (round(tip[0]), round(tip[1])), 6)


def draw_path_dots(screen, points):
    """Classic Aim's path dots: small light dots with a dark rim, so they read on any scenery."""
    for x, y in points:
        center = (round(x), round(y))
        pygame.draw.circle(screen, OUTLINE, center, 4)
        pygame.draw.circle(screen, PATH_DOT, center, 3)


def chip_rect(text, font, topleft):
    """The box draw_chip draws for `text`: 8 px of room left and right, 4 above and below."""
    width, height = font.size(text)
    return pygame.Rect(topleft, (width + 16, height + 8))


def draw_chip(screen, text, font, topleft, filled):
    """A short status in a rounded box (the Reflex status, THINKING, the path switch). A filled
    chip (gold, dark text) means "settled"; an outlined one (light text) means "going on"."""
    rect = chip_rect(text, font, topleft)
    if filled:
        pygame.draw.rect(screen, BRASS, rect, border_radius=7)
    pygame.draw.rect(screen, BRASS, rect, 2, border_radius=7)
    draw_text(screen, text, font, TEXT_COLOR if filled else LIGHT_TEXT, center=rect.center)
    return rect


def draw_six_seal(screen, center, size):
    """The studio's seal: a warm gold square with rounded corners and six dark pips, like the
    six on a die (two of them: Double Six)."""
    rect = pygame.Rect(0, 0, size, size)
    rect.center = center
    pygame.draw.rect(screen, BRASS, rect, border_radius=size // 6)
    pygame.draw.rect(screen, SEAL_EDGE, rect, 3, border_radius=size // 6)
    for dx in (-0.22, 0.22):
        for dy in (-0.27, 0, 0.27):
            pip = (round(center[0] + dx * size), round(center[1] + dy * size))
            pygame.draw.circle(screen, INTRO_COLOR, pip, max(3, size // 11))


PORTRAIT_SIZE = (120, 100)
_portraits = {}


def portrait(role, facing):
    """A half-body portrait of a role, 120 x 100 px, drawn once in code and then reused (flipped
    for the RIGHT team). The shapes say the role: the Knight's broad shoulder plates and shield,
    the Archer's pointed hood and slanted bow, the Engineer's low hard hat and short hammer, and
    (M6.3) the Gunner's double shoulder guards and three-shell badge, the Bombardier's split bomb
    on its back, the Medic's bag on a strap across the body. The clothes are neutral, so one
    portrait serves both teams; the card shows the team."""
    key = (role, facing)
    if key not in _portraits:
        image = pygame.Surface(PORTRAIT_SIZE, pygame.SRCALPHA)
        draw_bust(image, role)
        _portraits[key] = image if facing > 0 else pygame.transform.flip(image, True, False)
    return _portraits[key]


def card_portrait(role, facing):
    """The portrait made smaller for a selection card (M6.3: six cards per team), made once."""
    key = (role, facing, "card")
    if key not in _portraits:
        _portraits[key] = pygame.transform.smoothscale(portrait(role, facing), CARD_PORTRAIT_SIZE)
    return _portraits[key]


def shape(surface, color, points, edge=2):
    """A filled polygon with the dark outline."""
    pygame.draw.polygon(surface, color, points)
    pygame.draw.polygon(surface, OUTLINE, points, edge)


def draw_bust(surface, role):
    """The portrait itself, facing right, on a 120 x 100 surface (see portrait)."""
    shape(surface, CLOTH, [(16, 100), (22, 74), (40, 63), (80, 63), (98, 74), (104, 100)])   # shoulders
    pygame.draw.lines(surface, BRASS, False, [(80, 64), (97, 75), (102, 99)], 2)   # warm rim light
    pygame.draw.rect(surface, SKIN, (52, 50, 16, 14))                              # neck
    pygame.draw.circle(surface, SKIN, (60, 38), 16)
    pygame.draw.circle(surface, OUTLINE, (60, 38), 16, 2)
    pygame.draw.circle(surface, OUTLINE, (67, 37), 2)                              # an eye, looking ahead
    if role is Knight:
        shape(surface, STEEL, [(42, 38), (44, 24), (54, 18), (66, 18), (76, 24), (78, 38), (78, 44), (42, 44)])
        pygame.draw.line(surface, OUTLINE, (56, 36), (78, 36), 3)                  # the visor slit
        for box in ((10, 60, 38, 22), (72, 60, 38, 22)):                         # broad shoulder plates
            pygame.draw.ellipse(surface, STEEL, box)
            pygame.draw.ellipse(surface, OUTLINE, box, 2)
        shape(surface, STEEL, [(78, 66), (108, 66), (108, 84), (93, 99), (78, 84)])   # kite shield
        pygame.draw.line(surface, BRASS, (93, 69), (93, 93), 3)
        pygame.draw.line(surface, BRASS, (82, 76), (104, 76), 3)
    elif role is Archer:
        shape(surface, HOOD, [(40, 60), (40, 36), (48, 22), (62, 4), (68, 20), (80, 34), (80, 60), (70, 52),
                              (72, 36), (60, 28), (48, 36), (50, 52)])         # the pointed hood
        pygame.draw.line(surface, WOOD, (30, 66), (84, 99), 4)                    # quiver strap
        # The bow: a line slanting from (74, 10) to (110, 96), bent outward by up to 12 px.
        bow = [(74 + 36 * t + 11 * math.sin(math.pi * t), 10 + 86 * t - 4.6 * math.sin(math.pi * t))
               for t in (i / 10 for i in range(11))]
        pygame.draw.lines(surface, OUTLINE, False, bow, 6)
        pygame.draw.lines(surface, WOOD, False, bow, 3)                           # the slanted bow ...
        pygame.draw.line(surface, LIGHT_TEXT, bow[0], bow[-1], 1)                 # ... and its string
    elif role is Engineer:
        shape(surface, HARD_HAT, [(42, 34), (44, 24), (52, 18), (68, 18), (76, 24), (78, 34)])
        shape(surface, HARD_HAT, [(34, 33), (88, 33), (88, 39), (34, 39)])         # the low, wide brim
        pygame.draw.rect(surface, WOOD, (22, 88, 76, 7))                          # tool belt
        pygame.draw.rect(surface, OUTLINE, (22, 88, 76, 7), 1)
        pygame.draw.line(surface, OUTLINE, (80, 99), (98, 64), 7)
        pygame.draw.line(surface, WOOD, (80, 99), (98, 64), 4)                    # a short hammer
        shape(surface, STEEL, [(86, 58), (108, 68), (104, 76), (82, 66)])
    elif role is Gunner:                                                          # M6.3
        for box in ((8, 58, 38, 18), (12, 70, 34, 16), (74, 58, 38, 18), (74, 70, 34, 16)):
            pygame.draw.ellipse(surface, STEEL, box)                              # double shoulder guards
            pygame.draw.ellipse(surface, OUTLINE, box, 2)
        shape(surface, GUNNER_CAP, [(43, 31), (45, 22), (56, 17), (70, 18), (78, 24), (79, 31)])   # flat cap ...
        shape(surface, GUNNER_CAP, [(76, 28), (94, 30), (94, 35), (76, 34)])     # ... with its brim forward
        pygame.draw.circle(surface, BRASS, (60, 86), 10)                          # the three-shell badge
        pygame.draw.circle(surface, OUTLINE, (60, 86), 10, 2)
        for dx, dy in ((-5, 3), (0, -3), (5, 3)):
            pygame.draw.circle(surface, BOMB_COLOR, (60 + dx, 86 + dy), 3)
    elif role is Bombardier:
        pygame.draw.line(surface, OUTLINE, (26, 32), (34, 18), 3)                 # the fuse ...
        pygame.draw.circle(surface, FLASH_COLOR, (35, 16), 4)                     # ... and its spark
        pygame.draw.circle(surface, BOMB_COLOR, (24, 50), 19)                     # the split bomb on its back
        pygame.draw.circle(surface, OUTLINE, (24, 50), 19, 2)
        for start, end in (((8, 50), (40, 50)), ((24, 34), (24, 66)), ((13, 39), (35, 61))):
            pygame.draw.line(surface, STEEL, start, end, 2)                        # seams where it splits
        pygame.draw.line(surface, LEATHER, (34, 66), (90, 99), 5)                 # its strap
        shape(surface, LEATHER, [(43, 33), (45, 22), (55, 17), (67, 17), (76, 23), (78, 33)])   # leather cap
        pygame.draw.line(surface, OUTLINE, (44, 31), (78, 31), 4)                 # goggles strap ...
        for center in ((56, 30), (70, 30)):
            pygame.draw.circle(surface, BRASS, center, 6)                         # ... and lenses
            pygame.draw.circle(surface, OUTLINE, center, 6, 2)
    elif role is Medic:
        shape(surface, BANDAGE, [(43, 32), (45, 22), (55, 17), (67, 17), (76, 23), (78, 32)])   # white cap
        pygame.draw.line(surface, MEDIC_CROSS, (54, 25), (66, 25), 4)
        pygame.draw.line(surface, MEDIC_CROSS, (60, 19), (60, 31), 4)
        pygame.draw.line(surface, OUTLINE, (30, 64), (88, 98), 8)
        pygame.draw.line(surface, BANDAGE, (30, 64), (88, 98), 5)                 # the strap across the body
        bag = pygame.Rect(76, 76, 34, 24)
        pygame.draw.rect(surface, BANDAGE, bag, border_radius=4)                  # the bag, with a red cross
        pygame.draw.rect(surface, OUTLINE, bag, 2, border_radius=4)
        pygame.draw.line(surface, MEDIC_CROSS, (bag.centerx - 7, bag.centery), (bag.centerx + 7, bag.centery), 4)
        pygame.draw.line(surface, MEDIC_CROSS, (bag.centerx, bag.centery - 7), (bag.centerx, bag.centery + 7), 4)


def draw_spread_icon(screen, center, shells, color):
    """A small picture of a special's shells (M6.3), about 16 px: three straight lines in a fan for
    the Triple Volley (shells=3), or one line rising to a point and five short lines falling from it
    for the Airburst (shells=5). Drawn with the dark outline under it, so it reads on any colour."""
    x, y = center
    if shells == 3:
        lines = [((x - 8, y + 7), arc_point((x - 8, y + 7), 1, degrees, 17)) for degrees in (20, 42, 64)]
    else:
        top = (x - 1, y - 6)
        lines = [((x - 8, y + 7), top)] + [(top, arc_point(top, 1, degrees, 11)) for degrees in (-10, -35, -60, -85, -110)]
    for width, line_color in ((4, OUTLINE), (2, color)):
        for start, end in lines:
            pygame.draw.line(screen, line_color, start, end, width)


def draw_marked_shell(screen, center):
    """The Airburst shell before it splits (M6.3): bigger and darker, with a gold ring and five
    notches round it, one for each small shell it will become."""
    pygame.draw.circle(screen, SHOT_RIM_LIGHT, center, 9)
    pygame.draw.circle(screen, BOMB_COLOR, center, 7)
    pygame.draw.circle(screen, BRASS, center, 7, 2)
    for degrees in range(90, 450, 72):
        notch = arc_point(center, 1, degrees, 11)
        pygame.draw.circle(screen, BRASS, (round(notch[0]), round(notch[1])), 2)


def draw_split_flash(screen, center, progress):
    """Where the Airburst shell split (M6.3): a gold ring that grows and five rays that fade,
    `progress` going from 0 (the moment of the split) to 1."""
    radius = round(6 + 18 * progress)
    width = max(1, round(4 * (1 - progress)))
    pygame.draw.circle(screen, OUTLINE, center, radius + 1, width + 2)
    pygame.draw.circle(screen, FLASH_COLOR, center, radius, width)
    for degrees in (-30, -60, -90, -120, -150):
        start = arc_point(center, 1, degrees, radius + 3)
        end = arc_point(center, 1, degrees, radius + 3 + round(8 * (1 - progress)))
        pygame.draw.line(screen, FLASH_EDGE, start, end, 2)


class Button:
    """A clickable rectangle with a label. A disabled button is greyed out and ignores clicks.

    M6.2: a `primary` button (the main step of a screen: PLACE COVER, ATTACK, Rematch) is warm
    gold. A `note` (a few words, e.g. "ready in 2") is written small under the label, and a
    disabled button is also striped, so "can't use it now" is a shape as well as a colour.
    """

    def __init__(self, x, y, width, height, label, primary=False):
        self.rect = pygame.Rect(x, y, width, height)
        self.label = label
        self.enabled = True
        self.chosen = False         # drawn highlighted (e.g. the chosen team size)
        self.primary = primary
        self.note = ""

    def is_clicked(self, pos):
        return self.enabled and self.rect.collidepoint(pos)

    def draw(self, screen, font, note_font=None):
        hovered = self.enabled and self.rect.collidepoint(pygame.mouse.get_pos())   # M4.1
        if not self.enabled:
            fill, text_color = BUTTON_OFF, DIM_TEXT
        elif self.chosen:
            fill, text_color = (BUTTON_CHOSEN_HOVER if hovered else BUTTON_CHOSEN), TEXT_COLOR
        elif self.primary:
            fill, text_color = (PRIMARY_HOVER if hovered else PRIMARY_COLOR), TEXT_COLOR
        else:
            fill, text_color = (BUTTON_HOVER if hovered else BUTTON_COLOR), LIGHT_TEXT
        pygame.draw.rect(screen, fill, self.rect, border_radius=6)
        if not self.enabled:                       # diagonal stripes, kept inside the button
            screen.set_clip(self.rect)
            for x in range(self.rect.left - self.rect.height, self.rect.right, 10):
                pygame.draw.line(screen, HATCH_COLOR, (x, self.rect.bottom), (x + self.rect.height, self.rect.top), 3)
            screen.set_clip(None)
        pygame.draw.rect(screen, TEXT_COLOR, self.rect, 2, border_radius=6)
        if self.note and note_font is not None:
            draw_text(screen, self.label, font, text_color, center=(self.rect.centerx, self.rect.centery - 6))
            draw_text(screen, self.note, note_font, text_color, center=(self.rect.centerx, self.rect.bottom - 9))
        else:
            draw_text(screen, self.label, font, text_color, center=self.rect.center)
