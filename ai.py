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

M6.3: a special that fires (Power Shot, and now Triple Volley and Airburst: the role's
SPECIAL_SHELLS) is imagined on the copy like an Attack, so the real rules decide how much its
shells are worth. When a Triple Volley or Airburst could be fired, every shooter is also tried at
the aims of the next EXTRA_AIMS best targets, and every option is rated by its average over the
AI's own power error (as expected_score does for targets): a spread of shells is worth having
because a slightly wrong aim still hits. A Medic's Field Dressing is chosen instead when the HP it
restores is worth more than the shot (heal_plan); with nobody hurt it is never chosen.

M6.4: the rules have no chance in them, so an imagined shot always ends the same way. Within one
decision the AIController remembers every shot it has imagined (AIController.imagine), so none is
imagined twice. And thinking_ahead() imagines, one shot per step, the shots the next decision will
ask for: main.py runs a few steps in each frame of the computer's pause, so the decision itself
finds them in the memory and the window keeps answering. Neither rolls dice or changes a score, so
every decision is exactly the one the AI made before.

The difficulty (DIFFICULTY_SETTINGS) changes only these choices and the aiming error,
never the damage, the cooldowns, the cover budget or which actions are allowed. The AI
sees only what a player sees: the battlefield, the HP bars and its own aiming skill.

