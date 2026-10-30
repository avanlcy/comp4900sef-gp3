# Dead Fire — Phase 4 (AI Racers) Design Addendum

Date: 2026-10-30
Extends: `2026-10-20-dead-fire-design.md` (§3 core loop, §6 architecture, §7 phase table), `2026-10-21-phase2-race-flow-design.md` (deaths, respawn, ranking, HUD) and `2026-10-30-phase3-items-design.md` (items, explosions). Only what Phase 4 needs is added; nothing earlier changes unless stated.
Status: the project manager asked the agent to proceed straight to the design and plan with its own calls, as in Phase 3. Every decision below that the proposal, flowchart and earlier designs do not settle is an implementer's call, marked **[call]**; the team can overturn any of them in the generator modules (`tools/bpgen/graphs/`) or by changing an Instance Editable value.

The project manager also asked, in the same breath, for the Blueprint generator to drop its author watermark and to produce graphs a person can read in the editor. That is §7 of this document and the first task of the plan, because every Phase 4 graph is produced through it.

## 1. What Phase 4 delivers

Proposal week 11: "NPC drivers following the spline, avoidance, item use, attacking the player, respawn". Concretely:

1. **NPC drivers.** `BP_DFVehicleAIController` (an `AIController` with a `BPC_DFRacer`) drives a `BP_DFVehicle` around the main track spline: it steers at a point ahead on its own lane, slows for corners, reverses out when stuck, and is put back on the track when flipped or stuck for too long.
2. **Avoidance.** Three forward traces; a car or obstacle ahead shifts the driver's lane away from it.
3. **Items.** NPCs never leave their cars, so the GameMode supplies each of them with a random item every so often. They use them with simple rules: shield when hurt, gun or rocket at a car ahead (aim-assisted), bomb when a car is close behind, boost on a straight.
4. **Attacking the player.** When choosing a target for the gun or rocket, an NPC prefers the player's car.
5. **Respawn and race plumbing.** Each racer carries its own pending-respawn timer (several racers can die at once); an NPC's third death never ends the race; an NPC respawns in a car at its last gate, on its own lane; the GameMode ticks every racer, not only player 0.
6. **Ranking you can see.** Every half second the GameMode writes each racer's `Rank` and the `RacerCount`; the HUD shows `POS 2 / 4`; the summary's `Place n of m` now compares the player with real opponents.
7. **Spawning.** `NPCCount` NPCs on a grid behind the start line at race start and on every `RestartRace`. The functional-test level uses a GameMode child with `NPCCount` 0 so the existing 40 tests keep their single-racer world; AI tests spawn and despawn NPCs themselves.
8. **Generator readability** (§7): no author watermark, automatic graph layout, section comments, function descriptions, comment bubbles on key decisions.
9. Functional tests for every rule, README, playtest checklist, base design table rows.

Out of scope: NPCs on foot or collecting crates (they are supplied instead, §3.1); ramming damage (the game has no collision damage); difficulty selection and rubber-banding (Phases 5–6; `NPCCount`, `MaxSpeedKPH` and `NPCSkillSpread` are the knobs); navmesh, behaviour trees or EQS (the track spline is the plan, as the base design chose in §9); NPC voices or name tags.

## 2. The NPC driver (`BP_DFVehicleAIController`)

Parent `/Script/AIModule.AIController`; component `Racer` (`BPC_DFRacer`), so the GameMode's `FindRacer`, scoring, checkpoints, kills and ranking work unchanged. One controller per NPC, spawned by the GameMode (§4.1).

### 2.1 Possession and vehicle inputs

- An AI-possessed pawn has no input component, so the Sedan's `MoveForward`/`MoveRight` axis events never fire and `GetInputAxisValue` reads 0. `BP_DFVehicle` gains `bAIControlled`, `AIThrottle`, `AISteering`, `bAIHandbrake` and `SetAIInput(Throttle, Steering, bHandbrake)`. `TickDriveOverrides` keeps its parked/wrecked branch; otherwise, when `bAIControlled`, it applies the AI values (throttle still scaled by blown tires) instead of the axis.
- `On Possess` on the controller: `CurrentVehicle` = the car, `bAIControlled` true, `LastDriver` = the controller. `On UnPossess`: inputs zeroed with the handbrake on, `bAIControlled` false. The player may enter an NPC's car that `CanBeEntered` (no occupant, not wrecked); the AI then has no pawn and gets a fresh car at its last gate after `NoPawnSeconds` (1 s) without a death being counted. **[call]**

