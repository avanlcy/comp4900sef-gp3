# Dead Fire (死火) — Game Design & Engineering Design

Date: 2026-10-20
Source: "Group 3_4900SEF_Project Proposal.docx" (COMP 4900SEF, Group 3) plus the flowchart and paper prototype attached to it.
Status: Phase 1 approved for build by the project manager's request ("brainstorm and implement in phases"). Items marked **[call]** are engineering decisions made by the implementer, not stated in the proposal; the team can overturn any of them.

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
- **C++ game module + Blueprint subclasses.** The proposal says "built on the Vehicle and Third Person Blueprint templates". The game-logic foundation is written in C++ instead, because:
  - Blueprint graphs cannot be authored by the automation tooling used to build this project (UE 4.27's Python API and the MCP server only create assets and components, not graph nodes).
  - C++ gives compile-time checks and a stable API for six people to work against.
  - Every C++ class is subclassed by a Blueprint under `/Game/DeadFire/Blueprints/`, and all tunables and hooks are exposed as Blueprint-editable properties and events, so teammates who prefer Blueprints extend the Blueprint children without touching C++.
  - Consequence: every team member needs Visual Studio 2019 or 2022 with the "Desktop development with C++" workload to open the project. This is the single biggest decision the team should confirm.
- **Vehicles: PhysX Vehicles** (`AWheeledVehicle`, `UWheeledVehicleMovementComponent4W`), which is the UE4.27 default. Chaos Vehicles is experimental in 4.27 and is not used.
- **Input: classic UE4 action/axis mappings** in `DefaultInput.ini`. Enhanced Input is experimental in 4.27.
- **Content: free only.** Engine template packs copied into the project (Vehicle Sedan, Mannequin, Geometry, VehicleAdv arena meshes/materials/engine sounds) and the Starter Content pack. Later phases may import CC0 packs (e.g. Kenney, Quaternius) via the editor's import pipeline.
- Editor plugins enabled in the `.uproject`: `PhysXVehicles` (runtime), `PythonScriptPlugin` and `EditorScriptingUtilities` (editor-only; used by the automation and harmless for teammates).

## 6. Architecture

Class prefix `DF`. Everything lives in the `comp4900sef` module under `comp4900sef/Source/comp4900sef/`.

| Class | Parent | Responsibility | Owner (from proposal) |
|---|---|---|---|
| `ADFVehiclePawn` | `AWheeledVehicle` | Driving, chase/in-car camera, body + per-tire health, enter/exit, damage events | Fung Ming Chu (physics/driving/enter-exit), Chong Tsz Ho (vehicle health) |
| `UDFWheelFront`, `UDFWheelRear` | `UVehicleWheel` | Wheel/tire setup | Fung Ming Chu |
| `ADFCharacter` | `ACharacter` | On-foot movement, camera, interact (enter vehicle), fires its weapon component, health | Cheung Tsz Hin Anderson (weapons/shooting) |
| `UDFWeaponComponent` | `UActorComponent` | Hitscan weapon: damage, range, cooldown, fire from an origin/direction. Owned by the character now; mounted on vehicles for gun/RPG items in Phase 3 | Cheung Tsz Hin Anderson |
| `ADFPlayerController` | `APlayerController` | Possession switching between vehicle and character, respawn requests; owns a `UDFRacerComponent` | Lee Chun Yin (integration) |
| `UDFRacerComponent` | `UActorComponent` | Per-racer race state (score, laps, kills, deaths, next checkpoint). Lives on the **controller** (player or AI) so it survives vehicle respawns and lets the GameMode rank NPCs against the player for "first place" | Choy Tsz Lok |
| `ADFRaceGameMode` | `AGameModeBase` | Spawns player vehicle + stowed on-foot character, race rules/tunables, lap/checkpoint/kill hooks, ranking, end-of-race | Choy Tsz Lok (GameMode/scoring) |
| `ADFRaceGameState` | `AGameStateBase` | Remaining time, race active flag | Choy Tsz Lok |
| `ADFHUD` | `AHUD` | Phase 1 canvas HUD (speed, gear, health, prompts, score, time). Phase 2 replaces with UMG | Lee Chun Yin |
| `ADFTrackSpline` | `AActor` | Closed spline that auto-generates road slabs and side barriers; also the racing line for AI and progress measurement | Lau Chun Kit (level/checkpoints) |
| `ADFCheckpoint` (Phase 2) | `AActor` | Ordered trigger volumes; lap detection; time bonus | Lau Chun Kit |
| `ADFItemBase`, `ADFLootBox` (Phase 3) | `AActor` | Pickups off-track, inventory entries, use-on-vehicle effects | Chong Tsz Ho |
| `ADFVehicleAIController` (Phase 4) | `AAIController` | NPC drivers following the track spline, item use, attacks | TBD |

Blueprint children (created by the automation, saved under `/Game/DeadFire/Blueprints/`): `BP_DFVehicle`, `BP_DFCharacter`, `BP_DFRaceGameMode`, `BP_DFPlayerController`, `BP_DFHUD`, `BP_DFTrackSpline`. The GameMode Blueprint references the Blueprint pawn/character classes so visual swaps never require C++.

Score and progress data is not kept on `APlayerState` because NPC racers have none; see `UDFRacerComponent`.

Maps under `/Game/DeadFire/Maps/`. Phase 1 ships `L_TestTrack`.

### 6.1 Enter / exit vehicle flow

- The player always has two pawns: a vehicle and an on-foot character. The GameMode spawns both at race start and stows the character inside the vehicle (hidden, collision off, attached, movement disabled).
- **Enter:** the character's interaction sphere (radius 300 cm) overlaps a vehicle that `CanBeEntered()` (no occupant, not destroyed). Press Interact → the controller possesses the vehicle, the character is stowed.
- **Exit:** press Interact while the vehicle is below the exit speed. The vehicle applies the handbrake, the character is placed at the driver-side door (left side, 220 cm out, ground-checked via `FindTeleportSpot`; falls back to the right side and then behind), unhidden, and possessed.
- Both transitions fire Blueprint events (`OnEnteredVehicle`, `OnExitedVehicle`) on both actors.
- NPC vehicles are the same `ADFVehiclePawn` class possessed by an AI controller; they never have an occupant character.

### 6.2 Damage plumbing

- `ADFVehiclePawn::TakeDamage` routes point damage by hit bone: a wheel bone hits that tire's health; anything else hits body health. A tire at 0 health is "blown" and reduces top speed. Body health at 0 marks the vehicle destroyed and fires `OnVehicleDestroyed` (explosion, scoring and respawn are Phase 2/3).
- `ADFCharacter::TakeDamage` reduces health; at 0 fires `OnCharacterDied` (respawn is Phase 2).
- **Shooting happens both on foot and from the car.** The proposal's on-foot system explicitly includes aiming and shooting with gun traces that hit tires and vehicles, and found items (gun, RPG) are used from the car while driving. So the weapon logic is a reusable `UDFWeaponComponent` (hitscan: damage, range, cooldown, `Fire(Origin, Direction)`); the character owns one from Phase 1, and Phase 3 mounts one on the vehicle per item. The Phase 1 on-foot fire is real gameplay, not a test harness.

### 6.3 Track tooling and off-track rules

`ADFTrackSpline` is a closed `USplineComponent`. In `OnConstruction` it builds one `USplineMeshComponent` per segment from a road mesh (default: engine basic cube scaled into a slab, `RoadWidth` 1400 cm). The level designer drops one actor, drags spline points, and the road follows.

**Cars may leave the road.** The paper prototype allows "a few seconds off track", opens a second road by destroying a rock or waterfall, and hides secret items in the infield, so the track must not be a walled tube. Side barriers are therefore optional per track actor and **off by default**; walls are placed by hand where the level designer wants them. The tool exposes `GetDistanceAlongTrack(WorldLocation)` (progress, for checkpoints and AI) and `GetLateralDistanceFromTrack(WorldLocation)` (how far off the road a car is, for the Phase 2 off-track timer). A level may contain several track actors (main loop plus shortcut roads); the one flagged `bIsMainTrack` is the lap-scoring line.

## 7. Phases

The proposal's week plan maps to these phases. Each phase ends with a working build.

| Phase | Proposal weeks | Scope |
|---|---|---|
| **1 — Foundation** (this session) | 6–7 | C++ module, vehicle driving + camera + HUD, on-foot character, enter/exit, damage plumbing, hitscan, track spline tool, test track level, input, GameMode/State skeleton |
| **2 — Race flow** | 8–9 | Checkpoints, lap detection, timer + time bonus, score for laps/kills, race end + summary, respawn at last checkpoint, death count, UMG HUD |
| **3 — Items & damage** | 10 | Loot boxes off-track, inventory, item use from vehicle (boost, shield, bomb/mine, gun, RPG), tire penalties, vehicle destruction, destructible rock/waterfall shortcuts |
| **4 — AI** | 11 | NPC drivers following the spline, avoidance, item use, attacking the player, respawn |
| **5 — Menus & meta** | 12 | Main menu, vehicle select with stats, level select, unlocks (SaveGame), pause, summary, audio/VFX polish |
| **6 — Test & ship** | 12–13 | Bug fixing, balance (score, items), packaged Windows build, presentation |

## 8. Phase 1 acceptance

- The project compiles as a C++ project (Development Editor) with no errors.
- Opening `L_TestTrack` and pressing Play: the player starts in a Sedan on a looped road with barriers. W/S/A/D drive, Space handbrake, Tab switches to the in-car camera, the HUD shows speed and gear.
- Pressing E while stopped exits the car; the mannequin appears beside the car and walks/runs/jumps with mouse look. Pressing E near the car enters it again.
- Left mouse on foot fires a hitscan that damages the vehicle (visible in the HUD when back inside).
- All of the above verified by an automated Play-In-Editor test (`DeadFire.PIE.DriveExitFireEnter`) that starts a real play session and injects the actual key bindings (W, Space, E, left mouse) through the player controller, plus screenshots. The regression suite the team keeps green is the set of editor automation tests (`DeadFire.*`); the unit-level tests spawn their own actors and do not depend on `L_TestTrack`.

Ranking: the flowchart's "first place on this level" compares the player with NPC racers, so race progress lives on each controller's `UDFRacerComponent` and the GameMode ranks all racers by score, then laps, then distance along the track.

## 9. Constraints and risks

- Team must install the C++ toolchain (see §5). This decision was taken without the team present and is the first thing to confirm with them. Mitigations built in: the C++ surface is kept small (about ten classes) and everything tunable or extensible is exposed to Blueprint, so only the one or two people maintaining the foundation need to write C++; everyone else works in Blueprint children. If a teammate cannot install Visual Studio, a built `Binaries/Win64/UE4Editor-comp4900sef.dll` can be shared out of band so the editor opens without compiling. If the team rejects C++ outright, the C++ classes become a specification for hand-built Blueprints and the schedule slips by roughly a week.
- Vehicle tuning is iterative; the proposal flags it as a key challenge. Phase 1 ships the Sedan template tuning plus a lower centre of mass and 4WD limited-slip differential **[call]**; drifting, collisions and tire-damage feel are Phase 3 work.
- AI driving (Phase 4) is the hardest unknown. The track spline as a shared racing line is chosen now to de-risk it.
- `StarterContent` is git-ignored; the project auto-adds it on first open. Committed content is limited to the template packs.

## 10. Left to the builder

- Exact camera numbers, slab thickness, barrier height, and HUD layout.
- Folder layout under `/Game/DeadFire/` beyond `Blueprints/` and `Maps/`.
- Choice of debug visualisation toggles.