Only the Python standard library is used: no Pygame and no machine learning.
"""
import copy
import random

from battle import FIELD_WIDTH, MAX_ANGLE, MAX_POWER, MAX_STEPS, MIN_ANGLE, MIN_POWER, clamp, other_side
from castle import MAX_BLOCKS, SLOT_COUNT, place_block
from characters import ARCHETYPES, Engineer, Knight, Medic, calculate_damage

# How each difficulty plays. All of them follow exactly the same game rules.
#   angle_error, power_error  the most the final aim can be off (degrees, power points)
#   top_choices               choose at random among this many of the best options (1 = always the best)
#   special_chance            chance per turn that Rally, Power Shot and Repair are considered at all
#   defend_chance             chance to Defend when every character has at least half its HP
#   hurt_defend_chance        chance to Defend when a character is below half its HP
# Easy aimed with 6 / 8 / 5 until M3.4-B.1. With cover that error was wider than the gap in
# which a shot can reach a character, so even Easy's best aim damaged one only about 4 times in
# 10, and most Easy-vs-Easy 3v3 matches ran out of rounds. 4 / 5 / 4 still misses far more than
# Normal (docs/M0_design.md, "M3.4-B.1 notes").
DIFFICULTY_SETTINGS = {
    "easy": {"angle_error": 4, "power_error": 5, "top_choices": 4,
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
# M6.3: when a Triple Volley or Airburst could be fired, every shooter is also tried at the aims of this
# many more of the best targets (a spread of shells may do best at another aim than one shell).
EXTRA_AIMS = 2


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
        # front of one), "defend", "repair", "heal" (M6.3), or None (the fallback aim).
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


def heal_value(battle, side, gained):
    """What restoring `gained` HP to one of `side`'s characters is worth (M6.3, Field Dressing), on
    the same scale as progress(): the HP restored / our team's HP left. It is the mirror of the
    damage part of progress() (enemy HP removed / enemy HP left), so the less HP the team has left,
    the more a heal is worth."""
    return gained / max(1, team_hp(battle.teams[side]))


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


def scan_aims(battle, scout_index, imagine_shot=None):
    """Imagine an Attack by the active team's character in `scout_index` at every scan aim.

    Returns [(angle, power, the copy afterwards, its events), ...]. Strong shots come
    first; once a shot comes down on our own half of the field, every weaker shot at
    that angle lands even shorter, so the scan of that angle stops there.
    imagine_shot: the function that imagines one shot (None: imagine). M6.4: an AIController
    passes its own, which remembers the shots of one decision (AIController.imagine).
    """
    return list(scanning(battle, scout_index, imagine_shot))


def scanning(battle, scout_index, imagine_shot=None):
    """scan_aims(), one aim at a time (M6.4): a generator that gives each scanned aim as soon as it
    is imagined, so the work can be spread over several frames (AIController.thinking_ahead)."""
    imagine_shot = imagine_shot or imagine
    side = battle.active_side
    for angle in SCAN_ANGLES:
        for power in range(MAX_POWER, MIN_POWER - 1, -SCAN_POWER_STEP):
            trial, events = imagine_shot(battle, scout_index, "attack", angle, power)
            yield angle, power, trial, events
            if landed_on_own_half(events, side):
                break


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
        # M6.4: the shots imagined for the decision being made, and the battle they belong to
        # (see imagine): {(slot, action, angle, power): (the copy afterwards, its events)}.
        self.memory = {}
        self.memory_battle = None

    def new_match(self):
        """Call when a new match starts with this controller."""
        self.defended_last_turn = False
        self.forget()

    # ----- M6.4: a memory of imagined shots, and thinking ahead ---------------------------

    def forget(self):
        """Empty the memory of imagined shots: after each decision, and when a match starts again."""
        self.memory = {}
        self.memory_battle = None

    def imagine(self, battle, actor_index, action, angle=None, power=None):
        """imagine(), remembered for one decision. The rules have no chance in them, so the same
        action with the same aim on the same battle always ends the same way: it is imagined once,
        and when it is asked for again the result comes from the memory. The aim is first kept
        inside the cannon's limits (as aim_cannon does), so power 104 and power 100 are one shot.
        Shots imagined on another Battle object are never used."""
        if battle is not self.memory_battle:
            self.forget()
            self.memory_battle = battle
        if angle is not None:
            angle = clamp(angle, MIN_ANGLE, MAX_ANGLE)
            power = clamp(power, MIN_POWER, MAX_POWER)
        key = (actor_index, action, angle, power)
        if key not in self.memory:
            self.memory[key] = imagine(battle, actor_index, action, angle, power)
        return self.memory[key]

    def thinking_ahead(self, battle):
        """Imagine now, one shot per step, the shots the next decision on `battle` will ask for, so
        they are in the memory when choose() asks. A generator: main.py runs a few steps in each
        frame of the computer's pause, so the decision itself takes only a moment and the window
        keeps answering. It rolls no dice and changes nothing else, so the decision is exactly the
        one choose() would make without it.

        The steps: the scan (an attack plan always starts with it); then every option the attack
        plan could rate: the aims of the best targets it may choose from (and FALLBACK_AIM if there
        are none), each living shooter, Attack and a special that fires, at the aim's power and, if
        a Triple Volley or Airburst is ready, at both ends of the power error; then a Repair. The
        dice decide which of these the decision really uses; the others cost only time in which
        the computer was waiting anyway."""
        team = battle.teams[self.side]
        living = [i for i, c in enumerate(team.characters) if c.is_alive()]
        if battle.active_side != self.side or not battle.can_fire() or not living:
            return
        scan = []
        for scanned in scanning(battle, living[0], self.imagine):
            scan.append(scanned)
            yield
        routes = find_routes(battle, self.side, scan)
        targets = self.rank_targets(battle, scan, routes)
        yield
        choices = max(self.settings["top_choices"], EXTRA_AIMS + 1)      # see attack_plan
        aims = [(angle, power) for _, angle, power, _, _ in targets[:choices]] or [FALLBACK_AIM]
        error = self.settings["power_error"]
        changes = (-error, 0, error) if self.spread_ready(battle, living) else (0,)
        for angle, power in aims:
            for index in living:
                for action in self.firing_actions(battle, index, True):
                    for change in changes:
                        self.imagine(battle, index, action, angle, power + change)
                        yield
        for index, character in enumerate(team.characters):             # see repair_plan
            if isinstance(character, Engineer) and battle.why_not_allowed(index, "special") is None:
                self.imagine(battle, index, "special")
                yield

    def spread_ready(self, battle, living):
        """True if one of the living characters (slots) could fire a Triple Volley or an Airburst now."""
        team = battle.teams[self.side]
        return any(team.characters[i].SPECIAL_SHELLS > 1 and battle.why_not_allowed(i, "special") is None
                   for i in living)

    def firing_actions(self, battle, index, use_specials):
        """The actions that fire which slot `index` may choose: Attack, and its special if it fires
        shells, specials are considered this turn and the special is ready."""
        actions = ["attack"]
        character = battle.teams[self.side].characters[index]
        if use_specials and character.SPECIAL_SHELLS > 0 and battle.why_not_allowed(index, "special") is None:
            actions.append("special")
        return actions

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
        """Choose and carry out this turn's action at once. Returns the Plan, or None if the
        AI may not act now (not its turn, a shot in the air, or the game is over).

        The tests and benchmarks use this. The game (main.py) calls choose() and carry_out()
        separately instead: since M3.4-C it first shows the character running to the cannon,
        and carries out a firing plan only when the character gets there."""
        plan = self.choose(battle)
        if plan is None:
            return None
        return self.carry_out(battle, plan)

    def carry_out(self, battle, plan):
        """Carry out a Plan from choose(): aim the cannon if the plan fires, then call
        Battle.perform_action(), the method the ATTACK / DEFEND / SPECIAL buttons call.
        Returns the plan, or None if the plan is no longer allowed (then nothing changes)."""
        if battle.why_not_allowed(plan.actor_index, plan.action) is not None:
            return None                          # not in play: choose() checked the plan
        if plan.fires_a_shot():
            aim_cannon(battle.cannons[self.side], plan.angle, plan.power)
        battle.perform_action(plan.actor_index, plan.action)
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
            if battle.why_not_allowed(plan.actor_index, plan.action) is not None:
                # M4.2-B: Defend is refused right after the team's own Defend (anti-stall).
                # The AI never plans that itself; a new controller mid-match might.
                plan = self.attack_plan(battle, use_specials)
        else:
            plan = self.attack_plan(battle, use_specials)
        if battle.why_not_allowed(plan.actor_index, plan.action) is not None:
            plan = self.safety_plan(battle)          # it should never be needed
        self.forget()                                # M6.4: the memory served this decision only
        return plan

    def safety_plan(self, battle):
        """A plan the Battle is sure to accept, for when the chosen one was refused.

        Defend by the first living character if Defend is allowed; otherwise (since M4.2-B the
        anti-stall rule forbids a Defend right after the team's own Defend) a normal Attack
        with FALLBACK_AIM by the first living character. Both are checked with
        Battle.why_not_allowed; on our turn a living character may always Attack, so this
        always finds a plan and the turn can't get stuck."""
        for index, character in enumerate(battle.teams[self.side].characters):
            if not character.is_alive():
                continue
            why = "the planned action was not allowed"
            if battle.why_not_allowed(index, "defend") is None:
                return Plan(index, "defend", defensive=True, goal="defend",
                            reason=f"{character.name} defends (safety net: {why})")
            if battle.why_not_allowed(index, "attack") is None:
                angle, power = FALLBACK_AIM
                return Plan(index, "attack", angle, power,
                            reason=f"{character.name} attacks (safety net: {why})")
        return None                                   # not our turn after all (choose() checked)

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
        Attack or a special that fires) to fire at it, then add the aiming error. A Repair or
        (M6.3) a Field Dressing is chosen instead if it would be worth more.

        M6.3: if a Triple Volley or Airburst could be fired this turn, every shooter is also tried
        at the aims of up to EXTRA_AIMS more of the best targets, every option is rated by its
        average over this AI's power error (option_value), and the best (shooter, action, aim) is
        chosen. Otherwise only the chosen target's aim is tried, exactly as before."""
        team = battle.teams[self.side]
        living = [i for i, c in enumerate(team.characters) if c.is_alive()]
        scan = scan_aims(battle, living[0], self.imagine)
        routes = find_routes(battle, self.side, scan)
        targets = self.rank_targets(battle, scan, routes)
        if targets:
            _, angle, power, description, goal = self.rng.choice(targets[:self.settings["top_choices"]])
        else:
            (angle, power), goal = FALLBACK_AIM, None
            description = f"the {other_side(self.side).upper()} side"

        aims = [(angle, power, description, goal)]
        spread_ready = self.spread_ready(battle, living)
        if use_specials and spread_ready:                 # M6.3: a few more aims for the shells to try
            for _, other_angle, other_power, other_description, other_goal in targets:
                if len(aims) > EXTRA_AIMS:
                    break
                if (other_angle, other_power) != (angle, power):
                    aims.append((other_angle, other_power, other_description, other_goal))

        shooters = []                                  # (score, slot, action, aim)
        for option in aims:
            for index in living:
                for action in self.firing_actions(battle, index, use_specials):
                    value = self.option_value(battle, routes, index, action, option[0], option[1],
                                              averaged=use_specials and spread_ready)
                    shooters.append((value, index, action, option))
        shooters.sort(key=lambda option: option[0], reverse=True)    # stable: ties keep aim and slot order
        score, index, action, (angle, power, description, goal) = self.rng.choice(
            shooters[:self.settings["top_choices"]])
        character = team.characters[index]
        verb = f"uses {character.SPECIAL_NAME} on" if action == "special" else "attacks"
        plan = Plan(index, action, angle, power, score, f"{character.name} {verb} {description}", goal=goal)

        if use_specials:
            best = plan
            for support in (self.repair_plan(battle), self.heal_plan(battle)):
                if support is not None and support.score > best.score:
                    best = support
            if best is not plan:
                return best
        return self.with_aiming_error(plan)

    def option_value(self, battle, routes, index, action, angle, power, averaged):
        """shot_value() of `action` by slot `index` fired at (angle, power), imagined on a copy.

        averaged (M6.3, only when a Triple Volley or Airburst could be fired): the average at the
        power itself and at the two ends of this AI's power error (the most its real shot can be
        off), so an option that still does well when the aim is a little off is rated higher.
        Three tries, not every power in between, keep the extra thinking time small."""
        if not averaged:
            trial, _ = self.imagine(battle, index, action, angle, power)
            return shot_value(battle, trial, self.side, routes)
        error = self.settings["power_error"]
        values = []
        for change in (-error, 0, error):
            trial, _ = self.imagine(battle, index, action, angle, clamp(power + change, MIN_POWER, MAX_POWER))
            values.append(shot_value(battle, trial, self.side, routes))
        return sum(values) / len(values)

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
                trial, _ = self.imagine(battle, index, "special")
                castle = battle.castles[self.side]
                missing = castle.max_hp - castle.total_hp()
                return Plan(index, "special", score=progress(battle, trial, self.side), goal="repair",
                            reason=f"{character.name} uses Repair ({missing} cover HP missing)")
        return None

    def heal_plan(self, battle):
        """A Field Dressing by a living Medic whose special is ready (M6.3), or None. Its score is
        heal_value() of the HP it would really restore, to the same target the heal will choose
        (Medic.heal_target). With nobody hurt the special is refused, so this is None."""
        team = battle.teams[self.side]
        for index, character in enumerate(team.characters):
            if isinstance(character, Medic) and battle.why_not_allowed(index, "special") is None:
                target, amount = character.heal_target(team)
                return Plan(index, "special", score=heal_value(battle, self.side, amount), goal="heal",
                            reason=f"{character.name} uses Field Dressing on {target.name} (+{amount} HP)")
        return None

    def with_aiming_error(self, plan):
        """Add a random error to the plan's aim, kept within the cannon's legal limits."""
        if plan.fires_a_shot():
            angle_error, power_error = self.settings["angle_error"], self.settings["power_error"]
            plan.angle = clamp(plan.angle + self.rng.randint(-angle_error, angle_error), MIN_ANGLE, MAX_ANGLE)
            plan.power = clamp(plan.power + self.rng.randint(-power_error, power_error), MIN_POWER, MAX_POWER)
        return plan
