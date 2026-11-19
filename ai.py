"""The computer opponent for Player vs AI (Milestone 3.1).

An AIController plays one team. On its turn it:
1. decides whether to Defend. A character below half HP makes that more likely
   (a course requirement), but it never defends two turns in a row, so it keeps
   making progress;
2. otherwise "imagines" shots: it tries aims on a COPY of the battle
   (copy.deepcopy) and looks at what the explosion does there. The copy runs the
   real rules, so this file repeats none of them, and the real battle is not touched;
3. ranks what it could do by how much closer each option brings it to winning,
   picks one (Easy picks less carefully), and adds an aiming error (Easy misses more);
4. carries the plan out with Battle.perform_action(), the method the ATTACK /
   DEFEND / SPECIAL buttons call. So it has to follow every rule a human follows.

The difficulty (DIFFICULTY_SETTINGS) changes only these choices and the aiming
error, never the damage, the cooldowns or which actions are allowed.

Only the Python standard library is used: no Pygame and no machine learning.
"""
import copy
import random

from battle import FIELD_WIDTH, MAX_ANGLE, MAX_POWER, MAX_STEPS, MIN_ANGLE, MIN_POWER, clamp, other_side
from castle import LOSS_PERCENT
from characters import ARCHETYPES, Archer, Engineer, Knight

# How each difficulty plays. All of them follow exactly the same game rules.
#   angle_error, power_error  the most the final aim can be off (degrees, power points)
#   top_choices               choose at random among this many of the best options (1 = always the best)
#   special_chance            chance per turn that Rally, Power Shot and Repair are considered at all
#   defend_chance             chance to Defend when every character has at least half its HP
#   hurt_defend_chance        chance to Defend when a character is below half its HP
DIFFICULTY_SETTINGS = {
    "easy": {"angle_error": 6, "power_error": 8, "top_choices": 5,
             "special_chance": 0.25, "defend_chance": 0.10, "hurt_defend_chance": 0.40},
    "normal": {"angle_error": 3, "power_error": 4, "top_choices": 3,
               "special_chance": 0.50, "defend_chance": 0.05, "hurt_defend_chance": 0.50},
    "hard": {"angle_error": 1, "power_error": 2, "top_choices": 1,
             "special_chance": 1.00, "defend_chance": 0.00, "hurt_defend_chance": 0.60},
}

SCAN_ANGLES = (30, 45, 60)       # the aims tried: a low, a middle and a high arc ...
SCAN_POWER_STEP = 2              # ... each with every second power: 100, 98, 96, ...
FALLBACK_AIM = (45, 70)          # used only if no aim at all would hit anything
DEFEAT_BONUS = 0.25              # extra score for each enemy an option would defeat
WIN_BONUS = 10                   # an option that wins the game beats everything else


class Plan:
    """One decision: who acts (their slot), what they do, and the aim if the action fires."""

    def __init__(self, actor_index, action, angle=None, power=None, score=0.0,
                 reason="", defensive=False):
        self.actor_index = actor_index
        self.action = action            # "attack", "defend" or "special"
        self.angle = angle              # None if the action fires nothing
        self.power = power
        self.score = score              # how much closer to winning (see progress())
        self.reason = reason            # a short sentence for the combat log
        self.defensive = defensive      # Defend or Rally

    def fires_a_shot(self):
        return self.angle is not None


# ----- looking ahead on a copy of the battle ---------------------------------------

def aim_cannon(cannon, angle, power):
    """Turn a cannon to (angle, power) with its own methods, which keep the aim legal."""
    cannon.adjust_angle(angle - cannon.angle)
    cannon.adjust_power(power - cannon.power)


def imagine(battle, actor_index, action, angle=None, power=None):
    """Try an action on a copy of the battle and let any shot land.

    Returns (the copy afterwards, the events the action produced). The real battle
    is not changed.
    """
    trial = copy.deepcopy(battle)
    if angle is not None:
        aim_cannon(trial.cannons[trial.active_side], angle, power)
    trial.take_events()                          # forget anything from before this action
    trial.perform_action(actor_index, action)
    for _ in range(MAX_STEPS):                   # every shot lands within MAX_STEPS steps
        if trial.projectile is None:
            break
        trial.update()
    return trial, trial.take_events()


def team_hp(team):
    return sum(character.hp for character in team.characters)


def hp_before_falling(castle):
    """How much more HP the castle can lose before it falls (at 60 % destruction)."""
    return castle.total_hp() - castle.max_hp * (100 - LOSS_PERCENT) / 100


