"""The computer opponent for Player vs AI (Milestone 3.1; cover-aware since M3.4-B).

Before a battle, an AIController places its team's cover (choose_layout). On its turn it:
1. decides whether to Defend. A character below half HP makes that more likely
   (a course requirement), but it never defends two turns in a row, so it keeps
   making progress;
2. otherwise "imagines" shots: it tries aims on a COPY of the battle
   (copy.deepcopy) and looks at what the explosion does there. The copy runs the
   real rules, so this file repeats none of them, and the real battle is not touched;
3. rates every aim it tried (see shot_value):
   - damage: how much closer the shot brings it to winning (enemy HP removed, defeats);
   - cover: how much of the cover that stands between its cannon and a living enemy
     the shot breaks. To find that cover it traces the whole path of each aim that
     ends on a block (Battle.path_contacts): if a living enemy stands behind the
     blocks, those blocks are "in the way" of a shot at that enemy (a route). A block
     that is in nobody's way is worth nothing to break;
   and because it knows its own aiming error, it rates an aim by the average of the
   aims around it that it might really fire (a narrow gap over the cover is worth
   less than a wide one, so a protected enemy makes breaking the cover attractive);
4. picks one of the best aims (Easy picks less carefully), adds its aiming error, and
   carries the plan out with Battle.perform_action(), the method the ATTACK / DEFEND /
   SPECIAL buttons call. So it has to follow every rule a human follows.

The difficulty (DIFFICULTY_SETTINGS) changes only these choices and the aiming error,
never the damage, the cooldowns, the cover budget or which actions are allowed. The AI
sees only what a player sees: the battlefield, the HP bars and its own aiming skill.

Only the Python standard library is used: no Pygame and no machine learning.
"""
import copy
import random

from battle import FIELD_WIDTH, MAX_ANGLE, MAX_POWER, MAX_STEPS, MIN_ANGLE, MIN_POWER, clamp, other_side
from castle import MAX_BLOCKS, SLOT_COUNT, place_block
from characters import ARCHETYPES, Archer, Engineer, Knight, calculate_damage

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
FALLBACK_AIM = (45, 70)          # used only if no aim at all would help
DEFEAT_BONUS = 0.25              # extra score for each enemy an option would defeat
WIN_BONUS = 10                   # an option that wins the game beats everything else
# Breaking cover pays off one turn later at the earliest (and the enemy may Repair it), so
# opening a shot at an enemy counts half as much as hitting that enemy now.
COVER_WEIGHT = 0.5
TOWER = (0, 4)                   # the AI's cover always starts with these two slots (see choose_layout)


class Plan:
    """One decision: who acts (their slot), what they do, and the aim if the action fires."""

    def __init__(self, actor_index, action, angle=None, power=None, score=0.0,
                 reason="", defensive=False, goal=None):
        self.actor_index = actor_index
        self.action = action            # "attack", "defend" or "special"
        self.angle = angle              # None if the action fires nothing
        self.power = power
        self.score = score              # how much closer to winning (see shot_value())
        self.reason = reason            # a short sentence for the combat log
        self.defensive = defensive      # Defend or Rally
        # What the action is for: "damage" (hit a character), "cover" (break cover in
        # front of one), "defend", "repair", or None (the fallback aim).
        self.goal = goal

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


def progress(before, after, side):
    """How much closer `side` is to winning in `after` than in `before` (0 = no progress).

      elimination:  enemy HP removed / enemy HP that was left (+ a bonus per defeat)
      Repair:       our block HP restored / our cover's full HP (more cover protects us)
    """
    enemy = other_side(side)
    score = 0.0
    enemy_hp = team_hp(before.teams[enemy])
    if enemy_hp > 0:
        score += (enemy_hp - team_hp(after.teams[enemy])) / enemy_hp
    defeated = (len(before.teams[enemy].alive_characters())
                - len(after.teams[enemy].alive_characters()))
    score += DEFEAT_BONUS * defeated
    repaired = after.castles[side].total_hp() - before.castles[side].total_hp()
    score += max(0, repaired) / max(1, before.castles[side].max_hp)
    if after.winner == side:
        score += WIN_BONUS
    return score


def first_explosion(events):
    """The explosion event of an imagined shot, or None if it flew off the field."""
    for event in events:
        if event["type"] == "explosion":
            return event
    return None


def landed_on_own_half(events, side):
    """True if the imagined shot came down on the shooter's own half of the field."""
    for event in events:
        if event["type"] in ("explosion", "miss"):
            middle = FIELD_WIDTH / 2
            return event["x"] < middle if side == "left" else event["x"] > middle
    return False


def scan_aims(battle, scout_index):
    """Imagine an Attack by the active team's character in `scout_index` at every scan aim.

    Returns [(angle, power, the copy afterwards, its events), ...]. Strong shots come
    first; once a shot comes down on our own half of the field, every weaker shot at
    that angle lands even shorter, so the scan of that angle stops there.
    """
    side = battle.active_side
    scan = []
    for angle in SCAN_ANGLES:
        for power in range(MAX_POWER, MIN_POWER - 1, -SCAN_POWER_STEP):
            trial, events = imagine(battle, scout_index, "attack", angle, power)
            scan.append((angle, power, trial, events))
            if landed_on_own_half(events, side):
                break
    return scan


