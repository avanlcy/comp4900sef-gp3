# Dead Fire playtest checklist (Blueprint build)

Walk this once per phase, by hand, in the editor: open `/Game/DeadFire/Maps/L_TestTrack` and press **Play**.
The functional tests (`tools/run_tests.ps1`) cover the race rules but cannot press keys, so everything that depends on
real input, physics feel and what the screen looks like is checked here. Tick a line only after seeing it happen;
write anything odd in the notes column.

| # | Do | Expect | OK | Notes |
|---|---|---|---|---|
| 1 | Press Play | You sit in the Sedan on the start line between two gate poles; HUD shows `SCORE 0`, `LAPS 0`, `KILLS 0`, `LIVES 3`, clock `2:00` counting down, `0 km/h`, `GEAR N`, `CAR 100 / 100`, `TIRES [30] [30] [30] [30]`, prompt `[E] Exit vehicle` | | |
| 2 | Hold **W**, steer with **A/D** | The car accelerates and steers; speed and gear on the HUD follow | | |
| 3 | Hold **S** while moving, then while stopped | Brakes, then reverses; gear shows `R` in red | | |
| 4 | **Space** while moving | Handbrake slides the rear | | |
| 5 | **Tab** | Switches between chase and in-car camera | | |
| 6 | Drive through gate 2 (the second pair of poles) | `CHECKPOINT  +8 s` flashes for about 1.5 s; clock jumps up 8 s | | |
| 7 | Drive back through the same gate, or skip ahead to a later gate | Nothing is credited | | |
| 8 | Complete a lap (all gates in order, then the start line) | `LAPS 1`, `SCORE 100`, +8 s | | |
| 9 | While moving above 10 km/h press **E** | Prompt reads `Stop to exit  [E]`; you stay in | | |
| 10 | Stop, press **E** | The mannequin appears beside the car; HUD switches to `HEALTH 100 / 100`, crosshair `+`, prompt `[E] Enter vehicle` near the car | | |
| 11 | **W A S D**, **Space**, mouse | Walk, jump, look around | | |
| 12 | Aim at the car, **left mouse** | The car loses health (visible after re-entering: `CAR 80 / 100`, or a tire count drops) | | |
| 13 | Walk away from the car | `[E] Enter vehicle` disappears beyond about 3 m | | |
| 14 | Next to the car press **E** | Back in the driver's seat; car HUD returns; the car drives again (handbrake released) | | |
| 15 | Drive more than 5 m off every road | `RETURN TO TRACK  5.0` counts down; at 0 the car is put back at the last gate; `LIVES` unchanged | | |
| 16 | Park off the road and get out | No countdown on foot | | |
| 17 | Wreck the car (shoot it from outside until `CAR 0`, or use the console: see below) | `WRECKED`; 2 s later you are in a fresh car at the last gate; `LIVES 2` | | |
| 18 | Lose two more lives | The third death shows the summary `GAME OVER`; no respawn | | |
| 19 | Let the clock run out (or console: see below) | Summary `TIME UP` (or `RACE COMPLETE` with 300+ points), `Place 1 of 1`, stats line; mouse cursor visible | | |
| 20 | Click **RETRY** | The level restarts: full clock, 3 lives, HUD back, keyboard driving works | | |
| 21 | Click **QUIT** | Play session ends | | |
| 22 | Gamepad (if available): sticks, triggers, A, Y, right trigger | Drive, jump, enter/exit, fire as in the README controls table | | |
| 23 | Phase 3. Drive toward one of the six orange crates (they sit 15 m or more off the road, three in the infield), stop beside it, press **E** and walk into it | `PICKED UP <ITEM>` flashes; the row at the bottom shows `<ITEM> x1` in amber; the crate vanishes | | |
| 24 | Drive the car through another crate | The car passes through it; nothing is collected and the crate stays | | |
| 25 | Walk away and wait 30 s | The crate you took is back | | |
| 26 | Collect two more types, then press **R** (or roll the mouse wheel) in the car and on foot | The amber highlight moves along the row; a fourth type is refused (`PICKED UP` does not flash, the crate stays) | | |
| 27 | Select BOOST, press **Q** | A shove forward, `BOOST` above the row for about 2 s, the count drops; an empty stack disappears from the row | | |
| 28 | Select SHIELD, press **Q**, then get shot or bump the parked target car | `SHIELD 6.0` counts down above the row; `CAR` health and tires do not change until it ends | | |
| 29 | Stop beside the parked target car (infield, 30 m past the start), select BOMB, press **Q**, drive off | A red ball drops behind you; about 8 s later it explodes with a flash and a bang, the target car is shoved, loses 60 health and a tire. Driving over an armed bomb yourself does the same to you | | |
| 30 | Face the target car, select GUN, press **Q** repeatedly | A shot per press (0.2 s apart), 15 off the target each; the stack counts down from 8 | | |
| 31 | Face the target car from 10–30 m, select RPG, press **Q** | A rocket with a fire trail flies and explodes on it (80 damage); a second rocket wrecks it: explosion, hop, smoke, `KILLS 1`, `SCORE +50` | | |
| 32 | Fire a rocket at (or leave a bomb beside) the dark block on the shortcut road that leaves the main road just after gate 1, from a few metres back and also with your nose touching it | The block explodes and disappears either way; driving the shortcut shows no `RETURN TO TRACK` countdown and rejoins before gate 2 | | |
| 33 | On foot, stand next to your own bomb when it goes off | `HEALTH` unchanged | | |
| 34 | Click **RETRY** | The item row is empty; bombs, rockets and effects are gone (taken crates come back on their own 30 s timer; a demolished block stays open until the level is reloaded) | | |
| 35 | Phase 4. Press Play and look behind you (or wait a second) | Three NPC Sedans sit on a grid behind the start line, two lanes, one behind the other; HUD shows `POS 1 / 4` | | |
| 36 | Drive off | The NPCs pull away on their lanes, follow the loop at racing speed, slow for the hairpins and pick up again; none drives off the road for long | | |
| 37 | Sit still on the start line | `POS` drops to `4 / 4` as they pass; passing one later raises it again; the summary at the end says `Place n of 4` | | |
| 38 | Park across the road in front of an NPC, or watch one meet the parked target car | It shifts a lane to go round; if it does get pinned it reverses out after a couple of seconds and carries on | | |
| 39 | Wreck an NPC with two rockets (or shoot it from behind) | It explodes and smokes, `KILLS +1`, `SCORE +50`; about 2 s later it is back at its last gate on its lane and the race goes on (no `GAME OVER` for an NPC's deaths) | | |
| 40 | Let an NPC follow you for a while after the first 20 s | It shoots you from behind (`CAR` health drops) or fires a rocket; one that is ahead of you drops a bomb in your path now and then; your `SHIELD` still blocks all of it | | |
| 41 | Get out of your car beside the road and wait for an NPC to pass | The parked car is not shot at; on foot you are never hit | | |
| 42 | Flip an NPC with a bomb under it (or roll one off the ramp) | Within about 2 s it is set back on its wheels at its gate; stop beside a stopped NPC car, get out and press **E** at it: you drive off in it and the NPC gets a fresh car at its gate a second later | | |

There is no cheat command for wrecking the car or running out the clock, so lines 17 to 19 are played for real (from Phase 3 on, two rockets at your own parked car also wreck it); the
matching functional tests (`FT_DFRespawn_*`, `FT_DFRaceEnd_TimeUpSetsResult`, `FT_DFHUD_SummaryShownAtRaceEnd`) check
the same rules automatically. The console command `ke * RestartRace` (press the `` ` `` key while playing) is expected
to call the GameMode's `RestartRace` for a fresh race without reloading; it has not been tried yet, so note whether it
works.

Record the date, the commit hash and who played at the bottom of the file when the list is complete.
