"""Reflex Aim (M6.1, an experimental prototype): the cannon's angle swings by itself.

In Classic Aim a person sets the angle with the arrow keys. In Reflex Aim the barrel swings
up and down between two limits, and the person times the shot: ATTACK or SPACE locks the
angle shown at that moment. Power is still set with the arrow keys. The computer opponent
never uses this: it keeps its own aim search (ai.py).

An AimSwing only counts frames. The angle on each frame follows a cosine, so the barrel
slows down into each limit, turns round and speeds up again, like a pendulum: there is no
jump and no sudden change of speed at either end. The motion is the same every time (no
randomness), one frame per step at 60 FPS, like the shot's flight in battle.py.

main.py steps the active team's swing once per frame while that team may act, and turns
the real cannon to angle() with the cannon's own methods. While the controls are locked
(a run to the cannon, a shot in the air, the computer's turn, the game over), main.py does
not step it, so the barrel stays at the locked angle until that team's next turn.

Like the rule modules, this file uses only the Python standard library (no Pygame).
"""
import math

from battle import MAX_ANGLE, MIN_ANGLE

SWING_LOW = 20               # degrees above horizontal: the bottom of the swing ...
SWING_HIGH = 75              # ... and the top
SWING_PERIOD_FRAMES = 180    # one full swing, up and back down: 3 s at 60 FPS


class AimSwing:
    """The swinging angle of one team's cannon.

    low, high: the limits in degrees (inside the cannon's own MIN_ANGLE..MAX_ANGLE).
    period: frames for one full swing, low -> high -> low. It must be even, so the swing
    is exactly at `high` on one frame (half way).
    """

    def __init__(self, low=SWING_LOW, high=SWING_HIGH, period=SWING_PERIOD_FRAMES):
        if not MIN_ANGLE <= low < high <= MAX_ANGLE:
            raise ValueError(f"the swing needs {MIN_ANGLE} <= low < high <= {MAX_ANGLE}, not {low}..{high}")
        if not isinstance(period, int) or period < 2 or period % 2:
            raise ValueError(f"the period must be an even whole number of frames, not {period!r}")
        self.low = low
        self.high = high
        self.period = period
        self.reset()

    def reset(self):
        """Back to the start of a swing: at `low`, about to rise (a new match or a rematch)."""
        self.frame = 0

    def step(self):
        """One frame later. After `period` frames the swing starts again."""
        self.frame = (self.frame + 1) % self.period

    def exact_angle(self):
        """The angle on this frame, in degrees, before rounding."""
        progress = (1 - math.cos(2 * math.pi * self.frame / self.period)) / 2    # 0 -> 1 -> 0
        return self.low + (self.high - self.low) * progress

    def angle(self):
        """The angle shown and fired on this frame: whole degrees, like the arrow keys give."""
        return round(self.exact_angle())
