# Castle Siege

A 2D side-view artillery game written in Python with Pygame, for the CS5001 final project.
Two castles face each other across a field, each with a cannon on top of its tower and a team
of characters (Knight, Archer, Engineer) standing behind it. The teams take turns: pick a
character, aim the cannon, and Attack, Defend or use a Special ability.

**Current status: Milestone 3.1 — Player vs AI.** You play the LEFT team against a computer
opponent (Easy, Normal or Hard) that picks and plays the RIGHT team. Two people can still play
each other on one computer ("Two players" mode). The design and roadmap are in
[docs/M0_design.md](docs/M0_design.md).

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
   - Click character cards to add them to your team; click again to remove one. Each card shows
     HP, ATK, DEF, castle damage and the special ability. Against the computer you pick only the
     LEFT team; the computer picks its own team of the same size when the battle starts.
   - A team can't have the same role twice. The first pick (Slot 1) stands nearest its castle.
   - Press **START BATTLE** when the team(s) are full.
2. **Battle.** The LEFT team moves first; then the turns alternate. On your turn:
   - **Choose who acts:** click one of your living characters, or press **1 / 2 / 3**. The chosen
     character has a yellow marker, and the panel shows its HP, ATK, DEF, Level, EXP and special.
   - **Aim** with the arrow keys (the orange arrow; longer means more power).
   - **Act:**
     - **ATTACK** (or **SPACE**) fires the cannon with that aim.
     - **DEFEND** halves the damage that character takes until your next turn.
     - **SPECIAL** uses its ability. A greyed-out button can't be used right now, and the panel
       says why.

   On the computer's turn the buttons are greyed out. After a short pause it chooses a character
   and an action by itself, and the combat log shows its choice (e.g. "AI (Normal): Archer
   attacks the LEFT castle.") and what happened.
3. **Result.** When a team wins, choose **Rematch** (same teams) or **Change teams**.
   **R** is a rematch shortcut.

The selection screen also has **Classic cannon duel (M1)**: the original two-cannon prototype
without characters (SPACE fires).

## Controls
| Input | Action |
|---|---|
| Mouse click | Team selection, choose a character, ATTACK / DEFEND / SPECIAL, Rematch / Change teams |
| 1 / 2 / 3 | Choose your character in slot 1, 2 or 3 |
| Up / Down | Raise / lower the cannon's angle (5°–80°) |
| Left / Right | Decrease / increase power (10–100) |
| Shift + arrow | Change by 5 instead of 1 |
| Space | ATTACK (in the classic duel: fire) |
| Enter | START BATTLE (selection screen) |
| R | Restart the match with the same teams |
| Esc | Quit |

Holding an arrow key keeps changing the value. SPACE acts once per press.

**If the keys don't respond:** click once inside the game window, so it has keyboard focus.
Chinese and other input methods (IMEs) are turned off inside the game window, so you don't need
to switch the keyboard to English first.

## Rules
- **Shots:** a shot flies in an arc under gravity. It explodes when it hits an enemy block, an
  enemy character or the ground. Shots pass through their own side (no friendly fire), and a shot
  that leaves the screen sideways is a miss.
- **Explosions:** every enemy block and character within 50 px of an explosion is damaged.
  - **Characters** take ATK − DEF damage (at least 1), or half that if they are defending.
  - **Blocks** take the attacker's castle damage: Knight 50, Archer 50, Engineer 60. Blocks start
    with 100 HP; damaged blocks get darker, and destroyed blocks disappear.
- **Specials:**
  - **Knight – Rally:** all living allies defend until your next turn. Cooldown 4 rounds.
  - **Archer – Power Shot:** an aimed shot doing ATK × 1.5 damage, ignoring DEF, and 75 per
    block. Cooldown 3.
  - **Engineer – Repair:** up to 75 castle HP, most damaged blocks first; destroyed blocks stay
    destroyed. Only possible when a block is damaged. Cooldown 4.

  A special used in round *r* is ready again in round *r + cooldown*. Each character shows
  "ready" or "wait N" under its feet.
- **EXP:** +10 for a shot that damages something, +20 more for each enemy it defeats, and +5 for
  Rally or Repair. Level-ups (30 × level EXP) raise HP, ATK and DEF, up to Level 5.
- **Winning:** defeat every enemy character, **or** destroy 60 % of the enemy castle (our extra
  rule; it can be switched off for elimination-only play with `Battle(castle_loss_enabled=False)`).
- **Damage formula:** deterministic, so tests can check exact numbers. The instructor's
  reference formula adds a random −5 to +10.

## The computer opponent (`ai.py`)
- It plays by the same rules as you: it can only act through the same `Battle.perform_action()`
  that the buttons use, so it can't use a special that is recharging, act with a defeated
  character, or act out of turn.
- **Aiming:** it "imagines" shots at many angles and powers on a copy of the battle (the real
  physics and damage rules run on the copy) and sees what each would hit. It ranks the options by
  how much closer each brings it to winning, then adds a random aiming error.
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
| `battle.py` | Cannons, projectile physics, turns, explosions and victory rules; `Team` and team combat (Attack / Defend / Special) |
| `castle.py` | `Block` and `Castle` classes: castle layout, damage, repair and destruction percentage |
| `characters.py` | `Character` base class with `Knight`, `Archer`, `Engineer`: HP/ATK/DEF, damage, defend, cooldowns, EXP, levels and each role's special ability |
| `tests/` | `unittest` tests for `castle.py`, `battle.py` (M1 duel), team combat (`test_combat.py`), `characters.py`, `ai.py` and `main.py` |
| `docs/M0_design.md` | Design: rules, architecture, roadmap (Revision 3 decisions at the top) |
| `docs/M3.1_balance_analysis.md` | Analysis of Defend and Repair under the current rules (recommendations only, nothing changed) |
| `docs/Rebound_reference_review.md` | Review of a reference project (ideas only) |

## References
- [ryonsherman/pygame-rebound](https://github.com/ryonsherman/pygame-rebound) (MIT License)
  was studied as an *idea* reference only (see `docs/Rebound_reference_review.md`).
  No code or assets from it are used in this project; its neural-network AI was not copied
  (our AI is a plain search over aims, written from scratch).