def progress(before, after, side):
    """How much closer `side` is to winning in `after` than in `before` (0 = no progress).

    Each way to win counts as the share of its remaining work that got done:
      elimination:  enemy HP removed / enemy HP that was left (+ a bonus per defeat)
      castle:       enemy castle HP removed / HP it could still lose (if that rule is on)
      Repair:       our castle HP restored / HP it could still lose (our loss moves away)
    """
    enemy = other_side(side)
    score = 0.0
    enemy_hp = team_hp(before.teams[enemy])
    if enemy_hp > 0:
        score += (enemy_hp - team_hp(after.teams[enemy])) / enemy_hp
    defeated = (len(before.teams[enemy].alive_characters())
                - len(after.teams[enemy].alive_characters()))
    score += DEFEAT_BONUS * defeated
    if before.castle_loss_enabled:
        damage = before.castles[enemy].total_hp() - after.castles[enemy].total_hp()
        score += min(1.0, damage / max(1, hp_before_falling(before.castles[enemy])))
        repaired = after.castles[side].total_hp() - before.castles[side].total_hp()
        score += min(1.0, repaired / max(1, hp_before_falling(before.castles[side])))
    if after.winner == side:
        score += WIN_BONUS
    return score


def what_it_hits(events):
    """(names of the characters hit, number of blocks hit) by an imagined shot, or None."""
    for event in events:
        if event["type"] == "explosion" and (event["characters_hit"] or event["blocks_hit"]):
            return tuple(hit["name"] for hit in event["characters_hit"]), event["blocks_hit"]
    return None


def landed_on_own_half(events, side):
    """True if the imagined shot came down on the shooter's own half of the field."""
    for event in events:
        if event["type"] in ("explosion", "miss"):
            middle = FIELD_WIDTH / 2
            return event["x"] < middle if side == "left" else event["x"] > middle
    return False


def describe_target(hit, enemy):
    names, _ = hit
    if names:
        return f"the {enemy.upper()} {' and '.join(names)}"
    return f"the {enemy.upper()} castle"


# ----- the controller ------------------------------------------------------------------

