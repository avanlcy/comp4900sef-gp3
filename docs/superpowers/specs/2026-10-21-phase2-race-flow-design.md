# Dead Fire — Phase 2 (Race Flow) Design Addendum

Date: 2026-10-21
Extends: `2026-10-20-dead-fire-design.md` (§3 core loop, §4 rules, §6 architecture, §7 phase table). This document only adds what Phase 2 needs; nothing in the base design is changed unless stated.
Status: the project manager asked for Phase 2 to start without a question round, so every decision below that the proposal and flowchart do not settle is an implementer's call, marked **[call]**. The team can overturn any of them in the Blueprint children or by asking for a C++ change.

**Revision 2026-10-21:** the project moved from C++ to Blueprint (base design §5). The rules in §2–§5 and §7 stand as written; the class names (`ADF*`, `UDF*`) now mean the corresponding Blueprints (`BP_DF*`, `BPC_DF*`) from the base design §6. §6 (C++ widgets with a snapshot struct) is superseded: the HUD and summary are Widget Blueprints built in the designer and read the controller and pawn directly; the layout and copy in §6 still apply. §9's C++ test suite is replaced by Blueprint Functional Tests. See `docs/superpowers/plans/2026-10-21-blueprint-migration.md`.

## 1. What Phase 2 delivers

Proposal weeks 8–9: "checkpoints, scoring, race flow, basic HUD". Concretely:

1. Ordered checkpoints on the track; crossing the start line after all of them completes a lap.
2. The clock and time bonus (built in Phase 1) now driven by real checkpoint crossings.
3. Death and respawn: a wrecked car or a killed character respawns the player, in a car, at the last checkpoint; the death count ends the race at the limit.
4. An off-track timer: a car that stays off the roads for too long is put back at the last checkpoint.
5. Race end with a summary screen (time up, pass/fail, game over) and Retry / Quit.
6. The Phase 1 canvas HUD replaced by a UMG HUD.

Out of scope (later phases): item effects, destructible shortcuts (3); NPC racers, AI respawn (4); main menu, vehicle select, unlocks, pause menu, audio/VFX polish (5). Phase 2 hooks for those are listed in §8.

## 2. Checkpoints and laps

- `ADFCheckpoint` is an actor with a box trigger across the road and two visible poles at the road edges. Each has an integer `CheckpointIndex`; index 0 is the start/finish line. A level needs at least two checkpoints for laps to count. **[call]**
- Only vehicles trigger checkpoints; a player on foot cannot score laps. **[call]** The vehicle's racer is its controller, or `LastDriver` for a parked car (Phase 1 rule).
- Each racer tracks `NextCheckpointIndex` (starts at 1 because every racer starts on the line) and `LastCheckpoint`. A crossing counts only when the checkpoint's index equals the racer's next index, so driving backwards, skipping gates or rolling back and forth over one gate never credits. **[call]**
- Crossing an expected non-zero gate: the racer advances and, if it is the player, the clock gains `CheckpointTimeBonus` (+8 s). Crossing the expected start line: a lap is completed (+100, laps + 1), the player also gets the +8 s (the line is a checkpoint too **[call]**), and the next index returns to 1.
- Nothing is credited once the race is over.
- The test track gets four checkpoints at 0 %, 25 %, 50 % and 75 % of the main spline, placed by the level-building script. **[call]**

## 3. Death, respawn, death limit

- A death is the player's car being destroyed (driven or parked: it belongs to the last driver, Phase 1 rule) or the on-foot character's health reaching 0. The vehicle and character report these to the GameMode themselves, so nobody has to wire a delegate.
- After `RespawnDelay` (2 s **[call]**) the player is respawned **in a car** at the respawn point: `LastCheckpoint`, else checkpoint 0, else the player start. If the current car is intact (off-track case) it is teleported there and its velocity zeroed; if it is wrecked, a fresh car of the GameMode's default pawn class is spawned and the wreck removed. The character is revived if dead, pulled out of a wreck if trapped, stowed in the car, and the controller possesses the car. Blueprint event `OnRacerRespawned` for effects.
- A wrecked car no longer drives (throttle and steering ignored) and a dead character no longer walks or fires; both were deferred Phase 1 review items.
- `MaxDeaths` is 3: the race ends with **game over** the moment the player's death count reaches it (the third death is not respawned). **[call]** The flowchart's "exceeds maximum" is read as "no lives left".
- NPC racers (Phase 4) get the death count now; their respawn is Phase 4.

