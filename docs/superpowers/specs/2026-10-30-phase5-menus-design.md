# Dead Fire — Phase 5 (Menus & Meta) Design Addendum

Date: 2026-10-30
Extends: `2026-10-20-dead-fire-design.md` (§3 core loop, §4 rules, §7 phase table), `2026-10-21-phase2-race-flow-design.md` (§5 race end and summary, §8 Phase 5 hooks) and `2026-10-30-phase4-ai-design.md` (NPC count and speed as the difficulty knobs). Only what Phase 5 needs is added; nothing earlier changes unless stated.
Status: the project manager asked for the next phase to start, as for Phases 3 and 4, without a question round. Every decision below that the proposal, flowchart and earlier designs do not settle is an implementer's call, marked **[call]**; the team can overturn any of them in the generator modules (`tools/bpgen/graphs/`), the catalogue tables in `tools/bpgen/df.py`, or by changing an Instance Editable value.

## 1. What Phase 5 delivers

Proposal week 12 and base design §7: "main menu, vehicle select with stats, level select, unlocks (SaveGame), pause, summary, audio/VFX polish". The flowchart's outer loop: *Start Game → game menu → vehicle selection (with statistics) → level selection → race → summary; first place on the level unlocks that stage's vehicle; continue playing (back to vehicle select) or quit.* Concretely:

1. **A main menu level** (`L_MainMenu`) the packaged game starts in: title, PLAY / SETTINGS / QUIT, with the three cars on plinths behind the menu and the camera moving to the one being chosen.
2. **Vehicle select** with stat bars (top speed, acceleration, armor, boost), a description and the lock state; **level select** with each track's description, requirement, best score and place, and lock state.
3. **Three vehicles** that drive differently (SEDAN, BRUTE, VIPER) as children of `BP_DFVehicle`; the chosen class is what the player starts in and respawns in.
4. **Two tracks**: the existing loop (PROVING GROUND) and a new, longer one (SWITCHBACK) with its own per-level GameMode (requirement, clock, rivals).
5. **Progress that persists** in a SaveGame: unlocked vehicles and levels, best score and place per level, and the settings. Unlock rules per the flowchart: passing a level unlocks the next track; finishing **first** on a level (and passing it) unlocks that stage's vehicle.
6. **Pause menu** (P / gamepad Menu; Escape in a packaged build): RESUME, RESTART, MAIN MENU, QUIT; the world freezes.
7. **Summary** gains the unlock line (`NEW CAR UNLOCKED: BRUTE`, `NEXT TRACK UNLOCKED: SWITCHBACK`), a NEXT button when the next track is open, and QUIT becomes MENU (the Phase 2 hook).
8. **Settings**: master volume, difficulty (EASY / NORMAL / HARD, which changes the number of rivals), fullscreen toggle, reset progress.
9. **Polish, reduced to what the pipeline can author** **[call]**: a fade to black on every level change, a master-volume sound mix, and an empty `MenuMusic` ambient sound actor in the menu level for the team to drop a cue onto. No new particle systems, no UI sounds (see §6).
10. Functional tests for every rule the tests can reach, README, playtest checklist, base design table rows.

Out of scope: a 3D car preview inside the race HUD; keyboard/gamepad focus navigation of the menus beyond what UMG gives buttons by default (mouse first; the summary and pause menus focus their first button) **[call]**; leaderboards, names, multiple save slots; difficulty affecting NPC speed (only the count changes) **[call]**; packaging (Phase 6).

## 2. Flow, levels, GameModes

### 2.1 Screens and transitions

```
L_MainMenu                                   race level (L_TestTrack / L_Switchback)
 WBP_DFMainMenu ── PLAY ──► WBP_DFVehicleSelect ── NEXT ──► WBP_DFLevelSelect ── RACE ──► race ──► WBP_DFRaceSummary
   │ SETTINGS ──► WBP_DFSettings ── BACK ─┘        ◄── BACK ──┘                            RETRY: same track, same car
   │ QUIT: leave the game                                                                   NEXT:  next track, same car (when open)
   ▼                                                                                        MENU:  back to L_MainMenu, on the vehicle page
 (returning from a race opens on the vehicle page: the flowchart's "continue playing → vehicle selection")   P: WBP_DFPauseMenu (RESUME / RESTART / MAIN MENU / QUIT)
```

