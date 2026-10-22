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

There is no cheat command for wrecking the car or running out the clock, so lines 17 to 19 are played for real; the
matching functional tests (`FT_DFRespawn_*`, `FT_DFRaceEnd_TimeUpSetsResult`, `FT_DFHUD_SummaryShownAtRaceEnd`) check
the same rules automatically. The console command `ke * RestartRace` (press the `` ` `` key while playing) is expected
to call the GameMode's `RestartRace` for a fresh race without reloading; it has not been tried yet, so note whether it
works.

Record the date, the commit hash and who played at the bottom of the file when the list is complete.