### 2.2 Where it drives: lane and target point

Every tick while the race is active and the car is intact:

- `d` = `MainTrack.GetDistanceAlongTrack(car location)`. Lookahead `L = LookaheadBase + SpeedKPH × LookaheadPerKPH` (1200 cm + 12 cm per km/h → 24 m at 100 km/h **[call]**).
- Target point = the track transform at `WrapDistance(d + L)` moved along that transform's right vector by `LaneOffset + AvoidBias`. `LaneOffset` is fixed per NPC at spawn (alternating −350 / +350 cm **[call]**, so NPCs do not all hold the centre line); `AvoidBias` is §2.4.
- `BP_DFTrackSpline` gains `WrapDistance(Distance)` (modulo the length on a closed track, clamped on an open one) and `GetDirectionAtDistance(Distance)`.
- NPCs follow the **main** track only; they never take the shortcut. **[call]**

### 2.3 Steering and speed

- Steering = `Clamp(NormalizeAxis(LookAtYaw(car → target) − car yaw) / SteerFullLockDegrees, −1, 1)`, `SteerFullLockDegrees` 35 **[call]**.
- Corner severity = `Clamp(angle between the track direction at d and at d + CornerLookahead (2500 cm) / CornerAngleFull (60°), 0, 1)`.
- Target speed = `Lerp(MaxSpeedKPH 110, CornerSpeedKPH 45, severity) × SpeedScale` **[call]**. `SpeedScale` is set per NPC at spawn to `1 − Random(0, NPCSkillSpread 0.1)`, so the field spreads out.
- Throttle: `1.0` below the target, `−0.5` (brake) more than `BrakeMarginKPH` (10) above it, `0.2` in between; capped at `0.3` while steering harder than 0.8 above the corner speed. **[call]**
- The computations are pure functions on the controller (`ComputeSteering(FromLocation, FromYaw, Target)`, `ComputeTargetSpeed(Severity)`, `ComputeThrottle(SpeedKPH, TargetKPH, Steering)`), so the tests pin them without physics.

### 2.4 Avoidance

Three line traces on the Visibility channel from 300 cm ahead of the car's centre at 80 cm up, `AvoidanceDistance` (1500 cm) long: straight ahead and ±`AvoidanceAngle` (20°) about the car's up axis, the car itself ignored. **[call]**

- Centre blocked: bias toward the side whose trace is free (left blocked → +`AvoidanceOffset` 350 cm, i.e. right); both free or both blocked → keep the current side (right when none).
- Only one side blocked: half an offset the other way.
- Nothing hit: bias 0.
- `AvoidBias` interpolates toward that at `AvoidInterpSpeed` (3 per second), so lane changes are smooth. Anything that blocks Visibility counts (cars, the rock, the arena props); bombs and crates are overlap-only and are driven through.

### 2.5 Stuck and flipped

- Stuck: speed under `StuckSpeedKPH` (5) while commanding throttle above 0.5 for `StuckSeconds` (2.5) → reverse for `ReverseSeconds` (1.5) with inverted steering, then try again. Cumulative stuck time over `GiveUpSeconds` (10) → `GameMode.RespawnRacer(self)`; no death is counted (like the off-track rule). **[call]**
- Flipped: up vector Z below 0.3 for `FlipSeconds` (2) → `RespawnRacer`, no death. **[call]**
- The existing off-track rule (§4 of the Phase 2 design) applies to NPCs unchanged: 5 s more than 5 m off every road puts them back at their last gate.

### 2.6 Race end

When `bRaceActive` is false the controller sets throttle and steering to 0 with the handbrake on and stops thinking about items; `RestartRace` replaces every NPC anyway.

## 3. Items and attacks

### 3.1 Supply

