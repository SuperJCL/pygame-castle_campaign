# Castle Siege

A 2D side-view artillery game written in Python with Pygame, for the CS5001 final project.
Two teams of characters (Knight, Archer, Engineer, Gunner, Bombardier, Medic) face each other
across a field. Each team
stands behind its own cover blocks and shares one cannon standing in front of the cover. The
teams take turns: pick a character, aim the cannon, and Attack, Defend or use a Special ability.
**You win by defeating every enemy character.**

**Current status: Milestone 5.2-B — the final report as a PDF (`docs/Castle_Siege_Final_Report.pdf`); the code is frozen at commit `a4ceef8`.**
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
- M4.3: a full regression of every mode, size, cover type and first mover through the real
  interface; no gameplay defect was found and no rule changed
  (`docs/M4.3_stabilization_report.md`, screenshots in `docs/screenshots/`).
- M5.1: a requirement-to-evidence audit, a draft of the final report (with the 300–500-word
  explanation) and a class diagram. No code changed.
- M5.2-A: **a defend sound** (the instructor asks for sounds for attack, defence, victory and
  defeat): a successful Defend, or a Knight's Rally, plays it once. The final report
  (`docs/M5_final_report.md`) has the explanation of the code, class diagrams, test results,
  screenshots from unmodified matches and, in Appendix B, the complete source code.
- M5.2-B: the report exported as an 82-page PDF, a screenshot of the full test run in a real
  terminal, and the complete class diagram also shown in five readable parts. No code changed.
- After the report (M6, optional additions; the report and its source appendix describe the code
  as it was at `a4ceef8`): Reflex Aim (M6.1), a playability and presentation pass (M6.2), each
  team's own keys in two-player mode (M6.2 rework), **six roles** (M6.3: Gunner, Bombardier
  and Medic join the first three; see *Specials* below), and five aids from a user-experience
  review (M6.4): each team's last shot, a marker for shells above the window, a Restart question
  for R during a match, a computer that thinks during its pause, and a practice range.

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
0. **Studio intro.** The game opens with a 2.5-second *Double Six Studio* intro (two gold
   six-pip seals). A click, **Space** or **Enter** skips it; it plays only once per launch.
1. **Team selection.**
   - **Mode:** **Player vs AI** (the default: you are LEFT, the computer is RIGHT) or
     **Two players** (both teams are played on this computer, taking turns).
   - **Computer:** **Easy**, **Normal** (default) or **Hard** (Player vs AI only).
   - Choose **1 v 1**, **2 v 2** or **3 v 3** (characters per team).
   - **Aim style:** **Classic** (default) or **Reflex**; one sentence under the buttons always
     explains the chosen one.
   - Click character cards to add them to your team; click again to remove one. Each team has
     six cards in 3 columns × 2 rows (M6.3).
     - Each card shows a small half-body portrait, HP / ATK / DEF, the special's name and cooldown,
       and a band: "Click to add", the slot once chosen, or "THE COMPUTER PICKS". A Triple Volley
       or Airburst card also has a small picture of its shells (three lines, or five).
     - The **roster box** under a team's cards explains the specials of its picks, in slot order;
       with the mouse on a card it explains that card instead.
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
     next to the characters), so you can also just press the next-step button.
   - **Presets:** **Inner Wall** (the default: high wall near the team) and **Outer Wall** (high
     wall near the cannon). Both use 6 blocks and stay editable slot by slot.
   - With the mouse on a block, the blocks a click would remove are outlined in red (a lower
     block takes the raised block on top with it), with a warning line.
   - The corners show the step ("1/2 · Left cover") and the chosen Aim style.
   - **Against the computer:** you place the LEFT cover, then **Start Battle**. The computer
     places its RIGHT cover by itself.
   - **Two players:** LEFT places first, then **Next: Right Cover** shows RIGHT's screen
     ("2/2 · Right cover", then **Start Battle**). The other team's cover stays hidden until the
     battle starts.
   - **Back** returns to the previous step (RIGHT's screen → LEFT's → team selection) without
     losing the teams or the cover already placed. Cover choices are also kept when you change
     the teams, because characters never stand on cover slots.