# ----- cover: which enemy blocks are in the way of a shot at a living enemy ------------

def hit_value(battle, side, target_slot):
    """What one direct hit on the enemy in `target_slot` would be worth to `side`, on the
    same scale as progress(): its HP removed / the enemy HP left, plus DEFEAT_BONUS if
    the hit would defeat it. The shooter is `side`'s first living character, and the
    target's Defend is ignored, because it ends before the next turn."""
    shooter = battle.teams[side].alive_characters()[0]
    enemy_team = battle.teams[other_side(side)]
    target = enemy_team.characters[target_slot]
    damage = calculate_damage(shooter.atk, target.defense, defending=False)
    value = min(damage, target.hp) / team_hp(enemy_team)
    if damage >= target.hp:
        value += DEFEAT_BONUS
    return value


def find_routes(battle, side, scan):
    """The shots at living enemies that enemy cover is blocking right now.

    For every scanned aim whose shot comes down on an enemy block, the whole path is
    traced (Battle.path_contacts, the same flight and collision code as a real shot).
    If the path reaches a living enemy character behind the blocks, that is a route:
    those blocks are in the way of a shot at that character. Returns
    [(the character's slot, (indices of the blocks in the way, in castle.blocks), the
    route's value = hit_value of that character), ...], one entry per different route.
    """
    routes = {}
    for angle, power, _, events in scan:
        explosion = first_explosion(events)
        if explosion is None or explosion["kind"] != "block":
            continue
        in_the_way = []
        for kind, number, _, _ in battle.path_contacts(side, angle, power):
            if kind == "block":
                in_the_way.append(number)
                continue
            if kind == "character" and (number, tuple(in_the_way)) not in routes:
                routes[(number, tuple(in_the_way))] = hit_value(battle, side, number)
            break                                    # a character, the ground or the edge
    return [(target, blockers, value) for (target, blockers), value in routes.items()]


def cover_value(battle, trial, side, routes):
    """What an imagined shot does to the cover in the way of the routes.

    For each route, the shot removes a share of the HP of the blocks in its way (1 when
    they are all destroyed); that share times the route's value is how far the shot
    opens that route. Returns (the best of those, the target's slot, True if that
    route is now fully open), or (0.0, None, False) if the shot opens nothing.
    A block that stands in no route is worth nothing, however much it is damaged.
    """
    enemy = other_side(side)
    before, after = battle.castles[enemy].blocks, trial.castles[enemy].blocks
    best = (0.0, None, False)
    for target, blockers, value in routes:
        blocking = sum(before[i].hp for i in blockers)
        removed = sum(before[i].hp - after[i].hp for i in blockers)
        if removed > 0 and value * removed / blocking > best[0]:
            best = (value * removed / blocking, target, removed == blocking)
    return best


def shot_value(battle, trial, side, routes):
    """The score of an imagined shot: progress() (character damage, defeats, a win) plus
    COVER_WEIGHT x cover_value() (how far it opens a shot at a living enemy)."""
    return progress(battle, trial, side) + COVER_WEIGHT * cover_value(battle, trial, side, routes)[0]


