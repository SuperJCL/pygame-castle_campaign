# Castle Siege — M0 Requirements and Architecture

Status: **Revision 3 (M2.3), updated for M3.4-B.** This is the living design document. The game is
implemented up to M3.4-B (Player vs AI, two-player hot seat, the M3.2 balance numbers, the M3.3
match flow, the M3.4-A redesign: elimination-only victory and deployable cover, and M3.4-B: the
cover placement screen and a cover-aware computer opponent). Revision 3's final decisions and the
M3.2 / M3.3 / M3.4 changes, just below, override anything older in this document; **where they
disagree, the M3.4-B block wins, then M3.4-A.** The AI that was built differs from the plan in
§6.3; see §14, "M3.1 notes" and "M3.4-B notes". The course-compliance checklist is
`docs/M3.3_course_compliance.md` (updated for M3.4-B).

### Revision 3 — final decisions (made by the PM and the user in M2.3)
- **Alternating turns are the final design. Simultaneous turns are cancelled.** The left team
  acts, then the right team; on its turn a team picks one living character and one action.
  There is no simultaneous planning, hidden action submission or simultaneous firing. This also
  makes us compliant with the course's turn rule (§10, C1).
  - §2.2 (the simultaneous round flow), the `TURN_MODE` switch, `ActionPlan` / `submit_plan`, the
    hidden-plan rule (§2.4 rule 7) and the PvP HANDOVER cover screen are **not built**. They are
    kept below only as a record.
- **Team sizes:** 1v1, 2v2 or 3v3. That is characters per team, not players. Each team has
  different roles, and both teams have the same size (a rule of the selection screen; the engine
  itself allows unequal teams).
- **Modes:** Player vs AI is the primary, course-required mode (built in M3.1; the default on
  the selection screen): the human plays LEFT, the computer picks and plays RIGHT. Local
  two-player hot seat (M2.3) stays as an additional mode.
- **Victory:** defeating every enemy character wins. A 60 % destroyed enemy castle also wins (our
  extra rule), and it can be switched off (`castle_loss_enabled=False`) if the instructor requires
  elimination only. *Superseded in M3.4-A: only elimination wins; the castle rule and
  `castle_loss_enabled` are gone.*

### M3.2 — rule changes (chosen with the balance benchmark; see docs/M3.2_balance_report.md)
- **Castle Guard:** while one of a team's characters is defending (Defend or Rally), enemy shots
  do half damage to that team's castle blocks, rounded down (50 → 25, 60 → 30, 75 → 37). It ends
  with the Defend, at the team's next turn (`battle.CASTLE_GUARD_PERCENT = 50`).
- **Engineer Repair:** up to **150** castle HP per use (was 75); cooldown 4, no revived blocks,
  no block above 100 HP (`Engineer.REPAIR_POOL = 150`).
- **Kept:** the 60 % castle threshold, character Defend (half damage, minimum 1), the cooldowns,
  one action per team turn, the stats and the physics.
- Human play-testing of these rules is still pending.

### M3.3 — final game rules and flow
- **Round limit (our design rule, not an instructor number):** a team match ends after
  `ROUND_LIMIT = 30` complete rounds (both teams have acted, whichever side started). Ordinary
  elimination and castle wins are checked first, even on the last turn. Then the tie-breakers
  decide (§4.7); if all are equal, it is a draw. The M1 duel has no limit.
- **First mover:** `Battle(first_side=...)` / `Battle.reset(first_side=...)`. LEFT starts the first
  match. Each rematch (button or R) swaps the first mover; new teams start with LEFT again. The M1
  duel always starts with LEFT. A round starts whenever the first mover is to act, so cooldowns
  still tick once per round, and Defend still ends at the defending team's next turn.
- **Castle Guard indicator:** a blue outline on the guarded castle's blocks and a GUARDED badge.
  It is drawn straight from `Battle.castle_guarded(side)` every frame.
- **Result screen:** the winner or DRAW, the reason (elimination, castle, round-limit tie-break
  and its rule, or a true draw) and the rounds played. The HUD shows "Round N / 30".

### M3.4-A — character elimination and deployable cover (combat foundation)
The instructor's core requirement is that **the only normal victory is defeating every enemy
character**. M3.4 redesigns the battlefield around it. M3.4-A builds the rules; the placement
screen and the AI redesign are M3.4-B, the run-to-cannon animation M3.4-C.
- **Victory:** elimination only (`Team.has_lost`, `Battle.check_winner`). No castle percentage
  or block HP can win. A match that reaches the end of round 30 (complete rounds, as in M3.3)
  without an elimination is a **draw** (`end_reason = "timeout"`), a custom safety rule. An
  elimination on the last turn still wins. The M3.3 tie-breakers (§4.7) are removed: HP and cover
  never pick a winner.
- **Cover replaces the fixed castle:** each team places 0–6 blocks (100 HP) on 8 fixed slots
  between its characters and its cannon (4 columns × 2 rows; a raised block needs a block under
  it). `castle.layout_problem()` checks a layout; `Battle(roster, layouts=...)` builds each team's
  `Castle` from its layout, and a rematch rebuilds the same layout at full HP. Until the
  placement screen exists, both teams use `DEFAULT_LAYOUT` (slots 0–5). *(M3.4-B: each team now
  places its own cover; `DEFAULT_LAYOUT` is where the placement screen starts.)*
- **One shared cannon per team**, on the ground in front of the cover (pivots (340, 544) and
  (940, 544)). The acting character's stats set the damage, as before.
- **Collision:** each physics step checks the whole segment the shot moved along
  (`battle.segment_entry`), so nothing is skipped; the shot explodes at the exact point where it
  first touched an enemy block, an enemy character or the ground.
- **Cover rule (read once at impact, before any damage):** a directly hit character takes normal
  damage (Defend still halves it). Any other enemy character within 50 px takes normal damage
  unless a standing block of its team lies on the straight line from the explosion to its centre;
  then the block absorbs all of it. A block destroyed by the same explosion still shields against
  that explosion. Blocks within 50 px take block damage once.
- **Kept:** turns, first-mover alternation, cooldowns, Defend, Rally, Power Shot, EXP, levels,
  physics, the stats, Castle Guard 50 % (now called **Cover Guard** on screen) and Repair 150
  (damaged standing blocks only; unavailable when there is nothing to repair).
- **Removed:** the M1 cannon duel (in git: M1.1 at `2ccb68c`, last present at `86b90fa`), the 60 % castle rule, the
  round-limit tie-breakers, and the castle-rules benchmark script (the M3.2 results remain
  reproducible at commit `86b90fa`).
- Details, coordinates and the reasons are in §14, "M3.4-A notes". Human play-testing is pending.