3. **Battle.** The LEFT team moves first in the first match, then the turns alternate.
   - **The HUD** has a turn banner in the colour of the team to move, with the round and what
     is happening (e.g. "Round 7 / 30   LEFT TEAM'S TURN (you): aim and act"), the result of
     the last action under it, and for each team how many characters are still standing
     ("LEFT  2/3") with the cover count in a smaller line ("standing · cover 5/6").
   - **After every shot** the top line says where it landed and what it did, e.g.
     "DIRECT HIT · Archer -26 HP", "COVER HIT · Archer shielded", "GROUND IMPACT · no damage" or
     "OUT OF FIELD · no damage". A ring marks the landing point; the details stay in the log.
   - **Choose who acts:** click one of your living characters, or press **1 / 2 / 3**. The chosen
     character has a yellow marker, and the panel shows its HP, ATK, DEF, Level, EXP and special.
   - **Aim:** the panel shows ANGLE and POWER in large numbers, with the keys of the team to move
     over them. Set the power with your power keys or by clicking or dragging the gold power
     slider (both Aim styles). The gold arrow points along the current aim and grows as you
     increase power. Against the computer you use the arrow keys and SPACE; with two
     players each team has its own keys (see *Controls*).
     - **Classic:** your angle keys set the angle. Six light dots show the start of the shot's
       path (its first 24 physics steps); **V** hides or shows them. The far end is up to you.
       When the chosen character's special fires several shells, the dots are labelled
       "center shell": they follow the middle shell, the one fired with your aim.
     - **Reflex:** the barrel swings by itself between 20° and 75° (an arc with a tick at each
       end and a pointer); the panel says "REFLEX · SWINGING". ATTACK, your fire key or a
       special that fires locks the angle shown at that moment, once ("REFLEX · LOCKED 47°", a
       gold mark on the cannon), and that angle is fired.
   - **Act:**
     - **ATTACK** (or your fire key: SPACE, F or Enter, shown under the button as "key F")
       fires your team's cannon with that aim and the chosen character's stats. The character
       first runs to the cannon; the shot leaves when it gets there, and it runs back while the
       shot flies.
     - **DEFEND** halves the damage that character takes until your next turn, and also halves
       the damage enemy shots do to your cover blocks (**Cover Guard**). It also gives that
       character **Guarded Strike** for your next turn (a gold star beside its name), and your
       team can't DEFEND again on that next turn (the button is greyed out and says why).
     - The third button is the chosen character's special: **RALLY**, **POWER SHOT**,
       **REPAIR**, **TRIPLE VOLLEY**, **AIRBURST** or **FIELD DRESSING**. A button that can't be
       used now is grey and striped, with a short note ("ready in 2", "not twice", "nothing to
       repair", "all full HP"). One help line under the aim explains the special, or the button
       under the mouse, and what it costs. For Field Dressing it names the target and the HP
       before you click ("Heal LEFT Archer · +26 HP · ends turn", and "Archer +26" on the button).
     - A **Triple Volley** or **Airburst** is one run to the cannon and one attack: its shells fly
       together, each explodes on its own, and the turn ends after the last one lands. The top
       line then sums the whole attack up, e.g. "TRIPLE VOLLEY · 2 direct, 1 out · Knight -18 HP".
     - **Your last shot (M6.4).** On your turn the panel's left group ends with your team's last
       shot that has landed, in gold: "Last shot · 45° / 83 · COVER HIT" (for a Triple Volley or
       Airburst, where its shells landed: "2 direct, 1 ground"). A faint ring marked "last" shows
       where it landed (for several shells, the center shell: the one fired with the aim shown).
       A shot that left the field by the side has only the words. Each team sees only its own;
       nothing is aimed for you, and a rematch forgets both.
     - **Shells above the window (M6.4).** A high shot can fly over the top of the window and fall
       back. While it is up there, a gold triangle under the top line follows it from side to side
       with "Shell above view" ("3 shells above" for several).

   On the computer's turn the buttons are greyed out. After a short pause (2/3 s, in which it
   already works out its options: M6.4) it chooses a character and an action by itself. The
   combat log shows its choice (e.g. "AI (Normal): Archer attacks the LEFT Knight." or "AI
   (Hard): Engineer attacks the cover in front of the LEFT Knight.") and what happened. Its
   attacks take the same run to the cannon as yours.
4. **Result.** A solid panel over the battlefield shows, in order, the winner's badge and title
   (in that team's colour) or DRAW (amber, with a neutral "=" badge, "Time limit reached"), why
   the match ended (in gold), the final round, then the buttons.
   - Choose **Rematch** (same teams, both covers, same computer level; every character and block
     starts at full HP again) or **Change teams** (back to team selection; your cover choices are
     kept).
     **R** is a rematch shortcut here. **During a match**, Esc or R opens the pause menu.
     **Continue** (Enter, Space or Esc) resumes the same frame. **Restart** (or a fresh R
     press) starts the rematch. **Main Menu** (or Backspace) ends the match and keeps the
     current roster, cover layouts, difficulty and aim choice for the next match.
   - **Who moves first alternates:** each rematch swaps the side that moves first (LEFT, RIGHT,
     LEFT, …). Choosing teams again starts with LEFT. When the computer moves first, it plays its
     turn by itself.
5. **Practice range (M6.4).** **Practice** on the selection screen (no teams needed) opens a fixed
   range: Archer, Gunner and Bombardier (1-3) shoot at Knight, Archer and Engineer behind the
   default cover, with the real shots and damage. After every shot the targets, the cover and
   the special are back; the aim and the "Last shot" line stay, to compare the next shot with.
   Classic / Reflex / Back are in the panel's right group (Backspace = Back, R = reset now). The
   keys are those of the mode chosen on the selection screen. Back returns to the selection
   screen with every choice as you left it. DEFEND is greyed out there.

## Controls
| Input | Action |
|---|---|
| Mouse click | Skip the intro, team selection, cover presets and slots, Back / next step, choose a character, ATTACK / DEFEND / special, power slider, Rematch / Change teams |
| 1 / 2 / 3 | Choose your character in slot 1, 2 or 3 |
| Shift + an aiming key | Change by 5 instead of 1 |
| V | Classic Aim's path dots on / off |

Aiming and firing in a battle (each team's keys work only on its own turn):

| | Raise / lower the angle (Classic only) | More / less power | ATTACK (Reflex: lock and fire) |
|---|---|---|---|
| Player vs AI (you, LEFT) | Up / Down | Right / Left | Space |
| Two players: LEFT | W / S | D / A | F |
| Two players: RIGHT | Up / Down | Left / Right | Enter |

With two players, the power keys always add power toward the middle of the field. Space also
skips the intro.

| Input | Action |
|---|---|
| Enter | Skip the intro, PLACE COVER (selection screen), Next: Right Cover / Start Battle (cover screen); RIGHT's ATTACK in a two-player battle |
| Backspace | Back from cover or practice; Main Menu from the pause menu |
| R | After a match: rematch. During a match: open the pause menu (press again to restart). Practice range: reset the targets now |
| M | Sound on / off (any screen) |
| Esc | Pause or resume a match; return to the main menu from practice or results; quit from team selection or cover setup |

Holding an aiming key keeps changing the value. A fire key acts once per press: one that is
held down (from the last turn, or from the Enter that confirmed the cover) must be let go before
it fires again. While a character runs to the cannon and back, the combat keys and buttons do
nothing (R and Esc still open the pause menu). R and Esc act once per press. While paused,
combat input waits and M can still toggle sound.

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
    Engineer 60, Gunner 50, Bombardier 50, Medic 45. Damaged blocks get darker, and destroyed
    blocks disappear.
  - **One attack, several shells (M6.3).** A Triple Volley or Airburst shell explodes like any
    shot, with its own smaller blast and damage (see *Specials*). Shells move in the order they
    were fired, so a later shell can fly through a block an earlier one destroyed in the same
    moment. The turn ends, EXP is given once and the winner is checked once, after the last
    shell has landed.
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
  - **Gunner (HP 115, ATK 35, DEF 7) – Triple Volley:** three shells at once, at your aim and at
    −6° / −4 power and +6° / +4 power (each kept inside the legal aim). Each shell does ATK × 0.6
    (then DEF), 18 per block, with a 32 px blast. Cooldown 3.
  - **Bombardier (HP 100, ATK 32, DEF 6) – Airburst:** one marked shell that splits into five
    small shells when it starts to come down. Each keeps the vertical speed and takes 0.76, 0.88,
    1.00, 1.12 or 1.24 of the horizontal speed. Each small shell does ATK × 0.45, 16 per block,
    with a 24 px blast. A marked shell that hits something before it splits counts as one small
    shell (in a real match it can't reach the enemy before the top of its arc). Cooldown 4.
  - **Medic (HP 105, ATK 28, DEF 6) – Field Dressing:** heals the living teammate who would gain
    the most HP: up to 32 for another teammate, up to 24 for the Medic itself, never above full
    HP, never reviving. A tie goes to another teammate, then to the earlier slot. Only possible
    when a living teammate is hurt. Cooldown 4.

  A special used in round *r* is ready again in round *r + cooldown*. Each character shows
  "ready" or "wait N" under its feet.
- **EXP:** +10 for an attack that damages something (once, however many of its shells hit), +20
  more for each enemy it defeats, and +5 for Rally, Repair or Field Dressing. Level-ups (30 × level EXP) raise HP, ATK and DEF, up to Level 5.
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
  last shooter is still running back), *paused* (the Restart question, M6.4) or *game over*. In
  the practice range it reads *PRACTICE RANGE*.
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
  bigger muzzle flash. (M6.3) Each Triple Volley shell has its own trail; an Airburst shell is
  marked with a gold ring and five notches until it splits, with a gold flash, into five smaller
  shells, each with its own trail. "+26" floats up in green over a healed character.
- **Readability:** names on the battlefield use darker team colours (contrast at least 4.5 : 1
  against the sky); the chosen character has a thicker yellow box; buttons light up under the
  mouse.
- **Result screen:** a coloured title band (the winner's colour, or amber for a draw) with
  "Victory by elimination" or "Time limit reached", and "Final round: N / 30".

## Sound and atmosphere
- **Sound effects**, made in code by `sound.py` (no sound files, so nothing to license): the
  cannon firing, the explosion, a block hit, a block destroyed, a Defend or Rally (a metallic
  ring, added in M5.2-A), a level-up, and a tune for a victory, a defeat (against the computer)
  or a draw. Each plays once, when the game reads the matching Battle event; Repair and refused
  actions are silent. A rematch, new
  teams or quitting stop every sound.
- **M** turns the sound off and on, on every screen; the combat log heading shows which.
- **No audio device?** The game is silent and works exactly the same (the mixer is optional).
- **The battlefield** uses the AI-generated mountain-valley illustration in
  `assets/siege-valley.jpg`. Pygame loads it once per game and draws the ground, team flags,
  characters, and cover separately. If the picture is absent, the game draws the original landscape.
- **Screen changes** briefly fade in, and character cards and available cover slots highlight
  under the mouse. The fade draws over the incoming screen, so the other team's cover stays private.
- **Teams by shape:** LEFT's emblem is a circle and RIGHT's a diamond, on every character's chest,
  on the flags, in the HUD and in the turn banner, so the colours are not the only clue.
- **Readability:** names and HP bars sit on light plates; the turn banner is bold and the team
  lines smaller; floating damage words never overlap (a new one moves up); the cover screen's
  text has a plate too.

## The run to the cannon (M3.4-C)
- **One shared cannon per team.** Every character of a team attacks through the same cannon,
  which stands in front of the team's cover. The shot always starts at the cannon, and its
  damage uses the stats of the character who fired it.
- **The animation.** When you choose ATTACK (or a special that fires: Power Shot, Triple Volley,
  Airburst), the character runs from
  its slot to the cannon (1/3 s), fires it with a short muzzle flash (1/5 s), and runs back
  (1/3 s) while the shot flies. The shot is fired exactly once, on the frame the character
  reaches the cannon; the flash starts on that same frame. A Triple Volley's three shells leave
  together on that frame: one run, one flash. Defend, Rally, Repair and Field Dressing still
  happen at once, without a run.
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
- **Runs pause and resume with the match.** Restart, Main Menu and quitting cancel an
  unfinished run and its pending shot. If the match ends while a character is still
  running back, it finishes behind the result screen.
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
  - **The M6.3 specials** are imagined on the copy like any shot, so the real rules decide what
    their shells are worth. When a Triple Volley or Airburst could be fired, every shooter is
    also tried at the aims of the next two best targets, and each option is rated by its average
    over the computer's own power error (a spread of shells is worth having because a slightly
    wrong aim still hits). Teams with only Knight, Archer and Engineer choose exactly as before.
  - **Field Dressing** is chosen instead of a shot when the HP it restores, divided by the HP the
    team has left, is worth more (the mirror of "enemy HP removed / enemy HP left"). With nobody
    hurt it is never chosen.
  - **Thinking during its pause (M6.4).** The rules have no chance in them, so a shot imagined
    twice ends the same way twice: within one decision it remembers each imagined shot (same
    character, action and aim) and never imagines it again. During its 2/3 s pause it already
    imagines, a few per frame (at most 10 ms of each frame), the shots its decision will ask for,
    so the decision on the last frame of the pause takes about 30 ms instead of up to about
    0.45 s, and the window keeps answering. It rolls no dice while thinking ahead, so it makes
    exactly the same choices as before (checked with fixed seeds; `docs/M6.4_results.md`).
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
  which sounds play), `tests/test_sound.py` (the sound effects and the silent fallback) and the
  screen parts of `tests/test_playability.py` (M6.2), `tests/test_six_roles.py` (M6.3) and
  `tests/test_ux_aids.py` (M6.4) need Pygame. They are skipped if it isn't installed; they never
  open a visible window or make a sound.

## Project layout

For a walkthrough of the code and presentation diagrams, see [the code map](docs/presentation_code_map.md).

| File | Purpose |
|---|---|
| `main.py` | Pygame window, screens (team selection, cover placement, battle, result), buttons, mouse and keyboard input, the computer's turn, when an attack is fired (after the run), drawing and the main loop |
| `drawing.py` | The screens' shared look: colours, text, character figures (standing, running, firing), cover blocks (cracks, destroyed outline), HP-bar colours and buttons (moved out of `main.py` in M3.4-B; with `main.py`, the only files that use Pygame) |
| `assets/siege-valley.jpg` | Mountain valley used behind the selection, cover, and battle screens |
| `sound.py` | Sound effects made in code and `SoundBoard` (M4.2-A): plays them, stops them, mutes; silent without an audio device |
| `animation.py` | `CannonRun` (M3.4-C): the states and frames of a character's run to the cannon and back, and where to draw it; no Pygame, never changes the Battle |
| `ai.py` | `AIController`: the computer opponent (team and cover choice, Defend / Attack / Special choice, cover-aware aiming) and its difficulty table |
| `battle.py` | Cannons, projectile physics, collision along the flight path, explosions and cover, turns, the round limit and victory; `Team` and team combat (Attack / Defend / Special); `path_contacts` for the computer's planning |
| `castle.py` | `Block`, the 8 cover slots, the layout rules (`layout_problem`) and the placement clicks (`place_block`, `remove_block`), and `Castle` (one team's cover): damage and repair |
| `characters.py` | `Character` base class with `Knight`, `Archer`, `Engineer`, `Gunner`, `Bombardier`, `Medic`: HP/ATK/DEF, damage, healing, defend, cooldowns, EXP, levels and each role's special ability |
| `tests/` | `unittest` tests for `castle.py`, `battle.py` (physics and collision), team combat and cover (`test_combat.py`), `characters.py`, `ai.py`, `animation.py`, `sound.py` and `main.py` |
| `docs/M0_design.md` | Design: rules, architecture, roadmap (the latest decisions at the top; superseded sections are marked *Historical*) |
| `setup_choices.py` | Roster, aim style, and cover choices before a match |
| `battle_feedback.py` | Battle event text and each team's previous-shot record |
| `docs/M3.1_balance_analysis.md` | M3.1 analysis of Defend and Repair (recommendations only, nothing changed) |
| `docs/M3.2_balance_report.md` | M3.2 balance experiment under the old castle rules (historical; its script is in commit `86b90fa`) |
| `docs/M3.2_benchmark_results.md`, `docs/M3.2_benchmark_results_easy.md` | That benchmark's generated result tables (historical) |
| `docs/M3.3_course_compliance.md` | Course requirements checklist: what is verified, what awaits a manual check, what is missing, and our custom rules (updated for M5.1) |
| `docs/M4.2-B_defend_design_review.md` | M4.2-B: the audit of Defend and the redesign that was approved and built (Guarded Strike, anti-stall) |
| `docs/M4.3_stabilization_report.md` | M4.3: the final stabilization report (test matrix, seeded matches, course-compliance gaps, remaining human checks) |
| `docs/screenshots/` | Screenshots: 01–08 from scripted runs, 09–14 from complete unmodified matches, 15 the full test run in a terminal |
| `docs/Castle_Siege_Final_Report.pdf` | The final report as a PDF (M5.2-B), made from `docs/M5_final_report.md` |
| `docs/M5_final_report.md` | The final report (M5.2-A): the 300–500-word explanation of the code, gameplay, algorithms, class diagrams, testing, screenshots, AI-assistance draft, and the complete source code (Appendix B) |
| `docs/M5_class_diagram_main.mmd`, `docs/M5_class_diagram.mmd` | Class diagrams: simplified and complete (editable Mermaid sources) |
| `docs/M5_class_diagram_part_2.mmd` … `_part_6.mmd` | The complete diagram cut into five readable parts (made by script from `docs/M5_class_diagram.mmd`) |
| `docs/figures/` | The class diagrams (simplified, complete and its five parts), rendered as images for the report |
| `docs/M5.1_submission_audit.md` | Submission audit (M5.1, revised in M5.2-A with the instructor requirements the PM confirmed): matrix, source-code check, screenshots, risks, final human checklist |
| `docs/Rebound_reference_review.md` | Review of a reference project (ideas only) |

## References
- [ryonsherman/pygame-rebound](https://github.com/ryonsherman/pygame-rebound) (MIT License)
  was studied as an *idea* reference only (see `docs/Rebound_reference_review.md`).
  No code or assets from it are used in this project; its neural-network AI was not copied
  (our AI is a plain search over aims, written from scratch).
