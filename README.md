# Castle Siege

A 2D side-view artillery game written in Python with Pygame, for the CS5001 final project.
Two castles face each other across a field, each with a cannon on top of its tower and a team
of characters (Knight, Archer, Engineer) standing behind it. The teams take turns: pick a
character, aim the cannon, and Attack, Defend or use a Special ability.

**Current status: Milestone 2.3 — playable two-player game (hot seat).** Two people share the
mouse and keyboard and take turns. Player vs AI, the required final mode, comes in Milestone 3.
There is no AI in the game yet. The design and roadmap are in [docs/M0_design.md](docs/M0_design.md).

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
   - Choose **1 v 1**, **2 v 2** or **3 v 3** (characters per team).
   - Click character cards to add them to the LEFT and RIGHT teams; click again to remove one.
     Each card shows HP, ATK, DEF, castle damage and the special ability.
   - A team can't have the same role twice. The first pick (Slot 1) stands nearest its castle.
   - Press **START BATTLE** when both teams are full.
2. **Battle.** The LEFT team moves first; then the turns alternate. On your turn:
   - **Choose who acts:** click one of your living characters, or press **1 / 2 / 3**. The chosen
     character has a yellow marker, and the panel shows its HP, ATK, DEF, Level, EXP and special.
   - **Aim** with the arrow keys (the orange arrow; longer means more power).
   - **Act:**
     - **ATTACK** (or **SPACE**) fires the cannon with that aim.
     - **DEFEND** halves the damage that character takes until your next turn.
     - **SPECIAL** uses its ability. A greyed-out button can't be used right now, and the panel
       says why.
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

## Run the tests
From the project folder:
```
python -m unittest discover tests
```
- The tests for the game logic (`castle.py`, `battle.py`, `characters.py`) don't need Pygame.
- The tests in `tests/test_main.py` (screens, buttons, keyboard and mouse handling, window setup)
  need Pygame. They are skipped if it isn't installed, and they never open a visible window.

## Project layout
| File | Purpose |
|---|---|
| `main.py` | Pygame window, screens (team selection, battle, result), buttons, mouse and keyboard input, drawing and the main loop (the only file that uses Pygame) |
| `battle.py` | Cannons, projectile physics, turns, explosions and victory rules; `Team` and team combat (Attack / Defend / Special) |
| `castle.py` | `Block` and `Castle` classes: castle layout, damage, repair and destruction percentage |
| `characters.py` | `Character` base class with `Knight`, `Archer`, `Engineer`: HP/ATK/DEF, damage, defend, cooldowns, EXP, levels and each role's special ability |
| `tests/` | `unittest` tests for `castle.py`, `battle.py` (M1 duel), team combat (`test_combat.py`), `characters.py` and `main.py` |
| `docs/M0_design.md` | Design: rules, architecture, roadmap (Revision 3 decisions at the top) |
| `docs/Rebound_reference_review.md` | Review of a reference project (ideas only) |

## References
- [ryonsherman/pygame-rebound](https://github.com/ryonsherman/pygame-rebound) (MIT License)
  was studied as an *idea* reference only (see `docs/Rebound_reference_review.md`).
  No code or assets from it are used in this project.
