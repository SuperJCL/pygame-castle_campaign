"""Cannons, projectiles, teams and the rules of a Castle Siege match.

A Battle works in one of two modes, with the same physics and turn order:
- M1 cannon duel, Battle(): two castles and two cannons, no characters. The
  players take turns (left, right, left, ...) and call fire(). main.py uses this.
- Team combat, Battle(roster=...): each side also has a Team of 1-3 characters.
  On its turn a team picks one living character and one action ("attack",
  "defend" or "special") with perform_action().

Shots fly under gravity and explode when they hit an enemy block, an enemy
character or the ground. Everything enemy within the blast radius is damaged.
A side loses when its castle reaches 60 % destruction or, in team combat, when
all its characters are defeated.

Like castle.py and characters.py, this module uses only the standard library,
so the rules can be tested without opening a window. main.py draws the battle
and reads its events.
"""
import math

from castle import Castle, GROUND_Y
from characters import ShotDamage

FIELD_WIDTH = 1280            # a shot that leaves 0..FIELD_WIDTH sideways is a miss

# Physics (docs/M0_design.md §4.6). Screen y grows downward, so gravity is positive.
GRAVITY = 400.0               # pixels per second, per second
SPEED_PER_POWER = 7           # launch speed in pixels per second for each point of power
DT = 1 / 60                   # seconds per physics step (one step per frame at 60 FPS)
MAX_STEPS = 600               # a shot still flying after 600 steps (10 s) is a miss

BLAST_RADIUS = 50             # blocks and characters whose centre is this close are hit
SHOT_BLOCK_DAMAGE = 50        # M1 cannon duel: every shot deals 50 damage to each block it hits
                              # (30 in M1; raised in M1.1 because castles took too many shots)

MIN_ANGLE, MAX_ANGLE, DEFAULT_ANGLE = 5, 80, 45      # degrees above horizontal
MIN_POWER, MAX_POWER, DEFAULT_POWER = 10, 100, 50

# Each cannon sits on top of its castle's front tower: centred over the tower's
# two columns (x 328..392 on the left, 888..952 on the right), 10 px above its top (y = 400).
CANNON_PIVOT = {"left": (360, 390), "right": (920, 390)}

# Team combat.
MAX_TEAM_SIZE = 3
ACTIONS = ("attack", "defend", "special")
CHARACTER_WIDTH = 28          # each character is a 28 x 44 px rectangle standing on the ground
CHARACTER_HEIGHT = 44
# Centre x of each character slot. Slot 0 is the one nearest the team's own castle,
# so the two sides are mirror images (left x = 1280 - right x).
SLOT_X = {"left": (140, 95, 50), "right": (1140, 1185, 1230)}
EXP_FOR_HIT = 10              # the shot damaged at least one enemy block or character
EXP_FOR_DEFEAT = 20           # extra, for each enemy character the shot defeated
EXP_FOR_SUPPORT_SPECIAL = 5   # Rally or Repair (a basic Defend earns nothing)
# Castle Guard (M3.2): while one of a team's characters is defending (Defend or Rally),
# enemy shots do this much less damage to each of that team's castle blocks, rounded
# down (50 -> 25, 60 -> 30, 75 -> 37). It ends with the Defend, at the team's next turn.
CASTLE_GUARD_PERCENT = 50


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


