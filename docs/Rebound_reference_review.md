# Rebound — Technical Reference Review for Castle Siege

**Purpose.** This is a read-only technical audit of
[ryonsherman/pygame-rebound](https://github.com/ryonsherman/pygame-rebound), done before
revising `docs/M0_design.md`. It records which Rebound ideas could help Castle Siege and how
we would build our own, simpler versions. **No Rebound code, assets or file layouts are copied
into our project.**

**Snapshot studied:** commit `83f1766ea320b7f3052c16e3cf13e1764ab0178b` (2026-06-18,
"Fix difficulty scaling test values"), branch `main`, MIT License, about 9,700 lines of Python.

**How it was studied**
- A shallow clone into a temporary folder outside our repository. Files larger than 100 KB were
  skipped (57 trained-model `.zip` files in `rl/models/` and two screenshots). All Python source,
  docs, tests, small images and sounds were downloaded.
- **Read in full:** `src/engine.py`, `src/renderer.py`, `config.py`, `game.py`, `src/menu.py`,
  `src/sounds.py`, `src/game_client.py`, `src/nn_controller.py`, `README.md`, `CONTEXT.md`,
  `TESTS.md`, `LICENSE`, `requirements.txt`, `Makefile`, `tests/conftest.py`,
  `tests/test_engine_physics.py`, `tests/test_difficulty_scaling.py`.
  **Read in part:** `tests/test_renderer.py`, `tests/test_engine_gameplay.py`.
  **Seen by file name and docs only:** networking (`server.py`, `admin.py`, `src/nats_common.py`,
  `src/bot_client.py`), RL training (`rl/`) and the remaining tests.
- **No Rebound code was executed.** A small behaviour-check script was written, but the session's
  permission policy blocked running downloaded code, and the attempt was not repeated.

**Evidence labels used below**
- **[Code]** verified by reading the source at the cited `path:line`. Not executed.
- **[Doc]** stated only in Rebound's README / CONTEXT / TESTS files; not checked against the code.
- **[Inference]** our conclusion from reading the code; plausible, not demonstrated.

---

## 1. Summary

Rebound is a **real-time, top-down, 4-player arena game**. Each player owns a small castle
(3 × 3 bricks) in a corner. A rotating cannon fires balls that travel in straight lines, bounce off
walls, obstacles and each other, shrink and slow with every bounce, and break bricks. Holding Space
raises a shield that reflects shots. The last castle standing wins. It also has 12 power-ups,
online play through a NATS message server, an admin shell, and AI opponents driven by trained
PPO neural networks.

How close is it to Castle Siege?

| | Rebound | Castle Siege |
|---|---|---|
| View | top-down arena | side view with ground |
| Timing | real time, input every frame | turn-based rounds with planned actions |
| Projectiles | straight lines, **no gravity**, bounce many times | ballistic arcs under gravity, explode on impact |
| Castle | 9 bricks × 2 hits; **where the shot hits does not matter** | 15 blocks × 100 HP; the blast damages blocks near the impact |
| Sides | 4 castles, no characters | 2 castles, 1–3 characters with stats |
| AI | PPO neural network by default, heuristic fallback | rule-based and explainable |

**Conclusion:** Rebound is a useful source of **engineering patterns** (a headless engine, an
event list for sound, collision robustness, difficulty tables, testing habits). It is **not** a
source of gameplay rules or physics formulas for us.

---

## 2. Project structure, dependencies, architecture

### 2.1 Files

| Area | Files | Python lines |
|---|---|---|
| Game core | `src/engine.py` 1711, `src/renderer.py` 658, `game.py` 380, `src/menu.py` 159, `config.py` 123, `src/nn_controller.py` 97, `src/game_client.py` 77, `src/sounds.py` 56 | 3,261 |
| Networking / admin | `admin.py` 521, `server.py` 414, `src/bot_client.py` 128, `src/nats_common.py` 62 (plus the `NATSClient` class inside `game.py`) | 1,125 |
| RL training | `rl/env.py`, `train.py`, `make_vector_obs.py`, `eval.py`, `threaded_vec_env.py`, `reward.py`, `benchmark.py` | 1,124 |
| Tests | 20 files in `tests/` | 4,198 |
| Assets | `assets/powerups/` (12 icons in use), `assets/Sprites*/` (icon sheets), `sounds/` (21 `.ogg`), `rl/models/` (57 `.zip`) | — |

### 2.2 Dependencies
- `requirements.txt` [Code]: `pygame==2.6.1`, `nats-py`, `prompt_toolkit`, `pytest`,
  `pytest-asyncio`, `pytest-mock`, `gymnasium`, `numpy`, `stable-baselines3`, `torch`,
  `tensorboard`.
- `src/renderer.py:4` imports `PIL` (Pillow), which is **not listed** [Code]. Another package may
  install it indirectly [Inference].
- The README's install line is `pip install pygame nats-py prompt-toolkit` [Doc]. With only that,
  importing the renderer would fail without Pillow. Starting a local match would also fail, because
  the bundled model files are loaded through `stable_baselines3` with no fallback when the library
  is missing (`src/game_client.py:21,31-37`, `src/nn_controller.py:36-40`) [Inference; not executed].
- **Lesson for us:** the README's install steps must match our imports, checked from a fresh
  environment (an M5 acceptance criterion).

### 2.3 Architecture
- **One very large engine class.** `GameEngine` (`src/engine.py:573-1711`) holds physics, rules,
  power-ups, obstacles, blockades and state export in about 1,140 lines. The heuristic
  `AIController` is in the same file (`src/engine.py:222-571`) [Code].
- **State is plain dictionaries, not objects.** Castles, bricks, projectiles, blockades and
  power-ups are `dict`s (`_init_castles` `src/engine.py:675-711`, `_make_projectile` `:67-81`).
  The only inheritance in the game is `NNAIController(AIController)` (`src/nn_controller.py:13`) [Code].
- **Headless engine, separate renderer.** `engine.py` does not import pygame. `config.py` even
  wraps `pygame.Color` in a lazy proxy so that importing constants does not start pygame
  (`config.py:1-42`) [Code].
- **The engine reports sounds as data.** Each `update()` clears `sound_events` and appends
  `{"type", "volume"}` dictionaries (`_emit_sound`, `src/engine.py:713-715`). The UI later plays
  them (`src/sounds.py:41-56`) [Code].
- **Server-authoritative networking:** the server runs the engine, clients send only input, and
  state is broadcast at 20 Hz [Doc, `CONTEXT.md`].
- **Difficulty changes the rules as well as the AI:** projectile speed, bounce limits, ball cap
  (`src/engine.py:574-585`) and even friendly fire (`:955`, `:1236`, `:1242`) [Code].

**Relevance:** the headless engine and the event list fit our rule that only `main.py` imports
pygame. The dictionary-based "god class" is the opposite of what our OOP rubric category
(20 points) rewards, so it is a counter-example, not a model.

---

## 3. Mechanisms

Each mechanism lists: how Rebound does it → why it matters for us → recommendation →
complexity of our version → how we would build a simpler original version.

### 3.1 Projectile movement and gravity
- **How [Code].** `_make_projectile` (`src/engine.py:67-81`) sets a constant `vx, vy` from the
  angle and a speed of 8 px/frame (×0.9 / 1.0 / 1.1 by difficulty, `:576-578`).
  `_update_projectile` (`:999-1149`) moves the ball. **There is no gravity term anywhere.**
  Velocity changes only through bounces (reflection, then ×0.84–0.92 speed and ×0.75–0.85 radius,
  `:1133-1149`), the "hook" power-up curve (`:1003-1011`), shield reflection (`:1151-1167`), and a
  "sling" that adds the cannon's rotation speed to a new shot (`:865-870`). Movement is per frame,
  not per second.
- **Why it matters.** Little: our game is ballistic. The one shared choice is a fixed amount of
  movement per frame, which keeps results deterministic.
- **Recommendation: Reject** the movement model (bounces, decay, sling, hook). Keep our gravity model.
- **Complexity:** not applicable.
- **Our version:** unchanged. A fixed-step Euler update under gravity (M0 §4.6), launched from one
  cannon per side.

### 3.2 Collision detection
- **How [Code].**
  - Sub-steps: `steps = ceil(speed / radius)`, so a ball never moves more than its own radius per
    sub-step (`src/engine.py:1017-1022`).
  - Circle vs rectangle: clamp the ball centre into the rectangle to find the closest point, and
    collide if that point is closer than the radius (`:1065-1071`). Then push out along the normal
    and reflect the velocity (`:1097-1109`), with a special case when the centre is inside
    (`:1074-1096`). At most 5 passes per sub-step (`:1050`), then re-clamp to the walls (`:1115-1131`).
  - Castle hit: the ball **centre** inside the castle's 60 × 60 bounding box (`:949-960`), not a
    per-brick test.
  - Ball vs ball: equal-mass elastic exchange along the normal, with an 8-frame cooldown
    (`:962-976`, `:1169-1188`).
- **Why it matters.** Our shots are points tested against 28–32 px rectangles, so a plain
  point-in-rectangle test is enough. The useful idea is the **invariant "the largest move per step
  is smaller than the smallest target"**, which is what makes Rebound's sub-steps safe.
- **Recommendation: Adapt** the invariant. **Reject** sub-stepping, push-out and ball-vs-ball.
- **Complexity:** Low.
- **Our version:** keep the fixed step. Energy conservation gives the fastest possible shot in our
  design: √(700² + 2·400·170) ≈ 791 px/s, which is **13.2 px per step**, below the 28 px character
  width. So a shot can never jump over a whole target between two steps (it may still clip a corner
  by a few pixels, which is acceptable). We turn this into a unit test that fails if anyone raises
  `SPEED_PER_POWER` or `GRAVITY` too far. No sub-steps are needed.

### 3.3 Castle bricks, damage and destruction
- **How [Code].** A castle is 9 bricks of 14 px with `hp = 2` (`src/engine.py:50-65`), stored in
  spiral order: outer bricks first, centre last (`:59`). `_damage_castle` (`:1282-1335`) removes
  **1 HP from the first living brick in that order and returns**. So the impact point never matters,
  and, without repairs, every castle falls after exactly 18 hits. A brick at 1 HP is drawn darker
  with a cross (`src/renderer.py:289-290,329-343`). When the last brick dies, the castle is eliminated, its inventory is
  cleared, and **all of that player's balls still in flight are deleted** (`src/engine.py:1318-1325`).
  The game ends when at most one castle is alive; if none is alive, the winner is `None` (`:994-997`).
- **Why it matters.** It confirms that "every hit visibly moves the bar" is worth having, which our
  HP-based destruction % already does. Two parts conflict with our design: position-independent damage
  would make aiming at the castle pointless, and deleting in-flight shots contradicts simultaneous
  resolution.
- **Recommendation: Adapt** the two-stage "cracked" look as HP-band colours. **Reject**
  order-based damage and in-flight deletion.
- **Complexity:** Low.
- **Our version:** a block is drawn in its normal colour at 67–100 HP, darker with one crack line at
  34–66 HP, and darkest with two crack lines at 1–33 HP. Damage comes from the blast radius, so
  aiming matters. A shot already in flight always lands, even if its owner's team loses during the flight.

### 3.4 Shield and defensive abilities
- **How [Code].**
  - Shield: held with Space (human) or raised by AI threat detection. An **AI** shield lasts at
    most `SHIELD_DURATION` = 60 frames, because the timer is set only when the AI raises it
    (`src/engine.py:551-560`). A **human** shield lasts as long as Space is held: every frame
    `handle_input` resets the timer to 60 (`:737-741`), and `config.py:73` notes the limit is
    "unused if held manually". When the timer does run out, a 180-frame cooldown starts
    (`:826-831`). A ball entering the 50 px circle is reflected back, turned exactly 60° to one side
    chosen at random (`:1151-1167`). The shield then drops and goes on cooldown (`:908-922`).
    A castle cannot fire while shielded (`:747`, `:504`).
  - Reward for blocking: each reflected enemy ball spawns a 2 × 2 "blockade" in your quadrant,
    at most 4 (`:945-946`, `:1190-1220`).
  - Defensive power-ups (`:138-157`, `:1552-1657`): Fortify (double duration, charge refunded on
    a block), Healing Shield (repairs 2 destroyed bricks on a block, `:934-943`), Shield Pulse
    (pushes nearby balls away), Auto Shield (triggers when a ball comes within 80 px), and Repair
    Kit (restores 2 destroyed bricks to full HP, `:1569-1577`).
- **Why it matters.** Three ideas transfer. Defence has a clear on/off state that is easy to see.
  Defence costs offence (no firing while shielded). And repair is a **small, fixed amount**.
- **Recommendation: Adopt** a visible defend state. **Adapt** small fixed repair. **Reject**
  reflection, blockades and power-ups.
- **Complexity:** Low.
- **Our version:** a defending character is drawn inside a translucent bubble until its team's next
  turn. Defend and Rally already use up the team's action for the round. Engineer Repair restores
  **at most 75 HP (5 % of the castle) per use**, to damaged blocks that still stand (M0 §3.4).
  Unlike Rebound's Repair Kit, destroyed blocks never come back, so gaps in the wall stay open.

### 3.5 Enemy AI and difficulty
- **How [Code].**
  - The default AI in a local match is a **PPO neural network**. `Game._resolve_model` uses
    `rl/models/{difficulty}_model.zip` when the file exists (`src/game_client.py:31-37`).
    `NNAIController` runs `model.predict` every 4 frames and outputs an aim direction (32 bins),
    fire, and shield (`src/nn_controller.py:41-97`). The model input is a 112-value vector [Doc].
    Reported win rates are 80–100 % against the heuristic AI [Doc].
  - The heuristic `AIController` (fallback and training opponent, `src/engine.py:222-571`):
    - Target: a random living enemy, re-picked every 15–45 frames (`:471-482`).
    - Aim error: a **random pixel offset of the target point**, ±60 / ±35 / ±15 px for
      Easy / Medium / Hard (`:478-479`, `:241-268`).
    - Bank shots: mirror the target across a wall or obstacle face and aim at the mirror image
      (`:323-427`), with line-of-sight checks by segment–rectangle intersection (`:271-321`).
    - A limited turning speed (0.02 / 0.04 / 0.06 rad per frame, `:484-500`) and a random firing
      interval (99–198 / 60–150 / 27–81 frames, `:502-517`).
    - Shield: predicts each incoming ball's closest approach within a range (100 / 140 / 180 px)
      and time window (30 / 45 / 60 frames) (`:519-568`).
  - **Difficulty also changes the rules for every player:** speed, bounce limits and ball cap
    (`:574-585`). On Hard, your own shots can damage your own castle (`:955`), and own-blockade
    handling differs on Easy and Medium (`:1236`, `:1242`).
  - Docs and code disagree: README and TESTS.md give max bounces as 3 / 4 / 5, while the code and
    its test use 4 / 5 / 6 (`src/engine.py:579`, `tests/test_difficulty_scaling.py:10-15`) [Code + Doc].
- **Why it matters.** High for the **structure** (one parameter table per difficulty, noise-based
  aiming, seeded comparison tests). None for the neural network.
- **Recommendation:**
  - **Reject** the PPO AI: it needs `torch`, can't be explained line by line, and can't be tested by hand.
  - **Adopt** "every difficulty number in one table".
  - **Reject** difficulty that changes game rules. In our game, difficulty affects only the AI, so
    the rules the human plays under never change.
  - **Evaluated, not adopted:** target-offset aim noise (results below).
  - **Reject** bank-shot mirroring and threat prediction, because we have no bounces and play in turns.
- **Complexity:** Low.
- **Our version, and an evaluation of target-offset noise.** We simulated both noise styles for our
  tower-top cannon with throwaway scripts (per difficulty: 400 castle and 400 character shots for the
  angle/power row, 600 of each for the offset rows):

  | Noise style | Easy | Normal | Hard |
  |---|---|---|---|
  | Angle/power noise ±10°/±14, ±6°/±9, ±3°/±5 | castle 58 %, character 33 % | 75 %, 53 % | 96 %, 80 % |
  | Target-offset noise ±250 / ±150 / ±60 px | castle 47 %, character 36 % | 77 %, 60 % | 96 %, 90 % |
  | Target-offset noise ±100 / ±60 / ±30 px (Rebound-sized) | castle 91 %, character 79 % | 98 %, 92 % | 99 %, 100 % |

  Rebound-sized offsets barely matter in our game, because the 192 px castle, the 50 px blast and
  the closely spaced characters absorb the error. Both styles can be tuned to work. **We keep
  angle/power noise**, because it copies the controls a human uses and was already in M0. We
  record target-offset noise as an alternative.

### 3.6 HUD, animations, explosions and visual feedback
- **How [Code].**
  - **No HP bars, no combat log, no explosion or particle effects.** Feedback comes from brick
    colour bands, balls shrinking per bounce, a translucent shield (pre-rendered surfaces,
    `src/renderer.py:582-602`), a crown on human castles, per-castle "H:" hits and "B:" blocks
    counters (`:635-649`), winner text (`:651-658`) and a "MUTED" label.
  - Aim line: a ray cast from the cannon to the first wall or obstacle (slab method, `:380-542`).
    It is bright on Easy, dim on Medium and hidden on Hard (`:254-261`).
  - Menu: an all-AI match runs behind a translucent overlay, in an "endless" mode where castles
    respawn (`src/menu.py:19-20,74-85`; `src/engine.py:656-673,1314-1316`).
  - Sound: 7 sound types, each with 3 recorded variants picked at random. Volume scales with ball
    size and is ×1.3 for events caused by the human (`src/sounds.py:11-56`;
    `src/engine.py:17-18,713-715`). Muted by default; M toggles it.
  - Fonts are cached (`src/renderer.py:628-633`).
- **Why it matters.** Medium for feedback patterns. It is also a warning: Rebound has none of the HP
  bars, action buttons, combat log or result screen our course requires, so it is no model for those.
- **Recommendation and our version:**
  - **Adopt** the event list. The battle emits plain events and the UI turns them into explosions
    (M1), log lines (M2) and sounds (M4). Low.
  - **Adapt** the stats counters into a result-screen summary per team: shots fired, shots that
    hit, damage dealt. Low.
  - **Adapt** the menu background as an optional M4 item: the title screen runs our headless
    AI-vs-AI battle behind the menu. Low–Medium, and only after M3.
  - **Adapt (optional)** sound variety and the mute key. Low.
  - **Adopt** font caching. Low.
  - **Reject** the aim line and any trajectory preview. Aiming is the skill in our game (an M0 decision).
  - **Our own addition** (Rebound has none): an expanding circle drawn for about 20 frames at
    each explosion event.

### 3.7 Testing practices
- **How [Code / Doc].**
  - pytest, with 184 tests that don't need a network [Doc].
  - A fixture per difficulty (`tests/conftest.py`).
  - Stress tests over 1,000–2,000 frames: balls stay inside the arena, never get stuck, and keep a
    radius of at least 2 (`tests/test_engine_physics.py`).
  - Parameter lists for difficulty values, and a seeded pacing comparison, "Hard ends faster than
    Easy" (`tests/test_difficulty_scaling.py:42-57`).
  - Mocked pygame for the renderer, menu and sound tests.
- **A warning example [Code + Inference].** `TestGameOverNoneWinner` (`tests/test_renderer.py:159-173`)
  re-computes the colour expression itself instead of calling `draw_game_over`, so it can never
  fail. Meanwhile the real `draw_game_over` (`src/renderer.py:651-658`) and `_draw_game_over_direct`
  (`:280-287`) index `WINNER_NAMES[None]` when there is no winner. That raises `TypeError`.
- **Recommendation: Adopt** seeded comparison tests and stress tests, using unittest's `subTest`
  for parameter lists and `setUp` helpers instead of fixtures. **Adopt the lesson:** a test must
  call the real function, and our Draw result must be tested end to end.
- **Complexity:** Low.

### 3.8 Networking, admin shell, RL training, obstacles, power-ups
**Reject all.** They are outside our scope (M0 non-goals), they add large dependencies, and they
earn nothing under our rubric. That covers the NATS server, HMAC-signed admin commands, the
Gymnasium environment, Stable-Baselines3 training, the rotating centre obstacle, timed obstacles
and the 12 power-ups.

---

## 4. Source path index

| Topic | Rebound path : lines | Label |
|---|---|---|
| Brick layout and spiral order | `src/engine.py:50-65` | Code |
| Projectile creation | `src/engine.py:67-81` | Code |
| Heuristic AI and its difficulty table | `src/engine.py:222-571`, `:241-268` | Code |
| AI bank shots and line of sight | `src/engine.py:271-427` | Code |
| AI threat prediction and shield | `src/engine.py:519-568` | Code |
| Difficulty-dependent engine rules | `src/engine.py:574-585`, `:955`, `:1236`, `:1242` | Code |
| Firing, sling momentum | `src/engine.py:836-886` | Code |
| Shield collision and reflection | `src/engine.py:908-947`, `:1151-1167` | Code |
| Projectile movement, sub-steps, bounce decay | `src/engine.py:999-1149` | Code |
| Castle damage, elimination, win | `src/engine.py:1282-1335`, `:994-997` | Code |
| Repair Kit, Healing Shield | `src/engine.py:1569-1577`, `:934-943` | Code |
| Sound events (engine side / UI side) | `src/engine.py:713-715`; `src/sounds.py:41-56` | Code |
| Headless-safe colour constants | `config.py:1-42` | Code |
| Brick damage visuals | `src/renderer.py:289-290`, `:329-343` | Code |
| Shield drawing, cached surfaces | `src/renderer.py:582-602` | Code |
| Aim line: ray cast / drawing | `src/renderer.py:380-542` / `:545-580` | Code |
| Stats HUD, game-over text | `src/renderer.py:635-658` | Code |
| Neural AI controller | `src/nn_controller.py:13-97` | Code |
| Model selection by difficulty | `src/game_client.py:31-37` | Code |
| Attract-mode menu | `src/menu.py:19-20,74-85` | Code |
| Physics and difficulty tests | `tests/test_engine_physics.py`, `tests/test_difficulty_scaling.py` | Code |

---

## 5. Adopt / Adapt / Reject summary

| Idea from Rebound | Decision | Complexity | Castle Siege milestone |
|---|---|---|---|
| Headless engine; only the UI imports pygame | Adopt (already our rule) | Low | M1 |
| Engine emits a per-update list of plain events for the UI | Adopt | Low | M1 (explosions), M2 (log), M4 (sound) |
| "Largest move per step < smallest target" invariant | Adapt (as a unit test, no sub-steps) | Low | M1 |
| Stress tests with seeded random input | Adopt | Low | M1, M3 |
| Damage-stage colours for bricks | Adapt (3 HP bands with cracks) | Low | M1 (colours), M4 (cracks) |
| Visible defend state | Adopt (bubble around defending characters) | Low | M2 |
| Small fixed-size repair | Adapt (75 HP pool; destroyed blocks stay destroyed) | Low | M2 |
| All difficulty numbers in one table | Adopt | Low | M3 |
| Seeded "harder difficulty does better" comparison test | Adopt | Low | M3 |
| Aim error as a target-point offset | Evaluated; kept as an alternative | Low | M3 (optional) |
| Stats counters | Adapt into result-screen stats | Low | M4 |
| AI battle running behind the menu | Adapt (optional) | Low–Medium | M4 |
| Sound variants, mute key | Adapt (optional) | Low | M4 |
| Font caching | Adopt | Low | M2 |
| Straight-line bouncing balls, decay, sling, hook | Reject | — | — |
| Position-independent brick damage | Reject | — | — |
| Deleting in-flight shots when a castle falls | Reject | — | — |
| Shield reflection, blockades, 12 power-ups | Reject | — | — |
| Difficulty that changes game rules | Reject | — | — |
| PPO neural-network AI | Reject | — | — |
| Bank-shot mirroring, threat prediction | Reject | — | — |
| Aim line / trajectory preview | Reject | — | — |
| NATS networking, admin shell, RL training | Reject | — | — |
| Dictionary state in one large engine class | Reject (we use small classes) | — | — |

---

## 6. License and academic integrity

- **License [Code, `LICENSE`]:** MIT, copyright 2026 Ryon Sherman. MIT allows reuse of the code
  as long as the copyright notice is kept.
- **The course's academic-integrity rules, not the MIT license, decide what we may submit.**
  Our policy:
  1. **No Rebound code** (not even small helpers), **no assets**, and no copied file layouts. Our
     code is written from our own design document.
  2. **Ideas only.** The ideas are listed in §5 and will be cited in the README ("References")
     and in the final report, with the repository URL and the commit studied.
  3. **Assets:** the power-up icons are credited to Nikoichu, "used with permission" [Doc,
     `README.md` credits]. That permission was given to Rebound's author; MIT does not pass it on to
     us [Inference]. The sound files have no stated source: there is no credits file, and the README
     credits only the icons [Code / Doc]. **We use none of them.**
  4. This review stays in our repository as evidence of an independent design process.
- **Similarity risk:** Low [Inference]. Our mechanics (gravity artillery, turn-based characters,
  HP-based castles) differ from Rebound's.
- **Question for the instructor:** is citing a public repository as an idea reference acceptable
  under the course policy? (M0 §13, Q4.)

---

## 7. Specific recommendations for Castle Siege

1. **M1:** `Battle` methods append plain dictionaries to a private event list. Once per frame,
   `main.py` calls `battle.take_events()`, which returns the list and empties it, so no event is
   lost. `main.py` turns each event into an explosion circle (M1), a log line (M2) or a sound (M4).
   This is one list with one reader, not an event bus.
2. **M1:** draw blocks in three HP-band colours. Crack lines come in M4.
3. **M1:** add a speed-bound unit test (fastest shot moves less than 28 px per step) and a sweep
   test showing that no legal shot (every angle and power) reaches the 600-step timeout. A test
   that only checks "the shot ended" could never fail, because the cap always ends it.
4. **M2:** capped Engineer Repair (75 HP pool, damaged surviving blocks only).
5. **M2:** a translucent bubble around defending characters.
6. **M3:** all AI numbers in `ai.DIFFICULTY`. Difficulty never changes game rules. Add a seeded
   comparison test: over N planned shots, the hit rate satisfies Hard ≥ Normal ≥ Easy.
7. **M4:** result-screen stats, an optional AI battle behind the title menu, and a mute key.
8. **M5:**
   - Check the install from a fresh environment (README steps vs. actual imports).
   - Test the Draw result end to end.
   - Check that every number quoted in the README and report matches the code. Rebound's
     3/4/5 vs 4/5/6 drift shows how easily they diverge.
9. **Never:** neural-network AI, networking, power-ups, bouncing shots, or difficulty-dependent rules.

---

## 8. Defects and inconsistencies noticed in Rebound (cautionary lessons)

| Finding | Evidence | Label |
|---|---|---|
| Online non-spectator drawing calls `draw_game(..., difficulty=...)`, but `draw_game` has no `difficulty` parameter, which raises `TypeError` | `game.py:349`, `src/renderer.py:102` | Inference (not executed) |
| Game-over drawing with no winner indexes `WINNER_NAMES[None]` | `src/renderer.py:280-287,651-658` | Inference |
| The test for that case re-implements the logic, so it can't fail | `tests/test_renderer.py:159-173` | Code |
| Pillow is imported but not listed in `requirements.txt` | `src/renderer.py:4` | Code |
| The README's install line omits the libraries needed by the bundled AI models | `README.md` Setup; `src/nn_controller.py:36-40` | Inference |
| Max-bounce values differ between docs (3/4/5) and code (4/5/6) | `README.md`, `TESTS.md`; `src/engine.py:579` | Code + Doc |
| The README's project tree lists files that are not in the repository (`PLAN.md`, `tests/test_wall_escape.py`, `tests/test_obstacles.py`, `tests/test_nats.py`, `tests/test_difficulty_pacing.py`) | `README.md` vs. the commit's file list | Code |
| `FRAME_SKIP = 4` is defined twice | `src/nn_controller.py:20,22` | Code |
| While a human holds Space, the shield timer is reset to 60 every frame and then decremented to 59, which matches the "first frame of activation" check. So a held shield would spend one defensive power-up charge **per frame**, and Fortify's doubled timer would be overwritten at once | `src/engine.py:737-741`, `:812-823` | Inference (not executed) |

---

## 9. Limitations of this review
- No Rebound code was run. Every behaviour above comes from reading the code and docs.
- The networking, admin, RL training and most test files were not read line by line.
- The model files were not downloaded, so the neural AI's behaviour is known only from the docs.
- Castle Siege numbers quoted here (hit rates, speed bound) come from our own throwaway
  simulation of **our** design (M0 §14), not from Rebound.
- An independent reviewer agent spot-checked about 30 of the citations against the clone. Its
  corrections were verified against the source before being applied (the shield duration, three
  line ranges, and the wording of the reflection angle and the 18-hit claim).