def describe_shot(battle, trial, events, side, routes):
    """(goal, description) of an imagined shot, for the plan and the combat log:
    ("damage", "the RIGHT Knight"), ("cover", "the cover in front of the RIGHT Knight"),
    or (None, "") for a shot that helps with neither."""
    enemy = other_side(side)
    explosion = first_explosion(events)
    if explosion is not None and explosion["characters_hit"]:
        names = " and ".join(hit["name"] for hit in explosion["characters_hit"])
        return "damage", f"the {enemy.upper()} {names}"
    value, target, _ = cover_value(battle, trial, side, routes)
    if value > 0:
        return "cover", f"the cover in front of the {enemy.upper()} {battle.teams[enemy].characters[target].name}"
    return None, ""


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

    def choose_layout(self):
        """This AI's cover for a new battle (M3.4-B): a legal layout of MAX_BLOCKS blocks.

        It always builds a two-block tower on the slots next to its characters (TOWER),
        where enemy shots come down on its front character, then puts each remaining
        block on a random slot where a block is allowed (place_block asks layout_problem,
        the same check as a player's click). It never looks at the enemy's cover.
        """
        layout = ()
        for slot in TOWER:
            layout, _ = place_block(layout, slot)
        while len(layout) < MAX_BLOCKS:
            allowed = [slot for slot in range(SLOT_COUNT) if place_block(layout, slot)[1] is None]
            if not allowed:
                break
            layout, _ = place_block(layout, self.rng.choice(allowed))
        return layout

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
            plan = Plan(first_alive, "defend", defensive=True, goal="defend",
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
                    return Plan(index, "special", defensive=True, goal="defend",
                                reason=f"{why}{character.name} uses Rally to protect the team")
        reason = f"{weakest.name} is below half HP, so it defends" if hurt else f"{weakest.name} defends"
        return Plan(weakest_index, "defend", reason=reason, defensive=True, goal="defend")

    def attack_plan(self, battle, use_specials):
        """Pick a target (a character, or the cover in front of one), the character (and
        Attack or Power Shot) to fire at it, then add the aiming error. A Repair is chosen
        instead if it would be worth more."""
        team = battle.teams[self.side]
        living = [i for i, c in enumerate(team.characters) if c.is_alive()]
        scan = scan_aims(battle, living[0])
        routes = find_routes(battle, self.side, scan)
        targets = self.rank_targets(battle, scan, routes)
        if targets:
            _, angle, power, description, goal = self.rng.choice(targets[:self.settings["top_choices"]])
        else:
            (angle, power), goal = FALLBACK_AIM, None
            description = f"the {other_side(self.side).upper()} side"

        shooters = []                                  # (score, slot, action)
        for index in living:
            actions = ["attack"]
            if (use_specials and isinstance(team.characters[index], Archer)
                    and battle.why_not_allowed(index, "special") is None):
                actions.append("special")
            for action in actions:
                trial, _ = imagine(battle, index, action, angle, power)
                shooters.append((shot_value(battle, trial, self.side, routes), index, action))
        shooters.sort(key=lambda option: option[0], reverse=True)    # stable: ties keep slot order
        score, index, action = self.rng.choice(shooters[:self.settings["top_choices"]])
        name = team.characters[index].name
        verb = "uses Power Shot on" if action == "special" else "attacks"
        plan = Plan(index, action, angle, power, score, f"{name} {verb} {description}", goal=goal)

        if use_specials:
            repair = self.repair_plan(battle)
            if repair is not None and repair.score > plan.score:
                return repair
        return self.with_aiming_error(plan)

    def find_targets(self, battle, scout_index):
        """What the active team can usefully aim at, best first (see rank_targets)."""
        scan = scan_aims(battle, scout_index)
        return self.rank_targets(battle, scan, find_routes(battle, battle.active_side, scan))

    def rank_targets(self, battle, scan, routes):
        """Turn a scan into a list of targets, best first.

        Returns [(expected score, angle, power, description, goal), ...] with one entry
        for each different target: a character (or several) a shot hits, or the cover
        in front of a character. Shots that help with neither are left out. For each
        target the aim with the best expected score is kept (see expected_score).
        """
        side = battle.active_side
        scores, labels = {}, {}
        for angle, power, trial, events in scan:
            scores[(angle, power)] = shot_value(battle, trial, side, routes)
            labels[(angle, power)] = describe_shot(battle, trial, events, side, routes)
        best = {}
        for (angle, power), score in scores.items():
            goal, description = labels[(angle, power)]
            if score <= 0 or goal is None:
                continue
            expected = self.expected_score(scores, angle, power)
            if description not in best or expected > best[description][0]:
                best[description] = (expected, angle, power, description, goal)
        return sorted(best.values(), key=lambda target: target[0], reverse=True)

    def expected_score(self, scores, angle, power):
        """The average score of the scanned aims this AI may really fire when it aims at
        (angle, power): the same angle, with every scanned power within its power error
        (clamped to the cannon's limits, like the error itself). Aims that weren't scanned
        land on our own half and score 0. So a wide gap scores higher than a narrow one,
        and the less accurate the AI, the more it values wide targets such as cover."""
        steps = self.settings["power_error"] // SCAN_POWER_STEP
        values = [scores.get((angle, clamp(power + k * SCAN_POWER_STEP, MIN_POWER, MAX_POWER)), 0.0)
                  for k in range(-steps, steps + 1)]
        return sum(values) / len(values)

    def repair_plan(self, battle):
        """A Repair by a living Engineer whose special is ready, or None."""
        team = battle.teams[self.side]
        for index, character in enumerate(team.characters):
            if isinstance(character, Engineer) and battle.why_not_allowed(index, "special") is None:
                trial, _ = imagine(battle, index, "special")
                castle = battle.castles[self.side]
                missing = castle.max_hp - castle.total_hp()
                return Plan(index, "special", score=progress(battle, trial, self.side), goal="repair",
                            reason=f"{character.name} uses Repair ({missing} cover HP missing)")
        return None

    def with_aiming_error(self, plan):
        """Add a random error to the plan's aim, kept within the cannon's legal limits."""
        if plan.fires_a_shot():
            angle_error, power_error = self.settings["angle_error"], self.settings["power_error"]
            plan.angle = clamp(plan.angle + self.rng.randint(-angle_error, angle_error), MIN_ANGLE, MAX_ANGLE)
            plan.power = clamp(plan.power + self.rng.randint(-power_error, power_error), MIN_POWER, MAX_POWER)
        return plan
