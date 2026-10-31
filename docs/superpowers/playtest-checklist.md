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
| 6 | Drive through gate 2 (the second pair of poles) | `CHECKPOINT  +3 s` flashes for about 1.5 s; clock jumps up 3 s (Phase 6 balance; 2 s on SWITCHBACK) | | |
| 7 | Drive back through the same gate, or skip ahead to a later gate | Nothing is credited | | |
| 8 | Complete a lap (all gates in order, then the start line) | `LAPS 1`, `SCORE 100`, +3 s | | |
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
| 43 | Phase 5. Open `Maps/L_MainMenu` and press Play | `DEAD FIRE` over three cars on plinths (navy, gunmetal, teal since Phase 7), PLAY / SETTINGS / QUIT, footer `CARS 1 / 3   TRACKS 1 / 2`; the view fades in from black | | |
| 44 | PLAY, then `<` and `>` | The camera glides between the three cars and the stats change; BRUTE and VIPER read `LOCKED  -  FINISH 1ST ON ...` with NEXT greyed; SEDAN's NEXT works | | |
| 45 | NEXT (on SEDAN) | The track page: PROVING GROUND with `PASS 300   CLOCK 120 s   RIVALS 3` and `NOT RACED YET`; `>` shows SWITCHBACK locked (`LOCKED  -  PASS PROVING GROUND`) with RACE greyed | | |
| 46 | RACE on PROVING GROUND | Fade to black, then the race starts in the Sedan with three rivals and `POS 1 / 4` | | |
| 47 | Press **P** while racing | The world freezes under `PAUSED` with RESUME / RESTART / MAIN MENU / QUIT and the cursor; **P** again or RESUME continues; RESTART gives a fresh race; MAIN MENU returns to the car page | | |
| 48 | Finish a race with 300+ points in first place (console `ke * EndRace 1` ends it early once the score is there) | Summary `RACE COMPLETE`, line `NEW CAR UNLOCKED: BRUTE   NEXT TRACK UNLOCKED: SWITCHBACK`, buttons RETRY / NEXT / MENU | | |
| 49 | NEXT | SWITCHBACK: five gates, four rivals, the clock at `2:30`, a hairpin at the far end with the shortcut and its rock cutting it | | |
| 50 | MENU, then `>` to BRUTE and NEXT, RACE | BRUTE is open; the race starts in a grey car reading `CAR 160 / 160` that pulls away slower and will not pass 120 km/h | | |
| 51 | Quit the editor, open the project again, Play `L_MainMenu` | `CARS 2 / 3   TRACKS 2 / 2`: the unlocks survived (`Saved/SaveGames/DeadFire.sav`) | | |
| 52 | SETTINGS: drag MASTER VOLUME to 0 and race | Explosions and shots are silent; back at 100 % they are not | | |
| 53 | SETTINGS: `>` to HARD, race PROVING GROUND | Five rivals on the grid; EASY gives two | | |
| 54 | SETTINGS: the display button | Toggles WINDOWED and FULLSCREEN (in a packaged build; the editor viewport stays as it is) | | |
| 55 | SETTINGS: RESET PROGRESS | The label reads `PROGRESS RESET`; BACK shows `CARS 1 / 3   TRACKS 1 / 2` again | | |
| 56 | Summary MENU and the pause menu's MAIN MENU | Both fade out and arrive on the car page of the main menu | | |
| 57 | Phase 6. Unzip the Development build from `Builds\` and run `comp4900sef.exe` (not the editor) | The window is titled Dead Fire and opens on the main menu; no `LIGHTING NEEDS TO BE REBUILT` text anywhere | | |
| 58 | In the packaged game press **Escape** while racing, then Escape again | The pause menu opens and closes (Escape does not quit) | | |
| 59 | Race PROVING GROUND on NORMAL at a steady pace without stopping for crates | The clock runs out after roughly three minutes (about six laps); stopping for crates ends it sooner | | |
| 60 | SETTINGS: HARD, race; then EASY, race | HARD: five rivals that pull away faster and attack more often; EASY: two slower rivals. Note whether HARD feels harder or only more chaotic | | |
| 61 | SETTINGS: drag MASTER VOLUME to 30 %, release, QUIT, start the game again | The slider still reads 30 % | | |
| 62 | Pause a race, MAIN MENU | The car page with a working mouse cursor; the next race takes keyboard input normally | | |
| 63 | In the Development build press `` ` `` and type `ke * EndRace 1` during a race with 300+ points | The summary appears at once (`RACE COMPLETE`); `ke * RestartRace` restarts a race without reloading | | |
| 64 | SETTINGS: the display button in the packaged game | Switches between a window and fullscreen; Alt+Enter does the same | | |
| 65 | QUIT from the main menu, then run the Shipping build | Both close cleanly; the Shipping build starts on the main menu too | | |
| 66 | Phase 7. Listen to the 26 sounds in `/Game/DeadFire/Art/Sounds` (double-click each `SW_DF_*` in the Content Browser; the engine, skid and rocket sounds are loops) | Each is recognisable for its role: three engine tones (BRUTE lowest and roughest, VIPER highest), tyre screech, crash, car gun, rifle, rocket launch and loop, a long low explosion with crackle, bomb arm and beep, loot, pickup arpeggio, falling deny buzz, boost whoosh, three shield sounds, tyre pop, metal and dirt impacts, checkpoint, lap, UI click and hover. No clicks or pops at the start, end or loop join; none painfully loud or harsh | | |
| 67 | Drift the PROVING GROUND hairpin twice: on the keyboard (hold **Space**, steer **A**/**D**) and on a gamepad (hold the left shoulder, steer the left stick). Enter above 40 km/h | The tail swings out and the slide holds while the handbrake is held; letting go after a second or more gives a forward kick. For reference, a 1 s full-lock drift from 80 km/h turns the car about 66° and leaves it at about 41 km/h (no handbrake: 23° and 59 km/h). Note whether that feels right, too much or too little, on each device | | |
| 68 | Race SWITCHBACK and take the S-bend at speed, on the keyboard | The car turns in without a handbrake, steering is calmer at speed than when parking, the tail does not snap round, and letting go of the steering straightens the car | | |
| 69 | Flip the car (the ramp, a bomb under it, or a wall at speed), wait until it stops, then press **Backspace** (gamepad face-right) | It is set back on its wheels about 1.5 m up, where it lay and facing the same way; `LIVES` is unchanged. Pressed while still moving faster than 15 km/h, or again within 3 s, nothing happens | | |
| 70 | Hold **C** (gamepad right-stick click) while driving, then let go | The view cuts at once to the rear and back on release: a cut by design, not a swing. In an editor started before 2026-10-31, **C** and **Backspace** need an editor restart (the input mappings were added then) | | |
| 71 | Jump the ramp (more than half a second in the air), take a gun or rocket hit from a rival, and hit a wall or a car hard | A short light camera shake each time; none after a small bump or a gentle nudge | | |
| 72 | Drive SEDAN, then BRUTE and VIPER; slide, drift and crash | The engine pitch rises with the revs and drops at each gear change, louder on the throttle and quieter off it; each car sounds different (BRUTE lowest, VIPER highest); a tyre screech while sliding or drifting, none driving straight; a crash sound on a hard hit, none on a light touch. A car nobody drives (the one you got out of, a wreck, the main menu's three cars) is silent | | |
| 73 | Compare a lap in this build with a lap in the Phase 6 build (`Builds\`, Development) | Does the car feel better than the stock template? Note what is better and what is worse (turning, sliding, landing, camera, sound) | | |
| 74 | Race PROVING GROUND and SWITCHBACK at full speed without stopping; look for the six crates | Each crate shows from the road as a 30 m beacon in its item's colour, early enough to brake and stop beside it; close up the beacon fades and the crate, its coloured stripe and the floating icon show; `CRATE NEARBY - E TO GET OUT` appears when you slow down near one. Note any crate you only saw after passing it | | |
| 75 | On the grid and mid-race, glance at the cars around you (front-lit and against the low sun) | Yours alone is navy with white trim and the blue light bar; the rivals and the parked target car are black with flame-orange trim and no light bar. Note any moment you took a rival for your car or the other way round | | |
| 76 | Shoot: the car gun (GUN, **Q**) at a rival, the rifle on foot at a rival and into the road, a rocket (RPG) at a car | Each shot has a muzzle flash at the gun, a tracer and a spark at the hit, with its own sound; on foot the crosshair turns red and grows on a car or character hit and stays white on the road; a rocket flies with a flame and smoke trail and explodes with smoke, a close-range shake and a scorch mark that fades. Note any shot that feels as if it did not land | | |
| 77 | Leave the road on both tracks: drive into the infields and out to the foot of the ridge, round rocks, dead trees, wrecks, barrels, containers, fences and billboards, and over the terrain's slopes | Nothing traps the car: you can always drive back, or **Backspace** (line 69) or the 5 s off-track reset puts you back. Note any place where the car sticks, wedges or is hidden from the camera (near which gate) | | |

Escape ends Play-In-Editor before the game sees it, so the pause line uses **P**. There is no cheat command for wrecking the car or running out the clock, so lines 17 to 19 are played for real (from Phase 3 on, two rockets at your own parked car also wreck it); the
matching functional tests (`FT_DFRespawn_*`, `FT_DFRaceEnd_TimeUpSetsResult`, `FT_DFHUD_SummaryShownAtRaceEnd`) check
the same rules automatically. The console commands `ke * RestartRace` and `ke * EndRace 1` (press the `` ` `` key while playing, in the editor or the
Development build) were tried on 2026-10-30: the first restarts the race without reloading, the second ends it with
reason 1 (time up), which shows `RACE COMPLETE` when the score is at least the pass score.

Record the date, the commit hash and who played at the bottom of the file when the list is complete.