- The packaged game starts in `L_MainMenu` (`GameDefaultMap`). The editor still opens `L_TestTrack` (`EditorStartupMap`) so a developer can press Play and race at once **[call]**; a race level started directly uses the GameInstance defaults (SEDAN, NORMAL difficulty) and its GameMode writes its own `LevelIndex` into the GameInstance's `SelectedLevel` at Begin Play, so the summary's NEXT and the menu's return page are right whichever way the level was entered. Every existing test and workflow is unchanged.
- Every level change goes through `BP_DFGameInstance.OpenMapWithFade(MapName)`: the local player's camera fades to black over `FadeSeconds` (0.5 s) **[call]**, then `OpenLevel`. The summary's RETRY keeps reloading the current level through the same path.

### 2.2 Level catalogue

One table, `LEVELS` in `tools/bpgen/df.py`, feeds the GameInstance's `GetLevelInfo`, the per-level GameMode defaults and the level builder, so a number lives in one place:

| Index | Name | Map | GameMode | Pass score | Clock | Rivals | Gates | Unlocked by |
|---|---|---|---|---|---|---|---|---|
| 0 | PROVING GROUND | `Maps/L_TestTrack` | `BP_DFRaceGameMode` | 300 | 120 s | 3 | 4 | always |
| 1 | SWITCHBACK | `Maps/L_Switchback` | `BP_DFSwitchbackGameMode` | 400 | 150 s | 4 | 5 | passing PROVING GROUND |

Descriptions **[call]**: "The kidney loop you know: four gates, a shortcut behind a rock, crates in the infield." / "Longer and tighter: five gates, an S-bend you must brake for, more rivals, more time."

- `BP_DFRaceGameMode` gains `LevelIndex` (int, 0, `Dead Fire|Race`, Instance Editable): the catalogue row this level reports to. `BP_DFSwitchbackGameMode` (`/Game/DeadFire/Blueprints/`, a generated child with no graphs) sets `LevelIndex` 1, `RaceTimeLimit` 150, `ScoreRequirement` 400, `NPCCount` 4; everything else inherits. `BP_DFTestGameMode` is unchanged (`LevelIndex` 0, `NPCCount` 0).
- **SWITCHBACK** is built by the level builder from its own point list **[call, shape left to the builder]**: about 700 m around, flat, with one tight S-section where the Phase 4 AI slows to `CornerSpeedKPH`, five gates at equal distances, six crates ≥ 15 m from every road, a shortcut with its rock (the Phase 3 builder rules), the same infield prop set in new places, a parked target car, and a player start on the line. The level builder's single track constants become a per-map table (`LEVEL_LAYOUTS`) keyed by map path; the functional-test level keeps the PROVING GROUND layout and its test actors.

### 2.3 Difficulty

`BP_DFGameInstance.Difficulty` (0 EASY, 1 NORMAL, 2 HARD; saved) changes the number of rivals only **[call]**: `GetNPCCountFor(LevelCount)` returns 0 when the level says 0 (the test level stays empty on every difficulty), otherwise `max(1, LevelCount + (−1, 0, +2)[Difficulty])`. `BP_DFRaceGameMode` Begin Play sets `NPCCount` from it once, before `SpawnNPCs`, when the GameInstance is a `BP_DFGameInstance` (`RestartRace` reuses the adjusted count; it never applies the delta again). NPC speed and item supply are untouched (Phase 6 balance).

## 3. Vehicles and stats

### 3.1 Catalogue

`VEHICLES` in `tools/bpgen/df.py` feeds `GetVehicleInfo`, the child Blueprints' defaults, the menu level's showcase and the tests:

| Index | Name | Class | Unlocked by | Max health | Throttle scale | Top speed | Boost | Mass | Paint | Bars (speed / accel / armor / boost) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | SEDAN | `BP_DFVehicle` | always | 100 | 1.0 | none | 2 s, kick 1200 | template | template | 3 / 3 / 3 / 3 |
| 1 | BRUTE | `BP_DFVehicleBrute` | 1st on PROVING GROUND | 160 | 0.8 | 120 km/h | 2 s, kick 1200 | ×1.3 | `/Game/Vehicle/Meshes/GrayMaterial` | 2 / 2 / 5 / 3 |
| 2 | VIPER | `BP_DFVehicleViper` | 1st on SWITCHBACK | 70 | 1.0 | none | 3 s, kick 1600 | ×0.8 | `/Game/Vehicle/Meshes/OrangeMaterial` | 5 / 4 / 2 / 5 |