### M3.4-B — cover placement screen and cover-aware AI
- **Setup flow:** Player vs AI: select → LEFT cover → battle (the computer places RIGHT's cover).
  Two players: select → LEFT cover → RIGHT cover → battle. **Back** goes one step back (RIGHT's
  screen → LEFT's → team selection) and keeps the teams and both layouts. Rematch keeps the teams,
  both layouts, the computer and its level, and alternates the first mover (M3.3); every block
  starts at full HP again. The computer's layout is chosen once per new series, never on a rematch.
- **Placement screen** (`Game` state `"cover"`, `Game.placing`): one team's side of the field,
  drawn exactly as in battle: its characters, cannon and 8 slots. A click on an empty slot places a
  block (`castle.place_block`), a click on a block removes it (`castle.remove_block`); removing a
  lower block also removes the block on top, and the status line says so. "Blocks: n / 6", a short
  explanation, a legend (block / empty slot / no block allowed now), **Back** and **Confirm**.
  Enter = Confirm, Backspace = Back. 0–6 blocks may be confirmed. The other team's cover is hidden
  while a team places. The screen starts from `DEFAULT_LAYOUT`.
- **One rule check:** `castle.layout_problem()` is the only place that decides legality.
  `place_block` asks it; `remove_block` only removes blocks it would call floating
  (`castle.floating_blocks`, which `layout_problem` uses too); the screen shows a slot as
  placeable by asking `place_block`; Confirm asks `layout_problem` again; `Castle` refuses an
  illegal layout. Layouts are tuples, so the two teams can never share one mutable list.
- **The computer's cover** (`AIController.choose_layout`): a two-block tower next to its characters
  (slots 0 and 4), then 4 more blocks, one at a time, on random slots that `place_block` allows.
  Always the full 6-block budget, never more; six possible layouts; repeatable with a seed; it
  never looks at the player's cover.
- **Cover-aware aiming** (`ai.find_routes`, `cover_value`, `shot_value`, `rank_targets`): each
  scanned aim scores its character damage plus COVER_WEIGHT (0.5) × how far it opens a shot at a
  living enemy. A *route* is a scanned aim that ends on enemy blocks with a living enemy behind
  them on the same path (`Battle.path_contacts`, a read-only trace that uses the real flight and
  collision code). A shot that removes a share of the HP of the blocks in a route's way earns that
  share × the value of a direct hit on the character behind. Blocks in nobody's way earn nothing.
  Each aim is then rated by the average score of the aims within the AI's own power error, so
  narrow gaps over cover count for less and breaking cover becomes the better plan when a
  character is protected. Plans carry a goal: "damage", "cover", "defend" or "repair".
- **Unchanged:** physics, collision, the cover rule, HP, skills, cooldowns, Defend, Cover Guard 50 %,
  Repair 150, Power Shot, elimination-only victory and the round-30 timeout draw. No new combat
  mechanics.
- **Code layout:** `drawing.py` now holds the shared look (colours, text, figures, buttons), moved
  out of `main.py` unchanged.
- Details are in §14, "M3.4-B notes". Human play-testing is pending.

Revision 2's original header: *draft for project-manager review; M0 design only.*

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
Archer, Engineer). The teams take turns: the left team, then the right team. On its turn a team
picks **one** living character and **one** action (Attack, Defend or Special). An Attack fires
the team's cannon; the shot flies, then explodes. *(Revision 2 resolved both sides' actions at
the same time; that was cancelled in M2.3.)*

The acting character *operates* its team's cannon: the character's stats decide the damage.
The cannon itself is scenery. It cannot be damaged.

### 1.2 How you win
A team **loses** at the end of a round if either:
- its castle is **≥ 60 % destroyed**, or
- **all** of its characters are defeated (HP 0).

If both teams lose at the same time, the match is a **Draw**. With alternating turns this can't
happen during play, because only one team acts at a time.
- **Planned, not built yet:** after round 30 (`ROUND_LIMIT`), the tie-break in §4.7 decides.
- **Still needs instructor approval:** the castle loss and the round limit differ from the course
  specification (§10: C2, C7). Elimination-only victory is a switch (`castle_loss_enabled`).

### 1.3 Modes, by milestone
- **M1 prototype:** one keyboard controls both cannons, and shots alternate left, right, left…
  No characters. It is still available as the "Classic cannon duel" button.
- **M2.3 (built):** local two-player hot seat with full combat rules. Two people share the mouse
  and keyboard and take turns. No cover screen is needed, because nothing is hidden with
  alternating turns.
- **M3:** Player vs AI (Easy / Normal / Hard), the required final mode, next to the hot-seat mode.

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
M1:    BATTLE (press R to restart)
M2.3:  "select" ──► "battle" ──► "result" ──► Rematch ──► "battle"
       (size 1-3,     (turns)      (winner)  └► Change teams ──► "select"
        both rosters)
       The "select" screen also starts the classic M1 cannon duel.
M3:    the same, plus a choice of mode (hot seat / vs AI) and AI difficulty on "select".
M3.4-B: "select" ──► "cover" (LEFT) ──► "cover" (RIGHT, two players only) ──► "battle"
        Back:  RIGHT's "cover" ──► LEFT's "cover" ──► "select"   (nothing chosen is lost)
        The M1 duel was removed in M3.4-A.
```

### 2.2 Round flow — simultaneous mode (CANCELLED in M2.3; kept only as a record, see §2.3)
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

### 2.3 Alternating turns (the final design, built in M2.2) and elimination-only victory
**Alternating turns.** Since M2.3 this is the only mode. There is no `TURN_MODE` switch: the
battle simply alternates. The rules below are implemented as written, except for the
`TURN_MODE` and `turn_mode` references, which were never built. Originally this was specified
as the fallback in case the instructor required players to act one after another (§10, C1).
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
| 2 | What does Defend protect? | Defend: the acting character takes 50 % damage until its team's next turn starts. Knight Rally: every living ally, **including the Knight itself**. *Since M3.2 (Castle Guard):* while any of its characters is defending, the team's castle blocks also take half damage from enemy shots, rounded down. (Until M3.2: characters only, never castles.) | The old worry was that a team could stall the castle win by defending. Castle Guard halves only one enemy action and costs the team its own shot, so it can't: in 10,560 benchmark matches none reached the round cap (docs/M3.2_balance_report.md). |
| 3 | How do explosions affect characters and blocks? | One explosion per shot, when the shot enters an enemy character's rectangle or an enemy block's rectangle, or reaches the ground. Every **enemy** character and every **enemy** block whose centre is within **50 px** of the impact point is damaged once (§4.1, §4.3). No friendly fire: shots pass through their own team's castle and characters. Projectiles never collide with each other. Defeated characters are removed from the field: they no longer block or trigger shots. In M1 there are only blocks. | One rule covers every target, so it's easy to explain and test. |
| 4 | May the same character act every round? | **Yes.** Any living character may act in any round. | Simplest rule, and safe for the course's "AI defends below 50 % HP" requirement. The other characters still matter: their specials have separate cooldowns, they add HP, and they are targets. Rejected: "no acting two rounds in a row", because it can stop the AI from defending its weakest character. |
| 5 | Repair: damaged vs destroyed blocks? | Damaged blocks that still stand regain HP, up to their maximum. **Destroyed blocks (0 HP) never come back.** Pool: 150 HP per use (75 until M3.2), most damaged block first (§3.4). | Gaps in the wall stay open, so repairs can't undo the attacker's progress completely. |
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
| Special | **Rally:** every living ally, the Knight included, defends until the team's next turn. Does not fire. | **Power Shot:** an aimed cannon shot with ×1.5 damage that ignores DEF. | **Repair:** restores up to 150 HP to the castle (§3.4; 75 until M3.2). Does not fire. |
| Special cooldown | 4 | 3 | 4 |
| Special needs aim? | no | yes | no |

**Team selection:** a team picks 1–3 **different** archetypes. Duplicates are not allowed.

### 3.3 Cooldown rule
A special used in round *r* can be used again in round *r + cooldown*. Every special starts
ready. Details and an example: §2.4 rule 6 and §2.5.

### 3.4 Engineer Repair (rebalanced)
**Rule:** Repair restores **at most 150 HP in total** (10 % of the castle's 1500 HP; it was 75
until M3.2). The HP goes to damaged blocks that are still standing, **most damaged first** (ties:
leftmost, then top first). No block goes above 100 HP. Destroyed blocks stay destroyed. Any HP
left over is lost. Cooldown 4.

```
pool = 150          # Engineer.REPAIR_POOL (75 until M3.2)
for block in surviving blocks, sorted by hp (lowest first):
    gain = min(pool, block.max_hp - block.hp)
    block.hp += gain ;  pool -= gain
