"""Cannons, projectiles, teams and the rules of a Castle Siege match.

Each side has a Team of 1-3 characters, the cover blocks it placed (its Castle) and
one shared cannon standing in front of the cover. On its turn a team picks one
living character and one action ("attack", "defend" or "special") with
perform_action(). Attack (and Archer's Power Shot) fire the team's cannon with the
acting character's stats.

Shots fly under gravity and explode on the first enemy block or enemy character
they touch, or on the ground. The explosion damages the enemy blocks and characters
within the blast radius, except that a standing block between the explosion and a
character shields that character (cover). The only way to win is to defeat every
enemy character. The LEFT side moves first unless the Battle is told otherwise
(first_side). A match that reaches the end of ROUND_LIMIT complete rounds without
an elimination is a draw.

Like castle.py and characters.py, this module uses only the standard library,
so the rules can be tested without opening a window. main.py draws the battle
and reads its events.
"""
import math

from castle import Castle, DEFAULT_LAYOUT, GROUND_Y

FIELD_WIDTH = 1280            # a shot that leaves 0..FIELD_WIDTH sideways is a miss

# Physics (docs/M0_design.md §4.6). Screen y grows downward, so gravity is positive.
GRAVITY = 400.0               # pixels per second, per second
SPEED_PER_POWER = 7           # launch speed in pixels per second for each point of power
DT = 1 / 60                   # seconds per physics step (one step per frame at 60 FPS)
MAX_STEPS = 600               # a shot still flying after 600 steps (10 s) is a miss

BLAST_RADIUS = 50             # blocks and characters whose centre is this close are hit

MIN_ANGLE, MAX_ANGLE, DEFAULT_ANGLE = 5, 80, 45      # degrees above horizontal
MIN_POWER, MAX_POWER, DEFAULT_POWER = 10, 100, 50

# Each team's cannon stands on the ground in front of its cover (the cover slots end at
# x 300 on the left and start at x 980 on the right), facing the enemy.
CANNON_PIVOT = {"left": (340, 544), "right": (940, 544)}

# Team combat.
MAX_TEAM_SIZE = 3
ACTIONS = ("attack", "defend", "special")
CHARACTER_WIDTH = 28          # each character is a 28 x 44 px rectangle standing on the ground
CHARACTER_HEIGHT = 44
# Centre x of each character slot. Slot 0 is the front one, nearest the team's cover,
# so the two sides are mirror images (left x = 1280 - right x).
SLOT_X = {"left": (140, 95, 50), "right": (1140, 1185, 1230)}
EXP_FOR_HIT = 10              # the shot damaged at least one enemy block or character
EXP_FOR_DEFEAT = 20           # extra, for each enemy character the shot defeated
EXP_FOR_SUPPORT_SPECIAL = 5   # Rally or Repair (a basic Defend earns nothing)
# Cover Guard (M3.2, called Castle Guard until M3.4): while one of a team's characters is
# defending (Defend or Rally), enemy shots do this much less damage to each of that team's
# blocks, rounded down (50 -> 25, 60 -> 30, 75 -> 37). It ends with the Defend, at the
# team's next turn.
CASTLE_GUARD_PERCENT = 50
# Round limit (our safety rule, not a course requirement): a match that reaches the end of
# this many COMPLETE rounds (both teams have acted) without an elimination is a draw.
ROUND_LIMIT = 30


def clamp(value, low, high):
    """Keep value inside the range low..high."""
    return max(low, min(high, value))


def other_side(side):
    return "right" if side == "left" else "left"


def direction(side):
    """+1 if this side shoots toward larger x (the left side), -1 otherwise."""
    return 1 if side == "left" else -1


