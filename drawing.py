"""Shared look of the Castle Siege screens: colours, text, character figures and buttons.

Moved out of main.py unchanged in M3.4-B, so main.py can stay focused on the screens and
their input. M3.4-C added the running and firing poses; M4.1 the cracked and destroyed
blocks, HP-bar colours, outlined text and button hover. Everything here only draws: nothing
changes a rule. Uses Pygame, so (like main.py) it is not imported by the game-rule modules.
"""
import math

import pygame

from characters import Archer, Knight

SKY_COLOR = (160, 205, 235)
GROUND_COLOR = (96, 140, 72)
MENU_COLOR = (225, 232, 240)
PANEL_COLOR = (38, 46, 58)
TEXT_COLOR = (25, 25, 35)
LIGHT_TEXT = (235, 238, 242)
DIM_TEXT = (160, 166, 176)
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
PLATE_COLOR = (255, 255, 255, 150)    # the see-through plate behind each name and HP bar


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


def draw_block(screen, side, x, y, size, hp, max_hp):
    """A standing cover block: darker as it loses HP (block_color), with cracks (block_cracks)."""
    pygame.draw.rect(screen, block_color(side, hp, max_hp), (x, y, size, size))
    pygame.draw.rect(screen, TEXT_COLOR, (x, y, size, size), 1)
    for crack in CRACKS[:block_cracks(hp, max_hp)]:
        points = [(x + px * size // 32, y + py * size // 32) for px, py in crack]
        pygame.draw.lines(screen, CRACK_COLOR, False, points, 2)


def draw_rubble_outline(screen, x, y, size):
    """A dashed outline where a block was destroyed. Only a picture: it stops no shot."""
    last = size - 1
    for start in range(0, size, 10):
        end = min(start + 6, last)
        for a, b in (((start, 0), (end, 0)), ((start, last), (end, last)),
                     ((0, start), (0, end)), ((last, start), (last, end))):
            pygame.draw.line(screen, RUBBLE_COLOR, (x + a[0], y + a[1]), (x + b[0], y + b[1]))


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


def draw_badge(screen, side, center, radius):
    """The team emblem on a disc of the team's colour, for light backgrounds (HUD, flags)."""
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


def make_background(width, height, ground_y):
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
    pygame.draw.rect(surface, GROUND_COLOR, (0, ground_y, width, height - ground_y))
    pygame.draw.line(surface, GRASS_EDGE, (0, ground_y), (width - 1, ground_y), 2)
    for side, pole_x in (("left", 14), ("right", width - 15)):     # a flag behind each team
        pygame.draw.line(surface, WOOD, (pole_x, ground_y - 164), (pole_x, ground_y), 3)
        reach = 32 if side == "left" else -32
        cloth = [(pole_x, ground_y - 162), (pole_x + reach, ground_y - 152), (pole_x, ground_y - 138)]
        pygame.draw.polygon(surface, TEAM_COLORS[side], cloth)
        draw_emblem(surface, side, (pole_x + reach // 3, ground_y - 151), 3)
    return surface


def draw_figure(screen, role, center_x, top, facing, body_color, team=None):
    """A simple figure for a character role, standing in the 28 x 44 box whose top is `top`.

    `facing` is +1 (looking right) or -1 (looking left); the shield, bow or hammer
    is held on that side. `team` ("left" / "right") adds the team emblem on the chest.
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
        hovered = self.enabled and self.rect.collidepoint(pygame.mouse.get_pos())   # M4.1
        if not self.enabled:
            fill, text_color = BUTTON_OFF, DIM_TEXT
        elif self.chosen:
            fill, text_color = (BUTTON_CHOSEN_HOVER if hovered else BUTTON_CHOSEN), TEXT_COLOR
        else:
            fill, text_color = (BUTTON_HOVER if hovered else BUTTON_COLOR), LIGHT_TEXT
        pygame.draw.rect(screen, fill, self.rect, border_radius=6)
        pygame.draw.rect(screen, TEXT_COLOR, self.rect, 2, border_radius=6)
        draw_text(screen, self.label, font, text_color, center=self.rect.center)