```
Examples with the old 75 pool (the unit tests still check them through `Castle.repair(75)`):
block HP `[100, 40, 70, 0]` → `[100, 100, 85, 0]` (60 + 15 = 75 used; the destroyed block is
untouched). Block HP `[90, 95]` → `[100, 100]` (15 used, 60 lost). With 150: `[20, 40, 70, 0]` →
`[100, 100, 80, 0]` (80 + 60 + 10 = 150).

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
- *M3.2:* the benchmark showed exactly that. At 75, repairing instead of attacking cost 22 ± 8
  points of win rate on Hard. The pool was raised to 150: at most 10 destruction points back per
  use (≤ 2.5 per round), still less than the 3–4 enemy shots of a cooldown period. Repairing is
  now about even with attacking at the moment it is possible (docs/M3.2_balance_report.md).

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
- *Since M3.2:* while any character of a team is defending, enemy shots do half damage to that
  team's castle blocks, rounded down (**Castle Guard**, §2.4 rule 2, §4.3). Before M3.2, Defend
  never reduced castle damage.

### 4.3 Damage to castle blocks (one explosion)
Each shot deals a fixed amount to every enemy block in the blast (since M2.2; it no longer
depends on ATK or level):

| Shot | Damage per block |
|---|---|
| M1 cannon duel (no characters) | 50 (`SHOT_BLOCK_DAMAGE`; 30 until M1.1) |
| Knight Attack | 50 |
| Archer Attack | 50 |
| Engineer Attack | 60 |
| Archer Power Shot | 75 |

Blocks have no DEF. *Since M3.2,* each value is halved and rounded down (25 / 25 / 30 / 37) while
the target team has a defending character (Castle Guard, `CASTLE_GUARD_PERCENT`); never in the
M1 duel. (Revision 2 used `int(atk × multiplier ×
BLOCK_DAMAGE_MULT)`, which gave a Knight 30 per block. That brought back the slow pacing
M1.1 fixed, so M2.2 replaced it with these values.)

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

### 4.7 Round-limit tie-break (built in M3.3, removed in M3.4-A)
*Superseded in M3.4-A: a match that reaches the end of round 30 without an elimination is a
draw (a timeout). There are no tie-breakers any more. The M3.3 rule below is kept as a record.*

A team match ends after `ROUND_LIMIT` (30) **complete** rounds. A round is complete once both
teams have acted, whichever side started, so a match never ends after only the first team's turn
of round 30. Ordinary wins (elimination, castle) are checked first, after every action, so a win
on the very last turn beats the tie-break. If nobody has won, compare in order
(`Battle.tie_break`):
1. more **living characters** wins;
2. else a higher **share of character HP** wins: the team's total HP ÷ its total *current* max HP,
   defeated characters included (their HP counts 0, their max HP counts in full);
3. else more **castle HP left**, as a share of the castle's max HP, wins (also compared when
   castle loss is switched off);
4. else it is a **draw**.

Shares are compared exactly by cross-multiplying (a/b > c/d exactly when a·d > c·b), so
floating-point rounding can never decide a match. Putting the characters first matches the
course's elimination victory. This is our design rule; the number 30 is not an instructor
requirement (§10.1, C7). *Until M3.3 this section described a draft: total HP of living
characters only, and the castle step skipped when castle loss was off.*

### 4.8 Alignment with the course's examples (damage and EXP)
**Damage (updated in M2.2):** the instructor's reference formula is
*Damage = ATK − DEF + a random integer from −5 to 10*. Ours is deliberately **deterministic**:
*ATK − DEF*, minimum 1, halved when defending (Archer's Power Shot: ATK × 1.5, ignoring DEF).
- *Why:* the same hit always does the same damage, so the tests can check exact numbers.
- *Effect:* the reference formula does 2.5 more damage per hit on average, and varies by up to
  15 points between hits.
- *To match it:* add the random term inside `calculate_damage` (one line), with a seeded
  random generator for the tests.
- The course rule "Defend reduces incoming damage by 50 %" is applied after DEF, to the
  defending character only (§10, C5).

What still isn't known (§13, Q1):
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
| `main.py` | M1, grows each milestone | Pygame window, screens, input, all drawing, sound | **yes** |
| `drawing.py` | M3.4-B | Colours, text, character figures, `Button` (moved out of `main.py`) | **yes** (only these two) |
| `characters.py` | M2 | `calculate_damage`, `Character`, `Knight`, `Archer`, `Engineer`, `ARCHETYPES` | no |
| `ai.py` | M3.1 | `DIFFICULTY_SETTINGS`, `Plan`, `AIController`, `imagine` (planned: `DIFFICULTY`, `aim_power`) | no |

```
main.py ──imports──► battle.py, castle.py         (M1)
                 ──► characters.py (M2), ai.py (M3)
ai.py   ──imports──► battle.py, castle.py, characters.py (M3.1: it plays on copies of a Battle)
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

## 6. Player vs AI and local PvP

*M3.1 built Player vs AI differently from this section's plan.* There is no `submit_plan` or
`team.ai`: the `AIController` calls `Battle.perform_action()` on its turn, exactly like the
buttons, and `main.py` holds the controller (`Game.ai`). The AI actually built is described in
§14, "M3.1 notes"; §6.3 below is the original plan, kept as a record.

### 6.1 One rule: the battle doesn't know who is playing
`Battle` only ever receives `ActionPlan`s through `submit_plan(side, plan)`. Each `Team` has an
`ai` field:
- `team.ai` is an `AIController` → at the start of PLANNING, `main.py` calls
  `battle.submit_plan(side, team.ai.choose_plan(battle, side))`, before the human acts.
- `team.ai is None` → `main.py` collects that side's plan from keyboard and mouse.

