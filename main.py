"""Castle Siege - M1 artillery prototype.

This is the only module that uses Pygame. It reads the keyboard, draws the
battle and runs the main loop. All game rules live in battle.py and castle.py.

Run from the project folder:   python main.py

Controls: UP/DOWN = angle, LEFT/RIGHT = power (hold SHIFT for steps of 5),
SPACE = fire, R = restart, ESC = quit.
"""
import math

import pygame

from battle import BLAST_RADIUS, FIELD_WIDTH, Battle, direction
from castle import GROUND_Y

WINDOW_WIDTH = FIELD_WIDTH        # 1280
WINDOW_HEIGHT = 720
FPS = 60
EXPLOSION_FRAMES = 20             # how long an explosion stays on screen

SKY_COLOR = (160, 205, 235)
GROUND_COLOR = (96, 140, 72)
TEXT_COLOR = (25, 25, 35)
HINT_COLOR = (235, 240, 225)
CANNON_COLOR = (55, 55, 60)
ACTIVE_RING_COLOR = (255, 215, 0)
AIM_COLOR = (230, 110, 20)
SHOT_COLOR = (20, 20, 20)

# Colour of an undamaged block on each side.
STONE_COLORS = {"left": (150, 162, 195), "right": (196, 156, 142)}


def block_color(side, hp, max_hp):
    """A block gets darker as it loses HP, so every hit is visible.

    Full health keeps 100 % of the colour; a block with almost no HP left keeps 40 %.
    """
    shade = 0.4 + 0.6 * hp / max_hp
    return tuple(int(channel * shade) for channel in STONE_COLORS[side])