class AIController:
    """Plays one team ("right" in Player vs AI) at one difficulty.

    seed: give a number to make its random choices repeatable (the tests do this).
    """

    def __init__(self, side="right", difficulty="normal", seed=None):
        if difficulty not in DIFFICULTY_SETTINGS:
            raise ValueError(f"difficulty must be one of {', '.join(DIFFICULTY_SETTINGS)}")
        self.side = side
        self.difficulty = difficulty
        self.settings = DIFFICULTY_SETTINGS[difficulty]
        self.rng = random.Random(seed)
        self.defended_last_turn = False

    def new_match(self):
        """Call when a new match starts with this controller."""
        self.defended_last_turn = False

    def pick_team(self, size):
        """A legal team for this AI: `size` different roles in random slot order."""
        return self.rng.sample(ARCHETYPES, size)

    # ----- one turn ------------------------------------------------------------------

    def take_turn(self, battle):
        """Choose and carry out this turn's action. Returns the Plan, or None if the AI
        may not act now (not its turn, a shot in the air, or the game is over)."""
        plan = self.choose(battle)
        if plan is None:
            return None
        if plan.fires_a_shot():
            aim_cannon(battle.cannons[self.side], plan.angle, plan.power)
        if not battle.perform_action(plan.actor_index, plan.action):
            return None                          # can't happen: choose() checked the plan
        self.defended_last_turn = plan.defensive
        return plan

    def choose(self, battle):
        """Decide this turn's action without changing the battle (None if it isn't our turn)."""
        if battle.teams is None or battle.active_side != self.side or not battle.can_fire():
            return None
        team = battle.teams[self.side]
        use_specials = self.rng.random() < self.settings["special_chance"]
        if self.wants_to_defend(team):
            plan = self.defensive_plan(battle, use_specials)
        else:
            plan = self.attack_plan(battle, use_specials)
        if battle.why_not_allowed(plan.actor_index, plan.action) is not None:
            # A safety net (it should never be needed): Defend is always allowed on our turn.
            first_alive = next(i for i, c in enumerate(team.characters) if c.is_alive())
            plan = Plan(first_alive, "defend", defensive=True,
                        reason=f"{team.characters[first_alive].name} defends (safety net: "
                               f"the planned action was not allowed)")
        return plan

    def wants_to_defend(self, team):
        """Roll the dice for a defensive turn.

        A character below half its HP makes defending more likely. Never two
        defensive turns in a row, so the AI can't stall the game.
        """
        if self.defended_last_turn:
            return False
        hurt = any(character.hp * 2 < character.max_hp for character in team.alive_characters())
        chance = self.settings["hurt_defend_chance"] if hurt else self.settings["defend_chance"]
        return self.rng.random() < chance

    def defensive_plan(self, battle, use_specials):
        """Rally if the Knight can protect two or more allies, otherwise the weakest character defends."""
        team = battle.teams[self.side]
        living = [(i, c) for i, c in enumerate(team.characters) if c.is_alive()]
        weakest_index, weakest = min(living, key=lambda pair: pair[1].hp / pair[1].max_hp)
        hurt = weakest.hp * 2 < weakest.max_hp
        if use_specials and len(living) >= 2:
            for index, character in living:
                if isinstance(character, Knight) and battle.why_not_allowed(index, "special") is None:
                    why = f"{weakest.name} is below half HP, so " if hurt else ""
                    return Plan(index, "special", defensive=True,
                                reason=f"{why}{character.name} uses Rally to protect the team")
        reason = f"{weakest.name} is below half HP, so it defends" if hurt else f"{weakest.name} defends"
        return Plan(weakest_index, "defend", reason=reason, defensive=True)

    def attack_plan(self, battle, use_specials):
        """Pick a target, the character (and Attack or Power Shot) to fire at it, then add
        the aiming error. A Repair is chosen instead if it would be worth more."""
        team = battle.teams[self.side]
        living = [i for i, c in enumerate(team.characters) if c.is_alive()]
        targets = self.find_targets(battle, living[0])
        if targets:
            _, angle, power, description = self.rng.choice(targets[:self.settings["top_choices"]])
        else:
            (angle, power), description = FALLBACK_AIM, f"the {other_side(self.side).upper()} side"

        shooters = []                                  # (score, slot, action)
        for index in living:
            actions = ["attack"]
            if (use_specials and isinstance(team.characters[index], Archer)
                    and battle.why_not_allowed(index, "special") is None):
                actions.append("special")
            for action in actions:
                trial, _ = imagine(battle, index, action, angle, power)
                shooters.append((progress(battle, trial, self.side), index, action))
        shooters.sort(key=lambda option: option[0], reverse=True)    # stable: ties keep slot order
        score, index, action = self.rng.choice(shooters[:self.settings["top_choices"]])
        name = team.characters[index].name
        verb = "uses Power Shot on" if action == "special" else "attacks"
        plan = Plan(index, action, angle, power, score, f"{name} {verb} {description}")

        if use_specials:
            repair = self.repair_plan(battle)
            if repair is not None and repair.score > plan.score:
                return repair
        return self.with_aiming_error(plan)

    def find_targets(self, battle, scout_index):
        """Imagine Attacks at many aims and list what they can hit, best first.

        Returns [(score, angle, power, description), ...] with one entry for each
        different thing a shot can hit that helps to win (score above 0; with castle
        loss switched off, the castle isn't a target). For each one the most forgiving
        aim is kept: the middle power of the angle at which the most powers hit it,
        so a small aiming error still hits.
        """
        side = battle.active_side
        aims = {}            # what is hit -> {angle: [(power, score), ...]}
        for angle in SCAN_ANGLES:
            # Strong shots first. Once a shot comes down on our own half of the field,
            # every weaker shot at this angle lands even shorter, so stop there.
            for power in range(MAX_POWER, MIN_POWER - 1, -SCAN_POWER_STEP):
                trial, events = imagine(battle, scout_index, "attack", angle, power)
                hit = what_it_hits(events)
                score = progress(battle, trial, side)
                if hit is not None and score > 0:
                    aims.setdefault(hit, {}).setdefault(angle, []).append((power, score))
                if landed_on_own_half(events, side):
                    break
        targets = []
        for hit, by_angle in aims.items():
            angle = max(by_angle, key=lambda a: len(by_angle[a]))     # most powers hit at this angle
            powers = sorted(by_angle[angle])
            power, score = powers[len(powers) // 2]                    # the middle one
            targets.append((score, angle, power, describe_target(hit, other_side(side))))
        targets.sort(reverse=True)
        return targets

    def repair_plan(self, battle):
        """A Repair by a living Engineer whose special is ready, or None."""
        team = battle.teams[self.side]
        for index, character in enumerate(team.characters):
            if isinstance(character, Engineer) and battle.why_not_allowed(index, "special") is None:
                trial, _ = imagine(battle, index, "special")
                percent = int(battle.castles[self.side].destruction_percent())
                return Plan(index, "special", score=progress(battle, trial, self.side),
                            reason=f"{character.name} uses Repair ({percent}% of the castle destroyed)")
        return None

    def with_aiming_error(self, plan):
        """Add a random error to the plan's aim, kept within the cannon's legal limits."""
        if plan.fires_a_shot():
            angle_error, power_error = self.settings["angle_error"], self.settings["power_error"]
            plan.angle = clamp(plan.angle + self.rng.randint(-angle_error, angle_error), MIN_ANGLE, MAX_ANGLE)
            plan.power = clamp(plan.power + self.rng.randint(-power_error, power_error), MIN_POWER, MAX_POWER)
        return plan
