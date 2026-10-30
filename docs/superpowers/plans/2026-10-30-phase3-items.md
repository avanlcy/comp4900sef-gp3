# Dead Fire Phase 3 (Items & Damage) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every graph-authoring step is automation through the generator pipeline; the only **(person)** step is the playtest in Task 8.

**Goal:** Loot boxes collected on foot, a three-slot inventory on the racer, five items usable from the car (Boost, Shield, Bomb, Gun, RPG), a shared explosion rule with tire blasts, wreck effects, and a destructible rock that opens a shortcut road, each pinned by a Blueprint Functional Test.

**Architecture:** Every Blueprint is described in Python under `tools/bpgen/graphs/`, generated into `comp4900sef/Script/paste/<Asset>/` by `tools/bpgen/generate_all.py`, and applied inside the running editor by `comp4900sef/Script/df_apply_blueprint.py` through the DF Blueprint Authoring plugin. Phase 3 adds one gameplay module (`items.py`: damage type, loot box, bomb, rocket, destructible), one test module (`tests_items.py`), two data types, and extends the racer (inventory), GameMode (item info, grants, explosions), vehicle (effects, item use, gun, wreck effects), weapon (explicit instigator), character (cycle key), HUD (item row) and the level builder (crates, shortcut, rock). Nothing is hand-edited in the editor.

**Tech Stack:** UE 4.27.2 at `D:\UE_4.27`, Blueprint-only project `comp4900sef/comp4900sef.uproject`, PhysXVehicles, UMG, Functional Testing framework, editor Python 3.7 reached with `python tools/ue_remote.py --code "..."`, headless tests with `tools/run_tests.ps1`.

**Spec:** `docs/superpowers/specs/2026-10-30-phase3-items-design.md` (rules §2–§9, acceptance §11). Base designs: `docs/superpowers/specs/2026-10-20-dead-fire-design.md`, `docs/superpowers/specs/2026-10-21-phase2-race-flow-design.md`.

## Execution record (2026-10-30)

Executed natively by the agent, task by task with a failing apply or test watched before each implementation; every task is done except the Task 8 Step 5 playtest (a person). Ledger with every ruling: `.superpowers/sdd/2026-10-30-phase3-items-plans/progress.md` (git-ignored). Where the result differs from the task text below:

- **Runner changes** (`comp4900sef/Script/df_apply_blueprint.py`): a function that already exists is removed and re-added in pass 1, because the plugin's `AddFunction` is idempotent and silently kept `BPC_DFWeapon.Fire`'s old inputs (Task 4); `_value` maps lists element-wise so `"override_materials": [path]` sets a component template's materials (Task 3).
- **Task 2**: `RestartRace` does not call `ClearEffects` itself; `RespawnRacer`, which it calls, now clears the car's effects on both of its paths.
- **Task 3**: the bomb test moves a settled car onto the armed bomb with `SetActorLocation` instead of spawning it there, because overlap events dispatch at spawn before `BeginPlay` (the car would be hit before `InitTires`).
- **Task 4**: the two existing `FT_DFWeapon_*` tests were re-applied unchanged; their `Fire` call gains an unlinked `Instigator` pin (no kill credit, which they never asserted).
- **Task 5**: a crate's `Charges` default is 0 = "the type's box charges"; the `Trigger` sphere has absolute scale so the crate's 0.8 scale does not shrink it.
- **Task 6**: the Shield crate moved from (9500, 6800) to (7000, 6500), out of the shortcut's 15 m margin; the rock is a 4 × 16 × 4 m cube (`SM_Rock` has no collision); the shortcut measures 9087 cm in 17 pieces.
- **Task 8**: the Starter Content materials (gold, steel, copper, basalt) and their textures would have added 65 MB to the repo, so the crate, bomb, rocket and rock use the committed VehicleAdv material instances instead; the force-added closure is the particles, sound and shapes.
- **Harness**: shell commands over about 6 KB are truncated by the tool, so every long patch was written to the scratchpad and run by path.
- **Final review fix pass** (reviewer findings, see the ledger): the shortcut's slabs had been laid along a closed loop (17 pieces for an open 9087 cm spline) because the spline's loop flag is not component instance data and reverted on the construction-script rerun; `BP_DFTrackSpline.bClosedTrack` (Instance Editable) is now applied by `RebuildTrack` itself, the builder pulls the middle point only 10 % toward the centroid and refuses a shortcut with the wrong piece count, less than 10 m of saving, or a rock corner within 9 m of the main centre line (result: 7505 cm in 8 pieces, 17.8 m saved, rock 17.5 m in). Crates are overlap-only (cars drive through). `FireRPG` traces from the car's centre to the muzzle and starts the rocket 25 cm short of anything blocking, and `SpawnExplosion` ignores the shooter's own car for line of sight (a trace that starts inside a body reports it at distance 0) while applying its self-damage directly. Starter Content shapes have their pivot at the base, so the rock's base sits on the road. Rocket launches and bomb/rocket explosions write `DF:` log lines.
- Totals: 62 manifests, 40 functional tests (24 + 16), `VERIFY PASSED`, full headless suite green; three editor screenshots checked for the item row, amber selection, hint and `PICKED UP` flash.

## Global Constraints

