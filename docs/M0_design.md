# Castle Siege — M0 Requirements and Architecture

Status: **Revision 2 — draft for project-manager review.** No game code has been written.
Milestone: M0 (design only). M1 starts only after the PM approves this document.

Revision 2 updates Revision 1 (commit `2b865e8`). It follows PM feedback and a technical review
of the Rebound reference project (`docs/Rebound_reference_review.md`). The core concept is
unchanged. What changed:

| # | Change | Why |
|---|---|---|
| 1 | M1 is now only an artillery and destructible-castle prototype: no characters, AI, skills or EXP | PM request: get physics and castle damage right first |
| 2 | One fixed cannon per side, on top of the front tower. From M2 the acting character "operates" it | PM request. One launch point per side also removes slot-dependent aiming and simplifies the AI |
| 3 | `SPEED_PER_POWER` 9 → 7; default power 60 → 50 | The cannon is higher and closer than the old launch points. With 9, the castle can be hit at 30°–60° only within 10–13 power values; with 7, within 13–18 (§1.5, §14) |
| 4 | Engineer Repair capped: at most 75 HP (5 % of the castle) per use, damaged surviving blocks only | The old rule could restore 375 HP (25 % of the castle) per use |
| 5 | Alternating-turn mode specified as a one-constant switch (`TURN_MODE`) | The course specifies alternating turns (§10, C1) |
| 6 | Defend now lasts "until the team's next turn" | Same as "this round" in simultaneous mode, and it also works in alternating mode |
| 7 | Round-30 tie-break checks living characters, then their total HP, then castle % | Closer to the course's elimination victory |
| 8 | EXP: misses and basic Defend earn 0; Rally and an effective Repair earn +5; threshold `30 × level` | Rewards hits, not repeated defending; a level-up becomes visible in a normal match |
| 9 | AI aim noise retuned | The old table hit characters ~98 % of the time on Hard from the fixed cannon |
| 10 | Modules are created only when a milestone needs them; `Battle.events` list feeds the UI | PM request; the event list (a Rebound pattern) keeps game logic free of pygame |
| 11 | New: CS5001 rubric alignment (§8), requirement→milestone map (§9), roadmap M1–M5 (§11) | PM request |
| 12 | Rules tightened after an independent review: a per-team turn start, cannons that don't reveal hidden aim, AI edge cases, EXP edge cases, the round limit listed as its own deviation (C7) | Removes ambiguities a builder would otherwise have to guess |

All numbers are **initial tuning values**. They were sanity-checked with a throwaway script
(§14) and will change during playtesting. Every constant lives in one named place in the code,
so it can be changed without touching logic.

---

## 1. Game design (concise)

### 1.1 Pitch
A 2D side-view artillery game. Two castles face each other across an open field. Each castle
has **one cannon** on top of its front tower. Behind each castle stand 1–3 characters (Knight,
Archer, Engineer). Every round, each side secretly picks **one** character and **one** action
(Attack, Defend or Special). When both sides are ready, the actions resolve **at the same time**:
the cannons fire together, the shots fly, then they explode.

The acting character *operates* its team's cannon: the character's stats decide the damage.
The cannon itself is scenery. It cannot be damaged.

### 1.2 How you win
A team **loses** at the end of a round if either:
- its castle is **≥ 60 % destroyed**, or
- **all** of its characters are defeated (HP 0).

If both teams lose in the same round, the match is a **Draw**. Safety net: after **round 30**
(`ROUND_LIMIT`) the tie-break in §4.7 decides. Simultaneous turns, the castle loss, the Draw and
the round limit all differ from the course specification and need instructor approval (§10: C1,
C2, C7). §2.3 gives switches for alternating turns and for elimination-only victory. The round
limit stays in every mode, because it guarantees that a match ends.

### 1.3 Modes, by milestone
- **M1 prototype:** one keyboard controls both cannons, and shots alternate left, right, left…
  No characters.
- **M2:** full combat rules. Both sides are planned from one keyboard. This is a testing
  harness, not a final mode.
- **M3:** Player vs AI (Easy / Normal / Hard), and local Player vs Player ("hot seat", with a
  cover screen so Player 2 can't see Player 1's plan).

### 1.4 The battlefield (1280 × 720 window, 60 FPS)
```
y=0    +--------------------------------------------------------------------------+
       | Round 4      LEFT CASTLE 23% destroyed       RIGHT CASTLE 41% destroyed  |  HUD
       |                                                                          |
y=390  |                C                                    C                    |  cannons
y=400  |               ##                                   ##                    |
       |               ##                                   ##                    |
       |               ##                                   ##                    |
       |  K  A  E     ###                                   ###     K  A  E       |
y=560  |  ^units^  ######                                   ######   ^units^      |  ground
y=600  +--------------------------------------------------------------------------+
       | [1][2][3] actor  [Attack][Defend][Special 2]  Angle 45  Power 50 [READY] |  UI panel (M2+)
       | Combat log (last 6 lines) ...                                            |
y=720  +--------------------------------------------------------------------------+
        x=50..140   x=200..392            no-man's land           x=888..1080  x=1140..1230
```
- Ground surface `GROUND_Y = 560`. UI panel y 600–720 from M2. M1 uses one HUD line at the top.
- Castles: left x = 200..392, right x = 888..1080 (6 columns × 32 px).
- **Cannons:** pivot at left (360, 390) and right (920, 390), centred on top of each front
  tower. The barrel is drawn 24 px long; shots start at the pivot. A cannon cannot be hit, and it
  stays in place even if the blocks under it are destroyed (accepted simplification, R4).
- Characters (from M2): 28 × 44 px rectangles standing on the ground. Left slot centres
  x = 50, 95, 140; right slot centres x = 1140, 1185, 1230.
- The tall front tower faces the enemy and stops most low shots. The back wall is one block high,
  so lobbed shots can land on the characters.

### 1.5 Aiming
- Angle 5°–80°, measured up from horizontal, always toward the enemy. Default 45°.
- Power 10–100. Default **50**. The default shot lands at x ≈ 785, about 100 px short of the
  enemy castle (x = 888), so the player always has to adjust.
- Checked shot windows (§14):
  - To hit the castle: about power 58–70 at 45°, 57–74 at 30°, and 75–100 for flat 5° shots.
  - To hit the characters: lobs of 45°–60° with power about 72–87 (the farther slot needs more).
- Controls: Up/Down = angle ±1°, Left/Right = power ±1, hold Shift for ±5. Space = Fire (M1)
  or READY (M2+).
- An aim arrow shows direction, and its length shows power. There is **no** trajectory preview,
  because aiming is the skill in this game.

### 1.6 Goals, non-goals, anti-goals
- **Goals:** one readable, complete match loop; the course's OOP requirements met; game logic
  testable without opening a window.
- **Non-goals:** networking, campaign or map editor, terrain deformation, wind, structural
  collapse physics, sprite animation systems, save files, power-ups, bouncing projectiles,
  neural-network AI.
- **Anti-goals:** architecture a CS5001 student can't explain line by line; external
  dependencies other than Pygame; copying code or assets from any reference project.

---

## 2. Turn structure and explicit rules

### 2.1 Screen flow (in `main.py`), by milestone
```
M1:  BATTLE (press R to restart)
M2:  TEAM_SELECT ──► BATTLE ──► RESULT ──► TEAM_SELECT
M3:  TITLE ──► SETUP ──► TEAM_SELECT ──► BATTLE ──► RESULT ──► TITLE (or REMATCH ► TEAM_SELECT)
            (mode, difficulty)  (P1 picks 1–3; AI picks the same count, or P2 picks)
```

