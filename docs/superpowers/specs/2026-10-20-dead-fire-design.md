# Dead Fire (死火) — Game Design & Engineering Design

Date: 2026-10-20
Source: "Group 3_4900SEF_Project Proposal.docx" (COMP 4900SEF, Group 3) plus the flowchart and paper prototype attached to it.
Status: Phase 1 approved for build by the project manager's request ("brainstorm and implement in phases"). Items marked **[call]** are engineering decisions made by the implementer, not stated in the proposal; the team can overturn any of them.

**Revision 2026-10-21 (project manager's decision): the game is built in Blueprint, not C++.** Phases 1 and 2 were built as a C++ module (commits `b3ef0ce`, `c8a3040`); that foundation was replaced on 2026-10-22 by Blueprints built on the engine's Vehicle and Third Person Blueprint templates, as the proposal originally stated (Phase 2B). §5, §6, §7, §8 and §9 below are rewritten for Blueprint; §1–§4 and §6.1–§6.3 (behaviour and rules) are unchanged. The migration plan and its execution record are in `docs/superpowers/plans/2026-10-21-blueprint-migration.md`.

---

## 1. Intent

Dead Fire is a single-player **action-racing hybrid**: arcade racing on a looped track, mixed with third-person shooting and item-based interference. A syndicate called "Fire" runs an illegal race to flex its power; the player is an undercover cop who climbs the ranks by winning races and destroying gang members' cars.

The pitch in the proposal: *checkpoint scoring + item-based interference + the ability to leave the car and explore secrets behind the track.* Everything below serves those three ideas.

## 2. Goals, non-goals, anti-goals

**Goals**
- A race loop that is fun in 5 minutes: drive fast, hit checkpoints, finish laps, blow up rivals, survive.
- Leaving the car must matter: loot boxes and shortcuts are only reachable on foot.
- Chaos through items: boost, shield, bomb/trap, guns, RPG, and destructible environment.
- A foundation the six-person team can build on in parallel, mapped to the duties in the proposal.
- Ship a playable build by week 13.

**Non-goals**
- Multiplayer (listed optional in the proposal). Treated as **dead** for this course project: nothing is replicated, and the two-pawn possession model, HUD and timer are single-player designs. Adding networking later would be a rewrite, not an extension. **[call]**
- Realistic simulation driving. Arcade handling, forgiving physics.
- Final art. Grey-box and engine template assets are acceptable until polish.

**Anti-goals (what would make this a failure even if it runs)**
- Driving that feels bad (flips constantly, no sense of speed, unresponsive). Driving is 80% of the play time.
- Exiting the car being pointless or a death trap.
- Scope creep that blocks a playable loop before week 11.

## 3. Core loop (from the flowchart)

1. Main menu → vehicle selection (shows stats) → level selection.
2. Level spawns the track, NPC vehicles, items, and the player **inside** a vehicle.
3. Race loop, until the time limit expires:
   - Drive laps. Passing a checkpoint adds time. Completing a lap adds score (+X).
   - Destroying an NPC car adds score (+Y).
   - Stop the car and exit on foot to search for items off-track. Items found unlock limited uses on the car.
   - Driving-assist items (boost, shield) affect the player's car. Destruction items (bomb, gun, RPG) attack NPC cars or change the environment (destroy rock/waterfall to open a shortcut).
   - Dying respawns the player at the nearest checkpoint. Exceeding the max death count is game over.
4. When time is up: if the score reaches the level requirement, show the summary; first place unlocks that stage's vehicle. Otherwise game over.
5. Continue playing (back to vehicle select) or quit.

## 4. Scoring and race rules (initial values, all tunable) **[call]**

| Rule | Value |
|---|---|
| Race time limit | 120 s |
| Time bonus per checkpoint | +8 s |
| Score per lap completed | +100 |
| Score per NPC car destroyed | +50 |
| Max deaths before game over | 3 |
| Score requirement to pass a level | set per level in the GameMode Blueprint |
| Exit vehicle allowed when speed below | 10 km/h |
| Vehicle body health | 100 |
| Tire health (each) | 30; each blown tire scales top speed by 0.8 |
| On-foot character health | 100 |

## 5. Platform and tech **[call]**

- **Unreal Engine 4.27.2**, Windows, the existing `comp4900sef` project in this repository.
- **Blueprint-only project, built on the engine's Vehicle and Third Person Blueprint templates** (`TP_VehicleBP`'s `Sedan` and `TP_ThirdPersonBP`'s `ThirdPersonCharacter`, copied into the project with their original package paths). This is what the proposal states; the C++ module used for Phases 1–2 is removed. Consequences:
  - Nobody needs Visual Studio. The editor opens the project directly and every teammate can read and change any gameplay logic.
  - Driving, both vehicle cameras and on-foot movement come from the template Blueprints, which are **not edited**. All Dead Fire logic lives in child Blueprints (`BP_DFVehicle` is a child of `Sedan`, `BP_DFCharacter` of `ThirdPersonCharacter`), so template behaviour and our behaviour stay separable.
  - **Graphs are generated and applied by tooling.** UE 4.27's Python cannot create or read Blueprint variables, functions or graph nodes, so each Blueprint is described in Python under `tools/bpgen/graphs/` and emitted as a manifest plus the editor's own clipboard text per graph (`comp4900sef/Script/paste/`). An editor-only plugin, **DF Blueprint Authoring** (`tools/DFBlueprintAuthoring`, built into the engine install of whoever runs the tooling, never into the project), exposes the missing editor operations to Python; `comp4900sef/Script/df_apply_blueprint.py` uses it to create variables, functions, dispatchers, components and widget trees, import and link the graphs, verify that every node, link and pin default arrived, compile and save. Teammates never need the plugin: the result is ordinary Blueprint assets. Graphs with a generator module are changed through the module and re-applied; everything else is edited in the editor as usual.
  - Tests: the C++ automation suite is retired. Its place is taken by **Blueprint Functional Tests** (`FT_DF*`, children of the engine's `FunctionalTest` actor, placed in `/Game/DeadFire/Tests/L_DF_FunctionalTests`), generated like the gameplay Blueprints and run headless by `tools/run_tests.ps1`, plus a written playtest checklist (`docs/superpowers/playtest-checklist.md`) for what tests cannot press: real input, feel, cameras.
  - Cost: the Phase 1–2 feature set was rebuilt once (Phase 2B), by the tooling rather than by hand.
- **Vehicles: PhysX Vehicles** (`WheeledVehicle`, `WheeledVehicleMovementComponent4W`), which is the UE4.27 default and what the Vehicle template uses. Chaos Vehicles is experimental in 4.27 and is not used.
- **Input: classic UE4 action/axis mappings** in `DefaultInput.ini`. Enhanced Input is experimental in 4.27. The template Blueprints need the axis `LookRight` (MouseX) in addition to the Phase 1 mappings.
- **Content: free only.** Engine template packs copied into the project (Vehicle Sedan, Mannequin, Geometry, VehicleAdv arena meshes/materials/engine sounds) and the Starter Content pack. Later phases may import CC0 packs (e.g. Kenney, Quaternius) via the editor's import pipeline.
- Plugins enabled in the `.uproject`: `PhysXVehicles` (runtime), `PythonScriptPlugin` and `EditorScriptingUtilities` (editor-only; used by the automation and harmless for teammates).

## 6. Architecture

Asset prefix `DF`: `BP_DF*` actors, `BPC_DF*` actor components, `WBP_DF*` widgets, `S_DF*` structs, `E_DF*` enums, `FT_DF*` functional tests. Everything lives under `/Game/DeadFire/` in `Blueprints/`, `Components/`, `Data/`, `UI/`, `Maps/` and `Tests/`. The template Blueprints stay at `/Game/VehicleBP/Sedan/Sedan` and `/Game/ThirdPersonBP/Blueprints/ThirdPersonCharacter`.

| Asset | Parent | Responsibility | Owner (from proposal) |
|---|---|---|---|
| `BP_DFVehicle` | `Sedan` (Vehicle template) | Body + per-tire health, damage routing, destruction, enter/exit, "last driver"; driving and cameras inherited | Fung Ming Chu (physics/driving/enter-exit), Chong Tsz Ho (vehicle health) |
| `BP_DFCharacter` | `ThirdPersonCharacter` (Third Person template) | Interact (enter vehicle), fire, health, death/revive, stowed state; movement and camera inherited | Cheung Tsz Hin Anderson (weapons/shooting) |
| `BPC_DFWeapon` | `ActorComponent` | Hitscan weapon: damage, range, cooldown, fire from an origin/direction. On the character now; mounted on vehicles for gun/RPG items in Phase 3 | Cheung Tsz Hin Anderson |
| `BP_DFPlayerController` | `PlayerController` | Possession switching between vehicle and character; carries a `BPC_DFRacer` | Lee Chun Yin (integration) |
| `BPC_DFRacer` | `ActorComponent` | Per-racer race state (score, laps, kills, deaths, next/last checkpoint, off-track seconds). Lives on the **controller** (player or AI) so it survives vehicle respawns and lets the GameMode rank NPCs against the player for "first place" | Choy Tsz Lok |
| `BP_DFRaceGameMode` | `GameModeBase` | Spawns player vehicle + stowed on-foot character, race rules/tunables, checkpoint order, laps, kills, death/respawn, off-track timer, ranking, race end | Choy Tsz Lok (GameMode/scoring) |
| `BP_DFRaceGameState` | `GameStateBase` | Remaining time, race active flag, race result | Choy Tsz Lok |
| `BP_DFHUD` | `HUD` | Creates `WBP_DFRaceHUD` at start and `WBP_DFRaceSummary` at race end | Lee Chun Yin |
| `WBP_DFRaceHUD`, `WBP_DFRaceSummary` | `UserWidget` | In-race HUD; end-of-race summary with Retry/Quit | Lee Chun Yin |
| `BP_DFTrackSpline` | `Actor` | Closed spline whose construction script generates road slabs and optional barriers; the racing line for AI and progress/lateral queries | Lau Chun Kit (level/checkpoints) |
| `BP_DFCheckpoint` | `Actor` | Ordered gate: trigger box + two poles; reports crossings to the GameMode; respawn transform | Lau Chun Kit |
| `S_DFTireState`, `S_DFRaceResult`, `E_DFRaceEndReason` | struct / enum | Shared data types | Choy Tsz Lok |
| `BP_DFLootBox`, `BP_DFBomb`, `BP_DFProjectile` (Phase 3) | `Actor` | Crates collected on foot; the dropped bomb; the rocket. The inventory lives on `BPC_DFRacer`, item use on `BP_DFVehicle`, item names/caps and the explosion rule on the GameMode (`docs/superpowers/specs/2026-10-30-phase3-items-design.md`) | Chong Tsz Ho |
| `BP_DFDestructible`, `BP_DFExplosiveDamage` (Phase 3) | `Actor`, `DamageType` | Explosives-only rock on a shortcut road; the damage type explosions apply | Lau Chun Kit |
| `E_DFItemType`, `S_DFItemStack` (Phase 3) | enum / struct | Item types; an inventory stack | Choy Tsz Lok |
| `BP_DFVehicleAIController` (Phase 4) | `AIController` | NPC drivers following the track spline, item use, attacks | TBD |

Hooks that other Blueprints or later phases listen to are **Event Dispatchers** (`OnVehicleDamaged`, `OnTireBlown`, `OnVehicleDestroyed`, `OnOccupantEntered/Exited`, `OnCharacterDamaged/Died/Revived`, `OnEnteredVehicle/ExitedVehicle`, `OnFired`, `OnRaceEnded`, `OnRacerRespawned`). Tunables are variables with **Instance Editable** on, under a `Dead Fire|...` category. The GameMode references the `BP_DF*` pawn and controller classes, so visual swaps are a class-default change.

Score and progress data is not kept on `PlayerState` because NPC racers have none; see `BPC_DFRacer`.

Maps under `/Game/DeadFire/Maps/` (`L_TestTrack`) and `/Game/DeadFire/Tests/` (`L_DF_FunctionalTests`, the same track plus the functional test actors).

### 6.1 Enter / exit vehicle flow

- The player always has two pawns: a vehicle and an on-foot character. The GameMode spawns both at race start and stows the character inside the vehicle (hidden, collision off, attached, movement disabled).
- **Enter:** the character's interaction sphere (radius 300 cm) overlaps a vehicle that `CanBeEntered` (no occupant, not destroyed). Press Interact → the controller possesses the vehicle, the character is stowed.
- **Exit:** press Interact while the vehicle is below the exit speed. The vehicle applies the handbrake, the character is placed at the driver-side door (left side, 220 cm out, checked with a capsule sweep at the spot; falls back to the right side and then behind), unhidden, and possessed.
- Both transitions fire event dispatchers (`OnEnteredVehicle`, `OnExitedVehicle`) on both actors.
- NPC vehicles are the same `BP_DFVehicle` class possessed by an AI controller; they never have an occupant character.

### 6.2 Damage plumbing

- `BP_DFVehicle` handles **Event Point Damage** and routes by hit bone: a wheel bone hits that tire's health; anything else hits body health. A tire at 0 health is "blown" and reduces top speed. Body health at 0 marks the vehicle destroyed and fires `OnVehicleDestroyed` (explosion, scoring and respawn are Phase 2/3).
- `BP_DFCharacter` handles **Event Any Damage**; at 0 health it fires `OnCharacterDied` (respawn is Phase 2).
- **Shooting happens both on foot and from the car.** The proposal's on-foot system explicitly includes aiming and shooting with gun traces that hit tires and vehicles, and found items (gun, RPG) are used from the car while driving. So the weapon logic is a reusable `BPC_DFWeapon` component (hitscan: damage, range, cooldown, `Fire(Origin, Direction)`); the character owns one from the start, and Phase 3 mounts one on the vehicle per item. The on-foot fire is real gameplay, not a test harness.

### 6.3 Track tooling and off-track rules

`BP_DFTrackSpline` is an actor with a closed `Spline` component. Its construction script adds one `SplineMesh` component per segment from a road mesh (default: engine basic cube scaled into a slab, `RoadWidth` 1400 cm). The level designer drops one actor, drags spline points, and the road follows.

**Cars may leave the road.** The paper prototype allows "a few seconds off track", opens a second road by destroying a rock or waterfall, and hides secret items in the infield, so the track must not be a walled tube. Side barriers are therefore optional per track actor and **off by default**; walls are placed by hand where the level designer wants them. The tool exposes `GetDistanceAlongTrack(WorldLocation)` (progress, for checkpoints and AI) and `GetLateralDistanceFromTrack(WorldLocation)` (how far off the road a car is, for the Phase 2 off-track timer). A level may contain several track actors (main loop plus shortcut roads); the one flagged `bIsMainTrack` is the lap-scoring line.

## 7. Phases

The proposal's week plan maps to these phases. Each phase ends with a working build.

| Phase | Proposal weeks | Scope |
|---|---|---|
| **1 — Foundation** (done in C++, superseded) | 6–7 | Vehicle driving + camera + HUD, on-foot character, enter/exit, damage plumbing, hitscan, track spline tool, test track level, input, GameMode/State skeleton |
| **2 — Race flow** (done in C++, superseded) | 8–9 | Checkpoints, lap detection, timer + time bonus, score for laps/kills, race end + summary, respawn at last checkpoint, death count, UMG HUD |
| **2B — Blueprint migration** (done 2026-10-22) | 9–10 | Remove the C++ module; rebuild the Phase 1 + 2 feature set in Blueprint on the template Blueprints; Blueprint Functional Tests; playtest checklist. Plan: `docs/superpowers/plans/2026-10-21-blueprint-migration.md` |
| **3 — Items & damage** (done 2026-10-30) | 10–11 | Loot crates off-track (on foot only), three-slot inventory, item use from the car (boost, shield, bomb, gun, RPG), explosions with tire blasts, wreck effects, the explosives-only rock on a shortcut road; 15 more functional tests. Design: `docs/superpowers/specs/2026-10-30-phase3-items-design.md`; plan: `docs/superpowers/plans/2026-10-30-phase3-items.md` |
| **4 — AI** | 11 | NPC drivers following the spline, avoidance, item use, attacking the player, respawn |
| **5 — Menus & meta** | 12 | Main menu, vehicle select with stats, level select, unlocks (SaveGame), pause, summary, audio/VFX polish |
| **6 — Test & ship** | 12–13 | Bug fixing, balance (score, items), packaged Windows build, presentation |

The migration was done by the tooling in about a day, so the proposal's schedule for Phases 3–6 stands. If week 11 arrives with Phase 3 unfinished, the team cuts from the end of Phase 3 (destructible shortcuts first, then RPG) and from Phase 4 (AI item use), not from Phase 5 (the menus are in the flowchart and graded).

## 8. Migration (Phase 2B) acceptance

Replaces the Phase 1 and Phase 2 acceptance lists; the behaviour is the same, the implementation is Blueprint.

- The project opens in the stock UE 4.27.2 editor with no compile prompt and no Visual Studio installed; `comp4900sef/Source/` no longer exists.
- Opening `L_TestTrack` and pressing Play: the player starts in a Sedan on the looped road with four visible gates. W/S/A/D drive, Space handbrake, Tab switches to the in-car camera; the UMG HUD shows score, laps, kills, lives, clock, speed, gear, car health and tires.
- Pressing E while stopped exits the car; the mannequin appears beside the car and walks/runs/jumps with mouse look. Pressing E near the car enters it again. Left mouse on foot fires a hitscan that damages the vehicle.
- Gates credit only in order (+8 s each); crossing the start line after the others completes a lap (+100). A wrecked car or a killed character costs a life and respawns the player in a car at the last gate after 2 s; the third death ends the race with GAME OVER. Staying more than 5 m off every road for 5 s puts the car back at the last gate without costing a life. The clock reaching 0 shows the summary (RACE COMPLETE at 300 points or more, else TIME UP) with working Retry and Quit.
- `tools/run_tests.ps1` runs the Blueprint Functional Tests in `L_DF_FunctionalTests` headless and reports them all passed (24 on 2026-10-22). The playtest checklist (`docs/superpowers/playtest-checklist.md`) is walked once by a person and every line ticked.

Ranking: the flowchart's "first place on this level" compares the player with NPC racers, so race progress lives on each controller's `BPC_DFRacer` and the GameMode ranks all racers by score, then laps, then distance along the track.

## 9. Constraints and risks

- **Generated graphs are code.** A hand edit to a Blueprint that has a generator module is overwritten by the next apply; the README states the rule (change the module and re-apply). The generator emits engine function and pin names that must match UE 4.27 exactly; the apply script fails loudly on any node, link or default that does not arrive, and `tools/bpgen/sig.py` looks up exact declarations. Only the person maintaining the generators needs Visual Studio (to build the plugin once per machine); everyone else opens the project in the stock editor.
- No compile-time checks: a renamed variable or function breaks graphs silently until they are compiled. Rule: compile and save every Blueprint you touch before closing the editor, and keep the Functional Tests green before pushing.
- Blueprint assets are binary: two people editing the same Blueprint cannot merge. Ownership per §6 is strict; the integration owner merges content changes and resolves conflicts by taking one side and redoing the other's edit.
- Vehicle tuning is iterative; the proposal flags it as a key challenge. The migration ships the Sedan template tuning as is **[call]** (the Phase 1 centre-of-mass and differential tweaks are re-applied on `BP_DFVehicle`'s movement component defaults if the car flips in playtests); drifting, collisions and tire-damage feel are Phase 3 work.
- AI driving (Phase 4) is the hardest unknown. The track spline as a shared racing line is chosen now to de-risk it.
- `StarterContent` is git-ignored; the project auto-adds it on first open. Committed content is limited to the template packs.

## 10. Left to the builder

- Exact camera numbers, slab thickness, barrier height, and HUD layout.
- Folder layout under `/Game/DeadFire/` beyond `Blueprints/` and `Maps/`.
- Choice of debug visualisation toggles.
