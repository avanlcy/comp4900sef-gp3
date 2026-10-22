# Dead Fire Blueprint Migration (Phase 2B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every graph-authoring step is automation (see Task 0); the only **(person)** step left is the Task 9 playtest.

**Goal:** Replace the C++ foundation of Phases 1–2 with a Blueprint-only project that has the same features: drive the Sedan on `L_TestTrack`, exit and re-enter on foot, shoot, ordered checkpoints and laps, lives and respawn, off-track timer, race end with summary, and a UMG HUD, pinned by Blueprint Functional Tests.

**Architecture:** The project becomes a Blueprint project built on the engine's Vehicle and Third Person Blueprint templates, which are copied in untouched; `BP_DFVehicle` and `BP_DFCharacter` are children of the template pawns and all Dead Fire logic lives in `BP_DF*` / `BPC_DF*` assets under `/Game/DeadFire/`. Graphs are **generated and applied by automation**: each Blueprint is described in Python under `tools/bpgen/graphs/` (variables, functions, dispatchers, graphs), `tools/bpgen/bpgen.py` emits a `manifest.json` plus the editor's clipboard text per graph under `comp4900sef/Script/paste/<Blueprint>/`, and the in-editor runner `comp4900sef/Script/df_apply_blueprint.py` applies a manifest through the **DF Blueprint Authoring** editor plugin (`tools/DFBlueprintAuthoring`, built into the local engine by `tools/build_authoring_plugin.ps1`; it exposes `unreal.DFBlueprintAuthoringLibrary` to Python: add variable / function / dispatcher / struct member / enum value, import nodes, connect pins, describe, compile). The project itself stays Blueprint-only; the plugin lives in the engine install of whoever runs the automation. The automation also converts the project, creates every asset with its parent class and components, sets defaults, builds the levels and widget layouts, and verifies the compiled classes. Each rule is pinned by a Blueprint Functional Test in `L_DF_FunctionalTests` whose graph is generated the same way, run headless by `tools/run_tests.ps1`.

**Tech Stack:** UE 4.27.2 (D:\UE_4.27), PhysXVehicles, classic input, UMG, Functional Testing framework (`FunctionalTest` actor), editor Python 3.7 through the `unreal-mcp-ue4` MCP server or `tools/ue_remote.py`.

**Spec:** `docs/superpowers/specs/2026-10-20-dead-fire-design.md` (§5–§9 as revised 2026-10-21) and `docs/superpowers/specs/2026-10-21-phase2-race-flow-design.md` (rules §2–§5, §7; HUD layout §6).

## Execution record (2026-10-22)

Executed end to end by the agent; every task is done except Task 9 Step 2 (the human playtest). Ledger with every ruling: `.superpowers/sdd/2026-10-21-blueprint-migration/progress.md` (git-ignored). Where the result differs from the task text below:

