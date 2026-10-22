# Dead Fire (死火) — COMP 4900SEF Group 3

An action-racing hybrid built in **Unreal Engine 4.27.2**: race laps on a looped track, blow up rival cars, and get out of the car on foot to find items and shortcuts. See the proposal for the pitch, `docs/superpowers/specs/2026-10-20-dead-fire-design.md` for the design and phase plan, and `docs/superpowers/specs/2026-10-21-phase2-race-flow-design.md` for the race rules.

The game is **Blueprint-only**: open the project in the stock editor, no Visual Studio needed. Driving, cameras and on-foot movement come from the engine's Vehicle and Third Person Blueprint templates; all Dead Fire logic lives in `BP_DF*` Blueprints on top of them. (Phases 1–2 were first built in C++; the Blueprint migration replaced that on 2026-10-22, see `docs/superpowers/plans/2026-10-21-blueprint-migration.md`.)

## Current state: Phase 2 race flow, in Blueprint

- Drive a Sedan around `L_TestTrack` (W/S/A/D, Space handbrake, Tab in-car camera).
- Stop and press **E** to get out as the mannequin; walk/run/jump, mouse look, **left mouse** fires a hitscan weapon. Press **E** next to the car to get back in.
- Four checkpoint gates on the loop, index 0 on the start line. Only the next gate counts (driving backwards or skipping gates credits nothing); each gate adds **+8 s** to the 120 s clock, and crossing the start line completes a lap (**+100**).
- Three lives. A wrecked car (driven or parked) or a killed character costs a life; 2 s later the player is back in a car at the last gate (a fresh one if theirs was wrecked) with the character revived and inside. The third death ends the race (game over).
- Off-track timer: driving more than 5 m beyond the edge of every road for 5 s puts the car back at the last gate without costing a life. On foot the timer never runs.
- Race end (clock at 0 or no lives left): input stops and a summary shows the outcome (`RACE COMPLETE` at 300 points or more, `TIME UP`, `GAME OVER`), place, score, laps, kills and deaths, with **Retry** and **Quit**.
- UMG HUD: score, laps, kills, lives, clock, speed and gear, car or character health and tires, crosshair on foot, enter/exit prompts, and warnings (`RETURN TO TRACK` countdown, `WRECKED`, `YOU DIED`, `CHECKPOINT  +8 s`).

Phases 3–6 (items and damage, AI racers, menus, shipping) are described in the design document.

## Open and play

1. Install **Unreal Engine 4.27.2** from the Epic Games Launcher.
2. Open `comp4900sef/comp4900sef.uproject`. The editor opens `L_TestTrack`.
3. Press **Play**.

The Starter Content pack is git-ignored and re-added automatically on first open. Committed free content: the engine's template packs (`Content/Vehicle`, `Content/Mannequin`, `Content/Geometry`, `Content/VehicleAdv`) and the two template Blueprints the game builds on (`Content/VehicleBP/Sedan`, `Content/ThirdPersonBP/Blueprints/ThirdPersonCharacter`; do not edit these, change the `BP_DF*` children instead).

## Controls

| Action | Keyboard / mouse | Gamepad |
|---|---|---|
| Drive / move | W A S D, arrows | Left stick, triggers |
| Handbrake (car) / Jump (on foot) | Space | Left shoulder / A |
| Enter / exit vehicle | E | Y |
| Fire | Left mouse | Right trigger |
| Switch camera (car) | Tab | View |
| Look | Mouse | Right stick |

## Where the logic lives

| Asset (under `/Game/DeadFire/`) | Parent | What it does | Owner |
|---|---|---|---|
| `Blueprints/BP_DFVehicle` | Sedan (Vehicle template) | Body and tire health, damage routing, wrecking, enter/exit, teleport, blown-tire throttle cap | Fung Ming Chu, Chong Tsz Ho |
| `Blueprints/BP_DFCharacter` | ThirdPersonCharacter | Enter vehicle, fire, health, death and revive, riding inside a car | Cheung Tsz Hin Anderson |
| `Components/BPC_DFWeapon` | ActorComponent | Hitscan weapon: damage 20, range 80 m, cooldown 0.15 s | Cheung Tsz Hin Anderson |
| `Blueprints/BP_DFPlayerController`, `Components/BPC_DFRacer` | PlayerController, ActorComponent | Possession; per-racer score, laps, kills, deaths, gates, off-track time | Lee Chun Yin, Choy Tsz Lok |
| `Blueprints/BP_DFRaceGameMode`, `BP_DFRaceGameState` | GameModeBase, GameStateBase | Every race rule: clock, gates, laps, kills, deaths, respawn, off-track, ranking, race end, `RestartRace` | Choy Tsz Lok |
| `Blueprints/BP_DFTrackSpline` | Actor | Closed spline; its construction script lays the road; progress and off-road queries | Lau Chun Kit |
| `Blueprints/BP_DFCheckpoint` | Actor | Gate: trigger across the road, two poles, respawn point | Lau Chun Kit |
| `Blueprints/BP_DFHUD`, `UI/WBP_DFRaceHUD`, `UI/WBP_DFRaceSummary` | HUD, UserWidget | In-race HUD and end-of-race summary | Lee Chun Yin |
| `Data/S_DFTireState`, `S_DFRaceResult`, `E_DFRaceEndReason` | struct, enum | Shared data | Choy Tsz Lok |
| `Maps/L_TestTrack`, `Tests/L_DF_FunctionalTests`, `Tests/FT_DF*` | | Playable test level; functional tests | Lau Chun Kit, Lee Chun Yin |

