M6.2 screenshots. Every picture is a real frame drawn by the game (main.Game.draw) with
SDL's dummy video driver. All input was scripted through the game's own input handlers;
no person played. 12 is a composite of six real frames, cropped and labelled. before_3v3_*
come from the same script run on a copy of the project with main.py/drawing.py/battle.py as
they were before M6.2 (the working tree at the start of this task).

01_intro_studio.png: studio intro, frame 28 of 72 (hold)
02_intro_fading_out.png: intro fading out onto the selection screen, frame 60
03_roster_unselected.png: selection screen as it opens (Player vs AI, Classic): cards not chosen, computer's cards greyed, the Classic sentence under Aim style
04_roster_selected_reflex.png: two players, 3v3, every card chosen (slot bands), Reflex chosen with its sentence under Aim style
05_cover_left_inner_wall.png: LEFT cover, step 1/2, Aim: Reflex in the corner, Inner Wall preset, button says Next: Right Cover
06_cover_hover_support.png: the mouse on slot 1 (it holds up slot 5): both outlined red, with the warning
07_cover_right_outer_wall.png: RIGHT cover, step 2/2, Outer Wall preset (LEFT's cover hidden), button says Start Battle
08_reflex_swinging.png: Reflex: LEFT's gauge (arc, end ticks, pointer at 41°), panel chip REFLEX · SWINGING
09_reflex_locked.png: SPACE pressed while 48° was shown: gold lock mark, LOCKED 48°, chip REFLEX · LOCKED 48°, ATTACK note 'locked 48°'
10_reflex_shot_in_flight.png: the shot leaves at the locked 48° and flies; the lock stays on LEFT's cannon
11_reflex_right_turn.png: result of LEFT's shot on top and in the panel; RIGHT (a person) now swings its own gauge
12_reflex_swing_strip.png: six real frames 0.5 s apart: the gauge pointer from 20° up to 75° and back
13_lock_stays_with_shooter.png: a soft shot landed while LEFT's Knight runs back: it is RIGHT's turn (banner 'waiting', chip REFLEX · WAITING) but the lock mark stays on LEFT's cannon
14_pvai_reflex_computer_thinking.png: Player vs AI, Reflex: the computer's turn, chip THINKING, no gauge on its cannon
15_classic_path_dots.png: Classic: six path dots (first 24 physics steps), short barrel line, chip PATH ON · V; the far end is not shown
16_classic_hover_attack.png: Classic, mouse on ATTACK: the help line explains ATTACK and its cost
17_classic_path_hidden.png: after V: no dots, chip PATH OFF · V
18_buttons_engineer_nothing_to_repair.png: Engineer chosen: REPAIR greyed and striped, note 'nothing to repair', the help line says why
19_buttons_rally_cooldown.png: Knight after Rally: RALLY 'ready in 3'; ATTACK in warm gold
20_feedback_cover_hit.png: COVER HIT · 4 blocks, -200 HP: top message, blue impact ring with debris, the result first in the panel's log group
21_feedback_cover_broken_still_shielded.png: COVER HIT · 2 blocks destroyed, Archer shielded: the shot destroys two blocks, the Archer behind them is still shielded (RIGHT on Outer Wall, blocks set to 5 HP by the script)
22_feedback_direct_hit.png: DIRECT HIT · Archer -26 HP: red ring on the Archer, -26 floating
23_result_left_wins.png: LEFT wins (script set the Archer to 5 HP, then a direct hit): badge, title, reason in gold, round, Rematch in warm gold
24_result_right_wins.png: RIGHT wins the same way after LEFT defended
25_result_draw_30_rounds.png: a 30-round draw (both teams pass every turn): DRAW!, neutral badge, time-limit reason
after_3v3_1280.png: AFTER M6.2: the same scripted 3v3 scene, shot in flight
after_3v3_640.png: AFTER M6.2: the same scripted 3v3 scene, shot in flight (scaled to 640x360)
after_3v3_grey.png: AFTER M6.2: the same scripted 3v3 scene, shot in flight (greyscale)
before_3v3_1280.png: BEFORE M6.2: the same scripted 3v3 scene, shot in flight
before_3v3_640.png: BEFORE M6.2: the same scene scaled to 640x360
before_3v3_grey.png: BEFORE M6.2: the same scene in greyscale
