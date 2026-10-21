# Dead Fire Phase 2 (Race Flow) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Phase 1 foundation into a complete race: ordered checkpoints and laps, death/respawn with a life limit, an off-track timer, a race-end summary with Retry/Quit, and a UMG HUD.

**Architecture:** All logic stays in the `comp4900sef` C++ module (prefix `DF`) with Blueprint children for tuning. The GameMode owns every race rule (checkpoint order, respawn, off-track, race end); `ADFCheckpoint` and the pawns only report to it. The HUD and summary are C++ `UUserWidget`s that build their own widget tree when no designer tree exists and read one snapshot struct per frame. Tests are UE editor automation tests in `Source/comp4900sef/Tests/`, plus one real Play-In-Editor test.

**Tech Stack:** UE 4.27.2 (D:\UE_4.27), PhysXVehicles, UMG/Slate (already in Build.cs), classic input, editor Python through the `unreal-mcp-ue4` MCP server or `tools/ue_remote.py`, UE Automation framework.

**Spec:** `docs/superpowers/specs/2026-10-21-phase2-race-flow-design.md` (reads with `docs/superpowers/specs/2026-10-20-dead-fire-design.md`)

## Global Constraints

- Engine `D:\UE_4.27`; project `comp4900sef/comp4900sef.uproject`; module `comp4900sef`; sources under `comp4900sef/Source/comp4900sef/` in subfolders, included from the module root (`#include "Game/DFRaceGameMode.h"`). All paths below are relative to `comp4900sef/Source/comp4900sef/` unless they start with `comp4900sef/`, `docs/` or `tools/`.
- Class prefix `DF`; Blueprint children in `/Game/DeadFire/Blueprints/`; maps in `/Game/DeadFire/Maps/`. Every tunable is `UPROPERTY(EditAnywhere|EditDefaultsOnly, BlueprintReadWrite, Category = "Dead Fire|...")`; every gameplay hook is a `BlueprintImplementableEvent` or `BlueprintAssignable` delegate. Wrap headers/cpps that touch PhysX vehicle types in `PRAGMA_DISABLE_DEPRECATION_WARNINGS` / `PRAGMA_ENABLE_DEPRECATION_WARNINGS` as Phase 1 does.
- Spec §7 values: `MaxDeaths=3` (game over when `Deaths >= MaxDeaths`), `RespawnDelay=2.0`, `OffTrackMargin=500`, `OffTrackGraceSeconds=5.0`, checkpoint `TriggerHalfExtent=(100,1400,250)`, `PoleOffset=700`, `RespawnHeightOffset=50`, HUD `CheckpointFlashSeconds=1.5`; Phase 1 values unchanged (120 s, +8 s, +100, +50). Racers start with `NextCheckpointIndex=1`. The start line (index 0) gives the lap **and** the time bonus.
- Editor automation worlds (`DFTests::NewTestWorld()`) never run `BeginPlay`, `PostInitializeComponents`, overlap events or `GetAuthGameMode()`: tests spawn the GameMode, call `CollectLevelActors()` / `PostInitializeComponents()` themselves and call the GameMode notification functions directly. Timers (`GetWorldTimerManager`) exist but are not relied on by unit tests.
- Build: `D:\UE_4.27\Engine\Build\BatchFiles\Build.bat comp4900sefEditor Win64 Development -Project="E:\VSC projects\comp4900sef-gp3\comp4900sef\comp4900sef.uproject" -WaitMutex -FromMsBuild` (close/quit the editor first: it locks the DLL). Tests: `powershell -NoProfile -ExecutionPolicy Bypass -File tools/run_tests.ps1 [-Filter DeadFire.X]`; exit code 0 and `N passed, 0 failed, N found` is green. Phase 1 ends at 31 tests.
- TDD adapted to compile cost (Phase 1 ruling): per task write the tests and the declarations (stub bodies) together, build, run → RED on the assertions; implement, build, run → GREEN. Two builds per task.
- Editor restart procedure (after every C++ change the live editor must pick up): MCP `manage_editor.run_python` → `unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)`; console `QUIT_EDITOR`; wait for `UE4Editor.exe` to exit (kill after 60 s); build; relaunch `D:\UE_4.27\Engine\Binaries\Win64\UE4Editor.exe "E:\VSC projects\comp4900sef-gp3\comp4900sef\comp4900sef.uproject"` detached; poll MCP `get_unreal_project_path` until it answers (the server reconnects on its own). No-MCP fallback: `python tools/ue_remote.py --file <script>` / `--console "<cmd>"`.
- Do not commit; the user commits on request. Leave the working tree ready and list the commit command in the final report.

## Review Focus

1. Driving the loop backwards, or reversing back and forth over one gate: nothing is credited, no lap, no time (Task 1 `DeadFire.Checkpoint.OnlyTheNextGateCounts`).
2. The player's parked car is wrecked while they are on foot: a death is counted and the respawn pulls the on-foot character into a fresh car at the last gate instead of stranding them (Task 2 `DeadFire.Respawn.WreckedParkedCarPullsCharacterIn`).
3. The clock hits zero while a respawn is pending, or the player dies after the race ended: no respawn happens and the death count stops (Task 2 `DeadFire.Respawn.NothingAfterRaceEnd`).
4. The third death: the race ends with game over and no car is spawned (Task 2 `DeadFire.Respawn.DeathLimitEndsRace`).
5. A car wrecked while off the road: the off-track timer stops and must not respawn a second time on top of the death respawn (Task 3 `DeadFire.OffTrack.WreckStopsTheTimer`).

---

## File structure