class Team:
    """One side's characters (1 to 3, all different roles) and its castle.

    A character's position in `characters` is its slot number on the battlefield.
    """

    def __init__(self, side, characters, castle):
        if not 1 <= len(characters) <= MAX_TEAM_SIZE:
            raise ValueError(f"a team needs 1 to {MAX_TEAM_SIZE} characters")
        roles = [type(character) for character in characters]
        if len(set(roles)) != len(roles):
            raise ValueError("a team can't have two characters of the same role")
        if any(character.side != side for character in characters):
            raise ValueError("every character must belong to the team's side")
        self.side = side
        self.characters = tuple(characters)
        self.castle = castle

    def alive_characters(self):
        return [character for character in self.characters if character.is_alive()]

    def has_lost(self, castle_loss_enabled=True):
        """True if every character is defeated, or (if that rule is on) the castle has fallen."""
        if not self.alive_characters():
            return True
        return castle_loss_enabled and self.castle.has_fallen()

    def slot_center(self, index):
        """Centre point of the character standing in slot `index`."""
        return (SLOT_X[self.side][index], GROUND_Y - CHARACTER_HEIGHT // 2)

    def character_rect(self, index):
        """(left, top, width, height) of the character in slot `index`: it stands on the ground."""
        center_x, _ = self.slot_center(index)
        return (center_x - CHARACTER_WIDTH // 2, GROUND_Y - CHARACTER_HEIGHT,
                CHARACTER_WIDTH, CHARACTER_HEIGHT)

    def character_at(self, px, py):
        """The living character whose rectangle contains (px, py), or None.

        Defeated characters are ignored, so they no longer stop shots.
        """
        for index, character in enumerate(self.characters):
            if not character.is_alive():
                continue
            left, top, width, height = self.character_rect(index)
            if left <= px < left + width and top <= py < top + height:
                return character
        return None

    def characters_near(self, px, py, radius):
        """Living characters whose centre is within `radius` of (px, py)."""
        near = []
        for index, character in enumerate(self.characters):
            center_x, center_y = self.slot_center(index)
            if character.is_alive() and math.hypot(center_x - px, center_y - py) <= radius:
                near.append(character)
        return near


class Battle:
    """The state and rules of one match: castles, cannons, teams (in team combat),
    whose turn it is, the shot in flight and the winner.

    Things that happen (an action, a shot fired, an explosion, EXP, a new turn,
    the end of the game, a refused action) are recorded as small dictionaries in
    an event list. main.py collects them once per frame with take_events().
    """

    def __init__(self, roster=None, castle_loss_enabled=True):
        """roster: None for the M1 cannon duel, or {"left": [...], "right": [...]} with
        1-3 character classes per side, e.g. {"left": [Knight, Archer], "right": [Engineer]}.

        castle_loss_enabled: in team combat, whether a fallen castle loses the match.
        Set it to False if only defeating every enemy may win (the course's rule).
        """
        self._roster = roster
        self.castle_loss_enabled = castle_loss_enabled
        self.reset()

    def reset(self):
        """Start a fresh match (also used by the R key). Characters are created anew,
        so their HP, EXP, levels and cooldowns start over."""
        self.castles = {"left": Castle("left"), "right": Castle("right")}
        self.cannons = {"left": Cannon("left"), "right": Cannon("right")}
        self.teams = None
        if self._roster is not None:
            self.teams = {}
            for side in ("left", "right"):
                characters = [role(role.__name__, side) for role in self._roster[side]]
                self.teams[side] = Team(side, characters, self.castles[side])
        self.round_number = 1
        self.active_side = "left"       # the left side always moves first
        self.projectile = None          # the shot in flight, or None
        self._shooter = None            # the character who fired it (None in the M1 duel)
        self._shot_damage = None        # the ShotDamage of the shot in flight
        self.winner = None              # None while playing, then "left", "right" or "draw"
        self._events = []

    def is_over(self):
        return self.winner is not None

    def can_fire(self):
        """True when the active side may act: no shot is flying and the game isn't over."""
        return not self.is_over() and self.projectile is None

    # ----- the two ways to act ----------------------------------------------------

    def fire(self):
        """M1 cannon duel: fire the active cannon. Returns False if that isn't allowed now.

        In team combat, use perform_action() instead (a character must do the firing).
        """
        if self.teams is not None or not self.can_fire():
            return False
        self._launch(None, ShotDamage(SHOT_BLOCK_DAMAGE))
        return True

    def perform_action(self, actor_index, action):
        """Team combat: the active team's character in slot `actor_index` does `action`.

        action is "attack", "defend" or "special". Attack (and Archer's Power Shot)
        fire the active cannon with its current aim; the turn ends when the shot has
        landed. Defend, Rally and Repair end the turn at once.
        Returns True if the action was carried out. If it isn't allowed, returns
        False, records an "invalid" event with the reason, and changes nothing else.
        """
        reason = self.why_not_allowed(actor_index, action)
        if reason is not None:
            self._events.append({"type": "invalid", "reason": reason})
            return False

        team = self.teams[self.active_side]
        actor = team.characters[actor_index]
        self._events.append({"type": "action", "side": self.active_side,
                             "name": actor.name, "action": action})
        if action == "attack":
            self._launch(actor, actor.attack_shot())
        elif action == "defend":
            actor.defend()
            self._finish_turn(actor, 0)
        else:
            # Each role's use_special() does something different (polymorphism):
            # Rally makes the team defend, Repair fixes the castle, Power Shot
            # returns a stronger shot for the cannon to fire.
            actor.start_cooldown()
            message, shot = actor.use_special(team)
            self._events.append({"type": "special", "side": self.active_side,
                                 "name": actor.name, "message": message})
            if shot is not None:
                self._launch(actor, shot)
            else:
                self._finish_turn(actor, EXP_FOR_SUPPORT_SPECIAL)
        return True

    def castle_guarded(self, side):
        """True while one of `side`'s living characters is defending (Defend or Rally).

        Enemy shots then do CASTLE_GUARD_PERCENT less damage to that side's castle
        blocks. Always False in the M1 cannon duel, which has no characters.
        """
        if self.teams is None:
            return False
        return any(character.is_defending for character in self.teams[side].alive_characters())

    def why_not_allowed(self, actor_index, action):
        """None if the action may be performed now, otherwise the reason it can't.

        Only asks: nothing changes. The interface uses it to grey out buttons.
        """
        if self.teams is None:
            return "this battle has no characters (it is the M1 cannon duel)"
        if not self.can_fire():
            return "wait: a shot is in the air or the game is over"
        team = self.teams[self.active_side]
        if not 0 <= actor_index < len(team.characters):
            return "there is no character in that slot"
        actor = team.characters[actor_index]
        if not actor.is_alive():
            return f"{actor.name} has been defeated and can't act"
        if action not in ACTIONS:
            return f"unknown action {action!r}"
        if action == "special":
            return actor.special_blocked_reason(team)   # None if the special is available
        return None

    # ----- flight and explosions ------------------------------------------------

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
        """Set and return the winner if a side has lost.

        Both sides are checked together: if both have lost, the result is a draw
        (docs/M0_design.md §2.4, rule 1). In the M1 duel only the castles count.
        """
        if self.teams is None:
            left_lost = self.castles["left"].has_fallen()
            right_lost = self.castles["right"].has_fallen()
        else:
            left_lost = self.teams["left"].has_lost(self.castle_loss_enabled)
            right_lost = self.teams["right"].has_lost(self.castle_loss_enabled)
        if left_lost and right_lost:
            self.winner = "draw"
        elif left_lost:
            self.winner = "right"
        elif right_lost:
            self.winner = "left"
        return self.winner

    def _launch(self, shooter, shot_damage):
        """Fire the active cannon. `shooter` is the character firing (None in the M1 duel)."""
        self.projectile = self.cannons[self.active_side].fire()
        self._shooter = shooter
        self._shot_damage = shot_damage
        self._events.append({"type": "fire", "side": self.active_side})

    def _find_impact(self, shot):
        """What the shot touches at its current position:
        ("offscreen" | "block" | "character" | "ground", x, y), or None.

        Only the ENEMY castle and characters are checked, so a shot flies straight
        through its own side (no friendly fire).
        """
        if shot.x < 0 or shot.x > FIELD_WIDTH:
            return ("offscreen", shot.x, shot.y)
        enemy = other_side(shot.side)
        if self.castles[enemy].block_at(shot.x, shot.y) is not None:
            return ("block", shot.x, shot.y)
        if self.teams is not None and self.teams[enemy].character_at(shot.x, shot.y) is not None:
            return ("character", shot.x, shot.y)
        if shot.y >= GROUND_Y:
            # The shot may have sunk a few pixels into the ground during the last
            # step; the explosion happens on the surface.
            return ("ground", shot.x, GROUND_Y)
        return None

    def _end_shot(self, impact):
        """Apply a finished shot's explosion (or miss), award EXP, then end the turn."""
        kind, x, y = impact
        shooter, shot_damage = self._shooter, self._shot_damage
        enemy = other_side(self.projectile.side)
        self.projectile = None
        self._shooter = None
        self._shot_damage = None

        if kind in ("offscreen", "timeout"):
            self._events.append({"type": "miss", "side": other_side(enemy),
                                 "reason": kind, "x": x, "y": y})
            self._finish_turn(shooter, 0)
            return

        # Castle Guard is checked before anything is hit, so it also covers the shot
        # that defeats the defending character.
        guarded = self.castle_guarded(enemy)
        block_damage = shot_damage.block_damage
        if guarded:
            block_damage = block_damage * (100 - CASTLE_GUARD_PERCENT) // 100
        blocks_hit, damage = self.castles[enemy].apply_blast(x, y, BLAST_RADIUS, block_damage)
        characters_hit = []
        if shooter is not None:
            # Make the list of targets first, so each one is hit once even if it is defeated.
            for target in self.teams[enemy].characters_near(x, y, BLAST_RADIUS):
                lost = target.take_hit(shooter, shot_damage.multiplier, shot_damage.ignores_def)
                characters_hit.append({"name": target.name, "damage": lost,
                                       "defeated": not target.is_alive()})
        self._events.append({"type": "explosion", "side": other_side(enemy), "kind": kind,
                             "x": x, "y": y, "blocks_hit": blocks_hit, "damage": damage,
                             "guarded": guarded, "characters_hit": characters_hit})

        exp = 0
        if blocks_hit > 0 or characters_hit:
            exp += EXP_FOR_HIT
        exp += EXP_FOR_DEFEAT * sum(1 for hit in characters_hit if hit["defeated"])
        self._finish_turn(shooter, exp)

    # ----- turns and rounds ------------------------------------------------------

    def _finish_turn(self, actor, exp):
        """After an action has fully resolved: give EXP, then end the game or pass the turn."""
        if actor is not None and exp > 0 and actor.is_alive():
            levels = actor.gain_exp(exp)
            self._events.append({"type": "exp", "side": actor.side, "name": actor.name,
                                 "amount": exp, "levels": levels})

        if self.check_winner() is not None:
            self._events.append({"type": "game_over", "winner": self.winner})
            return

        self.active_side = other_side(self.active_side)
        if self.active_side == "left":
            self._start_round()             # left moves first, so its turn starts a new round
        self._start_turn(self.active_side)
        self._events.append({"type": "turn", "side": self.active_side})

    def _start_round(self):
        """A new round: count it and tick every character's cooldown once."""
        self.round_number += 1
        if self.teams is not None:
            for team in self.teams.values():
                for character in team.characters:
                    character.tick_cooldown()
        self._events.append({"type": "round", "number": self.round_number})

    def _start_turn(self, side):
        """The start of a team's turn: its Defend (and Rally) from last turn ends now.

        So a Defend protects against exactly one enemy action: the turn in between.
        """
        if self.teams is not None:
            for character in self.teams[side].characters:
                character.clear_defend()