### 2.2 Round flow — simultaneous mode (default, `TURN_MODE = "simultaneous"`)
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
| **ROUND_START** | `round_number += 1`. Every character's special cooldown goes down by 1 (minimum 0). Then `start_turn(side)` runs for **both** sides: it clears that side's `is_defending` flags. Log "— Round N —". |
| **PLANNING** | Each side submits one `ActionPlan(actor, action, angle, power)`. **The AI plans first, at the start of this phase**, using public information only (§2.4, rule 7). The human plans through the UI. Submitted plans, including their angle and power, stay private inside `Battle` until both are in. The cannons on screen keep their last fired angle. Invalid plans are rejected (rule 9). |
| **RESOLVE_INSTANT** | Both plans are revealed in the log. Instant effects apply first, left side then right side (the order doesn't matter, because each only touches its own team): **Defend**, **Knight Rally**, **Engineer Repair**. Specials start their cooldowns here. Then each firing plan's angle and power are applied to its cannon, and **both cannons fire** (Attack, or Archer Power Shot). |
| **FLIGHT** | Each frame, every flying projectile advances one fixed physics step. When a projectile collides, it **explodes immediately** and its damage is applied right away (§4.4). A character killed mid-flight can't be hit again, but a shot its team already fired keeps flying. FLIGHT ends when no projectile is still flying. |
| **ROUND_END** | Award EXP to each actor that is still alive, and process level-ups. Check loss conditions for **both** teams at once: neither lost → ROUND_START; one lost → the other wins; both lost → Draw; round 30 finished → tie-break (§4.7). |

### 2.3 Instructor fallbacks: alternating turns, elimination-only victory
**Alternating mode (`TURN_MODE = "alternating"`).** Use it if the instructor requires players to act
one after another (§10, C1).
- Turns strictly alternate: left (the human, in Player vs AI), then right. One round = two turns.
- A turn is `start_turn(active_side)` → PLANNING (active side only) → RESOLVE_INSTANT → FLIGHT → TURN_END.
- In this mode, ROUND_START (before the left turn) **only** does `round_number += 1` and ticks the
  cooldowns (once per round). It does not clear any Defend.
- `start_turn(side)` clears only the active team's `is_defending` flags. So a Defend always covers
  exactly one enemy action: the turn in between.
- TURN_END: award EXP to the actor, then check loss conditions. If a team has lost, the other wins
  immediately. Simultaneous double losses can't happen, but the round-30 tie-break can still end in
  a Draw.
- Left always moves first, which gives it a small first-mover advantage: it can win before right
  replies in the same round. If playtests show this matters, let the starting side swap on each rematch.
- **What changes in code:**
  - `Battle.sides_to_plan()` returns `["left", "right"]` or `[active_side]`.
  - `begin_resolution()` already resolves "every submitted plan", so it works unchanged for one plan.
  - `end_turn()` reuses the loss check from `end_round()`.
  - The M1 prototype loop already alternates, so this mode reuses it.
  - The AI uses the same `choose_plan`. It sees the result of the previous turn (public), and
    there is no hidden plan to see.
- **Testability:** `Battle(turn_mode=TURN_MODE, castle_loss_enabled=CASTLE_LOSS_ENABLED)`. The
  module constants are only defaults, so tests create a battle in each mode without patching.
- **Recommendation:** build the switch in M2, with tests for both values. It is small and greatly
  reduces the C1 risk. It does not remove it, because "alternating turns" might mean each character
  acts in turn (Q3). Keep `"simultaneous"` as the default until the instructor answers.

**Elimination-only victory (`CASTLE_LOSS_ENABLED = True`).** If the instructor requires victory by
defeating all enemies only (§10, C2), set it to `False`. Castles then act only as shields: the
tie-break skips the castle step (§4.7), and the AI's chance of targeting the castle becomes 0 (§6.3).

**Round limit (`ROUND_LIMIT = 30`).** It applies in every mode and can be raised but not removed:
it guarantees that every match ends, and the AI-vs-AI tests rely on that. It is listed as its own
deviation (§10, C7).

### 2.4 Explicit gameplay rules (PM item E)

| # | Question | Rule | Why |
|---|---|---|---|
| 1 | Both castles destroyed in the same round? | **Draw.** More generally, if both teams meet *any* loss condition at the same ROUND_END, it is a Draw. In alternating mode this can't happen, because each turn is checked on its own; only the round-30 tie-break can end in a Draw there. | Simultaneous resolution has no "first" shot; the only fair answer is a Draw. |
| 2 | What does Defend protect? | **Characters only, never castles.** Defend: the acting character takes 50 % damage until its team's next turn starts. Knight Rally: every living ally, **including the Knight itself**. | If Defend protected the castle, a team could stall the castle win forever. |
| 3 | How do explosions affect characters and blocks? | One explosion per shot, when the shot enters an enemy character's rectangle or an enemy block's rectangle, or reaches the ground. Every **enemy** character and every **enemy** block whose centre is within **50 px** of the impact point is damaged once (§4.1, §4.3). No friendly fire: shots pass through their own team's castle and characters. Projectiles never collide with each other. Defeated characters are removed from the field: they no longer block or trigger shots. In M1 there are only blocks. | One rule covers every target, so it's easy to explain and test. |
| 4 | May the same character act every round? | **Yes.** Any living character may act in any round. | Simplest rule, and safe for the course's "AI defends below 50 % HP" requirement. The other characters still matter: their specials have separate cooldowns, they add HP, and they are targets. Rejected: "no acting two rounds in a row", because it can stop the AI from defending its weakest character. |
| 5 | Repair: damaged vs destroyed blocks? | Damaged blocks that still stand regain HP, up to their maximum. **Destroyed blocks (0 HP) never come back.** Pool: 75 HP per use, most damaged block first (§3.4). | Gaps in the wall stay open, so repairs can't undo the attacker's progress completely. |
| 6 | How are cooldowns counted? | Each character has its own counter. Using the special sets it to `SPECIAL_COOLDOWN`. **Every** ROUND_START lowers every counter by 1 (minimum 0), even for characters that did not act. The special is usable when the counter is 0. **Used in round r → usable again in round r + cooldown.** | Counting happens in one place, so there are no off-by-one special cases. |
| 7 | How does the AI decide without seeing the hidden plan? | The AI submits **first**, at the start of PLANNING, before the human chooses. It reads only public information: positions, HP, levels, cooldowns, castle blocks and the log of earlier rounds. `Battle` keeps submitted plans in a private attribute (`_plans`) and reveals them only in RESOLVE_INSTANT. The planned angle and power are **not** applied to the `Cannon` until then, so the enemy barrel on screen keeps its last fired angle and can't give the plan away. The human's own draft aim is held by `main.py` and drawn only on the human's own cannon. Tests check that (a) with a fixed random seed, the AI's plan is identical whether or not the human's plan has been submitted, and (b) submitting a plan does not change the cannon's angle or power. | The order of play guarantees it, and the tests prove it. In PvP the same rule hides Player 1's aim from Player 2. |
| 8 | A team loses a character (or its castle) while its shot is in the air? | The shot still lands and still deals damage. | Both shots were fired together. Rebound deletes in-flight shots instead (review §3.3), which would break simultaneity. |
| 9 | What makes a plan invalid? | A dead actor; a special still cooling down; angle or power out of range; Repair when no surviving block is damaged. The plan is rejected with a log message, and the UI disables those buttons. | Bad input never reaches the rules, and a special can't be wasted by accident. |

### 2.5 Example: cooldown counting (Archer, cooldown 3)

| Round | ROUND_START sets counter to | Archer's action | Counter after the action |
|---|---|---|---|
| 2 | 0 | **Power Shot** | 3 |
| 3 | 2 | Attack | 2 |
| 4 | 1 | Attack | 1 |
| 5 | 0 → ready | **Power Shot** (2 + 3 = 5) | 3 |

---

## 3. Characters (from M2)

### 3.1 Attributes (every character)
| Attribute | Meaning |
|---|---|
| `name`, `side` | display name; `"left"` or `"right"` |
| `max_hp`, `hp` | health; the character is defeated when `hp == 0` |
| `atk` | base damage |
| `defense` | subtracted from incoming character damage (named `defense` because `def` is a Python keyword) |
| `level`, `exp` | start at Level 1 with 0 EXP; maximum level 5 |
| `is_defending` | True from its Defend (or a Knight's Rally) until its team's next turn |
| `special_cooldown` | rounds left until the special can be used again; 0 = ready |
| `slot_x` | slot centre position, set from the slot index |

**Encapsulation:** the values that must stay valid (`hp`, `exp`, `level`, `special_cooldown`,
`is_defending`) are stored with a leading underscore (`_hp`, …). They change **only** through
methods (`take_hit`, `gain_exp`, `defend`, `clear_defend`, `start_cooldown`, `tick_cooldown`)
and are read through read-only properties (plain getter methods work just as well). Other modules
never assign them directly.

Class-level constants, overridden by each archetype: `BASE_HP`, `BASE_ATK`, `BASE_DEF`,
`BLOCK_DAMAGE_MULT`, `SPECIAL_NAME`, `SPECIAL_COOLDOWN`, `SPECIAL_FIRES_SHOT`,
`SPECIAL_DAMAGE_MULT`, `SPECIAL_IGNORES_DEF`.

### 3.2 The three archetypes
| | **Knight** (tank) | **Archer** (damage) | **Engineer** (siege) |
|---|---|---|---|
| HP | 140 | 90 | 110 |
| ATK | 30 | 40 | 34 |
| DEF | 12 | 4 | 8 |
| Block damage multiplier | 1.0 | 0.75 (arrows are weak against stone) | 1.5 |
| Special | **Rally:** every living ally, the Knight included, defends until the team's next turn. Does not fire. | **Power Shot:** an aimed cannon shot with ×1.5 damage that ignores DEF. | **Repair:** restores up to 75 HP to the castle (§3.4). Does not fire. |
| Special cooldown | 4 | 3 | 4 |
| Special needs aim? | no | yes | no |

**Team selection:** a team picks 1–3 **different** archetypes. Duplicates are not allowed.

### 3.3 Cooldown rule
A special used in round *r* can be used again in round *r + cooldown*. Every special starts
ready. Details and an example: §2.4 rule 6 and §2.5.

### 3.4 Engineer Repair (rebalanced)
**Rule:** Repair restores **at most 75 HP in total** (5 % of the castle's 1500 HP). The HP goes
to damaged blocks that are still standing, **most damaged first** (ties: leftmost, then top
first). No block goes above 100 HP. Destroyed blocks stay destroyed. Any HP left over is lost.
Cooldown 4.

```
pool = 75
for block in surviving blocks, sorted by hp (lowest first):
    gain = min(pool, block.max_hp - block.hp)
    block.hp += gain ;  pool -= gain
```
Examples: block HP `[100, 40, 70, 0]` → `[100, 100, 85, 0]` (60 + 15 = 75 used; the destroyed
block is untouched). Block HP `[90, 95]` → `[100, 100]` (15 used, 60 lost).

**Trade-off:**
- *Old rule:* +25 HP for every surviving block, up to 375 HP (25 % of the castle) per use. One
  Repair cancelled three or four enemy hits, so a team could stall.
- *New rule:* at most 5 destruction points back per use, and at most once every 4 rounds
  (≤ 1.25 points per round). One Knight or Archer hit moves the enemy's bar 6–8 points, and an
  Engineer hit about 13 (51 × 3.7 ≈ 190 HP). Repairing also costs the team its attack for that
  round. So Repair is a situational choice, mainly to step back from the 60 % line, and it can
  never make the castle win unreachable. Repair is invalid when no surviving block is damaged
  (§2.4 rule 9).
- *Cost:* the Engineer's special is weaker. If playtests show nobody uses it, raise the pool
  (one constant), not the per-block amount.

### 3.5 EXP and levels (revised)
Only the character that acted earns EXP, and only if it is **still alive at the end of the round**
(at the end of its turn in alternating mode). A defeated character earns nothing and is never
revived by a level-up.

| Event | EXP |
|---|---|
| Its shot (Attack or Power Shot) damages at least one enemy block or character | +10 |
| Each enemy character its shot defeats | +20 extra |
| Rally, or a Repair that restored at least 1 HP | +5 |
| Basic Defend | 0 |
| Its shot misses | 0 |

`EXP to next level = 30 × current level` (30 to reach Level 2, then 60, 90, 120). Leftover EXP
carries over. One award can cross more than one threshold, so `gain_exp` levels up in a loop and
returns the number of levels gained. Each level-up gives `max_hp +10` and `hp +10`, `atk +3`,
`defense +1`. At the maximum level (5), EXP is no longer added. EXP and levels last for one match only.

*Why it changed:*
- The old rule gave +5 for any action, including misses, and needed 40 × level. Now a character
  that hits every round reaches Level 2 in round 3 and Level 3 in round 9, so a grader sees at
  least one level-up in a normal 8–15-round match.
- Basic Defend can be repeated every round, so it earns nothing; otherwise endless defending would
  still pay. Rally and Repair are limited by cooldowns, so a small reward is safe.

---

## 4. Rules and calculations

All arithmetic produces integers by truncating with `int()` or `//`. There is no `round()`,
because Python's `round()` uses banker's rounding and would surprise students.

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
- Archer Power Shot → Knight: int(40 × 1.5) = 60, DEF ignored = **60**. Defending: **30**.
- Knight Attack → Archer: 30 − 4 = **26**.

### 4.2 Defend
- **Defend** (any character): the acting character takes 50 % damage (§4.1) until its team's
  next turn. It does not attack this round.
- **Rally** (Knight special): every living ally is defending until the team's next turn.
- Defend never reduces castle damage (§2.4 rule 2).

### 4.3 Damage to castle blocks (one explosion)
```
block_damage = int(attacker.atk * shot_multiplier * attacker.BLOCK_DAMAGE_MULT)   # M2+
block_damage = SHOT_BLOCK_DAMAGE = 50                                             # M1 (no characters; 30 until M1.1)
```
Blocks have no DEF and cannot defend. Level 1 values: Knight 30, Archer 30, Engineer 51,
Archer Power Shot int(40 × 1.5 × 0.75) = 45.

### 4.4 Explosions (one rule for everything)
When a projectile enters an enemy character's rectangle or an enemy block's rectangle, or reaches
the ground, it **explodes** at that point. At the impact point:
- every **enemy** character whose centre is within **50 px** takes character damage (§4.1);
- every **enemy** block whose centre is within **50 px** takes block damage (§4.3).

Each target is damaged at most once per explosion. There is **no friendly fire**: a projectile
passes through its own team's castle and characters. A shot that leaves the screen sideways
(no explosion), or is still flying after 600 steps (10 s), is a miss. Shots may go above the top
of the screen (y < 0) and come back down.

On an intact castle, a hit damages **2–6 blocks, usually 3–4** (77 % of hits; mean 3.7; §14).

### 4.5 Castle and destruction
- Block: 32 × 32 px, **100 HP**. A block at 0 HP is destroyed: it disappears and stops blocking shots.
- Template for the left castle (top row first; `#` = block). The right castle uses each row
  reversed, so its tower faces left:
  ```
  ....##
  ....##
  ....##
  ...###
  ######
  ```
  15 blocks, 1500 HP in total. Front tower height 160 px. Back wall height 32 px.
- `destruction % = 100 × (1 − current total block HP / max total block HP)`. It counts damage,
  not destroyed blocks, so every hit moves the bar.
- **Loss at ≥ 60 %**, which is 900 HP of damage. With M1.1's fixed 50 damage per block, a
  player who always picks the best shot needs 4 hits, a skilled player about 6 (5–8), and a
  casual player about 8 (5–17) (M1.1 notes below). With M1's original 30 it was 7, 10 and 15.
  A Level-1 Knight or Archer deals only 30 per block, so M2 must re-check this scale (see the
  M1.1 notes).
- Blocks do **not** fall when the block below them is destroyed, and neither does the cannon.
  This is an accepted simplification (R4).

### 4.6 Projectile physics (shared by the game, the AI and the tests)
```
GRAVITY         = 400 px/s²  (screen y points down)
SPEED_PER_POWER = 7          (power 10–100 → 70–700 px/s)
DT              = 1/60 s per physics step, fixed (deterministic)
MAX_STEPS       = 600
launch point    = the side's cannon pivot: left (360, 390), right (920, 390)
vx = direction * speed * cos(angle)   (direction +1 for left, -1 for right)
vy = -speed * sin(angle)
each step:  vy += GRAVITY*DT ;  x += vx*DT ;  y += vy*DT ;  then check collisions
```
- `SIM_STEPS_PER_FRAME = 1`. Useful shots fly 46–218 frames (0.8–3.6 s).
- **Speed bound:** by energy conservation the fastest possible shot is
  √(700² + 2·400·(560 − 390)) ≈ 791 px/s, so it moves at most **13.2 px per step**. That is
  less than the smallest target (a character is 28 px wide), so a shot can never jump over a whole
  target between two steps. It can still clip a corner by a few pixels, because collisions are
  checked once per step; that is acceptable at this scale. A unit test enforces the inequality,
  so changing `SPEED_PER_POWER` or `GRAVITY` too far fails loudly. (Idea adapted from Rebound's
  sub-stepping rule; review §3.2.)

### 4.7 Round-limit tie-break
At the end of round `ROUND_LIMIT` (30), if nobody has lost, compare in order:
1. more **living characters** wins;
2. else more **total HP of living characters** wins;
3. else **lower castle destruction %** wins (this step is skipped when `CASTLE_LOSS_ENABLED` is `False`);
4. else it is a Draw.

Putting the characters first matches the course's elimination victory, and it works in every mode.

### 4.8 Alignment with the course's examples (damage and EXP)
We don't have the course's example formulas in the repository (§13, Q1), so we can't claim to
match them. What we can say:
- Our damage formula follows the common pattern *damage = ATK − DEF (minimum 1)*. The course rule
  "Defend reduces incoming damage by 50 %" is applied after DEF, to the defending character only
  (§10, C5).
- EXP uses fixed rewards and a linear level threshold. The course requires the EXP and Level
  attributes; it doesn't fix their numbers, as far as we know.
- Each formula lives in exactly one function (`calculate_damage`, `Character.gain_exp`). If the
  instructor gives exact example formulas, matching them is a one-function change plus updated
  test values.

---

## 5. Architecture

### 5.1 Modules, created only when a milestone needs them
| Module | Created in | Contents | Imports pygame? |
|---|---|---|---|
| `castle.py` | M1 | `Block`, `Castle`, castle geometry constants (`GROUND_Y`, `TEMPLATE`, …) | no |
| `battle.py` | M1, grows in M2 | M1: `Cannon`, `Projectile`, `Battle` (alternating shots). M2: adds `ActionPlan`, `Team`, the phases of §2.2 and the `TURN_MODE` switch | no |
| `main.py` | M1, grows each milestone | Pygame window, screens, input, all drawing, sound | **yes (only this one)** |
| `characters.py` | M2 | `calculate_damage`, `Character`, `Knight`, `Archer`, `Engineer`, `ARCHETYPES` | no |
| `ai.py` | M3 | `DIFFICULTY`, `aim_power`, `AIController` | no |

```
main.py ──imports──► battle.py, castle.py         (M1)
                 ──► characters.py (M2), ai.py (M3)
ai.py   ──imports──► battle.py (Projectile simulation, ActionPlan)
battle.py ─imports─► castle.py; characters.py from M2
characters.py, castle.py ── import nothing from the project
```
No empty placeholder modules are created. Each module keeps its own constants at the top, so
there is no separate config module. A test checks that importing the logic modules does not
load pygame. It runs the import in a fresh `python -c` subprocess and checks
`"pygame" not in sys.modules`, so other tests that import `main.py` can't spoil the result.

### 5.2 Classes
**`castle.py`** (M1)
| Class | Responsibility |
|---|---|
| `Block` | `x, y, size, max_hp`, private `_hp`. Methods: `is_destroyed()`, `center()`, `contains(px, py)`, `take_damage(n) -> int` (actual damage dealt, capped at remaining HP). M2 adds `restore(n) -> int` (capped at max HP; does nothing if destroyed). |
| `Castle` | `side`, private list of blocks built from `TEMPLATE` (mirrored for the right side). Methods: `alive_blocks()`, `block_at(px, py)`, `apply_blast(px, py, radius, damage) -> (blocks_hit, total_damage)`, `destruction_percent() -> float`, `has_fallen() -> bool` (≥ 60 %). M2 adds `is_damaged() -> bool` and `repair(pool) -> total_restored` (the §3.4 loop). |

**`battle.py`** (M1 part)
| Class | Responsibility |
|---|---|
| `Cannon` | `side`, pivot `x, y`, private `_angle` and `_power`. Methods: `adjust_angle(delta)`, `adjust_power(delta)` (both clamp to the legal range, so an invalid aim can't exist), `direction()` (+1 or −1), `fire(owner, multiplier=1.0, ignores_def=False) -> Projectile`. |
| `Projectile` | `x, y, vx, vy, side, owner, multiplier, ignores_def, flying, steps`. Method `step()` = one physics step (§4.6). |
| `Battle` (M1) | Owns `castles`, `cannons`, `active_side`, `projectile`, private `_events`, `winner`. Methods: `fire()` (active cannon), `update()` (one physics step; explosion → `_explode(x, y)`; when the shot ends, check for a winner, then switch `active_side`), `take_events() -> list` (returns and empties the event list, §5.3), `simulate_impact(side, angle, power) -> (x, y)` (side-effect-free preview, used by tests and later by the Hard AI). |

**`battle.py`** (M2 additions)
| Class | Responsibility |
|---|---|
| `ActionPlan` | Small plain class: `actor_index, action ("attack"/"defend"/"special"), angle, power`. |
| `Team` | `side, characters, castle, cannon, ai` (`None` means a human controls it). Methods: `alive_characters()`, `has_lost()`. |
| `Battle` (M2) | Constructor `Battle(..., turn_mode=TURN_MODE, castle_loss_enabled=CASTLE_LOSS_ENABLED)`. Adds `teams`, `round_number`, `phase`, private `_plans`, `log`. Methods: `start_round()`, `start_turn(side)` (clears that side's Defend flags), `sides_to_plan()`, `submit_plan(side, plan) -> bool` (stores the plan only; the cannon is unchanged), `ready_to_resolve()`, `begin_resolution()`, `update()`, `end_turn()`, `end_round()`, `resolve_round_instantly()` (test helper: runs `update()` until the round is over). |

**`characters.py`** (M2)
| Class / function | Responsibility |
|---|---|
| `calculate_damage(atk, multiplier, defense, ignores_def, defending)` | Pure function implementing §4.1. Easy to unit test. |
| `Character` (base) | Holds the §3.1 attributes. Methods: `is_alive()`, `hp_ratio()`, `take_hit(attacker, multiplier, ignores_def) -> int`, `block_damage(multiplier) -> int`, `defend()`, `clear_defend()`, `special_ready()`, `start_cooldown()`, `tick_cooldown()`, `gain_exp(amount) -> int` (number of levels gained, 0 or more), and `use_special(team) -> str` (the base version raises `NotImplementedError`). |
| `Knight(Character)` | Archetype constants. Overrides `use_special`: calls `defend()` on all living allies. |
| `Archer(Character)` | Archetype constants (`SPECIAL_FIRES_SHOT = True`, ×1.5, ignores DEF). Overrides `use_special`: returns a log line; the battle fires the cannon. |
| `Engineer(Character)` | Archetype constants. Overrides `use_special`: calls `team.castle.repair(REPAIR_POOL)`. |
| `ARCHETYPES = [Knight, Archer, Engineer]` | Used by the selection screen and the AI. |

**`ai.py`** (M3): see §6.

**`main.py`**
| Item | Responsibility |
|---|---|
| `Button` (M2) | Rectangle, label, enabled flag, `draw()`, `is_clicked(pos)`. |
| `Game` | `state` string (screens of §2.1, plus HANDOVER in M3). One `handle_event / update / draw` method group per state; the human's aiming input; all drawing (background, castles with HP-band colours, cannons, characters, HP bars, aim arrow, projectiles, explosions, HUD, buttons, combat log, result screen); sounds (M4). |
| `main()` | Pygame init and the main loop: `events → update → draw → clock.tick(60)`. |

### 5.3 `Battle.events`: how the logic talks to the screen
Any `Battle` method (`fire()`, `begin_resolution()`, `update()`, …) may append small
dictionaries to a private list, such as `{"type": "fire", "side": "left"}`,
`{"type": "explosion", "x": 905, "y": 512}`, `{"type": "block_destroyed", …}`,
`{"type": "character_defeated", …}` or `{"type": "game_over", "winner": "left"}`. Once per
frame, `main.py` calls `battle.take_events()`, which returns the list and empties it. `main.py`
then starts an explosion animation (M1), adds log lines (M2) or plays sounds (M4). Only the reader
empties the list, so no event is lost between calls. It is one list with one reader, not an event bus. The logic modules stay free
of pygame and easy to test. (Pattern adapted from Rebound's `sound_events`; review §2.3.)

### 5.4 Where the OOP marks come from
- **Inheritance + polymorphism:** `Character` → `Knight` / `Archer` / `Engineer`. The base class
  holds every shared rule. `Battle` calls `actor.use_special(team)` once, and the three overrides
  behave differently.
- **Encapsulation:** `_hp`, `_exp`, `_angle`, `_power` and block `_hp` change only through
  methods that enforce the limits (clamping, minimum 0, maximum HP).
- **Composition:** `Battle` has two `Team`s; a `Team` has characters, a `Castle` and a `Cannon`;
  a `Castle` has `Block`s.

### 5.5 Deliberately not used
No entity-component system, event bus, dependency injection, external physics engine, networking,
`config.py`, or abstract factory. Each one would add a concept a CS5001 grader has to learn,
without making this game better.

---

## 6. Player vs AI now, local PvP later (M3)

### 6.1 One rule: the battle doesn't know who is playing
`Battle` only ever receives `ActionPlan`s through `submit_plan(side, plan)`. Each `Team` has an
`ai` field:
- `team.ai` is an `AIController` → at the start of PLANNING, `main.py` calls
  `battle.submit_plan(side, team.ai.choose_plan(battle, side))`, before the human acts.
- `team.ai is None` → `main.py` collects that side's plan from keyboard and mouse.

### 6.2 What PvP needs (UI only, no battle changes)
1. A SETUP option: "vs AI" / "2 Players".
2. TEAM_SELECT for Player 2.
3. A HANDOVER cover screen between planning the left side and planning the right side, so
   Player 2 can't see Player 1's aim. The right-side angle mirrors automatically, so the controls
   are the same for both players.

AI-vs-AI is the same code with both `ai` fields set. The tests use it to play whole matches
without a window, which also shows that the battle code is fully symmetric.

### 6.3 AI behaviour (explicit numbers; difficulty changes the AI only, never the rules)
| Parameter | Easy | Normal | Hard |
|---|---|---|---|
| Angle noise (uniform ±) | 10° | 6° | 3° |
| Power noise (uniform ±) | 14 | 9 | 5 |
| Defend chance when its weakest character is below 50 % HP | 50 % | 70 % | 85 % |
| Chance to use a ready special when it's useful | 30 % | 70 % | 100 % |
| Base angle | random 35–65 | random 40–60 | first of [45, 55, 60, 50, 40] whose simulated impact lands within 25 px of the target |
| Checks the shot with `simulate_impact` | no | no | yes (up to 5 tries) |
| Actor choice when attacking | random living character | best for the target (highest block damage vs the castle, highest ATK vs characters) | same as Normal |
| Target choice | castle 70 %, random enemy 30 % | an enemy it can kill with this shot; else castle 60 % / lowest-HP enemy 40 % | an enemy it can kill with this shot; else the castle if the enemy castle is ≥ 40 % destroyed; else the lowest-HP enemy |

`aim_power(dx, dy_up, angle)` uses the closed-form projectile formula
`v² = g·dx² / (2·cos²θ·(dx·tanθ − dy_up))`, `power = v / SPEED_PER_POWER`. From the cannon it
lands within 17 px of the target (mean 12 px) under the step-by-step simulation, well inside the
50 px blast.

**Edge cases (so the AI is fully defined):**
- **Aim points.** "The castle" means the centre of the top surviving block in the enemy castle's
  front column (the column facing the AI); if that column is gone, the nearest surviving block.
  A character target means that character's centre.
- **No solution.** If `aim_power` returns `None` (the denominator is ≤ 0) or a power outside
  10–100 for the chosen angle, Easy and Normal draw a new base angle (up to 5 draws), then fall
  back to 60° with the power clamped. Hard skips that candidate angle.
- **Hard fallback.** If none of Hard's 5 candidate angles lands within 25 px, it uses the
  candidate whose simulated impact was closest to the target.
- **Elimination-only mode** (`CASTLE_LOSS_ENABLED = False`): the castle-targeting chances become
  0, and every attack targets a character.
- **Team choice.** `AIController.choose_team(count, rng)` returns `count` different archetypes
  picked at random from `ARCHETYPES`, the same on every difficulty. `count` matches the player's
  team size.

**Decision order** (all difficulties):
1. **Defensive preference.** If the AI's weakest living character is below 50 % HP, then with
   probability *Defend chance*: use a ready Knight's Rally if two or more allies are below 50 %
   (Hard also uses it for just one); otherwise the weakest character Defends.
2. **Repair.** If its castle is ≥ 30 % destroyed and a living Engineer's Repair is ready, use it
   (with probability *special chance*).
3. **Attack.** Pick the target, then the actor, then the angle. Compute power with `aim_power`,
   add noise, and clamp to the legal ranges. A ready Archer uses Power Shot (with probability
   *special chance*).

Throwaway Monte Carlo estimates of hit rates from the cannon (§14; 400 planned shots per cell):

| | Easy | Normal | Hard |
|---|---|---|---|
| Damages the castle | ~58 % | ~75 % | ~96 % |
| Damages a character behind the castle | ~33 % | ~53 % | ~80 % |

(The Rev 1 table, ±8°/±10, ±4°/±5, ±1°/±2, gave 98 % character hits on Hard from the fixed cannon.
We also simulated Rebound-style target-offset noise; see review §3.5.)

---

## 7. File structure by milestone
```
pygame-castle_campaign/
├── main.py              # M1+  Pygame loop, screens, input, drawing (sound from M4)
├── castle.py            # M1   Block, Castle
├── battle.py            # M1   Cannon, Projectile, Battle;  M2: ActionPlan, Team, phases
├── characters.py        # M2   Character, Knight, Archer, Engineer, calculate_damage
├── ai.py                # M3   AIController, aim_power, DIFFICULTY
├── tests/
│   ├── test_castle.py       # M1
│   ├── test_battle.py       # M1, extended in M2
│   ├── test_characters.py   # M2
│   └── test_ai.py           # M3
├── assets/              # M4 only, if needed: self-made or CC0 sounds/images + CREDITS.md
├── docs/
│   ├── M0_design.md                 # this file
│   ├── Rebound_reference_review.md  # reference-project audit
│   └── report/                      # M5: final report, screenshots
├── README.md            # M1: install, run, controls, test command; final in M5
└── requirements.txt     # M1: pygame (pinned version, see Q2)
```
Tests use the standard-library `unittest`: `python -m unittest discover tests`. pytest isn't
required, but it can run these tests too.

---

## 8. CS5001 rubric alignment

Rubric categories and points as given by the PM. The exact criteria inside each category are
not in this repository (§13, Q1), so the middle column is our reading of the category names and
of the PM's list of important requirements.

| Category (points) | What we will show | Where / milestone | Risk today |
|---|---|---|---|
| **Game Description (10)** | Pitch, rules, controls, both victory conditions, the Draw rule, screenshots, and an **explicit list of where we differ from the course specification** (C1–C7) | README draft in M1, final README and report in M5 | Medium: the deviations must be explained, never hidden |
| **Functionality (40)** | Every required feature in §9 working in a complete match: Attack / Defend / Special, Defend −50 %, cooldowns, HP / ATK / DEF / EXP / Level, character selection, AI with defensive preference, HP bars, action buttons, combat log, result screen | M1 (physics, castle), M2 (rules, GUI basics), M3 (AI), M4 (polish) | High until M3 is done; a late C1/C2 decision changes the battle phases (mitigated by the §2.3 switches) |
| **OOP Design (20)** | Inheritance and polymorphism (`Character` subclasses), encapsulation (private state behind methods), composition (`Battle` → `Team` → `Castle` → `Block`); a class diagram in the report | M1 (castle, cannon classes), M2 (characters), M5 (diagram) | Low |
| **Testing (15)** | `unittest` suites for every logic module; seeded AI tests; AI-vs-AI whole-match tests; a manual checklist for UI items; tests always call the real functions (review §3.7) | M1–M3; audit in M5 | Low–Medium: UI is covered by the manual checklist only |
| **Clean Code and Comments (10)** | Docstrings on every class and public method, named constants at the top of each module, short functions, no dead code, consistent naming | Every milestone; audit in M5 | Medium: `main.py` size (R3) |
| **Report Completeness (5)** | Report sections, documented algorithms (physics, explosion, damage, EXP, Repair, AI), screenshots, demo video, references (including Rebound) | M5 | Low once Q1/Q5 give the template |

---

## 9. Requirement → milestone mapping

| Course / project requirement | Where | Milestone | Verified by |
|---|---|---|---|
| Pygame window, battlefield, two castles, one cannon per side | `main.py`, `castle.py`, `battle.Cannon` | M1 | manual checklist |
| Projectile angle / power / gravity | `Projectile.step`, §4.6 | M1 | test_battle (determinism, default shot lands at x 770–800, speed bound, no legal shot reaches the 600-step timeout) |
| Explosion and collision detection | `Battle._explode`, `Castle.apply_blast` | M1 | test_castle, test_battle |
| Castle damage, destruction %, 60 % loss | `Castle.apply_blast`, `destruction_percent`, `has_fallen` | M1 | test_castle |
| Attack action | `ActionPlan("attack")`, `Battle.begin_resolution` | M2 | test_battle |
| Defend −50 % damage | `calculate_damage(... defending)`, `Character.defend` | M2 | test_characters (exact halving, minimum 1, lasts until next turn) |
| Special ability + cooldown | `use_special` overrides, `start_cooldown` / `tick_cooldown` | M2 | test_characters (round r → r + cooldown), test_battle |
| HP, ATK, DEF, EXP, Level | `Character` attributes, `gain_exp` | M2 | test_characters (thresholds, stat gains, dead earn nothing) |
| OOP inheritance and encapsulation | `Character` → `Knight / Archer / Engineer`; private state | M2 | code review, class diagram (M5) |
| Character selection | `TEAM_SELECT` screen, `ARCHETYPES`, `AIController.choose_team` | M2 (AI's pick in M3) | manual checklist; test_ai (`choose_team` returns `count` different archetypes) |
| HP bars, action buttons, combat log, result screen | `Game.draw_*`, `Button`, `Battle.log`, `RESULT` state | M2 (basic), M4 (polish) | manual checklist; test_battle (log entries) |
| Simultaneous resolution, with an alternating fallback | `Battle` phases, `turn_mode`, `start_turn` | M2 | test_battle (mutual kill → Draw; alternating turn order; Defend covers exactly one enemy turn in both modes) |
| Elimination victory, castle victory, Draw, tie-break | `Team.has_lost`, `end_round`, `castle_loss_enabled`, §4.7 | M2 | test_battle (both values of `castle_loss_enabled`) |
| Engineer Repair (capped) | `Castle.repair` | M2 | test_castle (pool examples of §3.4) |
| Enemy AI, defensive preference below 50 % HP | `AIController.choose_plan`, step 1 | M3 | test_ai (seeded rate check) |
| AI difficulty Easy / Normal / Hard | `ai.DIFFICULTY` | M3 | test_ai (Hard ≥ Normal ≥ Easy hit rate; AI-vs-AI matches end before the cap) |
| AI never sees the hidden plan | plan order, private `_plans`, cannons updated only at resolution | M2 (cannon rule), M3 (AI) | test_battle (submitting a plan leaves the cannon unchanged); test_ai (same seed → same plan) |
| Local PvP | HANDOVER screen + P2 team select | M3 | manual checklist |
| Background, sound, animations | drawing, `Battle.events` → sounds | M4 | manual checklist (silent fallback if the mixer fails) |
| Tests | `tests/` with `unittest` | M1–M5 | `python -m unittest discover tests` |
| Screenshots, documented algorithms, source code, report, demo video | `docs/report/`, README | M5 | rubric audit checklist |

---

## 10. Course compliance, design decisions and risks

### 10.1 Differences from the course specification (need instructor confirmation)
| # | Topic | Compliant? | Our design | If rejected |
|---|---|---|---|---|
| **C1** | Alternating turns | **No.** The course describes players acting one after another; we resolve both actions together. | Each round still has exactly one action per side, and the log shows them in a fixed order. | Set `TURN_MODE = "alternating"` (§2.3), one action per side per turn. Recommended to build in M2. If "alternating" means each *character* acts in turn, that needs a different design (Q3). |
| **C2** | Elimination victory | **Partly.** Elimination is kept. We **add** the 60 % castle loss and a Draw; the course mentions only win and lose. | The castle win gives aiming a target that isn't a character. | Set `CASTLE_LOSS_ENABLED = False`. In simultaneous mode a Draw still happens if both teams are eliminated in the same round; in alternating mode only the round-30 tie-break (C7) can produce one. |
| **C3** | Attacks can miss | **Unknown.** The course may assume every Attack deals damage. | Misses are what make artillery a skill. | Add an assist mode (for example, Easy-only aim help). Not planned. |
| **C4** | "AI defends below 50 % HP" with a team | **Interpretation.** "HP" is ambiguous with several characters, and our defence is probabilistic (50 / 70 / 85 %). | We use the weakest living AI character. | Set Defend chance to 100 % (one table row). |
| **C5** | "Defend reduces damage by 50 %" | **Interpretation.** Applied after DEF, minimum 1, to the defending character only; never to castles. | — | Moving the halving before DEF is a one-line change. |
| **C6** | Characters "attack" | **Interpretation.** Characters attack *through* their team's cannon; the actor's stats set the damage. | One launch point per side (PM request). | Fire from the actor's slot instead (the Rev 1 design). Needs re-tuning. |
| **C7** | Round limit | **Addition.** The course doesn't mention one. The match ends after round 30 with the §4.7 tie-break, which can be a Draw. | It guarantees that every match ends, including AI-vs-AI test matches. | Raise `ROUND_LIMIT`. Removing it isn't recommended. |

### 10.2 Design questions now decided (the PM may still override)
- **A1 Fewer than 3 characters:** allowed (1–3, as the course says). The AI matches the player's
  team size. No compensation bonus.
- **A2 Does Defend protect the castle?** No (§2.4 rule 2).
- **A3 Duplicate archetypes in a team?** Not allowed.
- **A4 May the same character act every round?** Yes (§2.4 rule 4).
- **A5 EXP and levels across matches:** reset every match. Carrying them over ("campaign") is out of scope.
- **A6 Assets:** shapes drawn in code until M4. In M4: sounds generated with the standard library,
  or CC0 files listed in `assets/CREDITS.md`. No assets from Rebound or any other project
  without a licence that allows it.

### 10.3 Implementation risks
- **R1 Physics tunnelling.** Prevented by the speed bound (§4.6), enforced by a unit test.
- **R2 AI strength.** Hard hits characters ~80 % of the time. Tune in M3 with the AI-vs-AI tests.
  Target: a Normal PvAI match lasts 8–15 rounds.
- **R3 `main.py` grows too large.** If it passes about 600 lines, split the drawing helpers into
  `ui.py` (a justified 6th module).
- **R4 Floating blocks and cannon.** Without collapse physics, blocks and the cannon can float
  over destroyed blocks. Accepted and documented.
- **R5 Pygame availability.** Pygame isn't installed in this design environment. The M1 README
  must pin a version (for example `pygame==2.6.1`), and the logic tests must not import pygame.
  Q2 decides the version.
- **R6 Hot-seat fairness (PvP).** The HANDOVER screen and the "cannons move only at resolution"
  rule (§2.4 rule 7) must hide Player 1's angle and power. A manual checklist item verifies it.
- **R7 Balance.** All numbers are first guesses. Tune constants, not code.
- **R8 Late instructor answers on C1/C2.** Mitigated by the §2.3 switches, built in M2.
- **R9 Scope creep from the reference project.** Power-ups, bouncing shots and neural AI are
  explicitly rejected (review §5).
- **R10 Docs drifting from code.** Numbers in the README and report must match the constants.
  An M5 audit checks them (lesson from Rebound, review §8).
- **R11 Elimination-only balance is unchecked.** If C2 is decided against us, matches may run
  longer (Easy vs Easy might reach round 30), and the M3 AI-vs-AI "ends before the cap" test would
  need different seeds or difficulties. Re-run the balance checks as soon as Q3 is answered.

---

## 11. Roadmap

No time estimates are given; each milestone ends when its acceptance criteria pass and the PM
approves.

### M1 — Minimal artillery and destructible-castle prototype
- **Required features:**
  - A 1280 × 720 Pygame window with sky, ground and two castles.
  - One cannon per side, with an aim arrow.
  - Keyboard aiming (angle and power, with clamping).
  - Space fires from the **active** cannon. When the shot ends, control passes to the other cannon.
  - Projectile physics (§4.6).
  - Explosions on enemy blocks or the ground, with a blast radius (§4.4) and a short circle animation.
  - Fixed block damage of 30.
  - Destroyed blocks disappear and stop blocking shots.
  - Live destruction % for both castles.
  - At ≥ 60 %, a banner announces the winner; R restarts.
  - Blocks drawn in HP-band colours.
- **Deliverables:** `main.py`, `castle.py`, `battle.py`, `tests/test_castle.py`,
  `tests/test_battle.py`, `requirements.txt`, and a README (install, run, controls, test command).
- **Acceptance criteria:**
  1. `python main.py` opens the window and shows both castles, both cannons and the HUD (active
     side, angle, power, both destruction %).
  2. A shot follows a visible arc and explodes on an enemy block or the ground. A shot leaving the
     screen sideways, or still flying after 600 steps, is a miss. Shots pass through their own castle.
  3. Blocks within 50 px lose 50 HP (or all they have left, if less; 30 HP before M1.1), and the destruction %
     updates at once.
  4. Input is ignored while a shot flies, then control alternates.
  5. A castle reaching ≥ 60 % ends the game with a banner, and R restarts.
  6. `python -m unittest discover tests` passes. Tests cover: template build and mirroring
     (15 blocks, positions); blast selection; destruction %; destroyed blocks no longer collide;
     own-castle pass-through; deterministic trajectories; the default shot landing at x 770–800;
     the speed bound; no legal shot reaching the 600-step timeout (a sweep over every angle and
     power; the longest legal flight is about 220 steps); cannon clamping; alternation; game over at
     60 %; the event list being emptied only by `take_events()`; logic modules not importing pygame.
- **Rubric categories:** Functionality, OOP Design, Testing, Clean Code.
- **Known risks:** Pygame install on the graders' machine (Q2); physics feel needs tuning; the
  temptation to pull M2 features forward.

### M2 — Complete combat rules, turns, characters, skills and OOP
- **Required features:**
  - `characters.py` (§3).
  - TEAM_SELECT (1–3 different archetypes per side; both sides chosen from the keyboard).
  - Round flow (§2.2) and the `TURN_MODE` and `CASTLE_LOSS_ENABLED` switches (§2.3).
  - Attack / Defend / Special; the three specials; cooldowns.
  - Character damage, and explosions that hit characters.
  - EXP and levels; capped Repair.
  - Draw and tie-break rules.
  - Basic required GUI: HP bars, action buttons (disabled when invalid), combat log (last 6 lines),
    and a result screen (Win / Lose / Draw, play again).
  - A defend bubble.
- **Deliverables:** `characters.py`, the extended `battle.py` and `main.py`,
  `tests/test_characters.py`, the extended `tests/test_battle.py`, and README rules.
- **Acceptance criteria:**
  1. A full match plays from the keyboard (both sides) to the result screen, in both turn modes.
  2. Tests pass for:
     - the §4.1 damage examples and minimum 1;
     - Defend halving that covers exactly one enemy action, in both turn modes;
     - cooldown round r → r + cooldown;
     - level thresholds and stat gains, a multi-level award, the Level 5 cap, and dead characters
       earning no EXP;
     - the Repair pool examples, and Repair being invalid on an undamaged castle;
     - mutual kill → Draw; castle win; elimination win; both values of `castle_loss_enabled`;
     - invalid plans rejected; submitting a plan leaving the cannon unchanged;
     - the tie-break order; alternating turn order;
     - an in-flight shot still landing after its team loses a character.
- **Rubric categories:** Functionality (most of it), OOP Design, Testing, Clean Code.
- **Known risks:** C1/C2 answers arriving late (mitigated by the switches); `main.py` growth (R3);
  balance.

### M3 — Enemy AI, difficulty selection and game modes
- **Required features:**
  - `ai.py` (§6.3).
  - TITLE and SETUP screens (vs AI / 2 Players; difficulty).
  - The AI's team choice and plans.
  - The HANDOVER screen for PvP, and Player 2's team selection.
- **Deliverables:** `ai.py`, `tests/test_ai.py`, and the extended `main.py`.
- **Acceptance criteria:**
  1. Player vs AI plays a full match on each difficulty.
  2. A PvP match hides each player's plan.
  3. Tests pass for:
     - `aim_power` accuracy (simulated impact within 25 px), and the no-solution fallbacks;
     - `choose_team(count)` returning `count` different archetypes;
     - the defensive preference rate with a seeded random generator;
     - the same seed giving the same plan with or without the opponent's plan;
     - hit rate Hard ≥ Normal ≥ Easy over a seeded batch;
     - seeded AI-vs-AI matches ending by castle destruction or elimination before the round-30
       cap, on every difficulty (the cap itself can't make this fail, so it isn't the test);
     - at least one level-up in a typical seeded match.
- **Rubric categories:** Functionality (AI, selection, modes), Testing, Game Description.
- **Known risks:** AI too strong or too weak (R2); hidden-plan fairness in PvP (R6).

### M4 — GUI improvements, background, sound, animations and polish
- **Required features:**
  - A drawn sky gradient and ground (an optional CC0 background image).
  - Sounds for firing, explosions, level-up and victory (generated or CC0, with credits; silent
    fallback if the mixer fails; M mutes).
  - A better explosion animation, block crack lines, and a marker at the top edge for shots above
    the screen.
  - Result-screen stats (shots, hits, damage per team).
  - An optional AI battle behind the title menu.
  - A balance tuning pass.
- **Deliverables:** the polished `main.py`, `assets/` with `CREDITS.md` (if any files are used),
  and an updated tuning table in this document.
- **Acceptance criteria:**
  1. Every event (fire, explosion, block destroyed, defeat, level-up, victory) has visible feedback.
  2. The game runs with sound disabled.
  3. No unlicensed assets.
  4. Average Normal PvAI match length is within 8–15 rounds in AI-vs-AI runs.
  5. All tests still pass.
- **Rubric categories:** Functionality, Game Description, Clean Code.
- **Known risks:** polish expanding without end (cap it at the list above); asset licensing.

### M5 — Testing, grading audit, report, screenshots, demo video and final submission
- **Required features:** no new gameplay.
- **Deliverables:**
  - A test audit: every §9 requirement mapped to an automated test or a manual checklist item.
  - A rubric audit table.
  - A final report (game description, how to play, rules, algorithms, class diagram, testing
    summary, deviations C1–C7 with the instructor's decisions, limitations, references including
    Rebound).
  - Screenshots (title, team select, battle, explosion, result).
  - A demo video.
  - The final README.
  - Code clean-up (docstrings, comments, naming).
  - A tagged release.
- **Acceptance criteria:**
  1. A fresh clone with `pip install -r requirements.txt` and then `python main.py` works on the
     graders' Python version (Q2).
  2. All tests pass.
  3. Every rubric category has evidence.
  4. Every number in the README and report matches the code.
  5. The Draw result was checked end to end.
- **Rubric categories:** all six, especially Report Completeness, Game Description and Testing.
- **Known risks:** missing course templates (Q1, Q5); last-minute bugs (freeze features at the
  start of M5).

---

## 12. Approaches considered

| Decision | Options | Chosen and why |
|---|---|---|
| Simultaneous resolution | (a) both shots fly at once and each explodes when it lands; (b) reveal both, then animate left then right; (c) real time | **(a).** It's the most faithful to "resolve together". Each shot only damages the other team, so the result doesn't depend on order. (c) is what Rebound does; it breaks turn-based play. |
| Course's alternating turns | build both modes now; build on demand; a constant switch | **A constant switch built in M2.** The per-plan resolution is shared, so it costs little, and it removes the biggest compliance risk. |
| Launch point | each character fires from its slot (Rev 1); a ground cannon behind the castle; a cannon on the front tower | **Tower cannon.** One launch point per side (PM request), aiming doesn't depend on the slot, flat shots still hit stone, and nothing passes visibly through its own wall. |
| Where characters stand | on top of the castle; in front of it; on the ground behind it | **Behind.** The castle acts as a shield (low shots hit stone, lobs hit characters), so there are two real tactical targets, and no falling-character physics is needed. |
| Hit detection | direct hits only; one uniform blast radius; Rebound-style "first living brick" damage | **Uniform 50 px blast.** One rule covers characters and blocks, and aiming matters. Position-independent damage would make aiming at the castle pointless. |
| Destruction measure | count destroyed blocks; HP-based % | **HP-based.** Every hit visibly moves the bar, and it's one formula. |
| Repair | +25 HP per block (Rev 1); restore one destroyed block; a fixed HP pool | **Fixed 75 HP pool to damaged blocks.** Easy to explain ("5 points back on the bar"), can't outpace attacks, and gaps stay open. |
| Cooldown counting | "next usable round" number; a ticking counter | **Ticking counter, ticked only at ROUND_START.** Familiar to students; it ticks in one place, so there are no off-by-one special cases. |
| AI aiming | brute-force search; closed-form formula + angle/power noise; closed-form + target-offset noise (Rebound) | **Formula + angle/power noise**, with Hard checking up to 5 angles by simulation. Offset noise also works but needs ±250 px on Easy to matter (review §3.5). |
| AI technique | rules + noise; neural network (Rebound) | **Rules + noise.** Explainable, testable and dependency-free. |
| Speed per power | 9 (Rev 1); 7 | **7.** From the tower cannon, with 9 the castle can be hit at 30°–60° only within 10–13 power values (45–60), and characters with 56–68. With 7 the castle windows are 13–18 values wide (57–78), and characters are hit with 72–87, so each power step matters less. |
| Constants location | a `config.py`; constants at the top of each module | **Per module.** Keeps us at five modules, and each number sits next to the code that uses it. |

---

## 13. Open questions for the PM and the instructor

**Instructor**
- **Q1 — Rubric details, due dates and example formulas.** Please confirm the §8 and §9 mapping
  against the actual rubric. Please share the course's example damage and EXP formulas, if any;
  we will match them exactly (§4.8). The milestone due dates decide what can be dropped if time
  runs short.
- **Q2 — Graders' Python version and OS.** This decides the pinned Pygame version and the install
  instructions.
- **Q3 — Decisions on C1–C7 (§10.1).** C1 (simultaneous turns), C2 (castle win, Draw) and C7
  (round limit) matter most. C1 and C2 have switches (§2.3), but the default affects the tests and
  the report. For C1, please also say what "alternating turns" means: does each *side* act in turn
  (our switch), or does each *character* act in turn (a different design)?
- **Q4 — Reference projects.** Is citing a public MIT-licensed repository (Rebound) as an *idea*
  reference acceptable under the course's academic-integrity policy, given that no code or assets
  are used? (Review §6.)
- **Q5 — Report format.** Is there a report template? Are screenshots and a demo video required,
  and what length and format for the video?

**PM**
- **Q6 — M1 scope.** Approve the alternating-shot hot-seat prototype, the tower-top cannons and
  the fixed 30 block damage for M1.
- **Q7 — Turn-mode switch.** Approve building `TURN_MODE` in M2 by default (recommended), or only
  if the instructor requires alternating turns.
- **Q8 — Rebalanced rules.** Approve the 75 HP Repair pool, the revised EXP table and the new
  AI noise table as starting values.

---

## 14. Process log

### Revision 1 (M0, 2026-11-19 04:22–04:35 UTC)
The first design draft, reviewed by an independent reviewer agent. The fixes from that review are
kept in this revision: a level-up can't revive a dead character, direct character hits trigger the
explosion rule, and the AI-vs-AI test was rewritten so it can fail. Rev 1's physics checks used
launch points at the character slots and `SPEED_PER_POWER = 9`. They are superseded by the
Revision 2 checks below.

### Revision 2 (this document)
- **Start:** 2026-11-18T21:11:34-08:00 (2026-11-19T05:11:35Z).
  **End:** 2026-11-18T21:51-08:00 (2026-11-19T05:51Z), when the documents were finished; the commit
  follows straight after.
- **Human intervention:** none during the work. Two automatic events: the first full clone of
  Rebound failed mid-download (network), so it was redone as a shallow clone; and the permission
  policy blocked running Rebound code (not retried).
- **Rebound study:** shallow clone into a temporary folder outside the repository (files over
  100 KB skipped). Core source, docs and the physics and difficulty tests read in full. Findings
  in `docs/Rebound_reference_review.md`. **No Rebound code was executed:** running downloaded code
  was blocked by the session's permission policy and was not retried. No Rebound code or assets
  were copied.
- **Checks performed (throwaway Python scripts, standard library only, not committed).** They
  simulated the §4.6 physics from the tower cannons against the §4.5 castle and the §1.4 character
  slots:
  - `SPEED_PER_POWER` 9 vs 7. With 9, the castle-hit windows at 30°/45°/60° are 45–57, 45–54 and
    51–60, and character lobs need 56–68. With 7, they are 57–74, 58–70 and 66–78, and lobs need
    72–87. Chose 7: the windows are wider, so aiming is less twitchy.
  - Default 45° / power 50 lands at x ≈ 785, about 100 px short of the enemy castle (x = 888).
  - Castle-hit power windows: 5° → 75–100, 15° → 64–95, 30° → 57–74, 45° → 58–70, 60° → 66–78,
    70° → 78–92.
  - Character lobs at 45–60°: powers 72–82 (near slot), 75–85 (middle), 78–87 (far).
  - The shield works: of 2,366 shots at 30° or lower, 88 (≈ 4 %) reach a character directly. All
    of them are in a narrow band of 15–30° high-power shots.
  - A 50 px blast on an intact castle hits 2–6 blocks: mean 3.7; 3–4 blocks in 77 % of hits.
  - Useful flights last 46–218 frames. The highest point of useful shots up to 60° is y = 47
    (on screen).
  - Largest move per step of a useful shot: 13.1 px. The energy bound for any shot: 13.2 px.
    Both are below the 28 px target width.
  - Closed-form aim: within 17 px of the target (mean 12 px) under the step simulation.
  - M1 (30 damage per block): a median of 10 hits to reach 60 % (9–13 for the 10th–90th
    percentile, 300 simulated games).
  - AI hit rates: Rev 1's noise table gave Hard 98 % character hits. Two retuned tables were
    tried, then the chosen ±10°/±14, ±6°/±9, ±3°/±5 (results in §6.3). Rebound-style target-offset
    noise was evaluated as well (review §3.5).
- **Independent review:** a fresh reviewer agent read both documents against the PM's requirements
  and re-ran the physics with its own script. Every number matched. It reported 6 must-fix and
  9 nice-to-have items.
  - **Applied:**
    - the overclaim that both deviations "can be switched off" (added C7, reworked the tie-break);
    - a per-team `start_turn` so alternating mode clears Defend at the right moment;
    - cannons that don't reveal hidden aim;
    - the AI's aim points, no-solution fallbacks and `choose_team`;
    - one mislabelled Rebound claim (the shield duration);
    - EXP edge cases; event draining via `take_events()`; a test that could never fail;
    - number inconsistencies; small missing rules; constructor flags for testability; risk R11.
  - **Not applied:** two of its citation "corrections". Re-checking the source showed the original
    line ranges were right.
- **Files changed:** `docs/M0_design.md` (this revision), `docs/Rebound_reference_review.md`
  (new). No game code.
- **No unit tests:** there is still no code to test in M0.

### M1 implementation notes (where the code departs from this document)
All physics constants, the castle layout and the 50 px blast are implemented exactly as written.
The M1 block damage was 30 as written, then raised to 50 in M1.1 (see below). Departures, each
found while building or running M1:
- **Block colours:** §11 asked for three HP bands. In play, a single hit (30 damage → 70 HP)
  didn't change a block's look, so blocks now darken in proportion to their HP (100 % → 40 % of
  the colour). Every hit is visible. The planned crack lines stay in M4.
- **Fonts:** `pygame.font.SysFont` crashed at start-up on the development Windows machine (Pygame
  2.6.1 hit a non-text value while reading the Windows font registry). `main.py` uses Pygame's
  built-in font (`pygame.font.Font(None, size)`) instead.
- **SPACE must be released between shots:** arrow keys repeat while held, so a held SPACE could
  have fired the next player's cannon as soon as their turn began. This is an input rule only.
- **`Battle.simulate_impact` deferred to M3:** in M1 only tests would call it, and the tests now
  drive real shots through `fire()` and `update()`. It will be added when the Hard AI needs it.
- **Draw rule present but unreachable in M1:** `Battle.check_winner()` checks both castles and
  returns `"draw"` if both have fallen (tested directly). An M1 shot damages only one castle, so it
  can't happen in play yet.

### M1.1 notes (after human acceptance testing)
- **Aiming and restart failed for the human tester. Root cause: a Chinese input method (IME).**
  This machine's default input method is a Chinese IME. Pygame starts in "text input" mode, so
  key presses go through the IME. Reproduced with real OS keystrokes:
  - R never reached the game: the IME started composing "r".
  - While it was composing, the IME also took the arrow keys (choosing a candidate) and SPACE
    (committing a Chinese character), so aiming and firing stopped working.
  - The earlier automated M1 check posted key events straight into Pygame's queue, which
    bypasses the IME, so it couldn't see this.

  **Fix:** `main.open_window()` calls `pygame.key.stop_text_input()`. Regression test:
  `tests/test_main.py` checks through SDL that text input is off after the window opens. The
  game's own key handling and restart logic were correct; tests confirm both.
- **Pacing: `SHOT_BLOCK_DAMAGE` 30 → 50** (block HP 100, blast 50 px and the 60 % loss line
  unchanged). Two hits now destroy a block.

  Simulated with the real `battle.py`, counting shots by the winning side to bring the enemy
  castle to 60 % (the full match is about twice as many turns; people also need a few extra
  ranging shots at the start):

  | Damage | Expert (best shot each turn) | Skilled (±2°/±3 power) | Casual (±4°/±6 power) |
  |---|---|---|---|
  | 30 | 7 | median 10 (9–12) | median 15 (10–21) |
  | 40 | 6 | median 8 (6–10) | median 10 (6–22) |
  | 50 | 4 | median 6 (5–8) | median 8 (5–17) |
- **Implications:**
  - Shorter matches make the left side's first-move advantage count for more. Watch for it in
    playtests.
  - The M2 character values (§3.2, §4.3: Knight and Archer deal 30 per block) would bring back
    the slow pacing. M2 must rescale them, for example with a higher `BLOCK_DAMAGE_MULT` or the
    50-damage baseline, and re-run this table.

### M2.1 notes (character system)
`characters.py` implements the §3.1–§3.5 attributes, the cooldown rule and the EXP rules exactly
(threshold `30 × level`, +10 max HP / +10 HP / +3 ATK / +1 DEF, maximum level 5, nothing for a
defeated character). EXP lasts one match because each match creates new character objects.

**Departures from §5.2, as the M2.1 brief asked:**
- `calculate_damage(attack, defense, defending)` and `take_hit(attacker)` have no multiplier or
  ignore-DEF parameters yet. Those exist only for Archer's Power Shot and arrive with the
  specials in M2.2.
- `use_special()` takes no team argument and only returns a description of the ability. The
  effects (and the team argument) come in M2.2.
- Deferred until something uses them:
  - `hp_ratio()` (M3 AI, HP bars);
  - `block_damage()` and `BLOCK_DAMAGE_MULT` (when characters fire the cannon);
  - `slot_x` (drawing);
  - `ARCHETYPES` (team selection);
  - the Power Shot constants.
- Added: `exp_to_next_level()`. Also, `take_damage` and `gain_exp` reject negative amounts with
  `ValueError`.

**Gap in this document, decided here:** §3.5 says EXP "is no longer added" at Level 5, but not
what happens to EXP left over when an award reaches Level 5. Decision: the leftover is discarded
and `exp` stays 0 at Level 5.

**Open conflict, not changed in M2.1:** §3.2 and §4.3 give Level-1 block damage of 30 (Knight,
Archer), but M1.1 raised the baseline to 50 because 30 made matches too long. This has to be
settled in M2.2/M2.3, when characters start firing the cannon.

**Damage formula and the course's example:** the course's example formula still isn't available
to us (§13, Q1), so we can't state the exact difference. Ours is `ATK − DEF`, minimum 1; when
the target is defending, the result is halved (rounded down), still minimum 1. The points most
likely to differ from a course example:
1. the minimum of 1 damage;
2. halving after DEF rather than before;
3. rounding down to whole numbers.
Each would be a one-line change in `calculate_damage`.