def segment_entry(x0, y0, x1, y1, rect):
    """How far along the straight move from (x0, y0) to (x1, y1) it first touches `rect`
    (left, top, width, height): a fraction from 0 (the start) to 1 (the end), or None if
    the move never touches the rectangle.

    For x, work out the part of the move during which x is inside the rectangle's
    left..right range; do the same for y. The move touches the rectangle exactly when
    those two parts overlap, and it enters where the later of the two parts begins.
    Because the whole move is checked, not only where it ends, a fast shot can't jump
    over a thin target between two steps.
    """
    left, top, width, height = rect
    enter, leave = 0.0, 1.0
    for start, change, low, high in ((x0, x1 - x0, left, left + width),
                                     (y0, y1 - y0, top, top + height)):
        if change == 0:                     # not moving along this axis
            if start < low or start > high:
                return None
            continue
        fraction_a = (low - start) / change
        fraction_b = (high - start) / change
        enter = max(enter, min(fraction_a, fraction_b))
        leave = min(leave, max(fraction_a, fraction_b))
    return enter if enter <= leave else None


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
    """A team's fixed cannon. Its angle and power always stay inside the legal limits."""

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
    """One side's characters (1 to 3, all different roles) and its cover (castle).

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

    def has_lost(self):
        """True once every character is defeated (the only way to lose)."""
        return not self.alive_characters()

    def slot_center(self, index):
        """Centre point of the character standing in slot `index`."""
        return (SLOT_X[self.side][index], GROUND_Y - CHARACTER_HEIGHT // 2)

    def character_rect(self, index):
        """(left, top, width, height) of the character in slot `index`: it stands on the ground."""
        center_x, _ = self.slot_center(index)
        return (center_x - CHARACTER_WIDTH // 2, GROUND_Y - CHARACTER_HEIGHT,
                CHARACTER_WIDTH, CHARACTER_HEIGHT)

    def characters_near(self, px, py, radius):
        """Slots of the living characters whose centre is within `radius` of (px, py)."""
        near = []
        for index, character in enumerate(self.characters):
            center_x, center_y = self.slot_center(index)
            if character.is_alive() and math.hypot(center_x - px, center_y - py) <= radius:
                near.append(index)
        return near

    def is_covered(self, index, px, py):
        """True if one of this team's standing blocks is on the straight line from an
        explosion at (px, py) to the centre of the character in slot `index`."""
        center_x, center_y = self.slot_center(index)
        return any(segment_entry(px, py, center_x, center_y, block.rect()) is not None
                   for block in self.castle.alive_blocks())


class Battle:
    """The state and rules of one match: teams, their cover and cannons, whose turn
    it is, the shot in flight and the result.

    Things that happen (an action, a shot fired, an explosion, EXP, a new turn,
    the end of the game, a refused action) are recorded as small dictionaries in
    an event list. main.py collects them once per frame with take_events().
    """

    def __init__(self, roster, layouts=None, first_side="left"):
        """roster: {"left": [...], "right": [...]} with 1-3 character classes per side,
        e.g. {"left": [Knight, Archer], "right": [Engineer]}.

        layouts: {"left": slots, "right": slots}, the cover slots (0-7) each team placed
        blocks on (see castle.layout_problem). None gives both teams DEFAULT_LAYOUT.

        first_side: "left" or "right", the side that moves first in every round.
        """
        if layouts is None:
            layouts = {"left": DEFAULT_LAYOUT, "right": DEFAULT_LAYOUT}
        self._roster = roster
        self.layouts = {side: tuple(sorted(layouts[side])) for side in ("left", "right")}
        self.first_side = first_side
        self.reset()

    def reset(self, first_side=None):
        """Start a fresh match (also used for a rematch). Characters and cover are created
        anew from the same roster and layouts, so HP, EXP, levels, cooldowns and every
        block's HP start over.

        first_side: who moves first in the new match; None keeps the current first side.
        """
        if first_side is not None:
            self.first_side = first_side
        if self.first_side not in ("left", "right"):
            raise ValueError(f"first_side must be 'left' or 'right', not {self.first_side!r}")
        self.castles = {side: Castle(side, self.layouts[side]) for side in ("left", "right")}
        self.cannons = {"left": Cannon("left"), "right": Cannon("right")}
        self.teams = {}
        for side in ("left", "right"):
            characters = [role(role.__name__, side) for role in self._roster[side]]
            self.teams[side] = Team(side, characters, self.castles[side])
        self.round_number = 1
        self.active_side = self.first_side
        self.projectile = None          # the shot in flight, or None
        self._shooter = None            # the character who fired it
        self._shot_damage = None        # the ShotDamage of the shot in flight
        self.winner = None              # None while playing, then "left", "right" or "draw"
        # Why the match ended: "elimination", "both_lost" or "timeout" (the round limit);
        # None while playing.
        self.end_reason = None
        self._events = []

    def is_over(self):
        return self.winner is not None

    def can_fire(self):
        """True when the active side may act: no shot is flying and the game isn't over."""
        return not self.is_over() and self.projectile is None

    # ----- acting --------------------------------------------------------------------

    def perform_action(self, actor_index, action):
        """The active team's character in slot `actor_index` does `action`.

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
            # Rally makes the team defend, Repair fixes the cover, Power Shot
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
        """Cover Guard: True while one of `side`'s living characters is defending (Defend
        or Rally). Enemy shots then do CASTLE_GUARD_PERCENT less damage to its blocks."""
        return any(character.is_defending for character in self.teams[side].alive_characters())

    def why_not_allowed(self, actor_index, action):
        """None if the action may be performed now, otherwise the reason it can't.

        Only asks: nothing changes. The interface uses it to grey out buttons.
        """
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
        start = (self.projectile.x, self.projectile.y)
        self.projectile.step()
        impact = self._find_impact(self.projectile, *start)
        if impact is None and self.projectile.steps >= MAX_STEPS:
            impact = ("timeout", self.projectile.x, self.projectile.y, None)
        if impact is not None:
            self._end_shot(impact)

    def take_events(self):
        """Return everything that happened since the last call, and empty the list."""
        events = self._events
        self._events = []
        return events

    def check_winner(self):
        """Set and return the winner if a team has been eliminated.

        Both teams are checked together: if both have lost, the result is a draw
        (docs/M0_design.md §2.4, rule 1).
        """
        left_lost = self.teams["left"].has_lost()
        right_lost = self.teams["right"].has_lost()
        if left_lost and right_lost:
            self.winner, self.end_reason = "draw", "both_lost"
        elif left_lost or right_lost:
            self.winner, self.end_reason = ("right" if left_lost else "left"), "elimination"
        return self.winner

    def _launch(self, shooter, shot_damage):
        """Fire the active cannon for `shooter`, the character whose stats the shot uses."""
        self.projectile = self.cannons[self.active_side].fire()
        self._shooter = shooter
        self._shot_damage = shot_damage
        self._events.append({"type": "fire", "side": self.active_side})

    def _find_impact(self, shot, x0, y0):
        """What the shot touched first while moving from (x0, y0) to where it is now:
        (kind, x, y, slot), with kind "block", "character", "ground" or "offscreen" and
        slot the character's slot for a character hit, or None if it touched nothing.

        Only the ENEMY blocks and characters are checked, so a shot flies straight
        through its own side (no friendly fire). (x, y) is the exact point where the
        shot first touched the thing it hit; ties go to the earlier kind in that list.
        """
        touches = self._touches(other_side(shot.side), x0, y0, shot.x, shot.y)
        if not touches:
            return None
        fraction, _, kind, number = touches[0]
        x, y = self._touch_point(x0, y0, shot.x, shot.y, fraction, kind)
        return (kind, x, y, number if kind == "character" else None)

    def _touches(self, enemy_side, x0, y0, x1, y1):
        """Everything of `enemy_side` that the straight move from (x0, y0) to (x1, y1)
        touches, nearest first: (fraction of the move, order, kind, number), where number
        is the block's index in castle.blocks or the character's slot. The ground and the
        edge of the field are included too; order breaks ties (blocks first)."""
        enemy = self.teams[enemy_side]
        touches = []
        for index, block in enumerate(enemy.castle.blocks):
            if not block.is_destroyed():
                fraction = segment_entry(x0, y0, x1, y1, block.rect())
                if fraction is not None:
                    touches.append((fraction, 0, "block", index))
        for index, character in enumerate(enemy.characters):
            if character.is_alive():
                fraction = segment_entry(x0, y0, x1, y1, enemy.character_rect(index))
                if fraction is not None:
                    touches.append((fraction, 1, "character", index))
        if y1 >= GROUND_Y:
            touches.append(((GROUND_Y - y0) / (y1 - y0), 2, "ground", None))
        if x1 < 0 or x1 > FIELD_WIDTH:
            edge = 0 if x1 < 0 else FIELD_WIDTH
            touches.append(((edge - x0) / (x1 - x0), 3, "offscreen", None))
        touches.sort(key=lambda touch: touch[:2])
        return touches

    @staticmethod
    def _touch_point(x0, y0, x1, y1, fraction, kind):
        """The point `fraction` of the way along the move (on the ground surface for "ground")."""
        x = x0 + fraction * (x1 - x0)
        y = GROUND_Y if kind == "ground" else y0 + fraction * (y1 - y0)
        return x, y

    def path_contacts(self, side, angle, power):
        """A planning aid for the computer player (ai.py); it changes nothing.

        Flies a shot from `side`'s cannon with this aim as if it could pass through
        everything, and returns what its path touches, in order: (kind, number, x, y) for
        each enemy block ("block", its index in castle.blocks) and living enemy character
        ("character", its slot), ending with ("ground" or "offscreen", None, x, y) where
        the path ends. The first entry is exactly what a real shot with this aim would hit
        now; the later ones are what it would hit if the things before them were gone.
        """
        cannon = self.cannons[side]
        shot = Projectile(cannon.x, cannon.y, clamp(angle, MIN_ANGLE, MAX_ANGLE),
                          clamp(power, MIN_POWER, MAX_POWER), side)
        contacts, listed = [], set()
        for _ in range(MAX_STEPS):
            x0, y0 = shot.x, shot.y
            shot.step()
            for fraction, _, kind, number in self._touches(other_side(side), x0, y0, shot.x, shot.y):
                x, y = self._touch_point(x0, y0, shot.x, shot.y, fraction, kind)
                if kind in ("ground", "offscreen"):
                    contacts.append((kind, None, x, y))
                    return contacts
                if (kind, number) not in listed:
                    listed.add((kind, number))
                    contacts.append((kind, number, x, y))
        contacts.append(("timeout", None, shot.x, shot.y))
        return contacts

    def _end_shot(self, impact):
        """Apply a finished shot's explosion (or miss), award EXP, then end the turn.

        Everything the explosion depends on is read once, at the moment of impact and
        before anything is damaged: Cover Guard, which characters the blast reaches,
        and which of them a standing block shields. So a block that this explosion
        destroys still shields the characters behind it from this explosion.
        """
        kind, x, y, target_slot = impact
        shooter, shot_damage = self._shooter, self._shot_damage
        enemy = other_side(self.projectile.side)
        team = self.teams[enemy]
        self.projectile = None
        self._shooter = None
        self._shot_damage = None

        if kind in ("offscreen", "timeout"):
            self._events.append({"type": "miss", "side": other_side(enemy),
                                 "reason": kind, "x": x, "y": y})
            self._finish_turn(shooter, 0)
            return

        guarded = self.castle_guarded(enemy)
        in_blast = team.characters_near(x, y, BLAST_RADIUS)
        if target_slot is not None and target_slot not in in_blast:
            in_blast.append(target_slot)            # a direct hit always counts
        # A directly hit character is never shielded: the shot reached it.
        covered = [i for i in in_blast if i != target_slot and team.is_covered(i, x, y)]

        block_damage = shot_damage.block_damage
        if guarded:
            block_damage = block_damage * (100 - CASTLE_GUARD_PERCENT) // 100
        blocks_hit, damage = team.castle.apply_blast(x, y, BLAST_RADIUS, block_damage)
        characters_hit = []
        for index in sorted(in_blast):
            if index in covered:
                continue
            target = team.characters[index]
            lost = target.take_hit(shooter, shot_damage.multiplier, shot_damage.ignores_def)
            characters_hit.append({"name": target.name, "damage": lost,
                                   "defeated": not target.is_alive()})
        self._events.append({
            "type": "explosion", "side": other_side(enemy), "kind": kind, "x": x, "y": y,
            "target": None if target_slot is None else team.characters[target_slot].name,
            "blocks_hit": blocks_hit, "damage": damage, "guarded": guarded,
            "characters_hit": characters_hit,
            "covered": [team.characters[i].name for i in sorted(covered)]})

        exp = 0
        if blocks_hit > 0 or characters_hit:
            exp += EXP_FOR_HIT
        exp += EXP_FOR_DEFEAT * sum(1 for hit in characters_hit if hit["defeated"])
        self._finish_turn(shooter, exp)

    # ----- turns and rounds ------------------------------------------------------

    def _finish_turn(self, actor, exp):
        """After an action has fully resolved: give EXP, then end the game or pass the turn."""
        if exp > 0 and actor.is_alive():
            levels = actor.gain_exp(exp)
            self._events.append({"type": "exp", "side": actor.side, "name": actor.name,
                                 "amount": exp, "levels": levels})

        # An elimination always comes first, even on the last turn of the last round.
        if self.check_winner() is not None:
            self._events.append({"type": "game_over", "winner": self.winner, "reason": self.end_reason})
            return

        # The round is complete when the turn would go back to the side that moves first.
        round_complete = other_side(self.active_side) == self.first_side
        if round_complete and self.round_number >= ROUND_LIMIT:
            self.winner, self.end_reason = "draw", "timeout"
            self._events.append({"type": "game_over", "winner": self.winner, "reason": self.end_reason})
            return

        self.active_side = other_side(self.active_side)
        if round_complete:
            self._start_round()
        self._start_turn(self.active_side)
        self._events.append({"type": "turn", "side": self.active_side})

    def _start_round(self):
        """A new round (the first side is to move again): count it and tick every
        character's cooldown once. So cooldowns count rounds, never single turns."""
        self.round_number += 1
        for team in self.teams.values():
            for character in team.characters:
                character.tick_cooldown()
        self._events.append({"type": "round", "number": self.round_number})

    def _start_turn(self, side):
        """The start of a team's turn: its Defend (and Rally) from last turn ends now.

        So a Defend protects against exactly one enemy action: the turn in between.
        """
        for character in self.teams[side].characters:
            character.clear_defend()
