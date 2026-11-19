"""Cannons, projectiles and the rules of an M1 Castle Siege match.

M1 rules: two castles, one cannon each. The players take turns (left, right,
left, ...). Each turn one shot is fired; it flies under gravity and explodes when
it hits an enemy block or the ground. Every enemy block near the explosion loses
HP. A castle that reaches 60 % destruction has fallen and the other side wins.

Like castle.py, this module uses only the standard library, so the rules can be
tested without opening a window. main.py draws the battle and reads its events.
"""
import math

from castle import Castle, GROUND_Y

FIELD_WIDTH = 1280            # a shot that leaves 0..FIELD_WIDTH sideways is a miss

# Physics (docs/M0_design.md §4.6). Screen y grows downward, so gravity is positive.
GRAVITY = 400.0               # pixels per second, per second
SPEED_PER_POWER = 7           # launch speed in pixels per second for each point of power
DT = 1 / 60                   # seconds per physics step (one step per frame at 60 FPS)
MAX_STEPS = 600               # a shot still flying after 600 steps (10 s) is a miss

BLAST_RADIUS = 50             # blocks whose centre is this close to an explosion are hit
SHOT_BLOCK_DAMAGE = 30        # M1 only: every shot deals 30 damage to each block it hits

MIN_ANGLE, MAX_ANGLE, DEFAULT_ANGLE = 5, 80, 45      # degrees above horizontal
MIN_POWER, MAX_POWER, DEFAULT_POWER = 10, 100, 50

# Each cannon sits on top of its castle's front tower: centred over the tower's
# two columns (x 328..392 on the left, 888..952 on the right), 10 px above its top (y = 400).
CANNON_PIVOT = {"left": (360, 390), "right": (920, 390)}


def clamp(value, low, high):
    """Keep value inside the range low..high."""
    return max(low, min(high, value))


def other_side(side):
    return "right" if side == "left" else "left"


def direction(side):
    """+1 if this side shoots toward larger x (the left castle), -1 otherwise."""
    return 1 if side == "left" else -1


class Projectile:
    """A cannonball flying under gravity."""

    def __init__(self, x, y, angle, power, side):
        speed = power * SPEED_PER_POWER
        radians = math.radians(angle)
        self.x = x
        self.y = y
        self.vx = direction(side) * speed * math.cos(radians)
        self.vy = -speed * math.sin(radians)     # negative = upward on screen
        self.side = side                         # the side that fired it
        self.steps = 0

    def step(self):
        """Move forward by one time step DT.

        Gravity first changes the vertical speed, then the position moves with
        the new speed (the "semi-implicit Euler" method). The horizontal speed
        never changes, because there is no wind or air resistance.
        """
        self.vy += GRAVITY * DT
        self.x += self.vx * DT
        self.y += self.vy * DT
        self.steps += 1


class Cannon:
    """A fixed cannon whose angle and power always stay inside the legal limits."""

    def __init__(self, side):
        self.side = side
        self.x, self.y = CANNON_PIVOT[side]
        self._angle = DEFAULT_ANGLE
        self._power = DEFAULT_POWER

    @property
    def angle(self):
        return self._angle

    @property
    def power(self):
        return self._power

    def adjust_angle(self, change):
        self._angle = clamp(self._angle + change, MIN_ANGLE, MAX_ANGLE)

    def adjust_power(self, change):
        self._power = clamp(self._power + change, MIN_POWER, MAX_POWER)

    def fire(self):
        """Return a new projectile launched from the pivot with the current aim."""
        return Projectile(self.x, self.y, self._angle, self._power, self.side)


class Battle:
    """The state and rules of one match: castles, cannons, whose turn it is, the
    shot in flight and the winner.

    Things that happen (a shot fired, an explosion, a miss, a new turn, the end of
    the game) are recorded as small dictionaries in an event list. main.py collects
    them once per frame with take_events() to draw explosions and messages.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        """Start a fresh match (also used by the R key)."""
        self.castles = {"left": Castle("left"), "right": Castle("right")}
        self.cannons = {"left": Cannon("left"), "right": Cannon("right")}
        self.active_side = "left"       # the left cannon always shoots first
        self.projectile = None          # the shot in flight, or None
        self.winner = None              # None while playing, then "left", "right" or "draw"
        self._events = []

    def is_over(self):
        return self.winner is not None

    def can_fire(self):
        return not self.is_over() and self.projectile is None

    def fire(self):
        """Fire the active cannon. Returns False if a shot is already flying or the game is over."""
        if not self.can_fire():
            return False
        self.projectile = self.cannons[self.active_side].fire()
        self._events.append({"type": "fire", "side": self.active_side})
        return True

    def update(self):
        """Advance the shot in flight by one physics step. main.py calls this once per frame."""
        if self.projectile is None:
            return
        self.projectile.step()
        impact = self._find_impact(self.projectile)
        if impact is None and self.projectile.steps >= MAX_STEPS:
            impact = ("timeout", self.projectile.x, self.projectile.y)
        if impact is not None:
            self._end_shot(impact)

    def take_events(self):
        """Return everything that happened since the last call, and empty the list."""
        events = self._events
        self._events = []
        return events

    def check_winner(self):
        """Set and return the winner if a castle has fallen.

        Both castles are checked together. M1 shots only damage one castle at a
        time, but if both have fallen the result is a draw (docs/M0_design.md §2.4, rule 1).
        """
        left_fallen = self.castles["left"].has_fallen()
        right_fallen = self.castles["right"].has_fallen()
        if left_fallen and right_fallen:
            self.winner = "draw"
        elif left_fallen:
            self.winner = "right"
        elif right_fallen:
            self.winner = "left"
        return self.winner

    def _find_impact(self, shot):
        """What the shot touches at its current position: ("offscreen" | "block" | "ground", x, y), or None.

        Only the ENEMY castle is checked, so a shot flies straight through its own
        castle (no friendly fire).
        """
        if shot.x < 0 or shot.x > FIELD_WIDTH:
            return ("offscreen", shot.x, shot.y)
        enemy_castle = self.castles[other_side(shot.side)]
        if enemy_castle.block_at(shot.x, shot.y) is not None:
            return ("block", shot.x, shot.y)
        if shot.y >= GROUND_Y:
            # The shot may have sunk a few pixels into the ground during the last
            # step; the explosion happens on the surface.
            return ("ground", shot.x, GROUND_Y)
        return None

    def _end_shot(self, impact):
        """Apply the result of a finished shot, then end the game or pass the turn."""
        kind, x, y = impact
        shooter = self.projectile.side
        self.projectile = None

        if kind in ("block", "ground"):
            target = self.castles[other_side(shooter)]
            blocks_hit, damage = target.apply_blast(x, y, BLAST_RADIUS, SHOT_BLOCK_DAMAGE)
            self._events.append({"type": "explosion", "side": shooter, "kind": kind,
                                 "x": x, "y": y, "blocks_hit": blocks_hit, "damage": damage})
        else:
            self._events.append({"type": "miss", "side": shooter, "reason": kind, "x": x, "y": y})

        if self.check_winner() is not None:
            self._events.append({"type": "game_over", "winner": self.winner})
        else:
            self.active_side = other_side(self.active_side)
            self._events.append({"type": "turn", "side": self.active_side})
