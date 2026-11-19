# Castle Siege

A 2D side-view artillery game written in Python with Pygame, for the CS5001 final project.
Two castles face each other across a field, and each has a cannon on top of its tower.
Players take turns aiming and firing; explosions break the enemy castle's blocks.

**Current status: Milestone 1 (M1), the artillery prototype.** It has two castles, one cannon
each, gravity physics, explosions, castle damage and a win at 60 % destruction. Characters,
skills, the AI opponent and the full interface come in later milestones (see
[docs/M0_design.md](docs/M0_design.md), §11).

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

## Controls
| Key | Action |
|---|---|
| Up / Down | Raise / lower the active cannon's angle (5°–80°) |
| Left / Right | Decrease / increase power (10–100) |
| Shift + arrow | Change by 5 instead of 1 |
| Space | Fire |
| R | Restart the match |
| Esc | Quit |

Holding an arrow key keeps changing the value. SPACE fires once per press.

**If the keys don't respond:** click once inside the game window, so it has keyboard focus.
Chinese and other input methods (IMEs) are turned off inside the game window, so you don't need
to switch the keyboard to English first.

## How to play (M1)
- The left cannon shoots first, then the turns alternate: left, right, left, …
  The active cannon has a yellow ring, and the orange arrow shows its aim (longer = more power).
- A shot flies in an arc under gravity. It explodes when it hits an enemy block or the ground.
  Every enemy block whose centre is within 50 pixels of the explosion loses 50 HP (blocks start
  with 100 HP, so two hits destroy a block). Damaged blocks get darker, and destroyed blocks disappear.
- Shots fly straight through their own castle (there is no friendly fire). A shot that leaves
  the screen sideways is a miss.
- Each castle's destruction percentage is shown at the top. A castle that reaches **60 %**
  destruction loses. Press **R** to play again.

## Run the tests
From the project folder:
```
python -m unittest discover tests
```
The tests for the game logic (`castle.py`, `battle.py`, `characters.py`) do not need Pygame. The tests in
`tests/test_main.py` (keyboard handling, restart, window setup) need Pygame; they are skipped
if it isn't installed, and they never open a visible window.

## Project layout
| File | Purpose |
|---|---|
| `main.py` | Pygame window, keyboard input, drawing and the main loop (the only file that uses Pygame) |
| `battle.py` | Cannons, projectile physics, turns, explosions and victory rules |
| `castle.py` | `Block` and `Castle` classes: castle layout, damage and destruction percentage |
| `characters.py` | `Character` base class with `Knight`, `Archer`, `Engineer`: HP/ATK/DEF, damage, defend, cooldowns, EXP and levels (M2.1; not used by the game screen yet) |
| `tests/` | `unittest` tests for `castle.py`, `battle.py`, `characters.py` and `main.py` |
| `docs/M0_design.md` | Approved design: rules, architecture, roadmap |
| `docs/Rebound_reference_review.md` | Review of a reference project (ideas only) |

## References
- [ryonsherman/pygame-rebound](https://github.com/ryonsherman/pygame-rebound) (MIT License)
  was studied as an *idea* reference only (see `docs/Rebound_reference_review.md`).
  No code or assets from it are used in this project.
