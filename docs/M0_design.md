# Castle Siege — M0 Requirements and Architecture

Status: **Draft for project-manager review.** No game code has been written.
Milestone: M0 (design only). M1 starts only after this document is approved.

All numbers in this document are **initial tuning values**. They have been
sanity-checked with a throwaway script (see §12), but they will be tuned during
M1/M2 playtesting. Every constant lives in one named place in the code so it can
be changed without touching logic.

---

## 1. Game Design Document (concise)

### 1.1 Pitch
A 2D side-view artillery game. Two castles face each other across an open field.
Each team has 1–3 characters standing on the ground **behind** their own castle.
Every round, each side secretly picks **one** character and **one** action
(Attack, Defend, or Special). When both sides are ready, the actions resolve
**at the same time**: shots fly together, then explode.

### 1.2 How you win
A team **loses** at the end of a round if either:
- its castle is **≥ 60 % destroyed**, or
- **all** of its characters are defeated (HP 0).

If both teams lose in the same round, the match is a **Draw** (see §9, C2).
Safety net: the match ends after **round 30**; the team whose castle is less
destroyed wins, and equal destruction is a Draw.

### 1.3 Modes
- **M1:** Player (left castle) vs AI (right castle), AI difficulty Easy / Normal / Hard.
- **Later:** local Player vs Player on one computer, taking turns at the keyboard
  ("hot seat"). The battle code supports this already (§6).

### 1.4 The battlefield (1280 × 720 window, 60 FPS)
```
y=0    +--------------------------------------------------------------------------+
       | Round 4      LEFT CASTLE 23% destroyed       RIGHT CASTLE 41% destroyed  |  HUD
       |                                                                          |
       |                         (sky / background)                               |
y=400  |              ##                                   ##                     |
       |              ##                                   ##                     |
       |              ##                                   ##                     |
       |  K  A  E   ###                                     ###   K  A  E         |
y=560  |  ^units^  ######                                   ######  ^units^       |  ground
y=600  +--------------------------------------------------------------------------+
       | [1][2][3] actor  [Attack][Defend][Special 2]  Angle 45  Power 60 [READY] |  UI panel
       | Combat log (last 6 lines) ...                                            |
y=720  +--------------------------------------------------------------------------+
        x=50..140   x=200..392            no-man's land           x=888..1080  x=1140..1230
```
- Ground surface: `GROUND_Y = 560`. UI panel: y 600–720.
- Castles: left starts at x = 200, right starts at x = 888 (6 columns × 32 px = 192 px wide).
- Characters: 28 × 44 px rectangles. Left slot centres x = 50, 95, 140.
  Right slot centres x = 1140, 1185, 1230. Characters stand on the ground.
- The tall **front tower** faces the enemy and blocks almost all flat shots. The back wall is
  one block high, so lobbed shots (about 45° or steeper) can land on the characters.

### 1.5 Aiming
- Angle: 5°–80°, measured up from horizontal, always toward the enemy. Default 45°.
- Power: 10–100. Default 60. From the middle slot this lands just short of the
  enemy castle (x ≈ 865). From the outer slots it lands about 45 px shorter or
  longer, so the player always has to adjust.
- Controls: Up/Down = angle ±1°, Left/Right = power ±1, hold Shift for ±5.
- An aim arrow shows direction, and its length shows power. There is **no** full
  trajectory preview, because aiming is the skill in this game.

### 1.6 Goals / non-goals
- Goals: one readable, complete match loop; course OOP requirements met; logic
  testable without opening a window.
- Non-goals for this project: networking, campaign or map editor, terrain
  deformation, wind, structural collapse physics, sprite animation systems, save files.
- Anti-goals: architecture a CS5001 student can't explain line by line; external
  dependencies other than Pygame.

---

## 2. Gameplay state machine

### 2.1 Screen flow (in `main.py`)
```
TITLE ──► SETUP ──► TEAM_SELECT ──► BATTLE ──► RESULT ──► TITLE (or REMATCH ► TEAM_SELECT)
          (mode,      (P1 picks 1–3;
          difficulty)  AI picks the same count;
                       later: P2 picks)
```