```
Track/DFCheckpoint.h/.cpp                 create: gate actor (trigger box, two poles, respawn transform)
Game/DFRacerComponent.h/.cpp              modify: LastCheckpoint, OffTrackSeconds, LastCheckpointTime, Next=1
Game/DFRaceGameState.h/.cpp               modify: EDFRaceEndReason, FDFRaceResult Result
Game/DFRaceGameMode.h/.cpp                modify: checkpoint order, respawn, off-track, EndRace(reason), level actor lists
Vehicle/DFVehiclePawn.h/.cpp              modify: overlap events on, DestroyVehicle reports to the GameMode, EjectOccupant
Vehicle/DFVehicleMovementComponent.cpp    modify: a destroyed car is parked like an unmanned one
Character/DFCharacter.h/.cpp              modify: death disables movement, Revive(), reports death to the GameMode
UI/DFHUDSnapshot.h                        create: FDFHUDSnapshot struct + capture
UI/DFRaceHUDWidget.h/.cpp                 create: in-race UMG widget
UI/DFRaceSummaryWidget.h/.cpp             create: end-of-race widget with Retry/Quit
UI/DFHUD.h/.cpp                           modify: creates the widgets, no canvas drawing
Tests/DFCheckpointTests.cpp               create
Tests/DFRespawnTests.cpp                  create (respawn, death limit, race end)
Tests/DFOffTrackTests.cpp                 create
Tests/DFHUDTests.cpp                      create (snapshot, HUD widget, summary widget)
Tests/DFPIETestUtils.h/.cpp               create: shared PIE helpers (moved out of DFPIESmokeTests.cpp)
Tests/DFPIESmokeTests.cpp                 modify: use the shared helpers
Tests/DFPIERaceFlowTests.cpp              create: DeadFire.PIE.CheckpointWreckRespawnSummary
Tests/DFGameTests.cpp                     modify: lap resets Next to 1
comp4900sef/Script/df_create_blueprints.py  modify: BP_DFCheckpoint
comp4900sef/Script/df_build_test_track.py   modify: four checkpoints at quarter distances
comp4900sef/Content/DeadFire/Blueprints/BP_DFCheckpoint.uasset   generated
comp4900sef/Content/DeadFire/Maps/L_TestTrack.umap               regenerated
README.md                                 modify: Phase 2 state, HUD/summary, scripts
```

---

### Task 1: Checkpoint actor and ordered checkpoint logic

**Files:**
- Create: `Track/DFCheckpoint.h/.cpp`, `Tests/DFCheckpointTests.cpp`
- Modify: `Game/DFRacerComponent.h/.cpp`, `Game/DFRaceGameMode.h/.cpp`, `Vehicle/DFVehiclePawn.cpp` (constructor), `Tests/DFGameTests.cpp`