- Generated Blueprints are never edited by hand; change the module, regenerate, re-apply. Every `tools/bpgen/graphs/*.py` module exposes `build()` returning a `Blueprint`/`WidgetBlueprint`/`Struct`/`Enum` or a list of them; new modules are added to `MODULES` in `tools/bpgen/generate_all.py`.
- Asset paths: `BP_DF*` in `/Game/DeadFire/Blueprints/`, `BPC_DF*` in `Components/`, `S_DF*`/`E_DF*` in `Data/`, `WBP_DF*` in `UI/`, `FT_DF*` in `Tests/`. New this phase: `BP_DFExplosiveDamage`, `BP_DFLootBox`, `BP_DFBomb`, `BP_DFProjectile`, `BP_DFDestructible`, `E_DFItemType`, `S_DFItemStack`.
- Tunables are variables with Instance Editable on, category `Dead Fire|<Area>`; hooks are Event Dispatchers with the spec's names (`OnExplosion`, `OnItemPickedUp`, `OnLootCollected`, `OnDestructibleDestroyed`).
- Spec values (§8): slots 3; box charges / cap Boost 1/3, Shield 1/2, Bomb 1/3, Gun 8/24, RPG 1/2; loot respawn 30 s; boost kick 1200 cm/s, acceleration 2500 cm/s², duration 2 s; shield 6 s; bomb drop offset 400 cm, arm 1 s, fuse 8 s, damage 60, radius 500; vehicle gun damage 15, range 10000, cooldown 0.2; muzzle forward 300, up 80; rocket speed 6000, life 4 s, damage 80, radius 600; explosion impulse 800 cm/s (velocity change, linear falloff), tire blast 30; wreck hop 600 cm/s; destructible health 60; pickup flash 1.5 s. Explosions deal full damage inside the radius, check line of sight on Visibility, use `BP_DFExplosiveDamage`.
- Item names (HUD and logs): `BOOST`, `SHIELD`, `BOMB`, `GUN`, `RPG`; `E_DFItemType` order `None, Boost, Shield, Bomb, Gun, RPG` (indices 0–5; `df.py` exports `ITEM_NONE..ITEM_RPG`).
- Enum values are compared with `KismetMathLibrary.EqualEqual_ByteByte` (A = the enum pin, B = the index as a byte literal), the pattern `game_mode.py` already uses for `E_DFRaceEndReason`; enum literals on pins are `enum_value(index)` (`NewEnumeratorN`).
- Engine names must be exact: run `python -I tools/bpgen/sig.py Class.Function` before writing any call node not already used in the codebase. Known this phase: `GameplayStatics.ApplyRadialDamage(WorldContextObject, BaseDamage, Origin, DamageRadius, DamageTypeClass, IgnoreActors, DamageCauser, InstigatedByController, bDoFullDamage, DamagePreventionChannel)` (`IgnoreActors` is AutoCreateRefTerm and may stay unlinked), `GameplayStatics.SpawnEmitterAtLocation(WorldContextObject, EmitterTemplate, Location, Rotation, Scale, bAutoDestroy, PoolingMethod, bAutoActivateSystem)`, `GameplayStatics.SpawnEmitterAttached(EmitterTemplate, AttachToComponent, AttachPointName, Location, Rotation, Scale, LocationType, bAutoDestroy, PoolingMethod, bAutoActivate)`, `GameplayStatics.PlaySoundAtLocation(WorldContextObject, Sound, Location, Rotation, VolumeMultiplier, PitchMultiplier, StartTime, AttenuationSettings, ConcurrencySettings, OwningActor)`, `PrimitiveComponent.AddRadialImpulse(Origin, Radius, Strength, Falloff, bVelChange)` with `Falloff` enum `/Script/PhysicsCore.ERadialImpulseFalloff` value `RIF_Linear`, `PrimitiveComponent.AddImpulse(Impulse, BoneName, bVelChange)`, `PrimitiveComponent.AddForce(Force, BoneName, bAccelChange)`, `PrimitiveComponent.SetPhysicsLinearVelocity(NewVel, bAddToCurrent, BoneName)`, `PrimitiveComponent.IgnoreActorWhenMoving(Actor, bShouldIgnore)`, `Actor.SetLifeSpan(InLifespan)`, `Actor.ReceiveActorBeginOverlap(OtherActor)`, `Actor.ReceiveHit(MyComp, Other, OtherComp, bSelfMoved, HitLocation, HitNormal, NormalImpulse, Hit)`, `KismetMathLibrary.RandomIntegerInRange(Min, Max)`. The 4.27 Spawn Actor node has `Owner` but no instigator pin: bombs and rockets carry an explicit `InstigatorController` variable.
- The first component added to an Actor Blueprint becomes its root (the plugin adds parentless SCS nodes in order; `BP_DFCheckpoint`'s `Trigger` is its root). The rocket's `Collision` sphere and the bomb's `Shell` are therefore added first.
- Component properties in manifests go through `set_editor_property` on the template, or `"call:<method>": arg` for one-argument setters (e.g. `"call:set_collision_profile_name": "OverlapOnlyPawn"`). Asset references on Blueprints are variables with `bp.default(name, "/Game/...")` (loaded by path), the pattern `track.py` uses for `RoadMesh`.
- Starter Content assets used: `/Game/StarterContent/Particles/P_Explosion`, `/Game/StarterContent/Particles/P_Smoke`, `/Game/StarterContent/Particles/P_Fire`, `/Game/StarterContent/Audio/Explosion_Cue`, `/Game/StarterContent/Shapes/Shape_Cube`, `/Game/StarterContent/Shapes/Shape_Sphere` (100 cm shapes; the pack is inserted on first open by `DefaultGame.ini`). Crate, bomb, rocket and rock use the already-committed `/Game/VehicleAdv/Materials/MaterialInstances/{SolidOrange,SolidRed,BlackGrid}` so the force-added Starter Content closure stays small.
- Pipeline commands (repo root `E:/VSC projects/comp4900sef-gp3`, editor running with Python remote execution; `tools/restart_editor.ps1` starts it):
  - Generate: `python -I tools/bpgen/generate_all.py` → `generated N manifests`.
  - Apply: `python tools/ue_remote.py --code "exec(open(r'E:/VSC projects/comp4900sef-gp3/comp4900sef/Script/df_apply_blueprint.py').read()); apply_all(r'E:/VSC projects/comp4900sef-gp3/comp4900sef/Script/paste', only=[...])"` → `APPLY OK: N manifests, 0 failed` (omit `only` for everything; full log `comp4900sef/Saved/df_apply.log`). Pass every manifest a task touches **and** every new asset the touched graphs reference.
  - Levels: `python tools/ue_remote.py --code "exec(open(r'E:/VSC projects/comp4900sef-gp3/comp4900sef/Script/df_build_test_track.py').read())"` → `df_build_test_track: OK; ...` (places one actor per `FT_DF*` class, so rebuild after adding tests).
  - Verify: `python tools/ue_remote.py --code "exec(open(r'E:/VSC projects/comp4900sef-gp3/comp4900sef/Script/df_verify_blueprints.py').read()); verify_all(r'E:/VSC projects/comp4900sef-gp3/comp4900sef/Script/paste')"` → `VERIFY PASSED`.
  - Tests: `powershell -NoProfile -ExecutionPolicy Bypass -File tools/run_tests.ps1 [-Filter "Project.Functional Tests./Game/DeadFire/Tests/L_DF_FunctionalTests.FT_DFItem"]` → `N passed, 0 failed, N found`. Never run `Automation RunTests` inside the GUI editor (it leaves PIE running); if PIE is running, end it with `unreal.EditorLevelLibrary.editor_end_play()` before applying or building.
  - `ue_remote.py` replies overflow past ~4 KB: print one short line.
- Functional tests share one play session: every item test starts from `race_context(t)` (which calls `RestartRace`) or clears the state it reads; headless frames are ~0.4 s, waits for a tick are ≥ 1 s; spawns use `AlwaysSpawn`; `bTreatLogWarningsAsTestErrors=False` (the Sedan `BoneIndex` warning is noise).
- No commits during the plan: the project manager commits. Leave the tree ready and list the commit command in the final report. Ledger: `.superpowers/sdd/2026-10-30-phase3-items/progress.md` (git-ignored), one entry per task with every ruling.
- Work in place (no worktree): the editor is open on this checkout and the Content folder is too large to duplicate.

## Review Focus

1. Using an item from a wrecked car: refused, nothing consumed (Task 2, `FT_DFItem_UseConsumesAndRefusesWhenEmpty`).
2. A shield protects the tires as well as the body: point damage on a wheel bone while shielded blows nothing (Task 2, `FT_DFItem_ShieldBlocksDamage`).
3. A bomb must not detonate on the car that drops it before arming: right after `DropBomb` the bomb is unarmed and the dropper is undamaged half a second later (Task 3, `FT_DFBomb_ArmedBombDamagesAndBlowsTire`).
4. A wreck's explosion (`Damage` 0) hurts nobody next to it (Task 1, `FT_DFExplosion_DamagesKicksAndBlowsTire`).
5. A pickup the inventory cannot take (three other types held) is refused and the crate stays (Task 5, `FT_DFLoot_PickupOnFootOnly`).

---

## File structure

```
tools/bpgen/df.py                              modify: new asset constants, ITEM_* indices, enum_is(), get_all_actors_of_class(), PARTICLE_SYSTEM/SOUND_BASE
tools/bpgen/graphs/data.py                     modify: E_DFItemType, S_DFItemStack
tools/bpgen/graphs/racer.py                    modify: inventory variables and functions on BPC_DFRacer
tools/bpgen/graphs/game_mode.py                modify: GetItemInfo, GrantItem, CycleItem, SpawnExplosion, effect assets, RestartRace/RespawnRacer additions
tools/bpgen/graphs/weapon.py                   modify: Fire(Origin, Direction, Instigator)
tools/bpgen/graphs/character.py                modify: Fire passes the controller; NextItem input
tools/bpgen/graphs/vehicle.py                  modify: Weapon component, effects, item use, gun/RPG/bomb, wreck effects, inputs
tools/bpgen/graphs/items.py                    create: BP_DFExplosiveDamage, BP_DFLootBox, BP_DFBomb, BP_DFProjectile, BP_DFDestructible
tools/bpgen/graphs/hud.py                      modify: item row, effect line, hint, pickup flash
tools/bpgen/graphs/tests_items.py              create: FT_DFItem_*, FT_DFExplosion_*, FT_DFBomb_*, FT_DFProjectile_*, FT_DFLoot_*, FT_DFDestructible_*, FT_DFTrack_Shortcut*, FT_DFHUD_ItemRow*
tools/bpgen/graphs/tests.py                    modify: screenshot test picks up an item first
tools/bpgen/generate_all.py                    modify: MODULES += "items", "tests_items"
comp4900sef/Script/df_build_test_track.py      modify: LOOT_BOXES, shortcut spline, rock
comp4900sef/Config/DefaultInput.ini            modify: NextItem action
README.md, docs/superpowers/playtest-checklist.md, docs/superpowers/specs/2026-10-20-dead-fire-design.md   modify (Task 8)
```

`tests_items.py` imports `T`, `spawn_vehicle`, `spawn_character`, `race_context`, `tire` from `tests` (add `sys.path.insert(0, os.path.dirname(__file__))` before the import; `generate_all.py` loads modules by path, so `tests` must be importable by name from the graphs folder).

---

### Task 0: Data types, inventory on the racer, item info and grants on the GameMode

**Files:**
- Modify: `tools/bpgen/df.py`, `tools/bpgen/graphs/data.py`, `tools/bpgen/graphs/racer.py`, `tools/bpgen/graphs/game_mode.py`, `tools/bpgen/generate_all.py`
- Create: `tools/bpgen/graphs/tests_items.py`

**Interfaces:**
- Produces (`df.py`): `E_ITEM_TYPE = DATA + "/E_DFItemType"`, `S_ITEM_STACK = DATA + "/S_DFItemStack"`, `BP_LOOTBOX`, `BP_BOMB`, `BP_PROJECTILE`, `BP_DESTRUCTIBLE`, `BP_EXPLOSIVE_DAMAGE` (all under `BPS`), `ITEM_NONE, ITEM_BOOST, ITEM_SHIELD, ITEM_BOMB, ITEM_GUN, ITEM_RPG = 0..5`, `ITEM_NAMES = ["-", "BOOST", "SHIELD", "BOMB", "GUN", "RPG"]`, `PARTICLE_SYSTEM = "/Script/Engine.ParticleSystem"`, `SOUND_BASE = "/Script/Engine.SoundBase"`, `enum_is(g, src, index) -> Node` (pure `EqualEqual_ByteByte`, `ReturnValue` bool; `src` is a `(node, pin)` or `("entry", pin)` source), `get_all_actors_of_class(g, class_path) -> Node` (impure; `OutActors` array pin).
- Produces (`BPC_DFRacer`, category `Dead Fire|Items`): variables `Inventory: array<S_DFItemStack>`, `SelectedSlot: int = 0`, `MaxSlots: int = 3` (editable), `LastPickupTime: float = -1`, `LastPickupType: E_DFItemType`; functions `AddItem(Type: E_DFItemType, Charges: int, MaxCharges: int) -> ReturnValue: bool`, `GetSelected() -> Type: E_DFItemType, Charges: int` (pure; None/0 when empty), `ConsumeSelected() -> Type: E_DFItemType` (None when empty; removes a stack at 0 and sets `SelectedSlot` to 0), `CycleSelected()`, `ClearInventory()` (also `SelectedSlot` 0, `LastPickupTime` -1).
- Produces (`BP_DFRaceGameMode`): `GetItemInfo(Type: E_DFItemType) -> Name: string, BoxCharges: int, MaxCharges: int` (pure; `-`/0/0 for None), `GrantItem(C: Controller, Type: E_DFItemType, Charges: int) -> ReturnValue: bool` (looks up the racer and the cap, calls `AddItem`, on success stamps `LastPickupTime`/`LastPickupType`, logs `DF: pickup <Name> x<Charges> by <C>`, fires `OnItemPickedUp(Racer: Controller, Type: E_DFItemType)`), `CycleItem(C: Controller)`; `RestartRace` calls `ClearInventory` on the player's racer.

- [ ] **Step 1: Add the types** — in `data.py` append `Enum(E_ITEM_TYPE, ["None", "Boost", "Shield", "Bomb", "Gun", "RPG"])` and `Struct(S_ITEM_STACK).member("Type", enum_spec(E_ITEM_TYPE)).member("Charges", "int", "0")`; add the constants and helpers to `df.py`.

- [ ] **Step 2: Write the failing test** — `tests_items.py` with `FT_DFItem_InventoryStacksAndCaps` ("Items stack to their cap, a fourth type is refused, cycling and consuming walk the slots."): `race_context`; `AddItem(Shield, 1, 2)` true; `AddItem(Shield, 1, 2)` true; `AddItem(Shield, 1, 2)` false (at cap); `AddItem(Boost, 1, 3)` true; `AddItem(Bomb, 1, 3)` true; `AddItem(Gun, 8, 24)` false (no slot); `Array_Length(Inventory)` == 3; `GetSelected` → Type Shield, Charges 2 (compare `Conv_ByteToInt(Type)` == 2); `CycleSelected` → `SelectedSlot` 1; `CycleSelected` twice more → 0; `ConsumeSelected` → Shield, then again → Shield, then `Array_Length` == 2 and `GetSelected` Type Boost; `ClearInventory` → length 0. Add `MODULES += ["items", "tests_items"]` (the `items` module may not exist yet: `generate_all.load` returns `None` for a missing file).

- [ ] **Step 3: Generate and apply the test only** — `python -I tools/bpgen/generate_all.py`; apply `only=["E_DFItemType", "S_DFItemStack", "FT_DFItem_InventoryStacksAndCaps"]`. Expected: the apply reports the `FT_` manifest FAILED (unknown functions `AddItem` ... on `BPC_DFRacer`) — the red step.

- [ ] **Step 4: Implement the racer inventory** in `racer.py` (`build_racer`): the five variables and five functions. `AddItem`: loop `Inventory` for a stack of the same `Type` (`enum_is` on the broken struct's `Type` against `Conv_ByteToInt`... no: compare the two enum pins with `EqualEqual_ByteByte` A=element Type, B=input Type); if found, new charges = `Min(Charges + old, MaxCharges)`, write back with `Array_Set`, return `new > old`; else if `Array_Length < MaxSlots` append `MakeStruct(Type, Min(Charges, MaxCharges))`, return true; else false. `ConsumeSelected`: when `SelectedSlot < length`, decrement, `Array_Set`; if the result is 0 `Array_RemoveIndex(SelectedSlot)` and `SelectedSlot = 0`; return the type. `CycleSelected`: `SelectedSlot = (SelectedSlot + 1) % Max(1, length)`.

- [ ] **Step 5: Implement `GetItemInfo`, `GrantItem`, `CycleItem` in `game_mode.py`** — `GetItemInfo` is a chain of five `enum_is` branches each ending in a function-result node with literal `Name`/`BoxCharges`/`MaxCharges` (Boost `BOOST`/1/3, Shield `SHIELD`/1/2, Bomb `BOMB`/1/3, Gun `GUN`/8/24, RPG `RPG`/1/2, fallthrough `-`/0/0). `GrantItem` as in Interfaces (`LastPickupTime` = `GetTimeSeconds`). Add the dispatcher `OnItemPickedUp`. In `RestartRace`, after the racer stats reset, call `ClearInventory` on `R_`.

- [ ] **Step 6: Generate, apply, rebuild the test level, run** — apply `only=["E_DFItemType", "S_DFItemStack", "BPC_DFRacer", "BP_DFRaceGameMode", "FT_DFItem_InventoryStacksAndCaps"]` → `APPLY OK`; build levels; `run_tests.ps1 -Filter "...FT_DFItem"` → `1 passed, 0 failed, 1 found`. Then the full suite → `25 passed, 0 failed, 25 found`.

- [ ] **Step 7: Ledger** — create `.superpowers/sdd/2026-10-30-phase3-items/progress.md` with the task entry and any engine-name ruling made.

---

### Task 1: Explosions, explosive damage type, tire blast, wreck effects

**Files:**
- Create: `tools/bpgen/graphs/items.py` (first asset: `BP_DFExplosiveDamage`)
- Modify: `tools/bpgen/graphs/game_mode.py`, `tools/bpgen/graphs/vehicle.py`, `tools/bpgen/graphs/tests_items.py`

**Interfaces:**
- Consumes: `get_all_actors_of_class`, `GetItemInfo` (not needed here), `ApplyTireDamage(Index, Damage)` on the vehicle.
- Produces: `BP_DFExplosiveDamage` (parent `/Script/Engine.DamageType`, no members). On `BP_DFRaceGameMode` (category `Dead Fire|Explosions`): `ExplosionEffect: object:ParticleSystem` (default `P_Explosion`), `ExplosionSound: object:SoundBase` (default `Explosion_Cue`), `ExplosiveDamageType: class:DamageType` (default `class:` `BP_DFExplosiveDamage`), `TireBlastDamage: float = 30`, `ExplosionImpulse: float = 800`, all editable; `SpawnExplosion(Location: vector, Damage: float, Radius: float, InstigatedBy: Controller, Causer: Actor, bBlowTires: bool)`; dispatcher `OnExplosion(Location: vector, Radius: float)`. On `BP_DFVehicle`: `BlowNearestTire(Point: vector, Damage: float)` (nearest wheel socket by `GetSocketLocation`, any distance; no-op when destroyed or shielded — `IsShielded` arrives in Task 2, so for now only the destroyed check), `WreckHopImpulse: float = 600`, `WreckSmokeEffect: object:ParticleSystem` (default `P_Smoke`), both editable in `Dead Fire|Items`.

- [ ] **Step 1: Write the failing test** — `FT_DFExplosion_DamagesKicksAndBlowsTire` ("An explosion damages a car in range for the full amount, blows its nearest tire, spares a character beside it, and an effects-only explosion hurts nobody."): `race_context`; spawn a car at the test actor (`spawn_vehicle`) and a character 2 m to its side (`spawn_character(t, 0, 200)`), delay 1; `SpawnExplosion(loc(car) + (150, 0, 0), 60, 500, player, none, true)`; car `Health` == 40 (tolerance 0.5); `GetBlownTireCount` == 1; character `Health` == 100; a second car 8 m away (`spawn_vehicle(t, 800)`), `SpawnExplosion(loc(car2), 0, 0, none, none, false)` → car2 `Health` == 100 and blown tires 0.

- [ ] **Step 2: Generate and apply the test** (`only=["FT_DFExplosion_DamagesKicksAndBlowsTire"]`) — expected FAILED on the unknown `SpawnExplosion`.

- [ ] **Step 3: Implement** — `items.py` `build()` returns `[Blueprint(BP_EXPLOSIVE_DAMAGE, parent="/Script/Engine.DamageType")]`. In `character.py`'s `ReceiveAnyDamage`, before the dead/stowed check, cast `DamageType` to `BP_DFExplosiveDamage`: on success do nothing (characters are immune to explosions, spec §5). `SpawnExplosion` body order: `SpawnEmitterAtLocation(ExplosionEffect, Location, rot 0, scale 1,1,1, bAutoDestroy true, PoolingMethod None, bAutoActivateSystem true)`; `PlaySoundAtLocation(ExplosionSound, Location, ...)`; branch `Damage > 0` → `ApplyRadialDamage(Damage, Location, Radius, ExplosiveDamageType, IgnoreActors unlinked, Causer, InstigatedBy, bDoFullDamage true, DamagePreventionChannel ECC_Visibility)`; then `get_all_actors_of_class(BP_DFVehicle)` → ForEach: skip when element == Causer or `Vector_Distance(element location, Location) > Radius`; else `Mesh.AddRadialImpulse(Location, Radius, ExplosionImpulse, RIF_Linear, bVelChange true)` and, when `bBlowTires`, `BlowNearestTire(Location, TireBlastDamage)`; finally `OnExplosion`. `DestroyVehicle` in `vehicle.py`: after the handbrake, cast the GameMode once; from it `SpawnExplosion(GetActorLocation, 0, 0, Killer, self, false)`, `Mesh.AddImpulse((0,0,WreckHopImpulse), None, bVelChange true)`, `SpawnEmitterAttached(WreckSmokeEffect, Mesh, None, (0,0,100), rot 0, scale 1,1,1, KeepRelativeOffset, bAutoDestroy false, None, true)`, then the existing `OnVehicleDestroyed` and `NotifyVehicleDestroyed`.

- [ ] **Step 4: Generate, apply, build, run** — apply `only=["BP_DFExplosiveDamage", "BP_DFRaceGameMode", "BP_DFVehicle", "BP_DFCharacter", "FT_DFExplosion_DamagesKicksAndBlowsTire"]` → `APPLY OK`; build levels; `run_tests.ps1 -Filter "...FT_DFExplosion"` → `1 passed`; `-Filter "...FT_DFVehicle"`, `"...FT_DFCharacter"` and `"...FT_DFRespawn"` still green (the wreck and character damage paths changed).

- [ ] **Step 5: Ledger entry.**

---

### Task 2: Vehicle effects and item use (Boost, Shield, select, consume, inputs)

**Files:**
- Modify: `tools/bpgen/graphs/vehicle.py`, `tools/bpgen/graphs/character.py`, `tools/bpgen/graphs/game_mode.py` (`RespawnRacer`, `RestartRace`), `comp4900sef/Config/DefaultInput.ini`, `tools/bpgen/graphs/tests_items.py`

**Interfaces:**
- Consumes: `GetSelected`, `ConsumeSelected`, `CycleItem(C)`, `GetItemInfo`, `FindRacer(C)`.
- Produces on `BP_DFVehicle` (category `Dead Fire|Items`): variables `BoostRemaining: float = 0`, `ShieldRemaining: float = 0`, `BoostDuration: float = 2` (e), `BoostKickSpeed: float = 1200` (e), `BoostAcceleration: float = 2500` (e), `ShieldDuration: float = 6` (e); functions `ActivateBoost()` (sets `BoostRemaining = BoostDuration`, `Mesh.SetPhysicsLinearVelocity(GetActorForwardVector * BoostKickSpeed, bAddToCurrent true)`), `ActivateShield()`, `IsShielded() -> ReturnValue: bool` (pure, `ShieldRemaining > 0`), `TickEffects(DeltaSeconds: float)` (boost: `Mesh.AddForce(Forward * BoostAcceleration, None, bAccelChange true)` while `BoostRemaining > 0`; both timers decrease, clamped at 0), `ClearEffects()`, `CanUseItem(Type: E_DFItemType) -> ReturnValue: bool` (pure; true for every type until Task 4 adds the gun cooldown), `ApplyItem(Type: E_DFItemType)` (Boost/Shield now; Bomb/Gun/RPG branches added in Tasks 3–4), `UseSelectedItem() -> ReturnValue: bool` (refused when `bIsDestroyed`, no controller, no racer, selected None, or `CanUseItem` false; otherwise `ConsumeSelected` then `ApplyItem`, log `DF: used <Name> by <C>`), `CycleItem()` (GameMode `CycleItem(GetController)`). `TakeDamageInternal` returns early while shielded (after the destroyed check); `BlowNearestTire` also returns early while shielded. Event graph: Tick calls `TickEffects` after `TickDriveOverrides`; `UseItem` Pressed → `UseSelectedItem`; `NextItem` Pressed → `CycleItem`.
- Produces on `BP_DFCharacter`: `NextItem` Pressed → GameMode `CycleItem(GetController)`.
- Produces on `BP_DFRaceGameMode`: `RespawnRacer` calls `ClearEffects` on `Car` after the handbrake release; `RestartRace` calls `ClearEffects` on the player's pawn car (cast of `K2_GetPawn`) after `RespawnRacer`.
- `DefaultInput.ini`: `+ActionMappings=(ActionName="NextItem",...Key=R)`, `Key=MouseScrollUp`, `Key=Gamepad_DPad_Right` under `; --- Shared ---`.

- [ ] **Step 1: Write the failing tests** —
  - `FT_DFItem_UseConsumesAndRefusesWhenEmpty` ("Using the selected item consumes one charge; an empty inventory and a wrecked car refuse."): `race_context`; `GrantItem(pc, Boost, 1)` true; player's car (`CurrentVehicle`) `UseSelectedItem` true; `Array_Length(Inventory)` == 0; `UseSelectedItem` false; `GrantItem(pc, Shield, 1)`; `DestroyVehicle(none)` on the car; `UseSelectedItem` false; `Array_Length(Inventory)` == 1.
  - `FT_DFItem_BoostKicksCar` ("Boost sets the timer and kicks the car to at least 35 km/h at once."): `race_context`; player's car `ActivateBoost`; `BoostRemaining` > 1.5 (`less` on the negative is awkward: assert `Greater_FloatFloat(BoostRemaining, 1.5)` true); delay 0.2; `GetSpeedKPH` > 35; `ClearEffects` → `BoostRemaining` == 0.
  - `FT_DFItem_ShieldBlocksDamage` ("While shielded, body and tire damage are ignored; after the shield they apply."): `race_context`; spawn a car; delay 1; `ActivateShield`; `IsShielded` true; `damage(car, 50)` → `Health` 100; `point_damage(car, 30, "Wheel_Front_Left")` → tire 0 `bBlown` false; `ClearEffects`; `damage(car, 50)` → `Health` 50.
  - `FT_DFItem_RestartClearsItemsAndEffects` ("RestartRace empties the inventory and clears the car's effects."): `race_context`; `GrantItem(pc, Shield, 1)`; player's car `ActivateShield`; `RestartRace`; delay 0.5; `Array_Length(Inventory)` == 0; the player's car (`pawn_car`-style cast of `K2_GetPawn`) `ShieldRemaining` == 0.

- [ ] **Step 2: Generate and apply the tests** — expected FAILED on the unknown vehicle functions.

- [ ] **Step 3: Implement** the Interfaces above in `vehicle.py`, `character.py`, `game_mode.py`, `DefaultInput.ini`.

- [ ] **Step 4: Generate, apply, build, run** — apply `only=["BP_DFVehicle", "BP_DFCharacter", "BP_DFRaceGameMode"] + the four tests` → `APPLY OK`; build; `run_tests.ps1 -Filter "...FT_DFItem"` → `5 passed`; full suite → `30 passed, 0 failed, 30 found`.

- [ ] **Step 5: Ledger entry.**

---

### Task 3: Bomb

**Files:**
- Modify: `tools/bpgen/graphs/items.py`, `tools/bpgen/graphs/vehicle.py`, `tools/bpgen/graphs/game_mode.py` (`RestartRace`), `tools/bpgen/graphs/tests_items.py`

**Interfaces:**
- Consumes: `SpawnExplosion`, `ApplyItem`, `enum_is`.
- Produces `BP_DFBomb` (parent Actor): component `Shell` (StaticMeshComponent, first → root; `static_mesh` `Shape_Sphere`, `relative_scale3d` (0.5, 0.5, 0.5), `"call:set_collision_profile_name": "OverlapOnlyPawn"`, `override_materials` `[M_Metal_Burnished_Steel]` if the runner accepts the array, else no material); variables (`Dead Fire|Bomb`) `ArmDelay: float = 1` (e), `FuseSeconds: float = 8` (e), `Damage: float = 60` (e), `Radius: float = 500` (e), `bArmed: bool`, `bExploded: bool`, `SpawnTime: float`, `InstigatorController: object:Controller`; functions `Arm()`, `Detonate()` (once: `SpawnExplosion(GetActorLocation, Damage, Radius, InstigatorController, self, true)` then `DestroyActor`), `PlaceOnGround()` (`LineTraceSingle` from location + (0,0,100) to location − (0,0,400) on Visibility ignoring self; on hit `SetActorLocation(ImpactPoint + (0,0,30))`). Events: BeginPlay → `SpawnTime = GetTimeSeconds`, `PlaceOnGround`; Tick → `Arm` when `now − SpawnTime ≥ ArmDelay`, `Detonate` when `now − SpawnTime ≥ FuseSeconds`; `ReceiveActorBeginOverlap(OtherActor)` → when `bArmed` and the actor casts to `BP_DFVehicle` → `Detonate`.
- Produces on `BP_DFVehicle`: `BombDropOffset: float = 400` (e); `DropBomb() -> Bomb: object:BP_DFBomb` (spawn at `GetActorLocation − Forward * BombDropOffset + (0,0,30)`, rotation of the car, Owner self, AlwaysSpawn; set `InstigatorController = GetController`); `ApplyItem` Bomb branch → `DropBomb`.
- Produces on `BP_DFRaceGameMode`: `RestartRace` destroys every `BP_DFBomb` (and, from Task 4, every `BP_DFProjectile`) in the level.

- [ ] **Step 1: Write the failing tests** —
  - `FT_DFBomb_ArmedBombDamagesAndBlowsTire` ("A dropped bomb starts unarmed and leaves its dropper alone; an armed bomb under a car damages it, blows a tire and disappears."): `race_context`; player's car `DropBomb` → valid, `bArmed` false; delay 0.5; player's car `Health` == 100; then spawn a `BP_DFBomb` at test location + (0, 600, −150), `Arm`; spawn a car on it (`spawn_vehicle(t, 0, 600)`); delay 1.5; car `Health` == 40 (tolerance 0.5); `GetBlownTireCount` == 1; the bomb is no longer valid.
  - `FT_DFBomb_FuseDetonates` ("With the fuse run out a bomb detonates on its own and damages a car 3 m away."): spawn a bomb at + (0, 0, −150), set `ArmDelay` 0 and `FuseSeconds` 0.3; `spawn_vehicle(t, 300)`; delay 1.5; car `Health` == 40; bomb invalid.
  - Extend `FT_DFItem_RestartClearsItemsAndEffects`: before `RestartRace`, `DropBomb`; after it, `GetAllActorsOfClass(BP_DFBomb)` length == 0.

- [ ] **Step 2: Generate and apply the tests** — expected FAILED (unknown `BP_DFBomb` / `DropBomb`).

- [ ] **Step 3: Implement** per Interfaces. After applying, confirm the root: in the editor `a = unreal.EditorLevelLibrary.spawn_actor_from_class(bp_class('/Game/DeadFire/Blueprints/BP_DFBomb'), unreal.Vector(0,0,0)); print(a.root_component.get_name()); unreal.EditorLevelLibrary.destroy_actor(a)` → `Shell`.

- [ ] **Step 4: Generate, apply, build, run** — apply `only=["BP_DFBomb", "BP_DFVehicle", "BP_DFRaceGameMode"] + tests` → `APPLY OK`; build; `-Filter "...FT_DFBomb"` → `2 passed`; `-Filter "...FT_DFItem"` → `5 passed`.

- [ ] **Step 5: Ledger entry** (record whether `override_materials` worked).

---

### Task 4: Gun on the vehicle, rocket, explicit weapon instigator

**Files:**
- Modify: `tools/bpgen/graphs/weapon.py`, `tools/bpgen/graphs/character.py`, `tools/bpgen/graphs/vehicle.py`, `tools/bpgen/graphs/items.py`, `tools/bpgen/graphs/game_mode.py` (`RestartRace`), `tools/bpgen/graphs/tests_items.py`, `tools/bpgen/graphs/tests.py` (the two `FT_DFWeapon_*` tests pass an `Instigator` pin: link the player controller)

**Interfaces:**
- Produces on `BPC_DFWeapon`: `Fire(Origin: vector, Direction: vector, Instigator: Controller) -> bHit: bool, Hit: HitResult` — `Instigator` goes straight into `ApplyPointDamage.EventInstigator` (the owner lookup is dropped).
- Produces on `BP_DFCharacter`: `Fire` passes `GetController`.
- Produces on `BP_DFVehicle`: component `Weapon` (class `BPC_DFWeapon`; properties `Damage` 15, `Range` 10000, `Cooldown` 0.2, `bDebugTrace` false); variables `MuzzleForward: float = 300` (e), `MuzzleUp: float = 80` (e); `GetMuzzleLocation() -> Location: vector` (pure: `GetActorLocation + Forward * MuzzleForward + Up * MuzzleUp`); `FireGun() -> ReturnValue: bool` (`Weapon.Fire(GetMuzzleLocation, GetActorForwardVector, GetController)` → `bHit`); `FireRPG() -> Projectile: object:BP_DFProjectile` (spawn at the muzzle with the car's rotation, Owner self, AlwaysSpawn; `InstigatorController = GetController`); `CanUseItem` Gun → `Weapon.CanFire`; `ApplyItem` Gun → `FireGun`, RPG → `FireRPG`.
- Produces `BP_DFProjectile` (parent Actor): components in this order `Collision` (SphereComponent, `sphere_radius` 15, `"call:set_collision_profile_name": "BlockAllDynamic"`, `"call:set_notify_rigid_body_collision": true`), `Mesh` (StaticMeshComponent, parent `Collision`, `Shape_Sphere`, scale 0.3, `"call:set_collision_profile_name": "NoCollision"`), `Trail` (ParticleSystemComponent, parent `Collision`, `template` `P_Fire`, scale (0.3, 0.3, 0.3)), `Movement` (ProjectileMovementComponent: `initial_speed` 6000, `max_speed` 6000, `projectile_gravity_scale` 0.05, `rotation_follows_velocity` True, `should_bounce` False, `initial_velocity_in_local_space` True); variables (`Dead Fire|Rocket`) `Damage: float = 80` (e), `Radius: float = 600` (e), `LifeSeconds: float = 4` (e), `InstigatorController: object:Controller`, `bExploded: bool`; `Explode()` (once: `SpawnExplosion(GetActorLocation, Damage, Radius, InstigatorController, self, true)`, `DestroyActor`). Events: BeginPlay → `SetLifeSpan(LifeSeconds)`, and when `GetOwner` is valid `Collision.IgnoreActorWhenMoving(Owner, true)`; `ReceiveHit(...)` → `Explode`.
- Produces on `BP_DFRaceGameMode`: `RestartRace` also destroys every `BP_DFProjectile`.

- [ ] **Step 1: Write the failing tests** —
  - `FT_DFItem_GunShotHitsCarAhead` ("The car's gun hits a car 8 m ahead for 15."): `race_context`; the player's car; spawn a car at `loc(player car) + Forward * 800` (use `GetActorForwardVector` × 800 added to the location; same Z as the player car) — delay 1; `FireGun` true; target `Health` == 85.
  - `FT_DFProjectile_ExplodesOnHitAndCreditsKill` ("A rocket fired at a car 10 m ahead explodes on it; a lethal rocket credits the shooter with a kill and +50."): `race_context`; spawn a target 10 m ahead of the player's car (as above, 1000); delay 1; `FireRPG` → valid; delay 1.5; target `Health` == 20 (tolerance 0.5), rocket invalid; `FireRPG` again, set its `Damage` to 200 right after spawn; delay 1.5; target `bIsDestroyed` true; racer `Kills` == 1, `Score` == 50.

- [ ] **Step 2: Generate and apply the tests** — expected FAILED.

- [ ] **Step 3: Implement** per Interfaces (also update `tests.py`'s `fire()` helper to link `Instigator` to `t.player()`... the weapon tests have no player cast today: add `pc = t.player()` to those two tests and link it). After applying, confirm the rocket's root is `Collision` the way Task 3 did for the bomb.

- [ ] **Step 4: Generate, apply, build, run** — apply `only=["BPC_DFWeapon", "BP_DFCharacter", "BP_DFVehicle", "BP_DFProjectile", "BP_DFRaceGameMode", "FT_DFWeapon_HitscanDamagesVehicle", "FT_DFWeapon_RespectsCooldown"] + new tests` → `APPLY OK`; build; `-Filter "...FT_DFItem"` → `6 passed`, `"...FT_DFProjectile"` → `1 passed`, `"...FT_DFWeapon"` → `2 passed`.

- [ ] **Step 5: Ledger entry.**

---

### Task 5: Loot boxes

**Files:**
- Modify: `tools/bpgen/graphs/items.py`, `comp4900sef/Script/df_build_test_track.py`, `tools/bpgen/graphs/tests_items.py`

**Interfaces:**
- Consumes: `GrantItem`, `GetItemInfo`, `OwningController`/`bIsStowed`/`IsDead` on the character.
- Produces `BP_DFLootBox` (parent Actor): components `Crate` (StaticMeshComponent, first → root; `Shape_Cube`, scale (0.8, 0.8, 0.8), `"call:set_collision_profile_name": "BlockAllDynamic"`, `override_materials` `[M_Metal_Gold]` if Task 3 found it works), `Trigger` (SphereComponent, parent `Crate`, `sphere_radius` 150, `"call:set_collision_profile_name": "OverlapOnlyPawn"`); variables (`Dead Fire|Loot`) `ItemType: E_DFItemType` (e, default `enum_value(1)` = Boost), `Charges: int = 0` (e; 0 = the type's box charges), `bRandom: bool = false` (e), `bRespawns: bool = true` (e), `RespawnSeconds: float = 30` (e), `bCollected: bool`, `CollectedTime: float = -1`; dispatcher `OnLootCollected(Character: BP_DFCharacter, Type: E_DFItemType)`; functions `Pickup(Character: BP_DFCharacter) -> ReturnValue: bool` (refused when collected, character invalid, dead, stowed or without `OwningController`; charges = `Charges` if > 0 else `GetItemInfo(ItemType).BoxCharges`; `GrantItem` true → `bCollected`, `CollectedTime = now`, `SetActorHiddenInGame(true)`, `SetActorEnableCollision(false)`, fire the dispatcher), `Reset()` (when `bRandom`: `ItemType` = one of Boost..RPG by `RandomIntegerInRange(1, 5)` through five compare branches; `bCollected` false, visible, collision on). Events: BeginPlay → `Reset` when `bRandom`; Tick → `Reset` when `bCollected and bRespawns and now − CollectedTime ≥ RespawnSeconds`; `ReceiveActorBeginOverlap(OtherActor)` → cast `BP_DFCharacter` → `Pickup`.
- Produces in `df_build_test_track.py`: `LOOT_BOXES = [("Boost", (5000, 2500)), ("Shield", (9500, 6800)), ("Bomb", (2500, 8500)), ("Gun", (16500, 5500)), ("RPG", (-6500, 4500)), (None, (3000, 14000))]` (None = random), spawned at Z 45 with `ItemType` set through the wrapped enum type (`et = type(unreal.get_default_object(cls).get_editor_property('ItemType'))`; `getattr(et, name.upper())`) and `bRandom` for the last; the builder raises if any box is closer than 1500 cm to the main spline (`find_location_closest_to_world_location`) — after Task 6 also to the shortcut. Also one driverless `BP_DFVehicle` labelled `TargetCar` at the main spline's 3000 cm transform moved 1500 cm toward the infield (right-vector sign chosen so it lands inside the loop), Z 30, facing along the road (spec §3).

- [ ] **Step 1: Write the failing tests** —
  - `FT_DFLoot_PickupOnFootOnly` ("A crate ignores a car, is collected by a character on foot, and refuses a fourth item type."): `race_context`; spawn a `BP_DFLootBox` at + (0, 0, −150), set `ItemType` Shield; `spawn_vehicle` on it; delay 1; `bCollected` false; destroy the car (`K2_DestroyActor`); `spawn_character` on the crate, set its `OwningController` to the player **before** the overlap can fire (spawn the character 6 m away, set the controller, then `K2_SetActorLocation` onto the crate); delay 1; `bCollected` true; `Array_Length(Inventory)` == 1; `GetSelected` Type Shield, Charges 1; `bHidden` true on the crate. Then `GrantItem(pc, Boost, 1)`, `GrantItem(pc, Bomb, 1)`; a second crate with `ItemType` Gun; move the character onto it; delay 1; `bCollected` false (inventory full).
  - `FT_DFLoot_RespawnsAfterDelay` ("A collected crate comes back after its respawn delay."): `race_context`; crate with `RespawnSeconds` 0.5; character onto it as above; delay 1 → `bCollected` true; delay 1.5 → `bCollected` false, `bHidden` false.

- [ ] **Step 2: Generate and apply the tests** — expected FAILED.

- [ ] **Step 3: Implement** `BP_DFLootBox` and the builder additions; rebuild both levels (`df_build_test_track: OK` line now also reports `6 crates`).

- [ ] **Step 4: Generate, apply, build, run** — apply `only=["BP_DFLootBox"] + tests` → `APPLY OK`; build; `-Filter "...FT_DFLoot"` → `2 passed`; in the editor viewport of `L_TestTrack` six crates are visible off the road (screenshot with `FT_DFZZ_Screenshots` is Task 7).

- [ ] **Step 5: Ledger entry** (record the Python enum-setting code that worked).

---

### Task 6: Destructible rock and shortcut road

**Files:**
- Modify: `tools/bpgen/graphs/items.py`, `comp4900sef/Script/df_build_test_track.py`, `tools/bpgen/graphs/tests_items.py`

**Interfaces:**
- Produces `BP_DFDestructible` (parent Actor): component `Rock` (StaticMeshComponent, root; `Shape_Cube`, `override_materials` `[M_Rock_Basalt]` when supported, `"call:set_collision_profile_name": "BlockAllDynamic"`); variables (`Dead Fire|Destructible`) `Health: float = 60` (e), `bExplosivesOnly: bool = true` (e), `bDestroyed: bool`; dispatcher `OnDestructibleDestroyed()`; `Demolish()` (once: `bDestroyed`, GameMode `SpawnExplosion(GetActorLocation, 0, 0, none, self, false)`, `SetActorHiddenInGame(true)`, `SetActorEnableCollision(false)`, dispatcher, log `DF: destructible demolished <name>`). Event `ReceiveAnyDamage(Damage, DamageType, InstigatedBy, DamageCauser)`: ignore when destroyed; when `bExplosivesOnly` and `DamageType` does not cast to `BP_DFExplosiveDamage` ignore; else `Health = Max(0, Health − Damage)`, `Demolish` at 0.
- Produces in `df_build_test_track.py`: a second `BP_DFTrackSpline` labelled `Shortcut` (`bIsMainTrack` False; open spline, points `[p1, mid, p2]` at Z −2 where `p1`/`p2` are the main spline's locations at distances `L*0.25 + 1500` and `L*0.5 − 1500`, `mid` the midpoint moved 35 % toward the centroid of `TRACK_POINTS`; `set_closed_loop(False, True)`, `spline_has_been_edited`, touch `RoadWidth`; raise unless `GeneratedMeshCount ≥ 1`), and one `BP_DFDestructible` labelled `Rock` at the shortcut's 1000 cm transform, yaw from the spline tangent, scale (4, 16, 4), Z = −2 + 200. The crate distance check also covers the shortcut spline. `L_DF_FunctionalTests` gets the same.

- [ ] **Step 1: Write the failing tests** —
  - `FT_DFDestructible_ExplosivesOnlyOpensRoad` ("A rock ignores plain damage, is demolished by explosive damage, and then neither blocks nor shows."): spawn a `BP_DFDestructible` at + (0, 800, 0); delay 0.5; `damage(rock, 100)` (default damage type) → `Health` 60, `bDestroyed` false; `ApplyDamage` with `DamageTypeClass` = `BP_DFExplosiveDamage` class, 60 → `bDestroyed` true, `bHidden` true, `GetActorEnableCollision` false (read the actor property `bActorEnableCollision`... use the pure `Actor.GetActorEnableCollision()` call).
  - `FT_DFTrack_ShortcutIsOpenSplineOnTrack` ("The level's shortcut is a second track actor with road pieces, counted as on-track, with a rock on it."): `GetAllActorsOfClass(BP_DFTrackSpline)` length == 2; the one with `bIsMainTrack` false has `GetGeneratedMeshCount` > 0 and `Spline.IsClosedLoop` false; GameMode `IsOnAnyTrack(shortcut.GetTransformAtDistance(length/2).Location)` true; `GetAllActorsOfClass(BP_DFDestructible)` length == 1.

- [ ] **Step 2: Generate and apply the tests** — expected FAILED.

- [ ] **Step 3: Implement** per Interfaces; rebuild both levels (`OK` line reports the shortcut's piece count). The existing track tests pick `GetAllActorsOfClass(BP_DFTrackSpline)[0]` (`main_track(t)` in `tests.py`): change the helper to read the GameMode's `MainTrack` variable so a second track actor cannot be chosen.

- [ ] **Step 4: Generate, apply, build, run** — apply `only=["BP_DFDestructible"] + tests`; build; `-Filter "...FT_DFDestructible"` → `1 passed`; `-Filter "...FT_DFTrack"` → `3 passed` (two existing + one); `-Filter "...FT_DFOffTrack"` still green (a second track must not break the off-track rule).

- [ ] **Step 5: Ledger entry.**

---

### Task 7: HUD item row, effect line, pickup flash, screenshots

**Files:**
- Modify: `tools/bpgen/graphs/hud.py`, `tools/bpgen/graphs/tests.py` (`screenshot_test`), `tools/bpgen/graphs/tests_items.py`

**Interfaces:**
- Consumes: `Inventory`, `SelectedSlot`, `LastPickupTime`, `LastPickupType` on the racer; `GetItemInfo`; `BoostRemaining`, `ShieldRemaining` on the vehicle.
- Produces in `WBP_DFRaceHUD`: widgets `ItemPanel` (VerticalBox, anchors (0.5, 1, 0.5, 1), alignment (0.5, 1), position (0, −120), auto size) holding `EffectText` (TextBlock 22, amber, centre), `ItemRow` (HorizontalBox) with `Slot0Text`, `Slot1Text`, `Slot2Text` (TextBlock 24, padding (12, 0, 12, 0)), and `ItemHintText` (TextBlock 18, `[Q] USE   [R] NEXT`, centre); functions `SetAmber(Target: TextBlock, bAmber: bool)` (amber `(1, 0.75, 0.2)` else white, same shape as `SetRed`), `RefreshItems(Racer: BPC_DFRacer, Car: BP_DFVehicle)` (slot i text = `<Name> x<Charges>` or `-`; `SetAmber` on the selected, filled slot; `EffectText` = `BOOST` / `SHIELD n.n` / `BOOST  SHIELD n.n` / `` from the car when valid; `ItemHintText` shown only when `Car` is valid); `Refresh` calls `RefreshItems` after `RefreshCar`/`RefreshFoot`; `RefreshWarning` adds `PICKED UP <Name>` while `LastPickupTime ≥ 0 and now − LastPickupTime < 1.5`, below the checkpoint flash in the `pick` chain.
- `screenshot_test`: after `race_context`, `GrantItem(pc, Shield, 1)` and `GrantItem(pc, Bomb, 1)` before the first shot so the item row shows.

- [ ] **Step 1: Write the failing test** — `FT_DFHUD_ItemRowShowsInventory` ("The HUD item row lists the racer's slots and marks empty ones."): `race_context`; `GrantItem(pc, Shield, 1)` twice; delay 0.5; the single `WBP_DFRaceHUD` widget's `Slot0Text` reads `SHIELD x2` and `Slot1Text` reads `-` (reuse the `widgets()`/`GetText`/`EqualEqual_StrStr` pattern of `FT_DFHUD_SummaryShownAtRaceEnd`).

- [ ] **Step 2: Generate and apply the test** — expected FAILED (unknown widgets).

- [ ] **Step 3: Implement** per Interfaces.

- [ ] **Step 4: Generate, apply, build, run** — apply `only=["WBP_DFRaceHUD", "FT_DFHUD_ItemRowShowsInventory", "FT_DFZZ_Screenshots"]`; build; `-Filter "...FT_DFHUD"` → `2 passed`. In the editor (not headless) run `FT_DFZZ_Screenshots` through `python tools/ue_remote.py --console "Automation RunTests Project.Functional Tests./Game/DeadFire/Tests/L_DF_FunctionalTests.FT_DFZZ_Screenshots"` with `EditorPerformanceSettings.throttle_cpu_when_not_foreground` False, wait, then `unreal.EditorLevelLibrary.editor_end_play()`; view `comp4900sef/Saved/Screenshots/Windows/ScreenShot*.png` and check the item row, amber selection and hint in the car shot.

- [ ] **Step 5: Ledger entry.**

---

### Task 8: Full verification, documentation, handoff

**Files:**
- Modify: `README.md`, `docs/superpowers/playtest-checklist.md`, `docs/superpowers/specs/2026-10-20-dead-fire-design.md` (§6 table rows for the five new Blueprints and the two data types; §7 row `3 — Items & damage (done 2026-10-30)` with the plan path), this plan (execution record at the top), memory file `dead-fire-phase-log.md`.

- [ ] **Step 1: Full pipeline from scratch** — `generate_all.py`; full `apply_all` (no `only`) → `APPLY OK: 57 manifests, 0 failed` (39 + 5 Blueprints + 2 data + 15 tests... count the folders under `comp4900sef/Script/paste` and quote the real number); build levels; `verify_all` → `VERIFY PASSED`; full `run_tests.ps1` → `39 passed, 0 failed, 39 found`.

- [ ] **Step 1b: Starter Content closure** — in the editor, for each Starter Content asset the new Blueprints reference (the list in Global Constraints), collect the recursive hard dependencies with `unreal.AssetRegistryHelpers.get_asset_registry().get_dependencies(package_name, unreal.AssetRegistryDependencyOptions(include_hard_package_references=True))`, map package names to `.uasset` paths, and `git add -f` those files (expected: a few dozen files, under 20 MB); record the list in the ledger and the README's content paragraph.

- [ ] **Step 2: README** — "Current state" becomes Phase 3 (crates on foot, three-slot inventory, Q/R, the five items, explosions and tire blasts, wreck effects, the rock and shortcut); controls table rows `Use item | Q | X` and `Next item | R / wheel up | D-pad right`; "Where the logic lives" rows for `BP_DFLootBox`, `BP_DFBomb`, `BP_DFProjectile`, `BP_DFDestructible`, `BP_DFExplosiveDamage`, `E_DFItemType`, `S_DFItemStack` (owner Chong Tsz Ho for items per the base design §6; others TBD); tests paragraph mentions the new groups; hooks list gains the four dispatchers.

- [ ] **Step 3: Playtest checklist** — add lines 23–32: walk to a crate on foot (row shows the item, `PICKED UP` flash), a car driving over a crate collects nothing, Q from the car uses it (boost shove, shield line, bomb drops behind and explodes on the second car, gun hits, rocket flies and explodes), R cycles, bomb or rocket at the rock opens the shortcut and driving it starts no off-track countdown, a wreck explodes and smokes, Retry clears the row.

- [ ] **Step 4: Design doc and plan record** — base design §6/§7 as listed; execution record at the top of this plan (what differed from the task text); update the memory file for Phase 3 (done, test count, gotchas learned).

- [ ] **Step 5 (person): playtest** — the checklist lines above in `L_TestTrack`.

- [ ] **Step 6: Final report** — tree status, the commit command (`git add -A && git commit -m "Phase 3: items, loot boxes, explosions, destructible shortcut; 39 functional tests"`), and the rulings list from the ledger.
