# Castle Siege

A 2D side-view artillery game written in Python with Pygame, for the CS5001 final project.
Two teams of characters (Knight, Archer, Engineer) face each other across a field. Each team
stands behind its own cover blocks and shares one cannon standing in front of the cover. The
teams take turns: pick a character, aim the cannon, and Attack, Defend or use a Special ability.
**You win by defeating every enemy character.**

**Current status: Milestone 3.4-A — combat foundation.**
- Only elimination wins. Castle destruction is no longer a victory condition.
- Each team's cover is a layout of up to 6 blocks on 8 fixed slots, and cover shields characters
  from explosions.
- Both teams currently use the same default cover. Choosing your own layout on a placement screen
  is planned for M3.4-B, and the characters' run to the cannon for M3.4-C.

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
       same size when the battle starts.
   - A team can't have the same role twice. The first pick (Slot 1) stands at the front, right
     behind the cover.
   - Press **START BATTLE** when the team(s) are full.
2. **Battle.** The LEFT team moves first in the first match, then the turns alternate.
   - **The HUD** shows the round (e.g. "Round 7 / 30") and, for each team, how many characters
     are still standing and how many cover blocks are left (e.g. "LEFT  2/3 standing   cover 5/6").
   - **Choose who acts:** click one of your living characters, or press **1 / 2 / 3**. The chosen
     character has a yellow marker, and the panel shows its HP, ATK, DEF, Level, EXP and special.
   - **Aim** with the arrow keys (the orange arrow; longer means more power).
   - **Act:**
     - **ATTACK** (or **SPACE**) fires your team's cannon with that aim and the chosen
       character's stats.
     - **DEFEND** halves the damage that character takes until your next turn, and also halves
       the damage enemy shots do to your cover blocks (**Cover Guard**).
     - **SPECIAL** uses its ability. A greyed-out button can't be used right now, and the panel
       says why.

   On the computer's turn the buttons are greyed out. After a short pause it chooses a character
   and an action by itself. The combat log shows its choice (e.g. "AI (Normal): Archer attacks
   the LEFT Knight.") and what happened.
3. **Result.** The result screen shows the winner, or DRAW, why the match ended and how many
   rounds were played.
   - Choose **Rematch** (same teams, same cover, same computer level) or **Change teams**.
     **R** is a rematch shortcut (it also restarts a match in progress).
   - **Who moves first alternates:** each rematch swaps the side that moves first (LEFT, RIGHT,
     LEFT, …). Choosing teams again starts with LEFT. When the computer moves first, it plays its
     turn by itself.

## Controls
| Input | Action |
|---|---|
| Mouse click | Team selection, choose a character, ATTACK / DEFEND / SPECIAL, Rematch / Change teams |
| 1 / 2 / 3 | Choose your character in slot 1, 2 or 3 |
| Up / Down | Raise / lower the cannon's angle (5°–80°) |
| Left / Right | Decrease / increase power (10–100) |
| Shift + arrow | Change by 5 instead of 1 |
| Space | ATTACK |
| Enter | START BATTLE (selection screen) |
| R | Rematch: restart with the same teams and cover (the side that moves first swaps) |
| Esc | Quit |

Holding an arrow key keeps changing the value. SPACE acts once per press.

**If the keys don't respond:** click once inside the game window, so it has keyboard focus.
Chinese and other input methods (IMEs) are turned off inside the game window, so you don't need
to switch the keyboard to English first.

## Rules
- **Battlefield:** each side, from the edge of the screen inward, has its characters (slots 1–3),
  then its cover slots, then its cannon. The two sides are mirror images.
- **Cover:** each team may place up to **6 blocks** (100 HP each) on its **8 fixed cover slots**,
  in 4 columns × 2 rows.
  - A raised block must stand on a block.
  - A slot holds one block.
  - Blocks never overlap characters, cannons or the screen's text and buttons.
  - Unused blocks give no protection. A team may even place none.
  - For now (M3.4-A) both teams use the default cover: the whole bottom row plus the two raised
    blocks nearest the characters.
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
- **Winning:** defeat every enemy character. Destroying blocks never wins by itself.
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

## The computer opponent (`ai.py`)
- It plays by the same rules as you: it can only act through the same `Battle.perform_action()`
  that the buttons use, so it can't use a special that is recharging, act with a defeated
  character, or act out of turn.
- **Aiming:** it "imagines" shots at many angles and powers on a copy of the battle (the real
  physics and damage rules run on the copy) and sees what each would hit. It ranks the options by
  how much damage each does to the enemy characters, then adds a random aiming error. Repair is
  chosen when restoring cover is worth more.
- **Not yet (M3.4-B):** it does not yet plan around cover or try to break the blocks protecting
  a character.
- **Defending:** when one of its characters is below half HP, it is more likely to Defend (or to
  use the Knight's Rally). It never defends two turns in a row.
- **Difficulty** changes only how carefully it chooses and how accurately it aims:

| | Easy | Normal | Hard |
|---|---|---|---|
| Aiming error (angle / power, up to ±) | 6° / 8 | 3° / 4 | 1° / 2 |
| Chooses among the best … options | 5 | 3 | 1 (always the best) |
| Considers specials on a turn | 25 % | 50 % | 100 % |
| Defend chance (all at least half HP / one below half HP) | 10 % / 40 % | 5 % / 50 % | 0 % / 60 % |

## Run the tests
From the project folder:
```
python -m unittest discover tests
```
- The tests for the game logic (`castle.py`, `battle.py`, `characters.py`) and for the computer
  opponent (`ai.py`) don't need Pygame. The AI tests use fixed random seeds, so every run gives
  the same results.
- The tests in `tests/test_main.py` (screens, buttons, keyboard and mouse handling, window setup)
  need Pygame. They are skipped if it isn't installed, and they never open a visible window.

## Project layout
| File | Purpose |
|---|---|
| `main.py` | Pygame window, screens (team selection, battle, result), buttons, mouse and keyboard input, the computer's turn, drawing and the main loop (the only file that uses Pygame) |
| `ai.py` | `AIController`: the computer opponent (team choice, Defend / Attack / Special choice, aiming) and its difficulty table |
| `battle.py` | Cannons, projectile physics, collision along the flight path, explosions and cover, turns, the round limit and victory; `Team` and team combat (Attack / Defend / Special) |
| `castle.py` | `Block`, the 8 cover slots and layout rules (`layout_problem`), and `Castle` (one team's cover): damage and repair |
| `characters.py` | `Character` base class with `Knight`, `Archer`, `Engineer`: HP/ATK/DEF, damage, defend, cooldowns, EXP, levels and each role's special ability |
| `tests/` | `unittest` tests for `castle.py`, `battle.py` (physics and collision), team combat and cover (`test_combat.py`), `characters.py`, `ai.py` and `main.py` |
| `docs/M0_design.md` | Design: rules, architecture, roadmap (the latest decisions at the top) |
| `docs/M3.1_balance_analysis.md` | M3.1 analysis of Defend and Repair (recommendations only, nothing changed) |
| `docs/M3.2_balance_report.md` | M3.2 balance experiment under the old castle rules (historical; its script is in commit `86b90fa`) |
| `docs/M3.2_benchmark_results.md`, `docs/M3.2_benchmark_results_easy.md` | That benchmark's generated result tables (historical) |
| `docs/M3.3_course_compliance.md` | Course requirements checklist: what is verified, what awaits a manual check, what is missing, and our custom rules (updated for M3.4-A) |
| `docs/Rebound_reference_review.md` | Review of a reference project (ideas only) |

## References
- [ryonsherman/pygame-rebound](https://github.com/ryonsherman/pygame-rebound) (MIT License)
  was studied as an *idea* reference only (see `docs/Rebound_reference_review.md`).
  No code or assets from it are used in this project; its neural-network AI was not copied
  (our AI is a plain search over aims, written from scratch).