class Game:
    """Connects the keyboard and the screen to one Battle."""

    def __init__(self, screen):
        self.screen = screen
        self.battle = Battle()
        # Font(None, size) uses Pygame's built-in font. (SysFont scans the system's
        # installed fonts, and on some Windows machines that scan crashes.)
        self.font = pygame.font.Font(None, 30)
        self.small_font = pygame.font.Font(None, 24)
        self.big_font = pygame.font.Font(None, 80)
        self.running = True
        self.space_released = True    # fire only once per SPACE press (see handle_event)
        self.explosions = []          # each one is [x, y, age in frames]
        self.message = ""
        self.restart()

    def restart(self):
        self.battle.reset()
        self.explosions = []
        self.message = "LEFT cannon: aim, then press SPACE to fire."

    # ----- input -------------------------------------------------------------

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self.space_released = True
        elif event.type == pygame.KEYDOWN:
            self.handle_key(event.key, event.mod)

    def handle_key(self, key, mods):
        if key == pygame.K_ESCAPE:
            self.running = False
            return
        if key == pygame.K_r:
            self.restart()
            return
        if not self.battle.can_fire():
            return                    # no aiming while a shot flies or after the game ends

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
        elif key == pygame.K_SPACE and self.space_released:
            # Holding SPACE produces repeated key presses (key repeat is on for the
            # arrow keys). Requiring a release stops a held SPACE from also firing
            # the next player's cannon as soon as their turn starts.
            self.space_released = False
            self.battle.fire()

    # ----- update ------------------------------------------------------------

    def update(self):
        self.battle.update()
        for event in self.battle.take_events():
            self.show_event(event)
        for explosion in self.explosions:
            explosion[2] += 1
        self.explosions = [e for e in self.explosions if e[2] < EXPLOSION_FRAMES]

    def show_event(self, event):
        """Turn a battle event into an on-screen message or effect."""
        if event["type"] == "fire":
            self.message = f"{event['side'].upper()} cannon fired!"
        elif event["type"] == "explosion":
            self.explosions.append([event["x"], event["y"], 0])
            if event["blocks_hit"] > 0:
                self.message = f"Hit! {event['blocks_hit']} blocks, {event['damage']} damage."
            else:
                self.message = "Boom! No blocks were close enough."
        elif event["type"] == "miss":
            self.message = "Miss: the shot left the battlefield."
        elif event["type"] == "turn":
            self.message += f"  {event['side'].upper()} cannon's turn."
        elif event["type"] == "game_over":
            self.message += "  Game over."

    # ----- drawing -----------------------------------------------------------

    def draw(self):
        self.screen.fill(SKY_COLOR)
        pygame.draw.rect(self.screen, GROUND_COLOR,
                         (0, GROUND_Y, WINDOW_WIDTH, WINDOW_HEIGHT - GROUND_Y))
        for side, castle in self.battle.castles.items():
            self.draw_castle(side, castle)
        for side, cannon in self.battle.cannons.items():
            self.draw_cannon(cannon, is_active=(side == self.battle.active_side))
        if self.battle.can_fire():
            self.draw_aim_arrow(self.battle.cannons[self.battle.active_side])
        if self.battle.projectile is not None:
            shot = self.battle.projectile
            pygame.draw.circle(self.screen, SHOT_COLOR, (round(shot.x), round(shot.y)), 5)
        self.draw_explosions()
        self.draw_hud()
        self.draw_instructions()
        if self.battle.is_over():
            self.draw_game_over()

    def draw_castle(self, side, castle):
        for block in castle.alive_blocks():
            color = block_color(side, block.hp, block.max_hp)
            rect = (block.x, block.y, block.size, block.size)
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, TEXT_COLOR, rect, 1)      # outline

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
        # Arrowhead: two short lines angled back from the tip.
        back = math.atan2(-dy, -dx)
        for offset in (-0.5, 0.5):
            wing = (end[0] + 12 * math.cos(back + offset), end[1] + 12 * math.sin(back + offset))
            pygame.draw.line(self.screen, AIM_COLOR, end, wing, 3)

    def draw_explosions(self):
        # A circle that grows to the blast radius while fading from yellow to red.
        for x, y, age in self.explosions:
            progress = age / EXPLOSION_FRAMES
            radius = int(8 + (BLAST_RADIUS - 8) * progress)
            color = (255, int(220 - 150 * progress), int(80 - 60 * progress))
            width = 0 if progress < 0.5 else 4                 # filled, then a ring
            pygame.draw.circle(self.screen, color, (round(x), round(y)), radius, width)

    def draw_text(self, text, font, color, center=None, topleft=None, topright=None):
        image = font.render(text, True, color)
        rect = image.get_rect()
        if center:
            rect.center = center
        elif topleft:
            rect.topleft = topleft
        else:
            rect.topright = topright
        self.screen.blit(image, rect)

    def draw_hud(self):
        for side, position in (("left", {"topleft": (20, 15)}),
                               ("right", {"topright": (WINDOW_WIDTH - 20, 15)})):
            percent = int(self.battle.castles[side].destruction_percent())  # whole percent, rounded down
            self.draw_text(f"{side.upper()} CASTLE  {percent}% destroyed",
                           self.font, TEXT_COLOR, **position)

        if self.battle.is_over():
            status = "Game over"
        elif self.battle.projectile is not None:
            status = "Shot in flight..."
        else:
            cannon = self.battle.cannons[self.battle.active_side]
            status = (f"Turn: {self.battle.active_side.upper()}    "
                      f"Angle {cannon.angle}°    Power {cannon.power}")
        self.draw_text(status, self.font, TEXT_COLOR, center=(WINDOW_WIDTH // 2, 27))
        self.draw_text(self.message, self.small_font, TEXT_COLOR, center=(WINDOW_WIDTH // 2, 58))

    def draw_instructions(self):
        lines = [
            "UP / DOWN: angle     LEFT / RIGHT: power     SHIFT: change by 5     "
            "SPACE: fire     R: restart     ESC: quit",
            "Players take turns. A castle that reaches 60% destruction loses.",
        ]
        for index, line in enumerate(lines):
            self.draw_text(line, self.small_font, HINT_COLOR,
                           center=(WINDOW_WIDTH // 2, 640 + index * 30))

    def draw_game_over(self):
        panel = pygame.Surface((620, 190), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 170))                             # semi-transparent black
        self.screen.blit(panel, panel.get_rect(center=(WINDOW_WIDTH // 2, 250)))
        if self.battle.winner == "draw":
            title = "DRAW!"
        else:
            title = f"{self.battle.winner.upper()} WINS!"
        self.draw_text(title, self.big_font, (255, 255, 255), center=(WINDOW_WIDTH // 2, 225))
        self.draw_text("Press R to play again", self.font, (230, 230, 230),
                       center=(WINDOW_WIDTH // 2, 295))


def open_window():
    """Start Pygame, open the game window and set up the keyboard. Returns the screen."""
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Castle Siege - M1 prototype")
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