The GameMode grants every NPC racer that has a free slot one random item (Boost..RPG, that type's box charges) every `AIItemInterval` (20 s) **[call]**, the first one 20 s into the race; `GrantNPCItems()` is callable for tests. `AIItemInterval` 0 turns it off. Items reach NPCs through the same `GrantItem` as crates, so caps and logs apply.

### 3.2 Use

Every `ItemThinkInterval` (0.5 s) **[call]** the controller runs `ThinkItems()`; the first rule that fires uses one charge through `BPC_DFRacer.SelectType(Type)` and the vehicle's existing `UseSelectedItem`:

1. **Shield** held, car health below `ShieldHealthFraction` (0.5) of max, not already shielded.
2. **RPG**, then **Gun**, held and a target car ahead: within `RPGRange` (4000 cm, and beyond `RPGMinRange` 1200 cm so the 6 m blast never reaches the shooter) / `GunRange` (6000 cm) and inside `AimCone` (dot ≥ 0.96, about 16°). The player's car is taken when it qualifies, otherwise the nearest qualifying car (`bPreferPlayer`) **[call]**. The car's `AimTarget` is set for the shot, so the gun trace and the rocket leave the muzzle toward the target's centre instead of straight ahead (a turret with 16° of traverse); players never set `AimTarget`, their shots stay straight. **[call]**
3. **Bomb** held and a car within `BombRange` (1500 cm) behind the car (dot ≤ −0.5).
4. **Boost** held, last corner severity below `BoostMaxSeverity` (0.2), speed below the target and no boost running.

Targets are intact `BP_DFVehicle`s other than the controller's own that are **being driven** (a valid controller): the player's car while the player is in it, other NPCs, and the parked target car (a pawn placed in a level gets the engine's default AI controller). A car the player has parked to go on foot has no controller and is never a target, so leaving the car to loot a crate does not cost a life to a passing NPC (the base design's anti-goal; a Phase 2 rule credits a parked car's wreck to its last driver). **[call]** Kill credit and the +50 flow through the Phase 2/3 damage path unchanged; an NPC that wrecks the player's car costs the player a life like any other wreck. A rocket aimed at another car can still splash a parked car within its 6 m radius; that stands. **[call]**

`BPC_DFRacer` gains `HasType(Type)` and `SelectType(Type) -> bool` for this.

## 4. GameMode changes

### 4.1 Spawning

- `Dead Fire|AI` on `BP_DFRaceGameMode`: `NPCCount` 3 **[call]**, `NPCRowSpacing` 800 cm, `NPCColumnOffset` 350 cm, `NPCSkillSpread` 0.1, `AIItemInterval` 20 s, `RankInterval` 0.5 s.
- `SpawnNPCs(Count)` runs at BeginPlay after `CollectLevelActors` and inside `RestartRace`, when the level has a main track. Start-line distance `d0` = the main track distance of gate 0 (0 when the level has no gates). NPC `k` (0-based) is spawned 50 cm above the track transform at `WrapDistance(d0 − NPCRowSpacing × (k + 1))`, moved sideways by `NPCColumnOffset` (left for even `k`, right for odd), facing along the road; a `BP_DFVehicleAIController` is spawned and possesses it; the racer's `RacerName` is `NPC k+1`, the controller's `LaneOffset` is that lateral offset and its `SpeedScale` as in §2.3. NPCs drive `BP_DFVehicle` (the Phase 2 note about a per-racer vehicle class waits for Phase 5's vehicle select). **[call]**
- `DespawnNPCs()` unregisters every AI controller and destroys its car; the controller dies with its pawn (a Blueprint cannot destroy a controller directly: `AController::K2_DestroyActor` is a no-op in UE 4.27, and a controller without a PlayerState is destroyed by the engine when its pawn is). A controller that has no car is given a throwaway pawn to die with. For the same reason an AI respawn possesses the new car **before** destroying the wreck. `RestartRace` calls `DespawnNPCs` then `SpawnNPCs(NPCCount)`.
- `BP_DFTestGameMode` (`/Game/DeadFire/Tests/`, a child of `BP_DFRaceGameMode` with `NPCCount` 0) is the default GameMode of `L_DF_FunctionalTests`; `L_TestTrack` keeps `BP_DFRaceGameMode` and its three NPCs. **[call]**

### 4.2 Registration, ticking, ranking

- `RacerControllers: array<Controller>` with `RegisterRacer(C)` / `UnregisterRacer(C)`; the player is registered in `HandleStartingNewPlayer`, NPCs in `SpawnNPCs`. `GetRankedRacers` ranks these (score, then laps, then distance, unchanged). The GameMode Tick runs `TickRacer` (progress, off-track) and the respawn check for each of them.
- `UpdateRanks()` every `RankInterval`, at `RestartRace` and when a racer is registered: writes 1-based `Rank` to each `BPC_DFRacer` and `RacerCount` to `BP_DFRaceGameState`.

### 4.3 Deaths and respawn

- `BPC_DFRacer.RespawnDueTime` (−1 = none) replaces the GameMode's single `PendingRespawnRacer` / `RespawnDueTime` pair. `HandleRacerDeath`: duplicate deaths of one racer while its respawn is pending are still ignored; a **player** at `MaxDeaths` ends the race (unchanged); an **NPC** always schedules a respawn after `RespawnDelay`. `EndRace` clears every pending respawn.
- `RespawnRacer(C)` for an AI controller: its car intact → `TeleportAndStop` at the respawn transform; wrecked or missing → a fresh `BP_DFVehicle` there, the wreck destroyed, the controller possesses it; `LastDriver`, `ClearEffects`, `OffTrackSeconds` 0 and `OnRacerRespawned` as for the player. The respawn point is `GetRespawnTransform(C)` shifted along its right vector by the controller's `LaneOffset`, so an NPC coming back at gate 0 does not land on the player. **[call]** The player path is unchanged.

## 5. HUD

`WBP_DFRaceHUD` gains `PositionText` under `LIVES`: `POS <Rank> / <RacerCount>` (`Rank` shown as 1 until the first ranking pass). **[call]** The summary's `Place n of m` already reads `S_DFRaceResult`.

## 6. Rules summary (tunables; owner in brackets)

| Rule | Value |
|---|---|
| NPCs per race / row spacing / column offset [GameMode] | 3 / 800 cm / 350 cm |
| NPC skill spread (speed scale 1 − Random(0, spread)) [GameMode] | 0.1 |
| NPC item interval / rank interval [GameMode] | 20 s / 0.5 s |
| Max / corner speed [AI] | 110 / 45 km/h |
| Lookahead base / per km/h / corner lookahead / full-slowdown angle [AI] | 1200 cm / 12 cm / 2500 cm / 60° |
| Full steering lock angle / brake margin [AI] | 35° / 10 km/h |
| Avoidance distance / angle / offset / interpolation [AI] | 1500 cm / 20° / 350 cm / 3 per s |
| Stuck speed / seconds / reverse seconds / give-up seconds [AI] | 5 km/h / 2.5 s / 1.5 s / 10 s |
| Flip seconds / no-pawn seconds [AI] | 2 s / 1 s |
| Item think interval [AI] | 0.5 s |
| Gun range / RPG range / RPG minimum range, aim cone (dot) [AI] | 6000 cm / 4000 cm / 1200 cm, 0.96 |
| Bomb range (behind, dot ≤ −0.5) [AI] | 1500 cm |
| Shield health fraction / boost max severity [AI] | 0.5 / 0.2 |
| Respawn delay (shared with the player) [GameMode] | 2 s |

## 7. Generator readability

The project manager's request: no author watermark, and graphs a human can read in the editor. Applies to every generated Blueprint, re-applied in full.

1. **No watermark.** The `Generated by tools/bpgen/graphs/<module>.py ...` comment boxes are removed from every graph. The README already states that these Blueprints are generated and where the modules live.
2. **Sections instead.** In an event graph each event's chain (the event, everything it executes, and the pure nodes feeding them) sits in a comment box whose title says what it does (`Tick: drive overrides and item effects`, `Point damage: route by hit bone`). Function graphs get a box titled with the function's one-line description, which is also written into the function's **Description** (the tooltip in My Blueprint and on call nodes) through a new plugin call. New functions carry a description; existing ones get the one-liner their module comment already has.
3. **Automatic layout.** Positions are computed from the graph instead of creation order: exec flow runs left to right in columns; the main path (`then`, `LoopBody`, cast success) keeps its row and every other branch starts a new row below; a pure node sits to the left of and just below the node that consumes it, in depth columns; column widths and row heights come from estimated node sizes, so nothing overlaps; a function's entry node stays at the far left and its result node is moved to the far right (new plugin call). The generator checks its own output for overlapping nodes.
4. **Comment bubbles** on key decision nodes (`g.note(node, "stuck for 2.5 s?")`), used in the new AI module and where a branch is not obvious.
5. **Plugin.** `SetNodePosition(Blueprint, Graph, Node, X, Y)` and `SetFunctionDescription(Blueprint, Function, Description)` are added to `DFBlueprintAuthoring`, the plugin rebuilt with `tools/build_authoring_plugin.ps1` and reinstalled with `tools/restart_editor.ps1 -InstallPlugin`. The runner uses both when present and skips them on an older plugin. The hand-paste fallback is unchanged (positions travel in the text).
6. **Check.** The full re-apply and the full test suite stay green (layout changes nothing functional); `grep "Generated by" comp4900sef/Script/paste` finds nothing; screenshots of two graphs (one event graph, one function) are taken in the editor and looked at.

Node names (`DFN_...`) are internal and never shown; they stay.

## 8. Tests (`tools/bpgen/graphs/tests_ai.py`, `FT_DFAI_*`)

Headless frames are about 0.4 s and physics advances at most 1/30 s per frame, so no test depends on a car covering distance; driving is pinned through the controller's pure functions and its last inputs.

- `VehicleTakesAIInput`: a car possessed by the controller stores and applies `SetAIInput`, and parks (handbrake on) when unpossessed.
- `SpawnGridAndRanking`: `SpawnNPCs(3)` → three AI controllers, each possessing an intact `BP_DFVehicle` on a track, named `NPC 1..3`; `GetRankedRacers` has 4; after an NPC's score is set to 200 and `UpdateRanks`, the player's `Rank` is 2, `RacerCount` 4, the HUD reads `POS 2 / 4`; `DespawnNPCs` → none left, `RacerCount` 1.
- `SteeringAndSpeedMath`: `ComputeSteering` positive for a target to the right and negative to the left, 0 straight ahead, ±1 at the lock angle; `ComputeTargetSpeed` 110 at severity 0 and 45 at 1 (scale 1); `ComputeThrottle` 1 below, −0.5 far above, and the hard-steer cap.
- `DrivesTowardItsLane`: one NPC spawned on the track reports throttle 1 and small steering at its spawn; moved 3 m left of its lane it steers right on the next tick; moved onto the lane facing 60° off the road it steers back.
- `AvoidsBlockedSide`: an AI car on open ground with a parked car ahead-left reports a positive avoidance bias, ahead-right negative, none 0.
- `UsesItemsAtTargets` (deterministic, `ThinkItems` called directly): shield at 30 health; gun at the player's car 8 m ahead (its health drops 15, the stack 8 → 7); bomb with the player's car 6 m behind; boost on a straight (`LastSeverity` 0); rocket at the player's car 15 m ahead explodes on it, and no rocket at 8 m; with the player on foot and the parked car 8 m ahead the gun stays holstered; nothing is used once the race is over.
- `RespawnsWithoutEndingRace`: an NPC with 2 deaths is wrecked; 2.5 s later the race is still active, the NPC has 3 deaths and drives an intact car near gate 0, the player's deaths are unchanged.
- `TwoRacersRespawnTogether`: two NPCs wrecked in the same frame both return 2.5 s later.
- `FlippedCarRespawns`: an NPC car turned onto its roof is upright at its gate about 3.5 s later, no death counted.
- `RestartRespawnsNPCs`: with `NPCCount` 0 a restart removes spawned NPCs; with `NPCCount` 2 it spawns two; back to 0.
- `ItemSupply`: `GrantNPCItems` fills one slot of each NPC and none of the player.
- `RaceEndStopsDriving`: after `EndRace` the NPC's throttle is 0 with the handbrake on.
- The existing 40 tests pass unchanged (the test level has no NPCs).

## 9. Level, docs, hooks

- `df_build_test_track.py`: `L_DF_FunctionalTests` gets `BP_DFTestGameMode`; nothing else is placed (NPCs spawn at runtime).
- README (current state, controls unchanged, logic table rows for the AI controller and the test GameMode, tests paragraph, generator paragraph for the layout and sections), playtest checklist lines for racing against NPCs, base design §6/§7 rows, this phase's plan with its execution record.
- Hooks for Phase 5: `OnRacerRespawned` fires for NPCs too; `RacerName`, `Rank` and `RacerCount` are what a results board needs; `NPCCount` and `MaxSpeedKPH` are the difficulty knobs.

## 10. Phase 4 acceptance

- `tools/run_tests.ps1` green with the `FT_DFAI_*` tests and the existing 40; `df_verify_blueprints.py` `VERIFY PASSED`; `grep "Generated by" comp4900sef/Script/paste` empty.
- Playing `L_TestTrack`: three NPC Sedans start behind the player, drive the loop on their own lanes at racing speed, slow for corners, go round the player and each other, come back after a wreck, get out when stuck; `POS n / 4` on the HUD and `Place n of 4` on the summary; NPCs shoot the player from behind and drop bombs in front of them; a flipped NPC is back on the road within a few seconds.
- Opening `BP_DFVehicleAIController` and `BP_DFRaceGameMode` in the editor: no `Generated by` boxes, titled sections, left-to-right flow, descriptions on functions, no overlapping nodes.

## 11. Left to the builder

Exact node size estimates and spacing of the layout; the colour of section boxes; how `ThinkItems` orders its traces; whether `SpawnNPCs` and `RespawnRacer` share a placement helper; log line wording (`DF: npc spawned ...`, `DF: npc item ...`); test world set-up details; the order of the new generator modules.
