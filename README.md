# Castle Siege

A 2D side-view artillery game written in Python with Pygame, for the CS5001 final project.
Two teams of characters (Knight, Archer, Engineer) face each other across a field. Each team
stands behind its own cover blocks and shares one cannon standing in front of the cover. The
teams take turns: pick a character, aim the cannon, and Attack, Defend or use a Special ability.
**You win by defeating every enemy character.**

**Current status: Milestone 4.2-B — Defend redesign (Guarded Strike and the anti-stall rule).**
- Only elimination wins. Castle destruction is not a victory condition.
- Before each battle, every team places its own cover: up to 6 blocks on 8 fixed slots. Against
  the computer you place the LEFT cover and the computer places its own.
- The computer breaks cover on purpose when that cover stands between its cannon and one of your
  characters.
- M3.4-B.1: the Easy computer aims a little better (4° / 5 instead of 6° / 8). Before that, most
  Easy-vs-Easy 3v3 matches ran out of rounds without a winner.
- M3.4-C: an attacking character runs to its team's cannon, fires it and runs back (see
  *The run to the cannon* below). It is a visual effect only: no rule changed.
- M4.1: clearer screens (see *What the screen shows* below): a turn banner that says what is
  happening, floating damage numbers, see-through explosions, cracked and destroyed cover,
  distinct win and draw screens. **Cosmetic only: no game rule, AI choice or number changed.**
- M4.2-A: sound effects made in code (M turns them off), a battlefield with a sky, hills and a
  flag for each team, team emblems (LEFT circle, RIGHT diamond) so the teams differ by shape
  as well as colour, and name plates. **Presentation only: no rule changed.**
