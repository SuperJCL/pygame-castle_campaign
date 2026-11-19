"""Castle Siege balance benchmark (M3.2).

Plays seeded AI-vs-AI matches under several rule variants and writes the results
as a Markdown file. It never changes a project file: every worker process sets a
variant's three rule numbers in memory (battle.CASTLE_GUARD_PERCENT,
Engineer.REPAIR_POOL and castle.LOSS_PERCENT) just before it plays a match.

Run from the project folder:
    python scripts/balance_benchmark.py --quick          # a small run, to check that it works
    python scripts/balance_benchmark.py                  # the main M3.2 run: Normal and Hard
                                                         # (about 100 minutes on 17 workers)
    python scripts/balance_benchmark.py --difficulties easy --variants A,B,C150,D150
        --decision-variants A,B,C150,D150 --matches 24 --samples 24
        --out docs/M3.2_benchmark_results_easy.md        # the Easy check, one command
                                                         # (about 30 minutes)
    python scripts/balance_benchmark.py --out FILE.md    # where to write the results

What is compared (see docs/M3.2_balance_report.md for the method and the conclusions):
- Strategies, all built on the real AIController, so the aiming is the same:
    aggressive   attacks every turn (never Defends, Rallies or Repairs)
    existing     the shipped M3.1 AI
    defensive    Defends / Rallies whenever its castle could fall to one strong hit
                 or a character is below half HP (never two turns in a row)
    repair       Repairs whenever its Engineer can restore a full Repair
- Mirrored rosters only (both teams have the same roles in the same slots), with the
  sides swapped half of the time, so first-move advantage cancels out.
- Every match is limited to MAX_ROUNDS rounds; a match still going is "unfinished".
"""
import argparse
import copy
import json
import math
import multiprocessing
import os
import sys
import time

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

import battle as battle_module  # noqa: E402  (the modules, so the rule numbers can be set per variant)
import castle  # noqa: E402
from ai import AIController  # noqa: E402
from battle import MAX_STEPS, Battle, other_side  # noqa: E402
from characters import Archer, Engineer, Knight, ShotDamage, calculate_damage  # noqa: E402

MAX_ROUNDS = 40
THREAT_HP = 300            # "the castle could fall to one strong hit": a Power Shot on 4 blocks

# ----- rule variants ------------------------------------------------------------------

VARIANTS = {
    "A":    {"label": "A  Baseline (M3.1 rules)", "guard": False, "repair": 75, "loss": 60, "castle_loss": True},
    "B":    {"label": "B  Castle Guard", "guard": True, "repair": 75, "loss": 60, "castle_loss": True},
    "C125": {"label": "C  Repair 125", "guard": False, "repair": 125, "loss": 60, "castle_loss": True},
    "C150": {"label": "C  Repair 150", "guard": False, "repair": 150, "loss": 60, "castle_loss": True},
    "D125": {"label": "D  Castle Guard + Repair 125", "guard": True, "repair": 125, "loss": 60, "castle_loss": True},
    "D150": {"label": "D  Castle Guard + Repair 150 (adopted)", "guard": True, "repair": 150, "loss": 60, "castle_loss": True},
    "E70":  {"label": "E  Castle loss at 70 %", "guard": False, "repair": 75, "loss": 70, "castle_loss": True},
    "ELIM": {"label": "Elimination only (castle loss off)", "guard": False, "repair": 75, "loss": 60, "castle_loss": False},
}


def apply_rules(rules):
    """Set the variant's numbers in this process (the files are not changed).

    Castle Guard (battle.py) halves the block damage of an enemy shot, rounded down,
    while the target team has a defending character; 0 % switches it off.
    """
    battle_module.CASTLE_GUARD_PERCENT = 50 if rules["guard"] else 0
    Engineer.REPAIR_POOL = rules["repair"]
    castle.LOSS_PERCENT = rules["loss"]


