# Dead Fire (死火) — COMP 4900SEF Group 3

An action-racing hybrid built in **Unreal Engine 4.27.2**: race laps on a looped track, blow up rival cars, and get out of the car on foot to find items and shortcuts. See the proposal for the pitch, `docs/superpowers/specs/2026-10-20-dead-fire-design.md` for the design and phase plan, and `docs/superpowers/specs/2026-10-21-phase2-race-flow-design.md` for the race rules.

The game is **Blueprint-only**: open the project in the stock editor, no Visual Studio needed. Driving, cameras and on-foot movement come from the engine's Vehicle and Third Person Blueprint templates; all Dead Fire logic lives in `BP_DF*` Blueprints on top of them. (Phases 1–2 were first built in C++; the Blueprint migration replaced that on 2026-10-22, see `docs/superpowers/plans/2026-10-21-blueprint-migration.md`.)

## Current state: Phase 7 (own look and feel), in Blueprint

- Drive a Sedan around `L_TestTrack` (W/S/A/D, Space handbrake and drift, Tab in-car camera, C look back, Backspace puts a stopped car back on its wheels).
- Stop and press **E** to get out as the mannequin; walk/run/jump, mouse look, **left mouse** fires a hitscan weapon. Press **E** next to the car to get back in.
- Four checkpoint gates on the loop, index 0 on the start line. Only the next gate counts (driving backwards or skipping gates credits nothing); each gate adds **+3 s** to the 120 s clock (+2 s on SWITCHBACK's 150 s), and crossing the start line completes a lap (**+100**).
- Three lives. A wrecked car (driven or parked) or a killed character costs a life; 2 s later the player is back in a car at the last gate (a fresh one if theirs was wrecked) with the character revived and inside. The third death ends the race (game over).
- Off-track timer: driving more than 5 m beyond the edge of every road for 5 s puts the car back at the last gate without costing a life. On foot the timer never runs.
- Race end (clock at 0 or no lives left): input stops and a summary shows the outcome (`RACE COMPLETE` at 300 points or more, `TIME UP`, `GAME OVER`), place, score, laps, kills and deaths, with **Retry** and **Quit**.
- UMG HUD: score, laps, kills, lives, clock, speed and gear, car or character health and tires, crosshair on foot, enter/exit prompts, and warnings (`RETURN TO TRACK` countdown, `WRECKED`, `YOU DIED`, `CHECKPOINT  +8 s`, `PICKED UP <ITEM>`).
- **Loot crates** (six metal crates placed off the road, one random; each shows from the road as a 30 m beacon in its item's colour): walk into one **on foot** to take its item; a car drives straight through a crate and gets nothing. A taken crate comes back after 30 s.
- **Inventory**: three stacks on the racer, shown as a row at the bottom of the HUD with the selected stack in amber. **R** (or mouse wheel) cycles the selection, **Q** uses it from the car (not on foot). Items survive respawns; `Retry` clears them.
- **Items**: *Boost* (a shove plus 2 s of extra acceleration), *Shield* (6 s of immunity for body and tires), *Bomb* (dropped 4 m behind the car, armed after 1 s, explodes when any car touches it or after 8 s), *Gun* (8 hitscan shots of 15 from the bumper, 0.2 s cooldown), *RPG* (a rocket that explodes on whatever it hits, 80 damage within 6 m).
- **Explosions** deal full damage inside their radius, blow the nearest tire of every car caught, shove the cars, and show a fireball and smoke with a sound, a camera shake close by and a scorch mark that fades. Kills made with items score the usual +50. The on-foot character is immune to explosions. A wrecked car explodes, hops, burns and smokes until it is cleaned up.
- A **rock wall** (it breaks into chunks) closes a **shortcut road** across the infield (it leaves the main road just after gate 1 and rejoins just before gate 2, about 18 m shorter); only a bomb or a rocket clears it, and the shortcut counts as road for the off-track timer. A **parked target car** sits on the infield near the start for trying the weapons on (wrecking it scores a kill).
- **Three NPC racers** (`BP_DFVehicleAIController` driving `BP_DFVehicle`s) start on a grid behind you and race the loop on their own lanes: they look ahead along the track spline, slow for corners, shift lanes around cars and obstacles, reverse out when stuck and are reset when flipped. Each has its own racer record, so NPC laps and kills rank against yours.
- NPCs are handed a random item every 20 s and use them with simple rules: a shield when hurt, a rocket or gun at a car ahead (the player's car first, with aim assist), a bomb for a car close behind, a boost on a straight. A car you parked to go on foot is never a target; a car you are driving is.
- Every racer respawns on its own timer: an NPC wreck is replaced at its last gate 2 s later (its lane kept), and an NPC's third death never ends the race. Taking an NPC's car gives the NPC another one.
- The HUD shows your place among all racers (`POS 2 / 4`, refreshed twice a second) and the summary's `Place n of m` counts the NPCs.
- **Main menu** (`Maps/L_MainMenu`, where the packaged game starts): the title over the three cars on plinths, PLAY → the car page → the track page → the race, SETTINGS, QUIT, and a footer `CARS 1 / 3   TRACKS 1 / 2`. Returning from a race lands on the car page.
- **Three cars**: SEDAN (balanced, navy with the blue light bar), BRUTE (160 health, throttle 0.8, limited to 120 km/h, 30 % heavier, gunmetal) and VIPER (70 health, 20 % lighter, a 3 s boost with a harder kick, teal). The car page shows stat bars (`TOP SPEED  [###--]`), the description and the lock hint; a locked car cannot be confirmed. The chosen car is what you start and respawn in; rivals keep driving Sedans, in the Fire syndicate's black with flame-orange trim and no light bar.
- **Two tracks**: PROVING GROUND (the kidney loop: 300 to pass, 120 s, 3 rivals) and SWITCHBACK (`Maps/L_Switchback`: 790 m, five gates, a hairpin the shortcut cuts, 400 to pass, 150 s, 4 rivals). The track page shows the rules, the best score and place, and the lock hint.
- **Progress** is saved (`Saved/SaveGames/DeadFire.sav`): passing a track opens the next one; passing it in **first place** opens that track's car (BRUTE from PROVING GROUND, VIPER from SWITCHBACK); best score and place per track; the settings. The functional tests keep their own slot (`DeadFireTest`).
- **Pause** with **P** (gamepad Menu; Escape in a packaged build): the world freezes under RESUME, RESTART, MAIN MENU, QUIT. Not while the summary is up.
- The **summary** names what the race unlocked (`NEW CAR UNLOCKED: BRUTE   NEXT TRACK UNLOCKED: SWITCHBACK`), offers NEXT when the next track is open, and MENU instead of QUIT.
- **Settings**: master volume (a sound mix on the engine's Master class), difficulty EASY / NORMAL / HARD (2 / 3 / 5 rivals on PROVING GROUND, a track with no rivals keeps none; the rivals' speed scale 0.85 / 1 / 1.1 and their item interval 1.5 / 1 / 0.6 times as long), windowed / fullscreen, reset progress. Every level change fades to black and back.

- **Phase 6, test and ship**: a packaged Windows build made and smoke-tested by one script (Development and Shipping; see *Play the packaged build* and *Package it yourself* below).
- **Balanced race clock**: with 8 s per gate a lap at the rivals' pace earned back almost all of its time and a race never ended; the gate bonus is now 3 s on PROVING GROUND and 2 s on SWITCHBACK, about three minutes of racing at the rivals' pace (measurements in `docs/superpowers/balance-2026-10-30.md`; `tools/balance_sim.py` re-measures).
- **Fixes**: the race ending under the pause menu closes it; the pause menu's MAIN MENU restores the cursor and input before leaving; the volume slider saves once on release; no runtime errors from a racer controller destroyed mid-frame, a missing save object, a race ending with no player racer, or the last frame of a race level; a first run reads no missing save file; a car class that does not load falls back to the SEDAN; generated levels use Movable lights (no "LIGHTING NEEDS TO BE REBUILT" banner); the cook is warning-free.
- **Presentation**: `docs/presentation/` holds the live demo script, the slide outline and engine screenshots (`tools/capture_shots.py` recaptures them).

- **Phase 7, own look and feel** (design `docs/superpowers/specs/2026-10-30-phase7-art-feel-design.md`, plan `docs/superpowers/plans/2026-10-30-phase7-art-feel.md`): every mesh, texture, sound, effect and image the game shows is Dead Fire's own, generated by scripts (see *How the art is built*), except the template mannequin's body, which wears our materials and gear, and the five scanned Poly Haven surfaces (see *Credits*); the shipped maps and `/Game/DeadFire` use no Starter Content, VehicleAdv, Geometry or Vehicle-template mesh art (a stock audit checks it).
- **Driving**: an arcade layer on the template car for every car, player and rival alike (grip assist, downforce, stability, a handbrake drift that gives a forward kick when it lasted a second, air control), speed-scaled and smoothed steering for the player, a car reset and a look-back view; a chase camera with lag, a speed FOV and shakes on landings, hits and crashes; engine, tyre and crash sounds per car.
- **Cars and character**: three car bodies and wheels of our own on the template car's skeleton and physics, a light bar on the player's SEDAN, a roof gun and launcher that show the held item; the rivals in the gang's paint; the mannequin in a navy suit with a helmet, vest and rifle.
- **Items and shots**: mesh effects for muzzle flashes, tracers, impacts, explosions, smoke, sparks and loot bursts; shot and impact sounds; a crosshair image with a hit marker on a racer hit; crates with a coloured stripe, a floating icon, a beacon and a lid that pops off; the bomb's blinking lamp, the shield bubble, boost flames and the rocket with its trail; item icons in the HUD and the Russo One font.
- **Terrain**: PROVING GROUND and SWITCHBACK sit in their own 1 km landscapes (a valley closed by a ridge) under a dusk light, with rocks, dead trees, wrecks, barrels, containers, fences, billboards and light towers kept clear of the roads; gates are lit pylons with a banner; the menu's plinths stand on the same ground.
- **Checks**: 122 functional tests (44 new); offline art tests; `ART VERIFY` with the stock audit; the balance re-run kept the gate bonus (`docs/superpowers/balance-2026-10-31.md`); the packaged Development build ran PROVING GROUND at an average frame of about 3 to 4 ms at 1920 x 1080 (`tools/perf_run.ps1`; target 16.7 ms), measured at the race start with the player's car parked and the three rivals driving off, so not a whole-race figure.

## Open and play

1. Install **Unreal Engine 4.27.2** from the Epic Games Launcher.
2. Open `comp4900sef/comp4900sef.uproject`. The editor opens `L_TestTrack` (a race, straight away); open `Maps/L_MainMenu` for the full flow the packaged game starts with.
3. Press **Play**.

The Starter Content pack is git-ignored and re-added automatically on first open, except for the handful of its assets the Phase 3 Blueprints referenced (the explosion, smoke and fire particles, the explosion sound and the cube and sphere shapes, with their own materials and textures, about 11 MB), which are force-added so a fresh clone has them before the pack is inserted. Since Phase 7 no Dead Fire asset and no shipped map references them, nor `Content/Geometry`, `Content/VehicleAdv` or the Vehicle template's meshes (`ART VERIFY`'s stock audit checks it; only the functional-test level keeps its VehicleAdv ground, on purpose); they stay committed until the team decides to remove them. Committed free content: the engine's template packs (`Content/Vehicle`, `Content/Mannequin`, `Content/Geometry`, `Content/VehicleAdv`) and the template Blueprints the game builds on (`Content/VehicleBP/Sedan`, its `Content/VehicleBP/Blueprints/VehicleHUD`, `Content/ThirdPersonBP/Blueprints/ThirdPersonCharacter`; do not edit these, change the `BP_DF*` children instead).

The DF Blueprint Authoring plugin is marked optional and editor-only in the `.uproject`, so the project opens in a stock UE 4.27.2 install that does not have it (only regenerating Blueprints needs it).

## Play the packaged build

1. Unzip `DeadFire-v1.0.0-Win64-<Development|Shipping>-<date>-<commit>.zip` anywhere and run `comp4900sef.exe` (the project's internal name; the window says Dead Fire). The first run may install the UE4 prerequisites; Windows SmartScreen may warn because the build is not signed ("More info", "Run anyway").
2. The game starts in the main menu. **Escape** (or P) pauses; Alt+Enter or F11 toggles fullscreen.
3. Progress is saved beside the game in `comp4900sef\Saved\SaveGames\DeadFire.sav`.

The **Development** build keeps the console (`` ` ``) and writes `comp4900sef\Saved\Logs\comp4900sef.log`, which is what to attach to a bug report; the **Shipping** build has neither and is the hand-in. Each zip carries a `README.txt` with the controls and the commit it was built from.

## Package it yourself

```powershell
.\tools\package_game.ps1                    # Development: cook, stage, pak, archive into Builds\, smoke test, zip
.\tools\package_game.ps1 -Config Shipping   # the hand-in build
.\tools\package_game.ps1 -NoSmoke -NoZip    # cook, stage and archive only
pwsh -File tools\perf_run.ps1 -Build Builds\DeadFire-v1.0.0-Win64-Development-<date>-<commit>   # frame time on PROVING GROUND
```

`perf_run.ps1` (Phase 7) starts a Development build on PROVING GROUND at 1920 x 1080 with its three rivals and the engine's CSV profiler, measures 1800 frames after 300 warm-up frames, closes the game by its window and prints `PERF avg=<ms> p95=<ms> PASS|FAIL` against the targets of 16.7 ms and 20 ms, with the machine's CPU load from other programs before and during the run (a busy machine skews the numbers). The CSV and the game log are kept beside the build (`Builds\<name>-perf.csv`, `-perf.log`).

It takes a few minutes the first time (the cook is incremental after that) and can run with the editor open, but not while `run_tests.ps1` runs. The output is `Builds\DeadFire-v<version>-Win64-<config>-<yyyymmdd>-<commit>\` and a zip of it; `-dirty` after the commit means the build includes uncommitted changes, so build the hand-in after committing. Before the smoke test it checks the build holds the exe, its pak and the UE4 prerequisites installer. The smoke test starts the game windowed, checks the log for the main menu, the save system and no script errors (Development), or that it keeps running and its window could be captured (Shipping, which has no log: look at the image), captures the game's window to `Builds\<name>-smoke.png`, and deletes the `Saved` folder the run created so the zip is clean; the AutomationTool log is `Builds\<name>-uat.log`. The cooked maps are `L_MainMenu`, `L_TestTrack` and `L_Switchback`; `/Game/DeadFire/Tests` is never cooked (`Config/DefaultGame.ini`).

The script calls the engine's `AutomationTool.exe` directly instead of `RunUAT.bat`. On an installed engine `RunUAT.bat` runs `AutomationTool.exe` by bare name from its own folder, which fails ("'AutomationTool.exe' is not recognized ... BUILD FAILED") whenever the environment sets `NoDefaultCurrentDirectoryInExePath=1`, as some shells do; an editor started from such a shell inherits it, and then its own **Platforms > Windows > Package Project** fails the same way. From an editor started by the Epic Games Launcher the Package button works too, and uses the same maps and settings.

## Controls

| Action | Keyboard / mouse | Gamepad |
|---|---|---|
| Drive / move | W A S D, arrows | Left stick, triggers |
| Handbrake (car) / Jump (on foot) | Space | Left shoulder / A |
| Drift (car: hold the handbrake while steering at 40 km/h or more; let go after a second or more for a forward kick, `DRIFT` on the HUD) | Space + A / D | Left shoulder + left stick |
| Reset car (below 15 km/h, at most every 3 s: set back on its wheels where it was, no life lost) | Backspace | B (face right) |
| Look back (car, while held) | C | Right stick click |
| Enter / exit vehicle | E | Y |
| Fire | Left mouse | Right trigger |
| Use selected item (in the car) | Q | X |
| Next item | R, mouse wheel up | D-pad right |
| Switch camera (car) | Tab | View |
| Pause menu | P (Escape in a packaged build) | Menu |
| Look | Mouse | Right stick |

## Where the logic lives

| Asset (under `/Game/DeadFire/`) | Parent | What it does | Owner |
|---|---|---|---|
| `Blueprints/BP_DFVehicle` | Sedan (Vehicle template) | Body and tire health, damage routing, wrecking (explosion, hop, smoke), enter/exit, teleport, blown-tire throttle cap; item use (`UseSelectedItem`, boost, shield, `DropBomb`, `FireGun`, `FireRPG`); the car's stats (`ComputeDriveThrottle`: throttle scale and speed limiter; paint) | Fung Ming Chu, Chong Tsz Ho |
| `Blueprints/BP_DFVehicleBrute`, `BP_DFVehicleViper` | BP_DFVehicle | The other two cars: class defaults only (health, throttle scale, speed limit, boost, paint, mass), generated from the `VEHICLES` table | Fung Ming Chu, Chong Tsz Ho |
| `Blueprints/BP_DFCharacter` | ThirdPersonCharacter | Enter vehicle, fire, health, death and revive, riding inside a car; immune to explosions | Cheung Tsz Hin Anderson |
| `Components/BPC_DFWeapon` | ActorComponent | Hitscan weapon: on the character (20 / 80 m / 0.15 s) and on the car (15 / 100 m / 0.2 s); `Fire(Origin, Direction, Instigator)` | Cheung Tsz Hin Anderson |
| `Blueprints/BP_DFPlayerController`, `Components/BPC_DFRacer` | PlayerController, ActorComponent | Possession; the pause menu (`TogglePause`); per-racer score, laps, kills, deaths, gates, off-track time; the three-slot item inventory (`AddItem`, `GetSelected`, `ConsumeSelected`, `CycleSelected`) | Lee Chun Yin, Choy Tsz Lok |
| `Blueprints/BP_DFRaceGameMode`, `BP_DFRaceGameState` | GameModeBase, GameStateBase | Every race rule: clock, gates, laps, kills, deaths, per-racer respawn, off-track, ranking (`UpdateRanks`), race end, `RestartRace`; item names and caps (`GetItemInfo`), `GrantItem`, the explosion rule (`SpawnExplosion`); NPC spawning (`SpawnNPCs`, `DespawnNPCs`) and item supply (`GrantNPCItems`); the GameInstance hooks (`ApplyGameInstanceSettings`: save slot, difficulty, audio; `RefreshPlayerVehicleClass`; `RecordResult` at race end) | Choy Tsz Lok |
| `Blueprints/BP_DFSwitchbackGameMode` | BP_DFRaceGameMode | SWITCHBACK's rules (400 to pass, 150 s, 4 rivals, `LevelIndex` 1), generated from the `LEVELS` table | Choy Tsz Lok |
| `Blueprints/BP_DFGameInstance`, `BP_DFSaveGame` | GameInstance, SaveGame | The meta layer: the car and track catalogues (`GetVehicleInfo`, `GetLevelInfo`), saved progress and the unlock rules (`RecordResult`, `UnlockVehicle`, `UnlockLevel`), settings (`SetMasterVolume`, `PreviewMasterVolume`, `SetDifficulty`, the difficulty table `GetDifficultyInfo`, `ToggleFullscreen`), level changes with a fade (`OpenMapWithFade`) | Lee Chun Yin |
| `Blueprints/BP_DFMenuGameMode`, `BP_DFMenuPlayerController` | GameModeBase, PlayerController | The menu level: no pawn, cursor and UI input, the page on screen (`ShowPage`), the showcase cameras (`ShowVehicle`) | TBD |
| `UI/WBP_DFMainMenu`, `WBP_DFVehicleSelect`, `WBP_DFLevelSelect`, `WBP_DFSettings`, `WBP_DFPauseMenu` | UserWidget | The menu pages and the pause menu | TBD |
| `Blueprints/BP_DFVehicleAIController` | AIController | An NPC driver with its own `BPC_DFRacer`: lane target on the track spline, steering and speed, avoidance traces, stuck and flip recovery, item rules (`ThinkItems`) | TBD |
| `Tests/BP_DFTestGameMode` | BP_DFRaceGameMode | The functional-test level's GameMode: `NPCCount` 0, so the single-racer tests keep their world and the AI tests spawn their own NPCs | Lee Chun Yin |
| `Blueprints/BP_DFLootBox` | Actor | Orange crate collected on touch by a character on foot (cars pass through it); fixed or random item; respawns | Chong Tsz Ho |
| `Blueprints/BP_DFBomb`, `BP_DFProjectile` | Actor | The dropped bomb (arm delay, fuse, contact) and the rocket (projectile movement, explodes on hit) | Chong Tsz Ho |
| `Blueprints/BP_DFDestructible`, `BP_DFExplosiveDamage` | Actor, DamageType | The explosives-only rock on the shortcut; the damage type explosions apply | Lau Chun Kit |
| `Data/E_DFItemType`, `S_DFItemStack` | enum, struct | Item types; one inventory stack | Choy Tsz Lok |
| `Blueprints/BP_DFTrackSpline` | Actor | Closed spline; its construction script lays the road; progress and off-road queries | Lau Chun Kit |
| `Blueprints/BP_DFCheckpoint` | Actor | Gate: trigger across the road, two poles, respawn point | Lau Chun Kit |
| `Blueprints/BP_DFFx` and its children `BP_DFFxMuzzle`, `BP_DFFxTracer`, `BP_DFFxImpact`, `BP_DFFxExplosion`, `BP_DFFxPuff`, `BP_DFFxSparks`, `BP_DFFxLootBurst` | Actor | Phase 7 effects without particles: mesh shells that grow, fade and rise over a short lifetime, tinted per use, then destroy themselves; spawned by the weapon, explosions, the car and the crates | TBD |
| `Blueprints/BP_DFShakeLight`, `BP_DFShakeHeavy` | MatineeCameraShake | Camera shakes: landings and hits taken (light); crashes and explosions within 25 m (heavy) | TBD |
| `Blueprints/BP_DFScatter`, `BP_DFDebris` | Actor | The terrain's props: one instanced mesh per actor, its transforms from the terrain generator, solid or not, culled with distance; the rock wall's chunks after it breaks | TBD |
| `Blueprints/BP_DFHUD`, `UI/WBP_DFRaceHUD`, `UI/WBP_DFRaceSummary` | HUD, UserWidget | In-race HUD and end-of-race summary (unlock line, RETRY / NEXT / MENU) | Lee Chun Yin |
| `Data/S_DFTireState`, `S_DFRaceResult`, `E_DFRaceEndReason` | struct, enum | Shared data | Choy Tsz Lok |
| `Maps/L_MainMenu`, `Maps/L_TestTrack`, `Maps/L_Switchback`, `Tests/L_DF_FunctionalTests`, `Tests/FT_DF*` | | The menu level (three cars on plinths, three cameras, an empty `MenuMusic` sound actor for the team to fill); the two tracks; functional tests | Lau Chun Kit, Lee Chun Yin |

Tunables are variables marked **Instance Editable** in `Dead Fire|...` categories (for example `Dead Fire|Race` on `BP_DFRaceGameMode`: `RaceTimeLimit`, `CheckpointTimeBonus`, `PointsPerLap`, `PointsPerKill`, `MaxDeaths`, `ScoreRequirement`, `RespawnDelay`, `OffTrackMargin`, `OffTrackGraceSeconds`; `Dead Fire|Explosions` there: `TireBlastDamage`, `ExplosionImpulse`, the explosion particle and sound; `Dead Fire|AI` there: `NPCCount`, `NPCRowSpacing`, `NPCColumnOffset`, `NPCSkillSpread`, `NPCSpeedScale` (set from the difficulty), `AIItemInterval`, `RankInterval`; `Dead Fire|Items` on `BP_DFVehicle`: boost, shield, bomb and muzzle numbers; `Dead Fire|AI|Driving`, `|Avoidance`, `|Recovery` and `|Items` on `BP_DFVehicleAIController`: speeds, look-ahead, steering lock, trace distances, stuck and flip timers, item ranges and `bAutoDrive`; the bomb, rocket, crate and rock each carry their own; `Dead Fire|Stats` on `BP_DFVehicle`: `VehicleName`, `ThrottleScale`, `TopSpeedKPH`, `PaintMaterial`, `PaintSlot`; `Dead Fire|Race` also holds `LevelIndex`, `PlayerVehicleClass` and `SaveSlotOverride`; `Dead Fire|Meta` on `BP_DFGameInstance`: `SaveSlotName`, `FadeSeconds`, `MasterMix`, `MasterClass`; `Dead Fire|Menu` on the two player controllers). The per-item charges and caps live in one place, `GetItemInfo` on the GameMode; the cars, tracks and difficulties live in three tables in `tools/bpgen/df.py` (`VEHICLES`, `LEVELS` with each track's clock, pass score, rivals and checkpoint bonus, `DIFFICULTIES`), which feed the GameInstance's catalogue functions, the child Blueprints' defaults and the level builder. Hooks for effects and later phases are **event dispatchers**: `OnVehicleDamaged`, `OnTireBlown`, `OnVehicleDestroyed`, `OnOccupantEntered/Exited`, `OnCharacterDamaged/Died/Revived`, `OnEnteredVehicle/ExitedVehicle`, `OnFired`, `OnRaceEnded`, `OnRacerRespawned`, `OnExplosion`, `OnItemPickedUp`, `OnLootCollected`, `OnDestructibleDestroyed`. The GameMode writes `DF: ...` lines to the output log for deaths, wrecks, respawns, restarts, race ends, pickups and item use.

## How the Blueprints are built

The Blueprint graphs are **generated**, so they can be reviewed as code and rebuilt identically:

- `tools/bpgen/graphs/*.py` describe each Blueprint (variables, functions, dispatchers, components, widget layout, graphs) in Python; `tools/bpgen/bpgen.py` is the node library and `tools/bpgen/df.py` the shared Dead Fire names and recipes.
- `python -I tools/bpgen/generate_all.py` writes `comp4900sef/Script/paste/<Blueprint>/manifest.json` plus one `<Graph>.txt` per graph (the editor's own copy-paste format; these files also paste by hand with Ctrl+V).
- Inside the editor, `comp4900sef/Script/df_apply_blueprint.py` applies the manifests through the **DF Blueprint Authoring** editor plugin (`tools/DFBlueprintAuthoring`): creates the assets, variables, functions, dispatchers, components and widget trees, imports the graphs, links them, checks that every node, link and pin default arrived, compiles and saves. A function that already exists is removed and re-added, so a changed signature takes effect on re-apply; a Blueprint that fails to compile is retried after the others (a new variable on one Blueprint is visible to the rest only once it has compiled); a generated child Blueprint (`BP_DFTestGameMode`, the two cars, `BP_DFSwitchbackGameMode`) inherits its parent's tunable defaults and can override a property of an inherited component (`component_defaults`: the cars' `VehicleMovement.Mass`); a manifest can require a support asset the runner creates (`requires`: the `SM_DFMaster` sound mix); children of a Blueprint in the same batch are created only after it has compiled, and the functional tests are applied last; a compile that leaves a call to a not-yet-compiled Blueprint unresolved counts as a failure and is retried. A variable's declared default is written only when the variable is created; a value meant to follow a table or a later change goes through the class defaults (`Blueprint.default`), which every apply writes. A changed `editable=` on an existing variable is applied too (the plugin updates its Instance Editable flag and category).
- The graphs are laid out for reading: exec flow runs left to right, each branch gets its own row, a node's inputs sit to its left and below it, every event's chain in an event graph sits in a comment box titled with what it does, every function has a one-line description (its tooltip, and the title of the box around its body), and the branches that matter carry comment bubbles. The plugin's `set_node_position`, `set_function_description` and `focus_graph` calls place the nodes, store the descriptions and open a graph in the editor; `describe_graph` reports node positions. `python -I tools/bpgen/test_layout.py` checks the layout engine; the generator warns about any overlapping nodes it produces.
- `comp4900sef/Script/df_build_test_track.py` builds `L_TestTrack`, `L_Switchback`, `L_MainMenu` and `L_DF_FunctionalTests` from per-map layouts (`LAYOUTS`: spline points, gates, props, crates, target car, shortcut span, GameMode; the menu level gets its plinths, cars and tagged cameras).

**Rule:** for a Blueprint that has a generator module, change the module and re-apply rather than editing the graph by hand, or the next apply overwrites the edit. New Blueprints can be made by hand in the editor as usual; run `df_verify_blueprints.py` afterwards to check nothing the generated graphs call went missing.

Running the pipeline (only the person maintaining the generators needs this; everyone else just opens the project):

```powershell
.\tools\build_authoring_plugin.ps1          # once per machine: builds the plugin into D:\UE_4.27\Engine\Plugins\DeadFire (needs Visual Studio's C++ workload)
python -I tools\bpgen\generate_all.py       # regenerate manifests
python tools\ue_remote.py --code "exec(open(r'<repo>/comp4900sef/Script/df_apply_blueprint.py').read()); apply_all(r'<repo>/comp4900sef/Script/paste')"
python tools\ue_remote.py --code "exec(open(r'<repo>/comp4900sef/Script/df_build_test_track.py').read())"
python tools\ue_remote.py --code "exec(open(r'<repo>/comp4900sef/Script/df_verify_blueprints.py').read()); verify_all(r'<repo>/comp4900sef/Script/paste')"
.\tools\restart_editor.ps1 [-InstallPlugin]  # save, quit, (install the last plugin build,) relaunch, wait for Python
```

`python -I tools\bpgen\sig.py KismetMathLibrary.SelectVector` prints an engine function's exact C++ declaration, for writing new graph code with the right names. Python remote execution is pinned to loopback (`RemoteExecutionMulticastBindAddress=127.0.0.1` in `Config/DefaultEngine.ini`); if you use the `unreal-mcp-ue4` MCP server, set `UNREAL_MCP_BIND_ADDRESS=127.0.0.1` in its environment. The scripts refuse to run while a Play-In-Editor session is active.

## How the art is built

Everything under `/Game/DeadFire/Art` (meshes, textures, materials, sounds, UI images, terrain materials, effect shells) is generated by scripts in `tools/artgen` from one catalogue, `tools/artgen/catalog.py` (each asset's name, recipe, budget and import settings), and committed as imported assets. A fresh clone needs none of this: only whoever changes the art runs it. The intermediate files land in `art/` at the repository root, which is git-ignored.

```powershell
python -I tools\artgen\build_all.py                                    # everything: art\catalog.json, tools\artgen\THIRD_PARTY.md, textures, images, meshes, sounds, fonts, terrain
python -I tools\artgen\build_all.py --kind meshes --only SM_DF_Crate   # one kind (catalog, textures, images, meshes, sounds, fonts, terrain), optionally some names only
python -I tools\artgen\test_catalog.py                                 # offline checks; also test_textures, test_sounds, test_meshes, test_terrain
python -I tools\artgen\test_polyhaven.py                               # online: the Poly Haven downloader against the live site (temporary folder only)
python tools\ue_remote.py --code "exec(open(r'<repo>/comp4900sef/Script/df_export_tracks.py').read()); export_tracks(r'<repo>/tools/artgen/data/tracks')"  # after a track layout changes, before --kind terrain
python tools\ue_remote.py --code "exec(open(r'<repo>/comp4900sef/Script/df_import_art.py').read()); import_all(r'<repo>/art')"
python tools\ue_remote.py --code "exec(open(r'<repo>/comp4900sef/Script/df_build_materials.py').read()); build_materials(r'<repo>/art')"
python tools\ue_remote.py --code "exec(open(r'<repo>/comp4900sef/Script/df_verify_art.py').read()); verify_art(r'<repo>/art', audit=True)"   # ART VERIFY PASSED, STOCK AUDIT PASSED
python tools\ue_remote.py --code "exec(open(r'<repo>/comp4900sef/Script/df_build_test_track.py').read())"   # the levels: landscape, scatter, props, dusk light, the menu
python tools\capture_shots.py                                          # the presentation screenshots (editor open, no tests running)
```

- **Textures, images and sounds** are made with numpy and Pillow (`textures.py`, `images.py`, `sfx.py`); every sound keeps its asset name, so a recorded file can replace it later with no other change. **Fonts**: Russo One is copied from `tools/artgen/fonts/`.
- **Meshes** are built by Blender run headless (`--factory-startup`, so your own Blender settings and files are never touched) from one script per mesh in `tools/artgen/blender/meshes/`. **Blender 5.2 LTS is needed only to regenerate meshes** (`--kind meshes` or `all`): it is looked for at `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`, or set `DF_BLENDER` to its path.
- **Reviewing a mesh** before it is exported: the optional live loop shows it in your own Blender through the Blender MCP server (`uvx mcp-for-blender`). In Blender 5.2 install the **MCP for Blender** add-on and start it from its sidebar tab (port 9876), and turn **off** Blender Lab's own "MCP" extension, which takes the same port and speaks another protocol. `tools/artgen/blender/preview_live.py` then builds into a `DF_Preview` scene and never saves or closes your file. Without the MCP, the headless fallback renders front, side, top and three-quarter views beside a 1.8 m figure: `blender -b --factory-startup --python tools\artgen\blender\preview.py -- --script barrel --name SM_DF_Barrel --out <folder>`. Phase 7 was reviewed with the headless fallback throughout, because the MCP was not connected.
- **Poly Haven** (CC0) is used only where a generated surface failed that review, and only for natural surfaces, rocks, trees and debris. `tools/artgen/polyhaven.py` downloads the files into `art/` (8 bits per channel) and records each file's SHA-256 in `tools/artgen/polyhaven.lock.json`: a file that changed upstream is refused. `build_all.py` writes the credit lines into `tools/artgen/THIRD_PARTY.md`. Five texture sets are pinned today (see *Credits*).
- **Terrain**: `terrain.py` makes each track's 1009 x 1009 heightmap, splat map and scatter list from the exported layout: the roads on a flat shoulder, the valley closed by a ridge, props kept clear of roads, gates and crates. The level builder imports the heightmap through the authoring plugin's `CreateLandscapeFromRaw`.

## Tests

```powershell
.\tools\run_tests.ps1                                   # all functional tests, headless
.\tools\run_tests.ps1 -Filter "Project.Functional Tests./Game/DeadFire/Tests/L_DF_FunctionalTests.FT_DFRespawn"
```

The tests are Blueprint **Functional Tests** (`/Game/DeadFire/Tests/FT_DF*`, placed in `L_DF_FunctionalTests`): vehicle damage, tires, wrecking once; weapon hit and cooldown; character death and nearest-car search; enter/exit including blocked and moving cases; track length and road edges; gate order, laps, respawn at the last gate, the parked-wreck case, the death limit, nothing after the race ends, the off-track reset, time-up results, and the HUD/summary switch; and, from Phase 3, the inventory (stacking, caps, cycling, consuming), explosions (damage, tire blast, character immunity, effects-only), item use (consume, refuse when empty or wrecked), boost, shield, restart clearing, bombs (armed contact, fuse), the gun, the rocket (hit, kill credit), crates (on foot only, full inventory, respawn), the explosives-only rock, the shortcut track, and the HUD item row; and, from Phase 4, the NPC racers (spawn grid, ranking and the HUD position line, restart, the vehicle's AI inputs, steering and speed maths, lane keeping, avoidance, race end, respawn without ending the race, two respawns at once, a flipped car, the player taking an NPC's car, item use at targets, item supply); and, from Phase 5, the menus and meta (each car's throttle scale, limiter, health, boost and paint; the save round trip and the padding of an older save; the unlock rules; the settings; the chosen car on respawn and the fallback for a locked or unknown choice; result recording at race end and the test level staying empty on HARD; the summary's unlock line and NEXT; pause and resume; the car and track pages); and, from Phase 6, the ship fixes (race end under the pause menu, the volume preview, a dead racer entry, `RecordResult` without a save, a slot with no save file, the player's car class) and the difficulty table with the rivals' speed scale; and, from Phase 7 (44 more, 122 in all), the driving layer (`FT_DFDrive_*`: steering and force maths, each car's top speed, straight-line stability, turning at speed, grip, the drift and its boost, air levelling, the car reset and its limits, the speed FOV, the engine sound following the revs), the art (`FT_DFArt_*`: car parts on their sockets, wheels following the bones, the character's gear, the roof weapon showing the held item, shield bubble, boost flames, blown-tyre rim, charred wreck, the rivals' paint, crates' colour and hiding, the bomb's blink, the next gate lit, the rock wall breaking, scatter instances), the effects (`FT_DFFx_*`: shells growing and fading, tracers between their ends, gun and rifle shots, explosions, sparks, no tyre smoke far away, effects cleared on restart) and the HUD (`FT_DFHUD_*`: the hit marker, the damage vignette, the crate prompt). `FT_DFShot_*` in the same folder are presentation captures, not tests: the level builder never places them, and `tools/capture_shots.py` puts one in its level for a capture run only. The functional-test level runs `BP_DFTestGameMode` (no NPCs, and the `DeadFireTest` save slot so a test run never touches your progress); the playable levels have three and four rivals. All tests share one play session, so race tests start with `RestartRace`. In the editor: **Window → Developer Tools → Session Frontend → Automation**, filter `Functional Tests`. `FT_DFZZ_Screenshots` captures the HUD, on-foot and summary screens to `comp4900sef/Saved/Screenshots/Windows/` when run in the editor (black when headless). A test run started inside the editor can leave its play session open afterwards; press **Stop** (or run `unreal.EditorLevelLibrary.editor_end_play()`) before running the editor scripts, which refuse to work during play.

Engine warnings raised during tests (the Sedan physics asset logs `BoneIndex ... out of range of SpaceBases` once per freshly spawned car) are listed by `run_tests.ps1` but do not fail tests (`bTreatLogWarningsAsTestErrors=False`); failed assertions do.

The tests cannot press keys, so driving feel, cameras and the menus are checked by hand with `docs/superpowers/playtest-checklist.md`.

## Working together on Blueprint assets

`.uasset` files are binary and cannot be merged. Each Blueprint has one owner (table above); coordinate before touching someone else's, and pull before you start. If two people did change the same asset, keep one version and redo the other change by hand (or, for generated Blueprints, re-apply from the generator).

## Project layout

```
comp4900sef/Content/DeadFire/   Blueprints/, Components/, Data/, UI/, Audio/ (the master sound mix), Maps/ (L_MainMenu, L_TestTrack, L_Switchback), Tests/ (functional tests + test level), Art/ (the imported generated art and the L_DF_LookDev look-dev level)
comp4900sef/Content/VehicleBP/, ThirdPersonBP/   engine template Blueprints the game builds on (do not edit)
comp4900sef/Script/             editor Python: apply / verify Blueprints, build levels, import / verify art, build materials, export tracks, balance runs, conversion check; paste/ = generated manifests
tools/bpgen/                    Blueprint generators (graphs/*.py: one module per area, items.py for the Phase 3 actors, ai.py for the NPC driver, meta.py for the GameInstance and SaveGame, menus.py for the menu pages, tests*.py for the functional tests), library (bpgen.py: node library and layout engine), df.py (shared names, the VEHICLES and LEVELS tables), engine signature lookup, test_layout.py
tools/DFBlueprintAuthoring/     editor plugin source used by the apply script (built into the engine, not the project)
tools/artgen/                   art generators (Phase 7): catalog.py (every asset), build_all.py, textures/images/sfx/terrain.py, blender/ (mesh scripts, headless and live previews), polyhaven.py + polyhaven.lock.json, THIRD_PARTY.md, fonts/, data/ (car dimensions, track exports), test_*.py
art/                            generated files before import (git-ignored); art/lookdev/ holds the development captures
tools/                          run_tests.ps1, package_game.ps1 (+ package/README.template.txt), perf_run.ps1, balance_sim.py + balance_timestep.py, capture_shots.py, ue_remote.py, restart_editor.ps1, build_authoring_plugin.ps1
docs/superpowers/               design, phase plans, playtest checklist, balance-2026-10-30.md and balance-2026-10-31.md
docs/presentation/              live demo script, slide outline, screenshots
```

## Credits

Third-party assets are listed, with their licences, in [`tools/artgen/THIRD_PARTY.md`](tools/artgen/THIRD_PARTY.md) (written by `build_all.py`):

- **Poly Haven** (polyhaven.com), CC0: five scanned texture sets, each pinned by SHA-256 in `tools/artgen/polyhaven.lock.json`: burned ground, grass ground, rock face, brushed concrete and rusty metal (`T_DF_AshGround`, `T_DF_DryGrass`, `T_DF_Rock`, `T_DF_Concrete`, `T_DF_RustMetal`). Some textures: Poly Haven (polyhaven.com), CC0.
- **Russo One** by Jovanny Lemonad, SIL Open Font License 1.1 (the licence is `tools/artgen/fonts/OFL.txt`).
- **Unreal Engine 4.27 template content** by Epic Games, under the Unreal Engine EULA: the Vehicle template's Sedan (the skeleton and physics under our car bodies), the Third Person template's mannequin and Blueprints, and the other committed template packs listed under *Open and play*.

Everything else (the Blueprints, levels, meshes, textures, sounds, effects and UI) is generated for Dead Fire by the scripts in this repository.