- M4.2-B: **a gameplay change**, approved after a design review: a Defend now also gives that
  character **Guarded Strike** (its Attack in your team's next turn uses ATK × 1.25), and a team
  **can't Defend two turns in a row**. Defend still halves the damage the defender takes.

You play the LEFT team against a computer opponent (Easy, Normal or Hard), or two people play
each other on one computer. The design and roadmap are in [docs/M0_design.md](docs/M0_design.md).

## Requirements
- Python 3 (developed and tested with Python 3.11.9 on Windows)
- Pygame 2.6.1 (installed from `requirements.txt`)

## Set up and run (VS Code or any terminal)
1. Open the project folder in VS Code, then open a terminal (**Terminal → New Terminal**).
2. Create and activate a virtual environment (recommended, so Pygame is installed only for this project):
   - Windows (PowerShell):
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
     If PowerShell refuses to run the script, run
     `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use Command Prompt with
     `.venv\Scripts\activate.bat`.
   - macOS / Linux:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
3. Install Pygame:
   ```
   pip install -r requirements.txt
   ```
4. Start the game:
   ```
   python main.py
   ```

In VS Code you can also pick the `.venv` interpreter (**Python: Select Interpreter**) and press
**Run Python File** while `main.py` is open.

## How to play
1. **Team selection.**
   - **Mode:** **Player vs AI** (the default: you are LEFT, the computer is RIGHT) or
     **Two players** (both teams are played on this computer, taking turns).
   - **Computer:** **Easy**, **Normal** (default) or **Hard** (Player vs AI only).
   - Choose **1 v 1**, **2 v 2** or **3 v 3** (characters per team).
   - Click character cards to add them to your team; click again to remove one.
     - Each card shows HP, ATK, DEF, block damage and the special ability.
     - Against the computer you pick only the LEFT team; the computer picks its own team of the
       same size when the battle starts (its cards say "THE COMPUTER PICKS").
   - A team can't have the same role twice. The first pick (Slot 1) stands at the front, right
     behind the cover.
   - Press **PLACE COVER** when the team(s) are full.
2. **Cover placement.** One team at a time sees its own side of the battlefield: its characters,
   its cannon and its 8 cover slots, exactly where they will be in the battle.
   - Click an **empty slot** (light, with a "+") to place a block. Click a **block** to remove it.
   - "Blocks: 4 / 6" and six small squares show how many of the 6 blocks are used. You may
     confirm any cover from 0 to 6 blocks.
   - A raised slot needs a block under it. A slot that can't take a block right now (no block
     under it, or all 6 blocks used) shows an "×". Removing a lower block also removes the
     block on top of it, and the status line says so.
   - The screen starts with the default cover (the whole bottom row plus the two raised slots
     next to the characters), so you can also just press **Confirm**.
   - **Against the computer:** you place the LEFT cover, then **Confirm** starts the battle. The
     computer places its RIGHT cover by itself.
   - **Two players:** LEFT places first, then **Confirm** shows RIGHT's screen. The other team's
     cover stays hidden until the battle starts.
   - **Back** returns to the previous step (RIGHT's screen → LEFT's → team selection) without
     losing the teams or the cover already placed. Cover choices are also kept when you change
     the teams, because characters never stand on cover slots.
3. **Battle.** The LEFT team moves first in the first match, then the turns alternate.
   - **The HUD** has a turn banner in the colour of the team to move, with the round and what
     is happening (e.g. "Round 7 / 30   LEFT TEAM'S TURN (you): aim and act"), the result of
     the last action under it, and for each team how many characters are still standing and how
     many cover blocks are left (e.g. "LEFT  2/3 standing   cover 5/6").
   - **Choose who acts:** click one of your living characters, or press **1 / 2 / 3**. The chosen
     character has a yellow marker, and the panel shows its HP, ATK, DEF, Level, EXP and special.
   - **Aim** with the arrow keys (the orange arrow; longer means more power). The angle and
     power are shown in the panel (with a power bar) and under the cannon.
   - **Act:**
     - **ATTACK** (or **SPACE**) fires your team's cannon with that aim and the chosen
       character's stats. The character first runs to the cannon; the shot leaves when it gets
       there, and it runs back while the shot flies.
     - **DEFEND** halves the damage that character takes until your next turn, and also halves
       the damage enemy shots do to your cover blocks (**Cover Guard**). It also gives that
       character **Guarded Strike** for your next turn (a gold star beside its name), and your
       team can't DEFEND again on that next turn (the button is greyed out and says why).
     - **SPECIAL** uses its ability. A greyed-out button can't be used right now, and the panel
       says why.

   On the computer's turn the buttons are greyed out. After a short pause it chooses a character
   and an action by itself. The combat log shows its choice (e.g. "AI (Normal): Archer attacks
   the LEFT Knight." or "AI (Hard): Engineer attacks the cover in front of the LEFT Knight.") and
   what happened. Its attacks take the same run to the cannon as yours.
4. **Result.** The result screen shows the winner (in that team's colour) or DRAW (in amber,
   "Time limit reached"), why the match ended and the final round.
   - Choose **Rematch** (same teams, both covers, same computer level; every character and block
     starts at full HP again) or **Change teams** (back to team selection; your cover choices are
     kept).
     **R** is a rematch shortcut (it also restarts a match in progress).
   - **Who moves first alternates:** each rematch swaps the side that moves first (LEFT, RIGHT,
     LEFT, …). Choosing teams again starts with LEFT. When the computer moves first, it plays its
     turn by itself.

## Controls
| Input | Action |
|---|---|
| Mouse click | Team selection, cover slots, Back / Confirm, choose a character, ATTACK / DEFEND / SPECIAL, Rematch / Change teams |
| 1 / 2 / 3 | Choose your character in slot 1, 2 or 3 |
| Up / Down | Raise / lower the cannon's angle (5°–80°) |
| Left / Right | Decrease / increase power (10–100) |
| Shift + arrow | Change by 5 instead of 1 |
| Space | ATTACK |
| Enter | PLACE COVER (selection screen), Confirm (cover screen) |
| Backspace | Back (cover screen) |
| R | Rematch: restart with the same teams and cover (the side that moves first swaps) |
| M | Sound on / off (any screen) |
| Esc | Quit |

Holding an arrow key keeps changing the value. SPACE acts once per press. While a character
runs to the cannon and back, the combat keys and buttons do nothing (R and Esc still work).

**If the keys don't respond:** click once inside the game window, so it has keyboard focus.
Chinese and other input methods (IMEs) are turned off inside the game window, so you don't need
to switch the keyboard to English first.

## Rules
- **Battlefield:** each side, from the edge of the screen inward, has its characters (slots 1–3),
  then its cover slots, then its cannon. The two sides are mirror images.
- **Cover:** each team places up to **6 blocks** (100 HP each) on its **8 fixed cover slots**,
  in 4 columns × 2 rows, before the battle (see *Cover placement* above).
  - A raised block must stand on a block. A slot holds one block. There is no free placement:
    only the 8 slots.
  - Blocks never overlap characters, cannons or the screen's text and buttons.
  - Unused blocks give no protection. A team may even place none.
  - One function, `castle.layout_problem()`, decides whether a layout is legal. The placement
    screen, the computer and the battle all use it, so an illegal layout can never reach a battle.
  - **Why cover exists:** with nothing in the way, the first accurate shots would decide the match.
    Cover makes a team choose between a hard shot over or around the blocks and breaking the
    blocks first, and it gives Defend (Cover Guard) and the Engineer's Repair something to protect.
- **Shots:** a shot flies in an arc under gravity. It explodes on the **first** enemy block or
  enemy character it touches, or on the ground.
  - The whole path of every step is checked, so a fast shot can't jump through a thin target.
  - Shots pass through their own side (no friendly fire).
  - A shot that leaves the screen sideways is a miss.
  - Destroyed blocks and defeated characters no longer stop shots.
- **Explosions:**
  - A **directly hit** character takes ATK − DEF damage (at least 1), or half that if it is
    defending.
  - Every other enemy character within 50 px takes the same damage, **unless a standing block of
    its team is on the straight line between the explosion and the character**. That block is
    **cover** and absorbs the whole blast for that character. The log says "… was shielded by
    cover."
  - Every enemy block within 50 px takes the attacker's block damage: Knight 50, Archer 50,
    Engineer 60. Damaged blocks get darker, and destroyed blocks disappear.
  - Everything is decided at the moment of impact, before any damage is done. So a block that
    this explosion destroys still shields the characters behind it from this explosion, but not
    from the next one.
  - Characters behind cover can still be hit by a shot that comes down on them from above.
- **Cover Guard** (called Castle Guard before M3.4):
  - While one of a team's characters is defending (Defend or Rally), enemy shots do half damage
    to that team's blocks, rounded down (50 → 25, 60 → 30, Power Shot 75 → 37).
  - It ends with the Defend, when that team's next turn starts, so it covers one enemy action.
  - Several defenders don't add up: it is always half.
  - Guarded cover has a blue outline and a **GUARDED** badge.
- **Guarded Strike (M4.2-B):** a basic Defend gives the defender Guarded Strike for its team's
  **next turn only**.
  - If that character makes a normal **Attack** in that turn, the shot uses **ATK × 1.25**, then
    DEF, minimum 1, halved against a defender: the same formula Power Shot uses with × 1.5. For
    example, a Knight hits an enemy Knight for 25 instead of 18. Block damage is unchanged.
  - It is used up by that Attack. If another character acts, or the defender uses its special
    (Power Shot keeps its own × 1.5), it expires at the end of that turn ("expired").
  - It never stacks, and Rally does not give it.
  - A hollow gold star beside the name means "next turn"; a filled star means "this turn's
    Attack is stronger"; "+25%" floats up when it is used.
- **Anti-stall (M4.2-B):** a team can't Defend two turns in a row (Rally doesn't count). Without
  this rule, a team that is behind could defend every turn to reach the round-30 draw. The
  computer has always played this way.
- **Specials:**
  - **Knight – Rally:** all living allies defend until your next turn (so the cover is guarded
    too). Cooldown 4 rounds.
  - **Archer – Power Shot:** an aimed shot doing ATK × 1.5 damage, ignoring DEF, and 75 per
    block. Cooldown 3.
  - **Engineer – Repair:** up to 150 HP for the team's damaged blocks, most damaged first.
    - No block goes above 100 HP, and destroyed blocks are not rebuilt.
    - Only possible when a standing block is damaged.
    - Cooldown 4.

  A special used in round *r* is ready again in round *r + cooldown*. Each character shows
  "ready" or "wait N" under its feet.
- **EXP:** +10 for a shot that damages something, +20 more for each enemy it defeats, and +5 for
  Rally or Repair. Level-ups (30 × level EXP) raise HP, ATK and DEF, up to Level 5.
- **Winning:** defeat every enemy character. Destroying blocks never wins by itself. This is the
  course's core requirement (character elimination), and it keeps the cover what it is meant to
  be: protection, not a target worth winning for.
- **Round limit (our safety rule, not a course requirement):** a match that reaches the end of
  round 30 without an elimination is a **draw** (a timeout).
  - A round is complete once both teams have acted, whichever side started.
  - An elimination always counts first, even on the very last turn.
  - HP and cover never pick a winner.
- **Damage formula:** deterministic, so tests can check exact numbers. The instructor's
  reference formula adds a random −5 to +10.
- **Balance:** Cover Guard 50 % and Repair 150 come from the M3.2 balance work
  (`docs/M3.2_balance_report.md`). That benchmark measured the old castle rules, so its numbers
  don't apply to M3.4. Not yet confirmed by human play-testing.

## What the screen shows (M4.1, cosmetic only)
Nothing in this section changes a rule, the computer's choices or any number: it only changes
what is drawn and what the text says.
- **Turn banner:** whose turn it is, who plays it ("you" or "computer") and the phase: *aim and
  act*, *running to the cannon*, *shot in the air*, *thinking...* (the computer), *waiting* (the
  last shooter is still running back) or *game over*.
- **Status line:** keeps the result of the last action ("LEFT Knight takes 28 damage."); new
  rounds and EXP are only in the combat log. When the computer moves first it says so, and
  nothing asks you to act.
- **The computer's turn:** no character is marked until the computer has chosen, and the panel
  says it is thinking.
- **Damage:** a red "-28" floats up from a hit character for a second ("DEFEATED" when it falls,
  "shielded" when cover protected it). Explosions are see-through, so the character they hit
  stays visible. HP bars have an outline and turn orange below half HP and red below a quarter.
- **Cover:** damaged blocks get darker and show one crack below 80 % HP and two below 40 %. A
  destroyed block leaves a dashed outline; it is only a picture and stops nothing.
- **Shots:** a short trail of dots follows every shot. A Power Shot is bigger and orange, with a
  bigger muzzle flash.
- **Readability:** names on the battlefield use darker team colours (contrast at least 4.5 : 1
  against the sky); the chosen character has a thicker yellow box; buttons light up under the
  mouse.
- **Result screen:** a coloured title band (the winner's colour, or amber for a draw) with
  "Victory by elimination" or "Time limit reached", and "Final round: N / 30".

## Sound and atmosphere (M4.2-A, presentation only)
- **Sound effects**, made in code by `sound.py` (no sound files, so nothing to license): the
  cannon firing, the explosion, a block hit, a block destroyed, a level-up, and a tune for a
  victory, a defeat (against the computer) or a draw. Each plays once, when the game reads the
  matching Battle event; Defend, Rally, Repair and refused actions are silent. A rematch, new
  teams or quitting stop every sound.
- **M** turns the sound off and on, on every screen; the combat log heading shows which.
- **No audio device?** The game is silent and works exactly the same (the mixer is optional).
- **The battlefield** has a sky that lightens toward the horizon, a few clouds, pale far hills
  with two distant castles, green near hills and each team's flag. It is drawn once, as a
  picture: nothing in it stops a shot, and no hit box, trajectory or rule changed.
- **Teams by shape:** LEFT's emblem is a circle and RIGHT's a diamond, on every character's chest,
  on the flags, in the HUD and in the turn banner, so the colours are not the only clue.
- **Readability:** names and HP bars sit on light plates; the turn banner is bold and the team
  lines smaller; floating damage words never overlap (a new one moves up); the cover screen's
  text has a plate too.

## The run to the cannon (M3.4-C)
- **One shared cannon per team.** Every character of a team attacks through the same cannon,
  which stands in front of the team's cover. The shot always starts at the cannon, and its
  damage uses the stats of the character who fired it.
- **The animation.** When you choose ATTACK (or the Archer's Power Shot), the character runs from
  its slot to the cannon (1/3 s), fires it with a short muzzle flash (1/5 s), and runs back
  (1/3 s) while the shot flies. The shot is fired exactly once, on the frame the character
  reaches the cannon; the flash starts on that same frame. Defend, Rally and Repair still happen
  at once, without a run.
- **Positions and hit boxes don't move.** The Battle (`battle.py`) keeps every character in its
  slot. Only the drawing moves: the name, HP bar and cooldown stay over the slot, and nothing can
  hit the runner, because the enemy can't act until it is back. So the animation can never change
  a collision, the damage or the flight of a shot.
- **The Battle still runs the turn.** The turn ends when the shot lands and the Battle applies
  its damage, as before. If the shot lands before the character is back (a very short shot), the
  next team waits: its buttons and keys, and the computer, start only when the character is back
  in its slot.
- **The computer uses the same run.** It decides what to do (`AIController.choose`), turns its
  cannon, and its character runs to the cannon; the plan is carried out
  (`AIController.carry_out`, which calls `Battle.perform_action`) only when the character gets
  there. The computer's aim and choices are unchanged.
- **R and Esc stay instant.** R during a run cancels it and restarts the match as before (the
  side that moves first swaps), and nothing is fired later. A new match, Change teams and
  quitting also stop a run. If the match ends while a character is still running back, it
  finishes behind the result screen.
- **Simplified on purpose:** the run is a straight line at an even speed, with no collision,
  jumping or path-finding, so a runner passes in front of the cover and of team-mates nearer the
  cannon. Legs swap and the body bobs every 5 frames; the cannon itself never moves. Drawn only
  with Pygame shapes (no sprite images).

## The computer opponent (`ai.py`)
- It plays by the same rules as you: it can only act through the same `Battle.perform_action()`
  that the buttons use, so it can't use a special that is recharging, act with a defeated
  character, or act out of turn. Its attacks take the same run to the cannon as yours (M3.4-C).
- **Its cover:** before the battle it builds a two-block tower on the slots next to its
  characters, where enemy shots come down on its front character, then places its other 4 blocks
  one at a time on random slots where a block is allowed. The same 6-block budget and the same
  `layout_problem()` check as yours. It never looks at your cover. (It can build six different
  layouts; with a fixed seed it always builds the same one.)
- **Aiming:** it "imagines" shots at many angles and powers on a copy of the battle (the real
  physics and damage rules run on the copy) and sees what each would do. Each aim scores:
  - **damage** to your characters (and a bonus for defeating one), or
  - **opening a shot:** for every aim that ends on a block, it traces the rest of the path
    (`Battle.path_contacts`). If one of your living characters stands behind those blocks, the
    blocks are *in the way*. A shot that damages blocks in the way scores the share of their HP it
    removes × the value of hitting that character, counted at half (the payoff is a turn later,
    and you may Repair). A block that is in nobody's way is worth nothing, so it never wastes
    turns on harmless cover.
  - It knows its own aiming error, so it rates each aim by the average of the aims around it that
    it might really fire. A narrow gap over the cover is worth less than a wide one, which is why
    a protected character makes breaking the cover attractive.
  - It picks one of its best aims, then adds a random aiming error. Repair is chosen when
    restoring cover is worth more.
- **Defending:** when one of its characters is below half HP, it is more likely to Defend (or to
  use the Knight's Rally). It never defends two turns in a row, so it keeps the anti-stall rule.
  It imagines its shots with the real rules, so it values a ready Guarded Strike by itself.
- **Difficulty** changes only how carefully it chooses and how accurately it aims:

| | Easy | Normal | Hard |
|---|---|---|---|
| Aiming error (angle / power, up to ±) | 4° / 5 (6° / 8 before M3.4-B.1) | 3° / 4 | 1° / 2 |
| Chooses among the best … targets (a character, or the cover in front of one) | 4 | 3 | 1 (always the best) |
| Considers specials on a turn | 25 % | 50 % | 100 % |
| Defend chance (all at least half HP / one below half HP) | 10 % / 40 % | 5 % / 50 % | 0 % / 60 % |

## Run the tests
From the project folder:
```
python -m unittest discover tests
```
- The tests for the game logic (`castle.py`, `battle.py`, `characters.py`), the computer
  opponent (`ai.py`) and the run's timing and positions (`animation.py`) don't need Pygame. The
  AI tests use fixed random seeds, so every run gives the same results.
- The tests in `tests/test_main.py` (screens, buttons, keyboard and mouse handling, window setup,
  which sounds play) and `tests/test_sound.py` (the sound effects and the silent fallback) need
  Pygame. They are skipped if it isn't installed; they never open a visible window or make a sound.

## Project layout
| File | Purpose |
|---|---|
| `main.py` | Pygame window, screens (team selection, cover placement, battle, result), buttons, mouse and keyboard input, the computer's turn, when an attack is fired (after the run), drawing and the main loop |
| `drawing.py` | The screens' shared look: colours, text, character figures (standing, running, firing), cover blocks (cracks, destroyed outline), HP-bar colours and buttons (moved out of `main.py` in M3.4-B; with `main.py`, the only files that use Pygame) |
| `sound.py` | Sound effects made in code and `SoundBoard` (M4.2-A): plays them, stops them, mutes; silent without an audio device |
| `animation.py` | `CannonRun` (M3.4-C): the states and frames of a character's run to the cannon and back, and where to draw it; no Pygame, never changes the Battle |
| `ai.py` | `AIController`: the computer opponent (team and cover choice, Defend / Attack / Special choice, cover-aware aiming) and its difficulty table |
| `battle.py` | Cannons, projectile physics, collision along the flight path, explosions and cover, turns, the round limit and victory; `Team` and team combat (Attack / Defend / Special); `path_contacts` for the computer's planning |
| `castle.py` | `Block`, the 8 cover slots, the layout rules (`layout_problem`) and the placement clicks (`place_block`, `remove_block`), and `Castle` (one team's cover): damage and repair |
| `characters.py` | `Character` base class with `Knight`, `Archer`, `Engineer`: HP/ATK/DEF, damage, defend, cooldowns, EXP, levels and each role's special ability |
| `tests/` | `unittest` tests for `castle.py`, `battle.py` (physics and collision), team combat and cover (`test_combat.py`), `characters.py`, `ai.py`, `animation.py`, `sound.py` and `main.py` |
| `docs/M0_design.md` | Design: rules, architecture, roadmap (the latest decisions at the top) |
| `docs/M3.1_balance_analysis.md` | M3.1 analysis of Defend and Repair (recommendations only, nothing changed) |
| `docs/M3.2_balance_report.md` | M3.2 balance experiment under the old castle rules (historical; its script is in commit `86b90fa`) |
| `docs/M3.2_benchmark_results.md`, `docs/M3.2_benchmark_results_easy.md` | That benchmark's generated result tables (historical) |
| `docs/M3.3_course_compliance.md` | Course requirements checklist: what is verified, what awaits a manual check, what is missing, and our custom rules (updated for M4.2-B) |
| `docs/M4.2-B_defend_design_review.md` | M4.2-B: the audit of Defend and the redesign that was approved and built (Guarded Strike, anti-stall) |
| `docs/Rebound_reference_review.md` | Review of a reference project (ideas only) |

## References
- [ryonsherman/pygame-rebound](https://github.com/ryonsherman/pygame-rebound) (MIT License)
  was studied as an *idea* reference only (see `docs/Rebound_reference_review.md`).
  No code or assets from it are used in this project; its neural-network AI was not copied
  (our AI is a plain search over aims, written from scratch).