def make_battle(rules, roster):
    return Battle(roster={"left": roster, "right": roster}, castle_loss_enabled=rules["castle_loss"])


# ----- strategies ------------------------------------------------------------------------

class Aggressive(AIController):
    """Attacks every turn: never Defends, Rallies or Repairs (Power Shot is still used)."""

    def wants_to_defend(self, team):
        return False

    def repair_plan(self, battle):
        return None


class Defensive(AIController):
    """Defends or Rallies whenever its castle could fall to one strong hit, or a character
    is below half HP; never two turns in a row. Otherwise it plays like the shipped AI."""

    def __init__(self, side, difficulty, seed, castle_loss):
        super().__init__(side, difficulty, seed)
        self.castle_loss = castle_loss

    def wants_to_defend(self, team):
        if self.defended_last_turn:
            return False
        threatened = self.castle_loss and team.castle.hp_before_falling() <= THREAT_HP
        hurt = any(c.hp * 2 < c.max_hp for c in team.alive_characters())
        return threatened or hurt or super().wants_to_defend(team)


class RepairAware(AIController):
    """Repairs whenever an Engineer's Repair is ready and surviving blocks are missing at
    least a full Repair of HP; otherwise it plays like the shipped AI."""

    def attack_plan(self, battle, use_specials):
        repairable = sum(b.max_hp - b.hp for b in battle.castles[self.side].alive_blocks())
        if repairable >= Engineer.REPAIR_POOL:
            plan = self.repair_plan(battle)
            if plan is not None:
                return plan
        return super().attack_plan(battle, use_specials)


def make_player(name, side, difficulty, seed, rules):
    if name == "defensive":
        return Defensive(side, difficulty, seed, rules["castle_loss"])
    return {"aggressive": Aggressive, "existing": AIController, "repair": RepairAware}[name](side, difficulty, seed)


# ----- the experiment grid ---------------------------------------------------------------

ROSTERS = {1: [[Knight], [Archer], [Engineer]],
           2: [[Knight, Archer], [Knight, Engineer], [Archer, Engineer]],
           3: [[Knight, Archer, Engineer]]}
VERSUS_AGGRESSIVE = ("existing", "defensive", "repair")
MIRRORS = ("aggressive", "existing")