**Interfaces:**
- Consumes: Phase 1 `UDFRacerComponent::FindOn`, `ADFRaceGameMode::NotifyLapCompleted/NotifyCheckpointPassed`, `ADFVehiclePawn::LastDriver`, `ADFRaceGameState::bRaceActive`.
- Produces:
  - `UCLASS() class ADFCheckpoint : public AActor` — components `UBoxComponent* Trigger` (root, collision profile `Trigger`, `SetGenerateOverlapEvents(true)`, box extent `TriggerHalfExtent`), `UStaticMeshComponent* LeftPole`, `RightPole` (`/Game/VehicleAdv/ArenaMesh/pole`, `NoCollision`, at ±`PoleOffset` on the actor's Y axis). Properties (`Dead Fire|Checkpoint`): `int32 CheckpointIndex = 0`, `FVector TriggerHalfExtent = (100, 1400, 250)`, `float PoleOffset = 700`, `float RespawnHeightOffset = 50`. Functions: `FTransform GetRespawnTransform() const` (actor rotation, location + Z `RespawnHeightOffset`); `bool NotifyVehicle(ADFVehiclePawn* Vehicle)` (resolves the racer as `Vehicle->GetController()` else `Vehicle->LastDriver`, calls `GameMode->NotifyCheckpointReached(Racer, this)` on `GetWorld()->GetAuthGameMode<ADFRaceGameMode>()`, returns its result; false when no GameMode); `UFUNCTION() void OnTriggerBeginOverlap(UPrimitiveComponent*, AActor* OtherActor, UPrimitiveComponent*, int32, bool, const FHitResult&)` bound in the constructor, calls `NotifyVehicle` for `ADFVehiclePawn` actors; `BeginPlay` registers with the GameMode (`RegisterCheckpoint`). `OnConstruction` re-applies extent and pole offsets so edits in the level update.
  - `UDFRacerComponent` additions (`Dead Fire|Race`, VisibleAnywhere, BlueprintReadWrite): `ADFCheckpoint* LastCheckpoint = nullptr`, `float OffTrackSeconds = 0`, `float LastCheckpointTime = -1` (world seconds of the last credited gate; -1 never). Constructor default `NextCheckpointIndex = 1`.
  - `ADFRaceGameMode` additions: `UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TArray<ADFCheckpoint*> Checkpoints` (sorted by index); `void RegisterCheckpoint(ADFCheckpoint*)` (idempotent, keeps the array sorted by `CheckpointIndex`); `void CollectLevelActors()` (registers every `ADFCheckpoint` in the world via `TActorIterator`; also collects `ADFTrackSpline`s into `TArray<ADFTrackSpline*> Tracks` and `ADFTrackSpline* MainTrack` (the first with `bIsMainTrack`) for Task 3; called from `BeginPlay`); `int32 GetCheckpointCount() const`; `bool NotifyCheckpointReached(AController* Racer, ADFCheckpoint* Checkpoint)` — false when the race is over (`GetRaceState()` exists and `!bRaceActive`), the racer has no component, or `Checkpoint->CheckpointIndex != NextCheckpointIndex`; otherwise sets `LastCheckpoint`, `LastCheckpointTime = World->GetTimeSeconds()`, then index 0 → `NotifyLapCompleted(Racer)` plus the player time bonus, else `NotifyCheckpointPassed(Racer)`; returns true.
  - Changed Phase 1 behaviour: `NotifyLapCompleted` sets `NextCheckpointIndex = 1` (was 0); `NotifyCheckpointPassed` sets `NextCheckpointIndex = (Count > 0) ? (Next + 1) % Count : Next + 1`; the time bonus for players moves into a private `GrantCheckpointTimeBonus(AController*)` used by both paths.
  - `ADFVehiclePawn` constructor: `GetMesh()->SetGenerateOverlapEvents(true)` so the car overlaps triggers.

- [ ] **Step 1:** Write `Tests/DFCheckpointTests.cpp`. Each test: `NewTestWorld()`, spawn `ADFRaceGameMode`, `ADFRaceGameState` (assign `GameMode->GameState`, `bRaceActive = true`), one `ADFPlayerController` (`Racer = FindOn(PC)`), and checkpoints with `SpawnAt<ADFCheckpoint>` then `CheckpointIndex` set and `GameMode->RegisterCheckpoint`.
  - `DeadFire.Checkpoint.RegistrationSortsByIndex`: register indices 2, 0, 1 (in that order) → `Checkpoints[0..2]` indices are 0,1,2; registering index 1 again keeps `GetCheckpointCount()==3`. `CollectLevelActors()` on a world with the same three actors yields the same order.
  - `DeadFire.Checkpoint.OnlyTheNextGateCounts`: three gates; racer starts with `NextCheckpointIndex==1`. `NotifyCheckpointReached(PC, Gate2)` false, Next still 1, `State->RemainingTime` unchanged (set 60 first); `NotifyCheckpointReached(PC, Gate0)` false (no lap: `LapsCompleted==0`); `NotifyCheckpointReached(PC, Gate1)` true → Next 2, `RemainingTime==68`, `LastCheckpoint==Gate1`, `LastCheckpointTime >= 0`; `NotifyCheckpointReached(PC, Gate1)` again false and `RemainingTime` still 68.
  - `DeadFire.Checkpoint.StartLineCompletesLapWithBonus`: three gates; pass 1, 2 (Next becomes 0), then gate 0 → true, `LapsCompleted==1`, `Score==100`, `NextCheckpointIndex==1`, `RemainingTime` gained 8 for this crossing as well (60 → 84 across the three crossings).
  - `DeadFire.Checkpoint.IgnoredWhenRaceOver`: `State->bRaceActive=false` → `NotifyCheckpointReached(PC, Gate1)` false, Next 1.
  - `DeadFire.Checkpoint.RespawnTransformAndNoGameMode`: car with `LastDriver = PC`, no controller; `Gate1->NotifyVehicle(Car)` — there is no auth GameMode in an editor world, so this returns false; assert false and that `Gate1->GetRespawnTransform().GetLocation().Z == Gate1->GetActorLocation().Z + 50` and the transform's rotation equals the actor rotation (spawn the gate with yaw 90). (The overlap → GameMode path is exercised by the PIE test in Task 7.)
  - Update `Tests/DFGameTests.cpp` `ScoringHooks`: after `NotifyLapCompleted(PC1)` assert `Racer1->NextCheckpointIndex == 1`.
- [ ] **Step 2:** Add the declarations with stub bodies (`return false;`, empty) so it compiles. Build. Expected: exit code 0.
- [ ] **Step 3:** Run `tools/run_tests.ps1 -Filter DeadFire.Checkpoint`. Expected: the four logic tests fail on assertions (RED); `VehicleResolvesParkedCarDriver` may already pass.
- [ ] **Step 4:** Implement `ADFCheckpoint`, the racer fields, `RegisterCheckpoint` / `CollectLevelActors` / `NotifyCheckpointReached` and the Phase 1 changes above.
- [ ] **Step 5:** Build, run the full suite. Expected: 36 passed, 0 failed (31 + 5).

### Task 2: Death, respawn, death limit, race end

**Files:**
- Create: `Tests/DFRespawnTests.cpp`
- Modify: `Game/DFRaceGameState.h/.cpp`, `Game/DFRaceGameMode.h/.cpp`, `Vehicle/DFVehiclePawn.h/.cpp`, `Vehicle/DFVehicleMovementComponent.cpp`, `Character/DFCharacter.h/.cpp`

**Interfaces:**
- Consumes: Task 1 `Checkpoints`, `UDFRacerComponent::LastCheckpoint`; Phase 1 `ADFVehiclePawn::EnterVehicle/ResetHealth/bIsDestroyed/Occupant`, `ADFCharacter::SetStowed/IsDead/CurrentVehicle`, `ADFPlayerController::CurrentVehicle/OnFootCharacter`, `GetRankedRacers`.
- Produces:
  - In `DFRaceGameState.h`: `UENUM(BlueprintType) enum class EDFRaceEndReason : uint8 { None, TimeUp, DeathLimit }`; `USTRUCT(BlueprintType) struct FDFRaceResult { EDFRaceEndReason Reason = None; bool bPassed = false; int32 Score = 0; int32 ScoreRequirement = 0; int32 Rank = 0; int32 RacerCount = 0; int32 Laps = 0; int32 Kills = 0; int32 Deaths = 0; }` (all `UPROPERTY(BlueprintReadOnly)`); `ADFRaceGameState::FDFRaceResult Result` (VisibleAnywhere, BlueprintReadOnly).
  - `ADFRaceGameMode`: properties (`Dead Fire|Race`, EditDefaultsOnly, BlueprintReadWrite) `float RespawnDelay = 2.f`; functions `void NotifyCharacterDied(ADFCharacter* Character)` (Deaths+1 on `Character->GetController()`'s racer, then `HandleRacerDeath`); `NotifyVehicleDestroyed` now also calls `HandleRacerDeath(VictimController)` after counting; `void HandleRacerDeath(AController* Racer)` (nothing when the race is over; `Deaths >= MaxDeaths` → `EndRace(EDFRaceEndReason::DeathLimit)`; else for a player controller schedules `RespawnRacer(Racer)` after `RespawnDelay` with a per-controller `FTimerHandle` in `TMap<AController*, FTimerHandle> PendingRespawns`); `UFUNCTION(BlueprintCallable) void RespawnRacer(AController* Racer)` (nothing when the race is over; respawn point = `LastCheckpoint` → `Checkpoints[0]` → `FindPlayerStart(Racer)` transform; intact `ADFPlayerController::CurrentVehicle` (or `GetPawn()` cast for other controllers) is teleported with `ETeleportType::TeleportPhysics`, mesh linear/angular velocity zeroed, throttle/steering 0; a wrecked or missing one is replaced by spawning `DefaultPawnClass` at the point (`AlwaysSpawn`) and `Destroy()`ing the wreck after `EjectOccupant()`; a dead `OnFootCharacter` is `Revive()`d; the character is stowed with `Vehicle->EnterVehicle(Character)` after `SetStowed(false, nullptr)`/`CurrentVehicle = nullptr` if it was in the wreck; `Racer->Possess(Vehicle)` when `GetPawn() != Vehicle`; `OffTrackSeconds = 0`; updates `DFPC->CurrentVehicle`; fires `OnRacerRespawned(AController*, ADFVehiclePawn*)` BlueprintImplementableEvent); `UFUNCTION(BlueprintCallable) void EndRace(EDFRaceEndReason Reason)` replaces the no-arg `EndRace` (Tick calls it with `TimeUp`): sets `bRaceActive=false`, `RemainingTime=0` only for `TimeUp`, clears `PendingRespawns` timers, fills `State->Result` from the first `APlayerController` racer (`bPassed = Reason==TimeUp && Score >= ScoreRequirement`, `Rank` = 1-based position in `GetRankedRacers()`, `RacerCount`), disables input on every player's pawn (`Pawn->DisableInput(PC)`), calls `ADFHUD::ShowSummary()` on each player's HUD if it is an `ADFHUD` (Task 5 implements it; declare it now as an empty `virtual void ShowSummary()` on `ADFHUD`), fires `OnRaceEnded(bPassed)`.
  - `ADFVehiclePawn`: `void EjectOccupant()` (clears `Occupant`, the character's `CurrentVehicle`, `SetStowed(false, nullptr)`; no possession change); `DestroyVehicle()` additionally calls `GameMode->NotifyVehicleDestroyed(this, LastDamageInstigator)` on `GetWorld()->GetAuthGameMode<ADFRaceGameMode>()` when one exists; `MoveForward/MoveRight` and `OnHandbrakeReleased` do nothing when `bIsDestroyed`.
  - `UDFVehicleMovementComponent::UpdateState`: the park override also applies when the owner is an `ADFVehiclePawn` with `bIsDestroyed`.
  - `ADFCharacter`: `UFUNCTION(BlueprintCallable) void Revive()` (`Health = MaxHealth`, `SetMovementMode(MOVE_Walking)`, fires `OnCharacterRevived()` BlueprintImplementableEvent); on death `TakeDamage` calls `GetCharacterMovement()->DisableMovement()` and `GameMode->NotifyCharacterDied(this)` when an auth GameMode exists; `MoveForward/MoveRight` ignore input while `IsDead()`.

- [ ] **Step 1:** Write `Tests/DFRespawnTests.cpp`. Shared set-up per test: world, `SpawnFloor`, GameMode + GameState (`bRaceActive=true`, `RemainingTime=60`), `ADFPlayerController* PC`, two gates (index 0 at origin, index 1 at (5000,0,0) yaw 90) registered, `ADFCharacter* Char` and `ADFVehiclePawn* Car` spawned, `Car->EnterVehicle(Char)`, `PC->CurrentVehicle = Car`, `PC->OnFootCharacter = Char`, `Racer->LastCheckpoint = Gate1`.
  - `DeadFire.Respawn.WreckSpawnsFreshCarAtLastCheckpoint`: `Car->TakeDamage(1000, FDamageEvent(), nullptr, nullptr)` → `bIsDestroyed`; `GameMode->NotifyVehicleDestroyed(Car, nullptr)` → `Deaths==1`; `GameMode->RespawnRacer(PC)` → `PC->CurrentVehicle != Car`, new car not destroyed, `Health==MaxHealth`, within 300 cm (2D) of `Gate1` location, yaw ≈ 90 (±1), `Occupant==Char`, `Char->IsInVehicle()`, old `Car->IsPendingKill()` (or `IsActorBeingDestroyed()`), `PC->GetPawn()` is the new car.
  - `DeadFire.Respawn.WreckedParkedCarPullsCharacterIn`: `Car->ExitVehicle()` (needs the floor; assert true), then wreck `Car` and `RespawnRacer(PC)` → `Char->IsInVehicle()`, new car's `Occupant==Char`, `Char` not hidden before but hidden after (stowed).
  - `DeadFire.Respawn.DeadCharacterRevivedIntoCar`: exit (the car has no controller, so nothing possesses the character), `PC->Possess(Char)`, `Char->TakeDamage(500,...)` → `IsDead()`, movement mode `MOVE_None`; `GameMode->NotifyCharacterDied(Char)` → `Deaths==1`; `RespawnRacer(PC)` → `Char->Health==Char->MaxHealth`, `!IsDead()`, stowed in `PC->CurrentVehicle` which is still `Car` (intact → teleported: within 300 cm of Gate1), `PC->GetPawn()==Car`.
  - `DeadFire.Respawn.NoCheckpointUsesGateZero`: `LastCheckpoint=nullptr` → respawn within 300 cm of Gate0 at the origin.
  - `DeadFire.Respawn.DeathLimitEndsRace`: `Racer->Deaths = 2`; wreck + `NotifyVehicleDestroyed(Car, nullptr)` → `Deaths==3`, `State->bRaceActive==false`, `State->Result.Reason==DeathLimit`, `Result.bPassed==false`, `Result.Deaths==3`, `Result.Rank==1`, `Result.RacerCount==1`; `PC->CurrentVehicle==Car` (no respawn).
  - `DeadFire.Respawn.NothingAfterRaceEnd`: `GameMode->EndRace(EDFRaceEndReason::TimeUp)` with `Racer->Score=300` → `Result.bPassed==true`, `Result.Reason==TimeUp`, `RemainingTime==0`; then `RespawnRacer(PC)` leaves `PC->CurrentVehicle==Car` at its old location; wrecking it afterwards leaves `Deaths==0`.
  - `DeadFire.Vehicle.DestroyedCarIgnoresThrottle`: `Car->MoveForward(1.f)` → `GetVehicleMovementComponent()->GetThrottleInput()==1`; wreck the car (throttle becomes 0), `Car->MoveForward(1.f)` and `MoveRight(1.f)` again → throttle 0 and steering 0. (`MoveForward`/`MoveRight` become `public` `UFUNCTION(BlueprintCallable, Category="Dead Fire|Vehicle")` so tests and Blueprints can drive the car.)
  - `DeadFire.Character.DeadCannotMoveAndRevives`: on-foot character, `TakeDamage(500)` → `GetCharacterMovement()->MovementMode==MOVE_None`, `Fire()` false; `Revive()` → `Health==100`, `MovementMode==MOVE_Walking`.
- [ ] **Step 2:** Add declarations and stubs; build (exit 0); run `-Filter DeadFire.Respawn` and the two pawn tests. Expected: RED on assertions.
- [ ] **Step 3:** Implement. For `Destroy()` of the wreck use `Old->Destroy()` after `EjectOccupant()`; in editor worlds `IsPendingKill()` becomes true immediately. Possession: `AController::Possess` works in editor worlds (`NM_Standalone` has authority); if `APlayerController::ClientRestart` logs about a missing local player that is acceptable — assert state, not logs.
- [ ] **Step 4:** Build, run the full suite. Expected: 44 passed, 0 failed (36 + 8). Phase 1 `KillCreditRules` still passes (its two wrecks schedule respawns that never fire; `Deaths` reaches 2 < 3).

### Task 3: Off-track timer and per-racer tick

**Files:**
- Create: `Tests/DFOffTrackTests.cpp`
- Modify: `Game/DFRaceGameMode.h/.cpp`

**Interfaces:**
- Consumes: Task 1 `Tracks`/`MainTrack`, Task 2 `RespawnRacer`; Phase 1 `ADFTrackSpline::GetLateralDistanceFromTrack/RoadWidth/GetDistanceAlongTrack/SetPointsFromArray`.
- Produces: `ADFRaceGameMode` properties `float OffTrackMargin = 500.f`, `float OffTrackGraceSeconds = 5.f`; `UFUNCTION(BlueprintPure) bool IsOnAnyTrack(const FVector& Location) const` (true when `Tracks` is empty, or any track has `GetLateralDistanceFromTrack(Location) <= RoadWidth*0.5 + OffTrackMargin`); `UFUNCTION(BlueprintCallable) void TickRacer(AController* Racer, APawn* Pawn, float DeltaSeconds)` — nothing when the race is over or the racer has no component; updates `DistanceAlongTrack` from `MainTrack` for any pawn; when `Pawn` is a live (`!bIsDestroyed`) `ADFVehiclePawn`: on track → `OffTrackSeconds = 0`, else `OffTrackSeconds += DeltaSeconds` and at `>= OffTrackGraceSeconds` → `OffTrackSeconds = 0`, `RespawnRacer(Racer)` (no death); for any other pawn (on foot, wreck, none) → `OffTrackSeconds = 0`. `Tick` calls `TickRacer(C, C->GetPawn(), Dt)` for every `AController` (`TActorIterator`) while the race is active.

- [ ] **Step 1:** Write `Tests/DFOffTrackTests.cpp`. Set-up: world, floor, GameMode + GameState active, PC + racer, a main `ADFTrackSpline` built with `SetPointsFromArray` (square 0,0 → 20000,0 → 20000,20000 → 0,20000, closed; `RoadWidth` 1400), gate 0 at the origin registered, `GameMode->CollectLevelActors()`, car + character entered, `PC->CurrentVehicle=Car`, `OnFootCharacter=Char`, `LastCheckpoint=Gate0`.
  - `DeadFire.OffTrack.OnRoadResetsTimer`: car at (10000, 300, 0) (lateral 300) → `TickRacer(PC, Car, 1.f)` → `OffTrackSeconds==0`; move to (10000, 1500, 0) (lateral 1500 > 700+500) → three ticks of 1 s → `OffTrackSeconds==3`; back to (10000, 300) → tick → 0.
  - `DeadFire.OffTrack.GraceRespawnsWithoutDeath`: car at (10000, 3000, 0); five ticks of 1.1 s → after the fifth, `OffTrackSeconds==0`, car within 300 cm of the origin (teleported, same actor: `PC->CurrentVehicle==Car`), `Deaths==0`.
  - `DeadFire.OffTrack.OnFootDoesNotCount`: `TickRacer(PC, Char, 10.f)` with the character at (10000, 5000, 0) → `OffTrackSeconds==0`, character not moved.
  - `DeadFire.OffTrack.ShortcutRoadCountsAsTrack`: second `ADFTrackSpline` (`bIsMainTrack=false`) through (10000, 5000) (open spline (5000,5000) → (15000,5000)); `CollectLevelActors()` again; car at (10000, 5000) → `IsOnAnyTrack` true, timer stays 0.
  - `DeadFire.OffTrack.WreckStopsTheTimer`: car at (10000, 3000), two ticks → 2; `Car->TakeDamage(1000)`; tick 10 s → `OffTrackSeconds==0` and the car has not moved.
  - `DeadFire.OffTrack.NoTracksNoPenalty`: a world without track actors → `IsOnAnyTrack((99999,99999,0))` true.
- [ ] **Step 2:** Declarations and stubs; build; run `-Filter DeadFire.OffTrack`. Expected: RED.
- [ ] **Step 3:** Implement `IsOnAnyTrack`, `TickRacer`, the Tick loop.
- [ ] **Step 4:** Build, run the full suite. Expected: 50 passed, 0 failed.

### Task 4: HUD snapshot and the in-race UMG widget

**Files:**
- Create: `UI/DFHUDSnapshot.h`, `UI/DFRaceHUDWidget.h/.cpp`, `Tests/DFHUDTests.cpp`
- Modify: `UI/DFHUD.h/.cpp`

**Interfaces:**
- Consumes: Phase 1 `ADFVehiclePawn::GetSpeedKPH/GetGearDisplayText/Health/MaxHealth/Tires/bIsDestroyed/bInReverseGear/CanExit/FindExitLocation/Occupant`, `ADFCharacter::Health/MaxHealth/IsDead/FindNearestEnterableVehicle`, `UDFRacerComponent` fields incl. Task 1 `LastCheckpointTime`, Task 3 `OffTrackSeconds`, `ADFRaceGameMode::MaxDeaths/OffTrackGraceSeconds/CheckpointTimeBonus`, `ADFRaceGameState::RemainingTime/GetRemainingTimeText`.
- Produces:
  - `USTRUCT(BlueprintType) struct FDFHUDSnapshot` (all `UPROPERTY(BlueprintReadWrite)`): `int32 Score, Laps, Kills, Lives`; `float RemainingTime`; `FText TimeText`; `bool bInVehicle, bVehicleDestroyed, bInReverse`; `int32 SpeedKPH`; `FText GearText`; `float VehicleHealth, VehicleMaxHealth`; `TArray<float> TireHealth` (−1 for blown); `bool bOnFoot, bCharacterDead`; `float CharacterHealth, CharacterMaxHealth`; `FText PromptText` (empty when none); `FText WarningText` (empty when none); `float OffTrackRemaining` (−1 when not off track); `float CheckpointFlashRemaining` (−1 when none).
  - `UDFRaceHUDWidget : UUserWidget` — `UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category="Dead Fire|HUD") float CheckpointFlashSeconds = 1.5f`; `UFUNCTION(BlueprintPure, Category="Dead Fire|HUD") static FDFHUDSnapshot CaptureSnapshot(APlayerController* Player, float CheckpointFlashSeconds)` (gathers the controller's racer, `GetPawn()`, the world's `ADFRaceGameState` and the GameMode — `GetAuthGameMode<ADFRaceGameMode>()`, else the first `TActorIterator<ADFRaceGameMode>` so editor-world tests find it — and delegates to `static FDFHUDSnapshot CaptureSnapshotFor(APawn* Pawn, const UDFRacerComponent* Racer, const ADFRaceGameState* State, const ADFRaceGameMode* GameMode, float CheckpointFlashSeconds)`, also `BlueprintPure`; every input may be null; prompt priority in a vehicle: destroyed → none; `CanExit()` and `FindExitLocation` fails → `No room to exit`; `CanExit()` → `[E] Exit vehicle`; occupant present → `Stop to exit  [E]`; on foot: dead → none; enterable vehicle near → `[E] Enter vehicle`; warning priority: `WRECKED` (vehicle destroyed) > `YOU DIED` > `RETURN TO TRACK  {0:0.0}` (OffTrackRemaining ≥ 0) > `CHECKPOINT  +{bonus} s` (flash) > empty; `Lives = MaxDeaths - Deaths`); `UFUNCTION(BlueprintCallable) void ApplySnapshot(const FDFHUDSnapshot& Snapshot)` (writes every text/bar; hides vehicle-only and foot-only blocks with `ESlateVisibility::Collapsed`; time text red when `RemainingTime < 10`, gear red in reverse, warning yellow → red as `OffTrackRemaining` nears 0); `NativeOnInitialized` builds the default tree with `WidgetTree->ConstructWidget<...>` when `WidgetTree->RootWidget == nullptr` (a `UCanvasPanel` root; anchors per spec §6); `NativeTick` calls `ApplySnapshot(CaptureSnapshot(GetOwningPlayer(), CheckpointFlashSeconds))`. Elements, all `UPROPERTY(BlueprintReadOnly, meta=(BindWidgetOptional))`: `UTextBlock* ScoreText, LapText, KillsText, LivesText, TimeText, SpeedText, GearText, VehicleHealthText, TireText, CharacterHealthText, CrosshairText, PromptText, WarningText`; `UProgressBar* VehicleHealthBar, CharacterHealthBar`; `UWidget* VehiclePanel, CharacterPanel` (the two bottom-left containers).
  - `ADFHUD`: `UPROPERTY(EditDefaultsOnly, BlueprintReadWrite, Category="Dead Fire|HUD") TSubclassOf<UDFRaceHUDWidget> HUDWidgetClass` (default `UDFRaceHUDWidget::StaticClass()`), `UPROPERTY(BlueprintReadOnly) UDFRaceHUDWidget* HUDWidget`; `BeginPlay` creates it with `CreateWidget<UDFRaceHUDWidget>(GetOwningPlayerController(), HUDWidgetClass)` and `AddToViewport()`; `DrawHUD`, `DrawRaceInfo/DrawVehicleInfo/DrawCharacterInfo/DrawPrompt` and `HUDFont` are removed.

- [ ] **Step 1:** Write `Tests/DFHUDTests.cpp`:
  - `DeadFire.HUD.SnapshotFromRaceState`: world, GameMode (`MaxDeaths` default 3), GameState (`RemainingTime=73`), PC with racer `Score=150, LapsCompleted=2, Kills=1, Deaths=1`; `CaptureSnapshot(PC, 1.5f)` → `Score==150, Laps==2, Kills==1, Lives==2`, `TimeText=="1:13"`, `bInVehicle==false`, `bOnFoot==false`, `PromptText` empty, `OffTrackRemaining==-1`, `CheckpointFlashRemaining==-1`.
  - `DeadFire.HUD.SnapshotVehiclePrompts`: floor, car + character entered; `CaptureSnapshotFor(Car, Racer, State, GameMode, 1.5f)` → `bInVehicle`, `PromptText=="[E] Exit vehicle"`, `SpeedKPH==0`, `TireHealth.Num()==4`; surround the three exit spots with `SpawnBlockingBox` → `No room to exit`; racer `OffTrackSeconds=3` (`OffTrackGraceSeconds` 5) → `OffTrackRemaining==2` and `WarningText` starts with `RETURN TO TRACK`; wreck the car → `WarningText=="WRECKED"`, prompt empty; `CaptureSnapshotFor(Char, ...)` after `Car->EjectOccupant()` → `bOnFoot`, `PromptText=="[E] Enter vehicle"` is **not** shown because the car is destroyed (`CanBeEntered()` false) → prompt empty; `Char->TakeDamage(500)` → `WarningText=="YOU DIED"`.
  - `DeadFire.HUD.WidgetAppliesSnapshot`: `CreateWidget<UDFRaceHUDWidget>(World)` → `ScoreText`, `TimeText`, `PromptText` non-null; apply a hand-built snapshot (`Score 150`, `TimeText "1:13"`, `bInVehicle`, `SpeedKPH 87`, `GearText "3"`, tires `{30,-1,30,30}`, prompt `[E] Exit vehicle`) → `ScoreText->GetText()=="SCORE 150"`, `TimeText->GetText()=="1:13"`, `SpeedText=="87 km/h"`, `GearText=="GEAR 3"`, `TireText=="TIRES [30] [X] [30] [30]"`, `PromptText=="[E] Exit vehicle"`, `CharacterPanel->GetVisibility()==Collapsed`, `VehiclePanel` visible; apply a foot snapshot (`bOnFoot`, `CharacterHealth 40/100`, prompt `[E] Enter vehicle`) → `CharacterHealthText=="HEALTH 40 / 100"`, `VehiclePanel` collapsed, `CrosshairText` visible.
- [ ] **Step 2:** Declarations and stubs; build; run `-Filter DeadFire.HUD`. Expected: RED.
- [ ] **Step 3:** Implement the snapshot capture, the widget (tree built in `NativeOnInitialized`; `CreateWidget` on a `UWorld` without a game instance is supported by `UUserWidget::CreateWidgetInstance`), and the `ADFHUD` change.
- [ ] **Step 4:** Build, run the full suite. Expected: 53 passed, 0 failed. `DeadFire.PIE.DriveExitFireEnter` still passes (it never read the canvas).

### Task 5: Summary widget and race-end presentation

**Files:**
- Create: `UI/DFRaceSummaryWidget.h/.cpp`
- Modify: `UI/DFHUD.h/.cpp`, `Tests/DFHUDTests.cpp`

**Interfaces:**
- Consumes: Task 2 `FDFRaceResult`, `ADFRaceGameState::Result`, `ADFHUD::ShowSummary` (declared empty in Task 2).
- Produces:
  - `UDFRaceSummaryWidget : UUserWidget` — elements (`BindWidgetOptional`): `UTextBlock* TitleText, PlaceText, StatsText`; `UButton* RetryButton, QuitButton`; `UTextBlock* RetryLabel, QuitLabel`. `UFUNCTION(BlueprintCallable) void ShowResults(const FDFRaceResult& Result)`: title `RACE COMPLETE` / `TIME UP` / `GAME OVER` per spec §5, `PlaceText` = `Place {Rank} of {RacerCount}`, `StatsText` = `Score {Score} / {ScoreRequirement}    Laps {Laps}    Kills {Kills}    Deaths {Deaths}`; `UFUNCTION(BlueprintPure) static FText TitleFor(const FDFRaceResult&)`. `UFUNCTION() void HandleRetry()` → `UGameplayStatics::OpenLevel(this, FName(*UGameplayStatics::GetCurrentLevelName(this, true)))`; `UFUNCTION() void HandleQuit()` → `UKismetSystemLibrary::QuitGame(this, GetOwningPlayer(), EQuitPreference::Quit, false)`; both bound to `OnClicked` in `NativeOnInitialized` (after building the default tree: a centred `UVerticalBox` on a `UCanvasPanel` with a dark `UBorder` behind it).
  - `ADFHUD`: `TSubclassOf<UDFRaceSummaryWidget> SummaryWidgetClass` (default the C++ class), `UDFRaceSummaryWidget* SummaryWidget`; `void ShowSummary()` (creates the widget once, `ShowResults(State->Result)`, `AddToViewport(10)`, hides `HUDWidget`, sets `bShowMouseCursor = true` and `SetInputMode(FInputModeUIOnly())` on the owning controller); `UFUNCTION(BlueprintPure) bool IsSummaryShown() const`.

- [ ] **Step 1:** Add to `Tests/DFHUDTests.cpp`:
  - `DeadFire.Summary.TitleByOutcome`: `TitleFor` → `{TimeUp, bPassed}` = `RACE COMPLETE`; `{TimeUp, !bPassed}` = `TIME UP`; `{DeathLimit}` = `GAME OVER`.
  - `DeadFire.Summary.ShowsPlaceAndStats`: `CreateWidget<UDFRaceSummaryWidget>(World)`; `ShowResults({TimeUp, true, Score 250, Req 300, Rank 1, Count 3, Laps 2, Kills 1, Deaths 0})` → `TitleText=="RACE COMPLETE"`, `PlaceText=="Place 1 of 3"`, `StatsText=="Score 250 / 300    Laps 2    Kills 1    Deaths 0"`, `RetryButton` and `QuitButton` non-null.
- [ ] **Step 2:** Declarations and stubs; build; run `-Filter DeadFire.Summary`. Expected: RED.
- [ ] **Step 3:** Implement the widget and `ADFHUD::ShowSummary` / `IsSummaryShown`.
- [ ] **Step 4:** Build, run the full suite. Expected: 55 passed, 0 failed.

### Task 6: Blueprint child, checkpoints in the test track, editor verification

**Files:**
- Modify: `comp4900sef/Script/df_create_blueprints.py`, `comp4900sef/Script/df_build_test_track.py`
- Generated: `comp4900sef/Content/DeadFire/Blueprints/BP_DFCheckpoint.uasset`, `comp4900sef/Content/DeadFire/Maps/L_TestTrack.umap` (regenerated)

**Interfaces:**
- Consumes: Task 1 `ADFCheckpoint` (`checkpoint_index` editor property), Phase 1 `ADFTrackSpline::GetTrackLength/GetTransformAtDistance`.
- Produces: `BP_DFCheckpoint` (parent `/Script/comp4900sef.DFCheckpoint`) in `SPECS`; `L_TestTrack` with four `BP_DFCheckpoint` actors labelled `Checkpoint_0..3` at track distances `L*k/4` (location and yaw from `track.get_transform_at_distance(d)`, Z = road surface), `checkpoint_index = k`; everything else in the level as in Phase 1. Script docstrings use `<repo>` instead of the hard-coded `E:/...` path (deferred Phase 1 minor).

- [ ] **Step 1:** Restart the editor (Global Constraints procedure) so the Task 5 build is loaded.
- [ ] **Step 2:** Edit and run `df_create_blueprints.py` through `run_python`. Expected: log `created: /Game/DeadFire/Blueprints/BP_DFCheckpoint`; MCP `manage_blueprint` read reports parent `DFCheckpoint`.
- [ ] **Step 3:** Edit and run `df_build_test_track.py` (adds the checkpoint loop after `set_points_from_array`; spawn with `spawn_actor_from_class(cls, loc, rot)`, then `set_editor_property('checkpoint_index', k)` and `set_actor_label`). Expected: `manage_level.list_actors` lists `Checkpoint_0..3` and `MainTrack`; the printed track length is ≈ 40000 cm.
- [ ] **Step 4:** Verify in the live editor: `Automation RunTests DeadFire.PIE.DriveExitFireEnter` still passes, and a `unreal.AutomationLibrary.take_high_res_screenshot` (or the test's own screenshot) shows the poles of `Checkpoint_0` beside the player start.

### Task 7: Play-In-Editor race-flow test, README, final verification

**Files:**
- Create: `Tests/DFPIETestUtils.h/.cpp`, `Tests/DFPIERaceFlowTests.cpp`
- Modify: `Tests/DFPIESmokeTests.cpp` (use the shared helpers), `README.md`

**Interfaces:**
- Consumes: everything.
- Produces:
  - `Tests/DFPIETestUtils.h`: `namespace DFPIE { UWorld* PIEWorld(); APlayerController* PlayerController(); APawn* PlayerPawn(); void Key(const FKey&, EInputEvent); }` (inline), and latent commands declared in the header with bodies in `DFPIETestUtils.cpp`: `FDFPIEKey(FKey, EInputEvent)`, `FDFPIEWaitFrames(int32)`, `FDFPIEScreenshot(FString)`. `DFPIESmokeTests.cpp` drops its copies of these four and keeps its own `DFSmoke::State` and checks.
  - `DeadFire.PIE.CheckpointWreckRespawnSummary` (`EditorContext | ProductFilter`), latent steps on `L_TestTrack` with `FStartPIECommand(false)`; all waits are frame- or condition-based with a frame cap, never wall-clock:
    1. Find the vehicle, the `ADFRaceGameMode` (`World->GetAuthGameMode`), its state, the racer; assert `GetCheckpointCount()==4`, `NextCheckpointIndex==1`, `ADFHUD::HUDWidget` non-null and in the viewport.
    2. Teleport the car to `Checkpoints[1]->GetRespawnTransform()` moved 1500 cm back along its forward vector, velocity zeroed; record `RemainingTime` and `World->GetTimeSeconds()`; hold W; wait until `NextCheckpointIndex==2` (cap 900 frames); release W. Assert `LastCheckpoint==Checkpoints[1]` and `RemainingTime ≈ RecordedTime − elapsed + 8` (±0.5).
    3. `UGameplayStatics::ApplyDamage(Vehicle, 1000.f, nullptr, nullptr, UDamageType::StaticClass())` → `bIsDestroyed`, `Deaths==1`; wait until `PlayerPawn()` is an `ADFVehiclePawn` other than the wreck (cap 600 frames) → new car within 1500 cm of `Checkpoints[1]`, `Occupant` is the character, `Health==MaxHealth`; screenshot `DF_PIE_04_respawned`.
    4. Teleport the new car to `Checkpoints[1]` location + its right vector × 4000; wait until `OffTrackSeconds > 0.5` (cap 300 frames); wait until the car is within 1500 cm of `Checkpoints[1]` again (cap 2000 frames) → `Deaths` still 1.
    5. `State->RemainingTime = 0.1f`; wait 30 frames → `!bRaceActive`, `Result.Reason==TimeUp`, `IsSummaryShown()`, `PlayerPawn()->InputEnabled()==false`; screenshot `DF_PIE_05_summary`.
    6. `FEndPlayMapCommand`.

- [ ] **Step 1:** Extract the shared helpers; build; run `-Filter DeadFire.PIE.DriveExitFireEnter`. Expected: still passes.
- [ ] **Step 2:** Write the race-flow test; build; run it in the live editor (`Automation RunTests DeadFire.PIE.CheckpointWreckRespawnSummary` after an editor restart). Expected: passed; screenshots `DF_PIE_04_respawned` (car at the second gate's poles, HUD visible) and `DF_PIE_05_summary` (summary panel) in `comp4900sef/Saved/Screenshots/Windows/`. View them.
- [ ] **Step 3:** Run `tools/run_tests.ps1` headless. Expected: 56 passed, 0 failed, 56 found, exit code 0.
- [ ] **Step 4:** Update `README.md`: "Current state: Phase 2" (gates, laps, lives, off-track, summary, UMG HUD), the two PIE tests, `BP_DFCheckpoint` in the layout and owner table, how to restyle the HUD (Widget Blueprint child with the same element names set on `BP_DFHUD`), the `<repo>` script paths.
- [ ] **Step 5:** `git status` review; do not commit. Report the commit command in the final summary.
