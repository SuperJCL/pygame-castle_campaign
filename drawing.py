"""Shared look of the Castle Siege screens: colours, text, character figures and buttons.

Moved out of main.py unchanged in M3.4-B, so main.py can stay focused on the screens and
their input. Uses Pygame, so (like main.py) it is not imported by the game-rule modules.
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