All values **[call]**; descriptions **[call]**: "Balanced. Takes a beating, keeps its speed." / "Armoured and heavy: slow to get going, hard to kill, limited to 120." / "Light and fragile: fastest off the line, with a longer, harder boost."

### 3.2 How a vehicle differs

- `BP_DFVehicle` gains `Dead Fire|Stats`: `VehicleName` (string, `SEDAN`), `ThrottleScale` (float 1), `TopSpeedKPH` (float 0 = no limiter), `PaintMaterial` (object `MaterialInterface`, none), `PaintSlot` (int; the Sedan mesh's paint material index, read in the editor when the module is written) — all Instance Editable.
- `ComputeDriveThrottle(Input, SpeedKPH) -> float` (pure): `Input × ThrottleScale`, except 0 when `Input > 0`, `TopSpeedKPH > 0` and `SpeedKPH ≥ TopSpeedKPH` (a limiter; braking and reverse are never scaled down to nothing: a negative input only gets the scale). `TickDriveOverrides` runs the player's axis and the AI throttle through it (after the Phase 2 blown-tire cap). **[call]**
- Begin Play: `Health = MaxHealth` (today the car starts at the variable's own default of 100, which a 160-health child would keep), then, when `PaintMaterial` is set, `Mesh.SetMaterial(PaintSlot, PaintMaterial)`.
- Boost: the children set `BoostDuration` / `BoostKickSpeed` (existing Phase 3 tunables).
- Mass: a child overrides the inherited `VehicleMovement` component's `Mass` default (the Sedan template's value × the factor). The manifest gains `component_defaults: {"VehicleMovement": {"Mass": <kg>}}`, applied by the runner to the child's class-default object's component (the editor's own way of overriding a native component default in a child Blueprint). **[call]** This is the one Phase 5 mechanism the pipeline has not used before, so the plan spikes it first; if the value does not survive compile and save, the children keep the template mass, the accel/speed bars are corrected, and the ledger records it.
- The children are generated Blueprints with variables' defaults only (no graphs), parent `BP_DFVehicle`; the runner's `_inherited_defaults` copies the parent's editable defaults into them first, as for `BP_DFTestGameMode`.
- NPCs, the parked target car and every test keep driving `BP_DFVehicle` **[call]**: the player's choice is the one variable in the field.

### 3.3 Which car the player gets

- `BP_DFRaceGameMode` gains `PlayerVehicleClass` (class of `BP_DFVehicle`, Instance Editable, default `BP_DFVehicle`). `HandleStartingNewPlayer`, before the parent call, sets it from the GameInstance (`GetVehicleInfo(SelectedVehicle).Class`, falling back to `BP_DFVehicle` when that index is locked or the GameInstance is not ours) and writes it into `DefaultPawnClass`, so the engine's own spawn uses it. `RespawnRacer`'s player path spawns `PlayerVehicleClass` instead of `BP_DFVehicle` (the SpawnActor node's class pin wired to the variable). The NPC path is unchanged.

## 4. Progress: SaveGame, GameInstance, unlocks

### 4.1 `BP_DFSaveGame` (`/Game/DeadFire/Blueprints/`, parent `/Script/Engine.SaveGame`)

`UnlockedVehicles: array<bool>`, `UnlockedLevels: array<bool>`, `BestScores: array<int>`, `BestRanks: array<int>` (0 = never placed), `MasterVolume: float` (1), `Difficulty: int` (1). Arrays are padded to the catalogue sizes on load (`EnsureArrays`), so an older save survives a new car or track; vehicle 0 and level 0 are forced unlocked. **[call]**

### 4.2 `BP_DFGameInstance` (`/Game/DeadFire/Blueprints/`, parent `/Script/Engine.GameInstance`; the project's `GameInstanceClass`)

Variables (`Dead Fire|Meta`): `Save` (object `BP_DFSaveGame`), `SaveSlotName` (string `DeadFire`, Instance Editable), `SelectedVehicle` (int 0), `SelectedLevel` (int 0), `LastUnlockedVehicle` (int −1), `bLastUnlockedLevel` (bool), `bReturnToVehicleSelect` (bool), `FadeSeconds` (float 0.5), `MasterMix` (object `SoundMix`, default `/Game/DeadFire/Audio/SM_DFMaster`), `MasterClass` (object `SoundClass`, default `/Engine/EngineSounds/Master`).

Functions:
- Catalogue (pure, `Select` chains keyed on the index, like `GetItemInfo`): `GetVehicleCount`, `GetVehicleInfo(Index) -> Name, Class, UnlockLevel, Speed, Acceleration, Armor, Boost, Description`, `GetLevelCount`, `GetLevelInfo(Index) -> Name, MapName, Description, ScoreRequirement, TimeLimit, NPCCount`. Out-of-range indices return the first row.
- Progress (pure): `IsVehicleUnlocked(Index)` (0 always; out of range false), `IsLevelUnlocked(Index)`, `GetBestScore(Level)`, `GetBestRank(Level)`, `CountUnlockedVehicles()`, `CountUnlockedLevels()`.
- `LoadProgress()`: `LoadGameFromSlot(SaveSlotName, 0)` cast to `BP_DFSaveGame`, else `CreateSaveGameObject`; then `EnsureArrays`. `SaveProgress()`: `SaveGameToSlot`. `ResetProgress()`: a fresh object with the settings kept **[call]**, saved; `SelectedVehicle` and `SelectedLevel` back to 0.
- `RecordResult(LevelIndex, Score, Rank, bPassed) -> UnlockedVehicle:int, bUnlockedLevel:bool`: `BestScores[L] = max`; when `bPassed`, `BestRanks[L] = min` over placed results (0 counts as none); when `bPassed` and `Rank == 1`, the vehicle whose `UnlockLevel == LevelIndex` is unlocked if it was locked (returned, else −1); when `bPassed`, level `L + 1` is unlocked if it exists and was locked (returned); writes `LastUnlockedVehicle` / `bLastUnlockedLevel`; `SaveProgress`. Deaths (GAME OVER) never pass, so they unlock nothing and set no place; the score still counts toward the best. **[call]**
- Settings: `SetMasterVolume(V)` (clamped 0–1, saved, `ApplyAudioSettings`), `ApplyAudioSettings()` (`SetSoundMixClassOverride(MasterMix, MasterClass, Volume, 1, 0.2, true)` + `PushSoundMixModifier`; the Master class is every sound's default class, so one override covers the game), `SetDifficulty(D)` (0–2, saved), `GetDifficultyName()`, `GetNPCCountFor(LevelCount)` (§2.3), `ToggleFullscreen()` (`GameUserSettings`: Fullscreen ↔ Windowed, `ApplySettings`; the engine persists this itself), `IsFullscreen()`.
- Navigation: `StartRace()` (`SelectedLevel`'s map), `StartNextLevel()` (`SelectedLevel + 1` when unlocked), `OpenMainMenu()` (sets `bReturnToVehicleSelect` when called from a race level, i.e. when the GameMode is a `BP_DFRaceGameMode`), each through the custom event `OpenMapWithFade(MapName)` (fade, `Delay FadeSeconds`, `OpenLevel`).
- `UseSaveSlot(SlotName)`: when the name differs from `SaveSlotName`, switches to it and `LoadProgress` (the tests' slot, below).
- Event `Init`: `LoadProgress`. Audio is applied by each level's GameMode at Begin Play (`BP_DFRaceGameMode`, `BP_DFMenuGameMode`), because the GameInstance has no world yet at Init **[call]**.
- **The developer's real save is never touched by a test run.** Every `EndRace` records a result (§4.3), and the Phase 2–4 tests call `EndRace` too, so the protection sits in the GameMode, not in the tests: `BP_DFRaceGameMode` gains `SaveSlotOverride` (string, empty, Instance Editable); when it is set, Begin Play calls `UseSaveSlot(SaveSlotOverride)`. `BP_DFTestGameMode` sets it to `DeadFireTest`, so the whole functional-test level reads and writes `Saved/SaveGames/DeadFireTest.sav` and nothing else. **[call, from the builder check]**

### 4.3 Race end

`EndRace`, after the result struct is written and before `OnRaceEnded`: when the GameInstance is a `BP_DFGameInstance`, `RecordResult(LevelIndex, Score, Rank, bPassed)`; `S_DFRaceResult` is unchanged (the summary reads the unlock outcome from the GameInstance) **[call]**. `BP_DFHUD.ShowSummary` passes the GameMode's `LevelIndex` to the summary as a third argument.

## 5. Menus

All widgets in `/Game/DeadFire/UI/`, built with the Phase 2 widget recipes (text blocks with shadows, default UMG buttons with dark labels) so they match the HUD and summary. Copy and layout **[call]**; fonts and exact positions are the builder's.

### 5.1 `L_MainMenu`, `BP_DFMenuGameMode`, `BP_DFMenuPlayerController`

- The level (built by the level builder): ground slab, the same sun / sky / fog as the tracks, three plinths (scaled `Shape_Cube`) 7 m apart with one car of each class parked on them (placed `BP_DFVehicle`, `BP_DFVehicleBrute`, `BP_DFVehicleViper`), three `CameraActor`s tagged `Showcase0..2` framing each car from the front-left, and an `AmbientSound` actor `MenuMusic` with no sound set (the team drops a cue on it; nothing in Starter Content is small enough to force-add **[call]**). World Settings GameMode: `BP_DFMenuGameMode`.
- `BP_DFMenuGameMode` (parent `GameModeBase`): `PlayerControllerClass` = `BP_DFMenuPlayerController`, `DefaultPawnClass` = none, HUD default. Begin Play: `ApplyAudioSettings`.
- `BP_DFMenuPlayerController`: `CurrentPage` (object `UserWidget`), `ShowcaseCameras` (array of `CameraActor`, filled at Begin Play from tags). Begin Play: cursor on, `SetInputMode_UIOnlyEx`, view target `Showcase0`, then `ShowPage(WBP_DFVehicleSelect)` when the GameInstance's `bReturnToVehicleSelect` is set (and cleared), else `ShowPage(WBP_DFMainMenu)`. `ShowPage(Class)`: removes `CurrentPage`, creates the new widget for this player, adds it to the viewport, keeps it in `CurrentPage`. `ShowVehicle(Index)`: `SetViewTargetWithBlend(ShowcaseCameras[Index], 0.5 s)`.
- Each page's buttons call the owning player cast to `BP_DFMenuPlayerController`; in the functional-test world that cast fails and the page does nothing, which is what the tests want (they exercise the page functions directly).

### 5.2 Pages

- **`WBP_DFMainMenu`**: `DEAD FIRE` (60, amber) with `死火` under it (28), buttons PLAY, SETTINGS, QUIT in a left-hand column over a translucent panel (the cars stay visible to the right), and a footer `CARS 1 / 3   TRACKS 1 / 2` from the GameInstance counts. PLAY → vehicle select; SETTINGS → settings; QUIT → `QuitGame`.
- **`WBP_DFVehicleSelect`**: `CHOOSE YOUR CAR`; `NameText`; four stat lines `TOP SPEED     [###--]`, `ACCELERATION  [###--]`, `ARMOR         [###--]`, `BOOST         [###--]` (ASCII bars, five cells **[call]**: Roboto has no block glyphs); `DescriptionText`; `LockText` (`LOCKED  -  FINISH 1ST ON PROVING GROUND`, blank when unlocked); `<` and `>` buttons (wrapping), `NEXT` (disabled while locked), `BACK`. `Index` (int) starts at the GameInstance's `SelectedVehicle`. `Refresh()` fills everything from `GetVehicleInfo` / `IsVehicleUnlocked` and calls `ShowVehicle(Index)` on the menu controller; `SelectNext()` / `SelectPrevious()`; `Confirm()` writes `SelectedVehicle` and opens the level page. The page's functions are the testable surface.
- **`WBP_DFLevelSelect`**: `CHOOSE A TRACK`; `NameText`; `DescriptionText`; `RulesText` (`PASS 300   CLOCK 120 s   RIVALS 3`); `BestText` (`BEST 450   PLACE 1`, `BEST 120   PLACE -` or `NOT RACED YET`); `LockText` (`LOCKED  -  PASS PROVING GROUND`); `<` `>`, `RACE` (disabled while locked), `BACK` (to the vehicle page). `Confirm()` writes `SelectedLevel` and calls `StartRace`.
- **`WBP_DFSettings`**: `SETTINGS`; `MASTER VOLUME` with a `Slider` (0–1, bound `OnValueChanged` → `SetMasterVolume`) and a percentage label; `DIFFICULTY  < NORMAL >` (`SetDifficulty`, label from `GetDifficultyName`, with a one-line hint `2 / 3 / 5 rivals on Proving Ground`); `DISPLAY: WINDOWED / FULLSCREEN` button (`ToggleFullscreen`); `RESET PROGRESS` (one press; the label changes to `PROGRESS RESET` for the rest of the visit **[call]**); `BACK`.
- **`WBP_DFPauseMenu`**: dark backdrop (0.65), `PAUSED`, RESUME, RESTART, MAIN MENU, QUIT. RESUME → the owning `BP_DFPlayerController.TogglePause()`; RESTART → unpause, then `RestartRace`; MAIN MENU → unpause, then `OpenMainMenu`; QUIT → `QuitGame`.
- **`WBP_DFRaceSummary`** changes: `UnlockText` (amber, 26) under the stats line: `NEW CAR UNLOCKED: BRUTE`, `NEXT TRACK UNLOCKED: SWITCHBACK`, both joined with `   `, or blank, from the GameInstance's `LastUnlockedVehicle` / `bLastUnlockedLevel` (read in `ShowResult(Result, ScoreRequirement, LevelIndex)`, then cleared); buttons RETRY, NEXT (collapsed unless `bPassed` and level `LevelIndex + 1` exists and is unlocked), MENU. RETRY reloads the level through the GameInstance's fade; NEXT sets `SelectedLevel` to `LevelIndex + 1` and starts it; both keep the car; MENU → `OpenMainMenu`.

### 5.3 Pause

- `BP_DFPlayerController` gains `PauseWidgetClass` (class, default `WBP_DFPauseMenu`), `PauseWidget`, and `TogglePause()`: refused (no change) when there is no GameState or the race is over (the summary owns the screen then) **[call]**; pausing = `SetGamePaused(true)`, create and add the widget, cursor on, `SetInputMode_GameAndUIEx` with RESUME focused (Game-and-UI, not UI-only, so the P key still reaches the controller and resumes **[call, from the builder check]**); resuming = remove the widget, `SetGamePaused(false)`, cursor off, `SetInputMode_GameOnly`.
- Event graph: `InputAction Pause` (the existing mapping: P, Escape, gamepad Menu) with **Execute when Paused** on, → `TogglePause`. The generator's `input_action` gains the flag. Escape ends Play-In-Editor before the game sees it, so the checklist uses P.
- `RestartRace` and `EndRace` resume a paused game first (a race cannot end while paused, but a restart from the pause menu must work).

## 6. Polish

- **Fade**: every level change fades the local camera to black over `FadeSeconds` before `OpenLevel` (§2.1). The arriving level fades in from black over the same time: the camera manager's fade at Begin Play of both player controllers (`BP_DFPlayerController`, `BP_DFMenuPlayerController`; a GameMode's Begin Play runs before the player exists). **[call]**
- **Master volume**: `SM_DFMaster` (`/Game/DeadFire/Audio/`, a `SoundMix` asset created by the apply runner when missing, through the editor's `SoundMixFactory`) overrides the engine `Master` class volume (§4.2).
- **Menu music**: the empty `MenuMusic` actor (§5.1).
- Nothing else: new particle systems, UMG animations and UI sounds cannot be authored through the generator and the plugin, and hand-made assets would be overwritten or orphaned; the team can add them in the editor on the assets that are **not** generated (the level, sound cues, materials). **[call]**

## 7. Rules summary (tunables; owner in brackets)

| Rule | Value |
|---|---|
| Vehicles: name / max health / throttle scale / top speed / boost s, kick / mass factor [VEHICLES, child defaults] | SEDAN 100 / 1.0 / none / 2, 1200 / 1; BRUTE 160 / 0.8 / 120 / 2, 1200 / 1.3; VIPER 70 / 1.0 / none / 3, 1600 / 0.8 |
| Vehicle unlock [GameInstance] | pass the level **and** place 1st: BRUTE from PROVING GROUND, VIPER from SWITCHBACK |
| Level unlock [GameInstance] | pass the previous level (any place) |
| Levels: pass score / clock / rivals / gates [LEVELS, GameMode children] | PROVING GROUND 300 / 120 s / 3 / 4; SWITCHBACK 400 / 150 s / 4 / 5 |
| Difficulty rival delta (EASY / NORMAL / HARD) [GameInstance] | −1 / 0 / +2, at least 1, and 0 stays 0 |
| Save slot / user index [GameInstance] | `DeadFire` / 0 (`DeadFireTest` through the test GameMode's `SaveSlotOverride`) |
| Fade on level change [GameInstance] | 0.5 s |
| Showcase camera blend [Menu PC] | 0.5 s |
| Master volume default / mix fade [SaveGame, GameInstance] | 1.0 / 0.2 s |
| Pause refused when [Player PC] | no GameState or `bRaceActive` false |

## 8. Tests (`tools/bpgen/graphs/tests_menu.py`, `FT_DFMenu_*`)

All run in the shared functional-test world with `BP_DFTestGameMode`, whose `SaveSlotOverride` points the whole session at `DeadFireTest` (§4.2), so no test can touch a developer's real save; every test that reads progress starts with `ResetProgress` (and asserts the slot name is `DeadFireTest` as a guard) and ends with `ResetProgress` again. Paused-world tests put no latent node between pause and resume (latent actions do not tick while paused).

- `SaveRoundTrip`: `UnlockVehicle(2)` (an internal helper exposed for tests), `SaveProgress`, `LoadProgress` → vehicle 2 unlocked, vehicle 1 not, best score 0; a save whose arrays were shortened to one entry loads padded, with vehicle 0 open; `ResetProgress` → vehicle 2 locked again; `DoesSaveGameExist(DeadFireTest)` true.
- `UnlockRules`: `RecordResult(0, 400, 1, true)` → `UnlockedVehicle` 1, `bUnlockedLevel` true, level 1 unlocked, best score 400, best rank 1; `RecordResult(0, 500, 2, true)` → −1 / false, best 500, rank still 1; `RecordResult(1, 100, 1, false)` → nothing unlocked, best 100, rank 0; `RecordResult(1, 450, 1, true)` → vehicle 2 unlocked, `bUnlockedLevel` false (no level 2); `RecordResult(0, 400, 1, true)` again → −1 (already unlocked).
- `EndRaceRecordsAndShowsUnlock`: `race_context`; score 350 (requirement 300); `EndRace(TimeUp)` → `GetBestScore(0)` 350, vehicle 1 unlocked, the summary's `UnlockText` reads `NEW CAR UNLOCKED: BRUTE   NEXT TRACK UNLOCKED: SWITCHBACK`, the NEXT button is visible; `RestartRace`.
- `GameOverRecordsScoreOnly`: score 350, `EndRace(DeathLimit)` → best score 350, best rank 0, nothing unlocked, `UnlockText` blank, NEXT collapsed.
- `VehiclePage`: a `WBP_DFVehicleSelect` created for the player, `Refresh` → `NameText` `SEDAN`, `ArmorText` ends in `[###--]`, `LockText` blank, NEXT enabled; `SelectNext` → `BRUTE`, `LockText` `LOCKED  -  FINISH 1ST ON PROVING GROUND`, NEXT disabled; `UnlockVehicle(1)`, `Refresh` → enabled; `SelectNext` twice → `SEDAN` (wraps); `Confirm` → `SelectedVehicle` 0.
- `LevelPage`: `WBP_DFLevelSelect`: index 0 `PROVING GROUND`, `RulesText` `PASS 300   CLOCK 120 s   RIVALS 3`, `BestText` `NOT RACED YET`, RACE enabled; `SelectNext` → `SWITCHBACK` locked, RACE disabled; `RecordResult(0, 420, 2, true)`, `SelectPrevious`, `Refresh` → `BEST 420   PLACE 2`; `SelectNext` → unlocked.
- `SettingsApply`: `SetMasterVolume(0.3)` → `Save.MasterVolume` 0.3 (clamped: 1.7 → 1); `SetDifficulty(2)` → `GetDifficultyName` `HARD`; `GetNPCCountFor(3)` → 5, `GetNPCCountFor(0)` → 0; `SetDifficulty(0)` → `GetNPCCountFor(1)` → 1; `ResetProgress` keeps difficulty 0 and volume 1; the test GameMode's effective count stays 0 (`SpawnNPCs` after a restart spawns none on HARD).
- `PauseToggles`: `TogglePause` → `IsGamePaused` true, one `WBP_DFPauseMenu` on screen; `TogglePause` → false, none. `EndRace`, `TogglePause` → still unpaused, no widget; `RestartRace`.
- `ThrottleStats`: a spawned `BP_DFVehicleBrute`: `ComputeDriveThrottle(1, 50)` 0.8, `(1, 125)` 0, `(−0.5, 125)` −0.4, `MaxHealth` 160, `VehicleName` `BRUTE`, paint slot material is `GrayMaterial`; a `BP_DFVehicle`: `(1, 200)` 1; a `BP_DFVehicleViper`: `MaxHealth` 70, `BoostDuration` 3. Each matches `GetVehicleInfo`'s name and armor bar order (SEDAN 3 < BRUTE 5, VIPER 2).
- `SelectedVehicleSpawns`: `UnlockVehicle(1)`, `SelectedVehicle` 1, `RestartRace`, wreck the player's car, 2.5 s → the new car is a `BP_DFVehicleBrute` (`RestartRace` re-reads `PlayerVehicleClass` too; the intact car is kept and the class applies to the next car spawned, here the wreck's replacement **[call]**); `SelectedVehicle` 0, `RestartRace`, wreck → `BP_DFVehicle`.
- `LockedSelectionFallsBack`: `SelectedVehicle` 2 while locked, `RestartRace`, wreck → `BP_DFVehicle`.
- The existing 56 tests pass unchanged (the test GameMode spawns no NPCs on any difficulty, the default car is the SEDAN, the test world never changes level, and their `EndRace` calls record into the test slot).

## 9. Level, config, docs, hooks

- `df_build_test_track.py`: `LEVEL_LAYOUTS` per map (points, gates, props, crates, target car, GameMode); builds `L_TestTrack`, `L_Switchback`, `L_MainMenu` and `L_DF_FunctionalTests`; the SWITCHBACK layout is validated by the existing builder checks (shortcut saving, crate clearance, rock clearance).
- `Config/DefaultEngine.ini`: `GameDefaultMap=/Game/DeadFire/Maps/L_MainMenu`, `GameInstanceClass=/Game/DeadFire/Blueprints/BP_DFGameInstance.BP_DFGameInstance_C`; `EditorStartupMap` unchanged. The headless runner and PIE pick the GameInstance up from the config (the editor is restarted once after the change).
- The apply runner: `component_defaults`, the SoundMix asset, `input_action` flags; `df_verify_blueprints.py` unchanged.
- README (current state, controls: P pauses, where-the-logic-lives rows for the GameInstance, SaveGame, menu GameMode and controller, vehicle children, Switchback GameMode, widgets; tests paragraph), playtest checklist lines for the menus, vehicles, second track, pause, settings and unlocks; base design §6 rows and §7 row `5 — Menus & meta (done <date>)`; this phase's plan with its execution record; the memory file.
- Hooks for Phase 6: `RecordResult` is where a leaderboard would hang; `GetNPCCountFor` is the difficulty seam; `LEVEL_LAYOUTS` and `LEVELS` take a third track by adding a row.

## 10. Phase 5 acceptance

- `tools/run_tests.ps1` green with the `FT_DFMenu_*` tests and the existing 56; `df_verify_blueprints.py` `VERIFY PASSED`; the generator reports no overlaps.
- In the editor, opening `L_MainMenu` and pressing Play: the title and three buttons over the car showcase; PLAY → the car page, `<` `>` move the camera between the three cars and the stats change; BRUTE and VIPER read LOCKED with the unlock hint and NEXT greyed; SEDAN → NEXT → PROVING GROUND with its rules and `NOT RACED YET`; SWITCHBACK locked; RACE → fade to black → the race starts in the Sedan with the NORMAL three rivals.
- Racing: P pauses (world frozen, cursor, four buttons); RESUME continues; RESTART restarts; MAIN MENU returns to the car page. Finishing with 300+ in first place shows `NEW CAR UNLOCKED: BRUTE   NEXT TRACK UNLOCKED: SWITCHBACK` and a NEXT button; NEXT loads SWITCHBACK (five gates, four rivals, 150 s clock); MENU returns to the car page where BRUTE is now open; choosing BRUTE and racing: the car is grey, reads `CAR 160 / 160`, pulls away slower and will not pass 120 km/h.
- Quitting the editor and playing again: the unlocks and best scores are still there (`Saved/SaveGames/DeadFire.sav`); SETTINGS → RESET PROGRESS locks them again; MASTER VOLUME at 0 silences the explosions; HARD → five rivals on PROVING GROUND.

## 11. Left to the builder

The SWITCHBACK point list and prop positions; plinth and camera placement in the menu level; widget fonts, sizes and panel widths; the exact Select-chain shape of the catalogue functions; the string format of the stat bars beyond `[###--]`; log line wording (`DF: progress saved ...`, `DF: unlocked ...`); how `ShowPage` keeps the showcase camera when returning from settings; test world set-up details; the order of the new generator modules.