### 2.2 Round flow (in `battle.py`, class `Battle`)
```
          ┌───────────────────────────────────────────────────────────┐
          ▼                                                           │
   ROUND_START ──► PLANNING ──(both plans submitted)──► RESOLVE_INSTANT
                                                              │
                                                              ▼
   RESULT ◄──(a team lost / round 30)── ROUND_END ◄──(all shots landed)── FLIGHT
```

| Phase | What happens (in this order) |
|---|---|
| **ROUND_START** | `round_number += 1`. Every character's special cooldown goes down by 1 (minimum 0). Every character's `is_defending` is cleared. Log "— Round N —". |
| **PLANNING** | Each side submits one `ActionPlan(actor, action, angle, power)`. The AI plans at the start of this phase and **never reads the other side's plan**. The human plans through the UI. The plans are hidden until both are submitted. Invalid plans are rejected (dead actor, special still cooling down, angle or power out of range). |
| **RESOLVE_INSTANT** | Both plans are revealed in the log. Instant effects are applied first, left side then right side (the order doesn't matter because they only touch the team that used them): **Defend** sets `is_defending` on the actor. **Knight Rally** sets `is_defending` on every living ally. **Engineer Repair** repairs the castle. Specials start their cooldowns here. Then **both projectiles are launched** (Attack, or Archer Power Shot). |
| **FLIGHT** | Each frame, every flying projectile advances the same number of fixed physics steps. When a projectile collides, it **explodes immediately** and its damage is applied right away (§4.4). A character killed mid-flight can't be hit again, but a shot it already fired keeps flying, because both shots were launched together. FLIGHT ends when no projectile is still flying. |
| **ROUND_END** | Award EXP to the actor if it is still alive, and process level-ups. Check loss conditions for **both** teams at the same time: neither has lost → ROUND_START; one has lost → the other wins; both have lost → Draw; round 30 reached → tie-break (§1.2). |

PvP adds **no battle phases**. Its hot-seat steps happen only in the UI, inside
PLANNING: `PLAN_LEFT → HANDOVER ("Player 2, press Space") → PLAN_RIGHT`.

---

## 3. Characters

### 3.1 Attributes (every character)
| Attribute | Meaning |
|---|---|
| `name`, `side` | display name; `"left"` or `"right"` |
| `max_hp`, `hp` | health; the character is defeated when `hp == 0` |
| `atk` | base damage |
| `defense` | subtracted from incoming character damage (named `defense` because `def` is a Python keyword) |
| `level`, `exp` | start at Level 1 with 0 EXP; maximum level 5 |
| `is_defending` | True only during the round it was set |
| `special_cooldown` | rounds left until the special can be used again; 0 = ready |
| `x` | slot centre position (set from the slot index) |

Class-level constants (overridden per archetype): `BASE_HP`, `BASE_ATK`,
`BASE_DEF`, `BLOCK_DAMAGE_MULT`, `SPECIAL_NAME`, `SPECIAL_COOLDOWN`,
`SPECIAL_FIRES_SHOT`, `SPECIAL_DAMAGE_MULT`, `SPECIAL_IGNORES_DEF`.

### 3.2 The three archetypes
| | **Knight** (tank) | **Archer** (damage) | **Engineer** (siege) |
|---|---|---|---|
| HP | 140 | 90 | 110 |
| ATK | 30 | 40 | 34 |
| DEF | 12 | 4 | 8 |
| Block damage multiplier | 1.0 | 0.75 (arrows are weak against stone) | 1.5 |
| Special | **Rally**: every living ally Defends this round. Does not fire. | **Power Shot**: an aimed shot with ×1.5 damage that ignores DEF | **Repair**: every surviving castle block regains 25 HP (up to its maximum). Destroyed blocks stay destroyed. Does not fire. |
| Special cooldown | 4 | 3 | 4 |
| Special needs aim? | no | yes | no |

**Cooldown rule:** a special used in round *r* can be used again in round
*r + cooldown*. (Using it sets `special_cooldown = SPECIAL_COOLDOWN`, and
ROUND_START lowers it by 1 each round.) Every special starts ready.

**Team selection:** a team picks 1–3 **different** archetypes. Duplicates are
not allowed in M1 (see §9, A3).

### 3.3 EXP and levels
Only the character that acted this round earns EXP, and only if it is **still
alive at ROUND_END**. A defeated character earns no EXP and can never be
revived by a level-up.
- +5 for taking any action
- +10 more if its projectile damaged at least one enemy block or character
- +20 more for each enemy character its projectile defeated

`EXP to next level = 40 × current level` (40 to reach Level 2, then 80, 120, 160).
Leftover EXP carries over. Each level-up gives: `max_hp +10` and `hp +10`,
`atk +3`, `defense +1`. EXP and levels last for **one match only** in M1.

---

## 4. Rules and calculations

All arithmetic produces integers by truncating with `int()` (no `round()`,
because Python's `round()` uses banker's rounding and would surprise students).

### 4.1 Damage to a character (one explosion)
```
raw        = int(attacker.atk * shot_multiplier)          # 1.0 for Attack, 1.5 for Power Shot
after_def  = raw if ignores_def else raw - target.defense
after_def  = max(1, after_def)                             # minimum 1 damage
final      = max(1, after_def // 2) if target.is_defending else after_def
target.hp  = max(0, target.hp - final)
```
Examples (Level 1):
- Archer Attack → Knight: 40 − 12 = **28**. If the Knight is defending: **14**.
- Archer Power Shot → Knight: int(40 × 1.5) = 60 (DEF ignored) = **60**. Defending: **30**.
- Knight Attack → Archer: 30 − 4 = **26**.

### 4.2 Defend
- **Defend** (any character): the acting character takes 50 % damage (§4.1) for
  this round. The character does not attack.
- **Rally** (Knight special): every living ally on the team is defending this round.
- Defend **does not reduce castle damage** (see §9, A2).

### 4.3 Damage to castle blocks (one explosion)
```
block_damage = int(attacker.atk * shot_multiplier * attacker.BLOCK_DAMAGE_MULT)
```
Blocks have no DEF and cannot defend. Level 1 values: Knight 30, Archer 30,
Engineer 51. Archer Power Shot: int(40 × 1.5 × 0.75) = 45.

### 4.4 Explosions (one rule for everything)
When a projectile enters an enemy character's rectangle or an enemy block's
rectangle, or reaches the ground, it **explodes** at that point. All three
cases use the same rule. At the impact point:
- every **enemy** character whose centre is within **50 px** takes character damage (§4.1)
- every **enemy** block whose centre is within **50 px** takes block damage (§4.3)

There is **no friendly fire.** A projectile passes through its own team's castle
and characters. A shot that leaves the screen sideways (no explosion), or is still flying after
600 steps (10 s), is a miss. Shots may go above the top of the screen (y < 0) and
come back down. The UI draws a small marker at the top edge while a shot is out of view.

A typical hit on a castle face damages **3–4 blocks** (checked in §12).

### 4.5 Castle and destruction
- Block: 32 × 32 px, **100 HP**. A block with 0 HP is destroyed: it disappears
  and stops blocking shots.
- Template for the left castle (top row first; `#` = block). The right castle
  uses each row reversed, so its tower faces left:
  ```
  ....##
  ....##
  ....##
  ...###
  ######
  ```
  This gives 15 blocks, 1500 HP in total. Front tower height = 160 px. Back wall height = 32 px.
- `destruction % = 100 × (1 − current total block HP / max total block HP)`.
  This counts damage, not destroyed blocks, so every hit moves the bar.
- **Loss at ≥ 60 %**, which is 900 HP of damage. At Level 1 that's about 8–10
  Knight hits (90–120 damage each) or 5–6 Engineer hits.
- Blocks do **not** fall when the block below them is destroyed. This is an
  accepted simplification (§9, R4).

### 4.6 Projectile physics (shared by the game, the AI and the tests)
```
GRAVITY         = 400 px/s²  (screen y points down)
SPEED_PER_POWER = 9          (power 10–100 → 90–900 px/s)
DT              = 1/60 s per physics step, fixed (deterministic)
MAX_STEPS       = 600
launch point    = top centre of the acting character
vx = direction * speed * cos(angle)   (direction +1 for left team, -1 for right)
vy = -speed * sin(angle)
each step:  vy += GRAVITY*DT ;  x += vx*DT ;  y += vy*DT ;  then check collisions
```
`SIM_STEPS_PER_FRAME = 1`. Typical flights take 1.5–3 s on screen. If that feels
slow, set it to 2.

### 4.7 Round-limit tie-break
At the end of round 30, if nobody has lost: lower castle destruction % wins, and
equal destruction is a Draw.

---

## 5. Class structure

Five modules. Only `main.py` imports Pygame. The other four use only the
standard library (`math`, `random`), so they can be tested without a window.
Each module keeps its own constants at the top, so there is no sixth config module.

```
main.py ──imports──► battle.py, ai.py, characters.py, castle.py
ai.py   ──imports──► battle.py (Projectile simulation, ActionPlan)
battle.py ─imports─► characters.py, castle.py
characters.py, castle.py ── import nothing from the project
```

### `characters.py`
| Class / function | Responsibility |
|---|---|
| `calculate_damage(atk, multiplier, defense, ignores_def, defending)` | Pure function implementing §4.1. Easy to unit test. |
| `Character` (base) | Holds the attributes in §3.1. Methods: `is_alive()`, `hp_ratio()`, `take_hit(attacker, multiplier, ignores_def) -> int`, `block_damage(multiplier) -> int`, `defend()`, `special_ready()`, `start_cooldown()`, `tick_cooldown()`, `gain_exp(amount) -> bool (levelled up)`, and `use_special(team) -> str` (the base version raises `NotImplementedError`). |
| `Knight(Character)` | Archetype constants. Overrides `use_special`: calls `defend()` on all living allies. |
| `Archer(Character)` | Archetype constants (`SPECIAL_FIRES_SHOT = True`, ×1.5, ignores DEF). Overrides `use_special`: returns a log line. The battle launches the shot. |
| `Engineer(Character)` | Archetype constants. Overrides `use_special`: calls `team.castle.repair(25)`. |
| `ARCHETYPES = [Knight, Archer, Engineer]` | Used by the selection screen and the AI. |

This inheritance does real work: the base class holds all shared rules, and the
three overrides of `use_special` behave differently, called through one
polymorphic call in `Battle`.

### `castle.py`
| Class | Responsibility |
|---|---|
| `Block` | `x, y, size, max_hp, hp`. Methods: `is_destroyed()`, `center()`, `contains(px, py)`, `take_damage(n) -> int` (actual damage dealt, capped at remaining HP). |
| `Castle` | `side`, `blocks`, built from `TEMPLATE` (mirrored for the right side). Methods: `alive_blocks()`, `block_at(px, py)`, `apply_blast(px, py, radius, damage) -> (blocks_hit, total_damage)`, `repair(amount) -> total_repaired`, `destruction_percent() -> float`, `is_destroyed() -> bool` (≥ 60 %). |

### `battle.py`
| Class | Responsibility |
|---|---|
| `ActionPlan` | Small plain class: `actor_index, action ("attack"/"defend"/"special"), angle, power`. |
| `Team` | `side, characters, castle, ai` (`None` means a human controls it). Methods: `alive_characters()`, `has_lost()`, `direction()` (+1 or −1). |
| `Projectile` | `x, y, vx, vy, owner, side, multiplier, ignores_def, flying, steps`. Method `step()` = one physics step (§4.6). |
| `Battle` | Owns `teams {"left","right"}`, `round_number`, `phase`, `plans`, `projectiles`, `log`, `winner`. Methods: `start_round()`, `submit_plan(side, plan) -> bool`, `both_ready()`, `begin_resolution()` (RESOLVE_INSTANT + launch), `update()` (one physics step for every flying projectile; when none are left, calls `end_round()`), `end_round()`, `simulate_impact(actor, angle, power) -> (x, y)` (a side-effect-free preview used by Hard AI and tests), `resolve_round_instantly()` (test helper: runs `update()` until the round is over). |

### `ai.py`
| Item | Responsibility |
|---|---|
| `DIFFICULTY` table | All AI numbers (§6.3). |
| `aim_power(dx, dy_up, angle) -> power or None` | Closed-form projectile formula: `v² = g·dx² / (2·cos²θ·(dx·tanθ − dy_up))`, `power = v / 9`. |
| `AIController` | `__init__(difficulty, rng)`, `choose_team(size) -> list[Character]`, `choose_plan(battle, side) -> ActionPlan`. Reads team state only. **Never** reads `battle.plans`. |

### `main.py`
| Item | Responsibility |
|---|---|
| `Button` | Rectangle, label, enabled flag, `draw()`, `is_clicked(pos)`. |
| `Game` | `state` string (TITLE / SETUP / TEAM_SELECT / BATTLE / RESULT, plus HANDOVER later). Has one `handle_event / update / draw` method group per state, the human aiming input, all drawing (background, castles, characters, HP bars, aim arrow, projectiles, HUD, buttons, combat log, result screen), and sounds. |
| `main()` | Pygame init and the main loop: `events → update → draw → clock.tick(60)`. |

---

## 6. Player vs AI now, local PvP later

### 6.1 One rule: the battle doesn't know who is playing
`Battle` only ever receives `ActionPlan`s through `submit_plan(side, plan)`.
Each `Team` has an `ai` field:
- `team.ai` is an `AIController` → at PLANNING start, `main.py` calls
  `battle.submit_plan(side, team.ai.choose_plan(battle, side))`.
- `team.ai is None` → `main.py` collects that side's plan from keyboard and mouse.

### 6.2 What PvP needs later (UI only, no battle changes)
1. A SETUP option: "vs AI" / "2 Players".
2. TEAM_SELECT for Player 2.
3. A HANDOVER cover screen between `PLAN_LEFT` and `PLAN_RIGHT`, so Player 2
   can't see Player 1's aim. The right-side angle mirrors automatically, so the
   controls are the same for both players.

AI-vs-AI is the same code with both `ai` fields set. The tests use it to play
whole matches without a window, which also shows that the battle code is fully
symmetric.

### 6.3 AI behaviour (explicit numbers)
| Parameter | Easy | Normal | Hard |
|---|---|---|---|
| Angle noise (uniform ±) | 8° | 4° | 1° |
| Power noise (uniform ±) | 10 | 5 | 2 |
| Defend chance when its weakest character is below 50 % HP | 50 % | 70 % | 85 % |
| Chance to use a ready special when it's useful | 30 % | 70 % | 100 % |
| Base angle | random 35–65 | random 40–60 | first of [45, 55, 60, 50, 40] whose simulated impact lands within 25 px of the target |
| Checks the shot with `simulate_impact` | no | no | yes (up to 5 tries) |
| Actor choice when attacking | random living character | best for the target (highest block damage vs castle, highest ATK vs characters) | same as Normal |
| Target choice | castle 70 %, random enemy 30 % | an enemy it can kill this shot; else castle 60 % / lowest-HP enemy 40 % | an enemy it can kill this shot; else castle if the enemy castle is ≥ 40 % destroyed; else lowest-HP enemy |

**Decision order** (all difficulties):
1. **Defensive preference.** If the AI's weakest living character is below
   50 % HP, then with probability *Defend chance*: use a ready Knight's Rally if
   two or more allies are below 50 % (Hard also uses it for just one); otherwise
   the weakest character Defends.
2. **Repair.** If its castle is ≥ 30 % destroyed and a living Engineer's Repair
   is ready, use it (with probability *special chance*).
3. **Attack.** Pick the target, then the actor, then the angle. Compute power
   with `aim_power`, add noise, and clamp to the legal ranges. A ready Archer
   uses Power Shot (with probability *special chance*).

Throwaway Monte Carlo estimates of hit rates (§12):

| | Easy | Normal | Hard |
|---|---|---|---|
| Hit the castle | ~51 % | ~87 % | ~100 % |
| Hit a character behind the castle | ~17 % | ~32 % | ~74 % |

---

## 7. Minimal file structure
```
pygame-castle_campaign/
├── main.py              # Pygame loop, screens, input, drawing, sound
├── characters.py        # Character, Knight, Archer, Engineer, calculate_damage
├── castle.py            # Block, Castle
├── battle.py            # ActionPlan, Team, Projectile, Battle
├── ai.py                # AIController, aim_power, DIFFICULTY
├── assets/
│   ├── sounds/          # M2: short CC0 or self-made .wav files (+ CREDITS.md)
│   └── images/          # optional background image (M2)
├── tests/
│   ├── test_characters.py
│   ├── test_castle.py
│   ├── test_battle.py
│   └── test_ai.py
├── docs/
│   └── M0_design.md     # this file
├── README.md            # how to install, run, play and test (M1)
└── requirements.txt     # pygame (pinned version)
```
Tests use the standard-library `unittest`: `python -m unittest discover tests`.
pytest isn't required, but it can run these tests too.

---

## 8. Requirement → implementation mapping

| Course / project requirement | Where | Milestone | Verified by |
|---|---|---|---|
| Attack action | `ActionPlan("attack")`, `Battle.begin_resolution`, `Projectile` | M1 | test_battle |
| Defend −50 % damage | `calculate_damage(... defending)`, `Character.defend` | M1 | test_characters (exact halving and min 1) |
| Special ability + cooldown | `use_special` overrides, `start_cooldown/tick_cooldown` | M1 | test_characters (cooldown timing), test_battle |
| HP, ATK, DEF, EXP, Level | `Character` attributes, `gain_exp` | M1 | test_characters (level-up thresholds and stat gains) |
| Character selection | `TEAM_SELECT` screen, `ARCHETYPES`, `AIController.choose_team` | M1 | manual checklist |
| Enemy AI, defensive below 50 % HP | `AIController.choose_plan` step 1 | M1 | test_ai (seeded RNG) |
| AI difficulty Easy/Normal/Hard | `ai.DIFFICULTY` | M1 | test_ai, AI-vs-AI test |
| HP bars | `Game.draw_battle` | M1 | manual |
| Action buttons | `Button`, battle UI panel | M1 | manual |
| Combat log | `Battle.log` list, drawn in the UI panel (last 6 lines) | M1 | test_battle (log entries), manual |
| Win / lose screen | `RESULT` state (+ Draw) | M1 | manual |
| OOP with meaningful inheritance | `Character` → `Knight/Archer/Engineer` | M1 | code review |
| Simultaneous action resolution | `Battle` PLANNING → RESOLVE_INSTANT → FLIGHT | M1 | test_battle (mutual kill gives a Draw) |
| Projectile angle / power / gravity | `Projectile.step`, §4.6 | M1 | test_battle (determinism, known landing range) |
| Castle damage / 60 % destruction win | `Castle.apply_blast`, `destruction_percent`, `Team.has_lost` | M1 | test_castle, test_battle |
| Elimination win | `Team.has_lost` | M1 | test_battle |
| Background | drawn sky/ground in M1; optional image in M2 | M1/M2 | manual |
| Basic sound effects | fire / explosion / victory sounds | M2 | manual (silent fallback if mixer fails) |
| Local PvP | HANDOVER screen + P2 team select | M3 | manual |
| Testing | `tests/` with unittest | M1+ | `python -m unittest` |
| Documentation | README, docstrings, this document | M1+ | review |

---

## 9. Ambiguities, contradictions and risks

### 9.1 Conflicts with the course specification (need PM / instructor confirmation)
- **C1 — Alternating turns vs simultaneous resolution.** The course describes
  players acting one after another. We resolve both actions together.
  **This is a direct conflict.** Argument for compliance: each round still has
  exactly one action per side, and the log shows them in a fixed order.
  Fallback if it's rejected: resolve the left plan fully, then ask for and
  resolve the right plan. That's small, because RESOLVE_INSTANT and FLIGHT
  already work for a single plan. We don't propose building both modes.
- **C2 — Elimination victory vs castle destruction.** The course expects a win
  by defeating all enemies. We keep elimination and **add** the 60 % castle
  condition, so a match can end with enemies still alive. Simultaneous
  resolution also allows a **Draw** (both teams lose in the same round), and the
  round-30 limit adds a third ending. The course mentions only win/lose screens.
- **C3 — Attacks can miss.** The course likely assumes Attack always deals
  damage. With aiming, an Attack may deal 0 damage. This is intended (it's what
  makes artillery fun), but the instructor should know.
- **C4 — "Enemy AI defends below 50 % HP" with a team of characters.** "HP" is
  ambiguous when there are several characters. We use the **weakest living AI
  character**, and the defence is probabilistic (50 / 70 / 85 %), not
  guaranteed. If the grader expects it always, set Defend chance to 100 %.
- **C5 — "Defend reduces incoming damage by 50 %."** We apply this to the
  defending character only, after DEF, with a minimum of 1. Castle damage is
  not reduced.

### 9.2 Design ambiguities (our proposed answer; the PM may override)
- **A1 — Why pick fewer than 3 characters?** In this design it's strictly
  weaker: fewer HP to lose and fewer options. Proposal: allow 1–3 as the course
  says, and have the AI match the player's team size. No compensation bonus.
- **A2 — Does Defend protect the castle?** Proposal: no. Otherwise turtling
  would stall the castle win condition.
- **A3 — Duplicate archetypes in a team?** Proposal: not allowed. This keeps
  names and the UI simple, and with 3 archetypes it's a subset choice.
- **A4 — The same character may act every round.** Players will mostly use
  their best character, and the others act as extra HP. Optional fix (not in
  M1): a character can't act two rounds in a row. PM decision.
- **A5 — EXP and levels across matches.** The repository name says
  "campaign", but no campaign is specified. Proposal: EXP and levels reset each
  match in M1; carrying them over is a later decision.
- **A6 — Sound and image assets.** Proposal: shapes drawn in code for M1. In
  M2, short sounds generated with the standard library or CC0 files listed in
  `assets/CREDITS.md`. No unlicensed assets.

### 9.3 Open questions only the PM / instructor can answer
- **Q1 — Course rubric and due dates.** This design paraphrases the course
  requirements. Please confirm the §8 mapping against the actual rubric
  (for example: is a written report required? save files?). Please also give
  the milestone due dates, which decide what M1 can drop if time is short.
- **Q2 — Graders' Python version and OS.** This decides the pinned Pygame
  version and the install instructions.
- **Q3 — Decisions on C1–C5 and A1–A6 above.** C1 (simultaneous turns) and C2
  (castle win and Draw) matter most. If either is rejected, the battle phases,
  when the AI plans, and the victory tests all change.

### 9.4 Implementation risks
- **R1 — Physics tunnelling.** Fast shots could skip through a 28 px
  character. At ≤ 900 px/s and 60 steps/s a shot moves ≤ 15 px per step, which
  is safe for 28–32 px targets. Keep `SPEED_PER_POWER × 100 / 60 < 28`.
- **R2 — Hard AI too strong.** It hits the castle ~100 % of the time. That's
  acceptable for "Hard", but if it isn't fun, raise its noise to ±2°/±3.
- **R3 — `main.py` grows too large.** UI code tends to sprawl. If `main.py`
  passes about 600 lines, split the drawing helpers into `ui.py` (a justified
  6th module).
- **R4 — Floating blocks.** Without collapse physics, blocks can float above
  destroyed blocks. This is documented as an accepted simplification.
- **R5 — Pygame availability.** Pygame isn't installed in this design
  environment. The M1 README must pin a version (e.g. `pygame==2.6.1`) and the
  logic tests must not import Pygame. We need the graders' Python version and
  OS (Q2) to pick a version that has a ready-made wheel for them.
- **R6 — Hot-seat fairness (PvP).** The HANDOVER screen must hide Player 1's
  angle and power. That's UI-only work.
- **R7 — Balance.** All numbers are first guesses. Target: an average PvAI
  Normal match lasts 8–15 rounds. Tune constants, not code.

---

## 10. M1 plan — playable vertical slice

**Scope:** one complete PvAI match. TITLE → SETUP (difficulty) → TEAM_SELECT
(1–3 archetypes) → BATTLE (all 3 actions, all 3 specials, castle damage,
EXP/levels, HP bars, buttons, combat log) → RESULT (Win/Lose/Draw, Play again).
Everything is drawn with simple shapes; no sound.

**Out of M1:** PvP, sound, image assets, the off-screen shot marker (if time is
short), the A4 rotation rule, and balance polish.

Order (test-first for the logic modules):
1. Skeleton: the five empty modules, `tests/`, `requirements.txt`, and a README with run/test commands.
2. `characters.py` + `test_characters.py`: damage formula (including defend and minimum 1), cooldown timing, level-up.
3. `castle.py` + `test_castle.py`: template build and mirroring, blast radius, destruction %, repair cap.
4. `battle.py` + `test_battle.py`: physics determinism; a known shot lands in a known x-range; simultaneous round with a mutual kill giving a Draw; castle-60 % and elimination wins; invalid plans rejected; round-30 tie-break.
5. `ai.py` + `test_ai.py`: `aim_power` accuracy (simulated impact within 25 px); defensive preference with a seeded RNG; the AI never reads opponent plans; with fixed seeds, AI-vs-AI matches on every difficulty end by castle
   destruction or elimination **before** the round-30 cap. ("Ends within 30
   rounds" can't fail because of the cap, so it isn't the test.)
6. `main.py`: screens, aiming input, flight animation, HUD, log, result screen.
7. Manual playtest checklist (in the README) and first tuning pass.

**M1 is done when:** `python main.py` plays a full PvAI match to the result
screen on all three difficulties, and `python -m unittest discover tests` passes.

Rough size: characters ~150 lines, castle ~100, battle ~250, ai ~150, main ~450–550.

**Later milestones (for context only):**
- M2: sound, background art, polish, tuning.
- M3: local PvP hot-seat.
- M4: final documentation and report.

---

## 11. Approaches considered

| Decision | Options | Chosen and why |
|---|---|---|
| Simultaneous resolution | (a) both shots fly at once and each explodes when it lands; (b) reveal both, then animate left then right; (c) real-time | **(a).** It's the most faithful to "resolve together". Because each shot only damages the other team, the result doesn't depend on order. (b) looks sequential, and (c) breaks turn-based play. |
| Where characters stand | on top of the castle; in front of it; on the ground behind it | **Behind.** The castle acts as a shield (flat shots hit stone, lobs hit characters), so there are two real tactical targets, and no "falling characters" physics is needed. |
| Hit detection | direct hits only; one uniform blast radius | **Uniform 50 px blast.** One rule covers characters and blocks. Direct-hit-only made characters nearly impossible to hit and castles slow to break. |
| Destruction measure | count destroyed blocks; HP-based % | **HP-based.** Every hit visibly moves the bar, and it's one formula. |
| Cooldown counting | "next usable round" number; a ticking counter | **Ticking counter, ticked only at ROUND_START.** It's familiar to students and ticks in one place, so there are no off-by-one special cases. |
| AI aiming | brute-force search; closed-form formula + noise | **Formula + noise**, with Hard checking up to 5 angles by simulation. It's fast and easy to explain. |
| Constants location | a `config.py`; constants at the top of each module | **Per module.** This keeps us at five modules, and each number sits next to the code that uses it. |

---

## 12. Process log (M0)

- **Start:** 2026-11-19T04:22:11Z. **End:** 2026-11-19T04:35:04Z.
- **Independent review:** a fresh reviewer agent read this document as a builder
  would and re-ran the physics. Fixed from its report:
  - a level-up could revive a dead character (now: defeated characters earn no EXP)
  - direct character hits weren't covered by the explosion rule
  - the default-shot landing point depends on the slot
  - "8–9 hits" corrected to "8–10"
  - small drift in the §12 figures
  - an AI-vs-AI test that could never fail
  Its open questions are now Q1–Q3 in §9.3.
- **Files created:** `docs/M0_design.md` (this file). No game code.
- **Checks performed (throwaway, not committed):** a ~60-line Python script
  simulated the §4.6 physics against the §4.5 castle layout. Results:
  - Default 45°/power 60 lands at x ≈ 865, just short of the enemy castle (x = 888).
  - 30° shots at the characters hit the front tower in almost all cases, so the
    shield works. (A second check found one narrow power band, about 79–82,
    that still reaches a character.)
  - 45–60° lobs reach every character slot with power of about 69–82. Peak height stays on screen (y ≥ 35) for angles up to 60°.
  - Closed-form aim lands within about 7–19 px of the target under the Euler
    simulation, well inside the 50 px blast radius.
  - Blasts on the castle face hit 3–4 blocks.
  - Flights last 88–187 frames.
  - A 400-sample Monte Carlo per difficulty gave the hit rates in §6.3.
- **No unit tests yet:** there is no code to test in M0.
