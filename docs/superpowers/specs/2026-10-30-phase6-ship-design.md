# Dead Fire — Phase 6 (Test & Ship) Design Addendum

Date: 2026-10-30
Extends: `2026-10-20-dead-fire-design.md` (§2 goals, §4 rules, §7 phase table, §9 risks), `2026-10-21-phase2-race-flow-design.md` (§7 race tunables, §11 deferred follow-ups), `2026-10-30-phase3-items-design.md` (§8 item tunables), `2026-10-30-phase4-ai-design.md` (§6 AI tunables, §4.1 spawning), `2026-10-30-phase5-menus-design.md` (§2.3 difficulty, §4 progress, §5 menus). Only what Phase 6 needs is added; nothing earlier changes unless stated.
Status: the project manager asked for the next phase to start, as for Phases 3, 4 and 5, without a question round. Every decision below that the proposal and the earlier designs do not settle is an implementer's call, marked **[call]**; the team can overturn any of them in the generator modules (`tools/bpgen/graphs/`), the tables in `tools/bpgen/df.py`, the packaging script, or an Instance Editable value. A fresh builder check raised four points; all were settled from the project's own files or as implementer's calls, marked **[call, from the builder check]**.

## 1. What Phase 6 delivers

Base design §7: "Bug fixing, balance (score, items), packaged Windows build, presentation" (proposal weeks 12–13). Base design §2: "Ship a playable build by week 13." Concretely:

1. **A packaged Windows build** of the game, produced by one script (`tools/package_game.ps1`), that starts in the main menu, runs the whole flow (menus → race → summary → unlocks → settings) without the editor, and is smoke-tested by the same script. Two configurations: **Development** (the team's test build: console, log file) and **Shipping** (the hand-in).
2. **The project opens and packages on any team machine**: the editor-only plugins are declared editor-only and the authoring plugin optional, so a stock UE 4.27.2 install opens the project with no prompt and the game target never needs them.
3. **A balance pass with evidence**: a simulation tool measures the NPC pace, race length and wreck rate on both tracks; the race clock and checkpoint bonus are set from those numbers so a race lasts about three minutes; difficulty now also changes how fast the rivals drive and how often they get items.
4. **Bug fixes**: the seven review minors the Phase 5 ledger deferred (five fixed here, two left as they are; the reviewer's other three minors were already settled as rulings in that ledger), race end with no player, the one Blueprint runtime error found in today's editor logs, the unbuilt-lighting banner, the save-file warning on first run, and the two cook warnings, so the shipped build cooks and starts clean.
5. **Presentation material**: a demo run-of-show, a slide outline with speaker notes, a screenshot set taken from the packaged build and the editor, and a draft slide deck the team restyles.
6. **Final regression**: every functional test green (70 plus the new ones), the manifests verified, both packaged configurations booted, README, playtest checklist, base design row and the memory updated.

Out of scope **[call]**: new gameplay, art or audio; a custom icon or splash (the engine defaults stay); code signing; other platforms; an installer (the build is a zip); a trailer video; leaderboards. The playtest checklist is walked by a person, not by the agent.

## 2. Packaging

### 2.1 The script: `tools/package_game.ps1`

```powershell
.\tools\package_game.ps1                    # Development build into Builds\DeadFire-v1.0.0-Win64-Development-<yyyymmdd>-<hash>\ (+ .zip), then the smoke test
.\tools\package_game.ps1 -Config Shipping   # the hand-in build
.\tools\package_game.ps1 -NoSmoke -NoZip    # cook, stage, archive only
```

- It runs the engine's `AutomationTool.exe` **directly, by full path, with the working directory set to `Engine\Binaries\DotNET`**, never `RunUAT.bat`. Reason (found today): this machine's `RunUAT.bat` falls back to running `AutomationTool.exe` by bare name from its own folder (the installed engine has no `AutomationToolLauncher.exe`), and that lookup fails under `NoDefaultCurrentDirectoryInExePath=1`, which the agent's shell sets and which the editor inherits when the agent's `restart_editor.ps1` starts it. The editor's own **Launch** and **Package Project** buttons fail the same way from such an editor (`'AutomationTool.exe' is not recognized ... BUILD FAILED`, 2026-10-30 20:34), and so did the earlier plugin build attempts through UAT. An editor started from the Epic launcher does not have the variable and packages normally; the script works either way. **[call]**
- Command (the one that succeeded in today's trial, 2 min 40 s, 318 MB staged, 49 MB pak): `BuildCookRun -nop4 -project="<uproject>" -cook -stage -archive -archivedirectory="<Builds\...>" -package -ue4exe=UE4Editor-Cmd.exe -pak -prereqs -nodebuginfo -targetplatform=Win64 -build -clientconfig=<Config> -utf8output -nocompile -nocompileeditor -map=/Game/DeadFire/Maps/L_MainMenu+/Game/DeadFire/Maps/L_TestTrack+/Game/DeadFire/Maps/L_Switchback`. It may run while the editor is open (the cook is a separate `UE4Editor-Cmd` process), but not while a headless test suite runs (file locks, the Phase 5 rule).
- Output folder name: `DeadFire-v<ProjectVersion>-Win64-<Config>-<yyyymmdd>-<short hash>` under `Builds/` (git-ignored; `.gitignore` gains `Builds/`). The UAT output folder `WindowsNoEditor` is renamed to that name; the zip has the same name. When `git status --porcelain` lists anything, the hash gets `-dirty`, so a build from an uncommitted tree never names a commit it was not made from. The builds made during this phase are verification builds; the hand-in zips are made by re-running the script for both configurations after the project manager's commit. A `v1.0.0` tag is suggested, not created. **[call, from the builder check]** The executable stays `comp4900sef.exe` (a content-only project's game is named after its `.uproject`; renaming the project is not worth the churn in week 13) **[call]**; the window title is `Dead Fire` from `ProjectDisplayedTitle`.
- The script writes `README.txt` into the folder from `tools/package/README.template.txt`: title, version, commit, date, configuration, how to run (double-click `comp4900sef.exe`; the first run installs the UE4 prerequisites), the controls table (from the README; Escape pauses in the packaged game), where the save lives (`comp4900sef/Saved/SaveGames/DeadFire.sav` next to the exe), known issues, and the team. **[call]**
- `-Config Development` is the default **[call]**: it keeps the console (`` ` ``: `ke * RestartRace`, `ke * EndRace 1`) and writes `comp4900sef/Saved/Logs/comp4900sef.log`, which the test week needs for bug reports; Shipping has neither (logging is compiled out of Shipping for a content-only project). Both are built once for the release.

### 2.2 Smoke test (inside the script, unless `-NoSmoke`)

Launches the packaged exe with `-windowed -resx=1280 -resy=720 -nosplash` (plus `-log` for Development), waits up to 60 s, takes a screen capture into the build folder (`smoke.png`), then closes the process. Pass criteria **[call]**:
- Development: the log contains `Bringing World /Game/DeadFire/Maps/L_MainMenu` and `DF: progress loaded from slot DeadFire`, and no line matching `LogScript:`, `Blueprint Runtime Error`, `LogBlueprint: Error`, `Fatal error`, or `LogStreaming: Warning: Failed to read file` (the save warning §5.7 removes).
- Shipping: the process is still alive after 20 s and `smoke.png` exists; the person looks at the image.
- Either: the script exits non-zero on failure and prints the offending lines.

### 2.3 Project settings for shipping

- `Config/DefaultGame.ini`: `[/Script/EngineSettings.GeneralProjectSettings] ProjectVersion=1.0.0` **[call]**, `CompanyName=COMP 4900SEF Group 3`, `Description` as in the uproject; `[/Script/UnrealEd.ProjectPackagingSettings]`: `BuildConfiguration=PPBC_Development`, `bUsePakFile=True`, `bCookAll=False`, `bIncludePrerequisites=True`, `+MapsToCook=(FilePath="/Game/DeadFire/Maps/L_MainMenu")`, `L_TestTrack`, `L_Switchback`, `+DirectoriesToNeverCook=(Path="/Game/DeadFire/Tests")`. The functional-test level, the test actors and `BP_DFTestGameMode` never ship; nothing shipped references them (the test GameMode is set only on the test level). The editor's own Package button then does the same thing as the script when it works.
- `comp4900sef.uproject` plugin references: `DFBlueprintAuthoring` gets `"Optional": true` and `"WhitelistTargets": ["Editor"]` (a stock editor without the plugin opens the project silently; the game target never looks for it); `PythonScriptPlugin` and `EditorScriptingUtilities` get `"WhitelistTargets": ["Editor"]` (the Python plugin has a `Runtime` preload module that the shipped game does not need). `PhysXVehicles` is unchanged. **[call]** The headless tests and the cook run the Editor target, so nothing changes for the pipeline.
- `Config/DefaultInput.ini`: `+ActionMappings=(ActionName="ResetVR", Key=F10)` **[call]**, which removes the two cook warnings `InputAction Event references unknown Action 'ResetVR'` from the template pawns (the node resets an HMD; without one it does nothing). The template's own binding was `R`, which Dead Fire uses for `NextItem`.
- `Content/VehicleBP/Blueprints/VehicleHUD.uasset` is restored from the engine's vehicle template (`D:\UE_4.27\Templates\TP_VehicleBP\Content\VehicleBP\Blueprints\VehicleHUD.uasset`) and committed **[call]**: the Sedan template Blueprint, and so `BP_DFVehicle`, reference it from the in-car HUD logic, and its absence is the other cook warning (`Failed to load '/Game/VehicleBP/Blueprints/VehicleHUD': Can't find file`, seven times). Restoring the asset is the only fix that does not edit a template Blueprint.
- Acceptance for the cook: the UAT log of a release build has no `Warning:` line from `LogUObjectGlobals` or `LogBlueprint` (§2.3 removes all nine seen today).

## 3. Balance

### 3.1 Why

Base design §4 set the clock at 120 s with +8 s per gate. PROVING GROUND is 491 m with four gates; a driver who keeps NPC pace (45–60 km/h today) laps in roughly 30–35 s and earns +32 s per lap, so the clock barely moves and a competent race never ends by time; a fast driver gains time every lap. Base design §2 wants a race that is "fun in 5 minutes" and the proposal's loop ends "when the time limit expires". Phase 5 §2.3 deferred NPC speed and item supply to this phase.

### 3.2 The simulation tool

`tools/balance_sim.py <map> [--seconds N] [--difficulty 0|1|2]` (host side; it drives the open editor through `tools/ue_remote.py`) and `comp4900sef/Script/df_balance_sim.py` (editor side): opens the map, sets the difficulty on the GameInstance's save slot `DeadFireBalance` **[call]** (so the developer's progress is untouched), starts **Simulate** (`editor_play_simulate`: the GameMode spawns and drives the NPCs, the clock runs, items are handed out and used; there is no player), samples every 5 s each racer's `LapsCompleted`, `Score`, `Kills`, `Deaths`, `DistanceAlongTrack`, the GameState's `RemainingTime` and `bRaceActive`, ends the simulation when the race ends or at `--seconds`, and prints one table per run: per NPC laps, best lap time (from the sampled lap-completion times), average speed, kills, deaths; and for the field the median lap time **P** and wrecks per NPC. There is no player in a simulation, and only the player's gates add time, so the clock runs down in exactly `C` seconds; the race length a driver at pace would get is **computed** from P and the bonus (`laps = C / (P − G × bonus)`, length `= laps × P`) and printed with the table. The difficulty for a run comes from a save written into the `DeadFireBalance` slot before play and pointed at through the GameMode's `SaveSlotOverride` on its class defaults for the duration of the run, so the real code path (`ApplyGameInstanceSettings`) applies it and the developer's `DeadFire.sav` is never read or written. Results of the runs used for the numbers below go into `docs/superpowers/balance-2026-10-30.md` (what was measured, what was changed, what the follow-up run showed). **[call]**

### 3.3 Rules derived from the measurements **[call]**

Let **P** be the median NPC lap time at NORMAL on a track, **G** its gates, **C** its clock.

- **Target race length**: a driver at NPC pace runs out of clock after about `TargetLaps` laps: 6 on PROVING GROUND, 4 on SWITCHBACK (about three to three and a half minutes either way). `CheckpointTimeBonus = round to 0.5 s of (TargetLaps × P − C) / (TargetLaps × G)`, clamped to 2–8 s. The clock `C` stays 120 / 150 s. A faster human gains a little time per lap and plays longer; a slower one runs out sooner; neither races for ever.
- **Pass score** stays 300 / 400 unless `TargetLaps × 100 < requirement` after the measurement (then it drops to `TargetLaps × 100`): the requirement must be reachable at pace by laps alone, with kills as the margin.
- **NPC pace**: the AI driving defaults (Phase 4 §6) do not change unless the simulation shows NPCs failing to finish laps (stuck or flipped for more than 10 % of the race); speed moves through the difficulty seam below.
- **Wreck rate**: at NORMAL the field averages at most one wreck per NPC per race. A simulated race lasts only `C`, shorter than the tuned race, so the tool measures wrecks per NPC per minute and scales the rate to the computed race length **[call, from the builder check]**; if that shows more than one, `AIItemInterval` rises to 25 s (then 30 s). Nothing else about items changes (Phase 3 §8 holds; the team tunes feel by hand).
- **Where the numbers live**: `LEVELS` in `df.py` gains `bonus` (checkpoint time bonus, s); the per-level GameMode defaults come from the row (`BP_DFRaceGameMode` itself for PROVING GROUND, `BP_DFSwitchbackGameMode` for SWITCHBACK). `BP_DFTestGameMode` pins `CheckpointTimeBonus` 8 so the Phase 2 tests' arithmetic (+8 s) stays as written.

### 3.4 Difficulty: rivals, speed, items **[call]**

One table, `DIFFICULTIES` in `df.py`, replaces `DIFFICULTY_NAMES` / `DIFFICULTY_DELTA`:

| Index | Name | Rival delta | NPC speed scale | NPC item interval scale |
|---|---|---|---|---|
| 0 | EASY | −1 | 0.85 | 1.5 |
| 1 | NORMAL | 0 | 1.0 | 1.0 |
| 2 | HARD | +2 | 1.1 | 0.6 |

- `BP_DFGameInstance.GetDifficultyInfo(Difficulty) -> Name, RivalDelta, SpeedScale, ItemIntervalScale` (pure, `Select` chain like the catalogues); `GetDifficultyName` and `GetNPCCountFor` read it.
- `BP_DFRaceGameMode` gains `NPCSpeedScale` (float 1, `Dead Fire|AI`, Instance Editable). `SpawnNPCs` multiplies each NPC's `SpeedScale` (`1 − Random(0, NPCSkillSpread)`) by it. `ApplyGameInstanceSettings` (Begin Play, once) sets `NPCSpeedScale` from the difficulty and multiplies `AIItemInterval` by the item scale, beside the rival count it already applies. The test GameMode is unaffected in practice (no NPCs; its tests set what they need).
- The settings page's hint becomes `EASY: 2 slower rivals   NORMAL: 3   HARD: 5 faster, better armed` (PROVING GROUND numbers) **[call]**.
- On HARD the fastest rival's straight-line target is 110 × 1.1 = 121 km/h, one above the BRUTE's 120 km/h limiter. This is accepted: the BRUTE is the armour pick and HARD is meant to out-pace it on long straights; the balance runs show whether rivals reach that speed at all. **[call, from the builder check]**

## 4. Bug fixes and robustness

Each item names where it came from.

1. **Pause menu → MAIN MENU** (Phase 5 review minor): goes through `BP_DFPlayerController.TogglePause` (widget removed, cursor and input mode restored) before `OpenMainMenu`, as RESTART already does; the raw `SetGamePaused(false)` goes.
2. **`EndRace` closes an open pause menu** (Phase 5 review minor): when the game is paused at race end, the player controller's `TogglePause` runs first (it removes the widget and unpauses), instead of the bare unpause; the summary then owns the screen.
3. **Volume slider saves on release** (Phase 5 review minor): `BP_DFGameInstance.PreviewMasterVolume(Volume)` applies the mix without saving; the slider's `OnValueChanged` calls it and updates the label; `OnMouseCaptureEnd` (and the page's BACK) call `SetMasterVolume(slider value)`, which saves once. `SetMasterVolume` keeps its meaning (the tests use it).
4. **Unknown vehicle class falls back** (Phase 5 review minor): `RefreshPlayerVehicleClass` checks `IsValidClass` on the catalogue's class before using it; an invalid class gives `BP_DFVehicle`.
5. **The racer tick skips dead controllers** (runtime error in today's 08:31 editor log: `Attempted to access BP_DFVehicleAIController_C_2 via property C, but ... is pending kill` in `BP_DFRaceGameMode:TickRacer`): the Tick loop over `RacerControllers` tests `IsValid` on each element before `TickRacer` and the respawn check, so a controller destroyed mid-frame can never raise a runtime error.
6. **`RecordResult` with no save object** (Phase 5 review minor): an `IsValid(Save)` branch guards the function before any array read (Blueprint `AND` does not short-circuit).
7. **No warning on first run** (packaged log today: `LogStreaming: Warning: Failed to read file '.../DeadFire.sav'`): `LoadProgress` calls `DoesSaveGameExist` first and only then `LoadGameFromSlot`; otherwise it creates the fresh save as before.
8. **No "LIGHTING NEEDS TO BE REBUILT" banner** (seen in the packaged main menu and every PIE screenshot since Phase 2): the level builder sets every light it spawns (`DirectionalLight`, `SkyLight`) to **Movable** in all four generated levels, so no lightmap build is ever needed and the banner has nothing to report; the levels are rebuilt and saved. **[call]** (Building lighting would be undone by the next level rebuild.)
9. **Clean cook** (§2.3): the `VehicleHUD` asset and the `ResetVR` mapping.
10. **Checklist hints verified**: `ke * RestartRace` and `ke * EndRace 1` are tried in the Development build's console (or PIE through Python) and the checklist says what they do.
11. **Race end with no player** (builder check): `EndRace` reads `GetPlayerController(0)` and uses it for the place, input and summary without a check, so a race with no player (Simulate, which the balance tool uses) raises errors at its end. An `IsValid(Player)` branch skips the player-only steps; with a player nothing changes. **[call, from the builder check]**

Deferred review minors that stay as they are **[call]**: the comment about `RefreshPlayerVehicleClass` running before `ApplyGameInstanceSettings` at the first spawn (a comment in `game_mode.py`, nothing else); `__pycache__` (already ignored in `5cdd1cd`).

## 5. Presentation (`docs/presentation/`) **[call]**

- `demo-script.md`: a six-to-eight-minute run-of-show on the packaged Development build: main menu and footer → car page (stats, the locked BRUTE) → track page → PROVING GROUND race (rivals, `POS`, a gate, the item row after a crate on foot, a rocket at the target car, a shortcut rock) → P pause → finish first with 300+ (console `ke * EndRace 1` once the score is there, if the race would run long) → the unlock line → NEXT to SWITCHBACK → MENU → BRUTE races grey → SETTINGS (HARD, volume, reset). Each step names what to say and what the audience should notice; a fallback for every step that can go wrong (a wreck, a slow rocket).
- `slides-outline.md`: 12–15 slides mapped to the proposal's sections (pitch, the three ideas, core loop and flowchart, architecture and the Blueprint pipeline, the race rules and balance evidence, AI, menus and meta, testing — 70+ functional tests, the headless runner, the smoke test — the packaged build, challenges and what the team would do next), each with bullets, speaker notes and the screenshot it uses.
- `screenshots/`: taken from the packaged build and the editor at 1920×1080: main menu, car page (BRUTE), track page, settings, race start with the grid and `POS 1 / 4`, mid-race with NPCs, on foot beside a crate with the item row, an explosion or wreck, the pause menu (if a key reaches the game; else the functional-test capture), the summary with the unlock line, SWITCHBACK from above.
- `DeadFire-Final.pptx`: a draft deck generated from the outline and the screenshots, plain styling, for the team to restyle in their template.

## 6. Rules summary (tunables; owner in brackets)

| Rule | Value |
|---|---|
| Packaged configurations [package_game.ps1] | Development (default) and Shipping |
| Maps cooked / never cooked [DefaultGame.ini] | `L_MainMenu`, `L_TestTrack`, `L_Switchback` / `/Game/DeadFire/Tests` |
| Project version [DefaultGame.ini] | 1.0.0 |
| Smoke-test window / wait [package_game.ps1] | 1280×720 windowed / 60 s (Development log lines), 20 s alive (Shipping) |
| Target race length at NPC pace [LEVELS] | 6 laps on PROVING GROUND, 4 on SWITCHBACK |
| Checkpoint bonus [LEVELS `bonus`, GameMode defaults] | from §3.3, 2–8 s (test GameMode pins 8) |
| Clock / pass score [LEVELS] | 120 s / 300; 150 s / 400 (pass may drop per §3.3) |
| Difficulty: rival delta / speed scale / item interval scale [DIFFICULTIES] | EASY −1 / 0.85 / 1.5; NORMAL 0 / 1 / 1; HARD +2 / 1.1 / 0.6 |
| Wreck-rate ceiling at NORMAL [balance] | 1 per NPC per race, else `AIItemInterval` 25 s then 30 s |
| Balance save slot [balance_sim] | `DeadFireBalance` |
| Lights in generated levels [level builder] | Movable |
| `ResetVR` mapping [DefaultInput.ini] | F10 |

## 7. Tests (`tools/bpgen/graphs/tests_ship.py`, `FT_DFShip_*`)

Same shape and world as the earlier test modules (test GameMode, `DeadFireTest` slot, `fresh_progress` at both ends of a progress test, `RestartRace` to leave the world as found). The functional-test framework fails a test on any `Error` log line raised while it runs, which is how the two runtime-error fixes are observed red first.

- `EndRaceClosesPauseMenu`: `race_context`; `TogglePause` → paused, one `WBP_DFPauseMenu` on screen; `EndRace(TimeUp)` → not paused, no pause widget; `TogglePause` → still not paused; `RestartRace`.
- `VolumePreviewDoesNotSave`: `fresh_progress`; `PreviewMasterVolume(0.4)` → `Save.MasterVolume` 1.0; `SetMasterVolume(0.4)` → 0.4; `fresh_progress`.
- `TickSkipsDeadControllers`: `race_context`; add a `None` element to the GameMode's `RacerControllers`; `Delay 1.0` (several ticks); remove it (`Array_Remove` of the last index); the race is still active. Red before the fix (the loop raises `Accessed None` errors), green after.
- `RecordResultWithoutSave`: `fresh_progress`; set the GameInstance's `Save` to `None`; `RecordResult(0, 100, 1, true)` → `UnlockedVehicle` −1, `bUnlockedLevel` false; `LoadProgress` → `Save` valid, vehicle 0 unlocked; `fresh_progress`. Red before the fix.
- `FreshSlotLoadsCleanly`: `UseSaveSlot("DeadFireFresh")` (the slot is deleted first with `DeleteGameInSlot`) → `Save` valid, `IsVehicleUnlocked(0)` true, `(1)` false, `DoesSaveGameExist` false until `SaveProgress`; `UseSaveSlot("DeadFireTest")`, `DeleteGameInSlot("DeadFireFresh")`, `fresh_progress`.
- `DifficultyInfo`: `GetDifficultyInfo(0)` → EASY, −1, 0.85, 1.5; `(2)` → HARD, 2, 1.1, 0.6; `(7)` → NORMAL (out of range falls to index 1); `GetNPCCountFor(3)` on HARD → 5 as before.
- `NPCSpeedScaleApplied`: `race_context`; GameMode `NPCSpeedScale` 1.1; `SpawnNPCs(1)` → the one AI controller's `SpeedScale` is within [0.99, 1.1]; `DespawnNPCs`; `NPCSpeedScale` back to 1.
- `RefreshKeepsAValidClass`: `RefreshPlayerVehicleClass` → `PlayerVehicleClass` is a valid class (`IsValidClass`) and `DefaultPawnClass` equals it.
- The level builder's Movable lights, the GameMode defaults from `LEVELS` (`CheckpointTimeBonus`, `RaceTimeLimit`, `ScoreRequirement`), the `.uproject` plugin fields and the packaging settings are checked by editor Python in the plan (class defaults and actor mobility read back), not by functional tests.
- The existing 70 tests pass unchanged (the test GameMode pins the bonus at 8 and spawns no NPCs; the difficulty table keeps NORMAL at 0 / 1 / 1).

## 8. Docs, config, hooks

- README: "Current state" becomes Phase 6 (what shipped, where the build is, how to run it, the balance numbers), a **Play the packaged build** section, a **Package it yourself** section (the script, the direct-UAT reason, the `NoDefaultCurrentDirectoryInExePath` note), the settings table gains `NPCSpeedScale`, the tests paragraph gains the ship group, the tables gain the `DIFFICULTIES` row; the playtest checklist gains Phase 6 lines (the packaged build starts in the menu, Escape pauses, the display toggle, QUIT, difficulty changes rival speed, a race ends by time in about three minutes at pace, no lighting banner, the console hints); base design §7 row `6 — Test & ship (done <date>)` and §9 gains the packaging risk line; this phase's plan with its execution record; `docs/superpowers/balance-2026-10-30.md`; the memory files (the UAT finding above all).
- After Phase 6 there is no next phase: the hand-off is the zip, the repo at the release commit, and the presentation folder. Hooks that remain for the team: `GetDifficultyInfo` for any further difficulty knob; `LEVELS` rows for a third track; `tools/balance_sim.py` for any re-tune.

## 9. Phase 6 acceptance

- `tools/package_game.ps1` (Development) and `-Config Shipping` both end with `BUILD SUCCESSFUL`, a cook log free of `LogUObjectGlobals` / `LogBlueprint` warnings, a `Builds/DeadFire-v1.0.0-Win64-<Config>-...` folder and zip with `README.txt`, and a passing smoke test whose `smoke.png` shows the main menu with no lighting banner.
- On a stock UE 4.27.2 editor without the authoring plugin the project opens with no plugin prompt (checked by temporarily renaming the installed plugin folder, opening the project headless with `UE4Editor-Cmd -run=...` or the GUI, and restoring it).
- `tools/run_tests.ps1` green with the `FT_DFShip_*` tests and the existing 70; `df_verify_blueprints.py` `VERIFY PASSED`; the generator reports no overlaps.
- `docs/superpowers/balance-2026-10-30.md` holds the before and after simulation tables for both tracks at NORMAL and the HARD/EASY check, and the values in `LEVELS` / `DIFFICULTIES` match it; the race length computed from the measured NORMAL lap time and the chosen bonus is between 2.5 and 4 minutes on both tracks.
- In the packaged Development build (by a person, checklist lines): the menu flow, a race that ends by time, P / Escape pause, the summary's unlock, SWITCHBACK, BRUTE, settings including the display toggle, QUIT; the save survives a relaunch.
- `docs/presentation/` holds the demo script, the slide outline, at least ten screenshots and the draft deck.

## 10. Left to the builder

The sampling details and output format of the balance tool; the exact smoke-test polling; the `README.txt` wording; the zip tool (`Compress-Archive`); the order of the new generator module; the screenshot composition and the deck's look; how the pause-menu screenshot is obtained if keys still do not reach the game window (the functional-test capture is the fallback); the wording of the checklist lines.
