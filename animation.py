"""The run to the cannon (M3.4-C): an attacking character runs to its team's cannon, fires
it and runs back. This is a visual effect only.

Each team has one shared cannon. When a character attacks (ATTACK, or a special that fires:
Power Shot, Triple Volley, Airburst), main.py does not fire straight away. A CannonRun goes through four states:

    IDLE -> RUN_TO_CANNON -> FIRE -> RETURN_TO_SLOT -> IDLE

step() advances the run one frame and returns True on exactly one frame: the one on which
the character reaches the cannon. main.py fires the real shot then, with Battle.perform_action(),
so the shot is fired once, at the moment it is drawn leaving the cannon.

A CannonRun never touches the Battle. The Battle keeps every character in its slot, so hit
boxes, collisions, damage and turns never depend on where the runner is drawn. The Battle
also still decides when the turn ends: when the shot lands. While a run is going, main.py
ignores combat input and the computer waits.

Like the rule modules, this file uses only the Python standard library (no Pygame), so it
can be tested without opening a window.
"""
from battle import CANNON_PIVOT, direction

IDLE = "idle"
RUN_TO_CANNON = "run to cannon"
FIRE = "fire"
RETURN_TO_SLOT = "return to slot"

# Frame counts at 60 FPS, the same frames the Battle moves a shot in.
RUN_FRAMES = 20         # 1/3 s from the slot to the cannon
FIRE_FRAMES = 12        # 1/5 s of firing pose and muzzle flash
RETURN_FRAMES = 20      # 1/3 s back to the slot
# The firing spot is this far behind the cannon's pivot: in the gap between the cover (it
# ends at x 300 on the left) and the cannon's wheel (it starts at x 332).
FIRING_OFFSET = 24


def firing_x(side):
    """Centre x of the spot where `side`'s characters stand to fire their cannon."""
    return CANNON_PIVOT[side][0] - direction(side) * FIRING_OFFSET


def fires_the_cannon(character, action):
    """True if `action` by `character` fires the team's cannon: every Attack, and a special that
    fires shells (M6.3: the role's SPECIAL_SHELLS, so Power Shot, Triple Volley and Airburst).
    Defend, Rally, Repair and Field Dressing fire nothing, so they happen at once."""
    return action == "attack" or (action == "special" and character.SPECIAL_SHELLS > 0)


class PendingShot:
    """An attack waiting for its character to reach the cannon. It is kept exactly as it was
    asked for: the side and slot of the character, "attack" or "special", the aim at that
    moment, and the computer's Plan if the computer chose it (None for a person)."""

    def __init__(self, side, actor_index, action, angle, power, plan=None):
        self.side = side
        self.actor_index = actor_index
        self.action = action
        self.angle = angle
        self.power = power
        self.plan = plan


class CannonRun:
    """Where the attacking character is drawn while it runs to the cannon and back.

    It only counts frames: the state, the frames spent in it, and the pending shot.
    """

    def __init__(self):
        self.cancel()

    def cancel(self):
        """Stop at once and forget the shot (a rematch, new teams, the game closing).
        Nothing is fired: a shot that was already fired belongs to the Battle."""
        self.state = IDLE
        self.shot = None
        self.frame = 0           # frames spent in the current state
        self.slot_x = None       # where the runner starts and ends (its slot's centre x)
        self.cannon_x = None     # where it fires (firing_x)

    def is_busy(self):
        return self.state != IDLE

    def start(self, shot, slot_x):
        """Send the character of `shot` (a PendingShot) from its slot, centre x `slot_x`,
        toward its cannon. main.py checks is_busy() first, so only one run goes at a time."""
        if self.is_busy():
            raise RuntimeError("a character is already running to the cannon")
        self.state = RUN_TO_CANNON
        self.shot = shot
        self.frame = 0
        self.slot_x = slot_x
        self.cannon_x = firing_x(shot.side)

    def step(self):
        """Advance one frame. Returns True only on the frame the character reaches the
        cannon: main.py fires the shot on that frame, while the FIRE pose starts."""
        if self.state == IDLE:
            return False
        self.frame += 1
        if self.state == RUN_TO_CANNON and self.frame == RUN_FRAMES:
            self.state, self.frame = FIRE, 0
            return True
        if self.state == FIRE and self.frame == FIRE_FRAMES:
            self.state, self.frame = RETURN_TO_SLOT, 0
        elif self.state == RETURN_TO_SLOT and self.frame == RETURN_FRAMES:
            self.cancel()        # back in its slot
        return False

    def moves(self, side, index):
        """True if the character in slot `index` of `side` is the runner, so it is drawn at
        actor_x() instead of in its slot."""
        return self.is_busy() and (self.shot.side, self.shot.actor_index) == (side, index)

    def actor_x(self):
        """Centre x at which to draw the runner now: a straight line between its slot and
        the firing spot, covered at an even speed."""
        if self.state == RUN_TO_CANNON:
            return self.slot_x + (self.cannon_x - self.slot_x) * self.frame / RUN_FRAMES
        if self.state == FIRE:
            return self.cannon_x
        if self.state == RETURN_TO_SLOT:
            return self.cannon_x + (self.slot_x - self.cannon_x) * self.frame / RETURN_FRAMES
        return self.slot_x

    def facing(self):
        """+1 to look right, -1 to look left: toward the cannon while running there and
        firing (which is also toward the enemy), toward its slot on the way back."""
        toward_cannon = direction(self.shot.side)
        return -toward_cannon if self.state == RETURN_TO_SLOT else toward_cannon