Tunables are variables marked **Instance Editable** in `Dead Fire|...` categories (for example `Dead Fire|Race` on `BP_DFRaceGameMode`: `RaceTimeLimit`, `CheckpointTimeBonus`, `PointsPerLap`, `PointsPerKill`, `MaxDeaths`, `ScoreRequirement`, `RespawnDelay`, `OffTrackMargin`, `OffTrackGraceSeconds`). Hooks for effects and later phases are **event dispatchers**: `OnVehicleDamaged`, `OnTireBlown`, `OnVehicleDestroyed`, `OnOccupantEntered/Exited`, `OnCharacterDamaged/Died/Revived`, `OnEnteredVehicle/ExitedVehicle`, `OnFired`, `OnRaceEnded`, `OnRacerRespawned`. The GameMode writes `DF: ...` lines to the output log for deaths, wrecks, respawns, restarts and race ends.

## How the Blueprints are built

The Blueprint graphs are **generated**, so they can be reviewed as code and rebuilt identically:

- `tools/bpgen/graphs/*.py` describe each Blueprint (variables, functions, dispatchers, components, widget layout, graphs) in Python; `tools/bpgen/bpgen.py` is the node library and `tools/bpgen/df.py` the shared Dead Fire names and recipes.
- `python -I tools/bpgen/generate_all.py` writes `comp4900sef/Script/paste/<Blueprint>/manifest.json` plus one `<Graph>.txt` per graph (the editor's own copy-paste format; these files also paste by hand with Ctrl+V).
- Inside the editor, `comp4900sef/Script/df_apply_blueprint.py` applies the manifests through the **DF Blueprint Authoring** editor plugin (`tools/DFBlueprintAuthoring`): creates the assets, variables, functions, dispatchers, components and widget trees, imports the graphs, links them, checks that every node, link and pin default arrived, compiles and saves.
- `comp4900sef/Script/df_build_test_track.py` builds `L_TestTrack` and `L_DF_FunctionalTests` (track, gates, props, lights, test actors).

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

## Tests

```powershell
.\tools\run_tests.ps1                                   # all functional tests, headless
.\tools\run_tests.ps1 -Filter "Project.Functional Tests./Game/DeadFire/Tests/L_DF_FunctionalTests.FT_DFRespawn"
```

The tests are Blueprint **Functional Tests** (`/Game/DeadFire/Tests/FT_DF*`, placed in `L_DF_FunctionalTests`): vehicle damage, tires, wrecking once; weapon hit and cooldown; character death and nearest-car search; enter/exit including blocked and moving cases; track length and road edges; gate order, laps, respawn at the last gate, the parked-wreck case, the death limit, nothing after the race ends, the off-track reset, time-up results, and the HUD/summary switch. All tests share one play session, so race tests start with `RestartRace`. In the editor: **Window → Developer Tools → Session Frontend → Automation**, filter `Functional Tests`. `FT_DFZZ_Screenshots` captures the HUD, on-foot and summary screens to `comp4900sef/Saved/Screenshots/Windows/` when run in the editor (black when headless). A test run started inside the editor can leave its play session open afterwards; press **Stop** (or run `unreal.EditorLevelLibrary.editor_end_play()`) before running the editor scripts, which refuse to work during play.

Engine warnings raised during tests (the Sedan physics asset logs `BoneIndex ... out of range of SpaceBases` once per freshly spawned car) are listed by `run_tests.ps1` but do not fail tests (`bTreatLogWarningsAsTestErrors=False`); failed assertions do.

The tests cannot press keys, so driving feel, cameras and the menus are checked by hand with `docs/superpowers/playtest-checklist.md`.

## Working together on Blueprint assets

`.uasset` files are binary and cannot be merged. Each Blueprint has one owner (table above); coordinate before touching someone else's, and pull before you start. If two people did change the same asset, keep one version and redo the other change by hand (or, for generated Blueprints, re-apply from the generator).

## Project layout

```
comp4900sef/Content/DeadFire/   Blueprints/, Components/, Data/, UI/, Maps/L_TestTrack, Tests/ (functional tests + test level)
comp4900sef/Content/VehicleBP/, ThirdPersonBP/   engine template Blueprints the game builds on (do not edit)
comp4900sef/Script/             editor Python: apply / verify Blueprints, build levels, conversion check; paste/ = generated manifests
tools/bpgen/                    Blueprint generators (graphs/*.py), library, engine signature lookup
tools/DFBlueprintAuthoring/     editor plugin source used by the apply script (built into the engine, not the project)
tools/                          run_tests.ps1, ue_remote.py, restart_editor.ps1, build_authoring_plugin.ps1
docs/superpowers/               design, phase plans, playtest checklist
```