## 4. Off-track timer

- The paper prototype allows "a few seconds off track". Rule: while the player is **driving** a car that is farther than `OffTrackMargin` (500 cm **[call]**) beyond the edge of every track spline in the level (main loop and shortcut roads alike), `OffTrackSeconds` accumulates; back on any road it resets to 0. At `OffTrackGraceSeconds` (5 s **[call]**) the player is respawned at the last checkpoint **without** counting a death — leaving the road costs progress, not a life. **[call]**
- On foot the timer never runs, so parking beside the road and exploring the infield is free. Re-entering a car that is off the road restarts the timer from 0.
- The HUD shows a "RETURN TO TRACK" countdown while the timer runs.
- A level with no track spline never penalises anyone.

## 5. Race end and summary

- The race ends on **time up** (clock hits 0) or **death limit**. The GameState records the reason, whether the player passed (`Score >= ScoreRequirement`, time-up only), the player's rank among all racers (`GetRankedRacers`, 1-based) and the racer count.
- At the end: scoring, checkpoints, respawns and the off-track timer stop; the player's pawn input is disabled (the car rolls to a stop); the mouse cursor appears and the summary widget is shown.
- Summary copy **[call]**: title `RACE COMPLETE` (passed), `TIME UP` (time up, score below the requirement) or `GAME OVER` (death limit); a line `Place 1 of 1`; a line `Score 250 / 300    Laps 2    Kills 1    Deaths 0`; buttons `RETRY` (reloads the current level) and `QUIT` (quits the game). Phase 5 replaces Quit with "back to menu" and adds the first-place vehicle unlock behind the same `bPassed`/rank data.

## 6. UMG HUD

- UE 4.27's Python cannot author Widget Blueprints, so the HUD and summary are C++ `UUserWidget` classes that build their own widget tree at runtime when no Blueprint designer tree is present. Every element is a `BindWidgetOptional` property, so a teammate can later make a Widget Blueprint child of either class, lay it out in the designer with the same element names, and set it on `BP_DFHUD` — the C++ keeps feeding the data. **[call]**
- Data flows through one snapshot struct captured from the player controller once per frame (score, lap, kills, lives, time, speed, gear, car health, tires, character health, prompts, warnings, checkpoint flash). The snapshot is the testable surface.
- Layout **[call]**: top-left `SCORE 150` / `LAPS 2` (completed laps) / `KILLS 1` / `LIVES 2`; numbers never use digit grouping (`SCORE 1500`); top-centre clock `1:13`, red under 10 s; bottom-right (in a car) `87 km/h` and `GEAR 3` (`R` in red); bottom-left a health bar with `CAR 80 / 100` and `TIRES [30] [X] [30] [30]`, or `HEALTH 100 / 100` on foot; a `+` crosshair on foot only; the prompt line at 72 % height (`[E] Exit vehicle`, `Stop to exit  [E]`, `No room to exit`, `[E] Enter vehicle`); a warning line at 40 % height (`RETURN TO TRACK  4.2`, `WRECKED`, `YOU DIED`, and `CHECKPOINT  +8 s` for 1.5 s after a gate).
- `ADFHUD` stays the HUD class (and `BP_DFHUD` its child) but no longer draws on the canvas: it creates the HUD widget at start and the summary widget at race end.

## 7. Rules summary (tunables on `BP_DFRaceGameMode` unless stated)