### 6.2 What PvP needs (UI only, no battle changes)
*Done in M2.3, without the cover screen.* With alternating turns nothing is hidden, so local
PvP is simply the hot-seat game: the selection screen picks both teams, and the players take
turns. Items 2 and 3 below were written for simultaneous turns.
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
| Castle Guard (M3.2) | `Battle.castle_guarded`, `CASTLE_GUARD_PERCENT`, `Battle._end_shot` | M3.2 | test_combat `CastleGuardTest` (Defend and Rally, expiry, rounding, only the defending team, can save a castle, covers the defender's last shot, not in the M1 duel); test_main (log line) |
| Special ability + cooldown | `use_special` overrides, `start_cooldown` / `tick_cooldown` | M2 | test_characters (round r → r + cooldown), test_battle |
| HP, ATK, DEF, EXP, Level | `Character` attributes, `gain_exp` | M2 | test_characters (thresholds, stat gains, dead earn nothing) |
| OOP inheritance and encapsulation | `Character` → `Knight / Archer / Engineer`; private state | M2 | code review, class diagram (M5) |
| Character selection | `TEAM_SELECT` screen, `ARCHETYPES`, `AIController.pick_team` | M2 (AI's pick in M3.1) | test_main; test_ai (`pick_team(size)` returns `size` different roles) |
| HP bars, action buttons, combat log, result screen | `Game.draw_*`, `Button`, `Battle.log`, `RESULT` state | M2 (basic), M4 (polish) | manual checklist; test_battle (log entries) |
| Alternating turns (simultaneous resolution cancelled in M2.3) | `Battle._finish_turn`, `_start_round`, `_start_turn` | M2.2 | test_combat (turn order, cooldowns once per round, Defend covers exactly one enemy turn) |
| Elimination victory (the only victory since M3.4-A); timeout Draw | `Team.has_lost`, `Battle.check_winner`, `ROUND_LIMIT` | M2, M3.3, M3.4-A | test_combat VictoryTest (destroying every block does not win), RoundLimitTest (both sides first, a timeout is a draw even when one team is far ahead, a last-turn elimination beats the timeout) |
| Deployable cover, collision along the path, cover rule | `castle.layout_problem`, `slot_position`, `Castle(side, layout)`, `Battle(layouts=...)`, `battle.segment_entry`, `Team.is_covered`, `Battle._end_shot` | M3.4-A | test_castle LayoutTest; test_battle SegmentEntryTest, ShotTest (mirror images); test_combat CoverTest (intact / destroyed / same-explosion cover, hits from above, every legal layout leaves every character reachable) |
| Cover placement screen and setup flow | `castle.place_block`, `remove_block`; `main.CoverSetup`, `Game.begin_cover`, `click_cover`, `confirm_cover`, `back_from_cover`, `draw_cover_screen` | M3.4-B | test_castle PlacementTest (every click on every legal layout stays legal); test_main CoverPlacementScreenTest, SetupFlowTest (PvAI, PvP, Back, team changes, rematch) |
| AI cover placement and cover-aware aiming | `AIController.choose_layout`; `Battle.path_contacts`; `ai.find_routes`, `cover_value`, `shot_value`, `rank_targets`, `expected_score` | M3.4-B | test_ai LayoutChoiceTest, CoverAwarenessTest, DecisionTimeTest; test_battle PathContactsTest |
| Alternating first mover on rematch | `Battle(first_side=...)`, `Battle.reset(first_side=...)`, `Game.rematch` | M3.3 | test_combat FirstMoverTest (rounds, cooldowns, Defend / Rally with RIGHT first); test_main RematchAndFirstMoverTest (alternation, the AI moving first, PvP) |
| Castle Guard indicator, result screen | `Game.draw_castle_guard`, `guard_badge_rect`, `Game.result_reason`, `result_rounds` | M3.3 | test_main CastleGuardIndicatorTest, ResultReasonTest |
| Engineer Repair (capped) | `Castle.repair`, `Block.restore`, `Engineer.REPAIR_POOL` (150 since M3.2) | M2, M3.2 | test_castle (pool examples of §3.4, no revival, no overheal); test_combat and test_main (150 through the real battle and buttons) |
| Enemy AI, defensive preference below 50 % HP | `AIController.wants_to_defend`, `defensive_plan` | M3.1 | test_ai (seeded rate check: below half HP vs not; never two defensive turns in a row) |
| AI difficulty Easy / Normal / Hard | `ai.DIFFICULTY_SETTINGS` | M3.1 | test_ai (seeded: Hard hits more often than Easy; whole matches end at every size and level) |
| Player vs AI mode | `main.Game.ai`, `update_ai`, mode and difficulty buttons | M3.1 | test_main (PvAI selection and battle), scripted and real-input runs; human playtest pending |
| ~~AI never sees the hidden plan~~ | not needed: with alternating turns there are no hidden plans | — | — |
| Local PvP (hot seat) | `main.py` selection screen + alternating battle | M2.3 | test_main, human playtest |
| Team selection 1v1 / 2v2 / 3v3, HP bars, action buttons, combat log, result screen | `main.TeamSelection`, `Game` screens | M2.3 | test_main, human playtest |
| Background, sound, animations | drawing, `Battle.events` → sounds | M4 | manual checklist (silent fallback if the mixer fails) |
| Tests | `tests/` with `unittest` | M1–M5 | `python -m unittest discover tests` |
| Screenshots, documented algorithms, source code, report, demo video | `docs/report/`, README | M5 | rubric audit checklist |

---

## 10. Course compliance, design decisions and risks

### 10.1 Differences from the course specification (need instructor confirmation)
| # | Topic | Compliant? | Our design | If rejected |
|---|---|---|---|---|
| **C1** | Alternating turns | **Yes, since M2.3.** The teams act one after another, one character and one action per turn. (Revision 2 resolved both actions together; that was cancelled.) | — | If the course means that *every character* acts in turn, rather than one chosen character per team, that would need a change (Q3). |
| **C2** | Elimination victory | **Compliant since M3.4-A.** Defeating every enemy character is the only way to win; the 60 % castle loss is removed. A Draw remains possible only through the round limit (C7). | (Until M3.4-A we added a castle win; the PM removed it to meet the instructor's core requirement.) | — |
| **C3** | Attacks can miss | **Unknown.** The course may assume every Attack deals damage. | Misses are what make artillery a skill. | Add an assist mode (for example, Easy-only aim help). Not planned. |
| **C4** | "AI defends below 50 % HP" with a team | **Interpretation.** "HP" is ambiguous with several characters, and our defence is probabilistic: 40 / 50 / 60 % (Easy / Normal / Hard) when a character is below half HP, against 10 / 5 / 0 % otherwise (M3.1 table; the 50 / 70 / 85 % here before M3.3 was an outdated draft). | We use any living AI character below half HP as the trigger. | Set Defend chance to 100 % (one table row). |
| **C5** | "Defend reduces damage by 50 %" | **Interpretation.** Applied after DEF, minimum 1, to the defending character. *Since M3.2,* the team's blocks also take half damage while it defends (Castle Guard, called Cover Guard since M3.4, our addition). | — | Moving the halving before DEF is a one-line change; `CASTLE_GUARD_PERCENT = 0` turns Cover Guard off. |
| **C6** | Characters "attack" | **Interpretation.** Characters attack *through* their team's cannon; the actor's stats set the damage. Since M3.4-A the cannon stands on the ground in front of the team's cover; in M3.4-C the acting character will run to it and back (animation only). | One launch point per side (PM request) keeps aiming and the AI simple. | Fire from the actor's slot instead (the Rev 1 design). Needs re-tuning. |
| **C7** | Round limit | **Addition (built in M3.3; changed in M3.4-A).** The course doesn't mention one. A match that reaches the end of round 30 without an elimination is a Draw (a timeout); HP and cover never decide it. | It guarantees that every match ends, including AI-vs-AI test matches. | Raise `ROUND_LIMIT`. Removing it isn't recommended. |
| **C8** | Battlefield structures | **Addition (M3.4-A; placement screen M3.4-B).** Each team places up to 6 cover blocks on 8 fixed slots before the battle (the computer places its own with the same budget and rules). Blocks stop shots and shield characters from the blast; they never decide the winner. | Gives the artillery game a defensive choice while characters stay the only target that wins. | An empty layout (no blocks) plays as an open field. |

### 10.2 Design questions now decided (the PM may still override)
- **A1 Fewer than 3 characters:** allowed (1–3, as the course says). The AI matches the player's
  team size. No compensation bonus.
- **A2 Does Defend protect the castle?** Partly, since M3.2: Castle Guard halves block damage
  until the team's next turn (§2.4 rule 2). Before M3.2: no.
- **A3 Duplicate archetypes in a team?** Not allowed.
- **A4 May the same character act every round?** Yes (§2.4 rule 4).
- **A5 EXP and levels across matches:** reset every match. Carrying them over ("campaign") is out of scope.
- **A6 Assets:** shapes drawn in code until M4. In M4: sounds generated with the standard library,
  or CC0 files listed in `assets/CREDITS.md`. No assets from Rebound or any other project
  without a licence that allows it.

### 10.3 Implementation risks
- **R1 Physics tunnelling.** Prevented by the speed bound (§4.6), enforced by a unit test.
- **R2 AI strength.** Hard hits characters ~80 % of the time. Tune in M3 with the AI-vs-AI tests.
  Target: a Normal PvAI match lasts 8–15 rounds. *M3.1 measured (seeded, castle loss off):
  1v1 character hit rate Easy 23 %, Normal 46 %, Hard 66 %; 3v3 46 / 67 / 85 %. Hard beat Easy in
  67 of 72 AI-vs-AI matches. AI-vs-AI matches average only 4.8–7.7 rounds, because castle victory
  comes quickly (see docs/M3.1_balance_analysis.md), so the 8–15-round target isn't met.*
  *M3.2 measured (castle loss on, existing AI mirrors): 6–7.5 rounds on Normal and 4.7–5.3 on
  Hard with the new rules (+0.85 / +0.32 rounds). The target is still not met; a side moving
  first wins 59–66 % of mirror matches (docs/M3.2_balance_report.md).*
- **R3 `main.py` grows too large.** If it passes about 600 lines, split the drawing helpers into
  `ui.py` (a justified 6th module). *`main.py` is 862 lines after M3.1; the split is still a PM
  decision.*
- **R4 Floating blocks and cannon.** Without collapse physics, blocks and the cannon can float
  over destroyed blocks. Accepted and documented.
- **R5 Pygame availability.** Pygame isn't installed in this design environment. The M1 README
  must pin a version (for example `pygame==2.6.1`), and the logic tests must not import pygame.
  Q2 decides the version.
- **R6 Hot-seat fairness (PvP).** *No longer applies: alternating turns hide nothing.* Original
  text: the HANDOVER screen and the "cannons move only at resolution"
  rule (§2.4 rule 7) must hide Player 1's angle and power. A manual checklist item verifies it.
- **R7 Balance.** All numbers are first guesses. Tune constants, not code. *M3.2 tuned Defend
  (Castle Guard) and Repair (150) with a seeded benchmark; human play-testing is still pending.*
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
**Status: done in three steps, with alternating turns only.**
- **M2.1:** the character classes.
- **M2.2:** team combat in `battle.py`.
- **M2.3:** the playable hot-seat interface: team selection (1v1, 2v2, 3v3), characters on the
  battlefield with HP bars, cooldowns, Defend and defeat shown, the ATTACK / DEFEND / SPECIAL
  buttons, a combat log, and a result screen with Rematch and Change teams.

The `TURN_MODE` switch below was cancelled. The round limit and tie-break (§4.7) are still
open (see M3). The original plan follows.
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
**Status after M3.1:**
- **M3.1 (done, awaiting PM review and human playtesting):** `ai.py` with `AIController` and the
  Easy / Normal / Hard table; Player vs AI as the default mode on the selection screen (mode and
  difficulty buttons; the computer builds a legal RIGHT team of the same size); a preflight of
  the M2.3 abilities; a Defend / Repair balance analysis (analysis only).
- **M3.2 (done, PM-accepted; human playtesting pending):** a reproducible balance benchmark
  (`scripts/balance_benchmark.py`); Castle Guard and Repair 150 adopted; 60 % kept
  (`docs/M3.2_balance_report.md`).
- **M3.3 (done, awaiting PM review and human playtesting):** the 30-round limit and tie-break
  (§4.7); the first mover alternates on rematch (this answers the first-move advantage measured in
  M3.2 over a series of matches, not within one match); the Castle Guard indicator; the result
  screen's reason and rounds; the course-compliance checklist (`docs/M3.3_course_compliance.md`).
- **M3.4-A (done, PM-accepted):** elimination-only victory, timeout draw, deployable cover
  (layout model and validation, default layout), collision along the flight path, the cover rule,
  Cover Guard and Repair on blocks; the M1 duel and the castle benchmark removed.
- **M3.4-B (done, awaiting PM review; human play-testing pending):** the cover placement screen
  and setup flow (PvAI and PvP, Back, rematch), the computer's cover placement, cover-aware AI
  aiming, `drawing.py`.
- **Next:** M3.4-C (run-to-cannon animation), only after PM approval.

**Updated in M2.3.**
- **Required:** Player vs AI.
  - The AI chooses its team, then on each of its turns a character, an action and an aim.
  - It works through the same `Battle.perform_action()` the buttons use, so no combat rule is
    rewritten.
- **The selection screen** gains a mode choice (hot seat / vs AI) and the AI difficulty.
- **The round limit and tie-break (§4.7)** should be added here.
- **Not needed any more:** the HANDOVER screen (alternating turns hide nothing). The original plan
  follows.
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
- **Q3 — Decisions on C1–C7 (§10.1).** *C1 was settled in M2.3: alternating turns.* C2
  (castle win, Draw) and C7 (round limit) remain open. Original text: C1 (simultaneous turns),
  C2 (castle win, Draw) and C7
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
- **Q7 — Turn-mode switch.** *Settled in M2.3: no switch; alternating turns only.* Original text:
  approve building `TURN_MODE` in M2 by default (recommended), or only
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

### M2.2 notes (team combat in `battle.py`)
**What was built.** `Team` and one `Battle` engine with two modes:
- `Battle()` is the unchanged M1 cannon duel that `main.py` still uses;
- `Battle(roster=..., castle_loss_enabled=True)` adds team combat through
  `perform_action(slot, "attack" | "defend" | "special")`.

Turns still alternate (left, then right); the simultaneous mode isn't built yet. The physics,
cannon geometry and collision rules are unchanged. Explosions now also hit enemy characters
within 50 px, and a shot also explodes when it enters an enemy character's 28 × 44 rectangle.

**Exactly when Defend expires.** A team's Defend (and Rally) flags are cleared at the very start
of that team's next turn, so they protect against exactly one enemy action. Cooldowns tick once
per round, when the left side's turn begins. So a special used in round *r* is ready again in
round *r + cooldown*, for either side.

**Departures from this document:**
- **Castle damage** is a fixed value per role (§4.3): 50 / 50 / 60, and 75 for Power Shot.
  This replaces the `BLOCK_DAMAGE_MULT` formula and settles the open conflict from the M2.1
  notes. It doesn't grow with level.
- **Specials:** `use_special(team)` returns `(message, shot)`. Knight and Engineer apply their
  effect directly and return no shot; Archer returns a stronger `ShotDamage` for the battle to
  fire. `can_use_special(team)` is new; the Engineer overrides it, because Repair needs a
  damaged block. `ShotDamage` is a small new value class.
- **Actions:** `perform_action` replaces `ActionPlan` / `submit_plan` while turns alternate.
  `ActionPlan` will come with the simultaneous mode.
- **Slots:** slot 0 is the one nearest the team's own castle, so the left slots are x = 140,
  95, 50 (the mirror of the right slots 1140, 1185, 1230). §1.4 lists the same positions, in
  the opposite order on the left.
- **Not built yet:** the round limit and tie-break (§4.7, C7), the AI, and anything on screen.

**Balance at Level 1** (from the stats; worked out by hand):
- **Characters:** a hit deals 18–36 damage, so defeating one takes 3–8 hits. For example, an
  Archer needs 5 hits to beat a Knight, and a Knight needs 4 to beat an Archer. A Power Shot
  deals 60 to anyone.
- **Splash:** a blast can reach 2–3 characters standing next to each other.
- **Castle:** a 4-block tower hit deals 200 (Knight/Archer), 240 (Engineer) or 300 (Power
  Shot), so a castle still falls in about 4–6 good hits, as in M1.1.
- **Which victory comes first:** the castle is usually faster than wiping out a team. A team
  has 90–340 HP in total, and hitting characters needs harder lob shots.
- **Repair** (75 HP every 4 rounds) can't keep up with one hit (200+).
- **Risk:** if `castle_loss_enabled` is set to `False` (the course fallback, C2), matches will
  be much longer, and there is no round limit yet.

### M2.3 notes (playable hot-seat interface)
**Decisions:** see "Revision 3 — final decisions" at the top. Simultaneous turns are cancelled,
and alternating turns are final.

**Screens** (`main.Game.state`):
- `"select"`: team size and both rosters; also starts the classic M1 duel.
- `"battle"`
- `"result"`: Rematch and Change teams.

**Small classes:** `Button` and `TeamSelection`. `TeamSelection` holds the picks and draws nothing.

**Rules stay in the engine.** The interface asks the engine and never re-implements a rule:
- `Battle.why_not_allowed()` decides which buttons are greyed out and why;
- `Battle.perform_action()` performs every action;
- the event list fills the combat log.

**Character positions:** these come only from `Team.character_rect()` / `slot_center()`.

**Targeted engine changes, each with regression tests:**
- `Battle._why_not_allowed` → public `why_not_allowed`;
- `Character.special_blocked_reason(team)`: a clear reason, such as "Rally is recharging:
  ready in 2 rounds". The Engineer override adds "nothing to repair". `can_use_special` now
  uses it;
- `Team.character_rect(index)`, now also used by `character_at`;
- `characters.ARCHETYPES` and `SPECIAL_DESCRIPTION`, which are display data.

The physics, collision and damage rules are unchanged.

**Verification:**
- Unit tests drive the real click and key handlers.
- A scripted run of the unmodified `main.main()` passed all checks for 1v1, 2v2 and 3v3. The
  input was posted into Pygame's event queue, and the screenshots were inspected.
- Real OS mouse and keyboard input could **not** be tested this time: Windows refused the game
  window focus. The IME probe showed the game window's input method disabled. Human
  playtesting is still required.

### M3.1 notes (computer opponent and Player vs AI)
**Decisions (PM, M3.1):**
- Alternating turns only; simultaneous firing is cancelled permanently.
- Player vs AI is the primary mode: the human plays LEFT, the AI plays RIGHT.
- Local two-player play stays as an additional mode.
- No balance or victory-rule changes without PM approval.

**Preflight of the M2.3 abilities.** New interface-level tests (`tests/test_main.py`,
`AbilityPreflightTest`) play each special through clicks and frames. They check the results in
the real `Battle` and on the drawn screen:
- **Rally:** the next enemy blast on all three allies is halved (14 / 18 / 16 instead of
  28 / 36 / 32); the defend bubble is drawn, then cleared at the team's next turn.
- **Power Shot:** 60 damage against the same Knight that a normal Archer Attack hits for 28.
- **Repair:** after a real tower hit (−200) it restores 75, most damaged blocks first; the HUD
  shows 8 %.
- **Cooldowns:** they tick only at round starts; the button is disabled and refuses clicks in
  rounds 2–3; it is ready again in round 4 = 1 + 3.

Eight injected defects were all caught, including the IME regression (text input left on).
**No defect was found, so no ability code changed.** Human acceptance of these abilities is still
pending.

**The AI as built (`ai.py`), not the §6.3 plan:**
- **Interface:**
  - `AIController(side, difficulty, seed)`;
  - `choose(battle)` returns a `Plan` and changes nothing;
  - `take_turn(battle)` aims the real cannon with `Cannon.adjust_angle` / `adjust_power` and calls
    `Battle.perform_action()`;
  - `pick_team(size)` draws distinct roles at random.

  The AI never touches HP or castle blocks directly; a test scans `ai.py` for that.
- **No combat rule is written twice.** To judge an option, the AI runs it on a
  `copy.deepcopy` of the battle with the real `perform_action` / `update`, and reads the
  explosion events (`imagine`). Gravity, speed, collisions and damage formulas are reused
  unchanged.
- **Aiming (bounded candidate search):**
  - It tries angles 30° / 45° / 60° with powers 100, 98, …, stopping at an angle once a shot
    lands on its own half.
  - It groups the aims by what they would hit. For each target it keeps the most forgiving aim:
    the middle power at the angle where the most powers hit.
  - The options are ranked by `progress()`: the share of the remaining work toward each victory
    condition (enemy HP, enemy castle HP still to lose before falling, own castle HP repaired),
    plus a bonus for each defeat and for a win.
  - Finally it adds a uniform random aiming error.

  One decision takes about 60–120 ms on average (the most measured was 174 ms).
- **Decision order:**
  1. **Defend?** `wants_to_defend`: the defend chance is higher when a character is below half
     HP (the course requirement), and there are never two defensive turns in a row.
     `defensive_plan` uses Rally if a ready Knight can protect two or more allies, otherwise the
     weakest character defends.
  2. **Otherwise attack:** a target is picked among the best `top_choices`, then the shooter
     (Attack, or Power Shot when specials are considered this turn) among the best
     `top_choices`. A Repair replaces the attack if its score is higher.
  3. **Safety net:** a plan that `why_not_allowed` refuses is replaced by Defend, and marked so
     the tests fail if it is ever used.
- **Difficulty table** (`DIFFICULTY_SETTINGS`; the rules are the same for all):

| | Easy | Normal | Hard |
|---|---|---|---|
| Aiming error, uniform ± (angle / power) | 6° / 8 | 3° / 4 | 1° / 2 |
| `top_choices` (1 = always the best) | 5 | 3 | 1 |
| Specials considered on a turn | 25 % | 50 % | 100 % |
| Defend chance: nobody below half HP / someone below half | 10 % / 40 % | 5 % / 50 % | 0 % / 60 % |

**Measured** (seeded; 150 shots per cell; castle loss off, so only characters count):

| Character hit rate | Easy | Normal | Hard |
|---|---|---|---|
| 1v1 | 23 % | 46 % | 66 % |
| 3v3 | 46 % | 67 % | 85 % |

AI vs AI (castle loss on, 12 seeded matches per pairing and size):
- Hard beat Easy in 67 of 72 matches.
- Matches lasted 4.8–7.7 rounds on average.
- Normal vs Normal: the side moving first won 28 of 36. Hard vs Hard: 18 of 36. So the
  first-move advantage is unclear and needs a bigger sample.

**Interface changes (`main.py`):**
- **Selection screen:**
  - Mode buttons: Player vs AI (the default) and Two players.
  - Computer level buttons: Easy, Normal (the default), Hard.
  - In Player vs AI, the RIGHT cards are greyed out and refuse clicks. START needs only the LEFT
    team, then the AI builds a legal RIGHT team of the same size.
- **Battle:**
  - `Game.ai` holds the controller. `update_ai()` waits `AI_DELAY_FRAMES` (40) and then calls
    `take_turn`.
  - During the AI's turn, buttons, aiming keys and character clicks are disabled.
  - The log adds "AI (level): reason."; the existing events show the effects. The HUD says
    "(you)" or "(computer)".
- **Rematch:** keeps the teams and the controller (`new_match()`).

No engine module (`battle.py`, `castle.py`, `characters.py`) changed in M3.1.

**Balance research:** `docs/M3.1_balance_analysis.md`. It is analysis only; nothing changed.

**Verification:**
- **Tests:** 194 in total. 52 need Pygame; the rest, including the 27 AI tests, need only the
  standard library.
- **Injected defects:** 17 AI and Player-vs-AI defects were each caught.
- **Scripted runs** of the real `main.main()` with posted events:
  - Player vs AI, 24 / 24 checks, for Easy 1v1, Normal 2v2 and Hard 3v3, up to the result and
    Rematch;
  - the M2.3 hot-seat drives through "Two players";
  - the original M1 duel drive (15 / 15; it ends on frame 713, as before).
- **Real Windows input** (`SendInput`, only while the game window had focus): 11 / 11 checks.
  - Real clicks: picking a card; the AI's card refused; START; DEFEND; ATTACK, which was ignored
    on the computer's turn.
  - Real keys: arrows, Shift, R and SPACE.
  - The computer took its own turn.
  - The first attempt clicked at a stale position. Cause: my driver clicked without a preceding
    mouse move. The driver was fixed; the game was not changed.

This is still not human gameplay acceptance.

### M3.2 notes (gameplay balance)
**Brief (PM, M3.2):** make Defend and Engineer Repair strategically useful without redesigning the
game. The allowed changes were Castle Guard, a Repair amount of 75–150 and a castle threshold of
60–70 %, each only with convincing evidence. No new attack mechanics, counterattacks, extra
actions or rebuilt blocks.

**Benchmark** (`scripts/balance_benchmark.py`, no project file changed while it runs):
- seeded AI-vs-AI matches with the real `Battle` and `AIController`;
- four strategies (aggressive, the shipped AI, defensive, repair-aware) and eight rule variants;
- mirrored rosters only, sides swapped, the same seeds in every variant (paired comparisons), a
  40-round cap;
- a decision-point experiment: a match is copied at the moment a Defend or Repair is possible,
  and both choices are played to the end.

There were 10,560 matches on Normal and Hard, plus an Easy check. Method, results and
uncertainty are in `docs/M3.2_balance_report.md`; the raw tables are in
`docs/M3.2_benchmark_results*.md`.

**Result:**
- **Castle Guard** raised a defend-when-threatened strategy by +13 ± 6 (Normal) and +4 ± 3 (Hard)
  points. 84–92 % of defensive actions now prevent castle damage.
- **Repair 150** made repairing about even with attacking at the moment it is possible. At 75 it
  cost 22 ± 8 points on Hard.
- Together they add 0.85 / 0.32 rounds. No match stalled, and no AI action was refused.
- **60 % kept:** 70 % only lengthened matches.
- The AI was not changed: it plans on copies of the battle with the real rules, so it adapts by
  itself.

**Code:**
- `battle.py`: `CASTLE_GUARD_PERCENT`, `Battle.castle_guarded`, and the guard in `_end_shot`;
  the explosion event gets `"guarded"`.
- `characters.py`: `REPAIR_POOL = 150`.
- `castle.py`: `Castle.hp_before_falling` (used by the AI instead of its own 60 % arithmetic).
- `main.py`: after a guarded explosion the combat log adds "Castle Guard halved the damage to the
  castle."

**Verification:**
- **Tests:** 207 in total. With Pygame, all 207 pass; without it, 154 pass and the 53 in
  `test_main.py` are skipped. New Castle Guard tests are in `CastleGuardTest`: Defend, Rally,
  no stacking, the exact turn boundary, rounding, the defender's last shot, the M1 duel. The
  Repair tests moved to 150.
- **Injected defects:** 19 rule defects were injected; 18 were caught. The remaining one is
  equivalent: `Castle.repair` and `Block.restore` each refuse destroyed blocks, so removing only
  one of the two checks changes nothing.
- **M1 duel:** 60 seeded duels gave the same events with the old and the new code; the scripted
  duel drive still passes 15 / 15 checks.
- **Benchmark:** the Normal/Hard run was reproduced record for record by a second run of the
  committed script.

This is not human gameplay acceptance.

### M3.3 notes (final game rules and flow)
**Brief (PM, M3.3):** finish the core rules and the player flow before the December 8 deadline. No
new classes, abilities or major GUI features, and no rebalancing.

**Battle (`battle.py`):**
- `ROUND_LIMIT = 30` and `Battle.tie_break()` (§4.7).
- `Battle(first_side=...)`; `reset(first_side=None)` keeps or changes the first mover.
- `end_reason` (`"elimination"`, `"castle"`, `"tie_break"`, `"draw"`, `"both_lost"`) and
  `tie_break_rule`. The `game_over` event carries `"reason"`.
- `Team.total_hp()` and `total_max_hp()`.
- A round starts when the first mover is to act again, instead of always at LEFT's turn.

**Interface (`main.py`):**
- `Game.rematch()` swaps the first mover in team matches. The M1 duel keeps LEFT.
- A guarded castle gets a blue outline and a GUARDED badge (`draw_castle_guard`,
  `guard_badge_rect`), read from `Battle.castle_guarded` every frame.
- The HUD shows "Round N / 30".
- The result screen adds the reason and "Rounds played: N" (team matches only).
- The log says who moves first and when the round limit decided the match.

**Benchmark:** `scripts/balance_benchmark.py` lifts the game's round limit above its own 40-round
cap, so the M3.2 results still reproduce. 300 replayed matches were identical.

**Not changed:** the combat rules, M3.2 balance, AI decisions, physics and the M1 duel.

Human gameplay acceptance is pending.

### M3.4-A notes (character elimination and deployable cover)
**Brief (PM, M3.4):** meet the instructor's core requirement (the only normal victory is
eliminating every enemy character); replace the fixed castles with player-deployable blocks; keep
one shared cannon per team in front of the characters. Phase A builds and tests the combat rules
only: no placement screen, no new AI, no animation.

**Battlefield (left side; the right side is the mirror image, x' = 1280 - x):**
- Characters: slots at x 140 (slot 1, the front), 95 and 50; 28 × 44 px, standing on the ground (y 560).
- Cover slots: 32 px blocks in 4 columns at x 172, 204, 236 and 268, and 2 rows (bottom y 528,
  raised y 496). Slots 0–3 are the bottom row (slot 0 next to the characters); slot 4 + c sits on
  slot c. They end at x 300.
- Cannon: pivot (340, 544), on the ground in front of the cover (a wheel under the pivot).
- The GUARDED badge is drawn at (236, 476), above the raised row.

**Why one shared cannon:** one launch point per side keeps aiming learnable, keeps the AI's
search small, and matches the M0 design (C6). In M3.4-C the acting character will run to the
cannon and back; that animation will not change the physics, because the shot always starts at
the pivot.

**Placement budget and constraints:** 0–6 blocks on 8 slots, no duplicates, a raised block only
on a block. `layout_problem()` returns the reason a layout is illegal (or None), and `Castle`
refuses an illegal layout. The slots are fixed, so no block can overlap a character, a cannon,
the launch point or the HUD and buttons (tests check every slot). There are 76 legal layouts.

**Projectile and cover interaction:**
1. Each step, `segment_entry()` finds where the segment from the old position to the new one
   first touches each standing enemy block and living enemy character. The earliest touch (blocks
   before characters before the ground on an exact tie) is the impact, at the exact touching
   point.
2. At impact, before any damage: Cover Guard, the characters in the 50 px blast (a directly hit
   character always counts) and which of them are shielded (`Team.is_covered`: a standing block of
   their team lies on the segment from the explosion to their centre). A direct hit is never
   shielded.
3. Then blocks in the blast take block damage once (halved by Cover Guard), and every unshielded
   character in the blast takes `calculate_damage` once (halved by Defend).
4. The explosion event lists the characters hit, the shielded characters (`"covered"`) and the
   directly hit character (`"target"`).

Consequences: a block destroyed by this explosion still shields against it; a shot that lands on
top of the block in front of a character is absorbed; a steep shot can still hit a character
from above, so no legal layout makes a character unreachable (tested for all 76 layouts).
Because the explosion is now at the exact surface point, one explosion can no longer reach all
three characters of a team (the old point check exploded a few pixels inside the target).

**Turns and animation states:** the turn and round rules are unchanged from M3.3 (an attack turn
ends when its shot lands). Planned for M3.4-C, drawing only: IDLE -> RUN_TO_CANNON -> FIRE (the
battle launches the shot) -> RETURN_TO_SLOT -> IDLE, with input locked until the turn ends.

**AI target selection (M3.4-A, interim):** `ai.progress()` now counts only damage to enemy
characters (and defeats), plus Repair valued as the share of the team's cover HP it restores.
Shots that hit only blocks score 0, so the AI aims at characters it can reach and otherwise uses
its fallback aim. Planning around cover and breaking cover on purpose are M3.4-B.

**Intentional simplifications:** no structural collapse (a raised block stays in place if the
block under it is destroyed); cover is all-or-nothing for a character (the block absorbs the whole
blast); blocks do not shield other blocks; the class is still called `Castle` (one team's cover)
and the method `castle_guarded`, to avoid renaming every file this late.

**Removed:** the M1 cannon duel (its 60 % rule must not be a selectable mode; it is in git: M1.1
at `2ccb68c`, last present at `86b90fa`), `castle_loss_enabled`, the castle template, `has_fallen`, `destruction_percent`,
`hp_before_falling`, `Battle.tie_break` and `scripts/balance_benchmark.py` (it compared castle-rule
variants; reproducible at `86b90fa`).

**Tests:** the aiming values in the tests come from an independent simulation (its own physics and
a fine-sampling collision check), not from `battle.py`.

Human gameplay acceptance is pending.

### M3.4-B notes (cover placement screen and cover-aware AI)
**Brief (PM, M3.4-B):** a cover placement screen between team selection and battle (Player vs AI:
LEFT only, the AI places RIGHT; two players: both teams, with Back), rematches that keep both
covers, an AI that tells character damage, cover that opens a shot, cover that weakens a blocked
route and harmless shots apart, measured decision times and match statistics, and scripted
gameplay screenshots. No animation (M3.4-C), no new combat mechanics.

**Placement rules live in `castle.py`:** `place_block(layout, slot)` returns the new layout or the
unchanged layout and `layout_problem()`'s reason; `remove_block(layout, slot)` removes the block
and then every block `floating_blocks()` reports (the raised block that stood on it), and returns
the removed slots so the screen can say what happened. `layout_problem()` uses the same
`floating_blocks()`, so the support rule is written once. A property test clicks every slot of
every one of the 76 legal layouts and checks that the result is always legal, and that every legal
layout can be built by clicks and cleared to zero blocks.

**Screen decisions:**
- The screen shows the placing team's side **at battle scale and position** (characters, cannon,
  slots), so what you place is exactly what you get. The slots are the real 32 px squares; the
  legend, the "+" on placeable slots and the status line make them readable at 1280 × 720.
- A slot is drawn as placeable only if `place_block` would accept a block there, so the drawing
  never repeats a rule.
- It starts from `DEFAULT_LAYOUT`, so Confirm alone gives a sensible cover, with the same budget
  the computer uses.
- In two-player mode the other team's cover is not drawn while a team places (both are visible in
  battle); this stops RIGHT from simply countering LEFT's layout.
- Keys: Enter = Confirm, Backspace = Back (Esc still quits).
- `Game.state == "cover"` and `Game.placing` ("left"/"right") describe the step; the battle is
  updated only in "battle" and "result", so an old finished battle can't produce events while the
  teams or the cover are being chosen again.

**Setup state:** `CoverSetup.layouts` holds one tuple per side. Back keeps everything; Change teams
keeps the picks and both layouts (cover slots don't depend on the team size or roles). In Player
vs AI the computer's controller, team and cover are created when LEFT confirms its cover (a new
series), and a rematch only calls `Battle.reset`, which rebuilds the same layouts at full HP, so
the computer's cover is never regenerated on a rematch. The human's RIGHT layout from two-player
mode is kept separately and is not overwritten by the computer's. `Game(screen, ai_seed=...)`
makes the computer repeatable for the tests; the real game passes no seed.

**AI layout policy (`AIController.choose_layout`):** first a two-block tower on slots 0 and 4,
next to its characters, because that is where shots that clear the cover come down on the front
character; then 4 more blocks, each on a random slot that `place_block` allows. Always 6 blocks,
never more; 6 different layouts are possible; the same seed gives the same layout; the player's
cover is never read.

**AI cover-clearing algorithm, in plain language (`ai.py`):**
1. Scan: imagine an Attack at angles 30°, 45° and 60° with every second power (as since M3.1).
2. Routes: for each scanned aim that came down on an enemy block, trace the whole path
   (`Battle.path_contacts`). If a living enemy character stands behind the blocks on that path,
   it is a *route*; the blocks before the character are *in its way*. A route is worth one direct
   hit on that character (`hit_value`: its HP removed / the enemy team's HP left, plus the defeat
   bonus if it would fall).
3. Score each aim: `progress()` (character damage, defeats, a win) + 0.5 × the best
   *route value × share of the HP of that route's blocking blocks that the shot removes*. So:
   (1) a shot that damages a character scores its damage; (2) a shot that destroys the last block
   in a route's way scores half the route value; (3) a shot that only weakens such a block scores
   the matching share; (4) a shot that damages only blocks in nobody's way, or nothing, scores 0.
   The 0.5 says that an opened route pays off a turn later at the earliest, and the enemy may
   Repair.
4. Reliability: each aim is rated by the average score of the scanned aims within the AI's own
   power error (±8 Easy, ±4 Normal, ±2 Hard; clamped like the error itself). A narrow gap over the
   cover therefore counts for less than a wide target, and a protected character makes breaking
   the cover the better plan. The angle error is not included (only three angles are scanned).
5. Targets are grouped (a character, a group of characters, or "the cover in front of" a
   character); Easy picks among the best 5, Normal 3, Hard always the best. Then the shooter
   (and Attack or Power Shot) is chosen with the same score, Repair is compared as before, and the
   aiming error is added. The plan's `goal` is "damage", "cover", "defend", "repair" or None.
It is a one-turn lookahead with real Battle copies plus path traces: no game tree, no minimax,
and no information a player can't see (the battlefield, HP and its own aiming skill).

**Why `path_contacts` is in `battle.py`:** it reuses the real `Projectile` and the same
`_touches()` collision helper that `_find_impact()` now uses, so the AI's route tracing can't
drift from the real collision rule. A test checks that its first contact is exactly what a real
shot hits, for 3 layouts × 33 aims, and that it changes nothing.

**Code layout:** `drawing.py` now holds the colours, `draw_text`, `wrap_text`, `draw_figure`,
`Button`, `block_color` and `hp_bar_width`, moved out of `main.py` unchanged; `main.py` imports
them back, so `main.block_color` etc. still work. Long combat-log lines (the AI's reasons) now
wrap inside the log panel.

**Measured (seeded, scratch scripts, not committed):**
Decision time of one `AIController.choose()` on an otherwise idle Windows PC (Python 3.11.9), over
every decision in 9 seeded AI-vs-AI matches per level (1v1/2v2/3v3, AI-placed cover): Easy median
96 ms (95th percentile 197, max 263), Normal 132 ms (268, 435), Hard 150 ms (211, 228); the
slowest positions are early 3v3 rounds with 10–12 blocks standing. In a real game window the
ordinary frame takes about 2 ms, and the one frame in which the computer decides took 118–157 ms
(median per level, max 171 ms): a pause of about a tenth of a second once per computer turn,
after its 2/3 s "thinking" delay. While other heavy work ran on the same PC, single decisions
took up to 1.2 s. Whether this feels smooth is part of the pending human play-test.

AI vs AI, 6 seeded matches per row, each AI placing its own cover (eliminations / 6, average
rounds; LEFT first | RIGHT first):

| | 1v1 | 2v2 | 3v3 |
|---|---|---|---|
| Easy | 5, 23.0 \| 6, 23.5 | 4, 25.5 \| 4, 28.7 | 3, 26.8 \| 1, 29.8 |
| Normal | 6, 9.0 \| 6, 10.7 | 6, 15.2 \| 6, 15.7 | 5, 20.0 \| 5, 21.5 |
| Hard | 6, 8.0 \| 6, 7.5 | 6, 11.7 \| 6, 11.2 | 6, 11.5 \| 6, 12.2 |

Every match that did not end in an elimination ended in the round-30 timeout draw; no match
needed the fallback aim. Against a team that Defends every turn (the hardest case: Defend halves
character damage and Cover Guard halves block damage), behind each of the six layouts the AI can
build (one of them is the default cover), 6 seeds each: Hard eliminated it in 36/36 (1v1, 13–16
rounds on average) and 36/36 (3v3, 13–16); Normal in 29/36 (1v1, 18–19) and 31/36 (3v3, 23–26);
Easy in 6/36 (1v1) and 0/36 (3v3).

**Gameplay blocker for Easy (reported, not fixed):** Easy cannot reliably reach and eliminate
protected characters within 30 rounds: Easy vs Easy ends in a draw in up to 5 of 6 3v3 matches,
and Easy almost never eliminates a team that keeps defending. The cause is its aiming error
(±6°, ±8 power) against narrow routes over the cover, made worse by Defend and Cover Guard. Normal
and Hard do reach and eliminate protected characters. Options for the PM: accept it (Easy is meant
to lose to a human who attacks; not yet measured with humans), lower Easy's aiming error, or raise
`ROUND_LIMIT`. No change was made without approval.

**Intentional simplifications:** routes count only paths that touch a character directly (not
blasts that would land next to one); route values use the first living character's ATK; a block
destroyed later in the same blast is not credited twice; the angle error is not part of the
reliability average.

Human gameplay acceptance is pending.