- **Asset creation** is done by `df_apply_blueprint.py` from the manifests (components, variables, defaults, class overrides, widget trees included); `df_create_blueprints.py` was deleted instead of rewritten, and so was `df_resave_test_track.py` (C++-era).
- **Verification** of each import is built into the runner: every node present, every written link present, no orphaned pin, every class/object default and every literal default as written (UE 4.27 drops `false`/`0` literals during reconstruction; the runner re-applies them). `df_verify_blueprints.py` checks variables, functions, dispatchers, components and a clean compile per manifest.
- **24 functional tests**, not 22: added `FT_DFRace_PlayerStartsInCar` (start-of-race smoke test) and `FT_DFZZ_Screenshots` (captures HUD, on-foot and summary screens in the editor); `FT_DFHUD_SummaryShownAtRaceEnd` also checks that `RestartRace` brings the HUD back.
- **Tests share one play session** (UE 4.27 only loads the map once for all tests of a map), so the GameMode gained `RestartRace` (clock, result, racer stats, pending respawn, player back in an intact car at the start, input and HUD restored) and every race test calls it first.
- **Engine warnings** no longer fail tests (`bTreatLogWarningsAsTestErrors=False`); `run_tests.ps1` lists them. The only one is the Sedan physics asset's first-pose `BoneIndex out of range` warning on each car spawn.
- **Track generation** moved from the construction script into a `RebuildTrack` function it calls (the editor forbids Add-Component nodes in the construction script graph itself), and cuts the road into ~10 m pieces like the C++ version, not one piece per spline point.
- **Summary input** focuses the Retry button (focusing the user widget logged an engine error and left keyboard/gamepad users without focus; a Phase 2 follow-up).
- The vehicle releases the latched handbrake on entering; the GameMode logs `DF: ...` lines for deaths, wrecks, respawns, restarts and race ends.
- **Plugin build**: UAT `BuildPlugin` does not run from this shell, so `tools/build_authoring_plugin.ps1` compiles the plugin inside a minimal C++ host project (default `%LOCALAPPDATA%\DFPluginHost`; keep the path short, UBT rejects output paths over 260 characters) and copies it to `D:\UE_4.27\Engine\Plugins\DeadFire\`.

## Global Constraints

- Engine `D:\UE_4.27`; project `comp4900sef/comp4900sef.uproject`. After Task 1 the project has **no `Modules` entry and no `Source/` folder**; nothing in this plan may add C++ back.
- Template Blueprints are copied with their original package paths (`/Game/VehicleBP/Sedan/Sedan`, `/Game/ThirdPersonBP/Blueprints/ThirdPersonCharacter`) and are **never edited**; all logic goes in children.
- Asset prefixes and folders: `BP_DF*` in `/Game/DeadFire/Blueprints/`, `BPC_DF*` in `Components/`, `S_DF*`/`E_DF*` in `Data/`, `WBP_DF*` in `UI/`, maps in `Maps/`, `FT_DF*` and `L_DF_FunctionalTests` in `Tests/`.
- Every tunable is a variable with **Instance Editable** on, category `Dead Fire|<Area>`; every hook listed in the spec is an **Event Dispatcher** with the spec's name. Function and variable names below are exact; graphs in other Blueprints call them by name.
- Spec values: body health 100; tire health 30; blown-tire speed scale 0.8; tire hit radius 60 cm; exit below 10 km/h; exit offsets side 220 / up 100 / behind 350 cm; character health 100; weapon damage 20, range 8000, cooldown 0.15 s; race time 120 s; checkpoint bonus +8 s; +100 per lap; +50 per kill; max deaths 3; score requirement 300; respawn delay 2 s; off-track margin 500 cm; off-track grace 5 s; checkpoint trigger half-extents (100, 1400, 250); pole offset 700; respawn height 50; checkpoint flash 1.5 s; road width 1400, thickness 20. Racers start with `NextCheckpointIndex = 1`; the start line (index 0) gives the lap **and** the time bonus.
- Automation entry points: MCP `manage_editor.run_python`, `manage_blueprint.{create_blueprint,add_component,set_blueprint_property,read}`, `manage_widget.*`, `manage_level.*`; no-MCP fallback `python tools/ue_remote.py --code "exec(open(r'<repo>/comp4900sef/Script/<script>.py').read())"` and `--console "<cmd>"`. UE 4.27 Python cannot create or read Blueprint variables, functions or graph nodes (verified 2026-10-21: `BPVariableDescription`, `EdGraphPinType`, `EdGraph` are not exposed and `Blueprint.new_variables` / `function_graphs` are not readable), so verification works on the **compiled class**: `cdo = unreal.get_default_object(unreal.load_asset(path).generated_class())`, `cdo.get_editor_property(name)` for variables and defaults, `cdo.call_method(fn, args)` on a spawned instance for functions, and the Functional Tests for behaviour.
- Generate and apply: `python -I tools/bpgen/graphs/<module>.py` writes `comp4900sef/Script/paste/<Blueprint>/manifest.json` (asset path, variables with type/default/category/editable, dispatchers, functions with inputs/outputs/pure, graphs with their text file and the pin links to make after import, e.g. to a function's `entry` node) and one `<Graph>.txt` per graph. `df_apply_blueprint.py` (run in the editor through `run_python` or `tools/ue_remote.py`, with the manifest folder as its argument) applies each manifest in order variables → dispatchers → functions → graphs (`ClearGraph`, `ImportNodes`, `ConnectPins`) → `Compile` → save, and fails loudly with the compiler messages if there is any error. Re-running is safe: creation calls are idempotent and graphs are cleared before re-import.
- Verification: `DescribeBlueprint` / `DescribeGraph` JSON from the plugin for structure, the compiled class for defaults (`unreal.get_default_object(...).get_editor_property`), `call_method` on a spawned instance for functions, Functional Tests for behaviour.
- Functional Tests: each `FT_DF*` is a Blueprint child of `FunctionalTest` (created and placed in `L_DF_FunctionalTests` by the automation), with a generated **Event Start Test** graph that asserts with the actor's `AssertTrue` / `AssertEqual_Int` / `AssertEqual_Float` functions and ends with `FinishTest(Succeeded|Failed)`. Run: `powershell -NoProfile -ExecutionPolicy Bypass -File tools/run_tests.ps1` (default filter `Project.Functional Tests` after Task 1); green is exit code 0 and `N passed, 0 failed, N found` with `N` equal to the number of placed tests.
- Every applied Blueprint is compiled and saved by the runner; a task is done only when `df_apply_blueprint.py` reports no compiler errors for every manifest it applied.
- Do not commit until Task 9; the user commits on request. Leave the working tree ready and list the commit command in the final report.

## Review Focus

1. Exiting the car next to a wall: the character must never be placed inside geometry. Expected: `FindExitLocation` tries left, right, then behind and `ExitVehicle` returns false with the character still stowed when all three are blocked (Task 5 `FT_DFEnterExit_BlockedExitFails`).
2. Pressing Interact while the car is still rolling: no exit, no state change (Task 5 `FT_DFEnterExit_RefusedWhileMoving`).
3. Damage after the vehicle is already destroyed: ignored, `OnVehicleDestroyed` fires once (Task 3 `FT_DFVehicle_BodyDamageDestroysOnce`).
4. The player's parked car is wrecked while they are on foot: a life is lost and the respawn pulls the character into a fresh car at the last gate (Task 7 `FT_DFRespawn_WreckedParkedCarPullsCharacterIn`).
5. The clock reaches zero while a respawn is pending: no car spawns after the race ends and the death count stops (Task 7 `FT_DFRespawn_NothingAfterRaceEnd`).

---

## File structure

```
comp4900sef/comp4900sef.uproject                     modify: remove Modules; keep the three plugins
comp4900sef/Source/                                  delete (whole folder, incl. Target.cs files)
comp4900sef/Binaries/, Intermediate/, .vs/, *.sln    delete (untracked build output)
comp4900sef/Config/DefaultEngine.ini                 modify: drop ActiveGameNameRedirects; same maps and GameMode path
comp4900sef/Config/DefaultInput.ini                  modify: add LookRight axis (MouseX)
comp4900sef/Content/VehicleBP/Sedan/{Sedan,Sedan_FrontWheel,Sedan_BackWheel}.uasset   copied from the engine template
comp4900sef/Content/ThirdPersonBP/Blueprints/ThirdPersonCharacter.uasset              copied from the engine template
comp4900sef/Content/DeadFire/Blueprints/BP_DF{Vehicle,Character,PlayerController,RaceGameMode,RaceGameState,HUD,TrackSpline,Checkpoint}.uasset   recreated (old ones deleted)
comp4900sef/Content/DeadFire/Components/BPC_DF{Weapon,Racer}.uasset
comp4900sef/Content/DeadFire/Data/{S_DFTireState,S_DFRaceResult,E_DFRaceEndReason}.uasset
comp4900sef/Content/DeadFire/UI/WBP_DF{RaceHUD,RaceSummary}.uasset
comp4900sef/Content/DeadFire/Maps/L_TestTrack.umap   rebuilt
comp4900sef/Content/DeadFire/Tests/L_DF_FunctionalTests.umap, FT_DF*.uasset
comp4900sef/Script/df_convert_to_blueprint.py        create: deletes stale assets, verifies template assets load
comp4900sef/Script/df_create_blueprints.py           rewrite: template parents, components, defaults, GameMode class overrides
comp4900sef/Script/df_build_test_track.py            modify: new classes, spline points on a Blueprint spline, builds both maps
comp4900sef/Script/df_build_widgets.py               create: WBP_DFRaceHUD / WBP_DFRaceSummary widget trees
comp4900sef/Script/df_verify_blueprints.py           create: checks every compiled BP_DF*/BPC_DF* class for the expected variables, defaults and callable functions
comp4900sef/Script/paste/<Blueprint>/<Graph>.txt     generated: clipboard text per graph (committed, so anyone can re-apply or paste by hand)
comp4900sef/Script/paste/<Blueprint>/manifest.json   generated: what the runner applies (variables, dispatchers, functions, graphs, links)
comp4900sef/Script/df_apply_blueprint.py             create: in-editor runner applying manifests through the authoring plugin
tools/DFBlueprintAuthoring/                          exists: editor plugin source (UDFBlueprintAuthoringLibrary); tools/build_authoring_plugin.ps1 builds and installs it into D:\UE_4.27\Engine\Plugins\DeadFire\
tools/bpgen/bpgen.py                                 exists: graph generator library (node constructors, links, emit) + Blueprint manifest writer
tools/bpgen/graphs/paste_test.py                     exists: Task 0 proof sample
tools/bpgen/graphs/{vehicle,weapon,character,enter_exit,track,checkpoint,game_mode,hud,tests}.py   create: one module per task, each emits its Blueprints' manifests and graph text
tools/run_tests.ps1                                  modify: default filter "Project.Functional Tests"
README.md                                            rewrite in Task 9
docs/superpowers/playtest-checklist.md               create in Task 9
```

Ownership per the design §6; "owner" in a **(person)** step means that teammate, or the project manager when the teammate is unavailable.

---

### Task 0: Authoring plugin and proof

**Files:**
- Exists: `tools/DFBlueprintAuthoring/` (uplugin, Build.cs, `DFBlueprintAuthoringLibrary.h/.cpp`), `tools/build_authoring_plugin.ps1`, `tools/bpgen/bpgen.py`, `tools/bpgen/graphs/paste_test.py`; scratch asset `/Game/DeadFire/Scratch/BP_DFPasteTest` (Actor child)
- Create: `comp4900sef/Script/df_apply_blueprint.py`; extend `bpgen.py` with the manifest writer (`Blueprint` object: asset path, `variable(...)`, `function(...)`, `dispatcher(...)`, graphs, `link(...)` incl. `entry`/`result` ids) and `paste_test.py` to use it

**Interfaces:**
- Produces: `unreal.DFBlueprintAuthoringLibrary` with `add_variable(bp, name, type_spec, default, category, instance_editable) → (ok, err)`, `add_function(bp, name, inputs, outputs, pure, category)`, `add_event_dispatcher(bp, name, params)`, `add_struct_member(struct, name, type_spec, default)`, `add_enum_value(enum, display_name)`, `import_nodes(bp, graph, text) → (ok, report)`, `connect_pins(bp, graph, node_a, pin_a, node_b, pin_b)`, `set_pin_default(...)`, `clear_graph(bp, graph)`, `describe_blueprint(bp) → json`, `describe_graph(bp, graph) → json`, `compile(bp) → (ok, messages)`. Type specs: `bool|int|int64|float|string|name|text|byte|object:<class path>|class:<class path>|struct:<path>|enum:<path>|array<...>`; params `Name:Type[=Default]`.
- `df_apply_blueprint.py`: `apply_manifest(path) → bool` (creation in order, graphs cleared and re-imported, links, compile, save; prints every compiler message; returns False on any error) and a `main()` applying every `manifest.json` under a folder given by `DF_MANIFESTS` (env or module variable).

- [ ] **Step 1:** Build and install the plugin with `tools/build_authoring_plugin.ps1` (close the editor first if a previous build is loaded). Expected: `UE4Editor-DFBlueprintAuthoring.dll` under `D:\UE_4.27\Engine\Plugins\DeadFire\DFBlueprintAuthoring\Binaries\Win64\`. Restart the editor; `run_python` → `hasattr(unreal, 'DFBlueprintAuthoringLibrary')` is `True`.
- [ ] **Step 2:** Extend `bpgen.py` with the manifest writer and `df_apply_blueprint.py`; rework `paste_test.py` to declare the two variables, a function `Probe(Value: float) → Doubled: float` (body: `Multiply_FloatFloat` → result, linked from `entry.Value`), a dispatcher `OnProbed(Value: float)` fired from `Probe`, and the Event Graph from before plus a `ForEachLoop` over an int array. Run the generator, then the runner on the scratch manifest. Expected: runner reports compile OK.
- [ ] **Step 3:** Verify: `describe_blueprint` lists the variables, `Probe`, `OnProbed`; spawn the actor in the editor world, `call_method('PasteCheck')` → `PasteRan == True` and the log shows `DF paste: TestFlag true`; `call_method('Probe', 2.0) == 4.0`. If a node kind fails to import or resolve, fix `bpgen.py` or the plugin here before any other task.
- [ ] **Step 4:** Delete `/Game/DeadFire/Scratch/` and the sample paste folder. Record in the ledger which node kinds are proven.

### Task 1: Convert the project to Blueprint-only and import the template Blueprints

**Files:**
- Modify: `comp4900sef/comp4900sef.uproject`, `comp4900sef/Config/DefaultEngine.ini`, `comp4900sef/Config/DefaultInput.ini`, `tools/run_tests.ps1`
- Delete: `comp4900sef/Source/`, `comp4900sef/Binaries/`, `comp4900sef/Intermediate/`, `comp4900sef/Content/DeadFire/Blueprints/*.uasset`, `comp4900sef/Content/DeadFire/Maps/L_TestTrack.umap`
- Copy: `D:\UE_4.27\Templates\TP_VehicleBP\Content\VehicleBP\Sedan\*.uasset` → `comp4900sef/Content/VehicleBP/Sedan/`; `D:\UE_4.27\Templates\TP_ThirdPersonBP\Content\ThirdPersonBP\Blueprints\ThirdPersonCharacter.uasset` → `comp4900sef/Content/ThirdPersonBP/Blueprints/`
- Create: `comp4900sef/Script/df_convert_to_blueprint.py`

**Interfaces:**
- Produces: a project the stock editor opens with no compile prompt; `/Game/VehicleBP/Sedan/Sedan` and `/Game/ThirdPersonBP/Blueprints/ThirdPersonCharacter` loadable; input axis `LookRight` (MouseX, scale 1) added to the Phase 1 mappings (which stay as they are); `tools/run_tests.ps1` default `-Filter "Project.Functional Tests"`.

- [ ] **Step 1:** Save dirty packages and quit the running editor (`unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)`, console `QUIT_EDITOR`, wait for `UE4Editor.exe` to exit).
- [ ] **Step 2:** Delete the folders and assets listed above. Remove the `Modules` array from the `.uproject` (keep `Plugins`). Remove both `ActiveGameNameRedirects` lines from `DefaultEngine.ini`; keep `EditorStartupMap`, `GameDefaultMap` and `GlobalDefaultGameMode` (the GameMode is recreated at the same path in Task 2). Add `+AxisMappings=(AxisName="LookRight",Scale=1.000000,Key=MouseX)` to `DefaultInput.ini`.
- [ ] **Step 3:** Copy the template assets to the paths above.
- [ ] **Step 4:** Change `tools/run_tests.ps1`'s `$Filter` default to `"Project.Functional Tests"` and its synopsis text to say Functional Tests.
- [ ] **Step 5:** Launch `D:\UE_4.27\Engine\Binaries\Win64\UE4Editor.exe "<repo>\comp4900sef\comp4900sef.uproject"` detached. Expected: the editor opens without a "rebuild modules" prompt (a missing-map warning for `L_TestTrack` is fine until Task 6).
- [ ] **Step 6:** Write `df_convert_to_blueprint.py`: asserts `unreal.EditorAssetLibrary.does_asset_exist` for the two template Blueprints and the four Sedan/Mannequin assets they reference (`/Game/Vehicle/Sedan/Sedan_SkelMesh`, `/Game/Vehicle/Sedan/Sedan_AnimBP`, `/Game/Mannequin/Character/Mesh/SK_Mannequin`, `/Game/Mannequin/Animations/ThirdPerson_AnimBP`), loads both Blueprints and prints their `generated_class()` names. Run it through `run_python`. Expected: six `True` and the two class names `Sedan_C`, `ThirdPersonCharacter_C`, no load errors in the log.
- [ ] **Step 7:** Run `tools/run_tests.ps1`. Expected: exit code 0, `0 found` (no tests yet).

### Task 2: Shared data types and skeleton Blueprints

**Files:**
- Create **(person, owner Choy Tsz Lok)**: `Data/E_DFRaceEndReason`, `Data/S_DFTireState`, `Data/S_DFRaceResult`
- Create (automation): `comp4900sef/Script/df_create_blueprints.py` (rewrite) producing every `BP_DF*`, `BPC_DF*`, `WBP_DF*` asset with parent and components; `comp4900sef/Script/df_verify_blueprints.py`

**Interfaces:**
- Produces:
  - `E_DFRaceEndReason`: `None`, `TimeUp`, `DeathLimit`.
  - `S_DFTireState`: `BoneName: Name`, `Health: Float = 30`, `MaxHealth: Float = 30`, `bBlown: Boolean = false`.
  - `S_DFRaceResult`: `Reason: E_DFRaceEndReason`, `bPassed: Boolean`, `Rank: Integer`, `RacerCount: Integer`, `Score: Integer`, `Laps: Integer`, `Kills: Integer`, `Deaths: Integer`.
  - Blueprints and parents: `BP_DFVehicle` ← `Sedan`; `BP_DFCharacter` ← `ThirdPersonCharacter`; `BPC_DFWeapon`, `BPC_DFRacer` ← `ActorComponent`; `BP_DFPlayerController` ← `PlayerController`; `BP_DFRaceGameMode` ← `GameModeBase`; `BP_DFRaceGameState` ← `GameStateBase`; `BP_DFHUD` ← `HUD`; `BP_DFTrackSpline`, `BP_DFCheckpoint` ← `Actor`; `WBP_DFRaceHUD`, `WBP_DFRaceSummary` ← `UserWidget`.
  - Components added by the script: `BP_DFCharacter`: `InteractionSphere` (`SphereComponent`, radius 300, collision preset `OverlapOnlyPawn`), `Weapon` (`BPC_DFWeapon`); `BP_DFPlayerController`: `Racer` (`BPC_DFRacer`); `BP_DFTrackSpline`: `Spline` (`SplineComponent`, root, closed loop on); `BP_DFCheckpoint`: `Trigger` (`BoxComponent`, root, preset `Trigger`, extent (100, 1400, 250), generate overlap events on), `LeftPole` and `RightPole` (`StaticMeshComponent`, mesh `/Game/VehicleAdv/ArenaMesh/pole`, no collision, relative Y −700 / +700).
  - `BP_DFRaceGameMode` class defaults: `DefaultPawnClass = BP_DFVehicle`, `PlayerControllerClass = BP_DFPlayerController`, `GameStateClass = BP_DFRaceGameState`, `HUDClass = BP_DFHUD`.
  - `df_verify_blueprints.py`: a table `EXPECTED = {asset_path: {'functions': [...], 'variables': {name: default_or_None}}}` filled in by later tasks; prints `OK <asset>` or `MISSING <asset> <kind> <name>` per entry and ends with `VERIFY PASSED` / `VERIFY FAILED`. It reads functions from `bp.get_editor_property('function_graphs')` names and defaults from the generated class CDO.

- [ ] **Step 1 (person):** Create the enum and the two structs in `/Game/DeadFire/Data/` with the exact members above (Content Browser → Blueprints → Enumeration / Structure). Save.
- [ ] **Step 2:** Rewrite `df_create_blueprints.py`: for each asset, skip if it exists, else `unreal.BlueprintFactory()` with `parent_class` (a template Blueprint's `generated_class()` for the two pawns), save; add the components through MCP `manage_blueprint.add_component` with the properties above; set the GameMode class overrides on the CDO as the Phase 1 script did. Run it. Expected: `manage_blueprint.read` on each asset reports the parent above and the listed components.
- [ ] **Step 3:** If `add_component` fails on 4.27 for any component, record it in the ledger and have the owner add that component by hand with the same name and settings; re-run `read` to confirm.
- [ ] **Step 4:** Write `df_verify_blueprints.py` with `EXPECTED` covering the parents and components only; run it. Expected: `VERIFY PASSED`.

### Task 3: Vehicle health, tires, destruction, drive overrides

**Files:**
- Modify **(person, owners Fung Ming Chu / Chong Tsz Ho)**: `BP_DFVehicle`
- Create **(person)**: `Tests/FT_DFVehicle_TireDamageByBone`, `FT_DFVehicle_TireBlowsAndScalesThrottle`, `FT_DFVehicle_BodyDamageDestroysOnce`
- Modify: `df_verify_blueprints.py`

**Interfaces:**
- Consumes: `S_DFTireState` (Task 2); the template's `Mesh` and `VehicleMovement` components.
- Produces on `BP_DFVehicle`:
  - Variables (`Dead Fire|Health`): `MaxHealth: Float = 100`, `Health: Float = 100`, `TireMaxHealth: Float = 30`, `BlownTireSpeedScale: Float = 0.8`, `TireHitRadius: Float = 60`, `Tires: Array<S_DFTireState>` (4 entries, bone names `Wheel_Front_Left`, `Wheel_Front_Right`, `Wheel_Rear_Left`, `Wheel_Rear_Right`, each 30/30/false), `bIsDestroyed: Boolean = false`. (`Dead Fire|Enter Exit`): `ExitMaxSpeedKPH: Float = 10`, `ExitSideOffset: Float = 220`, `ExitUpOffset: Float = 100`, `ExitBehindOffset: Float = 350`, `Occupant: BP_DFCharacter` (not editable), `LastDriver: Controller` (not editable).
  - Functions: `GetSpeedKPH() → Float` (`VehicleMovement.GetForwardSpeed × 0.036`, absolute), `GetGearText() → Text` (`R` when `VehicleMovement.GetCurrentGear < 0`, `N` at 0, else the number), `GetBlownTireCount() → Integer`, `GetThrottleScale() → Float` (= `BlownTireSpeedScale ^ GetBlownTireCount`), `IsBelowExitSpeed() → Boolean` (`GetSpeedKPH < ExitMaxSpeedKPH`), `CanBeEntered() → Boolean` (no `Occupant` and not destroyed), `FindTireIndexForHit(BoneName: Name, ImpactPoint: Vector) → Integer` (index whose `BoneName` matches, else nearest wheel bone whose `Mesh.GetSocketLocation` is within `TireHitRadius`, else −1), `ApplyTireDamage(Index: Integer, Damage: Float)`, `DestroyVehicle(Killer: Controller)` (sets `bIsDestroyed`, fires `OnVehicleDestroyed`, then calls the GameMode's `NotifyVehicleDestroyed(self, Killer)` if the GameMode casts to `BP_DFRaceGameMode`; Task 7 adds that function), `TeleportAndStop(NewTransform: Transform)` (`Mesh.SetPhysicsLinearVelocity 0`, `SetPhysicsAngularVelocityInDegrees 0`, `SetActorTransform` with teleport, `VehicleMovement.SetHandbrakeInput false`).
  - Events: **Event Point Damage** → if `bIsDestroyed` do nothing; else `FindTireIndexForHit(BoneName, HitLocation)`; index ≥ 0 → `ApplyTireDamage` (tire health − Damage, clamped at 0; crossing to 0 sets `bBlown` and fires `OnTireBlown(Index)`); else `Health − Damage` clamped; fire `OnVehicleDamaged(Damage, TireIndex)`; `Health == 0` → `DestroyVehicle(InstigatedBy)`. **Event Any Damage** (radial/general) → same path with tire index −1. **Event Tick** (call parent first): when `bIsDestroyed` or no controller: `VehicleMovement.SetThrottleInput 0`, `SetSteeringInput 0`, `SetHandbrakeInput true`; else `SetThrottleInput(GetInputAxisValue "MoveForward" × GetThrottleScale)` so blown tires cap the throttle set by the template graph.
  - Event Dispatchers: `OnVehicleDamaged(Damage: Float, TireIndex: Integer)`, `OnTireBlown(TireIndex: Integer)`, `OnVehicleDestroyed(Vehicle: BP_DFVehicle, Killer: Controller)`, `OnOccupantEntered(Character: BP_DFCharacter)`, `OnOccupantExited(Character: BP_DFCharacter)`.

- [ ] **Step 1:** Write `tools/bpgen/graphs/vehicle.py`: the Event Graph (Point Damage, Any Damage, Tick, Interact placeholder) and one body per function above, `SETUP.md` listing every variable (type, default, category, Instance Editable), function stub (inputs/outputs) and dispatcher. Run it. Expected: `comp4900sef/Script/paste/BP_DFVehicle/` holds `EventGraph.txt`, one `<Function>.txt` per function and `SETUP.md`.
- [ ] **Step 2 (person):** Follow `BP_DFVehicle/SETUP.md` (create, paste, wire, Refresh All Nodes, Compile, Save). Report any error text.
- [ ] **Step 3:** Add the three Functional Tests to `tools/bpgen/graphs/tests.py` and run it; create the `FT_DF*` Blueprints (parent `FunctionalTest`) with `df_create_blueprints.py` and place them in `L_DF_FunctionalTests` with `df_build_test_track.py` (an empty level with a ground cube at Z −10 until Task 6 rebuilds it with the track). Each Start Test graph spawns a `BP_DFVehicle` at the test's location + (0, 0, 100), then:
  - `FT_DFVehicle_TireDamageByBone`: `ApplyPointDamage(Vehicle, 10, HitFromDirection (1,0,0), Hit with BoneName Wheel_Front_Left, ...)` → `Tires[0].Health == 20` and `Health == 100`.
  - `FT_DFVehicle_TireBlowsAndScalesThrottle`: 30 point damage to `Wheel_Front_Left` → `Tires[0].bBlown`, `GetBlownTireCount == 1`, `GetThrottleScale` within 0.001 of 0.8.
  - `FT_DFVehicle_BodyDamageDestroysOnce`: bind a counter to `OnVehicleDestroyed`; 100 point damage with bone `Vehicle_Base` → `bIsDestroyed`, `Health == 0`; another 50 → `Health == 0` and the counter is 1.
- [ ] **Step 4 (person):** Follow the three `FT_DF*/SETUP.md` sheets (each is one paste into Start Test, plus one counter variable for the third test).
- [ ] **Step 5:** Add `BP_DFVehicle`'s functions and the defaults above to `EXPECTED` in `df_verify_blueprints.py`; run it. Expected: `VERIFY PASSED`.
- [ ] **Step 6:** Run `tools/run_tests.ps1`. Expected: `3 passed, 0 failed, 3 found`.

### Task 4: Weapon component and on-foot character

**Files:**
- Modify **(person, owner Cheung Tsz Hin Anderson)**: `BPC_DFWeapon`, `BP_DFCharacter`
- Create **(person)**: `FT_DFWeapon_HitscanDamagesVehicle`, `FT_DFWeapon_RespectsCooldown`, `FT_DFCharacter_DiesAtZeroHealth`, `FT_DFCharacter_FindsNearestVehicle`
- Modify: `df_verify_blueprints.py`

**Interfaces:**
- Consumes: `BP_DFVehicle.CanBeEntered`, `EnterVehicle` (Task 5; the character's `TryEnterVehicle` calls it, so Task 5's Step 1 is done before this task's graphs are compiled), the template's `CameraBoom`, `FollowCamera`, `CharacterMovement`.
- Produces:
  - `BPC_DFWeapon` variables (`Dead Fire|Weapon`): `Damage: Float = 20`, `Range: Float = 8000`, `Cooldown: Float = 0.15`, `bDebugTrace: Boolean = true`, `DamageTypeClass: Class<DamageType> = DamageType`, `LastFireTime: Float = -1` (not editable). Functions: `CanFire() → Boolean` (`GetGameTimeInSeconds − LastFireTime ≥ Cooldown`), `Fire(Origin: Vector, Direction: Vector) → bHit: Boolean, Hit: HitResult` (returns false without tracing when `!CanFire`; `LineTraceByChannel` Visibility from Origin to Origin + Direction × Range, ignoring the owner and the owner's attach parent actor, debug draw when `bDebugTrace`; on a hit `ApplyPointDamage(HitActor, Damage, Direction, Hit, Owner.GetInstigatorController, Owner, DamageTypeClass)`; sets `LastFireTime`; fires `OnFired(Hit, bHit)`). Dispatcher: `OnFired(Hit: HitResult, bHit: Boolean)`.
  - `BP_DFCharacter` variables (`Dead Fire|Health`): `MaxHealth: Float = 100`, `Health: Float = 100`; state (not editable): `CurrentVehicle: BP_DFVehicle`, `bIsStowed: Boolean`, `bIsDead: Boolean`, `OwningController: Controller` (set by the GameMode at spawn, Task 7; needed because a stowed character has no controller). Functions: `IsInVehicle() → Boolean`, `IsDead() → Boolean`, `FindNearestEnterableVehicle() → BP_DFVehicle` (nearest overlapping actor of `InteractionSphere` that casts to `BP_DFVehicle` and `CanBeEntered`, else null), `TryEnterVehicle(Vehicle: BP_DFVehicle) → Boolean` (null → `FindNearestEnterableVehicle`; false when none or dead; else `Vehicle.EnterVehicle(self)`), `SetStowed(bStowed: Boolean, AttachTo: Actor)` (stowed: `SetActorHiddenInGame true`, `SetActorEnableCollision false`, `CharacterMovement.DisableMovement`, `AttachToActor(AttachTo, SnapToTarget)`, `SetActorTickEnabled false`; un-stowed: detach keep world, show, collision on, `SetMovementMode Walking`, tick on), `Fire() → Boolean` (false when dead or stowed; else `Weapon.Fire(FollowCamera.GetWorldLocation, FollowCamera.GetForwardVector)`), `Revive()` (`Health = MaxHealth`, `bIsDead = false`, `SetMovementMode Walking`, fires `OnCharacterRevived`).
  - Events: **Event Any Damage** → ignore when dead or stowed; `Health − Damage` clamped; `OnCharacterDamaged(Damage)`; at 0: `bIsDead = true`, `CharacterMovement.DisableMovement`, `OnCharacterDied`, then GameMode `NotifyCharacterDied(self)` (Task 7). **InputAction Interact** (Pressed) → `TryEnterVehicle(null)`. **InputAction Fire** (Pressed) → `Fire`.
  - Dispatchers: `OnCharacterDamaged(Damage: Float)`, `OnCharacterDied()`, `OnCharacterRevived()`, `OnEnteredVehicle(Vehicle: BP_DFVehicle)`, `OnExitedVehicle(Vehicle: BP_DFVehicle)`.

- [ ] **Step 1:** Write `tools/bpgen/graphs/weapon.py` and `character.py` per the Interfaces block; run both. Expected: paste folders and `SETUP.md` for `BPC_DFWeapon` and `BP_DFCharacter`. `TryEnterVehicle`'s body calls `BP_DFVehicle.EnterVehicle`, so `BP_DFVehicle/SETUP.md` from Task 5 Step 1 (the stub only) is done before this paste.
- [ ] **Step 2 (person):** Follow both `SETUP.md` sheets. Report any error text.
- [ ] **Step 3:** Add the four tests to `tests.py`, run it, create and place the `FT_DF*` Blueprints:
  - `FT_DFWeapon_HitscanDamagesVehicle`: spawn a vehicle at test location + (400, 0, 100) and a character at test location + (0, 0, 100); `Character.Weapon.Fire(character location + (0,0,100), (1,0,0))` → `bHit` and vehicle `Health == 80`.
  - `FT_DFWeapon_RespectsCooldown`: same set-up; two `Fire` calls in the same frame → the second returns false and `Health == 80`.
  - `FT_DFCharacter_DiesAtZeroHealth`: `ApplyDamage(Character, 100)` → `Health == 0` and `IsDead`.
  - `FT_DFCharacter_FindsNearestVehicle`: vehicles at +250 and +900 cm on X → `FindNearestEnterableVehicle` is the near one (after a 0.2 s `Delay` so overlaps register); move both to 1000 cm → null.
- [ ] **Step 4 (person):** Follow the four `FT_DF*/SETUP.md` sheets.
- [ ] **Step 5:** Extend `EXPECTED` with both assets' functions and defaults; run `df_verify_blueprints.py`. Expected: `VERIFY PASSED`.
- [ ] **Step 6:** Run `tools/run_tests.ps1`. Expected: `7 passed, 0 failed, 7 found`.

### Task 5: Enter/exit, player controller, racer component

**Files:**
- Modify **(person, owners Fung Ming Chu / Lee Chun Yin / Choy Tsz Lok)**: `BP_DFVehicle`, `BP_DFPlayerController`, `BPC_DFRacer`
- Create **(person)**: `FT_DFEnterExit_RoundTrip`, `FT_DFEnterExit_BlockedExitFails`, `FT_DFEnterExit_RefusedWhileMoving`, `FT_DFEnterExit_EnterRefusedWhenOccupied`
- Modify: `df_verify_blueprints.py`

**Interfaces:**
- Consumes: `BP_DFCharacter.SetStowed`, `IsDead`, `OnEnteredVehicle/OnExitedVehicle` (Task 4).
- Produces:
  - `BP_DFVehicle` functions: `CanExit() → Boolean` (has `Occupant`, not destroyed, `IsBelowExitSpeed`), `FindExitLocation() → bFound: Boolean, Location: Vector` (candidates in order: actor location − Right × `ExitSideOffset`, + Right × `ExitSideOffset`, − Forward × `ExitBehindOffset`, each + Up × `ExitUpOffset`; a candidate is free when `CapsuleOverlapActors` (radius 42, half-height 96, object types WorldStatic, WorldDynamic, Vehicle, PhysicsBody; ignore self) returns nothing), `EnterVehicle(Character: BP_DFCharacter) → Boolean` (false if `!CanBeEntered` or `Character.IsDead`; sets `Occupant`, `Character.CurrentVehicle = self`, `Character.SetStowed(true, self)`; if the character's controller exists it `Possess`es this vehicle; `LastDriver = GetController`; fires `OnOccupantEntered` and `Character.OnEnteredVehicle`), `ExitVehicle() → Boolean` (false if `!CanExit` or `!FindExitLocation`; `VehicleMovement.SetHandbrakeInput true`, `SetThrottleInput 0`; `Occupant.SetStowed(false, null)`; `Occupant.SetActorLocation(Location)`; the vehicle's controller `Possess`es the character; `LastDriver = that controller`; clear `Occupant` and `Character.CurrentVehicle`; fires `OnOccupantExited` and `Character.OnExitedVehicle`), `EjectOccupant()` (used by respawn: un-stow beside the wreck without speed or possession checks). **InputAction Interact** (Pressed) → `ExitVehicle`.
  - `BPC_DFRacer` variables (`Dead Fire|Race`, all editable, defaults): `Score: Integer = 0`, `LapsCompleted: Integer = 0`, `Kills: Integer = 0`, `Deaths: Integer = 0`, `NextCheckpointIndex: Integer = 1`, `LastCheckpoint: BP_DFCheckpoint = null`, `LastCheckpointTime: Float = -1`, `OffTrackSeconds: Float = 0`, `DistanceAlongTrack: Float = 0`, `RacerName: Text = "Player"`.
  - `BP_DFPlayerController` variables (not editable): `OnFootCharacter: BP_DFCharacter`, `CurrentVehicle: BP_DFVehicle`. Function `SwitchToPawn(NewPawn: Pawn)` (`Possess`). **Event On Possess** → `CurrentVehicle` = pawn cast to `BP_DFVehicle` or null.

- [ ] **Step 1:** Write `tools/bpgen/graphs/enter_exit.py`: adds the functions above and the Interact event to `vehicle.py`'s output (regenerate `BP_DFVehicle/`), and produces `BPC_DFRacer/` and `BP_DFPlayerController/`. Run it. Expected: the three paste folders with updated `SETUP.md` sheets (the vehicle sheet marks what is new since Task 3).
- [ ] **Step 2 (person):** Follow the three sheets (for `BP_DFVehicle`: new stubs, then paste the new function bodies and the Interact event). Report any error text.
- [ ] **Step 3:** Add the four tests to `tests.py`, run it, create and place the `FT_DF*` Blueprints (each spawns a vehicle and a character 400 cm apart, 100 cm up):
  - `FT_DFEnterExit_RoundTrip`: `Vehicle.EnterVehicle(Char)` → true, `Occupant == Char`, `Char.IsInVehicle`, `Char.IsHidden`, `Char.GetAttachParentActor == Vehicle`, `!Vehicle.CanBeEntered`; `ExitVehicle` → true, `Occupant == null`, character visible and detached, `|Char.Y − Vehicle.Y| ≥ 150`, within 500 cm of the vehicle.
  - `FT_DFEnterExit_BlockedExitFails`: after entering, spawn three `StaticMeshActor` cubes (`/Engine/BasicShapes/Cube`, scale 3) at the left, right and behind exit spots → `ExitVehicle` false and `Char.IsInVehicle` still true.
  - `FT_DFEnterExit_RefusedWhileMoving`: after entering, `Mesh.SetPhysicsLinearVelocity (1000, 0, 0)`; next frame `CanExit` false and `ExitVehicle` false.
  - `FT_DFEnterExit_EnterRefusedWhenOccupied`: a second character's `EnterVehicle` returns false.
- [ ] **Step 4 (person):** Follow the four `FT_DF*/SETUP.md` sheets.
- [ ] **Step 5:** Extend `EXPECTED`; run `df_verify_blueprints.py`. Expected: `VERIFY PASSED`.
- [ ] **Step 6:** Run `tools/run_tests.ps1`. Expected: `11 passed, 0 failed, 11 found`.

### Task 6: Track spline tool, checkpoint actor, test track and test level

**Files:**
- Modify **(person, owner Lau Chun Kit)**: `BP_DFTrackSpline`, `BP_DFCheckpoint`
- Create **(person)**: `FT_DFTrack_ClosedLoopGeneratesSegments`, `FT_DFTrack_LateralDistance`
- Modify (automation): `comp4900sef/Script/df_build_test_track.py`
- Generated: `Maps/L_TestTrack`, `Tests/L_DF_FunctionalTests`

**Interfaces:**
- Produces:
  - `BP_DFTrackSpline` variables (`Dead Fire|Track`): `bIsMainTrack: Boolean = true`, `RoadMesh: StaticMesh = /Engine/BasicShapes/Cube`, `RoadMaterial: MaterialInterface = /Game/VehicleAdv/Materials/MaterialInstances/BlackGrid`, `RoadWidth: Float = 1400`, `RoadThickness: Float = 20`, `bGenerateBarriers: Boolean = false`, `BarrierMesh: StaticMesh = Cube`, `BarrierMaterial = .../SolidOrange`, `BarrierHeight: Float = 80`, `BarrierThickness: Float = 30`, `MeshNativeSize: Float = 100`. **Construction Script:** for each segment `i` (closed loop: `N` segments, end index `(i+1) mod N`; open: `N−1`): `AddSplineMeshComponent` (mobility Static, collision `BlockAll`, forward axis X), `SetStaticMesh RoadMesh`, `SetMaterial 0 RoadMaterial`, `SetStartScale`/`SetEndScale` `(RoadWidth / MeshNativeSize, RoadThickness / MeshNativeSize)`, `SetStartAndEnd` with the local locations and tangents at `i` and the end index; when `bGenerateBarriers`, two more per segment offset ± (`RoadWidth`/2 + `BarrierThickness`/2) on the local right vector with scale (`BarrierThickness`, `BarrierHeight`) / `MeshNativeSize`. Functions: `GetSegmentCount() → Integer`, `GetGeneratedMeshCount() → Integer`, `GetTrackLength() → Float` (`Spline.GetSplineLength`), `GetDistanceAlongTrack(WorldLocation: Vector) → Float` (`Spline.FindInputKeyClosestToWorldLocation` → `GetDistanceAlongSplineAtSplineInputKey`), `GetLateralDistanceFromTrack(WorldLocation: Vector) → Float` (horizontal distance to `Spline.FindLocationClosestToWorldLocation`), `IsOnRoad(WorldLocation) → Boolean` (lateral ≤ `RoadWidth`/2), `GetTransformAtDistance(Distance: Float) → Transform`.
  - `BP_DFCheckpoint` variables (`Dead Fire|Checkpoint`): `CheckpointIndex: Integer = 0`, `TriggerHalfExtent: Vector = (100, 1400, 250)`, `PoleOffset: Float = 700`, `RespawnHeightOffset: Float = 50`. Construction Script re-applies the extent and pole offsets. Functions: `GetRespawnTransform() → Transform` (actor rotation, location + Z `RespawnHeightOffset`), `NotifyVehicle(Vehicle: BP_DFVehicle) → Boolean` (racer = `Vehicle.GetController`, else `Vehicle.LastDriver`; calls GameMode `NotifyCheckpointReached(Racer, self)`, Task 7; false when no GameMode). Events: `Trigger` **OnComponentBeginOverlap** → other actor cast to `BP_DFVehicle` → `NotifyVehicle`; **BeginPlay** → GameMode `RegisterCheckpoint(self)`.
  - `df_build_test_track.py`: builds `L_TestTrack` as before (ground, lights, fog, props, `PlayerStart` on the start line, world settings GameMode `BP_DFRaceGameMode`), spawns `BP_DFTrackSpline`, sets its points with `spline.set_spline_points(TRACK_POINTS, WORLD, True)` and triggers the construction script by re-setting `road_width` through `set_editor_property`, places four `BP_DFCheckpoint`s at 0 %, 25 %, 50 %, 75 % of the spline (via `GetTransformAtDistance`, index 0–3); with `BUILD_TESTS = True` it builds `L_DF_FunctionalTests` identically and keeps every existing `FT_DF*` actor in it (reads them before clearing, re-places them after).

- [ ] **Step 1:** Write `tools/bpgen/graphs/track.py` and `checkpoint.py` (the Construction Script is a graph too: paste into **ConstructionScript**, wire its entry exec by hand). Run both. Expected: `BP_DFTrackSpline/` and `BP_DFCheckpoint/` paste folders and sheets.
- [ ] **Step 2 (person):** Follow both sheets. Then drop one `BP_DFTrackSpline` into an empty level, drag points, confirm the road appears and follows the spline.
- [ ] **Step 3:** Modify and run `df_build_test_track.py`. Expected: `manage_level.list_actors` lists the track, four checkpoints with indices 0–3, lights, player start; `manage_editor.screenshot` shows the road loop with gate poles. If the road does not appear, nudge one spline point by hand (person) and resave.
- [ ] **Step 4:** Add the two tests to `tests.py`, run it, create and place the `FT_DF*` Blueprints, then **(person)** follow their sheets:
  - `FT_DFTrack_ClosedLoopGeneratesSegments`: the level's main track (`GetAllActorsOfClass BP_DFTrackSpline`, `bIsMainTrack`) has `GetSegmentCount == Spline.GetNumberOfSplinePoints` and `GetGeneratedMeshCount == GetSegmentCount` (no barriers).
  - `FT_DFTrack_LateralDistance`: a point 500 cm to the right of the spline at distance 1000 → `GetLateralDistanceFromTrack` within 5 of 500 and `IsOnRoad` true; 1000 cm → `IsOnRoad` false.
- [ ] **Step 5:** Extend `EXPECTED`; run `df_verify_blueprints.py`. Expected: `VERIFY PASSED`.
- [ ] **Step 6:** Run `tools/run_tests.ps1`. Expected: `13 passed, 0 failed, 13 found`.

### Task 7: Race GameMode and GameState: clock, scoring, checkpoint order, deaths, respawn, off-track, race end

**Files:**
- Modify **(person, owner Choy Tsz Lok)**: `BP_DFRaceGameMode`, `BP_DFRaceGameState`; finish the GameMode calls left open in `BP_DFVehicle.DestroyVehicle` (Task 3), `BP_DFCharacter` death (Task 4), `BP_DFCheckpoint` (Task 6)
- Create **(person)**: `FT_DFCheckpoint_OnlyTheNextGateCounts`, `FT_DFCheckpoint_LapResetsAndScores`, `FT_DFRespawn_WreckRespawnsAtLastGate`, `FT_DFRespawn_WreckedParkedCarPullsCharacterIn`, `FT_DFRespawn_DeathLimitEndsRace`, `FT_DFRespawn_NothingAfterRaceEnd`, `FT_DFOffTrack_RespawnsWithoutDeath`, `FT_DFRaceEnd_TimeUpSetsResult`
- Modify: `df_verify_blueprints.py`

**Interfaces:**
- Consumes: everything from Tasks 3–6.
- Produces:
  - `BP_DFRaceGameState` variables: `RemainingTime: Float`, `bRaceActive: Boolean = true`, `Result: S_DFRaceResult`. Function `GetRemainingTimeText() → Text` (`m:ss`).
  - `BP_DFRaceGameMode` variables (`Dead Fire|Race`, editable): `OnFootCharacterClass: Class<BP_DFCharacter> = BP_DFCharacter`, `RaceTimeLimit: Float = 120`, `CheckpointTimeBonus: Float = 8`, `PointsPerLap: Integer = 100`, `PointsPerKill: Integer = 50`, `MaxDeaths: Integer = 3`, `ScoreRequirement: Integer = 300`, `RespawnDelay: Float = 2`, `OffTrackMargin: Float = 500`, `OffTrackGraceSeconds: Float = 5`. State (not editable): `Checkpoints: Array<BP_DFCheckpoint>` (sorted by index), `Tracks: Array<BP_DFTrackSpline>`, `MainTrack: BP_DFTrackSpline`, `PendingRespawnRacer: Controller`, `RespawnDueTime: Float = -1`.
  - Functions: `GetRaceState() → BP_DFRaceGameState`; `FindRacer(C: Controller) → BPC_DFRacer` (component by class, may be null); `CollectLevelActors()` (fills `Checkpoints` sorted, `Tracks`, `MainTrack` = first with `bIsMainTrack`); `RegisterCheckpoint(CP)` (idempotent, keeps the array sorted); `AddScore(C: Controller, Points: Integer)`; `GrantCheckpointTimeBonus(C)` (player controllers only: `RemainingTime += CheckpointTimeBonus`); `NotifyCheckpointReached(C: Controller, CP: BP_DFCheckpoint) → Boolean` (false when `!bRaceActive`, no racer, or `CP.CheckpointIndex != NextCheckpointIndex`; else `LastCheckpoint = CP`, `LastCheckpointTime = GetGameTimeInSeconds`; index 0 → `NotifyLapCompleted` + bonus, else `NotifyCheckpointPassed`; true); `NotifyLapCompleted(C)` (`Laps + 1`, `AddScore PointsPerLap`, `NextCheckpointIndex = 1`); `NotifyCheckpointPassed(C)` (`Next = (Next + 1) mod Count`, bonus); `NotifyVehicleDestroyed(Victim: BP_DFVehicle, Killer: Controller)` (racer = victim controller else `LastDriver`; killer's racer, if different, `Kills + 1` and `AddScore PointsPerKill`; `HandleRacerDeath(racer controller)`); `NotifyCharacterDied(Char: BP_DFCharacter)` (`HandleRacerDeath(Char.OwningController)`); `HandleRacerDeath(C)` (ignored when `!bRaceActive`; `Deaths + 1`; `Deaths ≥ MaxDeaths` → `EndRace(DeathLimit)`, else `PendingRespawnRacer = C`, `RespawnDueTime = now + RespawnDelay`); `GetRespawnTransform(C) → Transform` (`LastCheckpoint`, else `Checkpoints[0]`, else the first `PlayerStart`); `RespawnRacer(C: Controller)` (vehicle = `C.CurrentVehicle` if intact → `TeleportAndStop`; else spawn `DefaultPawnClass` at the transform and `DestroyActor` the wreck; character = `C.OnFootCharacter`: `Revive` if dead, `EjectOccupant` from a wreck, then `Vehicle.EnterVehicle(Character)`; `OffTrackSeconds = 0`; `OnRacerRespawned(C)`); `IsOnAnyTrack(Location: Vector) → Boolean` (true when `Tracks` is empty; else any track with `GetLateralDistanceFromTrack ≤ RoadWidth/2 + OffTrackMargin`); `TickRacer(C, DeltaSeconds)` (`DistanceAlongTrack` from `MainTrack`; off-track timer only while the pawn is an intact `BP_DFVehicle`: accumulate, reset when on a track, at `OffTrackGraceSeconds` reset and `RespawnRacer` without a death); `GetRankedRacers() → Array<BPC_DFRacer>` (all controllers with a racer, selection-sorted by `Score`, then `LapsCompleted`, then `DistanceAlongTrack`, descending); `EndRace(Reason: E_DFRaceEndReason)` (`bRaceActive = false`; clear the pending respawn; fill `Result` from the first player's racer, `bPassed = Reason == TimeUp && Score ≥ ScoreRequirement`, `Rank` = 1-based index in `GetRankedRacers`, `RacerCount`; `OnRaceEnded(Reason, bPassed)`; player: `DisableInput`, `SetInputModeUIOnly`, show cursor; `HUD.ShowSummary` (Task 8)).
  - Events: **BeginPlay** → `RemainingTime = RaceTimeLimit`, `CollectLevelActors`. **Event OnPostLogin** → spawn `OnFootCharacterClass` 300 cm left of the new player's pawn, set `Character.OwningController` and `PC.OnFootCharacter`, `Vehicle.EnterVehicle(Character)`. **Event Tick** → when `bRaceActive`: `RemainingTime −= dt`; ≤ 0 → `RemainingTime = 0`, `EndRace(TimeUp)`; `TickRacer` for every player controller; `RespawnDueTime ≥ 0 && now ≥ RespawnDueTime` → clear and `RespawnRacer(PendingRespawnRacer)`.
  - Dispatchers: `OnRaceEnded(Reason: E_DFRaceEndReason, bPassed: Boolean)`, `OnRacerRespawned(C: Controller)`.

- [ ] **Step 1:** Write `tools/bpgen/graphs/game_mode.py` for `BP_DFRaceGameState` and `BP_DFRaceGameMode`; regenerate `vehicle.py`, `character.py` and `checkpoint.py` so their pending GameMode calls (`DestroyVehicle`, character death, `NotifyVehicle`, `RegisterCheckpoint`) are real `call_on(BP_DFRaceGameMode, ...)` nodes. Run them. Expected: paste folders for the two new Blueprints and re-paste instructions in the three updated sheets (only the changed graphs are listed).
- [ ] **Step 2 (person):** Follow the five sheets (new Blueprints fully; the three updated ones: delete the listed old graph, re-paste the new file). Report any error text.
- [ ] **Step 3:** Add the eight tests to `tests.py`, run it, create and place the `FT_DF*` Blueprints, then **(person)** follow their sheets. The level's GameMode spawns the player in a car at the start line; `PC` = player controller 0, `GM` = game mode cast, `Racer = GM.FindRacer(PC)`, `Gates = GM.Checkpoints`:
  - `FT_DFCheckpoint_OnlyTheNextGateCounts`: `NotifyCheckpointReached(PC, Gates[2])` false and `Next == 1`; `(PC, Gates[1])` true, `Next == 2`, `RemainingTime` grew by 8 ± 0.1; `(PC, Gates[1])` again false.
  - `FT_DFCheckpoint_LapResetsAndScores`: set `Next = 0`; `NotifyCheckpointReached(PC, Gates[0])` → `Laps == 1`, `Score == 100`, `Next == 1`, clock +8.
  - `FT_DFRespawn_WreckRespawnsAtLastGate`: `Racer.LastCheckpoint = Gates[1]`; `ApplyDamage(PC.CurrentVehicle, 100)`; `Delay 2.5` → `Deaths == 1`, `PC.GetPawn` is a `BP_DFVehicle` that is not destroyed, within 300 cm of `Gates[1].GetRespawnTransform`, with `Occupant == PC.OnFootCharacter`.
  - `FT_DFRespawn_WreckedParkedCarPullsCharacterIn`: `PC.CurrentVehicle.ExitVehicle` (first `TeleportAndStop` so it is still); `ApplyDamage(that car, 100)`; `Delay 2.5` → `Deaths == 1`, `PC.GetPawn` is a fresh intact vehicle, character `IsInVehicle`.
  - `FT_DFRespawn_DeathLimitEndsRace`: `Racer.Deaths = 2`; wreck the car; next frame `Result.Reason == DeathLimit`, `bRaceActive` false; `Delay 2.5` → still only one `BP_DFVehicle` that is destroyed (no respawn).
  - `FT_DFRespawn_NothingAfterRaceEnd`: wreck the car (respawn pending); `EndRace(TimeUp)`; `Delay 2.5` → `PC.GetPawn` is still the wreck; `ApplyDamage(PC.OnFootCharacter, 100)` → `Deaths` still 1.
  - `FT_DFOffTrack_RespawnsWithoutDeath`: `PC.CurrentVehicle.TeleportAndStop` to the main track's centre + (0, 0, 100) offset 5000 cm sideways from the road; `Delay 5.5` → car within 300 cm of `Gates[0].GetRespawnTransform`, `Deaths == 0`.
  - `FT_DFRaceEnd_TimeUpSetsResult`: `Racer.Score = 300`; `GameState.RemainingTime = 0.01`; `Delay 0.2` → `Result.Reason == TimeUp`, `bPassed`, `Rank == 1`, `RacerCount == 1`.
- [ ] **Step 4:** Extend `EXPECTED` with both assets' functions and defaults; run `df_verify_blueprints.py`. Expected: `VERIFY PASSED`.
- [ ] **Step 5:** Run `tools/run_tests.ps1`. Expected: `21 passed, 0 failed, 21 found`.

### Task 8: UMG HUD, summary widget, HUD class

**Files:**
- Create (automation): `comp4900sef/Script/df_build_widgets.py` (widget trees of `WBP_DFRaceHUD` and `WBP_DFRaceSummary` through `manage_widget`)
- Modify **(person, owner Lee Chun Yin)**: `WBP_DFRaceHUD`, `WBP_DFRaceSummary`, `BP_DFHUD`
- Create **(person)**: `FT_DFHUD_SummaryShownAtRaceEnd`

**Interfaces:**
- Consumes: `BP_DFPlayerController.CurrentVehicle`, `OnFootCharacter`; `BPC_DFRacer`; `BP_DFVehicle.GetSpeedKPH`, `GetGearText`, `Health`, `Tires`, `CanExit`, `IsBelowExitSpeed`; `BP_DFCharacter.FindNearestEnterableVehicle`; `BP_DFRaceGameState.GetRemainingTimeText`, `RemainingTime`, `Result`; `GM.OffTrackGraceSeconds`; `Racer.OffTrackSeconds`, `LastCheckpointTime`.
- Produces:
  - `WBP_DFRaceHUD` tree (canvas root): text blocks `ScoreText`, `LapText`, `KillsText`, `LivesText` (top-left column), `TimeText` (top-centre), `SpeedText`, `GearText` (bottom-right), a `VehiclePanel` (vertical box, bottom-left) with `VehicleHealthText`, `VehicleHealthBar` (progress bar), `TireText`; a `CharacterPanel` with `CharacterHealthText`, `CharacterHealthBar`; `CrosshairText` (`+`, centre), `PromptText` (72 % height), `WarningText` (40 % height). Function `Refresh()` called from **Event Tick** with the copy of Phase 2 design §6: `SCORE 150`, `LAPS 2`, `KILLS 1`, `LIVES 2` (= `MaxDeaths − Deaths`), clock `1:13` red under 10 s, `87 km/h`, `GEAR 3` (`R` red), `CAR 80 / 100`, `TIRES [30] [X] [30] [30]`, `HEALTH 100 / 100`; prompts `[E] Exit vehicle` / `Stop to exit  [E]` / `No room to exit` / `[E] Enter vehicle`; warnings `RETURN TO TRACK  4.2` (`OffTrackGraceSeconds − OffTrackSeconds`, one decimal, while `OffTrackSeconds > 0`), `WRECKED`, `YOU DIED`, `CHECKPOINT  +8 s` for 1.5 s after `LastCheckpointTime`. `VehiclePanel`/`SpeedText`/`GearText` visible only in a car; `CharacterPanel`/`CrosshairText` only on foot.
  - `WBP_DFRaceSummary` tree: `TitleText`, `PlaceText`, `StatsText`, `RetryButton` with `RetryLabel`, `QuitButton` with `QuitLabel`. Function `ShowResult(Result: S_DFRaceResult, ScoreRequirement: Integer)` sets `RACE COMPLETE` / `TIME UP` / `GAME OVER`, `Place 1 of 1`, `Score 250 / 300    Laps 2    Kills 1    Deaths 0`. Retry → `SetInputModeGameOnly`, `OpenLevel(GetCurrentLevelName)`; Quit → `QuitGame`.
  - `BP_DFHUD` variables (editable): `HUDWidgetClass: Class<UserWidget> = WBP_DFRaceHUD`, `SummaryWidgetClass = WBP_DFRaceSummary`; state `HUDWidget`, `SummaryWidget`. **BeginPlay** → create and add the HUD widget. Function `ShowSummary()` → remove the HUD widget, create the summary, `ShowResult(GameState.Result, GM.ScoreRequirement)`, add to viewport, `SetInputModeUIOnly` with the summary as the widget to focus.

- [ ] **Step 1:** Write and run `df_build_widgets.py` (`manage_widget.create_widget_blueprint`, `ensure_canvas_root`, `add_text_block`, `add_button`, `add_child_widget`, `position_widget` per the layout above; sizes and colours are the builder's). Expected: `manage_widget.inspect_tree` lists every named element for both widgets.
- [ ] **Step 2:** Write `tools/bpgen/graphs/hud.py` for `WBP_DFRaceHUD` (`Refresh` body and Tick), `WBP_DFRaceSummary` (`ShowResult`, the two button `OnClicked` component events) and `BP_DFHUD`. Run it. Expected: three paste folders and sheets.
- [ ] **Step 3 (person):** Follow the three sheets. The widget variables for named elements already exist (Is Variable is on for every element the builder created), so the sheets list only the state variables.
- [ ] **Step 4:** Add `FT_DFHUD_SummaryShownAtRaceEnd` to `tests.py`, run it, create and place it, then **(person)** follow its sheet: `GM.EndRace(TimeUp)`; next frame `GetAllWidgetsOfClass WBP_DFRaceSummary` has one entry whose `TitleText` reads `TIME UP`, and no `WBP_DFRaceHUD` is in the viewport.
- [ ] **Step 5:** Extend `EXPECTED` (HUD defaults, widget functions); run `df_verify_blueprints.py`. Expected: `VERIFY PASSED`.
- [ ] **Step 6:** Run `tools/run_tests.ps1`. Expected: `22 passed, 0 failed, 22 found`.

### Task 9: Playtest, README, final verification

**Files:**
- Create: `docs/superpowers/playtest-checklist.md`
- Rewrite: `README.md`

- [ ] **Step 1:** Write `playtest-checklist.md` as a tick list of the design §8 acceptance lines, one line per observable behaviour (drive, Tab camera, HUD fields, exit/enter, fire, gates in order, lap, wreck → respawn at the last gate, third death → GAME OVER, off-track → back on track without a life, time up → summary, Retry, Quit).
- [ ] **Step 2 (person):** Play `L_TestTrack` and tick every line; record any failure in the ledger and fix it in the owning task's Blueprint before continuing.
- [ ] **Step 3:** Rewrite `README.md`: prerequisites (UE 4.27.2 only), open and play, controls, the Blueprint asset table with owners, how logic is organised (template parents untouched, `BP_DF*` children, dispatchers, `Dead Fire|` categories), how graphs are generated and pasted (`tools/bpgen`, `comp4900sef/Script/paste/`, the SETUP procedure, "change the generator, not the graph" for anything a later phase extends), how to run the Functional Tests and where to add one, the editor scripts (`df_create_blueprints.py`, `df_build_test_track.py`, `df_build_widgets.py`, `df_verify_blueprints.py`, `tools/ue_remote.py`), the playtest checklist, the Blueprint merge rule from the design §9, and the phase roadmap.
- [ ] **Step 4:** Run `df_verify_blueprints.py` and `tools/run_tests.ps1` one last time. Expected: `VERIFY PASSED`; `22 passed, 0 failed, 22 found`.
- [ ] **Step 5:** `git status` review: `comp4900sef/Source/` gone, template and `DeadFire` content present, scripts and docs updated. Do not commit; report `git add -A && git commit -m "Blueprint migration: replace the C++ module with Blueprints on the template pawns; 22 functional tests"` for the user.