def make_jobs(variants, difficulties, matches_per_size):
    """One job per match. For each size the same number of matches is played, spread over
    its mirrored rosters, with the tested strategy moving first in half of them."""
    jobs = []
    for variant in variants:
        rules = VARIANTS[variant]
        for difficulty in difficulties:
            for size, rosters in ROSTERS.items():
                per_roster = max(2, matches_per_size // len(rosters))
                for roster_index, roster in enumerate(rosters):
                    for i in range(per_roster):
                        first = i % 2 == 0                   # tested strategy on the left (moves first)?
                        for strategy in VERSUS_AGGRESSIVE:
                            if strategy == "repair" and (Engineer not in roster or not rules["castle_loss"]):
                                continue                     # nothing to measure without an Engineer / castle rule
                            left, right = (strategy, "aggressive") if first else ("aggressive", strategy)
                            jobs.append((variant, difficulty, size, roster_index, left, right, i))
                        for strategy in MIRRORS:
                            jobs.append((variant, difficulty, size, roster_index, strategy, strategy, i))
    return jobs


# ----- one match ----------------------------------------------------------------------------

def fly(battle):
    for _ in range(MAX_STEPS + 1):
        if battle.projectile is None:
            break
        battle.update()
    return battle.take_events()


def new_side_stats():
    return {"attack": 0, "power_shot": 0, "defend": 0, "rally": 0, "repair": 0,
            "repaired_hp": 0, "defenses": [], "invalid": 0, "safety_net": 0}


def action_kind(actor, plan):
    if plan.action == "special":
        return {Knight: "rally", Archer: "power_shot", Engineer: "repair"}[type(actor)]
    return plan.action


def measure_defense(record, before, battle, events, shooter_atk, shot, guard):
    """Fill `record` with what the target team's Defend / Rally prevented during this enemy shot."""
    for event in events:
        if event["type"] != "explosion":
            continue
        for hit in event["characters_hit"]:
            target = before["characters"].get(hit["name"])
            if target is None or not target["defending"]:
                continue
            full = min(target["hp"], calculate_damage(shooter_atk, target["defense"], False,
                                                      shot.multiplier, shot.ignores_def))
            record["prevented_character"] += full - hit["damage"]
            if full >= target["hp"] > hit["damage"]:
                record["saved_character"] = True
    if guard and before["guarded"]:
        prevented = 0
        for hp_before, block in zip(before["blocks"], battle.castles[before["side"]].blocks):
            if block.hp < hp_before:
                prevented += min(hp_before, shot.block_damage) - (hp_before - block.hp)
        record["prevented_castle"] += prevented
        target_castle = battle.castles[before["side"]]
        lost_without_guard = target_castle.max_hp - target_castle.total_hp() + prevented
        would_have_fallen = lost_without_guard * 100 >= castle.LOSS_PERCENT * target_castle.max_hp
        if prevented and would_have_fallen and not target_castle.has_fallen():
            record["saved_castle"] = True


def play_match(job):
    variant, difficulty, size, roster_index, left_name, right_name, seed = job
    rules = VARIANTS[variant]
    apply_rules(rules)
    roster = ROSTERS[size][roster_index]
    battle = make_battle(rules, roster)
    players = {"left": make_player(left_name, "left", difficulty, 1000 * seed + 1, rules),
               "right": make_player(right_name, "right", difficulty, 1000 * seed + 2, rules)}
    stats = {"left": new_side_stats(), "right": new_side_stats()}
    open_defense = {"left": None, "right": None}       # the side's Defend / Rally now in force
    battle.take_events()
    while not battle.is_over() and battle.round_number <= MAX_ROUNDS:
        side = battle.active_side
        enemy = other_side(side)
        open_defense[side] = None                        # our own Defend ended when our turn began
        target_team = battle.teams[enemy]
        before = {"side": enemy,
                  "characters": {c.name: {"hp": c.hp, "defense": c.defense, "defending": c.is_defending}
                                 for c in target_team.characters},
                  "guarded": battle.castle_guarded(enemy),
                  "blocks": [b.hp for b in battle.castles[enemy].blocks],
                  "own_castle_hp": battle.castles[side].total_hp()}
        atk_before = {c.name: c.atk for c in battle.teams[side].characters}   # before any level-up
        plan = players[side].take_turn(battle)
        if plan is None:                                 # can't happen on our turn; never loop forever
            stats[side]["invalid"] += 1
            break
        actor = battle.teams[side].characters[plan.actor_index]
        shooter_atk = atk_before[actor.name]
        kind = action_kind(actor, plan)
        if kind == "power_shot":
            shot = ShotDamage(Archer.POWER_SHOT_BLOCK_DAMAGE, Archer.POWER_SHOT_MULTIPLIER, True)
        else:
            shot = actor.attack_shot()
        events = fly(battle)

        stats[side][kind] += 1
        stats[side]["invalid"] += sum(1 for e in events if e["type"] == "invalid")
        stats[side]["safety_net"] += "safety net" in plan.reason
        if kind == "repair":
            stats[side]["repaired_hp"] += battle.castles[side].total_hp() - before["own_castle_hp"]
        if open_defense[enemy] is not None and plan.fires_a_shot():
            measure_defense(open_defense[enemy], before, battle, events, shooter_atk, shot, rules["guard"])
        open_defense[enemy] = None
        if plan.defensive:
            record = {"prevented_character": 0, "prevented_castle": 0,
                      "saved_character": False, "saved_castle": False}
            stats[side]["defenses"].append(record)
            open_defense[side] = record

    if battle.winner is None:
        result = "unfinished"
    elif battle.winner == "draw":
        result = "draw"
    else:
        loser = other_side(battle.winner)
        result = "elimination" if not battle.teams[loser].alive_characters() else "castle"
    return {"variant": variant, "difficulty": difficulty, "size": size,
            "roster": "/".join(role.__name__ for role in roster),
            "left": left_name, "right": right_name, "seed": seed,
            "winner": battle.winner, "result": result,
            "rounds": min(battle.round_number, MAX_ROUNDS), "stats": stats}


# ----- decision points: is the defensive action better than attacking right now? ---------------
#
# A match between two copies of the shipped AI is played until the side to move first
# reaches a decision point. The match is then copied: in one copy that side Defends /
# Rallies / Repairs, in the other it attacks (the AI's own attack choice). Both copies are
# played to the end by the same AIs with the same random state, so the only difference is
# that one action. Win rate (defensive action) − win rate (attack) = what the action is worth.

DECISIONS = {
    "defend_castle": "Defend / Rally when the castle could fall to one strong hit",
    "defend_hurt": "Defend / Rally when a character is below half HP",
    "repair": "Repair when the castle is missing at least one full Repair",
}


def at_decision_point(kind, battle, side, rules):
    team = battle.teams[side]
    if kind == "defend_castle":
        return rules["castle_loss"] and team.castle.hp_before_falling() <= THREAT_HP
    if kind == "defend_hurt":
        return any(c.hp * 2 < c.max_hp for c in team.alive_characters())
    engineer_ready = any(isinstance(c, Engineer) and battle.why_not_allowed(i, "special") is None
                         for i, c in enumerate(team.characters))
    repairable = sum(b.max_hp - b.hp for b in team.castle.alive_blocks())
    return engineer_ready and repairable >= Engineer.REPAIR_POOL


def play_to_end(battle, players):
    while not battle.is_over() and battle.round_number <= MAX_ROUNDS:
        if players[battle.active_side].take_turn(battle) is None:
            break
        fly(battle)
    return battle.winner


def decision_score(winner, side):
    if winner == side:
        return 1.0
    return 0.5 if winner in (None, "draw") else 0.0


def play_decision(job):
    variant, difficulty, size, roster_index, kind, seed = job
    rules = VARIANTS[variant]
    apply_rules(rules)
    battle = make_battle(rules, ROSTERS[size][roster_index])
    players = {"left": AIController("left", difficulty, 1000 * seed + 1),
               "right": AIController("right", difficulty, 1000 * seed + 2)}
    while not battle.is_over() and battle.round_number <= MAX_ROUNDS:
        side = battle.active_side
        if not players[side].defended_last_turn and at_decision_point(kind, battle, side, rules):
            break
        players[side].take_turn(battle)
        fly(battle)
    else:
        return None                                      # this match never reached the decision point
    scores = {}
    for choice in ("act", "attack"):
        trial, trial_players = copy.deepcopy((battle, players))
        ai = trial_players[side]
        if choice == "act":
            if kind == "repair":
                plan = ai.repair_plan(trial)
            else:
                plan = ai.defensive_plan(trial, use_specials=True)
        else:
            ai.repair_plan = lambda b: None              # this copy attacks: no Repair this turn
            plan = ai.attack_plan(trial, use_specials=True)        # includes the aiming error
            del ai.repair_plan
        if plan.fires_a_shot():
            cannon = trial.cannons[side]
            cannon.adjust_angle(plan.angle - cannon.angle)
            cannon.adjust_power(plan.power - cannon.power)
        trial.perform_action(plan.actor_index, plan.action)
        ai.defended_last_turn = plan.defensive
        fly(trial)
        scores[choice] = decision_score(play_to_end(trial, trial_players), side)
    return {"variant": variant, "difficulty": difficulty, "size": size, "kind": kind,
            "act": scores["act"], "attack": scores["attack"]}


def decision_jobs(variants, difficulties, kinds, samples_per_size):
    jobs = []
    for variant in variants:
        for difficulty in difficulties:
            for kind in kinds:
                if kind == "repair" and not VARIANTS[variant]["castle_loss"]:
                    continue
                if kind == "defend_castle" and not VARIANTS[variant]["castle_loss"]:
                    continue
                for size, rosters in ROSTERS.items():
                    usable = [i for i, r in enumerate(rosters) if kind != "repair" or Engineer in r]
                    per_roster = max(1, samples_per_size // len(usable))
                    for roster_index in usable:
                        for seed in range(per_roster):
                            jobs.append((variant, difficulty, size, roster_index, kind, seed))
    return jobs


def summarize_decisions(results, variants, difficulties, kinds):
    lines = ["## Decision points: the defensive action versus attacking at the same moment", "",
             "Each sample copies one match at a decision point and plays both choices to the end with "
             "the same AIs and random state. Value = win rate after the defensive action − win rate "
             "after attacking (positive = the defensive action was the better move). ± is a 95 % margin "
             "of error of the paired difference.", ""]
    for difficulty in difficulties:
        lines += [f"### {difficulty.capitalize()}", "",
                  "| Decision | Variant | samples | win rate if it acts | win rate if it attacks | value of acting "
                  "| acting changed the result: better / worse |",
                  "|---|---|---|---|---|---|---|"]
        for kind in kinds:
            for variant in variants:
                rs = [r for r in results if r and r["variant"] == variant and r["difficulty"] == difficulty
                      and r["kind"] == kind]
                if not rs:
                    continue
                n = len(rs)
                diffs = [r["act"] - r["attack"] for r in rs]
                mean = sum(diffs) / n
                sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / max(1, n - 1))
                lines.append(f"| {DECISIONS[kind]} | {VARIANTS[variant]['label']} | {n} | "
                             f"{100 * sum(r['act'] for r in rs) / n:.0f} % | "
                             f"{100 * sum(r['attack'] for r in rs) / n:.0f} % | "
                             f"{100 * mean:+.0f} pts ± {100 * 1.96 * sd / math.sqrt(n):.0f} | "
                             f"{100 * sum(d > 0 for d in diffs) / n:.0f} % / {100 * sum(d < 0 for d in diffs) / n:.0f} % |")
        lines.append("")
    return lines


# ----- summaries -------------------------------------------------------------------------------

def score_of(match, strategy):
    """1 if `strategy` won, 0.5 for a draw or an unfinished match, 0 if it lost."""
    side = "left" if match["left"] == strategy else "right"
    if match["winner"] == side:
        return 1.0
    if match["winner"] in (None, "draw"):
        return 0.5
    return 0.0


def first_mover_score(match):
    """For a mirror match: 1 if LEFT (which moves first) won, 0.5 for a draw or unfinished, else 0."""
    if match["winner"] == "left":
        return 1.0
    return 0.5 if match["winner"] in (None, "draw") else 0.0


def rate(scores):
    """'52 % ± 7 (n=144)': the mean score with a 95 % margin of error."""
    if not scores:
        return "–"
    n = len(scores)
    p = sum(scores) / n
    margin = 1.96 * math.sqrt(max(p * (1 - p), 0.0001) / n)
    return f"{100 * p:.0f} % ± {100 * margin:.0f} (n={n})"


def versus(matches, strategy):
    return [m for m in matches if {m["left"], m["right"]} == {strategy, "aggressive"}]


def mirror(matches, strategy):
    return [m for m in matches if m["left"] == m["right"] == strategy]


def side_stats(match, strategy):
    return [match["stats"][side] for side in ("left", "right") if match[side] == strategy]


def summarize(matches, variants, difficulties):
    if not matches:
        return []
    lines = ["## Strategies against each other", "",
             f"{len(matches)} matches, at most {MAX_ROUNDS} rounds each. Win rate = wins + ½ × (draws "
             "and unfinished), with a 95 % margin of error. Every match uses mirrored rosters.", ""]
    for difficulty in difficulties:
        lines += [f"## {difficulty.capitalize()}", "",
                  "### Win rate against the aggressive strategy (all team sizes)", "",
                  "| Variant | existing AI | defensive | repair-aware | first mover wins (mirrors) |",
                  "|---|---|---|---|---|"]
        for variant in variants:
            ms = [m for m in matches if m["variant"] == variant and m["difficulty"] == difficulty]
            mirrors = [m for m in ms if m["left"] == m["right"]]
            lines.append(f"| {VARIANTS[variant]['label']} | " + " | ".join(
                rate([score_of(m, s) for m in versus(ms, s)]) for s in VERSUS_AGGRESSIVE)
                + f" | {rate([first_mover_score(m) for m in mirrors])} |")
        lines += ["", "### By team size (win rate against aggressive)", "",
                  "| Variant | Size | existing AI | defensive | repair-aware |", "|---|---|---|---|---|"]
        for variant in variants:
            for size in ROSTERS:
                ms = [m for m in matches if m["variant"] == variant and m["difficulty"] == difficulty
                      and m["size"] == size]
                lines.append(f"| {VARIANTS[variant]['label']} | {size}v{size} | " + " | ".join(
                    rate([score_of(m, s) for m in versus(ms, s)]) for s in VERSUS_AGGRESSIVE) + " |")
        lines += ["", "### Match length and how matches end (existing AI vs existing AI)", "",
                  "| Variant | Size | mean rounds | castle | elimination | draw | unfinished |",
                  "|---|---|---|---|---|---|---|"]
        for variant in variants:
            for size in ROSTERS:
                ms = [m for m in mirror(matches, "existing") if m["variant"] == variant
                      and m["difficulty"] == difficulty and m["size"] == size]
                if not ms:
                    continue
                count = {r: sum(m["result"] == r for m in ms) for r in ("castle", "elimination", "draw", "unfinished")}
                lines.append(f"| {VARIANTS[variant]['label']} | {size}v{size} | "
                             f"{sum(m['rounds'] for m in ms) / len(ms):.1f} | "
                             + " | ".join(f"{count[r]}/{len(ms)}" for r in count) + " |")
        lines += ["", "### Defensive actions (Defend or Rally) by the defensive strategy", "",
                  "| Variant | actions | per action: character HP saved | castle HP saved | "
                  "prevented any damage | saved a character or the castle |", "|---|---|---|---|---|---|"]
        for variant in variants:
            records = [r for m in matches if m["variant"] == variant and m["difficulty"] == difficulty
                       for s in side_stats(m, "defensive") for r in s["defenses"]]
            if not records:
                lines.append(f"| {VARIANTS[variant]['label']} | 0 | – | – | – | – |")
                continue
            n = len(records)
            lines.append(f"| {VARIANTS[variant]['label']} | {n} | "
                         f"{sum(r['prevented_character'] for r in records) / n:.1f} | "
                         f"{sum(r['prevented_castle'] for r in records) / n:.1f} | "
                         f"{100 * sum(r['prevented_character'] + r['prevented_castle'] > 0 for r in records) / n:.0f} % | "
                         f"{100 * sum(r['saved_character'] or r['saved_castle'] for r in records) / n:.0f} % |")
        lines += ["", "### Action mix and Repair", "",
                  "| Variant | strategy | attack | power shot | defend | rally | repair | HP per repair |",
                  "|---|---|---|---|---|---|---|---|"]
        for variant in variants:
            for strategy in ("aggressive", "existing", "defensive", "repair"):
                sides = [s for m in matches if m["variant"] == variant and m["difficulty"] == difficulty
                         for s in side_stats(m, strategy)]
                total = sum(s[k] for s in sides for k in ("attack", "power_shot", "defend", "rally", "repair"))
                if not total:
                    continue
                repairs = sum(s["repair"] for s in sides)
                per_repair = f"{sum(s['repaired_hp'] for s in sides) / repairs:.0f}" if repairs else "–"
                lines.append(f"| {VARIANTS[variant]['label']} | {strategy} | " + " | ".join(
                    f"{100 * sum(s[k] for s in sides) / total:.0f} %"
                    for k in ("attack", "power_shot", "defend", "rally", "repair")) + f" | {per_repair} |")
        lines.append("")
    invalid = sum(s["invalid"] for m in matches for s in m["stats"].values())
    safety = sum(s["safety_net"] for m in matches for s in m["stats"].values())
    unfinished = sum(m["result"] == "unfinished" for m in matches)
    lines += ["## Legality and stalling", "",
              f"- Refused (\"invalid\") actions in all matches: {invalid}",
              f"- AI safety-net Defends in all matches: {safety}",
              f"- Unfinished matches (still going after {MAX_ROUNDS} rounds): {unfinished} of {len(matches)}", ""]
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="a small run to check that everything works")
    parser.add_argument("--experiments", default="strategies,decisions")
    parser.add_argument("--variants", default=",".join(VARIANTS))
    parser.add_argument("--difficulties", default="normal,hard")
    parser.add_argument("--decision-variants", default="A,B,C125,C150,D125,D150,E70,ELIM")
    parser.add_argument("--matches", type=int, default=48, help="matches per team size, per pairing")
    parser.add_argument("--samples", type=int, default=48, help="decision samples per team size")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--out", default=os.path.join(PROJECT, "docs", "M3.2_benchmark_results.md"))
    parser.add_argument("--json", help="also save every result as JSON here")
    args = parser.parse_args()
    experiments = args.experiments.split(",")
    variants = args.variants.split(",")
    decision_variants = args.decision_variants.split(",")
    difficulties = args.difficulties.split(",")
    per_size = 6 if args.quick else args.matches
    samples = 6 if args.quick else args.samples
    kinds = list(DECISIONS)

    start = time.time()
    matches, decisions = [], []
    with multiprocessing.Pool(args.workers) as pool:
        if "strategies" in experiments:
            jobs = make_jobs(variants, difficulties, per_size)
            print(f"strategies: {len(jobs)} matches on {args.workers} worker(s)...", flush=True)
            matches = pool.map(play_match, jobs, chunksize=4)
        if "decisions" in experiments:
            jobs = decision_jobs(decision_variants, difficulties, kinds, samples)
            print(f"decisions: {len(jobs)} samples...", flush=True)
            decisions = [r for r in pool.map(play_decision, jobs, chunksize=2) if r is not None]
    elapsed = time.time() - start
    print(f"done in {elapsed:.0f} s", flush=True)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"matches": matches, "decisions": decisions}, f)

    shown = []                                   # the command, without local file paths
    arguments = iter(sys.argv[1:])
    for argument in arguments:
        if argument in ("--out", "--json"):
            next(arguments, None)
        elif not argument.startswith(("--out=", "--json=")):
            shown.append(argument)
    command = " ".join(["python scripts/balance_benchmark.py"] + shown)
    lines = ["# M3.2 balance benchmark results", "",
             f"Generated by `{command}` in {elapsed / 60:.0f} minutes."
             " The method is explained in docs/M3.2_balance_report.md.",
             "", "Rule variants:", ""]
    lines += [f"- **{VARIANTS[v]['label']}**" for v in dict.fromkeys(variants + decision_variants)]
    lines.append("")
    lines += summarize(matches, variants, difficulties)
    if decisions:
        lines += summarize_decisions(decisions, decision_variants, difficulties, kinds)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"results written to {args.out}")


if __name__ == "__main__":
    main()