| Rule | Value |
|---|---|
| Race time limit / checkpoint bonus / lap / kill points | 120 s / +8 s / +100 / +50 (Phase 1) |
| Max deaths (game over when reached) | 3 |
| Respawn delay | 2 s |
| Off-track margin beyond the road edge | 500 cm |
| Off-track grace | 5 s |
| Checkpoint trigger half-extents (on `BP_DFCheckpoint`) | 100 × 1400 × 250 cm |
| Checkpoint pole offset from centre line | 700 cm |
| Respawn height above the checkpoint | 50 cm |
| Checkpoint flash on the HUD | 1.5 s |

## 8. Hooks left for later phases

- Phase 3: `ADFVehiclePawn::DestroyVehicle` now notifies the GameMode; explosion effects go on `OnVehicleDestroyed`. Items that teleport or heal can call `RespawnRacer` / `Revive`.
- Phase 4: every controller with a `UDFRacerComponent` is ticked for distance and off-track; AI respawn is `RespawnRacer(Controller)` with a vehicle in `GetPawn()`.
- Phase 5: `FDFRaceResult` on the GameState carries everything the unlock and the menus need; the summary's Quit becomes "Menu".

## 9. Phase 2 acceptance

- Headless suite `tools/run_tests.ps1` green, including a new Play-In-Editor test that drives through a checkpoint (clock gains 8 s), wrecks the car (death counted, fresh car at that checkpoint with the character inside), is put back on the track after staying off it (no death), and sees the summary when the clock is forced to zero.
- Playing `L_TestTrack`: four visible gates; the UMG HUD; crossing gates in order adds time; lapping adds 100; getting wrecked respawns at the last gate; the clock running out shows the summary with working Retry and Quit.

## 10. Left to the builder

Widget fonts, sizes and colours; pole mesh and material; exact text of log lines; where the respawn timer handles live; test world set-up details.

## 11. Follow-ups deferred from the Phase 2 reviews

Recorded here so Phase 3 planning can pick them up; none blocks the Phase 2 build.

- Phase 4 readiness: `SpawnRespawnVehicle` always spawns the GameMode's `DefaultPawnClass` (NPC respawn needs a per-racer vehicle class); `PendingRespawns` is keyed by raw `AController*` (switch to weak keys once controllers can die mid-race); `HandleRacerDeath`/`TickRacer` assume player controllers for the death limit and respawn scheduling; `NotifyCharacterDied` reads `Character->GetController()`, which is null for a stowed character.
- Untested paths: the zero-delay next-tick respawn; `EndRace` cancelling it; the widget-class fallback in `ADFHUD`; the reverse-order one-incident-one-life case (car wrecked, then character killed); the handbrake release after an off-track respawn (add a `GetHandbrakeInput()` getter); an NPC crossing the start line leaving the clock untouched; HUD text/colour branches (checkpoint flash, `Stop to exit`, `[E] Enter vehicle`).
- Robustness: `IsOnAnyTrack` lacks the `>= 2` spline-points guard, so a degenerate track counts as a disc of road; `ADFHUD` has no `EndPlay` cleanup of its widget; `WarningColor` hard-codes 5 s instead of reading `OffTrackGraceSeconds`; the crosshair stays visible while dead; the summary's UI-only input mode sets no `WidgetToFocus` (mouse-only buttons).
- Wording: "a parked car still belongs to its last driver" comments at `DFRaceGameModeRespawn.cpp`, `DFVehiclePawn.h` and `DFGameTests.cpp` predate the rule that taking another car clears `LastDriver`.
- Tests and tooling: PIE frame caps assume ≤ ~300 fps; headless screenshot fallback overwrites the live images with black PNGs; Slate captures include editor overlay messages ("LIGHTING NEEDS TO BE REBUILT": the level's lighting has never been built); the chase camera never frames the gate poles; the Phase 1 smoke test keeps two wall-clock waits; `Sedan_SkelMesh has no skeleton` and MagicLeap warnings are pre-existing log noise; LogPhysics `BoneIndex out of range` warnings on the fresh car's first animation tick after a respawn are engine-side with no functional effect.
- Design points for the team: a wreck sliding through its next gate credits its driver; a skipped gate gives no on-screen hint (a `NEXT GATE n` line would help playtests); `ShowSummary` is a plain virtual, not a Blueprint event.
